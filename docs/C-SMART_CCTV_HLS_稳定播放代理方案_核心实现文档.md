# C-SMART CCTV HLS 稳定播放代理方案核心实现文档

> 目标：把 C-SMART / Ezviz 返回的短有效期 HLS 地址，封装成 chtong 或其他系统可长期播放的稳定本地地址。  
> 更新时间：2026-06-21  
> 本次验证通道：`E48203280` / channel `1`  

---

## 1. 背景与结论

C-SMART CCTV 页面背后使用萤石 Ezviz。我们可以通过 C-SMART 自动登录和网络监听拿到 Ezviz `accessToken`，再调用 Ezviz Open API 获取 HLS 流地址。

直接播放 Ezviz 返回的 m3u8 有一个核心问题：

- Ezviz HLS URL 有效期很短。
- 如果前端直接播放一次性 m3u8，过期后会断。
- 如果前端每 18-20 秒销毁 hls.js 并重新加载新 URL，会产生 1-2 秒闪断。

本方案采用 **后端 HLS 代理**：

```text
chtong 前端
  固定播放：
  /api/cctv/live/1/index.m3u8

chtong 后端
  自动刷新 Ezviz HLS 短地址
  拉取上游 m3u8
  重写分片 URL
  代理 ts 分片

Ezviz
  只对后端暴露短期 m3u8 和 ts 分片
```

结论：

- 可以消除“短 URL 过期导致的周期性重启/闪断”。
- 前端不需要知道 Ezviz token，也不需要接触真实 m3u8。
- 4G 摄像头本身断流无法完全消除，但可以通过缓冲、重试、降码率降低感知。

---

## 2. 本次实测结果

优化前的“前端定时重连”方案：

- 75 秒测试成功。
- 期间每 18 秒主动重连一次。
- 会有短暂黑屏/加载感。

优化后的“后端 HLS 代理”方案：

```text
测试命令：
node stable-hls-smoke-test.js --channel 1 --seconds 90 --port 3457
```

结果：

```json
{
  "success": true,
  "playableSamples": 17,
  "totalSamples": 18,
  "channel": 1,
  "seconds": 90,
  "final": {
    "currentTime": 84.03,
    "paused": false,
    "readyState": 4,
    "videoWidth": 640,
    "videoHeight": 480,
    "error": null,
    "app": {
      "reconnectCount": 1,
      "lastReason": "auto start",
      "lastError": ""
    }
  }
}
```

关键观察：

- 90 秒内没有周期性销毁播放器。
- 播放时间连续推进到 84 秒。
- 最终状态仍在播放，`paused=false`。
- 视频分辨率 `640x480`。
- 期间出现过非 fatal 的 `bufferStalledError` / `levelLoadError`，hls.js 自动恢复，没有触发整体重启。

---

## 3. 关键文件

| 文件 | 用途 |
|---|---|
| `cctv-hls-proxy-core.js` | 可复用核心模块，建议 chtong 正式集成使用 |
| `csmart-ezviz-token-refresh-service.js` | Ezviz token 缓存、提取、定时刷新、热更新服务 |
| `stable-hls-player-server.js` | 本地 demo 服务，含播放器页面和代理路由 |
| `stable-hls-smoke-test.js` | Playwright 自动化稳定性测试脚本 |
| `C-SMART_CCTV_视频流+截图_Pipeline_完整实现文档.md` | C-SMART 登录、抓 token、取流完整背景文档 |

---

## 4. 核心原理

### 4.1 Ezviz 取流

后端调用：

```text
POST https://isgpopen.ezvizlife.com/api/lapp/live/address/get
Content-Type: application/x-www-form-urlencoded

accessToken=at.xxx
deviceSerial=E48203280
channelNo=1
protocol=2
quality=2
```

返回：

```json
{
  "code": "200",
  "data": {
    "url": "https://vtmucyn.ezvizlife.com:8883/v3/openlive/E48203280_1_2.m3u8?...",
    "expireTime": "..."
  }
}
```

### 4.2 上游 m3u8 示例

