# Xem dashboard CP2 trên Windows (3 bước)

Nguồn duy nhất: `data/logs.jsonl` thật do API ghi. Không dùng dữ liệu giả.

## 1. Tạo dữ liệu thật

```powershell
uvicorn app.main:app --port 8000 --env-file .env
python scripts/load_test.py --concurrency 5
```

> Bắt buộc có `--env-file .env`: nếu thiếu, API vẫn chạy nhưng `/health` báo
> `tracing_enabled: false`, không tạo Langfuse trace và prompt rơi về local-fallback.

## 2. Render dashboard

```powershell
python scripts/render_dashboard.py
python scripts/validate_dashboard.py
```

## 3. Xem

Mở bằng trình duyệt (double-click):

```text
submission\evidence\dashboard.html
```

Số liệu thô: `submission\evidence\dashboard-values.json`.
Đối chiếu 6 panel với `config/dashboard.yaml` (time range 60 phút, refresh 30s, đơn vị + threshold trên mỗi panel).
Chụp màn hình trình duyệt lưu `submission\evidence\11-dashboard-overview.png`.
