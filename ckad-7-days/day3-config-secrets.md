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

## Checklist trước khi qua Ngày 4
- [ ] Phân biệt rõ khi nào dùng ConfigMap, khi nào dùng Secret.
- [ ] Tạo được Secret/ConfigMap bằng cả 2 cách: file YAML và lệnh `kubectl create` imperative.
- [ ] Biết vì sao secret trong Git là vi phạm bảo mật dù đã "chỉ là base64".
