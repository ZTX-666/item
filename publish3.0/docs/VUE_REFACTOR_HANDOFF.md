# Vue 重构交接指南：WacliDesktop / 赤瞳灵讯

本文档用于让新的 AI 或开发者快速接手：在不破坏现有 C# / WPF 业务架构的前提下，将桌面 UI 逐步重构为 Vue 前端。

## 1. 当前结论

当前软件是一个 .NET 8 WPF 桌面应用，主项目可以正常构建和启动。

- 项目类型：C# WPF 桌面程序
- 目标框架：`net8.0-windows`
- 主入口：`WacliDesktop\App.xaml`
- 启动窗口：`HomeWindow.xaml`
- 主业务能力：WhatsApp 登录、wacli 同步、SQLite 数据浏览、媒体缩略图/附件处理、云端同步、HiAgent 本地 API、AgentToolbox 调用
- 构建验证：`dotnet build` 成功，0 warning，0 error

不要把目标理解为“把 C# 窗口直接塞进 Vue”。正确目标是：

> 保留现有 C# 业务层、运行时目录、数据库路径、外部进程调用、同步逻辑和服务编排；新增一个最小 API 层，让 Vue 替代 WPF UI 调用这些能力。

## 2. 绝对路径总览

软件根目录：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli`

主 WPF 项目：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj`

Launcher 项目：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktopLauncher\WacliDesktopLauncher.csproj`

当前 Debug 构建产物：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\bin\Debug\net8.0-windows\WacliDesktop.exe`

建议运行命令：

```powershell
dotnet build "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj"
```

```powershell
dotnet run --project "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj"
```

## 3. 必须保留的现有架构

Vue 重构时不要重写这些核心能力：

- `WacliService`：负责调用 `wacli.exe`，包括 QR 登录、手机号配对、同步、退出、状态读取、进程管理。
- `AppConfig`：负责 AppRoot、runtime、wacli 路径、数据库路径、缩略图目录和环境变量。
- `DatabaseProfileStore`：负责多手机号数据库目录、数据库导入导出、默认数据目录、profile 保存。
- `DatabaseStoreMutex`：负责跨进程互斥，避免多个实例同时写同一数据库。
- `SqliteQueryService` / `CloudSyncDataReader`：负责 SQLite 查询和云同步数据读取。
- `CloudSyncService` / `CloudSyncConfig` / `CloudSyncState`：负责耀耀工厂云端同步。
- `HiAgentLocalApiServer` / `HiAgentBridgeService` / `HiAgentBridgeConfig`：负责本地 HTTP API 和 HiAgent 桥接。
- `AgentToolboxClient`：负责调用本地 AgentToolbox HTTP 服务，默认 `http://127.0.0.1:8899`。
- `RuntimeEnvironment` / `EnvironmentSetupService` / `ToolDiscovery`：负责本地工具发现、环境初始化、wacli 编译或路径解析。

Vue 层应该只替代 WPF 交互界面，不应该直接管理 wacli 进程、SQLite 文件锁、DPAPI token 或本地工具探测。

## 4. 推荐目标架构

推荐采用“C# 本地后端 + Vue UI”的分层方案：

```text
Vue 前端
  |
  | HTTP / SSE / WebSocket
  v
C# Local API Host
  |
  | 调用现有 Services
  v
WacliService / SqliteQueryService / CloudSyncService / HiAgent / AgentToolbox
  |
  v
runtime / SQLite / wacli.exe / Python agent-services
```

### 最小改造原则

- 不移动现有 `Services` 文件。
- 不改变 `AppConfig` 的路径规则。
- 不改变 `WACLI_STORE_DIR` 行为。
- 不改变 `runtime`、`portable`、`agent-services` 的发布结构。
- 不直接让 Vue 访问 SQLite 文件。Vue 必须通过 C# API 查询。
- 不直接让 Vue 启动或 kill `wacli.exe`。Vue 必须通过 C# API 调用 `WacliService`。
- 不把 C# 业务逻辑搬到 TypeScript，除非是纯展示逻辑。

