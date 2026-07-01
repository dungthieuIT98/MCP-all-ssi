# MCP Project Architecture

## Tổng Quan

Project này là một hệ thống **Model Context Protocol (MCP)** gồm nhiều service kết nối AI clients với các data platform (Trino SQL Engine và Apache Superset).

---

## Sơ Đồ Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────┐
│           AI CLIENTS                                     │
│  (Claude Desktop / Cursor / VSCode / Web)               │
└────────────┬────────────────────────┬───────────────────┘
             │ STDIO                  │ HTTP
             ▼                        ▼
    ┌─────────────────┐    ┌──────────────────────┐
    │  mcp-trino      │    │  auth-proxy          │
    │  (STDIO mode)   │    │  port: 6275          │
    └────────┬────────┘    │  Azure AD OAuth      │
             │             └──────────┬───────────┘
             │                        │ HTTP /mcp
             └──────────┬─────────────┘
                        ▼
            ┌───────────────────────┐
            │  mcp-trino (Go)       │
            │  port: 6274 / 8080    │
            │  HTTP StreamableHTTP  │
            ├───────────────────────┤
            │  MCP Tools:           │
            │  • execute_query      │
            │  • list_catalogs      │
            │  • list_schemas       │
            │  • list_tables        │
            │  • get_table_schema   │
            │  • sample_table       │
            │  • explain_query      │
            └───────────┬───────────┘
                        │ SQL
                        ▼
            ┌───────────────────────┐
            │  Trino SQL Engine     │
            │  port: 8090 → 8080    │
            │  (trinodb/trino:424)  │
            └──────┬────────────────┘
                   │
         ┌─────────┴──────────┐
         ▼                    ▼
    ┌─────────┐         ┌───────────┐
    │  MySQL  │         │ PostgreSQL │
    │  :3307  │         │  BigQuery  │
    │  (demo) │         │  S3, etc   │
    └─────────┘         └───────────┘

            ┌───────────────────────┐
            │  mcp-superset (Py)    │
            │  FastMCP / STDIO      │
            ├───────────────────────┤
            │  30+ MCP Tools:       │
            │  • auth tools (3)     │
            │  • dashboard (5)      │
            │  • chart (5)          │
            │  • database (13)      │
            │  • sqllab (7)         │
            │  • query (3)          │
            │  • tag (6)            │
            └───────────┬───────────┘
                        │ HTTP REST
                        ▼
            ┌───────────────────────┐
            │  Apache Superset      │
            │  port: 8088           │
            │  BI Dashboard         │
            └───────────────────────┘
