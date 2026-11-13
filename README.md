# AI Image Recognition — Application

Đồ án DevOps đề tài 10: frontend tải ảnh, API, AI worker (ONNX/PyTorch), hàng đợi Redis, database.

> Trạng thái: khởi tạo repo. Chưa có ứng dụng chạy được.

## Thành phần dự kiến
- `frontend/`: React + Vite (đề xuất)
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
Sẽ bổ sung Docker, Compose, Jenkinsfile và kiểm thử ở các bước tiếp theo.
