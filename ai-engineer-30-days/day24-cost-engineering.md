# Ngày 24 — Cost engineering: caching, batching, model routing

## Mục tiêu hôm nay
Học cách giảm chi phí LLM có chủ đích — prompt caching, Batch API, model routing, và giảm token đầu vào/đầu ra — thay vì phản xạ mặc định "dùng model to nhất cho mọi việc".

## Đọc trước
- [Anthropic — Prompt caching](https://docs.anthropic.com/) (tìm mục "prompt caching" trong docs Anthropic — cơ chế `cache_control`, thời gian sống cache, điều kiện cache hit).
- [Anthropic — Batch API / Message Batches](https://docs.anthropic.com/) (tìm mục "Message Batches" — giảm giá, tăng thời gian xử lý, giới hạn số request/batch).
- [Anthropic — Pricing](https://docs.anthropic.com/) (tìm trang pricing chính thức — không chép số giá cụ thể vào đây vì giá thay đổi theo thời gian, luôn tra tại thời điểm quyết định).

## Khái niệm cốt lõi

### Vì sao "dùng model to nhất cho mọi thứ" là lựa chọn của người mới
Backend dev quen tư duy "chọn công nghệ tốt nhất trong khả năng rồi dùng chung cho toàn hệ thống" (ví dụ chọn 1 loại DB, 1 ngôn ngữ). Với LLM, chi phí không tuyến tính với chất lượng — một model mạnh hơn thường đắt hơn nhiều lần cho một mức cải thiện chất lượng nhỏ ở phần lớn task đơn giản, và ngược lại, dùng model yếu cho task khó dẫn tới chất lượng tệ mà không rẻ hơn bao nhiêu nếu phải retry/escalate sau đó. Senior engineer coi cost là một chiều thiết kế hệ thống ngay từ đầu — không phải việc "tối ưu sau khi bị complain hóa đơn" — và tối ưu có chủ đích ở 4 hướng: cache phần lặp lại, batch phần không cần real-time, route đúng model theo độ khó, và cắt token dư thừa.

### Prompt caching — cơ chế thật, không phải cache HTTP thông thường
Prompt caching (như Anthropic triển khai) cho phép đánh dấu một phần prompt (thường là phần đầu, tĩnh, lặp lại giữa nhiều request — ví dụ system prompt dài, tài liệu tham chiếu cố định, danh sách tool definition) để nhà cung cấp lưu lại trạng thái xử lý (cache) phần đó, và các request sau **trong một khoảng thời gian ngắn** tái sử dụng cache đó thay vì xử lý lại từ đầu.

Cơ chế thật cần hiểu đúng, không chỉ ở mức "cache thì rẻ hơn":
- Cache hoạt động theo nguyên tắc **prefix match** — phần được cache phải nằm ở đầu prompt (hoặc đầu một block cụ thể) và **giống chính xác byte-for-byte** với lần gọi trước để cache hit. Chỉ cần đổi 1 ký tự trong phần đã đánh dấu cache là cache miss cho phần đó.
- Đánh dấu phần cần cache qua tham số `cache_control` gắn vào block nội dung (ví dụ trong system prompt hoặc trong message) — không phải cache toàn bộ request tự động, phải khai báo tường minh phần nào muốn cache.
- Cache có **thời gian sống hữu hạn** (thường tính bằng phút, không phải vô hạn) — cache tự hết hạn nếu không có request nào dùng lại trong khoảng thời gian đó; mỗi lần cache hit thường refresh lại thời gian sống. Vì vậy prompt caching hiệu quả nhất khi có traffic đủ dày đặc dùng lại cùng prefix trong khoảng thời gian ngắn (ví dụ nhiều user cùng dùng 1 system prompt trong vài phút), không hiệu quả nếu request quá thưa.
- Giá cache **không đối xứng**: ghi vào cache (cache write, lần đầu) thường **đắt hơn** giá thông thường một chút, đọc từ cache (cache hit, các lần sau) thì **rẻ hơn** đáng kể — nên caching chỉ có lợi khi phần được cache đủ lớn và được tái sử dụng đủ nhiều lần để phần tiết kiệm ở các lần hit bù lại được chi phí ghi cache lần đầu. Tra số giá cụ thể tại trang pricing chính thức khi tính toán thật, không dùng số cũ.
- Ứng dụng thực dụng: system prompt dài (hướng dẫn, ví dụ few-shot, mô tả tool), tài liệu tham chiếu cố định trong RAG (nếu context đó không đổi giữa nhiều câu hỏi), hoặc few-shot example cố định — đặt các phần này ở đầu, đánh dấu cache, để phần thay đổi (câu hỏi user) ở cuối, sau phần cache.

### Batch API — đánh đổi latency lấy giá
Batch API (Message Batches của Anthropic) cho phép gửi một lượng lớn request cùng lúc, xử lý bất đồng bộ (không real-time), nhận kết quả sau một khoảng thời gian xử lý dài hơn nhiều so với gọi API thông thường, đổi lại giá rẻ hơn đáng kể so với gọi trực tiếp.

- Phù hợp cho việc **không cần trả lời ngay cho user đang chờ**: xử lý hàng loạt tài liệu (tóm tắt, phân loại, trích xuất thông tin), chạy lại toàn bộ golden dataset cho eval (Ngày 22) khi không cần kết quả tức thì, tiền xử lý dữ liệu cho pipeline offline, gắn label cho tập dữ liệu training/eval.
- Không phù hợp cho bất kỳ luồng có user đang chờ phản hồi trực tiếp (chat, tool-calling trong agent loop) — latency của batch có thể là hàng giờ, không phải giây.
- Thiết kế hệ thống thực dụng: tách rõ hai luồng ngay từ đầu — luồng real-time (dùng API thông thường, có thể kèm streaming — Ngày 25) và luồng batch (dùng Batch API cho việc xử lý số lượng lớn không gấp) — không trộn lẫn hai luồng vào cùng một code path, vì logic retry/timeout/theo dõi trạng thái của batch job khác hẳn một API call đồng bộ thông thường (batch job có trạng thái pending/processing/completed cần polling hoặc webhook, không phải request-response tức thì).

### Model routing — dùng đúng model cho đúng việc
Ý tưởng: không phải mọi request đều cần model mạnh nhất/đắt nhất. Model routing là kiến trúc định tuyến request tới model phù hợp với độ khó của task đó, thường theo 2 cách:

1. **Routing tĩnh theo loại tác vụ đã biết trước**: nếu biết rõ một loại request luôn đơn giản (ví dụ phân loại intent, trích xuất field có cấu trúc rõ, format lại text), route thẳng tới model rẻ mà không cần "hỏi" gì thêm — quyết định này nằm trong code logic, dựa trên loại endpoint/tool được gọi.
2. **Routing động bằng "trọng tài" (triage model)**: dùng một model rẻ, nhanh để **phân loại độ khó/độ rủi ro** của request trước, quyết định request đó có thể xử lý bằng model rẻ luôn, hay cần escalate lên model đắt hơn. Model trọng tài không cần trả lời câu hỏi gốc — chỉ cần trả lời "task này dễ hay khó", "câu hỏi này có rủi ro cao (liên quan tài chính/pháp lý) cần model tốt hơn không" — nên có thể dùng model rất rẻ, prompt ngắn, latency thấp cho bước này.

Đánh đổi cần cân nhắc khi thiết kế routing động:
- Thêm một lệnh gọi model (trọng tài) trước khi xử lý thật nghĩa là thêm latency và thêm một điểm có thể lỗi — với task thực sự dễ, tổng latency (gọi trọng tài + gọi model rẻ) có khi còn chậm hơn gọi thẳng model đắt một lần.
- Trọng tài có thể phân loại sai (đánh giá nhầm việc khó thành dễ) — cần có eval riêng cho chính bước routing này (đo tỉ lệ misroute), không mặc định tin trọng tài luôn đúng.
- Ngưỡng "khi nào escalate" nên có thể điều chỉnh và theo dõi qua thời gian (giống ngưỡng canary ở Ngày 23) — không phải hằng số cố định mãi.

### Giảm token đầu vào/đầu ra có chủ đích
Trước khi nghĩ tới đổi model, nhiều hệ thống có thể giảm chi phí đáng kể chỉ bằng cách giảm số token thực sự cần gửi/nhận:

- **Đầu vào**: cắt bớt context không cần thiết (ví dụ trong RAG, chỉ đưa vào các chunk thực sự liên quan sau rerank — Ngày 12 — thay vì nhồi tất cả kết quả retrieval thô); tóm tắt lịch sử hội thoại dài thay vì gửi full transcript mỗi lần (đánh đổi với mất chi tiết — cần cân nhắc theo bài toán); rút ngắn system prompt/tool definition dài dòng nếu không cần thiết cho chất lượng.
- **Đầu ra**: giới hạn `max_tokens` hợp lý theo nhu cầu thật (không đặt tuỳ ý một số lớn "cho chắc" nếu câu trả lời thực tế luôn ngắn); yêu cầu structured output (Ngày 4) súc tích (ví dụ JSON có field cần thiết, không yêu cầu model giải thích dài dòng nếu ứng dụng chỉ cần con số/field đó); với tác vụ lặp (ví dụ phân loại hàng loạt), thiết kế output ở dạng ngắn nhất có thể biểu diễn đủ thông tin (ví dụ trả về 1 ký tự category thay vì câu văn đầy đủ).
- Nguyên tắc: đo trước khi tối ưu — dùng token usage thật trả về trong response (không đoán) để biết phần nào của request đang tốn nhiều token nhất, rồi tối ưu đúng chỗ đó, tránh tối ưu cảm tính.

## Đối chiếu với code thật trong repo
`mcp-superset` có nhiều tool trả về dữ liệu có cấu trúc từ Superset (dataset, chart, dashboard) — đây chính là dạng dữ liệu dễ bị "nhồi thô" vào context của agent nếu không cẩn thận, làm tăng token đầu vào ở lượt gọi tiếp theo của LLM một cách không cần thiết (ví dụ response API Superset trả về nhiều field agent không cần dùng tới). Một hướng cost engineering thực tế cho repo này là rà lại từng tool trong `tools/` xem response trả về từ Superset có đang forward toàn bộ payload thô cho agent hay đã lọc field cần thiết — càng ít token đưa vào context của lượt gọi LLM kế tiếp, chi phí và latency của bước generate càng giảm. Ngoài ra, vì `core/context.py` forward session cookie theo từng user thật (không có service account chung), mọi request qua MCP server đều gắn với 1 người dùng cụ thể — nếu triển khai model routing hoặc caching ở tầng ứng dụng dùng chính server này, cần đảm bảo cache/routing không vô tình trộn lẫn dữ liệu/kết quả giữa các user khác nhau (một cache prefix cache dùng chung nhưng câu trả lời chứa dữ liệu riêng theo quyền của từng user là một lỗi bảo mật, không chỉ lỗi cost).

## Thực hành
```python
"""
Minh hoạ 3 kỹ thuật: đo token usage thật, prompt caching qua cache_control,
và model routing đơn giản bằng "trọng tài" rẻ quyết định escalate.
Chạy được với `pip install anthropic`.
"""
import anthropic

client = anthropic.Anthropic()

CHEAP_MODEL = "claude-3-5-haiku-20241022"
STRONG_MODEL = "claude-sonnet-4-5-20250929"

# Phần "tĩnh" dài — ứng dụng thật có thể là tài liệu hướng dẫn nội bộ,
# danh sách tool definition, hoặc few-shot example cố định.
STATIC_SYSTEM_CONTEXT = """Bạn là trợ lý nội bộ SSI Securities hỗ trợ tra cứu
dữ liệu Superset. Quy tắc: không đưa ra khuyến nghị đầu tư cụ thể, không dự
đoán giá. Luôn trả lời ngắn gọn, trích dẫn tên dataset/chart cụ thể khi có.
""" * 20  # lặp để mô phỏng 1 system prompt dài thật (few-shot, hướng dẫn chi tiết)


def call_with_prompt_caching(user_input: str):
    """cache_control đánh dấu STATIC_SYSTEM_CONTEXT để tái sử dụng ở các lần
    gọi sau — chỉ có lợi nếu nhiều request dùng lại đúng prefix này trong
    khoảng thời gian ngắn."""
    response = client.messages.create(
        model=STRONG_MODEL,
        max_tokens=300,
        system=[
            {
                "type": "text",
                "text": STATIC_SYSTEM_CONTEXT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_input}],
    )
    usage = response.usage
    print(
        f"input_tokens={usage.input_tokens}, "
        f"cache_creation_input_tokens={getattr(usage, 'cache_creation_input_tokens', 0)}, "
        f"cache_read_input_tokens={getattr(usage, 'cache_read_input_tokens', 0)}, "
        f"output_tokens={usage.output_tokens}"
    )
    return response.content[0].text


def triage_and_route(user_input: str) -> str:
    """Bước 1: dùng model rẻ làm trọng tài, chỉ quyết định độ khó — không trả
    lời câu hỏi gốc, để prompt ngắn và nhanh."""
    triage_prompt = f"""Câu hỏi: "{user_input}"
Đây là câu hỏi ĐƠN GIẢN (tra cứu thông tin cơ bản, có thể trả lời chắc chắn)
hay PHỨC TẠP (cần suy luận nhiều bước, liên quan số liệu tài chính nhạy cảm,
hoặc rủi ro trả lời sai cao)?
Trả lời CHỈ một từ: DON_GIAN hoặc PHUC_TAP."""

    triage_resp = client.messages.create(
        model=CHEAP_MODEL,
        max_tokens=10,
        messages=[{"role": "user", "content": triage_prompt}],
    )
    verdict = triage_resp.content[0].text.strip()

    # Bước 2: route theo verdict.
    target_model = STRONG_MODEL if "PHUC_TAP" in verdict else CHEAP_MODEL
    print(f"[routing] verdict={verdict} -> dùng model {target_model}")

    final_resp = client.messages.create(
        model=target_model,
        max_tokens=300,
        messages=[{"role": "user", "content": user_input}],
    )
    return final_resp.content[0].text


if __name__ == "__main__":
    print("--- Prompt caching (gọi 2 lần, lần 2 nên rẻ hơn nếu cache hit) ---")
    call_with_prompt_caching("Dataset nào chứa dữ liệu doanh thu quý 3?")
    call_with_prompt_caching("Cách tạo chart mới trong Superset?")

    print("\n--- Model routing ---")
    triage_and_route("Superset là gì?")  # kỳ vọng: DON_GIAN
    triage_and_route(
        "Phân tích xu hướng biến động của các chỉ số tài chính trong dashboard "
        "quý 3 và so sánh với quý 2, giải thích nguyên nhân có thể."
    )  # kỳ vọng: PHUC_TAP
```

## Bài tập tự làm
1. Chạy `call_with_prompt_caching` hai lần liên tiếp với cùng `STATIC_SYSTEM_CONTEXT` — quan sát `cache_creation_input_tokens` ở lần đầu và `cache_read_input_tokens` ở lần hai. Đổi 1 ký tự trong `STATIC_SYSTEM_CONTEXT` rồi gọi lại — xác nhận cache miss.
2. Chạy `triage_and_route` với 5 câu hỏi tự viết (2 dễ, 2 khó, 1 mơ hồ ở biên) — ghi lại verdict của trọng tài, đánh giá bằng tay xem trọng tài có phân loại đúng theo cảm nhận của bạn không.
3. Tính tay: giả sử model trọng tài rẻ hơn model mạnh X lần (tra giá thật tại thời điểm làm bài, không dùng số cũ) và 70% traffic thực tế là câu hỏi dễ — ước lượng % tiết kiệm chi phí tổng thể so với việc dùng thẳng model mạnh cho mọi request, có tính luôn chi phí gọi trọng tài cho cả câu dễ và khó.
4. Đọc kỹ tài liệu Batch API — viết ra (không cần code) một use case thật trong công việc của bạn phù hợp dùng Batch API, giải thích vì sao latency cao là chấp nhận được cho use case đó.

## Đào sâu / nâng cao

### Cache theo cấu trúc prompt, không phải cache theo nội dung
Khác với cache HTTP (key thường là URL/hash toàn bộ request), prompt caching hoạt động theo prefix — nghĩa là *thứ tự sắp xếp* các phần trong prompt ảnh hưởng trực tiếp tới hiệu quả cache. Thiết kế prompt tốt cho caching: đặt phần tĩnh (system instruction, tool definitions, tài liệu tham chiếu cố định) ở đầu, phần biến đổi (câu hỏi user, lịch sử hội thoại gần nhất) ở cuối — đảo ngược thứ tự này (biến đổi trước, tĩnh sau) sẽ vô hiệu hoá cache hoàn toàn dù nội dung tĩnh giống nhau.

### Chi phí ẩn của routing sai chiều
Một lỗi thiết kế routing hay gặp: dùng model rẻ cho câu hỏi tưởng là dễ nhưng thực ra khó, model trả lời sai, user không hài lòng, phải hỏi lại hoặc escalate lên người — tổng chi phí (gồm cả chi phí vận hành support, chi phí trải nghiệm user) cao hơn nhiều so với việc route đúng ngay từ đầu bằng model đắt hơn một chút. Cost engineering không chỉ nhìn giá tiền API mà phải nhìn tổng chi phí vòng đời của một request sai.

### Theo dõi cost per outcome, không chỉ cost per request
Metric "chi phí trung bình mỗi request" dễ đánh lừa nếu không gắn với outcome — một hệ thống rẻ hơn mỗi request nhưng tỉ lệ phải hỏi lại/escalate cao hơn có thể đắt hơn về tổng thể. Metric hữu ích hơn: chi phí trung bình mỗi *tác vụ hoàn thành thành công* (tính cả các lần retry/escalate dẫn tới hoàn thành đó) — cần kết hợp dữ liệu cost với dữ liệu chất lượng từ Ngày 22-23 mới tính được.

## Bài tập senior
Team bạn đang trả tiền model cho một tính năng "tóm tắt báo cáo nội bộ hằng ngày" — chạy 1 lần/ngày cho khoảng vài nghìn báo cáo, không có user chờ real-time, hiện đang gọi API thông thường (không dùng Batch API) với model mạnh nhất cho toàn bộ, không phân loại độ khó. Viết một đề xuất cải tiến cost (dạng bullet, ước lượng định tính "giảm được nhiều/ít" không cần số cụ thể) áp dụng ít nhất 3 trong 4 kỹ thuật đã học (caching, batching, routing, giảm token) — nêu rõ thứ tự triển khai ưu tiên và lý do (kỹ thuật nào rủi ro thấp/lợi ích cao nên làm trước).

## Checklist trước khi qua Ngày 25
- [ ] Giải thích đúng cơ chế prompt caching: prefix match, thời gian sống, giá không đối xứng giữa cache write/read.
- [ ] Biết khi nào Batch API phù hợp và khi nào tuyệt đối không dùng được (luồng real-time).
- [ ] Thiết kế được một bước triage/routing đơn giản, hiểu đánh đổi latency thêm vs tiết kiệm cost.
- [ ] Đọc được `usage` trong response API để biết chính xác số token input/output/cache, không đoán.
- [ ] Biết đo cost theo outcome, không chỉ theo request đơn lẻ.
</content>
