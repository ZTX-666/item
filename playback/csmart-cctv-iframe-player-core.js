/**
 * C-SMART 11-channel CCTV stable playback core.
 *
 * Stable path:
 *   C-SMART auto login -> C-SMART channel list -> C-SMART hosted iframe player
 *   -> EZUIKit -> /api/lapp/live/url/ezopen -> WSS stream.
 *
 * This module intentionally does not print full bearer/access tokens.
 */
const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');

const DEFAULT_CSMART_GATEWAY = 'gateway4.c-smart.hk';
const DEFAULT_CSMART_ORG_ID = '1778119371126';
const DEFAULT_PLAYER_URL = 'https://custom.c-smart.hk/csmart-player/cctv-video-list/';
const DEFAULT_CHANNEL_CACHE_FILE = 'csmart-channel-list-latest.json';

function maskSecret(value) {
  return String(value || '')
    .replace(/Bearer\s+[0-9a-f-]{36}/gi, 'Bearer <masked>')
    .replace(/at\.[A-Za-z0-9._-]+/g, 'at.<masked>')
    .replace(/dv\.[A-Za-z0-9._-]+/g, 'dv.<masked>')
    .replace(/checkToken=[^&\s"']+/g, 'checkToken=<masked>')
    .replace(/accessToken=[^&\s"']+/g, 'accessToken=<masked>');
}

function readJsonIfExists(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return null;
  }
}

function defaultCapturePaths(baseDir) {
  return [
    path.join(baseDir, 'v16c-stream-data', 'stream-capture-result.json'),
    path.join(baseDir, 'v16-stream-capture', 'stream-capture-result.json'),
    path.join(baseDir, 'v16b-stream-intercept', 'stream-capture-result.json'),
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

function getLatestCsmartBearer(options = {}) {
  const baseDir = options.baseDir || __dirname;
  const capturePaths = options.capturePaths || defaultCapturePaths(baseDir);
  for (const capturePath of capturePaths) {
    const capture = readJsonIfExists(capturePath);
    if (!capture) continue;
    const token = extractCsmartBearerFromCapture(capture);
    if (token) return token;
  }
  return null;
}

function requestText(options, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const client = options.protocol === 'http:' ? http : https;
    const req = client.request({ ...options, timeout: timeoutMs }, (res) => {
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

async function fetchCsmartChannelList(options = {}) {
  const bearer = options.bearer || getLatestCsmartBearer(options);
  if (!bearer) throw new Error('Missing C-SMART bearer token. Run auto-login-v15-cctv.js --token-refresh-only first.');

  const orgId = options.orgId || DEFAULT_CSMART_ORG_ID;
  const gateway = options.gateway || DEFAULT_CSMART_GATEWAY;
  const pageSize = options.pageSize || 11;
  const requestPath = `/video/v5/channel/video/listPage?orgId=${encodeURIComponent(orgId)}&status=1&hidden=false&relatedIpc=true&pageNum=1&pageSize=${pageSize}`;
  const response = await requestText({
    protocol: 'https:',
    hostname: gateway,
    port: 443,
    path: requestPath,
    method: 'GET',
    headers: {
      Authorization: `Bearer ${bearer}`,
      Accept: 'application/json',
    },
  }, options.timeoutMs || 15000);

  if (response.statusCode < 200 || response.statusCode >= 300) {
    throw new Error(`C-SMART channel list HTTP ${response.statusCode}: ${maskSecret(response.body.slice(0, 200))}`);
  }

  const payload = JSON.parse(response.body);
  if (payload.code !== 200) {
    throw new Error(`C-SMART channel list failed: ${payload.code} ${payload.msg || ''}`.trim());
  }
  return payload;
}

function normalizeCsmartChannelPayload(payload, source = 'unknown', orgId = DEFAULT_CSMART_ORG_ID) {
  const list = payload && payload.data && Array.isArray(payload.data.list) ? payload.data.list : [];
  return {
    ok: payload && payload.code === 200,
    orgId,
    totalCount: payload && payload.data && payload.data.totalCount,
    channels: list
      .filter(item => item && item.status === 1 && item.deviceType === 1)
      .sort((a, b) => Number(a.number) - Number(b.number)),
    raw: payload,
    source,
    updatedAt: new Date().toISOString(),
  };
}

function loadCachedChannels(baseDir = __dirname, cacheFile = DEFAULT_CHANNEL_CACHE_FILE) {
  const cachePath = path.isAbsolute(cacheFile) ? cacheFile : path.join(baseDir, cacheFile);
  const cached = readJsonIfExists(cachePath);
  if (!cached) return null;
  return cached.channels ? cached : normalizeCsmartChannelPayload(cached, 'cache-legacy');
}

function saveCachedChannels(payload, options = {}) {
  const baseDir = options.baseDir || __dirname;
  const cacheFile = options.cacheFile || DEFAULT_CHANNEL_CACHE_FILE;
  const cachePath = path.isAbsolute(cacheFile) ? cacheFile : path.join(baseDir, cacheFile);
  const normalized = normalizeCsmartChannelPayload(payload, options.source || 'gateway', options.orgId || DEFAULT_CSMART_ORG_ID);
  if (!normalized.channels.length) throw new Error('C-SMART channel list is empty');
  fs.writeFileSync(cachePath, JSON.stringify(normalized, null, 2));
  return normalized;
}

function createCsmartIframePlayerHtml(options = {}) {
  const defaultChannelNo = Number(options.defaultChannelNo || 1);
  const playerUrl = options.playerUrl || DEFAULT_PLAYER_URL;
  const refreshIntervalMs = Number(options.refreshIntervalMs || 55 * 60 * 1000);
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
    button, select, input { font: inherit; border-radius: 8px; border: 1px solid #374151; padding: 7px 10px; background: #020617; color: #e5e7eb; }
    button { background: #2563eb; cursor: pointer; border-color: #1d4ed8; }
    .status { color: #fde68a; font-size: 13px; }
    .grid { display: grid; gap: 8px; padding: 10px; height: calc(100vh - 58px); }
    .grid.layout-1 { grid-template-columns: 1fr; }
    .grid.layout-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .grid.layout-9 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .grid.layout-11 { grid-template-columns: repeat(4, minmax(0, 1fr)); grid-auto-rows: minmax(190px, 1fr); }
    .tile { position: relative; min-height: 190px; background: #000; border: 1px solid #1f2937; border-radius: 10px; overflow: hidden; }
    .tile iframe { width: 100%; height: 100%; border: 0; display: block; background: #000; }
    .tile-title { position: absolute; left: 8px; top: 8px; z-index: 2; padding: 3px 6px; border-radius: 6px; background: rgba(0,0,0,.55); font-size: 12px; pointer-events: none; }
  </style>
</head>
<body>
  <header>
    <strong>C-SMART Stable CCTV Player</strong>
    <label>布局 <select id="layout"><option value="1">1 路</option><option value="4">4 路</option><option value="9">9 路</option><option value="11" selected>11 路</option></select></label>
    <label>单路 <input id="channel" type="number" min="1" max="32" value="${defaultChannelNo}" style="width:70px" /></label>
    <button id="reload">刷新播放</button>
    <button id="refreshToken">后台刷新 token/list</button>
    <span id="status" class="status">初始化中...</span>
  </header>
  <main id="grid" class="grid layout-11"></main>
  <script>
    const PLAYER_URL = ${JSON.stringify(playerUrl)};
    const REFRESH_INTERVAL_MS = ${refreshIntervalMs};
    const grid = document.getElementById('grid');
    const layoutEl = document.getElementById('layout');
    const channelEl = document.getElementById('channel');
    const statusEl = document.getElementById('status');
    let channels = [];
    let currentLayout = 11;
    window.__cctvStats = { mode: 'csmart-iframe', ready: false, channels: 0, layout: currentLayout, errors: [] };

    function setStatus(message) { statusEl.textContent = message; window.__cctvStats.lastMessage = message; console.log('[cctv]', message); }
    function visibleChannels() {
      if (currentLayout === 1) return channels.filter(item => Number(item.number) === Number(channelEl.value || ${defaultChannelNo})).slice(0, 1);
      return channels.slice(0, currentLayout);
    }
    function initIframe(iframe, item) {
      const listStr = JSON.stringify([item]);
      let initSent = false;
      const send = reason => {
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
      for (const item of list) {
        const tile = document.createElement('section');
        tile.className = 'tile';
        tile.innerHTML = '<div class="tile-title">#' + item.number + ' ' + (item.cameraName || item.name || '') + '</div>';
        const iframe = document.createElement('iframe');
        iframe.allow = 'autoplay; fullscreen';
        iframe.src = PLAYER_URL + '?type=1&t=' + Date.now() + '&channel=' + encodeURIComponent(item.number);
        tile.appendChild(iframe);
        grid.appendChild(tile);
        initIframe(iframe, item);
      }
      window.__cctvStats.ready = true;
      window.__cctvStats.channels = list.length;
      setStatus('已加载 ' + list.length + ' 路');
    }
    async function loadChannels(forceRefresh = false) {
      const res = await fetch('/api/csmart/channels?' + (forceRefresh ? 'refresh=1&' : '') + 't=' + Date.now(), { cache: 'no-store' });
      const data = await res.json();
      if (!res.ok || !data.channels) throw new Error(data.error || '读取摄像头列表失败');
      channels = data.channels.sort((a, b) => Number(a.number) - Number(b.number));
      render();
    }
    layoutEl.addEventListener('change', () => { currentLayout = Number(layoutEl.value); render(); });
    channelEl.addEventListener('change', render);
    document.getElementById('reload').addEventListener('click', render);
    document.getElementById('refreshToken').addEventListener('click', () => loadChannels(true).catch(err => setStatus(err.message)));
    setInterval(() => loadChannels(true).catch(err => { window.__cctvStats.errors.push(err.message); setStatus('刷新失败: ' + err.message); }), REFRESH_INTERVAL_MS);
    loadChannels(false).catch(err => { window.__cctvStats.errors.push(err.message); setStatus(err.message); });
  </script>
</body>
</html>`;
}

module.exports = {
  DEFAULT_CSMART_GATEWAY,
  DEFAULT_CSMART_ORG_ID,
  DEFAULT_PLAYER_URL,
  DEFAULT_CHANNEL_CACHE_FILE,
  maskSecret,
  readJsonIfExists,
  defaultCapturePaths,
  extractCsmartBearerFromCapture,
  getLatestCsmartBearer,
  fetchCsmartChannelList,
  normalizeCsmartChannelPayload,
  loadCachedChannels,
  saveCachedChannels,
  createCsmartIframePlayerHtml,
};
