/**
 * C-SMART Auto Login V15 — V12 login + DOM-based navigation + CCTV download
 *
 * V15 changes from V12:
 *   - Login: EXACTLY V12 code (channel: 'chrome', proven working)
 *   - Navigation: Replaced ALL coordinate clicks with DOM selectors
 *   - New: Navigate 安全管理 → CCTV-5.0 → download all snapshots with pagination
 *
 * Flow: Login → Search FFL → 立即前往地盤 → 汉堡菜单 → 安全管理 → CCTV-5.0 → snapshot all pages
 */

const { chromium } = require('playwright');
const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const TOKEN_REFRESH_ONLY = process.argv.includes('--token-refresh-only');

// ==================== CONFIG ====================
const CONFIG = {
  url: 'https://50.c-smart.hk/home/login/index.html#/haihong',
  username: 'xuehui.deng',
  password: 'dXH13420167153!',
  dir: __dirname,
  pythonExe: 'C:/Users/User/.workbuddy/binaries/python/versions/3.13.12/python.exe',
  opencvScript: path.join(__dirname, 'captcha-opencv.py'),
  maxRetries: 6,
  tmpDir: path.join(os.tmpdir(), 'csmart-captcha'),
  loginUrlPattern: /login|haihong/,
  outputDir: path.join(__dirname, 'v15-cctv-output'),
};

const ss = (page, name) => page.screenshot({ path: path.join(CONFIG.dir, `${name}.png`) }).catch(() => {});
const log = (...a) => console.log(`[${new Date().toISOString().substring(11, 19)}]`, ...a);
const ensureTmpDir = () => { try { fs.mkdirSync(CONFIG.tmpDir, { recursive: true }); } catch (_) {} };

// ==================== HUMAN-LIKE TRAJECTORY (V12 code, unchanged) ====================
function generateHumanTrajectory(distance) {
  const points = [];
  const numSteps = 25 + Math.floor(Math.random() * 15);
  const overshoot = distance + Math.round((Math.random() - 0.3) * 8);
  const correction = distance - overshoot;
  for (let i = 0; i <= numSteps; i++) {
    const t = i / numSteps;
    const ease = 1 - Math.pow(1 - t, 3);
    points.push({ x: overshoot * ease + (Math.random() - 0.5) * 1.5, y: (Math.random() - 0.5) * 4, delay: 8 + Math.random() * 22 });
  }
  if (Math.abs(correction) > 1) {
    for (let i = 1; i <= 3 + Math.floor(Math.random() * 3); i++)
      points.push({ x: overshoot + correction * (i / 4), y: (Math.random() - 0.5) * 2, delay: 15 + Math.random() * 20 });
  }
  points.push({ x: distance, y: 0, delay: 50 + Math.random() * 80 });
  return points;
}

async function humanDrag(page, startX, startY, distance) {
  const trajectory = generateHumanTrajectory(distance);
  await page.mouse.move(startX, startY);
  await page.waitForTimeout(100 + Math.random() * 150);
  await page.mouse.down();
  log(`  🖱️ mousedown (${Math.round(startX)}, ${Math.round(startY)})`);
  for (const pt of trajectory) { await page.mouse.move(startX + pt.x, startY + pt.y); await page.waitForTimeout(pt.delay); }
  await page.waitForTimeout(60 + Math.random() * 90);
  await page.mouse.up();
  log(`  ✅ mouseup, slid ${distance}px (${trajectory.length} points)`);
}

