# MCP-all-ssi — Kiến trúc hệ thống

> Tài liệu mô tả kiến trúc tổng thể của hệ thống MCP Data Platform: một bộ MCP server
> (Trino + Superset) đặt sau một auth-proxy xử lý Azure AD, expose qua Kong Gateway
> cho các MCP client (VS Code, Claude Code, MCP Inspector).
>
> Xem thêm: [auth-architecture.md](auth-architecture.md) (chi tiết luồng xác thực),
> [architecture.html](architecture.html) (bản diagram tương tác).

## 1. Tổng quan

Hệ thống cho phép AI assistant (qua giao thức MCP) truy vấn dữ liệu **Trino** và đọc
metadata **Superset**, với định danh người dùng thật (Azure AD) được giữ xuyên suốt
tới tận query engine (Trino impersonation) và Superset (per-user JWT, roles/RLS).

```
┌──────────────────────┐
│  MCP Client          │  VS Code / Claude Code / MCP Inspector
│  (.mcp.json /        │  header: X-Api-Key: <api_key>
│   claude.json)       │
└──────────┬───────────┘
           │ HTTP POST /mcp (JSON-RPC 2.0)
           ▼
┌──────────────────────┐
│  Kong Gateway :8000  │  bare reverse proxy + CORS
└──────────┬───────────┘  (không có auth plugin)
           ▼
┌──────────────────────────────────────────────────────────┐
│  auth-proxy :6275  (Python / Starlette)                  │
│  • identity = giá trị header X-Api-Key (api_key)         │
│  • Azure AD Device Code Flow (login lần đầu)             │
│  • refresh token tự động, quản lý MCP session per-user   │
│  • dispatcher: tool Trino ↔ tool Superset                │
└───────┬──────────────────────────────┬───────────────────┘
        │ Bearer <Azure AD token>      │ Bearer <Superset JWT>
        ▼                              ▼
┌──────────────────┐          ┌──────────────────────┐
│ trino-mcp :8080  │          │ superset-mcp :8000   │
│ (Go, OAuth-      │          │ (Python FastMCP,     │
│  protected)      │          │  read-only tools)    │
└───────┬──────────┘          └──────────┬───────────┘
        │ X-Trino-User = email           │ REST API /api/v1
        ▼                                ▼
┌──────────────────┐          ┌──────────────────────┐
│ Trino :8090      │◀────────▶│ Superset :8088       │
│ (read-only,      │  charts  │ (Azure AD OAuth +    │
│  impersonation)  │  query   │  azure_login API)    │
└───────┬──────────┘          └──────────────────────┘
        ▼
┌──────────────────┐          ┌──────────────────────┐
│ MySQL :3307      │          │ Postgres             │
│ (catalog demo)   │          │ (token store của     │
└──────────────────┘          │  auth-proxy)         │
                              └──────────────────────┘
```

## 2. Các thành phần

| Thành phần | Thư mục | Công nghệ | Vai trò |
|---|---|---|---|
| **Kong Gateway** | [kong/](kong/) | Kong (DB-less, [kong.yml](kong/kong.yml)) | Reverse proxy thuần + CORS. Route `/mcp` và `/` → auth-proxy. Không có auth plugin — identity xử lý ở auth-proxy. |
| **auth-proxy** | [auth-proxy/](auth-proxy/) | Python, Starlette, psycopg3 | Trái tim của hệ thống. Nhận JSON-RPC từ client, xử lý Azure AD Device Code Flow theo từng user, gắn Bearer token và forward lên upstream. |
| **trino-mcp** | [mcp-trino/](mcp-trino/) | Go, mcp-go, oauth-mcp-proxy | MCP server cho Trino. OAuth-protected (validate Azure AD JWT), impersonate user xuống Trino theo claim `email`. |
| **stdio-wrapper** | [stdio-wrapper/](stdio-wrapper/) | Go | Cầu nối cho client chỉ hỗ trợ stdio: đọc JSON-RPC từng dòng từ stdin → POST tới auth-proxy `:6275/mcp` → in response ra stdout. |
| **superset-mcp** | [mcp-superset/](mcp-superset/) | Python, FastMCP (streamable-http) | MCP server cho Superset REST API. Chỉ enable nhóm tool read-only (auth, chart, dashboard, dataset, explore, tag, user). |
| **Superset** | container `superset` | apache/superset + [superset_config.py](mcp-superset/superset_config.py) | BI platform. Được vá thêm endpoint `POST /api/v1/security/azure_login` để đổi Azure token → Superset JWT. |
| **Trino** | container `trino` | trinodb/trino:424 | Query engine. Access control file-based: **read-only toàn bộ catalog** ([rules.json](mcp-trino/trino-conf/rules.json)). |
| **Postgres** | container `postgres` | postgres:16 | Token store của auth-proxy: access/refresh token, claims, session id — keyed theo `api_key`. |
| **MySQL** | container `mysql` | mysql:8.0 | Data source demo, được Trino kết nối qua catalog `mysql`. |

