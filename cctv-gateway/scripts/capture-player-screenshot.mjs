#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';

const outputPath = process.env.CCTV_SCREENSHOT_OUTPUT;
const screenshotUrl = process.env.CCTV_SCREENSHOT_URL;
const sourceImage = process.env.CCTV_SCREENSHOT_SOURCE_IMAGE;
const channel = process.env.CCTV_SCREENSHOT_CHANNEL || '';
const waitMs = Number(process.env.CCTV_SCREENSHOT_WAIT_MS || 8000);
const timeoutMs = Number(process.env.CCTV_SCREENSHOT_TIMEOUT_MS || 30000);
const selector = process.env.CCTV_SCREENSHOT_SELECTOR || '.main-tile';

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (!outputPath) fail('CCTV_SCREENSHOT_OUTPUT is required.');

await fs.mkdir(path.dirname(outputPath), { recursive: true });

if (sourceImage) {
  await fs.copyFile(sourceImage, outputPath);
  console.log(`Copied test screenshot for channel ${channel || 'unknown'} to ${outputPath}`);
  process.exit(0);
}

if (!screenshotUrl) fail('CCTV_SCREENSHOT_URL is required.');

let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch (err) {
  fail(
    [
      'Playwright is required for browser player screenshots.',
      'Install it in cctv-gateway with: npm install -D playwright && npx playwright install chromium',
      `Original error: ${err.message}`,
    ].join('\n'),
  );
}

const browser = await chromium.launch({
  headless: true,
  args: ['--autoplay-policy=no-user-gesture-required'],
});

try {
  const page = await browser.newPage({
    viewport: { width: 1280, height: 720 },
    deviceScaleFactor: 1,
  });
  page.setDefaultTimeout(timeoutMs);
  await page.goto(screenshotUrl, { waitUntil: 'domcontentloaded', timeout: timeoutMs });
  await page.waitForTimeout(Math.max(0, waitMs));
  const target = await page.$(selector);
  if (target) {
    await target.screenshot({ path: outputPath, type: 'jpeg', quality: 88 });
  } else {
    await page.screenshot({ path: outputPath, type: 'jpeg', quality: 88, fullPage: false });
  }
  console.log(`Captured player screenshot for channel ${channel || 'unknown'} to ${outputPath}`);
} finally {
  await browser.close();
}
