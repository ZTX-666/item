# Vue 对接文档：WacliDesktop Local API

本文档供 Vue 前端（或另一个窗体/页面）对接 C# 本地 API 使用。  
方案一目标：**Vue 负责 UI，C# 负责业务能力，不重写 wacli / SQLite / 同步逻辑。**

## 1. 启动顺序

1. 可选：先启动 Agent 服务（若需要工具箱功能）

```bat
E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0\start.bat
```

2. 启动 Local API（推荐单独启动，供 Vue 对接）

```bat
E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\start-api.bat
```

或：

```powershell
$env:CHITONG_APP_ROOT = "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0"
dotnet run --project "E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\WacliDesktop.ApiHost\WacliDesktop.ApiHost.csproj"
```

3. 启动 Vue 前端（你的另一个系统）

```bash
npm run dev
```

## 2. 基础信息

| 项 | 值 |
|---|---|
| Local API 地址 | `http://127.0.0.1:8790` |
| Vue dev 地址（示例） | `http://127.0.0.1:5173` |
| AgentToolbox | `http://127.0.0.1:8899` |
| HiAgent 本地 API（原 WPF 内） | 默认 `8787`（与 Local API 不同） |
| 环境变量 | `CHITONG_APP_ROOT` 指向 publish 根目录 |

**重要：** Local API 使用端口 **8790**，避免与 HiAgent 默认端口 **8787** 冲突。

`CHITONG_APP_ROOT` 必须指向包含 `runtime/` 的 publish 目录，例如：

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\04 Whats APP Wacli\publish3.0`

## 3. 健康检查

```http
GET http://127.0.0.1:8790/api/app/info
GET http://127.0.0.1:8790/api/app/status
```

`GET /api/app/status` 返回示例字段：

```json
{
  "authStatusText": "未登录",
  "authenticated": false,
  "authRunning": false,
  "syncRunning": false,
  "currentPhone": "",
  "appRoot": "...",
  "storeDir": "...",
  "dbPath": "...",
  "wacliExeExists": true,
  "mediaDownloaded": 0,
  "mediaPending": 0,
  "mediaProgressText": "附件：0 已下载"
}
```

## 4. 认证 / 登录（Vue Login 页对接）

### 4.1 先订阅 SSE 事件

```javascript
const es = new EventSource('http://127.0.0.1:8790/api/auth/events')

es.addEventListener('log', (e) => {
  const msg = JSON.parse(e.data)
  console.log('log', msg.data.line)
})

es.addEventListener('qr', (e) => {
  const msg = JSON.parse(e.data)
  const payload = msg.data.payload
  // 方式 A：前端自己生成二维码
  // 方式 B：调用 POST /api/auth/qr/png
})

es.addEventListener('pairing_code', (e) => {
  const msg = JSON.parse(e.data)
  console.log('pairing code', msg.data.code)
})

es.addEventListener('auth_state', (e) => {
  const msg = JSON.parse(e.data)
  console.log('auth state', msg.data.state)
})
```

### 4.2 二维码登录

```http
POST http://127.0.0.1:8790/api/auth/qr/start
```

### 4.3 手机号登录

```http
POST http://127.0.0.1:8790/api/auth/phone/start
Content-Type: application/json

{ "phone": "+8613800138000" }
```

### 4.4 停止认证 / 退出

```http
POST http://127.0.0.1:8790/api/auth/stop
POST http://127.0.0.1:8790/api/auth/logout
```

### 4.5 服务端生成 QR PNG（Base64）

```http
POST http://127.0.0.1:8790/api/auth/qr/png
Content-Type: application/json

{ "payload": "2@...." }
```

Vue 显示：

```html
<img :src="'data:image/png;base64,' + pngBase64" />
```

## 5. 同步控制

```http
POST http://127.0.0.1:8790/api/sync/start
Content-Type: application/json

{ "interruptAuth": true }

