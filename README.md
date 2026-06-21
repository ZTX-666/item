# C-SMART CCTV VLM Detection

This folder contains the stable C-SMART CCTV playback and VLM detection handoff package.

## Main entry points

- `playback/stable-hls-player-server.js` - main stable player service. Default page uses C-SMART iframe/EZUIKit WebSocket playback for 11 CCTV channels.
- `playback/csmart-cctv-iframe-player-core.js` - reusable core module for C-SMART bearer extraction, channel list fetching/caching, and iframe player HTML generation.
- `scripts/auto-login-v15-cctv.js` - C-SMART auto-login and CCTV network capture script.
- `scripts/captcha-opencv.py` - captcha helper used by the auto-login workflow.
- `vlm/cctv_vlm_pipeline_v2.py` - CCTV snapshot/VLM detection pipeline.
- `docs/C-SMART_CCTV_11路稳定播放_EZUIKit_WebSocket_交底文档.md` - primary handoff document. Read this first.

## Quick start

```powershell
npm install
node auto-login-v15-cctv.js --token-refresh-only
node stable-hls-player-server.js --port 3457
```

Open:

```text
http://localhost:3457/player
```

## Security note

Do not commit or share runtime token/cache/capture files such as `csmart-channel-list-latest.json`, `cctv-token-cache.json`, or `v16c-stream-data/stream-capture-result.json`.
