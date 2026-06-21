/**
 * C-SMART -> Ezviz token refresh service.
 *
 * Responsibilities:
 *   - Load cached Ezviz accessToken/deviceSerial.
 *   - Extract fresh token/deviceSerial from existing C-SMART network captures.
 *   - Optionally run a refresh command that logs into C-SMART and regenerates captures.
 *   - Keep token hot in memory and notify the HLS proxy via callback.
 *
 * This file intentionally avoids printing full tokens in logs.
 */

const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const DEFAULT_CACHE_FILE = 'cctv-token-cache.json';
const DEFAULT_REFRESH_INTERVAL_MS = 20 * 60 * 60 * 1000;
const DEFAULT_MIN_REFRESH_GAP_MS = 5 * 60 * 1000;

function maskToken(token) {
  if (!token) return '';
  if (token.length <= 16) return `${token.slice(0, 4)}...`;
  return `${token.slice(0, 10)}...${token.slice(-6)}`;
}

function readJsonIfExists(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (_) {
    return null;
  }
}

function walkValues(value, visitor) {
  visitor(value);
  if (Array.isArray(value)) {
    for (const item of value) walkValues(item, visitor);
    return;
  }
  if (value && typeof value === 'object') {
    for (const item of Object.values(value)) walkValues(item, visitor);
  }
}