Tất cả chạy chung network Docker `trino-net` ([docker-compose.yml](docker-compose.yml)).
Chỉ Kong (`:8000`, `:8001`), auth-proxy (`:6275`), Superset (`:8088`), Trino (`:8090`)
và MySQL (`:3307`) publish port ra host; `trino-mcp` và `superset-mcp` chỉ expose nội bộ.

## 3. Flow chính

### 3.1. Request lifecycle (một tool call)

Mọi request là `POST /mcp` với body JSON-RPC 2.0. [proxy.py](auth-proxy/proxy.py) xử lý:

1. **Resolve identity** — đọc header `X-Api-Key`:
   - Không có header → dùng `DEFAULT_API_KEY` (`_local`, cho local dev).
   - Có header → giá trị đó chính là `api_key`, không tra cứu DB — key chưa
     từng login sẽ được đưa vào device-code flow khi gọi tool.
2. **Parse JSON-RPC** — lỗi parse → `-32700`.
3. **Route theo `method`**:

| Method | Handler | Hành vi |
|---|---|---|
| notification (`id == null`) | `handle_notifications` | Fire-and-forget, trả HTTP 202. Chỉ forward nếu đã có token hợp lệ. |
| `initialize` | [trino_handlers.handle_initialize](auth-proxy/trino_handlers.py#L164) | Token hợp lệ → forward lên trino-mcp, lưu `Mcp-Session-Id`. Chưa auth → trả `SERVER_INFO` cục bộ (client vẫn kết nối được **trước khi** login). |
| `tools/list` | [mcp_handlers.handle_tools_list](auth-proxy/mcp_handlers.py#L28) | Lấy tool list thật từ trino-mcp (cache lại) rồi **merge** thêm `SUPERSET_TOOLS`. Chưa auth → fallback danh sách tĩnh. |
| `tools/call` | [mcp_handlers.handle_tools_call](auth-proxy/mcp_handlers.py#L46) | Xem 3.2. |
| `ping` | inline | Trả `{}`. |
| khác | `forward_to_upstream` | Forward nguyên văn nếu đã auth, không thì `-32601`. |

4. **Response** — gắn header `Mcp-Session-Id` (session upstream lưu theo user trong Postgres).

### 3.2. Tool call flow

```
tools/call
   │
   ├── token chưa hợp lệ?
   │      ├── refresh_token() OK ──────────────┐
   │      └── refresh fail → start Device Code │
   │            Flow → trả message hướng dẫn   │
   │            login (URL + code + api_key)   │
   │                                           ▼
   ├── tool ∈ SUPERSET_TOOLS ──▶ đổi Azure token → Superset JWT
   │                              │  (POST /api/v1/security/azure_login)
   │                              └─▶ forward tới superset-mcp
   │                                  (Bearer JWT + Mcp-Session-Id riêng)
   │
   └── tool ∈ TRINO_TOOLS ─────▶ forward tới trino-mcp
                                  (Bearer Azure token + Mcp-Session-Id)
                                  │
                                  ├── 400 "Invalid session" → re-initialize
                                  │     upstream, retry 1 lần
                                  └── 401 → báo token bị reject
```

### 3.3. Đường đi của một câu SQL

```
Client ──"execute_query {query}"──▶ Kong ──▶ auth-proxy
   ──Bearer Azure JWT──▶ trino-mcp
        │ validate JWT (issuer/audience, JWKS Azure AD)
        │ lấy claim email → impersonation
        ▼
      Trino (X-Trino-User = email, access control read-only)
        ▼
      MySQL catalog → kết quả JSON trả ngược về client
```

- trino-mcp chặn query ghi ở tầng ứng dụng (`isReadOnlyQuery()`: chỉ cho
  SELECT / SHOW / DESCRIBE / EXPLAIN / WITH).
- Trino chặn tiếp ở tầng engine: [rules.json](mcp-trino/trino-conf/rules.json)
  đặt `allow: read-only` cho mọi catalog — phòng thủ 2 lớp.

### 3.4. Tool Superset

`get_superset_token` xử lý cục bộ tại auth-proxy (đổi Azure token → Superset JWT rồi
trả JWT về client). Các tool `superset_*` còn lại forward tới superset-mcp kèm JWT
per-user, nên [mcp-superset/client.py](mcp-superset/client.py) (`get_caller_token`)
dùng đúng identity + roles + RLS của user thật thay vì service account admin.

## 4. MCP tools

**Trino** (định nghĩa upstream tại mcp-trino, fallback tĩnh tại
[trino_handlers.py](auth-proxy/trino_handlers.py#L27)):
`execute_query`, `list_catalogs`, `list_schemas`, `list_tables`,
`get_table_schema`, `sample_table`, `explain_query`, `ping_trino`
(đăng ký tại `mcp-trino/internal/mcp/handlers.go` — `RegisterTrinoTools()`).

**Superset** (whitelist read-only tại
[superset_handlers.py](auth-proxy/superset_handlers.py#L23)):
`get_superset_token`, `superset_dashboard_list/get_by_id`,
`superset_chart_list/get_by_id`, `superset_dataset_list/get_by_id`,
`superset_saved_query_get_by_id`, `superset_query_list/get_by_id`,
`superset_user_get_current`, `superset_user_get_roles`, `superset_menu_get`,
`superset_tag_list/get_by_id/objects`.

Nhóm tool ghi/nguy hiểm của mcp-superset (`database`, `sqllab`, `query`,
`saved_query`, `system`) bị tắt ngay tại [tools/__init__.py](mcp-superset/tools/__init__.py)
— truy vấn SQL đi qua đường Trino MCP.

## 5. Cách client kết nối

| Cách | Endpoint | Ghi chú |
|---|---|---|
| Qua Kong (khuyến nghị) | `http://localhost:8000/mcp` | Kèm header `X-Api-Key` — xem [claude.json](claude.json). |
| Trực tiếp auth-proxy | `http://localhost:6275/mcp` | Không có key → chạy với identity `_local` (dev). |
| Client chỉ hỗ trợ stdio | chạy [stdio-wrapper](stdio-wrapper/main.go) | Bridge stdin/stdout ↔ HTTP `:6275/mcp`. |

Lần gọi tool đầu tiên khi chưa login sẽ trả về hướng dẫn Device Code Flow
(URL `microsoft.com/devicelogin` + user code + api_key). Sau khi login xong,
client giữ `api_key` làm `X-Api-Key` cho mọi request sau — chi tiết ở
[auth-architecture.md](auth-architecture.md).

## 6. Lưu ý / điểm cần biết

- **Identity = `api_key`**: sau migration
  [004_api_key_identity.sql](auth-proxy/migrations/004_api_key_identity.sql),
  `api_key` là PRIMARY KEY của `user_tokens`, không còn cột `username`.
  [db.py](auth-proxy/db.py) expose bộ hàm keyed theo api_key
  (`get_by_api_key`, `upsert_by_api_key`, `save_device_flow_state`,
  `clear_tokens`, `get/set_*_session`); [proxy.py](auth-proxy/proxy.py) lấy
  identity trực tiếp từ giá trị header `X-Api-Key` (không tra cứu DB —
  key chưa có row nghĩa là chưa login, sẽ được đưa vào device-code flow).
- Header định danh đã thống nhất là **`X-Api-Key`** trên toàn bộ code + docs.
  Lưu ý [README.md](auth-proxy/README.md) cũ còn nhắc token cache file JSON —
  thực tế token lưu Postgres.
- Device-flow state (`_device_state` trong [azure/oauth.py](auth-proxy/azure/oauth.py))
  nằm trong RAM — restart auth-proxy giữa chừng login sẽ mất flow đang poll
  (token đã cấp thì bền vững trong Postgres).
- Kong hiện là pass-through; nếu cần rate-limit / key-auth tập trung thì thêm
  plugin tại [kong.yml](kong/kong.yml).
