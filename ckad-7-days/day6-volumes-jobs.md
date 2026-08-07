# Ngày 6 — Volumes, multi-container pattern, Jobs/CronJobs

## Mục tiêu hôm nay
Phủ nốt các chủ đề nhỏ nhưng chắc chắn xuất hiện trong đề CKAD: volumes, multi-container pod pattern (sidecar/init container), Job/CronJob.

## Đọc trước
- [Volumes](https://kubernetes.io/docs/concepts/storage/volumes/)
- [Init Containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/)
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [CronJob](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)

## Khái niệm cốt lõi
- `emptyDir`: volume tạm, sống cùng vòng đời Pod, mất khi Pod bị xoá — dùng cho cache/scratch space (đúng như `/tmp` trong `deployment.yaml`).
- Init container chạy **tuần tự và xong hết trước** khi container chính khởi động — dùng để chờ dependency sẵn sàng hoặc chuẩn bị dữ liệu.
- Sidecar container chạy **song song** với container chính trong cùng Pod, chia sẻ network/volume — dùng cho logging agent, proxy...
- Job chạy đến khi hoàn thành thì dừng (không tự restart vô hạn như Deployment); CronJob là Job chạy theo lịch cron.

## Đối chiếu với file thật trong repo
[`deploy/deployment.yaml`](../../deploy/deployment.yaml) dòng 80-85:
```yaml
volumeMounts:
  - name: tmp
    mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
```
Đây là ví dụ `emptyDir` điển hình: vì `readOnlyRootFilesystem: true` (Ngày 4) khoá toàn bộ filesystem, ứng dụng cần một nơi ghi tạm hợp lệ nên mount riêng `/tmp` bằng `emptyDir`.

## Thực hành
```bash
# Job chạy 1 lần
kubectl create job demo-job --image=busybox -- sh -c "echo hello; sleep 5"
kubectl get jobs
kubectl logs job/demo-job

# CronJob chạy mỗi phút (chỉ để luyện tập, xoá ngay sau khi test)
kubectl create cronjob demo-cron --image=busybox --schedule="*/1 * * * *" -- sh -c "date"
kubectl get cronjobs
kubectl delete cronjob demo-cron
```

## Bài tập tự làm
1. Viết 1 Pod có init container kiểm tra 1 Service đã sẵn sàng (`wget` tới service, retry) trước khi container chính khởi động — pattern "wait-for-dependency" rất hay gặp trong đề CKAD.
2. Thử đổi `emptyDir: {}` trong bản copy `deployment.yaml` thành `emptyDir: {sizeLimit: 10Mi}`, hiểu ý nghĩa giới hạn dung lượng.
3. Tạo 1 CronJob chạy mỗi 5 phút, giới hạn `successfulJobsHistoryLimit: 3` để không tích luỹ quá nhiều Job cũ.

## Đào sâu / nâng cao

### PersistentVolume / PersistentVolumeClaim — khác biệt cốt tử với emptyDir
- `emptyDir` mất dữ liệu khi Pod bị xoá — chỉ phù hợp cho scratch space. Có biến thể `emptyDir.medium: Memory` để dùng RAM thay vì disk (tăng tốc nhưng tính vào giới hạn memory của Pod).
- `PersistentVolumeClaim` (PVC) là "đơn xin cấp phát storage" do người viết Pod tạo ra; `PersistentVolume` (PV) là "kho storage thật" — có thể do admin tạo tay hoặc do `StorageClass` tự động cấp phát (dynamic provisioning). PVC và PV được ghép cặp (bind) 1-1 dựa trên `accessModes`, dung lượng, và `storageClassName` khớp nhau.
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  storageClassName: standard
  resources:
    requests:
      storage: 1Gi
```
Rồi mount vào Pod bằng `volumes: - name: data / persistentVolumeClaim: { claimName: data-pvc }`.

3 loại `accessModes` cần phân biệt:
- `ReadWriteOnce` (RWO): mount ghi được bởi **1 node** tại 1 thời điểm (nhiều Pod trên cùng node vẫn mount chung được, nhưng khác node thì không) — phổ biến nhất cho database.
- `ReadOnlyMany` (ROX): nhiều node mount đồng thời, chỉ đọc.
- `ReadWriteMany` (RWX): nhiều node mount đồng thời, đọc/ghi — cần loại storage backend hỗ trợ (NFS, CephFS...), không phải storage nào cũng có.

`StorageClass` quyết định PV được cấp phát động hay phải tạo tay; `reclaimPolicy` (`Delete` hay `Retain`) quyết định PV có bị xoá theo khi PVC bị xoá hay không — `Retain` an toàn hơn cho dữ liệu quan trọng vì giữ lại PV (và dữ liệu) ngay cả khi PVC bị lỡ tay xoá.

Đọc: [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/) và [Persistent Volume access modes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/#access-modes).

### `subPath` — mount 1 file từ ConfigMap thay vì cả thư mục
```yaml
volumeMounts:
  - name: config-vol
    mountPath: /app/config.yaml
    subPath: config.yaml
```
Dùng khi chỉ muốn mount 1 key cụ thể thành 1 file, không muốn ghi đè toàn bộ thư mục đích (tránh mất các file khác vốn có trong thư mục đó — nếu mount cả ConfigMap vào 1 thư mục đã có file khác, toàn bộ thư mục đó sẽ bị **thay thế hoàn toàn** bởi nội dung ConfigMap, không phải merge). `subPath` cũng hữu ích khi 1 Pod cần mount nhiều phần khác nhau của cùng 1 volume vào nhiều đường dẫn khác nhau (ví dụ PVC dùng chung nhưng mỗi container chỉ thấy 1 thư mục con).

Đánh đổi: file mount bằng `subPath` **không** tự cập nhật khi ConfigMap đổi (khác với mount cả thư mục ở Ngày 3) — vì cơ chế symlink-swap atomic (giải thích ở Ngày 3) chỉ áp dụng cho mount nguyên thư mục, `subPath` bị bind-mount thẳng vào 1 file cụ thể nên mất khả năng tự cập nhật.

Đọc: [Using subPath](https://kubernetes.io/docs/concepts/storage/volumes/#using-subpath).

### Native sidecar container (K8s 1.29+)
Từ bản ổn định 1.29, khai sidecar đúng chuẩn bằng cách đặt trong `initContainers` kèm `restartPolicy: Always`:
```yaml
initContainers:
  - name: log-shipper
    image: fluent-bit
    restartPolicy: Always   # biến init container này thành "sidecar" thật
```
Sidecar kiểu này có vòng đời đặc biệt:
1. Khởi động **trước** container chính (giống init container thường).
2. Không chặn container chính khởi động — K8s coi sidecar là "đã sẵn sàng" ngay khi container ở trạng thái `Running` (không cần đợi nó tự thoát như init container thường).
3. Tự động **restart** nếu crash trong suốt vòng đời Pod (nhờ `restartPolicy: Always`), giống hệt container chính.
4. Bị **dừng sau cùng** khi Pod terminate — đảm bảo container chính (ví dụ ứng dụng ghi log) vẫn còn sidecar (ví dụ log shipper) sống để nhận log cuối cùng trước khi cả Pod tắt hẳn.

Khác hẳn init container thường (chạy 1 lần, phải exit thành công thì container tiếp theo mới chạy) và khác pattern "sidecar giả" thời trước 1.29 (đặt trong `containers` bình thường, không đảm bảo thứ tự khởi động, cả Pod chỉ `Ready` khi **mọi** container kể cả sidecar đều pass readinessProbe — dễ gây treo Pod nếu sidecar có bug).

Đọc: [Sidecar Containers](https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/).

### `restartPolicy` của Job ảnh hưởng thế nào
Job chỉ chấp nhận `restartPolicy: Never` hoặc `OnFailure` ở cấp Pod template (không được `Always` như Deployment, vì Job cần có khái niệm "hoàn thành" — `Always` sẽ khiến Job không bao giờ kết thúc).
- `Never`: Pod thất bại thì **tạo Pod mới** thay thế (không restart container trong Pod cũ) — số Pod thất bại được giữ lại để xem log, dễ debug hơn.
- `OnFailure`: container trong **cùng Pod** tự restart khi thất bại (giống cơ chế của Deployment) — không tạo Pod mới, nhanh hơn nhưng log của các lần thất bại trước bị mất trừ khi xem `kubectl logs --previous`.

`backoffLimit` (mặc định 6) giới hạn tổng số lần retry trước khi Job bị đánh dấu `Failed` hẳn — thời gian chờ giữa các lần retry tăng dần theo cấp số nhân (exponential backoff, tối đa 6 phút).

`completions`/`parallelism` kiểm soát chạy bao nhiêu Pod tổng cộng và bao nhiêu Pod chạy song song cùng lúc:
```yaml
spec:
  completions: 5     # cần 5 Pod hoàn thành thành công
  parallelism: 2     # tối đa 2 Pod chạy cùng lúc
  backoffLimit: 4
```
Nếu không khai `completions`, Job coi là "hoàn thành" ngay khi **1** Pod chạy thành công. CKAD hay hỏi viết Job chạy song song nhiều Pod xử lý theo kiểu "hàng đợi công việc" (work queue) — dùng `parallelism` mà không khai `completions`, các Pod tự phối hợp dừng khi hàng đợi rỗng.

Đọc: [Parallel Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/#parallel-jobs) và [Pod Backoff Failure Policy](https://kubernetes.io/docs/concepts/workloads/controllers/job/#pod-backoff-failure-policy).

## Bài tập nâng cao
1. Tạo 1 PVC `ReadWriteOnce` với `storageClassName: standard` trên minikube (mặc định có sẵn StorageClass `standard`), mount vào 1 Pod, ghi 1 file vào đó, xoá Pod và tạo Pod mới mount cùng PVC — xác nhận file vẫn còn (khác hẳn hành vi của `emptyDir`).
2. Mount cùng 1 ConfigMap vào 1 thư mục **đã có sẵn file khác** trong image (ví dụ mount đè lên `/etc/nginx/conf.d/`), quan sát các file gốc trong thư mục đó biến mất — sau đó sửa lại bằng `subPath` để chỉ mount đúng 1 file cần thiết, giữ nguyên các file gốc khác.
3. Viết 1 Pod có native sidecar (K8s 1.29+, `initContainers` với `restartPolicy: Always`) chạy `tail -f /var/log/app.log`, container chính ghi log liên tục vào file đó qua `emptyDir` dùng chung — cố tình `kubectl exec` vào sidecar và `kill 1` để giả lập crash, quan sát sidecar tự restart mà container chính không bị ảnh hưởng.
4. Viết 1 Job với `completions: 6`, `parallelism: 2`, mỗi Pod chạy `sh -c "echo Processing $RANDOM; sleep 3"` — quan sát bằng `kubectl get pods -w` để thấy đúng tối đa 2 Pod chạy song song cho tới khi đủ 6 lần hoàn thành.
5. Viết 1 Job cố tình luôn thất bại (`exit 1`), đặt `backoffLimit: 2`, `restartPolicy: Never` — quan sát đúng 3 Pod được tạo ra (1 lần đầu + 2 lần retry) trước khi Job chuyển sang trạng thái `Failed`, dùng `kubectl get pods --selector=job-name=<job>` để đếm.

## Checklist trước khi qua Ngày 7
- [ ] Phân biệt được init container và sidecar container (cả kiểu cũ lẫn native sidecar 1.29+).
- [ ] Viết được Job/CronJob bằng cả imperative command và YAML.
- [ ] Hiểu vì sao `mcp-superset` cần `emptyDir` cho `/tmp`.
- [ ] Phân biệt được `emptyDir` và PVC, biết khi nào cần cái nào.
- [ ] Viết được Job với `completions`/`parallelism` > 1.
