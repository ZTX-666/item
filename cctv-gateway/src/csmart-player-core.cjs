const fs = require('node:fs');
const http = require('node:http');
const https = require('node:https');
const path = require('node:path');

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
  const entries = [...(capture?.playwireCaptured || []), ...(capture?.jsIntercepted || [])];
  for (const entry of entries) {
    const url = String(entry.url || '');
    const body = String(entry.bodyPreview || entry.body || '');
    if (!url.includes('/oauth/oauth/token') && !body.includes('access_token')) continue;

    try {
      const parsed = JSON.parse(body);
      const token = parsed?.data?.access_token;
      if (token) return token;
    } catch (_) {
      const match = body.match(/"access_token"\s*:\s*"([0-9a-f-]{36})"/i);
      if (match) return match[1];
    }
  }
  return null;
}

function getLatestCsmartBearer(options = {}) {
  const baseDir = options.baseDir || process.cwd();
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
      res.on('data', (chunk) => { raw += chunk; });
      res.on('end', () => resolve({ statusCode: res.statusCode, body: raw }));
    });
    req.on('timeout', () => req.destroy(new Error('request timeout')));
    req.on('error', reject);
    req.end();
  });
}

async function fetchCsmartChannelList(options = {}) {
  const bearer = options.bearer || getLatestCsmartBearer(options);
  if (!bearer) {
    throw new Error('Missing C-SMART bearer token. Run token capture first or provide CSMART_BEARER.');
  }

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
  const list = Array.isArray(payload?.data?.list) ? payload.data.list : [];
  return {
    ok: payload?.code === 200,
    orgId,
    totalCount: payload?.data?.totalCount,
    channels: list
      .filter((item) => item && item.status === 1 && item.deviceType === 1)
      .sort((a, b) => Number(a.number) - Number(b.number)),
    raw: payload,
    source,
    updatedAt: new Date().toISOString(),
  };
}

function resolveCachePath(baseDir, cacheFile = DEFAULT_CHANNEL_CACHE_FILE) {
  return path.isAbsolute(cacheFile) ? cacheFile : path.join(baseDir, cacheFile);
}

function loadCachedChannels(baseDir = process.cwd(), cacheFile = DEFAULT_CHANNEL_CACHE_FILE) {
  const cached = readJsonIfExists(resolveCachePath(baseDir, cacheFile));
  if (!cached) return null;
  return cached.channels ? cached : normalizeCsmartChannelPayload(cached, 'cache-legacy');
}

function saveCachedChannels(payload, options = {}) {
  const baseDir = options.baseDir || process.cwd();
  const cacheFile = options.cacheFile || DEFAULT_CHANNEL_CACHE_FILE;
  const normalized = normalizeCsmartChannelPayload(payload, options.source || 'gateway', options.orgId || DEFAULT_CSMART_ORG_ID);
  if (!normalized.channels.length) throw new Error('C-SMART channel list is empty');
  fs.writeFileSync(resolveCachePath(baseDir, cacheFile), JSON.stringify(normalized, null, 2));
  return normalized;
}

function csmartChannelList(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.channels)) return payload.channels;
  if (Array.isArray(payload?.data?.list)) return payload.data.list;
  return [];
}

function findCsmartChannel(payload, identifier) {
  const needle = String(identifier || '').trim();
  if (!needle) return null;
  const channels = csmartChannelList(payload);
  return channels.find((channel) => {
    const number = String(channel?.number || '').trim();
    const id = String(channel?.id || '').trim();
    const name = String(channel?.cameraName || channel?.name || '').trim();
    return number === needle || id === needle || name === needle;
  }) || null;
}

function getCsmartChannelSnapshotUrl(channel = {}) {
  return String(
    channel.screenshot
    || channel.snapshot
    || channel.snapshot_url
    || channel.snapshotUrl
    || channel.captureUrl
    || '',
  );
}

