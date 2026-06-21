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
  getLatestCsmartBearer,
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
  return {
    ok: Boolean(cached?.channels?.length || bearer),
    hasBearer: Boolean(bearer),
    cacheFile: CACHE_FILE,
    channelCount: cached?.channels?.length || 0,
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
      sendHtml(res, createCsmartIframePlayerHtml({
        defaultChannelNo: Number(url.searchParams.get('channel') || 1),
        playerUrl: PLAYER_URL,
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
