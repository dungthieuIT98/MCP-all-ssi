# Ngày 25 — Latency & streaming: p50/p95/p99 cho hệ thống có LLM

## Mục tiêu hôm nay
Hiểu latency của LLM khác latency API thông thường ở bản chất (time-to-first-token, variance cao theo độ dài output), biết đo đúng percentile, và thiết kế streaming/timeout/retry hợp lý cho LLM call.

## Đọc trước
- [Anthropic — Streaming Messages](https://docs.anthropic.com/) (tìm mục "streaming" trong API reference — cách nhận response dạng server-sent events, các loại event).
- [Anthropic — Errors and rate limits](https://docs.anthropic.com/) (tìm mục lỗi/rate limit — cơ sở để thiết kế retry đúng, tránh retry vô tội vạ).
- Tài liệu chung về đo latency percentile (p50/p95/p99) trong hệ thống phân tán — khái niệm không riêng LLM, tìm theo từ khoá "latency percentiles SRE" nếu chưa quen.

## Khái niệm cốt lõi

### Time-to-first-token (TTFT) vs time-to-last-token (TTLT)
API thông thường (REST CRUD, tra DB) trả về toàn bộ response cùng lúc — chỉ có một mốc thời gian đáng nói: lúc response hoàn tất. LLM sinh output **tuần tự, từng token một** (về bản chất autoregressive — xem lại Ngày 1), nên có hai mốc thời gian tách biệt và đều quan trọng:

- **Time-to-first-token (TTFT)**: thời gian từ lúc gửi request tới lúc nhận được token/chunk đầu tiên. Phần này bao gồm thời gian xử lý toàn bộ input (đọc prompt, prefill context) trước khi model bắt đầu sinh token đầu ra — với prompt dài, TTFT có thể chiếm phần đáng kể của tổng latency dù chưa sinh ra chữ nào.
- **Time-to-last-token (TTLT)**: thời gian từ lúc gửi request tới lúc nhận token cuối cùng — đây là "tổng thời gian" theo nghĩa truyền thống. TTLT phụ thuộc trực tiếp vào **số token output sinh ra** — output dài hơn thì TTLT dài hơn theo cách gần tuyến tính, khác hẳn API thông thường nơi thời gian xử lý thường không phụ thuộc "kích thước câu trả lời" theo cách rõ rệt như vậy.

Hai mốc này quan trọng vì chúng phục vụ hai mục đích đo khác nhau: TTFT phản ánh "hệ thống có phản hồi nhanh không" (quan trọng cho perceived latency), TTLT phản ánh "tác vụ hoàn thành trong bao lâu" (quan trọng cho use case cần full output trước khi làm bước tiếp, ví dụ parse structured output).

### Streaming cải thiện perceived latency, không cải thiện total time
Streaming là gửi từng phần token về client ngay khi model sinh ra, thay vì đợi toàn bộ response xong rồi trả một lần. Điểm cần hiểu rõ: **streaming không làm model sinh nhanh hơn** — TTLT (tổng thời gian tới token cuối) gần như không đổi so với non-streaming. Cái thay đổi là **trải nghiệm cảm nhận** (perceived latency): user thấy chữ xuất hiện dần ngay từ TTFT thay vì nhìn màn hình trống suốt TTLT rồi bất ngờ nhận toàn bộ câu trả lời.

- Với ứng dụng có giao diện hội thoại (chat), streaming gần như là yêu cầu bắt buộc ở mức UX hiện đại — người dùng đã quen "chữ chạy dần" và cảm thấy hệ thống "đứng hình" nếu phải chờ không phản hồi gì trong vài giây.
- Với ứng dụng không có giao diện tương tác trực tiếp (batch xử lý, API nội bộ gọi rồi parse toàn bộ response để dùng tiếp) — streaming không mang lại lợi ích UX vì không có người ngồi nhìn màn hình, và có thể còn phức tạp hoá code (phải buffer/ghép chunk lại trước khi parse) mà không đổi lại gì.
- Streaming cũng hữu ích cho việc **phát hiện sớm** một số loại lỗi hoặc để implement "cancel giữa đường" (user có thể dừng model đang sinh output dở nếu thấy không đúng ý, tiết kiệm token — cả về cost và về thời gian).

### Đo p50/p95/p99 cho hệ thống có LLM
Percentile latency (p50 = trung vị, p95 = 95% request nhanh hơn giá trị này, p99 = 99% request nhanh hơn giá trị này) là cách đo chuẩn cho bất kỳ hệ thống phân tán — nhưng với LLM, ý nghĩa và cách đọc percentile khác biệt rõ so với API thông thường:

- **Variance cao hơn nhiều, và có nguyên nhân rõ ràng, không phải nhiễu ngẫu nhiên**: độ dài output do model tự quyết định sinh ra bao nhiêu token — hai request giống nhau về input có thể ra output ngắn/dài rất khác nhau tuỳ nội dung, kéo theo TTLT khác nhau đáng kể. Với API thông thường, variance thường do hạ tầng (network, DB load) — với LLM, variance còn cộng thêm yếu tố "nội dung sinh ra dài bao nhiêu", một biến số nằm ngoài kiểm soát trực tiếp của hạ tầng.
- **Nên đo TTFT và TTLT riêng biệt theo percentile, không trộn chung**: p95 TTFT cho biết "hệ thống có bắt đầu phản hồi nhanh không" (phụ thuộc hạ tầng, độ dài input, tải hệ thống) — p95 TTLT cho biết "tác vụ dài nhất mất bao lâu để xong hoàn toàn" (phụ thuộc thêm cả độ dài output). Chỉ báo cáo một số "latency trung bình" duy nhất cho LLM system là dấu hiệu thiếu hiểu về đặc thù hệ thống.
- **Phân tách percentile theo loại tác vụ**: nếu hệ thống có nhiều loại request khác nhau về độ dài output kỳ vọng (ví dụ tool đơn giản trả 1 câu ngắn vs tác vụ tổng hợp báo cáo dài), gộp chung percentile của hai loại vào một số sẽ cho một con số vô nghĩa (trộn lẫn phân bố khác nhau) — nên đo riêng theo category, giống nguyên tắc phân nhóm category trong golden dataset ở Ngày 22.
- **p99 với LLM dễ bị kéo dài bất thường bởi rate limit/retry ở phía nhà cung cấp** hơn API nội bộ tự host — cần phân biệt rõ trong log: latency chậm vì model sinh output dài, hay chậm vì phải chờ retry do rate limit/lỗi tạm thời (hai nguyên nhân cần hai hướng xử lý khác nhau).

### Timeout/retry strategy — không thể retry vô tội vạ
API thông thường có thói quen retry khá rộng rãi (lỗi mạng thoáng qua, timeout ngắn, thử lại 2-3 lần) vì chi phí một request thường rất nhỏ. Với LLM call, thói quen này có hai rủi ro thật:

- **Chi phí gấp đôi (hoặc hơn) mỗi lần retry**: một request LLM có thể tốn đáng kể (tiền, latency) — retry 3 lần cho một request thất bại nghĩa là trả tiền 3 lần cho phần input token đã gửi lại, dù chỉ nhận được 1 kết quả dùng được (nếu có). Retry cần có chủ đích, không phải "cứ retry cho chắc" như với một API rẻ.
- **Timeout khó đặt một số cố định cho mọi loại request**: vì latency phụ thuộc độ dài output kỳ vọng (đã nói ở trên), một timeout ngắn phù hợp cho tác vụ trả lời ngắn sẽ cắt ngang tác vụ cần output dài trước khi kịp xong — nên timeout nên được đặt theo loại tác vụ (dựa trên `max_tokens` kỳ vọng và p95/p99 đã đo thực tế cho loại đó), không phải một hằng số toàn cục.

Thiết kế retry thực dụng cho LLM:
- **Phân loại lỗi trước khi quyết định retry**: lỗi do rate limit (nên retry có backoff, vì thử lại sau khi giảm tải thường thành công) khác lỗi do input không hợp lệ hoặc lỗi phía model xử lý nội dung (retry không giải quyết gì, tốn tiền vô ích) khác lỗi do timeout vì output đang sinh dài (retry ngay có thể timeout lại đúng như vậy — cần tăng timeout hoặc dùng streaming để biết model có đang tiến triển không, thay vì huỷ và gọi lại từ đầu).
- **Backoff có giới hạn số lần rõ ràng** (ví dụ tối đa 2 lần, không phải retry đến khi thành công) — vì mỗi lần thử lại là một request mới tính phí đầy đủ, không phải "resume" từ chỗ dừng.
- **Với streaming, cân nhắc retry theo phần chưa xong thay vì huỷ toàn bộ và gọi lại từ đầu** nếu framework/SDK hỗ trợ — tránh trả tiền lại cho phần input token đã xử lý xong trước khi lỗi xảy ra giữa đường (tuỳ nhà cung cấp có hỗ trợ resume hay không, không phải mặc định có sẵn).
- **Idempotency khi retry có tác dụng phụ**: nếu LLM call nằm trong một agent loop có tool-calling (Tuần 3), retry sau khi tool đã chạy thành công một phần có thể gây tác dụng phụ lặp lại (ví dụ gọi lại một tool ghi dữ liệu) — cần thiết kế idempotency ở tầng tool, không chỉ ở tầng gọi model.

## Đối chiếu với code thật trong repo
`core/context.py` cấu hình `httpx.AsyncClient` với `timeout=30.0` cho các lệnh gọi tới Superset — đây là timeout cho API truyền thống (tra cứu dataset/chart trong DB), có thời gian xử lý ổn định và dự đoán được, khác hẳn bản chất timeout cần cho một lệnh gọi LLM (nơi thời gian phụ thuộc độ dài output sinh ra, không cố định). Nếu một ngày `mcp-superset` được mở rộng để tự gọi LLM ở tầng server (ví dụ tool tự tóm tắt kết quả trước khi trả cho agent), timeout cho lệnh gọi đó cần thiết kế tách biệt khỏi timeout gọi Superset — không dùng chung hằng số 30 giây, vì bản chất hai loại latency khác nhau hoàn toàn. Đây cũng là lý do các tool hiện tại dùng `handle_api_errors` (`utils/decorators.py`) bắt mọi exception thành `{"error": ...}` có cấu trúc — cùng nguyên tắc này áp dụng cho lỗi timeout/retry của LLM call: luôn trả lỗi có cấu trúc rõ, không để exception thô/stack trace lộ ra ngoài (liên hệ lại ở Ngày 27 khi nói về insecure output handling).

## Thực hành
```python
"""
Đo TTFT/TTLT qua streaming, và minh hoạ timeout + retry có chủ đích (không
retry vô điều kiện). Chạy được với `pip install anthropic`.
"""
import time

import anthropic
from anthropic import APIStatusError, APITimeoutError

client = anthropic.Anthropic()


def measure_ttft_ttlt(user_input: str, max_tokens: int = 300) -> dict:
    """Đo time-to-first-token và time-to-last-token bằng streaming."""
    start = time.perf_counter()
    ttft = None
    full_text = []

    with client.messages.stream(
        model="claude-sonnet-4-5-20250929",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": user_input}],
    ) as stream:
        for text in stream.text_stream:
            if ttft is None:
                ttft = time.perf_counter() - start  # mốc token đầu tiên
            full_text.append(text)

    ttlt = time.perf_counter() - start  # mốc token cuối cùng
    return {
        "ttft_ms": round(ttft * 1000, 1) if ttft else None,
        "ttlt_ms": round(ttlt * 1000, 1),
        "output_len_chars": len("".join(full_text)),
    }


def call_with_bounded_retry(
    user_input: str, max_retries: int = 2, timeout_s: float = 20.0
) -> str:
    """Retry có chủ đích: chỉ retry lỗi tạm thời (rate limit/timeout), không
    retry lỗi do input sai; giới hạn số lần rõ ràng; backoff tăng dần."""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=300,
                timeout=timeout_s,
                messages=[{"role": "user", "content": user_input}],
            )
            return response.content[0].text
        except APITimeoutError as e:
            # Timeout: có thể do output dài hơn dự kiến hoặc tải cao — retry
            # có ý nghĩa, nhưng giới hạn số lần vì mỗi lần tốn tiền lại từ đầu.
            last_error = e
            wait = 2 ** attempt  # backoff tăng dần: 1s, 2s, 4s...
            print(f"[retry] timeout, thử lại sau {wait}s (lần {attempt + 1})")
            time.sleep(wait)
        except APIStatusError as e:
            if e.status_code == 429:
                # Rate limit: retry có backoff hợp lý.
                last_error = e
                wait = 2 ** attempt
                print(f"[retry] rate limited, thử lại sau {wait}s")
                time.sleep(wait)
            else:
                # Lỗi 4xx khác (input không hợp lệ, v.v.) — retry không giải
                # quyết được gì, dừng ngay để không tốn tiền vô ích.
                raise

    raise RuntimeError(f"Hết {max_retries} lần retry, lỗi cuối: {last_error}")


if __name__ == "__main__":
    print("--- Đo TTFT/TTLT với output ngắn ---")
    print(measure_ttft_ttlt("Trả lời bằng 1 câu: Superset dùng để làm gì?", max_tokens=50))

    print("\n--- Đo TTFT/TTLT với output dài hơn ---")
    print(
        measure_ttft_ttlt(
            "Giải thích chi tiết kiến trúc của Apache Superset trong khoảng 5 đoạn văn.",
            max_tokens=500,
        )
    )

    print("\n--- Retry có chủ đích ---")
    print(call_with_bounded_retry("Superset là gì?"))
```

## Bài tập tự làm
1. Chạy `measure_ttft_ttlt` với 5 câu hỏi có `max_tokens` khác nhau (50, 200, 500, 1000) — vẽ hoặc ghi lại bảng TTFT vs TTLT, xác nhận TTFT tương đối ổn định còn TTLT tăng theo `max_tokens`/độ dài output thật.
2. Chạy cùng một câu hỏi 20 lần, ghi lại TTLT mỗi lần, tự tính p50/p95/p99 bằng tay hoặc bằng `numpy.percentile` — nhận xét độ phân tán (variance) so với latency một API REST thông thường bạn đã từng đo trong công việc backend.
3. Sửa `call_with_bounded_retry` để phân biệt thêm trường hợp lỗi do nội dung input (ví dụ giả lập bằng cách raise `ValueError` thủ công) — xác nhận trường hợp này không rơi vào nhánh retry.
4. Thiết kế (chỉ viết ra, không cần code) một chính sách timeout khác nhau cho 2 loại tool trong `mcp-superset`: một tool trả lời nhanh có cấu trúc cố định (ví dụ lấy thông tin 1 dataset theo ID) và một tool giả định cần model tổng hợp câu trả lời dài — giải thích vì sao timeout của hai loại này nên khác nhau.

## Đào sâu / nâng cao

### Streaming trong agent loop có tool-calling
Khi model quyết định gọi tool giữa lúc đang stream (Tuần 3), luồng xử lý phức tạp hơn chat đơn giản: cần phát hiện đúng lúc model phát ra tool-call event trong stream, dừng lại chờ tool thực thi xong, rồi tiếp tục vòng lặp — không thể coi toàn bộ response là một luồng text liên tục. Thiết kế sai phần này (ví dụ đợi hết toàn bộ stream mới parse tool call) làm mất lợi ích của streaming ngay tại bước cần nó nhất (khi output tổng của cả agent loop dài, nhiều bước).

### Latency budget khi hệ thống có nhiều bước LLM nối tiếp
Một pipeline RAG hoặc agent nhiều bước (retrieve → rerank → generate → có thể gọi tool → generate lại) cộng dồn latency của từng bước LLM — TTLT tổng của cả pipeline có thể lớn hơn nhiều so với một lệnh gọi LLM đơn lẻ. Cần đặt "latency budget" cho từng bước ngay từ thiết kế (bước nào được phép tốn bao nhiêu thời gian tối đa) thay vì đo tổng sau cùng rồi mới ngạc nhiên vì sao chậm — nguyên tắc giống phân rã latency budget trong hệ thống microservice truyền thống, chỉ khác biến số đầu vào (độ dài output) khó dự đoán hơn.

### Speculative/parallel calls để giảm latency cảm nhận
Một số kiến trúc gọi song song nhiều bước không phụ thuộc nhau (ví dụ vừa gọi model chính vừa gọi trước một bước chuẩn bị khác) để giảm tổng latency cảm nhận, đánh đổi bằng việc có thể lãng phí một phần compute nếu kết quả song song đó không dùng tới. Cân nhắc kỹ chi phí phát sinh trước khi áp dụng — đây là tối ưu latency đổi lấy cost, ngược hướng với các kỹ thuật ở Ngày 24, cần cân bằng theo ưu tiên thực tế của hệ thống (SLA latency có quan trọng hơn cost ở use case đó không).

## Bài tập senior
Một tính năng chatbot nội bộ đang bị phàn nàn "chậm" dù đã dùng streaming. Đo thực tế cho thấy p50 TTFT khoảng 800ms (chấp nhận được) nhưng p95 TTLT lên tới hơn 20 giây cho một số câu hỏi. Viết một quy trình chẩn đoán (dạng bước) để xác định nguyên nhân p95 TTLT cao là do: (a) output thực sự dài cho những câu hỏi đó (bản chất bài toán), (b) rate limit/retry ở phía nhà cung cấp, hay (c) một bước xử lý phía trước/sau lệnh gọi model (ví dụ retrieval chậm) đang được tính nhầm vào latency của LLM. Với mỗi nguyên nhân, đề xuất một hướng xử lý khác nhau — không có một fix chung cho cả ba.

## Checklist trước khi qua Ngày 26
- [ ] Phân biệt rõ TTFT và TTLT, biết vì sao streaming cải thiện cái này mà không đổi cái kia.
- [ ] Giải thích được vì sao variance latency LLM cao hơn API thông thường, gắn với nguyên nhân cụ thể (độ dài output).
- [ ] Biết đo p50/p95/p99 riêng cho TTFT và TTLT, và vì sao cần phân theo category tác vụ.
- [ ] Thiết kế được retry có phân loại lỗi, có giới hạn số lần, không retry vô điều kiện.
- [ ] Chạy được đoạn code đo TTFT/TTLT thực hành và đọc ra được số liệu hợp lý.
</content>
