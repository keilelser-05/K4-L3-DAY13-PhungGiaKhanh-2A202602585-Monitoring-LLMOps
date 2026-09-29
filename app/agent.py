from __future__ import annotations

import contextlib
import os
import time
from dataclasses import dataclass
from typing import Any

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .prompt_management import resolve_prompt
from .tracing import get_langfuse_client, observe, propagate_attributes, tracing_enabled


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    ttft_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float


class _NoopObservation:
    def update(self, **kwargs: Any) -> None:
        return None


def _child_observation(client: Any, **kwargs: Any):
    """Mở child observation; fallback no-op khi client test không có API v4."""
    start = getattr(client, "start_as_current_observation", None)
    if callable(start):
        try:
            return start(**kwargs)
        except Exception:
            pass
    return contextlib.nullcontext(_NoopObservation())


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5") -> None:
        self.model = model
        self.llm = FakeLLM(model=model)

    @observe(name="lab-agent-run", as_type="agent", capture_input=False, capture_output=False)
    def run(
        self,
        user_id: str,
        feature: str,
        session_id: str,
        message: str,
        correlation_id: str,
    ) -> AgentResult:
        langfuse_client = get_langfuse_client()
        with propagate_attributes(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, self.model],
            trace_name="day13-agent-request",
            environment=os.getenv("APP_ENV", "dev"),
            metadata={
                "feature": feature,
                "model": self.model,
                "correlation_id": correlation_id,
            },
        ):
            started = time.perf_counter()
            query_preview = summarize_text(message)
            with _child_observation(
                langfuse_client,
                name="retrieval",
                as_type="retriever",
                input={"query_preview": query_preview},
                metadata={"doc_count": 0, "query_preview": query_preview},
            ) as retrieval_obs:
                docs = retrieve(message)
                retrieval_obs.update(
                    output={"doc_count": len(docs)},
                    metadata={
                        "doc_count": len(docs),
                        "query_preview": query_preview,
                        "doc_previews": [summarize_text(doc) for doc in docs],
                    },
                )
            prompt = resolve_prompt(
                langfuse_client,
                feature=feature,
                docs=docs,
                message=message,
                enabled=tracing_enabled(),
            )
            is_managed = prompt.source == "langfuse" and prompt.managed_prompt is not None
            langfuse_client.update_current_span(
                metadata={
                    "doc_count": len(docs),
                    "query_preview": query_preview,
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                    "prompt_version": prompt.version,
                    "prompt_source": prompt.source,
                    "prompt_fetch_error": prompt.fetch_error or "",
                },
                version=prompt.version if is_managed else None,
            )
            linked_prompt = prompt.managed_prompt if is_managed else None
            with propagate_attributes(prompt=linked_prompt):
                generation_input = {
                    "query_preview": query_preview,
                    "doc_count": len(docs),
                    "prompt_name": prompt.name,
                    "prompt_label": prompt.label,
                }
                generation_kwargs: dict[str, Any] = {
                    "name": "llm-generate",
                    "as_type": "generation",
                    "model": self.model,
                    "input": generation_input,
                    "metadata": {
                        "feature": feature,
                        "model": self.model,
                        "prompt_name": prompt.name,
                        "prompt_label": prompt.label,
                        "prompt_source": prompt.source,
                    },
                }
                if is_managed:
                    generation_kwargs["prompt"] = prompt.managed_prompt
                    generation_kwargs["version"] = prompt.version
                with _child_observation(langfuse_client, **generation_kwargs) as generation_obs:
                    response = self.llm.generate(prompt.text)
                    cost_usd = self._estimate_cost(
                        response.usage.input_tokens, response.usage.output_tokens
                    )
                    usage_details = {
                        "input": response.usage.input_tokens,
                        "output": response.usage.output_tokens,
                        "prompt_tokens": response.usage.input_tokens,
                        "completion_tokens": response.usage.output_tokens,
                        "total": response.usage.input_tokens + response.usage.output_tokens,
                    }
                    cost_details = {"total": cost_usd}
                    generation_update: dict[str, Any] = {
                        "output": {"answer_preview": summarize_text(response.text)},
                        "metadata": {
                            "feature": feature,
                            "model": self.model,
                            "prompt_name": prompt.name,
                            "prompt_label": prompt.label,
                            "prompt_source": prompt.source,
                        },
                        "model": self.model,
                        "usage_details": usage_details,
                        "cost_details": cost_details,
                    }
                    if is_managed:
                        generation_update["prompt"] = prompt.managed_prompt
                        generation_update["version"] = prompt.version
                    generation_obs.update(**generation_update)
            quality_score = self._heuristic_quality(message, response.text, docs)
            latency_ms = int((time.perf_counter() - started) * 1000)

        metrics.record_request(
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            ttft_ms=response.ttft_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
        )

    def _estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        input_cost = (tokens_in / 1_000_000) * 3
        output_cost = (tokens_out / 1_000_000) * 15
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
