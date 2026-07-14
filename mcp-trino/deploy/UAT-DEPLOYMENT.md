# Triển khai mcp-trino lên UAT (ho-data-cluster)

## 1. Mô hình

Trino hiện tại của SSI chỉ có **một cụm** (không tách namespace UAT/PROD riêng):

- Cluster: `ho-data-cluster`
- Namespace: `trino`
- Service: `trino`, port `8080` (HTTP nội bộ, không TLS giữa các pod trong cluster)
- Auth: `PASSWORD,OAUTH2` + Ranger access-control

mcp-trino sẽ deploy vào namespace riêng **`mcp-trino-uat`** trong cùng cluster, gọi Trino qua
DNS nội bộ K8s — không cần Ingress, không expose ra internet:

```
Claude Code / client MCP
        │  HTTP nội bộ (VPN/port-forward), header X-User-Email
        ▼
mcp-trino (namespace: mcp-trino-uat)
        │  TRINO_USER/TRINO_PASSWORD (service account) + X-Trino-User (impersonate)
        ▼
trino.trino.svc.cluster.local:8080  (namespace: trino)
        │
        ▼
Ranger (access-control theo user thật, không theo service account)
```

Vì không có Ingress, client bên ngoài cluster (máy dev) truy cập mcp-trino qua
`kubectl port-forward` hoặc VPN nội bộ tới ClusterIP — phù hợp cho giai đoạn thử nghiệm UAT.

## 2. Điều kiện tiên quyết (cần xác nhận / thực hiện trước, không tự động)

| # | Việc cần làm | Ai làm |
|---|---|---|
| 1 | Tạo service account Trino riêng cho mcp-trino (vd `mcp-trino-svc`), thêm vào `auth.passwordAuth` trong `trino/override-values.template.yaml` | Người quản trị Trino |
| 2 | Cấp Ranger policy **impersonation** cho `mcp-trino-svc` (được phép giả danh user thật khi có `X-Trino-User`) | Người quản trị Ranger |
| 3 | Build & push image `harbor.ssi.com.vn/dataflatform/mcp-trino:<tag>` (tag theo commit/semver, KHÔNG dùng `latest`) | CI của repo `mcp_server_trino` |
| 4 | Xác nhận cơ chế lưu `TRINO_PASSWORD` (Vault Agent Injector / External Secrets Operator / tạo Secret thủ công ngoài Git) | Team hạ tầng |
| 5 | Duyệt CR theo QĐ 373A/2023 trước khi merge manifest vào `data-platform-infrastructure` (main) | Change Management |

mcp-trino tự nó **không cần quyền đọc dữ liệu gì** — nó chỉ cần quyền "impersonate", còn
phân quyền dữ liệu thật vẫn theo Ranger policy gắn với từng user SSI.

## 3. Cấu trúc file (bản nháp, xem tại `deploy/manifests/` trong repo này)

```
mcp-trino/
├── manifests/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── secret.example.yaml   # mẫu, KHÔNG chứa secret thật, không commit bản điền thật
└── argocd-app.example.yaml   # Application trỏ tới mcp-trino/manifests
```

Khi được duyệt, các file trên sẽ copy sang
`data-platform-infrastructure/mcp-trino/manifests/` và
`data-platform-infrastructure/argocd-config/mcp-trino.yaml`, theo đúng pattern hiện có của
`argocd-config/trino.yaml`.

## 4. Các bước triển khai

### Bước 1 — Build & push image

```bash
docker build -t harbor.ssi.com.vn/dataflatform/mcp-trino:uat-<commit-sha> .
docker push harbor.ssi.com.vn/dataflatform/mcp-trino:uat-<commit-sha>
```
(Cần xác nhận trước khi `docker push` — đẩy image lên registry dùng chung.)

### Bước 2 — Tạo Secret chứa credential Trino (KHÔNG commit vào Git)

```bash
kubectl create namespace mcp-trino-uat

kubectl create secret generic mcp-trino-credentials \
  --namespace mcp-trino-uat \
  --from-literal=TRINO_USER='mcp-trino-svc' \
  --from-literal=TRINO_PASSWORD='<lấy từ Vault, không gõ trực tiếp trong shell history>'
```

Nếu team hạ tầng đã có Vault Agent Injector hoặc External Secrets Operator, dùng cơ chế đó
thay vì tạo Secret thủ công — tránh secret nằm trong lịch sử shell/CI log.

### Bước 3 — Apply manifest

```bash
kubectl apply -f mcp-trino/manifests/namespace.yaml
kubectl apply -f mcp-trino/manifests/deployment.yaml
kubectl apply -f mcp-trino/manifests/service.yaml
```

Hoặc để ArgoCD tự sync sau khi merge `argocd-config/mcp-trino.yaml` (khuyến nghị, đúng
quy trình GitOps hiện có — tránh `kubectl apply` trực tiếp vào cluster dùng chung).

### Bước 4 — Kiểm tra rollout

```bash
kubectl -n mcp-trino-uat rollout status deploy/mcp-trino
kubectl -n mcp-trino-uat get pods
kubectl -n mcp-trino-uat logs -l app=mcp-trino --tail=100
```

### Bước 5 — Test kết nối từ trong cluster

```bash
kubectl -n mcp-trino-uat run tmp-curl --rm -it --image=curlimages/curl -- \
  curl -s http://mcp-trino.mcp-trino-uat.svc.cluster.local:8080/status
```

Kỳ vọng: HTTP 200, service báo đã kết nối được tới `trino.trino.svc.cluster.local:8080`.

### Bước 6 — Test từ máy client (dev) qua port-forward

```bash
kubectl -n mcp-trino-uat port-forward svc/mcp-trino 8080:8080
```

Sau đó trỏ MCP client (Claude Code/Claude Desktop) tới `http://localhost:8080/mcp`,
set header `X-User-Email: <email-thật-của-bạn>` để test impersonation — xác nhận Ranger
áp đúng quyền của user đó (không thấy được bảng ngoài quyền của user, hoặc bị từ chối
nếu user chưa có policy).

## 5. Rollback

```bash
kubectl -n mcp-trino-uat rollout undo deploy/mcp-trino
```

Hoặc revert commit trong `data-platform-infrastructure` nếu deploy qua ArgoCD — ArgoCD sẽ
tự sync về trạng thái trước đó.

## 6. Việc KHÔNG làm tự động

- Không `docker push` / `kubectl apply` vào cluster dùng chung mà chưa có xác nhận rõ ràng.
- Không tạo Ranger policy hộ — cần người quản trị Ranger thực hiện và xác nhận phạm vi quyền.
- Không commit `TRINO_PASSWORD` hay bất kỳ secret nào vào Git dưới mọi hình thức
  (kể cả trong `values.yaml`, `.env`, hay comment).
