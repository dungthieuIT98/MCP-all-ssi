# Phần 2 — Context window, token, chi phí

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
Mọi model tính phí theo **hai mức giá riêng biệt trên mỗi triệu token (per-1M-token)**: giá cho input token và giá cho output token, và **output luôn đắt hơn input** — thường gấp 4-5 lần tuỳ model. Lý do nằm ở Phần 1: input được xử lý song song trong giai đoạn prefill, output phải sinh tuần tự token-by-token trong giai đoạn decode — decode tốn tài nguyên tính toán hơn nhiều cho cùng số token.

Vì giá thay đổi theo thời gian và theo model, **không chốt số liệu cụ thể ở đây** — luôn tra [trang pricing chính thức](https://docs.anthropic.com/en/docs/about-claude/pricing) để lấy số mới nhất trước khi tính ngân sách thật. Điều cần nhớ ở mức khái niệm: model nhỏ hơn (Haiku) rẻ hơn model lớn (Opus) khoảng một bậc độ lớn (order of magnitude) trên cùng khối lượng token — đây là lý do model routing (Phần 6) là một kỹ thuật tối ưu chi phí thật, không phải chi tiết vụn vặt.

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

**Cơ chế giá ghi (write) vs đọc (read) cache — dễ hiểu sai nhất:**

Cache không "giảm dần" liên tục — nó nhảy giữa 2 mức giá tuỳ request đó là **ghi mới** hay **đọc lại** phần đã cache, và hai mức giá này là **hệ số cố định do Anthropic công bố** (tra ở [trang pricing](https://docs.anthropic.com/en/docs/about-claude/pricing)), không phải công thức bạn tự tính ra được:

| Loại | Hệ số so với giá input gốc | Khi nào áp dụng |
|---|---|---|
| Ghi cache (write), TTL 5 phút | **×1.25** (đắt hơn bình thường) | Request đầu tiên thấy prefix này, hoặc cache đã hết hạn |
| Ghi cache (write), TTL 1 giờ | **×2** (đắt hơn 5 phút) | Như trên, nhưng chọn TTL dài hơn |
| Đọc cache (read/hit) | **×0.1** (rẻ) | Prefix giống byte-for-byte với lần ghi trước, còn trong TTL |
| Token không cache (bình thường) | ×1 | Phần message/câu hỏi mới, không đánh `cache_control` |

Điểm quan trọng: **chỉ phần được đánh `cache_control` mới áp dụng hệ số này** — phần còn lại của request (câu hỏi mới mỗi lượt) luôn trả giá ×1 như thường, không liên quan gì đến cache.

Ví dụ với system prompt 8000 token, giá gốc $5/1M, TTL 5 phút:
```
Request 1 (ghi lần đầu):        8000 × 0.000005 × 1.25 = $0.05
Request 2 (đọc, trong 5 phút):  8000 × 0.000005 × 0.1  = $0.004
Request 3 (đọc, trong 5 phút):  8000 × 0.000005 × 0.1  = $0.004
Request 4 (cache đã hết hạn):   8000 × 0.000005 × 1.25 = $0.05   ← ghi lại từ đầu
```

Vì vậy hoà vốn (so với không cache) chỉ đạt được nếu có **đủ số lượt đọc lại trong TTL** để bù cho chi phí ghi ban đầu — không cache 1 lần rồi bỏ đó (traffic thưa, khoảng cách giữa request dài hơn TTL) thường lỗ chứ không lợi, vì mỗi request lại phải ghi lại ở giá đắt hơn thay vì được đọc ở giá rẻ.

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
    system=[{
    "type": "text",
    "text": system_prompt,
    "cache_control": {"type": "ephemeral"} 
    }],
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
#
# LƯU Ý QUAN TRỌNG: cache_control KHÔNG làm giảm số token gửi đi — messages
# vẫn phải gửi đầy đủ mỗi lượt (API stateless, server không tự nhớ lượt trước).
# Nó chỉ làm phần token TRÙNG với lượt trước được tính giá rẻ hơn (~0.1x thay
# vì giá đầy). Nên input_tokens vẫn tăng dần như cũ — muốn thấy cache có
# hoạt động hay không phải đọc cache_read_input_tokens / cache_creation_input_tokens.
#
# system_prompt phải đủ dài (>= 512 token với Claude Opus 5) mới cache được —
# prompt ngắn dưới ngưỡng này sẽ âm thầm không cache (không lỗi, chỉ vô hiệu).
system_prompt = (
    "Bạn là trợ lý phân tích dữ liệu tài chính cho SSI Securities. "
    "Luôn trả lời ngắn gọn, dựa trên dữ liệu được cung cấp, không suy đoán. "
    "..."  # trong thực tế đây là đoạn hướng dẫn dài (>= 512 token) mới cache được
)

messages = []
running_input_tokens = 0

def send_turn(user_text: str):
    global running_input_tokens
    messages.append({"role": "user", "content": user_text})

    # Đặt breakpoint ở CUỐI message mới nhất (không phải chỉ ở system) —
    # để lượt sau tái sử dụng cache của TOÀN BỘ history tính đến message này,
    # không chỉ system prompt. Đây là điểm khác so với ví dụ trước.
    messages[-1] = {
        "role": "user",
        "content": [{
            "type": "text",
            "text": user_text,
            "cache_control": {"type": "ephemeral"},
        }],
    }

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=200,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},  # cache system prompt riêng
        }],
        messages=messages,
    )
    reply = next((b.text for b in response.content if b.type == "text"), "")
    messages.append({"role": "assistant", "content": reply})

    usage = response.usage
    running_input_tokens += usage.input_tokens
    print(
        f"input_tokens={usage.input_tokens} (không cache, giá đầy) | "
        f"cache_read={usage.cache_read_input_tokens} (đọc cache, giá ~0.1x) | "
        f"cache_creation={usage.cache_creation_input_tokens} (ghi cache, giá ~1.25x) | "
        f"cộng dồn input_tokens={running_input_tokens}"
    )
    return reply

