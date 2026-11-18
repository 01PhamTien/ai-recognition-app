# Bàn giao TV3-Thuận — Issue #16

Nhánh: `feat/frontend-kubernetes`.  
Công việc: **Chuẩn bị Frontend hiện tại để chạy trên Kubernetes và kết nối đúng Backend qua Service/Ingress.**

---

## 1. Đã triển khai

- **Rà soát cấu hình URL API:**
  - Cập nhật hàm `getApiBaseUrl()` trong `frontend/src/recognitionApi.js`: Khi chạy ở chế độ production (`import.meta.env.PROD`), nếu không có biến `VITE_API_BASE_URL` thì mặc định về chuỗi rỗng `""` (dùng relative path `/jobs`), tuyệt đối không bị hardcode `http://localhost:8000`.
  - Thêm unit test kiểm tra logic fallback production trong `frontend/src/recognitionApi.test.js`.
- **Sửa lỗi Nginx DNS resolver trên Kubernetes:**
  - Cập nhật `frontend/nginx.conf`: Loại bỏ dòng `resolver 127.0.0.11` (vốn là DNS nội bộ của Docker Compose không tồn tại trên Kubernetes).
  - Sử dụng trực tiếp `proxy_pass ${API_UPSTREAM};` để Nginx sử dụng DNS của hệ thống (`/etc/resolv.conf` - CoreDNS trên Kubernetes và Docker DNS trên Compose), giúp Nginx phân giải tên service Backend `api:8000` mượt mà, không bị lỗi 502 Bad Gateway.
- **Tạo Manifests Kubernetes cho Frontend:**
  - `k8s/frontend-configmap.yaml`: Quản lý biến môi trường `API_UPSTREAM: "http://api:8000"` (kết nối service Backend thực tế tên `api`, cổng 8000 trên namespace `ai-recognition-staging`).
  - `k8s/frontend-deployment.yaml`:
    - Sử dụng image chính thức từ GHCR theo tag build-11 đã được Jenkins push và xác nhận chạy thành công trên Staging. Khi tích hợp CI/CD, tag sẽ được thay bằng SHA commit của build.: `ghcr.io/01phamtien/ai-recognition-frontend:build-11`.
    - Cấu hình `imagePullSecrets: [{name: ghcr-pull}]` theo secret đã có sẵn trong staging.
    - Bảo mật: `runAsNonRoot: true`, `runAsUser: 101`, `allowPrivilegeEscalation: false`.
    - Probes: `livenessProbe` và `readinessProbe` trên path `/health` cổng 8080.
    - Tài nguyên: `requests` (50m CPU, 64Mi RAM) và `limits` (200m CPU, 128Mi RAM).
  - `k8s/frontend-service.yaml`: Service loại `ClusterIP`, mở cổng 8080 cho lưu lượng nội bộ.
  - `k8s/frontend.yaml`: File all-in-one tích hợp cả 3 tài nguyên trên.
- **Thống nhất phương án Ingress với TV4 (Định):**
  - Không tự ý tạo file Ingress để tránh trùng lặp.
  - Đã ghi rõ đặc tả kỹ thuật và 2 phương án routing cho TV4 trong `k8s/README.md`:
    - Service name: `ai-recognition-frontend`, port: `8080`.
    - Healthcheck endpoint: `/health`.
    - Annotations đề xuất: `nginx.ingress.kubernetes.io/proxy-body-size: "6m"`, `proxy-read-timeout: "60"`.
- **Công cụ kiểm thử và tài liệu:**
  - Viết script PowerShell kiểm thử luồng end-to-end trên Kubernetes: `scripts/smoke-k8s.ps1`.
  - Viết tài liệu runbook chi tiết tại `k8s/README.md`.
  - Cập nhật `README.md` chính của repo và `frontend/README.md`.

---

## 2. Bằng chứng kiểm thử

### Bộ kiểm thử Frontend (Vitest)
Đã chạy bộ unit test sau khi cập nhật cấu hình API:
```bash
cd frontend && npm test -- --run
```
Kết quả: **18 passed** (18/18 tests pass), bao gồm:
- 4 tests xác thực định dạng và dung lượng ảnh.
- 7 tests API client và fallback production.
- 7 tests giao diện người dùng App.

### Cú pháp Manifest Kubernetes
Đã kiểm tra tính toàn vẹn và cú pháp của toàn bộ file YAML trong thư mục `k8s/`:
- `k8s/frontend-configmap.yaml`
- `k8s/frontend-deployment.yaml`
- `k8s/frontend-service.yaml`
- `k8s/frontend.yaml`

---

## 3. Việc cần thành viên nhóm xác nhận

- **TV4 (Định):** Xác nhận thông số Service `ai-recognition-frontend:8080` và path `/` hoặc `/jobs` để cấu hình Ingress của cluster.
- **TV1 (Tiến):** Review Pull Request liên kết với Issue #16.
- **TV2 (Sang):** Đã xác nhận tên Service Backend trong cluster staging là `api`, cổng `8000` (`API_UPSTREAM: "http://api:8000"`).

---

## 4. Danh sách file đã thêm hoặc sửa

- `frontend/src/recognitionApi.js` (sửa: fallback an toàn production)
- `frontend/src/recognitionApi.test.js` (thêm test fallback production)
- `frontend/nginx.conf` (sửa: loại bỏ hardcode resolver 127.0.0.11)
- `k8s/frontend-configmap.yaml` (thêm mới)
- `k8s/frontend-deployment.yaml` (thêm mới)
- `k8s/frontend-service.yaml` (thêm mới)
- `k8s/frontend.yaml` (thêm mới)
- `k8s/README.md` (thêm mới: runbook hướng dẫn K8s)
- `scripts/smoke-k8s.ps1` (thêm mới: smoke test K8s)
- `docs/TV3-K8S-BAN-GIAO.md` (thêm mới: biên bản bàn giao)
- `README.md` (cập nhật)
- `frontend/README.md` (cập nhật)
