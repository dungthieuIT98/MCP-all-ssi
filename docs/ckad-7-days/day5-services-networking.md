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

## Đào sâu / nâng cao

### NetworkPolicy — mặc định K8s cho phép mọi traffic
Nếu không có `NetworkPolicy` nào, mọi Pod trong cluster đều gọi được lẫn nhau bất kể namespace ("flat network", đúng nguyên tắc thiết kế mạng gốc của Kubernetes). Muốn giới hạn (ví dụ chỉ cho phép Ingress Controller gọi vào `mcp-superset`, chặn Pod khác), cần viết NetworkPolicy — nhưng lưu ý: NetworkPolicy chỉ có tác dụng nếu **CNI plugin** của cluster hỗ trợ nó (Calico, Cilium... — Flannel mặc định không hỗ trợ; nếu áp NetworkPolicy trên CNI không hỗ trợ, object được tạo thành công nhưng **không có tác dụng gì**, dễ gây ảo tưởng đã bảo mật).

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-only
  namespace: dataplatform
spec:
  podSelector:
    matchLabels:
      app: mcp-superset
  policyTypes: ["Ingress"]
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
```

Các điểm hay gây nhầm lẫn:
- `podSelector: {}` (rỗng) nghĩa là áp dụng cho **mọi Pod** trong namespace đó, không phải "không chọn Pod nào".
- Khi 1 Pod được chọn bởi ít nhất 1 NetworkPolicy có `policyTypes: ["Ingress"]`, Pod đó chuyển sang chế độ **default-deny** cho chiều ingress — chỉ traffic khớp đúng 1 rule nào đó trong **bất kỳ** NetworkPolicy nào áp dụng lên nó mới được phép (nhiều NetworkPolicy cộng dồn theo kiểu OR, không phải AND).
- `policyTypes: ["Egress"]` kiểm soát traffic **đi ra** từ Pod — nếu khai `egress: []` (rỗng) mà có `policyTypes: ["Egress"]`, Pod bị chặn gọi ra **mọi nơi** kể cả DNS (port 53) — lỗi rất hay gặp khi luyện tập là quên mở egress cho DNS khiến Pod không resolve được tên miền.
- `ipBlock` dùng để giới hạn theo dải CIDR (ví dụ chỉ cho phép IP nội bộ công ty) thay vì theo Pod/namespace selector.

Đọc: [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/).

### Ingress path types và multiple rules
`pathType` trong [`ingress.yaml`](../../deploy/ingress.yaml#L19) đang dùng `ImplementationSpecific` (hành vi match do Ingress Controller quyết định, ở đây là nginx — nginx xử lý gần giống `Prefix` theo mặc định). Hai loại khác:
- `Prefix`: match theo tiền tố path, chuẩn hoá theo segment `/` — ví dụ path `/api` khớp `/api`, `/api/`, `/api/v1` nhưng **không** khớp `/apiextra` (vì K8s so khớp theo từng segment `/`, không phải so khớp chuỗi con đơn thuần).
- `Exact`: match chính xác tuyệt đối, phân biệt hoa thường, phải khớp y hệt path yêu cầu (không có dấu `/` thừa ở cuối).
- Khi nhiều rule cùng khớp 1 request, Ingress Controller ưu tiên rule có path **cụ thể/dài hơn** trước.

Một Ingress cũng có thể định tuyến nhiều host/path tới nhiều Service khác nhau trong cùng 1 file (`rules` là mảng):
```yaml
spec:
  rules:
    - host: "api.ssi.com.vn"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: api-svc, port: { number: 80 } }
    - host: "admin.ssi.com.vn"
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service: { name: admin-svc, port: { number: 80 } }
```
`tls.hosts` cũng nhận mảng nhiều host dùng chung 1 `secretName`, hoặc khai nhiều mục trong mảng `tls` để mỗi nhóm host dùng 1 chứng chỉ TLS riêng.

Đọc kỹ: [Ingress path types](https://kubernetes.io/docs/concepts/services-networking/ingress/#path-types).

### Headless Service
`clusterIP: None` tạo Service "headless" — không có IP ảo, DNS trả thẳng về IP của từng Pod thay vì load-balance qua 1 IP chung. Dùng khi client cần biết địa chỉ từng Pod riêng lẻ (ví dụ StatefulSet, peer discovery giữa các node của 1 cluster database). Kết hợp với StatefulSet, mỗi Pod còn có DNS riêng dạng `<pod-name>.<headless-svc-name>.<namespace>.svc.cluster.local` — đây là cơ chế StatefulSet dùng để các Pod tự tìm nhau theo tên cố định.

Đọc: [Headless Services](https://kubernetes.io/docs/concepts/services-networking/service/#headless-services).

### `externalTrafficPolicy` cho NodePort/LoadBalancer
Mặc định `Cluster` cho phép traffic bị forward sang node khác qua kube-proxy (có thể mất source IP thật vì bị SNAT), nhưng đảm bảo traffic luôn cân bằng đều dù Pod chỉ tồn tại trên 1-2 node. Đặt `Local` giữ nguyên source IP nhưng traffic chỉ được route tới Pod đang chạy trên đúng node nhận request — nếu node đó không có Pod nào, request bị drop thẳng (không forward sang node khác) — cần hiểu đánh đổi này khi debug vấn đề "một số client báo lỗi kết nối ngẫu nhiên" trên NodePort.

Đọc: [Preserving the client source IP](https://kubernetes.io/docs/tutorials/services/source-ip/#source-ip-for-services-with-type-nodeport).

## Bài tập nâng cao
1. Trên cluster có CNI hỗ trợ NetworkPolicy (Calico trên `kind`, hoặc `minikube start --cni=calico`), viết 1 NetworkPolicy `podSelector: {}` với `policyTypes: ["Ingress"]` và `ingress: []` (rỗng) áp cho toàn namespace — xác nhận mọi Pod trong namespace đó bị chặn nhận traffic hoàn toàn (default-deny). Sau đó thêm 1 rule cho phép đúng 1 Pod cụ thể gọi vào.
2. Viết 1 NetworkPolicy với `policyTypes: ["Egress"]` chặn hết traffic ra ngoài của 1 Pod, quan sát Pod đó mất luôn khả năng phân giải DNS (`nslookup` timeout) — sau đó sửa lại, mở thêm rule cho phép egress tới port 53 (UDP/TCP) để sửa lỗi.
3. Viết 1 Ingress có 2 path trên cùng 1 host: `/api` (`pathType: Prefix`) trỏ Service A, `/api/admin` (`pathType: Exact`) trỏ Service B — gọi thử `/api/admin`, `/api/adminx`, `/api/other` để xác nhận đúng rule nào được chọn.
4. Tạo 1 headless Service (`clusterIP: None`) cho 1 Deployment có 3 replicas, từ 1 Pod khác chạy `nslookup <service-name>` và quan sát DNS trả về **cả 3 IP Pod** thay vì 1 IP ảo duy nhất như ClusterIP thông thường.
5. Nếu có cluster nhiều node, tạo 1 Service `NodePort` với `externalTrafficPolicy: Local`, gọi vào NodePort của 1 node **không** có Pod chạy trên đó và quan sát request bị drop/timeout — đối chiếu với `externalTrafficPolicy: Cluster` (mặc định) vẫn trả lời bình thường trong cùng tình huống.

## Checklist trước khi qua Ngày 6
- [ ] Biết dùng `kubectl get endpoints` để chẩn đoán Service không route được traffic.
- [ ] Giải thích được vì sao Ingress cần Ingress Controller mới hoạt động.
- [ ] Hiểu named port giúp gì khi maintain YAML lâu dài.
- [ ] Phân biệt được `Prefix`/`Exact`/`ImplementationSpecific` trong Ingress path type.
- [ ] Biết NetworkPolicy mặc định không tồn tại nghĩa là gì, và nó cần CNI hỗ trợ.
