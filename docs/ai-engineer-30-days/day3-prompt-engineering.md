# Phần 3 — Prompt engineering có hệ thống

## Mục tiêu hôm nay
Học prompt engineering như một kỹ thuật có thể đo lường, review, version control — không phải "thử vài câu tới khi ra kết quả đẹp". Đây là kỹ năng senior thật sự phân biệt với mức "gọi API là xong": biết vì sao một prompt hoạt động, không chỉ biết nó hoạt động.

## Đọc trước
- [Anthropic — Prompt engineering overview](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Anthropic — Use examples (multishot prompting)](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/multishot-prompting)
- [Anthropic — Let Claude think (chain of thought)](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/chain-of-thought)
- [Anthropic — Give Claude a role (system prompts)](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/system-prompts)

## Khái niệm cốt lõi

### Vì sao prompt engineering là kỹ thuật thật, không phải may rủi
Lý do prompt engineering có vẻ giống "thử và cầu nguyện" với người mới: không có compiler báo lỗi, không có type system, kết quả có tính ngẫu nhiên (Phần 1 — sampling). Nhưng bản chất nó vẫn là kỹ thuật có nguyên lý, vì hai lẽ:

1. **Model được huấn luyện để bám theo pattern trong dữ liệu huấn luyện, và pattern đó có cấu trúc dự đoán được.** Ví dụ: khi bạn cho model vài ví dụ input→output theo một format cụ thể (few-shot), model có xu hướng mạnh để tiếp tục đúng format đó — đây không phải "trực giác AI", mà là next-token prediction đang bám theo pattern rõ ràng nhất trong context vừa cho, và pattern rõ ràng nhất chính là các ví dụ bạn vừa đưa.
2. **Có thể đo lường và lặp lại.** Một prompt tốt hơn prompt khác không phải vì "cảm thấy đúng hơn" — mà vì nó cho ra kết quả đúng nhiều hơn trên một bộ test case cụ thể (eval set), đo được bằng số. Nếu bạn không đo, bạn không biết prompt A tốt hơn prompt B hay chỉ là bạn thấy vài ví dụ đẹp rồi kết luận vội.

Điểm khác biệt giữa dev "gọi API là xong" và senior: người gọi API là xong viết một câu prompt, thấy chạy được, deploy. Senior viết prompt, viết bộ test case đại diện cho các trường hợp thực tế (bao gồm edge case), đo tỷ lệ đúng, sửa prompt dựa trên lỗi cụ thể quan sát được, và **version control prompt như version control code** — vì một thay đổi nhỏ trong câu chữ có thể làm hành vi model thay đổi đáng kể, và bạn cần rollback được khi phát hiện regression.

### Few-shot prompting — dạy bằng ví dụ, không dạy bằng mô tả
Few-shot (hay multishot) là kỹ thuật đưa vài ví dụ input→output mẫu vào prompt trước khi đưa input thật cần xử lý. Nó hiệu quả hơn việc chỉ mô tả bằng lời ("hãy trả lời ngắn gọn, theo định dạng JSON") vì hai lý do kỹ thuật:

- **Ví dụ loại bỏ sự mơ hồ ngôn ngữ.** "Trả lời ngắn gọn" có thể hiểu là 1 câu hay 3 câu — một ví dụ cụ thể xoá bỏ hoàn toàn sự mơ hồ đó vì nó cho model thấy chính xác độ dài/định dạng kỳ vọng.
- **Ví dụ là tín hiệu mạnh hơn mô tả trong không gian next-token prediction.** Model có xu hướng "bắt chước" format của những gì vừa xuất hiện gần nhất trong context nhiều hơn là suy luận từ một câu mô tả trừu tượng — điều này khớp với cách model được huấn luyện: học từ pattern lặp lại trong dữ liệu, không phải học từ định nghĩa hình thức.

