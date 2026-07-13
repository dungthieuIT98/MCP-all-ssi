# MCP-all-ssi — Kiến trúc xác thực (Auth Architecture)

> Tài liệu chi tiết về identity & authentication xuyên suốt hệ thống:
> API key → Azure AD Device Code Flow → Bearer token → Trino impersonation /
> Superset JWT. Xem kiến trúc tổng thể tại [architecture.md](architecture.md).

## 1. Mô hình định danh

Có **3 lớp identity** nối tiếp nhau:

| Lớp | Định danh | Ai cấp | Lưu ở đâu |
|---|---|---|---|
| Client ↔ auth-proxy | `api_key` (header `X-Api-Key`) | auth-proxy sinh bằng `secrets.token_urlsafe(32)` khi bắt đầu device flow | Client giữ; Postgres bảng `user_tokens` |
| auth-proxy ↔ trino-mcp | Azure AD access token (JWT, Bearer) | Azure AD (Device Code Flow / refresh) | Postgres, kèm refresh token + claims |
| trino-mcp ↔ Trino | claim `email` trong JWT → `X-Trino-User` | trino-mcp trích từ token đã validate | Không lưu — per-request |
| auth-proxy ↔ Superset | Superset JWT (FAB `create_access_token`) | Superset qua endpoint `azure_login` | Cache RAM tại auth-proxy (TTL 4h) |

Nguyên tắc: **client không bao giờ cầm Azure token** (trừ tool `get_superset_token`
chủ động trả Superset JWT). Client chỉ giữ một `api_key` mờ; mọi token thật nằm
phía server, keyed theo `api_key` trong Postgres.

## 2. Luồng đăng nhập lần đầu (Device Code Flow)

Người dùng không login trước — flow được kích hoạt **lazy** khi gọi tool đầu tiên:

```
Client                auth-proxy                  Azure AD              User (browser)
  │  tools/call           │                           │                       │
  ├──────────────────────▶│                           │                       │
  │                       │ token_valid()? = 0        │                       │
  │                       │ refresh_token()? fail     │                       │
  │                       ├── POST /devicecode ──────▶│                       │
  │                       │◀─ device_code, user_code ─┤                       │
  │                       │   verification_uri        │                       │
  │◀─ result.content: ────┤                           │                       │
  │   "Truy cap <uri>     │  (background task)        │                       │
  │    Nhap code <code>   ├── POST /token (poll) ────▶│                       │
  │    API Key: <key>"    │◀─ authorization_pending ──┤                       │
  │                       │        ...                │   mở devicelogin,     │
  │                       │                           │◀──nhập code, consent──┤
  │                       ├── POST /token (poll) ────▶│                       │
  │                       │◀─ access + refresh token ─┤                       │
  │                       │ decode claims (upn/email) │                       │
  │                       │ lưu Postgres theo api_key │                       │
  │  tools/call (retry,   │                           │                       │
  │  kèm X-Api-Key)       │                           │                       │
  ├──────────────────────▶│ token_valid() = 1 → forward bình thường           │
```

Chi tiết code ([azure/oauth.py](auth-proxy/azure/oauth.py)):

1. `start_device_code_flow(api_key)` — nếu chưa có `api_key` thì sinh mới
   (`secrets.token_urlsafe(32)`). POST tới
   `login.microsoftonline.com/{tenant}/oauth2/v2.0/devicecode` với scope
   `{CLIENT_ID}/.default offline_access` (→ có refresh token).
2. Trạng thái flow (`device_code`, `user_code`, `verification_uri`, task poll)
   giữ trong dict RAM `_device_state[api_key]`; đồng thời ghi DB
   (`save_device_flow_state`). Gọi lại khi đang poll → tái dùng flow cũ,
   không spam Azure.
3. `_poll_for_token` chạy nền, poll `POST /token` với grant
   `urn:ietf:params:oauth:grant-type:device_code`:
   - `authorization_pending` → tiếp tục; `slow_down` → tăng interval +5s;
   - `expired_token` / `bad_verification_code` → hủy flow;
   - 200 → decode payload JWT (không verify chữ ký — chỉ để lấy claims hiển thị),
     lưu `access_token`, `refresh_token`, `expires_at`, `token_claims` vào
     Postgres dưới `api_key`.
4. Message trả cho user ([auth/handlers.py](auth-proxy/auth/handlers.py) —
   `login_message`) chứa URL + code + chính `api_key` để user dán vào header
   `X-Api-Key` cho các request sau.

## 3. Vòng đời token

