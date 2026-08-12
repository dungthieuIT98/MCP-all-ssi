# Phần 14 — Ôn tập tuần 2: build RAG trên tài liệu Superset thật

## Mục tiêu hôm nay
Không có lý thuyết mới. Ghép toàn bộ Phần 8-13 (embedding, vector DB, chunking, pipeline, hybrid search/rerank, eval) thành một hệ RAG hoàn chỉnh, chạy được, trên một corpus thật — không phải dữ liệu giả lập vài câu như các bài thực hành trước. Đây là bài kiểm tra thật: nếu chỉ hiểu lý thuyết mà chưa từng ráp một pipeline đầy đủ chịu được câu hỏi lộn xộn của người dùng thật, hôm nay sẽ lộ ra ngay.

## Mô tả dự án

Xây một hệ RAG trả lời câu hỏi về Apache Superset, dùng một trong hai corpus (hoặc cả hai để so sánh):
- **Corpus A — tài liệu chính thức**: một phần của [docs.superset.apache.org](https://superset.apache.org/docs/) (crawl hoặc tải thủ công một số trang liên quan tới chủ đề bạn quan tâm — ví dụ phần API, phần cấu hình database connection, phần dataset). Không cần crawl toàn bộ site, vài chục trang đủ để có corpus thật với cấu trúc heading/code block thật.
- **Corpus B — chính repo `mcp-superset`**: `README.md`, docstring và comment trong `core/`, `tools/`, `utils/` — một corpus nhỏ hơn nhưng có sẵn, có cấu trúc code thật (đúng bài toán "chunk theo ranh giới hàm" đã học ở Phần 10).

Khuyến nghị làm cả hai nếu còn thời gian: Corpus A luyện chunking theo markdown/heading trên tài liệu dài; Corpus B luyện chunking theo code block/docstring — hai bài toán chunking khác nhau rõ rệt, cả hai đều có giá trị nghề nghiệp thật (RAG trên tài liệu công khai, RAG trên codebase nội bộ).

### Yêu cầu chức năng tối thiểu
1. Ingest pipeline: đọc corpus, chunk theo cấu trúc document (không chunk mù theo ký tự cố định — áp đúng nguyên tắc Phần 10), embed, lưu vào pgvector hoặc Qdrant local.
2. Query pipeline: nhận câu hỏi, retrieve (tối thiểu dense vector search; điểm cộng nếu có hybrid search hoặc rerank), augment prompt, generate câu trả lời bằng Claude.
3. Citation: mọi câu trả lời phải kèm nguồn cụ thể (tên file/trang, section nếu có) — không chấp nhận câu trả lời "trôi" không trích dẫn được.
4. Xử lý câu hỏi ngoài phạm vi corpus: hỏi một câu chắc chắn không có trong corpus (ví dụ "Superset có hỗ trợ nấu ăn không") — hệ thống phải từ chối rõ ràng, không suy diễn hoặc hallucinate một câu trả lời nghe hợp lý.
5. Đo retrieval quality bằng eval **trước khi** đánh giá chất lượng câu trả lời cuối — tự tạo một golden dataset nhỏ (tối thiểu 10-15 câu hỏi có đáp án/chunk đúng đã biết trước) và tính ít nhất Precision@k hoặc Recall@k trước khi coi pipeline retrieval là "đủ tốt" để đưa vào bước generate.

## Tiêu chí chấp nhận mức senior

Một bài làm ở mức "chạy được" (junior/demo) khác một bài làm ở mức senior ở những điểm cụ thể sau — dùng danh sách này để tự chấm, không chỉ hỏi "code có chạy không":

- **Có citation thật, verify được**: không chỉ in ra "[Nguồn: đâu đó]" mà là tên file/URL/section cụ thể, và khi mở nguồn đó ra thật, nội dung phải khớp với thông tin trong câu trả lời. Tự kiểm tra bằng cách chọn 5 câu trả lời ngẫu nhiên, verify tay từng citation.
- **Xử lý được câu hỏi ngoài phạm vi corpus một cách nhất quán**: không phải một lần thử ăn may — thử tối thiểu 5 câu hỏi ngoài phạm vi khác nhau (một câu hỏi về chủ đề hoàn toàn khác, một câu hỏi về Superset nhưng chi tiết không có trong corpus đã ingest, một câu hỏi mập mờ) và xác nhận hệ thống từ chối hoặc nói rõ "không tìm thấy" ở cả 5, không chỉ 1.
- **Có đo retrieval quality bằng số, trước khi generate**: đã tính Precision@k/Recall@k/MRR trên golden dataset tự tạo, và đã dùng số đó để quyết định retrieval hiện tại "đủ tốt" hay cần chỉnh (đổi chunk size, thêm hybrid search) — không đi thẳng từ ingest sang generate mà bỏ qua bước đo.
- **Retrieval và generation được debug tách biệt**: khi một câu trả lời sai, biết cách xác định lỗi nằm ở retrieval (chunk đúng không có trong top-k) hay ở generation (chunk đúng có trong context nhưng LLM không dùng đúng/bịa thêm) — thể hiện qua việc log/in ra được chunk đã retrieve cho mỗi câu trả lời, không phải hộp đen.
- **Chunking có lý do, không phải giá trị mặc định của thư viện**: giải thích được vì sao chọn chunk size/overlap/chiến lược cụ thể cho corpus này, dựa trên đặc điểm thật của corpus (độ dài section trung bình, có code block hay không), không chỉ copy tham số mẫu từ tutorial.
- **Biết giới hạn của chính hệ thống mình xây**: viết ra (ngắn gọn) 2-3 điểm yếu còn tồn tại (ví dụ "chưa xử lý tốt câu hỏi cần tổng hợp thông tin từ nhiều section xa nhau", "chưa test với câu hỏi viết sai chính tả/viết tắt") — một senior luôn biết hệ thống của mình yếu ở đâu, không tự nhận nó hoàn hảo.

## Checklist đạt chuẩn senior
- [ ] Corpus được chunk theo cấu trúc thật của nó (heading cho markdown, ranh giới hàm/docstring cho code), không chunk mù theo ký tự cố định.
- [ ] Có bước embed + lưu vào pgvector hoặc Qdrant chạy được thật (không phải giả lập/mock).
- [ ] Retrieval quality được đo bằng số (Precision@k/Recall@k/MRR) trên golden dataset tự tạo trước khi coi là đủ tốt để generate.
- [ ] Mọi câu trả lời sinh ra có citation cụ thể, đã verify tay ít nhất 5 câu.
- [ ] Đã test tối thiểu 5 câu hỏi ngoài phạm vi corpus và hệ thống từ chối/nói rõ "không tìm thấy" một cách nhất quán, không hallucinate.
- [ ] Có khả năng debug tách biệt lỗi retrieval và lỗi generation (log được chunk đã dùng cho mỗi câu trả lời).
- [ ] Viết ra được lý do cụ thể cho lựa chọn chunk size/chiến lược chunking, không chỉ copy mặc định.
- [ ] Tự liệt kê được ít nhất 2-3 điểm yếu còn tồn tại của hệ thống đã xây.
- [ ] Không dùng dữ liệu khách hàng thật hoặc thông tin nội bộ nhạy cảm của SSI trong corpus luyện tập — chỉ dùng tài liệu Superset công khai hoặc chính repo `mcp-superset` (đã là mã nguồn nội bộ dùng cho mục đích học tập, không chứa credential/secret thật vì `core/context.py` xác nhận server không giữ credential nào).
</content>