```m3u8
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:2.476,
https://vtmucyn.ezvizlife.com:8883/openlivepar/E48203280_1_2/xxx-88.ts
#EXTINF:2.477,
https://vtmucyn.ezvizlife.com:8883/openlivepar/E48203280_1_2/xxx-89.ts
```

### 4.3 代理后 m3u8

后端把每个真实分片 URL 改写成本地代理 URL：

```m3u8
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-ALLOW-CACHE:NO
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:712788421
#EXTINF:2.476,
/api/cctv/live/1/segment/712788421?src=https%3A%2F%2Fvtmucyn...
#EXTINF:2.477,
/api/cctv/live/1/segment/712788422?src=https%3A%2F%2Fvtmucyn...
```

前端只看到：

```text
/api/cctv/live/1/index.m3u8
```

不会看到 Ezviz token，也不会被短期 m3u8 地址变化影响。

---

## 5. 可复用核心模块

核心文件：

```text
cctv-hls-proxy-core.js
```

导出：

```javascript
const { CctvHlsProxyCore } = require('./cctv-hls-proxy-core');
```

### 5.1 最小 Node 服务示例

```javascript
const http = require('http');
const { CctvHlsProxyCore } = require('./cctv-hls-proxy-core');

const proxy = new CctvHlsProxyCore({
  accessToken: process.env.EZVIZ_ACCESS_TOKEN,
  deviceSerial: process.env.EZVIZ_DEVICE_SERIAL || 'E48203280',
  routePrefix: '/api/cctv',
  protocol: 2,
  quality: 2,
  upstreamLeaseMs: 18000,
});

const server = http.createServer(async (req, res) => {
  try {
    const handled = await proxy.handleRequest(req, res);
    if (!handled) {
      res.writeHead(404);
      res.end('Not found');
    }
  } catch (err) {
    proxy.sendJson(res, 500, { error: err.message });
  }
});

server.listen(3457, () => {
  console.log('CCTV proxy listening on http://localhost:3457');
});
```

### 5.2 暴露的接口

默认 `routePrefix=/api/cctv`：

| 接口 | 说明 |
|---|---|
| `GET /api/cctv/health` | 检查 token / deviceSerial 是否存在 |
| `GET /api/cctv/cameras` | 获取摄像头列表 |
| `GET /api/cctv/stream/:channelNo` | 获取一次性 Ezviz HLS URL，调试用 |
| `GET /api/cctv/live/:channelNo/index.m3u8` | 稳定播放入口，前端正式使用 |
| `GET /api/cctv/live/:channelNo/segment/:seq?src=...` | 分片代理，播放器自动请求 |

---

## 6. hls.js 前端配置

正式前端只需要固定播放本地代理地址：

```javascript
import Hls from 'hls.js';

function playCctv(videoEl, channelNo) {
  const src = `/api/cctv/live/${channelNo}/index.m3u8`;

  const hls = new Hls({
    enableWorker: true,
    lowLatencyMode: false,
    liveSyncDurationCount: 6,
    liveMaxLatencyDurationCount: 18,
    maxBufferLength: 45,
    maxMaxBufferLength: 90,
    backBufferLength: 30,
    manifestLoadingTimeOut: 12000,
    manifestLoadingMaxRetry: 6,
    manifestLoadingRetryDelay: 800,
    levelLoadingTimeOut: 12000,
    levelLoadingMaxRetry: 8,
    levelLoadingRetryDelay: 800,
    fragLoadingTimeOut: 15000,
    fragLoadingMaxRetry: 12,
    fragLoadingRetryDelay: 800,
  });

  hls.on(Hls.Events.ERROR, (_, data) => {
    if (!data.fatal) return;

    if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
      hls.recoverMediaError();
      return;
    }

    // network fatal 才整体重载。不要对普通 bufferStalledError 重启。
    hls.destroy();
    setTimeout(() => playCctv(videoEl, channelNo), 1000);
  });

  hls.loadSource(src);
  hls.attachMedia(videoEl);
}
```

稳定优先配置说明：

- `lowLatencyMode=false`：不追求极低延迟，换取更稳定缓冲。
- `liveSyncDurationCount=6`：比实时慢若干个分片，减少 4G 抖动影响。
- `maxBufferLength=45`：允许更多缓冲。
- `fragLoadingMaxRetry=12`：分片失败时多重试，不轻易重启播放器。