POST http://127.0.0.1:8790/api/sync/stop
GET  http://127.0.0.1:8790/api/sync/status
```

## 6. 数据库 / 数据浏览

```http
GET  http://127.0.0.1:8790/api/db/profile
POST http://127.0.0.1:8790/api/db/switch-phone
POST http://127.0.0.1:8790/api/db/default-root
POST http://127.0.0.1:8790/api/db/import
POST http://127.0.0.1:8790/api/db/export
GET  http://127.0.0.1:8790/api/db/tables
GET  http://127.0.0.1:8790/api/db/schema?table=messages
POST http://127.0.0.1:8790/api/db/query
GET  http://127.0.0.1:8790/api/db/presets
GET  http://127.0.0.1:8790/api/db/messages?preset=message_detail&limit=100
```

`POST /api/db/query` 请求体：

```json
{
  "sql": "SELECT msg_id, chat_name, text FROM messages LIMIT 20",
  "limit": 100
}
```

仅允许 SELECT，服务端会拦截危险关键字。

## 7. 媒体进度

```http
GET http://127.0.0.1:8790/api/media/progress
```

## 8. 赤瞳工具箱（AgentToolbox 代理）

```http
GET http://127.0.0.1:8790/api/toolbox/health

POST http://127.0.0.1:8790/api/toolbox/call
Content-Type: application/json

{
  "tool": "whatsapp_search",
  "arguments": { "q": "安全", "limit": 10 }
}
```

## 9. 云端同步（耀耀工厂）

```http
GET  http://127.0.0.1:8790/api/cloud/config
POST http://127.0.0.1:8790/api/cloud/config
POST http://127.0.0.1:8790/api/cloud/test
POST http://127.0.0.1:8790/api/cloud/run
```

注意：`GET /api/cloud/config` 不会返回明文 SyncToken。

## 10. Vue 侧推荐封装

建议在 Vue 项目中新增：

```text
src/api/wacli/
  client.ts      // axios/fetch 基址 http://127.0.0.1:8790
  app.ts         // status/info
  auth.ts        // qr/phone/logout + EventSource
  sync.ts
  db.ts
  toolbox.ts
  cloud.ts
```

基址配置示例：

```typescript
export const WACLI_API_BASE = import.meta.env.VITE_WACLI_API_BASE ?? 'http://127.0.0.1:8790'
```

`.env.development`：

```env
VITE_WACLI_API_BASE=http://127.0.0.1:8790
```

## 11. Vue 页面与 API 映射

| Vue 页面 | 主要 API |
|---|---|
| Home | `GET /api/app/status` |
| Login | `POST /api/auth/*` + `GET /api/auth/events` |
| Browse | `GET /api/db/messages`, `GET /api/db/profile` |
| SQL | `GET /api/db/tables`, `POST /api/db/query` |
| Console | `POST /api/sync/*`, `GET /api/app/status` |
| Toolbox | `GET /api/toolbox/health`, `POST /api/toolbox/call` |
| Yaoyao | `GET/POST /api/cloud/*` |

## 12. CORS

ApiHost 已默认允许：

- `http://127.0.0.1:5173`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://localhost:3000`

如需其他 origin，修改：

`WacliDesktop.ApiHost\appsettings.json` → `ApiHost:AllowedOrigins`

## 13. 给新 AI 的对接提示词

```text
Vue 前端需要对接 WacliDesktop Local API，不要直接访问 SQLite 或 wacli.exe。
先阅读：
- VUE_API_INTEGRATION.md
- VUE_REFACTOR_HANDOFF.md

Local API 基址：http://127.0.0.1:8790
启动命令：start-api.bat（需设置 CHITONG_APP_ROOT=publish3.0）

第一阶段只做：
1. Home 状态卡片（GET /api/app/status）
2. Login 页（SSE + QR/Phone 登录）
3. 同步按钮（POST /api/sync/start|stop）
```

## 14. 相关源码

- API Host：`WacliDesktop.ApiHost\Program.cs`
- 后端桥接：`WacliDesktop.ApiHost\Services\WacliBackendHost.cs`
- SSE：`WacliDesktop.ApiHost\Services\AuthEventBroadcaster.cs`
- 原业务层：`WacliDesktop\Services\*`
- 启动脚本：`start-api.bat`
