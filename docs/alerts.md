# Template Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: SlowResponsesHighP95
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack `#l3a-incidents`
- SLI/SLO liên quan: `fast_successful_requests` 99.5% trong 28 ngày (`config/slo.yaml`); panel `latency` (`config/dashboard.yaml`, ngưỡng P95 ≤ 3000ms).
- Điều kiện và thời gian duy trì: P95 của `latency_ms` trên event `response_sent` > 3000ms liên tục 5 phút.
- Ảnh hưởng tới người dùng: trả lời chậm, trải nghiệm hội thoại bị đứt quãng; tương ứng practice `rag_slow`.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency, xác định khoảng P95 vượt ngưỡng và lấy 1 `correlation_id` chậm từ `data/logs.jsonl` (`event == "response_sent"`, sort `latency_ms` desc).
  2. Mở trace cùng `correlation_id` trong Langfuse, xem span `retrieval` có chiếm phần lớn thời gian không.
  3. Kiểm tra `python scripts/inject_incident.py` trạng thái incident và log `request_received`/`response_sent` quanh khoảng đó.
- Mitigation tạm thời: tắt practice incident nếu đang bật; giảm concurrency load test; nếu retrieval chậm kéo dài, chuyển traffic về fallback và báo backend-oncall.
- Owner: backend-oncall

## Alert 2

- Tên: RetrievalFailuresHigh
- Severity: critical
- Duration: 5m
- Kênh thông báo: Slack `#l3a-incidents`
- SLI/SLO liên quan: guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90` (`config/slo.yaml`); panel `errors` (`config/dashboard.yaml`).
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` HOẶC `retrieval_success_rate_pct < 90` liên tục 5 phút.
- Ảnh hưởng tới người dùng: request lỗi 500 hoặc câu trả lời thiếu ngữ cảnh; tương ứng practice `tool_fail`.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Errors, xem breakdown `error_type` và `tool_success_rate_pct`.
  2. Lọc `data/logs.jsonl` lấy 1 dòng `request_failed` kèm `correlation_id`, kiểm tra `error_type` và `tool_name`.
  3. Mở trace cùng `correlation_id`, xác định span `retrieval` báo lỗi.
- Mitigation tạm thời: tắt incident nếu do practice; kiểm tra vector store/dependency retrieval; bật fallback general answer và báo backend-oncall.
- Owner: backend-oncall

## Alert 3

- Tên: CostQualityDegraded
- Severity: warning
- Duration: 15m
- Kênh thông báo: Slack `#l3a-incidents`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5`, `quality_score_avg_min: 0.75` (`config/slo.yaml`); panel `cost` và `quality` (`config/dashboard.yaml`).
- Điều kiện và thời gian duy trì: nhịp `sum(cost_usd)` vượt pace ngân sách 2.5 USD/ngày HOẶC `mean(quality_score) < 0.75` liên tục 15 phút.
- Ảnh hưởng tới người dùng: chi phí bùng nổ hoặc câu trả lời kém chất lượng; tương ứng practice `cost_spike`.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Cost/Tokens/Quality, so `sum(cost_usd)`, `tokens_out` và `mean(quality_score)` với baseline (sau CP3: cost $0.049233/25 req, quality 0.872).
  2. Lọc `response_sent` có `tokens_out`/`cost_usd` cao bất thường, lấy `correlation_id`.
  3. Mở trace cùng ID, kiểm tra generation `usage_details`/`cost_details` và prompt version đang dùng.
- Mitigation tạm thời: giới hạn độ dài output/max tokens, rà soát prompt version mới deploy, rollback prompt nếu cần và báo llm-ops.
- Owner: llm-ops