---

## 7. 本地运行方法

### 7.1 启动 demo 服务

```bash
node stable-hls-player-server.js --channel 1 --port 3457
```

打开：

```text
http://localhost:3457/player?channel=1
```

### 7.2 健康检查

```bash
node -e "fetch('http://127.0.0.1:3457/api/health').then(r=>r.text()).then(console.log)"
```

正常返回：

```json
{
  "ok": true,
  "deviceSerial": "E48203280",
  "hasToken": true,
  "defaultChannel": 1
}
```

### 7.3 验证代理 m3u8

```bash
node -e "fetch('http://127.0.0.1:3457/api/live/1/index.m3u8').then(r=>r.text()).then(t=>console.log(t.split(/\r?\n/).slice(0,10).join('\n')))"
```

应看到本地分片地址：

```text
/api/live/1/segment/...
```

### 7.4 自动化稳定性测试

```bash
node stable-hls-smoke-test.js --channel 1 --seconds 90 --port 3457
```

判定标准：

- 大多数采样点 `paused=false`
- `readyState >= 2`
- `videoWidth > 0`
- 最终状态仍在播放
- `error=null`

---

## 8. chtong 集成建议

### 8.1 后端集成

在 chtong 后端增加一个 CCTV 模块：

```text
server/cctv/
  cctv-hls-proxy-core.js
  cctv-token-service.js
  cctv-routes.js
```

推荐接口：

```text
GET /api/cctv/health
GET /api/cctv/cameras
GET /api/cctv/live/:channelNo/index.m3u8
GET /api/cctv/live/:channelNo/segment/:seq
POST /api/cctv/token/refresh
```

### 8.2 token 管理

正式环境不要硬编码：

```text
EZVIZ_ACCESS_TOKEN=at.xxx
EZVIZ_DEVICE_SERIAL=E48203280
```

推荐 token 刷新流程：

```text
每天凌晨定时：
  自动登录 C-SMART
  进入 CCTV 页面
  网络监听提取 Ezviz accessToken
  写入安全存储 / 内存缓存 / 数据库

播放过程中：
  Ezviz API 返回 10001 / token error
  立即触发 token refresh
  更新 CctvHlsProxyCore.updateAccessToken(newToken)
```

本仓库已实现后台 token 刷新模块：

```text
csmart-ezviz-token-refresh-service.js
```

它负责：

- 从 `cctv-token-cache.json` 读取当前 token。
- 从 `v16c-stream-data/stream-capture-result.json`、`v17c-stream-urls.json` 等抓包/结果文件提取 token。
- 定时运行登录抓包命令刷新 token。
- token 失效时被 HLS proxy 调用，立即刷新并重试。
- 刷新后通过 `proxy.updateAccessToken(newToken)` 热更新，不重启播放器。

`stable-hls-player-server.js` 当前默认刷新命令：

```bash
node auto-login-v15-cctv.js --token-refresh-only
```

`auto-login-v15-cctv.js --token-refresh-only` 的行为：

```text
自动登录 C-SMART
进入 FFL 项目
进入 CCTV-5.0 页面
网络监听抓取 Ezviz accessToken / deviceSerial
保存 v16c-stream-data/stream-capture-result.json
立即退出
```

不会继续下载 CCTV 截图，也不会等待 120 秒。

也可以用环境变量覆盖刷新命令：

```bash
set CSMART_TOKEN_REFRESH_COMMAND=node auto-login-v15-cctv.js --token-refresh-only
node stable-hls-player-server.js --channel 1 --port 3457
```

生产建议：

```text
后台常驻 stable-hls-player-server.js
每 20 小时自动刷新一次 token
播放 API 遇到 token invalid 时立即刷新
刷新过程中已有分片继续播放，新 playlist 使用新 token
```

### 8.3 前端集成

chtong 前端播放器只需要：

```text
/api/cctv/live/{channelNo}/index.m3u8
```

不需要调用 Ezviz API，不需要保存真实流地址。

---

## 9. 调参指南