## 5. 建议新增的 C# API 层

新增一个本地 API host，优先使用 ASP.NET Core Minimal API，监听 `127.0.0.1`。

建议新增项目：

`WacliDesktop.ApiHost`

也可以先在 `WacliDesktop` 里临时新增本地 API 服务，但长期建议单独项目，避免污染 WPF UI。

建议端口：

- Vue dev server：`http://127.0.0.1:5173`
- C# local API：`http://127.0.0.1:8787`
- AgentToolbox：`http://127.0.0.1:8899`
- ChitungCenter：`http://127.0.0.1:8999`
- HiAgentLocalApiServer：按 `HiAgentBridgeConfig` 配置，代码中由 `_port` 决定

### API 草案

认证/状态：

- `GET /api/app/status`：返回登录状态、sync 状态、当前手机号、数据库路径、媒体下载进度。
- `POST /api/auth/qr/start`：调用 `WacliService.StartQrAuth()`。
- `POST /api/auth/phone/start`：调用 `WacliService.StartPhoneAuth(phone)`。
- `POST /api/auth/stop`：调用 `WacliService.StopAuth()`。
- `POST /api/auth/logout`：调用 `WacliService.Logout()`。
- `GET /api/auth/events`：SSE 推送 log、QR payload、pairing code、auth state。

同步：

- `POST /api/sync/start`：调用 `WacliService.StartSync()`。
- `POST /api/sync/stop`：调用 `WacliService.StopSync()`。
- `GET /api/sync/status`：返回 sync running、store dir、最近日志。

SQLite / 数据浏览：

- `GET /api/db/profile`：返回 `DefaultDatabaseRoot`、`CurrentPhone`、`DbPath`、`ThumbnailDir`。
- `POST /api/db/switch-phone`：调用 `AppConfig.SwitchToPhone(phone, out message)`。
- `POST /api/db/default-root`：调用 `AppConfig.SetDefaultDatabaseRoot(path, out message)`。
- `POST /api/db/import`：调用 `AppConfig.ImportDatabase(sourcePath, out message)`。
- `POST /api/db/export`：调用 `AppConfig.ExportDatabase(targetPath, out message)`。
- `GET /api/db/tables`：调用 `SqliteQueryService.ListTables()`。
- `GET /api/db/schema?table=...`：调用 `SqliteQueryService.GetSchema(table)`。
- `POST /api/db/query`：执行受限 SQL 查询，必须保持只读防护。
- `GET /api/messages`：迁移现有消息列表查询。

媒体：

- `GET /api/media/progress`：调用 `MediaBackfillService.GetCounts()`。
- `GET /api/media/thumbnail?msgId=...`：返回缩略图或文件图标。
- `GET /api/media/file?path=...`：必须做路径白名单，禁止任意文件读取。

云同步：

- `GET /api/cloud/config`：读取 `CloudSyncConfig.Load()`，不要返回明文 token。
- `POST /api/cloud/config`：保存配置，继续使用 DPAPI 保护 token。
- `POST /api/cloud/test`：调用 `CloudSyncService.TestConnectionAsync()`。
- `POST /api/cloud/run`：调用 `CloudSyncService.RunSyncAsync()`。
- `GET /api/cloud/events`：SSE 推送同步日志。

AgentToolbox：

- `GET /api/toolbox/health`：调用 `AgentToolboxClient.HealthCheckAsync()`。
- `POST /api/toolbox/call`：代理调用 `AgentToolboxClient.CallToolAsync()`。
- 可先暴露三个现有封装：`whatsapp_search`、`query_safety_cases`、`search_form_templates`。

HiAgent：

- 现有 `HiAgentLocalApiServer` 已提供：
  - `GET /health`
  - `GET /api/ping`
  - `GET /api/messages/search?q=&limit=10`
  - `POST /api/upload`
- Vue 重构时不要删除该服务。可以新增页面用于配置、启动、停止和复制外网转发地址。

