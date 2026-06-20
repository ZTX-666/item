import express from 'express'
import os from 'os'
import path from 'path'
import qrcode from 'qrcode'
import pino from 'pino'
import makeWASocket, {
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  Browsers,
  DisconnectReason,
} from '@whiskeysockets/baileys'

const log = pino({ level: process.env.LOG_LEVEL || 'info' })

const app = express()
app.use(express.json({ limit: '200kb' }))

const storeDir = process.env.WHATSCLI_STORE_DIR?.trim() || path.join(os.homedir(), '.whatscli')
const authDir = path.join(storeDir, 'auth')

let latestQr = null
let status = { state: 'idle' }
let sock = null
let lastPairing = null
let socketPromise = null

function resetSocket() {
  try {
    sock?.end?.(undefined)
  } catch {}
  sock = null
  socketPromise = null
  latestQr = null
}

async function ensureSocket() {
  if (sock) return sock
  if (socketPromise) return socketPromise

  socketPromise = (async () => {
    status = { state: 'starting', storeDir, authDir }

    const { state, saveCreds } = await useMultiFileAuthState(authDir)
    const { version } = await fetchLatestBaileysVersion()

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger: log,
      browser: Browsers.windows('Chrome'),
    })

    sock.ev.on('creds.update', saveCreds)
    sock.ev.on('connection.update', (u) => {
      const { connection, lastDisconnect, qr } = u
      if (qr) {
        latestQr = qr
        status = { state: 'qr', updatedAt: Date.now() }
      }
      if (connection) {
        status = {
          state: connection,
          updatedAt: Date.now(),
          lastDisconnect: lastDisconnect ? String(lastDisconnect.error || '') : null,
        }
      }

      if (connection === 'close') {
        const code = lastDisconnect?.error?.output?.statusCode
        const shouldReconnect = code !== DisconnectReason.loggedOut
        resetSocket()
        if (shouldReconnect) {
          setTimeout(() => {
            ensureSocket().catch(() => {})
          }, 1500)
        }
      }
    })

    return sock
  })()

  try {
    return await socketPromise
  } finally {
    // If creation failed, allow retries.
    if (!sock) socketPromise = null
  }
}

app.get('/', async (_req, res) => {
  await ensureSocket()
  res.type('html').send(`
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>WhatsApp 连接设备</title>
    <style>
      body { font-family: system-ui, Segoe UI, sans-serif; margin: 24px; }
      .wrap { max-width: 720px; margin: 0 auto; }
      img { width: 360px; height: 360px; background: #fff; border: 1px solid #ddd; border-radius: 8px; }
      code { background: #f3f4f6; padding: 2px 6px; border-radius: 4px; }
      input { width: 100%; padding: 10px 12px; font-size: 16px; border-radius: 8px; border: 1px solid #ddd; box-sizing: border-box; }
      button { padding: 10px 12px; font-size: 16px; border-radius: 8px; border: 1px solid #111827; background: #111827; color: #fff; cursor: pointer; }
      button:disabled { opacity: 0.6; cursor: not-allowed; }
      .row { display: flex; gap: 10px; align-items: center; margin-top: 8px; }
      .hint { color: #4b5563; font-size: 14px; margin-top: 6px; }
      .card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; margin: 14px 0; background: #fff; }
      .mono { font-family: ui-monospace, Consolas, monospace; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h2>连接 WhatsApp</h2>
      <div class="card">
        <h3 style="margin:0 0 8px;">方式 A：配对码（推荐，避免扫码）</h3>
        <div class="hint">输入手机号（只填数字，不要 <span class="mono">+</span>、空格、括号、短横线）。香港示例：<span class="mono">85291234567</span></div>
        <div class="row">
          <input id="phone" placeholder="例如：85291234567" />
          <button id="btn" onclick="pair()">获取配对码</button>
        </div>
        <div class="hint">然后在手机 WhatsApp → 已连接的设备 → 连接设备 → 选择“使用电话号码配对/配对码”并输入该码。</div>
        <div class="hint">配对码：<code id="code" class="mono">-</code></div>
      </div>

      <div class="card">
        <h3 style="margin:0 0 8px;">方式 B：二维码</h3>
        <div class="hint">如果你的 WhatsApp 客户端不支持配对码入口，再用扫码方式。</div>
        <div>
          <img id="qr" alt="QR code" />
        </div>
      </div>

      <p>数据目录: <code>${storeDir}</code></p>
      <p>状态: <code id="st">loading</code></p>
    </div>
    <script>
      async function tick() {
        const r = await fetch('/status').then(r => r.json())
        document.getElementById('st').textContent = r.state || 'unknown'
        if (r.state === 'open') {
          document.getElementById('qr').style.display = 'none'
          return
        }
        const img = document.getElementById('qr')
        img.src = '/qr.png?t=' + Date.now()
      }
      async function pair() {
        const btn = document.getElementById('btn')
        const phone = (document.getElementById('phone').value || '').trim()
        btn.disabled = true
        try {
          const r = await fetch('/pair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ phone }) })
          const j = await r.json()
          if (!r.ok) throw new Error(j.error || 'pair failed')
          document.getElementById('code').textContent = j.code || '-'
        } catch (e) {
          document.getElementById('code').textContent = 'ERROR'
          alert(String(e.message || e))
        } finally {
          btn.disabled = false
        }
      }
      tick()
      setInterval(tick, 2000)
    </script>
  </body>
</html>
  `)
})

