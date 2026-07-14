# mcp-superset — Mô tả từng file (dạng cây thư mục)

MCP server (Model Context Protocol) cho Apache Superset. Cho phép AI agent kết nối và thao tác với một Superset instance qua REST API. Server chạy ở chế độ **streamable-http** trên cổng 8000, hiện cấu hình **read-only** (chỉ đọc), xác thực **per-user only**: token trong header `Authorization` của mỗi request chính là JWT Superset dùng được luôn (không lưu username/password, không service-account).

Luồng chạy: `main.py` → `_mcp.py` (FastMCP + lifespan) → `client.py` (HTTP client + đọc caller token) → `tools/*` (đăng ký @mcp.tool) → `utils/*` (helper gọi API).

```
mcp-superset/
│
├── tools/                     📦 Các công cụ MCP — mỗi file = 1 nhóm API Superset
│   │                             (hầu hết bọc @requires_auth + @handle_api_errors)
│   ├── __init__.py            🔀 Đăng ký tool đang bật: auth, chart, dashboard,
│   │                             dataset, explore, tag, user
│   ├── auth.py                🔑 Xác thực: check_token_validity (kiểm tra caller token qua /me)
│   ├── chart.py               📊 Chart (read-only): chart_list, chart_get_by_id
│   ├── dashboard.py           📈 Dashboard (read-only): dashboard_list, dashboard_get_by_id
│   ├── dataset.py             🗂️ Dataset (read-only): dataset_list, dataset_get_by_id
│   ├── explore.py             🔍 Explore: form_data_get, permalink_get (lấy lại cấu hình chart theo key)
│   ├── tag.py                 🏷️ Tag (read-only): tag_list, tag_get_by_id, tag_objects
│   └── user.py                👤 User & hoạt động: user_get_current, user_get_roles, activity_get_recent
│
├── utils/                     🧰 Helper dùng chung
│   ├── __init__.py            📄 Đánh dấu package (chỉ docstring)
│   ├── api.py                 🌐 Lõi gọi API: make_api_request (GET/POST/PUT/DELETE + CSRF,
│   │                             gắn caller token; 401 → trả thẳng cho caller re-auth),
│   │                             get_csrf_token, delete_with_confirmation_async
│   ├── constants.py           🔗 Tập trung đường dẫn endpoint Superset (/api/v1/...)
│   └── decorators.py          🎀 requires_auth (bắt buộc caller token) + handle_api_errors (bắt lỗi)
│
├── .env.example               📝 Mẫu biến môi trường: chỉ SUPERSET_BASE_URL
├── .gitignore                 🚫 Bỏ qua build, .venv, .env
├── .python-version            🐍 Phiên bản Python (3.13) cho pyenv/uv
│
├── __init__.py                🧩 Package init — import TẤT CẢ module tool để đăng ký; export mcp,
│                                 get_superset_context, SupersetContext
├── _mcp.py                    ⭐ Tạo instance FastMCP dùng chung ("superset") + lifespan
│                                 (khởi tạo/dọn SupersetContext). Mọi tool "from _mcp import mcp"
├── client.py                  🔐 HTTP client (httpx) + SupersetContext + get_caller_token
│                                 (đọc per-user token từ header Authorization của mỗi request)
├── config.py                  🎚️ Đọc cấu hình từ .env qua python-dotenv (chỉ base_url)
├── main.py                    🚀 Entry point — chạy uvicorn (streamable-http) trên 0.0.0.0:8000
│
├── Dockerfile                 🐳 Đóng gói server (python:3.10-slim, expose 8000, python main.py)
├── smithery.yaml              🛠️ Cấu hình nền tảng Smithery (chạy stdio, schema config, command)
├── pyproject.toml             📦 Metadata & dependency (fastapi, httpx, mcp[cli], uvicorn, dotenv) + black/isort
├── uv.lock                    🔒 Lockfile khóa phiên bản dependency cho uv (không sửa tay)
│
├── superset.spec.json         📘 Bản đặc tả OpenAPI/Swagger REST API Superset (tra cứu khi thêm/sửa tool)
└── README.md                  📖 Hướng dẫn cài đặt & sử dụng (Smithery, chạy Superset local, .env)
```

---

## Chú thích thêm về "khi nào dùng"

| File / nhóm | Khi nào dùng |
|-------------|--------------|
| `main.py` | Chạy `python main.py` để bật server (production/deploy) |
| `_mcp.py`, `__init__.py` | Trung tâm khởi tạo & đăng ký tool — sửa khi thêm module tool |
| `tools/__init__.py` | Sửa để thêm/bớt nhóm tool hiển thị cho AI |
| `client.py`, `utils/api.py` | Lõi bảo mật & mọi request tới Superset đi qua đây |
| `config.py`, `.env.example` | Cấu hình base_url Superset lúc khởi động |
| `Dockerfile`, `smithery.yaml`, `pyproject.toml`, `uv.lock` | Đóng gói & deploy |
| `README.md`, `superset.spec.json` | Tài liệu tham chiếu (không chạy runtime) |

**Ghi chú:** các file tools ở chế độ read-only — mọi hàm create/update/delete đã được comment ẩn trong code.
