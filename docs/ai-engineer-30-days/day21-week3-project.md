# Phần 21 — Ôn tập tuần 3: thiết kế 1 agent tool-using cho bài toán tự chọn

## Mục tiêu hôm nay
Tổng hợp toàn bộ Tuần 3 (tool-calling, giao thức/framework, agent loop, memory, multi-agent, authorization) bằng cách tự thiết kế và code 1 agent tool-using hoàn chỉnh cho 1 bài toán tự chọn, đạt tiêu chí chấp nhận mức senior — không chỉ "chạy được" mà phải kiểm soát được.

## Yêu cầu dự án

### Bước 1 — Chọn 1 bài toán
Chọn 1 trong các gợi ý sau, hoặc tự đề xuất 1 bài toán tương đương độ phức tạp từ công việc thật (miễn không dùng dữ liệu khách hàng thật hoặc thông tin định danh thật — xem lưu ý SSI ở README):

1. **Agent trả lời câu hỏi về log lỗi hệ thống**: có tool tìm log theo khoảng thời gian/từ khoá, tool tra cứu mã lỗi trong 1 bảng tra cứu tĩnh, agent trả lời tổng hợp nguyên nhân khả năng cao.
2. **Agent tự động phân loại ticket support**: có tool đọc nội dung ticket, tool tra cứu danh mục phân loại có sẵn, tool gán nhãn (side-effect: viết vào hệ thống ticket giả lập).
3. **Agent truy vấn dữ liệu báo cáo**: có tool query 1 nguồn dữ liệu (DB giả lập hoặc file CSV/SQLite), tool tổng hợp số liệu theo điều kiện, trả lời câu hỏi dạng "tổng doanh thu tháng X theo phòng ban Y".

### Bước 2 — Chọn cách tiếp cận
Tự chọn 1 trong các cách đã học ở Phần 16 để định nghĩa và gọi tool:
- Function calling thuần (Anthropic SDK hoặc OpenAI SDK, viết tay tool schema)
- Framework orchestration (LangChain hoặc LlamaIndex, nếu đã cài đặt được môi trường)
- MCP (nếu muốn thực hành thêm luồng client-server, không bắt buộc)

**Không bắt buộc phải dùng MCP.** Tiêu chí chấm không đánh giá cách nào "cao cấp hơn" — đánh giá dựa trên việc bạn giải thích được RÕ RÀNG vì sao chọn cách đó cho đúng bài toán này (liên hệ trực tiếp bảng so sánh Phần 16).

### Bước 3 — Thiết kế và code
Agent phải có tối thiểu 2-3 tool thật (không phải tool giả chỉ trả chuỗi cố định), 1 vòng lặp xử lý nhiều bước (không chỉ 1 lần gọi tool rồi dừng — phải thể hiện được ít nhất 1 tình huống cần 2+ lượt tool-use nối tiếp để trả lời đúng).

## Tiêu chí chấp nhận mức senior (bắt buộc phải có, không phải "nice to have")

- [ ] **Giới hạn iteration/cost**: có `MAX_ITERATIONS` cứng, và tối thiểu 1 trong (time budget hoặc token/cost budget) — đúng theo Phần 17. Agent phải tự dừng có kiểm soát khi vượt giới hạn, không chạy vô hạn.
- [ ] **Audit log ai/cái gì gọi tool nào**: mọi lần tool được gọi (thành công hoặc lỗi) phải được ghi lại tối thiểu: identity người gọi (dù chỉ là 1 user giả lập cố định nếu bài toán không có multi-user thật), tên tool, input, kết quả/lỗi, thời điểm — đúng theo Phần 20. Không cần database thật, ghi ra list/file/log console có cấu trúc là đủ.
- [ ] **Xử lý khi model gọi tool với input sai**: có validate input trước khi thực thi (không tin schema mù quáng — liên hệ Phần 15), và có cách xử lý rõ ràng khi model gọi tool không tồn tại hoặc input không hợp lệ (trả lỗi có message rõ để model có cơ hội sửa, không để exception rơi thẳng ra ngoài làm crash toàn bộ agent).
- [ ] **Có ít nhất 1 cơ chế phát hiện lặp vô nghĩa** (agent gọi lại đúng tool + đúng input đã thử) — đúng theo Phần 17, không cần phức tạp, so sánh khoá tool+input đã normalize là đủ.
- [ ] **Quyết định rõ ràng về memory**: nêu rõ (bằng comment hoặc note đi kèm) bài toán bạn chọn có cần long-term memory không, và giải thích tại sao có/không — đúng theo Phần 18 (không thêm memory system nếu context window session hiện tại đã đủ).
- [ ] **Quyết định rõ ràng về multi-agent**: nêu rõ tại sao dùng 1 agent đơn là đủ (trường hợp phổ biến với độ phức tạp bài toán gợi ý ở trên), hoặc nếu chọn tách multi-agent, giải thích cụ thể lý do chuyên môn hoá/cách ly context thật — không tách "cho có" (Phần 19).
- [ ] **Nêu rõ mô hình identity/authorization** dù bài toán giả lập: agent hành động thay ai, tool có side-effect (nếu có, ví dụ tool "gán nhãn ticket") có giới hạn theo quyền của ai không, ai chịu trách nhiệm nếu tool đó thực thi sai (Phần 20).

## Không cần
- Không cần UI đẹp — console/script Python là đủ.
- Không cần production-grade deployment (Docker, CI/CD) — đó là phạm vi Tuần 4.
- Không cần benchmark/eval số liệu chính thức — đó là phạm vi Phần 22, nhưng nên tự chạy thử tối thiểu 5-10 câu hỏi khác nhau (kể cả câu hỏi "khó"/mơ hồ cố ý) để tự kiểm chứng agent không vỡ trận ngay khi gặp input lạ.

## Checklist hoàn thành Tuần 3
- [ ] Agent chạy được từ đầu tới cuối với tối thiểu 2 tình huống test (1 tình huống bình thường, 1 tình huống cố ý gây khó — input mơ hồ, tool trả lỗi, hoặc câu hỏi ngoài phạm vi tool có sẵn).
- [ ] Toàn bộ 6 tiêu chí senior ở trên được thoả mãn và có thể chỉ ra chính xác đoạn code nào tương ứng với tiêu chí nào.
- [ ] Tự viết được 1 đoạn ngắn (5-10 câu) giải thích lựa chọn kiến trúc: cách tiếp cận tool nào, có multi-agent không, có long-term memory không, mô hình identity nào — và vì sao KHÔNG chọn các phương án khác đã học trong tuần.
- [ ] Đối chiếu lại 1 lần với `mcp-superset`: chỉ ra 1 điểm cụ thể trong bài làm của bạn giống/khác cách repo xử lý (ví dụ: cách xử lý lỗi có giống `handle_api_errors` không, cách xác thực có tính tới identity pass-through không) — không bắt buộc phải giống, chỉ cần có khả năng so sánh có ý thức.
