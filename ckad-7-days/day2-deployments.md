# Ngày 2 — Deployment, ReplicaSet, rolling update

## Mục tiêu hôm nay
Hiểu vì sao ứng dụng thật không chạy Pod trần mà chạy qua Deployment, và cách kiểm soát rolling update/rollback — domain "Application Deployment" chiếm tỉ trọng lớn trong đề thi CKAD.

## Đọc trước
- [Deployments — Kubernetes docs](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [ReplicaSet](https://kubernetes.io/docs/concepts/workloads/controllers/replicaset/)
- [Rolling Update Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-update-deployment)

## Khái niệm cốt lõi
- Chuỗi quản lý: **Deployment → ReplicaSet → Pod**. Deployment không chạy Pod trực tiếp, nó tạo ReplicaSet, ReplicaSet mới tạo Pod.
- `strategy.type: RollingUpdate` với `maxSurge`/`maxUnavailable` kiểm soát tốc độ và độ an toàn khi cập nhật phiên bản mới — mặc định K8s cho phép 1 pod dư và 1 pod thiếu tạm thời.
- `revisionHistoryLimit` giữ lại bao nhiêu ReplicaSet cũ để có thể rollback.

## Đối chiếu với file thật trong repo
[`deploy/deployment.yaml`](../../deploy/deployment.yaml) dòng 9-15:
```yaml
replicas: 1
revisionHistoryLimit: 5
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```
`maxUnavailable: 0` nghĩa là trong lúc update, không được phép có lúc nào 0 pod sẵn sàng phục vụ — ưu tiên tính sẵn sàng hơn tốc độ update. Đây là lựa chọn hợp lý cho service nội bộ như `mcp-superset`.

## Thực hành
```bash
kubectl create deployment demo --image=nginx:1.27 --replicas=2 --dry-run=client -o yaml > deploy.yaml
kubectl apply -f deploy.yaml
kubectl get deployment,rs,pods

# Cập nhật image và theo dõi rollout
kubectl set image deployment/demo nginx=nginx:1.28
kubectl rollout status deployment/demo
kubectl rollout history deployment/demo

# Rollback về bản trước
kubectl rollout undo deployment/demo

# Scale nhanh
kubectl scale deployment/demo --replicas=4
```

## Bài tập tự làm
1. Áp dụng [`deploy/deployment.yaml`](../../deploy/deployment.yaml) thật của repo lên minikube (namespace `dataplatform` sẽ cần tạo trước bằng `kubectl create namespace dataplatform`; secret `mcp-superset-credentials` tạo bằng giá trị giả — xem Ngày 3).
2. Đổi `replicas` từ 1 lên 3, apply lại, quan sát 3 Pod mới được tạo với cùng label `app: mcp-superset`.
3. Cố tình đổi image tag thành một tag không tồn tại, apply, rồi dùng `kubectl rollout undo` để quay lại — đây là thao tác rollback thường gặp trong đề thi.

## Checklist trước khi qua Ngày 3
- [ ] Giải thích được luồng Deployment → ReplicaSet → Pod bằng lời của mình.
- [ ] Thực hiện được rolling update và rollback bằng `kubectl set image` / `kubectl rollout undo`.
- [ ] Hiểu sự khác biệt `maxSurge` vs `maxUnavailable`.
