# Auth Proxy — Mô tả Flow Code

Proxy đứng giữa MCP client (VS Code / MCP Inspector) và các server upstream
(`trino-mcp` được bảo vệ bằng OAuth, và `mcp-superset`). Nó xử lý Azure AD
Device Code Flow trong suốt, **theo từng user**, và lưu token bền vững trong
Postgres.

```
MCP Client ──HTTP POST /mcp──▶ Kong (:8000, reverse proxy)
                                   │  (hoặc gọi thẳng :6275)
                                   ▼
                              proxy.py  (Starlette)
                               │  resolve identity từ X-Api-Key
                               ▼
                          mcp_handlers.py  (dispatcher theo method)
                          ┌────────┼─────────────┐
                          ▼        ▼             ▼
                  trino_handlers  superset_handlers  auth.py
                          │                          │ (Azure AD device flow)
                          ▼                          ▼
                    trino-mcp (:6274)            Azure AD
                          │
                          ▼
                        db.py ──▶ Postgres (token + session id theo api_key)
```

## Các file chính

| File | Vai trò |
|------|---------|
| [proxy.py](proxy.py) | HTTP entrypoint (Starlette). Resolve identity, route theo JSON-RPC method. |
| [mcp_handlers.py](mcp_handlers.py) | Dispatcher: gọi handler đúng cho `initialize` / `tools/list` / `tools/call`. |
| [trino_handlers.py](trino_handlers.py) | Forward request tới upstream trino-mcp, kèm Bearer token + session id theo api_key. |
| [superset_handlers.py](superset_handlers.py) | Xử lý các tool Superset. |
| [auth.py](auth.py) | Azure AD Device Code Flow: xin device code, poll token, refresh. |
| [db.py](db.py) | Persistence Postgres: token, session id — keyed trực tiếp theo `api_key` (PRIMARY KEY). |

## Định danh (identity)

Kong ở đây chỉ là reverse proxy thuần — không có auth plugin. `api_key` (header
**`X-Api-Key`**) là khóa định danh duy nhất — không còn khái niệm `username`.
Client tự tạo/giữ một api_key (chuỗi bất kỳ do họ chọn hoặc được cấp), gửi kèm
mọi request, và toàn bộ token/session được lưu trực tiếp dưới khóa đó trong
Postgres.

[_resolve_api_key()](proxy.py#L47) trong proxy.py:
- Không có header `X-Api-Key` → trả `None` (caller vô danh).
- Có header → trả nguyên giá trị đó làm `api_key`, không cần tra cứu DB để đổi
  sang identity khác.

## Vòng đời một request (`mcp_endpoint`)

[mcp_endpoint()](proxy.py#L55) xử lý mọi `POST /mcp`:

1. Đọc body + hạ lowercase toàn bộ header.
2. `_resolve_api_key(headers)` → `api_key` (có thể là `None`).
3. Parse JSON. Lỗi parse → trả `-32700 Parse error` (HTTP 400).
4. Route theo `method`:
   - `id is None` → notification, fire-and-forget → `handle_notifications` → HTTP 202.
   - `initialize` → `handle_initialize`
   - `tools/list` → `handle_tools_list`
   - `tools/call` → `handle_tools_call`
   - `ping` → trả `{}`
   - method khác → nếu token hợp lệ thì `forward_to_upstream`, không thì `-32601 Method not found`.
5. Gắn `Mcp-Session-Id` (lấy từ DB theo api_key) vào response header nếu có.

## Method flows

### initialize — [handle_initialize](trino_handlers.py)
- Nếu token không hợp lệ → thử `refresh_token`.
- Nếu token hợp lệ → forward `initialize` lên upstream, lưu `mcp-session-id` trả về vào DB.
- Nếu vẫn chưa auth → trả `SERVER_INFO` cục bộ (client vẫn kết nối được).

### tools/list — [handle_tools_list](mcp_handlers.py) → [_trino_handle_tools_list](trino_handlers.py)
- Token hợp lệ → forward lên upstream lấy danh sách tool thật, cache lại, rồi **merge** với `SUPERSET_TOOLS`.
- Chưa auth → trả fallback: `(_cached_tools hoặc TRINO_TOOLS) + SUPERSET_TOOLS`.

### tools/call — [handle_tools_call](mcp_handlers.py)
1. Nếu tool thuộc Superset → `handle_get_superset_token`.
2. Nếu token không hợp lệ → thử `refresh_token`.
3. Refresh thất bại → `start_device_code_flow(api_key)` rồi trả về
   `_login_required_response` (text hướng dẫn login, hiển thị lại chính api_key đó).
4. Token OK → `handle_trino_tool_call` forward lên upstream.

## Migration

[004_api_key_identity.sql](migrations/004_api_key_identity.sql) đổi
`user_tokens.api_key` thành PRIMARY KEY và xóa cột `username`. Các row chưa có
`api_key` (chưa từng login) sẽ bị xóa khi áp migration này.
