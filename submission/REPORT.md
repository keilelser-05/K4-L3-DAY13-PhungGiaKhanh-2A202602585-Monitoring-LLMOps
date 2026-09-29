# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phùng Gia Khánh
- **MSSV:** 2A202602585
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/keilelser-05/K4-L3-DAY13-PhungGiaKhanh-2A202602585-Monitoring-LLMOps
- **Commit SHA cuối:** `bca4dffae1ebec1132653858fa88d2b175e59080` (commit nội dung đầy đủ; HEAD sau commit này chỉ thêm đúng dòng SHA này)
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602585`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.json` |
| PII redaction | `evidence/05-pii-redaction.json` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/dashboard.png` |
| Incident metric | `evidence/12-incident-metric.json` |
| Incident log | `evidence/13-incident-log.json` |
| Incident trace | `evidence/14-incident-trace.json` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 (`evidence/02-log-validator.txt`, 62 records, 0 PII leak) | đạt ngưỡng 80 |
| `validate_dashboard.py` | — (contract giữ nguyên từ đầu) | HỢP LỆ 6/6 (`evidence/03-dashboard-validator.txt`) | đủ 6 panel |
| `pytest` | — | 26 passed (`evidence/01-pytest.txt`) | |
| Số traces hợp lệ | — | 29 trace đầy đủ (root `lab-agent-run` + child `retrieval` + `generation`) trên tổng 50 root observations trong project cá nhân (yêu cầu ≥10) | đếm qua observations API v2 |
| Số PII leak | — | 0 (validator + quét `submission/`, `config/slo.yaml`, `config/alert_rules.yaml`, `docs/alerts.md`) | |
| Latency P95 / TTFT P95 | 1916.5 / 50.0 (trước challenge) | 2654.6 / 50.0 (sau challenge CP3) | P95 tăng do `rag_slow` |
| Retrieval success rate | 100% | 100% | 0 `request_failed` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `app/middleware.py:14` nhận `x-request-id` hoặc sinh `req-<8-hex>`, bind vào context và trả lại qua header `x-request-id`/`x-response-time-ms` (`app/middleware.py:21-22`).
- **Các metadata được ghi vào structured log:** `app/main.py:51-57` gắn `user_id_hash`, `session_id`, `feature`, `model`, `env` (cùng `correlation_id` từ middleware) vào mọi log của request.
- **Cách bảo đảm PII được scrub trước khi ghi:** `app/pii.py` che email/phone/CCCD/thẻ; `app/logging_config.py:53-55` chạy `scrub_event` TRƯỚC `JsonlFileProcessor`/JSONRenderer nên PII không bao giờ xuống file.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100, 0 PII leak (`evidence/02-log-validator.txt`); mẫu log đỏ đã che: `evidence/05-pii-redaction.json`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:** `day13-chat`
- **Version/label baseline:** version `1`, labels `baseline` + `production` (ban đầu và sau rollback)
- **Version/label candidate:** version `2`, label `candidate` (v2 chỉ thêm dòng trình bày ngắn gọn ≤ 3 câu, giữ nguyên 3 biến `{{feature}}`, `{{docs}}`, `{{message}}`)
- **Trace ID của mỗi version:** cùng câu hỏi `What is the refund policy?` — `baseline` → trace `be8e0229e15afc02df36a02e79c32344` (version `1`, `prompt_source=langfuse`, corr `req-ba5e11ne`); `candidate` → trace `2664e5fa2f119fa89d2fdf163a70c673` (version `2`, corr `req-cand1da7`); `production=v2` → trace `e8147d13042f57b6e379e86d691d680b` (version `2`, corr `req-prod0v2x`). Chi tiết: `evidence/prompt-traces.json`
- **Cách promote và rollback `production`:** `update_prompt(day13-chat, v2, [candidate, production])` để promote (verify `production → 2`), chạy 1 request kiểm chứng, rồi `update_prompt(day13-chat, v1, [baseline, production])` để rollback (verify `production → 1`, `candidate → 2`). Trước/sau lưu tại `evidence/prompt-rollback.json`; ảnh UI Langfuse: `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** nguồn `data/logs.jsonl` thật (25 req_received/25 response_sent/0 request_failed, đã gồm 5 req challenge CP3). Render local: `python scripts/render_dashboard.py` → `evidence/dashboard.html` + `evidence/dashboard-values.json` (xem: `docs/DASHBOARD_LOCAL.md`). 6 panel đúng `config/dashboard.yaml`: latency P50 404.0/P95 2654.6/P99 3533.6/TTFT P95 50.0ms; traffic 25 req; errors 0.0% + retrieval success 100.0%; cost $0.049233; tokens in 851/out 3112; quality mean 0.872. Validator `HỢP LỆ: 6/6 panel` (`evidence/03-dashboard-validator.txt`). Ảnh runtime: `evidence/dashboard.png`.
- **SLO và lý do chọn:** giữ `fast_successful_requests` 99.5%/28d (`config/slo.yaml`); baseline trước challenge đạt SLI 100% (20/20 latency≤3000ms). Sau challenge CP3, SLI cửa sổ đo là 96.0% (24/25, 1 req 3811ms vượt ngưỡng) — vượt error budget 0.5%, đúng bản chất incident `rag_slow` và là bằng chứng alert `SlowResponsesHighP95` cần thiết.
- **Cách tính error budget:** budget 0.5% = tối đa 5 bad/1000 req (50 bad/10000 req/28 ngày). Trên mẫu đo 25 request, mức cho phép chỉ 0.125 bad nên 1 request lỗi (4%) đã vượt ngân sách của mẫu này.
- **Ba alert và runbook tương ứng:** `config/alert_rules.yaml` — `SlowResponsesHighP95` (warning, P95>3000ms giữ 5m, owner backend-oncall), `RetrievalFailuresHigh` (critical, error_rate>2% hoặc retrieval_success<90% giữ 5m, owner backend-oncall), `CostQualityDegraded` (warning, vượt pace 2.5 USD/ngày hoặc quality<0.75 giữ 15m, owner llm-ops); cả ba kênh Slack `#l3a-incidents`, runbook tại `docs/alerts.md#alert-1..3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4, incident `rag_slow`)
- **Khoảng thời gian điều tra:** 2026-09-29T09:48:20Z → 09:48:38Z (5 queries, feature `monitoring`, concurrency 5)
- **Triệu chứng từ metrics:** 4 giá trị server-side được lưu là 2652–3811 ms (sàn ~2650ms, vượt xa baseline P95 ~1713ms); client đo 5 request 9.8–15.1s do xếp hàng concurrency. Chi tiết: `evidence/12-incident-metric.json`
- **Log line và correlation ID liên quan:** `req-fb6f1112` — `response_sent` latency_ms 3811, ttft 50, quality 0.8, cost 0.00201, tool_success true. Dòng log: `evidence/13-incident-log.json`
- **Trace ID và span gây ảnh hưởng:** trace `a84d4143887304263d4d9567670c31d5` — root `lab-agent-run` 3.811s, span `retrieval` 2.502s (66% trace), `llm-generate` 0.151s. Spans: `evidence/14-incident-trace.json`
- **Root cause:** span `retrieval` chậm do `rag_slow` (sleep 2.5s trong `mock_rag.py:retrieve` khi `STATE["rag_slow"]=True`); generation bình thường.
- **Fix action:** đã disable incident (`rag_slow → false`, verify qua `/health`).
- **Preventive measure:** alert `SlowResponsesHighP95` (P95>3000ms giữ 5m, Slack `#l3a-incidents`, runbook `docs/alerts.md#alert-1`) + thêm retrieval timeout/circuit-breaker.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** bọc `start_as_current_observation` trong `_child_observation()` có fallback no-op (`app/agent.py:33-41`) để trace thật trên Langfuse nhưng tests cũ (client giả không có API v4) vẫn pass; chỉ link `prompt`/`version` khi `source == "langfuse"` để không ghi version giả lúc fallback.
- **Một lỗi/blocker đã gặp:** API chạy thiếu `--env-file .env` nên `/health` báo `tracing_enabled: false` — log vẫn ghi nhưng không có trace; tiếp đó Langfuse trả `410 LEGACY_API_UNAVAILABLE` cho endpoint traces cũ.
- **Cách tìm nguyên nhân và xử lý:** đối chiếu `/health` giữa 2 cách chạy API rồi cố định lệnh trong `docs/DASHBOARD_LOCAL.md`; chuyển truy vấn trace sang observations API v2 (`trace_id` + `correlation_id` trong metadata).
- **Cách hiểu luồng Metrics → Logs → Traces:** dashboard chỉ ra P95 vượt ngưỡng và khoảng thời gian (CP3: 2652–3811ms); lọc log theo khoảng đó lấy `correlation_id` bất thường (`req-fb6f1112`); mở trace cùng ID thấy span `retrieval` 2.502s/3.811s là nguyên nhân.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** prompt version cho biết request dùng template nào và rollback an toàn (`production` v2→v1 đã verify); token/cost phát hiện `cost_spike`; SLO 99.5% + error budget biến incident thành con số (CP3: 1/25 bad = 4% vượt budget 0.5%).
- **Điều quan trọng nhất đã học:** validator chỉ kiểm tra contract — bằng chứng runtime (trace, log, dashboard có dữ liệu thật) mới chứng minh hệ thống quan sát được.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** còn thiếu ảnh `06-trace-list.png`, `07-trace-waterfall.png`, `08-trace-metadata.png` (chụp thủ công trên Langfuse); `dashboard.png` là ảnh bản render cũ (10 req) nên chụp lại từ `dashboard.html` mới; mục §4 còn trống; SHA/URL nộp chờ commit cuối.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối (hiện còn thay đổi chưa commit — commit rồi cập nhật SHA ở §1).
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối (thiếu `06`, `07`, `08`; `dashboard.png` cần chụp lại bản mới).
- [x] Incident evidence nối đúng metric → log → trace (`12/13/14-incident-*.json` cùng `req-fb6f1112`).
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret (đã quét: không lộ key; nhưng ảnh prompt hiện tên project `My Project` — đổi/tạo đúng `day13-k4-l3a-2A202602585` nếu quy định chấm tên).
- [ ] Repository chạy lại được theo README (26 passed + 2 validators mới chỉ chứng minh code hiện tại đúng — chưa chạy lại toàn bộ README từ đầu đến cuối trên môi trường sạch).
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác (đã quét `submission/`, SLO, alerts, runbook).
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
