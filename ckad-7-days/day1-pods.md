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

## Đào sâu / nâng cao

### Labels, Selectors, Annotations — dễ nhầm nhưng hay bị hỏi
- **Label**: key-value gắn lên object để nhóm/lọc (`app: mcp-superset`). Dùng cho `selector` của Service/Deployment — **bắt buộc phải khớp chính xác** (so khớp string, không có khái niệm "gần đúng").
- **Annotation**: key-value để lưu metadata không dùng cho việc chọn lọc (ví dụ `nginx.ingress.kubernetes.io/ssl-redirect` trong [`ingress.yaml`](../../deploy/ingress.yaml#L7)) — Ingress Controller đọc annotation để biết cách cấu hình hành vi riêng, không dùng label vì không cần định tuyến/lọc. Annotation có thể chứa giá trị dài, dạng JSON/text tự do — label thì bị giới hạn 63 ký tự và chỉ chấp nhận `[a-z0-9A-Z]` cùng `-_.`.
- **2 kiểu selector**: *equality-based* (`app=mcp-superset`, `env!=prod`) và *set-based* (`environment in (production, qa)`, `tier notin (frontend)`, `partition` — chỉ kiểm tra key tồn tại). Set-based mạnh hơn nhưng chỉ dùng được ở một số chỗ (ví dụ `NetworkPolicy.podSelector`, `kubectl get -l`), **không** dùng được trong `spec.selector` của Service/ReplicaSet — 2 chỗ này chỉ chấp nhận equality-based vì nó cần map trực tiếp thành `matchLabels`.
- `matchLabels` vs `matchExpressions` trong `spec.selector` của Deployment/ReplicaSet: `matchLabels` là rút gọn của equality-based; `matchExpressions` cho phép set-based (`operator: In/NotIn/Exists/DoesNotExist`) — CKAD có thể yêu cầu viết `matchExpressions` thay vì `matchLabels` đơn giản.
- Lệnh hay dùng khi thi:
```bash
kubectl label pod <name> tier=backend
kubectl label pod <name> tier=frontend --overwrite   # bắt buộc --overwrite nếu label đã tồn tại, nếu không lệnh sẽ báo lỗi
kubectl label pod <name> tier-                        # dấu "-" ở cuối = xoá label
kubectl get pods -l app=mcp-superset
kubectl get pods -l 'environment in (production,qa)'  # set-based, nhớ quote để shell không hiểu nhầm dấu ngoặc
kubectl get pods --show-labels
kubectl get pods -L app,tier                           # hiện label app, tier thành cột riêng trong output
```
- Đọc: [Labels and Selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/) và [Annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/).

### Multi-container Pod — 3 pattern chính thức (Kubernetes patterns)
1. **Sidecar**: container phụ chạy song song hỗ trợ container chính (log shipper, proxy). Từ K8s 1.28+, sidecar có thể khai báo qua `initContainers` với `restartPolicy: Always` để được quản lý vòng đời như sidecar thật thay vì init container thường (xem chi tiết ở Ngày 6).
2. **Ambassador**: container phụ đóng vai trò proxy ra ngoài (ví dụ proxy tới DB ở địa chỉ khác nhau theo môi trường) — container chính chỉ cần gọi `localhost`, ambassador lo việc route đi đâu.
3. **Adapter**: container phụ chuẩn hoá output của container chính (ví dụ convert log format cho hệ thống monitoring hiểu được) trước khi expose ra ngoài Pod.

Trong đề thi, dạng hay gặp nhất là ghép 2 container trong 1 Pod, chia sẻ volume `emptyDir`, container A ghi file, container B đọc. Điểm hay bị sai khi mới học:
- 2 container trong cùng Pod chia sẻ **network namespace** (cùng địa chỉ IP/localhost, khác port thì gọi qua `localhost:<port>`) nhưng **không tự động chia sẻ filesystem** — muốn chia sẻ file bắt buộc phải khai `volumes` + `volumeMounts` ở cả hai container, trỏ cùng 1 volume.
- Container trong cùng Pod không có DNS riêng cho nhau — không thể gọi `curl container-b:8080`, chỉ có thể `curl localhost:8080` vì dùng chung network namespace.
- `kubectl logs <pod> -c <container-name>` bắt buộc chỉ định `-c` khi Pod có nhiều hơn 1 container, nếu không sẽ báo lỗi.

Đọc: [Multi-container pods (Cluster Networking)](https://kubernetes.io/docs/concepts/cluster-administration/networking/#the-kubernetes-network-model) và [Kubernetes.io blog — Container Design Patterns](https://kubernetes.io/blog/2016/06/container-design-patterns/).

### Namespace và resource quota
- Namespace cô lập tên object (2 object cùng tên nhưng khác namespace là hợp lệ) và có thể giới hạn tài nguyên bằng `ResourceQuota`/`LimitRange`:
  - `LimitRange`: đặt **default** và **min/max** cho `requests`/`limits` của từng Pod/Container trong namespace — nếu Pod không khai `resources`, LimitRange tự điền giá trị mặc định; nếu Pod khai vượt max, `kubectl apply` sẽ bị từ chối ngay khi tạo (không phải lúc chạy).
  - `ResourceQuota`: giới hạn **tổng** tài nguyên toàn namespace (tổng CPU, tổng memory, tổng số Pod/Service/PVC...) — khi vượt quota, Pod mới không được tạo, báo lỗi `exceeded quota`.
  - Một số object không có namespace (gọi là *cluster-scoped*): `Node`, `PersistentVolume`, `ClusterRole`, `Namespace` chính nó. Phân biệt bằng `kubectl api-resources --namespaced=false`.
- Lệnh: `kubectl create namespace <ns>`, `kubectl config set-context --current --namespace=<ns>` để không phải gõ `-n` mỗi lệnh (dùng nhiều trong lúc thi), `kubectl get resourcequota,limitrange -n <ns>` để xem giới hạn hiện có trước khi tạo Pod mới trong 1 namespace lạ.
- Đọc thêm: [Limit Ranges](https://kubernetes.io/docs/concepts/policy/limit-range/), [Resource Quotas](https://kubernetes.io/docs/concepts/policy/resource-quotas/).

### API deprecation — chủ đề hay bị bỏ sót
- K8s định kỳ loại bỏ API version cũ (ví dụ `extensions/v1beta1` cho Ingress đã bị xoá từ lâu, hiện dùng `networking.k8s.io/v1` như trong [`ingress.yaml`](../../deploy/ingress.yaml#L1)). Quy tắc chung: API ở giai đoạn `alpha` (`v1alpha1`) có thể đổi/xoá bất kỳ lúc nào; `beta` (`v1beta1`) ổn định hơn nhưng vẫn có thể đổi; chỉ `v1` (GA — General Availability) mới được đảm bảo tương thích ngược lâu dài.
- Biết tra `kubectl api-resources` (liệt kê mọi resource + apiVersion nhóm tương ứng) và `kubectl api-versions` (liệt kê mọi group/version cluster đang hỗ trợ) để chọn đúng `apiVersion` khi không nhớ — nhanh hơn nhiều so với đoán rồi apply thử.
- Đọc: [Deprecated API Migration Guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/).

## Bài tập nâng cao
1. Viết 1 Deployment với `spec.selector.matchExpressions` (không dùng `matchLabels`) chọn Pod có label `tier in (backend, worker)` — apply và xác nhận bằng `kubectl get pods -l 'tier in (backend,worker)'`.
2. Tạo 1 namespace mới, áp 1 `LimitRange` đặt `default.cpu: 200m` và `max.memory: 512Mi`, sau đó tạo 1 Pod không khai `resources` — dùng `kubectl describe pod` xác nhận Pod tự nhận giá trị default từ LimitRange. Thử tạo tiếp 1 Pod khai `limits.memory: 1Gi` (vượt max) và quan sát lỗi bị từ chối ngay lúc `apply`.
3. Tạo 1 `ResourceQuota` giới hạn `pods: "2"` trong namespace đó, cố tạo Pod thứ 3 và đọc thông báo lỗi để hiểu quota chặn ở bước nào.
4. Viết 1 Pod 2 container theo pattern **Adapter**: container A (ví dụ `busybox`) ghi log dạng thô vào file trong `emptyDir` mỗi 5 giây, container B đọc file đó và in ra định dạng khác (`sh -c "while true; do cat /data/log.txt; sleep 5; done"`). Xác nhận bằng `kubectl logs <pod> -c <container-b>`.
5. Chạy `kubectl api-resources | grep -i ingress` và `kubectl api-versions | grep networking` trên cluster test — đối chiếu `apiVersion` trả về với `apiVersion` đang dùng trong [`ingress.yaml`](../../deploy/ingress.yaml#L1) để xác nhận chúng khớp nhau.

## Checklist trước khi qua Ngày 2
- [ ] Tự gõ được 1 file Pod YAML hoàn chỉnh mà không copy mẫu.
- [ ] Biết đọc `kubectl describe pod` để tìm nguyên nhân lỗi (Events ở cuối output).
- [ ] Thành thạo `kubectl explain <resource>.<field>`.
- [ ] Phân biệt được label và annotation, biết khi nào dùng cái nào.
- [ ] Viết được 1 Pod 2-container chia sẻ volume.
