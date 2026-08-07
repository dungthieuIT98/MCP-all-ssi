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

## Checklist trước khi qua Ngày 5
- [ ] Giải thích được sự khác nhau giữa liveness fail và readiness fail.
- [ ] Biết cách khắc phục lỗi filesystem read-only bằng `emptyDir`.
- [ ] Đọc hiểu toàn bộ khối `securityContext` trong `deployment.yaml` mà không cần tra doc.
