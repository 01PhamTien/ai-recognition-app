# Bàn giao TV2-Sang — issue #1

Nhánh: `feat/backend-nhan-dien-anh`.

## Đã triển khai

- FastAPI, GET /health, GET /ready và /metrics.
- POST /jobs nhận JPEG/PNG, kiểm tra MIME, đuôi, nội dung, byte và pixel.
- GET /jobs/{job_id} theo hợp đồng [API cho TV3](API.md).
- PostgreSQL lưu job, trạng thái, metadata và kết quả.
- Redis Streams consumer group, outbox, lease, ACK sau commit và nhận lại pending.
- Worker MobileNetV2 ONNX CPU, model/nhãn có version và SHA256.
- Biến môi trường, log JSON stdout, metrics cho API và worker.
- Docker Compose và hướng dẫn chạy/test trên Windows.
- Không đưa trọng số model, ảnh upload hoặc secret vào Git.

## Bằng chứng kiểm thử

Đã chạy trên Windows Python 3.13.2:

```powershell
$env:RUN_INTEGRATION_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -v
Remove-Item Env:RUN_INTEGRATION_TESTS
```

Kết quả: **32 passed**, gồm 2 integration test PostgreSQL/Redis/ONNX thật.
Có 1 cảnh báo Starlette về httpx trong TestClient, không làm test thất bại.

Đã build và khởi động stack Linux container Python 3.12:

```powershell
docker compose up -d --build --wait --wait-timeout 180
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1
```

Kết quả: API, worker, PostgreSQL và Redis đều healthy; job mẫu trả completed,
có 5 dự đoán từ model thật; health, readiness và metrics của hai service trả 200.
Đã parse 30 dòng log API/worker thành JSON và kiểm tra timestamp, service, message.

Smoke dùng ảnh màu tự sinh để kiểm tra đường đi dữ liệu, không đánh giá độ chính xác
nhận diện. Muốn kiểm tra ảnh thật, thêm tham số -ImagePath.

## Việc cần thành viên nhóm xác nhận

- TV3 xác nhận hợp đồng API và tích hợp frontend.
- Ít nhất một người khác review PR theo issue #1 trước khi merge.
- Chỉ đóng issue sau khi nhóm nghiệm thu; không tự merge PR.

Các giới hạn vận hành và lưu trữ đã ghi trong [ARCHITECTURE.md](ARCHITECTURE.md).
Jenkinsfile hiện có chỉ kiểm tra cấu trúc, chưa tự chạy bộ test TV2.

## File đã thêm hoặc sửa

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `README.md`
- `backend/Dockerfile`
- `backend/__init__.py`
- `backend/app/__init__.py`
- `backend/app/body_limit.py`
- `backend/app/config.py`
- `backend/app/database.py`
- `backend/app/errors.py`
- `backend/app/images.py`
- `backend/app/init_db.py`
- `backend/app/main.py`
- `backend/app/models.py`
- `backend/app/observability.py`
- `backend/app/queue.py`
- `backend/app/schemas.py`
- `backend/requirements-dev.txt`
- `backend/requirements.txt`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`
- `backend/tests/test_inference.py`
- `backend/tests/test_integration.py`
- `backend/tests/test_jobs.py`
- `backend/tests/test_logging.py`
- `backend/tests/test_worker.py`
- `compose.yaml`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/TV2-BAN-GIAO.md`
- `models/manifest.json`
- `pytest.ini`
- `scripts/download_model.py`
- `scripts/smoke.ps1`
- `worker/Dockerfile`
- `worker/__init__.py`
- `worker/consumer.py`
- `worker/inference.py`
- `worker/main.py`
- `worker/requirements.txt`
