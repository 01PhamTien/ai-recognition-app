# Frontend AI Vision

Ứng dụng React + Vite cho phép chọn hoặc kéo-thả ảnh JPG/PNG, xem trước, thay
đổi hoặc xóa ảnh, gửi ảnh tới backend để nhận diện và hiển thị kết quả. Giao
diện kiểm tra tệp rỗng và giới hạn 10 MB trước khi gửi.

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

Tạo `.env` từ `.env.example` và đặt `VITE_API_BASE_URL` thành URL gốc backend.
Frontend gửi `POST /api/recognize` dưới dạng `multipart/form-data`, tên field ảnh
là `file`. Có thể ghi đè URL đầy đủ bằng `VITE_RECOGNITION_ENDPOINT`. Ví dụ:

```env
VITE_API_BASE_URL=http://localhost:8000
# Hoặc dùng endpoint khác:
# VITE_RECOGNITION_ENDPOINT=http://localhost:8000/api/recognize
```

Backend cần chấp nhận upload JPG/PNG qua field `file`, trả HTTP 2xx cùng kết quả
nhận diện ở dạng JSON hoặc văn bản; khi lỗi nên trả JSON có `detail`, `message`
hoặc `error`. Ví dụ:

```json
{
  "label": "cat",
  "confidence": 0.98
}
```

Đây là hợp đồng tạm để luồng giao diện chạy được; nếu API TV2 dùng route, field
hoặc quy trình bất đồng bộ khác, cập nhật `VITE_RECOGNITION_ENDPOINT` và adapter
`src/recognitionApi.js` theo OpenAPI/hợp đồng đã thống nhất. Backend cũng cần
cho phép CORS từ origin frontend khi chạy local.

Frontend không giả kết quả nhận diện: khi backend chưa chạy hoặc URL/CORS sai,
giao diện sẽ báo lỗi kết nối thay vì hiển thị kết quả mẫu.

## Docker

Từ thư mục `frontend/`:

```powershell
docker build --build-arg VITE_API_BASE_URL=http://host.docker.internal:8000 -t ai-recognition-frontend .
docker run --rm -p 8080:8080 ai-recognition-frontend
```

Mở `http://localhost:8080`. Image chạy bằng user không phải root, phục vụ SPA
trên cổng 8080 và có health check tại `/health`. URL backend được cấu hình khi
build frontend vì Vite đóng gói biến `VITE_*` vào static assets. Nếu endpoint
khác mặc định, truyền thêm `--build-arg VITE_RECOGNITION_ENDPOINT=https://...`.