## 6. WPF UI 到 Vue 页面映射

现有 WPF 首页入口：

`WacliDesktop\HomeWindow.xaml`

对应代码：

`WacliDesktop\HomeWindow.xaml.cs`

首页模块点击映射：

- `login` -> `ModuleShellWindow("登录配对", new LoginView(), 920, 580)`
- `browse` -> `ModuleShellWindow("数据浏览", new BrowseView(), 960, 620)`
- `sql` -> `ModuleShellWindow("SQLite 查询", new SqlView(), 980, 620)`
- `console` -> `ModuleShellWindow("命令工具", new ConsoleView(), 920, 640)`
- `toolbox` -> `ModuleShellWindow("赤瞳工具箱", new ChitungToolboxView(), 1080, 720)`
- `BtnEnvSetup_Click` -> `SetupProgressWindow`
- `BtnYaoyaoFactory_Click` -> `YaoyaoFactoryWindow`
- `BtnHelp_Click` -> `HelpWindow`

建议 Vue 路由：

- `/`：首页 Dashboard，对应 `HomeWindow`
- `/login`：登录配对，对应 `Views\LoginView`
- `/browse`：数据浏览，对应 `Views\BrowseView`
- `/sql`：SQLite 查询，对应 `Views\SqlView`
- `/console`：命令工具，对应 `Views\ConsoleView`
- `/toolbox`：赤瞳工具箱，对应 `Views\ChitungToolboxView`
- `/setup`：配置环境，对应 `SetupProgressWindow`
- `/yaoyao`：耀耀工厂，对应 `YaoyaoFactoryWindow`
- `/help`：帮助，对应 `HelpWindow`
- `/hiagent`：HiAgent 桥接，对应 `HiAgentBridgeWindow`

## 7. 关键源码地址

### 项目文件

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktopLauncher\WacliDesktopLauncher.csproj`

### WPF 入口和窗口

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\App.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\App.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HomeWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HomeWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\MainWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\MainWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\ModuleShellWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\ModuleShellWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\SetupProgressWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\SetupProgressWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\YaoyaoFactoryWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\YaoyaoFactoryWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HiAgentBridgeWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HiAgentBridgeWindow.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HelpWindow.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\HelpWindow.xaml.cs`

### WPF UserControls

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\LoginView.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\LoginView.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\BrowseView.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\BrowseView.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\SqlView.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\SqlView.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\ConsoleView.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\ConsoleView.xaml.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\ChitungToolboxView.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Views\ChitungToolboxView.xaml.cs`

### 服务层源码

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\AppConfig.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\AppServices.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\WacliService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\DatabaseProfileStore.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\DatabaseStoreMutex.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\SqliteQueryService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\MediaBackfillService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\ThumbnailService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\FileIconService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\MessageRowMapper.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\WacliQuickCommands.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\CloudSyncService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\CloudSyncConfig.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\CloudSyncState.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\CloudSyncDataReader.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\HiAgentBridgeService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\HiAgentBridgeConfig.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\HiAgentLocalApiServer.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\AgentToolboxClient.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\EnvironmentSetupService.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\RuntimeEnvironment.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\ToolDiscovery.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Services\ModuleWindowManager.cs`

### Helpers / Models

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Helpers\AppBranding.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Helpers\HelpContent.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Helpers\GridViewFitHelper.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Helpers\QrHelper.cs`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Models\MessageRowViewModel.cs`

### 主题和资源

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Themes\AppThemes.xaml`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Assets\app-icon.ico`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Assets\app-icon.png`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Assets\banner-cscec.png`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\Assets\FileIcons\*.png`

这些资源在 `WacliDesktop.csproj` 中作为 `Resource` 和 `Content` 引入。Vue 重构时可以复制到 Vue 的 `public` 或 `src/assets`，但不要改变 C# 项目中的原资源路径。

## 8. 发布包和运行资源地址

主要发布包：

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish20`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish23`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish22`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish21`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish12`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish11`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish10`