send_turn("Tên tôi là Dũng, làm ở khối dữ liệu.")
send_turn("Tôi vừa nói tên gì?")
send_turn("Bạn còn nhớ tôi làm ở khối nào không?")
# Quan sát:
# - Lượt 1: cache_creation_input_tokens > 0 (lần đầu ghi cache, KHÔNG rẻ hơn —
#   ghi cache đắt hơn giá gốc ~1.25x), cache_read_input_tokens = 0.
# - Lượt 2, 3: cache_read_input_tokens > 0 — phần history của các lượt trước
#   được đọc từ cache với giá rẻ, chỉ phần message mới là giá đầy.
# - input_tokens (tổng số token thật) vẫn tăng dần qua từng lượt như cũ —
#   cache không xoá gì khỏi history, chỉ đổi GIÁ của phần trùng lặp.
```

### Compaction — khi cache không đủ, cần giảm THẬT số token trong history

Cache ở trên không xoá gì khỏi `messages` — history vẫn phình to vô hạn, đến lúc nào đó sẽ chạm giới hạn context window dù có cache hay không. **Compaction** giải quyết đúng vấn đề đó: khi history sắp vượt ngưỡng, server tự động thay phần cũ bằng một bản tóm tắt ngắn hơn, làm giảm thật số token của history — không chỉ giảm giá như cache.

Khác biệt cốt lõi cần nhớ: **cache giữ nguyên history, chỉ đổi giá**; **compaction thay đổi thật nội dung history** — 40 lượt cũ có thể bị nén thành 1 block tóm tắt duy nhất. Việc nén này do server làm, nhưng client (code của bạn) có nghĩa vụ giữ đúng kết quả đó lại trong `messages` cho lượt sau — nếu chỉ lấy phần text trả lời và bỏ qua block tóm tắt, bản tóm tắt sẽ biến mất và server không còn biết gì về phần history đã bị nén.

```python
# Compaction là tính năng beta — cần beta header và dùng client.beta.messages
# (không phải client.messages như các ví dụ trên).
# Model hỗ trợ: Claude Opus 5, Opus 4.8, Sonnet 5, Fable 5/Mythos 5, Sonnet 4.6.
messages = []

