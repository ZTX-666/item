@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

set BASE=%~dp0
set CHITONG_APP_ROOT=%BASE%

echo [publish3.0] CHITONG_APP_ROOT=%CHITONG_APP_ROOT%
echo [publish3.0] Local API: http://127.0.0.1:8790
echo [publish3.0] 文档: docs\VUE_API_INTEGRATION.md
echo.

dotnet run --project "%BASE%source\WacliDesktop.ApiHost\WacliDesktop.ApiHost.csproj"
