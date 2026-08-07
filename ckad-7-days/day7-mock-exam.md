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
