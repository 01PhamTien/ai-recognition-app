# AI Image Recognition — Application

Backend nhận diện ảnh của đồ án DevOps đề tài 10. TV2-Sang, [issue #1](https://github.com/01PhamTien/ai-recognition-app/issues/1):
FastAPI nhận ảnh, PostgreSQL lưu tác vụ/kết quả, Redis Streams chuyển việc cho
worker MobileNetV2 ONNX độc lập. API và worker có log JSON, health/readiness, metrics.

Hợp đồng bàn giao TV3: [docs/API.md](docs/API.md).
Schema, model, giấy phép và cơ chế phục hồi: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Bằng chứng kiểm thử và danh sách file: [docs/TV2-BAN-GIAO.md](docs/TV2-BAN-GIAO.md).

## Chạy toàn bộ bằng Docker trên Windows PowerShell

Cần Docker Desktop đang chạy với Linux containers. Chạy từ thư mục gốc repo:

```powershell
Set-Location 'D:\Sang IT\Ki7-Nam4\devops\ai-recognition-app'
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

Lần đầu cần mạng để tải image, thư viện và model (~14 MB).
Compose tự khởi tạo schema và tải model/nhãn/LICENSE có kiểm tra SHA256.
Model nằm trong named volume, không đưa file lớn vào Git.

| Dịch vụ | Địa chỉ từ Windows |
|---|---|
| Frontend | http://127.0.0.1:8081 |
| API / Swagger | http://127.0.0.1:8000/docs |
| API health / readiness | http://127.0.0.1:8000/health và /ready |
| API metrics | http://127.0.0.1:8000/metrics |
| Worker health / readiness | http://127.0.0.1:8001/health và /ready |
| Worker metrics | http://127.0.0.1:8001/metrics |
| PostgreSQL | localhost:5432, database ai_app, user app |
| Redis của dự án | localhost:16379 (trong mạng Compose là redis:6379) |

Redis dùng cổng 16379 để tránh trùng Redis có sẵn trên máy.
Nếu cổng khác bị chiếm, đổi FRONTEND_PORT, API_PORT, WORKER_PORT, POSTGRES_PORT hoặc REDIS_PORT
trong .env. Cập nhật URL dùng cho Python native/integration test theo cổng mới.
Mật khẩu `change_me` chỉ phục vụ chạy cục bộ; thay POSTGRES_PASSWORD và
DATABASE_URL tương ứng nếu cần. Các ký tự đặc biệt trong mật khẩu ở URL phải URL-encode.
Không commit .env thật.

Service `frontend` build trực tiếp từ thư mục `./frontend` trong cùng repository bằng Dockerfile của TV3. Nhờ vậy Frontend và Backend luôn được build từ cùng revision, không phụ thuộc vào commit hoặc nhánh GitHub bên ngoài.
Compose truyền `VITE_API_BASE_URL` rỗng khi build để trình duyệt gọi `/jobs`
cùng origin; Nginx chuyển tiếp tới `http://api:8000` trong mạng Compose.
Frontend đợi API healthy và dùng healthcheck `/health` có sẵn trong Dockerfile.

Kiểm tra health bằng PowerShell:

```powershell
$response = Invoke-WebRequest 'http://127.0.0.1:8000/health' -UseBasicParsing
$response.StatusCode
$response.Content
```

Kết quả: HTTP 200, `{"status":"ok"}`.

Kiểm tra toàn bộ luồng, tự tạo ảnh mẫu và đợi kết quả ONNX:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1
```

ExecutionPolicy chỉ áp dụng cho tiến trình kiểm tra này, không đổi cấu hình Windows.
Ảnh mẫu chỉ xác nhận luồng chạy được; không dùng để đánh giá độ chính xác model.
Để thử ảnh thật của bạn:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke.ps1 -ImagePath 'C:\duong-dan\anh.jpg'
```

Nếu đổi cổng, truyền thêm `-ApiUrl 'http://127.0.0.1:18000'` và
`-WorkerUrl 'http://127.0.0.1:18001'` tương ứng.

Upload thủ công bằng curl.exe (Windows PowerShell có alias curl, nên dùng đủ tên):

```powershell
$accepted = curl.exe --silent --show-error --fail-with-body -F "file=@C:\duong-dan\anh.png;type=image/png" http://127.0.0.1:8000/jobs | ConvertFrom-Json
Invoke-RestMethod ("http://127.0.0.1:8000" + $accepted.status_url)
```

POST trả 202 và job_id; poll tới completed/failed. Xem đầy đủ mã lỗi/schema trong
[API contract](docs/API.md). Swagger cũng hỗ trợ chọn file tại POST /jobs.

Xem log và dừng stack:

```powershell
docker compose logs --tail 50 api worker
docker compose down
```

`down` giữ named volume PostgreSQL, Redis, model và upload để lần sau dùng tiếp.

## Chạy Python trực tiếp trên Windows

Cần Python 3.10+; đã kiểm thử trên Python 3.13.2 Windows và Python 3.12 trong Docker.
Không cần activate virtualenv hay đổi Execution Policy.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe scripts/download_model.py
docker compose up -d --wait db redis
.\.venv\Scripts\python.exe -m backend.app.init_db
```

Nếu `py` không hoạt động, dùng đường dẫn Python đã cài. Ví dụ trên máy Sang:

```powershell
& 'C:\Users\trans\AppData\Local\Programs\Python\Python313\python.exe' -m venv .venv
```

Nếu stack Docker đầy đủ đang chạy, dừng API/worker container trước khi chạy native,
để tránh trùng cổng và hai bộ upload_dir khác nhau:

```powershell
docker compose stop api worker
```

Cửa sổ PowerShell thứ nhất:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload --no-access-log
```

Cửa sổ thứ hai, cùng thư mục repo:

```powershell
.\.venv\Scripts\python.exe -m uvicorn worker.main:app --host 127.0.0.1 --port 8001 --no-access-log
```

Cửa sổ thứ ba chạy `scripts/smoke.ps1` như trên. Dừng native bằng Ctrl+C.
Dùng cùng DATABASE_URL, REDIS_URL, REDIS_STREAM, REDIS_GROUP, UPLOAD_DIR cho API và worker.
Mặc định native đọc .env và dùng localhost; Compose tự dùng hostname nội bộ.
Không chạy nhiều Uvicorn process trong cùng một service vì metrics được giữ trong bộ nhớ.

API chỉ cần `backend/requirements.txt`; worker dùng `worker/requirements.txt`;
`backend/requirements-dev.txt` bao gồm cả hai và công cụ test.

## Kiểm thử

Unit test không cần PostgreSQL/Redis chạy; dùng SQLite và fakeredis trong thư mục
tạm riêng. Test model thật dùng artifact đã tải, tự skip nếu chưa có model:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Integration test dùng PostgreSQL, Redis và ONNX thật; mặc định tắt.
Mỗi test tạo schema PostgreSQL và stream Redis có tên ngẫu nhiên riêng, dọn sau test,
không xóa bảng/stream của ứng dụng:

```powershell
docker compose up -d --wait db redis
.\.venv\Scripts\python.exe scripts/download_model.py
$env:RUN_INTEGRATION_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest -v
Remove-Item Env:RUN_INTEGRATION_TESTS
```

Nếu đổi cổng/credentials, đặt thêm TEST_DATABASE_URL và TEST_REDIS_URL trước khi chạy.
User PostgreSQL cho test cần quyền CREATE SCHEMA.
Bộ test bao gồm health, upload hợp lệ, MIME/đuôi/nội dung giả, ảnh hỏng/rỗng/quá lớn,
giới hạn multipart chunked, CORS, readiness, metrics, JSON log, Redis outage/outbox,
message trùng, lease, database lỗi trước ACK và nhận lại pending job khi worker chết.

## Cấu hình

Tất cả cấu hình ứng dụng nằm trong `backend/app/config.py`, lấy từ biến môi trường
hoặc .env. Tham khảo `.env.example` về URL kết nối, stream/group, upload/pixel limit,
CORS, model/nhãn/version/checksum, top-K, lease và log level.
Các cổng Docker được cấu hình bằng biến PORT tương ứng trong .env.

## Cấu trúc

```text
backend/
  app/                 FastAPI, cấu hình, schema DB/API, validation, outbox, log và metrics
  tests/               Unit, model và integration tests
  Dockerfile
  requirements.txt
  requirements-dev.txt
worker/
  consumer.py          Redis consumer, lease, phục hồi và ghi kết quả
  inference.py         MobileNetV2 ONNX Runtime CPU
  main.py              Service HTTP giám sát và vòng chạy worker
  Dockerfile
  requirements.txt
models/manifest.json   Nguồn, phiên bản, checksum và giấy phép model
scripts/
  download_model.py    Tải artifact có kiểm tra checksum
  smoke.ps1            Kiểm tra luồng đầy đủ trên Windows
docs/
  API.md               Hợp đồng frontend TV3
  ARCHITECTURE.md      Luồng, schema, model và giới hạn vận hành
  TV2-BAN-GIAO.md      Bàn giao backend TV2
  TV3-K8S-BAN-GIAO.md  Bàn giao Kubernetes frontend TV3
k8s/
  frontend-configmap.yaml   ConfigMap biến runtime (API_UPSTREAM)
  frontend-deployment.yaml  Deployment frontend (GHCR image, probes, resources)
  frontend-service.yaml     Service ClusterIP cổng 8080
  frontend.yaml             Manifest gộp toàn bộ Frontend
  README.md                 Hướng dẫn chi tiết triển khai Kubernetes
compose.yaml           Stack chạy cục bộ
pytest.ini             Cấu hình test và markers
Jenkinsfile            Pipeline kiểm tra cấu trúc repo hiện có
```

Frontend của TV3-Thuận nằm trong thư mục `frontend/` và được build trực tiếp bởi service `frontend` trong Compose.
Hạ tầng Kubernetes Frontend được quản lý trong thư mục `k8s/` và tài liệu bàn giao tại [docs/TV3-K8S-BAN-GIAO.md](docs/TV3-K8S-BAN-GIAO.md).
Jenkinsfile hiện chỉ kiểm tra cấu trúc; các lệnh test ở trên dùng cho bàn giao TV2.


## Frontend (TV3 - Thuận)

Frontend React + Vite cung cấp giao diện tải ảnh và hiển thị kết quả nhận diện. Người dùng có thể chọn hoặc kéo-thả ảnh JPG/PNG, xem trước, thay/xóa ảnh; giao diện kiểm tra file rỗng và giới hạn 5 MiB trước khi gửi.

Frontend gửi ảnh bằng `multipart/form-data` (field `file`) tới `POST /jobs`, nhận `job_id` và `status_url`, sau đó polling trạng thái đến khi `completed` hoặc `failed`. Kết quả hiển thị danh sách nhãn, độ tin cậy và phiên bản model; lỗi được hiển thị thành thông báo dễ hiểu. Hợp đồng API chi tiết nằm trong [docs/API.md](docs/API.md).

Chạy frontend độc lập khi API đang hoạt động:

```powershell
Set-Location frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Vite mặc định chạy tại `http://localhost:5173`; `.env.example` cấu hình API tại `http://localhost:8000`. Chạy kiểm thử và build:

```powershell
npm test
npm run build
```

Dockerfile multi-stage build static assets bằng Node.js và phục vụ qua Nginx unprivileged tại cổng 8080. Nginx proxy đường dẫn `/jobs` tới `API_UPSTREAM` (mặc định `http://api:8000`); hai service cần cùng Docker network. Healthcheck frontend ở `/health`. Hướng dẫn chi tiết: [frontend/README.md](frontend/README.md).

### Triển khai Frontend trên Kubernetes

Manifest triển khai Frontend nằm trong thư mục `k8s/`:
- Image khởi tạo đã xác nhận trên Staging: `ghcr.io/01phamtien/ai-recognition-frontend:build-11`. Jenkins hiện publish image theo tag SHA của commit được build; khi tích hợp CI/CD, manifest sẽ được cập nhật theo SHA tương ứng, không sử dụng `latest`.
- Cấu hình runtime: `API_UPSTREAM=http://api:8000` quản lý qua ConfigMap.
- Liveness/Readiness probes tại `GET /health` cổng 8080.
- Service ClusterIP cổng 8080, sẵn sàng tích hợp với Ingress của TV4 (Định).

Triển khai và kiểm thử nhanh trên Kubernetes:

```powershell
kubectl apply -f k8s/frontend.yaml
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-k8s.ps1
```

Chi tiết phối hợp Ingress và runbook: [k8s/README.md](k8s/README.md) và biên bản bàn giao [docs/TV3-K8S-BAN-GIAO.md](docs/TV3-K8S-BAN-GIAO.md).

## Quy trình nhóm

1. Issue và branch dạng `feat/ten-cong-viec`.
2. Commit theo Conventional Commits, nội dung tiếng Việt.
3. Mở PR, cần ít nhất một người khác review trước khi merge vào main.
4. Không tự merge PR, không commit secret, .env thật hoặc model lớn.

<!-- Demo Jenkins webhook trigger lan 2-->
