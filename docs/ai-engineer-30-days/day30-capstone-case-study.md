# Phần 30 — Case study: audit và đề xuất nâng cấp `mcp-superset` theo góc nhìn AI Engineer

## Mục tiêu hôm nay
Không có lý thuyết mới. Đây là bài tập tổng hợp cuối cùng: áp toàn bộ 29 ngày trước lên một codebase thật đang tồn tại trong chính repo này — `mcp-superset`. Mục tiêu không phải "tìm lỗi cho có" mà là tập luyện đúng kỹ năng senior thật: đọc một hệ thống người khác viết, đánh giá nó theo khung production (eval/cost/latency/security), và viết ra đề xuất có ưu tiên — kỹ năng bạn sẽ dùng liên tục khi review code AI của đồng nghiệp hoặc khi nhận bàn giao một hệ thống AI có sẵn.

## Bối cảnh: `mcp-superset` là gì
Đây là MCP server viết bằng Python (dùng `mcp[cli]` / FastMCP), expose các tool để một AI assistant (Claude Desktop, Claude Code, hoặc client MCP khác) có thể thao tác với Apache Superset — một BI tool nội bộ. Cấu trúc chính:
- [`core/server.py`](../../core/server.py) — khởi tạo instance `FastMCP` dùng chung, quản lý lifespan (mở/đóng `httpx.AsyncClient`).
- [`core/context.py`](../../core/context.py) — `SupersetContext` giữ client HTTP dùng chung; hàm `get_caller_session` đọc session cookie của người gọi từ header `X-Superset-Session` — đây là **toàn bộ cơ chế identity** của hệ thống, không có service-account credential nào khác.
- [`core/config.py`](../../core/config.py) — cấu hình qua biến môi trường (`SUPERSET_BASE_URL`), có giá trị default trỏ tới một môi trường UAT nội bộ nếu biến môi trường không được set.
- [`tools/`](../../tools) — mỗi file là một nhóm tool (`chart.py`, `dashboard.py`, `dataset.py`, `database.py`, `explore.py`, `tag.py`, `user.py`, `auth.py`), mỗi hàm dùng decorator `@mcp.tool()` `@requires_auth` `@handle_api_errors`.
- [`utils/decorators.py`](../../utils/decorators.py) — `requires_auth` chặn nếu không có session; `handle_api_errors` bắt exception, luôn trả JSON có field `"error"` thay vì để lộ stack trace.
- [`main.py`](../../main.py) — entrypoint, chạy qua `streamable_http_app()` với `uvicorn`.

Đây **không phải một RAG hay agent tự trị** — nó là một MCP *server* (bên cung cấp tool), phần *client/agent* gọi vào nó (Claude Desktop, hoặc 1 agent loop tự viết) nằm ngoài phạm vi repo này. Vì vậy case study hôm nay tập trung đúng vào phần repo này thực sự sở hữu: **tool design, identity/authorization, error handling, observability** — không audit phần agent loop hay RAG vì repo không có phần đó.

## Bài tập senior — audit theo 4 trục

Tự làm, không cần thảo luận với ai — đây là bài tập đọc code + viết đánh giá, giống hệt việc bạn sẽ làm khi được giao review một PR AI thật hoặc nhận bàn giao hệ thống từ đội khác.

### Trục 1 — Tool design (liên hệ Phần 15-16)
Đọc 2-3 tool trong [`tools/chart.py`](../../tools/chart.py) hoặc [`tools/dashboard.py`](../../tools/dashboard.py). Với mỗi tool, tự trả lời:
1. Docstring có đủ rõ để một LLM chọn đúng tool này thay vì tool khác không? Có mô tả rõ khi nào dùng, tham số nào optional/bắt buộc, giá trị hợp lệ của từng tham số không?
2. Tên tool (`superset_chart_list`, `superset_chart_get_by_id`...) có theo pattern nhất quán giúp LLM suy luận được tool tương tự cho resource khác (ví dụ đoán được có `superset_dashboard_list` mà không cần đọc) không?
3. Tool nào có khả năng chồng lấp chức năng với tool khác (dễ gây model chọn sai)?

### Trục 2 — Identity & authorization (liên hệ Phần 20, 27)
Đây là phần thiết kế đáng chú ý nhất của repo: **không có service-account credential chung** — mọi tool bắt buộc `@requires_auth`, và `requires_auth` chỉ pass nếu `get_caller_session` đọc được session cookie thật của người gọi từ header `X-Superset-Session`. Nói cách khác, mọi request tới Superset API mang đúng identity + Row-Level-Security của người dùng thật, không phải quyền của "con bot".
1. Đây chính là pattern *on-behalf-of / identity pass-through* đã học ở Phần 20 — tự giải thích bằng lời của bạn (không copy lại tài liệu) vì sao pattern này an toàn hơn một service account chung có toàn quyền.
2. Giả sử một client MCP bị cấu hình sai và gửi lẫn session cookie của user A vào request đang xử lý cho user B (lỗi runtime, không phải lỗi cố ý) — nhìn vào code hiện tại, cơ chế nào (nếu có) phát hiện được việc này? Nếu không có, đề xuất 1 cách phát hiện (gợi ý: đối chiếu identity trả về từ `superset_auth_check_session_validity` hoặc `USER_ME` với identity mong đợi ở tầng gọi).
3. `core/config.py` có giá trị `SUPERSET_BASE_URL` default trỏ tới một môi trường cụ thể nếu biến môi trường không được set. Từ góc nhìn vận hành nhiều môi trường (dev/UAT/prod), giá trị default "âm thầm" này có rủi ro gì nếu ai đó quên set biến môi trường khi deploy?