Số lượng ví dụ cần: không có số cố định, nhưng nguyên tắc là **ví dụ phải đa dạng và bao gồm edge case**, không chỉ lặp lại một dạng dễ. 3 ví dụ đều là câu hỏi đơn giản sẽ không dạy model xử lý câu hỏi phức tạp/mơ hồ — model chỉ học được pattern có trong ví dụ, không tự suy ra pattern không xuất hiện.

### Chain-of-thought (CoT) — vì sao "hãy suy nghĩ từng bước" từng có tác dụng
Chain-of-thought là kỹ thuật yêu cầu model viết ra các bước suy luận trung gian trước khi đưa ra câu trả lời cuối, thay vì nhảy thẳng tới kết luận. Cơ chế vì sao nó hoạt động (đúng theo Phần 1): mỗi token model sinh ra trở thành một phần của context cho token tiếp theo — nếu model "viết ra" bước suy luận trung gian đúng, các token sau đó được sinh ra **có điều kiện** trên bước suy luận đúng đó, làm tăng khả năng kết luận cuối cũng đúng. Ngược lại, nếu bắt model nhảy thẳng tới kết luận, nó phải "nhắm" đúng ngay trong một bước sinh token, không có cơ hội tự sửa giữa đường.

Điểm quan trọng cho 2026: trên các model Claude hiện đại có **extended/adaptive thinking native** (Sonnet 4.6 trở lên, dòng Opus 4.6+), việc viết `<thinking>` hoặc yêu cầu "suy nghĩ từng bước" trong prompt phần lớn là dư thừa — model đã được huấn luyện để tự quyết định khi nào cần suy luận sâu, và cấu hình `thinking: {"type": "adaptive"}` kiểm soát điều này ở tầng API, không phải ở tầng prompt text. Yêu cầu CoT bằng prompt text vẫn có tác dụng trên các model không có thinking hoặc khi thinking bị tắt, nhưng trên model có adaptive thinking, thêm câu "suy nghĩ từng bước" vào prompt là dấu hiệu của prompt viết cho model cũ, không phải best practice hiện tại.

### Role prompting — system prompt định hình hành vi, không phải "diễn vai"
Đặt vai trò cho model qua system prompt (`"Bạn là một chuyên gia phân tích tài chính..."`) không phải để model "nhập vai" theo nghĩa kịch — nó là cách thu hẹp không gian phân phối xác suất mà model sample từ đó. Khi được gán vai "chuyên gia phân tích tài chính", model có xu hướng sinh ra từ vựng, cấu trúc câu, mức độ chi tiết gần với văn bản chuyên gia tài chính trong dữ liệu huấn luyện — vì đó là pattern có xác suất cao nhất khớp với vai trò đó.

Role prompting hiệu quả nhất khi kết hợp với **ràng buộc cụ thể**, không chỉ là danh xưng: "Bạn là chuyên gia phân tích tài chính, luôn trình bày số liệu kèm đơn vị, không đưa ra khuyến nghị mua/bán cụ thể" mạnh hơn nhiều so với chỉ "Bạn là chuyên gia phân tích tài chính". Danh xưng đơn thuần dễ bị model "quên" khi context dài ra qua nhiều lượt hội thoại — ràng buộc hành vi cụ thể giữ được lâu hơn nếu được nhắc lại đúng lúc (xem Phần 5 về system prompt design chi tiết hơn).

### Prompt template có version control — vì sao bắt buộc ở mức senior
Một prompt production không nên là string hardcode rải rác trong code. Lý do kỹ thuật, không phải chỉ "cho gọn":

