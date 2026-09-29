"""Chay cung input voi 2 label baseline/candidate, ghi trace ID + version thuc te.

Khong in secret. Ket qua -> submission/evidence/prompt-traces.json
Dung bien moi truong tam thoi, khong sua file .env.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv()

import app.agent as agent_module
from app.agent import LabAgent
from app.tracing import get_langfuse_client

QUESTION = "What is the refund policy?"
RUNS = [
    {"label": "baseline", "correlation_id": "req-ba5e11ne"},
    {"label": "candidate", "correlation_id": "req-cand1da7"},
]

results = []
for item in RUNS:
    os.environ["LANGFUSE_PROMPT_LABEL"] = item["label"]
    client = get_langfuse_client()
    try:
        client.clear_prompt_cache()
    except Exception:
        pass
    captured: dict = {}

    orig_update = client.update_current_span

    def wrapped_update(*args, **kwargs):
        try:
            captured["trace_id"] = client.get_current_trace_id()
        except Exception:
            pass
        captured["span_kwargs"] = {
            "metadata": kwargs.get("metadata"),
            "version": kwargs.get("version"),
        }
        return orig_update(*args, **kwargs)

    client.update_current_span = wrapped_update  # type: ignore[method-assign]
    agent_module.get_langfuse_client = lambda: client  # type: ignore[assignment]

    last_meta: dict = {}
    for attempt in range(4):
        captured.clear()
        agent = LabAgent()
        agent.run(
            user_id="student-01",
            feature="qa",
            session_id="prompt-version-check",
            message=QUESTION,
            correlation_id=item["correlation_id"],
        )
        client.flush()
        last_meta = ((captured.get("span_kwargs") or {}).get("metadata") or {})
        if last_meta.get("prompt_source") == "langfuse":
            break
        try:
            client.clear_prompt_cache()
        except Exception:
            pass
    meta = last_meta
    results.append(
        {
            "label": item["label"],
            "correlation_id": item["correlation_id"],
            "trace_id": captured.get("trace_id"),
            "prompt_name": meta.get("prompt_name"),
            "prompt_label": meta.get("prompt_label"),
            "prompt_version": meta.get("prompt_version"),
            "prompt_source": meta.get("prompt_source"),
            "span_version": (captured.get("span_kwargs") or {}).get("version"),
        }
    )
    print(
        f"label={item['label']} trace={captured.get('trace_id')} "
        f"prompt_version={meta.get('prompt_version')} source={meta.get('prompt_source')}"
    )

out_path = REPO_ROOT / "submission" / "evidence" / "prompt-traces.json"
out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"Wrote {out_path}")