主启动脚本示例：

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\start.bat`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\portable\start.bat`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\source\start.bat`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish20\start.bat`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish23\start.bat`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\releease\publish22\start.bat`

`publish3.0\start.bat` 会做这些事情：

- 检查 Python 3.11+。
- 启动 AgentToolbox：`http://127.0.0.1:8899`。
- 启动 ChitungCenter：`http://127.0.0.1:8999`。
- 等待 4 秒。
- 启动主程序：`portable\WacliDesktop.exe`。

Agent 服务目录：

- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\agent-toolbox`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\agent-toolbox\requirements.txt`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\agent-toolbox\run_server.py`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\agent-toolbox\README.md`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\chitung-center`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\chitung-center\requirements.txt`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\chitung-center\run_server.py`
- `E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\agent-services\chitung-center\README.md`

Runtime 目录：

- 发布运行时：`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\runtime`
- 源码 Debug 运行时：`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\bin\Debug\net8.0-windows\runtime`

`AppConfig` 中的运行时约定：

- `AppRoot`：如果 exe 位于 `portable`，则 AppRoot 是其父目录；否则是 exe 所在目录。
- `RuntimeDir`：`<AppRoot>\runtime`
- `LocalBinDir`：`<AppRoot>\runtime\bin`
- `LocalWacliExe`：`<AppRoot>\runtime\bin\wacli.exe`
- `WacliSrcDir`：`<AppRoot>\runtime\src\wacli`
- `WacliWebDir`：`<AppRoot>\runtime\wacli-web`
- `EnvironmentManifestPath`：`<AppRoot>\runtime\environment.json`
- `DatabaseProfilePath`：`<AppRoot>\runtime\database-profile.json`
- `CloudSyncConfig`：`<AppRoot>\runtime\cloud-sync.json`
- `CloudSyncState`：通常在 `runtime` 中，由 `CloudSyncState` 决定实际文件名
- `HiAgent uploads log`：`<AppRoot>\runtime\hiagent-uploads.jsonl`

默认用户数据目录：

`%USERPROFILE%\ChitongLingxun`

## 9. 外部依赖和端口

.NET：

- SDK：本机已检测到 .NET SDK 8.0 和 9.0。
- Runtime：本机已检测到 `Microsoft.WindowsDesktop.App 8.0`。

NuGet：

- `Microsoft.Data.Sqlite` `10.0.8`
- `QRCoder` `1.8.0`
- `System.Drawing.Common` `8.0.0`

外部工具：

- Python 3.11+
- Git
- Go
- GCC
- `wacli.exe`

远程仓库：

- `https://github.com/steipete/wacli.git`

本地端口：

- `8899`：AgentToolbox
- `8999`：ChitungCenter
- HiAgent 本地 API：`HiAgentLocalApiServer` 动态配置端口
- 建议新增 C# API：`8787`
- 建议 Vue dev server：`5173`

## 10. Vue 迁移分阶段计划

### 阶段 0：冻结现状

先验证当前 C# 项目：

```powershell
dotnet build "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj"
```

再启动：

```powershell
dotnet run --project "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop\WacliDesktop.csproj"
```

记录当前 WPF 行为，特别是：

- 首页状态显示
- 登录配对 QR 和手机号流程
- sync 启停
- 数据库浏览和 SQL 查询
- 媒体缩略图和附件下载状态
- AgentToolbox 页面
- 云同步页面
- HiAgent 桥接页面

### 阶段 1：新增 C# API Host

新增本地 API 项目或服务层。先不要写 Vue 页面。

第一批 API 只做：

- `/api/app/status`
- `/api/auth/qr/start`
- `/api/auth/phone/start`
- `/api/auth/stop`
- `/api/auth/events`
- `/api/sync/start`
- `/api/sync/stop`
- `/api/db/profile`

验收标准：

