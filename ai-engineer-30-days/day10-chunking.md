# Ngày 10 — Chunking strategy — sai ở đây là hỏng cả pipeline

## Mục tiêu hôm nay
Hiểu chunking không phải bước "cắt text cho vừa" tầm thường mà là quyết định kiến trúc ảnh hưởng trực tiếp tới chất lượng retrieval — chunk sai thì embedding tốt, vector DB tốt, LLM tốt cũng không cứu được, vì retrieval sẽ trả về đúng-sai-lệch ngay từ đầu.

## Đọc trước
- [Anthropic — Contextual Retrieval](https://docs.anthropic.com/) (kỹ thuật liên quan chunking và context, tìm mục "Contextual Retrieval" trong docs/blog Anthropic)
- [LangChain — Text Splitters](https://python.langchain.com/docs/concepts/text_splitters/)
- [pgvector — GitHub README](https://github.com/pgvector/pgvector) (tham khảo lại để nhớ dimension chunk sẽ đem đi embed)

## Khái niệm cốt lõi

### Vì sao chunking quan trọng hơn dev backend nghĩ
Chunking là bước chia một tài liệu dài thành các đoạn nhỏ hơn trước khi embed và lưu vào vector DB. Nghe có vẻ đơn giản như "cắt string theo độ dài cố định", nhưng bản chất bài toán là: **mỗi chunk phải là một đơn vị ngữ nghĩa đủ để tự nó có nghĩa khi bị tách khỏi phần còn lại của tài liệu**. Đây là điểm khác biệt so với các phép chia dữ liệu quen thuộc trong backend (pagination, batching cho xử lý song song) — pagination chia để xử lý tuần tự rồi vẫn ghép lại được ý nghĩa đầy đủ, còn chunking chia để **mỗi phần đứng độc lập vẫn phải mang đủ thông tin** cho việc retrieval và cho LLM đọc hiểu sau này.

Hậu quả của chunk sai lan truyền theo một chuỗi khó phát hiện: chunk cắt giữa câu → embedding của chunk đó mang ngữ nghĩa mơ hồ/thiếu → vector similarity với câu hỏi bị lệch → retrieval trả về chunk không thực sự liên quan (hoặc miss chunk đúng) → LLM nhận context sai hoặc thiếu → câu trả lời sai hoặc bị hallucinate để "lấp đầy" phần thiếu. Không có bước nào ở giữa (rerank, prompt tốt hơn) sửa được lỗi từ gốc này một cách triệt để — sửa chunking luôn rẻ hơn và hiệu quả hơn cố gắng "vá" ở các tầng sau.

### Fixed-size chunking
Chia text theo số ký tự hoặc số token cố định (ví dụ 500 token/chunk), thường kèm overlap. Ưu điểm: đơn giản, dự đoán được kích thước, dễ implement, chi phí tính toán thấp. Nhược điểm: cắt ngang câu, ngang đoạn, ngang ý — một chunk có thể bắt đầu giữa câu và kết thúc giữa câu khác, làm mất hoàn toàn context cục bộ. Đây là baseline hay dùng để so sánh khi benchmark các chiến lược khác, nhưng ít khi là lựa chọn cuối cùng cho production nếu chất lượng retrieval là ưu tiên.

### Sentence-based / recursive character splitting
Chia theo ranh giới câu (dùng tokenizer câu, hoặc thư viện NLP nhận diện dấu chấm câu đúng ngữ cảnh — tránh cắt nhầm ở "TS. Nguyễn" hay "Q3."). **Recursive character splitting** (cách LangChain implement `RecursiveCharacterTextSplitter`) là biến thể thực dụng phổ biến nhất: thử chia theo danh sách separator ưu tiên giảm dần (ví dụ `["\n\n", "\n", ". ", " "]`) — cố gắng chia theo đoạn văn trước, nếu đoạn vẫn quá dài mới chia theo câu, nếu câu vẫn quá dài mới chia theo khoảng trắng. Cách này giữ được ranh giới ngữ nghĩa tự nhiên tốt hơn fixed-size thuần, trong khi vẫn đơn giản, không cần model riêng để hiểu ngữ nghĩa.

### Semantic chunking
Dùng chính embedding để quyết định ranh giới chunk: embed từng câu (hoặc từng đoạn nhỏ), đo similarity giữa các câu liên tiếp, cắt chunk mới ở những điểm mà similarity giảm mạnh (dấu hiệu chuyển ý/chuyển chủ đề). Về lý thuyết cho chunk "đúng ngữ nghĩa" nhất, nhưng tốn chi phí tính toán (phải embed ở granularity câu trước khi biết cách chunk), và chất lượng phụ thuộc ngưỡng similarity chọn (threshold sai → chunk quá nhỏ vụn hoặc quá lớn). Phù hợp khi tài liệu có cấu trúc lộn xộn (transcript hội thoại, ghi chú tự do) không có heading/cấu trúc rõ để dựa vào.

### Overlap — vì sao cần và bao nhiêu là hợp lý
Overlap là phần text lặp lại giữa 2 chunk liền kề (ví dụ chunk 1 kết thúc ở câu X, chunk 2 bắt đầu lại từ câu X-1). Mục đích: giảm rủi ro một ý quan trọng bị "mắc" đúng ngay ranh giới cắt, dẫn tới cả hai chunk xung quanh đều thiếu ngữ cảnh cần thiết để hiểu ý đó đầy đủ. Overlap phổ biến ở mức 10-20% kích thước chunk (không có số tuyệt đối đúng cho mọi trường hợp — phụ thuộc độ dài trung bình của một "ý hoàn chỉnh" trong domain dữ liệu). Overlap quá lớn gây lãng phí (một nội dung bị embed và lưu trùng nhiều lần, tăng chi phí storage và có thể làm retrieval trả về nhiều chunk gần như giống nhau, chiếm chỗ trong context window mà không thêm thông tin mới).

### Chunking theo cấu trúc document — quan trọng nhất với tài liệu kỹ thuật
Khi tài liệu có cấu trúc tường minh (markdown với heading, code block; HTML với tag; PDF có section) — **luôn ưu tiên chunk theo cấu trúc đó trước khi áp thêm rule về độ dài**. Vài nguyên tắc cụ thể:
- **Markdown headers**: chia theo heading (`#`, `##`, `###`) trước, để mỗi chunk nằm trong một section có chủ đề rõ, sau đó mới áp fixed-size/recursive splitting *bên trong* section nếu section đó vẫn quá dài. Giữ lại heading cha (ví dụ prepend `"# Ngày 9 > ## Khi nào cần vector DB riêng"`) vào đầu mỗi chunk con giúp chunk tự mang được context mà không cần đọc toàn văn bản.
- **Code block**: không bao giờ cắt ngang một code block — một hàm/class bị cắt đôi giữa chunk vừa vô nghĩa với LLM đọc, vừa có thể khiến LLM sinh code sai khi paste "một nửa hàm" vào câu trả lời. Luôn coi code block (giữa hai dấu ``` ``` ```) là một đơn vị không thể chia, dù nó vượt kích thước chunk mong muốn — chấp nhận chunk to hơn bình thường trong trường hợp này.
- **Bảng (table)**: tương tự code block — một bảng bị cắt ngang mất hết ý nghĩa hàng/cột, nên coi là đơn vị nguyên vẹn.

Nguyên tắc tổng quát: **cấu trúc document là tín hiệu ngữ nghĩa miễn phí** — bất cứ khi nào tài liệu có cấu trúc rõ, dùng nó thay vì coi toàn bộ tài liệu là một chuỗi ký tự thô rồi chunk mù theo độ dài.

## Đối chiếu với code thật trong repo
Repo `mcp-superset` không xử lý văn bản tự do để chunk, nhưng cách tổ chức code trong repo là một minh hoạ tốt cho *đúng khái niệm ranh giới ngữ nghĩa* mà chunking đang cố mô phỏng cho text: mỗi file trong `tools/` (`database.py`, `dataset.py`, `chart.py`...) là một "chunk" tự nhiên theo domain — `tools/dataset.py` chỉ chứa các tool liên quan tới dataset, không lẫn logic của database connection. Nếu phải "chunk" chính codebase này để một LLM đọc hiểu (ví dụ RAG trên toàn bộ source code để trả lời câu hỏi "tool nào xoá dataset"), chunk theo **ranh giới hàm/class** (mỗi `@mcp.tool()` function là một chunk) sẽ cho kết quả tốt hơn nhiều so với chunk theo số dòng cố định — giống hệt nguyên tắc "chunk theo code block, không cắt ngang hàm" ở trên. Đây cũng là lý do các công cụ chunking code chuyên dụng (ví dụ dựa trên AST/tree-sitter) tồn tại riêng biệt với text splitter thông thường — vì ranh giới ngữ nghĩa của code là cấu trúc cú pháp (function, class), không phải câu/đoạn văn.

## Thực hành
```python
# pip install langchain-text-splitters

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)

# 1. Recursive character splitting — baseline thực dụng cho text thường
text = """
RAG là kỹ thuật kết hợp retrieval với generation. Thay vì để LLM trả lời
hoàn toàn từ kiến thức đã train, hệ thống tìm các đoạn tài liệu liên quan
trước, rồi đưa vào prompt làm context cho LLM.

Bước đầu tiên trong RAG là chunking — chia tài liệu nguồn thành các đoạn
nhỏ để embed. Chunking sai làm hỏng toàn bộ pipeline phía sau.
"""

splitter = RecursiveCharacterTextSplitter(
    chunk_size=200,
    chunk_overlap=40,
    separators=["\n\n", "\n", ". ", " ", ""],
)
chunks = splitter.split_text(text)
for i, c in enumerate(chunks):
    print(f"--- chunk {i} (len={len(c)}) ---")
    print(c)

# 2. Markdown header splitting — chunk theo section trước, giữ heading cha làm metadata
markdown_text = """
# Ngày 9 — Vector DB

## Khi nào cần vector DB riêng
Nội dung về việc khi nào nên dùng Pinecone/Qdrant...

## Khi nào pgvector là đủ
Nội dung về việc pgvector là extension của Postgres...
"""

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[("#", "h1"), ("##", "h2")]
)
md_chunks = header_splitter.split_text(markdown_text)
for doc in md_chunks:
    print(doc.metadata, "->", doc.page_content[:60])
```

## Bài tập tự làm
1. Lấy nội dung file `docs/ai-engineer-30-days/day9-vector-db.md` (chính file hôm qua), chạy qua `MarkdownHeaderTextSplitter` — quan sát mỗi chunk có giữ được heading cha làm metadata không, và so sánh chất lượng chunk so với việc chạy `RecursiveCharacterTextSplitter` thô lên toàn văn bản không quan tâm heading.
2. Cố tình tạo một đoạn text có 1 code block dài hơn `chunk_size` bạn chọn — chạy qua `RecursiveCharacterTextSplitter` mặc định và quan sát code block có bị cắt đôi không. Sau đó thử thêm dấu ``` ``` ``` vào danh sách separator ưu tiên cao nhất hoặc dùng splitter chuyên cho markdown/code để so sánh.
3. Với cùng một tài liệu, tạo 2 bộ chunk: overlap = 0 và overlap = 20% chunk_size. Chọn 1 câu hỏi có câu trả lời nằm sát ranh giới một chunk bất kỳ, retrieval thử (thủ công, đọc bằng mắt) để xem overlap có giúp câu trả lời không bị "hụt" thông tin ở ranh giới.

## Đào sâu / nâng cao

### Contextual Retrieval (Anthropic)
Kỹ thuật được Anthropic mô tả trong docs/blog: thêm một đoạn context ngắn (do LLM sinh ra) vào đầu mỗi chunk trước khi embed, mô tả chunk đó nằm ở đâu/nói về gì trong tài liệu gốc (ví dụ: "Đoạn này thuộc báo cáo tài chính Q3 2025 của công ty X, phần nói về doanh thu mảng môi giới"). Mục tiêu là bù lại chính vấn đề chunking gây ra: một chunk bị tách khỏi tài liệu gốc mất hết context ngầm định mà người đọc tự nhiên có khi đọc cả bài. Kỹ thuật này tốn thêm một lượt gọi LLM cho mỗi chunk lúc ingest (chi phí một lần, không phải mỗi query), đổi lại cải thiện chất lượng retrieval đáng kể theo báo cáo của Anthropic — đọc kỹ bài viết chính thức để hiểu cách họ đo cải thiện trước khi áp dụng mù quáng.

### Chunk size tối ưu không cố định theo domain
Không có "chunk size chuẩn" áp dụng mọi domain: tài liệu pháp lý/hợp đồng thường cần chunk theo điều khoản (có thể dài) để không cắt đứt logic ràng buộc giữa các câu trong cùng điều khoản; tài liệu hỏi-đáp/FAQ có thể chunk rất nhỏ (mỗi Q&A một chunk) vì mỗi đơn vị đã tự đủ nghĩa; transcript hội thoại cần cân nhắc theo turn hoặc theo cụm chủ đề. Quyết định chunk size nên dựa trên việc đọc mẫu dữ liệu thật, không suy ra từ một con số nghe quen (ví dụ "512 token" chỉ là giá trị hay gặp trong tutorial, không phải quy luật vật lý).

### Chunking cho code (AST-aware splitting)
Với source code, chia theo ranh giới cú pháp (function, class, method) cho kết quả tốt hơn nhiều so với chia theo số dòng — công cụ dựa trên tree-sitter hoặc AST parser của ngôn ngữ tương ứng có thể tách chính xác từng định nghĩa hàm/class kèm docstring của nó làm một chunk. LangChain có `Language`-aware splitter hỗ trợ một số ngôn ngữ lập trình theo kiểu này — đọc tài liệu LangChain text splitters để biết ngôn ngữ nào được hỗ trợ tại thời điểm dùng.

## Bài tập senior
Team đang build RAG cho tài liệu compliance nội bộ (quy trình, quy định UBCKNN liên quan tới hoạt động của công ty), nguồn là các file Word/PDF có nhiều bảng biểu, danh sách điều khoản đánh số, và một số đoạn có ghi chú "Điều X tham chiếu Điều Y ở phần trước". Review pipeline chunking hiện tại của team (giả định): họ dùng `RecursiveCharacterTextSplitter` mặc định với `chunk_size=1000`, không xử lý gì đặc biệt cho bảng hoặc tham chiếu chéo giữa điều khoản. Chỉ ra tối thiểu 3 vấn đề cụ thể có thể xảy ra với pipeline này khi áp lên loại tài liệu compliance dạng này, và với mỗi vấn đề đề xuất một hướng xử lý (không cần code, mô tả chiến lược).

## Checklist trước khi qua Ngày 11
- [ ] Giải thích được vì sao chunk sai lan truyền lỗi xuống toàn bộ pipeline RAG, không chỉ nói "chunk sai thì kết quả sai".
- [ ] Phân biệt được fixed-size, sentence-based/recursive, semantic chunking — biết trade-off của mỗi loại.
- [ ] Biết khi nào và vì sao cần overlap, và overlap quá nhiều gây hại gì.
- [ ] Áp dụng được nguyên tắc "chunk theo cấu trúc document trước khi chunk theo độ dài" cho ít nhất markdown và code block.
- [ ] Tự chạy được `RecursiveCharacterTextSplitter` và `MarkdownHeaderTextSplitter`, đọc hiểu output.
</content>
