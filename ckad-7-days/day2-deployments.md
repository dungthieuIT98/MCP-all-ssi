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

## Đào sâu / nâng cao

### Deployment không phải lựa chọn duy nhất
CKAD có thể hỏi khi nào **không** dùng Deployment:
- **StatefulSet**: dùng khi Pod cần định danh ổn định (`pod-0`, `pod-1`...) và/hoặc volume riêng bền vững cho từng Pod — ví dụ database. Khác biệt cụ thể với Deployment: Pod tên cố định theo thứ tự (`<name>-0`, `<name>-1`...) thay vì tên ngẫu nhiên; scale lên/xuống theo thứ tự tuần tự (tạo `-0` trước `-1`, xoá `-2` trước `-1` khi scale down) chứ không song song; mỗi Pod có DNS ổn định riêng dạng `<pod-name>.<service-name>.<namespace>.svc.cluster.local` khi dùng kèm headless Service. Đọc: [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/).
- **DaemonSet**: đảm bảo mỗi node chạy đúng 1 Pod (hoặc theo `nodeSelector` — 1 Pod trên mỗi node khớp điều kiện) — dùng cho log agent, monitoring agent, CNI plugin chạy trên toàn cluster. DaemonSet **không có** field `replicas` vì số lượng Pod tự động bằng số node phù hợp — không dùng `kubectl scale` được với DaemonSet. Đọc: [DaemonSet](https://kubernetes.io/docs/concepts/workloads/controllers/daemonset/).
- **Job/CronJob**: việc chạy-xong-thì-dừng (xem Ngày 6), không dùng Deployment vì Deployment đảm bảo Pod chạy **mãi mãi**, tự restart bất kể exit code — không phù hợp cho tác vụ có điểm kết thúc.
- Bảng ghi nhớ nhanh: cần identity ổn định/storage riêng từng Pod → StatefulSet; cần chạy trên mọi node → DaemonSet; cần chạy xong rồi dừng → Job/CronJob; còn lại (web server, API stateless) → Deployment.

### rollout undo tới revision cụ thể
```bash
kubectl rollout history deployment/demo --revision=2   # xem chi tiết 1 revision
kubectl rollout undo deployment/demo --to-revision=2    # rollback về đúng revision đó, không chỉ lùi 1 bước
kubectl rollout pause deployment/demo                   # tạm dừng rollout để gộp nhiều thay đổi
kubectl rollout resume deployment/demo
kubectl rollout restart deployment/demo                 # ép tạo lại toàn bộ Pod mà không đổi image/config, dùng khi cần Pod đọc lại Secret/ConfigMap
```
Lưu ý: `revisionHistoryLimit: 5` trong [`deployment.yaml`](../../deploy/deployment.yaml#L10) giới hạn số ReplicaSet cũ giữ lại — nếu số revision cần rollback về đã bị dọn, `rollout undo --to-revision` sẽ thất bại. Một ReplicaSet chỉ được tính là 1 revision mới khi **PodTemplate** (`spec.template`) thay đổi — đổi `replicas` một mình không tạo revision mới, đổi `image` thì có.

Cách K8s biết revision nào — annotation `deployment.kubernetes.io/revision` tự động gắn lên mỗi ReplicaSet, xem bằng `kubectl get rs -o yaml | grep revision`.

Đọc: [Rolling Back a Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back-a-deployment).

### Chiến lược deploy nâng cao hơn RollingUpdate
- **Recreate**: xoá hết Pod cũ rồi mới tạo Pod mới (`strategy.type: Recreate`) — chấp nhận downtime, dùng khi ứng dụng không chạy được 2 phiên bản song song (ví dụ có migration DB không tương thích ngược, hoặc ứng dụng dùng `ReadWriteOnce` volume không thể mount đồng thời từ 2 Pod).
- **Blue/Green**: chạy song song 2 Deployment độc lập hoàn toàn (`version: blue` và `version: green`), Service trỏ vào 1 trong 2 bằng cách đổi `selector`. Ưu điểm: rollback tức thời (chỉ đổi lại selector), không có giai đoạn lưng chừng 2 phiên bản cùng nhận traffic. Nhược điểm: tốn gấp đôi tài nguyên trong lúc chuyển đổi.
- **Canary**: chạy Deployment phiên bản mới với số `replicas` nhỏ (ví dụ 1/10 tổng), cùng `selector` label với bản cũ để Service chia tải ngẫu nhiên theo tỷ lệ số Pod — không kiểm soát chính xác % traffic bằng core Kubernetes (muốn chia % chính xác theo request phải dùng Ingress Controller hỗ trợ canary annotation, hoặc service mesh).
- Kubernetes core không có field `strategy.type: Canary` hay `BlueGreen` có sẵn — 2 khái niệm này luôn là **kỹ thuật dàn dựng bằng tay** từ Deployment + Service, không phải 1 API riêng. CKAD có thể hỏi bạn tự dàn dựng canary bằng 2 Deployment + 1 Service dùng chung selector.
- Công cụ ngoài như Argo Rollouts/Flagger tự động hoá việc này (rollout theo % traffic, tự rollback khi metric xấu) nhưng nằm ngoài phạm vi thi CKAD.

Đọc: [Deployment strategies (Kubernetes docs)](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy) và [Argo Rollouts — Progressive Delivery](https://argo-rollouts.readthedocs.io/en/stable/features/canary/) (công cụ ngoài, chỉ để tham khảo khái niệm).

### HorizontalPodAutoscaler (HPA) và PodDisruptionBudget (PDB)
- HPA tự scale `replicas` theo CPU/memory hoặc custom metric: `kubectl autoscale deployment demo --min=2 --max=5 --cpu-percent=80`. HPA **cần** Deployment đã khai `resources.requests` (như [`deployment.yaml`](../../deploy/deployment.yaml#L59-L65)) vì % CPU được tính dựa trên `requests`, không có `requests` thì HPA không hoạt động được. Cũng cần Metrics Server chạy sẵn trong cluster để HPA đọc được số liệu thực tế (`kubectl top pods` dùng chung nguồn dữ liệu này).
- PDB giới hạn số Pod tối đa được phép "gián đoạn" cùng lúc (do node drain, không phải do rolling update) — quan trọng để tránh mất toàn bộ replica khi bảo trì node. Khai bằng `minAvailable` (số/% Pod tối thiểu phải còn chạy) hoặc `maxUnavailable` (số/% Pod tối đa được phép gián đoạn) — chỉ chọn 1 trong 2, không khai cả hai cùng lúc.
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: mcp-superset-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: mcp-superset
```
Đọc: [HorizontalPodAutoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) và [Pod Disruption Budget](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets).

## Bài tập nâng cao
1. Tạo 1 Deployment `demo` với `resources.requests.cpu: 100m`, áp `kubectl autoscale deployment demo --min=1 --max=3 --cpu-percent=50` (nếu cluster test có Metrics Server — trên minikube chạy `minikube addons enable metrics-server` trước). Tạo tải giả bằng cách chạy 1 Pod gọi liên tục vào Deployment, quan sát `kubectl get hpa` để thấy `replicas` tự tăng.
2. Viết 1 PodDisruptionBudget với `minAvailable: 2` cho 1 Deployment có `replicas: 3`, sau đó thử `kubectl drain <node>` (trên cluster nhiều node) và quan sát PDB chặn việc drain nếu số Pod còn lại sẽ dưới 2.
3. Tự dàn dựng 1 canary release thủ công: tạo 2 Deployment `app-stable` (`replicas: 4`, label `app: demo, track: stable`) và `app-canary` (`replicas: 1`, label `app: demo, track: canary`), 1 Service `selector: {app: demo}` (không có `track`) để traffic rơi vào cả hai theo tỷ lệ 4:1. Gọi liên tục vào Service và đếm log xem tỷ lệ request có xấp xỉ 80/20 không.
4. Làm 3 lần `kubectl set image` liên tiếp để tạo 3 revision khác nhau, dùng `kubectl rollout undo --to-revision=1` để quay thẳng về revision đầu tiên (không phải revision liền trước) — xác nhận bằng `kubectl rollout history`.
5. Đổi `strategy.type` của 1 Deployment từ `RollingUpdate` sang `Recreate`, cập nhật image, quan sát bằng `kubectl get pods -w` cách toàn bộ Pod cũ bị xoá hết trước khi Pod mới xuất hiện — so sánh khoảng thời gian downtime với `RollingUpdate`.

## Checklist trước khi qua Ngày 3
- [ ] Giải thích được luồng Deployment → ReplicaSet → Pod bằng lời của mình.
- [ ] Thực hiện được rolling update và rollback bằng `kubectl set image` / `kubectl rollout undo`.
- [ ] Hiểu sự khác biệt `maxSurge` vs `maxUnavailable`.
- [ ] Biết khi nào chọn StatefulSet/DaemonSet/Job thay vì Deployment.
- [ ] Rollback được về đúng 1 revision cụ thể, không chỉ lùi 1 bước.
