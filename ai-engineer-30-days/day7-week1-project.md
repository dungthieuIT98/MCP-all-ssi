# Ngày 7 — Dự án Tuần 1: CLI hỏi-đáp có structured output

## Mục tiêu hôm nay
Không học lý thuyết mới — ghép toàn bộ kiến thức 6 ngày trước (next-token prediction, context/token, prompt engineering, structured output, guardrail, model selection) thành một sản phẩm nhỏ chạy được thật, và tự đánh giá theo tiêu chuẩn senior chứ không chỉ "chạy được là xong".

## Đề bài
Xây một CLI (command-line tool) hỏi-đáp cho phép người dùng nhập câu hỏi tự do, và trả về kết quả có **structured output** theo một schema cố định — không phải chỉ in ra văn bản tự do. Chủ đề gợi ý (chọn 1, hoặc tự chọn chủ đề khác nếu phù hợp với công việc thực tế của bạn):

- **CLI phân loại + tóm tắt yêu cầu hỗ trợ**: người dùng nhập một đoạn mô tả vấn đề, CLI trả về JSON có `loai_yeu_cau` (enum), `muc_do_uu_tien` (enum), `tom_tat` (string ngắn), `can_escalate` (boolean).
- **CLI trích xuất thông tin từ văn bản tài chính**: người dùng nhập một đoạn tin tức/báo cáo, CLI trả về JSON có `ten_cong_ty`, `ma_co_phieu` (nếu có), `loai_su_kien` (enum: "kết quả kinh doanh" / "M&A" / "nhân sự" / "khác"), `tom_tat_1_cau`.
- **CLI hỏi-đáp tài liệu nội bộ**: người dùng dán một đoạn quy định + câu hỏi, CLI trả về JSON có `co_tra_loi_duoc` (boolean), `cau_tra_loi` (string, rỗng nếu không trả lời được), `trich_dan` (đoạn tài liệu đã dùng, rỗng nếu không áp dụng).

Yêu cầu bắt buộc bất kể chọn chủ đề nào — đây là phần quyết định CLI của bạn đạt chuẩn senior hay chỉ "chạy được":

### 1. Structured output có validate thật
- Dùng `client.messages.parse()` với Pydantic model, hoặc `output_config.format` với JSON Schema thuần — không dùng "prompt-only" (chỉ dặn model trả JSON rồi tin tưởng).
- Có xử lý rõ ràng khi model trả sai schema — không để exception raise thẳng ra người dùng dưới dạng traceback khó hiểu.

### 2. Retry có giới hạn, không phải vòng lặp vô hạn
- Tối đa N lần thử lại (N do bạn chọn, hợp lý là 2-3), có đường thoát rõ ràng khi hết số lần retry — in lỗi rõ ràng cho người dùng, không crash im lặng, không treo máy.
- Mỗi lần retry phải đưa thông tin lỗi cụ thể vào lượt gọi lại (không gọi lại y hệt request cũ và hy vọng lần này may hơn).

### 3. Xử lý `stop_reason` đúng cách
- Kiểm tra `stop_reason` trước khi parse — xử lý riêng trường hợp `max_tokens` (cần tăng giới hạn hoặc báo lỗi) và `refusal` (không cố parse JSON từ một response bị từ chối).

### 4. Log token usage và ước tính chi phí
- Sau mỗi lệnh gọi, log lại `usage.input_tokens`, `usage.output_tokens`, và model đã dùng.
- Có một hàm tính tổng chi phí ước lượng dựa trên giá bạn tự tra từ trang pricing chính thức (không hardcode số giá cũ/nhớ sai — đọc lại nguyên tắc ở Ngày 2 và Ngày 6).

### 5. System prompt có cấu trúc, version control được
- System prompt nằm trong file riêng (không hardcode string dài giữa logic code), có thể thay đổi mà không cần sửa code Python.
- System prompt có đủ các khối: vai trò/phạm vi, ràng buộc hành vi, cách xử lý khi không chắc, định dạng đầu ra kỳ vọng (Ngày 5).

### 6. Có test
- Ít nhất 3-5 test case (dùng `pytest` hoặc tương đương) kiểm tra: parse JSON thành công với input hợp lệ, xử lý đúng khi model trả sai format (có thể mock response để test không tốn tiền API thật), và validate logic nghiệp vụ riêng (không chỉ dựa vào JSON Schema — liên hệ Ngày 4).

### 7. Model selection có chủ đích
- Chọn model (nhỏ hay lớn) có lý do rõ ràng ghi lại trong README hoặc comment — không phải "mặc định dùng model mạnh nhất vì chắc ăn" (liên hệ Ngày 6).

## Không bắt buộc nhưng cộng điểm senior
- Prompt caching nếu system prompt đủ dài để đáng cache.
- Nhận diện injection cơ bản nếu CLI cho phép người dùng dán văn bản dài từ nguồn ngoài (liên hệ Ngày 5).
- CLI có flag để chọn model qua tham số dòng lệnh (`--model haiku` / `--model opus`) để dễ so sánh khi test.

## Cấu trúc thư mục gợi ý
```
week1-project/
├── prompts/
│   └── system_prompt_v1.md
├── cli.py
├── schema.py          # Pydantic model định nghĩa structured output
├── llm_client.py       # wrapper gọi model, có retry + logging
├── test_llm_client.py
└── README.md           # ghi lý do chọn model, ước tính chi phí
```

