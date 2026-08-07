# Ngày 13 — Đánh giá RAG: retrieval metrics & answer faithfulness

## Mục tiêu hôm nay
Học cách đo chất lượng RAG bằng số liệu thay vì cảm giác "trông có vẻ đúng" — đây là kỹ năng phân biệt rõ nhất một AI Engineer senior với một người chỉ biết ghép API: senior luôn có cách chứng minh (hoặc bác bỏ) một thay đổi có làm hệ thống tốt hơn không, bằng eval, không bằng việc tự đọc vài câu trả lời rồi kết luận "có vẻ ổn".

## Đọc trước
- [RAGAS docs](https://docs.ragas.io/)
- [Anthropic — Building evals](https://docs.anthropic.com/) (tìm mục về evaluation/testing trong docs Anthropic)
- [Weaviate — RAG evaluation concepts](https://weaviate.io/developers/weaviate)

## Khái niệm cốt lõi

### Vì sao "trông có vẻ đúng" không phải là eval
Đọc thử 5-10 câu trả lời của hệ RAG rồi thấy "ổn" là bước kiểm tra hợp lý *ban đầu*, nhưng không phải eval — vì nó có 3 lỗi cấu trúc: (1) không có con số để so sánh khi thay đổi model/chunking/prompt — "có vẻ tốt hơn" không phải là kết luận có thể tái lập hoặc đưa vào báo cáo review; (2) sample nhỏ do một người đọc mang thiên kiến xác nhận (confirmation bias) — dễ vô thức chọn câu hỏi mà hệ thống trả lời tốt để test; (3) không phát hiện được lỗi tinh vi — một câu trả lời có thể *đọc trôi chảy, tự tin, đúng ngữ pháp* nhưng sai hoàn toàn về sự thật (hallucination được diễn đạt tốt), và người đọc không có thời gian verify từng câu trả lời với tài liệu nguồn thì không phát hiện ra. Eval nghiêm túc cần: bộ câu hỏi cố định (golden dataset) để test lại mỗi lần thay đổi, metric định lượng, và tách riêng việc đo **retrieval** với việc đo **answer generation** — vì lỗi ở RAG luôn có thể bắt nguồn từ một trong hai tầng, trộn chung sẽ không biết sửa ở đâu.

### Retrieval metrics
Các metric này đo: "trong số chunk mà hệ thống trả về, bao nhiêu thực sự liên quan, và những chunk liên quan có được xếp hạng cao không" — đo hoàn toàn độc lập với việc LLM sinh câu trả lời thế nào, cần một golden dataset có nhãn "chunk nào là đúng/liên quan cho câu hỏi này".

- **Precision@k**: trong top-k chunk trả về, tỷ lệ bao nhiêu là thực sự liên quan. `Precision@k = (số chunk liên quan trong top-k) / k`. Đo "độ sạch" của kết quả — precision thấp nghĩa là retrieval trả về nhiều rác, tăng nguy cơ context quá dài/gây nhiễu (Ngày 11).
- **Recall@k**: trong tổng số chunk thực sự liên quan có trong toàn corpus, tỷ lệ bao nhiêu được tìm thấy trong top-k. `Recall@k = (số chunk liên quan trong top-k) / (tổng số chunk liên quan trong corpus)`. Đo "độ đầy đủ" — recall thấp nghĩa là bỏ lỡ thông tin quan trọng, LLM sẽ trả lời thiếu dù không phải lỗi của nó.
- **MRR (Mean Reciprocal Rank)**: trung bình của `1/rank` của chunk liên quan **đầu tiên** xuất hiện trong kết quả, tính trên toàn bộ tập câu hỏi test. Nếu chunk đúng đầu tiên nằm ở vị trí 1 → reciprocal rank = 1; ở vị trí 3 → 1/3. MRR phù hợp khi chỉ cần "tìm thấy ít nhất một chunk đúng sớm" là đủ (ví dụ hệ thống chỉ cần 1 nguồn để trả lời).
- **NDCG (Normalized Discounted Cumulative Gain)**: metric tinh vi hơn, xử lý được trường hợp mức độ liên quan có **nhiều cấp độ** (không chỉ liên quan/không liên quan mà có thang điểm, ví dụ 0-3), và "discount" (giảm trọng số) theo vị trí — chunk liên quan cao nằm ở rank thấp (xa đầu danh sách) đóng góp ít điểm hơn nếu nó nằm ở rank cao. NDCG chuẩn hoá về khoảng 0-1 bằng cách chia cho DCG lý tưởng (thứ tự sắp xếp hoàn hảo), cho phép so sánh giữa các câu hỏi khác nhau có số lượng chunk liên quan khác nhau.

Quy tắc chọn metric: Precision/Recall@k đơn giản, dễ giải thích cho stakeholder không chuyên; MRR phù hợp khi chỉ cần một nguồn đúng sớm; NDCG phù hợp khi có khái niệm "mức độ liên quan" chứ không phải nhị phân, và cần một con số tổng hợp so sánh được giữa nhiều cấu hình retrieval khác nhau.

### Answer faithfulness / groundedness
Sau khi đo retrieval, tầng thứ hai là đo chất lượng câu trả lời **so với context đã retrieve** — tách biệt hai câu hỏi khác nhau:
- **Faithfulness/Groundedness**: câu trả lời của LLM có bị "bịa" thông tin không có trong context được cung cấp không? Đây là metric chống hallucination cụ thể cho RAG — một câu trả lời có thể đúng sự thật ngoài đời nhưng vẫn "không faithful" nếu thông tin đó không có trong context đưa vào (nghĩa là LLM dùng kiến thức train sẵn thay vì dùng context, vi phạm đúng mục đích của RAG là buộc LLM bám vào nguồn được cung cấp).
- **Answer relevance**: câu trả lời có thực sự trả lời đúng câu hỏi được hỏi không (có thể faithful với context nhưng lại lạc đề, trả lời một khía cạnh không ai hỏi).
- **Context precision/recall (ở mức câu trả lời)**: một số framework đo thêm liệu context được cung cấp có "vừa đủ" không — quá nhiều context không liên quan bị đưa vào dù retrieval đã lọc, hoặc thiếu context cần thiết.

Cách đo groundedness thực tế thường dùng **LLM-as-judge**: dùng một LLM (có thể khác model đang test, để giảm thiên kiến "tự chấm điểm mình") đọc câu trả lời + context + câu hỏi, và judge xem mỗi câu/claim trong câu trả lời có được context hỗ trợ không. Đây không phải phương pháp hoàn hảo (LLM judge cũng có thể sai), nhưng ở quy mô lớn, nó thực tế và có thể tái lập hơn nhiều so với việc con người đọc thủ công từng câu trả lời.

### RAGAS — framework đánh giá RAG
RAGAS là một framework mã nguồn mở chuyên đánh giá pipeline RAG, cung cấp sẵn cách tính các metric như faithfulness, answer relevance, context precision/recall theo phương pháp LLM-as-judge có cấu trúc (không cần tự viết prompt judge từ đầu). Giá trị chính của việc dùng một framework có sẵn (thay vì tự chế) là: có cách tính đã được kiểm định, dễ so sánh giữa các thử nghiệm (chunking khác, model khác) trên cùng một thang đo, và tích hợp được vào pipeline CI/CD để chạy eval tự động mỗi khi thay đổi cấu hình RAG. Đọc kỹ docs chính thức của RAGAS tại thời điểm dùng vì API và tên metric có thể thay đổi giữa các version.

### Xây golden dataset
Mọi eval nghiêm túc cần một golden dataset: tập câu hỏi cố định, kèm câu trả lời đúng mong đợi (hoặc chunk nào được coi là "đúng" cho câu hỏi đó). Cách xây dựng thực dụng: lấy câu hỏi thật từ log người dùng (nếu đã có traffic), hoặc thuê/tự viết dựa trên đọc kỹ corpus, đảm bảo có cả câu hỏi "trong phạm vi corpus" và câu hỏi "ngoài phạm vi" (để test khả năng từ chối đúng cách, xem Ngày 14). Golden dataset cần được review bởi người hiểu domain (không chỉ người viết code) — nếu nhãn "đúng" sai từ đầu, mọi số liệu tính ra từ đó vô nghĩa.

## Đối chiếu với code thật trong repo
`mcp-superset` không có eval framework cho RAG, nhưng liên hệ được ở tinh thần chung: `utils/decorators.py` có `handle_api_errors` bọc quanh mọi tool để bắt lỗi một cách nhất quán — đây là một dạng "guard" đảm bảo hành vi có thể đoán trước và kiểm tra được, đúng tinh thần mà eval framework mang lại cho RAG: thay vì để mỗi lần gọi tool tự xử lý lỗi riêng lẻ (không đoán trước được, khó kiểm tra hàng loạt), có một lớp thống nhất áp cho tất cả. Tương tự, một hệ RAG production nên có một "lớp eval" chạy nhất quán trên mọi thay đổi (đổi model embedding, đổi chunk size, đổi prompt) thay vì mỗi lần thay đổi lại tự kiểm tra thủ công theo cảm tính khác nhau. Ngoài ra, chính docstring chi tiết trong các tool (ví dụ trong `tools/dataset.py`, hàm `superset_dataset_delete` có docstring giải thích rõ điều kiện dùng, rủi ro) là một hình thức "đặc tả hành vi mong đợi" — golden dataset cho eval RAG đóng vai trò tương tự: đặc tả rõ "input nào thì output mong đợi là gì" để có cái so sánh khi hệ thống thay đổi.

## Thực hành
```python
# pip install ragas datasets

from ragas import evaluate, SingleTurnSample, EvaluationDataset
from ragas.metrics import Faithfulness, ContextPrecision, ContextRecall, AnswerRelevancy

# Golden dataset tối giản: mỗi sample có câu hỏi, câu trả lời hệ thống sinh ra,
# context đã retrieve, và (nếu có) câu trả lời tham chiếu đúng
samples = [
    SingleTurnSample(
        user_input="Khi nào nên dùng pgvector thay vì vector DB riêng?",
        response="Nên dùng pgvector khi hệ thống đã có Postgres và quy mô "
                 "dữ liệu ở mức vài trăm nghìn tới vài triệu vector.",
        retrieved_contexts=[
            "pgvector là đủ khi hệ thống đã có PostgreSQL đang chạy production...",
            "Quy mô dữ liệu ở mức vài trăm nghìn tới vài triệu vector...",
        ],
        reference="pgvector phù hợp khi đã có Postgres sẵn và quy mô dữ liệu "
                   "chưa tới hàng chục triệu vector.",
    ),
]

dataset = EvaluationDataset(samples=samples)

# Cần cấu hình LLM judge (ví dụ qua wrapper Anthropic/OpenAI của RAGAS) trước khi evaluate —
# xem hướng dẫn cấu hình LLM/embeddings mới nhất trong docs.ragas.io vì API cấu hình có thể đổi
result = evaluate(
    dataset=dataset,
    metrics=[Faithfulness(), ContextPrecision(), ContextRecall(), AnswerRelevancy()],
)
print(result)
```

```python
# Precision@k / Recall@k tự viết tay (khi chưa cần cả framework, muốn hiểu cơ chế)
def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    return sum(1 for doc_id in top_k if doc_id in relevant_ids) / len(top_k)

def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)

def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for rank, doc_id in enumerate(retrieved_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0
```

## Bài tập tự làm
1. Tạo một golden dataset tối giản (10 câu hỏi) cho corpus 3 file Ngày 8-10, mỗi câu hỏi ghi rõ chunk nào (theo id/tên) được coi là "đúng". Chạy retrieval hiện tại, tính Precision@3 và Recall@3 bằng tay theo công thức ở trên.
2. Chạy RAGAS (hoặc tự viết prompt LLM-as-judge tối giản) để đo faithfulness cho 5 câu trả lời đã sinh ở Ngày 11 — đọc kỹ giải thích của judge cho mỗi điểm số, không chỉ nhìn số.
3. Cố tình tạo 1 câu trả lời "bị nhiễm" hallucination (thêm một câu không có trong context vào câu trả lời), chạy qua faithfulness metric — xác nhận metric có bắt được lỗi này.

## Đào sâu / nâng cao

### LLM-as-judge — rủi ro và cách giảm thiểu
Dùng LLM để judge chất lượng câu trả lời của LLM khác (hoặc chính nó) có rủi ro: judge có thể có thiên kiến hệ thống (ưu tiên câu trả lời dài, ưu tiên câu trả lời có văn phong giống của chính nhà cung cấp model đó), hoặc không nhất quán giữa các lần chạy (temperature > 0). Cách giảm thiểu: dùng judge với temperature thấp/0, viết rubric chấm điểm rõ ràng thay vì hỏi mở, và định kỳ lấy mẫu để con người kiểm tra lại kết quả judge (calibration) — LLM-as-judge không thay thế hoàn toàn con người, nó thay thế việc con người phải đọc *mọi* câu trả lời.

### Eval offline vs online
Metric trong ngày hôm nay đều là eval offline (golden dataset cố định, chạy trước khi deploy). Ngày 22-23 (Tuần 4) sẽ đi vào eval online (theo dõi chất lượng khi hệ thống đã chạy thật với traffic thật, dùng feedback signal như thumbs up/down, tỷ lệ follow-up question). Hai loại eval bổ trợ nhau: offline eval bắt lỗi trước khi deploy nhưng không phản ánh hết sự đa dạng câu hỏi thật; online eval phản ánh thực tế nhưng phát hiện vấn đề sau khi đã ảnh hưởng người dùng thật.

### Đo eval theo từng thành phần pipeline riêng biệt
Khi RAG có nhiều thành phần (chunking, embedding model, retrieval, rerank, prompt, generation model), thay đổi một thành phần rồi đo eval tổng (end-to-end) một mình không cho biết *thành phần nào* gây ra thay đổi chất lượng. Cách làm nghiêm túc là giữ cố định mọi thành phần khác, chỉ đổi một thành phần mỗi lần (ablation study) — tốn công hơn nhưng là cách duy nhất để biết chính xác thay đổi nào đáng giá, tránh tình huống "cải thiện 1 chỗ nhưng làm hỏng chỗ khác mà không biết vì đo gộp chung".

## Bài tập senior
Sếp yêu cầu "chứng minh RAG mới build tốt hơn phiên bản cũ trước khi đưa vào production", nhưng team chưa có golden dataset, chỉ có một số câu hỏi mẫu được thử nghiệm ngẫu nhiên trong lúc demo. Viết một kế hoạch ngắn (dạng bullet, các bước theo thứ tự) để xây dựng bộ eval đủ nghiêm túc trong thời gian hạn chế (ví dụ 3-5 ngày làm việc), trả lời: (a) tối thiểu cần bao nhiêu câu hỏi trong golden dataset để kết luận có ý nghĩa, và nguồn lấy câu hỏi từ đâu là hợp lý nhất trong ngữ cảnh chưa có traffic thật; (b) đo retrieval và đo generation riêng biệt như thế nào trong kế hoạch; (c) nếu kết quả eval cho thấy phiên bản mới tốt hơn ở retrieval nhưng tệ hơn ở faithfulness, quyết định deploy hay không dựa trên cơ sở nào.

## Checklist trước khi qua Ngày 14
- [ ] Giải thích được vì sao đọc vài câu trả lời rồi kết luận "ổn" không phải là eval.
- [ ] Phân biệt được Precision@k, Recall@k, MRR, NDCG — biết khi nào metric nào phù hợp hơn.
- [ ] Phân biệt được việc đo retrieval và đo answer faithfulness là hai việc khác nhau, cần tách riêng.
- [ ] Biết RAGAS là gì và giá trị của việc dùng framework có sẵn thay vì tự chế toàn bộ.
- [ ] Tự tính được Precision@k/Recall@k/MRR bằng tay trên một golden dataset nhỏ tự tạo.
</content>