app.get('/status', async (_req, res) => {
  await ensureSocket()
  res.json({ ...status, storeDir, authDir, hasQr: Boolean(latestQr), lastPairing })
})

app.get('/qr.png', async (_req, res) => {
  await ensureSocket()
  if (!latestQr) return res.status(404).send('QR not ready yet')

  const png = await qrcode.toBuffer(latestQr, {
    type: 'png',
    errorCorrectionLevel: 'M',
    margin: 2,
    scale: 8,
  })
  res.setHeader('Content-Type', 'image/png')
  res.send(png)
})

app.post('/pair', async (req, res) => {
  try {
    const raw = String(req.body?.phone || '').trim()
    const phone = raw.replace(/[^\d]/g, '')
    if (!phone) return res.status(400).json({ error: 'Missing phone number' })
    if (phone.length < 8) return res.status(400).json({ error: 'Phone number looks too short' })

    const mask = (p) => p.length <= 6 ? `${p.slice(0, 2)}***` : `${p.slice(0, 4)}****${p.slice(-2)}`
    let lastError = null

    for (let attempt = 1; attempt <= 3; attempt += 1) {
      try {
        await ensureSocket()
        if (!sock) throw new Error('Socket not initialized')
        if (sock.authState?.creds?.registered) {
          return res.status(200).json({ code: null, message: 'already registered' })
        }

        let code = null
        try {
          code = await sock.requestPairingCode(phone)
        } catch (firstErr) {
          // If socket is still warming up, wait briefly then retry once.
          await sock.waitForConnectionUpdate((u) => u.connection === 'connecting' || Boolean(u.qr) || u.connection === 'open', 10_000)
          code = await sock.requestPairingCode(phone)
        }
        lastPairing = { phoneMasked: mask(phone), at: Date.now() }
        return res.json({ code, attempt })
      } catch (e) {
        lastError = e
        const msg = String(e?.message || e)
        if (msg.includes('Connection Closed') || msg.includes('Connection Failure')) {
          resetSocket()
          await new Promise((r) => setTimeout(r, 1500))
          continue
        }
        break
      }
    }

    const detail = lastError?.stack || lastError?.message || String(lastError || 'Pairing failed')
    res.status(500).json({ error: detail })
  } catch (e) {
    const detail = e?.stack || e?.message || String(e)
    res.status(500).json({ error: detail })
  }
})

const port = Number.parseInt(process.env.WA_AUTH_PORT || '8790', 10)
const server = app.listen(port, () => {
  console.log(`[wa-auth] http://localhost:${port}`)
  console.log(`[wa-auth] store dir: ${storeDir}`)
})

server.on('error', (err) => {
  console.error('[wa-auth] server error', err)
})

// Some environments aggressively exit if they think there are no active handles.
// Keep a tiny interval so the process stays alive.
setInterval(() => {}, 60_000)

