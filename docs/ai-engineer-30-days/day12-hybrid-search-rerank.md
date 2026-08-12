# Phần 12 — Hybrid search, reranking, query rewriting

## Mục tiêu hôm nay
Học các kỹ thuật nâng cấp retrieval vượt ra ngoài "cosine similarity thuần" — đây là ranh giới rõ nhất giữa một RAG demo và một RAG production, vì retrieval thuần vector luôn có những điểm mù mà hybrid search, rerank, và query rewriting được thiết kế để bù lại.

## Đọc trước
- [Qdrant — Hybrid Queries](https://qdrant.tech/documentation/concepts/hybrid-queries/)
- [Weaviate — Hybrid Search](https://weaviate.io/developers/weaviate/search/hybrid)
- [Anthropic — Contextual Retrieval](https://docs.anthropic.com/) (có đề cập kết hợp BM25 với embedding)

## Khái niệm cốt lõi

### Vì sao vector search thuần không đủ
Vector similarity (Phần 8) rất mạnh với việc bắt ngữ nghĩa tổng quát, nhưng có một điểm yếu cụ thể: nó kém với **exact match** — mã số, tên riêng, từ viết tắt, số liệu chính xác. Ví dụ câu hỏi "mã dataset ID 4521 là gì" — về ngữ nghĩa, "4521" không mang nhiều thông tin cho embedding model tổng quát; hai chunk chứa "ID 4521" và "ID 9932" có thể có similarity với câu hỏi gần như nhau, vì embedding model không được train để phân biệt tinh vi giữa các số nếu ngữ cảnh xung quanh giống nhau. Đây chính xác là bài toán mà tìm kiếm từ khoá truyền thống (keyword/lexical search) giải quyết tốt — khớp chuỗi ký tự chính xác, không quan tâm ngữ nghĩa.

### BM25 — sparse search, khái niệm cốt lõi
BM25 (Best Matching 25) là thuật toán ranking dựa trên tần suất từ, biến thể cải tiến của TF-IDF — tính điểm liên quan giữa query và document dựa trên: từ trong query xuất hiện bao nhiêu lần trong document (term frequency), từ đó hiếm hay phổ biến trong toàn bộ corpus (inverse document frequency — từ hiếm mang nhiều thông tin phân biệt hơn từ phổ biến), có điều chỉnh giảm ảnh hưởng khi document quá dài. Gọi là "sparse" vì biểu diễn mỗi document là một vector rất lớn (kích thước bằng từ vựng toàn corpus) nhưng hầu hết giá trị bằng 0 — đối lập với "dense" vector của embedding (vài trăm/nghìn chiều, hầu như không có giá trị 0). BM25 là nền tảng của Elasticsearch, Postgres full-text search (`tsvector`/`tsquery` dùng biến thể tương tự), và các vector DB hiện đại (Qdrant, Weaviate) đều có hỗ trợ BM25 built-in để kết hợp.

### Hybrid search — kết hợp dense và sparse
Hybrid search chạy cả hai: dense vector search (bắt ngữ nghĩa) và BM25/sparse search (bắt exact match), rồi **kết hợp điểm số** của hai phương pháp thành một ranking cuối. Cách kết hợp phổ biến nhất là **Reciprocal Rank Fusion (RRF)**: với mỗi document, lấy vị trí rank của nó trong mỗi danh sách kết quả (dense và sparse riêng biệt), tính điểm dựa trên nghịch đảo rank (`1/(k + rank)`, k là hằng số làm mượt), cộng điểm từ cả hai danh sách. RRF được ưa dùng vì không cần chuẩn hoá thang điểm giữa hai phương pháp có bản chất khác nhau (cosine similarity và BM25 score không cùng đơn vị đo, không thể cộng trực tiếp một cách có ý nghĩa) — RRF chỉ quan tâm **thứ hạng**, không quan tâm giá trị tuyệt đối của điểm.

Kết quả thực tế: hybrid search thường cho retrieval quality tốt hơn dùng riêng một phương pháp, đặc biệt với corpus có nhiều thuật ngữ chuyên ngành/mã số/tên riêng (đúng đặc điểm của tài liệu tài chính, mã chứng khoán, quy định pháp lý) — không có gì đảm bảo tuyệt đối cho mọi trường hợp, nên vẫn cần đo bằng eval (Phần 13) trên dữ liệu thật của mình, không mặc định tin lý thuyết.

### Reranking — cross-encoder
Retrieval ban đầu (dense, sparse, hoặc hybrid) thường dùng cách tính similarity "rẻ" (so sánh vector đã encode sẵn, hoặc BM25 score) để có thể chạy nhanh trên hàng triệu document — gọi là **bi-encoder** approach (query và document được encode độc lập, không "nhìn thấy nhau" lúc encode). Reranking dùng một model khác, **cross-encoder**, nhận cả query và document **cùng lúc** làm input, cho phép model học tương tác trực tiếp giữa hai chuỗi text — chính xác hơn nhiều nhưng chậm hơn đáng kể (không thể tiền tính toán trước như bi-encoder, phải chạy inference cho mỗi cặp query-document tại thời điểm query).

Vì cross-encoder chậm, thực tế luôn dùng theo mô hình 2 tầng: (1) retrieval rẻ (bi-encoder/BM25/hybrid) lấy top-N rộng (ví dụ 50-100 candidate), (2) rerank bằng cross-encoder chỉ trên N candidate đó để chọn ra top-k cuối cùng (ví dụ 5) đưa vào prompt. Cohere Rerank là dịch vụ rerank phổ biến hay được dùng theo dạng API, không cần tự host model.

### Query rewriting và expansion

**HyDE (Hypothetical Document Embeddings)**: kỹ thuật hơi ngược trực giác — thay vì embed trực tiếp câu hỏi của user để tìm document tương ứng, yêu cầu LLM **sinh ra một câu trả lời giả định** cho câu hỏi trước, rồi embed câu trả lời giả định đó để tìm document. Lý do: câu hỏi thường ngắn, mang dạng câu hỏi ("Làm sao để...", "Tại sao..."), còn document thường mang dạng câu trả lời/khẳng định — khoảng cách ngữ nghĩa giữa "dạng câu hỏi" và "dạng câu trả lời" đôi khi lớn hơn khoảng cách giữa hai câu trả lời cùng nội dung. HyDE thu hẹp khoảng cách này bằng cách biến câu hỏi thành một "câu trả lời giả" trước khi tìm kiếm.

**Multi-query**: yêu cầu LLM sinh ra nhiều phiên bản diễn đạt khác nhau của cùng một câu hỏi gốc (ví dụ 3-5 câu hỏi paraphrase), retrieve riêng cho mỗi phiên bản, rồi hợp nhất (thường bằng RRF) kết quả từ tất cả các lượt retrieve. Giảm rủi ro việc câu hỏi gốc của user dùng từ ngữ không khớp tốt với cách tài liệu diễn đạt — mỗi phiên bản paraphrase có cơ hội "bắt trúng" một cách diễn đạt khác trong corpus.

Cả hai kỹ thuật đều tốn thêm ít nhất 1 lượt gọi LLM trước khi retrieve thật — đánh đổi latency/chi phí để lấy chất lượng retrieval cao hơn, cần cân nhắc theo yêu cầu thực tế của use case (một chatbot cần trả lời tức thì có thể không chấp nhận thêm một lượt LLM call trước khi retrieve).

## Đối chiếu với code thật trong repo
`mcp-superset` không có tầng search/rerank, nhưng nguyên tắc "kết hợp nhiều tín hiệu để lọc/sắp xếp kết quả tốt hơn một tín hiệu đơn" xuất hiện dưới dạng khác trong `utils/rison.py` (dùng bởi `tools/database.py` và `tools/dataset.py` qua hàm `build_list_query`): khi liệt kê dataset/database, request có thể kết hợp **filter theo tên** (`name_contains`, dạng `ct` — contains, tương tự exact/substring match của sparse search) **cùng với** `order_column`/`order_direction` để sắp xếp — nghĩa là API Superset cho phép kết hợp một điều kiện lọc chính xác (lexical) với một tiêu chí sắp xếp riêng, một dạng "hybrid" đơn giản hơn nhiều so với RRF nhưng cùng tinh thần: không phụ thuộc vào một tín hiệu duy nhất để quyết định thứ tự/tính liên quan của kết quả trả về.

## Thực hành
```python
# Pseudocode minh hoạ hybrid search + RRF (dùng Qdrant, đã hỗ trợ BM25 + dense native
# qua "Query API" — kiểm tra cú pháp mới nhất trong docs.qdrant.tech vì API có thể đổi)
# pip install qdrant-client anthropic voyageai

from qdrant_client import QdrantClient, models

client = QdrantClient(url="http://localhost:6333")

def hybrid_search(query: str, query_vector: list[float], top_k: int = 5):
    """Chạy dense search và sparse (BM25) search riêng, hợp nhất bằng RRF."""
    results = client.query_points(
        collection_name="doc_chunks",
        prefetch=[
            models.Prefetch(query=query_vector, using="dense", limit=20),
            models.Prefetch(query=models.Document(text=query, model="bm25"), using="sparse", limit=20),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=top_k,
    )
    return results


# Rerank bằng cross-encoder qua API (ví dụ dịch vụ Cohere Rerank — kiểm tra tên model
# và cú pháp mới nhất trong docs chính thức trước khi dùng thật)
# pip install cohere
import cohere

co = cohere.Client(api_key="YOUR_COHERE_API_KEY")

def rerank(query: str, candidates: list[str], top_k: int = 5):
    result = co.rerank(query=query, documents=candidates, top_n=top_k, model="rerank-v3.5")
    return [(candidates[r.index], r.relevance_score) for r in result.results]


# HyDE — sinh câu trả lời giả định trước khi embed để retrieve
import anthropic

claude = anthropic.Anthropic(api_key="YOUR_ANTHROPIC_API_KEY")

def hyde_query(question: str) -> str:
    response = claude.messages.create(
        model="claude-sonnet-5",
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": f"Viết một đoạn văn ngắn (giả định) trả lời câu hỏi sau, "
                        f"như thể trích từ một tài liệu kỹ thuật thật: {question}",
        }],
    )
    hypothetical_doc = response.content[0].text
    return hypothetical_doc  # embed đoạn này thay cho câu hỏi gốc để retrieve
```

## Bài tập tự làm
1. Với corpus nhỏ đã có từ Phần 11, thử một câu hỏi chứa mã số hoặc tên riêng cụ thể (ví dụ "tool nào có tên `superset_dataset_refresh_columns`") — so sánh kết quả retrieval thuần dense vector so với thêm exact-match/keyword filter, quan sát dense-only có bắt trúng không.
2. Cài `cohere` (hoặc dùng rerank model khác có sẵn), lấy top-20 candidate từ retrieval thô, rerank xuống top-5 — so sánh top-5 trước và sau rerank bằng mắt, xem thứ tự có hợp lý hơn không.
3. Viết thử HyDE cho 1 câu hỏi, in ra "câu trả lời giả định" mà LLM sinh, và so sánh similarity của nó với các chunk thật trong corpus so với similarity của câu hỏi gốc.

## Đào sâu / nâng cao

### Reciprocal Rank Fusion — hiểu công thức
`RRF_score(d) = Σ 1/(k + rank_i(d))` với tổng chạy qua mọi danh sách kết quả `i` mà document `d` xuất hiện, `rank_i(d)` là vị trí của `d` trong danh sách đó (1-indexed), `k` là hằng số làm mượt (giá trị phổ biến trong tài liệu kỹ thuật là 60, nhưng nên coi là tham số cần tinh chỉnh theo dữ liệu thật, không phải hằng số cố định tuyệt đối). Tính chất quan trọng: document xuất hiện ở rank cao trong **nhiều** danh sách được ưu tiên hơn document chỉ xuất hiện tốt trong một danh sách — đúng tinh thần "đồng thuận giữa nhiều tín hiệu đáng tin hơn một tín hiệu".

### Khi nào rerank không đáng chi phí thêm
Rerank thêm latency (một lượt gọi model/API nữa) và chi phí — với use case cần trả lời tức thì (dưới một ngưỡng latency chặt), hoặc corpus nhỏ mà retrieval thô đã đủ chính xác (đo được qua eval, Phần 13), thêm rerank có thể là tối ưu hoá không cần thiết. Quyết định thêm rerank nên dựa trên đo lường retrieval quality trước/sau, không phải vì "ai cũng làm vậy".

### Multi-query và chi phí nhân bản
Multi-query nhân số lượt gọi vector DB lên theo số phiên bản câu hỏi sinh ra — với hệ thống có traffic cao, chi phí này cộng dồn đáng kể. Một biến thể tiết kiệm hơn là chỉ áp multi-query có điều kiện (ví dụ chỉ khi retrieval lần đầu cho kết quả confidence thấp), thay vì áp cho mọi câu hỏi.

## Bài tập senior
Hệ thống RAG hiện tại của team chỉ dùng dense vector search, đang gặp vấn đề: người dùng hỏi bằng mã sản phẩm/mã báo cáo cụ thể (ví dụ "báo cáo RPT-2024-Q3-117") thường không tìm ra tài liệu đúng, dù tài liệu đó có tồn tại và chứa đúng mã đó. Đề xuất một giải pháp (mô tả kiến trúc, không cần code đầy đủ) giải quyết vấn đề này, và trả lời: (a) tại sao dense vector search một mình không xử lý tốt trường hợp này; (b) thêm hybrid search có làm chậm hệ thống đáng kể không, cần đo gì để biết; (c) nếu chỉ được chọn một trong hai — thêm hybrid search hoặc thêm rerank — trong tình huống cụ thể này, chọn cái nào trước và vì sao.

## Checklist trước khi qua Phần 13
- [ ] Giải thích được vì sao dense vector search một mình yếu với exact match (mã số, tên riêng).
- [ ] Hiểu khái niệm BM25 ở mức đủ để biết khi nào nó bổ trợ tốt cho dense search.
- [ ] Giải thích được RRF dùng rank thay vì điểm số trực tiếp, và vì sao cách đó hợp lý khi kết hợp hai phương pháp khác bản chất.
- [ ] Phân biệt được bi-encoder (retrieval rẻ, tiền tính toán được) và cross-encoder (rerank, chính xác hơn nhưng chậm).
- [ ] Giải thích được HyDE và multi-query giải quyết vấn đề gì, và chi phí đánh đổi của mỗi kỹ thuật.
</content>
