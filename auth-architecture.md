# Auth Architecture

Per-user Azure AD identity. Mỗi user call xuống Superset bằng đúng danh tính Azure của họ.

## Luồng

```
User (Azure token)
  → auth-proxy: đổi Azure token lấy Superset JWT qua POST /api/v1/security/azure_login
  → forward tool call kèm Authorization: Bearer <per-user JWT>
  → mcp-superset: đọc token đó, gọi Superset API bằng chính token
  → Superset
```

## 3 bước

1. **Superset** (`superset_config.py`) — endpoint `POST /api/v1/security/azure_login`:
   verify Azure JWT (JWKS), auto-tạo user nếu chưa có (role `Gamma`), trả per-user Superset JWT.

2. **auth-proxy** (`superset_auth.py`, `superset_handlers.py`) — đổi Azure token qua
   `azure_login`, forward JWT per-user xuống mcp-superset.

3. **mcp-superset** (`client.py`, `utils/api.py`) — đọc Bearer token của caller per-request,
   dùng nó gọi Superset (không dùng chung admin). 401 → không fallback admin.

## Endpoint

```
POST /api/v1/security/azure_login
Body: {"access_token": "<azure jwt>"}
→     {"access_token": "<superset jwt>"}
```

## Env

| Service | Vars |
|---------|------|
| Superset | `OAUTH_CLIENT_ID`, `OAUTH_TENANT_ID`, `OAUTH_CLIENT_SECRET`, `SUPERSET_SECRET_KEY` |
| auth-proxy | `SUPERSET_URL`, `SUPERSET_ADMIN_USERNAME/PASSWORD`, `CLIENT_SECRET` |
| mcp-superset | `SUPERSET_BASE_URL`, `SUPERSET_USERNAME/PASSWORD` |

## Lưu ý

Superset OAuth chỉ chạy qua browser redirect, không có REST đổi token trực tiếp — nên phải
tự thêm endpoint `azure_login`. Service account (admin) chỉ dùng khi chạy mcp-superset độc lập.
