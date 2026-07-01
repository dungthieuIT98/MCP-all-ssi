# auth-proxy

MCP proxy nằm giữa VS Code (MCP client) và các backend service. Xử lý Azure AD authentication tự động để client không cần quan tâm đến token.

## Kiến trúc

```
VS Code / MCP Client
        │  POST /mcp
        ▼
  auth-proxy :6275
        │
        ├─ Superset tools ──→ mcp-superset :6276  (Superset JWT)
        │        │
        │        └─ get_superset_token (local, trả JWT về client)
        │
        └─ Trino tools ────→ trino-mcp :6274  (Azure AD Bearer token)
```

| File | Vai trò |
|------|---------|
| `proxy.py` | HTTP server (Starlette), route `/mcp` |
| `mcp_handlers.py` | Dispatcher — phân loại request theo method/tool |
| `auth.py` | Azure AD Device Code Flow, token refresh, cache |
| `trino_handlers.py` | Forward request đến upstream trino-mcp |
| `superset_handlers.py` | Forward read-only Superset tools đến mcp-superset |
| `superset_auth.py` | Đổi Azure token → Superset JWT, fallback admin |

## Luồng xác thực

1. Client gọi tool lần đầu → proxy kiểm tra `access_token`
2. Nếu chưa có → khởi động **Device Code Flow**: proxy trả về message kèm URL + code
3. User mở `https://microsoft.com/devicelogin`, nhập code
4. Background task poll Azure AD → lưu token vào `token_state` và `/app/cache/token_cache.json`
5. Các lần gọi sau: proxy tự attach `Authorization: Bearer <token>` khi forward lên trino-mcp
6. Token hết hạn → tự `refresh_token()` trước khi forward

## Cài đặt & chạy

### Local

```bash
pip install -r requirements.txt
CLIENT_SECRET=<secret> python proxy.py
```

### Docker

```bash
docker build -t auth-proxy .
docker run -p 6275:6275 \
  -e CLIENT_SECRET=<secret> \
  -e UPSTREAM_URL=http://host.docker.internal:6274/mcp \
  -v auth-proxy-cache:/app/cache \
  auth-proxy
```

## Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `CLIENT_SECRET` | _(bắt buộc)_ | Azure AD client secret |
| `UPSTREAM_URL` | `http://host.docker.internal:6274/mcp` | URL của trino-mcp |
| `PROXY_PORT` | `6275` | Port lắng nghe |
| `SUPERSET_URL` | `http://superset:8088` | URL của Superset |
| `SUPERSET_ADMIN_USERNAME` | `admin` | Tài khoản admin Superset (fallback) |
| `SUPERSET_ADMIN_PASSWORD` | `admin` | Mật khẩu admin Superset (fallback) |
| `SUPERSET_MCP_URL` | `http://host.docker.internal:6276/mcp` | URL của mcp-superset (read-only tools) |

## Cấu hình MCP client

Thêm vào `.mcp.json`:

```json
{
  "mcpServers": {
    "trino": {
      "url": "http://localhost:6275/mcp",
      "transport": "http"
    }
  }
}
```

## Tools

### Trino tools (yêu cầu Azure AD login)

| Tool | Mô tả |
|------|-------|
| `execute_query` | Chạy SQL query trên Trino |
| `list_catalogs` | Liệt kê catalogs |
| `list_schemas` | Liệt kê schemas trong catalog |
| `list_tables` | Liệt kê tables trong schema |
| `get_table_schema` | Lấy định nghĩa cột của table |
| `explain_query` | Xem execution plan của query |

### Superset tools (yêu cầu Azure AD login, forward đến mcp-superset)

Chỉ expose các read-only tools — không có create/update/delete.

| Tool | Mô tả |
|------|-------|
| `get_superset_token` | Lấy Superset JWT (xử lý local, trả token về client) |
| `superset_dashboard_list` | Liệt kê dashboards |
| `superset_dashboard_get_by_id` | Chi tiết một dashboard |
| `superset_chart_list` | Liệt kê charts |
| `superset_chart_get_by_id` | Chi tiết một chart |
| `superset_database_list` | Liệt kê database connections |
| `superset_database_get_by_id` | Chi tiết một database connection |
| `superset_database_get_tables` | Liệt kê tables trong database |
| `superset_database_schemas` | Liệt kê schemas trong database |
| `superset_database_get_catalogs` | Liệt kê catalogs trong database |
| `superset_database_validate_sql` | Validate SQL mà không thực thi |
| `superset_dataset_list` | Liệt kê datasets |
| `superset_dataset_get_by_id` | Chi tiết một dataset |
| `superset_sqllab_execute_query` | Chạy SQL query trong SQL Lab |
| `superset_sqllab_get_results` | Lấy kết quả query đã chạy |
| `superset_sqllab_format_sql` | Format SQL cho dễ đọc |
| `superset_sqllab_estimate_query_cost` | Ước tính chi phí thực thi query |
| `superset_saved_query_get_by_id` | Chi tiết một saved query |
| `superset_query_list` | Liệt kê recent queries |
| `superset_query_get_by_id` | Chi tiết một query |
| `superset_user_get_current` | Thông tin user hiện tại |
| `superset_user_get_roles` | Roles của user hiện tại |
| `superset_menu_get` | Lấy menu/navigation data |
| `superset_tag_list` | Liệt kê tags |
| `superset_tag_get_by_id` | Chi tiết một tag |
| `superset_tag_objects` | Liệt kê objects gắn với tags |

## Health check

```bash
curl http://localhost:6275/
# {"status":"ok","authenticated":true,"polling":false,"server":"trino-auth-proxy"}
```

## Token cache

Token được lưu tại `/app/cache/token_cache.json` để tránh phải đăng nhập lại khi restart container. Mount volume để cache tồn tại:

```bash
-v auth-proxy-cache:/app/cache
```
