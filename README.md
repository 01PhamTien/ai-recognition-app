# AI Image Recognition — Application

Đồ án DevOps đề tài 10: frontend tải ảnh, API, AI worker (ONNX/PyTorch), hàng đợi Redis, database.

> Trạng thái: frontend React + Vite gửi ảnh theo hợp đồng job bất đồng bộ `POST /jobs`, sau đó polling `status_url` đến khi hoàn tất.

## Thành phần dự kiến
- `frontend/`: giao diện React + Vite, Dockerfile multi-stage, kiểm thử và hướng dẫn tại [frontend/README.md](./frontend/README.md)
- `backend/`: FastAPI, `/health`, `/metrics`, JSON stdout logs, env vars
- `worker/`: service suy luận AI, xử lý công việc từ Redis
- `tests/`: kiểm thử

## Quy trình nhóm
1. Tạo Issue và branch dạng `feat/ten-cong-viec`.
2. Commit theo Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`).
3. Mở Pull Request; cần ít nhất 1 thành viên review trước khi merge vào `main`.
4. Không commit secret hoặc `.env` thật.

## Tiêu chí nghiệm thu task
- Có thay đổi rõ ràng; có hướng dẫn chạy hoặc bằng chứng test.
- Pull Request đã được review.
- Tài liệu liên quan được cập nhật.

## Trạng thái triển khai
- Frontend hỗ trợ JPG/PNG, kéo-thả, xem trước, thay ảnh và kiểm tra giới hạn 5 MiB theo backend.
- Frontend gửi `multipart/form-data` (field `file`) tới `POST /jobs`, nhận `job_id`/`status_url` rồi poll trạng thái.
- Dockerfile frontend build static assets; Nginx unprivileged phục vụ cổng 8080 và proxy `/jobs` tới API qua `API_UPSTREAM`.