- API 能启动。
- WPF 原程序仍能启动。
- `WacliService` 仍只存在一份核心逻辑。
- QR payload、pairing code、log 能通过 SSE 推到浏览器。

### 阶段 2：创建 Vue 壳

创建 Vue 项目，建议 Vite + Vue 3 + TypeScript。

建议目录：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliVue`

建议页面：

- `src/pages/Home.vue`
- `src/pages/Login.vue`
- `src/pages/Browse.vue`
- `src/pages/Sql.vue`
- `src/pages/Console.vue`
- `src/pages/Toolbox.vue`
- `src/pages/Setup.vue`
- `src/pages/Yaoyao.vue`
- `src/pages/HiAgent.vue`
- `src/pages/Help.vue`

建议 API 客户端：

- `src/api/client.ts`
- `src/api/auth.ts`
- `src/api/sync.ts`
- `src/api/db.ts`
- `src/api/cloud.ts`
- `src/api/toolbox.ts`
- `src/api/hiagent.ts`

### 阶段 3：先迁移 Home + Login

先做首页和登录页面，因为这是核心使用链路。

Vue Home 对标：

- `HomeWindow.xaml`
- `HomeWindow.xaml.cs`

Vue Login 对标：

- `Views\LoginView.xaml`
- `Views\LoginView.xaml.cs`
- `WacliService.StartQrAuth()`
- `WacliService.StartPhoneAuth(phone)`
- `QrHelper.CreateImage(payload)`：Vue 中可改用 JS QR 库生成二维码，但 QR payload 必须来自 C# API。

验收标准：

- Vue 可显示登录状态。
- 点击 QR 登录后能显示二维码。
- 手机号登录能显示配对码。
- 停止登录正常。
- 登录后 C# 能自动绑定手机号数据库。

### 阶段 4：迁移数据浏览和 SQL

对标：

- `Views\BrowseView.xaml`
- `Views\BrowseView.xaml.cs`
- `Views\SqlView.xaml`
- `Views\SqlView.xaml.cs`
- `SqliteQueryService.cs`
- `MessageRowMapper.cs`
- `MessageRowViewModel.cs`

重点：

- SQL 查询必须只读。
- 禁止 Vue 任意传文件路径让后端读取。
- 表名和 SQL 参数必须校验。
- 大结果集必须分页。

### 阶段 5：迁移 Console / Toolbox / Cloud / HiAgent

对标：

- `Views\ConsoleView.xaml`
- `Views\ChitungToolboxView.xaml`
- `YaoyaoFactoryWindow.xaml`
- `HiAgentBridgeWindow.xaml`
- `AgentToolboxClient.cs`
- `CloudSyncService.cs`
- `HiAgentBridgeService.cs`

这些页面依赖外部服务和长任务，必须使用 SSE 或 WebSocket 推日志，不要用长轮询硬等。

### 阶段 6：选择最终承载方式

有两种最终形态：

1. Vue 独立浏览器访问 + C# Local API 后台运行。
2. C# 桌面壳使用 WebView2 承载 Vue，保留桌面安装包体验。

如果用户最终还是要“桌面软件”，推荐 WebView2：

- C# 启动 Local API。
- C# 启动或加载 Vue 静态文件。
- WebView2 打开 `http://127.0.0.1:<port>` 或本地静态资源。
- Vue 通过 HTTP/SSE 调用 C#。

## 11. 安全和兼容性注意事项

- Local API 必须只监听 `127.0.0.1`，不要默认监听 `0.0.0.0`。
- 对会修改数据或启动进程的 API 加本地 token 或随机 session key。
- `CloudSyncConfig.SyncToken` 继续使用 DPAPI，不要把 token 明文返回给 Vue。
- 文件下载/缩略图接口必须限制在 `AppConfig.StoreDir`、`ThumbnailDir` 或允许的媒体目录内。
- SQL 接口默认只允许 SELECT / WITH，不允许 INSERT、UPDATE、DELETE、DROP、ATTACH。
- `DatabaseStoreMutex` 不能绕过。
- `WacliService.KillWacliProcesses()` 行为影响全局 `wacli` 进程，迁移时不要随意扩大调用范围。
- 不要改变 `AppConfig.ApplyWacliEnvironment()` 设置 `WACLI_STORE_DIR` 的逻辑。
- 发布包内 Python `.venv` 很大，迁移时不要把它复制进 Vue 源码目录。