// ==================== CAPTCHA (V12 code, unchanged) ====================
async function extractCaptchaImages(page) {
  return await page.evaluate(() => {
    const output = { bgBase64: null, sliderBase64: null, bgWidth: 0, bgHeight: 0, sliderBtn: null, trackWidth: 0, bgRect: null, debug: { imgs: [], canvases: [] }, captchaGone: false };
    const selList = ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="verify-box"]', '[class*="captcha"]', '[class*="jigsaw"]', '[class*="slider-wrap"]', '[class*="puzzle"]', '[class*="slide-verify"]'];
    let container = null;
    for (const s of selList) { const el = document.querySelector(s); if (el && el.offsetParent !== null && el.offsetWidth > 200) { container = el; break; } }
    if (!container) { output.captchaGone = true; return output; }
    const allImgs = container.querySelectorAll('img'), imgInfo = [];
    for (const img of allImgs) {
      const r = img.getBoundingClientRect();
      if (r.width < 5 || r.height < 5) continue;
      let src = img.src || '';
      const style = window.getComputedStyle(img);
      if (style.backgroundImage && style.backgroundImage !== 'none') { const bi = style.backgroundImage.replace(/url\(["']?/, '').replace(/["']?\)$/, ''); if (bi.startsWith('data:')) src = bi; }
      imgInfo.push({ src: src.substring(0, 100), w: Math.round(r.width), h: Math.round(r.height), nw: img.naturalWidth || 0, nh: img.naturalHeight || 0, element: img });
      output.debug.imgs.push({ src: src.substring(0, 80), w: Math.round(r.width), h: Math.round(r.height) });
    }
    let bgImg = null, sliderImg = null;
    imgInfo.sort((a, b) => (b.w * b.h) - (a.w * a.h));
    for (const info of imgInfo) {
      if (!bgImg && info.w > 200 && info.h > 100) bgImg = info;
      else if (!sliderImg && info.w >= 25 && info.w <= 120 && info.h >= 25 && info.h <= 160) sliderImg = info;
    }
    for (const cv of container.querySelectorAll('canvas')) {
      const r = cv.getBoundingClientRect();
      if (r.width > 200 && r.height > 100 && !bgImg) try { output.bgBase64 = cv.toDataURL('image/png').split(',')[1]; output.bgWidth = cv.width; output.bgHeight = cv.height; output.bgRect = { x: r.x, y: r.y, w: r.width, h: r.height }; } catch (_) {}
      output.debug.canvases.push({ w: Math.round(r.width), h: Math.round(r.height) });
    }
    if (bgImg && !output.bgBase64) {
      if (bgImg.element.src?.startsWith('data:')) { output.bgBase64 = bgImg.element.src.split(',')[1]; output.bgWidth = bgImg.nw || bgImg.w; output.bgHeight = bgImg.nh || bgImg.h; const r = bgImg.element.getBoundingClientRect(); output.bgRect = { x: r.x, y: r.y, w: bgImg.w, h: bgImg.h }; }
      else try { const c = document.createElement('canvas'); c.width = bgImg.nw || bgImg.w; c.height = bgImg.nh || bgImg.h; c.getContext('2d').drawImage(bgImg.element, 0, 0); output.bgBase64 = c.toDataURL('image/png').split(',')[1]; output.bgWidth = c.width; output.bgHeight = c.height; } catch (_) {}
    }
    if (sliderImg) { if (sliderImg.element.src?.startsWith('data:')) output.sliderBase64 = sliderImg.element.src.split(',')[1]; else try { const c = document.createElement('canvas'); c.width = sliderImg.nw || sliderImg.w; c.height = sliderImg.nh || sliderImg.h; c.getContext('2d').drawImage(sliderImg.element, 0, 0); output.sliderBase64 = c.toDataURL('image/png').split(',')[1]; } catch (_) {} }
    for (const s of ['[class*="verify-move-block"]', '[class*="slider-btn"]', '[class*="drag-btn"]', '[class*="handler"]', '[class*="slider"] [class*="btn"]', '[class*="slider"] [class*="block"]']) { const el = container.querySelector(s); if (el) { const r = el.getBoundingClientRect(); if (r.width > 10 && r.height > 10) { output.sliderBtn = { x: r.x + r.width / 2, y: r.y + r.height / 2 }; break; } } }
    if (!output.sliderBtn) for (const el of container.querySelectorAll('div, span, button, i')) { const t = (el.textContent || '').trim(); const r = el.getBoundingClientRect(); if ((t === '>' || t === '>>' || t === '➤' || t.includes('向右')) && r.width > 10 && r.width < 60) { output.sliderBtn = { x: r.x + r.width / 2, y: r.y + r.height / 2 }; break; } }
    for (const s of ['[class*="slider-track"]', '[class*="verify-bar"]', '[class*="slide-track"]']) { const el = document.querySelector(s); if (el) { const r = el.getBoundingClientRect(); if (r.width > 100) { output.trackWidth = r.width; break; } } }
    if (!output.trackWidth && output.bgRect) output.trackWidth = output.bgRect.w;
    return output;
  });
}

function analyzeWithOpenCV(bgPath, sliderPath) {
  return new Promise((resolve) => {
    const args = [CONFIG.opencvScript, '--bg', bgPath];
    if (sliderPath) args.push('--slider', sliderPath);
    log(`  🔬 OpenCV: ${sliderPath ? 'template matching' : 'Canny edge'}...`);
    execFile(CONFIG.pythonExe, args, { timeout: 15000, maxBuffer: 1024 * 1024 }, (err, stdout) => {
      if (err) resolve({ error: err.message }); else try { resolve(JSON.parse(stdout.trim())); } catch (e) { resolve({ error: `JSON parse: ${e.message}` }); }
    });
  });
}

async function waitForCaptchaSolved(page, initialUrl, maxWaitMs = 10000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    const currentUrl = page.url();
    if (!CONFIG.loginUrlPattern.test(currentUrl)) { log(`  ✅ URL changed to: ${currentUrl.replace(/.{60}/, '$&\n')}`); return true; }
    const dialogVisible = await page.evaluate(() => {
      for (const s of ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="jigsaw"]']) {
        const e = document.querySelector(s); if (e && e.offsetParent !== null && e.offsetWidth > 200) return true;
      } return false;
    }).catch(() => true);
    if (!dialogVisible) { log(`  ✅ Captcha dialog dismissed (${Date.now() - start}ms)`); return true; }
    await page.waitForTimeout(500);
  } return false;
}

async function detectCaptcha(page) {
  return page.evaluate(() => ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="captcha"]', '[class*="jigsaw"]', '[class*="slide-verify"]'].some(s => { const e = document.querySelector(s); return e && e.offsetParent !== null && e.offsetWidth > 200; }));
}

async function refreshCaptcha(page) {
  const clicked = await page.evaluate(() => {
    const selList = ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="jigsaw"]'];
    let container = null;
    for (const s of selList) { const el = document.querySelector(s); if (el && el.offsetParent !== null && el.offsetWidth > 200) { container = el; break; } }
    if (!container) return false;
    for (const s of ['[class*="refresh"] img', '[title*="刷新"]', '.icon-refresh', '[class*="refresh-icon"]', 'img[alt*="刷新"]']) {
      const btn = container.querySelector(s); if (btn) { btn.click(); return true; }
    }
    for (const el of container.querySelectorAll('i, svg, span, div, img')) {
      const r = el.getBoundingClientRect();
      if (r.width > 15 && r.width < 40 && r.height > 15 && r.height < 40) {
        const parentRect = container.getBoundingClientRect();
        if (r.right > parentRect.right - 60 && r.top < parentRect.top + 60) { el.click(); return true; }
      }
    } return false;
  });
  if (clicked) log('  🔄 Captcha refreshed (inside container)');
  else log('  ⚠️ No refresh icon found in captcha container');
  await page.waitForTimeout(3000);
  return clicked;
}

