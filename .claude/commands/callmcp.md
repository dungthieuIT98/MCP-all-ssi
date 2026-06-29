# /callmcp — Call MCP Trino Tool

Khi user gõ `/callmcp <tool_name> [args]`, hãy gọi MCP tool tương ứng trên server Trino.

## Bước 1: Kiểm tra token trước khi gọi

Trước khi gọi bất kỳ tool nào, hãy gọi thử `list_catalogs` (tool nhẹ nhất) để kiểm tra trạng thái auth:

- Nếu kết quả trả về **danh sách catalog** → đã có token, tiếp tục gọi tool được yêu cầu
- Nếu kết quả có chứa `https://` hoặc `microsoft.com/devicelogin` hoặc chứa `code` dạng chữ số → chưa đăng nhập, **dừng lại và hiển thị thông tin đăng nhập cho user**:

```
Bạn chưa đăng nhập. Hãy làm theo các bước sau:

1. Mở trình duyệt, truy cập: <url từ kết quả>
2. Nhập mã: <code từ kết quả>
3. Đăng nhập bằng tài khoản Azure AD
4. Sau khi đăng nhập xong, gõ lại lệnh `/callmcp ...` để tiếp tục
```

Không tự động retry — chờ user xác nhận đã đăng nhập xong.

## Bước 2: Gọi tool

```
/callmcp list_catalogs
/callmcp list_schemas catalog=tpch
/callmcp list_tables catalog=tpch schema=sf1
/callmcp execute_query query="SELECT * FROM tpch.sf1.orders LIMIT 10"
/callmcp get_table_schema table=tpch.sf1.orders
/callmcp explain_query query="SELECT count(*) FROM tpch.sf1.orders"
```

## Hành vi

1. Parse `$ARGUMENTS` để lấy tên tool và các tham số
2. Kiểm tra token (xem Bước 1)
3. Gọi MCP tool tương ứng với các tham số đã parse
4. Trả kết quả về cho user ở dạng dễ đọc (table hoặc markdown)

## Tool mapping

| Lệnh | MCP Tool | Tham số bắt buộc |
|------|----------|-----------------|
| `list_catalogs` | `list_catalogs` | — |
| `list_schemas` | `list_schemas` | `catalog` |
| `list_tables` | `list_tables` | `catalog`, `schema` |
| `execute_query` | `execute_query` | `query` |
| `get_table_schema` | `get_table_schema` | `table` |
| `explain_query` | `explain_query` | `query` |

## Lưu ý

- Nếu thiếu tham số bắt buộc, hỏi user trước khi gọi
- Arguments: $ARGUMENTS
