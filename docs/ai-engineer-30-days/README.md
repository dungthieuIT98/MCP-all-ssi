# Lộ trình 30 ngày lên AI Engineer (senior level) — từ backend dev 6 năm kinh nghiệm

Bộ tài liệu này dùng code thật trong repo `mcp-superset` (MCP server tích hợp Apache Superset — [`core/`](../../core), [`tools/`](../../tools), [`utils/`](../../utils)) làm ví dụ đối chiếu xuyên suốt. Không dạy lại lập trình cơ bản — giả định người học đã vững backend (HTTP, auth, DB, deploy, testing), chỉ tập trung vào phần **đặc thù của AI/LLM engineering** mà 6 năm backend không tự nhiên có được.

## Vì sao lộ trình này khác một khoá học GenAI thông thường
Phần lớn tài liệu "học AI Engineer" dừng ở mức gọi API model rồi in ra kết quả — đủ cho demo, không đủ cho production. Lộ trình này nhắm tới năng lực **senior**: không chỉ "làm được" mà còn phải trả lời được *tại sao chọn cách này, đánh giá chất lượng ra sao, sai ở đâu, chịu tải/chi phí thế nào, và ai/cái gì được quyền làm gì*. Mỗi tuần đều có phần đào sâu về **eval, cost, latency, security** — 4 trục mà một AI Engineer senior bị hỏi nhiều nhất trong review lẫn phỏng vấn.

## Cấu trúc 4 tuần + 2 ngày tổng hợp

| Tuần | Chủ đề | Ngày |
|---|---|---|
| 1 | Nền tảng LLM, prompt engineering, structured output | 1–7 |
| 2 | RAG, embeddings, vector DB, retrieval evaluation | 8–14 |
| 3 | Agents & tool-calling: kiến trúc, orchestration, giao thức (MCP là 1 ví dụ) | 15–21 |
| 4 | Production: eval framework, cost/latency, security, observability | 22–28 |
| — | Tổng hợp: system design mock + case study thật | 29–30 |

## Cách dùng 30 file này
- Mỗi ngày ước lượng 1.5–3 giờ (dev đi làm full-time, không phải học full-time) — có thể dồn 2 ngày cuối tuần thành 1 buổi dài nếu cần.
- Thứ tự tuần có phụ thuộc: Tuần 2 (RAG) cần khái niệm ở Tuần 1 (prompt, context window, structured output); Tuần 3 (agent) cần cả Tuần 1 và 2. Tuần 4 áp dụng lên toàn bộ hệ thống đã xây ở 3 tuần trước — **không học Tuần 4 trước khi có ít nhất 1 pipeline chạy được từ Tuần 2 hoặc 3**.
- Mỗi file có phần "Đối chiếu với code thật trong repo" — luôn mở file được link ra đọc song song, không chỉ đọc lý thuyết.
- Bài tập chia 2 mức: "Bài tập" (bắt buộc, để chắc kiến thức nền) và "Bài tập senior" (mô phỏng câu hỏi/review thật ở mức senior — production trade-off, không có đáp án duy nhất).
- Phần 29-30 không có lý thuyết mới — dùng để tự làm 1 mock system design và refactor lại 1 phần thật của `mcp-superset` theo góc nhìn AI Engineer.

## Danh sách file

### Tuần 1 — Nền tảng LLM & Prompt Engineering
1. [Phần 1 — Cách LLM thực sự sinh ra token, không phải "AI hiểu câu hỏi"](./day1-how-llms-work.md)
2. [Phần 2 — Context window, tokenization, chi phí theo token](./day2-context-tokens.md)
3. [Phần 3 — Prompt engineering có hệ thống, không phải "thử là ra"](./day3-prompt-engineering.md)
4. [Phần 4 — Structured output & function calling schema](./day4-structured-output.md)
5. [Phần 5 — System prompt, guardrail nội dung, jailbreak cơ bản](./day5-system-prompt-guardrails.md)
6. [Phần 6 — So sánh nhà cung cấp model & chọn model theo bài toán](./day6-model-selection.md)
7. [Phần 7 — Ôn tập tuần 1: build 1 CLI hỏi-đáp có structured output](./day7-week1-project.md)

