# Frontend AI Vision

Ứng dụng React + Vite cho phép chọn hoặc kéo-thả ảnh JPG/PNG, xem trước, thay
đổi hoặc xóa ảnh, gửi ảnh tới backend để nhận diện và hiển thị kết quả. Giao
diện kiểm tra tệp rỗng và giới hạn 5 MiB trước khi gửi.

## Yêu cầu

- Node.js 22 trở lên
- npm 10 trở lên

## Cài đặt và chạy local

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Mở URL được Vite hiển thị (mặc định `http://localhost:5173`).

## Kiểm thử và build

```powershell
npm test
npm run build
npm run preview
```

## Cấu hình backend

Khi chạy Vite local, tạo `.env` từ `.env.example` và đặt
`VITE_API_BASE_URL` thành URL gốc backend. Frontend gửi ảnh bằng
`POST /jobs` dưới dạng `multipart/form-data`, tên field là `file`. Backend trả
`202 Accepted` cùng `job_id` và `status_url`; frontend poll `status_url` mỗi
giây đến khi job `completed` hoặc `failed`. Sau 60 giây giao diện báo đang chờ
lâu hơn dự kiến nhưng vẫn tiếp tục poll đến trạng thái cuối.

```env
VITE_API_BASE_URL=http://localhost:8000
```

API hợp đồng được mô tả trong [docs/API.md của PR backend #5](https://github.com/01PhamTien/ai-recognition-app/blob/feat/backend-nhan-dien-anh/docs/API.md).
Kết quả `completed` gồm danh sách `predictions` (`label`, `confidence`, `class_id`) và `model_version`. Giao diện hiển thị nhãn cùng độ tin cậy, không hiển thị JSON thô. Job `failed` trả `error.code` và `error.message` trong HTTP 200. Các lỗi HTTP khi tạo hoặc truy vấn job có dạng
`{"error":{"code":"...","message":"..."}}`. Frontend không gửi lại `POST /jobs` khi lỗi mạng không rõ kết quả, vì mỗi lần gửi tạo một job mới.

```json
{
  "job_id": "fbd78598-08df-4973-8df0-3cbd6881375d",
  "status": "completed",
  "predictions": [
    { "class_id": 207, "label": "golden retriever", "confidence": 0.87 }
  ],
  "error": null
}
```

Khi chạy Vite local, backend cần cho phép CORS từ `http://localhost:5173`.
Khi chạy Docker, frontend gọi API cùng origin qua Nginx proxy `/jobs`; biến
`API_UPSTREAM` phải trỏ tới service API mà container frontend truy cập được
(mặc định `http://api:8000` trong mạng Docker Compose).

Frontend không giả kết quả nhận diện: khi backend chưa chạy hoặc URL/CORS sai,
giao diện sẽ báo lỗi kết nối thay vì hiển thị kết quả mẫu.

## Docker

Từ thư mục gốc repo, build frontend. Trong triển khai Compose, nối container
frontend vào cùng Docker network với service `api`:

```powershell
docker build -t ai-recognition-frontend ./frontend
docker run --rm --network ai-recognition_default -e API_UPSTREAM=http://api:8000 -p 8080:8080 ai-recognition-frontend
```

Mở `http://localhost:8080`. Nginx phục vụ SPA và chuyển tiếp `/jobs` tới
`API_UPSTREAM`. Biến này là origin của API, không có dấu `/` cuối, ví dụ
`http://api:8000`. Nginx phân giải tên service lúc có request qua DNS của Docker
(`127.0.0.11`), nên frontend vẫn nối được backend khi container `api` lên sau.
Hai container phải cùng Docker network. Image chạy bằng user không phải root,
nhận upload đến 6 MiB (đủ cho giới hạn file 5 MiB cộng multipart overhead), và
có health check tại `/health`.
