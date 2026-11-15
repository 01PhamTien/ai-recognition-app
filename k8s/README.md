# Hướng dẫn triển khai Frontend trên Kubernetes

Thư mục này chứa các manifest Kubernetes cho thành phần **Frontend (TV3 - Thuận)** của dự án AI Image Recognition.

## 1. Cấu trúc tài nguyên

- `frontend-configmap.yaml`: Quản lý biến môi trường runtime (`API_UPSTREAM`).
- `frontend-deployment.yaml`: Deployment quản lý Pod Frontend (dùng image từ GHCR, có probes, security context non-root, tài nguyên requests/limits).
- `frontend-service.yaml`: Service ClusterIP cổng `8080` điều hướng lưu lượng tới Pod Frontend.
- `frontend.yaml`: File manifest gộp tiện lợi (all-in-one) chứa cả ConfigMap, Deployment và Service.

---

## 2. Thông số kỹ thuật của Pod Frontend

| Thông số | Giá trị cấu hình | Ghi chú |
|---|---|---|
| **Image** | `ghcr.io/01phamtien/ai-recognition-frontend:latest` | Tự động build và push từ pipeline CI Jenkins |
| **Cổng Container** | `8080` (HTTP) | Nginx unprivileged chạy trên cổng 8080 |
| **User bảo mật** | `UID: 101` (`nginx`), `runAsNonRoot: true` | Không chạy quyền root, `allowPrivilegeEscalation: false` |
| **Liveness Probe** | `GET /health` trên cổng 8080 | Kiểm tra tiến trình Nginx còn sống |
| **Readiness Probe** | `GET /health` trên cổng 8080 | Kiểm tra Pod sẵn sàng nhận traffic |
| **Resource Requests** | CPU: `50m`, Memory: `64Mi` | Mức đảm bảo tối thiểu |
| **Resource Limits** | CPU: `200m`, Memory: `128Mi` | Giới hạn tối đa tránh chiếm dụng tài nguyên cluster |

---

## 3. Cơ chế cấu hình URL API (Build-time & Runtime)

Để đảm bảo Frontend chạy ổn định trong mọi môi trường và **không hardcode localhost**, hệ thống hỗ trợ 2 cơ chế:

1. **Runtime (Khuyến nghị cho Kubernetes & Docker):**
   - Ứng dụng SPA gọi API theo đường dẫn tương đối (cùng origin): `/jobs`.
   - Nginx nhận request `/jobs` và reverse-proxy tới biến môi trường `API_UPSTREAM`.
   - Trong Kubernetes, `API_UPSTREAM` được quản lý bởi `frontend-config` ConfigMap:
     ```yaml
     API_UPSTREAM: "http://ai-recognition-api:8000"
     ```
   - Nhờ vậy:
     - Trình duyệt người dùng không cần biết IP nội bộ của Backend.
     - Hoàn toàn **không bị lỗi CORS** vì frontend và API cùng origin tại trình duyệt.
     - Khi đổi tên service hoặc namespace backend, chỉ cần sửa ConfigMap và restart Pod, không cần build lại image.

2. **Build-time:**
   - Khi cần trỏ thẳng tới một API Gateway hoặc domain bên ngoài độc lập, truyền tham số build:
     ```bash
     docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL=https://api.mycluster.domain ./frontend
     ```
   - Mặc định trong bản build production (`import.meta.env.PROD`), nếu không truyền `VITE_API_BASE_URL` thì giá trị sẽ tự động là `""` (dùng relative path `/jobs`), tuyệt đối không rơi vào `localhost`.

---

## 4. Phối hợp với TV4 (Định) về cấu hình Ingress

Để tránh tạo manifest Ingress trùng lặp, **TV4 (Định) quản lý tài nguyên Ingress chung của cluster**. Dưới đây là thông số thống nhất để TV4 cấu hình:

- **Tên Service:** `ai-recognition-frontend`
- **Cổng Service:** `8080` (TCP/HTTP)
- **Endpoint kiểm tra sức khỏe:** `/health` (trả lời HTTP 200 `ok`)

### Hai phương án định tuyến Ingress đề xuất:

#### Phương án 1 (Khuyến nghị - Định tuyến đơn giản qua Nginx Frontend):
Ingress chỉ cần trỏ root path `/` về `ai-recognition-frontend`:
```yaml
spec:
  rules:
    - host: ai.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ai-recognition-frontend
                port:
                  number: 8080
```
*Lưu ý:* Mọi request `/jobs` từ trình duyệt gửi về `ai.example.com/jobs` sẽ đi qua Nginx của Frontend, Nginx tự động chuyển tiếp tới `http://ai-recognition-api:8000` trong mạng nội bộ cluster.

#### Phương án 2 (Định tuyến tách biệt Path-based tại Ingress):
Nếu TV4 muốn Ingress phân luồng trực tiếp API và Frontend:
```yaml
spec:
  rules:
    - host: ai.example.com
      http:
        paths:
          - path: /jobs
            pathType: Prefix
            backend:
              service:
                name: ai-recognition-api
                port:
                  number: 8000
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ai-recognition-frontend
                port:
                  number: 8080
```

### Các Annotations quan trọng TV4 cần thêm vào Ingress:
```yaml
metadata:
  annotations:
    # Cho phép upload ảnh tối đa 6 MiB (theo giới hạn 5 MiB của backend + multipart overhead)
    nginx.ingress.kubernetes.io/proxy-body-size: "6m"
    # Timeout chờ suy luận model AI
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "60"
```

---

## 5. Hướng dẫn triển khai và kiểm thử

### Triển khai lên cluster
Áp dụng toàn bộ manifest Frontend vào namespace mục tiêu (ví dụ `default`):

```bash
# Áp dụng tất cả tài nguyên Frontend
kubectl apply -f k8s/frontend.yaml

# Hoặc áp dụng từng file riêng:
kubectl apply -f k8s/frontend-configmap.yaml
kubectl apply -f k8s/frontend-deployment.yaml
kubectl apply -f k8s/frontend-service.yaml
```

Kiểm tra trạng thái triển khai:
```bash
kubectl get deployment ai-recognition-frontend
kubectl get pods -l app.kubernetes.io/name=ai-recognition-frontend
kubectl get svc ai-recognition-frontend
```

### Kiểm thử luồng hoạt động (Smoke Test)

Sử dụng script kiểm thử tự động trên PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\smoke-k8s.ps1 -Namespace default
```

Hoặc kiểm thử thủ công qua `kubectl port-forward`:
```bash
# 1. Mở cổng tạm thời tới Frontend
kubectl port-forward svc/ai-recognition-frontend 8080:8080

# 2. Kiểm tra health endpoint (trong terminal khác)
curl http://localhost:8080/health

# 3. Gửi ảnh nhận diện
curl -F "file=@test.png;type=image/png" http://localhost:8080/jobs

# 4. Kiểm tra kết quả trả về từ URL trong status_url
curl http://localhost:8080/jobs/<JOB_ID>
```
