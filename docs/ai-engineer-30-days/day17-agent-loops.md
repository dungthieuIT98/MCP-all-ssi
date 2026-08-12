# Phần 17 — Agent loop: ReAct, planning, khi nào dừng

## Mục tiêu hôm nay
Hiểu cấu trúc vòng lặp agent (ReAct), 2 chiến lược lập kế hoạch, và các điều kiện dừng bắt buộc phải có trước khi agent chạy trong bất kỳ hệ thống thật — vì agent loop không kiểm soát là nguồn lỗi production phổ biến nhất của kiến trúc agent.

## Đọc trước
- Paper: "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., arxiv.org) — đọc ít nhất phần giới thiệu và ví dụ minh hoạ, không cần đọc hết phần thực nghiệm.
- [Anthropic — Tool use / building agents](https://docs.anthropic.com/) — phần liên quan tới vòng lặp nhiều bước (multi-step tool use).
- [OpenAI — Function calling](https://platform.openai.com/docs/) — phần ví dụ multi-turn.

## Khái niệm cốt lõi

### ReAct: Reasoning + Acting
ReAct là pattern (không phải 1 sản phẩm/thư viện cụ thể) mô tả cách 1 agent xen kẽ giữa 2 việc trong cùng 1 vòng lặp: **suy luận** (sinh ra một đoạn "reasoning" bằng ngôn ngữ tự nhiên về việc nên làm gì tiếp) và **hành động** (gọi 1 tool cụ thể dựa trên suy luận đó), rồi quan sát kết quả hành động (observation) để suy luận tiếp cho bước sau. Vòng lặp cơ bản:

```
Thought: (model tự giải thích lý do, có thể ở dạng text trước tool_use, hoặc extended thinking)
Action: (tool_use — gọi 1 tool cụ thể với input cụ thể)
Observation: (tool_result — kết quả thực thi tool, do CODE trả về, không phải model tự tưởng tượng)
Thought: (dựa trên observation, suy luận bước tiếp theo)
Action: ...
...
Final Answer: (model trả lời, không còn tool_use)
```

Điểm giá trị của ReAct so với "chỉ gọi tool 1 lần rồi trả lời" (single-step tool use, đã thấy ở Phần 15): agent có thể **thích nghi giữa các bước** — quan sát kết quả 1 tool call rồi quyết định bước tiếp theo dựa trên kết quả đó, chứ không phải lên kế hoạch cứng từ đầu và làm y nguyên. Đây là khác biệt giữa "gọi tool" (Phần 15, có thể chỉ 1 vòng) và "agent" (nhiều vòng, có trạng thái tích lũy qua các bước).

Về mặt kỹ thuật, ReAct không cần cơ chế đặc biệt gì ngoài tool-calling đã học — nó chỉ là **cùng 1 vòng lặp tool-use (Phần 15) được chạy nhiều lần liên tục**, với lịch sử hội thoại tích lũy dần các cặp Action/Observation. Model "reasoning" chỉ là text model sinh ra trước hoặc cùng lúc với tool_use — với các model hỗ trợ extended thinking/reasoning tokens, phần suy luận này có thể tách riêng khỏi phần trả lời cuối, nhưng bản chất vòng lặp bên ngoài không đổi.

### Planning: task decomposition trước vs plan-as-you-go
Có 2 chiến lược chính để agent xử lý task nhiều bước:

1. **Task decomposition trước (plan-then-execute)**: agent (thường bằng 1 lời gọi model riêng, hoặc 1 bước reasoning đầu tiên) sinh ra toàn bộ kế hoạch nhiều bước NGAY TỪ ĐẦU trước khi hành động bước nào — ví dụ "Bước 1: tra cứu X. Bước 2: dùng kết quả X tính Y. Bước 3: tổng hợp báo cáo." Sau đó thực thi lần lượt theo kế hoạch, có thể điều chỉnh khi 1 bước thất bại nhưng khung kế hoạch tổng giữ nguyên.
   - **Ưu điểm**: dễ audit (có thể hiển thị kế hoạch cho người dùng duyệt trước khi chạy — quan trọng cho task có side-effect), dễ ước lượng chi phí/thời gian trước khi chạy, giảm khả năng lặp vô nghĩa vì đã có khung rõ.
   - **Nhược điểm**: kế hoạch lập từ đầu có thể sai nếu thông tin quan trọng chỉ lộ ra sau khi thực thi 1 vài bước đầu — cứng nhắc với task cần thích nghi cao.

2. **Plan-as-you-go (ReAct thuần)**: agent không lập kế hoạch tổng trước, mà quyết định từng bước một dựa trên observation của bước ngay trước — đúng như vòng lặp ReAct ở trên.
   - **Ưu điểm**: thích nghi tốt với task mà bước sau phụ thuộc chặt vào kết quả thật của bước trước (không đoán được trước), linh hoạt hơn.
   - **Nhược điểm**: khó audit trước khi chạy (không biết agent sẽ làm gì cho tới khi chạy xong), khó ước lượng chi phí, và **dễ rơi vào lặp vô nghĩa hơn** vì không có khung tổng để đối chiếu "mình đã đi đúng hướng chưa".

Trong thực tế, nhiều hệ thống agent production dùng kết hợp: lập kế hoạch tổng ở mức thô (vài bước lớn) rồi để từng bước lớn tự thích nghi chi tiết bên trong theo kiểu ReAct.

### Điều kiện dừng — bắt buộc phải có, không phải "nice to have"
Một agent loop không có điều kiện dừng rõ ràng là một hệ thống production không an toàn — vì đầu vào (câu hỏi người dùng, dữ liệu tool trả về) không nằm trong tầm kiểm soát của bạn, model có thể rơi vào trạng thái không tự nhận ra là nên dừng. Các điều kiện dừng bắt buộc:

- **Max iteration**: giới hạn cứng số vòng lặp (ví dụ tối đa 10-15 lượt gọi tool cho 1 request). Đây là lưới an toàn cuối cùng — không phải cơ chế dừng "thông minh", chỉ là chặn agent chạy vô hạn khi mọi cơ chế khác thất bại.
- **Model tự báo "done"**: cách dừng "tự nhiên" nhất — model trả về text thuần (không còn tool_use) khi tự xác định đã đủ thông tin trả lời. Đây là điều kiện dừng chính trong vận hành bình thường, nhưng không được là điều kiện DUY NHẤT vì model có thể sai (tiếp tục gọi tool khi đã đủ thông tin, hoặc dừng quá sớm khi chưa đủ).
- **Cost/time budget**: giới hạn theo token đã tiêu tốn (tổng input+output token cộng dồn qua các vòng) hoặc thời gian thực đã trôi qua (wall-clock timeout) — quan trọng hơn max iteration ở hệ thống có tool call tốn kém khác nhau (1 tool gọi DB nhanh, 1 tool gọi web search chậm) vì max iteration không phản ánh đúng chi phí thật.
- **Không tiến triển (no-progress detection)**: phát hiện agent lặp lại cùng 1 hành động — loại lỗi rất thường gặp là **agent gọi lại đúng 1 tool với đúng input đã thử trước đó**, thường xảy ra khi tool trả lỗi hoặc kết quả không như model "mong đợi" và model không có cách nào khác ngoài thử lại y nguyên. Cách phát hiện: so sánh (tên tool, input đã normalize) của lượt hiện tại với lịch sử các lượt trước trong cùng request; nếu trùng quá N lần liên tiếp, chặn vòng lặp và trả lỗi/yêu cầu người dùng can thiệp thay vì để agent tự "cố gắng" vô nghĩa.

### Vì sao agent loop dễ chạy vô hạn hoặc lặp vô nghĩa
- Model không có "bộ nhớ" về việc nó đã thử gì trừ khi lịch sử đó còn nằm trong context hiện tại — nếu context bị cắt/tóm tắt (do quá dài, xem Phần 18) và mất chi tiết "đã thử input X, bị lỗi Y", model có thể lặp lại chính xác input đã thất bại.
- Tool trả lỗi mơ hồ (chỉ "Error" không giải thích tại sao) khiến model không có tín hiệu để đổi chiến lược — nó chỉ có 2 lựa chọn: thử input khác (nếu đoán được lý do lỗi) hoặc thử lại y nguyên (nếu không đoán được) — và không phải lúc nào model cũng chọn đúng.
- Task người dùng đưa ra mơ hồ hoặc không thể hoàn thành với bộ tool hiện có — agent tiếp tục thử các tool khác nhau vô định vì không có cơ chế nào cho phép nó "báo cáo thất bại và dừng" một cách rõ ràng (nếu prompt không hướng dẫn rõ khi nào nên từ bỏ).

## Đối chiếu với code thật trong repo
`mcp-superset` bản thân chỉ là 1 MCP server (nơi tool được định nghĩa và thực thi) — vòng lặp agent (bên gọi model, quyết định thực thi bao nhiêu vòng) nằm ở phía **client** (Claude Desktop, Claude Code, hoặc 1 agent tự viết dùng MCP client SDK), không phải trong code của repo này. Điều này minh họa một điểm quan trọng: điều kiện dừng của agent loop KHÔNG PHẢI trách nhiệm của tool/MCP server — server chỉ trả kết quả (hoặc lỗi) khi được gọi, ví dụ [`utils/decorators.py`](../../utils/decorators.py) hàm `handle_api_errors` (dòng 33-51) đảm bảo mọi lỗi từ Superset trả về dưới dạng `{"error": "..."}` có message rõ ràng (kèm tên hàm và exception message) thay vì để exception rơi thẳng ra ngoài — đây góp phần giảm nguy cơ agent lặp vô nghĩa (theo mục "tool trả lỗi mơ hồ" ở trên), vì client/model nhận được tín hiệu lỗi cụ thể để đổi chiến lược, nhưng bản thân việc "có nên dừng hay thử tool khác" là quyết định của agent loop ở phía client, nằm ngoài phạm vi repo.

## Thực hành
Cài đặt 1 agent loop ReAct tối giản với giới hạn dừng đầy đủ (max iteration, no-progress detection), dùng Anthropic SDK:

```python
import hashlib
import json
import time
from anthropic import Anthropic

client = Anthropic()

MAX_ITERATIONS = 8
MAX_SECONDS = 60
MAX_SAME_CALL_REPEAT = 2  # chặn nếu gọi đúng (tool, input) này quá N lần


def normalize_call(name: str, tool_input: dict) -> str:
    """Tạo khoá so sánh để phát hiện lặp lại y nguyên 1 tool call."""
    canon = json.dumps(tool_input, sort_keys=True)
    return hashlib.sha256(f"{name}:{canon}".encode()).hexdigest()


def search_docs(query: str) -> dict:
    # Giả lập: luôn trả "không tìm thấy" để minh hoạ agent có thể bị kẹt
    return {"query": query, "found": False, "reason": "no matching document"}


TOOLS = [
    {
        "name": "search_docs",
        "description": "Tìm tài liệu nội bộ theo từ khoá. Trả found=false nếu không có kết quả — KHÔNG thử lại với y nguyên từ khoá, hãy đổi từ khoá hoặc báo không tìm được.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    }
]


def run_agent(user_message: str):
    messages = [{"role": "user", "content": user_message}]
    call_history = []  # danh sách các khoá normalize_call đã thực thi
    start = time.monotonic()

    for iteration in range(1, MAX_ITERATIONS + 1):
        if time.monotonic() - start > MAX_SECONDS:
            return {"status": "stopped", "reason": "time_budget_exceeded", "iteration": iteration}

        response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            final_text = "".join(b.text for b in response.content if b.type == "text")
            return {"status": "done", "answer": final_text, "iteration": iteration}

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            call_key = normalize_call(block.name, block.input)
            repeat_count = call_history.count(call_key)
            call_history.append(call_key)

            if repeat_count >= MAX_SAME_CALL_REPEAT:
                # Phát hiện lặp vô nghĩa: đúng tool + đúng input đã thử >= N lần
                return {
                    "status": "stopped",
                    "reason": "no_progress_detected",
                    "detail": f"{block.name} lặp lại với input giống hệt {repeat_count + 1} lần",
                    "iteration": iteration,
                }

            result = search_docs(**block.input) if block.name == "search_docs" else {"error": "unknown tool"}
            tool_results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)}
            )

        messages.append({"role": "user", "content": tool_results})

    return {"status": "stopped", "reason": "max_iteration_reached", "iteration": MAX_ITERATIONS}


if __name__ == "__main__":
    result = run_agent("Tìm tài liệu hướng dẫn cấu hình VPN nội bộ, thử nhiều cách diễn đạt nếu cần.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

Chạy thử và quan sát: vì `search_docs` luôn trả `found: False`, agent có xu hướng thử lại — bài tập là kiểm chứng `no_progress_detected` có kích hoạt đúng lúc.

## Bài tập tự làm
1. Chạy code thực hành trên, giảm `MAX_SAME_CALL_REPEAT` xuống 1 và tăng lên 3, quan sát khác biệt hành vi dừng.
2. Sửa `search_docs` để trả kết quả khác nhau (không phải luôn `found: False`) dựa trên từ khoá — quan sát agent có tự dừng đúng cách khi tìm được kết quả không, so với khi không bao giờ tìm được.
3. Thêm 1 bộ đếm token cộng dồn qua các iteration (dùng `response.usage.input_tokens` + `output_tokens` trả về trong mỗi response) và thêm điều kiện dừng theo tổng token vượt ngưỡng — đây là "cost budget" thay vì chỉ "time budget".
4. Viết lại `run_agent` theo kiểu plan-then-execute: thêm 1 lời gọi model đầu tiên chỉ để sinh danh sách bước dự kiến (không gọi tool), in ra kế hoạch, rồi mới chạy vòng lặp ReAct cho từng bước — so sánh độ dễ audit với bản gốc.

## Đào sâu / nâng cao

### Extended thinking / reasoning tokens và ReAct
Một số model hỗ trợ sinh "thinking" tách riêng khỏi output cuối (không phải text hiển thị cho người dùng). Về mặt vòng lặp agent, đây không thay đổi bản chất ReAct — phần "Thought" vẫn tồn tại, chỉ khác là được model xử lý ở 1 kênh riêng trước khi quyết định Action, có thể giúp quyết định tool tốt hơn nhưng không tự động giải quyết vấn đề lặp vô nghĩa nếu observation không đủ tín hiệu.

### Circuit breaker pattern áp cho agent
Khái niệm circuit breaker từ backend truyền thống (ngắt mạch khi 1 dependency lỗi liên tục) áp dụng trực tiếp cho agent: nếu 1 tool cụ thể lỗi N lần liên tiếp trong cùng request (không chỉ input giống nhau, mà bất kỳ input nào tới tool đó), có thể tạm loại tool đó khỏi danh sách tool active cho các vòng còn lại của request đó, buộc model tìm hướng khác hoặc báo thất bại rõ ràng hơn.

### Human-in-the-loop như một điều kiện dừng có chủ đích
Với task có side-effect quan trọng (xoá dữ liệu, gửi email ra ngoài, thực hiện giao dịch), điều kiện dừng nên bao gồm 1 checkpoint bắt buộc dừng lại chờ xác nhận người dùng trước khi model được tiếp tục vòng lặp — đây không phải "lỗi" mà là thiết kế chủ đích, liên hệ trực tiếp tới nguyên tắc least privilege ở Phần 20.

### Đo lường "tại sao agent dừng" như một metric
Ở hệ thống production, nên log lý do dừng của mọi request agent (done tự nhiên / max_iteration / no_progress / cost_budget / time_budget / human_stop) như 1 metric theo dõi liên tục — tỷ lệ dừng vì `max_iteration` hoặc `no_progress` tăng bất thường là tín hiệu sớm cho thấy tool description kém hoặc task người dùng đang vượt khả năng hệ thống, cần điều tra trước khi user complain.

## Bài tập senior
Hệ thống agent production của bạn có tỷ lệ 8% request bị dừng do `max_iteration_reached` (tăng từ 2% tuần trước) sau khi thêm 3 tool mới vào bộ tool hiện có (tổng cộng giờ có 22 tool active). Bạn được giao điều tra nguyên nhân và đề xuất fix, KHÔNG được chỉ đơn giản tăng `MAX_ITERATIONS` lên (vì đó không giải quyết nguyên nhân, chỉ trì hoãn). Viết ra quy trình điều tra bạn sẽ làm (log nào cần xem trước, giả thuyết nào cần kiểm chứng trước) và 2-3 hướng fix khả thi có đánh giá trade-off.

## Checklist trước khi qua Ngày kế
- [ ] Vẽ được (trên giấy hoặc mô tả bằng lời) vòng lặp Thought → Action → Observation không cần nhìn tài liệu.
- [ ] Giải thích được khác biệt plan-then-execute và plan-as-you-go, cho được ví dụ khi nào chọn cái nào.
- [ ] Tự viết được ít nhất 1 cơ chế phát hiện lặp vô nghĩa (không copy nguyên code mẫu).
- [ ] Liệt kê được tối thiểu 3 điều kiện dừng bắt buộc phải có trước khi đưa 1 agent loop lên production.