`token_valid(api_key)` ([auth/handlers.py](auth-proxy/auth/handlers.py#L16)) trả 3 trạng thái:
`0` = chưa từng login, `1` = còn hạn (trừ hao 30s), `2` = có nhưng hết hạn.

```
                    ┌──────────────┐
       chưa có row  │  UNAUTHED(0) │◀───────────────┐
      ┌────────────▶└──────┬───────┘                │ refresh bị Azure trả
      │                    │ device flow OK         │ invalid_grant /
      │             ┌──────▼───────┐                │ interaction_required
      │             │   VALID(1)   │                │ → clear_tokens()
      │             └──────┬───────┘                │
      │    hết expires_at  │                 ┌──────┴───────┐
      │                    └────────────────▶│  EXPIRED(2)  │
      │                                      └──────┬───────┘
      │                 refresh_token() OK          │
      └─────────────────────────────────────────────┘ (quay lại VALID)
```

- **Refresh** ([azure/oauth.py](auth-proxy/azure/oauth.py#L58)): dùng
  `grant_type=refresh_token`, cập nhật cả refresh token mới nếu Azure trả về
  (rotation). Thứ tự thử ở mọi handler: `token_valid == 1` → dùng luôn;
  không thì `refresh_token()`; fail nữa → khởi động lại device flow.
- **Thu hồi**: refresh bị `invalid_grant`/`interaction_required` (đổi mật khẩu,
  admin revoke, Conditional Access…) → xóa token trong DB, user phải login lại.

## 4. Validate token ở upstream (trino-mcp)

auth-proxy chỉ *cầm hộ* token; việc **verify chữ ký** nằm ở trino-mcp (Go),
qua thư viện `tuannvm/oauth-mcp-proxy`:

- Middleware OAuth đăng ký server-wide (`mcp-trino/internal/mcp/server.go`,
  `WithToolHandlerMiddleware`) — mọi tool call đều bị gate.
- Request `/mcp` không có `Authorization: Bearer` → **401** kèm
  `WWW-Authenticate` + resource metadata URL (chuẩn OAuth 2.1 resource server).
- Có Bearer → validate JWT với **JWKS của Azure AD**, kiểm
  `issuer = OIDC_ISSUER` (`https://sts.windows.net/{tenant}/`) và
  `audience = OIDC_AUDIENCE` (`AZURE_CLIENT_ID`) — cấu hình trong
  [docker-compose.yml](docker-compose.yml).
- Nếu upstream trả 401 (token bị reject), auth-proxy báo lỗi gợi ý kiểm tra
  `OIDC_AUDIENCE` ([trino_handlers.py](auth-proxy/trino_handlers.py#L256)).

### Impersonation xuống Trino

- `TRINO_ENABLE_IMPERSONATION=true`, `TRINO_IMPERSONATION_FIELD=email`.
- Handler gọi `prepareImpersonationContext`: lấy user từ OAuth context, chọn
  claim theo field cấu hình (ở đây `email`), nhét vào context.
- Client Trino truyền principal đó qua NamedArg **`X-Trino-User`** — trở thành
  *session user* thật trong Trino (audit log, access control theo user).
  Ngoài ra username OAuth luôn gắn vào `X-Trino-Client-Tags/Info/Source` để
  attribution.
- Bảo vệ 2 lớp phía dữ liệu: `isReadOnlyQuery()` ở app-level (chỉ cho
  SELECT/SHOW/DESCRIBE/EXPLAIN/WITH, chặn multi-statement) + Trino file-based
  access control [rules.json](mcp-trino/trino-conf/rules.json) `read-only`
  toàn catalog.

## 5. Nhánh Superset: đổi Azure token → Superset JWT

Superset gốc chỉ có OAuth browser-redirect, không có REST endpoint đổi token.
[superset_config.py](mcp-superset/superset_config.py) vá thêm qua
`FLASK_APP_MUTATOR`:

```
auth-proxy                        Superset (:8088)
    │  POST /api/v1/security/azure_login
    │  {"access_token": "<azure jwt>"}
    ├────────────────────────────────▶│
    │                                 │ 1. verify JWT: JWKS Azure AD,
    │                                 │    RS256, audience=CLIENT_ID,
    │                                 │    issuer=sts.windows.net/{tenant}
    │                                 │ 2. lấy email/upn/preferred_username
    │                                 │ 3. tìm user trong Superset —
    │                                 │    KHÔNG auto-provision
    │                                 │    (không có → 403)
    │                                 │ 4. create_access_token(user.id)
    │◀── {"access_token": <FAB JWT>} ─┤
```

Điểm đáng chú ý:

- **Không auto-provision**: `AUTH_USER_REGISTRATION = False`; user chưa tồn tại
  trong Superset → 403 "Contact an administrator". Chỉ nhân sự đã được cấp
  quyền Superset mới đi qua được nhánh này.
- Superset **tự verify** Azure JWT (JWKS, RS256, issuer, audience) — không tin
  auth-proxy.
- JWT Superset trả về là per-user thật → mọi call qua superset-mcp giữ nguyên
  roles / RLS / audit của user ([client.py get_caller_token](mcp-superset/client.py#L58)
  ưu tiên Bearer của caller thay vì service account admin).
- Endpoint được exempt CSRF vì auth bằng JWT trong body, không dùng session cookie.
- auth-proxy cache Superset JWT trong RAM 4h theo hash của Azure token
  ([superset_auth.py](auth-proxy/superset_auth.py)); Superset đặt
  `JWT_ACCESS_TOKEN_EXPIRES = 4h` tương ứng.
- Session MCP với superset-mcp được auth-proxy khởi tạo riêng per-key và lưu
  `superset_session_id` trong Postgres; session hỏng (400) → reset + retry 1 lần.

## 6. Session MCP per-user

MCP streamable-http có khái niệm session (`Mcp-Session-Id`). auth-proxy giữ
**2 session id riêng cho mỗi api_key** trong Postgres:

- `upstream_session_id` — session với trino-mcp. Lấy khi forward `initialize`;
  nếu upstream trả `400 Invalid session` thì `_reinitialize()` tự initialize
  lại bằng token của user rồi retry ([trino_handlers.py](auth-proxy/trino_handlers.py#L49)).
- `superset_session_id` — session với superset-mcp, khởi tạo lazy lần đầu gọi
  tool Superset.

Nhờ đó nhiều user dùng chung một auth-proxy không giẫm session/token của nhau.

## 7. Bảng `user_tokens` (Postgres)

Sau migration [004_api_key_identity.sql](auth-proxy/migrations/004_api_key_identity.sql),
`api_key` là PRIMARY KEY và cột `username` bị xóa — api_key là identity duy nhất:

| Cột | Ý nghĩa |
|---|---|
| `api_key` (PK) | Khóa định danh client (giá trị của `X-Api-Key`) |
| `access_token` | Azure AD access token hiện hành |
| `refresh_token` | Azure AD refresh token (offline_access) |
| `expires_at` | Epoch hết hạn access token |
| `token_claims` | Claims JWT đã decode (upn/email… — phục vụ log & Superset) |
| `upstream_session_id` | MCP session với trino-mcp |
| `superset_session_id` | MCP session với superset-mcp |
| (device-flow cols) | State device code flow (migration 003) |

## 8. Điểm yếu / lưu ý bảo mật

1. **Fallback `_local`**: gọi thẳng `:6275` không kèm `X-Api-Key` sẽ chạy
   dưới identity `_local` (env `DEFAULT_API_KEY`) — tiện dev nhưng khi
   production cần chặn truy cập trực tiếp port 6275 (chỉ cho vào qua Kong)
   hoặc tắt fallback.
2. **api_key là bearer credential**: ai cầm key là thành user đó (không có
   thêm yếu tố ràng buộc thiết bị). Client cũng có thể tự bịa key mới — key đó
   chỉ trở thành identity thật sau khi hoàn tất device-code login. Cân nhắc
   TTL/rotation cho api_key và truyền qua HTTPS khi ra khỏi localhost.
   Hiện Kong đang mở CORS `origins: "*"`.
3. **Device-flow state trong RAM**: restart auth-proxy giữa lúc user đang login
   → mất poll task, user phải xin code mới (token đã cấp thì không mất;
   state flow cũng được ghi DB qua `save_device_flow_state` để hiển thị lại).
4. **`decode_token_payload` không verify chữ ký** — chấp nhận được vì chỉ dùng
   lấy claims hiển thị/log phía proxy; verify thật nằm ở trino-mcp và Superset.
5. **Superset JWT cache theo `hash(azure_token)`** (Python `hash()` — không phải
   cryptographic hash và đổi seed mỗi process): đủ cho cache RAM nội bộ, nhưng
   không dùng pattern này cho persistence.
6. Header định danh đã thống nhất là `X-Api-Key` trên toàn bộ code + docs.
   [README.md](auth-proxy/README.md) cũ còn nhắc token cache file JSON —
   thực tế token lưu Postgres.