## 12. 给新 AI 的首轮任务提示

建议直接把下面这段发给新 AI：

```text
你正在接手一个 C# WPF 到 Vue 的渐进式重构。目标不是重写业务逻辑，而是在不破坏现有架构的前提下，用 Vue 替换 WPF UI。

请先阅读：
1. E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\VUE_REFACTOR_HANDOFF.md
2. WacliDesktop\WacliDesktop.csproj
3. WacliDesktop\App.xaml
4. WacliDesktop\HomeWindow.xaml.cs
5. WacliDesktop\Services\AppConfig.cs
6. WacliDesktop\Services\WacliService.cs
7. WacliDesktop\Services\AppServices.cs
8. WacliDesktop\Services\DatabaseProfileStore.cs
9. WacliDesktop\Services\SqliteQueryService.cs
10. WacliDesktop\Services\CloudSyncService.cs
11. WacliDesktop\Services\HiAgentLocalApiServer.cs
12. WacliDesktop\Services\AgentToolboxClient.cs

先运行 dotnet build 验证现状。不要删除或移动现有 WPF 文件。第一步只新增一个 C# Local API 层，复用现有 Services，并暴露 Home/Login 所需 API。完成 API 后再创建 Vue 3 + Vite 前端壳。
```

## 13. 当前建议的 token / 工作量策略

不要一次性让 AI 重构全部模块。建议按以下会话切分：

- 会话 1：API 架构落地，`/api/app/status`、auth、sync、SSE。
- 会话 2：Vue 项目初始化，Home + Login。
- 会话 3：Browse + Sql。
- 会话 4：Console + Toolbox。
- 会话 5：Cloud Sync + HiAgent。
- 会话 6：WebView2 或发布集成。
- 会话 7：端到端测试、打包、文档。

每个会话都要求：

- 先构建。
- 小步修改。
- 不改原服务职责。
- 保留 WPF 可运行。
- 增加最小测试或手工验证命令。

## 15. 方案一准备工作（已完成）

已为 Vue 对接准备好 C# Local API 层，无需重写 WPF 业务逻辑。

### 新增内容

| 路径 | 说明 |
|---|---|
| `WacliDesktop.ApiHost\` | ASP.NET Core Local API 项目 |
| `WacliDesktop.sln` | 解决方案（含 WPF + Launcher + ApiHost） |
| `start-api.bat` | 一键启动 Local API |
| `VUE_API_INTEGRATION.md` | Vue 对接文档（端口、接口、示例） |
| `AppConfig.cs` | 新增 `CHITONG_APP_ROOT` 环境变量支持 |

### Local API 地址

`http://127.0.0.1:8790`

### 启动命令

```bat
start-api.bat
```

或：

```powershell
$env:CHITONG_APP_ROOT = "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0"
dotnet run --project "WacliDesktop.ApiHost\WacliDesktop.ApiHost.csproj"
```

### Vue 对接第一步

1. 启动 `start-api.bat`
2. 浏览器访问 `http://127.0.0.1:8790/api/app/info` 确认服务正常
3. Vue 项目配置 `VITE_WACLI_API_BASE=http://127.0.0.1:8790`
4. 先对接 `GET /api/app/status` 和 Login 相关 API（见 `VUE_API_INTEGRATION.md`）

### 注意

- Local API 端口 **8790**，HiAgent 默认 **8787**，不要混用。
- `CHITONG_APP_ROOT` 必须指向含 `runtime/` 的 publish 目录。
- 若 `runtime/bin/wacli.exe` 不存在，需先在 WPF 中「配置环境」或手动安装 wacli。