### 9.1 追求更稳

适合 4G 摄像头、网络波动大：

```javascript
lowLatencyMode: false
liveSyncDurationCount: 6
liveMaxLatencyDurationCount: 18
maxBufferLength: 45
maxMaxBufferLength: 90
fragLoadingMaxRetry: 12
```

效果：

- 延迟更高。
- 卡顿感更少。
- 更适合长期看监控。

### 9.2 追求更实时

适合网络稳定、只看短时实时画面：

```javascript
lowLatencyMode: true
liveSyncDurationCount: 2
liveMaxLatencyDurationCount: 6
maxBufferLength: 12
```

效果：

- 延迟更低。
- 对网络抖动更敏感。

### 9.3 后端上游租约

```javascript
upstreamLeaseMs: 18000
```

Ezviz m3u8 很短，一般 18 秒左右刷新一次上游 URL 比较安全。注意：这是后端刷新，不是前端重启。

---

## 10. 已知边界

这个代理方案能解决：

- Ezviz m3u8 短有效期导致的前端断流。
- 前端频繁重建 hls.js 导致的周期性闪断。
- token / 真实流地址暴露给前端的问题。
- 普通短时 `bufferStalledError` / `levelLoadError` 的恢复问题。

这个代理方案不能完全解决：

- 摄像头本身离线。
- 4G 套餐或运营商链路完全断流。
- Ezviz 服务端长时间返回 5xx。
- C-SMART / Ezviz token 长期过期且刷新失败。

针对不能完全解决的问题，建议：

- 使用标清 `quality=2`。
- 增加前端缓冲。
- 记录播放健康状态，自动告警。
- token 自动刷新失败时降级为截图模式。

---

## 11. 推荐落地顺序

1. 在 chtong 后端接入 `cctv-hls-proxy-core.js`。
2. 用环境变量配置 `EZVIZ_ACCESS_TOKEN` 和 `EZVIZ_DEVICE_SERIAL`。
3. 前端播放器改为播放 `/api/cctv/live/:channelNo/index.m3u8`。
4. 加入 C-SMART 自动登录刷新 token 服务。
5. 加入播放健康监控：播放时长、重连次数、错误类型、分片失败次数。
6. 上线前做 30 分钟、2 小时、8 小时稳定性测试。

---

## 12. 当前可用命令

启动优化后的 demo：

```bash
node stable-hls-player-server.js --channel 1 --port 3457
```

打开播放器：

```text
http://localhost:3457/player?channel=1
```

跑 90 秒测试：

```bash
node stable-hls-smoke-test.js --channel 1 --seconds 90 --port 3457
```

检查 token 缓存：

```bash
node csmart-ezviz-token-refresh-service.js
```

立即执行一次 token 刷新：

```bash
node csmart-ezviz-token-refresh-service.js --refresh-now
```

手动触发运行中服务刷新 token：

```bash
node -e "fetch('http://127.0.0.1:3457/api/token/refresh',{method:'POST'}).then(r=>r.text()).then(console.log)"
```

批量检查 11 个通道代理 m3u8：

```bash
node -e "const channels=[1,2,3,4,5,6,7,8,9,10,11];(async()=>{for(const ch of channels){const r=await fetch('http://127.0.0.1:3457/api/live/'+ch+'/index.m3u8');const t=await r.text();console.log(ch,r.status,t.includes('#EXTM3U'),t.includes('/api/live/'+ch+'/segment/'));}})()"
```

正式复用建议优先看：

```text
cctv-hls-proxy-core.js
```

---

## 13. 安全注意

当前测试环境中历史脚本包含明文账号、Ezviz token、VLM key。正式接入 chtong 时必须：

- 不把 token 写死到代码。
- 不把真实 m3u8 传给前端。
- `.env` 不提交仓库。
- token 刷新日志不要打印完整 token。
- 对 `/api/cctv/*` 增加 chtong 登录态和权限校验。

---

## 14. 一句话总结

稳定播放的关键不是让前端反复换 Ezviz m3u8，而是让前端永远播放一个本地稳定 HLS 地址，由后端代理层负责刷新短地址、重写播放列表和代理分片。
