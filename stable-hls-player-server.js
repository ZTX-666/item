/**
 * Stable HLS Player Test Server
 *
 * Purpose:
 *   - Fetch fresh Ezviz HLS URLs on demand.
 *   - Serve a hls.js test player with automatic recovery.
 *   - Verify whether one CCTV channel can play for a long time with URL renewal.
 *
 * Usage:
 *   node stable-hls-player-server.js --channel 1 --port 3456
 *
 * Optional env overrides:
 *   EZVIZ_ACCESS_TOKEN=at.xxx
 *   EZVIZ_DEVICE_SERIAL=E48203280
 */

const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');
const querystring = require('querystring');
const { URL } = require('url');
const { CsmartEzvizTokenRefreshService } = require('./csmart-ezviz-token-refresh-service');

const EZVIZ_API = 'isgpopen.ezvizlife.com';
const DEFAULT_PORT = 3456;
const DEFAULT_CHANNEL = 1;
const UPSTREAM_LEASE_MS = 18000;
const SEGMENT_DURATION_GUESS_MS = 2500;
const CSMART_GATEWAY = 'gateway4.c-smart.hk';
const CSMART_ORG_ID = process.env.CSMART_ORG_ID || '1778119371126';
const CSMART_CHANNEL_CACHE_FILE = path.join(__dirname, 'csmart-channel-list-latest.json');
const CSMART_CHANNEL_REFRESH_MS = Number(process.env.CSMART_CHANNEL_REFRESH_MS || 20 * 60 * 60 * 1000);

const args = process.argv.slice(2);
const getArg = (name, fallback) => {
  const idx = args.indexOf(`--${name}`);
  return idx >= 0 && args[idx + 1] ? args[idx + 1] : fallback;
};

const PORT = Number(getArg('port', process.env.PORT || DEFAULT_PORT));
const DEFAULT_PLAY_CHANNEL = Number(getArg('channel', process.env.CCTV_CHANNEL || DEFAULT_CHANNEL));
const hlsLeaseCache = new Map();
let csmartChannelCache = null;
let csmartChannelRefreshInFlight = null;
const tokenService = new CsmartEzvizTokenRefreshService({
  baseDir: __dirname,
  refreshCommand: process.env.CSMART_TOKEN_REFRESH_COMMAND || `"${process.execPath}" "${path.join(__dirname, 'auto-login-v15-cctv.js')}" --token-refresh-only`,
  onToken: (info) => {
    if (info && info.deviceSerial) {
      process.env.EZVIZ_DEVICE_SERIAL = info.deviceSerial;
    }
    if (info && info.accessToken) {
      process.env.EZVIZ_ACCESS_TOKEN = info.accessToken;
    }
    hlsLeaseCache.clear();
  },
});

function loadSavedCredentials() {
  const filePath = path.join(__dirname, 'v17c-stream-urls.json');
  try {
    const data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    return {
      accessToken: data.token,
      deviceSerial: data.deviceSerial,
    };
  } catch (_) {
    return {};
  }
}

function getCredentials() {
  const saved = loadSavedCredentials();
  const hot = tokenService.tokenInfo || {};
  return {
    accessToken: process.env.EZVIZ_ACCESS_TOKEN || hot.accessToken || saved.accessToken,
    deviceSerial: process.env.EZVIZ_DEVICE_SERIAL || hot.deviceSerial || saved.deviceSerial || 'E48203280',
  };
}

function readJsonIfExists(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return null;
  }
}

function getCaptureFiles() {
  return [
    path.join(__dirname, 'v16c-stream-data', 'stream-capture-result.json'),
    path.join(__dirname, 'v16-stream-capture', 'stream-capture-result.json'),
    path.join(__dirname, 'v16b-stream-intercept', 'stream-capture-result.json'),
  ];
}

function extractCsmartBearerFromCapture(capture) {
  const entries = [...(capture.playwireCaptured || []), ...(capture.jsIntercepted || [])];
  for (const entry of entries) {
    const url = String(entry.url || '');
    const body = String(entry.bodyPreview || entry.body || '');
    if (!url.includes('/oauth/oauth/token') && !body.includes('access_token')) continue;
    try {
      const parsed = JSON.parse(body);
      const token = parsed && parsed.data && parsed.data.access_token;
      if (token) return token;
    } catch (_) {
      const match = body.match(/"access_token"\s*:\s*"([0-9a-f-]{36})"/i);
      if (match) return match[1];
    }
  }
  return null;
}

