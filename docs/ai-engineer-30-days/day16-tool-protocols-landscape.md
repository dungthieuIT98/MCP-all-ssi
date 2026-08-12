# Phần 16 — Các giao thức & framework kết nối tool: function calling thuần, MCP, OpenAPI-to-tool, LangChain/LlamaIndex — so sánh khi nào dùng gì

## Mục tiêu hôm nay
Có bức tranh toàn cảnh về các cách "gắn tool" cho LLM/agent hiện có, hiểu chúng giải quyết những vấn đề KHÁC NHAU (không phải 4 cách làm cùng 1 việc), và biết chọn đúng cho từng bài toán — không mặc định dùng framework hay MCP chỉ vì "nghe nói nó hiện đại".

## Đọc trước
- [OpenAI — Function calling](https://platform.openai.com/docs/)
- [Anthropic — Tool use](https://docs.anthropic.com/)
- [Model Context Protocol — tài liệu chính thức](https://modelcontextprotocol.io/)
- LangChain — tài liệu "Tools" và "Agents" (langchain.com/docs) — chỉ cần đọc phần khái niệm, không cần chạy hết ví dụ.

## Khái niệm cốt lõi

Phần 15 đã thống nhất: tool-calling là cơ chế model sinh cấu trúc gọi hàm, code thực thi. Câu hỏi ngày này khác: **tool schema đó lấy từ đâu, và ai định nghĩa/quản lý vòng đời của nó?** Có 4 cách phổ biến, mỗi cách nhằm giải quyết một vấn đề khác:

### 1. Function calling thuần (raw / no framework)
Định nghĩa tool schema (JSON Schema) trực tiếp trong code gọi API — như ví dụ Phần 15. Không có lớp trừu tượng nào giữa code của bạn và API của provider.

- **Ưu điểm**: đơn giản nhất để hiểu và debug — không có "hộp đen" nào giữa bạn và request/response thật. Không thêm dependency. Kiểm soát 100% việc parse, validate, retry.
- **Nhược điểm**: khi số lượng tool tăng, bạn tự viết tay toàn bộ logic loop, quản lý lịch sử hội thoại, xử lý parallel tool call, retry khi lỗi — những thứ framework đóng gói sẵn.
- **Dùng khi**: app nhỏ, ít tool (dưới ~10), 1 provider cố định, team hiểu rõ cơ chế và muốn kiểm soát tối đa (thường là lựa chọn đúng cho production system quan trọng, vì ít "magic" = dễ audit, dễ debug khi có lỗi ở mức security-sensitive).

### 2. Framework orchestration (LangChain tools/agents, LlamaIndex agents)
Framework cung cấp abstraction: bạn định nghĩa tool theo interface của framework (decorator, class), framework tự lo phần loop, quản lý memory, chuyển đổi format schema giữa nhiều provider, compose nhiều agent/bước.

- **Ưu điểm**: tiện khi cần compose nhiều bước phức tạp (chain nhiều LLM call, agent gọi agent, tích hợp sẵn nhiều connector — vector store, SQL, web search). Portable hơn giữa provider (đổi từ OpenAI sang Anthropic nhiều khi chỉ đổi 1 dòng cấu hình).
- **Nhược điểm**: thêm 1 lớp abstraction nghĩa là thêm 1 lớp phải học, phải debug khi có lỗi (stack trace xuyên qua nhiều lớp framework trước khi tới code của bạn), thêm dependency phải theo dõi version/security patch. Framework thay đổi API nhanh — code viết theo 1 phiên bản có thể breaking ở phiên bản sau.
- **Dùng khi**: cần compose nhiều bước có sẵn pattern (RAG + tool + memory), team đã quen framework, hoặc cần đa provider trong cùng codebase. Cân nhắc kỹ nếu chỉ dùng 1 provider và ít tool — framework có thể là "phức tạp hoá không cần thiết" (over-engineering, đối lập với nguyên tắc senior là chọn giải pháp đơn giản nhất đáp ứng đủ yêu cầu).

### 3. MCP (Model Context Protocol)
MCP là chuẩn mở do Anthropic khởi xướng, **giải quyết một vấn đề khác hẳn với 2 mục trên**. MCP không phải "cách gọi tool" — nó là "cách CHIA SẺ và TÁI SỬ DỤNG tool qua nhiều client khác nhau, viết 1 lần, dùng ở nhiều nơi". Một MCP server (ví dụ expose tool truy vấn Superset) chạy như **một process độc lập**, giao tiếp với client qua transport chuẩn hoá (stdio khi client và server cùng máy, hoặc HTTP/SSE khi khác máy). Bất kỳ client hỗ trợ MCP — Claude Desktop, Claude Code, một IDE, hoặc 1 agent tự viết dùng MCP SDK — đều có thể "nói" với server đó mà không cần biết server viết bằng ngôn ngữ gì hay implement thế nào.

Ví tương đương hữu ích: MCP với AI tool giống như **LSP (Language Server Protocol)** với IDE. Trước LSP, mỗi IDE phải tự viết tích hợp riêng cho mỗi ngôn ngữ (VSCode viết 1 bộ hiểu Python, Sublime viết 1 bộ khác). LSP chuẩn hoá giao thức, để 1 language server viết 1 lần dùng được bởi bất kỳ editor nào hỗ trợ LSP. MCP làm điều tương tự cho tool/context của AI: viết 1 MCP server, dùng được bởi bất kỳ AI client nào hỗ trợ MCP, không phải viết lại integration riêng cho từng app AI.

**Điểm quan trọng nhất cần nhớ: MCP không thay thế tool-calling.** Bên dưới, khi Claude (hoặc client khác) gọi 1 tool qua MCP, cơ chế model-sinh-tool-call ở Phần 15 vẫn nguyên vẹn — MCP chỉ chuẩn hoá lớp **discover tool nào đang có** (server công bố danh sách tool + schema qua giao thức) và **cách gọi tool đó qua transport** (client gửi request MCP, server trả kết quả) giữa 2 process độc lập. Nói cách khác, MCP là 1 lớp giao thức nằm TRÊN tool-calling, không phải một cơ chế cạnh tranh với nó.

- **Ưu điểm**: tách biệt server (nơi implement tool, cần domain knowledge — ví dụ ai đó ở team Superset) khỏi client (nơi chạy agent/LLM) — server viết 1 lần, nhiều team/nhiều app dùng lại được. Chuẩn hoá auth, discovery, transport.
- **Nhược điểm**: thêm 1 process, 1 giao thức, 1 khái niệm mới phải học (server lifecycle, transport, session) — với 1 tool đơn giản dùng nội bộ 1 lần, đây là chi phí không cần thiết.
- **Dùng khi**: tool cần dùng lại bởi nhiều client khác nhau (nhiều team, nhiều app, hoặc cả người dùng cuối qua Claude Desktop lẫn agent nội bộ), hoặc muốn tách rõ quyền/logic truy cập 1 hệ thống (ví dụ Superset) ra khỏi code của từng app gọi nó.

### 4. OpenAPI-to-tool
Nếu đã có REST API với OpenAPI/Swagger spec, có thể tự sinh tool schema từ spec đó (nhiều thư viện và cả một số framework ở mục 2 hỗ trợ import trực tiếp OpenAPI spec thành tool definition) — không cần viết tay JSON Schema cho từng endpoint.

- **Ưu điểm**: nhanh nếu đã có API hoàn chỉnh — tận dụng lại spec đã có, không cần định nghĩa 2 lần.
- **Nhược điểm**: chất lượng tool description hoàn toàn phụ thuộc chất lượng OpenAPI spec gốc. Spec REST thường viết cho developer đọc (ngắn, kỹ thuật) — không được viết với tiêu chí "đủ rõ để LLM chọn đúng tool" như đã nói ở Phần 15 (không phân biệt use-case, không có ví dụ, description generic kiểu "Get resource by ID"). Sinh tool tự động từ spec kém sẽ tạo ra tool chất lượng kém, và endpoint REST design tốt cho human/service-to-service chưa chắc là tool design tốt cho LLM (ví dụ REST có xu hướng chia nhỏ endpoint theo resource, nhưng LLM có thể cần 1 tool tổng hợp nhiều bước để giảm số lần gọi).
- **Dùng khi**: đã có REST API nội bộ chất lượng tốt, cần expose nhanh cho agent, và sẵn sàng review/viết lại description sau khi sinh tự động — không nên dùng thẳng kết quả sinh tự động mà không kiểm tra.

### Bảng so sánh nhanh

| Tiêu chí | Function calling thuần | Framework (LangChain/LlamaIndex) | MCP | OpenAPI-to-tool |
|---|---|---|---|---|
| Giải quyết vấn đề gì | Gọi tool cơ bản | Compose nhiều bước/agent | Tái sử dụng tool qua nhiều client | Tận dụng API có sẵn |
| Độ phức tạp thêm vào | Thấp nhất | Trung bình-cao | Trung bình (thêm process/transport) | Thấp (nếu spec tốt) |
| Phù hợp khi | Ít tool, 1 provider | Nhiều bước, đa provider | Tool dùng lại bởi nhiều app/team | Đã có REST API tốt |
| Rủi ro chính | Tự viết lại nhiều logic | Lock-in framework, debug khó | Thêm khái niệm mới, overhead cho use-case đơn giản | Chất lượng phụ thuộc spec gốc |

## Đối chiếu với code thật trong repo
`mcp-superset` là **một ví dụ triển khai theo hướng MCP** — không phải "cách đúng duy nhất" để expose tool cho Superset. Server viết bằng Python (thư viện `mcp`, cụ thể là FastMCP — xem [`core/server.py`](../../core/server.py)), expose các tool Python function thường trong [`tools/chart.py`](../../tools/chart.py), [`tools/dashboard.py`](../../tools/dashboard.py) qua decorator `@mcp.tool()`. Về nguyên tắc, cùng một bộ tool "quản lý chart/dashboard Superset" này có thể được viết theo bất kỳ 1 trong 4 cách ở trên: viết tay JSON Schema gọi thẳng REST API Superset (function calling thuần), bọc trong LangChain `Tool` class, hoặc sinh tool từ OpenAPI spec mà Superset tự công bố (Superset có expose Swagger/OpenAPI cho REST API của nó) — nếu spec đó đủ chi tiết. Lựa chọn MCP ở đây hợp lý vì mục tiêu là cho phép nhiều client khác nhau (Claude Desktop của người dùng cá nhân, Claude Code, agent nội bộ khác) cùng dùng lại bộ tool Superset này mà không phải viết lại tích hợp riêng — đúng vấn đề MCP giải quyết, không phải vì MCP "tốt hơn" các cách khác về mặt tool-calling.

## Thực hành
So sánh trực tiếp: cùng 1 tool định nghĩa theo 2 cách — function calling thuần (Anthropic) và OpenAI function calling — để thấy sự tương đồng về khái niệm (khác cú pháp field, giống bản chất).

```python
import json
import os
from anthropic import Anthropic
from openai import OpenAI

# --- Cùng 1 tool, khai báo theo 2 provider ---

TOOL_DEF_ANTHROPIC = {
    "name": "lookup_order_status",
    "description": "Tra cứu trạng thái đơn hàng theo mã đơn. Dùng khi khách hỏi 'đơn của tôi tới đâu rồi'.",
    "input_schema": {
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "Mã đơn hàng, ví dụ 'ORD-12345'"}},
        "required": ["order_id"],
    },
}

TOOL_DEF_OPENAI = {
    "type": "function",
    "function": {
        "name": "lookup_order_status",
        "description": "Tra cứu trạng thái đơn hàng theo mã đơn. Dùng khi khách hỏi 'đơn của tôi tới đâu rồi'.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Mã đơn hàng, ví dụ 'ORD-12345'"}},
            "required": ["order_id"],
        },
    },
}


def execute_tool(order_id: str) -> dict:
    return {"order_id": order_id, "status": "đang giao", "eta_days": 2}


def call_anthropic(question: str):
    client = Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=512,
        tools=[TOOL_DEF_ANTHROPIC],
        messages=[{"role": "user", "content": question}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            print("[Anthropic] tool_use:", block.name, block.input)


def call_openai(question: str):
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        tools=[TOOL_DEF_OPENAI],
        messages=[{"role": "user", "content": question}],
    )
    msg = resp.choices[0].message
    if msg.tool_calls:
        for tc in msg.tool_calls:
            print("[OpenAI] tool_call:", tc.function.name, tc.function.arguments)


if __name__ == "__main__":
    question = "Đơn ORD-12345 của tôi tới đâu rồi?"
    if os.getenv("ANTHROPIC_API_KEY"):
        call_anthropic(question)
    if os.getenv("OPENAI_API_KEY"):
        call_openai(question)
```

Quan sát: cấu trúc JSON Schema mô tả tham số (`type`, `properties`, `required`) giống nhau ở cả hai — khác nhau chủ yếu ở tên field bọc ngoài (`input_schema` vs `function.parameters`) và cách response trả về (`content` blocks vs `tool_calls` list). Đây chính là minh chứng "tool-calling là cơ chế chung" đã nói ở Phần 15.

## Bài tập tự làm
1. Tự liệt kê 1 bài toán thật bạn từng gặp ở công ty (ví dụ: tool tra cứu thông tin nhân sự, tool tạo báo cáo). Với bài toán đó, viết ra lý do cụ thể chọn 1 trong 4 cách ở trên — không chọn MCP mặc định, phải giải thích được vì sao KHÔNG chọn 3 cách còn lại.
2. Tìm 1 OpenAPI spec công khai (ví dụ của một API bạn quen thuộc), đọc description của 2-3 endpoint, tự đánh giá: mô tả đó có đủ tốt để làm tool description cho LLM không? Nếu không, viết lại description đó theo tiêu chí Phần 15.
3. Nếu có thời gian, cài thử `mcp-superset` (xem README repo) và dùng MCP Inspector (`test-inspector.bat` trong repo) để quan sát danh sách tool được discover qua giao thức MCP — so sánh với việc gọi trực tiếp 1 hàm Python trong `tools/chart.py` không qua MCP.
4. Viết 1 đoạn (5-8 câu) phản biện quan điểm "cứ dùng MCP cho mọi tool vì đó là chuẩn mới nhất" — nêu rõ ít nhất 2 tình huống MCP là lựa chọn tệ.

## Đào sâu / nâng cao

### MCP: resources và prompts, không chỉ tools
MCP không chỉ chuẩn hoá tool — giao thức còn có khái niệm "resources" (dữ liệu server expose cho client đọc, không phải hành động) và "prompts" (template prompt server gợi ý cho client). Phần lớn thảo luận về MCP tập trung vào tool vì đó là phần liên quan trực tiếp tool-calling, nhưng khi đọc spec chính thức, đừng nhầm "MCP" với "chỉ là tool-calling qua giao thức khác".

### Chi phí vận hành thêm của MCP: process và transport
Một MCP server là 1 process sống độc lập (hoặc 1 HTTP service). Điều này kéo theo bài toán vận hành mới không tồn tại ở function calling thuần: server phải được deploy, theo dõi uptime, xử lý version mismatch giữa client/server, và (quan trọng cho Phần 20) quản lý auth qua transport riêng — khác hẳn việc chỉ gọi thẳng 1 hàm Python trong cùng process.

### Framework lock-in và tốc độ thay đổi API
LangChain/LlamaIndex thay đổi API tương đối nhanh giữa các phiên bản major — code viết theo 1 tutorial cũ có thể không chạy được với version mới nhất mà không sửa. Khi đánh giá "dùng framework có đáng không", tính luôn chi phí bảo trì dài hạn này, không chỉ tốc độ viết code lúc đầu.

### Không có "chuẩn duy nhất sẽ thắng"
Đừng học Phần 16 với tư duy "1 trong 4 cách này sẽ trở thành chuẩn duy nhất trong tương lai". Cả 4 vẫn tồn tại song song vì giải quyết vấn đề khác nhau ở layer khác nhau — hoàn toàn hợp lý khi 1 hệ thống dùng cả MCP (cho tool tái sử dụng liên team) VÀ function calling thuần (cho 1 tool nội bộ chỉ 1 app dùng) trong cùng kiến trúc.

## Bài tập senior
Sếp yêu cầu: "chuyển hết tool nội bộ hiện tại (viết bằng function calling thuần trong 3 microservice khác nhau) sang MCP vì nghe nói đó là tương lai". Bạn được giao đánh giá đề xuất này trước khi triển khai. Viết ra: (1) câu hỏi bạn sẽ hỏi lại để hiểu rõ động lực thật (có phải vì cần chia sẻ tool giữa nhiều team/app, hay chỉ vì hype), (2) trường hợp cụ thể nào chuyển sang MCP THỰC SỰ mang lại lợi ích đo được, (3) trường hợp nào nên giữ nguyên và lý do chi phí/lợi ích không đủ để đổi.

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được MCP giải quyết vấn đề "chia sẻ/tái sử dụng tool qua nhiều client", không phải "cách gọi tool".
- [ ] Nêu được ưu/nhược của cả 4 cách gắn tool mà không cần tra lại tài liệu.
- [ ] Biết dùng ví dụ so sánh Anthropic/OpenAI function calling để thấy phần chung (tool-calling) và phần khác (cú pháp provider).
- [ ] Đưa ra được 1 quyết định "không dùng MCP" có lý do rõ ràng cho 1 bài toán cụ thể.
