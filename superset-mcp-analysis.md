# Superset MCP Analysis

**Source:** https://github.com/aptro/superset-mcp.git  
**License:** MIT | **Python:** 3.10+ | **Status:** Beta

---

## Overview

MCP server cho Apache Superset, cho phép AI agents kết nối và điều khiển Superset instance qua Model Context Protocol.

### Tech Stack
- **Framework:** FastMCP (MCP server)
- **HTTP Client:** httpx (async)
- **Web:** FastAPI + uvicorn
- **Auth:** Bearer token + CSRF token

---

## MCP Tools (48 total — 21 hidden, 27 active)

> **Đã ẩn**: Toàn bộ Database (12) và SQL Lab (7) tools bị disabled ở cả `mcp-superset/tools/__init__.py` và `auth-proxy/superset_handlers.py`. Lý do: Superset sẽ được config để call Trino hoặc DB khác — AI agent nên query trực tiếp qua Trino MCP thay vì qua Superset SQL Lab.

### Authentication (3)
| Tool | Mô tả |
|------|--------|
| `superset_auth_check_token_validity` | Check token còn valid không |
| `superset_auth_refresh_token` | Refresh access token |
| `superset_auth_authenticate_user` | Login với username/password |

### Dashboard (5)
| Tool | Mô tả |
|------|--------|
| `superset_dashboard_list` | List all dashboards |
| `superset_dashboard_get_by_id` | Get dashboard details |
| ~~`superset_dashboard_create`~~ | Tạo dashboard mới |
| ~~`superset_dashboard_update`~~ | Update dashboard |
| ~~`superset_dashboard_delete`~~ | Xóa dashboard |

### Chart (5)
| Tool | Mô tả |
|------|--------|
| `superset_chart_list` | List all charts |
| `superset_chart_get_by_id` | Get chart details |
| ~~`superset_chart_create`~~ | Tạo chart mới |
| ~~`superset_chart_update`~~ | Update chart |
| ~~`superset_chart_delete`~~ | Xóa chart |

### Database (12) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_database_list`~~ | List databases |
| ~~`superset_database_get_by_id`~~ | Get database details |
| ~~`superset_database_create`~~ | Tạo database connection |
| ~~`superset_database_get_tables`~~ | List tables |
| ~~`superset_database_schemas`~~ | Get schemas |
| ~~`superset_database_test_connection`~~ | Test connection |
| ~~`superset_database_update`~~ | Update database |
| ~~`superset_database_delete`~~ | Delete database |
| ~~`superset_database_get_catalogs`~~ | Get catalogs |
| ~~`superset_database_get_connection`~~ | Get connection info |
| ~~`superset_database_get_function_names`~~ | List SQL functions |
| ~~`superset_database_get_related_objects`~~ | Get related charts/dashboards |
| ~~`superset_database_validate_sql`~~ | Validate SQL |
| ~~`superset_database_validate_parameters`~~ | Validate connection params |

### Dataset (3)
| Tool | Mô tả |
|------|--------|
| `superset_dataset_list` | List all datasets |
| `superset_dataset_get_by_id` | Get dataset details |
| ~~`superset_dataset_create`~~ | Tạo dataset mới |

### SQL Lab (7) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_sqllab_execute_query`~~ | Execute SQL query |
| ~~`superset_sqllab_get_saved_queries`~~ | List saved queries |
| ~~`superset_sqllab_format_sql`~~ | Format SQL |
| ~~`superset_sqllab_get_results`~~ | Get query results |
| ~~`superset_sqllab_estimate_query_cost`~~ | Estimate query cost |
| ~~`superset_sqllab_export_query_results`~~ | Export to CSV |
| ~~`superset_sqllab_get_bootstrap_data`~~ | Get SQL Lab config |

### Query (3) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_query_list`~~ | List queries |
| ~~`superset_query_get_by_id`~~ | Get query details |
| ~~`superset_query_stop`~~ | Stop running query |

### Saved Query (2) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_saved_query_get_by_id`~~ | Get saved query |
| ~~`superset_saved_query_create`~~ | Create saved query |