1. **Prompt là logic nghiệp vụ, không phải string tiện ích.** Thay đổi một câu trong system prompt có thể thay đổi hành vi model đáng kể (Phần 5 sẽ có ví dụ cụ thể về injection/guardrail bị vô hiệu vì sửa một chữ). Logic nghiệp vụ luôn cần review, test, rollback — prompt cũng vậy.
2. **Cần đo A/B giữa các phiên bản.** Không version control thì không thể so sánh "prompt v2 có tốt hơn v1 không" một cách có kỷ luật — bạn sẽ chỉ nhớ mù mờ "hình như bản cũ tốt hơn" mà không chứng minh được.
3. **Cần tách biệt prompt theo model.** Một prompt viết tối ưu cho Opus 4.6 (model theo sát chỉ dẫn rất nghiêm) có thể hoạt động khác trên Sonnet 4.6 hoặc khi nâng cấp lên Opus 5 (model có xu hướng hành vi khác — dài dòng hơn, tự kiểm chứng nhiều hơn, theo tài liệu migration của Anthropic). Version control cho phép giữ nhiều biến thể prompt tương ứng với model, và biết chính xác biến thể nào đang chạy ở production.

Cách làm thực dụng ở mức tối thiểu (không cần công cụ phức tạp): lưu prompt trong file riêng (`.txt`/`.md`/`.j2` template), commit vào git cùng code, đặt tên file có version (`system_prompt_v3.md`) hoặc dùng git history làm version, và **log lại prompt version nào được dùng cho mỗi request** trong hệ thống production (không chỉ log input/output, log cả prompt version) để debug được khi có regression.

## Đối chiếu với code thật trong repo
Trong `mcp-superset`, mỗi tool được đăng ký bằng decorator `@mcp.tool()` (kết hợp `@requires_auth` và `@handle_api_errors`, xem `utils/decorators.py`) trong các file như `tools/chart.py`, `tools/dashboard.py`. **Docstring của mỗi tool chính là một system prompt engineering thật** — không phải ẩn dụ. Khi AI assistant (Claude) quyết định có nên gọi `superset_chart_list` hay không, và điền tham số gì, nó chỉ dựa vào: tên tool, docstring, và JSON schema tham số được sinh tự động từ type hint Python (chi tiết cơ chế sinh schema này sẽ nói kỹ ở Phần 4). Một docstring mơ hồ ("Lấy chart") sẽ khiến model gọi sai hoặc gọi thiếu điều kiện lọc — đúng như "few-shot mơ hồ" gây kết quả mơ hồ ở mục Khái niệm cốt lõi. Một docstring tốt nêu rõ **khi nào nên gọi tool này** (không chỉ tool làm gì), tương tự nguyên tắc "role prompting cần ràng buộc cụ thể, không chỉ danh xưng" — ví dụ nói rõ "gọi tool này khi người dùng hỏi về danh sách chart hiện có, có thể lọc theo dashboard_id hoặc tên" thay vì chỉ "Lấy danh sách chart". Đây chính xác là nguyên tắc mà Phần 4 sẽ đào sâu tiếp khi nói về structured output và function calling schema.

## Thực hành
```bash
pip install anthropic
```

```python
import anthropic

client = anthropic.Anthropic()

# Zero-shot: chỉ mô tả bằng lời, không có ví dụ — dễ ra kết quả không
# đồng nhất về định dạng giữa các lần gọi khác nhau.
zero_shot_prompt = """Phân loại cảm xúc của câu sau: tích cực, tiêu cực, hoặc trung tính.
Câu: "Dịch vụ chăm sóc khách hàng phản hồi chậm nhưng nhân viên rất nhiệt tình."
"""

# Few-shot: cho ví dụ cụ thể để cố định định dạng output — model bám
# theo pattern của ví dụ thay vì tự suy diễn định dạng.
few_shot_prompt = """Phân loại cảm xúc của câu, CHỈ trả về đúng 1 từ: tích cực, tiêu cực, hoặc trung tính.

Câu: "Sản phẩm giao đúng hẹn, đóng gói cẩn thận."
Cảm xúc: tích cực

Câu: "Giá cao hơn so với đối thủ, sẽ không mua lại."
Cảm xúc: tiêu cực

Câu: "Dịch vụ chăm sóc khách hàng phản hồi chậm nhưng nhân viên rất nhiệt tình."
Cảm xúc:"""

for label, prompt in [("Zero-shot", zero_shot_prompt), ("Few-shot", few_shot_prompt)]:
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    print(f"{label}: {text.strip()!r}")

# Quan sát: few-shot thường trả về CHÍNH XÁC 1 từ đúng định dạng ví dụ,
# zero-shot có thể trả về câu giải thích dài hơn dù đã yêu cầu ngắn gọn —
# vì không có ví dụ cụ thể để model bám theo.
```

