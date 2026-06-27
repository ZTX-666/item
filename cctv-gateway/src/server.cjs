const http = require('node:http');
const path = require('node:path');
const { URL } = require('node:url');

const {
  DEFAULT_CHANNEL_CACHE_FILE,
  DEFAULT_CSMART_GATEWAY,
  DEFAULT_CSMART_ORG_ID,
  DEFAULT_PLAYER_URL,
  createCsmartIframePlayerHtml,
  fetchCsmartChannelList,
  findCsmartChannel,
  getLatestCsmartBearer,
  getCsmartChannelSnapshotUrl,
  loadCachedChannels,
  maskSecret,
  saveCachedChannels,
} = require('./csmart-player-core.cjs');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.CCTV_GATEWAY_PORT || 3457);
const HOST = process.env.CCTV_GATEWAY_HOST || '127.0.0.1';
const CACHE_FILE = process.env.CCTV_CHANNEL_CACHE_FILE || DEFAULT_CHANNEL_CACHE_FILE;
const CSMART_ORG_ID = process.env.CSMART_ORG_ID || DEFAULT_CSMART_ORG_ID;
const CSMART_GATEWAY = process.env.CSMART_GATEWAY || DEFAULT_CSMART_GATEWAY;
const PLAYER_URL = process.env.CCTV_PLAYER_URL || DEFAULT_PLAYER_URL;

let channelCache = null;
let refreshInFlight = null;

function sendJson(res, status, payload) {
  res.writeHead(status, {
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  });
  res.end(JSON.stringify(payload, null, 2));
}

function sendHtml(res, body) {
  res.writeHead(200, {
    'Cache-Control': 'no-store',
    'Content-Type': 'text/html; charset=utf-8',
  });
  res.end(body);
}

function sendBinary(res, status, { body, contentType, headers = {} }) {
  res.writeHead(status, {
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
    'Content-Length': body.length,
    'Content-Type': contentType || 'application/octet-stream',
    ...headers,
  });
  res.end(body);
}

function parsePositiveInt(value, fallback) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : fallback;
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchSnapshotBinary(remoteUrl, options = {}) {
  const timeoutMs = parsePositiveInt(options.timeoutMs, 20000);
  const attempts = Math.max(1, parsePositiveInt(options.retries, 2) + 1);
  let lastError = null;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(remoteUrl, {
        headers: {
          Accept: 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
          'User-Agent': 'Mozilla/5.0 ChitungSafety/1.0',
        },
        redirect: 'follow',
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`snapshot HTTP ${response.status}`);
      }
      const body = Buffer.from(await response.arrayBuffer());
      if (!body.length) {
        throw new Error('snapshot response is empty');
      }
      return {
        body,
        contentType: response.headers.get('content-type') || 'image/jpeg',
        attempts: attempt,
      };
    } catch (err) {
      lastError = err;
      if (attempt < attempts) {
        await delay(1000);
      }
    } finally {
      clearTimeout(timer);
    }
  }

  throw lastError || new Error('snapshot fetch failed');
}

function ezvizCaptureParams(channel) {
  const accessToken = String(channel.accessToken || channel.ezvizAccessToken || process.env.EZVIZ_ACCESS_TOKEN || '').trim();
  const deviceSerial = String(channel.deviceSerial || channel.deviceId || process.env.EZVIZ_DEVICE_SERIAL || '').trim();
  const channelNo = String(channel.channelNo || channel.number || '').trim();
  if (!accessToken || !deviceSerial || !channelNo) return null;
  return { accessToken, deviceSerial, channelNo };
}

function ezvizAreaDomain(channel) {
  return String(channel.areaDomain || process.env.EZVIZ_AREA_DOMAIN || 'https://isgpopen.ezvizlife.com').replace(/\/$/, '');
}

