"""Render dashboard CP2 tu du lieu that data/logs.jsonl theo contract config/dashboard.yaml.

Khong dung du lieu gia. Ket qua: submission/evidence/dashboard.html + dashboard-values.json
Chay tren Windows:  python scripts/render_dashboard.py
Xem: mo file HTML bang trinh duyet (double-click).
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
CONFIG_PATH = REPO_ROOT / "config" / "dashboard.yaml"
OUT_HTML = REPO_ROOT / "submission" / "evidence" / "dashboard.html"
OUT_JSON = REPO_ROOT / "submission" / "evidence" / "dashboard-values.json"


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def main() -> int:
    contract = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["dashboard"]
    panels = {p["id"]: p for p in contract["panels"]}
    lines = [
        json.loads(line)
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    req = [e for e in lines if e.get("event") == "request_received"]
    res = [e for e in lines if e.get("event") == "response_sent"]
    fail = [e for e in lines if e.get("event") == "request_failed"]

    lat = [float(e.get("latency_ms", 0)) for e in res]
    ttf = [float(e.get("ttft_ms", 0)) for e in res]
    latency = {
        "p50": round(percentile(lat, 50), 1),
        "p95": round(percentile(lat, 95), 1),
        "p99": round(percentile(lat, 99), 1),
        "ttft_p95": round(percentile(ttf, 95), 1),
        "n": len(res),
    }

    def minute_key(e: dict) -> str:
        ts = parse_ts(str(e.get("ts", "")))
        return ts.strftime("%Y-%m-%dT%H:%M") if ts else "unknown"

    traffic_by_min = dict(sorted(Counter(minute_key(e) for e in req).items()))
    span_min = max(1, len(traffic_by_min))
    traffic = {
        "count": len(req),
        "rate_per_minute": round(len(req) / span_min, 3),
        "by_minute": traffic_by_min,
    }

    err_rate = round(len(fail) / max(1, len(req)) * 100, 3)
    tool_events = res + fail
    tool_known = [e for e in tool_events if e.get("tool_success") is not None]
    tool_ok = [e for e in tool_known if e.get("tool_success") is True]
    errors = {
        "error_rate_pct": err_rate,
        "failed": len(fail),
        "received": len(req),
        "count_by_error_type": dict(Counter(str(e.get("error_type")) for e in fail)),
        "tool_success_rate_pct": round(len(tool_ok) / max(1, len(tool_known)) * 100, 2)
        if tool_known
        else 0.0,
    }

    cost_by_min = {
        m: round(sum(float(e.get("cost_usd", 0)) for e in res if minute_key(e) == m), 6)
        for m in sorted({minute_key(e) for e in res})
    }
    cost = {
        "total": round(sum(float(e.get("cost_usd", 0)) for e in res), 6),
        "sum_by_minute": cost_by_min,
    }
    tokens = {
        "tokens_in_total": int(sum(int(e.get("tokens_in", 0)) for e in res)),
        "tokens_out_total": int(sum(int(e.get("tokens_out", 0)) for e in res)),
    }
    quality = {
        "mean": round(
            sum(float(e.get("quality_score", 0)) for e in res) / max(1, len(res)), 4
        )
        if res
        else 0.0,
        "n": len(res),
    }
    good = sum(1 for e in res if float(e.get("latency_ms", 10**9)) <= 3000)
    sli = {
        "good": good,
        "total": len(req),
        "sli_pct": round(good / max(1, len(req)) * 100, 3),
    }

    values = {
        "source": "data/logs.jsonl",
        "lines": len(lines),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latency": latency,
        "traffic": traffic,
        "errors": errors,
        "cost": cost,
        "tokens": tokens,
        "quality": quality,
        "sli": sli,
    }
    OUT_JSON.write_text(json.dumps(values, indent=2), encoding="utf-8")

    def check(pid: str, agg: str, val: float) -> str:
        th = panels[pid]["threshold"]
        op, lim = th["operator"], th["value"]
        ok = (val <= lim) if op == "lte" else (val >= lim)
        return f"{'ĐẠT' if ok else 'VƯỢT'} (ngưỡng {op} {lim})"

    rows = "".join(
        f"<tr><td>{pid}</td><td>{panels[pid]['title']}</td>"
        f"<td>{panels[pid]['unit']}</td><td>{panels[pid]['threshold']}</td></tr>"
        for pid in ["latency", "traffic", "errors", "cost", "tokens", "quality"]
    )
    html = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<title>{contract['title']}</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#111}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}}
.panel{{border:1px solid #ccc;border-radius:8px;padding:12px}}
.pass{{color:#0a7a2f;font-weight:bold}}.fail{{color:#b00020;font-weight:bold}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:4px 8px;font-size:13px}}
code{{background:#f4f4f4;padding:1px 4px}}</style></head><body>
<h1>{contract['title']}</h1>
<p>Nguồn: <code>data/logs.jsonl</code> ({len(lines)} dòng, {len(req)} request_received, {len(res)} response_sent, {len(fail)} request_failed).
Time range: {contract['time_range_minutes']} phút · Refresh: {contract['refresh_seconds']}s · Tạo lúc: {values['generated_at']}</p>
<h2>Contract (config/dashboard.yaml)</h2>
<table><tr><th>ID</th><th>Panel</th><th>Đơn vị</th><th>Threshold</th></tr>{rows}</table>
<div class="grid">
<div class="panel"><h3>1. Latency percentiles and TTFT (ms)</h3>
<p>P50 <b>{latency['p50']}</b> · P95 <b>{latency['p95']}</b> · P99 <b>{latency['p99']}</b> · TTFT P95 <b>{latency['ttft_p95']}</b> (n={latency['n']})</p>
<p class="{'pass' if latency['p95'] <= panels['latency']['threshold']['value'] else 'fail'}">{check('latency', 'p95', latency['p95'])}</p></div>
<div class="panel"><h3>2. Request traffic (requests_per_minute)</h3>
<p>Tổng <b>{traffic['count']}</b> · Rate <b>{traffic['rate_per_minute']}</b>/phút trên {span_min} phút có request</p>
<p class="{'pass' if traffic['rate_per_minute'] >= panels['traffic']['threshold']['value'] else 'fail'}">{check('traffic', 'rate_per_minute', traffic['rate_per_minute'])}</p>
<p>Theo phút: <code>{json.dumps(traffic['by_minute'])}</code></p></div>
<div class="panel"><h3>3. Error rate and retrieval success (percent)</h3>
<p>Error rate <b>{errors['error_rate_pct']}%</b> ({errors['failed']}/{errors['received']}) · Retrieval success <b>{errors['tool_success_rate_pct']}%</b> · Breakdown <code>{json.dumps(errors['count_by_error_type'])}</code></p>
<p class="{'pass' if errors['error_rate_pct'] <= panels['errors']['threshold']['value'] else 'fail'}">{check('errors', 'error_rate_pct', errors['error_rate_pct'])}</p></div>
<div class="panel"><h3>4. Cost over time (usd)</h3>
<p>Tổng <b>${cost['total']}</b></p>
<p class="{'pass' if cost['total'] <= panels['cost']['threshold']['value'] else 'fail'}">{check('cost', 'total', cost['total'])}</p>
<p>Theo phút: <code>{json.dumps(cost['sum_by_minute'])}</code></p></div>
<div class="panel"><h3>5. Input and output tokens (tokens)</h3>
<p>In <b>{tokens['tokens_in_total']}</b> · Out <b>{tokens['tokens_out_total']}</b> · Tổng <b>{tokens['tokens_in_total'] + tokens['tokens_out_total']}</b></p></div>
<div class="panel"><h3>6. Quality proxy (score_0_to_1)</h3>
<p>Mean <b>{quality['mean']}</b> (n={quality['n']})</p>
<p class="{'pass' if quality['mean'] >= panels['quality']['threshold']['value'] else 'fail'}">{check('quality', 'mean', quality['mean'])}</p></div>
</div>
<h2>SLO nhanh</h2>
<p>Fast successful (latency ≤ 3000ms): <b>{sli['good']}/{sli['total']} = {sli['sli_pct']}%</b> (xem chi tiết tại <code>config/slo.yaml</code>).</p>
</body></html>"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"N={len(lines)} req={len(req)} res={len(res)} fail={len(fail)}")
    print(f"latency p50/p95/p99={latency['p50']}/{latency['p95']}/{latency['p99']} ttft_p95={latency['ttft_p95']}")
    print(f"error_rate={errors['error_rate_pct']}% retrieval_success={errors['tool_success_rate_pct']}%")
    print(f"cost_total={cost['total']} tokens_in={tokens['tokens_in_total']} tokens_out={tokens['tokens_out_total']} quality={quality['mean']}")
    print(f"SLI={sli['sli_pct']}%  Wrote {OUT_HTML.name} + {OUT_JSON.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
