@echo off
REM ==== Kill any process holding the inspector ports (6277 proxy, 7000 UI) ====
for %%P in (6277 7000) do (
    for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
        echo Killing PID %%A on port %%P
        taskkill /F /PID %%A >nul 2>&1
    )
)

set CLIENT_PORT=7000
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