function getLatestCsmartBearer() {
  for (const captureFile of getCaptureFiles()) {
    const capture = readJsonIfExists(captureFile);
    if (!capture) continue;
    const token = extractCsmartBearerFromCapture(capture);
    if (token) return token;
  }
  return null;
}

function requestText(options, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = options.protocol === 'http:' ? http : https;
    const req = client.request({
      ...options,
      timeout: timeoutMs,
    }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { raw += chunk; });
      res.on('end', () => resolve({ statusCode: res.statusCode, body: raw }));
    });
    req.on('timeout', () => req.destroy(new Error('request timeout')));
    req.on('error', reject);
    req.end();
  });
}

function normalizeCsmartChannelPayload(payload, source) {
  const list = payload && payload.data && Array.isArray(payload.data.list) ? payload.data.list : [];
  return {
    ok: payload && payload.code === 200,
    orgId: CSMART_ORG_ID,
    totalCount: payload && payload.data && payload.data.totalCount,
    channels: list.filter(item => item && item.status === 1 && item.deviceType === 1),
    raw: payload,
    source,
    updatedAt: new Date().toISOString(),
  };
}

function loadCachedCsmartChannels() {
  const cached = readJsonIfExists(CSMART_CHANNEL_CACHE_FILE);
  if (!cached) return null;
  const normalized = cached.channels ? cached : normalizeCsmartChannelPayload(cached, 'cache-legacy');
  csmartChannelCache = normalized;
  return normalized;
}

function saveCsmartChannels(payload, source) {
  const normalized = normalizeCsmartChannelPayload(payload, source);
  if (!normalized.channels.length) {
    throw new Error('C-SMART channel list is empty');
  }
  fs.writeFileSync(CSMART_CHANNEL_CACHE_FILE, JSON.stringify(normalized, null, 2));
  csmartChannelCache = normalized;
  return normalized;
}

async function fetchCsmartChannelsWithBearer(bearer) {
  if (!bearer) throw new Error('Missing C-SMART bearer token');
  const pathName = `/video/v5/channel/video/listPage?orgId=${encodeURIComponent(CSMART_ORG_ID)}&status=1&hidden=false&relatedIpc=true&pageNum=1&pageSize=11`;
  const response = await requestText({
    protocol: 'https:',
    hostname: CSMART_GATEWAY,
    port: 443,
    path: pathName,
    method: 'GET',
    headers: {
      Authorization: `Bearer ${bearer}`,
      Accept: 'application/json',
    },
  });
  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`C-SMART channel list HTTP ${response.statusCode}: ${response.body.slice(0, 200)}`);
  }
  const payload = JSON.parse(response.body);
  if (payload.code !== 200) {
    throw new Error(`C-SMART channel list failed: ${payload.code} ${payload.msg || ''}`.trim());
  }
  return payload;
}

async function refreshCsmartChannels(reason = 'manual', retried = false) {
  if (csmartChannelRefreshInFlight) return csmartChannelRefreshInFlight;
  csmartChannelRefreshInFlight = (async () => {
    try {
      let bearer = getLatestCsmartBearer();
      if (!bearer || retried) {
        await tokenService.refreshNow(`csmart channel list: ${reason}`);
        bearer = getLatestCsmartBearer();
      }
      try {
        return saveCsmartChannels(await fetchCsmartChannelsWithBearer(bearer), `gateway:${reason}`);
      } catch (err) {
        if (!retried && /401|unauthorized|Missing C-SMART bearer/i.test(err.message)) {
          await tokenService.refreshNow(`csmart bearer invalid: ${reason}`);
          bearer = getLatestCsmartBearer();
          return saveCsmartChannels(await fetchCsmartChannelsWithBearer(bearer), `gateway:${reason}:retry`);
        }
        throw err;
      }
    } finally {
      csmartChannelRefreshInFlight = null;
    }
  })();
  return csmartChannelRefreshInFlight;
}

async function getCsmartChannels({ refresh = false } = {}) {
  const cached = csmartChannelCache || loadCachedCsmartChannels();
  const stale = !cached || (Date.now() - Date.parse(cached.updatedAt || 0)) > CSMART_CHANNEL_REFRESH_MS;
  if (refresh || stale) {
    try {
      return await refreshCsmartChannels(refresh ? 'forced api' : 'stale cache');
    } catch (err) {
      if (cached) return { ...cached, refreshWarning: err.message };
      throw err;
    }
  }
  return cached;
}

