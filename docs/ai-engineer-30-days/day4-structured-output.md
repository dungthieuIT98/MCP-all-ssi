# Ngày 4 — Structured output & function calling schema

## Mục tiêu hôm nay
Hiểu cách ép model trả về dữ liệu có cấu trúc đáng tin cậy (JSON đúng schema) và cách model quyết định gọi tool nào với tham số gì — đây là nền tảng bắt buộc để build bất kỳ hệ thống agent/tool-calling thật, bao gồm chính kiến trúc MCP server mà repo này implement.

## Đọc trước
- [Anthropic — Structured outputs](https://docs.anthropic.com/en/docs/build-with-claude/structured-outputs)
- [Anthropic — Tool use overview](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [Anthropic — Implement tool use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use)
- [JSON Schema — chuẩn định dạng schema dùng chung](https://json-schema.org/understanding-json-schema)

## Khái niệm cốt lõi

### Vì sao cần structured output — vấn đề thật, không phải tiện lợi
Model sinh văn bản tự do (free-form text) theo bản chất — Ngày 1 đã nói model chỉ là next-token prediction trên vocabulary. Khi ứng dụng của bạn cần **parse** output đó thành dữ liệu có cấu trúc (JSON để lưu DB, gọi tiếp API khác, hiển thị lên UI dạng bảng), bạn đang cố ép một quá trình sinh xác suất tự do vào một khuôn cứng — và đây là nguồn lỗi runtime rất thật: model có thể trả về JSON thiếu dấu ngoặc, thêm giải thích trước/sau JSON, đổi tên field, hoặc trả đúng cấu trúc nhưng sai kiểu dữ liệu (trả string cho field kỳ vọng number).

Có 3 tầng giải pháp, từ yếu tới mạnh:

1. **Prompt-only ("hãy trả về JSON")** — yếu nhất, không có gì đảm bảo. Model đôi khi vẫn thêm câu mở đầu kiểu "Đây là JSON bạn cần:" trước khi in JSON, làm parse thất bại nếu code chỉ `json.loads()` thẳng vào response text.
2. **JSON mode / `output_config.format` (structured outputs ở tầng API)** — API ràng buộc quá trình sinh token của model để đảm bảo output khớp một JSON Schema bạn cung cấp. Đây không phải "prompt khéo hơn" — là một ràng buộc kỹ thuật ở tầng sinh token, mạnh hơn hẳn prompt-only.
3. **Tool/function calling với `strict: true`** — khi mục tiêu không chỉ là "trả JSON" mà là "gọi một hành động cụ thể với tham số cụ thể", dùng tool schema thay vì chỉ ép format JSON tự do.

Với hệ thống MCP như repo này, tầng số 3 chính là cơ chế lõi: mỗi tool được định nghĩa bằng một JSON Schema (tự sinh từ type hint Python, xem mục Đối chiếu bên dưới), và khi model quyết định gọi tool, nó phải sinh ra `tool_use.input` khớp đúng schema đó.

### Function calling / tool schema hoạt động thế nào
Khi bạn gửi request kèm `tools=[...]`, mỗi tool định nghĩa: `name`, `description`, và `input_schema` (một JSON Schema mô tả các tham số). Model không "gọi hàm" thật — nó chỉ **sinh ra một content block đặc biệt** (`tool_use`) chứa tên tool và một object JSON làm tham số, dựa trên next-token prediction có điều kiện trên toàn bộ `tools` definition đã cho trong context. Code của bạn mới là nơi thực thi hành động thật — nhận `tool_use` block, chạy hàm tương ứng, rồi gửi kết quả trở lại model qua một `tool_result` block ở lượt tiếp theo.

Vì bản chất vẫn là sinh token, **model có thể sinh sai** — chọn sai tool, điền thiếu tham số bắt buộc, điền tham số sai kiểu. Cờ `strict: true` trên tool definition là cách ràng buộc cứng ở tầng API để đảm bảo `tool_use.input` luôn khớp chính xác schema (yêu cầu schema phải có `additionalProperties: false` và khai đầy đủ `required`) — không có `strict`, model vẫn có thể sinh JSON hợp lệ về mặt cú pháp nhưng lệch schema về ngữ nghĩa (thiếu field, thừa field, sai kiểu).

**Chất lượng description quyết định model có chọn đúng tool không** — đây là điểm nối trực tiếp với Ngày 3: description của tool chính là một prompt, và nguyên tắc "ràng buộc cụ thể mạnh hơn danh xưng chung" áp dụng nguyên vẹn ở đây. Description mơ hồ ("lấy dữ liệu") khiến model không biết khi nào nên gọi tool này so với tool khác có chức năng gần giống; description tốt nêu rõ **điều kiện gọi** ("gọi tool này khi người dùng hỏi về X, KHÔNG gọi khi Y vì có tool khác chuyên trách").

### Validate output — không bao giờ tin tuyệt đối
Kể cả với `output_config.format` hoặc `strict: true`, **vẫn phải validate ở tầng ứng dụng trước khi dùng dữ liệu cho hành động có side-effect** (ghi DB, gọi API bên ngoài, hiển thị cho người dùng cuối mà không qua kiểm tra). Lý do kỹ thuật cụ thể, không phải phòng xa vô căn cứ:

- **`stop_reason: "max_tokens"`**: nếu response bị cắt vì đạt giới hạn `max_tokens` giữa lúc đang sinh JSON, JSON đó sẽ không đầy đủ (thiếu dấu đóng ngoặc) dù bạn đã cấu hình `output_config.format` — cấu hình format chỉ ràng buộc *cách* sinh, không đảm bảo *sinh xong trong giới hạn token bạn cho phép*.
- **`stop_reason: "refusal"`**: model có thể từ chối trả lời vì lý do an toàn — response trả về HTTP 200 (không phải lỗi) nhưng `content` rỗng hoặc không phải JSON kỳ vọng. Code không kiểm tra `stop_reason` trước khi parse sẽ crash hoặc, nguy hiểm hơn, xử lý một giá trị rác như thể hợp lệ.
- **Schema đúng nhưng giá trị sai về nghiệp vụ**: JSON Schema chỉ kiểm tra được cấu trúc/kiểu dữ liệu, không kiểm tra được ràng buộc nghiệp vụ (ví dụ: model trả về `"mã_cổ_phiếu": "ABCDEF"` — đúng kiểu string, nhưng không phải mã cổ phiếu hợp lệ trên HoSE/HNX). Validate nghiệp vụ luôn phải làm riêng ở code, không thể giao hết cho schema.

### Retry khi model trả sai format — có giới hạn, không phải vòng lặp vô hạn
Khi validate phát hiện output sai (parse lỗi, thiếu field bắt buộc, giá trị không hợp lệ), chiến lược đúng là **retry có giới hạn số lần**, kèm phản hồi lỗi cụ thể vào lượt gọi lại để model có cơ hội tự sửa — không phải lặp vô hạn tới khi đúng (rủi ro treo hệ thống, tốn tiền vô kiểm soát nếu model liên tục sai). Một vòng retry đúng cách:

1. Gọi model, nhận response.
2. Validate. Nếu hợp lệ → dùng luôn, kết thúc.
3. Nếu không hợp lệ và chưa đạt giới hạn retry (ví dụ tối đa 3 lần) → gửi lại request, thêm vào context thông báo lỗi cụ thể model vừa mắc phải ("Response trước thiếu field `email`, hãy sửa và trả lại đúng schema"), tăng biến đếm retry.
4. Nếu đạt giới hạn retry mà vẫn sai → dừng, trả lỗi rõ ràng lên tầng gọi (không âm thầm trả dữ liệu rác), log lại để review sau.

Đây chính là điểm phân biệt senior: junior thường viết `while True: ... if valid: break` — trông "chắc ăn" nhưng là một cách chắc chắn để treo hệ thống hoặc gây vòng lặp tính phí vô kiểm soát khi gặp input mà model không bao giờ trả đúng được (ví dụ schema có ràng buộc mà chính schema đó tự mâu thuẫn). Retry luôn phải có giới hạn cứng và có đường thoát rõ ràng khi hết giới hạn.

## Đối chiếu với code thật trong repo
Đây là chỗ Ngày 3-4 nối trực tiếp vào cơ chế lõi của `mcp-superset`. Repo dùng FastMCP (`core/server.py` khởi tạo instance) để expose các hàm Python thành tool cho AI assistant gọi. Cơ chế: **FastMCP tự sinh JSON Schema cho `input_schema` của mỗi tool dựa trên type hint của hàm Python** — ví dụ nếu một tool trong `tools/chart.py` có signature `def superset_chart_list(dashboard_id: int | None = None, search: str | None = None)`, FastMCP tự dịch type hint đó thành JSON Schema với `properties.dashboard_id.type: "integer"`, đánh dấu tham số nào optional dựa trên giá trị default. Đây chính là "structured output schema" nói ở mục Khái niệm cốt lõi — chỉ khác là schema này mô tả **input** của tool (tham số Claude phải điền) thay vì mô tả **output** cuối cùng gửi cho người dùng.

Docstring của hàm (mô tả tool) đóng vai trò `description` trong tool definition gửi lên API — như đã nói ở Ngày 3, đây là nơi quyết định model có gọi đúng tool, đúng lúc, đúng tham số hay không. Về phần "validate output" và "retry": decorator `@handle_api_errors` trong `utils/decorators.py` đóng vai trò tương đương lớp validate/error-handling ở tầng tool — khi tool gọi API Superset thật và gặp lỗi (token hết hạn, quyền không đủ, resource không tồn tại), decorator này bắt lỗi và trả về JSON có field `"error"` thay vì để exception raise thẳng — đây là nguyên tắc "không âm thầm trả dữ liệu rác" áp dụng ở tầng tool: model nhận được thông báo lỗi rõ ràng qua `tool_result` (kèm `is_error: true` phía Anthropic SDK khi bạn tự viết tool client-side) và có thể tự quyết định thử lại hoặc báo cho người dùng, thay vì nhận một response mơ hồ khiến nó "đoán" tiếp.

## Thực hành
```bash
pip install anthropic pydantic
```

```python
import anthropic
from pydantic import BaseModel
from typing import List

client = anthropic.Anthropic()

# Cách được khuyến nghị: dùng Pydantic model làm schema, SDK tự validate
# response khớp model — không cần tự viết json.loads() + kiểm tra tay.
class ThongTinLienHe(BaseModel):
    ten: str
    email: str
    goi_dich_vu: str
    quan_tam: List[str]

response = client.messages.parse(
    model="claude-opus-5",
    max_tokens=500,
    messages=[{
        "role": "user",
        "content": (
            "Trích xuất thông tin: Nguyễn Văn A (a.nguyen@ssi.com.vn) "
            "muốn dùng gói Enterprise, quan tâm tới API và báo cáo tự động."
        ),
    }],
    output_format=ThongTinLienHe,
)

# response.parsed_output đã là instance ThongTinLienHe đã validate —
# nếu model trả sai schema, SDK raise lỗi rõ ràng thay vì trả object rác.
contact = response.parsed_output
print(contact.ten, contact.email, contact.quan_tam)
```

```python
# Minh hoạ retry có giới hạn khi validate thất bại — pattern bắt buộc
# cho production, KHÔNG dùng while True vô hạn.
import json

def call_with_retry(client, schema_description: str, user_input: str, max_retries: int = 3):
    messages = [{"role": "user", "content": user_input}]
    last_error = None

    for attempt in range(max_retries):
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=500,
            output_config={"format": {"type": "json_schema", "schema": schema_description}},
            messages=messages,
        )

        # Luôn kiểm tra stop_reason TRƯỚC khi parse — response có thể bị
        # cắt (max_tokens) hoặc bị refuse (refusal), cả hai đều không
        # phải "JSON hợp lệ nhưng khác ý" mà là "không có JSON dùng được".
        if response.stop_reason == "refusal":
            raise RuntimeError(f"Model từ chối trả lời: {response.stop_details}")
        if response.stop_reason == "max_tokens":
            last_error = "Response bị cắt do đạt max_tokens — cần tăng giới hạn."
            continue

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(text)
            return data  # Thành công — dừng ngay, không lặp thêm.
        except json.JSONDecodeError as e:
            last_error = f"JSON không hợp lệ: {e}"
            # Đưa lỗi cụ thể vào lượt tiếp theo để model có cơ hội tự sửa.
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": f"Lỗi: {last_error}. Hãy sửa lại."})

    # Hết số lần retry mà vẫn sai — dừng và báo lỗi rõ ràng, KHÔNG trả
    # dữ liệu rác lên tầng gọi.
    raise RuntimeError(f"Không lấy được output hợp lệ sau {max_retries} lần thử: {last_error}")
```

## Bài tập tự làm
1. Viết một Pydantic model mô tả kết quả trích xuất thông tin từ một email hỗ trợ khách hàng (tên khách hàng, mức độ ưu tiên enum `["thấp", "trung bình", "cao"]`, tóm tắt vấn đề). Dùng `client.messages.parse()` để trích xuất từ 3 email mẫu tự viết, kiểm tra `parsed_output` có đúng kiểu không.
2. Cố tình đặt `max_tokens` rất nhỏ (ví dụ 15) cho một tác vụ trả JSON có nhiều field, quan sát `stop_reason` trả về là gì và output bị cắt ra sao. Viết code kiểm tra `stop_reason` trước khi parse để tránh crash.
3. Viết một tool schema đơn giản (ví dụ `dat_ve_may_bay` với tham số `diem_den`, `ngay_bay`, `so_khach`) có `strict: true`, gọi model với một yêu cầu ngôn ngữ tự nhiên tương ứng, in ra `tool_use.input` và kiểm tra nó khớp đúng schema.

## Đào sâu / nâng cao

### Giới hạn thật của JSON Schema mà Claude hỗ trợ
Không phải mọi tính năng JSON Schema đều được hỗ trợ khi dùng `output_config.format` hoặc `strict: true`. Các ràng buộc số học (`minimum`, `maximum`, `multipleOf`), ràng buộc độ dài string (`minLength`, `maxLength`), và schema đệ quy (recursive schema) **không được hỗ trợ** ở tầng ràng buộc sinh token của API — SDK Python/TypeScript tự động loại các ràng buộc này khỏi schema gửi lên API và validate lại ở phía client sau khi nhận response. Hệ quả thực dụng: nếu bạn cần ràng buộc "tuổi phải từ 0-150", đừng chỉ tin `minimum`/`maximum` trong schema hoạt động ở tầng model — luôn có một lớp validate nghiệp vụ riêng ở code, không phụ thuộc hoàn toàn vào JSON Schema.

### `additionalProperties: false` — chi tiết nhỏ nhưng bắt buộc với `strict`
Để dùng `strict: true`, schema phải khai `additionalProperties: false` ở mọi object và khai đầy đủ `required`. Đây không phải chi tiết cú pháp vặt — nó là điều kiện để API biết chính xác không gian giá trị hợp lệ để ràng buộc quá trình sinh token. Thiếu điều kiện này, `strict: true` sẽ báo lỗi ngay khi gửi request, không đợi tới lúc chạy để phát hiện.

### Structured output không tương thích với mọi tính năng khác
Structured output (`output_config.format`) hiện không tương thích với citation (`citations.enabled: true` trên document block) và với assistant-turn prefill — kết hợp hai tính năng này sẽ trả lỗi 400. Đây là lý do cần đọc kỹ tài liệu tính năng trước khi kết hợp nhiều cấu hình lại với nhau, không giả định mọi tính năng luôn cộng dồn được tự do.

## Bài tập senior
1. Bạn nhận một hệ thống cũ dùng chiến lược "prompt-only" để ép JSON: system prompt viết "CHỈ trả về JSON, không giải thích gì thêm" và code parse bằng `json.loads(response.text)` không có try/except. Hệ thống này đôi khi crash ở production với tần suất thấp (khoảng 1-2% request). Chẩn đoán nguyên nhân khả dĩ nhất dựa trên kiến thức Ngày 4, và đề xuất bản sửa theo đúng 3 tầng giải pháp đã học (không chỉ thêm try/except).
2. Thiết kế tool schema cho một tool "chuyển tiền nội bộ giữa 2 tài khoản" trong một ứng dụng ngân hàng nội bộ. Nêu rõ những tham số nào bạn sẽ đưa vào `required`, tham số nào cần validate thêm ở tầng code dù đã đúng JSON Schema (gợi ý: liên hệ mục "JSON Schema chỉ kiểm tra cấu trúc, không kiểm tra ràng buộc nghiệp vụ"), và mô tả ngắn description của tool để giảm rủi ro model gọi nhầm tool này khi không cần.
3. Review đoạn code retry sau và chỉ ra vấn đề:
   ```python
   while True:
       response = call_model(prompt)
       try:
           data = json.loads(response)
           break
       except json.JSONDecodeError:
           prompt += "\nHãy trả JSON đúng."
   ```
   Liệt kê ít nhất 3 rủi ro cụ thể của đoạn code này ở production, không chỉ nói chung "nguy hiểm".

## Checklist trước khi qua Ngày kế
- [ ] Phân biệt được 3 tầng giải pháp ép structured output (prompt-only, JSON mode/output_config, tool schema với strict).
- [ ] Giải thích được vì sao vẫn phải validate output kể cả khi dùng `strict: true`.
- [ ] Viết được một vòng lặp retry có giới hạn số lần, có đường thoát rõ ràng khi hết giới hạn.
- [ ] Biết `stop_reason` nào cần kiểm tra trước khi parse response (`max_tokens`, `refusal`) và vì sao.
- [ ] Liên hệ được cơ chế tool schema với cách FastMCP sinh schema từ type hint trong repo `mcp-superset`.
