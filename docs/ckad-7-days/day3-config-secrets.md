# Ngày 3 — ConfigMap, Secret, biến môi trường

## Mục tiêu hôm nay
Tách cấu hình và bí mật ra khỏi image — chủ đề luôn xuất hiện trong domain "Application Environment, Configuration and Security" của đề CKAD.

## Đọc trước
- [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Define Environment Variables for a Container](https://kubernetes.io/docs/tasks/inject-data-application/define-environment-variable-container/)

## Khái niệm cốt lõi
- `ConfigMap` chứa dữ liệu cấu hình không nhạy cảm (URL, port, flag...). `Secret` cũng là key-value nhưng dành cho dữ liệu nhạy cảm — về mặt kỹ thuật chỉ mã hoá base64 (không phải mã hoá mạnh), nên **secret thật vẫn phải quản lý qua vault/CI secret, không tin base64 là đủ an toàn**.
- Có 2 cách đưa dữ liệu vào Pod: `envFrom`/`env.valueFrom` (biến môi trường) hoặc `volumeMounts` (mount thành file).
- `envFrom.configMapRef` bơm **toàn bộ** key trong ConfigMap thành biến môi trường; `env.valueFrom.secretKeyRef` bơm **từng key riêng lẻ** — dùng khi cần đổi tên biến hoặc chỉ lấy 1-2 key.

## Đối chiếu với file thật trong repo
[`deploy/configmap.yaml`](../../deploy/configmap.yaml) — 4 biến cấu hình không nhạy cảm (URL Superset UAT, transport, host, port).

[`deploy/deployment.yaml`](../../deploy/deployment.yaml) dòng 44-57:
```yaml
envFrom:
  - configMapRef:
      name: mcp-superset-config
env:
  - name: SUPERSET_USERNAME
    valueFrom:
      secretKeyRef:
        name: mcp-superset-credentials
        key: SUPERSET_USERNAME
  - name: SUPERSET_PASSWORD
    valueFrom:
      secretKeyRef:
        name: mcp-superset-credentials
        key: SUPERSET_PASSWORD
```
Lưu ý: repo **không** có file secret — đúng chuẩn, secret không commit vào Git. Secret `mcp-superset-credentials` phải tạo riêng ngoài Git (vault, `kubectl create secret`, hoặc CI secret).

## Thực hành (dùng giá trị giả, không dùng credential thật)
```bash
kubectl create namespace dataplatform

kubectl apply -f deploy/configmap.yaml

# Tạo secret giả để luyện tập — KHÔNG dùng mật khẩu Superset thật
kubectl create secret generic mcp-superset-credentials \
  --from-literal=SUPERSET_USERNAME=dummy-user \
  --from-literal=SUPERSET_PASSWORD=dummy-pass \
  -n dataplatform

kubectl get secret mcp-superset-credentials -n dataplatform -o yaml
kubectl get configmap mcp-superset-config -n dataplatform -o yaml
```

## Bài tập tự làm
1. Tạo 1 ConfigMap từ file (`kubectl create configmap app-conf --from-file=...`) thay vì từ `--from-literal`, hiểu sự khác biệt.
2. Sửa `deploy/deployment.yaml` (bản copy riêng để luyện tập) thêm 1 biến môi trường mới lấy từ ConfigMap bằng `env.valueFrom.configMapKeyRef` thay vì `envFrom`.
3. Giải thích được: nếu đổi giá trị trong ConfigMap đang được mount làm biến môi trường, Pod đang chạy có tự nhận giá trị mới không? (Gợi ý: không — cần restart Pod; khác với mount dạng volume có thể tự cập nhật sau một khoảng trễ).

## Đào sâu / nâng cao

### Mount ConfigMap/Secret dạng volume thay vì env
```yaml
volumes:
  - name: config-vol
    configMap:
      name: mcp-superset-config
containers:
  - name: app
    volumeMounts:
      - name: config-vol
        mountPath: /etc/config
```
Mỗi key trong ConfigMap trở thành 1 file riêng trong `/etc/config` (tên file = tên key, nội dung file = giá trị). Có thể chọn mount 1 phần bằng `items`:
```yaml
volumes:
  - name: config-vol
    configMap:
      name: mcp-superset-config
      items:
        - key: SUPERSET_BASE_URL
          path: superset-url.txt
```

Khác biệt quan trọng với env: nếu ConfigMap được mount làm **volume** (không phải `subPath`) và không phải `readOnlyRootFilesystem` chặn, kubelet sẽ tự đồng bộ nội dung mới sau một khoảng trễ (thường ~1 phút, phụ thuộc `--sync-frequency` của kubelet và cache TTL) mà **không cần restart Pod** — ứng dụng phải tự watch file để reload (K8s không tự reload tiến trình bên trong container). Ngược lại, biến môi trường (`envFrom`/`env`) chỉ được đọc **một lần lúc container khởi động** — đổi ConfigMap không tự cập nhật biến môi trường, bắt buộc phải restart Pod (`kubectl rollout restart deployment/...`).

Cơ chế thực tế đứng sau: volume mount ConfigMap/Secret dùng symlink tới thư mục ẩn có timestamp (`..data` → `..2024_01_01_00_00_00.xxx/`), khi nội dung đổi, kubelet tạo thư mục mới rồi đổi symlink — đây là lý do việc cập nhật là **atomic** (ứng dụng không bao giờ đọc phải file dở dang giữa chừng khi update).

Đọc: [ConfigMaps — Mounted ConfigMaps are updated automatically](https://kubernetes.io/docs/concepts/configuration/configmap/#mounted-configmaps-are-updated-automatically).

### Loại Secret có sẵn (`type`)
- `Opaque`: mặc định, tự do key-value (như `mcp-superset-credentials`).
- `kubernetes.io/dockerconfigjson`: dùng cho `imagePullSecrets` — chính là loại secret `harbor-registry-secret` trong [`deployment.yaml`](../../deploy/deployment.yaml#L29-L30). Tạo bằng:
```bash
kubectl create secret docker-registry harbor-registry-secret \
  --docker-server=harbor.ssi.com.vn \
  --docker-username=<user> --docker-password=<pass> \
  -n dataplatform
```
- `kubernetes.io/tls`: dùng cho secret TLS trong Ingress (chính là `ssi-tls` trong [`ingress.yaml`](../../deploy/ingress.yaml#L13)):
```bash
kubectl create secret tls ssi-tls --cert=path/to/tls.crt --key=path/to/tls.key -n dataplatform
```
- `kubernetes.io/basic-auth`, `kubernetes.io/ssh-auth`, `kubernetes.io/service-account-token`: ít gặp trong đề CKAD nhưng nên biết tồn tại — mỗi `type` quy định K8s validate field bắt buộc nào (ví dụ `tls` bắt buộc phải có đúng 2 key `tls.crt`/`tls.key`).
- `kubectl create secret generic` luôn tạo `type: Opaque` — muốn `type` khác **phải** dùng đúng subcommand (`docker-registry`, `tls`) hoặc viết tay YAML với `type:` tương ứng, không patch được `type` của secret sau khi đã tạo (field immutable theo thiết kế).

Đọc: [Secret Types](https://kubernetes.io/docs/concepts/configuration/secret/#secret-types).

### Immutable ConfigMap/Secret
Thêm `immutable: true` vào ConfigMap/Secret để ngăn sửa đổi sau khi tạo — giảm tải cho control-plane (kube-apiserver không cần watch thay đổi trên toàn bộ node đang mount object đó) và tránh sửa nhầm trong môi trường production. Muốn đổi giá trị phải tạo object mới (thường đặt tên kèm hash nội dung, ví dụ `mcp-superset-config-a1b2c3`) rồi cập nhật reference trong Deployment — pattern này thường đi kèm rolling update tự động vì tên ConfigMap đổi khiến `spec.template` đổi theo, kích hoạt revision mới (khác với sửa trực tiếp nội dung ConfigMap cũ, vốn **không** tự kích hoạt rolling update).

Đọc: [Immutable Secrets and ConfigMaps](https://kubernetes.io/docs/concepts/configuration/secret/#secret-immutable).

### `imagePullSecrets` ở cấp namespace
Thay vì khai `imagePullSecrets` trong từng Deployment, có thể gán mặc định cho toàn bộ ServiceAccount trong namespace bằng `kubectl patch serviceaccount default -p '{"imagePullSecrets": [{"name": "harbor-registry-secret"}]}'` — mọi Pod dùng ServiceAccount `default` tự động có quyền pull mà không cần khai lại. Cách này hữu ích khi nhiều Deployment trong cùng namespace đều pull từ 1 registry — tránh lặp lại `imagePullSecrets` ở mọi file.

Đọc: [Add ImagePullSecrets to a Service Account](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#add-imagepullsecrets-to-a-service-account).

### `stringData` — viết Secret plaintext, K8s tự encode base64
Khi viết tay YAML cho Secret, dùng `stringData` thay vì `data` để không phải tự encode base64 bằng tay:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-superset-credentials
type: Opaque
stringData:
  SUPERSET_USERNAME: dummy-user
  SUPERSET_PASSWORD: dummy-pass
```
K8s tự động encode `stringData` thành `data` (base64) khi lưu vào etcd — `kubectl get secret ... -o yaml` sau đó sẽ chỉ thấy `data`, không còn `stringData`. Đây là cách nhanh nhất để viết Secret trong lúc thi thay vì tự chạy `echo -n "value" | base64` rồi dán vào `data`.

## Bài tập nâng cao
1. Viết 1 Secret bằng `stringData` (không dùng `--from-literal` hay tự base64 tay), apply, rồi `kubectl get secret <name> -o jsonpath='{.data.SUPERSET_PASSWORD}' | base64 -d` để xác nhận giá trị đã được K8s tự encode đúng.
2. Mount ConfigMap `mcp-superset-config` dạng volume vào 1 Pod thay vì `envFrom`, sau đó sửa ConfigMap (`kubectl edit configmap mcp-superset-config`) và dùng `kubectl exec` vào Pod, `cat` lại file trong `/etc/config` mỗi 20 giây để tự quan sát thời điểm nội dung file cập nhật — đối chiếu với việc biến môi trường trong cùng Pod (nếu có) không hề đổi.
3. Tạo 1 ConfigMap với `immutable: true`, cố `kubectl edit` để sửa giá trị và đọc chính xác thông báo lỗi trả về.
4. Tạo Secret loại `kubernetes.io/tls` bằng chứng chỉ tự ký (`openssl req -x509 -newkey rsa:2048 -keyout tls.key -out tls.crt -days 30 -nodes -subj "/CN=test.local"`), gắn vào 1 Ingress test, xác nhận `kubectl describe ingress` không báo lỗi thiếu secret.
5. Patch ServiceAccount `default` của 1 namespace test để tự động có `imagePullSecrets`, xoá `imagePullSecrets` khỏi Deployment, apply lại và xác nhận Pod vẫn pull image thành công (dùng registry công khai để không cần dựng Harbor thật).

## Checklist trước khi qua Ngày 4
- [ ] Phân biệt rõ khi nào dùng ConfigMap, khi nào dùng Secret.
- [ ] Tạo được Secret/ConfigMap bằng cả 2 cách: file YAML và lệnh `kubectl create` imperative.
- [ ] Biết vì sao secret trong Git là vi phạm bảo mật dù đã "chỉ là base64".
- [ ] Biết tạo secret loại `docker-registry` và `tls`, không chỉ `generic`.
- [ ] Giải thích được vì sao đổi ConfigMap không tự cập nhật biến môi trường của Pod đang chạy.