function isTokenInvalidResult(result) {
  const code = String(result && result.code ? result.code : '');
  const msg = String(result && result.msg ? result.msg : '').toLowerCase();
  return ['10001', '10002', '10005'].includes(code) || (msg.includes('token') && (msg.includes('invalid') || msg.includes('expired') || msg.includes('过期') || msg.includes('失效')));
}

function postEzviz(apiPath, data) {
  return new Promise((resolve, reject) => {
    const body = querystring.stringify(data);
    const req = https.request({
      hostname: EZVIZ_API,
      port: 443,
      path: apiPath,
      method: 'POST',
      timeout: 15000,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Content-Length': Buffer.byteLength(body),
      },
    }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { raw += chunk; });
      res.on('end', () => {
        try {
          resolve(JSON.parse(raw));
        } catch (err) {
          reject(new Error(`Ezviz JSON parse failed: ${err.message}; body=${raw.slice(0, 200)}`));
        }
      });
    });

    req.on('timeout', () => req.destroy(new Error('Ezviz request timeout')));
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

async function getCameraList(retried = false) {
  const { accessToken, deviceSerial } = getCredentials();
  if (!accessToken) throw new Error('Missing EZVIZ_ACCESS_TOKEN or v17c-stream-urls.json token');

  const result = await postEzviz('/api/lapp/device/camera/list', {
    accessToken,
    deviceSerial,
  });

  if (result.code !== '200') {
    if (isTokenInvalidResult(result) && !retried) {
      await tokenService.refreshNow('camera/list token invalid');
      return getCameraList(true);
    }
    throw new Error(`camera/list failed: ${result.code} ${result.msg || ''}`.trim());
  }

  return {
    deviceSerial,
    cameras: (result.data || []).filter(cam => cam.status === 1 && cam.channelNo <= 64),
  };
}

async function getFreshHls(channelNo, retried = false) {
  const { accessToken, deviceSerial } = getCredentials();
  if (!accessToken) throw new Error('Missing EZVIZ_ACCESS_TOKEN or v17c-stream-urls.json token');

  const result = await postEzviz('/api/lapp/live/address/get', {
    accessToken,
    deviceSerial,
    channelNo,
    protocol: 2,
    quality: 2,
  });

  if (result.code !== '200') {
    if (isTokenInvalidResult(result) && !retried) {
      await tokenService.refreshNow(`live/address token invalid channel=${channelNo}`);
      return getFreshHls(channelNo, true);
    }
    throw new Error(`live/address/get failed: ${result.code} ${result.msg || ''}`.trim());
  }

  return {
    channelNo,
    deviceSerial,
    hlsUrl: result.data.url,
    expireTime: result.data.expireTime,
    fetchedAt: new Date().toISOString(),
  };
}

function fetchText(url, timeoutMs = 12000) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === 'http:' ? http : https;
    const req = client.get({
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'http:' ? 80 : 443),
      path: parsed.pathname + parsed.search,
      timeout: timeoutMs,
      headers: {
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Cache-Control': 'no-cache',
      },
    }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { raw += chunk; });
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(`GET ${url} failed with HTTP ${res.statusCode}: ${raw.slice(0, 160)}`));
          return;
        }
        resolve(raw);
      });
    });

    req.on('timeout', () => req.destroy(new Error(`GET ${url} timeout`)));
    req.on('error', reject);
  });
}

async function ensureHlsLease(channelNo, forceFresh = false) {
  const now = Date.now();
  const cached = hlsLeaseCache.get(channelNo);
  if (!forceFresh && cached && cached.refreshAfter > now) {
    return cached;
  }

  const fresh = await getFreshHls(channelNo);
  const lease = {
    ...fresh,
    refreshAfter: now + UPSTREAM_LEASE_MS,
    sequenceBase: Math.floor(now / SEGMENT_DURATION_GUESS_MS),
  };
  hlsLeaseCache.set(channelNo, lease);
  return lease;
}

function absolutizeUrl(line, baseUrl) {
  try {
    return new URL(line, baseUrl).toString();
  } catch (_) {
    return line;
  }
}

