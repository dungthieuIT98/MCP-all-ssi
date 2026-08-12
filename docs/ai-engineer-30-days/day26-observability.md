# Phần 26 — Observability: trace 1 request AI end-to-end

## Mục tiêu hôm nay
Hiểu nguyên lý trace một request AI từ đầu tới cuối (input user → retrieval → prompt build → tool call → output), biết log gì/không log gì, và nắm nguyên lý observability để tự chọn công cụ phù hợp — không cần gắn với 1 sản phẩm cụ thể.

## Đọc trước
- [OpenTelemetry — Traces](https://opentelemetry.io/docs/concepts/signals/traces/) (khái niệm trace/span gốc, không riêng LLM — nền tảng để hiểu bất kỳ công cụ LLM observability nào xây trên đó).
- [Anthropic docs](https://docs.anthropic.com/) — mục về logging/monitoring nếu có (tìm trong docs, nội dung/URL cụ thể tra tại thời điểm đọc).
- Tài liệu công cụ LLM observability nói chung: LangSmith, Langfuse — tìm trực tiếp trên trang chủ từng công cụ (`smith.langchain.com`, `langfuse.com`) nếu muốn xem cụ thể một sản phẩm, không có URL cố định để chép vào đây vì giao diện/docs các sản phẩm này thay đổi thường xuyên.

## Khái niệm cốt lõi

### Vì sao observability cho AI system khác observability truyền thống
Backend dev đã quen observability cho web service: log request/response, trace qua các service trong kiến trúc microservice, đo latency từng bước, dùng APM (Application Performance Monitoring) để thấy bottleneck. Nguyên lý này **không đổi** cho hệ thống AI — vẫn là trace + log + metric — nhưng có thêm những chiều dữ liệu đặc thù không tồn tại ở service CRUD thông thường:

- **Prompt là một phần dữ liệu quan trọng cần quan sát**, không chỉ input/output ở tầng API — vì cùng một bug có thể do prompt build sai (ví dụ thiếu context, template lỗi) mà response ở tầng ngoài "trông vẫn hợp lệ về hình thức". Nếu không log được prompt thực tế đã gửi cho model (sau khi đã build đầy đủ system + few-shot + context), rất khó debug tại sao model trả lời sai.
- **Quyết định của model là một "hộp đen" cần trace riêng**: việc model chọn gọi tool nào, với tham số gì, dựa trên phần nào của context — đây là loại quyết định không tồn tại trong service CRUD (code luôn chạy đường logic xác định), cần có trace riêng cho từng bước quyết định, không chỉ trace thời gian xử lý.
- **Non-determinism**: cùng input, hai lần chạy có thể ra hai kết quả khác nhau — nên trace không chỉ để tìm bug tái lập được (giống code thông thường) mà còn để hiểu *phân bố* hành vi qua nhiều lần chạy, gắn liền với phần eval (Phần 22-23).

### Trace 1 request AI end-to-end — các mốc cần thấy được
Một request đi qua một pipeline AI (RAG + agent, ví dụ điển hình) có các bước cần trace riêng biệt, mỗi bước là một "span" trong thuật ngữ tracing:

1. **Input user**: câu hỏi/message gốc, kèm metadata (user id, session id, timestamp) — là gốc của toàn bộ trace, mọi span khác đều liên kết về đây qua một trace ID chung.
2. **Retrieval (nếu có RAG)**: query dùng để tìm kiếm (có thể đã được rewrite — Phần 12), danh sách document/chunk trả về, điểm similarity/rerank score của từng kết quả. Đây là bước hay bị bỏ qua khi trace — nhiều hệ thống chỉ log "có gọi retrieval" mà không log *kết quả* trả về, khiến không thể debug được câu hỏi "model trả lời sai vì retrieval sai, hay vì generation sai trên context đúng".
3. **Prompt được build ra sao**: nội dung system prompt, phần few-shot (nếu có), phần context được chèn vào (kết quả retrieval, lịch sử hội thoại) — nói cách khác, log **prompt cuối cùng thực sự gửi cho model**, không chỉ log input gốc của user. Đây thường là bước debug quan trọng nhất vì rất nhiều lỗi thực chất là lỗi ở tầng "build prompt" (template sai, chèn nhầm biến, context bị cắt cụt do vượt giới hạn) chứ không phải lỗi ở model.
4. **Tool call nào được gọi**: tên tool, tham số gọi, kết quả trả về (hoặc lỗi), thời gian thực thi mỗi tool call — với agent nhiều bước, cần thấy được toàn bộ chuỗi tool call theo đúng thứ tự, không chỉ tool call cuối cùng.
5. **Output cuối**: câu trả lời cuối cùng trả cho user, cùng metadata (model dùng, token usage, latency của từng bước và tổng).

Toàn bộ 5 mốc này nên liên kết bằng một **trace ID chung** (đúng nguyên lý distributed tracing đã quen từ hệ thống microservice) — để khi có 1 request lỗi, chỉ cần trace ID là lấy lại được toàn bộ hành trình, không phải grep log rời rạc rồi tự ghép bằng tay theo timestamp.

### Log những gì — và bắt buộc KHÔNG log gì
**Nên log** (phục vụ debug và eval — nhiều nội dung log production thật ra có thể tái sử dụng làm case mới cho golden dataset ở Phần 22, đúng vòng lặp "dataset sống"):
- Prompt đầy đủ đã gửi (hoặc ít nhất đủ để tái tạo — có thể log riêng phần tĩnh và phần biến đổi nếu prompt quá lớn để log toàn bộ mỗi lần).
- Response đầy đủ từ model.
- Token usage (input/output/cache — xem lại Phần 24) để phục vụ cost tracking.
- Latency chi tiết theo từng bước (TTFT, TTLT, thời gian mỗi tool call — xem lại Phần 25).
- Tool call: tên, tham số, kết quả, có lỗi không.
- Metadata: model version dùng, timestamp, trace/session ID, category câu hỏi nếu có phân loại.

**Không log** nếu có PII (personally identifiable information) hoặc dữ liệu nhạy cảm — nguyên tắc này áp dụng cho *toàn bộ nội dung ở trên*, không phải một danh mục riêng:
- Nếu input user hoặc context retrieval chứa thông tin định danh khách hàng (số CMND/CCCD, số tài khoản, số dư, thông tin sức khỏe/tài chính cá nhân) — không log nguyên văn vào hệ thống observability, đặc biệt nếu công cụ đó gửi log ra dịch vụ bên thứ ba (SaaS observability platform ngoài SSI).
- Cần có bước **redact/mask** trước khi log (thay số cụ thể bằng placeholder, ví dụ `[SO_TAI_KHOAN]`) — làm ở tầng logging middleware, không phải hy vọng model/code nghiệp vụ tự nhớ che.
- Nguyên tắc thực dụng: coi log observability là một nơi dữ liệu "rời khỏi" luồng xử lý chính, đặc biệt nếu công cụ trace là SaaS bên thứ ba — áp dụng đúng mức độ kiểm soát dữ liệu như khi gửi dữ liệu ra một API bên ngoài công ty. Nếu không chắc một loại dữ liệu có thuộc diện nhạy cảm cần redact hay không, hỏi trước với đơn vị có thẩm quyền, không tự quyết định log "cho dễ debug".

### Công cụ có thật trong ngành — nguyên lý là chính, không cần chọn 1 cái
Không có một công cụ "chuẩn" duy nhất, và lựa chọn tuỳ ràng buộc hạ tầng/dữ liệu của tổ chức:
- **LangSmith, Langfuse**: nền tảng LLM observability chuyên biệt, có UI xem trace theo cây (span lồng span), tính năng gắn eval/feedback vào từng trace, so sánh giữa các version prompt. Thường dễ bắt đầu nhanh vì thiết kế riêng cho use case LLM.
- **Tự xây bằng OpenTelemetry (OTel)**: dùng chuẩn tracing mở (span, trace context propagation) đã có sẵn hệ sinh thái APM truyền thống (nếu tổ chức đã có Jaeger, Grafana Tempo, hoặc APM nội bộ) — định nghĩa custom span cho các bước đặc thù LLM (retrieval span, tool-call span, generation span) thay vì dùng nền tảng LLM-specific riêng. Lợi ích: tận dụng hạ tầng observability đã có sẵn trong tổ chức, không phải học/vận hành thêm một hệ thống mới; đánh đổi: phải tự định nghĩa schema cho các khái niệm LLM-specific (token usage, prompt version) vì OTel gốc không có sẵn khái niệm này.
- Với tổ chức có ràng buộc dữ liệu không được rời khỏi hạ tầng nội bộ (như phần lớn tổ chức tài chính) — cân nhắc kỹ việc gửi trace (có thể chứa nội dung prompt/response nhạy cảm) tới SaaS bên ngoài; tự host (self-hosted Langfuse, hoặc tự xây trên OTel + backend nội bộ) là hướng an toàn hơn về mặt kiểm soát dữ liệu, đổi lại tốn công vận hành hơn.
- Nguyên lý chọn công cụ: hỏi "công cụ này có cho tôi thấy đủ 5 mốc trace ở trên không, có hỗ trợ redact PII trước khi lưu không, dữ liệu lưu ở đâu (SaaS ngoài hay nội bộ)" — trả lời được 3 câu này quan trọng hơn việc chọn đúng brand công cụ nào.

## Đối chiếu với code thật trong repo
`mcp-superset` hiện chưa có tầng observability/tracing riêng cho LLM (đúng vì đây là MCP server thuần tool-provider, không tự chạy generation) — nhưng chính vì vậy nó là điểm tựa tốt để hình dung ranh giới trace: nếu một AI client (ví dụ Claude Desktop, hoặc một agent tuỳ biến) gọi vào các tool của server này, trace đầy đủ end-to-end sẽ nằm ở **phía client/agent** (nơi build prompt, gọi model, quyết định gọi tool), còn server `mcp-superset` chỉ là một "tool-call span" trong trace đó — input là tham số tool, output là kết quả trả về (hoặc `{"error": ...}` từ `handle_api_errors` trong `utils/decorators.py`). Điểm quan trọng khi thiết kế trace nếu tích hợp: `core/context.py` forward session cookie theo từng user thật qua header `X-Superset-Session` — nếu log trace ở tầng server này, session cookie chính là một credential, tuyệt đối không log giá trị cookie vào trace/observability tool (dù chỉ để debug), chỉ log việc "có gửi credential hay không" và user identity (nếu tách biệt được khỏi giá trị cookie) — đây là ví dụ cụ thể của nguyên tắc "không log gì nếu có dữ liệu nhạy cảm" áp dụng ngay trong chính repo này.

## Thực hành
```python
"""
Minh hoạ nguyên lý trace bằng OpenTelemetry: 1 trace cho toàn bộ request,
nhiều span con cho retrieval (giả lập), build prompt, gọi model, tool call.
Chạy được với `pip install anthropic opentelemetry-sdk opentelemetry-api`.
Ở đây dùng ConsoleSpanExporter để in trace ra terminal cho dễ quan sát —
production thật sẽ export tới backend thật (Jaeger, Langfuse, v.v.).
"""
import re

import anthropic
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(
    SimpleSpanProcessor(ConsoleSpanExporter())
)
tracer = trace.get_tracer("mcp-superset-demo")

client = anthropic.Anthropic()

# Regex đơn giản minh hoạ việc redact PII trước khi log — production thật cần
# bộ quy tắc đầy đủ hơn nhiều, đây chỉ để minh hoạ nguyên lý.
ACCOUNT_NUMBER_PATTERN = re.compile(r"\b\d{8,12}\b")


def redact_pii(text: str) -> str:
    return ACCOUNT_NUMBER_PATTERN.sub("[SO_TAI_KHOAN]", text)


def fake_retrieval(query: str) -> list[dict]:
    """Giả lập bước retrieval — thực tế sẽ gọi vector DB (Phần 9-11)."""
    return [
        {"doc_id": "doc-1", "score": 0.87, "text": "Superset hỗ trợ tạo dashboard từ dataset SQL."},
        {"doc_id": "doc-2", "score": 0.81, "text": "Dataset trong Superset ánh xạ tới 1 bảng hoặc 1 câu SQL."},
    ]


def build_prompt(user_input: str, retrieved: list[dict]) -> str:
    context = "\n".join(f"- {r['text']}" for r in retrieved)
    return f"""Dựa vào tài liệu sau, trả lời câu hỏi.
Tài liệu:
{context}

Câu hỏi: {user_input}"""


def handle_request(user_input: str) -> str:
    with tracer.start_as_current_span("ai_request") as root_span:
        # Log input user — đã redact trước khi gắn vào attribute của span,
        # vì span có thể được export ra hệ thống ngoài.
        root_span.set_attribute("user_input.redacted", redact_pii(user_input))

        with tracer.start_as_current_span("retrieval") as retrieval_span:
            retrieved = fake_retrieval(user_input)
            retrieval_span.set_attribute("retrieval.num_results", len(retrieved))
            retrieval_span.set_attribute(
                "retrieval.top_score", retrieved[0]["score"] if retrieved else 0
            )

        with tracer.start_as_current_span("build_prompt") as prompt_span:
            final_prompt = build_prompt(user_input, retrieved)
            # Log prompt cuối cùng (đã redact) — đây là bước debug quan trọng
            # nhất theo nguyên lý đã học ở phần khái niệm.
            prompt_span.set_attribute("prompt.redacted", redact_pii(final_prompt))
            prompt_span.set_attribute("prompt.char_len", len(final_prompt))

        with tracer.start_as_current_span("generate") as gen_span:
            response = client.messages.create(
                model="claude-sonnet-5",
                max_tokens=300,
                messages=[{"role": "user", "content": final_prompt}],
            )
            output_text = response.content[0].text
            gen_span.set_attribute("generate.model", "claude-sonnet-5")
            gen_span.set_attribute("generate.input_tokens", response.usage.input_tokens)
            gen_span.set_attribute("generate.output_tokens", response.usage.output_tokens)
            gen_span.set_attribute("generate.output_redacted", redact_pii(output_text))

        return output_text


if __name__ == "__main__":
    # Câu hỏi mẫu có chứa "số tài khoản" giả để minh hoạ redact hoạt động.
    result = handle_request("Số tài khoản 123456789 của tôi dùng dataset nào để xem lịch sử?")
    print("\n=== Output cuối trả cho user (KHÔNG redact, vì đây là response thật) ===")
    print(result)
```

## Bài tập tự làm
1. Chạy đoạn code trên, đọc output console — xác nhận có 4 span (`ai_request`, `retrieval`, `build_prompt`, `generate`) và attribute của mỗi span đã bị redact số tài khoản đúng như kỳ vọng.
2. Thêm 1 span `tool_call` giả lập (ví dụ gọi 1 hàm giả `lookup_dataset(name)`), gắn attribute tên tool và tham số — chèn vào giữa `build_prompt` và `generate` để mô phỏng trường hợp model cần gọi tool trước khi trả lời.
3. Viết thêm 2 pattern regex redact cho 2 loại dữ liệu nhạy cảm khác (ví dụ email, số điện thoại Việt Nam dạng `0xxxxxxxxx`) và tích hợp vào `redact_pii`.
4. Thử đổi `SimpleSpanProcessor` + `ConsoleSpanExporter` — tìm hiểu (đọc docs OpenTelemetry) sự khác biệt với `BatchSpanProcessor`, và giải thích vì sao production nên dùng batch processor thay vì simple processor (liên hệ lại ảnh hưởng tới latency của request chính nếu export đồng bộ).

## Đào sâu / nâng cao

### Trace context propagation qua nhiều service
Nếu pipeline AI trải qua nhiều service riêng biệt (ví dụ 1 service gateway, 1 service retrieval, 1 service gọi model) thay vì chạy trong 1 process, cần propagate trace context (trace ID, span ID cha) qua header HTTP giữa các service — đây là bài toán distributed tracing kinh điển, OpenTelemetry có chuẩn W3C Trace Context cho việc này, không cần tự nghĩ ra format riêng.

### Sampling — không trace 100% traffic ở scale lớn
Ở traffic lớn, lưu trace đầy đủ cho mọi request có thể tốn chi phí lưu trữ/băng thông đáng kể — nhiều hệ thống dùng sampling (chỉ trace một tỷ lệ request, hoặc trace 100% cho request có lỗi/latency cao bất thường, sampling thấp cho request "bình thường"). Quyết định tỷ lệ sampling là đánh đổi giữa chi phí quan sát và khả năng bắt được case hiếm — tương tự nguyên lý sampling trong APM truyền thống.

### Gắn eval và feedback vào trace
Nhiều nền tảng LLM observability cho phép gắn kết quả eval (Phần 22, LLM-as-judge) hoặc feedback signal thật (Phần 23, thumbs up/down) trực tiếp vào trace tương ứng — biến observability từ "chỉ xem cái gì đã xảy ra" thành "xem cái gì đã xảy ra VÀ nó có tốt không" trong cùng một nơi, thay vì hai hệ thống rời rạc phải tự ghép bằng ID.

## Bài tập senior
Một hệ thống chatbot nội bộ đang gặp phản hồi "đôi khi trả lời sai thông tin dataset, không rõ tại sao" — không có trace/observability nào được thiết lập từ đầu, chỉ có log dạng text tự do rải rác (`print` ra file log, không có cấu trúc). Viết một kế hoạch triển khai observability tối thiểu (dạng bước ưu tiên, không cần chọn công cụ cụ thể) để trong 1-2 tuần có thể debug được câu hỏi "sai ở retrieval hay sai ở generation" cho các case bị báo lỗi — nêu rõ bạn sẽ ưu tiên thêm trace ở đâu trước nếu chỉ có thời gian làm từng phần một, và giải thích vì sao chọn thứ tự đó.

## Checklist trước khi qua Phần 27
- [ ] Kể được đủ 5 mốc cần trace trong 1 request AI end-to-end.
- [ ] Giải thích được vì sao log prompt cuối cùng (đã build) quan trọng hơn chỉ log input gốc của user.
- [ ] Biết rõ nguyên tắc không log PII/dữ liệu nhạy cảm, và có ý tưởng cụ thể cách redact trước khi log.
- [ ] Hiểu nguyên lý trace/span của OpenTelemetry đủ để tự đánh giá bất kỳ công cụ LLM observability nào, không phụ thuộc 1 sản phẩm cụ thể.
- [ ] Chạy được đoạn code thực hành, quan sát được cây span và xác nhận redact hoạt động đúng.
</content>
