# Phần 9 — Vector database, index ANN, khi nào cần và khi nào không

## Mục tiêu hôm nay
Hiểu vector database giải quyết vấn đề gì về mặt kỹ thuật (index ANN, không phải "database thần kỳ cho AI"), và — quan trọng hơn với dev backend — biết phân biệt lúc nào việc thêm một vector DB riêng là kỹ thuật đúng đắn và lúc nào chỉ là FOMO (thấy công ty khác dùng Pinecone/Qdrant nên mình cũng phải dùng).

## Đọc trước
- [pgvector — GitHub README](https://github.com/pgvector/pgvector)
- [Qdrant docs](https://qdrant.tech/documentation/)
- [Pinecone docs](https://docs.pinecone.io/)
- [Weaviate docs](https://weaviate.io/developers/weaviate)

## Khái niệm cốt lõi

### Vấn đề mà vector DB giải quyết: tìm kiếm gần đúng ở quy mô lớn
So sánh similarity giữa 1 vector query và N vector đã lưu, theo cách "brute-force" (tính cosine similarity với từng vector một, sort) là `O(N)` mỗi lần query — với N vài nghìn thì máy tính thường vẫn đủ nhanh, nhưng với N hàng triệu/hàng tỷ, brute-force trở nên quá chậm cho một API cần trả lời trong vài trăm ms. Vector DB (hoặc extension như pgvector) giải quyết vấn đề này bằng cách xây **index xấp xỉ (Approximate Nearest Neighbor — ANN)**: đánh đổi một chút độ chính xác (có thể miss vài kết quả gần nhất tuyệt đối) để đổi lấy tốc độ truy vấn gần như hằng số hoặc logarit theo N, thay vì tuyến tính.

Đây là điểm mà dev backend cần nắm chắc: vector DB **không phải** một loại database mới có phép thuật hiểu ngữ nghĩa — nó vẫn chỉ là một cấu trúc lưu trữ + index chuyên cho phép toán similarity trên vector nhiều chiều. Phần "hiểu ngữ nghĩa" hoàn toàn nằm ở embedding model (Phần 8), vector DB chỉ lưu trữ và tìm kiếm hiệu quả trên output của model đó.

### Index ANN — hiểu khái niệm, không cần tự implement
Hai họ thuật toán ANN phổ biến nhất, ở mức hiểu khái niệm để đọc thông số config, không cần implement:

- **HNSW (Hierarchical Navigable Small World)**: xây một cấu trúc đồ thị nhiều lớp, lớp trên thưa (ít điểm, bước nhảy xa) dùng để định hướng nhanh, lớp dưới dày đặc hơn để tìm chính xác cục bộ — giống cách một bản đồ có đường cao tốc (di chuyển xa nhanh) và đường nội bộ (di chuyển gần chính xác). Query đi từ lớp trên xuống lớp dưới, mỗi lớp thu hẹp phạm vi tìm kiếm. HNSW cho chất lượng recall cao và tốc độ truy vấn tốt, nhưng tốn RAM (toàn bộ graph thường cần nằm trong memory) và build index tương đối chậm/tốn tài nguyên khi insert nhiều. Đây là lựa chọn mặc định của phần lớn vector DB hiện đại (Qdrant, Weaviate, pgvector đều hỗ trợ HNSW).
- **IVF (Inverted File Index, thường đi kèm Flat hoặc PQ — Product Quantization)**: chia không gian vector thành các "cluster" (dùng thuật toán như k-means), khi query chỉ tìm trong một số cluster gần nhất với query vector, không quét toàn bộ. Rẻ hơn HNSW về RAM (đặc biệt khi kết hợp Product Quantization để nén vector), nhưng thường cần bước "train" cluster trước, và độ chính xác nhạy với việc chọn số cluster (`nlist`) phù hợp với quy mô dữ liệu.

Tham số quan trọng nhất khi cấu hình index ANM (tên chung, không phải riêng thuật toán nào) luôn là đánh đổi giữa 3 trục: **recall** (tỷ lệ tìm đúng kết quả gần nhất thật so với brute-force), **latency** (query nhanh thế nào), **chi phí RAM/storage**. Không có cấu hình "tốt nhất tuyệt đối" — chỉ có cấu hình phù hợp với ràng buộc của hệ thống cụ thể (bao nhiêu vector, cần bao nhiêu QPS, chấp nhận miss bao nhiêu %).

### Khi nào THỰC SỰ cần vector DB riêng, khi nào chỉ cần pgvector
Đây là quyết định kiến trúc quan trọng nhất trong ngày hôm nay, và là nơi backend dev dễ mắc lỗi FOMO nhất — thấy blog/tutorial dùng Pinecone/Qdrant/Weaviate nên mặc định "RAG thì phải có vector DB riêng", trong khi phần lớn use case ở quy mô vừa và nhỏ không cần.

**pgvector là đủ khi:**
- Hệ thống đã có PostgreSQL đang chạy production (rất phổ biến với backend dev) — pgvector là một **extension** (`CREATE EXTENSION vector;`), không phải service mới, không thêm điểm lỗi (failure point) mới, không thêm chi phí vận hành (patching, monitoring, backup) của một hệ thống riêng.
- Quy mô dữ liệu ở mức vài trăm nghìn tới vài triệu vector — pgvector với HNSW xử lý tốt ở tầm này trên hạ tầng Postgres bình thường.
- Cần **transaction/JOIN giữa vector và dữ liệu quan hệ khác** trong cùng một query — ví dụ "tìm đoạn tài liệu gần nghĩa nhất, NHƯNG chỉ trong các tài liệu mà user này có quyền đọc" (kết hợp `WHERE permission_check AND ORDER BY embedding <=> query_vector`). Vector DB độc lập không có transaction/JOIN native với dữ liệu quan hệ — phải tự ghép ở application layer, dễ sai và chậm hơn.
- Team không có nhân sự/nhu cầu vận hành thêm một loại database mới — mỗi service mới thêm vào hệ thống là thêm một thứ phải patch, backup, giám sát, và một thứ có thể down.

**Vector DB riêng (Pinecone, Qdrant, Weaviate, Milvus) đáng cân nhắc khi:**
- Quy mô hàng chục triệu đến hàng tỷ vector, cần horizontal scaling mà Postgres không đáp ứng tốt ở tầm đó.
- Cần filter phức tạp kết hợp ANN ở throughput rất cao, cần multi-tenancy ở mức hạ tầng (mỗi tenant một collection cô lập), hoặc cần managed service không muốn tự vận hành (Pinecone là serverless, không cần tự quản lý index).
- Cần tính năng chuyên biệt mà pgvector chưa có ở version đang dùng (ví dụ một số kiểu quantization nâng cao, hybrid search built-in — kiểm tra tài liệu chính thức tại thời điểm quyết định vì các engine này cập nhật tính năng liên tục).

Quy tắc thực dụng cho backend dev: **bắt đầu với pgvector nếu đã có Postgres**, đo tải thật (số vector, QPS, latency yêu cầu), chỉ migrate sang vector DB riêng khi có bằng chứng cụ thể pgvector không đáp ứng được — không quyết định trước khi có số liệu.

## Đối chiếu với code thật trong repo
`mcp-superset` không dùng vector DB, nhưng có một liên hệ kiến trúc đáng nhìn: `tools/database.py` là tầng quản lý **nhiều loại database backend khác nhau qua Superset** — Superset tự nó đã là một lớp trừu tượng hoá kết nối tới Postgres, MySQL, Trino, và nhiều engine khác, expose qua REST API thống nhất (`superset_database_list`, `superset_database_list_tables`). Đây là một minh hoạ tốt cho nguyên tắc "đừng thêm database mới khi có thể mở rộng cái đã có": nếu tổ chức đã có Superset kết nối tới một Postgres, và Postgres đó dùng được `pgvector`, thì việc thêm một Pinecone/Qdrant riêng nghĩa là thêm hẳn một hệ thống mới phải cấu hình quyền truy cập, network, backup — trong khi câu trả lời "thêm 1 extension vào Postgres đang có" có thể đủ. Việc `database.py` trong repo cố tình **không** expose các endpoint tạo/sửa connection (đọc comment đầu file: "Read-only by design... a Superset database payload carries connection credentials") cũng là một nhắc nhở liên quan: thêm bất kỳ hệ thống lưu trữ mới nào (kể cả vector DB) đều kéo theo bài toán quản lý credential mới, không phải chuyện nhỏ.

## Thực hành
```sql
-- Yêu cầu: Postgres 15+ (khuyến nghị), cài extension pgvector
-- (build từ source theo README github.com/pgvector/pgvector, hoặc dùng
-- image Docker có sẵn pgvector nếu chạy Postgres qua container local)

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE doc_chunks (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding VECTOR(1024)  -- khớp với dimension của model embedding đang dùng
);

-- Build index HNSW cho cosine distance (operator <=> là cosine distance trong pgvector)
CREATE INDEX ON doc_chunks USING hnsw (embedding vector_cosine_ops);

-- Insert (giá trị vector minh hoạ, thực tế lấy từ model embedding)
INSERT INTO doc_chunks (content, embedding) VALUES
    ('Superset dataset có schema rõ ràng, truy vấn bằng SQL.', '[0.01, 0.02, ...]'),
    ('Bảng dữ liệu trong Superset dùng SQL để lấy thông tin.', '[0.015, 0.021, ...]');

-- Truy vấn top-5 gần nhất theo cosine distance (giá trị nhỏ hơn = gần hơn)
SELECT id, content, embedding <=> '[0.011, 0.019, ...]'::vector AS distance
FROM doc_chunks
ORDER BY distance
LIMIT 5;
```

```python
# Pseudocode minh hoạ Qdrant khi THỰC SỰ cần vector DB riêng
# (chạy Qdrant local qua Docker: docker run -p 6333:6333 qdrant/qdrant — nhớ pin version cụ thể
# khi dùng thật theo chuẩn "pin base image version", không dùng tag "latest")
# pip install qdrant-client

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

client = QdrantClient(url="http://localhost:6333")

client.create_collection(
    collection_name="doc_chunks",
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
)

client.upsert(
    collection_name="doc_chunks",
    points=[
        PointStruct(id=1, vector=[0.01, 0.02] + [0.0] * 1022, payload={"content": "..."}),
    ],
)

results = client.query_points(
    collection_name="doc_chunks",
    query=[0.011, 0.019] + [0.0] * 1022,
    limit=5,
)
```

## Bài tập tự làm
1. Cài pgvector local (Docker image có sẵn pgvector, hoặc build extension theo README chính thức), tạo bảng như ví dụ trên, insert 10 dòng với vector giả (random hoặc lấy từ Phần 8), chạy truy vấn top-k và giải thích kết quả.
2. Đọc tài liệu pgvector về `hnsw` index — tìm tham số `m` và `ef_construction` (build-time), `ef_search` (query-time), giải thích bằng lời của mình tác động của việc tăng/giảm mỗi tham số tới recall/latency/RAM.
3. Viết ra (không cần code) một bảng so sánh 3 cột: "quy mô dữ liệu", "pgvector đủ dùng", "cần vector DB riêng" — điền dựa trên phần lý thuyết ở trên, không chép nguyên văn.

## Đào sâu / nâng cao

### Product Quantization (PQ) và nén vector
PQ chia mỗi vector thành nhiều đoạn nhỏ, mỗi đoạn được lượng tử hoá (quantize) thành một mã ngắn tra từ một "sổ mã" (codebook) học trước — giảm mạnh dung lượng lưu trữ (ví dụ từ vài KB xuống vài chục byte mỗi vector) đổi lại mất một phần độ chính xác. Hữu ích khi tập dữ liệu quá lớn để giữ toàn bộ vector float32 gốc trong RAM. Đọc thêm trong docs của Milvus hoặc Qdrant — cả hai đều có tài liệu giải thích PQ ở mức áp dụng thực tế, không chỉ lý thuyết.

### Filtering kết hợp ANN (filtered vector search)
Bài toán "tìm k vector gần nhất, NHƯNG chỉ trong tập con thoả điều kiện metadata" (ví dụ `department = 'compliance'`) khó hơn filter thông thường vì index ANN được xây cho toàn bộ tập, filter trước hay sau khi tìm ANN ảnh hưởng lớn tới cả recall và tốc độ. Các vector DB hiện đại (Qdrant, Weaviate) đều có cơ chế filtered search riêng (pre-filter tại thời điểm duyệt graph HNSW thay vì filter sau khi có kết quả) — đọc tài liệu riêng của engine đang dùng vì cách implement khác nhau đáng kể giữa các hệ thống.

### Chi phí vận hành thật của một vector DB riêng
Ngoài chi phí license/usage, một service mới kéo theo: giám sát riêng (metrics, alerting), chiến lược backup/restore riêng, quy trình patch version riêng, và một điểm lỗi mới trong toàn hệ thống (nếu vector DB down, toàn bộ luồng RAG down theo dù LLM và app chính vẫn chạy tốt). Khi đề xuất thêm vector DB riêng trong review kiến trúc, nêu rõ những chi phí này thay vì chỉ nói về tính năng — đây chính là câu hỏi một reviewer senior sẽ hỏi đầu tiên.

## Bài tập senior
Một team trong SSI đề xuất triển khai Pinecone (managed, trả phí theo usage) cho một hệ RAG nội bộ phục vụ khoảng 50 nhân viên tra cứu quy trình/chính sách (ước tính vài nghìn tài liệu, vài chục nghìn chunk). Hệ thống hiện tại đã có một Postgres instance đang chạy cho ứng dụng nội bộ khác, có dư tài nguyên. Viết một bản đánh giá ngắn (dạng bullet) cho buổi review kiến trúc, trả lời: (a) ở quy mô này, Pinecone có thực sự cần thiết so với thêm `pgvector` vào Postgres đã có; (b) nếu chọn Pinecone, dữ liệu (có thể chứa nội dung nội bộ/giới hạn theo phân loại SSI) đi qua hạ tầng bên thứ 3 — rủi ro nào cần AIGC/security review trước khi triển khai; (c) nếu chọn pgvector, điểm nghẽn nào có thể xuất hiện khi hệ thống scale lên 10x, và cần đo gì để biết trước khi nó xảy ra.

## Checklist trước khi qua Phần 10
- [ ] Giải thích được vector DB giải quyết vấn đề gì (ANN ở quy mô lớn), không mô tả nó như "database AI thần kỳ".
- [ ] Phân biệt được khái niệm HNSW và IVF ở mức đủ đọc config, không cần tự viết thuật toán.
- [ ] Có thể lập luận rõ khi nào pgvector đủ dùng, khi nào cần vector DB riêng — có ví dụ cụ thể, không chỉ cảm tính.
- [ ] Tự chạy được truy vấn top-k trên pgvector local.
- [ ] Biết chi phí vận hành ẩn (ngoài tính năng) khi thêm một service mới vào hệ thống.
</content>
