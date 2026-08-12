# Phần 29 — Mock system design interview: thiết kế 1 hệ AI Engineer từ đầu

## Mục tiêu hôm nay
Không có lý thuyết mới. Ngày này ép bạn tổng hợp toàn bộ 28 ngày trước thành một buổi thiết kế hệ thống hoàn chỉnh, đúng dạng câu hỏi mà một AI Engineer senior bị hỏi khi phỏng vấn hoặc khi trình bày thiết kế trước tech lead/architect.

## Cách làm
Tự đóng cả hai vai: người hỏi và người trả lời. Viết ra giấy/markdown, không chỉ nghĩ trong đầu — trình bày miệng và trình bày viết ra bộc lộ lỗ hổng khác nhau. Giới hạn 90 phút cho toàn bộ đề, giống áp lực thời gian thật.

## Đề bài
Chọn **một trong ba đề** dưới đây (không làm cả ba, chọn đề gần với công việc thật của bạn nhất để phần trả lời có chiều sâu thay vì lan man):

### Đề A — Trợ lý hỏi-đáp nội bộ trên tài liệu vận hành
Công ty có hàng nghìn trang tài liệu vận hành/quy trình nội bộ (runbook, SOP, FAQ IT). Nhân viên hỏi bằng tiếng Việt tự nhiên, hệ thống phải trả lời đúng, trích được nguồn, và từ chối trả lời nếu câu hỏi ngoài phạm vi tài liệu (không bịa). Tải: vài trăm câu hỏi/ngày, tài liệu cập nhật vài lần/tuần.

### Đề B — Agent tự động phân loại và định tuyến ticket hỗ trợ
Ticket hỗ trợ (khách hàng hoặc nội bộ) đổ vào một hàng chờ. Agent phải: đọc nội dung ticket, phân loại đúng nhóm nghiệp vụ, gắn mức độ ưu tiên, và nếu đủ tự tin thì tự trả lời các câu hỏi lặp lại đơn giản (ví dụ hướng dẫn thao tác đã có sẵn đáp án chuẩn); nếu không đủ tự tin hoặc ticket nhạy cảm, chuyển cho người xử lý kèm gợi ý câu trả lời.

### Đề C — Trợ lý truy vấn dữ liệu báo cáo qua ngôn ngữ tự nhiên
Người dùng nghiệp vụ hỏi bằng tiếng Việt tự nhiên về số liệu trong data warehouse (ví dụ "doanh thu tháng trước theo từng chi nhánh"). Hệ thống phải sinh truy vấn đúng, chạy trên nguồn dữ liệu thật, và trả về kết quả có kèm cách hiểu câu hỏi (để người dùng xác nhận hệ thống hiểu đúng ý, tránh trả lời sai mà nhìn có vẻ đúng).

## Khung trả lời bắt buộc — đi qua đủ từng phần, đừng nhảy thẳng vào code
Một câu trả lời senior không nhảy ngay vào "dùng LangChain với Pinecone" — nó đi theo trình tự sau, và trình tự này chính là lý do tồn tại của Tuần 1–4:

### 1. Làm rõ yêu cầu và ràng buộc (5 phút)
- Ai là người dùng cuối, tần suất dùng, độ trễ chấp nhận được (real-time hay chấp nhận vài giây/phút)?
- Sai ở mức nào là chấp nhận được, sai ở mức nào là không chấp nhận được (ví dụ: trả lời chung sai thì chấp nhận, nhưng bịa ra số liệu tài chính cụ thể thì không)?
- Có dữ liệu nhạy cảm/PII/thông tin khách hàng trong luồng không? (quyết định toàn bộ thiết kế guardrail — liên hệ Phần 27-28)
- Ngân sách vận hành: có giới hạn cost/tháng rõ ràng không, hay chỉ cần "hợp lý"?

### 2. Kiến trúc tổng thể ở mức khối (block diagram bằng chữ)
Với cả 3 đề, khối chung luôn có: nguồn input → (có RAG hay không, có tool-calling hay không) → LLM call → guardrail output → nơi lưu/trả kết quả → observability xuyên suốt. Phần khác nhau giữa 3 đề là **cái gì đứng giữa input và LLM call**:
- Đề A: bắt buộc có RAG (Tuần 2) — không có RAG thì không thể trích nguồn/không bịa.
- Đề B: có thể không cần RAG (nếu category cố định, few-shot đủ) hoặc cần RAG nhẹ (nếu có kho câu trả lời chuẩn để agent tham khảo) — cần agent loop đơn giản (Tuần 3, Phần 17) để quyết định tự trả lời hay chuyển người.
- Đề C: cần tool-calling (Tuần 3, Phần 15) để agent gọi hàm chạy SQL thật, KHÔNG để LLM tự "đoán" số liệu — đây là lỗi thiết kế nghiêm trọng nhất người mới hay mắc ở đề này.

