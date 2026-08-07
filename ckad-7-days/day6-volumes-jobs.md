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

## Checklist trước khi qua Ngày 7
- [ ] Phân biệt được init container và sidecar container.
- [ ] Viết được Job/CronJob bằng cả imperative command và YAML.
- [ ] Hiểu vì sao `mcp-superset` cần `emptyDir` cho `/tmp`.