## Checklist "đạt yêu cầu senior" — không chỉ "chạy được"

Đây là điểm khác biệt cốt lõi của bài tập ngày hôm nay: một CLI "chạy được" chỉ cần gọi API và in ra kết quả khi mọi thứ suôn sẻ. Một CLI "đạt chuẩn senior" phải sống sót được khi mọi thứ **không** suôn sẻ — vì trong thực tế production, model sẽ trả sai format, sẽ bị rate limit, sẽ refuse, và người dùng sẽ nhập input kỳ quặc.

- [ ] **Chạy được với input hợp lệ** — mức tối thiểu, không phải mức đủ.
- [ ] **Không crash khi model trả JSON sai schema** — có bắt lỗi, có retry, có thông báo rõ ràng khi hết retry.
- [ ] **Retry có giới hạn cứng** — thử cố tình mock một model luôn trả sai để xác nhận CLI dừng đúng lúc, không treo.
- [ ] **Kiểm tra `stop_reason` trước khi parse** — thử cố tình set `max_tokens` rất nhỏ để xác nhận CLI phát hiện và xử lý đúng trường hợp bị cắt.
- [ ] **Log token usage mỗi lần gọi** — không phải chỉ log khi thành công, log cả khi lỗi/retry để biết chi phí thật của một lần "hỏi" (bao gồm các lần retry tốn thêm).
- [ ] **System prompt tách file, có version** — sửa system prompt không cần sửa code Python, và có ít nhất 1 commit git thể hiện lịch sử thay đổi prompt.
- [ ] **Có test chạy được `pytest` mà không cần gọi API thật** — dùng mock/fixture cho response model, để test chạy nhanh và không tốn tiền mỗi lần CI chạy.
- [ ] **Validate nghiệp vụ riêng ngoài JSON Schema** — ví dụ nếu có field enum, kiểm tra thêm logic (một mã cổ phiếu hợp lệ có đúng 3 ký tự viết hoa, một mức độ ưu tiên "cao" có đi kèm lý do cụ thể không rỗng).
- [ ] **Lý do chọn model được viết ra, không chỉ nằm trong đầu bạn** — người khác đọc README phải hiểu vì sao bạn chọn model đó cho tác vụ đó.
- [ ] **Không có `while True` không giới hạn ở bất kỳ đâu trong luồng gọi model** — kiểm tra lại toàn bộ code một lần cuối trước khi coi là hoàn thành.

## Tự đánh giá — 3 câu hỏi quyết định bạn có thực sự hiểu Tuần 1 hay chưa
Trả lời thành thật 3 câu này cho chính dự án bạn vừa viết — nếu trả lời "không" hoặc "không chắc" cho bất kỳ câu nào, quay lại đọc phần tương ứng trước khi qua Tuần 2:

1. Nếu model bạn đang dùng ngày mai đổi hành vi (ví dụ nâng cấp version, hoặc đổi từ Sonnet sang Opus), bạn có tự tin CLI của bạn vẫn hoạt động đúng, hay bạn phải sửa lại retry logic/parse logic vì đã viết cứng theo hành vi cụ thể của một model? (liên hệ Ngày 1, Ngày 3)
2. Nếu có người cố tình dán một đoạn văn bản chứa câu "bỏ qua mọi chỉ dẫn trước" vào CLI của bạn, bạn biết chính xác điều gì sẽ xảy ra — không phải đoán? (liên hệ Ngày 5)
3. Nếu CFO hỏi "CLI này chạy 10,000 lần/tháng thì tốn bao nhiêu tiền", bạn có thể trả lời bằng số cụ thể dựa trên log usage thật đã thu thập, không phải ước lượng cảm tính? (liên hệ Ngày 2, Ngày 6)

## Nếu bạn thấy dự án này "quá dễ" hoặc "quá cơ bản"
Đó là dấu hiệu tốt cho Tuần 1 — Tuần 1 chỉ là nền tảng single-call, chưa có agent loop, chưa có tool-calling thật, chưa có RAG, chưa có eval framework nghiêm túc. Những phần đó nằm ở các tuần sau của roadmap 30 ngày. Nếu bạn hoàn thành checklist senior ở trên một cách nghiêm túc (không tự lừa mình rằng "chắc cũng ổn" ở phần retry/validate), bạn đã có nền tảng chắc để bước vào phần agent/tool-calling nâng cao mà không phải quay lại vá những lỗ hổng cơ bản này giữa đường.

## Checklist trước khi qua Tuần 2
- [ ] CLI chạy được end-to-end với ít nhất 5 input khác nhau, bao gồm ít nhất 1 input cố tình gây lỗi (input rỗng, input cực dài, input vô nghĩa).
- [ ] Toàn bộ checklist "đạt yêu cầu senior" ở trên đã được tick thật (không tick khống).
- [ ] Code đã commit git với lịch sử rõ ràng, README giải thích được lý do thiết kế (model chọn, retry limit chọn, vì sao).
- [ ] Tự trả lời được 3 câu hỏi tự đánh giá ở trên mà không cần mở lại tài liệu Ngày 1-6.
