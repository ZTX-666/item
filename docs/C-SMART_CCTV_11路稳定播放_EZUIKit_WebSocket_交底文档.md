# C-SMART CCTV 11 路稳定播放交底文档

更新时间：2026-06-21

## 1. 最终结论

11 支 CCTV 的长期稳定播放方案，应使用 **C-SMART 原生 iframe 播放器 + EZUIKit WebSocket 流**，而不是直接使用 Ezviz OpenAPI 的 HLS/FLV/RTMP。

已验证：

- 通道 4 可以通过 C-SMART 原生 iframe 播放器成功出画面。
- 通道 11 可以通过同一方法成功出画面。
- C-SMART CCTV 页面实际调用 `/api/lapp/live/url/ezopen`，返回 `wss://.../live?dev=E48203280&chn=<channel>&stream=2` 和 `dv.*` 播放 token。
- 旧 HLS 代理适合 1-3 的验证，但对 4-11 会遇到 Ezviz 侧 `9053` 或空片段问题，不应作为 11 路长期方案。

当前推荐入口：

```powershell
node stable-hls-player-server.js --port 3457
```

打开：

```text
http://localhost:3457/player
```

旧 HLS 对照页仍保留：

```text
http://localhost:3457/hls-player?channel=1
```

## 2. 为什么旧 HLS/RTMP 不适合 4-11

前期测试过以下路径：

- `api/lapp/live/address/get` 获取 HLS。
- FLV 地址。
- RTMP 地址并使用 ffmpeg 解码。
- npm 版 `ezuikit-js` 本地播放。

结果：

- 1-3 路 HLS/FLV/RTMP 更容易成功。
- 4-11 路直接 HLS/RTMP 经常返回 Ezviz `9053`、错误片段或 I/O error。
- `device/capture` 截图接口对 4-11 可用，但这只能做截图，不能替代实时视频。

因此问题不在本地播放器或 HLS 代理，而是 **直接 OpenAPI 直播路径对部分通道有限制**。

## 3. C-SMART 自己为什么可以播放

自动登录并监听 C-SMART CCTV 页面后发现，C-SMART 页面会加载：

```text
https://custom.c-smart.hk/csmart-player/cctv-video-list/
```

iframe 播放器接收父页面发送的消息：

```javascript
iframe.contentWindow.postMessage({
  type: 'iframeInit',
  listStr: JSON.stringify([cameraItem])
}, '*');
```

每个 `cameraItem` 来自 C-SMART 后端：

```text
GET https://gateway4.c-smart.hk/video/v5/channel/video/listPage?orgId=1778119371126&status=1&hidden=false&relatedIpc=true&pageNum=1&pageSize=11
```

其中包含 `number`、`cameraName`、`deviceId`、`ezopen`、`ezopenHd`、`areaDomain`、`accessToken`、`deviceType` 等字段。

EZUIKit 会继续请求：

```text
POST https://isgpopen.ezvizlife.com/api/lapp/live/url/ezopen
```

返回：

```json
{
  "code": "200",
  "data": {
    "url": "wss://vtmsgpzl.ezvizlife.com:12001/live?dev=E48203280&chn=11&stream=2",
    "token": "dv.xxx"
  }
}
```

最终由 EZUIKit 通过 WebSocket 播放：

```text
wss://vtmsgpzl.ezvizlife.com:12001/live?dev=E48203280&chn=<channel>&stream=2&ssn=<dv-token>&auth=1&biz=4&cln=100
```

## 4. 当前核心文件

### `stable-hls-player-server.js`

当前主服务，已更正为默认使用 C-SMART iframe/EZUIKit 方案。

主要能力：

- `/player`：11 路稳定播放页面，支持 1/4/9/11 布局。
- `/api/csmart/channels`：返回 C-SMART 11 路 CCTV 列表。
- `/api/csmart/channels?refresh=1`：强制刷新 C-SMART 摄像头列表。
- `/api/token/refresh`：触发后台自动登录脚本刷新 Ezviz token。
- `/hls-player`：旧 HLS 测试页面，仅作为对照保留。
- `/api/live/:channelNo/index.m3u8`：旧 HLS 代理接口。

### `csmart-cctv-iframe-player-core.js`

新保存的可复用核心模块。

核心函数：

- `extractCsmartBearerFromCapture(capture)`：从 Playwright 抓包里提取 C-SMART bearer token。
- `getLatestCsmartBearer(options)`：从已知抓包文件中找到最新 C-SMART token。
- `fetchCsmartChannelList(options)`：调用 C-SMART 后端获取 11 路摄像头列表。
- `normalizeCsmartChannelPayload(payload)`：标准化列表结构。
- `loadCachedChannels()` / `saveCachedChannels()`：读取/保存本地列表缓存。
- `createCsmartIframePlayerHtml(options)`：生成可嵌入的 11 路 iframe 播放页面。

### `auto-login-v15-cctv.js`

自动登录 C-SMART、处理验证码、进入 CCTV 页面并抓包。

建议定期刷新 token 使用：

```powershell
node auto-login-v15-cctv.js --token-refresh-only
```

### `csmart-channel-list-latest.json`

本地缓存的 11 路 CCTV 列表。

注意：该文件包含 Ezviz `accessToken`，属于敏感数据，不应提交到代码仓库或外发。

## 5. 推荐稳定运行流程

### 第一次运行或换电脑

安装依赖：

```powershell
npm install
```

