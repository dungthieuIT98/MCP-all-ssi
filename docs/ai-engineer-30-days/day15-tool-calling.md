# Phần 15 — Tool-calling: LLM chọn hàm thế nào, và vì sao chọn sai

## Mục tiêu hôm nay
Hiểu tool-calling ở mức cơ chế thật (không phải "AI biết gọi API") và nắm được pattern thực thi chuẩn: model đề xuất, code thực thi, không bao giờ ngược lại.

## Đọc trước
- [Anthropic — Tool use (function calling)](https://docs.anthropic.com/)
- [OpenAI — Function calling](https://platform.openai.com/docs/)
- Google AI — Gemini function calling (tìm trong tài liệu Gemini API, phần "Function calling")
- Paper: "ReAct: Synergizing Reasoning and Acting in Language Models" (arxiv.org, Yao et al.) — nền tảng lý thuyết cho việc model "quyết định hành động" sẽ dùng ở Phần 17, nhưng cơ chế sinh tool call ở ngày này là tiền đề bắt buộc phải hiểu trước.

## Khái niệm cốt lõi

### Tool-calling không phải "model chạy code"
Model không bao giờ thực thi bất cứ thứ gì. Tool-calling là: model được **train** (fine-tune) để, khi thấy một danh sách tool schema trong context, có thể sinh ra một **cấu trúc output đặc biệt** (không phải văn bản tự nhiên) mô tả "tôi muốn gọi hàm X với tham số Y" — thay vì trả lời trực tiếp bằng text. Cấu trúc này thường là JSON (tên hàm + object tham số khớp schema). Sau đó, **code của bạn** (client, không phải model) đọc cấu trúc đó, thực thi hàm thật (gọi DB, gọi REST API, đọc file...), rồi gửi **kết quả thực thi** trở lại model như một message mới. Model tiếp tục sinh token dựa trên kết quả đó — có thể trả lời luôn, hoặc gọi tiếp tool khác.

Ba điểm hay bị hiểu lầm:
1. **Tool schema là một phần của input, không phải cấu hình ẩn.** Khi bạn "đăng ký" tool cho Claude hoặc GPT, thực chất bạn đang nhúng thêm một khối mô tả (tên tool, description, JSON Schema của input) vào system prompt/context mà model nhìn thấy ở mọi lượt gọi. Model không "biết" tool tồn tại theo cách gì khác ngoài việc đọc mô tả này trong cùng context window như phần còn lại của cuộc hội thoại — không có kênh riêng, không có bộ nhớ ngoài context.
2. **Việc "chọn tool" là một bài toán sinh token có điều kiện**, giống hệt việc model chọn từ tiếp theo trong câu — chỉ khác là được ràng buộc (constrained decoding ở nhiều implementation) để output khớp JSON Schema đã khai báo. Đây là lý do model đôi khi sinh ra tham số sai kiểu, thiếu field bắt buộc, hoặc "ảo tưởng" ra một tool không tồn tại nếu prompt không đủ rõ.
3. **Không có gọi hàm "trong lúc" model đang sinh token.** Toàn bộ turn của model dừng lại ngay khi nó sinh xong tool call (`stop_reason: tool_use` ở Anthropic, `finish_reason: tool_calls` ở OpenAI). Code của bạn thực thi tool đó, rồi phải chủ động gửi một request **mới** chứa kết quả để model tiếp tục. Nếu bạn không gửi lại, model không bao giờ biết tool đã chạy — nó chỉ "treo" ở trạng thái chờ.

### Pattern thực thi chuẩn (đúng cho mọi provider)
```
1. Gửi request kèm: system prompt + lịch sử hội thoại + tool schema list
2. Model trả về: text (nếu không cần tool) HOẶC tool_use block (tên tool + input)
3. Nếu là tool_use:
   a. Code validate input theo schema thật (không tin schema model tự nghĩ ra)
   b. Code thực thi tool (gọi hàm Python, REST API, query DB...)
   c. Code gửi lại kết quả dưới dạng "tool_result" gắn với đúng tool_use_id
   d. Quay lại bước 1 với lịch sử đã nối thêm tool_use + tool_result
4. Lặp tới khi model trả text thuần (không còn tool_use) hoặc đạt điều kiện dừng (Phần 17)
```
Không có bước nào trong đó model "tự chạy" tool. Đây là ranh giới an toàn quan trọng nhất của toàn bộ kiến trúc agent: **model chỉ đề xuất, code quyết định thực thi hay không** — chỗ này chính là nơi bạn áp least-privilege và validation (liên hệ Phần 20).

### Vì sao model chọn sai tool
- **Schema mơ hồ**: field không ghi rõ đơn vị, format, hoặc range hợp lệ (`"date": "start date"` không nói format `YYYY-MM-DD` hay timestamp) khiến model đoán bừa.
- **Tên/description tool không phân biệt được với tool khác**: hai tool `get_user` và `get_user_info` với description gần giống nhau — model chọn ngẫu nhiên hoặc chọn nhầm theo tên gần giống nhất về mặt embedding/token, không theo ngữ nghĩa bạn muốn.
- **Quá nhiều tool cùng lúc (tool overload)**: mỗi tool schema chiếm context, và khi số tool tăng (hàng chục, hàng trăm), khả năng model chọn đúng giảm — tương tự "lost in the middle" của context dài. Thực nghiệm chung của ngành: quá 15-20 tool active cùng lúc, tỷ lệ chọn sai tăng rõ rệt trừ khi model rất mạnh hoặc tool được nhóm/lọc theo ngữ cảnh trước khi đưa vào prompt.
- **Chức năng chồng lấp**: `search_docs` và `search_knowledge_base` cùng làm một việc dưới tên khác — model không có cách nào biết cái nào "đúng hơn" nếu description không nói rõ sự khác biệt (phạm vi dữ liệu, độ mới, chi phí).
- **Description viết cho người đọc, không viết cho model**: mô tả kiểu "Retrieves data" không cho model đủ tín hiệu để phân biệt khi nào dùng — description tốt phải nói rõ **khi nào dùng, khi nào KHÔNG dùng**, ví dụ kiểu input mong đợi và ví dụ cụ thể.

## Đối chiếu với code thật trong repo
Repo `mcp-superset` là một ví dụ cụ thể của tool-calling triển khai qua MCP (chi tiết giao thức ở Phần 16). Xem [`tools/chart.py`](../../tools/chart.py) dòng 20-35, hàm `superset_chart_list`: type hint Python (`Optional[str]`, `Optional[int]`) và docstring được framework FastMCP (thư viện `mcp`) tự chuyển thành JSON Schema mà model nhìn thấy — đúng cơ chế "tool schema nhúng vào context" nói ở trên, chỉ khác chỗ sinh schema là tự động từ code thay vì viết tay JSON. Docstring dòng 29-34 giải thích rõ `name_contains` lọc thế nào, `order_column` nhận giá trị gì — đây chính là kiểu description "viết cho model hiểu", tránh lỗi mơ hồ đã nêu trên.

## Thực hành
Cài `pip install anthropic` (dùng API key cá nhân/free tier khi tự học, không dùng key thật của SSI — xem lưu ý ở README). Ví dụ tool-calling tối giản với Anthropic SDK, có một tool "dễ gây chọn sai" để quan sát hành vi:

```python
import json
from anthropic import Anthropic

client = Anthropic()  # đọc ANTHROPIC_API_KEY từ env

# Hai tool có chức năng CHỒNG LẤP có chủ đích, để quan sát model chọn thế nào
tools = [
    {
        "name": "get_weather_now",
        "description": (
            "Lấy thời tiết HIỆN TẠI (real-time) cho một thành phố. "
            "Chỉ dùng khi câu hỏi hỏi về thời điểm HIỆN TẠI, không dùng cho dự báo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Tên thành phố, ví dụ 'Ha Noi'"},
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": (
            "Lấy DỰ BÁO thời tiết N ngày tới cho một thành phố. "
            "Dùng khi câu hỏi có từ khoá 'ngày mai', 'tuần tới', hoặc số ngày cụ thể."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "days": {"type": "integer", "description": "Số ngày dự báo, 1-7"},
            },
            "required": ["city", "days"],
        },
    },
]


def execute_tool(name: str, tool_input: dict) -> dict:
    """Đây là nơi code thật thực thi — model không bao giờ chạy tới đây."""
    if name == "get_weather_now":
        return {"city": tool_input["city"], "temp_c": 31, "condition": "nắng"}
    if name == "get_weather_forecast":
        return {"city": tool_input["city"], "days": tool_input["days"], "forecast": "mưa rào rải rác"}
    return {"error": f"unknown tool {name}"}


def run(user_message: str):
    messages = [{"role": "user", "content": user_message}]

    while True:
        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            tools=tools,
            messages=messages,
        )

        # Model dừng vì cần gọi tool
        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                print(f"[model chọn tool] {block.name} input={block.input}")
                # Bước validate input trước khi thực thi — KHÔNG tin schema mù quáng
                result = execute_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )
            messages.append({"role": "user", "content": tool_results})
            continue  # quay lại gọi model tiếp với kết quả tool

        # Model trả lời text thuần -> dừng loop
        for block in response.content:
            if block.type == "text":
                print("[model trả lời]", block.text)
        return


if __name__ == "__main__":
    run("Ha Noi ngày mai có mưa không?")
    run("Ha Noi bây giờ nhiệt độ bao nhiêu?")
```

Chạy thử với câu hỏi mơ hồ (ví dụ "Ha Noi thế nào?") để quan sát model chọn tool nào — đây chính là cách thực nghiệm vấn đề "chọn sai tool" thay vì chỉ đọc lý thuyết.

## Bài tập tự làm
1. Sửa `description` của `get_weather_forecast` thành một câu chung chung ("Get weather info for a city") — không còn phân biệt với `get_weather_now`. Chạy lại 5 câu hỏi khác nhau, ghi lại model chọn sai bao nhiêu lần so với bản description rõ ràng.
2. Thêm tool thứ ba trùng chức năng hoàn toàn với `get_weather_now` (tên khác, description khác chút) để mô phỏng "tool chồng lấp" — quan sát model có nhất quán chọn 1 tool hay chọn ngẫu nhiên giữa 2 lượt gọi giống nhau.
3. Viết một tool có `input_schema` với field `date` không ghi rõ format — thử prompt để model tự điền ngày, in ra để xem model điền theo format gì (ISO 8601? `DD/MM/YYYY`? phụ thuộc ngôn ngữ câu hỏi?).
4. Đo: gọi cùng 1 câu hỏi 5 lần với `temperature=0` và 5 lần với `temperature=1` (nếu SDK cho phép chỉnh) — so sánh độ ổn định của việc chọn tool.

## Đào sâu / nâng cao

### Parallel tool calls
Nhiều model (Claude, GPT từ các phiên bản gần đây) có thể trả về **nhiều tool_use block trong cùng 1 response** nếu xác định các tool call độc lập nhau (ví dụ: lấy thời tiết 3 thành phố cùng lúc). Code của bạn phải thực thi tất cả và trả về tool_result cho từng `tool_use_id` tương ứng trong đúng 1 message tiếp theo — không phải tách thành nhiều round-trip. Bỏ sót 1 `tool_result` sẽ làm request kế tiếp bị lỗi vì thiếu phản hồi cho 1 tool_use_id đã gửi.

### Forced tool choice
Cả Anthropic và OpenAI cho phép ép model phải gọi 1 tool cụ thể (`tool_choice={"type": "tool", "name": "..."}` ở Anthropic) thay vì để model tự quyết có cần tool hay không. Dùng khi bạn chắc chắn output phải theo 1 cấu trúc cụ thể (gần với structured output ở Phần 4) — nhưng lạm dụng sẽ làm mất khả năng model tự nhận ra "câu hỏi này không cần tool nào cả".

### Chi phí token của tool schema
Mỗi tool schema gửi trong request tốn token ở input, **mỗi lượt gọi**, kể cả khi model không dùng tool nào — vì schema nằm trong context mà model phải "đọc" để quyết định. Nhiều tool = context dài hơn = cost cao hơn + latency cao hơn ở input processing, không chỉ ảnh hưởng độ chính xác chọn tool. Đây liên hệ trực tiếp tới Phần 24 (cost engineering) — một lý do thực dụng để không nhồi tool "phòng khi cần".

### Vòng lặp validate trước khi thực thi
Không bao giờ thực thi trực tiếp input mà model sinh ra nếu tool đó có side-effect thật (viết DB, gọi API ghi dữ liệu, xoá file). Luôn có một lớp validate độc lập (ví dụ Pydantic model, hoặc kiểm tra range/enum tay) giữa "model đề xuất" và "code thực thi" — vì model có thể sinh input hợp lệ theo JSON Schema nhưng vô nghĩa về business logic (ví dụ `page_size=-1`, `chart_id=0`).

## Bài tập senior
Bạn review code của một dev junior: họ định nghĩa 40 tool trong 1 agent trả lời câu hỏi nội bộ (HR, IT helpdesk, tài chính) — tất cả tool active trong mọi lượt gọi, không phân nhóm. Model liên tục chọn sai tool giữa các domain khác nhau (ví dụ hỏi về ngày nghỉ nhưng gọi tool tra cứu ticket IT). Bạn sẽ đề xuất thay đổi gì? Cân nhắc: có nên tách theo domain và chỉ nạp tool liên quan theo intent trước (yêu cầu 1 bước phân loại trước khi gọi model chính), hay giữ 1 model duy nhất nhưng viết lại description; đánh giá trade-off latency (thêm 1 bước phân loại = thêm 1 lần gọi model) so với độ chính xác.

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được vì sao model "không chạy" tool, chỉ sinh cấu trúc đề xuất.
- [ ] Viết được 1 vòng lặp tool-use hoàn chỉnh (gửi tool schema → nhận tool_use → thực thi → gửi tool_result → nhận câu trả lời) không copy mẫu.
- [ ] Nêu được ít nhất 3 nguyên nhân khiến model chọn sai tool và cách giảm mỗi loại.
- [ ] Biết phân biệt schema tool "viết cho người" và "viết cho model".
