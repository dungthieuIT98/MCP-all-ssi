# Lộ trình 7 ngày ôn thi CKAD (Certified Kubernetes Application Developer)

Bộ tài liệu này dùng 4 manifest thật trong [`deploy/`](../../deploy) của repo `mcp-superset` làm ví dụ đối chiếu xuyên suốt, thay vì ví dụ trừu tượng.

## Vì sao CKAD chứ không phải CKA
CKAD tập trung vào việc **viết và deploy ứng dụng** (Pod, Deployment, Service, ConfigMap, Secret, probes, resource limits) — đúng công việc dev/engineer đang làm với `mcp-superset`. CKA thiên về vận hành cluster (etcd, RBAC, node, networking control-plane) — không cần cho việc viết manifest ứng dụng.

## Định dạng thi (tham khảo, xem lại trang chính thức trước khi thi vì lịch/tỉ lệ có thể đổi theo kỳ)
- Thi thực hành 100% trên terminal (performance-based), không trắc nghiệm.
- Được phép mở 1 tab tài liệu chính thức [kubernetes.io/docs](https://kubernetes.io/docs/) trong lúc thi.
- Trọng số domain chính: Application Design & Build, Application Deployment, Application Observability & Maintenance, Application Environment/Configuration/Security, Services & Networking.
- Nguồn chính thức: [CNCF — CKAD Certification](https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/) và [Curriculum trên GitHub](https://github.com/cncf/curriculum).

## Cách dùng 7 file này
- Mỗi ngày: đọc phần lý thuyết ngắn → đọc doc chính thức được link → thực hành trên `minikube`/`kind` → đối chiếu với file thật trong `deploy/`.
- Vì thi là thực hành gõ lệnh, **ưu tiên gõ tay `kubectl`/YAML**, hạn chế copy-paste, và tập quen `kubectl explain`, `--dry-run=client -o yaml` để tự sinh khung YAML nhanh trong lúc thi.
- Ngày 7 là ngày luyện đề mô phỏng, không đọc lý thuyết mới.

## Danh sách file
1. [Ngày 1 — Pod & Container cơ bản](./day1-pods.md)
2. [Ngày 2 — Deployment, ReplicaSet, rolling update](./day2-deployments.md)
3. [Ngày 3 — ConfigMap, Secret, biến môi trường](./day3-config-secrets.md)
4. [Ngày 4 — Probes, resource limits, security context](./day4-probes-security.md)
5. [Ngày 5 — Service, networking, Ingress](./day5-services-networking.md)
6. [Ngày 6 — Volumes, multi-container pattern, Jobs](./day6-volumes-jobs.md)
7. [Ngày 7 — Luyện đề mô phỏng & checklist ngày thi](./day7-mock-exam.md)

## Lưu ý theo chuẩn SSI khi thực hành
- Chỉ thực hành trên cluster cá nhân (`minikube`/`kind`) hoặc môi trường được cấp riêng cho luyện thi — không áp thử nghiệm lên cluster nội bộ SSI đang chạy dịch vụ thật.
- Không dùng giá trị secret thật (username/password Superset, token nội bộ...) khi luyện tập — luôn dùng giá trị giả (`dummy-user`, `dummy-pass`).
- Thay đổi thật lên manifest trong `deploy/` của repo vẫn phải qua review/PR như bình thường, không commit thẳng lên nhánh chính.
