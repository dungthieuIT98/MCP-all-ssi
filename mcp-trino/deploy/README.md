# Deploy mcp-trino to K8s (ho-data-cluster)

Theo pattern GitOps hiện có trong `data-platform-infrastructure` (xem `argocd-config/trino.yaml`).
mcp-trino chạy trong namespace riêng `mcp-trino`, gọi Trino qua Service DNS nội bộ
`trino.trino.svc.cluster.local:8080` — không cần TLS, không cần expose ra ngoài cluster.

## Cách hoạt động

Client (Claude Code/Claude Desktop) gọi vào `mcp-trino` qua HTTP nội bộ, kèm header
`X-User-Email`. mcp-trino dùng 1 service account Trino duy nhất (`TRINO_USER`/`TRINO_PASSWORD`)
để kết nối, rồi set `X-Trino-User` để Trino/Ranger impersonate & enforce quyền theo user thật.
Do vậy service account này cần được cấp policy "impersonate" phù hợp trong Ranger — việc này
do người quản trị Trino/Ranger cấu hình, không nằm trong phạm vi các file ở đây.

## Các bước để đưa vào repo hạ tầng (data-platform-infrastructure)

Đây chỉ là bản nháp để bạn review. Khi đồng ý, các file dưới `manifests/` sẽ copy sang
`data-platform-infrastructure/mcp-trino/manifests/`, và cần thêm 1 file
`data-platform-infrastructure/argocd-config/mcp-trino.yaml` trỏ tới đường dẫn đó
(tương tự cấu trúc của `argocd-config/trino.yaml`), theo đúng quy trình CR/Change Management
trước khi merge vào main / sync qua ArgoCD.

## Việc cần xác nhận trước khi merge thật

1. Tên user service account trong Trino (vd: `mcp-trino-svc`) — do người quản trị Trino tạo,
   set password trong `auth.passwordAuth` (đã có trong `trino/override-values.template.yaml`),
   và cấp policy impersonation trong Ranger (`ranger-trino-security.xml` liên quan tới
   `apache-ranger.plugin.config.resource`).
2. Nơi lưu `TRINO_PASSWORD` — repo hiện chưa thấy Vault Agent Injector hay External Secrets
   Operator được dùng cho Trino (`override-values.template.yaml` hiện lưu secret dạng plaintext
   ngay trong values, ví dụ `internal-communication.shared-secret`, password hash). Cách này
   **không nên copy lại** cho mcp-trino — nên hỏi team hạ tầng xem có Vault/ESO chuẩn hoá chưa,
   nếu chưa thì tối thiểu dùng `kubectl create secret` thủ công ngoài Git (không commit).
3. Image `harbor.ssi.com.vn/dataflatform/mcp-trino:<tag>` cần được build & push trước
   (xem `.goreleaser.yml`/CI của repo `mcp_server_trino`).
