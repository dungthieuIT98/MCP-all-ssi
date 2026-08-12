# Phần 22 — Eval framework nghiêm túc: offline eval, golden dataset, LLM-as-judge

## Mục tiêu hôm nay
Hiểu vì sao eval có hệ thống là năng lực phân biệt senior với junior trong AI engineering, và tự xây được một vòng eval offline tối thiểu: golden dataset, chấm điểm tự động (kể cả bằng LLM-as-judge), chạy trong CI.

## Đọc trước
- [Anthropic docs](https://docs.anthropic.com/) — mục về đánh giá chất lượng model/prompt (tìm "evaluate" trong docs, nội dung cụ thể có thể đổi theo thời điểm, tra bản mới nhất).
- [OWASP GenAI Security Project](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — không trực tiếp về eval nhưng cùng nhóm tài liệu LLMOps sẽ dùng lại ở Phần 27, đọc trước để quen thuật ngữ.
- Tài liệu chung về LLMOps/eval: tìm theo từ khoá "LLM evaluation framework", "golden dataset", "LLM-as-judge" — không có một nguồn "chính thức" duy nhất, đây là lĩnh vực đang định hình, nên đối chiếu nhiều nguồn thay vì tin một bài viết.

## Khái niệm cốt lõi

### Vì sao "thử vài prompt bằng tay" không phải là eval
Junior engineer khi đổi prompt hoặc đổi model thường làm việc: gõ 3-5 câu hỏi mẫu, đọc output, thấy "nghe hợp lý" thì kết luận "ổn, deploy được". Cách này thất bại vì ba lý do có thật:

1. **Không có baseline để so sánh.** "Ổn" so với cái gì? Nếu không có con số trước/sau, không thể biết một thay đổi prompt làm tăng hay giảm chất lượng — chỉ có cảm giác, và cảm giác bị thiên vị bởi ví dụ vừa test (recency bias).
2. **Không phát hiện regression.** Sửa prompt để fix case A rất dễ làm hỏng case B mà không ai để ý, vì không ai test lại case B. Không có bộ test cố định nghĩa là mọi lần sửa đều có rủi ro "vá chỗ này, thủng chỗ khác" mà không biết.
3. **Không scale được qua review.** Khi PR cần review, "tôi test bằng tay thấy ổn" không phải bằng chứng người khác kiểm tra lại được. Một con số (pass rate, score trung bình) từ một bộ test cố định thì kiểm tra lại được — đây là khác biệt giữa "trust me" và "đây là kết quả, tự chạy lại xem".

Senior engineer coi eval là một phần bắt buộc của thay đổi liên quan LLM, giống như unit test là bắt buộc của thay đổi code logic thông thường — không phải bước "làm thêm cho chắc" mà là điều kiện để merge.

### Offline eval là gì
Offline eval là đánh giá chất lượng model/prompt/pipeline **trước khi lên production**, chạy trên một bộ dữ liệu cố định (golden dataset), không có user thật tham gia. Đối lập với online eval (Phần 23) — đánh giá trên traffic thật sau khi đã deploy.

Offline eval cần ba thành phần:
- **Golden dataset**: tập input đại diện, kèm expected output hoặc tiêu chí chấm điểm.
- **Scorer** (hàm chấm điểm): so sánh output thực tế với expected/tiêu chí, ra một con số hoặc pass/fail. Có thể là so khớp chuỗi/regex, có thể là LLM-as-judge, có thể là rule-based (ví dụ kiểm tra JSON có đúng schema không).
- **Aggregation & threshold**: tổng hợp điểm qua toàn bộ dataset (pass rate, điểm trung bình, phân theo category), và một ngưỡng để quyết định "đạt/không đạt" khi chạy CI.

### Xây golden dataset: nhỏ nhưng đại diện
Golden dataset không cần lớn — vài chục đến vài trăm case được duy trì kỹ tốt hơn nhiều nghìn case không ai kiểm soát chất lượng. Nguyên tắc xây dataset:

- **Lấy case thật, không tự nghĩ ra.** Case tốt nhất lấy từ log production thật (câu hỏi user thật đã hỏi, đã gặp lỗi thật) — case tự nghĩ trong đầu engineer thường lệch xa phân bố thật, dễ toàn là case "dễ" vì người viết prompt vô thức tránh case khó.
- **Phân nhóm theo category.** Ví dụ với một trợ lý truy vấn Superset: nhóm "câu hỏi rõ ràng có 1 dataset khớp", nhóm "câu hỏi mơ hồ cần hỏi lại", nhóm "câu hỏi ngoài phạm vi (nên từ chối)", nhóm "câu hỏi có thể gây tool call sai". Aggregate theo category giúp thấy model yếu ở đâu cụ thể, không chỉ một con số tổng mơ hồ.
- **Ưu tiên case đã từng gây lỗi (regression case).** Mỗi khi phát hiện một lỗi thật trong production hoặc trong review — thêm ngay case đó vào golden dataset kèm kỳ vọng đúng. Đây là cách dataset "sống" theo thời gian, không đứng yên: dataset ban đầu chỉ là điểm khởi đầu, giá trị thật tích lũy dần từ lỗi thực tế.
- **Giữ dataset nhỏ có chủ đích.** Dataset lớn chậm chạy, đắt (nếu scorer là LLM-as-judge, mỗi lần chạy CI tốn tiền gọi API), và khó review khi ai đó muốn sửa case. Ưu tiên representative hơn exhaustive — vài case tốt cho mỗi category quan trọng, không cần vài trăm case gần giống nhau.
- **Version hoá dataset cùng code.** Golden dataset nên nằm trong Git, cùng repo hoặc repo liên quan, để mỗi PR sửa prompt đi kèm diff của cả code và dataset nếu cần — không phải file Excel nằm ngoài kiểm soát version.

### LLM-as-judge: dùng model mạnh để đánh giá model khác
Với bài toán không có "đáp án đúng duy nhất" để so khớp chuỗi (ví dụ chấm chất lượng một câu trả lời tự do, chấm độ tự nhiên, chấm mức độ hữu ích), so khớp string hoặc regex không đủ. LLM-as-judge dùng một model (thường là model mạnh, đôi khi chính là model đắt nhất có sẵn) để đọc input + output rồi chấm điểm hoặc phân loại pass/fail theo rubric viết tường minh trong prompt.

**Điểm mạnh:**
- Chấm được các tiêu chí ngữ nghĩa mà rule-based không làm được: "câu trả lời có đúng nội dung tài liệu nguồn không", "câu trả lời có né tránh câu hỏi không", "tone có phù hợp không".
- Scale tốt hơn con người chấm tay — chạy hàng trăm case trong vài phút, lặp lại được (không mệt, không thay đổi tâm trạng theo ngày như người chấm thật).
- Cho phép chấm theo rubric nhiều chiều (correctness, helpfulness, tone, an toàn) trong một lần gọi nếu prompt judge thiết kế tốt.

**Điểm yếu / bias cần biết — bắt buộc phải biết trước khi tin kết quả:**
- **Self-preference bias**: model có xu hướng chấm cao hơn cho output có văn phong giống chính nó (ví dụ dùng Claude để judge output của Claude thường cho điểm cao hơn khách quan) hoặc giống văn phong model cùng họ. Muốn giảm ảnh hưởng này, cân nhắc dùng model judge khác họ với model đang được chấm, hoặc chấp nhận bias này là giới hạn đã biết khi diễn giải số liệu.
- **Length bias**: nhiều LLM-as-judge có xu hướng chấm câu trả lời dài hơn là "tốt hơn", "đầy đủ hơn", dù nội dung dài không đồng nghĩa chất lượng cao — cần thiết kế rubric chỉ rõ "độ dài không phải tiêu chí", và test thử bằng cách đổi chỗ 2 câu trả lời (một ngắn đúng, một dài lan man) để xem judge có bị lệch không.
- **Position bias**: khi judge so sánh hai output A/B, thứ tự đưa vào prompt (A trước hay B trước) có thể ảnh hưởng kết quả — giảm bằng cách chạy cả hai thứ tự và lấy trung bình, hoặc random hoá thứ tự.
- **Judge không phải oracle tuyệt đối.** Judge có thể sai, đặc biệt với domain chuyên biệt (thuật ngữ tài chính, mã chứng khoán) nếu judge không được cấp đủ context để biết đúng/sai thật. Luôn kiểm định judge: lấy một mẫu nhỏ, cho người thật chấm độc lập, so sánh với judge — nếu lệch nhiều, sửa rubric hoặc đổi model judge trước khi tin số liệu ở scale lớn.
- **Prompt của judge cũng cần eval.** Rubric mơ hồ ("chấm câu trả lời này có tốt không, từ 1-10") cho kết quả nhiễu, không lặp lại được (chạy 2 lần cho 2 điểm khác nhau với cùng input). Rubric tốt liệt kê tiêu chí cụ thể, có ví dụ điểm cao/điểm thấp, và yêu cầu output có cấu trúc (structured output — xem lại Phần 4) để dễ parse và aggregate.

### Eval tự động hoá trong CI
Mục tiêu: mỗi PR đổi prompt/model/pipeline logic tự động chạy golden dataset, báo cáo pass rate, và (tuỳ mức độ nghiêm ngặt) chặn merge nếu điểm giảm dưới ngưỡng so với baseline (main branch).

Thiết kế thực dụng:
- Eval job chạy như một test job riêng trong CI pipeline, không lẫn với unit test thông thường vì latency và chi phí khác hẳn (mỗi case gọi API thật, có thể tốn vài giây đến vài chục giây/case, và tốn tiền — vài trăm case × giá gọi API không phải con số zero).
- Không nhất thiết chạy full dataset trên mọi PR — có thể chạy smoke set nhỏ (vài case đại diện, nhanh, rẻ) trên mọi PR, và full dataset theo lịch (nightly) hoặc khi PR có label "eval-full".
- Lưu kết quả có version — biết PR nào làm điểm tăng/giảm bao nhiêu, để trace lại nếu sau đó phát hiện regression production mà eval offline không bắt được (dấu hiệu golden dataset thiếu case đó — quay lại thêm case, đúng vòng lặp "dataset sống" nói ở trên).
- Ngưỡng chặn merge nên là chính sách đội ngũ quyết định (bao nhiêu % giảm là chấp nhận được, có ngoại lệ cần review tay không) — không có số chuẩn chung cho mọi hệ thống.

## Đối chiếu với code thật trong repo
Repo `mcp-superset` hiện chưa có eval framework nào — đây là điểm liên hệ hữu ích để hình dung cụ thể phải xây gì nếu áp dụng vào chính repo này. Mỗi tool trong `tools/` (ví dụ tool truy vấn dataset, tool tạo chart) đều dùng `handle_api_errors` (xem `utils/decorators.py`) để trả JSON có field `"error"` khi thất bại — nghĩa là bất kỳ agent nào gọi các tool này có thể trả về output "thành công về hình thức" (JSON hợp lệ) nhưng sai về logic (chọn sai dataset, sai filter). Một golden dataset thực tế cho `mcp-superset` sẽ không chỉ chấm "tool có trả JSON đúng schema không" (rule-based, dễ) mà cần chấm "agent có chọn đúng dataset/chart cho câu hỏi người dùng không" (cần LLM-as-judge hoặc so khớp với ID kỳ vọng) — hai loại lỗi khác hẳn nhau và cần hai loại scorer khác nhau trong cùng một eval suite.

## Thực hành
```python
"""
Eval offline tối thiểu: golden dataset nhỏ + 2 loại scorer (rule-based và
LLM-as-judge) + tổng hợp pass rate. Chạy được với `pip install anthropic`.
Đặt ANTHROPIC_API_KEY trong biến môi trường, không hardcode key vào code.
"""
import json
import os
from dataclasses import dataclass

import anthropic

client = anthropic.Anthropic()  # đọc ANTHROPIC_API_KEY từ env

# --- Golden dataset: nhỏ, có category, có case lấy từ "lỗi thật đã gặp" ---
GOLDEN_SET = [
    {
        "id": "clear-001",
        "category": "cau_hoi_ro_rang",
        "input": "Doanh thu quý 3 nằm trong dataset nào?",
        "expected_contains": ["dataset"],  # rule-based: output phải nhắc tới "dataset"
    },
    {
        "id": "oos-001",
        "category": "ngoai_pham_vi",
        "input": "Dự đoán giá cổ phiếu ABC ngày mai bao nhiêu?",
        # Case này lấy từ một lỗi thật giả định: model đã từng trả lời liều một
        # con số dự đoán giá — đây chính là kiểu case "thêm vào sau khi phát hiện
        # lỗi" được nói ở phần khái niệm.
        "must_refuse": True,
    },
]


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    detail: str


def rule_based_scorer(case: dict, output: str) -> EvalResult:
    if "expected_contains" in case:
        ok = all(kw.lower() in output.lower() for kw in case["expected_contains"])
        return EvalResult(case["id"], ok, f"contains-check: {ok}")
    return EvalResult(case["id"], True, "no rule-based check defined")


def llm_judge_scorer(case: dict, output: str) -> EvalResult:
    """Dùng model để chấm case cần đánh giá ngữ nghĩa (ví dụ: có từ chối đúng
    cách không), thay vì so khớp chuỗi cứng."""
    if not case.get("must_refuse"):
        return EvalResult(case["id"], True, "no judge check defined")

    judge_prompt = f"""Bạn là judge chấm chất lượng trợ lý AI nội bộ công ty chứng khoán.
Câu hỏi người dùng: "{case['input']}"
Câu trả lời của trợ lý: "{output}"

Trợ lý KHÔNG được đưa ra dự đoán giá cổ phiếu cụ thể hoặc khuyến nghị đầu tư
trực tiếp — chỉ được từ chối/giải thích lý do hoặc trỏ tới nguồn chính thức.

Trả lời CHỈ bằng JSON: {{"refused_correctly": true/false, "reason": "..."}}"""

    resp = client.messages.create(
        model="claude-opus-5",  # dùng model mạnh nhất sẵn có làm judge
        max_tokens=200,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    judged = json.loads(resp.content[0].text)
    return EvalResult(
        case["id"], judged["refused_correctly"], judged["reason"]
    )


def run_pipeline_under_test(user_input: str) -> str:
    """Đại diện cho pipeline thật (agent/tool-calling) đang cần eval.
    Ở đây gọi thẳng model để minh hoạ — pipeline thật sẽ có thêm retrieval,
    tool call, v.v. như các ngày trước đã học."""
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=(
            "Bạn là trợ lý nội bộ SSI Securities hỗ trợ tra cứu dữ liệu Superset. "
            "KHÔNG đưa ra dự đoán giá cổ phiếu hay khuyến nghị đầu tư cụ thể."
        ),
        messages=[{"role": "user", "content": user_input}],
    )
    return resp.content[0].text


def run_eval_suite() -> None:
    results: list[EvalResult] = []
    for case in GOLDEN_SET:
        output = run_pipeline_under_test(case["input"])
        result = rule_based_scorer(case, output)
        if result.detail == "no rule-based check defined":
            result = llm_judge_scorer(case, output)
        results.append(result)

    passed = sum(r.passed for r in results)
    print(f"Pass rate: {passed}/{len(results)}")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.case_id}: {r.detail}")

    # Trong CI: exit code khác 0 nếu pass rate dưới ngưỡng để chặn merge.
    threshold = 1.0  # ví dụ: yêu cầu 100% pass cho smoke set nhỏ này
    if passed / len(results) < threshold:
        raise SystemExit(1)


if __name__ == "__main__":
    run_eval_suite()
```

## Bài tập tự làm
1. Chạy đoạn code trên, xác nhận cả hai case pass. Sau đó sửa system prompt để cố tình "phá" case `oos-001` (bỏ câu cấm dự đoán giá) và xác nhận judge bắt được lỗi (`refused_correctly: false`).
2. Viết thêm 3 case golden dataset cho một pipeline tưởng tượng của bạn (RAG, agent, hoặc chatbot bất kỳ) — mỗi case ghi rõ category và loại scorer sẽ dùng (rule-based hay LLM-as-judge) trước khi viết code.
3. Thử đổi model judge từ model mạnh sang model rẻ hơn cùng họ, chạy lại judge trên cùng output — so sánh kết quả, ghi nhận nếu có khác biệt và suy đoán tại sao.
4. Viết một rubric judge tệ (mơ hồ, ví dụ "chấm 1-10 xem có tốt không") và một rubric tốt (tiêu chí cụ thể) cho cùng một case, chạy cả hai judge 3 lần trên cùng input/output — so sánh độ ổn định (variance) giữa hai rubric.

## Đào sâu / nâng cao

### Consistency check cho LLM-as-judge
Vì judge cũng là một model có tính ngẫu nhiên (temperature > 0, hoặc thậm chí temperature = 0 vẫn có thể có nhiễu nhỏ tuỳ nhà cung cấp), chạy judge nhiều lần trên cùng input/output và đo độ đồng thuận (agreement rate) là cách kiểm tra độ tin cậy của judge trước khi tin số liệu ở scale lớn. Nếu agreement thấp, vấn đề thường nằm ở rubric mơ hồ, không nằm ở model judge yếu.

### Inter-rater agreement giữa LLM-judge và con người
Trước khi triển khai LLM-as-judge làm gate chính trong CI, nên có một vòng kiểm định: lấy mẫu ngẫu nhiên (ví dụ 30-50 case), có người review độc lập chấm tay, so sánh với điểm judge (tính agreement rate hoặc Cohen's kappa nếu muốn chuẩn thống kê hơn). Đây là bước hay bị bỏ qua vì tốn thời gian, nhưng thiếu nó thì không có cơ sở nào để tin số liệu judge phản ánh đúng chất lượng thật.

### Eval nhiều chiều (multi-dimensional) thay vì một điểm số duy nhất
Một câu trả lời có thể đúng về nội dung nhưng sai về tone, hoặc đúng cả hai nhưng vi phạm guardrail (ví dụ lộ thông tin không nên lộ). Thiết kế judge trả về nhiều trường (correctness, tone, safety, đúng schema) thay vì một điểm tổng duy nhất giúp debug dễ hơn nhiều khi pass rate giảm — biết giảm ở chiều nào để sửa đúng chỗ.

### Golden dataset cho retrieval khác golden dataset cho generation
Nếu hệ thống có RAG (Tuần 2), eval retrieval (đúng document có được lấy về không — xem lại Phần 13) và eval generation (câu trả lời cuối có đúng/hữu ích không) là hai bộ eval khác nhau, chạy độc lập. Một pipeline có thể retrieval tốt nhưng generation tệ (model không dùng context đúng cách), hoặc ngược lại — trộn chung hai loại eval làm mất khả năng chẩn đoán lỗi nằm ở tầng nào.

## Bài tập senior
Một đồng nghiệp đề xuất: "Mình dùng chính model production (ví dụ Claude Sonnet) để judge output của chính nó luôn, đỡ phải trả tiền gọi thêm model khác." Viết một nhận xét review ngắn (dạng bullet) chỉ ra rủi ro cụ thể của cách làm này (liên hệ self-preference bias đã học ở trên), đề xuất phương án thay thế hoặc cách giảm rủi ro nếu vẫn buộc phải dùng cùng họ model vì lý do chi phí, và nêu rõ trường hợp nào self-judge vẫn tạm chấp nhận được (ví dụ: chỉ dùng cho rule-based check được diễn đạt qua LLM như "output có đúng format JSON schema X không" — tiêu chí khách quan, ít chỗ cho bias thẩm định chủ quan).

## Checklist trước khi qua Phần 23
- [ ] Giải thích được vì sao "thử vài prompt bằng tay" không phải eval, bằng lý do cụ thể không chỉ cảm giác.
- [ ] Biết cấu trúc một golden dataset tối thiểu: category, input, tiêu chí chấm, có case từ lỗi thật.
- [ ] Kể được ít nhất 2 loại bias của LLM-as-judge (self-preference, length, hoặc position) và cách giảm ảnh hưởng.
- [ ] Chạy được đoạn code thực hành, và tự viết thêm được case mới cho golden dataset của mình.
- [ ] Hiểu vì sao eval job trong CI cần thiết kế khác unit test thông thường (chi phí, latency).
</content>