### Trục 3 — Error handling & observability (liên hệ Phần 26-27)
Đọc [`utils/decorators.py`](../../utils/decorators.py), hàm `handle_api_errors`.
1. Hàm này bắt mọi exception và trả `{"error": f"Unexpected error in {function_name}: {str(e)}"}`. Từ góc nhìn *Improper Output Handling* (Phần 27): `str(e)` có khả năng lộ thông tin gì ra phía client MCP (đường dẫn file, chi tiết nội bộ của lỗi HTTP, có thể cả một phần nội dung response từ Superset)? Đề xuất 1 cách giảm rủi ro này mà không làm mất thông tin cần để debug (gợi ý: log đầy đủ ở server, chỉ trả về phía client 1 message rút gọn + mã lỗi tra cứu được).
2. Hiện tại không có bước log/trace tường minh nào cho việc "tool nào được gọi, bởi ai, kết quả gì, mất bao lâu" (theo khái niệm Phần 26). Đề xuất tối thiểu 3 trường bạn sẽ thêm vào log nếu được giao task "thêm observability cho MCP server này", và giải thích ngắn vì sao chọn đúng 3 trường đó trước (không phải log tất cả ngay từ đầu).

### Trục 4 — Ưu tiên hoá đề xuất
Không phải mọi phát hiện ở trên đều nên làm ngay. Viết ra một bảng ngắn (loại "cao/trung/thấp") xếp hạng các đề xuất bạn vừa nêu theo mức độ ưu tiên thật nếu bạn là người phải trình bày với tech lead trong 10 phút — nêu rõ tiêu chí bạn dùng để xếp hạng (ví dụ: rủi ro bảo mật > khả năng debug > tiện lợi).

## Bài tập senior mở rộng (tuỳ chọn, nếu muốn thực hành viết code thật)
Chọn **một** đề xuất ở mức "cao" từ Trục 4 và tự viết một patch nhỏ (không cần merge, chỉ cần chạy được cục bộ) minh hoạ cách sửa — ví dụ: sửa `handle_api_errors` để không lộ `str(e)` nguyên văn ra client, hoặc thêm 1 dòng log có cấu trúc (structured log, không phải log string tự do) mỗi khi tool được gọi. Nhắc lại nguyên tắc từ đầu lộ trình: mọi thay đổi thật lên `mcp-superset` phải qua review/PR bình thường, không commit thẳng lên nhánh chính — bài tập này chỉ để luyện tập cục bộ.

## Tổng kết lộ trình 30 ngày
Nếu bạn hoàn thành đủ 30 ngày và làm nghiêm túc các "Bài tập senior" (không chỉ đọc lý thuyết), bạn đã đi qua đúng 4 năng lực phân biệt AI Engineer senior với người chỉ biết gọi API model:
1. Hiểu **cơ chế thật** bên dưới (Tuần 1) — không coi LLM là hộp đen ma thuật.
2. Biết **khi nào cần RAG/vector DB và khi nào là thừa** (Tuần 2) — không dùng công cụ vì hype.
3. Biết **thiết kế agent/tool có kiểm soát được** (Tuần 3) — không để agent chạy tự do không giới hạn hoặc mượn quyền không cần thiết.
4. Biết **eval, đo cost/latency, và bảo mật trước khi gọi là "xong"** (Tuần 4) — đây là ranh giới rõ nhất giữa demo và production.

Bước tiếp theo tự nhiên sau lộ trình này không phải là học thêm framework mới, mà là **áp toàn bộ khung này lên 1 bài toán thật đang tồn tại ở nơi bạn làm việc** — cách học nhanh nhất từ đây trở đi là qua review thật và phản hồi thật từ hệ thống chạy production, không phải đọc thêm tài liệu.

## Checklist hoàn thành lộ trình
- [ ] Đã tự làm ít nhất 1 đề system design đầy đủ (Phần 29).
- [ ] Đã đọc và audit thật 3 file code trong `mcp-superset` theo 4 trục ở trên, viết ra nhận định bằng chữ (không chỉ đọc lướt).
- [ ] Có thể tự giải thích bằng lời (không nhìn tài liệu) sự khác biệt giữa service-account credential chung và identity pass-through, và vì sao điều này quan trọng với agent có tool.
- [ ] Có thể tự giải thích được khi nào RAG là cần thiết và khi nào chỉ là over-engineering.
- [ ] Có thể tự liệt kê được ít nhất 4 việc phải làm trước khi một hệ thống LLM được gọi là "sẵn sàng production" (không chỉ "chạy được trên máy mình").
