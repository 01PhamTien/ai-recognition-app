# Hợp đồng API bàn giao TV3

Phiên bản API: 1.0.0. Nguồn chính xác về schema: `GET /openapi.json`;
thử bằng Swagger tại `/docs`. Đây là hợp đồng đề xuất trong PR TV2,
cần TV3 xác nhận khi tích hợp frontend.

## Tạo tác vụ

`POST /jobs`, `Content-Type: multipart/form-data`, trường bắt buộc `file`.

Chấp nhận JPEG (`.jpg`, `.jpeg`, MIME `image/jpeg`) và PNG
(`.png`, MIME `image/png`). Phần mở rộng, MIME và nội dung giải mã phải khớp.
Giới hạn mặc định: 5 MiB/file và 20 triệu pixel. Giới hạn toàn bộ multipart:
kích thước file cho phép + 64 KiB. File rỗng, ảnh hỏng, nội dung giả mạo bị từ chối.

HTTP **202 Accepted**, header `Location: /jobs/<UUID>`:

```json
{
  "job_id": "fbd78598-08df-4973-8df0-3cbd6881375d",
  "status": "queued",
  "status_url": "/jobs/fbd78598-08df-4973-8df0-3cbd6881375d"
}
```

202 nghĩa là file và job đã được lưu. Nếu Redis tạm ngắt, job vẫn ở trạng thái
`queued`; worker sẽ đưa job vào stream khi Redis hoạt động lại.
Frontend không cần upload lại chỉ vì tác vụ chưa được xử lý ngay.

## Truy vấn

`GET /jobs/{job_id}` trả HTTP **200** khi tìm thấy job:

```json
{
  "job_id": "fbd78598-08df-4973-8df0-3cbd6881375d",
  "status": "completed",
  "predictions": [
    {"class_id": 207, "label": "golden retriever", "confidence": 0.87}
  ],
  "error": null,
  "model_version": "mobilenetv2-7-v1",
  "model_sha256": "c1c513582d56afceff8516c73804e484c81c6a830712ab6d682253f4a3cd042f",
  "created_at": "2026-11-14T04:00:00Z",
  "updated_at": "2026-11-14T04:00:01Z"
}
```

Ví dụ trên minh họa schema; kết quả thực tế gồm tối đa `TOP_K` nhãn (mặc định 5).
`class_id` bắt đầu từ 0 theo thứ tự ImageNet, `confidence` là softmax trong [0, 1],
các nhãn sắp xếp giảm dần. Đây là phân loại vật thể chính trong ảnh, không phải
phát hiện vị trí nhiều vật thể hay nhận diện danh tính người.

| Trạng thái | Ý nghĩa | predictions | error |
|---|---|---|---|
| queued | Chờ đưa vào stream hoặc chờ worker | null | null |
| processing | Worker đang giữ lease và suy luận | null | null |
| completed | Đã ghi kết quả vào PostgreSQL | Danh sách nhãn | null |
| failed | Suy luận thất bại | null | code + message |

Luồng bình thường: `queued → processing → completed/failed`.
Frontend poll `status_url` mỗi 1 giây, dừng khi `completed` hoặc `failed`;
hiển thị thông báo chờ nếu quá 60 giây. Sau sự cố worker, job có thể ở
`processing` đến khi lease hết hạn (mặc định 300 giây), rồi worker nhận lại.
Lỗi suy luận là trạng thái `failed` của job, truy vấn vẫn trả HTTP 200.

Trường `model_version` và `model_sha256` là null khi chưa có kết quả;
chúng ghi phiên bản thực tế của worker đã xử lý.

## Lỗi

Phản hồi lỗi HTTP luôn có dạng:

```json
{"error": {"code": "invalid_image", "message": "Không thể giải mã ảnh hoặc ảnh bị hỏng."}}
```

| HTTP | code | Trường hợp |
|---|---|---|
| 413 | file_too_large | File hoặc toàn bộ multipart vượt giới hạn |
| 413 | image_too_large | Ảnh vượt giới hạn pixel |
| 415 | unsupported_media_type | Không phải JPEG/PNG, sai đuôi hoặc MIME |
| 422 | empty_file | File rỗng |
| 422 | invalid_image | File hỏng/không giải mã được |
| 422 | validation_error | Thiếu file, UUID/tham số không hợp lệ |
| 404 | job_not_found | UUID đúng định dạng nhưng không có job |
| 503 | storage_unavailable | Không thể lưu file hoặc job mới |
| 503 | database_unavailable | Không thể đọc job từ PostgreSQL |
| 503 | dependency_unavailable | /ready: PostgreSQL/Redis chưa sẵn sàng |
| 500 | internal_error | Lỗi nội bộ không dự kiến |

Job thất bại dùng `error.code = inference_failed`, không lộ traceback
hay đường dẫn file. Không tự retry POST sau lỗi mạng không rõ kết quả:
mỗi POST là một job mới, chưa có khóa idempotency cho upload.

## Frontend mẫu

```javascript
const data = new FormData();
data.append("file", file);
const response = await fetch("http://localhost:8000/jobs", {
  method: "POST",
  body: data
});
const body = await response.json();
if (!response.ok) throw new Error(body.error.message);
// Không tự đặt Content-Type: trình duyệt tạo multipart boundary.
const job = await fetch("http://localhost:8000" + body.status_url)
  .then(response => response.json());
```

CORS mặc định cho `http://localhost:5173` và `http://127.0.0.1:5173`.
Thay bằng biến môi trường `CORS_ORIGINS` (mảng JSON) nếu frontend dùng cổng khác.
Mỗi phản hồi API có `X-Request-ID` để đối chiếu log JSON.

## Vận hành

Cả API (8000) và worker (8001) có:

- `GET /health`: HTTP 200, `{"status":"ok"}`, kiểm tra tiến trình HTTP.
- `GET /ready`: HTTP 200 khi phụ thuộc sẵn sàng; worker còn kiểm tra model,
  thread consumer và vòng xử lý Redis gần đây. Chưa sẵn sàng trả 503.
- `GET /metrics`: định dạng Prometheus; HTTP count/latency cho cả hai service,
  thêm `recognition_jobs_total` và `recognition_inference_seconds` cho worker.

Chạy một tiến trình Uvicorn mỗi container. Khi cần thêm worker, dùng container
riêng và consumer name riêng (được sinh tự động), đồng thời chia sẻ upload volume.
Endpoint worker phục vụ kiểm tra/giám sát; frontend chỉ gọi API.
