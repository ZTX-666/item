# C-SMART CCTV Gateway

Local gateway for C-SMART CCTV playback inside Chitung Guardian.

## What It Does

- Uses the C-SMART native iframe player at `https://custom.c-smart.hk/csmart-player/cctv-video-list/`.
- Sends each original C-SMART camera item through the `iframeInit` postMessage contract.
- Lets the hosted player and EZUIKit handle WebSocket playback internally.
- Keeps C-SMART bearer tokens and captured runtime files outside git.

## Run Locally

```bash
cd cctv-gateway
npm test
npm start
```

Open:

- Player: `http://127.0.0.1:3457/player`
- Health: `http://127.0.0.1:3457/api/health`

The Chitung frontend reads the gateway from:

```bash
VITE_CCTV_GATEWAY_URL=http://127.0.0.1:3457
```

## Channel Data

The gateway can load channels in two ways:

1. Set `CSMART_BEARER` in a local `.env` or shell environment, then call `/api/csmart/channels/refresh`.
2. Place a token-capture output under one of these ignored runtime folders:
   - `v16c-stream-data/stream-capture-result.json`
   - `v16-stream-capture/stream-capture-result.json`
   - `v16b-stream-intercept/stream-capture-result.json`

Successful refreshes are cached in `csmart-channel-list-latest.json`, which is ignored by git.

## Configuration

Copy `.env.example` to `.env` for local overrides.

```bash
CCTV_GATEWAY_HOST=127.0.0.1
CCTV_GATEWAY_PORT=3457
CSMART_ORG_ID=1778119371126
CSMART_GATEWAY=gateway4.c-smart.hk
CCTV_PLAYER_URL=https://custom.c-smart.hk/csmart-player/cctv-video-list/
CCTV_CHANNEL_CACHE_FILE=csmart-channel-list-latest.json
```

## Player Screenshot Capture

Guardian patrol can call the gateway as an image source:

```bash
http://127.0.0.1:3457/api/csmart/player-screenshot/2
```

Set `CCTV_PLAYER_SCREENSHOT_CMD` to a local screenshot command. The gateway passes these environment variables to the command:

```bash
CCTV_SCREENSHOT_URL=http://127.0.0.1:3457/player?channel=2&live=1&embedded=1
CCTV_SCREENSHOT_OUTPUT=/tmp/cctv-player-shot/channel.jpg
CCTV_SCREENSHOT_CHANNEL=2
```

The bundled Playwright-based command is:

```bash
npm install -D playwright
npx playwright install chromium
CCTV_PLAYER_SCREENSHOT_CMD="node scripts/capture-player-screenshot.mjs"
```

Do not commit real C-SMART accounts, passwords, bearer tokens, Ezviz tokens, or captured runtime files.