function rewritePlaylist(playlist, channelNo, upstreamUrl, sequenceBase) {
  const lines = playlist.split(/\r?\n/);
  const out = [];
  let segmentIndex = 0;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      out.push(line);
      continue;
    }

    if (trimmed.startsWith('#EXT-X-MEDIA-SEQUENCE:')) {
      out.push(`#EXT-X-MEDIA-SEQUENCE:${sequenceBase}`);
      continue;
    }

    if (trimmed.startsWith('#EXT-X-ALLOW-CACHE:')) {
      out.push('#EXT-X-ALLOW-CACHE:NO');
      continue;
    }

    if (trimmed.startsWith('#EXT-X-ENDLIST')) {
      continue;
    }

    if (trimmed.startsWith('#')) {
      out.push(line);
      continue;
    }

    const absolute = absolutizeUrl(trimmed, upstreamUrl);
    const proxied = `/api/live/${channelNo}/segment/${sequenceBase + segmentIndex}?src=${encodeURIComponent(absolute)}`;
    out.push(proxied);
    segmentIndex += 1;
  }

  if (!out.some(line => line.startsWith('#EXT-X-TARGETDURATION:'))) {
    out.splice(1, 0, '#EXT-X-TARGETDURATION:3');
  }

  if (!out.some(line => line.startsWith('#EXT-X-MEDIA-SEQUENCE:'))) {
    out.splice(1, 0, `#EXT-X-MEDIA-SEQUENCE:${sequenceBase}`);
  }

  return out.join('\n');
}

async function getProxiedPlaylist(channelNo) {
  let lease = await ensureHlsLease(channelNo);
  let playlist;

  try {
    playlist = await fetchText(lease.hlsUrl);
  } catch (_) {
    lease = await ensureHlsLease(channelNo, true);
    playlist = await fetchText(lease.hlsUrl);
  }

  if (!playlist.includes('#EXTM3U')) {
    lease = await ensureHlsLease(channelNo, true);
    playlist = await fetchText(lease.hlsUrl);
  }

  const sequenceBase = Math.floor(Date.now() / SEGMENT_DURATION_GUESS_MS);
  return {
    body: rewritePlaylist(playlist, channelNo, lease.hlsUrl, sequenceBase),
    lease,
  };
}

function proxySegment(res, src) {
  let parsed;
  try {
    parsed = new URL(src);
  } catch (_) {
    sendJson(res, 400, { error: 'Invalid segment URL' });
    return;
  }

  const client = parsed.protocol === 'http:' ? http : https;
  const upstream = client.get({
    hostname: parsed.hostname,
    port: parsed.port || (parsed.protocol === 'http:' ? 80 : 443),
    path: parsed.pathname + parsed.search,
    timeout: 15000,
    headers: {
      'User-Agent': 'Mozilla/5.0',
      'Accept': '*/*',
      'Cache-Control': 'no-cache',
    },
  }, (upRes) => {
    res.on('close', () => {
      if (!upRes.destroyed) upRes.destroy();
    });

    if (upRes.statusCode < 200 || upRes.statusCode >= 300) {
      res.writeHead(502, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
      });
      res.end(`Segment upstream HTTP ${upRes.statusCode}`);
      upRes.resume();
      return;
    }

    res.writeHead(200, {
      'Content-Type': upRes.headers['content-type'] || 'video/mp2t',
      'Cache-Control': 'no-store',
      'Access-Control-Allow-Origin': '*',
    });
    upRes.on('error', (err) => {
      if (!res.headersSent) {
        res.writeHead(502, {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-store',
          'Access-Control-Allow-Origin': '*',
        });
      }
      if (!res.writableEnded) res.end(err.message);
    });
    upRes.pipe(res);
  });

  upstream.on('timeout', () => upstream.destroy(new Error('Segment request timeout')));
  upstream.on('error', (err) => {
    if (!res.headersSent) {
      res.writeHead(502, {
        'Content-Type': 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
      });
    }
    if (!res.writableEnded) res.end(err.message);
  });
}

function sendM3u8(res, body) {
  res.writeHead(200, {
    'Content-Type': 'application/vnd.apple.mpegurl; charset=utf-8',
    'Cache-Control': 'no-store, no-cache, must-revalidate',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(body);
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload, null, 2);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'Access-Control-Allow-Origin': '*',
  });
  res.end(body);
}

