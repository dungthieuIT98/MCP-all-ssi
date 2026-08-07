# Ngày 5 — Service, networking, Ingress

## Mục tiêu hôm nay
Hiểu cách traffic đi từ ngoài internet vào tới đúng Pod — domain "Services & Networking" chiếm tỉ trọng lớn trong đề CKAD.

## Đọc trước
- [Service — Kubernetes docs](https://kubernetes.io/docs/concepts/services-networking/service/)
- [DNS for Services and Pods](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/)
- [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/)

## Khái niệm cốt lõi
- Service dùng `selector` (khớp label trên Pod) để biết nên forward traffic tới Pod nào — không quan tâm Pod bị xoá/tạo lại bao nhiêu lần.
- 4 loại Service chính: `ClusterIP` (mặc định, chỉ nội bộ cluster), `NodePort`, `LoadBalancer`, `ExternalName`. CKAD chủ yếu test `ClusterIP` và `NodePort`.
- DNS nội bộ: gọi Service từ Pod khác cùng namespace chỉ cần `<service-name>`, khác namespace cần `<service-name>.<namespace>.svc.cluster.local`.
- Ingress là lớp router HTTP/HTTPS phía trên Service, cần một Ingress Controller (ví dụ nginx) chạy sẵn trong cluster mới hoạt động — bản thân object Ingress chỉ là cấu hình định tuyến, không tự chạy proxy.

## Đối chiếu với file thật trong repo
[`deploy/service.yaml`](../../deploy/service.yaml):
```yaml
selector:
  app: mcp-superset
ports:
  - name: http
    port: 8000
    targetPort: http
```
`targetPort: http` tham chiếu tên port (không phải số) — khớp với `ports[0].name: http` trong [`deploy/deployment.yaml`](../../deploy/deployment.yaml#L40-L42). Dùng tên port thay vì số giúp đổi `containerPort` sau này không cần sửa Service.

[`deploy/ingress.yaml`](../../deploy/ingress.yaml): định tuyến host `data-mcp-superset.ssi.com.vn` → Service `mcp-superset` port 8000, bắt buộc TLS (`ssl-redirect: "true"`, `secretName: ssi-tls`), dùng `ingressClassName: nginx`.

## Thực hành
```bash
kubectl apply -f deploy/service.yaml -n dataplatform
kubectl get svc -n dataplatform
kubectl get endpoints mcp-superset -n dataplatform   # xem Service có tìm thấy Pod nào không — endpoints rỗng = selector sai hoặc Pod chưa Ready

# Test DNS nội bộ từ một pod tạm
kubectl run tmp-shell --rm -it --image=busybox -n dataplatform -- sh
# trong shell: wget -qO- http://mcp-superset:8000/mcp
```

## Bài tập tự làm
1. Cố tình sửa `selector` trong bản copy của `service.yaml` sai 1 ký tự, apply, dùng `kubectl get endpoints` để chẩn đoán vì sao Service "không thấy" Pod nào — đây là bài troubleshoot rất hay gặp trong đề thi.
2. Tạo thêm 1 Service kiểu `NodePort` cho cùng Deployment, so sánh với `ClusterIP`.
3. Nếu có sẵn ingress controller trên minikube (`minikube addons enable ingress`), áp `deploy/ingress.yaml` (sửa lại `secretName`/host cho môi trường test) và quan sát request đi qua ingress tới service.

## Checklist trước khi qua Ngày 6
- [ ] Biết dùng `kubectl get endpoints` để chẩn đoán Service không route được traffic.
- [ ] Giải thích được vì sao Ingress cần Ingress Controller mới hoạt động.
- [ ] Hiểu named port giúp gì khi maintain YAML lâu dài.
