# Ngày 11 — RAG pipeline đầy đủ: retrieve → rerank → generate

## Mục tiêu hôm nay
Ghép các khái niệm rời rạc của Ngày 8-10 (embedding, vector DB, chunking) thành một kiến trúc pipeline đầy đủ, và học cách nhìn ra những chỗ pipeline RAG dễ vỡ nhất trong thực tế — vì phần lớn demo RAG "chạy được" trên slide nhưng vỡ khi gặp câu hỏi thật.

## Đọc trước
- [Anthropic — RAG cookbook/guide](https://docs.anthropic.com/) (tìm mục retrieval-augmented generation trong docs Anthropic)
- [LangChain — RAG concepts](https://python.langchain.com/docs/concepts/rag/)
- [pgvector — GitHub README](https://github.com/pgvector/pgvector)

## Khái niệm cốt lõi

### Kiến trúc pipeline đầy đủ
RAG (Retrieval-Augmented Generation) có hai luồng tách biệt cần phân biệt rõ — nhầm lẫn hai luồng này là lỗi tư duy phổ biến khi mới học:

**Luồng ingest (offline, chạy khi có tài liệu mới hoặc cập nhật, không nằm trên đường request của user):**
1. **Ingest**: thu thập tài liệu nguồn (crawl web, đọc file, gọi API nội bộ).
2. **Chunk**: chia thành đoạn nhỏ theo chiến lược phù hợp (Ngày 10).
3. **Embed**: gọi model embedding, sinh vector cho mỗi chunk (Ngày 8).
4. **Store**: lưu vector + metadata (nguồn, vị trí trong tài liệu gốc, timestamp) vào vector DB/pgvector (Ngày 9).

**Luồng query (online, chạy mỗi khi user hỏi, nằm trên đường request — mọi bước ở đây cộng trực tiếp vào latency user cảm nhận được):**
5. **Retrieve**: embed câu hỏi của user, tìm top-k chunk gần nhất trong vector DB.
6. **(Rerank)**: dùng một model chuyên biệt (cross-encoder) sắp xếp lại top-k theo độ liên quan chính xác hơn (Ngày 12) — bước tuỳ chọn nhưng thường cải thiện chất lượng đáng kể.
7. **Augment prompt**: chèn các chunk đã chọn vào prompt gửi cho LLM, kèm hướng dẫn rõ (chỉ trả lời dựa trên context được cung cấp, cite nguồn nếu cần).
8. **Generate**: LLM sinh câu trả lời dựa trên context đã augment.

Điểm mà backend dev cần khắc sâu: **chất lượng của bước 8 (generate) bị chặn trên bởi chất lượng của bước 5-6 (retrieve/rerank)** — một LLM tốt nhất thế giới vẫn trả lời sai nếu context đưa vào sai hoặc thiếu. Đây là lý do phần lớn effort debug một hệ RAG production nên tập trung vào retrieval trước, không phải "prompt engineer thêm cho generate" — nếu retrieval trả về rác, không có prompt nào cứu được.

### Những chỗ dễ sai nhất trong thực tế

**Retrieval trả về đoạn không liên quan (nhưng similarity score vẫn "cao"):** Cosine similarity là một phép đo tương đối, không có ngưỡng tuyệt đối "đây là liên quan" — một câu hỏi rất khác biệt với toàn bộ corpus vẫn sẽ có "top-k gần nhất" nào đó được trả về, dù không có chunk nào thực sự trả lời được câu hỏi. Đây là lỗi khiến LLM nhận context "trông giống liên quan" và cố gắng trả lời dựa trên nó — dẫn tới câu trả lời tự tin nhưng sai (hallucination được "hợp lý hoá" bởi context sai). Cách giảm rủi ro: đặt ngưỡng similarity tối thiểu (không trả context nếu score quá thấp), và luôn có hướng dẫn tường minh trong prompt kiểu "nếu context không đủ để trả lời, hãy nói rõ là không tìm thấy thông tin, không suy diễn."

**Context quá dài:** Đưa quá nhiều chunk vào prompt (cố "cho chắc") có 3 vấn đề: (1) tăng chi phí và latency vì token đầu vào tăng; (2) tăng nguy cơ chunk nhiễu (không liên quan) lọt vào, làm LLM bị phân tán, đôi khi trộn lẫn thông tin từ nhiều chunk khác nhau thành một câu trả lời sai; (3) hiện tượng "lost in the middle" — nhiều nghiên cứu cho thấy LLM có xu hướng chú ý tốt hơn tới thông tin ở đầu và cuối context, thông tin nằm giữa một context rất dài dễ bị "bỏ qua" hơn dù về lý thuyết nằm trong context window. Retrieval tốt (top-k nhỏ, chính xác cao) luôn tốt hơn retrieval rộng (top-k lớn, hy vọng LLM tự lọc).

**Không cite nguồn:** Một câu trả lời RAG không kèm trích dẫn nguồn (tài liệu nào, section nào) không thể kiểm chứng được — với người dùng cuối, không phân biệt được câu trả lời dựa trên tài liệu thật hay LLM tự bịa. Ở mức senior, RAG production luôn phải trả về được: chunk nào được dùng, từ tài liệu nào, và lý tưởng là cho phép người dùng bấm vào để xem nguồn gốc. Đây không phải tính năng "nice to have" — với domain có yêu cầu tuân thủ (tài chính, pháp lý, y tế), thiếu citation đồng nghĩa với việc không thể audit được câu trả lời AI đã dựa trên cái gì, một vấn đề compliance thật, không chỉ UX.

**Chunk bị lệch domain nhưng vẫn lọt qua retrieval:** Khi corpus có nhiều tài liệu khác chủ đề (ví dụ vừa có tài liệu kỹ thuật vừa có tài liệu HR), một câu hỏi mơ hồ có thể vô tình retrieve chunk từ domain sai mà similarity score vẫn đủ cao để lọt top-k. Giải pháp thường là thêm metadata filter (department, document type) áp dụng trước hoặc trong bước retrieve, không chỉ dựa thuần vào similarity semantics.

## Đối chiếu với code thật trong repo
`mcp-superset` không triển khai RAG, nhưng kiến trúc chia tầng rõ ràng trong repo minh hoạ đúng nguyên tắc "mỗi bước trong pipeline nên là một tầng độc lập, dễ thay thế": `core/context.py` định nghĩa `SupersetContext` giữ một `httpx.AsyncClient` **dùng chung** cho toàn bộ server (comment trong file: "Holds only the shared HTTP client and base URL"), khởi tạo một lần trong `create_superset_context()` và tái sử dụng cho mọi tool gọi API — tránh việc mỗi request tạo mới một client (tốn kém, không tái sử dụng connection pool). Một pipeline RAG production nên áp dụng đúng nguyên tắc này cho **client của vector DB và client của embedding model**: khởi tạo một lần khi server start, tái sử dụng qua toàn bộ vòng đời request, không tạo mới client cho mỗi query — nếu không, mỗi câu hỏi của user sẽ trả thêm chi phí thiết lập connection không cần thiết vào latency. Đồng thời, việc `tools/dataset.py` và `tools/database.py` tách riêng theo domain (dataset logic không lẫn vào database connection logic) là hình mẫu tốt để tách các bước RAG (ingest/chunk là một module, retrieve/rerank là module khác, augment/generate là module khác) — không dồn tất cả vào một hàm khổng lồ.

## Thực hành
```python
# Pipeline RAG tối giản, đầy đủ 3 luồng: embed -> retrieve -> augment -> generate
# pip install anthropic voyageai psycopg[binary]

import anthropic
import voyageai
import psycopg

voyage = voyageai.Client(api_key="YOUR_VOYAGE_API_KEY")
claude = anthropic.Anthropic(api_key="YOUR_ANTHROPIC_API_KEY")

def retrieve(query: str, conn, top_k: int = 5, min_score: float = 0.3):
    """Embed câu hỏi, tìm top-k chunk gần nhất trong pgvector, lọc theo ngưỡng similarity."""
    query_vector = voyage.embed([query], model="voyage-3", input_type="query").embeddings[0]

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content, source, 1 - (embedding <=> %s::vector) AS similarity
            FROM doc_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (query_vector, query_vector, top_k),
        )
        rows = cur.fetchall()

    # Lọc rác: bỏ chunk có similarity quá thấp thay vì luôn nhồi đủ top_k vào prompt
    return [(content, source, score) for content, source, score in rows if score >= min_score]


def augment_and_generate(query: str, chunks: list[tuple[str, str, float]]) -> str:
    if not chunks:
        return "Không tìm thấy thông tin liên quan trong tài liệu để trả lời câu hỏi này."

    context_block = "\n\n".join(
        f"[Nguồn: {source}]\n{content}" for content, source, _ in chunks
    )

    system_prompt = (
        "Bạn chỉ được trả lời dựa trên các đoạn tài liệu trong CONTEXT dưới đây. "
        "Nếu context không đủ thông tin để trả lời, hãy nói rõ là không tìm thấy "
        "thông tin, KHÔNG suy diễn hoặc dùng kiến thức ngoài context. "
        "Luôn trích dẫn [Nguồn: ...] cho mỗi phần thông tin bạn dùng."
    )

    response = claude.messages.create(
        model="claude-sonnet-5",  # kiểm tra tên model mới nhất trong docs.anthropic.com trước khi dùng thật
        max_tokens=1024,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"CONTEXT:\n{context_block}\n\nCÂU HỎI: {query}",
        }],
    )
    return response.content[0].text


# Chạy end-to-end
conn = psycopg.connect("postgresql://user:pass@localhost/ragdb")
query = "Khi nào nên dùng pgvector thay vì vector DB riêng?"
chunks = retrieve(query, conn, top_k=5, min_score=0.3)
print(augment_and_generate(query, chunks))
```

## Bài tập tự làm
1. Chạy pipeline trên với corpus là chính 3 file `day8-embeddings.md`, `day9-vector-db.md`, `day10-chunking.md` (chunk + embed + lưu vào pgvector local trước). Hỏi 1 câu có câu trả lời rõ trong corpus, và 1 câu hoàn toàn ngoài phạm vi (ví dụ "Superset dùng để làm bánh như thế nào") — quan sát pipeline có từ chối trả lời đúng cách ở câu thứ hai không.
2. Thử bỏ ngưỡng `min_score` (đặt về 0, luôn lấy đủ top_k) và lặp lại câu hỏi ngoài phạm vi ở bài 1 — so sánh câu trả lời của LLM có khác không, và giải thích vì sao.
3. Thêm bước log ra: mỗi lần generate, in kèm những chunk/nguồn đã được dùng để augment — đây chính là phần "citation" tối thiểu, xác nhận bạn có thể trace lại câu trả lời đến nguồn cụ thể.

## Đào sâu / nâng cao

### Lost in the middle
Hiện tượng LLM chú ý không đồng đều theo vị trí thông tin trong context dài — thông tin ở đầu/cuối thường được dùng chính xác hơn thông tin ở giữa. Hệ quả thực dụng: khi có nhiều chunk quan trọng, xem xét thứ tự sắp xếp trước khi đưa vào prompt (ví dụ đặt chunk có độ liên quan cao nhất gần đầu hoặc gần cuối context, không chôn nó ở giữa một danh sách dài). Đọc thêm các bài nghiên cứu và blog kỹ thuật về "lost in the middle" của các nhà cung cấp LLM lớn để hiểu rõ ở model cụ thể đang dùng — hành vi này có thể khác nhau giữa các model/version.

### Agentic RAG / retrieval nhiều bước
RAG "cổ điển" là một lượt retrieve-rồi-generate. Các hệ thống nâng cao hơn cho phép LLM tự quyết định có cần retrieve thêm không, retrieve lại với query khác nếu lần đầu không đủ thông tin, hoặc gọi nhiều nguồn khác nhau tuỳ câu hỏi — bản chất là biến retrieval thành một "tool" mà agent loop (Ngày 17) có thể gọi lặp lại. Đây là hướng phát triển tự nhiên của RAG khi kết hợp với tool-calling, sẽ gặp lại ở Tuần 3.

### Đánh giá "context đủ chưa" trước khi generate
Một số pipeline RAG nâng cao thêm bước kiểm tra trung gian: sau khi retrieve, hỏi (chính LLM, hoặc một model nhỏ hơn/rẻ hơn) "context này có đủ để trả lời câu hỏi không" trước khi đi tới bước generate cuối — nếu không đủ, hệ thống có thể retrieve lại với query viết lại (query rewriting, xem Ngày 12) hoặc trả lời "không tìm thấy" sớm, tránh generate một câu trả lời nửa vá dựa trên context không đủ.

## Bài tập senior
Review đoạn thiết kế pipeline sau (giả định do một dev khác trong team đề xuất) và chỉ ra ít nhất 3 vấn đề cụ thể, kèm đề xuất sửa: "Pipeline của chúng ta: user hỏi → embed câu hỏi → lấy top-20 chunk gần nhất theo cosine similarity (không lọc ngưỡng) → nhồi toàn bộ 20 chunk vào prompt kèm câu hỏi → gọi Claude sinh câu trả lời → trả thẳng câu trả lời cho user, không kèm nguồn." Với mỗi vấn đề, giải thích tác động thực tế (chi phí, latency, độ tin cậy, khả năng audit) không chỉ nói "sai vì không đúng best practice".

## Checklist trước khi qua Ngày 12
- [ ] Vẽ được (trên giấy hoặc mô tả bằng lời) toàn bộ pipeline RAG, phân biệt rõ luồng ingest (offline) và luồng query (online).
- [ ] Giải thích được vì sao retrieval là chỗ quyết định chất lượng, không phải bước generate.
- [ ] Nêu được ít nhất 3 lỗi thực tế thường gặp (retrieval sai, context quá dài, thiếu citation) kèm cách giảm rủi ro cho mỗi lỗi.
- [ ] Tự chạy được pipeline end-to-end trên corpus nhỏ, có bước lọc ngưỡng similarity và có in ra nguồn được dùng.
- [ ] Biết pipeline nên xử lý thế nào khi context không đủ để trả lời (từ chối rõ ràng, không suy diễn).
</content>