function sendHtml(res, html) {
  res.writeHead(200, {
    'Content-Type': 'text/html; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(html);
}

function hlsPlayerHtml(channelNo) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>C-SMART Stable CCTV Player</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: Segoe UI, Arial, sans-serif; }
    header { padding: 16px 20px; background: #111827; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
    input, button { font: inherit; border-radius: 8px; border: 1px solid #334155; padding: 8px 10px; }
    input { width: 80px; background: #020617; color: #e2e8f0; }
    button { background: #2563eb; color: #fff; cursor: pointer; }
    main { padding: 20px; }
    video { width: min(100%, 1100px); background: #000; border-radius: 12px; box-shadow: 0 12px 40px rgba(0,0,0,.35); }
    pre { white-space: pre-wrap; background: #020617; border: 1px solid #1e293b; border-radius: 12px; padding: 12px; max-height: 240px; overflow: auto; }
    .ok { color: #86efac; } .warn { color: #fde047; } .err { color: #fca5a5; }
  </style>
</head>
<body>
  <header>
    <strong>C-SMART Stable CCTV Player</strong>
    <label>Channel <input id="channel" type="number" min="1" value="${channelNo}" /></label>
    <button id="play">Play / Refresh</button>
    <button id="stop">Stop</button>
    <span id="summary" class="warn">idle</span>
  </header>
  <main>
    <video id="video" controls muted autoplay playsinline></video>
    <h3>Runtime log</h3>
    <pre id="log"></pre>
  </main>

  <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
  <script>
    const video = document.getElementById('video');
    const channelInput = document.getElementById('channel');
    const logEl = document.getElementById('log');
    const summaryEl = document.getElementById('summary');

    let hls = null;
    let currentChannel = Number(channelInput.value);
    let reconnectTimer = null;
    let watchdogTimer = null;
    let lastTime = 0;
    let lastProgressAt = Date.now();
    let reconnectCount = 0;
    let playStartedAt = null;

    window.__cctvStats = {
      channel: currentChannel,
      reconnectCount: 0,
      lastReason: 'init',
      lastMessage: 'idle',
      lastError: '',
    };

    function log(message, level = 'info') {
      const line = '[' + new Date().toLocaleTimeString() + '] ' + message;
      console[level === 'error' ? 'error' : 'log'](line);
      logEl.textContent = line + '\\n' + logEl.textContent;
      summaryEl.textContent = message;
      summaryEl.className = level === 'error' ? 'err' : level === 'warn' ? 'warn' : 'ok';
      window.__cctvStats.lastMessage = message;
      if (level === 'error') window.__cctvStats.lastError = message;
    }

    function cleanupTimers() {
      clearTimeout(reconnectTimer);
      clearInterval(watchdogTimer);
      reconnectTimer = null;
      watchdogTimer = null;
    }

    function destroyHls() {
      if (hls) {
        try { hls.destroy(); } catch (_) {}
        hls = null;
      }
    }

    function startWatchdog() {
      clearInterval(watchdogTimer);
      lastTime = video.currentTime || 0;
      lastProgressAt = Date.now();
      watchdogTimer = setInterval(() => {
        const now = Date.now();
        const current = video.currentTime || 0;
        if (current > lastTime + 0.1) {
          lastProgressAt = now;
          lastTime = current;
          return;
        }
        if (!video.paused && now - lastProgressAt > 30000) {
          reconnect('watchdog: playback stalled');
        }
      }, 3000);
    }

    async function load(channelNo, reason = 'manual start') {
      cleanupTimers();
      destroyHls();
      currentChannel = channelNo;
      window.__cctvStats.channel = channelNo;
      window.__cctvStats.lastReason = reason;

      const streamUrl = '/api/live/' + channelNo + '/index.m3u8?t=' + Date.now();
      log('loading channel ' + channelNo + ' via proxy (' + reason + ')');

      if (Hls.isSupported()) {
        hls = new Hls({
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
          log('hls error: ' + data.type + ' / ' + data.details + ', fatal=' + data.fatal, data.fatal ? 'warn' : 'info');
          if (!data.fatal) return;
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            try {
              hls.recoverMediaError();
              log('recoverMediaError called');
            } catch (_) {
              reconnect('fatal media error');
            }
          } else {
            reconnect('fatal network error');
          }
        });

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          video.play().catch(err => log('autoplay blocked: ' + err.message, 'warn'));
        });

        hls.loadSource(streamUrl);
        hls.attachMedia(video);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = streamUrl;
        video.play().catch(err => log('native autoplay blocked: ' + err.message, 'warn'));
      } else {
        throw new Error('HLS is not supported in this browser');
      }

      if (!playStartedAt) playStartedAt = Date.now();
      reconnectCount += reason === 'manual start' ? 0 : 1;
      window.__cctvStats.reconnectCount = reconnectCount;
      startWatchdog();
    }

    function reconnect(reason) {
      if (reconnectTimer) return;
      log('reconnecting: ' + reason, 'warn');
      reconnectTimer = setTimeout(async () => {
        reconnectTimer = null;
        try {
          await load(currentChannel, reason);
        } catch (err) {
          log('reconnect failed: ' + err.message, 'error');
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            reconnect('retry after failure');
          }, 5000);
        }
      }, 1000);
    }

    document.getElementById('play').addEventListener('click', async () => {
      try {
        reconnectCount = 0;
        playStartedAt = null;
        await load(Number(channelInput.value), 'manual start');
      } catch (err) {
        log(err.message, 'error');
      }
    });

    document.getElementById('stop').addEventListener('click', () => {
      cleanupTimers();
      destroyHls();
      video.removeAttribute('src');
      video.load();
      log('stopped', 'warn');
    });

    video.addEventListener('playing', () => log('playing ' + video.videoWidth + 'x' + video.videoHeight));
    video.addEventListener('waiting', () => log('video waiting/buffering', 'warn'));
    video.addEventListener('error', () => reconnect('video element error'));

    setInterval(() => {
      if (!playStartedAt) return;
      const seconds = Math.round((Date.now() - playStartedAt) / 1000);
      const size = video.videoWidth && video.videoHeight ? video.videoWidth + 'x' + video.videoHeight : 'unknown';
      log('alive ' + seconds + 's, time=' + video.currentTime.toFixed(1) + ', size=' + size + ', reconnects=' + reconnectCount);
    }, 15000);

    load(currentChannel, 'auto start').catch(err => log(err.message, 'error'));
  </script>
</body>
</html>`;
}

function playerHtml(defaultChannelNo) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>C-SMART Stable CCTV Player</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; background: #05070d; color: #e5e7eb; font-family: Segoe UI, Arial, sans-serif; }
    header { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; padding: 12px 16px; background: #111827; border-bottom: 1px solid #1f2937; position: sticky; top: 0; z-index: 10; }
    header strong { margin-right: 8px; }
    button, select, input { font: inherit; border-radius: 8px; border: 1px solid #374151; padding: 7px 10px; background: #020617; color: #e5e7eb; }
    button { background: #2563eb; cursor: pointer; border-color: #1d4ed8; }
    button.secondary { background: #1f2937; border-color: #374151; }
    .status { color: #fde68a; font-size: 13px; }
    .grid { display: grid; gap: 8px; padding: 10px; height: calc(100vh - 58px); }
    .grid.layout-1 { grid-template-columns: 1fr; }
    .grid.layout-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.layout-9 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid.layout-11 { grid-template-columns: repeat(4, minmax(0, 1fr)); grid-auto-rows: minmax(190px, 1fr); }
    .tile { position: relative; min-height: 190px; background: #000; border: 1px solid #1f2937; border-radius: 10px; overflow: hidden; }
    .tile iframe { width: 100%; height: 100%; border: 0; display: block; background: #000; }
    .tile-title { position: absolute; left: 8px; top: 8px; z-index: 2; padding: 3px 6px; border-radius: 6px; background: rgba(0,0,0,.55); font-size: 12px; pointer-events: none; }
    .empty { display: grid; place-items: center; color: #94a3b8; height: 100%; font-size: 14px; }
    @media (max-width: 1000px) {
      .grid.layout-11, .grid.layout-9 { grid-template-columns: repeat(2, minmax(0, 1fr)); height: auto; }
      .grid.layout-4 { height: auto; }
    }
  </style>
</head>
<body>
  <header>
    <strong>C-SMART Stable CCTV Player</strong>
    <label>布局
      <select id="layout">
        <option value="1">1 路</option>
        <option value="4">4 路</option>
        <option value="9">9 路</option>
        <option value="11" selected>11 路</option>
      </select>
    </label>
    <label>单路 <input id="channel" type="number" min="1" max="32" value="${defaultChannelNo}" style="width:70px" /></label>
    <button id="reload">刷新播放</button>
    <button id="refreshToken" class="secondary">后台刷新 token/list</button>
    <a style="color:#93c5fd" href="/hls-player?channel=${defaultChannelNo}">旧 HLS 测试页</a>
    <span id="status" class="status">初始化中...</span>
  </header>
  <main id="grid" class="grid layout-11"></main>

  <script>
    const PLAYER_URL = 'https://custom.c-smart.hk/csmart-player/cctv-video-list/';
    const REFRESH_INTERVAL_MS = 55 * 60 * 1000;
    const grid = document.getElementById('grid');
    const layoutEl = document.getElementById('layout');
    const channelEl = document.getElementById('channel');
    const statusEl = document.getElementById('status');
    let channels = [];
    let currentLayout = 11;
    let refreshTimer = null;

    window.__cctvStats = { mode: 'csmart-iframe', ready: false, channels: 0, layout: currentLayout, lastRefreshAt: null, errors: [] };

    function setStatus(message) {
      statusEl.textContent = message;
      window.__cctvStats.lastMessage = message;
      console.log('[cctv]', message);
    }

    function visibleChannels() {
      if (currentLayout === 1) {
        const no = Number(channelEl.value || ${defaultChannelNo});
        return channels.filter(item => Number(item.number) === no).slice(0, 1);
      }
      return channels.slice(0, currentLayout);
    }

    function initIframe(iframe, item) {
      const listStr = JSON.stringify([item]);
      let initSent = false;
      const send = (reason) => {
        if (initSent || !iframe.contentWindow) return;
        initSent = true;
        iframe.contentWindow.postMessage({ type: 'iframeInit', listStr }, '*');
        console.log('[iframeInit]', item.number, item.cameraName, reason);
      };
      iframe.addEventListener('load', () => setTimeout(() => send('load'), 600));
      setTimeout(() => send('fallback'), 2500);
    }

    function render() {
      const list = visibleChannels();
      grid.className = 'grid layout-' + currentLayout;
      grid.innerHTML = '';
      if (!list.length) {
        grid.innerHTML = '<section class="tile"><div class="empty">没有找到可播放摄像头</div></section>';
        return;
      }
      for (const item of list) {
        const tile = document.createElement('section');
        tile.className = 'tile';
        const title = document.createElement('div');
        title.className = 'tile-title';
        title.textContent = '#' + item.number + ' ' + (item.cameraName || item.name || '');
        const iframe = document.createElement('iframe');
        iframe.allow = 'autoplay; fullscreen';
        iframe.src = PLAYER_URL + '?type=1&t=' + Date.now() + '&channel=' + encodeURIComponent(item.number);
        tile.appendChild(title);
        tile.appendChild(iframe);
        grid.appendChild(tile);
        initIframe(iframe, item);
      }
      window.__cctvStats.ready = true;
      window.__cctvStats.channels = list.length;
      window.__cctvStats.layout = currentLayout;
      setStatus('已加载 ' + list.length + ' 路，列表时间 ' + (window.__cctvStats.lastRefreshAt || 'unknown'));
    }

    async function loadChannels(forceRefresh = false) {
      const url = '/api/csmart/channels?' + (forceRefresh ? 'refresh=1&' : '') + 't=' + Date.now();
      setStatus(forceRefresh ? '后台刷新 C-SMART token/list...' : '读取摄像头列表...');
      const res = await fetch(url, { cache: 'no-store' });
      const data = await res.json();
      if (!res.ok || !data.channels) throw new Error(data.error || '读取摄像头列表失败');
      channels = data.channels.sort((a, b) => Number(a.number) - Number(b.number));
      window.__cctvStats.lastRefreshAt = data.updatedAt;
      if (data.refreshWarning) console.warn('[cctv refresh warning]', data.refreshWarning);
      render();
    }

    function scheduleRefresh() {
      clearInterval(refreshTimer);
      refreshTimer = setInterval(() => {
        loadChannels(true).catch(err => {
          window.__cctvStats.errors.push(err.message);
          setStatus('刷新失败，继续使用当前列表: ' + err.message);
        });
      }, REFRESH_INTERVAL_MS);
    }

    window.addEventListener('message', event => {
      if (event.data && event.data.type) console.log('[iframe message]', event.data);
    });

    layoutEl.addEventListener('change', () => {
      currentLayout = Number(layoutEl.value);
      render();
    });
    channelEl.addEventListener('change', render);
    document.getElementById('reload').addEventListener('click', () => render());
    document.getElementById('refreshToken').addEventListener('click', () => loadChannels(true).catch(err => setStatus(err.message)));

    loadChannels(false).then(scheduleRefresh).catch(err => {
      window.__cctvStats.errors.push(err.message);
      setStatus(err.message);
    });
  </script>
</body>
</html>`;
}

const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/' || url.pathname === '/player') {
      const channelNo = Number(url.searchParams.get('channel') || DEFAULT_PLAY_CHANNEL);
      sendHtml(res, playerHtml(channelNo));
      return;
    }

    if (url.pathname === '/hls-player') {
      const channelNo = Number(url.searchParams.get('channel') || DEFAULT_PLAY_CHANNEL);
      sendHtml(res, hlsPlayerHtml(channelNo));
      return;
    }

    if (url.pathname === '/api/health') {
      const creds = getCredentials();
      sendJson(res, 200, {
        ok: Boolean(creds.accessToken && creds.deviceSerial),
        deviceSerial: creds.deviceSerial,
        hasToken: Boolean(creds.accessToken),
        defaultChannel: DEFAULT_PLAY_CHANNEL,
        tokenSource: tokenService.tokenInfo && tokenService.tokenInfo.source,
        tokenUpdatedAt: tokenService.tokenInfo && tokenService.tokenInfo.updatedAt,
        tokenApproximateExpiresAt: tokenService.tokenInfo && tokenService.tokenInfo.approximateExpiresAt,
        csmartChannelCount: csmartChannelCache && csmartChannelCache.channels && csmartChannelCache.channels.length,
        csmartChannelUpdatedAt: csmartChannelCache && csmartChannelCache.updatedAt,
      });
      return;
    }

    if (url.pathname === '/api/token/refresh' && req.method === 'POST') {
      const refreshed = await tokenService.refreshNow('manual api');
      sendJson(res, 200, {
        ok: true,
        deviceSerial: refreshed.deviceSerial,
        updatedAt: refreshed.updatedAt,
        approximateExpiresAt: refreshed.approximateExpiresAt,
        source: refreshed.source,
      });
      return;
    }

    if (url.pathname === '/api/cameras') {
      sendJson(res, 200, await getCameraList());
      return;
    }

    if (url.pathname === '/api/csmart/channels') {
      const refresh = url.searchParams.get('refresh') === '1';
      sendJson(res, 200, await getCsmartChannels({ refresh }));
      return;
    }

    if (url.pathname === '/api/csmart/channels/refresh' && req.method === 'POST') {
      sendJson(res, 200, await refreshCsmartChannels('manual api'));
      return;
    }

    const playlistMatch = url.pathname.match(/^\/api\/live\/(\d+)\/index\.m3u8$/);
    if (playlistMatch) {
      const playlist = await getProxiedPlaylist(Number(playlistMatch[1]));
      sendM3u8(res, playlist.body);
      return;
    }

    const segmentMatch = url.pathname.match(/^\/api\/live\/(\d+)\/segment\/\d+$/);
    if (segmentMatch) {
      const src = url.searchParams.get('src');
      if (!src) {
        sendJson(res, 400, { error: 'Missing src' });
        return;
      }
      proxySegment(res, src);
      return;
    }

    const streamMatch = url.pathname.match(/^\/api\/stream\/(\d+)$/);
    if (streamMatch) {
      sendJson(res, 200, await getFreshHls(Number(streamMatch[1])));
      return;
    }

    sendJson(res, 404, { error: 'Not found' });
  } catch (err) {
    sendJson(res, 500, { error: err.message });
  }
});

