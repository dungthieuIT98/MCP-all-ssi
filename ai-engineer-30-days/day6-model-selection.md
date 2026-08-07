# Ngày 6 — So sánh nhà cung cấp model & model routing

## Mục tiêu hôm nay
Biết chọn đúng model cho đúng bài toán dựa trên trục chất lượng/cost/latency/context window, thay vì mặc định luôn dùng model lớn nhất — đây là quyết định kiến trúc ảnh hưởng trực tiếp tới chi phí vận hành thật, và là nơi rất nhiều hệ thống "gọi API là xong" lãng phí tiền không cần thiết.

## Đọc trước
- [Anthropic — Models overview](https://docs.anthropic.com/en/docs/about-claude/models/overview)
- [Anthropic — Pricing](https://docs.anthropic.com/en/docs/about-claude/pricing) (bắt buộc tra số mới nhất tại đây, không dùng số nhớ từ tài liệu cũ)
- [OpenAI — Models](https://platform.openai.com/docs/models)
- [OpenAI — Pricing](https://platform.openai.com/docs/pricing)

## Khái niệm cốt lõi

### Bốn trục để so sánh model — không có model "tốt nhất tuyệt đối"
Không tồn tại một model tốt nhất cho mọi việc — mỗi model là một điểm trade-off trên 4 trục, và quyết định đúng là chọn điểm trade-off phù hợp với **bài toán cụ thể**, không phải chọn theo tên tuổi hay theo benchmark tổng quát:

1. **Chất lượng (quality)** — khả năng suy luận, làm theo chỉ dẫn phức tạp, xử lý tác vụ đòi hỏi nhiều bước. Model lớn (Opus-tier của Anthropic, GPT cao cấp của OpenAI) vượt trội ở tác vụ khó, nhưng khoảng cách chất lượng với model nhỏ **thu hẹp đáng kể** ở tác vụ đơn giản (phân loại, trích xuất thông tin có cấu trúc rõ) — nhiều trường hợp model nhỏ đạt chất lượng gần tương đương model lớn cho đúng loại việc đó.
2. **Chi phí (cost)** — tính theo giá/triệu token, chia input/output riêng (Ngày 2). Model nhỏ rẻ hơn model lớn thường **khoảng một bậc độ lớn** (order of magnitude) trên cùng khối lượng token — không chốt số cụ thể ở đây vì giá thay đổi theo thời gian, luôn tra bảng giá chính thức mới nhất của từng nhà cung cấp trước khi tính ngân sách thật.
3. **Latency** — thời gian phản hồi. Model nhỏ luôn nhanh hơn model lớn cho cùng độ dài output (ít tham số hơn = mỗi bước decode tính toán ít hơn — liên hệ Ngày 1 về giai đoạn decode tuần tự). Với ứng dụng cần phản hồi tức thời (gợi ý gõ chữ, chatbot thời gian thực), latency có thể quan trọng hơn cả chất lượng tuyệt đối.
4. **Context window** — kích thước ngữ cảnh tối đa (Ngày 2). Các model hiện đại của Anthropic và Google có xu hướng hỗ trợ context window rất lớn (hàng trăm nghìn tới 1 triệu token ở một số model); cần tra tài liệu hiện tại của từng nhà cung cấp vì đây là trục thay đổi nhanh giữa các phiên bản.

Sai lầm phổ biến ở mức "gọi API là xong": chọn model lớn nhất cho mọi tác vụ vì "chắc ăn hơn". Đây là lãng phí thật — một tác vụ phân loại cảm xúc đơn giản chạy trên model lớn nhất tốn gấp nhiều lần chi phí và latency so với chạy trên model nhỏ, mà chất lượng tăng thêm gần như không đo được cho loại tác vụ đó.

### Các nhà cung cấp chính — đặc điểm định vị, không phải xếp hạng
Không xếp hạng "ai hơn ai" vì benchmark thay đổi liên tục và phụ thuộc loại tác vụ — chỉ nêu đặc điểm định vị để biết khi nào nên xem xét từng lựa chọn:

- **Anthropic (Claude)** — dòng model chia theo 3 tier rõ ràng (nhỏ/nhanh → trung → lớn/mạnh nhất), API có tư duy kỹ sư rõ (structured outputs chuẩn hoá, tool use mạnh, context caching, extended/adaptive thinking điều khiển được qua tham số riêng biệt khỏi phần prompt text). Định vị mạnh ở tác vụ agentic/tool-calling phức tạp và coding — đây cũng là lý do hệ sinh thái SDK Anthropic được dùng làm chuẩn chính trong tài liệu này.
- **OpenAI (GPT)** — hệ sinh thái lớn nhất về số lượng tool/thư viện bên thứ ba hỗ trợ, nhiều biến thể model tối ưu cho các mục đích khác nhau (bao gồm model tối ưu chi phí/latency riêng). API có khái niệm tương đương (structured outputs, function calling, model tier từ nhỏ tới lớn) nhưng cú pháp và tên tham số khác Anthropic — không dùng chung SDK.
- **Google (Gemini)** — thế mạnh về context window rất lớn ở một số model và tích hợp sâu với hạ tầng Google Cloud (Vertex AI) — hữu ích khi hệ thống đã nằm trong hệ sinh thái GCP hoặc cần xử lý input đa phương thức (multimodal) quy mô lớn.
- **Model mở (Llama, Mistral, và các model mã nguồn mở khác)** — khác biệt căn bản: bạn (hoặc bên thứ ba bạn thuê) tự host hoặc dùng qua nhà cung cấp inference trung gian, thay vì gọi API độc quyền của một hãng. Ưu điểm: kiểm soát hoàn toàn dữ liệu (quan trọng với yêu cầu tuân thủ/bảo mật nghiêm — dữ liệu không rời khỏi hạ tầng nội bộ), không phụ thuộc rate limit/chính sách của một nhà cung cấp duy nhất, có thể fine-tune sâu hơn. Nhược điểm: phải tự quản lý hạ tầng inference (GPU, scaling, uptime), và ở tác vụ suy luận phức tạp/agentic, phần lớn model mở hiện tại vẫn chưa bắt kịp các model đóng lớn nhất — khoảng cách này thu hẹp theo thời gian nhưng chưa biến mất.

Với ngữ cảnh làm việc trong tổ chức tài chính chịu quản lý bởi UBCKNN và luật bảo vệ dữ liệu cá nhân, việc **dữ liệu đi đâu** khi gọi API là câu hỏi kỹ thuật + pháp lý cần trả lời trước khi chọn nhà cung cấp — không chỉ là câu hỏi về chất lượng/giá. Model mở tự host hoặc các tuỳ chọn triển khai riêng theo khu vực dữ liệu (data residency) của các nhà cung cấp lớn là hướng cần cân nhắc cho dữ liệu nhạy cảm — quyết định này cần phối hợp với Bộ phận Luật & Tuân thủ và An toàn thông tin, không phải quyết định thuần kỹ thuật.

### Khi nào dùng model nhỏ/rẻ, khi nào dùng model lớn/đắt
Nguyên tắc thực dụng, không phải lý thuyết:

**Dùng model nhỏ/rẻ khi:**
- Tác vụ có **không gian đầu ra hẹp và rõ** — phân loại (có tập nhãn cố định), trích xuất thông tin có cấu trúc rõ ràng (tên, ngày, số tiền từ một mẫu văn bản chuẩn), tóm tắt ngắn không đòi hỏi suy luận sâu.
- Khối lượng request rất lớn — chênh lệch giá nhân với số lượng request khổng lồ trở thành khoản tiền thật đáng kể, không còn là chênh lệch "không đáng kể".
- Latency là ưu tiên hàng đầu — gợi ý tự động, kiểm tra nhanh trước khi chuyển sang bước xử lý nặng hơn.

**Dùng model lớn/đắt khi:**
- Tác vụ đòi hỏi suy luận nhiều bước, xử lý mơ hồ, hoặc ra quyết định có hậu quả cao nếu sai (phân tích tài liệu pháp lý, tổng hợp thông tin từ nhiều nguồn mâu thuẫn, viết code phức tạp).
- Tần suất gọi thấp nhưng mỗi lần gọi giá trị công việc cao — chi phí tuyệt đối vẫn nhỏ so với giá trị output tạo ra.
- Tác vụ agentic nhiều bước (gọi nhiều tool liên tiếp, tự lập kế hoạch) — model nhỏ thường không đủ khả năng duy trì kế hoạch nhất quán qua nhiều bước, dẫn tới lỗi dây chuyền tốn kém hơn là dùng model lớn ngay từ đầu.

### Model routing sơ bộ — kiến trúc, không phải tiểu tiết
Model routing là kỹ thuật **định tuyến động** mỗi request tới model phù hợp nhất dựa trên đặc điểm của request đó, thay vì hardcode một model cho toàn hệ thống. Dạng đơn giản nhất, dễ implement ngay:

1. **Routing theo loại tác vụ (rule-based)** — nếu biết trước loại tác vụ (ví dụ: endpoint `/classify` luôn dùng model nhỏ, endpoint `/analyze-report` luôn dùng model lớn), route tĩnh theo route/endpoint là đủ, không cần logic phức tạp.
2. **Routing hai giai đoạn (cascade)** — thử model nhỏ/rẻ trước; nếu output có tín hiệu "không chắc" (ví dụ model tự báo độ tin cậy thấp, hoặc output không đạt một ngưỡng kiểm tra tự động), escalate lên model lớn hơn để xử lý lại. Tiết kiệm chi phí đáng kể khi phần lớn request thuộc dạng dễ (model nhỏ xử lý được ngay) và chỉ một phần nhỏ request khó cần escalate.
3. **Routing theo độ phức tạp ước lượng trước (classifier riêng)** — dùng một bước phân loại nhẹ (có thể chính là một model rất nhỏ, hoặc rule-based) để đánh giá độ phức tạp của input trước khi quyết định gọi model nào — phức tạp hơn cascade nhưng tránh được việc luôn phải "thử model nhỏ trước rồi mới biết cần escalate".

Điểm cần lưu ý ở mức senior: model routing **thêm độ phức tạp vận hành** (phải theo dõi tỷ lệ escalate, chi phí tổng hợp qua cả 2 tầng, và độ trễ thêm khi phải gọi 2 lần cho case escalate) — chỉ nên áp dụng khi đã đo được rằng phần lớn traffic thực tế là tác vụ dễ (nếu 90% request đều là tác vụ khó, cascade chỉ làm chậm và tốn thêm mà không tiết kiệm được gì đáng kể).

## Đối chiếu với code thật trong repo
`mcp-superset` là một MCP server — nó không tự quyết định model nào được dùng, vì đó là trách nhiệm của AI assistant (Claude Desktop, Claude Code, hoặc client MCP khác) gọi vào nó. Nhưng nguyên tắc "chọn đúng công cụ cho đúng việc" áp dụng tương tự ở tầng thiết kế tool: các tool trong `tools/auth.py`, `tools/user.py` thực hiện tác vụ đơn giản (lấy thông tin phiên đăng nhập, danh sách user) — nếu một ngày hệ thống mở rộng để có một lớp xử lý riêng (ví dụ tự động tóm tắt kết quả trả về từ nhiều tool trước khi đưa vào context chính, để giảm token — liên hệ Ngày 2), lớp tóm tắt phụ đó là ứng cử viên hoàn hảo để dùng model nhỏ/rẻ, không cần dùng cùng model mạnh đang điều khiển toàn bộ agent loop chính. Đây chính là ý tưởng cốt lõi của model routing: không phải mọi lệnh gọi model trong một hệ thống agent cần dùng cùng một model.

## Thực hành
```bash
pip install anthropic
```

```python
import anthropic

client = anthropic.Anthropic()

# Minh hoạ routing rule-based đơn giản: map loại tác vụ sang model phù hợp.
# Đây là cách bắt đầu tối thiểu, không cần logic phức tạp ngay từ đầu.
MODEL_CHO_TAC_VU = {
    "phan_loai": "claude-haiku-4-5",       # tác vụ đơn giản, không gian đầu ra hẹp
    "tom_tat_ngan": "claude-haiku-4-5",
    "phan_tich_sau": "claude-opus-5",       # suy luận nhiều bước, độ chính xác quan trọng
    "agent_nhieu_buoc": "claude-opus-5",
}

def goi_model_theo_tac_vu(loai_tac_vu: str, noi_dung: str) -> str:
    model = MODEL_CHO_TAC_VU.get(loai_tac_vu, "claude-opus-5")  # mặc định an toàn: model mạnh
    response = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[{"role": "user", "content": noi_dung}],
    )
    text = next((b.text for b in response.content if b.type == "text"), "")
    print(f"[{loai_tac_vu} -> {model}] input_tokens={response.usage.input_tokens}, "
          f"output_tokens={response.usage.output_tokens}")
    return text

goi_model_theo_tac_vu("phan_loai", "Phân loại cảm xúc: 'Sản phẩm giao rất chậm.' — tích cực/tiêu cực/trung tính?")
goi_model_theo_tac_vu("phan_tich_sau", "Phân tích rủi ro của việc một công ty vừa công bố báo cáo tài chính có biên lợi nhuận giảm 15% so với cùng kỳ, trong ngành đang chịu áp lực cạnh tranh giá.")
```

```python
# Minh hoạ cascade: thử model rẻ trước, escalate lên model mạnh nếu
# output không đạt ngưỡng tin cậy (ở đây minh hoạ bằng độ dài output —
# thực tế nên dùng tín hiệu đáng tin hơn, ví dụ model tự báo "không chắc").
def phan_loai_voi_cascade(noi_dung: str) -> str:
    # Bước 1: thử model nhỏ, rẻ, nhanh.
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=50,
        messages=[{"role": "user", "content": (
            f"Phân loại chủ đề của câu sau vào 1 trong: kỹ_thuật, thanh_toán, khác. "
            f"Nếu KHÔNG chắc, trả về CHÍNH XÁC từ 'khong_chac'.\nCâu: {noi_dung}"
        )}],
    )
    ket_qua = next((b.text for b in response.content if b.type == "text"), "").strip()

    if ket_qua == "khong_chac":
        # Bước 2: escalate lên model mạnh hơn chỉ khi cần — không phải mọi request.
        print("Model nhỏ không chắc — escalate lên model mạnh.")
        response = client.messages.create(
            model="claude-opus-5",
            max_tokens=100,
            messages=[{"role": "user", "content": (
                f"Phân loại chủ đề của câu sau, phân tích kỹ nếu cần: "
                f"kỹ_thuật, thanh_toán, khác.\nCâu: {noi_dung}"
            )}],
        )
        ket_qua = next((b.text for b in response.content if b.type == "text"), "").strip()

    return ket_qua
```

## Bài tập tự làm
1. Tra bảng giá chính thức hiện tại của Anthropic và OpenAI. So sánh tỷ lệ giá giữa model nhỏ nhất và model lớn nhất của mỗi hãng (không cần số tuyệt đối, chỉ cần tỷ lệ) — có khớp với nhận định "chênh khoảng một bậc độ lớn" đã nêu ở mục Khái niệm cốt lõi không?
2. Chạy cùng một tác vụ phân loại đơn giản trên 2 model khác nhau (một nhỏ, một lớn của cùng nhà cung cấp), so sánh: thời gian phản hồi (đo bằng `time.time()` trước/sau lệnh gọi), số output token, và chất lượng câu trả lời bằng mắt. Ghi lại nhận xét.
3. Thiết kế bảng routing rule-based cho một hệ thống hỏi-đáp nội bộ của một công ty chứng khoán, có ít nhất 4 loại tác vụ khác nhau (ví dụ: trả lời FAQ, tóm tắt báo cáo, phân loại yêu cầu hỗ trợ, soạn draft email nội bộ) — với mỗi loại, chỉ rõ nên dùng model nhỏ hay lớn và lý do dựa trên 4 trục đã học.

## Đào sâu / nâng cao

### Batch processing — trục thứ 5 ít được nói tới nhưng ảnh hưởng chi phí lớn
Với tác vụ không cần phản hồi tức thời (xử lý hàng loạt dữ liệu vào cuối ngày, phân loại một lô lớn giao dịch để rà soát), hầu hết nhà cung cấp có API xử lý theo lô (batch) với mức giá thường **thấp hơn đáng kể** so với gọi API đồng bộ thông thường (Anthropic công bố mức giảm cụ thể trên trang batch processing của họ — luôn tra số hiện tại) — đổi lại thời gian xử lý có thể lên tới vài giờ thay vì vài giây. Với hệ thống xử lý hàng loạt dữ liệu tài chính không cần real-time (ví dụ rà soát cuối ngày), batch API thường là lựa chọn tối ưu chi phí bị bỏ qua vì mặc định nghĩ "API luôn phải đồng bộ".

### Rate limit khác nhau theo model và theo tier tài khoản
Mỗi model có giới hạn request/phút và token/phút riêng, và giới hạn này khác nhau giữa các tier tài khoản (tài khoản mới luôn có giới hạn thấp hơn tài khoản đã dùng lâu/nhiều). Khi thiết kế model routing, cần tính tới việc **các model khác nhau có rate limit pool riêng** — chuyển traffic từ model A sang model B không tự động "giải phóng" rate limit của A cho việc khác, và ngược lại B có pool giới hạn của riêng nó, cần kiểm tra trước khi đổ traffic lớn sang.

### "Chất lượng" không phải một số duy nhất — benchmark theo đúng loại tác vụ của bạn
Các bảng benchmark công khai (MMLU, HumanEval, và tương tự) đo chất lượng trên các bộ dữ liệu chuẩn hoá — không đảm bảo phản ánh đúng hiệu năng model trên **tác vụ cụ thể của bạn** (ví dụ: phân loại yêu cầu hỗ trợ bằng tiếng Việt trong ngành chứng khoán). Nguyên tắc senior: xây eval set riêng cho tác vụ thật (đã nói ở Ngày 3) và so sánh model trên eval set đó — không quyết định chọn model chỉ dựa vào bảng benchmark tổng quát tìm thấy trên mạng.

## Bài tập senior
1. Team bạn đang chạy toàn bộ hệ thống (bao gồm cả việc phân loại yêu cầu hỗ trợ đơn giản) trên model lớn nhất/đắt nhất "để chắc ăn". CFO yêu cầu giảm 40% chi phí API trong quý tới mà không được giảm chất lượng trải nghiệm người dùng ở các tác vụ quan trọng. Đề xuất một kế hoạch cụ thể (không chỉ nói "dùng model rẻ hơn") — nêu rõ bạn sẽ đo gì trước khi đổi, đổi phần nào trước, và cách xác nhận chất lượng không giảm ở phần quan trọng.
2. Một hệ thống cascade (model nhỏ thử trước, escalate khi không chắc) đang có tỷ lệ escalate 85% — nghĩa là gần như mọi request đều phải gọi model lớn sau khi đã tốn thêm một lượt gọi model nhỏ. Đánh giá: cascade này có còn hợp lý về chi phí/latency không? Đề xuất hướng xử lý.
3. Trong ngữ cảnh một công ty chứng khoán chịu quản lý của UBCKNN, thảo luận (ở mức kỹ thuật, không đưa ra kết luận pháp lý — vấn đề pháp lý thuộc thẩm quyền Bộ phận Luật & Tuân thủ) sự khác biệt về rủi ro khi dữ liệu khách hàng được gửi tới API của một nhà cung cấp mô hình đóng (Anthropic/OpenAI) so với khi dùng model mã nguồn mở tự host trong hạ tầng nội bộ. Nêu rõ những câu hỏi kỹ thuật cụ thể bạn cần trả lời trước khi đề xuất phương án cho dữ liệu được phân loại ở mức "Giới hạn" hoặc nhạy cảm hơn.

## Checklist trước khi qua Ngày kế
- [ ] Nêu được 4 trục so sánh model và giải thích trade-off giữa chúng bằng ví dụ cụ thể.
- [ ] Biết tra bảng giá chính thức của ít nhất 2 nhà cung cấp, không dựa vào số nhớ có thể lỗi thời.
- [ ] Giải thích được sự khác biệt giữa model đóng (Anthropic/OpenAI/Google) và model mở tự host, và khi nào cân nhắc phương án nào.
- [ ] Viết được một cơ chế routing rule-based đơn giản và một cascade cơ bản.
- [ ] Hiểu được vì sao cần eval set riêng cho tác vụ thật, không chỉ dựa vào benchmark công khai.
