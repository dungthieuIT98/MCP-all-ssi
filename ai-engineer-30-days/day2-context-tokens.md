# Ngày 2 — Context window, token, chi phí

## Mục tiêu hôm nay
Hiểu token và context window ở mức đủ để tự tính được chi phí và latency của một tính năng LLM trước khi build nó — kỹ năng bắt buộc để không bị "hoá đơn API" gây bất ngờ ở production, và để biết khi nào cần cắt/tóm tắt ngữ cảnh.

## Đọc trước
- [Anthropic — Context windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows)
- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting)
- [Anthropic — Pricing](https://docs.anthropic.com/en/docs/about-claude/pricing) (giá thay đổi theo thời gian — luôn tra trang này để lấy số hiện tại, không tin số cũ trong tài liệu/blog)
- [Anthropic — Prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)

## Khái niệm cốt lõi

### Token là gì, và vì sao không phải là "từ"
Token là đơn vị nhỏ nhất mà model xử lý — không phải từ, không phải ký tự. Các model hiện đại dùng thuật toán **BPE (Byte Pair Encoding)** hoặc biến thể của nó để tách văn bản thành token: thuật toán này học từ dữ liệu huấn luyện những cặp ký tự/subword xuất hiện thường xuyên nhất, rồi gộp dần thành các "đơn vị" lớn hơn. Kết quả là một từ tiếng Anh thông dụng (`the`, `is`) thường là 1 token, nhưng một từ hiếm, một từ tiếng Việt có dấu, hoặc một chuỗi code có thể bị tách thành 2-5 token.

Bạn không cần tự implement tokenizer — SDK và API cung cấp endpoint đếm token trực tiếp (`count_tokens`). Điều cần hiểu ở mức khái niệm:
- **Tiếng Việt có dấu tốn nhiều token hơn tiếng Anh cho cùng nội dung** — dấu thanh, dấu mũ là ký tự Unicode nhiều byte, và BPE được huấn luyện chủ yếu trên dữ liệu tiếng Anh nên coding tiếng Việt kém hiệu quả hơn. Nếu ứng dụng của bạn xử lý nhiều tiếng Việt, chi phí/token thực tế trên mỗi "ý nghĩa" truyền đạt sẽ cao hơn so với tiếng Anh — cần tính vào ngân sách ngay từ đầu, không đợi đến khi nhận hoá đơn.
- **Code cũng tốn token khác thường** — dấu ngoặc, khoảng trắng thụt lề, tên biến dài đều là token riêng. Một file JSON/YAML lồng nhau sâu tốn nhiều token hơn cảm giác trực quan về "độ dài văn bản".
- **Không có công thức quy đổi cố định** kiểu "1 token ≈ 4 ký tự" áp dụng chính xác cho mọi ngôn ngữ/loại nội dung — đó chỉ là ước lượng thô cho tiếng Anh thông thường. Muốn số chính xác, gọi endpoint đếm token thật, đừng đoán.

**Tuyệt đối không dùng `tiktoken` (tokenizer của OpenAI) để đếm token cho Claude.** Đây là lỗi rất phổ biến của dev quen với ecosystem OpenAI — hai họ model dùng tokenizer khác nhau, kết quả đếm sai lệch 15-20% hoặc hơn, đặc biệt sai nhiều hơn với code hoặc ngôn ngữ ngoài tiếng Anh. Luôn dùng endpoint `count_tokens` chính thức của Anthropic.

### Context window là gì
Context window là tổng số token tối đa mà model có thể "nhìn thấy" trong một request — bao gồm system prompt + toàn bộ lịch sử messages + input hiện tại + không gian dành cho output sắp sinh ra. Đây không phải "bộ nhớ" theo nghĩa lưu trữ dài hạn — nó là **kích thước cửa sổ đầu vào của một lần forward-pass**, hoàn toàn biến mất giữa các request nếu bạn không tự gửi lại.

Điểm dễ nhầm: context window là giới hạn **input + output cộng lại** đối với hầu hết mục đích tính phí/giới hạn kỹ thuật, nhưng có một giới hạn output riêng (`max_tokens`) luôn nhỏ hơn hoặc bằng context window tổng. Một request với context window 1M token và `max_tokens=64000` không có nghĩa bạn có 1M token cho input — nếu input đã chiếm 990K token, bạn chỉ còn 10K cho output dù `max_tokens` bạn set là 64000, và request đó sẽ bị cắt hoặc lỗi.

### Cấu trúc chi phí: input token và output token khác giá
Mọi model tính phí theo **hai mức giá riêng biệt trên mỗi triệu token (per-1M-token)**: giá cho input token và giá cho output token, và **output luôn đắt hơn input** — thường gấp 4-5 lần tuỳ model. Lý do nằm ở Ngày 1: input được xử lý song song trong giai đoạn prefill, output phải sinh tuần tự token-by-token trong giai đoạn decode — decode tốn tài nguyên tính toán hơn nhiều cho cùng số token.

Vì giá thay đổi theo thời gian và theo model, **không chốt số liệu cụ thể ở đây** — luôn tra [trang pricing chính thức](https://docs.anthropic.com/en/docs/about-claude/pricing) để lấy số mới nhất trước khi tính ngân sách thật. Điều cần nhớ ở mức khái niệm: model nhỏ hơn (Haiku) rẻ hơn model lớn (Opus) khoảng một bậc độ lớn (order of magnitude) trên cùng khối lượng token — đây là lý do model routing (Ngày 6) là một kỹ thuật tối ưu chi phí thật, không phải chi tiết vụn vặt.

### Prompt dài = tiền + latency, không phải chỉ một trong hai
Hai hệ quả tách biệt của một prompt dài:
1. **Tiền**: input token dài hơn = phí input cao hơn tuyến tính. Với hội thoại nhiều lượt mà bạn gửi lại toàn bộ lịch sử mỗi lần (bắt buộc vì API stateless), chi phí input **tăng theo cấp số cộng dồn qua từng lượt** — lượt 10 trong một hội thoại dài tốn input token gần bằng tổng của 10 lượt trước cộng lại, dù bạn chỉ hỏi một câu ngắn ở lượt đó.
2. **Latency**: input dài hơn làm giai đoạn prefill lâu hơn (dù song song hoá tốt, vẫn có giới hạn) — trực tiếp làm tăng time-to-first-token. Đây khác với output dài làm tăng latency vì decode tuần tự — hai nguồn latency riêng biệt, cần đo riêng khi debug hiệu năng.

Hệ quả thiết kế trực tiếp: một chatbot production không nên gửi lại **toàn bộ** lịch sử hội thoại vô hạn — sau một ngưỡng, phải áp dụng chiến lược cắt/tóm tắt (bên dưới), nếu không chi phí và latency sẽ tăng không kiểm soát theo độ dài hội thoại, kể cả khi mỗi câu hỏi của người dùng đều ngắn.

### Chiến lược cắt context (context management)
Không có một cách "đúng duy nhất" — chọn chiến lược theo bản chất ứng dụng:

- **Sliding window (cắt cứng theo N lượt gần nhất)**: đơn giản nhất, dễ implement, nhưng model mất hoàn toàn thông tin ở các lượt bị cắt — rủi ro cho hội thoại cần nhớ chi tiết đầu cuộc trò chuyện (ví dụ tên khách hàng nêu ở lượt 1, hỏi lại ở lượt 20).
- **Tóm tắt định kỳ (rolling summarization)**: khi hội thoại vượt một ngưỡng token, gọi model tóm tắt các lượt cũ thành một đoạn ngắn, thay các lượt gốc bằng bản tóm tắt đó trong lần gửi tiếp theo. Tốn thêm 1 lệnh gọi model (chi phí phụ) nhưng giữ được ngữ nghĩa cốt lõi tốt hơn cắt cứng.
- **Compaction do server tự làm** (tính năng của Anthropic, hiện là beta trên các model mới): API tự tóm tắt phần ngữ cảnh cũ khi gần đạt ngưỡng, trả về một "compaction block" — bạn chỉ cần luôn gửi lại đúng nguyên `response.content` (không chỉ phần text) ở lượt sau để giữ trạng thái compaction, nếu không sẽ mất thông tin đã được tóm tắt.
- **Retrieval-based (RAG)**: với ứng dụng hỏi-đáp trên tài liệu lớn, không nhồi toàn bộ tài liệu vào context — chỉ truy xuất (retrieve) đoạn liên quan nhất tới câu hỏi hiện tại rồi đưa vào context. Đây là chiến lược "cắt từ đầu" thay vì "cắt sau khi đã dài" — không thuộc phạm vi 7 ngày đầu (sẽ học kỹ ở tuần sau) nhưng cần biết nó tồn tại như một lựa chọn.
- **Prompt caching để giảm chi phí của phần không cắt được**: nếu system prompt/tài liệu tham chiếu lớn nhưng ổn định giữa các request, dùng `cache_control` để model không phải xử lý lại toàn bộ ở mức giá đầy đủ — phần đọc từ cache rẻ hơn nhiều so với input mới (thường khoảng một phần mười giá input thông thường, nhưng luôn tra số chính xác vì có thể thay đổi). Đây không phải "cắt" context nhưng giải quyết đúng vấn đề chi phí khi context lớn nhưng có phần lặp lại.

Nguyên tắc chọn: nếu ngữ cảnh cũ **ít khi cần chi tiết chính xác lại** → tóm tắt hoặc cắt. Nếu ngữ cảnh cũ **ổn định và lặp lại giữa nhiều request** (ví dụ system prompt, tài liệu tham chiếu cố định) → cache. Nếu ngữ cảnh là **một tập tài liệu lớn nhưng chỉ một phần nhỏ liên quan mỗi câu hỏi** → retrieval.

## Đối chiếu với code thật trong repo
Trong `mcp-superset`, mỗi lần AI assistant gọi một tool (ví dụ `superset_dashboard_list` trong `tools/dashboard.py`), kết quả trả về (JSON từ Superset API, có thể là danh sách dashboard, chart, dataset) sẽ được đưa vào context của model ở lượt tiếp theo dưới dạng `tool_result`. Nếu một tool trả về danh sách quá lớn (hàng trăm dashboard, mỗi cái có nhiều field), toàn bộ payload đó cộng dồn vào context — đây chính là lúc "prompt dài = tiền + latency" xảy ra thật trong một hệ thống MCP, không chỉ là lý thuyết. `utils/rison.py` (dùng để encode query filter theo định dạng Rison mà Superset API yêu cầu) gián tiếp ảnh hưởng tới việc này: filter tốt ở tầng gọi API Superset giúp tool trả về ít dữ liệu hơn, context nhỏ hơn, rẻ hơn — thiết kế tool nên ưu tiên filter/paginate ở phía Superset trước khi trả kết quả vào context của model, không nên "lấy hết rồi để model tự lọc bằng mắt".

## Thực hành
```bash
pip install anthropic
```

```python
import anthropic

client = anthropic.Anthropic()

# Đếm token TRƯỚC khi gọi model — luôn nên làm điều này cho request có
# payload lớn/không kiểm soát (ví dụ nội dung do người dùng dán vào),
# để biết trước có vượt context window hay tốn quá nhiều tiền không.
system_prompt = "Bạn là trợ lý phân tích dữ liệu tài chính cho SSI Securities."
long_document = "..." * 5000  # giả lập một tài liệu dài dán vào

count = client.messages.count_tokens(
    model="claude-opus-5",
    system=system_prompt,
    messages=[{"role": "user", "content": f"Tóm tắt tài liệu sau:\n{long_document}"}],
)
print(f"Input tokens: {count.input_tokens}")

# Ước tính chi phí — luôn tra giá mới nhất tại trang pricing chính thức,
# đừng hardcode số giá vào code production vì giá có thể thay đổi.
PRICE_PER_MTOK_INPUT = 3.0  # ví dụ minh hoạ — KHÔNG dùng số này để tính hoá đơn thật
estimated_cost = count.input_tokens / 1_000_000 * PRICE_PER_MTOK_INPUT
print(f"Ước tính chi phí input: ${estimated_cost:.4f}")
```

```python
# Minh hoạ chi phí cộng dồn qua nhiều lượt hội thoại khi gửi lại toàn bộ history —
# đây là hành vi thật của mọi chatbot multi-turn, không phải giả định lý thuyết.
messages = []
running_input_tokens = 0

def send_turn(user_text: str):
    global running_input_tokens
    messages.append({"role": "user", "content": user_text})

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=200,
        messages=messages,
    )
    reply = next((b.text for b in response.content if b.type == "text"), "")
    messages.append({"role": "assistant", "content": reply})

    # usage.input_tokens phản ánh ĐÚNG số token đã xử lý ở lượt này —
    # bao gồm toàn bộ history, không chỉ câu hỏi mới.
    running_input_tokens += response.usage.input_tokens
    print(f"Lượt này input_tokens={response.usage.input_tokens}, "
          f"cộng dồn={running_input_tokens}")
    return reply

send_turn("Tên tôi là Dũng, làm ở khối dữ liệu.")
send_turn("Tôi vừa nói tên gì?")
send_turn("Bạn còn nhớ tôi làm ở khối nào không?")
# Quan sát: input_tokens tăng dần theo từng lượt dù câu hỏi luôn ngắn,
# vì mỗi request phải gửi lại toàn bộ messages list.
```

## Bài tập tự làm
1. Dùng `count_tokens` để so sánh số token của cùng một đoạn văn bản 200 từ viết bằng tiếng Việt có dấu và bằng tiếng Anh (tự dịch tương đương). Ghi lại chênh lệch và giải thích bằng khái niệm BPE ở trên.
2. Viết một vòng lặp gửi 10 lượt hội thoại liên tiếp (như ví dụ "Thực hành" phần 2), vẽ tay hoặc mô tả bằng lời đường cong tăng của `input_tokens` cộng dồn — nó tăng tuyến tính hay tăng nhanh hơn tuyến tính? Giải thích vì sao.
3. Tính thử: nếu một tool trong hệ thống MCP trả về JSON list 500 dashboard, mỗi dashboard trung bình 150 token (id, tên, mô tả, tags), thì việc đưa toàn bộ list đó vào context tốn khoảng bao nhiêu token? Nếu bạn giới hạn tool chỉ trả 20 kết quả đầu (phân trang), tiết kiệm được bao nhiêu %?

## Đào sâu / nâng cao

### Prompt caching — cơ chế và khi nào đáng dùng
Prompt caching hoạt động trên nguyên tắc **khớp tiền tố (prefix match)**: cache được tính từ đầu request tới điểm đặt `cache_control`, và **chỉ một byte thay đổi ở bất kỳ đâu trong tiền tố cũng làm mất cache toàn bộ phần sau đó**. Thứ tự render trong request luôn là `tools` → `system` → `messages` — nghĩa là nếu bạn đặt breakpoint cache ở cuối system prompt, cả phần tools definition và system prompt đều được cache cùng nhau.

Hệ quả thiết kế quan trọng: nội dung ổn định (system prompt cố định, danh sách tool cố định) phải nằm **trước** nội dung biến động (câu hỏi người dùng, timestamp, ID request) trong thứ tự render. Nhiều lỗi "cache không bao giờ hit" xuất phát từ việc nhúng `datetime.now()` hoặc UUID ngẫu nhiên vào system prompt — điều này làm tiền tố khác nhau ở mọi request, hủy cache hoàn toàn mà không có lỗi nào báo ra.

Đọc thêm: [Anthropic — Prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching).

### Context window không đồng nghĩa với "hiệu năng đều trên toàn bộ cửa sổ"
Một hiểu lầm phổ biến: model có context window 1M token thì "nhớ tốt như nhau" ở mọi vị trí trong cửa sổ đó. Thực tế, hiệu năng truy xuất thông tin trong context dài thường không đồng đều — thông tin ở đầu và cuối cửa sổ thường được "chú ý" (attention) tốt hơn thông tin ở giữa, một hiện tượng được gọi không chính thức là "lost in the middle" trong nhiều nghiên cứu benchmark. Không có số liệu benchmark cụ thể nào được chốt cứng ở đây vì kết quả thay đổi theo model và loại tác vụ — nhưng hệ quả thiết kế thực dụng: nếu một chi tiết trong tài liệu dài là **bắt buộc phải đúng**, đừng chỉ nhồi cả tài liệu vào context và hy vọng — hãy đặt chi tiết đó gần cuối prompt (gần câu hỏi) hoặc dùng retrieval để chỉ đưa đúng đoạn liên quan vào, thay vì đưa cả tài liệu.

### Context window khác nhau giữa các model — không nên hardcode
Số context window (200K, 1M...) khác nhau giữa các model và **có thể thay đổi khi model được nâng cấp**. Đừng hardcode giới hạn context vào logic ứng dụng — dùng Models API (`client.models.retrieve(model_id)`) để tra `max_input_tokens` động tại runtime nếu ứng dụng cần biết giới hạn chính xác, tránh code chết cứng theo một con số có thể lỗi thời sau một lần model được cập nhật.

Đọc thêm: [Anthropic — Context windows](https://docs.anthropic.com/en/docs/build-with-claude/context-windows).

## Bài tập senior
1. Team bạn đang build một chatbot hỏi-đáp về quy trình nội bộ, dùng một system prompt cố định dài 8000 token (quy định, hướng dẫn nghiệp vụ) cho mọi request. Traffic thực tế: khoảng 3 request/phút liên tục trong giờ hành chính, im hoàn toàn ngoài giờ. Đề xuất có nên dùng prompt caching hay không, với TTL nào (5 phút hay 1 giờ), và giải thích trade-off chi phí write-cache vs read-cache dựa trên tần suất traffic này.
2. Một sản phẩm hỏi-đáp cho phép người dùng dán nguyên văn một hợp đồng dài (có thể 50-100 trang) vào để hỏi. Thiết kế (mô tả kiến trúc, không cần code đầy đủ) cách xử lý input này sao cho không vượt context window, không tốn phí không cần thiết, và vẫn trả lời chính xác các câu hỏi về chi tiết cụ thể trong hợp đồng (ví dụ "điều khoản phạt vi phạm ở đâu"). Nêu rõ bạn chọn cắt cứng, tóm tắt, hay retrieval, và vì sao.
3. Trong một buổi review, có người đề xuất: "Để giảm token, mình rewrite lại toàn bộ system prompt sang tiếng Anh vì tiếng Anh tốn ít token hơn tiếng Việt, dù ứng dụng phục vụ người dùng Việt Nam." Đánh giá đề xuất này — nó đúng ở khía cạnh nào, sai/thiếu ở khía cạnh nào (gợi ý: phân biệt token của *system prompt* — do bạn viết, cố định — với token của *nội dung người dùng/output* — biến động, không kiểm soát trực tiếp được).

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được vì sao không dùng `tiktoken` để đếm token cho Claude.
- [ ] Biết context window là gì và phân biệt được với `max_tokens`.
- [ ] Tính được (ước lượng) chi phí input/output của một request cụ thể dựa trên giá tra từ trang pricing chính thức.
- [ ] Giải thích được vì sao chi phí input cộng dồn qua các lượt hội thoại multi-turn.
- [ ] Nêu được ít nhất 2 chiến lược cắt/quản lý context và biết khi nào dùng cái nào.
- [ ] Hiểu nguyên tắc prefix-match của prompt caching và vì sao thứ tự nội dung trong prompt quan trọng.