### 3. Chọn model và giải thích trade-off (Tuần 1, Phần 6)
Không có đáp án "model tốt nhất" — chỉ có model phù hợp với ràng buộc đã làm rõ ở bước 1. Trả lời phải nêu được: vì sao chọn model này thay vì model khác, có cần routing giữa model rẻ/đắt không (Phần 24), context window có đủ cho use case không (Phần 2).

### 4. Thiết kế phần đặc thù (RAG hoặc agent, tuỳ đề)
- Nếu có RAG: chunking strategy cụ thể cho loại tài liệu của đề (Phần 10), có hybrid search/rerank không hay dense retrieval đơn giản đã đủ (Phần 12) — đừng thêm rerank nếu chưa đo được retrieval kém ở đâu.
- Nếu có agent/tool: liệt kê chính xác tool nào, input/output schema của từng tool (Phần 4, 15), điều kiện dừng loop (Phần 17), ai/cái gì có quyền gọi tool nào (Phần 20) — đề B và C đụng trực tiếp câu hỏi identity vì hành động thay người dùng thật.

### 5. Eval trước khi nói "xong" (Tuần 4, Phần 22-23)
Nêu rõ: golden dataset sẽ gồm loại câu hỏi gì (ít nhất phải có câu hỏi "đúng phạm vi", "ngoài phạm vi", "mơ hồ/thiếu thông tin"), metric nào đo được (không chỉ "trông đúng"), ai review kết quả eval trước khi lên production.

### 6. Vận hành thật: cost, latency, observability, guardrail (Tuần 4)
- Ước lượng cost ở mức thứ tự lớn (không cần số chính xác): bao nhiêu request/ngày × độ dài prompt trung bình × giá tương đối của model đã chọn — có cần caching/batching không (Phần 24).
- Latency budget: phần nào chạy đồng bộ chờ người dùng, phần nào chạy nền được (Phần 25).
- Trace được request lỗi từ đâu ra đâu (Phần 26).
- Guardrail input/output cụ thể cho đề đã chọn, đặc biệt nếu có dữ liệu khách hàng/tài chính (Phần 27-28) — nêu rõ điểm nào cần con người duyệt, không để hệ thống tự quyết.

### 7. Nói thẳng phần chưa chắc / rủi ro còn lại
Một câu trả lời senior luôn kết bằng việc tự nêu điểm yếu của chính thiết kế mình vừa trình bày — ví dụ "retrieval sẽ kém nếu tài liệu có nhiều bảng số liệu, cần đo lại sau khi có dữ liệu thật", "chưa tính được rõ tần suất người dùng sẽ hỏi ngoài phạm vi, cần theo dõi thêm ở giai đoạn online eval". Junior thường trình bày như thể thiết kế của mình hoàn hảo — đây là dấu hiệu dễ nhận ra nhất khi phân biệt junior/senior trong phỏng vấn.

## Bài tập senior
1. Làm đề đã chọn theo đúng khung 7 bước trên, viết ra thành 1 file markdown khoảng 1–2 trang. Sau đó tự đọc lại và tự hỏi: "nếu tôi là người review thiết kế này, tôi sẽ hỏi khó ở đâu?" — viết thêm 3 câu hỏi khó đó và tự trả lời.
2. Đổi đề (làm thêm 1 trong 2 đề còn lại), lần này giới hạn 45 phút — tốc độ nhanh hơn thật hơn buộc bạn ưu tiên đúng phần quan trọng, bỏ qua phần chi tiết không cần.
3. Nếu có đồng nghiệp/bạn cùng học, đổi vai: một người hỏi xoáy vào phần yếu nhất của thiết kế (giống phỏng vấn thật), người kia phải bảo vệ hoặc thừa nhận và sửa lại ngay tại chỗ.

## Checklist trước khi qua Phần 30
- [ ] Đã hoàn thành khung 7 bước cho ít nhất 1 đề, có ghi ra giấy/file, không chỉ nghĩ trong đầu.
- [ ] Thiết kế có nêu rõ eval plan, không chỉ nêu kiến trúc.
- [ ] Thiết kế có phần cost/latency ước lượng được, không bỏ trống.
- [ ] Thiết kế có ít nhất 1 điểm guardrail/human-in-the-loop rõ ràng.
- [ ] Tự nêu được ít nhất 2 điểm yếu/rủi ro còn lại của chính thiết kế mình.
