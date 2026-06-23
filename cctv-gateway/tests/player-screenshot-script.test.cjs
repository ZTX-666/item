const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');

function testCopiesSourceImageInTestMode() {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'cctv-player-script-test-'));
  const source = path.join(tempDir, 'source.jpg');
  const output = path.join(tempDir, 'output.jpg');
  fs.writeFileSync(source, Buffer.from('test-player-shot'));

  const result = spawnSync(process.execPath, ['scripts/capture-player-screenshot.mjs'], {
    cwd: ROOT,
    env: {
      ...process.env,
      CCTV_SCREENSHOT_SOURCE_IMAGE: source,
      CCTV_SCREENSHOT_OUTPUT: output,
      CCTV_SCREENSHOT_URL: 'http://127.0.0.1:3457/player?channel=2&live=1&embedded=1',
      CCTV_SCREENSHOT_CHANNEL: '2',
    },
    encoding: 'utf8',
  });

  try {
    assert.equal(result.status, 0, result.stderr || result.stdout);
    assert.equal(fs.readFileSync(output).toString(), 'test-player-shot');
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

testCopiesSourceImageInTestMode();
console.log('cctv-gateway player screenshot script tests passed');