def send_turn_with_compaction(user_text: str):
    messages.append({"role": "user", "content": user_text})

    response = client.beta.messages.create(
        betas=["compact-2026-01-12"],
        model="claude-opus-5",
        max_tokens=200,
        messages=messages,
        # Server sẽ tự kiểm tra khi context sắp chạm ngưỡng (mặc định ~150K
        # token) và tự chèn bước tóm tắt phần history cũ TRƯỚC khi trả lời
        # câu hỏi hiện tại — bạn không cần tự tính khi nào nên tóm tắt.
        context_management={"edits": [{"type": "compact_20260112"}]},
    )

    # QUAN TRỌNG NHẤT của compaction: phải append TOÀN BỘ response.content
    # (bao gồm block "compaction" nếu có), KHÔNG chỉ lấy text trả lời.
    # Nếu chỉ append text, bản tóm tắt bị mất và lượt sau server "quên"
    # hoàn toàn những gì đã tóm tắt.
    messages.append({"role": "assistant", "content": response.content})

    # In ra để quan sát: nếu server vừa thực hiện compaction, sẽ thấy 1 block
    # có type == "compaction" xuất hiện trong response.content.
    for block in response.content:
        if block.type == "compaction":
            print(f"[Đã compact] Tóm tắt: {block.content[:200]}...")
        elif block.type == "text":
            print(f"[Trả lời]: {block.text}")

    return messages

