# Ngày 18 — Memory cho agent: ngắn hạn, dài hạn, và khi nào không cần memory

## Mục tiêu hôm nay
Phân biệt short-term memory (context window) và long-term memory (lưu trữ ngoài, qua session), và rèn thói quen senior quan trọng nhất của ngày này: **biết khi nào KHÔNG cần xây long-term memory** — vì đây là chỗ dev dễ bị FOMO thêm hệ thống phức tạp không cần thiết.

## Đọc trước
- [Anthropic — Context windows](https://docs.anthropic.com/) — phần giải thích context window và giới hạn token.
- [OpenAI — Function calling / context](https://platform.openai.com/docs/) — phần liên quan tới quản lý lịch sử hội thoại nhiều lượt.
- Tài liệu vector database bạn đã học ở Ngày 9 (`day9-vector-db.md` trong repo này) — memory dài hạn dạng semantic search dùng lại đúng khái niệm đó, không phải kỹ thuật mới.

## Khái niệm cốt lõi

### Short-term memory = context window, không có gì bí ẩn hơn
"Short-term memory" của agent, trong 1 conversation, **chính là** nội dung đang nằm trong context window gửi lên model ở mỗi lượt gọi — toàn bộ lịch sử message (user, assistant, tool_use, tool_result) tích lũy từ đầu conversation tới hiện tại. Không có "bộ nhớ" nào khác tồn tại giữa các lượt gọi model — model là stateless, mỗi API call độc lập hoàn toàn, chỉ "nhớ" được gì nằm trong chính request đó.

Hệ quả trực tiếp: conversation dài dần sẽ khiến context window đầy dần, kéo theo 2 vấn đề đã học ở Ngày 2 (context window, token cost) — chi phí tăng theo token gửi lên mỗi lượt (kể cả phần lịch sử cũ không đổi vẫn tính tiền lại mỗi lần, trừ khi dùng prompt caching), và chất lượng có thể giảm khi context quá dài (hiện tượng model "bỏ sót" chi tiết ở giữa context dài — "lost in the middle"). Đây là lý do nhiều hệ thống agent phải **quản lý chủ động** short-term memory: cắt bớt lịch sử cũ, tóm tắt (summarize) các đoạn hội thoại đã qua, hoặc chỉ giữ lại N lượt gần nhất + 1 bản tóm tắt của phần cũ hơn.

### Long-term memory = lưu trữ ngoài context, tồn tại qua nhiều session
Long-term memory là khi thông tin cần "nhớ" **vượt quá** 1 lần conversation — ví dụ: agent hỗ trợ khách hàng cần nhớ lịch sử tương tác của khách đó từ lần trước (session khác, ngày khác), hoặc agent trợ lý cá nhân cần nhớ sở thích người dùng đã nói cách đây 2 tuần. Về kỹ thuật, long-term memory luôn cần 1 lớp lưu trữ ngoài (database, vector store, file) và 1 bước **retrieval** để lấy lại đúng phần thông tin liên quan, chèn vào context window của session hiện tại trước khi gọi model — bản chất là biến "memory" thành 1 dạng RAG (đã học Tuần 2): query hiện tại → tìm thông tin liên quan trong storage → nhúng vào prompt.

Có 2 dạng lưu trữ long-term memory phổ biến:
- **Structured (database truyền thống)**: lưu fact có cấu trúc rõ (tên, sở thích, lịch sử đơn hàng) — truy vấn bằng key/filter thông thường, không cần embedding.
- **Unstructured/semantic (vector store)**: lưu đoạn hội thoại/fact dạng text tự do, truy vấn bằng similarity search (giống RAG) khi không biết trước fact sẽ được hỏi lại theo cách diễn đạt nào.

Nhiều hệ thống dùng kết hợp cả hai — fact rõ ràng (tên, ID khách hàng) lưu structured, còn "tóm tắt ngữ cảnh trò chuyện trước" lưu dạng semantic để truy xuất linh hoạt hơn.

### Khi nào THỰC SỰ cần long-term memory
Cần long-term memory khi có **ít nhất một** trong các điều kiện:
1. Sản phẩm yêu cầu tính liên tục **qua nhiều session tách biệt** — ví dụ trợ lý cá nhân phải nhớ giữa 2 lần mở app cách nhau vài ngày, mỗi lần là 1 conversation mới (context window mới, rỗng).
2. Lượng thông tin cần nhớ vượt quá khả năng chứa hợp lý của context window ngay trong **1 session dài** (ví dụ agent xử lý 1 case hỗ trợ kéo dài nhiều giờ, tích lũy hàng trăm lượt tương tác) — tới mức việc giữ toàn bộ trong context window trở nên quá tốn token hoặc vượt giới hạn cứng của model.
3. Cần **tra cứu chọn lọc** một phần nhỏ trong lượng thông tin lớn (ví dụ tra lại 1 fact cụ thể từ hàng nghìn tương tác trước) — đây chính là bài toán retrieval, không phải "nhớ tất cả".

### Khi nào long-term memory là THỪA — dev hay FOMO thêm nhầm
Đây là phần quan trọng nhất của ngày học: rất nhiều team thêm "memory system" (thường là vector store + pipeline lưu/truy xuất phức tạp) vào agent chỉ vì nghe nói agent "cần có trí nhớ", trong khi:

- **Task chỉ diễn ra trong 1 session ngắn, context window hiện tại (128K-1M+ token tuỳ model) đã đủ chứa toàn bộ lịch sử cần thiết.** Nếu 1 conversation hỗ trợ khách hàng chỉ kéo dài 20-30 lượt, không cần gì hơn ngoài giữ nguyên lịch sử trong context — thêm vector store để "nhớ" cùng session là dư thừa, chỉ tạo thêm độ trễ (round-trip tới vector store) và điểm lỗi mới (store down, embedding lỗi, kết quả retrieval không liên quan).
- **Thông tin cần dùng lại có thể lấy trực tiếp từ hệ thống nguồn (database nghiệp vụ) thay vì "nhớ" qua agent memory.** Ví dụ: không cần agent "nhớ" đơn hàng khách đã hỏi tuần trước bằng vector store riêng — chỉ cần query thẳng bảng `orders` trong DB nghiệp vụ theo `customer_id`, đó là dữ liệu **có cấu trúc, đã có nguồn sự thật (source of truth)** — dùng memory system riêng để "nhớ lại" thứ đã có sẵn trong DB là trùng lặp không cần thiết và tạo ra 2 nguồn sự thật cho cùng 1 dữ liệu (rủi ro lệch dữ liệu).
- **"Retrieval" bị nhầm thành "memory" khi bài toán thực chất chỉ là RAG thông thường trên tài liệu tĩnh** (đã học Tuần 2) — không có yếu tố "nhớ lại điều đã xảy ra trong quá khứ với người dùng cụ thể này", chỉ là tra cứu tài liệu chung. Gọi nhầm tên dẫn tới thiết kế nhầm (cố lưu theo session/user trong khi dữ liệu không phụ thuộc user).
- **Task một lần, không lặp lại** (ví dụ agent chạy 1 báo cáo rồi kết thúc, không có "session sau") — không có khái niệm long-term ở đây vì không có "term" dài hơn 1 lần chạy để nhớ.

Nguyên tắc thực dụng: trước khi thiết kế bất kỳ memory system, tự hỏi "nếu tôi chỉ dùng context window của 1 session + query trực tiếp DB nghiệp vụ khi cần, task có giải quyết được không?" — nếu có, đừng thêm gì hơn. Chỉ thêm long-term memory chuyên dụng khi câu trả lời rõ ràng là không.

## Đối chiếu với code thật trong repo
`mcp-superset` không triển khai bất kỳ memory layer nào — và đây là quyết định đúng theo nguyên tắc trên, không phải thiếu sót. Server là 1 MCP tool provider: mỗi tool call (ví dụ `superset_chart_list` trong [`tools/chart.py`](../../tools/chart.py)) là 1 request độc lập, không cần "nhớ" gì giữa các lần gọi — trạng thái cần thiết (danh sách chart, dashboard hiện tại) luôn lấy trực tiếp từ Superset (source of truth thật), không lưu cache hay "nhớ lại" ở phía server. `SupersetContext` trong [`core/context.py`](../../core/context.py) chỉ giữ 1 HTTP client dùng chung (tối ưu kết nối, không phải memory) và không lưu bất kỳ state theo user/session nào — đúng với nguyên tắc "nếu dữ liệu có nguồn sự thật rõ ràng ở hệ thống khác, không cần agent tự nhớ lại nó". Nếu 1 ngày cần agent "nhớ" ví dụ sở thích trình bày dashboard của 1 người dùng qua nhiều lần hỏi khác nhau, đó mới là lúc cần xét thêm long-term memory — nhưng hiện repo không có nhu cầu đó nên không có, và không nên thêm "phòng khi cần".

## Thực hành
Minh hoạ sự khác biệt giữa (a) chỉ dùng context window, và (b) cần retrieval long-term thật — bằng 1 ví dụ tối giản dùng SQLite làm long-term store có cấu trúc (không cần vector store nếu fact có cấu trúc rõ, đúng nguyên tắc "chọn structured trước khi chọn semantic"):

```python
import sqlite3
import json
from anthropic import Anthropic

client = Anthropic()
DB_PATH = "agent_memory.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS user_facts (
            user_id TEXT, fact_key TEXT, fact_value TEXT,
            PRIMARY KEY (user_id, fact_key)
        )"""
    )
    conn.commit()
    return conn


def remember_fact(conn, user_id: str, key: str, value: str):
    """Long-term memory: fact có cấu trúc, lưu qua session, không phải vector store
    vì đây là key-value rõ ràng, không cần semantic search."""
    conn.execute(
        "INSERT OR REPLACE INTO user_facts (user_id, fact_key, fact_value) VALUES (?, ?, ?)",
        (user_id, key, value),
    )
    conn.commit()


def recall_facts(conn, user_id: str) -> dict:
    rows = conn.execute(
        "SELECT fact_key, fact_value FROM user_facts WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {k: v for k, v in rows}


def run_session(conn, user_id: str, user_message: str):
    # Bước retrieval: lấy fact liên quan từ long-term store, KHÔNG lấy toàn bộ lịch sử chat
    facts = recall_facts(conn, user_id)
    system_prompt = (
        "Bạn là trợ lý hỗ trợ khách hàng. "
        f"Thông tin đã biết về khách hàng này (từ lần trước): {json.dumps(facts, ensure_ascii=False)}"
        if facts
        else "Bạn là trợ lý hỗ trợ khách hàng. Chưa có thông tin về khách hàng này."
    )

    # Short-term memory: chỉ là list message trong CHÍNH session này, không lưu gì thêm
    messages = [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=512,
        system=system_prompt,
        messages=messages,
    )
    answer = "".join(b.text for b in response.content if b.type == "text")
    print(f"[session cho {user_id}] {answer}")
    return answer


if __name__ == "__main__":
    conn = init_db()
    # Session 1 (ngày hôm nay): khách nói sở thích -> lưu vào long-term
    remember_fact(conn, "user-42", "preferred_language", "tiếng Việt")
    remember_fact(conn, "user-42", "plan_tier", "enterprise")

    # Session 2 (giả lập: mở lại app vào ngày khác, context window RỖNG hoàn toàn)
    run_session(conn, "user-42", "Chào, tôi cần hỗ trợ về hoá đơn.")
```

Chạy và quan sát: `run_session` không có bất kỳ lịch sử chat cũ nào trong `messages`, nhưng model vẫn "biết" thông tin khách hàng nhờ bước `recall_facts` — đây là long-term memory đúng nghĩa, tách biệt hoàn toàn khỏi short-term (context window của session hiện tại).

## Bài tập tự làm
1. Thêm 1 hàm `summarize_and_trim(messages, max_tokens)` cắt lịch sử hội thoại khi vượt ngưỡng token — giữ N message gần nhất nguyên văn, gọi model tóm tắt phần còn lại thành 1 message hệ thống duy nhất. Đây là quản lý short-term memory chủ động, không phải long-term.
2. Viết ra 3 ví dụ thực tế ở công ty bạn nơi long-term memory THỰC SỰ cần (theo 3 điều kiện đã nêu) và 3 ví dụ nơi long-term memory sẽ là dư thừa (theo các trường hợp FOMO đã nêu) — mỗi ví dụ giải thích 1 câu vì sao.
3. Sửa ví dụ thực hành để dùng vector store thay vì SQLite cho 1 trường hợp cụ thể: lưu tóm tắt tự do (không phải key-value) của 5 cuộc hội thoại trước với 1 khách hàng, sau đó retrieval theo similarity với câu hỏi mới — so sánh độ phức tạp thêm vào so với bản SQLite key-value.
4. Đo thử: với model bạn đang dùng, context window tối đa là bao nhiêu token? Tính xem 1 cuộc hội thoại hỗ trợ khách hàng trung bình (ước lượng số lượt, số token/lượt) có thực sự cần cắt/tóm tắt hay còn dư nhiều so với giới hạn — số liệu thật giúp tránh tối ưu sớm không cần thiết.

## Đào sâu / nâng cao

### Prompt caching và short-term memory
Nhiều provider (bao gồm Anthropic) hỗ trợ prompt caching — phần đầu context (system prompt, tool schema, phần lịch sử ổn định) có thể được cache ở phía provider để giảm chi phí/latency cho các lượt gọi tiếp theo trong cùng conversation, thay vì phải tính lại toàn bộ. Đây là tối ưu ở tầng short-term memory, không phải long-term — liên hệ trực tiếp Ngày 24 (cost engineering).

### Memory "consolidation" — rủi ro hay bị bỏ qua
Khi hệ thống liên tục ghi fact mới vào long-term store (ví dụ mỗi session lại tự động "học" thêm điều gì về người dùng), cần cơ chế xử lý fact mâu thuẫn/lỗi thời (ví dụ khách đổi `plan_tier` nhưng fact cũ không bị xoá, agent sau đó trả lời dựa trên fact sai). Đây là bài toán "cập nhật/consolidate" thường bị bỏ qua khi thiết kế memory system — không chỉ là "ghi thêm", mà phải có chiến lược ghi đè/hết hạn.

### Ranh giới giữa "memory" và "RAG trên dữ liệu do chính agent tạo ra"
Nhiều hệ thống gọi là "agent memory" thực chất là RAG (Tuần 2) áp trên 1 tập dữ liệu đặc biệt: lịch sử hội thoại/hành động do chính agent đó tạo ra trước đây, thay vì tài liệu tĩnh bên ngoài. Về kỹ thuật retrieval (embedding, chunking, similarity search) không khác gì RAG thông thường — chunking chiến lược sai (Ngày 10) gây lỗi retrieval giống hệt cách nó gây lỗi RAG tài liệu.

### Memory theo scope: user, session, hay global
Khi thiết kế long-term memory, phải quyết định rõ fact thuộc scope nào — riêng 1 user, riêng 1 session cụ thể của user đó, hay dùng chung toàn hệ thống (ví dụ fact nghiệp vụ không đổi theo user). Nhầm scope là lỗi thiết kế phổ biến: lưu fact lẽ ra thuộc `user_id` cụ thể vào 1 store chung khiến agent trả lời dựa trên fact của người khác.

## Bài tập senior
Team bạn đang xây agent hỗ trợ nội bộ trả lời câu hỏi về quy trình nghỉ phép, và 1 dev đề xuất thêm "long-term memory bằng vector store" để agent "nhớ được lịch sử câu hỏi của từng nhân viên qua nhiều lần hỏi". Bạn nghi ngờ đây là over-engineering. Viết ra: (1) 3-4 câu hỏi bạn sẽ hỏi lại dev đó để xác định liệu có thực sự cần long-term memory hay chỉ cần context window session hiện tại + query thẳng hệ thống HR, (2) nếu sau khi hỏi vẫn xác nhận cần "nhớ" điều gì đó qua session, đề xuất phương án tối giản nhất (structured store trước, vector store chỉ khi thật cần semantic search) thay vì đi thẳng vào giải pháp phức tạp nhất.

## Checklist trước khi qua Ngày kế
- [ ] Giải thích được short-term memory chỉ là context window, không có cơ chế "nhớ" nào khác trong 1 session.
- [ ] Phân biệt được structured long-term memory và semantic/vector long-term memory, biết khi nào chọn loại nào.
- [ ] Tự đưa ra được ít nhất 1 ví dụ thật nơi long-term memory là dư thừa và giải thích được vì sao.
- [ ] Biết cách kiểm tra "có thực sự cần long-term memory không" bằng câu hỏi thực dụng trước khi thiết kế.
