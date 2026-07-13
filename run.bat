@echo off
REM ==== Kill any process holding the inspector ports (6277 proxy, 6280 UI) ====
for %%P in (6277 6280) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo Killing PID %%A on port %%P
        taskkill /F /PID %%A >nul 2>&1
    )
)

REM ==== Launch MCP Inspector against trino-mcp (direct, port 6274) ====
REM   - Inspector UI:    http://localhost:6280
REM   - Proxy:           http://localhost:6277
REM   - Target MCP:      http://localhost:6274/mcp  (streamable-http)
REM
REM NOTE: trino-mcp now requires an X-User-Email header ending in an @ssi domain
REM (e.g. demoA@ssi.com.vn). In the Inspector UI, add it under
REM   Authentication -> Header Name: X-User-Email / Value: demoA@ssi.com.vn
REM before calling any tool, otherwise requests are rejected with 401.

set CLIENT_PORT=6280
npx @modelcontextprotocol/inspector http://localhost:6274/mcp