# Trong thực tế, compaction chỉ kích hoạt khi history đủ lớn (gần ~150K token)
# — với hội thoại vài lượt ngắn như ví dụ trên sẽ KHÔNG thấy block "compaction"
# xuất hiện, vì chưa đủ ngưỡng. Muốn thấy nó hoạt động, cần một history dài
# thật (nhiều lượt, hoặc nạp sẵn tài liệu lớn vào context) hoặc set ngưỡng
# trigger thấp hơn để test — xem tài liệu chính thức để biết cách chỉnh ngưỡng.
```

**Tóm lại 2 kỹ thuật, dùng khi nào:**

| | Cache | Compaction |
|---|---|---|
| Đụng đến history không | Không, giữ nguyên 100% | Có, nén phần cũ thành tóm tắt |
| Giải quyết vấn đề gì | Chi phí (giá tiền) | Kích thước context (tránh vượt limit) |
| `input_tokens` báo về | Vẫn tăng dần như không cache | Giảm sau khi được compact |
| Khi nào dùng | Hội thoại/agent lặp lại nhiều lần với prefix ổn định | Hội thoại/agent chạy rất dài, có nguy cơ chạm context window |

## Bài tập tự làm
1. Dùng `count_tokens` để so sánh số token của cùng một đoạn văn bản 200 từ viết bằng tiếng Việt có dấu và bằng tiếng Anh (tự dịch tương đương). Ghi lại chênh lệch và giải thích bằng khái niệm BPE ở trên.
+ tiếng việt nhiều hơn vì nhiều dấu hơn => số lượng token trả ra nhiều hơn

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
=> với promt lớn và 3 lần 1 p thì ueu tiên cache 5p .
wrete cache và read cache  chỉ tốn 800 thôi .

2. Một sản phẩm hỏi-đáp cho phép người dùng dán nguyên văn một hợp đồng dài (có thể 50-100 trang) vào để hỏi. Thiết kế (mô tả kiến trúc, không cần code đầy đủ) cách xử lý input này sao cho không vượt context window, không tốn phí không cần thiết, và vẫn trả lời chính xác các câu hỏi về chi tiết cụ thể trong hợp đồng (ví dụ "điều khoản phạt vi phạm ở đâu"). Nêu rõ bạn chọn cắt cứng, tóm tắt, hay retrieval, và vì sao.
=> xử lý sematic + chuck + rag , sau đó tì ra top chuck rồi đưa vào ai trả lời .


3. Trong một buổi review, có người đề xuất: "Để giảm token, mình rewrite lại toàn bộ system prompt sang tiếng Anh vì tiếng Anh tốn ít token hơn tiếng Việt, dù ứng dụng phục vụ người dùng Việt Nam." Đánh giá đề xuất này — nó đúng ở khía cạnh nào, sai/thiếu ở khía cạnh nào (gợi ý: phân biệt token của *system prompt* — do bạn viết, cố định — với token của *nội dung người dùng/output* — biến động, không kiểm soát trực tiếp được).


=> tối ưu 1 cách ngớ ngẩn, thay vì đổi xang tiếng việt thì dùng promt caching đi , rồi sau đó compaction lại history còn hơn.
=> chuyển xang tiếng anh cũng chả giảm đc bao nhiêu mà còn k ddofng nhất ngôn ngữ với câu hỏi và câu trl .

## Câu hỏi cho Technical Leader

    1. **Ngân sách & FinOps**: Bạn được giao build một trợ lý AI dùng nội bộ cho 2000 nhân viên SSI, mỗi người trung bình 15 câu hỏi/ngày, mỗi câu có RAG context ~3000 token. Sếp hỏi "chi phí 1 năm là bao nhiêu, và nếu traffic tăng gấp 3 vào Q4 thì sao?" Bạn thiết kế cơ chế nào để dự báo và cảnh báo chi phí trước khi nó vượt ngân sách (không phải nhìn hoá đơn cuối tháng mới biết)? Đề xuất kiến trúc rate-limit/quota theo user, theo phòng ban, và điểm nào nên cảnh báo sớm.

2. **Model routing như một quyết định kiến trúc, không chỉ tối ưu chi phí**: Nếu bạn thiết kế một hệ thống route câu hỏi tự động (câu đơn giản → Haiku, câu phức tạp → Opus): rủi ro gì phát sinh khi bộ phân loại route sai (câu phức tạp bị route nhầm sang model rẻ)? Ai chịu trách nhiệm khi model rẻ trả lời sai một câu hỏi liên quan đến số liệu tài chính/quy định — có nên áp dụng model routing cho mọi loại truy vấn, hay cần loại trừ một số nhóm nghiệp vụ (ví dụ liên quan UBCKNN, tư vấn đầu tư)?
    Lớp 1 — Keyword/rule routing sang model mạnh

Vấn đề: keyword-matching sẽ miss nhiều câu (người dùng không dùng đúng từ khoá "UBCKNN" nhưng vẫn hỏi về quy định niêm yết chẳng hạn). Nên coi keyword list là tập hợp mở, không đóng — tức là:

Match keyword → chắc chắn route lên model mạnh (an toàn).
Không match keyword → không có nghĩa là an toàn để route xuống model rẻ, vẫn cần lớp phân loại ngữ nghĩa (semantic classifier) phía sau làm lưới an toàn thứ hai, vì keyword list luôn có khoảng trống.
Lớp 2 — Deny/chặn cứng cho nhóm nhạy cảm, bắt buộc người xác nhận

Đây là phần quan trọng nhất và cần tách rõ hai loại "nhạy cảm":

Nhạy cảm về nội dung quy định/tư vấn đầu tư → đúng như bạn nói, chặn auto-answer, bắt buộc người có thẩm quyền duyệt trước khi gửi ra ngoài (khớp với nguyên tắc human decision authority ở trên).
Nhạy cảm về dữ liệu (OTP, số CMND/CCCD khách hàng, token, mật khẩu...) → đây không phải vấn đề "chọn model", mà là không được để lộ/xử lý ở bất kỳ model nào, bất kể mạnh hay yếu. Hai loại rule này nên tách riêng trong hệ thống, vì cách xử lý khác nhau (một là "escalate cho người", một là "refuse hoàn toàn").
Lớp 3 — AI đánh giá độ khó, người dùng tự chọn model

Đây là phần hay nhưng có một rủi ro ngược: nếu AI đánh giá "câu này đơn giản, dùng Haiku là đủ" và người dùng tin theo, thì bản chất vẫn là routing tự động — chỉ là thêm một bước UI cho người dùng "bấm xác nhận". Nó chỉ thực sự an toàn hơn routing tự động nếu:

AI hiển thị lý do đánh giá (không chỉ độ khó, mà cả mức rủi ro hậu quả nếu sai), để người dùng chọn có thông tin, không phải chọn mù.
Với câu đã bị đánh dấu ở Lớp 1/2, không đưa lựa chọn model rẻ vào menu — tức Lớp 3 chỉ áp dụng cho câu đã qua được Lớp 1 và 2, không phải lớp thay thế cho chúng.


3. **Đánh đổi giữa cache/compaction và tính đúng đắn (correctness)**: Compaction làm mất thông tin gốc thật (nén thành tóm tắt do model tự viết). Với một agent nội bộ xử lý quy trình có tính pháp lý/tuân thủ (ví dụ tra cứu quy định giao dịch), bạn có chấp nhận để server tự động compact history hay không? Thiết kế nguyên tắc: khi nào bắt buộc giữ nguyên văn (không được tóm tắt/nén) và khi nào được phép compact, và cơ chế audit để biết một câu trả lời có dựa trên phần đã bị nén hay không.
=> chỉ compact đoạn hội thoại , k compact văn bản gốc
=> văn bản gốc phải đc lưu tách histoty, các câu trả lời phải trích dẫn chính sác tù văn bản gốc đó.


4. **Lost-in-the-middle như một rủi ro compliance, không chỉ rủi ro UX**: Nếu một RAG system tra cứu quy định nội bộ đưa "quy định mới nhất" nằm giữa context (bị model bỏ sót) và trả lời dựa trên quy định cũ hơn nằm ở đầu/cuối — hệ quả có thể là tư vấn sai lệch cho khách hàng hoặc vi phạm quy định UBCKNN. Bạn thiết kế cơ chế nào ở tầng kiến trúc (không phải "dặn model cẩn thận hơn") để giảm rủi ro này về mức chấp nhận được, và làm sao đo lường được rủi ro đó thay vì chỉ tin cảm tính?

5. **Đa ngôn ngữ và data residency/governance, không chỉ token cost**: Dữ liệu hợp đồng/quy định nội bộ SSI khi đưa vào context của một API bên thứ ba (Anthropic) — chính sách nào cần áp dụng trước khi cho phép loại dữ liệu nào đi qua LLM external, và khi nào bắt buộc phải dùng giải pháp on-prem/private deployment thay vì API công khai?

Chính sách kiểm soát dữ liệu qua LLM bên ngoài (SSI):

Dữ liệu được phân loại theo 4 tiêu chí — mức nhạy cảm (Công khai/Nội bộ/Giới hạn), có định danh khách hàng hay không, và có ràng buộc pháp lý về nơi lưu trữ hay không — để xác định kênh xử lý:

Công khai, không định danh khách hàng → được gửi qua API ngoài (Anthropic) tự do.
Nội bộ, không định danh khách hàng → được gửi qua API ngoài, nhưng phải qua lớp lọc DLP chạy on-prem trước (rule/regex cho dữ liệu có cấu trúc + phân loại ngữ nghĩa cho dữ liệu không cấu trúc, fail closed khi không phân loại rõ được), kèm log để An ninh thông tin audit định kỳ.
Có định danh khách hàng nhưng không ràng buộc residency pháp lý → phải ẩn danh hoá/che thông tin định danh trước, sau đó mới qua lớp DLP như trên; review lại định kỳ.
Có ràng buộc residency pháp lý và/hoặc thuộc project đã được xếp loại nhạy cảm đặc biệt → bắt buộc xử lý on-prem/private deployment toàn bộ, không đi qua API công khai dưới bất kỳ hình thức nào.
Quyền truy cập vào từng loại dữ liệu được giới hạn theo role/phòng ban ngay từ đầu vào. Việc xếp một project vào nhóm 4 (bắt buộc on-prem) do An ninh thông tin và Bộ phận Luật & Tuân thủ xác nhận, không do đội kỹ thuật tự quyết — và phải được đánh giá lại mỗi khi phạm vi dữ liệu của project thay đổi. Trước khi cho phép bất kỳ dữ liệu Nội bộ/Giới hạn nào đi qua API ngoài, phải xác nhận được điều khoản hợp đồng với nhà cung cấp về việc dữ liệu không bị dùng để huấn luyện model và có chính sách lưu giữ (retention) rõ ràng — nếu chưa xác nhận được, mặc định coi như chưa được phép.

6. **Observability cho chi phí/token ở tầng hệ thống, không chỉ ở tầng 1 request**: Với hàng chục tính năng LLM chạy song song trong công ty (chatbot nội bộ, MCP tool cho Superset, RAG hợp đồng...), làm sao biết **tính năng nào đang đốt tiền nhiều nhất** khi hoá đơn API là một con số gộp duy nhất từ Anthropic? Thiết kế cơ chế gắn nhãn (tagging) request theo tính năng/team/user để có thể breakdown chi phí, và nên log những field nào (input_tokens, cache_read, cache_creation, output_tokens, model, feature_id...) để sau này trả lời được câu "tại sao tháng này đắt hơn tháng trước" mà không phải đoán.
Đúng hướng — dùng một web app monitoring (self-hosted, ví dụ Langfuse hoặc Helicone) và tự định nghĩa các cột log theo nhu cầu. Chốt lại bảng cột đã thống nhất ở các câu trước:

Bảng cột cho hệ thống monitoring token/chi phí LLM:

Cột	Ý nghĩa
request_id	ID định danh duy nhất mỗi request, dùng để trace/điều tra khi cần
feature_id	Tính năng nào gọi (chatbot nội bộ, MCP Superset, RAG hợp đồng...)
project_id	Project/dự án nào
team	Phòng ban chịu chi phí
user_id	Ai gọi (nội bộ)
timestamp	Thời điểm gọi — để group theo giờ/ngày/tháng
model	Model nào được dùng (vì giá khác nhau theo model)
input_tokens	Số token đầu vào
output_tokens	Số token đầu ra (thường đắt hơn input)
cache_read_tokens	Token đọc từ cache (rẻ hơn, quan trọng để biết cache có hiệu quả không)
cache_creation_tokens	Token tạo cache mới
Với bảng này, web app monitoring (Langfuse/Helicone tự host) sẽ tự tính ra chi phí theo từng dòng dựa trên giá của từng model, rồi cho phép filter/group theo bất kỳ cột nào (theo feature, theo user, theo tháng...) để trả lời trực tiếp câu hỏi "tính năng nào đốt tiền nhiều nhất" và "tại sao tháng này đắt hơn" mà không cần đoán.


7. **Prompt injection qua context dài — rủi ro bảo mật, không chỉ rủi ro chi phí**: Nếu một RAG system hoặc agent MCP đưa nội dung từ nguồn không tin cậy (tài liệu người dùng paste vào, kết quả trả về từ một tool gọi API bên ngoài) thẳng vào context, kẻ tấn công có thể nhúng chỉ thị giả ("ignore previous instructions...") trong chính nội dung đó. Bạn thiết kế ranh giới nào giữa "nội dung để đọc" và "chỉ thị để thực thi" ở tầng kiến trúc prompt (không phải chỉ dặn model "cẩn thận với instruction lạ")? Nhóm nào trong hệ thống MCP nội bộ (ví dụ tool trả JSON từ Superset) cần áp dụng nguyên tắc này trước tiên?

8. **Đánh giá chất lượng RAG — làm sao biết retrieval đang lấy đúng, không chỉ tin cảm tính**: Sau khi triển khai RAG cho hợp đồng/quy định, làm sao đo lường một cách có hệ thống việc "retrieval có lấy đúng đoạn liên quan hay không" và "câu trả lời có bám sát đúng đoạn được lấy hay không" (tách bạch hai loại lỗi: lỗi retrieval vs lỗi generation)? Đề xuất một bộ test case tối thiểu (golden set) và tần suất re-run cần thiết khi thay đổi chunking strategy hoặc đổi embedding model.

9. **Multi-tenant context isolation**: Nếu một hệ thống AI nội bộ phục vụ nhiều phòng ban (mỗi phòng có tài liệu/dữ liệu riêng, có phòng xử lý dữ liệu khách hàng nhạy cảm hơn phòng khác) dùng chung một RAG pipeline và vector store — rủi ro gì nếu retrieval của phòng A vô tình lấy nhầm tài liệu của phòng B vào context? Thiết kế cơ chế cách ly (isolation) ở tầng nào (index riêng, metadata filter bắt buộc, hay hạ tầng riêng hoàn toàn) là đủ, và đánh đổi chi phí/độ phức tạp vận hành giữa các lựa chọn đó.

10. **Vendor lock-in và kế hoạch dự phòng (fallback)**: Toàn bộ thiết kế cache/compaction/token counting ở trên gắn chặt với API cụ thể của Anthropic (cấu trúc `cache_control`, beta header `compact-*`, endpoint `count_tokens`). Nếu một ngày cần chuyển sang model khác (đổi nhà cung cấp, hoặc dùng song song nhiều model cho các tác vụ khác nhau), phần nào trong kiến trúc hiện tại sẽ phải viết lại hoàn toàn, và phần nào có thể trừu tượng hoá (abstraction layer) từ đầu để giảm chi phí chuyển đổi sau này? Đánh đổi giữa "tối ưu sâu cho 1 vendor" và "giữ khả năng portable" nên nghiêng về bên nào ở giai đoạn hiện tại của dự án?

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được vì sao không dùng `tiktoken` để đếm token cho Claude.
- [ ] Biết context window là gì và phân biệt được với `max_tokens`.
- [ ] Tính được (ước lượng) chi phí input/output của một request cụ thể dựa trên giá tra từ trang pricing chính thức.
- [ ] Giải thích được vì sao chi phí input cộng dồn qua các lượt hội thoại multi-turn.
- [ ] Nêu được ít nhất 2 chiến lược cắt/quản lý context và biết khi nào dùng cái nào.
- [ ] Hiểu nguyên tắc prefix-match của prompt caching và vì sao thứ tự nội dung trong prompt quan trọng.