function extractTokenCandidatesFromText(text) {
  const candidates = [];
  if (!text) return candidates;

  const urlMatches = String(text).match(/https?:\/\/[^\s"'<>\\]+/g) || [];
  for (const rawUrl of urlMatches) {
    try {
      const parsed = new URL(rawUrl);
      const accessToken = parsed.searchParams.get('accessToken');
      const deviceSerial = parsed.searchParams.get('deviceSerial');
      if (accessToken && /^at\./.test(accessToken)) {
        candidates.push({ accessToken, deviceSerial, source: 'url-param' });
      }
    } catch (_) {}
  }

  const tokenMatches = String(text).match(/at\.[A-Za-z0-9._-]+/g) || [];
  const deviceMatches = String(text).match(/\b[A-Z][A-Z0-9]{7,12}\b/g) || [];
  for (const accessToken of tokenMatches) {
    candidates.push({
      accessToken,
      deviceSerial: deviceMatches.find(v => /^E\d{7,12}$/.test(v)) || null,
      source: 'regex',
    });
  }

  return candidates;
}

function extractBestTokenFromCapture(capture) {
  const candidates = [];
  walkValues(capture, (value) => {
    if (typeof value === 'string') {
      candidates.push(...extractTokenCandidatesFromText(value));
    }
  });

  const withDevice = candidates.find(c => c.accessToken && c.deviceSerial);
  const tokenOnly = candidates.find(c => c.accessToken);
  return withDevice || tokenOnly || null;
}

function parseCommand(command) {
  if (!command || !command.trim()) return null;
  const parts = [];
  let current = '';
  let quote = null;

  for (let i = 0; i < command.length; i += 1) {
    const ch = command[i];
    if ((ch === '"' || ch === "'") && (!quote || quote === ch)) {
      quote = quote ? null : ch;
      continue;
    }
    if (!quote && /\s/.test(ch)) {
      if (current) {
        parts.push(current);
        current = '';
      }
      continue;
    }
    current += ch;
  }
  if (current) parts.push(current);
  if (!parts.length) return null;
  return { file: parts[0], args: parts.slice(1) };
}

class CsmartEzvizTokenRefreshService {
  constructor(options = {}) {
    this.baseDir = options.baseDir || __dirname;
    this.cachePath = options.cachePath || path.join(this.baseDir, DEFAULT_CACHE_FILE);
    this.capturePaths = options.capturePaths || [
      path.join(this.baseDir, 'v16c-stream-data', 'stream-capture-result.json'),
      path.join(this.baseDir, 'v16-stream-capture', 'stream-capture-result.json'),
      path.join(this.baseDir, 'v16b-stream-intercept', 'stream-capture-result.json'),
      path.join(this.baseDir, 'v17c-stream-urls.json'),
    ];
    this.refreshCommand = options.refreshCommand || process.env.CSMART_TOKEN_REFRESH_COMMAND || '';
    this.refreshIntervalMs = options.refreshIntervalMs || Number(process.env.CSMART_TOKEN_REFRESH_INTERVAL_MS || DEFAULT_REFRESH_INTERVAL_MS);
    this.minRefreshGapMs = options.minRefreshGapMs || DEFAULT_MIN_REFRESH_GAP_MS;
    this.onToken = options.onToken || null;
    this.logger = options.logger || ((...args) => console.log(...args));
    this.timer = null;
    this.refreshInFlight = null;
    this.lastRefreshAttemptAt = 0;
    this.tokenInfo = null;
  }

  log(...args) {
    this.logger('[token-refresh]', ...args);
  }

  normalizeTokenInfo(info, source) {
    if (!info || !info.accessToken) return null;
    return {
      accessToken: info.accessToken,
      deviceSerial: info.deviceSerial || info.device_serial || 'E48203280',
      source: source || info.source || 'unknown',
      updatedAt: info.updatedAt || new Date().toISOString(),
      approximateExpiresAt: info.approximateExpiresAt || new Date(Date.now() + this.refreshIntervalMs + (2 * 60 * 60 * 1000)).toISOString(),
    };
  }

  loadFromCache() {
    const data = readJsonIfExists(this.cachePath);
    return this.normalizeTokenInfo(data, 'cache');
  }

  loadFromKnownFiles() {
    for (const capturePath of this.capturePaths) {
      const data = readJsonIfExists(capturePath);
      if (!data) continue;

      let tokenInfo = null;
      if (data.token) {
        tokenInfo = {
          accessToken: data.token,
          deviceSerial: data.deviceSerial,
          source: path.basename(capturePath),
        };
      } else {
        tokenInfo = extractBestTokenFromCapture(data);
      }

      const normalized = this.normalizeTokenInfo(tokenInfo, capturePath);
      if (normalized) return normalized;
    }
    return null;
  }

  saveToken(info) {
    const normalized = this.normalizeTokenInfo(info, info && info.source);
    if (!normalized) throw new Error('Cannot save empty token');
    fs.writeFileSync(this.cachePath, JSON.stringify(normalized, null, 2));
    this.tokenInfo = normalized;
    if (typeof this.onToken === 'function') this.onToken(normalized);
    this.log(`token saved: ${maskToken(normalized.accessToken)}, device=${normalized.deviceSerial}, source=${normalized.source}`);
    return normalized;
  }

  loadInitialToken() {
    const cached = this.loadFromCache();
    if (cached) {
      this.tokenInfo = cached;
      if (typeof this.onToken === 'function') this.onToken(cached);
      this.log(`loaded cached token: ${maskToken(cached.accessToken)}, device=${cached.deviceSerial}`);
      return cached;
    }

    const extracted = this.loadFromKnownFiles();
    if (extracted) {
      return this.saveToken(extracted);
    }

    throw new Error('No Ezviz token found. Run C-SMART login capture first or set EZVIZ_ACCESS_TOKEN.');
  }

  runRefreshCommand() {
    const parsed = parseCommand(this.refreshCommand);
    if (!parsed) {
      throw new Error('No CSMART_TOKEN_REFRESH_COMMAND configured');
    }

    this.log(`running refresh command: ${parsed.file} ${parsed.args.join(' ')}`);
    return new Promise((resolve, reject) => {
      const child = execFile(parsed.file, parsed.args, {
        cwd: this.baseDir,
        timeout: 8 * 60 * 1000,
        maxBuffer: 8 * 1024 * 1024,
        windowsHide: false,
      }, (err, stdout, stderr) => {
        if (err) {
          reject(new Error(`refresh command failed: ${err.message}\n${stderr || ''}`));
          return;
        }
        resolve({ stdout, stderr });
      });

      child.on('error', reject);
    });
  }

  async refreshNow(reason = 'manual') {
    if (this.refreshInFlight) return this.refreshInFlight;

    const now = Date.now();
    if (now - this.lastRefreshAttemptAt < this.minRefreshGapMs && this.tokenInfo) {
      this.log(`skip refresh (${reason}); recently attempted`);
      return this.tokenInfo;
    }

    this.lastRefreshAttemptAt = now;
    this.refreshInFlight = (async () => {
      this.log(`refresh start: ${reason}`);

      if (this.refreshCommand) {
        await this.runRefreshCommand();
      }

      const extracted = this.loadFromKnownFiles();
      if (!extracted) {
        throw new Error('Refresh finished but no Ezviz token was found in capture files');
      }

      return this.saveToken({
        ...extracted,
        source: `refresh:${extracted.source}`,
        updatedAt: new Date().toISOString(),
      });
    })();

    try {
      return await this.refreshInFlight;
    } finally {
      this.refreshInFlight = null;
    }
  }

  start() {
    if (this.timer) return;
    this.timer = setInterval(() => {
      this.refreshNow('scheduled').catch(err => this.log(`scheduled refresh failed: ${err.message}`));
    }, this.refreshIntervalMs);
    this.timer.unref?.();
    this.log(`scheduled refresh every ${Math.round(this.refreshIntervalMs / 3600000)}h`);
  }

  stop() {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}

module.exports = {
  CsmartEzvizTokenRefreshService,
  extractBestTokenFromCapture,
  maskToken,
};

if (require.main === module) {
  const service = new CsmartEzvizTokenRefreshService();
  const shouldRefresh = process.argv.includes('--refresh-now');
  Promise.resolve()
    .then(() => shouldRefresh ? service.refreshNow('cli') : service.loadInitialToken())
    .then((info) => {
      console.log(JSON.stringify({
        ok: true,
        accessTokenMasked: maskToken(info.accessToken),
        deviceSerial: info.deviceSerial,
        updatedAt: info.updatedAt,
        approximateExpiresAt: info.approximateExpiresAt,
        source: info.source,
      }, null, 2));
    })
    .catch((err) => {
      console.error(err.message);
      process.exit(1);
    });
}
