const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');

function listenOnRandomPort(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      resolve(server.address().port);
    });
  });
}

async function getFreePort() {
  const server = http.createServer();
  const port = await listenOnRandomPort(server);
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function requestBuffer(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      const chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: Buffer.concat(chunks),
        });
      });
    });
    req.on('error', reject);
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForGateway(port) {
  const healthUrl = `http://127.0.0.1:${port}/api/health`;
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await requestBuffer(healthUrl);
      if (response.statusCode === 200) return;
    } catch (_) {
      // Server is still starting.
    }
    await delay(100);
  }
  throw new Error('gateway did not start in time');
}

async function stopChild(child) {
  if (child.exitCode !== null) return;
  child.kill();
  await new Promise((resolve) => child.once('exit', resolve));
}

async function testProxiesCsmartChannelSnapshotByNumber() {
  const imageBytes = Buffer.from('fake-jpeg-bytes');
  const upstream = http.createServer((req, res) => {
    if (req.url === '/snapshot.jpg') {
      res.writeHead(200, { 'Content-Type': 'image/jpeg' });
      res.end(imageBytes);
      return;
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('missing');
  });
  const upstreamPort = await listenOnRandomPort(upstream);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cctv-gateway-test-'));
  const cachePath = path.join(tempDir, 'channels.json');
  fs.writeFileSync(cachePath, JSON.stringify({
    channels: [
      {
        id: 'channel-6',
        number: 6,
        cameraName: '斜坡03',
        status: 1,
        deviceType: 1,
        screenshot: `http://127.0.0.1:${upstreamPort}/snapshot.jpg`,
      },
    ],
  }));

  const gatewayPort = await getFreePort();
  const child = spawn(process.execPath, ['src/server.cjs'], {
    cwd: ROOT,
    env: {
      ...process.env,
      CCTV_GATEWAY_HOST: '127.0.0.1',
      CCTV_GATEWAY_PORT: String(gatewayPort),
      CCTV_CHANNEL_CACHE_FILE: cachePath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  let stderr = '';
  child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });

  try {
    await waitForGateway(gatewayPort);
    const response = await requestBuffer(`http://127.0.0.1:${gatewayPort}/api/csmart/snapshot/6`);

    assert.equal(response.statusCode, 200);
    assert.equal(response.headers['content-type'], 'image/jpeg');
    assert.deepEqual(response.body, imageBytes);
  } finally {
    await stopChild(child);
    await new Promise((resolve) => upstream.close(resolve));
    fs.rmSync(tempDir, { recursive: true, force: true });
  }

  assert.equal(stderr, '');
}

async function testPrefersEzvizDeviceCaptureBeforeCachedScreenshot() {
  const freshBytes = Buffer.from('fresh-device-capture');
  const staleBytes = Buffer.from('stale-cached-screenshot');
  const seenCaptureBodies = [];
  const upstream = http.createServer((req, res) => {
    if (req.url === '/api/lapp/device/capture' && req.method === 'POST') {
      const chunks = [];
      req.on('data', (chunk) => chunks.push(chunk));
      req.on('end', () => {
        const body = Buffer.concat(chunks).toString('utf8');
        seenCaptureBodies.push(body);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          code: '200',
          data: { picUrl: `http://127.0.0.1:${upstream.address().port}/fresh.jpg` },
        }));
      });
      return;
    }
    if (req.url === '/fresh.jpg') {
      res.writeHead(200, { 'Content-Type': 'image/jpeg' });
      res.end(freshBytes);
      return;
    }
    if (req.url === '/stale.jpg') {
      res.writeHead(200, { 'Content-Type': 'image/jpeg' });
      res.end(staleBytes);
      return;
    }
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    res.end('missing');
  });
  const upstreamPort = await listenOnRandomPort(upstream);

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cctv-gateway-test-'));
  const cachePath = path.join(tempDir, 'channels.json');
  fs.writeFileSync(cachePath, JSON.stringify({
    channels: [
      {
        id: 'channel-9',
        number: 9,
        cameraName: '施工區域01',
        deviceId: 'E48203280',
        accessToken: 'at.test-token',
        areaDomain: `http://127.0.0.1:${upstreamPort}`,
        status: 1,
        deviceType: 1,
        screenshot: `http://127.0.0.1:${upstreamPort}/stale.jpg`,
      },
    ],
  }));

  const gatewayPort = await getFreePort();
  const child = spawn(process.execPath, ['src/server.cjs'], {
    cwd: ROOT,
    env: {
      ...process.env,
      CCTV_GATEWAY_HOST: '127.0.0.1',
      CCTV_GATEWAY_PORT: String(gatewayPort),
      CCTV_CHANNEL_CACHE_FILE: cachePath,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  try {
    await waitForGateway(gatewayPort);
    const response = await requestBuffer(`http://127.0.0.1:${gatewayPort}/api/csmart/snapshot/9`);

    assert.equal(response.statusCode, 200);
    assert.equal(response.headers['content-type'], 'image/jpeg');
    assert.equal(response.headers['x-cctv-snapshot-source'], 'device_capture');
    assert.deepEqual(response.body, freshBytes);
    assert.equal(seenCaptureBodies.length, 1);
    assert.match(seenCaptureBodies[0], /accessToken=at\.test-token/);
    assert.match(seenCaptureBodies[0], /deviceSerial=E48203280/);
    assert.match(seenCaptureBodies[0], /channelNo=9/);
  } finally {
    await stopChild(child);
    await new Promise((resolve) => upstream.close(resolve));
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

Promise.all([
  testProxiesCsmartChannelSnapshotByNumber(),
  testPrefersEzvizDeviceCaptureBeforeCachedScreenshot(),
])
  .then(() => {
    console.log('cctv-gateway snapshot server tests passed');
  })
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  });
