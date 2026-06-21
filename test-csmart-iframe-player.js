const http = require('http');
const fs = require('fs');
const { chromium } = require('playwright');

const channelNo = Number(process.argv[2] || 4);
const port = Number(process.env.PORT || 4567);

function mask(value) {
  return String(value || '')
    .replace(/at\.[A-Za-z0-9._-]+/g, 'at.<masked>')
    .replace(/dv\.[A-Za-z0-9._-]+/g, 'dv.<masked>')
    .replace(/accessToken["':=][^,"'&\s]+/g, 'accessToken:<masked>')
    .replace(/checkToken=[^&\s"']+/g, 'checkToken=<masked>');
}

function loadChannel() {
  const raw = JSON.parse(fs.readFileSync('csmart-channel-list-latest.json', 'utf8'));
  const list = raw.channels || (raw && raw.data && raw.data.list);
  if (!Array.isArray(list)) throw new Error('channel list missing');
  const item = list.find(x => Number(x.number) === channelNo);
  if (!item) throw new Error(`channel ${channelNo} not found`);
  return item;
}

function html(videoItem) {
  const listStr = JSON.stringify([videoItem]).replace(/</g, '\\u003c');
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>C-SMART iframe player test</title>
  <style>
    html, body { margin: 0; width: 100%; height: 100%; background: #111; color: #eee; font-family: Arial, sans-serif; }
    #status { padding: 8px 12px; font-size: 13px; background: #222; }
    iframe { width: 100vw; height: calc(100vh - 34px); border: 0; background: #000; }
  </style>
</head>
<body>
  <div id="status">waiting for iframe...</div>
  <iframe id="player" src="https://custom.c-smart.hk/csmart-player/cctv-video-list/?type=1&t=${Date.now()}"></iframe>
  <script>
    const iframe = document.getElementById('player');
    const statusEl = document.getElementById('status');
    const listStr = ${JSON.stringify(listStr)};
    let initSent = false;
    function sendInit(reason) {
      if (initSent) return;
      initSent = true;
      statusEl.textContent = 'sending iframeInit: ' + reason;
      iframe.contentWindow.postMessage({ type: 'iframeInit', listStr }, '*');
    }
    window.addEventListener('message', event => {
      console.log('[parent message]', event.data);
      if (event.data && event.data.type === 'iframeReady') sendInit('iframeReady');
      if (event.data && event.data.type === 'iframeInitComplete') statusEl.textContent = 'iframeInitComplete';
    });
    iframe.addEventListener('load', () => setTimeout(() => sendInit('iframe load'), 1000));
    setTimeout(() => sendInit('fallback timer'), 4000);
  </script>
</body>
</html>`;
}

function startServer(videoItem) {
  const page = html(videoItem);
  const server = http.createServer((req, res) => {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end(page);
  });
  return new Promise(resolve => {
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

async function main() {
  const videoItem = loadChannel();
  console.log('testing channel', channelNo, videoItem.cameraName, videoItem.ezopen || videoItem.ezopenHd);
  const server = await startServer(videoItem);
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 820 } });
  const events = [];

  page.on('console', msg => {
    const line = mask(`[console:${msg.type()}] ${msg.text()}`);
    events.push(line);
    console.log(line);
  });
  page.on('request', req => {
    const url = req.url();
    if (/ezviz|ezvizlife|csmart-player|live|wss|appKey|get|capture|ezopen|stream/i.test(url)) {
      const line = mask(`[req] ${req.method()} ${url}`);
      events.push(line);
      console.log(line);
    }
  });
  page.on('response', async res => {
    const url = res.url();
    if (!/ezviz|ezvizlife|csmart-player|live|wss|appKey|get|capture|ezopen|stream/i.test(url)) return;
    let body = '';
    const ct = res.headers()['content-type'] || '';
    if (ct.includes('json') || ct.includes('text')) {
      try {
        body = (await res.text()).slice(0, 700);
      } catch (_) {}
    }
    const line = mask(`[res] ${res.status()} ${url} ${body}`);
    events.push(line);
    console.log(line);
  });
  page.on('websocket', ws => {
    const line = mask(`[ws] ${ws.url()}`);
    events.push(line);
    console.log(line);
    ws.on('framesent', frame => console.log(mask(`[ws sent] ${String(frame.payload).slice(0, 200)}`)));
    ws.on('framereceived', frame => console.log(mask(`[ws recv] ${String(frame.payload).slice(0, 80)}`)));
    ws.on('close', () => console.log('[ws close]'));
  });

  await page.goto(`http://127.0.0.1:${port}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(45000);
  await page.screenshot({ path: `csmart-iframe-channel-${channelNo}.png`, fullPage: true });
  fs.writeFileSync(`csmart-iframe-channel-${channelNo}-capture.log`, events.join('\n'));
  await browser.close();
  server.close();
}

main().catch(err => {
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
});
