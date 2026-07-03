# /inspector — Chạy MCP Inspector

Khởi động MCP Inspector để test server MCP đang chạy.

## Cách dùng

```
/inspector
```

Hoặc chạy thủ công:

```powershell
$env:CLIENT_PORT=6280; npx @modelcontextprotocol/inspector http://localhost:6275/mcp
```

## Hành động

Chạy lệnh sau trong background:

```powershell
$env:CLIENT_PORT=6280; npx @modelcontextprotocol/inspector http://localhost:6275/mcp
```

Sau đó thông báo cho user địa chỉ truy cập đầy đủ (bao gồm token).

## Lưu ý

- Inspector UI: http://localhost:6280
- MCP server target: http://localhost:6275/mcp (auth-proxy → trino-mcp)
- Transport mode mặc định: **streamable-http**
- Port 6274 là trino-mcp trực tiếp (không qua auth), port 6275 là auth-proxy
- Nếu port 6274 bị chiếm bởi process khác (không phải MCP của user), báo cho user biết
- Không kill process nào cả — tất cả các port đều là container của user

## Thực thi

Khi user gõ `/inspector`, hãy:

1. Chạy lệnh này trong background:
   ```
   npx @modelcontextprotocol/inspector http://localhost:6275/mcp
   ```

2. Đọc output để lấy URL đầy đủ có token

3. Thông báo cho user URL đầy đủ:
   ```
   MCP Inspector đang chạy tại: http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<token>
   Target server: http://localhost:6275/mcp (streamable-http)
   ```
