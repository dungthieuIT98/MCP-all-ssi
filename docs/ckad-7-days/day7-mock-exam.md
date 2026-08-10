# Ngày 7 — Luyện đề mô phỏng & checklist ngày thi

## Mục tiêu hôm nay
Không học lý thuyết mới — chỉ luyện tốc độ và phản xạ dưới áp lực thời gian, mô phỏng đúng điều kiện thi thật.

## Nguồn luyện đề chính thức/uy tín
- [Killer Shell CKAD simulator (đi kèm khi mua voucher CKAD chính thức từ Linux Foundation)](https://killer.sh/ckad)
- [Kubernetes documentation](https://kubernetes.io/docs/) — tập dùng thanh tìm kiếm trong lúc luyện, vì đây là tài nguyên duy nhất được phép mở khi thi thật.

## Mô phỏng điều kiện thi
- Đặt đồng hồ đếm ngược 2 giờ (thời lượng thi CKAD chính thức — kiểm tra lại thời lượng chính xác trên trang Linux Foundation trước khi thi vì có thể thay đổi theo kỳ).
- Chỉ dùng terminal + 1 tab `kubernetes.io/docs` — không tra Google, không hỏi AI.
- Luyện set alias/context nhanh lúc đầu giờ thi:
```bash
alias k=kubectl
export do="--dry-run=client -o yaml"
source <(kubectl completion bash)   # hoặc zsh tương ứng nếu dùng zsh
```

## Đề luyện tự tạo từ chính repo `mcp-superset`
Dùng 4 file trong [`deploy/`](../../deploy) làm đề bài, tự đặt ràng buộc thời gian:

1. **(10 phút)** Từ đầu, viết một Deployment tên `quiz-app`, image `nginx:1.27`, 2 replicas, có `securityContext` giống hệt [`deployment.yaml`](../../deploy/deployment.yaml) (non-root, drop all capabilities, readOnlyRootFilesystem) và mount `emptyDir` cho `/tmp`.
2. **(5 phút)** Viết Service `ClusterIP` cho `quiz-app`, named port `http`, port 8080 → targetPort `http`.
3. **(5 phút)** Viết ConfigMap chứa 2 biến môi trường bất kỳ, bơm vào Deployment bằng `envFrom`.
4. **(5 phút)** Tạo Secret imperative (giá trị giả) chứa `DB_USER`/`DB_PASS`, bơm từng biến bằng `secretKeyRef`.
5. **(10 phút)** Viết Ingress route host `quiz.local` → Service ở bước 2, có TLS.
6. **(10 phút)** Cố tình phá 1 file (sai selector, sai port, sai probe path) và tự troubleshoot bằng `kubectl describe`/`kubectl get events --sort-by=.lastTimestamp`.

Tổng: ~45 phút cho 1 vòng — lặp lại vòng này 2-3 lần trong ngày, mỗi lần cố rút ngắn thời gian.

## Checklist kỹ năng bắt buộc thành thạo trước khi thi
- [ ] Gõ được Deployment/Pod/Service/ConfigMap/Secret bằng imperative command + `--dry-run=client -o yaml` mà không cần nhớ thuộc lòng cú pháp YAML.
- [ ] Dùng `kubectl explain <resource>.<field>` nhanh hơn là mở doc.
- [ ] Đọc `kubectl describe`/`kubectl get events` để tự chẩn đoán lỗi phổ biến: `ImagePullBackOff`, `CrashLoopBackOff`, `OOMKilled`, Service không có endpoints, readiness fail.
- [ ] Chuyển `kubectl context`/namespace nhanh bằng `kubectl config set-context --current --namespace=<ns>` để không phải gõ `-n` mỗi lệnh.
- [ ] Quản lý thời gian: đề thi có nhiều câu, câu nào bí thì đánh dấu (`kubectl` hỗ trợ flag `--record` cũ đã bỏ, dùng note riêng) và làm câu dễ trước.

## Checklist ngày thi
- [ ] Kiểm tra thiết bị/camera/giấy tờ theo yêu cầu của Linux Foundation trước giờ thi ít nhất 30 phút.
- [ ] Dọn bàn làm việc theo quy định giám sát (proctoring) — không có giấy note, điện thoại, màn hình phụ.
- [ ] Nhớ mỗi câu hỏi thường ghi rõ context/namespace cần dùng — luôn `kubectl config use-context <ctx>` đúng câu trước khi làm.
- [ ] Review lại các câu đã làm nếu còn thời gian, ưu tiên kiểm tra lại các câu liên quan `securityContext` và probe vì dễ gõ sai chính tả field.

## Đào sâu / nâng cao — các chủ đề CKAD dễ bị bỏ sót ngoài 6 ngày trên

### Helm cơ bản (nằm trong domain Application Design & Build)
CKAD có thể hỏi khái niệm Helm dù không yêu cầu viết chart phức tạp:
- `Chart`: gói template YAML tái sử dụng, cấu trúc thư mục chuẩn gồm `Chart.yaml` (metadata), `values.yaml` (giá trị mặc định), `templates/` (file YAML có cú pháp Go template `{{ .Values.xxx }}`).
- `Release`: 1 lần install chart vào cluster, có tên riêng — có thể install cùng 1 chart nhiều lần với tên Release khác nhau để chạy song song nhiều bản độc lập.
- `Values`: tham số override template, ưu tiên theo thứ tự: `--set` trên command line > `-f custom-values.yaml` > `values.yaml` mặc định trong chart.
```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install my-release bitnami/nginx --set service.type=ClusterIP
helm upgrade my-release bitnami/nginx --set replicaCount=3
helm rollback my-release 1
helm uninstall my-release
helm template my-release bitnami/nginx   # render YAML ra terminal mà KHÔNG apply lên cluster — dùng để kiểm tra template trước khi install
helm get values my-release               # xem giá trị đang áp dụng cho 1 release đã install
```
Mỗi lần `helm upgrade` tạo 1 revision mới (tương tự ReplicaSet revision của Deployment) — `helm rollback` hoạt động dựa trên cơ chế revision này.

Đọc: [Helm Quickstart](https://helm.sh/docs/intro/quickstart/) và [Helm Chart Template Guide](https://helm.sh/docs/chart_template_guide/getting_started/).

### Kustomize — tuỳ biến YAML không cần template engine
Có sẵn trong `kubectl` (`kubectl apply -k <dir>`), dùng để override YAML gốc theo môi trường (dev/staging/prod) mà không sửa file gốc. Cấu trúc chuẩn: 1 thư mục `base/` chứa YAML gốc + file `kustomization.yaml` liệt kê resource; mỗi môi trường có 1 thư mục `overlays/<env>/` riêng, chứa `kustomization.yaml` trỏ về `base` kèm các `patch` cần áp dụng.
```yaml
# overlays/prod/kustomization.yaml
resources:
  - ../../base
patches:
  - target:
      kind: Deployment
      name: mcp-superset
    patch: |-
      - op: replace
        path: /spec/replicas
        value: 3
images:
  - name: harbor.ssi.com.vn/dataplatform/mcp-superset
    newTag: "2.0"
```
Khác biệt cốt lõi với Helm: Kustomize **không có template engine** (không có biến `{{ }}`), chỉ patch trực tiếp lên YAML thuần bằng JSON Patch hoặc strategic merge — dễ đọc hơn nhưng kém linh hoạt hơn khi cần logic điều kiện phức tạp.

```bash
kubectl kustomize overlays/prod        # xem YAML sau khi patch, không apply
kubectl apply -k overlays/prod         # apply thẳng
```

Đọc: [Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/).

### Custom Resource Definition (CRD) — nhận biết, không cần tự viết controller
CRD cho phép mở rộng Kubernetes API bằng `kind` tự định nghĩa (ví dụ `kind: Certificate` do cert-manager cung cấp) — về bản chất là dạy cho `kube-apiserver` biết thêm 1 loại object mới, `kubectl` thao tác với nó y hệt object built-in (`apply`, `get`, `describe`, `delete`).

Biết đọc 1 CRD lạ bằng:
```bash
kubectl get crd                                    # liệt kê mọi CRD đã cài trong cluster
kubectl explain <custom-kind>                       # tra field như mọi resource khác, miễn CRD có khai OpenAPI schema
kubectl explain <custom-kind>.spec.<field>          # đào sâu field cụ thể
kubectl get <custom-kind> -A                        # xem instance đang tồn tại
```
Đề thi CKAD có thể đưa 1 CRD đã cài sẵn (ví dụ từ 1 Operator) và yêu cầu tạo object từ CRD đó dựa theo doc hiển thị qua `kubectl explain` — không yêu cầu hiểu cách CRD được implement (Controller/Operator đứng sau nó là code Go, nằm ngoài phạm vi CKAD).

Lưu ý: một CRD chỉ định nghĩa **schema**, cần có 1 **Controller/Operator** đang chạy trong cluster mới thực sự "làm gì đó" khi object được tạo — CRD không có Controller tương ứng vẫn nhận `kubectl apply` thành công nhưng object đó chỉ nằm im trong etcd không có tác dụng.

Đọc: [Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/).

### ServiceAccount & RBAC cơ bản (phần overlap giữa CKAD và CKA)
- Mỗi Pod chạy dưới 1 `ServiceAccount` (mặc định là `default` nếu không khai `serviceAccountName`) — token của ServiceAccount được tự động mount vào `/var/run/secrets/kubernetes.io/serviceaccount/` trong container, dùng khi ứng dụng cần tự gọi ngược lại Kubernetes API (ví dụ Operator, CI job trong cluster).
- `Role`/`RoleBinding` (phạm vi 1 namespace) và `ClusterRole`/`ClusterRoleBinding` (toàn cluster, hoặc dùng RoleBinding trỏ tới ClusterRole để giới hạn phạm vi về 1 namespace nhưng tái sử dụng quyền định nghĩa sẵn) — cần biết mức cơ bản để debug lỗi `Forbidden` khi ứng dụng tự gọi K8s API.
```bash
kubectl create serviceaccount app-sa
kubectl create role pod-reader --verb=get,list,watch --resource=pods
kubectl create rolebinding app-sa-binding --role=pod-reader --serviceaccount=default:app-sa

# Gán serviceAccountName cho Pod
# spec.serviceAccountName: app-sa

# Kiểm tra quyền nhanh — lệnh quan trọng nhất để debug RBAC
kubectl auth can-i get pods --as=system:serviceaccount:default:app-sa
kubectl auth can-i delete pods --as=system:serviceaccount:default:app-sa -n dataplatform
```
`kubectl auth can-i` là công cụ chẩn đoán nhanh nhất khi ứng dụng báo lỗi `Forbidden` — kiểm tra ngay trước khi đi tìm Role/RoleBinding bị thiếu ở đâu.

Đọc: [RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) và [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/).

### API deprecation & version skew
Ôn lại `kubectl api-resources -o wide` và `kubectl explain <kind>` để tự tra `apiVersion` đúng — đề thi thường dùng phiên bản K8s cụ thể, một số field/API có thể khác so với tài liệu bạn học nếu chênh version. Luôn kiểm tra version cluster bằng `kubectl version` trước khi tra doc — `kubectl version` hiện cả version client (`kubectl`) và server (control-plane), 2 version này được phép lệch nhau tối đa ±1 minor version theo chính sách skew chính thức.

Đọc: [Kubernetes Version and Version Skew Support Policy](https://kubernetes.io/releases/version-skew-policy/) và [Deprecated API Migration Guide](https://kubernetes.io/docs/reference/using-api/deprecation-guide/).

### Debug container nâng cao — `kubectl debug`
Khi container không có shell (`distroless`/`scratch` image — thường gặp ở image production tối giản để giảm bề mặt tấn công), không thể `kubectl exec -it ... -- sh` vì không có binary shell nào trong image. 3 cách dùng `kubectl debug`:
```bash
# 1. Thêm 1 container debug tạm thời vào CÙNG Pod đang chạy, chia sẻ process namespace với container đích
kubectl debug -it <pod> --image=busybox --target=<container-name> -- sh

# 2. Tạo 1 BẢN SAO của Pod với thêm container debug (không đụng vào Pod gốc đang chạy) — an toàn hơn khi không muốn ảnh hưởng Pod production
kubectl debug <pod> -it --image=busybox --copy-to=debug-pod --container=debug

# 3. Debug thẳng 1 node (chạy Pod đặc quyền trên node đó) — hữu ích khi cần xem log/process ở mức OS
kubectl debug node/<node-name> -it --image=busybox
```
Cách 1 chia sẻ chung process namespace (`--target`) nên có thể thấy và `kill`/`strace` process của container đích — kỹ năng troubleshoot mức nâng cao hay xuất hiện ở câu khó nhất trong đề CKAD (thường là câu cuối, điểm cao nhất).

Đọc: [Debugging Running Pods](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/).

## Bài tập nâng cao
1. Cài Helm trên máy luyện tập (`helm version` để xác nhận), `helm install` 1 chart công khai đơn giản (ví dụ `bitnami/nginx`), dùng `helm get values` và `helm get manifest` để xem giá trị/YAML thực tế đã áp dụng, sau đó `helm upgrade --set replicaCount=3` và `helm rollback` về bản trước.
2. Tự viết 1 cấu trúc Kustomize tối thiểu: `base/` chứa bản rút gọn của [`deploy/deployment.yaml`](../../deploy/deployment.yaml) + `kustomization.yaml`; `overlays/staging/` patch `replicas` thành 2 và đổi image tag. Chạy `kubectl kustomize overlays/staging` để xem kết quả patch mà chưa apply.
3. Cài 1 CRD công khai đơn giản để luyện tập nhận biết (ví dụ CRD của `metrics-server` hoặc bất kỳ Operator nhỏ nào có sẵn Helm chart), dùng `kubectl explain <crd-kind>` để đọc field mà không cần mở doc ngoài, rồi tạo 1 object mẫu dựa hoàn toàn vào output của `kubectl explain`.
4. Tạo 1 ServiceAccount `readonly-sa` chỉ có quyền `get`/`list` Pod trong 1 namespace, gán vào 1 Pod test, `kubectl exec` vào Pod đó và dùng token mount sẵn để tự gọi Kubernetes API bằng `curl` (`curl -sk -H "Authorization: Bearer $(cat /var/run/secrets/kubernetes.io/serviceaccount/token)" https://kubernetes.default.svc/api/v1/namespaces/default/pods`) — quan sát request thành công cho GET nhưng bị `Forbidden` khi thử DELETE.
5. Tạo 1 Pod dùng image `gcr.io/distroless/static` (không có shell), thử `kubectl exec -it <pod> -- sh` và xác nhận lỗi `OCI runtime exec failed: exec: "sh": executable file not found`, sau đó dùng `kubectl debug -it <pod> --image=busybox --target=<container>` để vào được môi trường debug và `ps aux` xem process của container đích.

## Checklist bổ sung sau khi luyện nâng cao
- [ ] Phân biệt được Helm (template engine) và Kustomize (patch thuần) — biết khi nào tổ chức thực tế chọn cái nào.
- [ ] Đọc hiểu 1 CRD lạ bằng `kubectl explain` mà không cần tài liệu ngoài `kubernetes.io`.
- [ ] Dùng `kubectl auth can-i --as=system:serviceaccount:...` để chẩn đoán lỗi `Forbidden` trong dưới 30 giây.
- [ ] Debug được container không có shell bằng `kubectl debug --target`.