```

---

## Các Service Components

### 1. `mcp-trino` — Go MCP Server

**Mục đích:** Cầu nối giữa AI clients và Trino SQL Engine

| Thuộc tính | Giá trị |
|-----------|---------|
| Ngôn ngữ | Go |
| Transport | STDIO hoặc HTTP (StreamableHTTP) |
| Port (HTTP) | 8080 (container), 6274 (host) |
| Auth | OAuth 2.1 (tùy chọn: HMAC, Okta, Google, Azure) |

**Cấu trúc thư mục:**
```
mcp-trino/
├── cmd/
│   ├── main.go          # Entry point, mode detection
│   └── cli.go           # CLI mode
├── internal/
│   ├── config/config.go # Environment config & validation
│   ├── trino/client.go  # SQL client, security, caching
│   ├── mcp/
│   │   ├── handlers.go  # Tool implementations
│   │   └── server.go    # Server + OAuth middleware
│   └── cli/
│       ├── commands.go  # CLI subcommands
│       ├── repl.go      # Interactive shell
│       └── config.go    # YAML/JSON config
├── charts/              # Kubernetes Helm charts
├── Dockerfile
└── go.mod
```

**MCP Tools:**

| Tool | Mô tả |
|------|-------|
| `execute_query` | Thực thi SQL (chỉ đọc mặc định) |
| `list_catalogs` | Liệt kê catalogs |
| `list_schemas` | Liệt kê schemas |
| `list_tables` | Liệt kê tables |
| `get_table_schema` | Lấy schema & DDL của table |
| `sample_table` | Schema + 5 rows mẫu + stats |
| `explain_query` | Phân tích query plan |

---

### 2. `mcp-superset` — Python FastMCP Server

**Mục đích:** Tích hợp AI với Apache Superset BI platform

| Thuộc tính | Giá trị |
|-----------|---------|
| Ngôn ngữ | Python |
| Framework | FastMCP |
| Transport | STDIO hoặc HTTP |
| Auth | JWT Bearer + CSRF token |

**Cấu trúc thư mục:**
```
mcp-superset/
├── main.py              # Entry point
├── _mcp.py              # FastMCP server instance
├── client.py            # Superset HTTP client
├── config.py            # Environment config
├── tools/
│   ├── auth.py          # Authentication (3 tools)
│   ├── dashboard.py     # Dashboard ops (5 tools)
│   ├── chart.py         # Chart ops (5 tools)
│   ├── database.py      # Database mgmt (13 tools)
│   ├── dataset.py       # Dataset ops (3 tools)
│   ├── sqllab.py        # SQL Lab (7 tools)
│   ├── query.py         # Query mgmt (3 tools)
│   ├── saved_query.py   # Saved queries (2 tools)
│   ├── explore.py       # Chart exploration
│   ├── user.py          # User info
│   ├── system.py        # System & menu
│   └── tag.py           # Tag mgmt (6 tools)
└── utils/
    ├── api.py           # API helpers, token refresh
    ├── constants.py     # API endpoint constants
    └── decorators.py    # @requires_auth, @handle_api_errors
```

---

### 3. `auth-proxy` — Python OAuth Proxy

**Mục đích:** Xử lý Azure AD authentication cho mcp-trino

| Thuộc tính | Giá trị |
|-----------|---------|
| Ngôn ngữ | Python |
| Framework | Starlette |
| Port | 6275 |
| Auth Flow | Azure AD Device Code Flow |

**Cấu trúc:**
```
auth-proxy/
├── proxy.py          # Main Starlette server, /mcp endpoint
├── auth.py           # Azure AD device code flow
├── mcp_handlers.py   # MCP message forwarding
├── superset_auth.py  # Superset auth (optional)
└── requirements.txt
```

**Flow xác thực:**
```
Client → auth-proxy:6275/mcp
    → Azure AD (device code)
    → Token acquired & cached
    → Forward to trino-mcp:8080/mcp
    → Response proxied back
```

---

### 4. `stdio-wrapper` — Go STDIO↔HTTP Bridge

**Mục đích:** Chuyển đổi STDIO messages sang HTTP POST

```
AI Client (STDIO) → stdio-wrapper → HTTP POST → upstream MCP
```

**Dùng khi:** MCP client chỉ hỗ trợ STDIO nhưng downstream là HTTP (auth-proxy).

---

## Docker Compose Stack

```yaml
Services:
  mysql      → port 3307:3306  (Data source)
  trino      → port 8090:8080  (SQL Engine)
  trino-mcp  → port 6274:8080  (MCP Server)
  auth-proxy → port 6275:6275  (OAuth Proxy)

Network: trino-net (bridge)
Volumes:
  mysql-data        (MySQL persistent storage)
  auth-proxy-cache  (Token cache)
```

**Dependency chain:**
```
mysql → trino → trino-mcp → auth-proxy
```

---

## Security Architecture

### Read-Only Query Enforcement
- Pre-compiled regex ngăn INSERT/UPDATE/DELETE/DROP/ALTER
- Chỉ cho phép: SELECT, SHOW, DESCRIBE, EXPLAIN, WITH
- Override: `TRINO_ALLOW_WRITE_QUERIES=true`

### OAuth 2.1 Support
| Provider | Mode |
|----------|------|
| HMAC | Symmetric JWT signing |
| Azure AD | OIDC + Device Code Flow |
| Okta | OIDC |
| Google | OIDC |

### User Impersonation (mcp-trino)
```
JWT Token → extract claim (username/email/subject)
         → set X-Trino-User header
         → Trino enforces per-user ACL