// ==================== V15 NEW: DOM-BASED NAVIGATION ====================

/**
 * V15: Select FFL project using DOM selectors (no coordinate clicks)
 * Flow: click 地盤選擇 tab → fill search → click FFL → click 立即前往地盤
 */
async function selectFFLDOM(page) {
  log('━━━ STEP 7: Selecting FFL project (V15 DOM) ━━━');

  // Wait for page to settle after login
  await page.waitForTimeout(5000);
  await ss(page, 'v15-after-login');

  // Step 7a: Click "地盤選擇" tab (try multiple selectors)
  log('  🔍 Looking for "地盤選擇" tab...');
  const tabSelectors = [
    'text="地盤選擇"',
    'text="地盘选择"',
    '[class*="tab"]:has-text("地盤")',
    '[class*="tab"]:has-text("地盘")',
  ];
  let tabClicked = false;
  for (const sel of tabSelectors) {
    try { await page.click(sel, { timeout: 3000 }); tabClicked = true; log(`  ✅ Tab clicked: ${sel}`); break; } catch (_) {}
  }
  // Fallback: try getByText
  if (!tabClicked) {
    try { await page.getByText('地盤選擇').first().click({ timeout: 3000 }); tabClicked = true; log('  ✅ Tab clicked via getByText'); } catch (_) {}
  }
  if (!tabClicked) log('  ⚠️ "地盤選擇" tab not found, may already be on project page');
  
  await page.waitForTimeout(3000);
  await ss(page, 'v15-after-tab-click');

  // Step 7b: Fill search box
  log('  🔍 Filling search box...');
  const searchSelectors = [
    'input[placeholder*="地盤名稱"]',
    'input[placeholder*="地盘名称"]',
    'input[placeholder*="搜索"]',
    'input[type="text"]',
  ];
  let searchFilled = false;
  for (const sel of searchSelectors) {
    try { await page.fill(sel, 'FFL'); searchFilled = true; log(`  ✅ Search filled via: ${sel}`); break; } catch (_) {}
  }
  if (!searchFilled) {
    // JS fallback
    await page.evaluate(() => {
      const inputs = document.querySelectorAll('input[type="text"]');
      for (const inp of inputs) { if (inp.offsetParent !== null && inp.offsetWidth > 50) { inp.value = 'FFL'; inp.dispatchEvent(new Event('input', { bubbles: true })); return; } }
    });
    log('  ✅ Search filled via JS fallback');
  }

  await page.waitForTimeout(2000);
  await ss(page, 'v15-after-search');

  // Step 7c: Click FFL project item
  log('  🎯 Clicking FFL project item...');
  const projectSelectors = [
    'text="FFL 沙嶺數據產業園項目"',
    'text="FFL 沙嶺數據產業園項目"',
  ];
  let projectClicked = false;
  for (const sel of projectSelectors) {
    try { await page.click(sel, { timeout: 3000 }); projectClicked = true; log(`  ✅ Project clicked: ${sel}`); break; } catch (_) {}
  }
  if (!projectClicked) {
    try { await page.getByText('FFL 沙嶺').first().click({ timeout: 3000 }); projectClicked = true; log('  ✅ Project clicked via partial text'); } catch (_) {}
  }
  if (!projectClicked) { log('  ❌ FFL project item NOT found'); await ss(page, 'v15-no-ffl-item'); return false; }

  await page.waitForTimeout(3000);
  await ss(page, 'v15-after-ffl-click');

  // Step 7d: After clicking FFL project, we're directly on project page (no modal)
  await page.waitForTimeout(5000);
  
  const currentUrl = page.url();
  log(`  Current URL after click: ${currentUrl}`);

  // Check if we successfully navigated to project page
  const hasProjectContent = await page.evaluate(() => {
    return (document.body.innerText || '').includes('FFL') && 
           (document.body.innerText || '').includes('沙嶺');
  });
  
  if (!hasProjectContent && !currentUrl.includes('customized-home')) {
    log('  ❌ Not on FFL project page yet');
    await ss(page, 'v15-not-on-project');
    return false;
  }

  log('  ✅ Successfully navigated to FFL project page!');
  await ss(page, 'v15-on-project-page');
  log(`  ✅ Now on: ${page.url()}`);
  return true;
}