server.on('clientError', (err, socket) => {
  try {
    socket.end('HTTP/1.1 400 Bad Request\r\n\r\n');
  } catch (_) {}
});

server.on('error', (err) => {
  console.error('Server error:', err);
});

process.on('uncaughtException', (err) => {
  console.error('Uncaught exception:', err);
});

process.on('unhandledRejection', (err) => {
  console.error('Unhandled rejection:', err);
});

async function startServer() {
  try {
    tokenService.loadInitialToken();
  } catch (err) {
    console.warn(`[token-refresh] initial token load warning: ${err.message}`);
  }
  tokenService.start();
  loadCachedCsmartChannels();
  refreshCsmartChannels('server start').catch((err) => {
    console.warn(`[csmart-channels] initial refresh warning: ${err.message}`);
  });

  server.listen(PORT, () => {
    console.log(`Stable CCTV iframe player: http://localhost:${PORT}/player`);
    console.log(`Legacy HLS test player:    http://localhost:${PORT}/hls-player?channel=${DEFAULT_PLAY_CHANNEL}`);
    console.log(`Health check:           http://localhost:${PORT}/api/health`);
    console.log(`Token refresh:          POST http://localhost:${PORT}/api/token/refresh`);
    console.log(`Ezviz cameras:          http://localhost:${PORT}/api/cameras`);
    console.log(`C-SMART CCTV list:      http://localhost:${PORT}/api/csmart/channels`);
  });
}

startServer().catch((err) => {
  console.error(err);
  process.exit(1);
});