```

### Allowlisting
- Catalog: `TRINO_ALLOWED_CATALOGS=mysql,postgres`
- Schema: `TRINO_ALLOWED_SCHEMAS=mysql.demo`
- Table: `TRINO_ALLOWED_TABLES=mysql.demo.users`

---

## Environment Variables

### mcp-trino
```bash
# Trino Connection
TRINO_HOST=localhost
TRINO_PORT=8080
TRINO_USER=trino
TRINO_PASSWORD=
TRINO_CATALOG=mysql
TRINO_SCHEMA=demo
TRINO_SCHEME=https
TRINO_SSL=true

# Security
TRINO_ALLOW_WRITE_QUERIES=false
TRINO_QUERY_TIMEOUT=30s
TRINO_ENABLE_IMPERSONATION=false
TRINO_ALLOWED_CATALOGS=
TRINO_ALLOWED_SCHEMAS=
TRINO_ALLOWED_TABLES=

# MCP Server
MCP_TRANSPORT=stdio        # stdio | http
MCP_PORT=8080
MCP_HOST=0.0.0.0

# OAuth (optional)
OAUTH_ENABLED=false
OAUTH_PROVIDER=hmac        # hmac | okta | google | azure
JWT_SECRET=
OIDC_ISSUER=
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
```

### mcp-superset
```bash
SUPERSET_BASE_URL=http://localhost:8088
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin
# Token saved in .superset_token file
```

### auth-proxy
```bash
PROXY_PORT=6275
UPSTREAM_URL=http://trino-mcp:8080/mcp
CLIENT_SECRET=            # Azure AD client secret
```

---

## HTTP Endpoints

### mcp-trino
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/mcp` | POST | StreamableHTTP MCP endpoint |
| `/sse` | POST | Legacy SSE (backward compat) |
| `/` | GET | Server status & version |

### auth-proxy
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/mcp` | POST | Proxy to upstream với auth |

---

## Technology Stack

| Component | Language | Framework/Lib |
|-----------|----------|---------------|
| mcp-trino | Go 1.21+ | mcp-go, trino-go-client, oauth-mcp-proxy |
| mcp-superset | Python 3.11+ | FastMCP, httpx, starlette |
| auth-proxy | Python 3.11+ | Starlette, httpx, uvicorn |
| stdio-wrapper | Go | stdlib only |
| Trino | Java (Docker) | trinodb/trino:424 |
| Superset | Python (Docker) | apache/superset:latest |
| MySQL | Docker | mysql:8.0 |

---

## Data Flow Examples

### Query SQL qua mcp-trino
```
1. Client gửi: tools/call → execute_query { sql: "SELECT..." }
2. mcp-trino kiểm tra: read-only? allowlist OK?
3. trino/client.go thực thi qua trino-go-client
4. Kết quả format JSON: { columns, rows, stats }
5. Trả về client
```

### Authenticate & List Dashboards qua mcp-superset
```
1. Client gọi: superset_auth_authenticate_user
2. tools/auth.py → POST /api/v1/security/login
3. Token saved to .superset_token
4. Client gọi: superset_dashboard_list
5. @requires_auth decorator kiểm tra token
6. GET /api/v1/dashboard với Bearer token
7. Trả về danh sách dashboards
```

---

## Kubernetes Deployment

Helm chart tại `mcp-trino/charts/mcp-trino/`:
- Deployment, Service, Ingress
- ConfigMap, Secret, RBAC
- HPA (Horizontal Pod Autoscaling)
- Network Policy, PodDisruptionBudget
- Values files: `values-development.yaml`, `values-production.yaml`