### Tuần 2 — RAG, Embeddings, Vector DB
8. [Phần 8 — Embeddings là gì, đo similarity thế nào](./day8-embeddings.md)
9. [Phần 9 — Vector database, index ANN, khi nào cần và khi nào không](./day9-vector-db.md)
10. [Phần 10 — Chunking strategy — sai ở đây là hỏng cả pipeline](./day10-chunking.md)
11. [Phần 11 — RAG pipeline đầy đủ: retrieve → rerank → generate](./day11-rag-pipeline.md)
12. [Phần 12 — Hybrid search, reranking, query rewriting](./day12-hybrid-search-rerank.md)
13. [Phần 13 — Đánh giá RAG: retrieval metrics & answer faithfulness](./day13-rag-evaluation.md)
14. [Phần 14 — Ôn tập tuần 2: build RAG trên tài liệu Superset thật](./day14-week2-project.md)

### Tuần 3 — Agents & Tool-calling (kiến trúc tổng quát, không riêng 1 giao thức)
15. [Phần 15 — Tool-calling: LLM chọn hàm thế nào, và vì sao chọn sai](./day15-tool-calling.md)
16. [Phần 16 — Các giao thức & framework kết nối tool: function calling thuần, MCP, OpenAPI-to-tool, LangChain/LlamaIndex tool — so sánh khi nào dùng gì](./day16-tool-protocols-landscape.md)
17. [Phần 17 — Agent loop: ReAct, planning, khi nào dừng](./day17-agent-loops.md)
18. [Phần 18 — Memory cho agent: ngắn hạn, dài hạn, và khi nào không cần memory](./day18-agent-memory.md)
19. [Phần 19 — Multi-agent: khi nào đáng, khi nào chỉ là 1 agent giả trang](./day19-multi-agent.md)
20. [Phần 20 — Authorization & identity cho agent — nguyên lý chung, đối chiếu qua session cookie forwarding trong repo](./day20-agent-authz-identity.md)
21. [Phần 21 — Ôn tập tuần 3: thiết kế 1 agent tool-using cho bài toán tự chọn](./day21-week3-project.md)

### Tuần 4 — Production: Eval, Cost, Security, Observability
22. [Phần 22 — Eval framework nghiêm túc: offline eval, golden dataset, LLM-as-judge](./day22-eval-framework.md)
23. [Phần 23 — Online eval & A/B: theo dõi chất lượng khi đã lên production](./day23-online-eval.md)
24. [Phần 24 — Cost engineering: caching, batching, model routing](./day24-cost-engineering.md)
25. [Phần 25 — Latency & streaming: p50/p95/p99 cho hệ thống có LLM](./day25-latency-streaming.md)
26. [Phần 26 — Observability: trace 1 request AI end-to-end](./day26-observability.md)
27. [Phần 27 — Bảo mật LLM app: prompt injection, data exfiltration qua tool, OWASP LLM Top 10](./day27-llm-security.md)
28. [Phần 28 — Guardrail production & compliance cho ngành tài chính (SSI-context)](./day28-guardrails-compliance.md)

### Tổng hợp
29. [Phần 29 — Mock system design interview: thiết kế 1 hệ AI Engineer từ đầu](./day29-system-design-mock.md)
30. [Phần 30 — Case study: audit và đề xuất nâng cấp `mcp-superset` theo góc nhìn AI Engineer](./day30-capstone-case-study.md)

## Lưu ý theo chuẩn SSI khi thực hành
- Không dùng dữ liệu khách hàng thật, số dư tài khoản thật, hoặc thông tin định danh thật khi làm bài tập RAG/agent — luôn dùng dữ liệu giả hoặc dữ liệu công khai (ví dụ tài liệu docs của Superset, Kubernetes).
- Không gọi API key/model key thật của SSI vào code luyện tập cá nhân nếu chưa qua phê duyệt — dùng tài khoản cá nhân/free tier của nhà cung cấp khi tự học ở nhà; khi triển khai thật trong công việc, key phải nằm trong vault/env theo chuẩn bảo mật SSI, không hardcode.
- Mọi thay đổi thật lên `mcp-superset` (thêm tool, sửa auth, sửa deploy) vẫn phải qua review/PR bình thường, không commit thẳng lên nhánh chính — xem thêm phần 20-21 về việc thêm tool mới đúng chuẩn.
- Nội dung sinh bởi AI (bao gồm cả bộ tài liệu này) cần được con người review trước khi áp dụng vào hệ thống thật, đặc biệt các phần liên quan security/compliance ở Tuần 4.