function createCsmartIframePlayerHtml(options = {}) {
  const defaultChannelNo = Number(options.defaultChannelNo || 1);
  const playerUrl = options.playerUrl || DEFAULT_PLAYER_URL;
  const gatewayBaseUrl = String(options.gatewayBaseUrl || '').replace(/\/$/, '');
  const apiPrefix = gatewayBaseUrl || '';
  const refreshIntervalMs = Number(options.refreshIntervalMs || 55 * 60 * 1000);
  const hasBearer = Boolean(options.hasBearer);

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>C-SMART CCTV</title>
  <style>
    * { box-sizing: border-box; }
    body { height: 100vh; margin: 0; min-height: 100vh; overflow: auto; background: #0b0d0f; color: #e7ecef; font-family: Arial, "Microsoft YaHei", sans-serif; }
    body.is-embedded { overflow: hidden; }
    body.is-embedded header { display: none; }
    header { align-items: center; background: #14181c; border-bottom: 1px solid #2b3238; display: flex; flex-wrap: wrap; gap: 10px; padding: 12px 16px; }
    strong { margin-right: 4px; }
    button, select, input { background: #0f1418; border: 1px solid #3d464f; border-radius: 6px; color: #e7ecef; font: inherit; padding: 7px 10px; }
    button { background: #0f766e; border-color: #0d9488; cursor: pointer; }
    button:hover { background: #0d9488; }
    .status { color: #facc15; font-size: 13px; }
    .meeting-stage { --thumbnail-columns: 5; --thumbnail-rows: 3; --thumbnail-count: 0; display: grid; gap: 8px; grid-template-columns: repeat(5, minmax(0, 1fr)); grid-template-rows: auto auto auto; height: auto; margin: 0 auto; min-height: 0; padding: 8px; width: 100%; }
    body.is-embedded .meeting-stage { grid-template-columns: repeat(5, minmax(0, 1fr)); grid-template-rows: minmax(0, 1fr) minmax(0, 5fr) minmax(0, 1fr); height: 100vh; padding: 8px; width: 100%; }
    .meeting-stage.layout-1 { grid-template-columns: 1fr; grid-template-rows: 1fr; }
    .meeting-stage.layout-1 .thumbnail-wall { display: none; }
    .tile { background: #000; border: 1px solid #2b3238; border-radius: 8px; min-height: 0; overflow: hidden; position: relative; }
    .main-tile { align-self: center; aspect-ratio: 5 / 3; box-shadow: 0 18px 45px rgba(0,0,0,.38); grid-column: 1 / 6; grid-row: 2; height: auto; justify-self: center; max-height: 100%; max-width: 100%; outline: 1px solid rgba(45,212,191,.28); width: 100%; }
    body.is-embedded .main-tile { aspect-ratio: auto; box-shadow: none; grid-column: 1 / 6; grid-row: 2; height: 100%; justify-self: stretch; width: 100%; }
    .meeting-stage.layout-1 .main-tile { grid-column: 1; grid-row: 1; }
    .main-tile.is-drop-target { border-color: #2dd4bf; outline: 2px solid rgba(45,212,191,.82); }
    .tile iframe, .tile-media { background: #000; border: 0; display: block; height: 100%; width: 100%; }
    .tile-media { object-fit: contain; }
    .tile-placeholder { color: #94a3b8; display: grid; font-size: 13px; height: 100%; place-items: center; text-align: center; }
    .tile-title { background: rgba(0,0,0,.62); border-radius: 6px; font-size: 12px; left: 8px; line-height: 1.3; max-width: calc(100% - 16px); overflow: hidden; padding: 4px 7px; pointer-events: none; position: absolute; text-overflow: ellipsis; top: 8px; white-space: nowrap; z-index: 2; }
    .thumbnail-wall { display: contents; }
    body.is-embedded .thumbnail-wall { display: contents; }
    .thumbnail-tile { aspect-ratio: 5 / 3; border-color: #2f383f; cursor: grab; min-height: 0; opacity: .86; transition: border-color .15s ease, opacity .15s ease, transform .15s ease; }
    body.is-embedded .thumbnail-tile { aspect-ratio: auto; height: 100%; width: 100%; }
    .thumbnail-tile:nth-child(1) { grid-column: 1; grid-row: 1; }
    .thumbnail-tile:nth-child(2) { grid-column: 2; grid-row: 1; }
    .thumbnail-tile:nth-child(3) { grid-column: 3; grid-row: 1; }
    .thumbnail-tile:nth-child(4) { grid-column: 4; grid-row: 1; }
    .thumbnail-tile:nth-child(5) { grid-column: 5; grid-row: 1; }
    .thumbnail-tile:nth-child(6) { grid-column: 1; grid-row: 3; }
    .thumbnail-tile:nth-child(7) { grid-column: 2; grid-row: 3; }
    .thumbnail-tile:nth-child(8) { grid-column: 3; grid-row: 3; }
    .thumbnail-tile:nth-child(9) { grid-column: 4; grid-row: 3; }
    .thumbnail-tile:nth-child(10) { grid-column: 5; grid-row: 3; }
    .thumbnail-tile .tile-title { font-size: 11px; padding: 3px 6px; top: 6px; left: 6px; max-width: calc(100% - 12px); }
    .thumbnail-tile iframe { pointer-events: none; }
    .thumbnail-tile:hover, .thumbnail-tile.is-active { border-color: #2dd4bf; opacity: 1; }
    .thumbnail-tile.is-active { box-shadow: inset 0 0 0 1px rgba(45,212,191,.65); }
    .thumbnail-tile.is-dragging { opacity: .45; transform: scale(.98); }
    .empty { color: #94a3b8; display: grid; height: 100%; place-items: center; }
    @media (max-width: 900px) {
      body { overflow: auto; }
      .meeting-stage { grid-template-columns: repeat(3, minmax(0, 1fr)); grid-template-rows: minmax(210px, 2fr) repeat(4, minmax(100px, 1fr)); min-height: calc(100vh - 58px); overflow: visible; }
      body.is-embedded .meeting-stage { grid-template-columns: repeat(5, minmax(0, 1fr)); grid-template-rows: minmax(0, 1fr) minmax(0, 5fr) minmax(0, 1fr); min-height: 100vh; }
      body.is-embedded .main-tile { grid-column: 1 / 6; grid-row: 2; }
      .main-tile { grid-column: 1 / 4; grid-row: 1; }
      .thumbnail-tile:nth-child(n) { grid-column: auto; grid-row: auto; }
    }
  </style>
  <script src="https://cdn.jsdelivr.net/npm/flv.js@1.6.2/dist/flv.min.js"><\/script>
</head>
<body>
  <header>
    <strong>C-SMART CCTV</strong>
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
    <button id="refresh">刷新通道</button>
    <span id="status" class="status">初始化中...</span>
  </header>
  <main id="stage" class="meeting-stage layout-11" aria-live="polite">
    <section id="mainTile" class="main-tile tile"><div class="empty">初始化中...</div></section>
    <aside id="thumbnailWall" class="thumbnail-wall" aria-label="全部摄像头缩略画面"></aside>
  </main>
  <script>
    const PLAYER_URL = ${JSON.stringify(playerUrl)};
    const API_PREFIX = ${JSON.stringify(apiPrefix)};
    const REFRESH_INTERVAL_MS = ${refreshIntervalMs};
    const HAS_BEARER = ${hasBearer ? 'true' : 'false'};
    const pageParams = new URLSearchParams(window.location.search);
    const embeddedMode = pageParams.get('embedded') === '1';
    const liveMode = pageParams.get('live') === '1';
    const stage = document.getElementById('stage');
    const mainTile = document.getElementById('mainTile');
    const thumbnailWall = document.getElementById('thumbnailWall');
    const layoutEl = document.getElementById('layout');
    const channelEl = document.getElementById('channel');
    const statusEl = document.getElementById('status');
    let channels = [];
    let currentLayout = 11;
    let selectedChannelNumber = ${defaultChannelNo};
    const activePlayers = new Set();

    function disposePlayers() {
      for (const player of activePlayers) {
        try {
          if (player && typeof player.destroy === 'function') player.destroy();
        } catch (_) {}
      }
      activePlayers.clear();
    }

    document.body.classList.toggle('is-embedded', embeddedMode);
    window.__cctvStats = { mode: 'csmart-iframe', ready: false, channels: 0, layout: currentLayout, activeChannel: selectedChannelNumber, errors: [], playback: 'unknown' };

    function setStatus(message) {
      statusEl.textContent = message;
      window.__cctvStats.lastMessage = message;
      console.log('[cctv]', message);
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (ch) => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;',
      })[ch]);
    }

    function showError(message) {
      setStatus(message);
      window.__cctvStats.ready = false;
      window.__cctvStats.errors.push(message);
      stage.className = 'meeting-stage layout-1';
      mainTile.innerHTML = '<div class="empty">通道加载失败：' + escapeHtml(message) + '</div>';
      thumbnailWall.innerHTML = '';
    }

    function channelLabel(item) {
      return '#' + item.number + ' ' + (item.cameraName || item.name || '');
    }

    function findChannel(channelNumber) {
      const no = Number(channelNumber);
      return channels.find((item) => Number(item.number) === no) || null;
    }

    function ensureSelectedChannel() {
      if (findChannel(selectedChannelNumber)) return;
      const inputChannel = findChannel(channelEl.value);
      selectedChannelNumber = inputChannel ? Number(inputChannel.number) : Number(channels[0]?.number || ${defaultChannelNo});
      channelEl.value = selectedChannelNumber;
    }

    function visibleChannels() {
      if (!channels.length) return [];
      ensureSelectedChannel();
      if (currentLayout === 1) {
        return findChannel(selectedChannelNumber) ? [findChannel(selectedChannelNumber)] : [];
      }
      const selected = findChannel(selectedChannelNumber);
      const list = channels.slice(0, currentLayout);
      if (selected && !list.some((item) => Number(item.number) === Number(selected.number))) {
        return [selected, ...channels.filter((item) => Number(item.number) !== Number(selected.number)).slice(0, currentLayout - 1)];
      }
      return list;
    }

    function playerSrc(item) {
      return PLAYER_URL + '?type=1&t=' + Date.now() + '&channel=' + encodeURIComponent(item.number);
    }

    function snapshotSrc(item) {
      return item.screenshot || item.snapshot || item.snapshot_url || item.snapshotUrl || item.captureUrl || '';
    }

    function flvSrc(item) {
      return String(item.flv || item.flvUrl || item.flv_url || '').trim();
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

    function createFlvPlayer(item, options = {}) {
      const video = document.createElement('video');
      video.className = 'tile-media';
      video.muted = true;
      video.autoplay = true;
      video.playsInline = true;
      video.setAttribute('playsinline', 'true');
      const src = flvSrc(item);
      if (!src) {
        if (options.fallbackToSnapshot) {
          return createSnapshotPoller(item, options.snapshotIntervalMs || 5000);
        }
        const placeholder = document.createElement('div');
        placeholder.className = 'tile-placeholder';
        placeholder.textContent = '暂无 FLV 地址';
        return placeholder;
      }
      const fallbackToSnapshot = () => {
        if (!options.fallbackToSnapshot) return;
        window.__cctvStats.playback = 'snapshot-poll';
        video.replaceWith(createSnapshotPoller(item, options.snapshotIntervalMs || 5000));
      };
      if (typeof flvjs !== 'undefined' && flvjs.isSupported()) {
        const player = flvjs.createPlayer({ type: 'flv', url: src, isLive: true, hasAudio: false }, { enableWorker: false, lazyLoad: false, stashInitialSize: 128 });
        player.attachMediaElement(video);
        player.on(flvjs.Events.ERROR, () => fallbackToSnapshot());
        player.load();
        player.play().catch(() => fallbackToSnapshot());
        activePlayers.add(player);
        video._flvPlayer = player;
        return video;
      }
      video.src = src;
      video.addEventListener('error', () => {
        if (options.fallbackToSnapshot) {
          fallbackToSnapshot();
          return;
        }
        video.replaceWith(Object.assign(document.createElement('div'), {
          className: 'tile-placeholder',
          textContent: 'FLV 播放失败',
        }));
      });
      return video;
    }

    function createSnapshotPoller(item, intervalMs) {
      const image = document.createElement('img');
      image.className = 'tile-media';
      image.alt = channelLabel(item);
      image.loading = 'eager';
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      const refresh = () => {
        image.src = API_PREFIX + '/api/csmart/snapshot/' + encodeURIComponent(item.number) + '?t=' + Date.now();
      };
      refresh();
      const timer = setInterval(refresh, intervalMs || 5000);
      image._snapshotTimer = timer;
      activePlayers.add({ destroy: () => clearInterval(timer) });
      image.addEventListener('error', () => {
        image.alt = '截图加载失败';
      });
      return image;
    }

    function createLiveMedia(item, options = {}) {
      const preferSnapshot = Boolean(options.preferSnapshot);
      const src = flvSrc(item);
      if (!HAS_BEARER) {
        window.__cctvStats.playback = 'snapshot-poll';
        return createSnapshotPoller(item, options.snapshotIntervalMs || 5000);
      }
      if (!preferSnapshot && src) {
        window.__cctvStats.playback = 'flv';
        return createFlvPlayer(item, {
          fallbackToSnapshot: true,
          snapshotIntervalMs: options.snapshotIntervalMs || 5000,
        });
      }
      if (HAS_BEARER) {
        window.__cctvStats.playback = 'csmart-iframe';
        return createIframe(item);
      }
      window.__cctvStats.playback = 'snapshot-poll';
      return createSnapshotPoller(item, options.snapshotIntervalMs || 5000);
    }

    function createIframe(item) {
      const iframe = document.createElement('iframe');
      iframe.allow = 'autoplay; fullscreen';
      iframe.scrolling = 'no';
      iframe.src = playerSrc(item);
      initIframe(iframe, item);
      return iframe;
    }

    function createSnapshotImage(item) {
      const src = snapshotSrc(item);
      if (!src) {
        const placeholder = document.createElement('div');
        placeholder.className = 'tile-placeholder';
        placeholder.textContent = '暂无截图';
        return placeholder;
      }
      const image = document.createElement('img');
      image.className = 'tile-media';
      image.alt = channelLabel(item);
      image.loading = 'eager';
      image.decoding = 'async';
      image.referrerPolicy = 'no-referrer';
      image.src = src;
      image.addEventListener('error', () => {
        image.replaceWith(Object.assign(document.createElement('div'), {
          className: 'tile-placeholder',
          textContent: '截图加载失败',
        }));
      });
      return image;
    }

    function renderMainTile(item) {
      mainTile.className = 'main-tile tile';
      mainTile.innerHTML = '';
      mainTile.setAttribute('data-channel-number', String(item.number));
      const title = document.createElement('div');
      title.className = 'tile-title';
      title.textContent = '主画面 ' + channelLabel(item);
      mainTile.appendChild(title);
      if (liveMode) {
        mainTile.appendChild(createLiveMedia(item, { preferSnapshot: false, snapshotIntervalMs: 5000 }));
      } else {
        mainTile.appendChild(createSnapshotImage(item));
      }
    }

    function renderThumbnail(item, active) {
      const thumbnail = document.createElement('section');
      thumbnail.className = 'thumbnail-tile tile' + (active ? ' is-active' : '');
      thumbnail.setAttribute('data-channel-number', String(item.number));
      thumbnail.setAttribute('aria-label', '切换到 ' + channelLabel(item));
      thumbnail.setAttribute('aria-pressed', active ? 'true' : 'false');
      thumbnail.setAttribute('role', 'button');
      thumbnail.tabIndex = 0;
      thumbnail.draggable = true;

      const title = document.createElement('div');
      title.className = 'tile-title';
      title.textContent = channelLabel(item);
      thumbnail.appendChild(title);
      if (liveMode) {
        thumbnail.appendChild(createLiveMedia(item, { preferSnapshot: true, snapshotIntervalMs: 8000 }));
      } else {
        thumbnail.appendChild(createSnapshotImage(item));
      }

      thumbnail.addEventListener('click', () => switchMainChannel(item.number));
      thumbnail.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          switchMainChannel(item.number);
        }
      });
      thumbnail.addEventListener('dragstart', (event) => {
        thumbnail.classList.add('is-dragging');
        if (event.dataTransfer) {
          event.dataTransfer.effectAllowed = 'move';
          event.dataTransfer.setData('text/plain', String(item.number));
        }
      });
      thumbnail.addEventListener('dragend', () => thumbnail.classList.remove('is-dragging'));
      return thumbnail;
    }

    function thumbnailGridColumns(total) {
      if (total <= 1) return 1;
      if (total <= 4) return total;
      if (total <= 8) return 4;
      return 6;
    }

    function renderThumbnailWall(list) {
      const thumbnails = list.filter((item) => Number(item.number) !== selectedChannelNumber);
      const columns = thumbnailGridColumns(thumbnails.length);
      const rows = Math.max(1, Math.ceil(thumbnails.length / columns));
      stage.style.setProperty('--thumbnail-count', String(thumbnails.length));
      stage.style.setProperty('--thumbnail-columns', String(columns));
      stage.style.setProperty('--thumbnail-rows', String(rows));
      thumbnailWall.innerHTML = '';
      for (const item of thumbnails) {
        thumbnailWall.appendChild(renderThumbnail(item, Number(item.number) === selectedChannelNumber));
      }
    }

    function render() {
      disposePlayers();
      const list = visibleChannels();
      stage.className = 'meeting-stage layout-' + currentLayout;
      thumbnailWall.innerHTML = '';
      if (!list.length) {
        mainTile.innerHTML = '<div class="empty">没有可播放通道。请先刷新 C-SMART token/list。</div>';
        return;
      }
      const active = findChannel(selectedChannelNumber) || list[0];
      selectedChannelNumber = Number(active.number);
      channelEl.value = selectedChannelNumber;
      renderMainTile(active);
      renderThumbnailWall(list);
      window.__cctvStats.ready = true;
      window.__cctvStats.channels = list.length;
      window.__cctvStats.layout = currentLayout;
      window.__cctvStats.activeChannel = selectedChannelNumber;
      setStatus('已加载 ' + list.length + ' 路，主画面 #' + selectedChannelNumber);
    }

    function switchMainChannel(channelNumber) {
      const item = findChannel(channelNumber);
      if (!item) {
        setStatus('未找到通道 #' + channelNumber);
        return;
      }
      selectedChannelNumber = Number(item.number);
      channelEl.value = selectedChannelNumber;
      render();
    }

    async function loadChannels(forceRefresh = false) {
      setStatus(forceRefresh ? '刷新 C-SMART 通道...' : '读取 C-SMART 通道...');
      const res = await fetch(API_PREFIX + '/api/csmart/channels?' + (forceRefresh ? 'refresh=1&' : '') + 't=' + Date.now(), { cache: 'no-store' });
      const data = await res.json();
      if (!res.ok || !Array.isArray(data.channels)) throw new Error(data.error || '读取 C-SMART 通道失败');
      channels = data.channels.sort((a, b) => Number(a.number) - Number(b.number));
      render();
    }

    mainTile.addEventListener('dragover', (event) => {
      event.preventDefault();
      mainTile.classList.add('is-drop-target');
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
    });
    mainTile.addEventListener('dragleave', () => mainTile.classList.remove('is-drop-target'));
    mainTile.addEventListener('drop', (event) => {
      event.preventDefault();
      mainTile.classList.remove('is-drop-target');
      const channelNumber = event.dataTransfer?.getData('text/plain');
      if (channelNumber) switchMainChannel(channelNumber);
    });
    layoutEl.addEventListener('change', () => { currentLayout = Number(layoutEl.value); render(); });
    channelEl.addEventListener('change', () => switchMainChannel(channelEl.value));
    document.getElementById('reload').addEventListener('click', render);
    document.getElementById('refresh').addEventListener('click', () => loadChannels(true).catch((err) => showError(err.message)));
    setInterval(() => loadChannels(true).catch((err) => showError('刷新失败: ' + err.message)), REFRESH_INTERVAL_MS);
    loadChannels(false).catch((err) => showError(err.message));
  </script>
</body>
</html>`;
}

module.exports = {
  DEFAULT_CHANNEL_CACHE_FILE,
  DEFAULT_CSMART_GATEWAY,
  DEFAULT_CSMART_ORG_ID,
  DEFAULT_PLAYER_URL,
  createCsmartIframePlayerHtml,
  defaultCapturePaths,
  extractCsmartBearerFromCapture,
  fetchCsmartChannelList,
  findCsmartChannel,
  getLatestCsmartBearer,
  getCsmartChannelSnapshotUrl,
  loadCachedChannels,
  maskSecret,
  normalizeCsmartChannelPayload,
  readJsonIfExists,
  saveCachedChannels,
};
