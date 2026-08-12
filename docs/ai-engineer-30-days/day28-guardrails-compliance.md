# Phần 28 — Guardrail production & compliance cho ngành tài chính (SSI-context)

## Mục tiêu hôm nay
Nắm được các lớp guardrail cần có khi đưa AI vào production trong môi trường công ty chứng khoán chịu quản lý của UBCKNN, và biết rõ ranh giới việc nào AI được làm, việc nào bắt buộc phải qua con người — đồng thời biết khi nào cần dừng lại hỏi Pháp lý/Tuân thủ/An toàn thông tin thay vì tự quyết định.

## Đọc trước
- [Anthropic docs](https://docs.anthropic.com/) — mục về Usage Policy/Acceptable Use nếu có (tìm trong docs, nội dung/URL cụ thể tra tại thời điểm đọc) — tham khảo cách một nhà cung cấp model lớn đặt ranh giới sử dụng có trách nhiệm.
- Đọc lại `day27-llm-security.md` trong bộ tài liệu này — guardrail input/output ở ngày này là lớp kỹ thuật bổ sung trực tiếp cho các rủi ro đã học ở Phần 27.
- Văn bản pháp luật/quy định hiện hành liên quan bảo vệ dữ liệu cá nhân và AI tại Việt Nam — không liệt kê số hiệu cụ thể ở đây vì có thể thay đổi/cập nhật, tra trực tiếp với bộ phận Pháp lý & Tuân thủ hoặc cổng thông tin văn bản pháp luật chính thức khi cần áp dụng cho tình huống thật.
- Nội bộ SSI: liên hệ `security@ssi.com.vn` khi có tình huống thật liên quan dữ liệu nhạy cảm/khách hàng cần đánh giá — không tự suy diễn chính sách nội bộ SSI từ tài liệu học tập này.

## Khái niệm cốt lõi

### Vì sao Tuần 4 kết thúc ở compliance, không phải kỹ thuật
21 ngày trước xây năng lực kỹ thuật (prompt, RAG, agent), Phần 22-27 xây năng lực vận hành production (eval, cost, latency, security). Phần 28 đặt toàn bộ năng lực đó vào **ràng buộc thật của ngành**: một hệ thống AI kỹ thuật tốt nhưng vi phạm quy định ngành chứng khoán hoặc gây rủi ro dữ liệu khách hàng không phải là hệ thống "gần xong, còn thiếu vài polish" — nó là hệ thống không được phép chạy production cho tới khi được rà soát đúng quy trình. Senior AI engineer trong ngành tài chính cần biết đủ về compliance để **tự nhận ra khi nào cần dừng lại hỏi**, không cần biết đủ để tự ra quyết định compliance thay bộ phận có thẩm quyền — đây là ranh giới quan trọng của chính ngày học này.

### Input/output guardrail
Guardrail là lớp kiểm soát đặt quanh lệnh gọi model (trước khi gửi input, sau khi nhận output), độc lập với việc model "tự giác" tuân theo system prompt hay không — vì đã học ở Phần 27, không có system prompt nào đảm bảo tuyệt đối model không bị injection dẫn sai hướng.

- **Input guardrail**: kiểm tra/lọc trước khi input tới model — content filter (chặn nội dung vi phạm chính sách rõ ràng trước khi tốn tiền gọi model), phát hiện input có dấu hiệu injection (heuristic hoặc model rẻ làm classifier — tương tự vai trò "trọng tài" ở Phần 24 nhưng cho mục đích an toàn thay vì cost), rate limiting theo user để giảm rủi ro dò/khai thác hệ thống bằng số lượng lớn request thử nghiệm.
- **Output guardrail**: kiểm tra/lọc sau khi model trả lời, trước khi hiển thị cho user hoặc dùng ở bước tiếp theo — **PII detection/redaction** là guardrail quan trọng nhất trong ngữ cảnh tài chính: quét output (và log — liên hệ lại Phần 26) tìm mẫu số tài khoản, số CMND/CCCD, thông tin định danh khách hàng trước khi output đó được log ra hệ thống observability hoặc gửi ra ngoài phạm vi cần thiết. Không dựa vào việc "model đã được hướng dẫn không tiết lộ" — guardrail output là lớp kiểm tra độc lập, chạy bằng rule/model riêng, không tin tưởng một chiều vào hành vi tự giác của model chính.
- Nguyên tắc thiết kế: guardrail nên **fail-safe** — nếu guardrail bản thân gặp lỗi hoặc không chắc chắn, xử lý theo hướng an toàn hơn (từ chối/che dữ liệu) thay vì để lọt qua vì lỗi. Một guardrail bị lỗi và "mở toang" âm thầm nguy hiểm hơn một guardrail chặn nhầm một vài case hợp lệ.

### Human-in-the-loop bắt buộc cho quyết định có tính ràng buộc
Nguyên tắc chung của ngành tài chính (áp dụng rộng, không riêng AI): **hệ thống AI không được tự đưa ra khuyến nghị đầu tư cụ thể hoặc quyết định giao dịch mà không qua con người review**. Đây là nguyên tắc chung cần được tuân thủ ở mức kiến trúc hệ thống, không phải chỉ ở mức "nhắc model trong system prompt đừng làm vậy":

- Bất kỳ tính năng AI có khả năng sinh ra nội dung có thể bị hiểu là khuyến nghị đầu tư, dự đoán giá, hoặc quyết định liên quan giao dịch cho khách hàng — cần có một bước con người xác nhận/ký duyệt trước khi nội dung đó tới tay khách hàng hoặc được dùng để hành động, không để pipeline tự động chạy thẳng từ input tới output cuối.
- Điều này áp dụng cả khi AI chỉ đóng vai trò "hỗ trợ soạn draft" cho nhân viên (không trực tiếp gửi cho khách hàng) — người soạn/duyệt cuối vẫn là nhân viên có trách nhiệm, AI là công cụ hỗ trợ, không phải người ra quyết định.
- Đây là nguyên tắc chung của ngành, **không phải một kết luận pháp lý cụ thể của bộ tài liệu này** — theo quy định hiện hành về AI và bảo vệ dữ liệu cá nhân, cần rà soát cùng bộ phận Tuân thủ/Pháp lý trước khi triển khai bất kỳ tính năng thật nào có khả năng đưa ra nội dung kiểu này, để xác nhận đúng phạm vi và cách áp dụng cụ thể cho từng use case tại SSI.
- Việc thiết kế "điểm dừng" (approval gate) này nên nằm ở tầng kiến trúc — ví dụ agent có thể soạn draft khuyến nghị nhưng tool "gửi ra ngoài"/"thực thi giao dịch" phải yêu cầu một tín hiệu duyệt riêng từ người có thẩm quyền, không để model tự quyết định bỏ qua bước này dù được yêu cầu qua prompt.

### Disclosure khi output có AI hỗ trợ tạo ra
Một số ngành/khu vực pháp lý có yêu cầu ghi rõ khi nội dung được AI hỗ trợ tạo ra (ví dụ trong báo cáo, tài liệu gửi ra ngoài, hoặc giao tiếp với khách hàng) — mức độ và hình thức yêu cầu cụ thể (nếu có) cần xác nhận với bộ phận Pháp lý/Tuân thủ theo quy định hiện hành áp dụng cho SSI, bộ tài liệu này không đưa ra kết luận pháp lý cụ thể vì không có thẩm quyền và không chắc chắn về số hiệu văn bản áp dụng tại từng thời điểm. Về mặt kỹ thuật, việc chuẩn bị sẵn sàng cho yêu cầu này (nếu có) là việc đơn giản — gắn metadata "AI-assisted" vào nội dung sinh ra ngay từ tầng lưu trữ/log (liên hệ lại Phần 26), để khi cần bổ sung disclosure ra bề mặt hiển thị, không phải truy vết lại xem nội dung nào có AI tham gia tạo ra.

### Khi nào dừng lại và hỏi ai
Bảng ranh giới thực dụng (không thay thế quy trình chính thức của SSI, chỉ là khung tư duy để biết khi nào cần dừng):

- **Phát hiện/nghi ngờ dữ liệu nhạy cảm bị lộ qua log, output, hoặc tool call** (PII khách hàng, thông tin tài khoản, thông tin nội bộ chưa công bố) → liên hệ `security@ssi.com.vn` ngay, không tự xử lý một mình rồi coi như đã xong.
- **Tính năng AI có khả năng sinh nội dung dạng khuyến nghị đầu tư/quyết định giao dịch** → cần bộ phận Tuân thủ/Pháp lý rà soát trước khi triển khai, không tự quyết định "chắc ổn" rồi launch.
- **Câu hỏi về việc một tính năng có vi phạm quy định UBCKNN hay luật bảo vệ dữ liệu cá nhân hay không** → đây là câu hỏi pháp lý, không phải câu hỏi kỹ thuật — trả lời bằng bộ phận Pháp lý & Tuân thủ, không tự suy diễn từ hiểu biết kỹ thuật cá nhân dù có đọc qua văn bản luật.
- **Sự cố thật đã xảy ra** (data bị exfiltrate, injection thành công gây hậu quả, model đưa ra nội dung sai gây ảnh hưởng khách hàng) → quy trình incident response của tổ chức, không phải quy trình debug thông thường — báo cáo sớm quan trọng hơn tự điều tra xong mới báo.

## Đối chiếu với code thật trong repo
`pyproject.toml` của `mcp-superset` ghi tác giả là `"DTO Data Team, SSI Securities"` — bản thân việc một MCP server nội bộ được ghi rõ chủ sở hữu, đơn vị chịu trách nhiệm ngay trong metadata dự án là một thực hành tốt về mặt governance: khi có câu hỏi compliance hoặc sự cố liên quan tới cách server này xử lý dữ liệu (ví dụ dữ liệu Superset có chứa thông tin nhạy cảm được agent truy vấn), biết ngay đơn vị chịu trách nhiệm kỹ thuật để phối hợp với Pháp lý/Tuân thủ, không phải đi tìm "ai viết cái này". Về mặt guardrail, `core/context.py` đảm bảo mọi truy vấn qua server đi theo đúng identity thật của người dùng (không có service-account credential dùng chung) — đây là nền tảng kỹ thuật quan trọng để **quy trách nhiệm đúng người** khi audit: nếu một truy vấn Superset trả về dữ liệu vượt quyền, thiết kế forward session cookie theo identity thật giúp truy vết đúng ai đã request, dựa trên row-level security (RLS) mà Superset tự áp dụng theo quyền của user đó — chứ không phải bản thân MCP server tự quyết định quyền truy cập. Nếu tương lai có ai định thêm một service-account credential chung "cho tiện" vào server này, đó là thay đổi cần đặc biệt cẩn trọng dưới góc nhìn compliance vì nó xoá bỏ khả năng quy trách nhiệm theo từng cá nhân.

## Thực hành
```python
"""
Minh hoạ 1 lớp guardrail tối thiểu cho ngữ cảnh tài chính: input classifier
(chặn/flag câu hỏi có dấu hiệu yêu cầu khuyến nghị đầu tư cụ thể) + output PII
scan trước khi trả lời/log + gắn metadata AI-assisted. Đây là minh hoạ NGUYÊN
LÝ, không phải guardrail production đầy đủ — hệ thống thật cần bộ rule/model
được Pháp lý & Tuân thủ rà soát, không chỉ dựa vào ví dụ này.
Chạy được với `pip install anthropic`.
"""
import re
from dataclasses import dataclass

import anthropic

client = anthropic.Anthropic()

ACCOUNT_PATTERN = re.compile(r"\b\d{8,12}\b")
# Heuristic đơn giản minh hoạ input guardrail — production thật nên dùng
# classifier được huấn luyện/rà soát kỹ hơn 1 danh sách từ khoá cứng.
INVESTMENT_ADVICE_KEYWORDS = [
    "nên mua", "nên bán", "dự đoán giá", "khuyến nghị mua", "khuyến nghị bán",
    "có nên đầu tư",
]


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str
    redacted_text: str = ""


def input_guardrail(user_input: str) -> GuardrailResult:
    lowered = user_input.lower()
    for kw in INVESTMENT_ADVICE_KEYWORDS:
        if kw in lowered:
            return GuardrailResult(
                allowed=False,
                reason=(
                    "Câu hỏi có dấu hiệu yêu cầu khuyến nghị đầu tư/dự đoán giá "
                    "cụ thể — theo nguyên tắc chung ngành tài chính, hệ thống AI "
                    "không tự đưa ra loại nội dung này. Cần chuyển yêu cầu này "
                    "tới người có thẩm quyền (ví dụ chuyên viên tư vấn), không "
                    "xử lý tự động."
                ),
            )
    return GuardrailResult(allowed=True, reason="ok")


def output_guardrail(model_output: str) -> GuardrailResult:
    """Quét PII trước khi output được hiển thị hoặc log — fail-safe: nếu quét
    thấy nghi ngờ, redact trước, không để lộ ra ngoài rồi mới xử lý."""
    redacted = ACCOUNT_PATTERN.sub("[DA_CHE_SO]", model_output)
    has_pii = redacted != model_output
    return GuardrailResult(
        allowed=True,  # PII được redact, không chặn hoàn toàn câu trả lời
        reason="pii_redacted" if has_pii else "clean",
        redacted_text=redacted,
    )


def handle_request(user_input: str) -> dict:
    input_check = input_guardrail(user_input)
    if not input_check.allowed:
        return {
            "response": (
                "Yêu cầu này cần được chuyên viên có thẩm quyền xử lý trực "
                "tiếp, hệ thống không tự động trả lời loại câu hỏi này."
            ),
            "blocked_reason": input_check.reason,
            "ai_assisted": False,
        }

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=(
            "Bạn là trợ lý nội bộ SSI Securities hỗ trợ tra cứu dữ liệu "
            "Superset. Không đưa ra khuyến nghị đầu tư hay dự đoán giá cụ thể."
        ),
        messages=[{"role": "user", "content": user_input}],
    )
    raw_output = response.content[0].text

    output_check = output_guardrail(raw_output)

    # Gắn metadata "AI-assisted" ngay tại tầng xử lý — chuẩn bị sẵn cho yêu
    # cầu disclosure nếu Pháp lý/Tuân thủ xác nhận cần áp dụng, không phải
    # truy vết lại sau này.
    return {
        "response": output_check.redacted_text,
        "blocked_reason": None,
        "ai_assisted": True,
        "pii_redacted": output_check.reason == "pii_redacted",
    }


if __name__ == "__main__":
    print("--- Câu hỏi bình thường ---")
    print(handle_request("Dataset nào chứa dữ liệu doanh thu quý 3?"))

    print("\n--- Câu hỏi yêu cầu khuyến nghị đầu tư (phải bị chặn) ---")
    print(handle_request("Tôi có nên đầu tư vào cổ phiếu ABC không?"))
```

## Bài tập tự làm
1. Chạy đoạn code trên, xác nhận câu hỏi khuyến nghị đầu tư bị chặn đúng, và câu hỏi bình thường vẫn được trả lời có kèm `ai_assisted: True`.
2. Thử 3 cách diễn đạt khác cho câu hỏi khuyến nghị đầu tư mà không dùng đúng từ khoá trong `INVESTMENT_ADVICE_KEYWORDS` (ví dụ diễn đạt gián tiếp) — xác nhận guardrail heuristic đơn giản này có bị lách qua không, từ đó tự rút ra vì sao production cần classifier mạnh hơn danh sách từ khoá cứng.
3. Viết thêm 1 guardrail output kiểm tra "câu trả lời có vô tình chứa nội dung dạng khuyến nghị dù câu hỏi ban đầu không yêu cầu" (ví dụ model tự chèn thêm nhận định giá vào câu trả lời về chủ đề khác) — gợi ý dùng LLM-as-judge (Phần 22) thay vì regex vì đây là kiểm tra ngữ nghĩa.
4. Viết ra (không cần code) quy trình bạn sẽ làm nếu guardrail ở bài tập 2 cho thấy rất dễ bị lách — ai cần được thông báo, và đây có phải quyết định bạn tự xử lý một mình hay cần leo thang (escalate) cho ai.

## Đào sâu / nâng cao

### Guardrail là lớp bổ sung, không thay thế review con người
Toàn bộ guardrail kỹ thuật ở ngày này (input/output filter, PII redaction) là lớp phòng vệ kỹ thuật giảm rủi ro, **không phải sự thay thế** cho quy trình rà soát compliance chính thức hoặc human-in-the-loop cho quyết định có tính ràng buộc. Một sai lầm hay gặp là nghĩ "đã có guardrail tự động rồi, không cần người duyệt nữa" — hai lớp này giải quyết vấn đề khác nhau: guardrail chặn lỗi rõ ràng/phổ biến ở quy mô lớn, con người xử lý phần rủi ro cao/tinh vi mà guardrail tự động không đủ tin cậy để quyết định một mình.

### Audit trail cho quyết định của AI trong hệ thống có ràng buộc pháp lý
Với hệ thống tài chính, khả năng **truy vết lại** (audit) toàn bộ quyết định của AI — input gì, guardrail nào chạy, ai duyệt (nếu có human-in-the-loop), output cuối là gì — quan trọng không kém khả năng chặn lỗi ngay lúc đó. Liên hệ trực tiếp với observability (Phần 26): log đầy đủ có cấu trúc, giữ đủ lâu theo yêu cầu lưu trữ (thời hạn cụ thể cần xác nhận với Tuân thủ/Pháp lý, không tự đặt theo cảm tính kỹ thuật), là điều kiện cần để trả lời được câu hỏi audit "hệ thống đã làm gì, dựa trên cơ sở nào" khi có yêu cầu kiểm tra.

### Data residency và việc gửi dữ liệu ra ngoài qua API model bên thứ ba
Khi gọi API của một nhà cung cấp model bên ngoài, dữ liệu trong prompt (bao gồm context RAG, lịch sử hội thoại) đi ra khỏi hạ tầng nội bộ SSI, dù chỉ trong thời gian xử lý request. Với dữ liệu khách hàng/nhạy cảm, đây là điểm cần rà soát cùng An toàn thông tin/Pháp lý trước khi quyết định kiến trúc (dùng API bên ngoài trực tiếp, hay cần một lớp trung gian/on-premise cho dữ liệu nhạy cảm nhất) — không phải quyết định kỹ thuật đơn phương của engineer triển khai.

## Bài tập senior
Một phòng ban trong SSI đề xuất xây một chatbot nội bộ giúp nhân viên "hỏi nhanh về tình hình một mã cổ phiếu và nhận gợi ý có nên khuyến nghị khách hàng mua/bán hay không, để nhân viên tham khảo trước khi tự quyết". Viết một bản đánh giá ngắn (dạng bullet, không đưa ra kết luận pháp lý thay Pháp lý/Tuân thủ) trả lời: (a) ranh giới nào của đề xuất này chạm vào nguyên tắc "AI không tự đưa ra khuyến nghị đầu tư/quyết định giao dịch mà không qua người" đã học ở trên; (b) nếu vẫn muốn triển khai theo hướng "chỉ để nhân viên tham khảo, quyết định cuối vẫn là người", cần thiết kế human-in-the-loop và disclaimer ra sao để not tạo ảo tưởng rằng gợi ý của AI đã được duyệt; (c) các bên nào (ngoài team kỹ thuật) cần tham gia rà soát trước khi tính năng này được phép chạy thật, và vì sao team kỹ thuật không nên tự quyết định một mình dù về mặt code hoàn toàn khả thi.

## Checklist trước khi qua Phần 29
- [ ] Phân biệt được input guardrail và output guardrail, mỗi loại giải quyết rủi ro gì.
- [ ] Nói được nguyên tắc chung "AI không tự đưa ra khuyến nghị đầu tư/quyết định giao dịch không qua người" và biết đây là nguyên tắc cần rà soát cùng Tuân thủ/Pháp lý cho từng use case cụ thể, không phải luật cụ thể do bộ tài liệu này quy định.
- [ ] Biết khi nào cần dừng lại và liên hệ `security@ssi.com.vn` hoặc bộ phận Pháp lý & Tuân thủ, thay vì tự quyết định.
- [ ] Hiểu vì sao guardrail kỹ thuật không thay thế được quy trình compliance/human review chính thức.
- [ ] Chạy được đoạn code thực hành, và tự chứng minh được (qua bài tập 2) vì sao guardrail heuristic đơn giản chưa đủ cho production thật.
</content>
