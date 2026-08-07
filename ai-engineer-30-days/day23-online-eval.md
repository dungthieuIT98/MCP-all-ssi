# Ngày 23 — Online eval & A/B: theo dõi chất lượng khi đã lên production

## Mục tiêu hôm nay
Hiểu vì sao offline eval (Ngày 22) không đủ khi hệ thống đã chạy production, và nắm được các kỹ thuật online eval: shadow testing, canary rollout, feedback signal thật, và theo dõi drift khi model thay đổi ngầm.

## Đọc trước
- [Anthropic docs](https://docs.anthropic.com/) — mục về model versioning/deprecation (tìm "model deprecations", nội dung/URL cụ thể tra tại thời điểm đọc).
- Tài liệu chung LLMOps về online evaluation, A/B testing cho ML system — tìm theo từ khoá "online evaluation LLM", "shadow deployment machine learning", không có nguồn chính thức duy nhất, đối chiếu nhiều nguồn.
- Đọc lại `day22-eval-framework.md` — online eval là phần bổ sung, không thay thế offline eval.

## Khái niệm cốt lõi

### Vì sao offline eval không đủ
Golden dataset dù được xây cẩn thận vẫn chỉ phản ánh những gì engineer *đã biết* là quan trọng. Traffic thật luôn có case chưa từng nghĩ tới: cách diễn đạt câu hỏi lạ, ngôn ngữ trộn, câu hỏi ở biên giữa hai category, hoặc hành vi user thay đổi theo thời gian (ví dụ câu hỏi về một sự kiện thị trường mới xảy ra mà dataset cũ không có). Offline eval trả lời "hệ thống có còn đúng như kỳ vọng cũ không", nhưng không trả lời được "hệ thống đang thực sự làm tốt cho user thật hôm nay không". Hai câu hỏi này bổ sung cho nhau — online eval không thay thế offline eval, nó lấp phần offline không thấy được.

### Shadow testing
Chạy một phiên bản mới (model mới, prompt mới, pipeline mới) **song song** với phiên bản đang phục vụ user thật, trên cùng traffic thật, nhưng **không trả kết quả của phiên bản mới cho user** — chỉ log lại để so sánh offline sau đó.

- Cách làm: mỗi request thật vẫn được xử lý bình thường bởi phiên bản hiện tại (trả về cho user), đồng thời fire một request giống hệt input đó tới phiên bản mới (thường async, không block response cho user), lưu output của cả hai để so sánh.
- Lợi ích: kiểm tra được phiên bản mới trên **traffic thật 100%**, không có rủi ro ảnh hưởng tới user vì user không bao giờ thấy output của phiên bản shadow.
- Chi phí thật cần tính: mỗi request giờ tốn gấp đôi lệnh gọi API (cả bản cũ và bản mới đều chạy) — với hệ thống LLM, đây là chi phí tiền thật đáng kể, không phải chi phí "miễn phí" như shadow testing cho một service CRUD thông thường. Cần cân nhắc chạy shadow trên một tỷ lệ mẫu (ví dụ 5-10% traffic) thay vì 100% nếu chi phí là vấn đề.
- Hạn chế: không đo được phản ứng thật của user (vì user không thấy output mới) — chỉ so sánh được output hai bên bằng eval tự động (rule-based hoặc LLM-as-judge như Ngày 22), không đo được engagement/satisfaction thật.

### Canary rollout
Đưa phiên bản mới ra phục vụ **một phần nhỏ user thật** (ví dụ 1%, 5%), theo dõi metric sát sao, tăng dần tỷ lệ nếu ổn, rollback ngay nếu metric xấu đi.

- Khác shadow testing ở điểm mấu chốt: canary user **thực sự nhận** output của phiên bản mới — có rủi ro thật nếu phiên bản mới tệ hơn, nhưng đổi lại đo được phản ứng thật (feedback signal, tỉ lệ hỏi lại, escalate — xem phần dưới).
- Chọn tỷ lệ canary và tiêu chí tăng/rollback là quyết định sản phẩm + kỹ thuật kết hợp: tỷ lệ quá nhỏ thì mất nhiều thời gian mới đủ mẫu để kết luận có ý nghĩa thống kê; tỷ lệ quá lớn thì rủi ro ảnh hưởng nhiều user nếu phiên bản mới có lỗi.
- Cần cơ chế rollback nhanh (feature flag hoặc routing layer chuyển lại 100% traffic về phiên bản cũ trong vài giây/phút) — không có cơ chế này thì canary chỉ là "thử rồi hy vọng", không phải quy trình production thật.
- Với hệ thống LLM, một khác biệt so với canary rollout truyền thống (web service): metric "lỗi" không chỉ là HTTP 5xx hay latency, mà còn là chất lượng nội dung (câu trả lời sai, tone không phù hợp) — loại lỗi này thường không tự động hiện ra qua log lỗi kỹ thuật, cần feedback signal riêng.

### Feedback signal thật — proxy cho chất lượng khi không có "đáp án đúng"
Trên production, không có ai chấm điểm mỗi câu trả lời theo golden dataset — cần tín hiệu gián tiếp (proxy) để suy ra chất lượng đang tốt hay xấu:

- **Thumbs up/down (explicit feedback)**: tín hiệu rõ ràng nhất nhưng tỷ lệ user chủ động bấm thường rất thấp (hầu hết user không bấm gì cả dù hài lòng hay không) — không nên coi tỷ lệ thumbs down/tổng số request là "tỷ lệ lỗi thật", chỉ nên coi là một tín hiệu bổ sung, và theo dõi *xu hướng thay đổi* của nó qua thời gian quan trọng hơn giá trị tuyệt đối tại một thời điểm.
- **Tỉ lệ user sửa lại câu hỏi (rephrase rate)**: nếu user hỏi lại gần như ngay sau đó với cách diễn đạt khác cho cùng ý định, đây là proxy mạnh cho "câu trả lời trước không đáp ứng được" — user hiếm khi diễn đạt lại một câu hỏi mà họ đã hài lòng với câu trả lời. Cần định nghĩa "gần như ngay sau đó" (ví dụ trong cùng session, trong X giây) và có heuristic/embedding similarity để phát hiện "cùng ý định, câu chữ khác" thay vì so khớp chuỗi.
- **Tỉ lệ escalate lên người**: nếu hệ thống có đường thoát "chuyển cho người xử lý" (ví dụ chatbot hỗ trợ chuyển sang nhân viên), tỉ lệ escalate tăng đột biến là tín hiệu mạnh — model đang gặp nhiều case nó không xử lý được, hoặc user không tin tưởng câu trả lời. Theo dõi escalate rate theo category câu hỏi giúp khoanh vùng model yếu ở đâu.
- **Session abandonment**: user rời đi giữa hội thoại không hoàn thành mục đích — khó đo chính xác "mục đích" là gì nếu không có định nghĩa rõ, nhưng là tín hiệu bổ sung hữu ích khi kết hợp với các tín hiệu khác.

Nguyên tắc chung: không tín hiệu nào một mình là đủ, tất cả đều là proxy có nhiễu — cần nhìn nhiều tín hiệu cùng lúc và theo dõi xu hướng (trend) qua thời gian, so sánh giữa các version, thay vì đọc một số tuyệt đối rồi kết luận ngay.

### Drift khi nhà cung cấp cập nhật model ngầm
Rủi ro đặc thù của hệ thống dựa trên model do bên thứ ba cung cấp qua API: **endpoint/tên model giữ nguyên nhưng hành vi model thay đổi** vì nhà cung cấp cập nhật ngầm phiên bản phía sau (ví dụ một alias model không pin version cụ thể, hoặc nhà cung cấp âm thầm thay weights cho cùng version cũ để vá lỗi/cải thiện).

- Đây không phải giả định lý thuyết — đây là rủi ro vận hành thật của bất kỳ hệ thống gọi API model bên ngoài, vì engineer không kiểm soát được thời điểm/nội dung thay đổi phía nhà cung cấp.
- Cách giảm rủi ro:
  - **Pin version cụ thể** khi nhà cung cấp cho phép (ví dụ dùng tên model có ngày phát hành cụ thể thay vì alias "mới nhất") — giảm khả năng bị đổi ngầm, nhưng vẫn cần theo dõi thông báo deprecation vì version cụ thể cũng có ngày hết hỗ trợ.
  - **Theo dõi thông báo/changelog của nhà cung cấp** đều đặn — không đợi tự phát hiện qua lỗi production.
  - **Chạy lại golden dataset (Ngày 22) định kỳ, không chỉ khi có PR đổi code** — nếu điểm eval tự nhiên giảm mà không có thay đổi code nào ở phía mình, dấu hiệu mạnh là model phía nhà cung cấp đã đổi hành vi.
  - **Theo dõi metric hành vi output** (độ dài trung bình, tỉ lệ refuse, format có ổn định không) theo thời gian — thay đổi đột ngột dù request pattern không đổi là tín hiệu cảnh báo sớm.
- Đây là lý do online eval không phải việc làm một lần rồi xong — cần chạy liên tục, vì "hệ thống không đổi gì" không đảm bảo "model không đổi gì".

## Đối chiếu với code thật trong repo
`mcp-superset` hiện là một MCP server thuần túy tool-calling, không tự chạy A/B hay canary ở tầng application — routing/rollout dạng này thường nằm ở tầng hạ tầng phía trên (API gateway, hoặc chính client AI gọi vào server). Điểm liên hệ thực tế: nếu một ngày cần thử nghiệm một phiên bản mới của tool `superset_dataset_get_by_id` (ví dụ đổi cách format response để agent hiểu tốt hơn), một shadow test hợp lý là: log lại mọi request/response thật qua `handle_api_errors` (`utils/decorators.py`) hiện tại, chạy song song phiên bản mới của hàm trên cùng input đã log, so sánh output bằng eval tự động — mà không đổi hành vi trả cho client thật. Vì mỗi tool đều trả JSON có cấu trúc rõ (`{"error": ...}` khi lỗi), so sánh output cũ/mới có thể làm bằng diff cấu trúc trước khi cần tới LLM-as-judge.

## Thực hành
```python
"""
Minh hoạ shadow testing đơn giản: mỗi request thật vẫn trả lời bằng model
hiện tại (production), đồng thời fire song song một request tới model "ứng
viên" (candidate) để log so sánh — không bao giờ trả output candidate cho
người dùng thật. Chạy được với `pip install anthropic`.
"""
import asyncio
import json
import time
from dataclasses import dataclass, asdict

import anthropic

client = anthropic.AsyncClient()

PRODUCTION_MODEL = "claude-sonnet-4-5-20250929"
CANDIDATE_MODEL = "claude-opus-4-1-20250805"  # ví dụ: đang thử model mạnh hơn


@dataclass
class ShadowLogEntry:
    user_input: str
    production_output: str
    candidate_output: str
    production_latency_ms: float
    candidate_latency_ms: float


async def call_model(model: str, user_input: str) -> tuple[str, float]:
    start = time.perf_counter()
    resp = await client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": user_input}],
    )
    latency_ms = (time.perf_counter() - start) * 1000
    return resp.content[0].text, latency_ms


async def handle_request(user_input: str) -> str:
    """Đây là hàm thật xử lý request user — chỉ trả về kết quả production."""
    production_output, production_latency = await call_model(
        PRODUCTION_MODEL, user_input
    )

    # Fire-and-forget: chạy candidate song song, không block response cho user,
    # không để lỗi ở candidate ảnh hưởng tới response thật.
    asyncio.create_task(
        run_shadow_and_log(user_input, production_output, production_latency)
    )

    return production_output  # user chỉ nhận output này


async def run_shadow_and_log(
    user_input: str, production_output: str, production_latency: float
) -> None:
    try:
        candidate_output, candidate_latency = await call_model(
            CANDIDATE_MODEL, user_input
        )
    except Exception as e:
        # Lỗi ở candidate KHÔNG được để ảnh hưởng tới hệ thống thật —
        # chỉ log lại để biết candidate có vấn đề.
        print(f"[shadow] candidate error (không ảnh hưởng user thật): {e}")
        return

    entry = ShadowLogEntry(
        user_input=user_input,
        production_output=production_output,
        candidate_output=candidate_output,
        production_latency_ms=production_latency,
        candidate_latency_ms=candidate_latency,
    )
    # Production thật: đẩy vào hàng đợi/log store để phân tích batch sau,
    # không print ra stdout.
    print("[shadow-log]", json.dumps(asdict(entry), ensure_ascii=False))


async def main():
    test_inputs = [
        "Cho tôi biết dataset nào chứa dữ liệu doanh thu quý 3.",
        "Cách tạo dashboard mới trong Superset như thế nào?",
    ]
    for user_input in test_inputs:
        output = await handle_request(user_input)
        print(f"User nhận được: {output[:80]}...")
        await asyncio.sleep(0.1)  # để shadow task có thời gian log trước khi thoát demo


if __name__ == "__main__":
    asyncio.run(main())
```

## Bài tập tự làm
1. Chạy đoạn code trên, quan sát log shadow xuất hiện sau khi user đã "nhận" response — xác nhận thứ tự này (user không phải đợi candidate).
2. Thêm một bước so sánh tự động vào `run_shadow_and_log`: dùng LLM-as-judge (như Ngày 22) để chấm "candidate_output có tốt hơn production_output không", log kết quả so sánh thay vì chỉ log raw text.
3. Giả lập một escalate signal: viết một hàm `detect_rephrase(session_history: list[str]) -> bool` heuristic đơn giản (ví dụ so sánh độ dài chuỗi chung — hoặc dùng embedding similarity nếu đã học Ngày 8) phát hiện 2 câu hỏi liên tiếp trong session có cùng ý định nhưng câu chữ khác nhau.
4. Viết một bảng (dạng markdown) so sánh shadow testing và canary rollout theo 4 tiêu chí: rủi ro cho user thật, chi phí vận hành, tốc độ có kết luận, loại tín hiệu đo được.

## Đào sâu / nâng cao

### Ý nghĩa thống kê khi đọc kết quả A/B với LLM
Vì output LLM có phương sai (variance) tự nhiên cao hơn nhiều so với metric web service thông thường (một câu hỏi giống nhau có thể ra hai câu trả lời khác cách diễn đạt), cần cẩn trọng khi kết luận "version B tốt hơn version A" chỉ từ vài chục mẫu — nguy cơ kết luận sai (false positive) cao nếu không đủ mẫu hoặc không kiểm định thống kê. Đọc thêm về A/B testing cơ bản (kiểm định giả thuyết, cỡ mẫu cần thiết) nếu chưa quen — nguyên lý thống kê không đổi khi áp dụng cho LLM, chỉ là biến số đo (chất lượng câu trả lời) khó định lượng hơn latency hay tỉ lệ lỗi HTTP.

### Multi-armed bandit thay cho A/B tĩnh
Với hệ thống có nhiều lựa chọn (nhiều prompt, nhiều model) cần tối ưu liên tục, một số hệ thống dùng thuật toán multi-armed bandit để tự động phân bổ traffic nhiều hơn cho phương án đang tốt hơn, ít hơn cho phương án kém, thay vì cố định tỷ lệ 50/50 suốt quá trình test. Phức tạp hơn A/B tĩnh, chỉ đáng đầu tư khi có volume traffic đủ lớn để thuật toán học nhanh hơn con người theo dõi dashboard thủ công.

### Human review sampling cho production traffic
Ngoài feedback signal tự động, một số hệ thống nghiêm túc còn có quy trình người thật review một mẫu ngẫu nhiên nhỏ traffic production hằng ngày/hằng tuần (không phải toàn bộ — không scale được) để bắt các lỗi mà signal tự động không thấy (ví dụ output đúng về hình thức nhưng sai tinh tế về nội dung chuyên ngành). Với domain tài chính, nơi sai sót có thể có hậu quả nghiêm trọng, loại review này nên được cân nhắc nghiêm túc hơn ở các domain ít rủi ro.

## Bài tập senior
Hệ thống production của bạn dùng một model qua API bên thứ ba với tên model dạng alias (không pin version cụ thể, vì nhà cung cấp khuyến nghị dùng alias để tự nhận bản cập nhật mới nhất). Tuần trước, pass rate trên golden dataset (chạy nightly) giảm 8 điểm phần trăm so với tuần trước đó, không có PR nào đổi code hay prompt trong khoảng thời gian đó. Viết một quy trình điều tra (dạng bước, không cần code) bạn sẽ làm để xác nhận/loại trừ giả thuyết "nhà cung cấp đã đổi model ngầm", và đề xuất 2 thay đổi vận hành để giảm rủi ro loại này xảy ra lại (đánh đổi giữa lợi ích tự nhận bản mới nhất và rủi ro bị đổi hành vi ngoài kiểm soát).

## Checklist trước khi qua Ngày 24
- [ ] Phân biệt được shadow testing và canary rollout: rủi ro, chi phí, loại tín hiệu đo được của mỗi cách.
- [ ] Kể được ít nhất 3 loại feedback signal thật và biết vì sao mỗi loại chỉ là proxy có nhiễu, không phải chân lý tuyệt đối.
- [ ] Giải thích được rủi ro drift khi nhà cung cấp đổi model ngầm, và ít nhất 2 cách giảm rủi ro.
- [ ] Chạy được đoạn code shadow testing thực hành và hiểu vì sao lỗi ở candidate không được ảnh hưởng tới response thật.
</content>
