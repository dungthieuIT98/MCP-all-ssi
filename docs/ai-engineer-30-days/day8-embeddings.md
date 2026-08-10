# Ngày 8 — Embeddings là gì, đo similarity thế nào

## Mục tiêu hôm nay
Hiểu embedding là nền tảng của mọi hệ RAG/semantic search — dev backend quen thuộc với index B-tree/hash trong SQL, nhưng "tìm theo ý nghĩa" cần một biểu diễn số hoàn toàn khác, và chọn sai model/metric ở bước này thì mọi tầng phía trên (chunking, retrieval, rerank) đều xây trên cát.

## Đọc trước
- [Anthropic — Embeddings guide](https://docs.anthropic.com/) (Anthropic không tự có embedding model — mục "Embeddings" trong docs Anthropic khuyến nghị dùng Voyage AI, xem link kế)
- [Voyage AI docs](https://docs.voyageai.com/)
- [OpenAI — Embeddings guide](https://platform.openai.com/docs/guides/embeddings)
- [pgvector — GitHub README](https://github.com/pgvector/pgvector)

## Khái niệm cốt lõi

### Embedding là gì
Embedding là một vector số thực có chiều cố định (ví dụ 1024, 1536, 3072 chiều) đại diện cho *ngữ nghĩa* của một đoạn text (hoặc ảnh, audio — tuỳ model). Model embedding được train sao cho hai đoạn text có nghĩa gần nhau thì vector của chúng nằm gần nhau trong không gian đó, đo bằng một hàm similarity/distance nào đó — không phải gần nhau theo ký tự (edit distance) mà gần nhau theo *ý nghĩa*.

Khác biệt căn bản so với full-text search (`LIKE`, `tsvector`, Elasticsearch BM25) mà dev backend đã quen: full-text search khớp theo từ/token xuất hiện chung, nên "xe hơi bị hỏng máy" và "ô tô không nổ được" hầu như không khớp từ nào — nhưng hai câu này ngữ nghĩa gần như giống nhau, và một embedding model tốt sẽ đặt hai vector này gần nhau. Đây chính xác là lý do RAG cần embedding: câu hỏi người dùng hiếm khi dùng đúng từ có trong tài liệu.

Về bản chất, embedding không phải "vector ma thuật" — nó là output của layer áp chót (hoặc pooled hidden state) trong một mạng transformer được fine-tune bằng contrastive learning: kéo các cặp (query, passage liên quan) lại gần nhau, đẩy các cặp không liên quan ra xa, trên hàng triệu cặp dữ liệu. Hiểu điều này giúp giải thích tại sao embedding có thể sai: nếu domain của bạn (ví dụ thuật ngữ tài chính, mã chứng khoán, jargon nội bộ SSI) không xuất hiện nhiều trong dữ liệu train, model general-purpose sẽ đặt các khái niệm khác nhau gần nhau một cách sai lệch.

### Đo similarity: cosine, dot product, Euclidean — khi nào dùng cái nào
Ba metric phổ biến, và sự khác biệt không chỉ là công thức toán — nó ảnh hưởng trực tiếp tới việc chọn index và chọn model:

- **Cosine similarity**: đo góc giữa hai vector, bỏ qua độ dài (magnitude). Công thức `cos(θ) = (A·B) / (|A| × |B|)`, giá trị từ -1 đến 1 (với embedding text thường dương, gần 1 là rất giống). Đây là lựa chọn **mặc định an toàn nhất** vì nó chuẩn hoá độ dài — hai đoạn text một ngắn một dài viết cùng một ý vẫn cho similarity cao mà không bị "phạt" vì độ dài vector khác nhau.
- **Dot product (inner product)**: `A·B`, không chuẩn hoá độ dài. Nếu vector đã được model chuẩn hoá về unit length (norm = 1) — nhiều model embedding hiện đại làm sẵn bước này — thì dot product và cosine similarity cho kết quả **tương đương về thứ tự ranking**, nhưng dot product tính rẻ hơn (không cần chia cho norm mỗi lần so sánh). Đây là lý do nhiều vector DB mặc định dùng dot product khi biết trước model output đã normalize: tối ưu tốc độ mà không đổi kết quả.
- **Euclidean distance (L2)**: đo khoảng cách "thẳng" trong không gian, nhạy với độ dài vector. Phù hợp khi bài toán thực sự cần biết "khác nhau bao nhiêu" về magnitude (ví dụ clustering trên feature vector số liệu thô), nhưng với embedding text đã chuẩn hoá thì L2 và cosine cho thứ tự ranking giống nhau về mặt toán học (`||A-B||² = 2 - 2×cos(θ)` khi cả hai là unit vector) — nên với text, chọn cosine hoặc dot product là đủ, L2 ít khi cần thiết trừ khi thư viện/index chỉ hỗ trợ L2.

Quy tắc thực dụng: đọc tài liệu của **chính embedding model** đang dùng để biết nó được train/khuyến nghị dùng với metric nào (Voyage AI, OpenAI đều ghi rõ trong docs) — dùng sai metric so với lúc train không gây lỗi cú pháp nhưng làm giảm chất lượng ranking một cách âm thầm, khó phát hiện nếu không có eval (xem Ngày 13).

### Embedding model: không có "một model cho tất cả"
- **Anthropic không có embedding model riêng** — Claude là model sinh text (generation), không phải model embedding. Docs của Anthropic khuyến nghị dùng **Voyage AI** làm nhà cung cấp embedding đi kèm khi xây hệ thống dùng Claude cho phần generate.
- **OpenAI**: dòng `text-embedding-3` (small/large) — phổ biến, có tham số `dimensions` cho phép rút gọn chiều vector ngay tại API mà không cần train lại (xem phần dimension trade-off).
- **Voyage AI**: có các model tổng quát và cả model chuyên domain (ví dụ tối ưu cho code, cho tài liệu luật/tài chính) — với ngành securities/tài chính, việc có domain-specific embedding có thể tạo khác biệt thật, không chỉ là marketing, vì thuật ngữ chuyên ngành (mã CK, tên chỉ số, thuật ngữ UBCKNN) không phổ biến trong dữ liệu train chung.
- **Model open-source tự host** (chạy qua sentence-transformers, hoặc qua Hugging Face) là lựa chọn khi có ràng buộc dữ liệu không được rời khỏi hạ tầng nội bộ — đánh đổi là tự vận hành GPU/inference, không có SLA nhà cung cấp.

Không có bảng benchmark cố định đáng tin cậy để chép vào đây — thứ hạng giữa các model thay đổi theo phiên bản và theo domain dữ liệu, tra bảng benchmark chính thức (MTEB leaderboard hoặc benchmark riêng của nhà cung cấp) tại thời điểm quyết định, đừng tin số cũ.

### Dimension trade-off
Chiều vector (dimension) là tham số quyết định trade-off giữa chất lượng, tốc độ, và chi phí lưu trữ:
- Dimension cao hơn (ví dụ 3072 so với 1536) **thường** biểu diễn ngữ nghĩa chi tiết hơn, nhưng không tuyến tính — vượt một ngưỡng nào đó, tăng dimension không còn cải thiện đáng kể chất lượng retrieval mà chỉ tăng chi phí.
- Chi phí tăng theo dimension ở **3 chỗ**: (1) băng thông/latency khi gọi API embedding, (2) dung lượng lưu trữ trong vector DB (mỗi vector là `dimension × 4 bytes` nếu lưu float32), (3) tốc độ tính similarity và build index ANN — index HNSW trên vector 3072 chiều chậm hơn đáng kể so với 1024 chiều ở cùng số lượng record.
- Nhiều model hiện đại hỗ trợ **giảm chiều ngay tại API** (ví dụ tham số `dimensions` của OpenAI `text-embedding-3`) nhờ kỹ thuật train Matryoshka Representation Learning — cắt bớt chiều cuối vector vẫn giữ được phần lớn chất lượng, tốt hơn nhiều so với tự làm PCA sau khi đã có vector đủ chiều.
- Quyết định thực dụng: bắt đầu với dimension mặc định của model, đo retrieval quality (Ngày 13) trước, chỉ giảm dimension khi có bằng chứng chi phí/latency là vấn đề thật — đừng tối ưu sớm dựa trên cảm giác "vector nhỏ thì nhanh hơn".

## Đối chiếu với code thật trong repo
Repo `mcp-superset` không có embedding hay vector DB — đây là điểm liên hệ ngược lại có ích: `tools/dataset.py` định nghĩa "dataset" là dữ liệu **có cấu trúc** (bảng, cột, kiểu dữ liệu tường minh trong Superset) — đối lập hoàn toàn với đầu vào của một embedding pipeline, luôn là dữ liệu **phi cấu trúc hoặc bán cấu trúc** (đoạn văn, tài liệu, đoạn code) mà không có "cột" nào để `WHERE` hay `JOIN` trực tiếp. Khi một dataset trong Superset đã có schema rõ (tên cột, kiểu dữ liệu), câu hỏi "SSI Q3 revenue là bao nhiêu" nên trả lời bằng SQL query trực tiếp (`superset_dataset_get_by_id` rồi query), không cần embedding — chỉ khi câu hỏi cần tìm trong văn bản tự do (báo cáo PDF, tài liệu chính sách, email) thì mới cần bước embed. Nhầm lẫn hai loại bài toán này là lỗi kiến trúc phổ biến của backend dev mới học RAG: thấy "hỏi đáp bằng AI" là nghĩ ngay tới vector DB, dù dữ liệu đang có sẵn structured và SQL trả lời chính xác hơn, rẻ hơn.

## Thực hành
```python
# pip install voyageai numpy
# (Voyage AI có free tier để test — không cần thẻ tín dụng cho một lượng gọi nhỏ,
# kiểm tra hạn mức mới nhất trên docs.voyageai.com trước khi chạy)

import voyageai
import numpy as np

vo = voyageai.Client(api_key="YOUR_VOYAGE_API_KEY")  # để trong env var khi dùng thật, không hardcode

texts = [
    "Superset dataset là dữ liệu có cấu trúc, truy vấn bằng SQL.",
    "Bảng dữ liệu trong Superset có schema rõ ràng, dùng SQL để lấy.",   # gần nghĩa câu 1
    "Con mèo đang ngủ trên ghế sofa.",                                    # không liên quan
]

result = vo.embed(texts, model="voyage-3", input_type="document")
vectors = np.array(result.embeddings)

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

print("câu 1 vs câu 2 (cùng ý):", cosine_similarity(vectors[0], vectors[1]))
print("câu 1 vs câu 3 (khác ý):", cosine_similarity(vectors[0], vectors[2]))
# Kỳ vọng: similarity câu 1-2 cao hơn rõ rệt so với câu 1-3.
# Nếu dùng model đã tự chuẩn hoá vector (norm = 1), np.dot(a, b) một mình
# đã cho đúng thứ tự ranking như cosine — nhưng viết đầy đủ công thức ở đây
# để không phụ thuộc giả định đó.
```

## Bài tập tự làm
1. Chạy đoạn code trên với 5 câu tự viết: 2 cặp gần nghĩa (diễn đạt khác nhau) và 1 câu hoàn toàn khác chủ đề. Ghi lại ma trận similarity 5x5, xác nhận cặp gần nghĩa có similarity cao hơn.
2. Thử `input_type="query"` so với `input_type="document"` cho cùng một câu (nếu model hỗ trợ tham số này) — đọc docs Voyage AI để hiểu tại sao model tách riêng "câu hỏi" và "tài liệu" thành hai loại encode khác nhau (asymmetric embedding).
3. Tính thử dung lượng lưu trữ: nếu có 100,000 đoạn văn, mỗi đoạn embed thành vector 1024 chiều float32, tính tổng dung lượng cần lưu (bytes) — so sánh với 1536 chiều.

## Đào sâu / nâng cao

### Asymmetric vs symmetric embedding
Một số model embed câu hỏi (`query`) và tài liệu (`document`) bằng hai "chế độ" khác nhau (dù cùng một model) — vì bản chất câu hỏi ngắn, mang ý định tìm kiếm, còn tài liệu dài, mang thông tin. Model bỏ qua sự khác biệt này (symmetric, encode giống nhau) thường kém hơn model có tách biệt tường minh (asymmetric) trong bài toán retrieval. Đọc kỹ tham số `input_type` (Voyage AI) hoặc hướng dẫn tương đương của nhà cung cấp đang dùng — dùng sai loại (encode câu hỏi như tài liệu) làm giảm chất lượng retrieval một cách khó nhận ra.

### Matryoshka Representation Learning (MRL)
Kỹ thuật train khiến các chiều đầu của vector mang nhiều thông tin nhất, các chiều sau bổ sung dần — cho phép cắt vector (truncate) mà vẫn giữ phần lớn chất lượng, khác với PCA áp dụng sau khi train (PCA cần tính lại trên toàn bộ tập dữ liệu, không làm được real-time per-vector). Đây là lý do OpenAI/Voyage AI cho phép chọn `dimensions` ngay ở API call. Đọc: paper gốc "Matryoshka Representation Learning" (arXiv) và phần giải thích trong docs của nhà cung cấp embedding đang dùng.

### Embedding drift khi đổi model
Vector từ hai model (hoặc hai version của cùng model) **không so sánh được với nhau** — không gian vector của mỗi model là riêng biệt, không có chuẩn chung. Nếu đổi embedding model, toàn bộ dữ liệu đã embed trong vector DB phải **re-embed lại từ đầu**, không thể "chuyển đổi" vector cũ sang không gian mới. Đây là chi phí vận hành hay bị đánh giá thấp khi thiết kế hệ RAG dài hạn — cần có kế hoạch migrate (batch job re-embed) trước khi đổi model production.

## Bài tập senior
Team đang có một hệ thống search nội bộ dùng PostgreSQL full-text search (`tsvector`/`tsquery`) cho tài liệu quy trình nội bộ SSI, đang bị phàn nàn là "tìm không ra dù tài liệu có nội dung liên quan" vì nhân viên gõ từ khoá khác cách diễn đạt trong tài liệu gốc. Sếp đề xuất "thêm embedding vào cho nó AI hơn". Viết một đề xuất ngắn (dạng bullet, không cần code) trả lời: (a) embedding một mình có giải quyết được vấn đề gốc không, hay cần kết hợp gì thêm; (b) rủi ro/chi phí nào phát sinh khi thêm embedding (data cần rời khỏi Postgres đi qua API bên thứ 3? domain thuật ngữ nội bộ có được model general-purpose hiểu đúng không?); (c) có cần vector DB riêng hay pgvector là đủ ở quy mô này — biết rằng data hiện tại chỉ vài nghìn tài liệu.

## Checklist trước khi qua Ngày 9
- [ ] Giải thích được embedding khác full-text search ở điểm nào, bằng ví dụ cụ thể không chỉ lý thuyết.
- [ ] Biết khi nào dùng cosine, khi nào dot product đủ (và vì sao lại tương đương khi vector đã normalize).
- [ ] Biết Anthropic không có embedding model, và tên nhà cung cấp được khuyến nghị thay thế.
- [ ] Giải thích được trade-off dimension: chất lượng vs chi phí lưu trữ/tốc độ, không chỉ nhớ "cao hơn thì tốt hơn".
- [ ] Chạy được đoạn code thực hành và tự đọc ra kết quả similarity có hợp lý không.
</content>
