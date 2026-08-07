# Ngày 1 — Pod & Container cơ bản

## Mục tiêu hôm nay
Hiểu Pod là gì, vòng đời của nó, và cách tạo/troubleshoot bằng `kubectl` — nền tảng bắt buộc trước khi học Deployment.

## Đọc trước
- [Pods — Kubernetes docs](https://kubernetes.io/docs/concepts/workloads/pods/)
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- [kubectl Quick Reference](https://kubernetes.io/docs/reference/kubectl/quick-reference/)

## Khái niệm cốt lõi
- Pod là đơn vị triển khai nhỏ nhất trong K8s — 1 hoặc nhiều container dùng chung network namespace và storage.
- Pod là "phù du" (ephemeral): mất đi không tự hồi sinh nếu tạo trực tiếp bằng `kubectl run` — đây là lý do Ngày 2 cần Deployment.
- Trạng thái Pod: `Pending` → `Running` → `Succeeded`/`Failed`. Container trong Pod còn có `Waiting`/`Running`/`Terminated`.

## Đối chiếu với file thật trong repo
Xem [`deploy/deployment.yaml`](../../deploy/deployment.yaml) dòng 19-28 (`spec.template`) — phần này chính là một PodSpec đầy đủ, chỉ khác là nó nằm lồng trong Deployment thay vì đứng một mình.

## Thực hành (bắt buộc gõ tay, không copy-paste)
```bash
# Cài minikube trước nếu chưa có, rồi khởi động cluster test
minikube start

# Tạo pod nhanh bằng lệnh mệnh lệnh (imperative) — kỹ năng bắt buộc trong thi CKAD vì tiết kiệm thời gian
kubectl run test-pod --image=nginx:1.27 --port=80

# Xem trạng thái, log, chi tiết
kubectl get pods
kubectl describe pod test-pod
kubectl logs test-pod

# Sinh khung YAML từ lệnh imperative — mẹo quan trọng nhất khi thi để không phải nhớ cú pháp
kubectl run test-pod --image=nginx:1.27 --port=80 --dry-run=client -o yaml > pod.yaml

# Exec vào container để debug
kubectl exec -it test-pod -- sh

# Dọn dẹp
kubectl delete pod test-pod
```

## Bài tập tự làm
1. Tự viết tay (không dùng `--dry-run`) một file `pod.yaml` chạy image `nginx:1.27`, container tên `web`, expose port 80, có `resources.requests` là `cpu: 100m, memory: 64Mi`.
2. Áp dụng, sau đó cố tình sửa tên image sai (`nginx:not-exist-tag`) và `kubectl apply` lại — quan sát trạng thái `ImagePullBackOff` bằng `kubectl describe pod`.
3. Dùng `kubectl explain pod.spec.containers` để tra cứu field ngay trên terminal — kỹ năng thay thế việc mở doc khi thi.

## Checklist trước khi qua Ngày 2
- [ ] Tự gõ được 1 file Pod YAML hoàn chỉnh mà không copy mẫu.
- [ ] Biết đọc `kubectl describe pod` để tìm nguyên nhân lỗi (Events ở cuối output).
- [ ] Thành thạo `kubectl explain <resource>.<field>`.