```python
# Minh hoạ prompt template có version, tách khỏi code — cách làm tối thiểu
# để bắt đầu version control prompt mà không cần công cụ phức tạp.
from pathlib import Path

def load_prompt(name: str, version: str) -> str:
    """Load prompt template từ file, theo version — cho phép rollback
    và A/B test bằng cách chỉ đổi tham số version, không sửa code logic."""
    path = Path(f"prompts/{name}_{version}.md")
    return path.read_text(encoding="utf-8")

# Ví dụ dùng — giả sử đã có file prompts/classify_sentiment_v2.md
# system_prompt = load_prompt("classify_sentiment", "v2")
# response = client.messages.create(
#     model="claude-opus-5",
#     system=system_prompt,
#     max_tokens=20,
#     messages=[{"role": "user", "content": "..."}],
# )
# Log lại version đã dùng cùng request_id để debug sau này:
# logger.info("llm_call", extra={"prompt_name": "classify_sentiment",
#                                  "prompt_version": "v2",
#                                  "request_id": response._request_id})
```

## Bài tập tự làm
1. Viết 2 phiên bản prompt cho cùng một tác vụ trích xuất thông tin (ví dụ: trích tên công ty + mã cổ phiếu từ một đoạn tin tức) — bản 1 chỉ mô tả bằng lời, bản 2 dùng few-shot với 3 ví dụ. Chạy cả hai trên 5 đoạn tin tức khác nhau, so sánh tỷ lệ đúng định dạng output.

bạn là AI phân tích thông tin,  từ đoạn nội dung này hãy trích xuất thông tin và mã cổ phiếu cho tôi : <văn bản >

-bạn là AI phân tích thông tin,  từ đoạn nội dung này hãy trích xuất thông tin và mã cổ phiếu cho tôi : 
ví dụ : 
văn bản 1 => công ty ssi mã cổ phiếu là ssi 

<văn bản >
2. Tạo một thư mục `prompts/` trong project cá nhân, viết 1 system prompt, commit vào git. Sửa prompt đó, commit lần 2 với message rõ ràng nêu lý do sửa (không chỉ "update prompt"). Dùng `git log` để xem lại lịch sử — đây là bài tập tối thiểu để tập quen version control prompt.
3. Viết một system prompt có role cụ thể + ràng buộc hành vi rõ ràng (không chỉ danh xưng) cho một trợ lý trả lời câu hỏi nội bộ về quy trình công ty. So sánh với một system prompt chỉ có danh xưng ("Bạn là trợ lý nội bộ"), chạy cùng 3 câu hỏi giống nhau ở cả hai, nhận xét sự khác biệt về mức độ tuân theo ràng buộc.

## Đào sâu / nâng cao

### XML tag để phân định cấu trúc prompt
Claude được huấn luyện để nhận diện tốt các thẻ dạng XML (`<document>`, `<instructions>`, `<example>`) như một cách phân định rõ ràng ranh giới giữa các phần khác nhau trong một prompt dài. Điều này khác với việc chỉ dùng markdown heading hoặc xuống dòng — thẻ XML cho model một tín hiệu cấu trúc mạnh hơn để phân biệt "đây là tài liệu cần phân tích" với "đây là chỉ dẫn cách phân tích", tránh model nhầm lẫn giữa nội dung và chỉ dẫn (một nguồn gây prompt injection sẽ nói ở Phần 5). Đọc thêm: [Anthropic — Use XML tags to structure your prompts](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags).