### User (2)
| Tool | Mô tả |
|------|--------|
| `superset_user_get_current` | Get current user info |
| `superset_user_get_roles` | Get user roles |

### Activity (1) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_activity_get_recent`~~ | Get recent activity |

### Tag (7)
| Tool | Mô tả |
|------|--------|
| `superset_tag_list` | List tags |
| ~~`superset_tag_create`~~ | Create tag |
| `superset_tag_get_by_id` | Get tag details |
| `superset_tag_objects` | Get tagged objects |
| ~~`superset_tag_delete`~~ | Delete tag |
| ~~`superset_tag_object_add`~~ | Add tag to object |
| ~~`superset_tag_object_remove`~~ | Remove tag from object |

### Explore (4)
| Tool | Mô tả |
|------|--------|
| `superset_explore_form_data_create` | Create chart form data |
| `superset_explore_form_data_get` | Get form data |
| `superset_explore_permalink_create` | Create shareable link |
| `superset_explore_permalink_get` | Get permalink |

### Advanced Data Type (2)
| Tool | Mô tả |
|------|--------|
| `superset_advanced_data_type_convert` | Convert value to advanced type |
| `superset_advanced_data_type_list` | List available types |

### System (2) — ~~hidden~~
| Tool | Mô tả |
|------|--------|
| ~~`superset_menu_get`~~ | Get menu data |
| ~~`superset_config_get_base_url`~~ | Get base URL |

---

## Architecture

### Project Structure
```
superset-mcp/
├── main.py          # Entry point - tất cả MCP tools defined ở đây
├── pyproject.toml   # Dependencies
├── Dockerfile       # Container image cho Smithery
├── .env.example     # Environment template
├── smithery.yaml    # Smithery MCP config
└── superset.spec.json
```

### Key Classes/Functions
- **`SupersetContext`** - Lưu trữ client, base_url, access_token, csrf_token
- **`make_api_request()`** - Helper cho HTTP requests với auto-refresh
- **`with_auto_refresh()`** - Auto-refresh token khi gặp 401
- **`get_csrf_token()`** - Lấy CSRF token từ Superset
- **`requires_auth` decorator** - Check authentication trước khi execute
- **`handle_api_errors` decorator** - Consistent error handling

### Authentication Flow

> Kiến trúc auth per-user Azure AD (OAuth2 resource-server) được tách riêng ra
> [auth-architecture.md](auth-architecture.md).

1. Load stored token từ `.superset_token` file
2. Verify token bằng cách gọi `/api/v1/me/`
3. Nếu invalid → refresh token qua `/api/v1/security/refresh`
4. Nếu refresh fail → re-authenticate qua `/api/v1/security/login`
5. Token được lưu lại sau khi auth thành công

### API Pattern
- Base: `SUPERSET_BASE_URL` (default: `http://localhost:8088`)
- Auth: `Authorization: Bearer <token>` header
- CSRF: `X-CSRFToken` header cho POST/PUT/DELETE
- Auto-refresh token on 401 response

---

## Environment Variables

| Variable | Default | Mô tả |
|----------|---------|--------|
| `SUPERSET_BASE_URL` | http://localhost:8088 | Superset URL |
| `SUPERSET_USERNAME` | - | Username |
| `SUPERSET_PASSWORD` | - | Password |

---

## Installation

```bash
# Clone & install
git clone https://github.com/aptro/superset-mcp.git
cd superset-mcp
uv pip install .

# Run MCP server
python main.py

# Install cho Claude Desktop
mcp install main.py
```

---

## Supported Superset Version

Tested với **Superset 4.1.1**

---

## Key Features

- ✅ Token auto-refresh khi hết hạn
- ✅ CSRF token handling
- ✅ Stored token persistence
- ✅ Comprehensive error handling
- ✅ Full CRUD cho dashboards, charts, databases, datasets
- ✅ SQL Lab execution và formatting
- ✅ Tag management
- ✅ Explore/Form data API
- ✅ Advanced data types
