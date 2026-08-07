# Ngày 1 — LLM sinh token thế nào

## Mục tiêu hôm nay
Hiểu đúng cơ chế next-token prediction để không còn nói "AI hiểu câu hỏi" một cách sai lệch — vì mọi quyết định kỹ thuật sau này (prompt engineering, structured output, guardrail, đánh giá hallucination) đều xuất phát từ việc model chỉ làm một việc: dự đoán token tiếp theo dựa trên phân phối xác suất.

## Đọc trước
- [Anthropic — What is Claude?](https://docs.anthropic.com/en/docs/about-claude/models/overview) (tổng quan model, không sa vào toán)
- [Attention Is All You Need (Vaswani et al., 2017)](https://arxiv.org/abs/1706.03762) — paper gốc kiến trúc Transformer, không cần đọc hết, chỉ cần hiểu §3.2 (attention) ở mức khái niệm
- [Andrej Karpathy — Let's build GPT: from scratch, in code, spelled out](https://www.youtube.com/watch?v=kCc8FmEb1nY) — video dựng một GPT nhỏ từ đầu, xem 20-30 phút đầu là đủ để thấy rõ next-token prediction chạy thế nào
- [Anthropic — Extended thinking overview](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) (đọc lướt, chỉ cần hiểu "thinking" cũng là token được sinh ra theo cùng cơ chế, không phải một quá trình "suy nghĩ" tách biệt)

## Khái niệm cốt lõi

### Next-token prediction là toàn bộ câu chuyện
Một LLM là một hàm số khổng lồ: nhận vào một chuỗi token (câu hỏi + toàn bộ ngữ cảnh trước đó), xuất ra một **phân phối xác suất** trên toàn bộ vocabulary (thường vài chục nghìn đến hơn 100 nghìn token khả dĩ). Không có bước "hiểu ý" tách biệt khỏi bước "sinh chữ" — hai thứ đó là một. Model không có biểu diễn nội tại nào của "sự thật" ngoài các trọng số (weights) đã học được từ dữ liệu huấn luyện.

Quá trình sinh văn bản là **autoregressive**: model sinh token thứ N dựa trên (prompt + token 1..N-1) đã sinh ra trước đó, rồi nối token N vào chuỗi, đưa lại toàn bộ chuỗi vào model để sinh token N+1, lặp lại đến khi gặp token kết thúc (`stop_reason: end_turn`) hoặc chạm giới hạn `max_tokens`. Đây là lý do một câu trả lời dài luôn tốn nhiều lượt forward-pass hơn câu ngắn — không có "đường tắt" để model biết trước toàn bộ câu trả lời rồi mới in ra.

Điểm quan trọng cho backend dev: **API là stateless**. Mỗi request bạn gửi đi là một lần chạy forward-pass trên toàn bộ ngữ cảnh bạn gửi (system + messages). Model không "nhớ" giữa các request — cái gọi là "hội thoại nhiều lượt" chỉ là bạn tự gửi lại toàn bộ lịch sử ở mỗi lượt gọi. Không hiểu điều này thì thiết kế cache, giới hạn context, tối ưu chi phí ở Ngày 2 sẽ sai từ gốc.

### Sampling: temperature, top-p, top-k
Sau khi model tính ra phân phối xác suất trên vocabulary, hệ thống phải **chọn** một token cụ thể từ phân phối đó — bước này gọi là sampling, và nó là nơi các tham số quen thuộc phát huy tác dụng:

- **Temperature**: chia logit (giá trị trước khi qua softmax) cho một số T trước khi tính xác suất. T thấp (gần 0) làm phân phối "nhọn" hơn — token có xác suất cao càng áp đảo, output gần như deterministic. T cao làm phân phối "phẳng" hơn — các token ít khả dĩ hơn cũng có cơ hội được chọn, output đa dạng/sáng tạo hơn nhưng dễ lạc đề hoặc sai sự thật hơn.
- **Top-k**: chỉ giữ lại k token có xác suất cao nhất, loại bỏ phần còn lại của phân phối trước khi sample. Top-k nhỏ = an toàn nhưng cứng nhắc; top-k lớn = đa dạng nhưng rủi ro chọn trúng token kỳ quặc.
- **Top-p (nucleus sampling)**: giữ lại tập token nhỏ nhất mà tổng xác suất cộng lại ≥ p (ví dụ p=0.9 giữ 90% "khối xác suất"). Khác top-k ở chỗ top-p co giãn theo hình dạng phân phối — lúc model rất chắc chắn thì tập giữ lại rất nhỏ, lúc model lưỡng lự thì tập giữ lại lớn hơn tự động.

Một điều thực dụng cần biết ngay: **các model Claude thế hệ mới (4.6 trở lên, Sonnet 5, Opus 5) đã loại bỏ `temperature`/`top_p`/`top_k` khỏi API** — gửi các tham số này sẽ trả lỗi 400. Lý do là các model này được huấn luyện để việc điều khiển hành vi (giọng văn, độ sáng tạo) nên làm qua prompt, không qua sampling. Nếu bạn đọc code cũ hoặc tài liệu cũ có `temperature=0.7`, biết rằng đó là kỹ thuật của thế hệ model trước — dùng cho Opus 4.5, Sonnet 4.5, Haiku 4.5 trở về trước.

**"Temperature = 0 thì output deterministic"** — cách nói này chỉ đúng một phần và **chưa từng được đảm bảo tuyệt đối** trên bất kỳ model nào, kể cả các model cũ còn nhận `temperature`. Lý do: hạ tầng suy luận phân tán (batching động, floating-point non-determinism trên GPU) vẫn có thể khiến hai lần gọi giống hệt nhau cho ra output khác nhau dù xác suất token cao nhất luôn được ưu tiên. Đừng thiết kế hệ thống production dựa trên giả định "cùng input → luôn cùng output".

### Vì sao "AI hiểu câu hỏi" là cách nói sai lệch
Nói model "hiểu" ngụ ý có một quá trình suy luận ngữ nghĩa tách biệt, có chủ đích, giống người. Thực tế: model chỉ tối ưu một mục tiêu duy nhất trong huấn luyện — dự đoán token tiếp theo sao cho giống phân phối trong dữ liệu huấn luyện (rồi được fine-tune thêm bằng RLHF/instruction tuning để bám sát ý định người dùng hơn). Hành vi "có vẻ hiểu" là **hệ quả nổi lên (emergent)** từ việc tối ưu mục tiêu đó ở quy mô đủ lớn, không phải một module riêng biệt để "hiểu" rồi mới "trả lời".

Hệ quả thực dụng: khi model trả lời sai một câu hỏi logic đơn giản nhưng trả lời đúng một câu phức tạp hơn, đừng ngạc nhiên — không có "mức độ hiểu" tăng dần đều theo độ khó theo cách con người cảm nhận. Điều model làm tốt là những gì **có nhiều mẫu tương tự trong dữ liệu huấn luyện và không đòi hỏi tính toán chính xác nhiều bước** — sai lệch ở đây thường là vấn đề phân phối dữ liệu, không phải "AI chưa đủ thông minh".

### Hallucination bắt nguồn từ đâu
Hallucination — model tự tin đưa ra thông tin sai — không phải lỗi (bug) mà là **hệ quả cấu trúc** của cách model được huấn luyện và sinh token:

1. **Model luôn phải sinh ra token tiếp theo.** Không có nút "tôi không biết" mặc định trong quá trình sample — model luôn phải chọn một token có xác suất cao nhất tại mỗi bước, kể cả khi không có dữ liệu huấn luyện nào hỗ trợ câu trả lời đó. Việc trả lời "tôi không biết" chỉ xảy ra khi *chính câu đó* có xác suất cao trong phân phối — nghĩa là phải được huấn luyện/prompt để làm vậy, không tự nhiên xảy ra.
2. **Độ trôi chảy (fluency) không tương quan với độ chính xác (factuality).** Model được tối ưu để sinh ra văn bản giống phân phối ngôn ngữ tự nhiên — câu văn mạch lạc, ngữ pháp đúng, giọng điệu tự tin. Không có tín hiệu huấn luyện nào trực tiếp ép "chỉ nói điều đúng" — tính đúng đắn là hệ quả gián tiếp của việc dữ liệu huấn luyện chủ yếu chứa thông tin đúng, không phải một ràng buộc cứng.
3. **Autoregressive error compounding.** Vì mỗi token được sinh dựa trên các token trước, một sai lệch nhỏ ở token thứ N (một tên riêng bị lẫn, một số liệu bị suy diễn) sẽ trở thành một phần "sự thật đã cho" khi sinh token N+1 — model không quay lại sửa, nó tiếp tục xây dựng câu chuyện nhất quán với cái đã sinh ra, đúng hay sai không quan trọng bằng nhất quán.
4. **Ngoài phạm vi kiến thức huấn luyện (out-of-distribution).** Hỏi về sự kiện sau ngày cắt dữ liệu huấn luyện, một API nội bộ công ty bạn không có trong dữ liệu public, hoặc một câu hỏi cực kỳ chi tiết (số phiên bản chính xác, số dòng trong file) — model sẽ generalize từ pattern gần giống nhất nó biết, và pattern đó có thể sai hoàn toàn với thực tế bạn cần.

Hệ quả kỹ thuật: **không có cách nào loại bỏ hallucination bằng prompt engineering thuần túy** — chỉ có thể giảm thiểu. Các kỹ thuật giảm thiểu thật (không phải "câu thần chú"): grounding bằng RAG/tool-calling để model trích dẫn từ nguồn thay vì generate từ trí nhớ tham số, structured output để giảm không gian tự do sinh chữ, và ở tầng ứng dụng — validate output trước khi tin dùng, không bao giờ pipe trực tiếp output model vào hành động có side-effect mà không qua kiểm tra.

## Đối chiếu với code thật trong repo
Repo `mcp-superset` không tự chạy inference — nó là MCP server expose tool cho một AI assistant (Claude) gọi vào Superset. Nhưng cơ chế next-token prediction chi phối trực tiếp cách AI assistant quyết định gọi tool nào: khi Claude "đọc" danh sách tool đã đăng ký qua `@mcp.tool()` trong các file `tools/chart.py`, `tools/dashboard.py`, v.v., việc chọn gọi tool nào — và điền argument gì — cũng chỉ là next-token prediction trên một vocabulary đặc biệt (tên tool + JSON schema tham số). Docstring của mỗi tool (ví dụ mô tả của `superset_chart_list`) chính là văn bản duy nhất model dùng để "quyết định" — không có kênh giao tiếp nào khác giữa bạn (người viết tool) và model ngoài chuỗi ký tự đó. Ngày 3-4 sẽ đi sâu vào việc docstring này thực chất là một dạng prompt engineering.

## Thực hành
Cài SDK và quan sát trực tiếp hiệu ứng của effort/thinking lên cách model sinh token — không cần tài khoản trả phí lớn, một vài request là đủ để thấy sự khác biệt.

```bash
pip install anthropic
```

```python
import anthropic

client = anthropic.Anthropic()  # đọc ANTHROPIC_API_KEY từ biến môi trường

# Câu hỏi cố ý mơ hồ/không có "một đáp án đúng" để quan sát model
# sinh ra các phương án khác nhau khi gọi lại nhiều lần — minh hoạ
# rằng sampling là ngẫu nhiên có kiểm soát, không phải deterministic.
question = "Đặt tên cho một quán cà phê nhỏ ở Hà Nội, chỉ trả 1 tên, không giải thích."

for i in range(3):
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=50,
        messages=[{"role": "user", "content": question}],
    )
    # response.content là list các content block — luôn kiểm tra .type
    # trước khi đọc .text, vì có thể có thinking block hoặc tool_use block.
    text = next((b.text for b in response.content if b.type == "text"), "")
    print(f"Lần {i + 1}: {text.strip()}")

# Quan sát: mặc dù cùng prompt, 3 lần gọi có thể ra 3 tên khác nhau.
# Đây KHÔNG phải "AI sáng tạo" theo nghĩa có chủ đích — đó là sampling
# trên phân phối xác suất, mỗi lần forward-pass là một phiên độc lập.
```

```python
# Minh hoạ autoregressive: dùng streaming để thấy token sinh ra TỪNG CÁI MỘT,
# không phải toàn bộ câu trả lời xuất hiện cùng lúc.
with client.messages.stream(
    model="claude-opus-5",
    max_tokens=200,
    messages=[{"role": "user", "content": "Giải thích autoregressive generation trong 2 câu."}],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)  # mỗi lần in ra là một (vài) token mới
```

## Bài tập tự làm
1. Chạy lại đoạn code "đặt tên quán cà phê" 5 lần, ghi lại 5 kết quả. Thử giải thích bằng ngôn ngữ của Ngày 1 (không dùng từ "sáng tạo" hay "hiểu") vì sao 5 kết quả có thể khác nhau.
2. Đặt một câu hỏi về một sự kiện/API bạn biết chắc xảy ra sau ngày cắt dữ liệu huấn luyện của model (tra ngày cắt dữ liệu chính thức trong tài liệu Anthropic mới nhất). Quan sát model trả lời thế nào — nó có báo "tôi không biết" hay tự tin bịa ra thông tin? Viết lại bằng ngôn ngữ kỹ thuật vì sao điều đó xảy ra (liên hệ mục "ngoài phạm vi kiến thức huấn luyện" ở trên).
3. Dùng streaming để in ra một câu trả lời dài (~300 token). Đo thời gian giữa lúc gọi API và lúc token đầu tiên xuất hiện (time-to-first-token) so với thời gian từ token đầu tới token cuối — hai khoảng thời gian này phản ánh hai giai đoạn khác nhau của inference (prefill vs decode), sẽ dùng lại ở Ngày 2 khi nói về latency.

## Đào sâu / nâng cao

### Prefill và decode — hai giai đoạn khác nhau của một request
Một lần gọi API thực chất chạy qua 2 giai đoạn có đặc tính hiệu năng khác nhau:
- **Prefill**: xử lý toàn bộ input (system + toàn bộ messages) trong một lần forward-pass song song — đây là lý do input dài không làm tăng latency theo cấp số nhân, chỉ tăng gần như tuyến tính và có thể tận dụng tối đa phần cứng song song.
- **Decode**: sinh output token-by-token, mỗi token là một forward-pass **tuần tự** riêng (không song song hoá được vì token N+1 cần token N làm input). Đây là lý do output dài luôn chậm hơn tuyến tính so với input dài tương đương, và là lý do các tính năng như "Fast Mode" (tăng tốc decode) tồn tại như một tính năng riêng biệt với việc giảm input.

Hiểu 2 giai đoạn này giải thích trực tiếp vì sao ở Ngày 2, chi phí và độ trễ của input token và output token được tính khác nhau và giá khác nhau (output luôn đắt hơn input, thường gấp 4-5 lần).

### Extended thinking / adaptive thinking không phải "một bộ não khác"
Các model Claude hiện đại có "thinking block" — nhìn giống như model "suy nghĩ" trước khi trả lời. Về cơ chế, đây **vẫn là next-token prediction**, chỉ khác là model được huấn luyện để sinh ra một chuỗi token trung gian (reasoning trace) trước khi sinh token của câu trả lời cuối, và chuỗi trung gian đó có thể cải thiện chất lượng câu trả lời cuối cùng — giống việc con người viết nháp trước khi viết bản chính. Adaptive thinking (`thinking: {"type": "adaptive"}`) để model tự quyết định độ dài chuỗi trung gian này dựa trên độ khó cảm nhận của câu hỏi, thay vì cấu hình cứng bằng `budget_tokens` (cách cũ, đã loại bỏ trên các model mới). Xem [Extended thinking overview](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) để hiểu cách chuỗi thinking này được tính token và tính phí — vẫn tính vào output token dù không phải câu trả lời cuối.

### Vì sao model không "biết" nó đang bịa
Không có tín hiệu nội tại đáng tin cậy nào trong quá trình sinh token báo cho model biết "tôi đang generalize sai" — xác suất token cao không đồng nghĩa với "nội dung đó đúng trong thực tế", nó chỉ có nghĩa "token này hợp lý về mặt ngôn ngữ/thống kê tại vị trí này". Nghiên cứu về calibration (mức độ "độ tự tin" của model có khớp với xác suất đúng thực tế hay không) là một hướng nghiên cứu riêng, và kết quả nói chung là các model hiện tại **chưa được calibrate tốt** — độ tự tin thể hiện qua văn phong không phải chỉ số đáng tin để đánh giá độ chính xác.

## Bài tập senior
1. Một đồng nghiệp junior đề xuất: "Set `temperature=0` cho toàn bộ pipeline production để đảm bảo output luôn giống nhau, dễ test và cache." Hãy chỉ ra 2 vấn đề với đề xuất này — một vấn đề về API hiện đại của Claude, một vấn đề về giả định "temperature=0 = deterministic" nói chung.
2. Thiết kế (ở mức mô tả, không cần code) một cơ chế phát hiện khả năng hallucination ở tầng ứng dụng cho một chatbot hỏi-đáp dựa trên tài liệu nội bộ công ty (không dùng RAG — model trả lời từ kiến thức tham số). Bạn sẽ dựa vào tín hiệu nào để gắn cờ "câu trả lời này có rủi ro cao là bịa", biết rằng bạn không có quyền truy cập vào logit/xác suất nội bộ của model qua API thông thường?
3. Review đoạn mô tả sau trong một tài liệu kỹ thuật nội bộ giả định: *"Model của chúng ta hiểu ngữ cảnh nghiệp vụ chứng khoán rất tốt nên có thể tự đưa ra khuyến nghị mua/bán mà không cần review."* Chỉ ra chỗ sai về mặt kỹ thuật trong câu này (liên hệ khái niệm "hiểu" ở mục Khái niệm cốt lõi), và giải thích vì sao — kể cả khi bỏ qua yếu tố tuân thủ pháp lý — đây là rủi ro kỹ thuật thực sự chứ không chỉ là vấn đề diễn đạt.

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được autoregressive generation bằng lời của mình, không copy định nghĩa.
- [ ] Biết vì sao "AI hiểu câu hỏi" là cách nói không chính xác về mặt kỹ thuật, và có thể diễn đạt lại đúng hơn.
- [ ] Phân biệt được vai trò của temperature/top-p/top-k, biết model Claude thế hệ mới không nhận các tham số này.
- [ ] Nêu được ít nhất 3 nguồn gốc kỹ thuật của hallucination, không chỉ nói "AI đôi khi sai".
- [ ] Chạy được ví dụ streaming và hiểu vì sao token xuất hiện tuần tự chứ không phải cùng lúc.