async function requestDeviceCapture(channel, options = {}) {
  const params = ezvizCaptureParams(channel);
  if (!params) {
    throw new Error('missing EZVIZ capture parameters');
  }
  const timeoutMs = parsePositiveInt(options.timeoutMs, 20000);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${ezvizAreaDomain(channel)}/api/lapp/device/capture`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 ChitungSafety/1.0',
      },
      body: new URLSearchParams(params),
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`device/capture HTTP ${response.status}: ${maskSecret(text.slice(0, 200))}`);
    }
    let payload;
    try {
      payload = JSON.parse(text);
    } catch (_) {
      throw new Error(`device/capture returned non-json: ${maskSecret(text.slice(0, 120))}`);
    }
    if (String(payload.code) !== '200') {
      throw new Error(`device/capture failed: ${payload.code || ''} ${payload.msg || ''}`.trim());
    }
    const picUrl = String(payload.data?.picUrl || payload.data?.url || payload.picUrl || '').trim();
    if (!picUrl) {
      throw new Error('device/capture returned empty picUrl');
    }
    return picUrl;
  } finally {
    clearTimeout(timer);
  }
}

async function captureDeviceSnapshot(channel, options = {}) {
  const picUrl = await requestDeviceCapture(channel, options);
  const snapshot = await fetchSnapshotBinary(picUrl, options);
  return {
    ...snapshot,
    source: 'device_capture',
    remoteUrl: picUrl,
  };
}

async function refreshChannels(reason = 'manual') {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    const bearer = process.env.CSMART_BEARER || getLatestCsmartBearer({ baseDir: ROOT });
    const payload = await fetchCsmartChannelList({
      baseDir: ROOT,
      bearer,
      cacheFile: CACHE_FILE,
      gateway: CSMART_GATEWAY,
      orgId: CSMART_ORG_ID,
    });
    channelCache = saveCachedChannels(payload, {
      baseDir: ROOT,
      cacheFile: CACHE_FILE,
      orgId: CSMART_ORG_ID,
      source: `gateway:${reason}`,
    });
    return channelCache;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

async function getChannels({ refresh = false } = {}) {
  const cached = channelCache || loadCachedChannels(ROOT, CACHE_FILE);
  if (!refresh && cached) {
    channelCache = cached;
    return cached;
  }

  try {
    return await refreshChannels(refresh ? 'forced' : 'startup');
  } catch (err) {
    if (cached) {
      return { ...cached, refreshWarning: maskSecret(err.message) };
    }
    throw err;
  }
}

function healthPayload() {
  const cached = channelCache || loadCachedChannels(ROOT, CACHE_FILE);
  const bearer = process.env.CSMART_BEARER || getLatestCsmartBearer({ baseDir: ROOT });
  const channelCount = cached?.channels?.length || 0;
  return {
    ok: channelCount > 0 || Boolean(bearer),
    hasBearer: Boolean(bearer),
    hasFlvPlayback: channelCount > 0 && Boolean(cached?.channels?.some((item) => item?.flv)),
    cacheFile: CACHE_FILE,
    channelCount,
    channelUpdatedAt: cached?.updatedAt || null,
    gateway: CSMART_GATEWAY,
    orgId: CSMART_ORG_ID,
    playerUrl: PLAYER_URL,
  };
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, {
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
        'Access-Control-Allow-Origin': '*',
      });
      res.end();
      return;
    }

    const url = new URL(req.url, `http://${req.headers.host}`);

    if (url.pathname === '/' || url.pathname === '/player') {
      const bearer = process.env.CSMART_BEARER || getLatestCsmartBearer({ baseDir: ROOT });
      sendHtml(res, createCsmartIframePlayerHtml({
        defaultChannelNo: Number(url.searchParams.get('channel') || 1),
        playerUrl: PLAYER_URL,
        gatewayBaseUrl: `http://${HOST}:${PORT}`,
        hasBearer: Boolean(bearer),
      }));
      return;
    }

    if (url.pathname === '/api/health') {
      sendJson(res, 200, healthPayload());
      return;
    }

    if (url.pathname === '/api/csmart/channels') {
      const refresh = url.searchParams.get('refresh') === '1';
      sendJson(res, 200, await getChannels({ refresh }));
      return;
    }

    if (url.pathname === '/api/csmart/snapshot' || url.pathname.startsWith('/api/csmart/snapshot/')) {
      const identifier = url.pathname === '/api/csmart/snapshot'
        ? url.searchParams.get('channel')
        : decodeURIComponent(url.pathname.slice('/api/csmart/snapshot/'.length));
      if (!identifier) {
        sendJson(res, 400, { error: 'Missing channel identifier' });
        return;
      }

      const channels = await getChannels({ refresh: url.searchParams.get('refresh') === '1' });
      const channel = findCsmartChannel(channels, identifier);
      if (!channel) {
        sendJson(res, 404, { error: `C-SMART channel not found: ${identifier}` });
        return;
      }

      try {
        const snapshotOptions = {
          retries: url.searchParams.get('retries') || process.env.CSMART_SNAPSHOT_RETRIES || 2,
          timeoutMs: url.searchParams.get('timeoutMs') || process.env.CSMART_SNAPSHOT_TIMEOUT_MS || 20000,
        };
        let snapshot;
        let captureError = null;
        try {
          snapshot = await captureDeviceSnapshot(channel, snapshotOptions);
        } catch (err) {
          captureError = err;
        }

        if (!snapshot) {
          const remoteUrl = getCsmartChannelSnapshotUrl(channel);
          if (!remoteUrl) {
            throw captureError || new Error(`C-SMART channel has no snapshot URL: ${identifier}`);
          }
          snapshot = {
            ...(await fetchSnapshotBinary(remoteUrl, snapshotOptions)),
            source: 'cached_screenshot',
            remoteUrl,
            captureError,
          };
        }

        sendBinary(res, 200, {
          body: snapshot.body,
          contentType: snapshot.contentType,
          headers: {
            'X-CCTV-Channel': String(channel.number || identifier),
            'X-CCTV-Snapshot-Attempts': String(snapshot.attempts),
            'X-CCTV-Snapshot-Source': snapshot.source,
          },
        });
      } catch (err) {
        sendJson(res, 502, {
          error: `C-SMART snapshot fetch failed: ${maskSecret(err.message)}`,
          channel: String(channel.number || identifier),
        });
      }
      return;
    }

    if (url.pathname === '/api/csmart/channels/refresh' && req.method === 'POST') {
      sendJson(res, 200, await refreshChannels('manual-api'));
      return;
    }

    sendJson(res, 404, { error: 'Not found' });
  } catch (err) {
    sendJson(res, 500, { error: maskSecret(err.message) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`C-SMART CCTV gateway: http://${HOST}:${PORT}/player`);
  console.log(`Health check:         http://${HOST}:${PORT}/api/health`);
});
