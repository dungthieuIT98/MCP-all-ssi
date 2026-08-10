# Ngày 4 — Probes, resource limits, security context

## Mục tiêu hôm nay
Làm chủ 3 nhóm field xuất hiện dày đặc trong đề thi thực hành: liveness/readiness probe, resource requests/limits, và securityContext.

## Đọc trước
- [Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#liveness-readiness-startup-probes)
- [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)

## Khái niệm cốt lõi
- `readinessProbe` thất bại → Pod bị gỡ khỏi Service (không nhận traffic) nhưng **không** bị restart.
- `livenessProbe` thất bại → container bị **restart**.
- `requests` là mức tài nguyên tối thiểu để scheduler chọn node; `limits` là trần tối đa, vượt trần CPU sẽ bị throttle, vượt trần memory sẽ bị `OOMKilled`.
- `securityContext` ở cấp Pod áp dụng cho mọi container; ở cấp container ghi đè lên cấp Pod.

## Đối chiếu với file thật trong repo
[`deploy/deployment.yaml`](../../deploy/deployment.yaml):
- Dòng 24-28 (Pod-level securityContext): `runAsNonRoot: true`, `runAsUser/runAsGroup: 1000`, `fsGroup: 1000` — bắt buộc container không chạy bằng root, đúng chuẩn Build & Container Standards của SSI.
- Dòng 35-39 (container-level): `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]` — giảm tối đa bề mặt tấn công nếu container bị chiếm quyền.
- Dòng 59-65: `requests`/`limits` cho cpu và memory.
- Dòng 67-78: `livenessProbe`/`readinessProbe` cùng gọi `GET /mcp` nhưng khác `initialDelaySeconds`/`periodSeconds`.
- Dòng 80-85: vì `readOnlyRootFilesystem: true` khiến toàn bộ filesystem chỉ đọc, ứng dụng cần ghi tạm vào `/tmp` nên có `emptyDir` mount riêng cho `/tmp` — đây là pattern quan trọng cần nhớ khi bật `readOnlyRootFilesystem`.

## Thực hành
```bash
# Áp dụng và quan sát Pod không khởi động được nếu image không hỗ trợ non-root
kubectl apply -f deploy/deployment.yaml -n dataplatform
kubectl describe pod -l app=mcp-superset -n dataplatform

# Thử giả lập probe fail: exec vào container và đổi trạng thái app (nếu có endpoint debug), hoặc sửa tạm path probe sai rồi quan sát readiness
kubectl edit deployment mcp-superset -n dataplatform
```

## Bài tập tự làm
1. Tự viết 1 Pod YAML có `readOnlyRootFilesystem: true` nhưng **không** mount `emptyDir` cho `/tmp` — chạy ứng dụng cần ghi file tạm và quan sát lỗi `Read-only file system`. Sau đó thêm volume để sửa lỗi — đây là bug rất hay gặp trong đề thi.
2. Đổi `livenessProbe.path` thành một path không tồn tại (`/wrong`), apply, quan sát Pod bị restart liên tục (`RESTARTS` tăng khi `kubectl get pods`).
3. Đặt `limits.memory` rất thấp (`16Mi`) cho một image nặng hơn, quan sát trạng thái `OOMKilled` trong `kubectl describe pod`.

## Đào sâu / nâng cao

### startupProbe — dễ bị bỏ quên
Ứng dụng khởi động chậm (nạp cache lớn, chạy migration) mà đặt `initialDelaySeconds` quá ngắn cho `livenessProbe` sẽ bị restart liên tục trước khi kịp sẵn sàng — vòng lặp restart này gọi là "crash loop do probe", rất dễ bị chẩn đoán nhầm thành lỗi ứng dụng. Giải pháp đúng là thêm `startupProbe`: khi có `startupProbe`, `livenessProbe`/`readinessProbe` bị **tạm hoãn hoàn toàn** (không chạy) cho tới khi `startupProbe` báo thành công lần đầu; sau đó `startupProbe` ngừng chạy vĩnh viễn cho vòng đời container đó.
```yaml
startupProbe:
  httpGet:
    path: /mcp
    port: http
  failureThreshold: 30
  periodSeconds: 10   # cho phép tối đa 300s để khởi động (30 lần thử x 10s)
```
Công thức tính thời gian chờ tối đa: `failureThreshold × periodSeconds` (cộng thêm `initialDelaySeconds` nếu có khai). Nếu `startupProbe` fail hết `failureThreshold` lần mà vẫn chưa thành công, container bị coi là chết và bị **kubelet restart** — tương tự hệ quả của livenessProbe fail.

Đọc: [Protect slow starting containers with startup probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-startup-probes).

### 3 loại probe handler
Không chỉ `httpGet` như trong `deployment.yaml` — còn có:
- `exec.command`: chạy lệnh trong container, exit code 0 = thành công, khác 0 = thất bại. Dùng khi ứng dụng không expose HTTP/TCP port kiểm tra được (ví dụ kiểm tra file lock, kiểm tra process còn sống bằng script nội bộ).
```yaml
livenessProbe:
  exec:
    command: ["sh", "-c", "pgrep -f my-process"]
```
- `tcpSocket.port`: chỉ kiểm tra mở được kết nối TCP, không quan tâm nội dung phản hồi — dùng cho service không phải HTTP (database, message queue). Yếu hơn `httpGet` vì port có thể mở nhưng ứng dụng bên trong đã treo/deadlock mà vẫn "pass" probe.
- `httpGet`: coi HTTP status `200-399` là thành công, `400+` hoặc không kết nối được là thất bại. Có thể thêm `httpHeaders` (ví dụ header auth) nếu endpoint yêu cầu.

Cả 3 đều dùng chung các field `initialDelaySeconds` (chờ bao lâu trước lần probe đầu), `periodSeconds` (tần suất probe), `timeoutSeconds` (timeout mỗi lần gọi), `successThreshold` (số lần thành công liên tiếp để coi là "khỏe" — luôn phải là 1 với livenessProbe/startupProbe, chỉ readinessProbe được đặt khác 1), `failureThreshold` (số lần thất bại liên tiếp trước khi coi là "chết").

Đọc: [Configure Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#configure-probes).

### QoS Class — hệ quả của requests/limits
Kubernetes tự gán 1 trong 3 mức QoS cho Pod dựa trên `requests`/`limits`, quyết định thứ tự bị OOMKilled/evict trước khi node thiếu tài nguyên:
- `Guaranteed`: `requests == limits` cho **mọi** container trong Pod, cả cpu lẫn memory (và phải khai tường minh cả 2, không được để trống). Đây là mức ưu tiên cao nhất — evict/OOMKilled sau cùng.
- `Burstable`: có khai `requests`/`limits` nhưng không bằng nhau, hoặc chỉ khai 1 trong 2 (đúng trường hợp [`deployment.yaml`](../../deploy/deployment.yaml#L59-L65): `requests` 100m/128Mi, `limits` 500m/256Mi).
- `BestEffort`: không khai `resources` gì cả cho container nào trong Pod — bị evict/OOMKilled đầu tiên khi node thiếu tài nguyên.

Thứ tự evict khi node thiếu memory: `BestEffort` bị evict trước, rồi tới `Burstable` (Pod dùng vượt `requests` nhiều nhất bị evict trước trong nhóm này), cuối cùng mới tới `Guaranteed`. Đây là lý do production luôn nên tránh `BestEffort` cho service quan trọng.

Xem QoS thực tế: `kubectl get pod <name> -o jsonpath='{.status.qosClass}'`.

Đọc: [Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/).

### seccompProfile — field securityContext hay bị thiếu trong đề thi
Ngoài các field đã có trong `deployment.yaml`, chuẩn bảo mật đầy đủ còn khuyến nghị:
```yaml
securityContext:
  seccompProfile:
    type: RuntimeDefault
```
Giới hạn syscall container được phép gọi ở mức kernel — lớp phòng thủ sâu hơn `capabilities.drop` (capabilities giới hạn *quyền* Linux, seccomp giới hạn *syscall* được gọi, hai lớp bổ trợ nhau chứ không thay thế nhau). `type: RuntimeDefault` dùng seccomp profile mặc định của container runtime (containerd/CRI-O) — đủ dùng cho hầu hết ứng dụng, không cần tự viết profile riêng trừ khi có yêu cầu đặc biệt.

Ghép đầy đủ 1 khối `securityContext` container-level đạt chuẩn "restricted" theo Pod Security Standards:
```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  capabilities:
    drop: ["ALL"]
  seccompProfile:
    type: RuntimeDefault
```
Đọc: [Restrict a Container's Syscalls with seccomp](https://kubernetes.io/docs/tutorials/security/seccomp/) và [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) (mức `restricted` liệt kê đầy đủ field bắt buộc).

## Bài tập nâng cao
1. Viết 1 Deployment giả lập ứng dụng khởi động chậm (dùng `command: ["sh", "-c", "sleep 45 && nginx -g 'daemon off;'"]` với image `nginx`), không có `startupProbe`, chỉ có `livenessProbe` với `initialDelaySeconds: 5`. Quan sát Pod bị `CrashLoopBackOff` dù ứng dụng thực ra chỉ chậm khởi động chứ không lỗi. Sau đó thêm `startupProbe` phù hợp để sửa.
2. Viết 1 Pod với `livenessProbe` dùng `exec.command` kiểm tra sự tồn tại của 1 file (`test -f /tmp/healthy`), container ban đầu tạo file đó lúc start nhưng có một lệnh xoá file sau 30 giây (mô phỏng ứng dụng bị lỗi) — quan sát Pod bị restart đúng lúc file biến mất.
3. Tạo 3 Pod với 3 tổ hợp `resources` khác nhau (không khai gì; chỉ `requests`; `requests == limits`), dùng `kubectl get pod -o jsonpath='{.status.qosClass}'` xác nhận đúng 3 mức QoS `BestEffort`/`Burstable`/`Guaranteed`.
4. Trên 1 node test có ít tài nguyên (hoặc dùng `kubectl cordon`/giới hạn giả lập), tạo áp lực memory bằng cách chạy nhiều Pod `BestEffort` và `Guaranteed` cùng lúc — quan sát `kubectl get events` để xác nhận Pod `BestEffort` bị evict trước.
5. Thêm `seccompProfile: {type: RuntimeDefault}` vào [`deployment.yaml`](../../deploy/deployment.yaml) (bản copy riêng để luyện tập), apply, xác nhận Pod vẫn khởi động bình thường — đối chiếu với việc thử `type: Localhost` trỏ tới 1 profile không tồn tại để xem lỗi báo như thế nào.

## Checklist trước khi qua Ngày 5
- [ ] Giải thích được sự khác nhau giữa liveness fail và readiness fail.
- [ ] Biết cách khắc phục lỗi filesystem read-only bằng `emptyDir`.
- [ ] Đọc hiểu toàn bộ khối `securityContext` trong `deployment.yaml` mà không cần tra doc.
- [ ] Biết khi nào cần thêm `startupProbe` và vì sao.
- [ ] Tự tính được QoS class của 1 Pod từ `requests`/`limits`.