/**
 * V15: Click hamburger menu (DOM selector)
 */
async function clickHamburgerDOM(page) {
  log('  🍔 Clicking hamburger menu...');
  const selectors = [
    '.collapse-icon',
    '.icon-menu',
    '.business-icon.icon-menu',
    '[class*="collapse"]',
    '[class*="menu-icon"]',
    '[class*="sidebar-toggle"]',
  ];
  for (const sel of selectors) {
    const count = await page.locator(sel).count();
    if (count > 0) { await page.locator(sel).first().click(); log(`  ✅ Hamburger clicked: ${sel}`); return true; }
  }
  // Try getByRole or getByLabel
  try { await page.getByRole('button', { name: /菜单|menu/i }).first().click({ timeout: 3000 }); log('  ✅ Hamburger clicked via role'); return true; } catch (_) {}
  
  log('  ❌ Hamburger menu NOT found via DOM');
  await ss(page, 'v15-no-hamburger');
  return false;
}

/**
 * V15: Navigate to 安全管理 → CCTV-5.0 (DOM selectors)
 */
async function navigateToCCTV(page) {
  log('━━━ Navigating to CCTV-5.0 (V15 DOM) ━━━');

  // Step 1: Click hamburger menu
  const hamburgerOk = await clickHamburgerDOM(page);
  if (!hamburgerOk) return false;
  
  await page.waitForTimeout(3000);
  await ss(page, 'v15-after-hamburger');

  // Step 2: Click "安全管理" menu
  log('  🔍 Clicking "安全管理"...');
  let safetyClicked = false;
  
  // Try: click the menu item title (the whole clickable area)
  const safetySelectors = [
    'text="安全管理"',
    '.menu-item-title:has-text("安全管理")',
    '[class*="menu-item"]:has-text("安全管理")',
  ];
  for (const sel of safetySelectors) {
    try { await page.click(sel, { timeout: 3000 }); safetyClicked = true; log(`  ✅ "安全管理" clicked: ${sel}`); break; } catch (_) {}
  }
  if (!safetyClicked) {
    try { await page.getByText('安全管理').first().click({ timeout: 3000 }); safetyClicked = true; log('  ✅ "安全管理" clicked via getByText'); } catch (_) {}
  }
  if (!safetyClicked) { log('  ❌ "安全管理" NOT found'); await ss(page, 'v15-no-safety-menu'); return false; }

  await page.waitForTimeout(3000);
  await ss(page, 'v15-after-safety-menu');

  // Step 3: Click "CCTV-5.0" submenu item
  log('  🔍 Clicking "CCTV-5.0"...');
  let cctvClicked = false;
  const cctvSelectors = [
    'text="CCTV-5.0"',
    '.ellipsis-tooltip:has-text("CCTV-5.0")',
    '[class*="menu-item"]:has-text("CCTV-5.0")',
  ];
  for (const sel of cctvSelectors) {
    try { await page.click(sel, { timeout: 3000 }); cctvClicked = true; log(`  ✅ "CCTV-5.0" clicked: ${sel}`); break; } catch (_) {}
  }
  if (!cctvClicked) {
    try { await page.getByText('CCTV-5.0').first().click({ timeout: 3000 }); cctvClicked = true; log('  ✅ "CCTV-5.0" clicked via getByText'); } catch (_) {}
  }
  if (!cctvClicked) { log('  ❌ "CCTV-5.0" NOT found'); await ss(page, 'v15-no-cctv-menu'); return false; }

  await page.waitForTimeout(6000);
  await ss(page, 'v15-on-cctv-page');
  log(`  ✅ Now on CCTV page: ${page.url()}`);
  return true;
}

