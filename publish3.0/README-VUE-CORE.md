# publish3.0 · 方案一核心代码（Vue 对接）

本目录在原有发布包基础上，已加入 **Vue 对接 Local API** 的核心源码。

## 新增/更新内容

| 路径 | 说明 |
|---|---|
| `source/WacliDesktop/` | WPF 源码（含 `CHITONG_APP_ROOT` 支持） |
| `source/WacliDesktop.ApiHost/` | Local API，Vue 对接入口 |
| `source/WacliDesktopLauncher/` | 启动器源码 |
| `source/vue-shell/` | Vue 3 最小对接示例 |
| `source/WacliDesktop.sln` | 解决方案 |
| `docs/VUE_API_INTEGRATION.md` | Vue 对接接口文档 |
| `docs/VUE_REFACTOR_HANDOFF.md` | 架构与交接文档 |
| `start-api.bat` | 启动 Local API (:8790) |
| `start-vue-shell.bat` | 启动 Vue 示例 (:5173) |

## 原有内容（保留）

- `portable/`、`runtime/`、`agent-services/` — 运行时与 Python 服务
- `start.bat` — 原一键启动（Agent + WPF）
- `ChitongLingxun-standalone.exe` — 独立版可执行文件

## 快速使用

```bat
:: 1. 启动 Local API
start-api.bat

:: 2. 启动 Vue 示例（另一个窗口）
start-vue-shell.bat
```

验证 API：`http://127.0.0.1:8790/api/app/info`

## 对接你自己的 Vue 系统

1. 运行 `start-api.bat`
2. 阅读 `docs/VUE_API_INTEGRATION.md`
3. 配置 `VITE_WACLI_API_BASE=http://127.0.0.1:8790`
4. 参考 `source/vue-shell/src/api/wacli.ts`

## 构建

```powershell
dotnet build E:\publish3.0\source\WacliDesktop.sln
```
