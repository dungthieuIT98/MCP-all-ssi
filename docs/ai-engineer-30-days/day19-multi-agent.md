# Phần 19 — Multi-agent: khi nào đáng, khi nào chỉ là 1 agent giả trang

## Mục tiêu hôm nay
Nắm các pattern multi-agent chính (supervisor/orchestrator-worker, hand-off, debate/critique) và rèn khả năng đánh giá phản biện — vì multi-agent là chủ đề dễ bị lạm dụng theo hype nhất trong toàn bộ kiến trúc agent, và hay bị hỏi xoáy ở review senior.

## Đọc trước
- [Anthropic — Tool use / building agents](https://docs.anthropic.com/) — phần thảo luận về khi nào cần nhiều agent hay chỉ cần 1 agent với nhiều tool.
- Paper "ReAct: Synergizing Reasoning and Acting in Language Models" (đã đọc Phần 17) — đọc lại phần liên quan tới việc 1 agent đơn có thể xử lý nhiều bước, làm nền so sánh với lý do "cần" nhiều agent.
- LangChain — tài liệu về multi-agent orchestration (nếu có, phần khái niệm không cần chạy code) — để thấy cách 1 framework mô tả pattern supervisor/worker.

## Khái niệm cốt lõi

### Định nghĩa: multi-agent là gì, không phải là gì
Multi-agent là kiến trúc trong đó **nhiều lời gọi model độc lập, mỗi lời gọi có system prompt/vai trò/bộ tool riêng**, phối hợp với nhau để hoàn thành 1 task — khác với 1 agent đơn (single agent) chạy 1 vòng lặp ReAct với 1 system prompt cố định và 1 bộ tool chung cho toàn bộ task.

Điều multi-agent KHÔNG phải: không phải "gọi model nhiều lần" (1 agent đơn với vòng lặp ReAct đã gọi model nhiều lần, đó không làm nó thành multi-agent). Ranh giới thật là: có **nhiều vai trò/persona/system prompt khác nhau, mỗi vai trò xử lý 1 phần việc riêng biệt và có context riêng** (không nhìn thấy toàn bộ context của agent khác) — đây là điểm khác biệt về **cách ly context**, không chỉ là số lần gọi model.

### Pattern 1: Supervisor / Orchestrator-Worker
Một agent "supervisor" nhận task tổng, chia nhỏ thành sub-task, giao (thường qua tool-calling — supervisor "gọi" 1 worker agent như thể nó là 1 tool) cho các "worker" agent chuyên biệt xử lý từng phần, rồi tổng hợp kết quả từ các worker để trả lời cuối. Mỗi worker thường có system prompt hẹp, chuyên 1 domain (ví dụ: 1 worker chuyên viết SQL, 1 worker chuyên tóm tắt văn bản, 1 worker chuyên gọi API bên ngoài).

- **Giá trị thật**: mỗi worker chỉ cần thấy tool và context liên quan tới domain của nó — giảm nhiễu tool-selection (liên hệ Phần 15: quá nhiều tool cùng lúc gây chọn sai) vì mỗi agent chỉ có 1 tập tool nhỏ, liên quan. Supervisor không cần biết chi tiết implementation của worker, chỉ cần biết "giao việc gì, nhận lại gì" — tách biệt rõ ràng (separation of concerns, khái niệm quen thuộc từ backend).
- **Chi phí thật**: mỗi worker là 1 (hoặc nhiều) lời gọi model riêng — tăng số lượng API call, tăng latency tổng (thường không parallel hoá hoàn toàn được vì worker sau phụ thuộc kết quả worker trước), tăng cost theo số lời gọi.

### Pattern 2: Hand-off giữa agent chuyên biệt
Khác supervisor (1 agent trung tâm điều phối toàn bộ), hand-off là khi 1 agent đang xử lý task **chuyển giao hoàn toàn** cuộc hội thoại cho 1 agent khác khi nhận ra task vượt phạm vi chuyên môn của nó — giống mô hình "chuyển máy" trong contact center (nhân viên tổng đài chuyển khách qua bộ phận chuyên trách khi không xử lý được). Agent nhận hand-off tiếp quản toàn bộ ngữ cảnh (hoặc 1 phần được tóm tắt lại) và tiếp tục từ đó, không có "agent trung tâm" giữ quyền điều phối suốt.

- **Giá trị thật**: phù hợp khi các domain rất khác biệt (ví dụ: agent hỗ trợ kỹ thuật hand-off qua agent xử lý thanh toán khi khách chuyển câu hỏi) và không cần agent trung tâm biết chi tiết cả 2 domain.
- **Rủi ro**: mất context khi hand-off nếu không thiết kế kỹ phần tóm tắt/chuyển giao — agent nhận hand-off có thể thiếu thông tin quan trọng đã trao đổi trước đó, dẫn tới hỏi lại người dùng những gì đã hỏi rồi (trải nghiệm tệ).

### Pattern 3: Debate / Critique giữa nhiều agent
Nhiều agent (thường cùng model hoặc khác model) cùng xử lý 1 vấn đề độc lập, sau đó so sánh/phản biện kết quả của nhau (1 agent đóng vai "critic" chấm/phản biện output của agent khác) trước khi chọn ra câu trả lời cuối — hoặc lặp lại vài vòng debate để hội tụ về câu trả lời tốt hơn.

- **Giá trị thật**: tăng độ chính xác cho task có tính chất đánh giá/suy luận phức tạp, nơi 1 lần sinh output duy nhất dễ mắc lỗi mà chính model khó tự phát hiện lỗi của mình (self-critique trong cùng 1 lần gọi thường yếu hơn 1 lời gọi riêng đóng vai critic với context sạch). Cũng dùng trong LLM-as-judge (sẽ gặp lại ở Phần 22 khi học eval).
- **Chi phí thật**: nhân số lời gọi model lên nhiều lần (N agent x M vòng debate) — chi phí và latency tăng tuyến tính hoặc hơn, chỉ hợp lý khi giá trị tăng độ chính xác lớn hơn chi phí tăng thêm, và task đủ quan trọng để trả giá đó (ví dụ eval offline chạy 1 lần, không phải mỗi request người dùng).

### Khi nào multi-agent THỰC SỰ đáng
- **Cần chuyên môn hoá rõ rệt**: các domain đủ khác biệt để 1 system prompt/bộ tool chung không thể phục vụ tốt cả hai (ví dụ 1 agent viết code SQL phức tạp và 1 agent viết văn bản tự nhiên cho khách hàng — 2 "kỹ năng" khác hẳn, trộn vào 1 system prompt làm cả hai yếu đi).
- **Cần cách ly context vì lý do cụ thể**: worker xử lý dữ liệu nhạy cảm không nên "thấy" context của phần việc khác (ví dụ 1 agent xử lý thông tin cá nhân khách hàng, tách biệt khỏi agent tổng hợp báo cáo công khai) — cách ly ở đây có giá trị bảo mật/compliance thật, không chỉ tổ chức code.
- **Task đủ lớn và đủ giá trị để trả chi phí latency/cost tăng thêm** — ví dụ 1 pipeline chạy offline (không chờ người dùng real-time) xử lý hàng loạt tài liệu, có thể chấp nhận nhiều agent chuyên biệt vì không bị áp lực latency như chat trực tiếp.

### Khi nào chỉ là "1 agent giả trang nhiều agent" — lạm dụng theo hype
Đây là lỗi thiết kế rất thường gặp và là chủ đề hay bị hỏi xoáy khi review senior:
- **Chia nhỏ theo "bước" thay vì theo "chuyên môn"**: tạo ra "agent bước 1", "agent bước 2", "agent bước 3" chỉ vì task có nhiều bước — trong khi bản chất đó chỉ là 1 vòng lặp ReAct đơn (Phần 17) của 1 agent duy nhất, gọi tool khác nhau ở mỗi bước. Không có sự khác biệt về "chuyên môn" hay "cách ly context" thật — chỉ là chia nhỏ 1 quy trình tuần tự và gọi mỗi phần là "1 agent" để nghe hiện đại hơn.
- **Không tăng chất lượng đo được, chỉ tăng cost/latency/độ khó debug**: nếu benchmark/eval (Phần 22) không cho thấy multi-agent cho kết quả tốt hơn rõ rệt so với 1 agent đơn với tool tốt, thì việc thêm nhiều agent chỉ đang trả thêm chi phí (nhiều API call, nhiều điểm lỗi, log rải ở nhiều nơi khó trace — liên hệ Phần 26 observability) mà không đổi lại gì.
- **Debug multi-agent khó hơn hẳn 1 agent đơn**: lỗi có thể xảy ra ở supervisor, ở 1 trong N worker, hoặc ở bước tổng hợp — cần trace xuyên qua nhiều lời gọi model độc lập để tìm ra chỗ sai, so với 1 agent đơn chỉ có 1 luồng log tuyến tính. Chi phí vận hành/debug này thường bị đánh giá thấp khi thiết kế ban đầu, chỉ lộ ra khi hệ thống đã chạy production và có lỗi khó tái hiện.
- **"Nghe cho oai" trong pitch/CV nhưng không giải quyết vấn đề thật**: multi-agent là cụm từ hot, dễ bị đưa vào thiết kế để "nghe hiện đại" — senior engineer phải phản biện được câu hỏi "nếu bỏ hết, dùng 1 agent với tool tốt hơn và prompt rõ hơn, kết quả có tệ đi không?" trước khi chốt kiến trúc multi-agent.

Quy tắc thực dụng: **luôn thử thiết kế bằng 1 agent đơn với bộ tool đủ tốt trước.** Chỉ tách thành multi-agent khi có lý do cụ thể (chuyên môn hoá rõ, cách ly context có giá trị bảo mật/compliance, hoặc đã đo được chất lượng tăng thật qua eval) — không tách "vì nó nghe hợp lý trên giấy".

## Đối chiếu với code thật trong repo
`mcp-superset` không phải là 1 agent, và cũng không triển khai multi-agent — nó là 1 MCP server cung cấp tool cho agent ở phía client dùng. Nhưng có thể dùng cấu trúc tool của nó để minh hoạ ranh giới "chuyên môn hoá tool" so với "multi-agent": các tool trong [`tools/chart.py`](../../tools/chart.py), [`tools/dashboard.py`](../../tools/dashboard.py), [`tools/database.py`](../../tools/dashboard.py), [`tools/user.py`](../../tools/user.py) được nhóm theo domain (chart, dashboard, database, user) — đây là **tổ chức code và tool theo domain**, nhưng khi 1 client (ví dụ Claude Desktop) dùng các tool này, vẫn chỉ có **1 agent duy nhất** (1 vòng lặp ReAct, 1 context, 1 system prompt) chọn tool phù hợp từ tất cả các nhóm đó — không có "agent chart" và "agent dashboard" riêng biệt nào cả. Nếu 1 ngày cần tách thành multi-agent thật (ví dụ 1 "agent phân tích dashboard" tổng hợp nhiều chart rồi giao cho 1 "agent viết báo cáo" khác), lý do phải là chuyên môn hoá/cách ly context thật, không phải chỉ vì tool đã được chia file theo domain — chia file là tổ chức code, không tự động là ranh giới agent.

## Thực hành
Ví dụ supervisor/worker tối giản với Anthropic SDK — supervisor phân loại câu hỏi rồi giao cho 1 trong 2 worker chuyên biệt (mỗi worker có system prompt và bộ tool RIÊNG, minh hoạ đúng "cách ly context"):

```python
import json
from anthropic import Anthropic

client = Anthropic()


def worker_billing(question: str) -> str:
    """Worker chuyên hoá đơn/thanh toán — chỉ thấy context của chính nó, KHÔNG thấy
    lịch sử của worker khác. Đây là điểm khác biệt thật so với 1 agent đơn."""
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=512,
        system="Bạn là chuyên gia hoá đơn/thanh toán. Chỉ trả lời trong phạm vi này.",
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def worker_technical(question: str) -> str:
    """Worker chuyên kỹ thuật — cũng có context riêng, tách biệt hoàn toàn."""
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=512,
        system="Bạn là chuyên gia hỗ trợ kỹ thuật. Chỉ trả lời trong phạm vi này.",
        messages=[{"role": "user", "content": question}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


SUPERVISOR_TOOLS = [
    {
        "name": "route_to_billing",
        "description": "Chuyển câu hỏi tới chuyên gia hoá đơn/thanh toán.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
    {
        "name": "route_to_technical",
        "description": "Chuyển câu hỏi tới chuyên gia hỗ trợ kỹ thuật.",
        "input_schema": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]},
    },
]


def supervisor(user_message: str) -> str:
    """Supervisor CHỈ quyết định route, không tự trả lời nội dung chuyên môn —
    đây là ranh giới rõ giữa 'điều phối' và 'chuyên môn hoá'."""
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=256,
        system="Bạn chỉ có nhiệm vụ định tuyến câu hỏi tới đúng chuyên gia, không tự trả lời nội dung.",
        tools=SUPERVISOR_TOOLS,
        tool_choice={"type": "any"},  # ép phải chọn 1 trong 2 tool, không trả text thuần
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type != "tool_use":
            continue
        question = block.input["question"]
        if block.name == "route_to_billing":
            print("[supervisor] route -> billing")
            return worker_billing(question)
        if block.name == "route_to_technical":
            print("[supervisor] route -> technical")
            return worker_technical(question)
    return "Không xác định được worker phù hợp."


if __name__ == "__main__":
    print(supervisor("Tại sao hoá đơn tháng này của tôi cao hơn tháng trước?"))
    print(supervisor("App bị lỗi không đăng nhập được, tôi cần hỗ trợ."))
```

## Bài tập tự làm
1. Chạy ví dụ trên, log số lời gọi model và tổng token tiêu tốn cho 1 câu hỏi (supervisor + 1 worker = tối thiểu 2 lời gọi) — so sánh với việc chỉ dùng 1 agent đơn có system prompt gộp cả 2 domain, đo chênh lệch cost/latency thật.
2. Viết lại ví dụ trên thành **1 agent đơn** (bỏ supervisor, gộp 2 system prompt thành 1, không có `route_to_*` tool) — so sánh chất lượng trả lời giữa 2 cách với cùng 5 câu hỏi test. Ghi lại: multi-agent có thực sự trả lời tốt hơn không, hay chỉ tốn thêm chi phí?
3. Thiết kế (chỉ viết ra giấy/mô tả, không cần code) 1 pattern debate/critique cho bài toán "đánh giá 1 đoạn code có lỗi bảo mật không" — 1 agent sinh review, 1 agent khác phản biện review đó trước khi chốt kết quả cuối. Liệt kê rõ giá trị tăng thêm và chi phí tăng thêm.
4. Tìm 1 ví dụ thật (từ blog kỹ thuật, tài liệu công khai, hoặc kinh nghiệm cá nhân) về 1 hệ thống multi-agent bị đánh giá là "over-engineered" — chỉ ra cụ thể phần nào lẽ ra chỉ cần 1 agent đơn.

## Đào sâu / nâng cao

### Context isolation là giá trị kỹ thuật, không chỉ tổ chức
Khi worker KHÔNG thấy toàn bộ lịch sử của supervisor hay worker khác, đây có giá trị thật ngoài "gọn code": giảm token phải xử lý mỗi lời gọi (worker chỉ nhận phần liên quan, không nhận toàn bộ lịch sử tích lũy), và giảm rủi ro "nhiễu" thông tin không liên quan ảnh hưởng tới output của worker (tương tự lý do giảm số tool active ở Phần 15).

### Đo lường trước khi quyết định tách multi-agent
Nguyên tắc senior: không tách multi-agent dựa trên cảm giác "có vẻ nên tách" — chạy eval (Phần 22) so sánh output của kiến trúc 1-agent và multi-agent trên cùng bộ test case, đo cả chất lượng VÀ cost/latency, rồi quyết định dựa trên số liệu. Nếu chưa có eval framework, đó là dấu hiệu chưa nên vội tách multi-agent.

### Failure mode riêng của multi-agent: lỗi lan truyền
Khi supervisor route sai (chọn worker sai domain), lỗi này không lộ ra ngay — worker vẫn trả lời "hợp lý" nhưng lệch chủ đề, và người dùng/hệ thống eval có thể không phát hiện ngay lỗi nằm ở bước routing chứ không phải ở worker. Multi-agent thêm 1 lớp lỗi mới (routing/hand-off sai) không tồn tại ở 1 agent đơn.

### Multi-agent với cùng model vs khác model
Debate/critique có thể dùng cùng 1 model cho tất cả agent (rẻ hơn, nhưng cùng model có xu hướng có cùng điểm mù/bias), hoặc dùng model khác nhau cho từng vai trò (đắt hơn, nhưng giảm rủi ro tất cả agent cùng mắc đúng 1 loại lỗi). Cân nhắc này liên hệ trực tiếp Phần 6 (model selection) và Phần 24 (cost engineering).

## Bài tập senior
Trong 1 buổi review thiết kế, đồng nghiệp đề xuất kiến trúc "5 agent chuyên biệt" cho 1 chatbot hỗ trợ nội bộ đơn giản (trả lời câu hỏi về chính sách công ty, chỉ cần tra cứu 1 bộ tài liệu tĩnh) — lý do đưa ra là "để hệ thống có khả năng mở rộng và chuyên môn hoá cao". Bạn nghi ngờ đây là over-engineering vì bài toán thực chất chỉ là RAG đơn giản (Tuần 2) + có thể vài tool nhỏ. Viết ra: (1) 3-4 câu hỏi bạn sẽ hỏi để làm rõ liệu có domain nào thực sự khác biệt cần cách ly, (2) cách bạn đề xuất bắt đầu bằng 1 agent đơn và chỉ tách khi có số liệu eval chứng minh cần, (3) cách trình bày phản biện này mà không phủ nhận hoàn toàn ý tưởng của đồng nghiệp trong 1 buổi review (kỹ năng giao tiếp senior, không chỉ kỹ thuật).

## Checklist trước khi qua Ngày kế
- [ ] Phân biệt được multi-agent với "1 agent gọi model nhiều lần trong vòng lặp ReAct".
- [ ] Giải thích được 3 pattern (supervisor, hand-off, debate/critique) và ví dụ dùng đúng cho mỗi pattern.
- [ ] Tự đưa ra được ít nhất 1 lý luận phản biện cụ thể chống lại việc dùng multi-agent khi không cần.
- [ ] Biết cách đo (không chỉ đoán) liệu multi-agent có thực sự đáng giá cho 1 bài toán cụ thể.