### Prompt engineering vs fine-tuning — khi nào prompt không còn đủ
Prompt engineering có giới hạn: nó điều khiển hành vi model tại **thời điểm inference**, không thay đổi trọng số model. Với các tác vụ đòi hỏi kiến thức chuyên sâu không có trong dữ liệu huấn luyện gốc (thuật ngữ nội bộ công ty cực kỳ đặc thù, format output rất lạ so với dữ liệu huấn luyện), có 3 lựa chọn theo thứ tự chi phí/độ phức tạp tăng dần: (1) prompt engineering + few-shot, (2) RAG — cung cấp kiến thức ngoài qua context tại runtime, (3) fine-tuning — huấn luyện lại một phần trọng số model. Ở mức senior, câu hỏi cần trả lời trước khi nhảy sang fine-tuning là: "vấn đề này có giải quyết được bằng prompt + RAG không?" — phần lớn trường hợp thực tế câu trả lời là có, và fine-tuning tốn kém, khó version control, khó rollback hơn hẳn so với sửa một file prompt.

### Đánh giá prompt bằng eval set — bước senior thường bỏ qua
Viết prompt xong, chạy thử 2-3 câu thấy "được" rồi deploy là cách làm không senior — vì mẫu 2-3 câu không đại diện cho phân phối input thật ở production. Cách làm đúng: xây một **eval set** — tập hợp các input đại diện (bao gồm case dễ, case khó, case biên/edge case, case cố ý gây nhiễu) kèm kết quả kỳ vọng hoặc tiêu chí đánh giá, rồi chạy prompt qua toàn bộ eval set mỗi khi thay đổi, đo tỷ lệ đạt. Đây là nguyên tắc test-driven áp dụng cho prompt — không cần công cụ phức tạp để bắt đầu, một file JSON chứa list `{"input": ..., "expected": ...}` và một script Python lặp qua để so sánh là đủ ở quy mô nhỏ.

## Bài tập senior
1. Review đoạn prompt sau (dùng trong một tool phân loại yêu cầu hỗ trợ khách hàng) và chỉ ra ít nhất 3 vấn đề kỹ thuật (không phải vấn đề chính tả):
   > "Bạn là AI thông minh nhất, hãy luôn cố gắng hết sức trả lời đúng, đừng bao giờ sai. Phân loại yêu cầu sau vào 1 trong các loại: kỹ thuật, thanh toán, khác. Nếu không chắc thì đoán loại nào có vẻ hợp lý nhất."
2. Một prompt production đã chạy ổn định 6 tháng bỗng bắt đầu cho kết quả khác lạ sau khi team nâng cấp từ Sonnet 4.6 lên Sonnet 5 (không sửa gì trong prompt). Liệt kê ít nhất 3 hướng điều tra bạn sẽ làm theo thứ tự ưu tiên, dựa trên hiểu biết rằng các model khác nhau có thể phản ứng khác nhau với cùng một prompt (gợi ý: liên hệ khái niệm "model theo sát chỉ dẫn nghiêm hơn/khác hơn" đã nêu ở mục Prompt template).
3. Thiết kế (mô tả, không cần code đầy đủ) một quy trình CI tối thiểu để mỗi lần có Pull Request sửa file prompt trong repo, hệ thống tự động chạy eval set và báo cáo tỷ lệ đạt trước/sau thay đổi, chặn merge nếu tỷ lệ đạt giảm quá X%. Nêu rõ bạn sẽ đo "đạt" bằng tiêu chí gì cho một tác vụ sinh văn bản tự do (không có đáp án đúng duy nhất, khác với bài toán phân loại có nhãn rõ).

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được vì sao few-shot hiệu quả hơn zero-shot dựa trên cơ chế next-token prediction, không chỉ nói "vì có ví dụ".
- [ ] Biết khi nào chain-of-thought bằng prompt text còn cần thiết và khi nào adaptive thinking đã thay thế nó.
- [ ] Viết được một system prompt có role + ràng buộc hành vi cụ thể, không chỉ danh xưng.
- [ ] Có ít nhất một prompt được lưu file riêng, commit git, có lịch sử thay đổi rõ ràng.
- [ ] Hiểu được vì sao đánh giá prompt cần eval set, không chỉ thử vài câu bằng mắt.