确保系统有 Chrome。当前脚本使用 Playwright `channel: 'chrome'`，需要本机安装 Google Chrome。

先自动登录并抓取 token：

```powershell
node auto-login-v15-cctv.js --token-refresh-only
```

启动稳定播放器服务：

```powershell
node stable-hls-player-server.js --port 3457
```

打开：

```text
http://localhost:3457/player
```

### 日常长期运行

只要缓存 token 未过期，可以直接启动：

```powershell
node stable-hls-player-server.js --port 3457
```

服务会：

- 加载 `cctv-token-cache.json` 里的 Ezviz token。
- 加载 `csmart-channel-list-latest.json` 里的摄像头列表。
- 前端定期请求 `/api/csmart/channels?refresh=1`。
- 后端在需要时调用自动登录脚本刷新 token 和列表。

建议生产或长期运行环境用进程管理器守护，例如 PM2、Windows 服务或计划任务。

## 6. 前端播放原理

页面每个摄像头 tile 创建一个 iframe：

```html
<iframe src="https://custom.c-smart.hk/csmart-player/cctv-video-list/?type=1&t=..."></iframe>
```

iframe 加载完成后，父页面发送：

```javascript
iframe.contentWindow.postMessage({
  type: 'iframeInit',
  listStr: JSON.stringify([cameraItem])
}, '*');
```

`cameraItem` 必须是 C-SMART 后端返回的原始通道对象，不能只传 `deviceSerial` 和 `channelNo`，因为播放器还依赖 `accessToken`、`ezopen`、`areaDomain` 等字段。

## 7. 后端刷新逻辑

后端刷新顺序：

1. 从 `v16c-stream-data/stream-capture-result.json` 等抓包文件提取 C-SMART bearer token。
2. 调用 C-SMART 后端 `video/v5/channel/video/listPage` 获取 11 路列表。
3. 保存为 `csmart-channel-list-latest.json`。
4. 前端定时重新读取 `/api/csmart/channels?refresh=1`，并重建 iframe。

如果 C-SMART bearer token 过期：

1. 调用 `tokenService.refreshNow()`。
2. 执行 `auto-login-v15-cctv.js --token-refresh-only`。
3. 重新生成抓包。
4. 再次提取 C-SMART bearer token 并拉取最新 11 路列表。

## 8. 换电脑说明

换电脑后通常需要重新登录一次 C-SMART，因为以下数据都是临时凭证：

- C-SMART bearer token。
- C-SMART 返回的 Ezviz `accessToken`。
- EZUIKit 临时 `dv.*` 播放 token。

但不需要人工手动打开网页操作，只要环境准备好，运行：

```powershell
npm install
node auto-login-v15-cctv.js --token-refresh-only
node stable-hls-player-server.js --port 3457
```

然后打开：

```text
http://localhost:3457/player
```

## 9. 验证方法

健康检查：

```text
http://localhost:3457/api/health
```

应看到：

```json
{
  "ok": true,
  "hasToken": true,
  "csmartChannelCount": 11
}
```

摄像头列表：

```text
http://localhost:3457/api/csmart/channels
```

应返回 `channels.length === 11`。

强制刷新列表：

```text
http://localhost:3457/api/csmart/channels?refresh=1
```

单路验证脚本：

```powershell
node test-csmart-iframe-player.js 4
node test-csmart-iframe-player.js 11
```

预期生成：

```text
csmart-iframe-channel-4.png
csmart-iframe-channel-11.png
```

截图里应看到实时画面。

## 10. 常见问题

### `/api/csmart/channels` 返回 401

C-SMART bearer token 过期。运行：

```powershell
node auto-login-v15-cctv.js --token-refresh-only
```

然后重启或刷新服务。

### 页面能显示部分通道，但某一路黑屏

先检查 C-SMART 页面是否也黑屏。如果 C-SMART 页面正常，再用：

```powershell
node test-csmart-iframe-player.js <channelNo>
```

查看日志中是否有：

```text
/api/lapp/live/url/ezopen
wss://vtmsgpzl.ezvizlife.com:12001/live
开始播放
```

### 控制台出现 `appKey/get` CORS

在验证中该请求可能报 CORS，但不一定阻断播放。关键看是否继续成功调用 `live/url/ezopen` 并建立 WSS。

### 旧 HLS 页 4-11 不能播

这是预期结果。4-11 应使用 `/player` 的 iframe/EZUIKit WebSocket 路线。

## 11. 安全注意事项

- 不要提交 `csmart-channel-list-latest.json`、`cctv-token-cache.json`、抓包文件到公开仓库。
- 文档或日志中不要暴露完整 `at.*`、`dv.*`、C-SMART bearer token。
- 生产环境不要直接把 `/api/csmart/channels` 暴露到公网。
- 如果集成到 `chtong`，建议由后端统一代理和鉴权，仅向前端提供必要的播放页面。

## 12. 给后续 AI 的重点提示

如果后续 AI 接手，请优先阅读：

1. `C-SMART_CCTV_11路稳定播放_EZUIKit_WebSocket_交底文档.md`
2. `csmart-cctv-iframe-player-core.js`
3. `stable-hls-player-server.js`
4. `auto-login-v15-cctv.js`
5. `test-csmart-iframe-player.js`

不要再把 4-11 的主要方向放在 HLS/RTMP 上。已验证可行方向是：

```text
C-SMART channel list -> custom.c-smart.hk iframe -> postMessage iframeInit -> EZUIKit -> live/url/ezopen -> WSS
```