/**
 * V15: Download all CCTV snapshots with pagination
 */
async function downloadAllCCTVSnapshots(page) {
  log('━━━ Downloading all CCTV snapshots (V15) ━━━');
  
  let pageNum = 1;
  let hasMorePages = true;
  const outputDir = CONFIG.outputDir;
  fs.mkdirSync(outputDir, { recursive: true });

  while (hasMorePages) {
    log(`\n  📄 Processing page ${pageNum}...`);
    
    // Wait for grid to load
    await page.waitForTimeout(4000);
    await ss(page, `v15-cctv-page-${pageNum}`);

    // Find all snapshot tiles on current page
    const tileCount = await page.evaluate(() => {
      // Look for grid tiles / cards that contain CCTV snapshot
      const tiles = document.querySelectorAll('[class*="grid"] [class*="tile"], [class*="card"], [class*="snapshot"], [class*="cctv"]');
      return tiles.length;
    });
    log(`  Found ${tileCount} tile(s) on page ${pageNum}`);

    // Click each tile to open snapshot, then download
    for (let i = 0; i < tileCount; i++) {
      log(`    📷 Downloading snapshot ${i + 1}/${tileCount} on page ${pageNum}...`);
      
      // Click tile to open snapshot
      const clicked = await page.evaluate((idx) => {
        const tiles = document.querySelectorAll('[class*="grid"] [class*="tile"], [class*="card"], [class*="snapshot"]');
        if (tiles[idx]) { tiles[idx].click(); return true; }
        return false;
      }, i);
      
      if (!clicked) { log(`    ⚠️ Tile ${i + 1} not clickable`); continue; }
      
      await page.waitForTimeout(3000);
      
      // Look for download/snapshot image in the modal
      const snapshotPath = path.join(outputDir, `page${pageNum}_tile${i + 1}.png`);
      await page.screenshot({ path: snapshotPath, fullPage: false }).catch(() => {});
      
      // Close modal (ESC or close button)
      await page.keyboard.press('Escape');
      await page.waitForTimeout(1000);
    }

    // Check for next page button
    hasMorePages = await page.evaluate(() => {
      const nextBtn = document.querySelector('[class*="next"], [class*="pagination"] [class*="next"], .arco-pagination-next');
      return nextBtn && !nextBtn.classList.contains('disabled') && nextBtn.offsetParent !== null;
    });
    
    if (hasMorePages) {
      await page.evaluate(() => {
        const nextBtn = document.querySelector('[class*="next"], [class*="pagination"] [class*="next"], .arco-pagination-next');
        if (nextBtn) nextBtn.click();
      });
      pageNum++;
      await page.waitForTimeout(3000);
    } else {
      log(`  ✅ No more pages. Total: ${pageNum} page(s).`);
    }
  }
  
  return pageNum;
}

// ==================== MAIN PROGRAM (V12 login + V15 navigation) ====================
(async () => {
  log('🚀 C-SMART Auto Login V15 starting...');
  log(`  Account: ${CONFIG.username}`);
  ensureTmpDir();
  fs.mkdirSync(CONFIG.outputDir, { recursive: true });

  // V12: Use system Chrome (channel: 'chrome') — CRITICAL for login success
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
    args: ['--start-maximized', '--disable-blink-features=AutomationControlled'],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();

  // ── V16c: Network listener for stream URL capture ─────
  const capturedNetwork = [];
  page.on('request', req => {
    const url = req.url();
    if (/ezviz|ys7|stream|play|rtmp|hls|m3u8|token|snapshot|capture|device|camera|video|live|flv|webrtc/i.test(url)) {
      capturedNetwork.push({ type: 'req', url, method: req.method(), time: new Date().toISOString() });
      log(`  📡 REQ: ${req.method()} ${url.substring(0,140)}`);
    }
  });
  page.on('response', async res => {
    const url = res.url();
    if (!/ezviz|ys7|stream|play|rtmp|hls|m3u8|token|snapshot|capture|device|camera|video|live|flv|webrtc/i.test(url)) return;
    let body = '';
    try { const ct = res.headers()['content-type']||''; if (ct.includes('json')||ct.includes('text')||url.endsWith('.m3u8')) body = (await res.text()).substring(0,2000); } catch(e) {}
    capturedNetwork.push({ type: 'res', url, status: res.status(), time: new Date().toISOString(), bodyPreview: body });
    log(`  📡 RES: ${res.status()} ${url.substring(0,140)}`);
    if (body) log(`    BODY: ${body.substring(0,300)}`);
  });

  // JS injection for intercepting fetch/XHR/WebSocket
  const INTERCEPT_JS = `
(function(){if(window.__ci)return;window.__ci=1;window.__cd=[];
function cap(u){return/ezviz|ys7|stream|play|rtmp|hls|m3u8|token|snapshot|capture|camera|live|webrtc/i.test(u)}
function log(t,u,x){var e={t:t,url:u,time:new Date().toISOString()};for(var k in x)e[k]=x[k];window.__cd.push(e);console.log('[CI]',t,u.substring(0,150))}
const _f=window.fetch;window.fetch=function(a,b){var u=typeof a==='string'?a:a.url||'';if(cap(u))log('F-REQ',u,{m:(b||{}).method||'GET'});return _f.apply(this,arguments).then(function(r){if(cap(u)){r.clone().text().then(function(t){log('F-RES',u,{s:r.status,b:t.substring(0,3000)})})}return r})}
})();
`;
  
  try {
    // ========== STEP 1: Open Login Page (V12 code) ==========
    log('━━━ STEP 1: Opening login page ━━━');
    await page.goto(CONFIG.url, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(2000);
    await ss(page, 'v15-step1-open');
    log('');

    // ========== STEP 2: Fill Username (V12 code) ==========
    log('━━━ STEP 2: Filling username ━━━');
    await page.fill('input[placeholder*="请输入"], input[placeholder*="用户"], input[type="text"]', CONFIG.username)
      .catch(() => page.evaluate((u) => {
        const inputs = document.querySelectorAll('input:not([type="hidden"])');
        for (const inp of inputs) {
          if (inp.type === 'text' || !inp.type) {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(inp, u);
            inp.dispatchEvent(new Event('input', { bubbles: true }));
            inp.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
          }
        } return false;
      }, CONFIG.username));
    await page.waitForTimeout(800);
    log('');

    // ========== STEP 3: Fill Password (V12 code) ==========
    log('━━━ STEP 3: Filling password ━━━');
    await page.fill('input[type="password"]', CONFIG.password)
      .catch(() => page.evaluate((p) => {
        const pwd = document.querySelector('input[type="password"]');
        if (pwd) {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(pwd, p);
          pwd.dispatchEvent(new Event('input', { bubbles: true }));
          pwd.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }, CONFIG.password));
    await page.waitForTimeout(800);
    log('');

    // ========== STEP 4: Check Agreement Checkbox (V12 code) ==========
    log('━━━ STEP 4: Checking agreement checkbox ━━━');
    const cbResult = await page.evaluate(() => {
      const inners = document.querySelectorAll('span.el-checkbox__inner');
      for (const inner of inners) {
        const parent = inner.closest('.el-checkbox');
        if (parent && !parent.classList.contains('is-checked')) { inner.click(); return 'el-checkbox__inner clicked'; }
      } return null;
    });
    if (cbResult) log(`  ✅ ${cbResult}`);
    else { log('  ⚠️ Coordinate click...'); await page.mouse.click(437, 452); }
    await page.waitForTimeout(500);
    await ss(page, 'v15-step4-ready');
    log('');

    // ========== STEP 5: Click Login Button (V12 code) ==========
    log('━━━ STEP 5: Clicking login button ━━━');
    const btnText = await page.evaluate(() => {
      for (const sel of ['button[type="button"]', '.login-btn', '[class*="login"] button', 'form button']) {
        for (const btn of document.querySelectorAll(sel)) {
          if ((btn.textContent || '').trim().includes('登')) { btn.click(); return (btn.textContent || '').trim(); }
        }
      } return null;
    });
    if (btnText) log(`  ✅ Clicked: "${btnText}"`);
    else { await page.mouse.click(890, 488); log('  ⚠️ Fallback coordinate click'); }
    log('');

    // ========== STEP 6: Handle Captcha (V12 code, unchanged) ==========
    log('━━━ STEP 6: Handling captcha ━━━');
    await page.waitForTimeout(3500);
    await ss(page, 'v15-step6-captcha');

    const hasCaptcha = await detectCaptcha(page);
    log(`  Captcha visible: ${hasCaptcha}`);
    let loginSuccess = false;
    const urlBeforeLogin = page.url();

    if (!hasCaptcha) {
      log('  🎉 No captcha!');
      loginSuccess = true;
    } else {
      let solved = false;
      for (let attempt = 1; attempt <= CONFIG.maxRetries && !solved; attempt++) {
        if (attempt > 1) {
          const currentUrl = page.url();
          if (!CONFIG.loginUrlPattern.test(currentUrl)) { log(`  ✅ Already on home page! Skipping remaining attempts.`); loginSuccess = true; solved = true; break; }
          const captchaStillVisible = await detectCaptcha(page);
          if (!captchaStillVisible) { log(`  ✅ Captcha already gone!`); loginSuccess = true; solved = true; break; }
          const refreshed = await refreshCaptcha(page);
          if (refreshed) await ss(page, `v15-attempt${attempt}`);
          else { log('  ⚠️ Could not refresh, trying current state...'); await page.waitForTimeout(2000); }
        }

        log(`\n  ── Attempt ${attempt}/${CONFIG.maxRetries} ──`);
        const imgData = await extractCaptchaImages(page);
        log(`  📊 DOM: ${imgData.debug.imgs.length} imgs, ${imgData.debug.canvases.length} canvases, captchaGone=${imgData.captchaGone}`);

        if (imgData.captchaGone) {
          const currentUrl = page.url();
          if (!CONFIG.loginUrlPattern.test(currentUrl)) { log(`  ✅ Captcha gone AND URL changed! Login successful!`); loginSuccess = true; solved = true; break; }
          else {
            log(`  ⚠️ Captcha container gone but URL still on login page. Waiting...`);
            await waitForCaptchaSolved(page, urlBeforeLogin, 8000);
            if (!CONFIG.loginUrlPattern.test(page.url())) { loginSuccess = true; solved = true; break; }
            log('  ⚠️ Still on login page after waiting. Retrying...');
            continue;
          }
        }

        if (!imgData.bgBase64) {
          log('  ⚠️ No bg image extracted, screenshot fallback...');
          const captchaEl = await page.evaluate(() => {
            const el = document.querySelector('[class*="verifybox"], [class*="verify-panel"], [class*="jigsaw"]');
            if (el) { const r = el.getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height }; }
            return null;
          });
          const ssPath = path.join(CONFIG.tmpDir, `bg-${Date.now()}.png`);
          if (captchaEl && captchaEl.w > 200) await page.screenshot({ path: ssPath, clip: { x: captchaEl.x, y: captchaEl.y, width: Math.min(captchaEl.w, 500), height: Math.min(captchaEl.h, 300) } });
          else await page.screenshot({ path: ssPath });
          const cv = await analyzeWithOpenCV(ssPath, null);
          if (cv.error || !imgData.sliderBtn) { log('  ❌ Fallback failed'); continue; }
          const dist = cv.gap_x - imgData.sliderBtn.x + (imgData.bgRect?.x || 0);
          await humanDrag(page, imgData.sliderBtn.x, imgData.sliderBtn.y, dist);
          const passAfterFallback = await waitForCaptchaSolved(page, urlBeforeLogin);
          if (passAfterFallback) { log(`  🎉 PASSED attempt ${attempt}!`); solved = true; await ss(page, `v15-success-${attempt}`); break; }
          continue;
        }

        const bgPath = path.join(CONFIG.tmpDir, `bg-${Date.now()}.png`);
        fs.writeFileSync(bgPath, Buffer.from(imgData.bgBase64, 'base64'));
        let sliderPath = null;
        if (imgData.sliderBase64) { sliderPath = path.join(CONFIG.tmpDir, `sl-${Date.now()}.png`); fs.writeFileSync(sliderPath, Buffer.from(imgData.sliderBase64, 'base64')); }

        const cv = await analyzeWithOpenCV(bgPath, sliderPath);
        if (cv.error) { log(`  ❌ OpenCV: ${cv.error}`); continue; }
        log(`  📍 gap_x=${cv.gap_x}, conf=${cv.confidence}, method=${cv.method}`);

        let useGap = cv.gap_x;
        const rMin = Math.round(cv.image_width * 0.35), rMax = Math.round(cv.image_width * 0.85);
        if (cv.method === 'template' && (useGap < rMin || useGap > rMax)) {
          log(`  ⚠️ Out of range [${rMin}-${rMax}], Canny fallback...`);
          const canny = await analyzeWithOpenCV(bgPath, null);
          if (!canny.error && canny.gap_x > 0) useGap = canny.gap_x;
        }

        let dist = (imgData.bgRect && imgData.trackWidth) ? Math.round(useGap * (imgData.trackWidth / cv.image_width)) : useGap;
        dist += Math.round((Math.random() - 0.5) * 6);
        log(`  🎯 Slide: ${dist}px`);

        if (!imgData.sliderBtn) { log('  ❌ No slider button!'); continue; }
        await humanDrag(page, imgData.sliderBtn.x, imgData.sliderBtn.y, dist);

        const passed = await waitForCaptchaSolved(page, urlBeforeLogin);
        if (passed) { log(`  🎉🎉🎉 PASSED attempt ${attempt}!`); solved = true; await ss(page, `v15-success-${attempt}`); break; }
        log(`  ❌ Attempt ${attempt} failed`);
      }
      if (solved) loginSuccess = true;
      else { log('  😞 All attempts exhausted.'); await ss(page, 'v15-all-failed'); }
    }

    // ==================== POST-LOGIN: V15 DOM-based navigation ====================
    if (loginSuccess) {
      log('\n═════════════════════════════════');
      log('  ✅ LOGIN SUCCESSFUL! Starting V15 DOM navigation...');
      log('═════════════════════════════════\n');

      // Step 7: Select FFL project (DOM-based)
      const step7ok = await selectFFLDOM(page);
      if (!step7ok) { log('\n  ⚠️ Step 7 failed.'); await ss(page, 'v15-stop-at-step7'); return; }

      // Step 8: Click hamburger → 安全管理 → CCTV-5.0
      const step8ok = await navigateToCCTV(page);
      if (!step8ok) { log('\n  ⚠️ Step 8 failed.'); await ss(page, 'v15-stop-at-step8'); return; }

      // ── V16c: Capture stream URLs from CCTV page ─────
      log('\n━━━ STEP 8.5: Capturing stream URLs from CCTV page ━━━');
      
      // Inject JS interceptor
      await page.evaluate(INTERCEPT_JS);
      log('  ✅ JS interceptor injected');
      
      // Wait for video streams to load
      await page.waitForTimeout(10000);
      
      // Reload to trigger fresh stream requests
      log('  🔄 Reloading CCTV page to capture stream requests...');
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(15000);
      await ss(page, 'v16c-cctv-after-reload');
      
      // Re-inject after reload
      await page.evaluate(INTERCEPT_JS);
      await page.waitForTimeout(8000);
      
      // Extract JS-captured data
      const jsCaptured = await page.evaluate(() => window.__cd || []).catch(() => []);
      log(`  ✅ JS interceptor captured ${jsCaptured.length} entries`);
      
      // Scan page JS for stream URLs
      const jsStreamUrls = await page.evaluate(() => {
        var results = [];
        // Scan all script tags for stream-related URLs
        document.querySelectorAll('script').forEach(function(s) {
          var text = s.textContent || '';
          var matches = text.match(/https?:\/\/[^\s"']+/gi);
          if (matches) {
            matches.forEach(function(url) {
              if (/ezviz|ys7|rtmp|hls|m3u8|stream|webrtc/i.test(url)) results.push(url);
            });
          }
        });
        return results;
      }).catch(() => []);
      if (jsStreamUrls && jsStreamUrls.length > 0) {
        log(`  ✅ Found ${jsStreamUrls.length} stream URL(s) in page JS:`);
        jsStreamUrls.forEach(u => log(`    ${u.substring(0,200)}`));
      }

      // Save captured data
      const streamOutputDir = path.join(__dirname, 'v16c-stream-data');
      if (!fs.existsSync(streamOutputDir)) fs.mkdirSync(streamOutputDir, { recursive: true });
      
      const allData = {
        playwireCaptured: capturedNetwork,
        jsIntercepted: jsCaptured,
        streamUrlsInJS: jsStreamUrls || [],
        cctvPageUrl: page.url(),
      };
      fs.writeFileSync(path.join(streamOutputDir, 'stream-capture-result.json'), JSON.stringify(allData, null, 2));
      if (jsStreamUrls && jsStreamUrls.length > 0) {
        fs.writeFileSync(path.join(streamOutputDir, 'stream-urls.txt'), jsStreamUrls.join('\n'));
      }
      log(`  ✅ Stream capture saved to: ${streamOutputDir}`);

      if (TOKEN_REFRESH_ONLY) {
        log('\n  ✅ Token refresh capture complete (--token-refresh-only).');
        return;
      }

      // Step 9: Download all CCTV snapshots
      log('\n━━━ STEP 9: Downloading all CCTV snapshots ━━━');
      const totalPages = await downloadAllCCTVSnapshots(page);
      log(`\n  🏆 COMPLETE! Downloaded ${totalPages} page(s) of CCTV snapshots to: ${CONFIG.outputDir}`);

    } else {
      log('\n  ❌ LOGIN FAILED — cannot proceed.');
    }

    log('\n💡 Browser stays open 120s for inspection...');
    await page.waitForTimeout(120000);

  } catch (err) {
    log(`\n❌ FATAL: ${err.message}`);
    console.error(err.stack);
    await ss(page, 'v15-error');
  } finally {
    await browser.close();
    log('\n👋 Done.');
  }
})();
