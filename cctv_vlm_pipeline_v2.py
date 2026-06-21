#!/usr/bin/env python3
"""
C-SMART CCTV Snapshot + VLM Safety Detection Pipeline (v2.0)
=============================================================
自动登录 C-SMART -> 项目导航(FFL沙嶺) -> 多页九宫格截图 -> GLM-4.6V 安全检测 -> JSON/HTML 报告

Usage:
  python cctv_vlm_pipeline_v2.py                  # 完整管线
  python cctv_vlm_pipeline_v2.py --report-only     # 只重新分析已有截图
  python cctv_vlm_pipeline_v2.py --no-vlm          # 只截图不跑VLM
  python cctv_vlm_pipeline_v2.py --project FFL     # 指定项目过滤
  python cctv_vlm_pipeline_v2.py --max-pages 10    # 限制翻页数

Author: Senior Developer
Date: 2026-06-20
Version: 2.0
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import requests
from playwright.sync_api import sync_playwright, Page, BrowserContext

# ========================== 配置区 ==========================

CONFIG = {
    # C-SMART 登录
    "login_url": "https://50.c-smart.hk/home/login/index.html#/haihong",
    "monitor_url": "https://50.c-smart.hk/home/video-monitor-project-5.0/index.html#/",
    "home_url": "https://50.c-smart.hk/home/index.html",
    "username": "xuehui.deng",
    "password": "dXH13420167153!",
    "max_captcha_retries": 6,

    # 浏览器
    "profile_dir": str(Path(__file__).resolve().parent / ".pw-fresh"),
    "channel": "msedge",
    "headless": False,

    # 截图配置
    "grid_tile_selector": "div.video_item",
    "expand_selector": ".tip-right svg",
    "expand_candidates": [
        "span.iconfont-video.icon-quanping1",
        ".tip-right svg",
        "span[class*='quanping']",
        "span[class*='fullscreen']",
        "i[class*='fullscreen']",
        "[class*='icon-quanping']",
        ".pos_right svg",
        "svg",
        "[class*='expand']",
        "[class*='zoom-in']",
        ".el-icon-full-screen",
        "button",
        "[title*='全屏']",
        "[title*='放大']",
    ],
    "close_selector": "div.close-btn",
    "after_expand_delay_ms": 2500,
    "after_close_delay_ms": 800,
    "download_timeout_ms": 30000,
    "tile_count_limit": 0,

    # 项目过滤
    "project_filter": "FFL",
    "project_keywords": ["FFL", "沙嶺"],

    # 翻页
    "max_pages": 20,

    # 输出
    "shots_dir": str(Path(__file__).resolve().parent / "shots"),

    # VLM 配置
    "vlm_api_key": "a3816cf3fa86497da3bfdec6967dbd6a.jjt0HopCMzvNqdfO",
    "vlm_base_url": "https://open.bigmodel.cn/api/paas/v4/",
    "vlm_model": "glm-4.6v",
}

LOGIN_URL_PATTERN = re.compile(r"login/index\.html")

# ========================== 日志 ==========================

_log_file = Path(__file__).resolve().parent / "pipeline.log"

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ========================== 浏览器启动辅助 ==========================

def clean_profile_locks(profile_dir: Path):
    """清理 browser profile 的 Singleton 锁文件"""
    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        lock_file = profile_dir / lock_name
        try:
            if lock_file.exists():
                lock_file.unlink()
        except Exception:
            pass

def launch_browser(p, profile_dir: Path, headless: bool = False, channel: str = "msedge"):
    """启动持久化浏览器上下文，自动处理锁文件"""
    profile_dir.mkdir(parents=True, exist_ok=True)
    clean_profile_locks(profile_dir)

    for attempt in range(3):
        try:
            context = p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                channel=channel,
                no_viewport=True,
                ignore_https_errors=True,
                accept_downloads=True,
            )
            page = context.pages[0] if context.pages else context.new_page()
            return context, page
        except Exception as e:
            log(f"  浏览器启动失败 (attempt {attempt+1}/3): {e}")
            clean_profile_locks(profile_dir)
            time.sleep(2)
    raise RuntimeError("浏览器启动失败，请手动关闭所有 Edge 进程后重试")

# ========================== 滑块验证码求解 (OpenCV) ==========================

def solve_captcha_gap(bg_b64: str, slider_b64: str | None = None) -> dict:
    """用 OpenCV 求解滑块验证码缺口位置"""
    bg_bytes = base64.b64decode(bg_b64)
    bg_arr = np.frombuffer(bg_bytes, dtype=np.uint8)
    bg_gray = cv2.imdecode(bg_arr, cv2.IMREAD_GRAYSCALE)
    if bg_gray is None:
        return {"error": "Cannot decode bg image"}

    bg_h, bg_w = bg_gray.shape

    if slider_b64:
        sl_bytes = base64.b64decode(slider_b64)
        sl_arr = np.frombuffer(sl_bytes, dtype=np.uint8)
        sl_gray = cv2.imdecode(sl_arr, cv2.IMREAD_GRAYSCALE)
        if sl_gray is None:
            return {"error": "Cannot decode slider image"}

        sl_h, sl_w = sl_gray.shape
        if sl_w > bg_w or sl_h > bg_h:
            return {"error": "Slider larger than bg"}

        bg_edge = cv2.Canny(bg_gray, 100, 200)
        sl_edge = cv2.Canny(sl_gray, 100, 200)

        result = cv2.matchTemplate(bg_edge, sl_edge, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        return {
            "gap_x": int(max_loc[0]),
            "confidence": float(max_val),
            "method": "template",
            "image_width": bg_w,
            "image_height": bg_h,
            "slider_width": sl_w,
        }
    else:
        bg_blur = cv2.GaussianBlur(bg_gray, (5, 5), 0)
        bg_edge = cv2.Canny(bg_blur, 80, 160)
        kernel = np.ones((5, 5), np.uint8)
        bg_edge = cv2.dilate(bg_edge, kernel, iterations=1)

        contours, _ = cv2.findContours(bg_edge, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w < 20 or h < 20:
                continue
            if w > bg_w * 0.5 or h > bg_h * 0.8:
                continue
            aspect = w / h if h > 0 else 0
            if 0.3 < aspect < 5.0:
                candidates.append((x, w * h))

        if candidates:
            candidates.sort(key=lambda t: t[1], reverse=True)
            return {
                "gap_x": int(candidates[0][0]),
                "confidence": 0.5,
                "method": "canny",
                "image_width": bg_w,
                "image_height": bg_h,
            }

        col_sum = np.sum(bg_edge > 0, axis=0)
        threshold = np.max(col_sum) * 0.3
        gap_x = 0
        for i in range(len(col_sum)):
            if col_sum[i] > threshold and i > bg_w * 0.2:
                gap_x = i
                break

        return {
            "gap_x": int(gap_x),
            "confidence": 0.3,
            "method": "column_density",
            "image_width": bg_w,
            "image_height": bg_h,
        }

# ========================== 类人鼠标拖拽 ==========================

def generate_human_trajectory(distance: float) -> list[dict]:
    points = []
    num_steps = 25 + random.randint(0, 14)
    overshoot = distance + round((random.random() - 0.3) * 8)
    correction = distance - overshoot

    for i in range(num_steps + 1):
        t = i / num_steps
        ease = 1 - (1 - t) ** 3
        points.append({
            "x": overshoot * ease + (random.random() - 0.5) * 1.5,
            "y": (random.random() - 0.5) * 4,
            "delay": 8 + random.random() * 22,
        })

    if abs(correction) > 1:
        fix_steps = 3 + random.randint(0, 2)
        for i in range(1, fix_steps + 1):
            points.append({
                "x": overshoot + correction * (i / fix_steps),
                "y": (random.random() - 0.5) * 2,
                "delay": 15 + random.random() * 20,
            })

    points.append({"x": distance, "y": 0, "delay": 50 + random.random() * 80})
    return points

def human_drag(page: Page, start_x: float, start_y: float, distance: float):
    trajectory = generate_human_trajectory(distance)
    page.mouse.move(start_x, start_y)
    time.sleep(0.1 + random.random() * 0.15)
    page.mouse.down()
    for pt in trajectory:
        page.mouse.move(start_x + pt["x"], start_y + pt["y"])
        time.sleep(pt["delay"] / 1000.0)
    time.sleep(0.06 + random.random() * 0.09)
    page.mouse.up()

# ========================== 验证码 DOM 提取 ==========================

EXTRACT_CAPTCHA_JS = r"""
() => {
  const output = {
    bgBase64: null, sliderBase64: null,
    bgWidth: 0, bgHeight: 0, sliderBtn: null,
    trackWidth: 0, bgRect: null,
    captchaGone: false,
  };

  const selList = ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="verify-box"]',
                   '[class*="captcha"]', '[class*="jigsaw"]', '[class*="slider-wrap"]',
                   '[class*="puzzle"]', '[class*="slide-verify"]'];
  let container = null;
  for (const s of selList) {
    const el = document.querySelector(s);
    if (el && el.offsetParent !== null && el.offsetWidth > 200) { container = el; break; }
  }
  if (!container) { output.captchaGone = true; return output; }

  const allImgs = container.querySelectorAll('img');
  const imgInfo = [];
  for (const img of allImgs) {
    const r = img.getBoundingClientRect();
    if (r.width < 5 || r.height < 5) continue;
    let src = img.src || '';
    const style = window.getComputedStyle(img);
    if (style.backgroundImage && style.backgroundImage !== 'none') {
      const bi = style.backgroundImage.replace(/url\(["']?/, '').replace(/["']?\)$/, '');
      if (bi.startsWith('data:')) src = bi;
    }
    imgInfo.push({ src, w: Math.round(r.width), h: Math.round(r.height),
                   nw: img.naturalWidth || 0, nh: img.naturalHeight || 0, element: img });
  }

  let bgImg = null, sliderImg = null;
  imgInfo.sort((a, b) => (b.w * b.h) - (a.w * a.h));
  for (const info of imgInfo) {
    if (!bgImg && info.w > 200 && info.h > 100) bgImg = info;
    else if (!sliderImg && info.w >= 25 && info.w <= 120 && info.h >= 25 && info.h <= 160) sliderImg = info;
  }

  for (const cv of container.querySelectorAll('canvas')) {
    const r = cv.getBoundingClientRect();
    if (r.width > 200 && r.height > 100 && !bgImg) {
      try {
        output.bgBase64 = cv.toDataURL('image/png').split(',')[1];
        output.bgWidth = cv.width; output.bgHeight = cv.height;
        output.bgRect = { x: r.x, y: r.y, w: r.width, h: r.height };
      } catch (_) {}
    }
  }

  if (bgImg && !output.bgBase64) {
    if (bgImg.element.src && bgImg.element.src.startsWith('data:')) {
      output.bgBase64 = bgImg.element.src.split(',')[1];
      output.bgWidth = bgImg.nw || bgImg.w; output.bgHeight = bgImg.nh || bgImg.h;
      const r = bgImg.element.getBoundingClientRect();
      output.bgRect = { x: r.x, y: r.y, w: bgImg.w, h: bgImg.h };
    } else {
      try {
        const c = document.createElement('canvas');
        c.width = bgImg.nw || bgImg.w; c.height = bgImg.nh || bgImg.h;
        c.getContext('2d').drawImage(bgImg.element, 0, 0);
        output.bgBase64 = c.toDataURL('image/png').split(',')[1];
        output.bgWidth = c.width; output.bgHeight = c.height;
        const r = bgImg.element.getBoundingClientRect();
        output.bgRect = { x: r.x, y: r.y, w: bgImg.w, h: bgImg.h };
      } catch (_) {}
    }
  }

  if (sliderImg) {
    try {
      if (sliderImg.element.src && sliderImg.element.src.startsWith('data:'))
        output.sliderBase64 = sliderImg.element.src.split(',')[1];
      else {
        const c = document.createElement('canvas');
        c.width = sliderImg.nw || sliderImg.w; c.height = sliderImg.nh || sliderImg.h;
        c.getContext('2d').drawImage(sliderImg.element, 0, 0);
        output.sliderBase64 = c.toDataURL('image/png').split(',')[1];
      }
    } catch (_) {}
  }

  for (const s of ['[class*="verify-move-block"]', '[class*="slider-btn"]', '[class*="drag-btn"]',
                    '[class*="handler"]', '[class*="slider"] [class*="btn"]', '[class*="slider"] [class*="block"]']) {
    const el = container.querySelector(s);
    if (el) {
      const r = el.getBoundingClientRect();
      if (r.width > 10 && r.height > 10) { output.sliderBtn = { x: r.x + r.width / 2, y: r.y + r.height / 2 }; break; }
    }
  }
  if (!output.sliderBtn) {
    for (const el of container.querySelectorAll('div, span, button, i')) {
      const t = (el.textContent || '').trim(), r = el.getBoundingClientRect();
      if ((t === '>' || t === '>>' || t.includes('向右')) && r.width > 10 && r.width < 60) {
        output.sliderBtn = { x: r.x + r.width / 2, y: r.y + r.height / 2 }; break;
      }
    }
  }

  for (const s of ['[class*="slider-track"]', '[class*="verify-bar"]', '[class*="slide-track"]']) {
    const el = document.querySelector(s);
    if (el) { const r = el.getBoundingClientRect(); if (r.width > 100) { output.trackWidth = r.width; break; } }
  }
  if (!output.trackWidth && output.bgRect) output.trackWidth = output.bgRect.w;
  return output;
}
"""

DETECT_CAPTCHA_JS = r"""
() => {
  const sels = ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="captcha"]',
                '[class*="jigsaw"]', '[class*="slide-verify"]'];
  for (const s of sels) {
    const e = document.querySelector(s);
    if (e && e.offsetParent !== null && e.offsetWidth > 200) return true;
  }
  return false;
}
"""

REFRESH_CAPTCHA_JS = r"""
() => {
  const selList = ['[class*="verifybox"]', '[class*="verify-panel"]', '[class*="jigsaw"]'];
  let container = null;
  for (const s of selList) { const el = document.querySelector(s); if (el && el.offsetParent !== null && el.offsetWidth > 200) { container = el; break; } }
  if (!container) return false;
  for (const s of ['[class*="refresh"] img', '[title*="刷新"]', '.icon-refresh', '[class*="refresh-icon"]', 'img[alt*="刷新"]']) {
    const btn = container.querySelector(s);
    if (btn) { btn.click(); return true; }
  }
  for (const el of container.querySelectorAll('i, svg, span, div, img')) {
    const r = el.getBoundingClientRect();
    if (r.width > 15 && r.width < 40 && r.height > 15 && r.height < 40) {
      const parentRect = container.getBoundingClientRect();
      if (r.right > parentRect.right - 60 && r.top < parentRect.top + 60) { el.click(); return true; }
    }
  }
  return false;
}
"""

# ========================== 自动登录 ==========================

def auto_login(page: Page) -> bool:
    """自动登录 C-SMART 平台 (含滑块验证码求解)"""
    log("=== STEP 1: 打开登录页 ===")
    page.goto(CONFIG["login_url"], wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)

    log("=== STEP 2: 填用户名 ===")
    try:
        page.fill('input[placeholder*="请输入"], input[placeholder*="用户"], input[type="text"]', CONFIG["username"])
    except Exception:
        page.evaluate("""(u) => {
            const inputs = document.querySelectorAll('input:not([type="hidden"])');
            for (const inp of inputs) {
                if (inp.type === 'text' || !inp.type) {
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(inp, u);
                    inp.dispatchEvent(new Event('input', { bubbles: true }));
                    inp.dispatchEvent(new Event('change', { bubbles: true }));
                    return true;
                }
            }
        }""", CONFIG["username"])
    time.sleep(0.8)

    log("=== STEP 3: 填密码 ===")
    try:
        page.fill('input[type="password"]', CONFIG["password"])
    except Exception:
        page.evaluate("""(p) => {
            const pwd = document.querySelector('input[type="password"]');
            if (pwd) {
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(pwd, p);
                pwd.dispatchEvent(new Event('input', { bubbles: true }));
                pwd.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", CONFIG["password"])
    time.sleep(0.8)

    log("=== STEP 4: 勾选协议 ===")
    cb_result = page.evaluate("""() => {
        const inners = document.querySelectorAll('span.el-checkbox__inner');
        for (const inner of inners) {
            const parent = inner.closest('.el-checkbox');
            if (parent && !parent.classList.contains('is-checked')) { inner.click(); return true; }
        }
        return false;
    }""")
    if cb_result:
        log("  checkbox clicked")
    else:
        page.mouse.click(437, 452)
        log("  fallback coordinate click")
    time.sleep(0.5)

    log("=== STEP 5: 点登录 ===")
    btn_text = page.evaluate("""() => {
        for (const sel of ['button[type="button"]', '.login-btn', '[class*="login"] button', 'form button']) {
            for (const btn of document.querySelectorAll(sel)) {
                if ((btn.textContent || '').trim().includes('登')) { btn.click(); return (btn.textContent || '').trim(); }
            }
        }
        return null;
    }""")
    if btn_text:
        log(f'  clicked: "{btn_text}"')
    else:
        page.mouse.click(890, 488)
        log("  fallback coordinate click")

    log("=== STEP 6: 验证码处理 ===")
    time.sleep(3.5)

    has_captcha = page.evaluate(DETECT_CAPTCHA_JS)
    log(f"  captcha visible: {has_captcha}")

    if not has_captcha:
        log("  no captcha needed!")
        return True

    url_before = page.url

    for attempt in range(1, CONFIG["max_captcha_retries"] + 1):
        if attempt > 1:
            cur_url = page.url
            if not LOGIN_URL_PATTERN.search(cur_url):
                log("  already on home page!")
                return True
            if not page.evaluate(DETECT_CAPTCHA_JS):
                log("  captcha already gone!")
                return True
            refreshed = page.evaluate(REFRESH_CAPTCHA_JS)
            if refreshed:
                log("  captcha refreshed")
            time.sleep(3)

        log(f"  -- Attempt {attempt}/{CONFIG['max_captcha_retries']} --")
        img_data = page.evaluate(EXTRACT_CAPTCHA_JS)

        if img_data.get("captchaGone"):
            if not LOGIN_URL_PATTERN.search(page.url):
                log("  captcha gone, login success!")
                return True
            time.sleep(3)
            continue

        bg_b64 = img_data.get("bgBase64")
        if not bg_b64:
            log("  no bg image found, retrying...")
            time.sleep(2)
            continue

        slider_b64 = img_data.get("sliderBase64")
        cv_result = solve_captcha_gap(bg_b64, slider_b64)
        if "error" in cv_result:
            log(f"  OpenCV error: {cv_result['error']}")
            continue

        gap_x = cv_result["gap_x"]
        conf = cv_result["confidence"]
        method = cv_result["method"]
        img_w = cv_result["image_width"]
        log(f"  gap_x={gap_x}, conf={conf:.2f}, method={method}, img_w={img_w}")

        r_min = round(img_w * 0.35)
        r_max = round(img_w * 0.85)
        if method == "template" and (gap_x < r_min or gap_x > r_max):
            log("  out of range, Canny fallback...")
            cv2_result = solve_captcha_gap(bg_b64, None)
            if "gap_x" in cv2_result and cv2_result["gap_x"] > 0:
                gap_x = cv2_result["gap_x"]
                log(f"  Canny: gap_x={gap_x}")

        bg_rect = img_data.get("bgRect")
        track_w = img_data.get("trackWidth", 0)
        if bg_rect and track_w:
            dist = round(gap_x * (track_w / img_w))
        else:
            dist = gap_x
        dist += round((random.random() - 0.5) * 6)
        log(f"  slide distance: {dist}px (track_w={track_w})")

        slider_btn = img_data.get("sliderBtn")
        if not slider_btn:
            log("  no slider button found!")
            continue

        human_drag(page, slider_btn["x"], slider_btn["y"], dist)

        passed = wait_captcha_solved(page, url_before, 10000)
        if passed:
            log(f"  PASSED attempt {attempt}!")
            return True
        log(f"  attempt {attempt} failed")

    log("  all captcha attempts exhausted")
    return False


def wait_captcha_solved(page: Page, initial_url: str, max_wait_ms: int = 10000) -> bool:
    """轮询检测验证码是否通过（修复版：处理 SPA 导航导致的 context 销毁）"""
    start = time.time()
    while (time.time() - start) * 1000 < max_wait_ms:
        cur_url = page.url
        if not LOGIN_URL_PATTERN.search(cur_url):
            log(f"  URL changed: {cur_url[:80]}")
            return True
        # 检测验证码弹窗是否消失（用 try-except 处理 SPA 导航）
        try:
            captcha_still_visible = page.evaluate(DETECT_CAPTCHA_JS)
        except Exception as e:
            # execution context 被销毁 = 页面已导航 = 验证码已过
            log(f"  page context destroyed (验证码已过，页面已跳转): {str(e)[:60]}")
            time.sleep(2)
            try:
                cur_url = page.url
                log(f"  跳转后 URL: {cur_url[:80]}")
                if not LOGIN_URL_PATTERN.search(cur_url):
                    return True
            except Exception:
                pass
            return True  # 页面已跳转，认为验证码通过
        if not captcha_still_visible:
            log(f"  captcha dismissed ({int((time.time() - start) * 1000)}ms)")
            time.sleep(1.5)
            try:
                cur_url = page.url
                if not LOGIN_URL_PATTERN.search(cur_url):
                    return True
            except Exception:
                return True  # 页面已跳转
        time.sleep(0.5)
    return False


# ========================== 项目导航 (FFL 沙嶺) — v2 增强版 ==========================

def navigate_to_project(page: Page, project_keywords: list[str]) -> bool:
    """
    树形导航到指定项目 (如 FFL 沙嶺)
    v2 改进:
    1. 点击基礎公司后等待 8 秒 (异步加载)
    2. 检测并点击展开箭头图标
    3. 多次重试扫描子节点
    4. 支持双击展开
    """
    log(f"=== 项目导航: {' '.join(project_keywords)} ===")

    # Phase 0: 检查是否有 "地盤選擇" tab
    diban_clicked = page.evaluate("""() => {
        const all = document.querySelectorAll('*');
        for (const el of all) {
            const t = (el.textContent || '').trim();
            if (t === '地盤選擇' && el.offsetParent !== null) {
                el.click();
                return true;
            }
        }
        return false;
    }""")
    if diban_clicked:
        log("  点击了 '地盤選擇' tab")
        time.sleep(3)

    # Phase 1: 找到并点击 "基礎公司" 展开树节点
    log("  Phase 1: 查找 '基礎公司'...")
    time.sleep(5)

    # 诊断：打印页面上所有短文本元素
    all_short = page.evaluate("""() => {
        const root = document.body || document.documentElement;
        if (!root) return [];
        const items = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        let el;
        while ((el = walker.nextNode())) {
            const r = el.getBoundingClientRect();
            if (r.width < 10 || r.height < 5) continue;
            if (r.left > 500 || r.top < 20 || r.top > 900) continue;
            let direct = '';
            for (const c of el.childNodes) {
                if (c.nodeType === 3) direct += c.textContent;
            }
            direct = direct.trim();
            if (direct.length < 2 || direct.length > 50) continue;
            items.push({ text: direct.substring(0, 50), tag: el.tagName, x: Math.round(r.x), y: Math.round(r.y), cls: (el.className||'').toString().substring(0,40) });
        }
        return items;
    }""")
    log(f"  [诊断] 页面左侧短文本元素: {len(all_short)} 个")
    for item in all_short[:30]:
        log(f"    <{item['tag']}> '{item['text']}' at ({item['x']},{item['y']}) cls='{item['cls']}'")

    # 搜索展开图标
    expand_icons = page.evaluate("""() => {
        const root = document.body || document.documentElement;
        if (!root) return [];
        const results = [];
        const selectors = [
            '[class*="expand"]', '[class*="arrow"]', '[class*="switch"]',
            '[class*="toggle"]', '[class*="caret"]', '[class*="chevron"]',
            '.el-tree-node__expand-icon', '.arco-tree-node-switcher',
            '[class*="iconfont"]', '[class*="icon-arrow"]',
        ];
        const seen = new Set();
        for (const sel of selectors) {
            const els = document.querySelectorAll(sel);
            for (const el of els) {
                if (seen.has(el)) continue;
                seen.add(el);
                const r = el.getBoundingClientRect();
                if (r.width < 1 || r.height < 1) continue;
                if (r.left > 500 || r.top < 50 || r.top > 600) continue;
                results.push({
                    tag: el.tagName,
                    cls: (el.className || '').toString().substring(0, 80),
                    x: Math.round(r.x + r.width/2),
                    y: Math.round(r.y + r.height/2),
                });
            }
        }
        return results;
    }""")
    if expand_icons:
        log(f"  [诊断] 找到 {len(expand_icons)} 个展开图标")
        for icon in expand_icons[:10]:
            log(f"    <{icon['tag']}> cls='{icon['cls']}' at ({icon['x']},{icon['y']})")

    # 查找基礎公司
    jichu_found = page.evaluate("""() => {
        const root = document.body || document.documentElement;
        if (!root) return [];
        const results = [];
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
        let el;
        while ((el = walker.nextNode())) {
            const r = el.getBoundingClientRect();
            if (r.left < 0 || r.left > 400 || r.top < 30 || r.top > 850) continue;
            if (r.width < 20 || r.height < 8) continue;
            let directText = '';
            for (const child of el.childNodes) {
                if (child.nodeType === Node.TEXT_NODE) {
                    directText += child.textContent;
                }
            }
            directText = directText.trim();
            const fullText = (el.textContent || '').trim();
            if (fullText.length > 40) continue;
            const matchStr = directText || fullText;
            if (!(matchStr.includes('基礎') || matchStr.includes('基礟') || matchStr.includes('基礡') ||
                 matchStr.includes('基礤') || matchStr.includes('基礴'))) continue;
            if (!matchStr.includes('公司')) continue;
            results.push({
                text: fullText.substring(0, 60),
                x: Math.round(r.x + r.width / 2),
                y: Math.round(r.y + r.height / 2),
                w: Math.round(r.width),
                len: fullText.length,
            });
        }
        results.sort((a, b) => a.len - b.len);
        return results;
    }""")

    if not jichu_found:
        log("  ❌ 未找到 '基礎公司'")
        page.screenshot(path=str(Path(CONFIG["shots_dir"]) / "nav_no_jichu.png"))
        return False

    jichu_target = jichu_found[0]
    for j in jichu_found:
        if re.search(r'\(\d+\)', j["text"]):
            jichu_target = j
            break

    log(f"  点击 '{jichu_target['text']}' at ({jichu_target['x']}, {jichu_target['y']})")

    # v2: 先尝试点击附近的展开图标 (在基礎公司左侧)
    expand_clicked = False
    for icon in expand_icons:
        # 检查图标是否在基礎公司附近 (y 坐标接近, x 在左侧)
        if abs(icon["y"] - jichu_target["y"]) < 30 and icon["x"] < jichu_target["x"]:
            log(f"  先点击展开图标: <{icon['tag']}> cls='{icon['cls']}' at ({icon['x']},{icon['y']})")
            page.mouse.click(icon["x"], icon["y"])
            time.sleep(2)
            expand_clicked = True
            break

    # 点击基礎公司
    page.mouse.click(jichu_target["x"], jichu_target["y"])

    # v2: 等待 8 秒让子节点异步加载
    log("  等待子节点加载 (8s)...")
    time.sleep(8)

    # v2: 如果展开图标点击过，也再点一次基礎公司确保
    if expand_clicked:
        page.mouse.click(jichu_target["x"], jichu_target["y"])
        time.sleep(3)

    # Phase 2: 搜索 FFL 沙嶺 叶节点 (v2: 多次重试)
    log(f"  Phase 2: 查找 '{' '.join(project_keywords)}'...")
    ffl_y_threshold = jichu_target["y"] + 10

    ffl_nodes = []
    for scan_attempt in range(3):
        ffl_nodes = page.evaluate("""(args) => {
            const { keywords, minY } = args;
            const root = document.body || document.documentElement;
            if (!root) return [];
            const results = [];
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
            let el;
            while ((el = walker.nextNode())) {
                const text = (el.textContent || '').trim();
                if (text.length > 50) continue;
                let match = true;
                for (const kw of keywords) {
                    if (!text.includes(kw)) { match = false; break; }
                }
                if (!match) continue;
                const r = el.getBoundingClientRect();
                if (r.left < 0 || r.left > 400) continue;
                if (r.top < minY || r.top > 900) continue;
                if (r.width < 20 || r.height < 5) continue;
                results.push({
                    text: text.substring(0, 80),
                    x: Math.round(r.x + r.width / 2),
                    y: Math.round(r.y + r.height / 2),
                    len: text.length,
                });
            }
            results.sort((a, b) => a.len - b.len);
            return results.slice(0, 10);
        }""", {"keywords": project_keywords, "minY": ffl_y_threshold})

        if ffl_nodes:
            break

        if scan_attempt < 2:
            log(f"  未找到，尝试双击基礎公司重新展开 (attempt {scan_attempt + 1})...")
            page.mouse.dblclick(jichu_target["x"], jichu_target["y"])
            time.sleep(5)

    if not ffl_nodes:
        # v2: 也尝试只搜索 "沙嶺" (不带 FFL)
        log(f"  尝试只搜索 '沙嶺'...")
        ffl_nodes = page.evaluate("""(args) => {
            const { minY } = args;
            const root = document.body || document.documentElement;
            if (!root) return [];
            const results = [];
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
            let el;
            while ((el = walker.nextNode())) {
                const text = (el.textContent || '').trim();
                if (text.length > 50) continue;
                if (!text.includes('沙嶺') && !text.includes('沙岭')) continue;
                const r = el.getBoundingClientRect();
                if (r.left < 0 || r.left > 400) continue;
                if (r.top < minY || r.top > 900) continue;
                if (r.width < 20 || r.height < 5) continue;
                results.push({
                    text: text.substring(0, 80),
                    x: Math.round(r.x + r.width / 2),
                    y: Math.round(r.y + r.height / 2),
                    len: text.length,
                });
            }
            results.sort((a, b) => a.len - b.len);
            return results.slice(0, 10);
        }""", {"minY": ffl_y_threshold})

    if not ffl_nodes:
        log(f"  ❌ 未找到 {' '.join(project_keywords)} 节点")
        # 打印所有新出现的短文本元素
        new_elements = page.evaluate("""() => {
            const root = document.body || document.documentElement;
            if (!root) return [];
            const items = [];
            const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
            let el;
            while ((el = walker.nextNode())) {
                const r = el.getBoundingClientRect();
                if (r.width < 10 || r.height < 5) continue;
                if (r.left > 500 || r.top < 20 || r.top > 900) continue;
                let direct = '';
                for (const c of el.childNodes) {
                    if (c.nodeType === 3) direct += c.textContent;
                }
                direct = direct.trim();
                if (direct.length < 2 || direct.length > 50) continue;
                items.push({ text: direct.substring(0, 50), tag: el.tagName, x: Math.round(r.x), y: Math.round(r.y), cls: (el.className||'').toString().substring(0,40) });
            }
            return items;
        }""")
        log(f"  [诊断] 点击后页面元素: {len(new_elements)} 个")
        for item in new_elements[:30]:
            log(f"    <{item['tag']}> '{item['text']}' at ({item['x']},{item['y']}) cls='{item['cls']}'")
        page.screenshot(path=str(Path(CONFIG["shots_dir"]) / "nav_no_ffl.png"))
        return False

    log(f"  找到 {len(ffl_nodes)} 个候选:")
    for i, n in enumerate(ffl_nodes):
        log(f"    [{i}] '{n['text'][:50]}' at ({n['x']},{n['y']})")

    ffl_target = ffl_nodes[0]
    log(f"  点击 '{ffl_target['text'][:50]}' at ({ffl_target['x']}, {ffl_target['y']})")
    page.mouse.click(ffl_target["x"], ffl_target["y"])
    time.sleep(3)

    # Phase 3: 点击 "立即前往地盤" 按钮
    log("  Phase 3: 查找 '立即前往' 按钮...")
    btn_found = False
    for _ in range(16):
        btn_info = page.evaluate("""() => {
            const cands = [];
            const all = document.querySelectorAll('button, [class*="btn"], div[role="button"], a, span, div');
            for (const el of all) {
                const t = (el.textContent || '').trim();
                if (!t.includes('立即前往')) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 30 || r.height < 10) continue;
                const s = window.getComputedStyle(el);
                cands.push({
                    text: t.substring(0, 40),
                    tag: el.tagName,
                    bg: s.backgroundColor,
                    x: Math.round(r.x + r.width / 2),
                    y: Math.round(r.y + r.height / 2),
                    w: Math.round(r.width),
                    h: Math.round(r.height),
                });
            }
            if (cands.length === 0) {
                const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                let n;
                while ((n = w.nextNode())) {
                    const t = n.textContent.trim();
                    if (t.includes('立即前往') && t.length < 30) {
                        const p = n.parentElement;
                        if (p) {
                            const r = p.getBoundingClientRect();
                            if (r.width > 30 && r.height > 10) {
                                cands.push({ text: t, tag: p.tagName, x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), w: Math.round(r.width), h: Math.round(r.height) });
                            }
                        }
                    }
                }
            }
            return cands;
        }""")

        if btn_info:
            button_sized = [b for b in btn_info if b["w"] < 300 and b["h"] < 60]
            target = None
            for b in button_sized:
                if b["tag"] == "BUTTON" and b["bg"] not in ("rgba(0, 0, 0, 0)", "transparent"):
                    target = b
                    break
            if not target:
                for b in button_sized:
                    if b["tag"] == "BUTTON":
                        target = b
                        break
            if not target:
                for b in button_sized:
                    if b["bg"] not in ("rgba(0, 0, 0, 0)", "transparent") and "255, 255, 255" not in b["bg"]:
                        target = b
                        break
            if not target and button_sized:
                target = button_sized[0]
            if not target:
                target = btn_info[0]

            log(f"  点击 '{target['text']}' at ({target['x']}, {target['y']})")
            page.mouse.click(target["x"], target["y"])
            btn_found = True
            break

        time.sleep(0.5)

    if not btn_found:
        log("  ❌ 未找到 '立即前往' 按钮")
        page.screenshot(path=str(Path(CONFIG["shots_dir"]) / "nav_no_btn.png"))
        return False

    log("  ✅ 项目导航完成")
    time.sleep(6)
    return True


# ========================== 九宫格截图 ==========================

def find_grid_context(page: Page) -> tuple:
    """在主页面和所有 iframe 中搜索九宫格"""
    grid_sel = CONFIG["grid_tile_selector"]

    try:
        count = page.locator(grid_sel).count()
        if count > 0:
            log(f"  grid found in main page: {count} tiles")
            return page, grid_sel, count
    except Exception:
        pass

    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            count = frame.locator(grid_sel).count()
            if count > 0:
                log(f"  grid found in iframe: {count} tiles, url={frame.url[:100]}")
                return frame, grid_sel, count
        except Exception:
            continue

    return None, "", 0


def capture_cctv_snapshots(page: Page, output_dir: Path) -> list[Path]:
    """九宫格逐个放大截图"""
    output_dir.mkdir(parents=True, exist_ok=True)
    captured_files = []

    log("=== 搜索九宫格 ===")
    grid_ctx, grid_sel, tile_count = find_grid_context(page)

    if grid_ctx is None:
        log("  九宫格未找到! 尝试 fallback 选择器...")
        fallback_sels = [
            "div.video-monitor-right",
            "[class*='video-monitor']",
            "[class*='video-item']",
            "[class*='camera-item']",
            "[class*='monitor-item']",
            "video",
            "canvas",
        ]
        for sel in fallback_sels:
            for ctx in [page] + [f for f in page.frames if f != page.main_frame]:
                try:
                    count = ctx.locator(sel).count()
                    if count > 0:
                        log(f"  fallback: {sel} -> {count} tiles")
                        grid_ctx, grid_sel, tile_count = ctx, sel, count
                        break
                except Exception:
                    continue
            if grid_ctx is not None:
                break

    if grid_ctx is None:
        log("  ❌ 九宫格完全未找到，截图整个视口作为 fallback")
        fallback_path = output_dir / f"viewport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        page.screenshot(path=str(fallback_path), full_page=False)
        captured_files.append(fallback_path)
        return captured_files

    limit = CONFIG["tile_count_limit"]
    n = min(tile_count, limit) if limit > 0 else tile_count
    log(f"  共 {tile_count} 个格子，处理 {n} 个")

    expand_sel = CONFIG["expand_selector"]
    close_sel = CONFIG["close_selector"]
    after_expand_ms = max(CONFIG["after_expand_delay_ms"], 2500)
    after_close_ms = CONFIG["after_close_delay_ms"]
    download_timeout = CONFIG["download_timeout_ms"]

    tiles = grid_ctx.locator(grid_sel)

    detected_expand_sel = None
    if n > 0:
        try:
            candidates_info = page.evaluate("""(sel) => {
                const tile = document.querySelector(sel);
                if (!tile) return [];
                const results = [];
                for (const el of tile.querySelectorAll('svg, i, span, div, button, a')) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 5 && r.width < 60 && r.height > 5 && r.height < 60) {
                        results.push({
                            tag: el.tagName.toLowerCase(),
                            cls: (el.className || '').toString().substring(0, 80),
                            title: el.title || '',
                        });
                    }
                }
                return results;
            }""", grid_sel)
            log(f"  [DOM探测] 格子1内小图标: {len(candidates_info)} 个")
            for ci in candidates_info:
                log(f"    {ci['tag']}.{ci.get('cls','')[:50]} title='{ci.get('title','')}'")
        except Exception as e:
            log(f"  [DOM探测] 失败: {e}")

    for i in range(n):
        slot = i + 1
        log(f"  --- 格子 {slot}/{n} ---")

        lens_name = ""
        try:
            name_el = tiles.nth(i).locator("span.name").first
            if name_el.count() > 0:
                lens_name = name_el.inner_text(timeout=3000).strip()
        except Exception:
            pass

        try:
            tiles.nth(i).scroll_into_view_if_needed(timeout=10000)
        except Exception:
            pass

        expand_clicked = False
        all_sels = CONFIG.get("expand_candidates", [
            expand_sel, "span.iconfont-video.icon-quanping1", "svg",
            "[class*='fullscreen']", "[class*='expand']",
            "[class*='zoom-in']", ".el-icon-full-screen", "button",
            "[title*='全屏']", "[title*='放大']"
        ])
        if detected_expand_sel and detected_expand_sel not in all_sels:
            all_sels.insert(0, detected_expand_sel)

        for esel in all_sels:
            try:
                exp_el = tiles.nth(i).locator(esel)
                cnt = exp_el.count()
                if cnt == 0:
                    continue
                if cnt > 1:
                    best_idx = 0; best_sc = -99999
                    for idx in range(min(cnt, 10)):
                        try:
                            b = exp_el.nth(idx).bounding_box()
                            if b and (b["x"] + b["y"]) > best_sc:
                                best_sc = b["x"] + b["y"]; best_idx = idx
                        except: pass
                    exp_el = exp_el.nth(best_idx)
                exp_el.first.click(timeout=8000)
                expand_clicked = True
                if not detected_expand_sel and esel != expand_sel:
                    detected_expand_sel = esel
                break
            except Exception:
                continue

        if not expand_clicked:
            try:
                tb = tiles.nth(i).bounding_box()
                if tb:
                    page.mouse.click(tb["x"] + tb["width"] - 20, tb["y"] + tb["height"] - 15)
                    expand_clicked = True
                    log(f"    坐标点击右下角")
            except Exception as e:
                log(f"    所有放大方式失败: {e}")

        if not expand_clicked:
            log(f"    跳过此格子")
            continue

        # 等待视频加载
        video_loaded = False
        for wait_sec in range(15):
            try:
                loading = page.evaluate("""() => {
                    const popup = document.querySelector('div.video-popup, .video-popup');
                    if (!popup) return false;
                    const txt = (popup.textContent || '').trim();
                    return txt.includes('加載') || txt.includes('加载') || txt.includes('Loading') || txt.includes('loading');
                }""")
                video_ready = page.evaluate("""() => {
                    const videos = document.querySelectorAll('video');
                    for (const v of videos) {
                        if (v.readyState >= 2) return true;
                    }
                    return false;
                }""")
                if not loading and (video_ready or wait_sec >= 8):
                    video_loaded = True
                    log(f"    视频已加载 (等待{wait_sec + 1}s)")
                    break
            except Exception:
                pass
            time.sleep(1)

        if not video_loaded:
            log(f"    视频可能仍在加载，继续截图")

        time.sleep(after_expand_ms / 1000.0)

        # 搜索截图按钮
        shot_candidates = [
            "button.vjs-snapshot-control",
            "easy-player button.vjs-snapshot-control",
            "div.vjs-control-bar button.vjs-snapshot-control",
            ".video-popup [class*='snap']",
            ".video-popup [class*='camera']",
            ".video-popup [class*='shot']",
            ".video-popup [class*='capture']",
            ".video-popup button[title*='截图']",
            ".video-popup button[aria-label*='截图']",
            ".video-popup button",
        ]

        shot_btn = None
        search_contexts = [page] + list(page.frames)
        for ctx in search_contexts:
            for sel in shot_candidates:
                try:
                    loc = ctx.locator(sel).first
                    if loc.count() > 0 and loc.is_visible(timeout=1000):
                        shot_btn = loc
                        break
                except Exception:
                    continue
            if shot_btn is not None:
                break

        js_clicked = False
        if shot_btn is None:
            for ctx in search_contexts:
                try:
                    result = ctx.evaluate("""() => {
                        const pick = (root) => root.querySelector("button.vjs-snapshot-control") ||
                            root.querySelector('button[title="快照"]') || root.querySelector('button[title="截图"]');
                        let btn = pick(document);
                        if (btn) { btn.click(); return "doc"; }
                        for (const ep of document.querySelectorAll("easy-player")) {
                            const sr = ep && ep.shadowRoot;
                            if (sr && pick(sr)) { pick(sr).click(); return "shadow"; }
                        }
                        return "";
                    }""")
                    if result in ("doc", "shadow"):
                        js_clicked = True
                        log(f"    JS snapshot click: {result}")
                        break
                except Exception:
                    continue

        if shot_btn is None and not js_clicked:
            log(f"    未找到截图按钮，fallback 元素截图")
            fb_path = output_dir / f"{_safe_name(lens_name, slot)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            try:
                for ctx in search_contexts:
                    for sel in ["div.video-popup", ".video-popup", "easy-player", "video"]:
                        try:
                            loc = ctx.locator(sel).first
                            if loc.count() > 0 and loc.is_visible(timeout=1000):
                                loc.screenshot(path=str(fb_path))
                                captured_files.append(fb_path)
                                log(f"    saved (fallback): {fb_path.name}")
                                break
                        except Exception:
                            continue
                    if fb_path.exists():
                        break
                if not fb_path.exists():
                    page.screenshot(path=str(fb_path), full_page=False)
                    captured_files.append(fb_path)
                    log(f"    saved (viewport): {fb_path.name}")
            except Exception as e:
                log(f"    fallback 截图也失败: {e}")
        else:
            photo_stem = _safe_name(lens_name, slot)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = output_dir / f"{photo_stem}_{ts}.png"

            try:
                with page.expect_download(timeout=download_timeout) as dl:
                    if shot_btn is not None:
                        shot_btn.click(timeout=15000)

                download = dl.value
                sugg = download.suggested_filename or ""
                ext = Path(sugg).suffix or ".png"
                if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
                    ext = ".png"
                dest = output_dir / f"{photo_stem}_{ts}{ext}"
                download.save_as(str(dest))
                captured_files.append(dest)
                log(f"    saved: {dest.name}")
            except Exception as e:
                log(f"    下载失败: {e}，尝试元素截图 fallback")
                fb_path = output_dir / f"{photo_stem}_{ts}.png"
                try:
                    for ctx in search_contexts:
                        for sel in ["div.video-popup", ".video-popup", "easy-player", "video"]:
                            try:
                                loc = ctx.locator(sel).first
                                if loc.count() > 0 and loc.is_visible(timeout=1000):
                                    loc.screenshot(path=str(fb_path))
                                    captured_files.append(fb_path)
                                    log(f"    saved (fallback): {fb_path.name}")
                                    break
                            except Exception:
                                continue
                        if fb_path.exists():
                            break
                    if not fb_path.exists():
                        page.screenshot(path=str(fb_path), full_page=False)
                        captured_files.append(fb_path)
                except Exception:
                    log(f"    所有截图方式失败")

        # 关闭放大层
        try:
            if close_sel:
                page.locator(close_sel).first.click(timeout=8000)
            else:
                page.keyboard.press("Escape")
        except Exception:
            page.keyboard.press("Escape")

        time.sleep(after_close_ms / 1000.0)

    return captured_files


# ========================== 翻页 ==========================

def has_next_page(page: Page) -> dict:
    """检测是否有下一页分页按钮"""
    result = page.evaluate("""() => {
        const sels = [
            'button.btn-next',
            'button[class*="next"]',
            '.el-pagination .btn-next',
            '.pagination [class*="next"]',
            '[class*="pager"] [class*="next"]',
            'li[class*="next"]',
            'a[class*="next"]',
            'button[aria-label*="next"]',
            'button[title*="下一"]',
            'button[title*="next"]',
            '.ivu-page-next',
            '.ant-pagination-next',
        ];
        for (const sel of sels) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) {
                const r = el.getBoundingClientRect();
                if (r.width > 5 && r.height > 5) {
                    const cls = (el.className || '').toString();
                    const isDisabled = cls.includes('disabled') || cls.includes('is-disabled') ||
                                       el.disabled === true || el.getAttribute('aria-disabled') === 'true';
                    return {
                        found: true,
                        disabled: isDisabled,
                        selector: sel,
                        x: Math.round(r.x + r.width / 2),
                        y: Math.round(r.y + r.height / 2),
                        cls: cls.substring(0, 60),
                    };
                }
            }
        }

        const allBtns = document.querySelectorAll('button, a, li, span, div');
        for (const el of allBtns) {
            const t = (el.textContent || '').trim();
            if (t !== '下一頁' && t !== '下一页' && t !== '>' && t !== '›' && t !== '»' && t !== 'Next') continue;
            const r = el.getBoundingClientRect();
            if (r.width < 5 || r.height < 5 || r.width > 100) continue;
            if (el.offsetParent === null) continue;
            const cls = (el.className || '').toString();
            const isDisabled = cls.includes('disabled') || cls.includes('is-disabled') || el.disabled === true;
            return {
                found: true,
                disabled: isDisabled,
                selector: 'text:' + t,
                x: Math.round(r.x + r.width / 2),
                y: Math.round(r.y + r.height / 2),
                cls: cls.substring(0, 60),
            };
        }

        return { found: false };
    }""")
    return result


def click_next_page(page: Page, btn_info: dict) -> bool:
    """点击下一页按钮"""
    try:
        if btn_info.get("selector", "").startswith("text:"):
            page.mouse.click(btn_info["x"], btn_info["y"])
        else:
            sel = btn_info["selector"]
            el = page.locator(sel).first
            if el.count() > 0:
                el.click(timeout=5000)
            else:
                page.mouse.click(btn_info["x"], btn_info["y"])
        return True
    except Exception as e:
        log(f"  翻页点击失败: {e}")
        try:
            page.mouse.click(btn_info["x"], btn_info["y"])
            return True
        except Exception:
            return False


def capture_all_pages(page: Page, output_dir: Path) -> list[Path]:
    """多页截图：截完一页后翻页继续"""
    all_captured = []
    max_pages = CONFIG.get("max_pages", 20)

    for page_num in range(1, max_pages + 1):
        log(f"\n{'='*40}")
        log(f"  📄 第 {page_num} 页")
        log(f"{'='*40}")

        time.sleep(3)

        grid_ctx, _, tile_count = find_grid_context(page)
        if grid_ctx is None or tile_count == 0:
            log(f"  第 {page_num} 页未找到九宫格，结束翻页")
            break

        log(f"  第 {page_num} 页有 {tile_count} 个摄像头")

        page_dir = output_dir / f"page_{page_num:02d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        captured = capture_cctv_snapshots(page, page_dir)
        all_captured.extend(captured)

        log(f"  第 {page_num} 页截图完成: {len(captured)} 张")

        if page_num >= max_pages:
            log(f"  已达到最大翻页限制 ({max_pages})")
            break

        next_btn = has_next_page(page)
        if not next_btn.get("found"):
            log(f"  未找到翻页按钮，结束")
            break

        if next_btn.get("disabled"):
            log(f"  翻页按钮已禁用 (最后一页)，结束")
            break

        log(f"  翻页: selector={next_btn.get('selector')} at ({next_btn['x']},{next_btn['y']})")
        if not click_next_page(page, next_btn):
            log(f"  翻页失败，结束")
            break

        log(f"  已翻到第 {page_num + 1} 页")
        time.sleep(5)

    return all_captured


def _safe_name(name: str, slot: int) -> str:
    if name and name.strip():
        bad = '\\/:*?"<>|'
        s = "".join("_" if c in bad else c for c in name.strip())
        s = re.sub(r"\s+", "_", s).strip("._")
        return s[:100] if s else f"camera_{slot}"
    return f"camera_{slot}"


# ========================== VLM 安全检测 ==========================

VLM_PROMPT = """你是建筑工地安全监控AI。分析这张CCTV截图并输出JSON。

分析维度：人员防护装备(安全帽/反光衣)、危险行为、环境隐患(物料堆放/临边防护/积水)、设备异常。

只输出JSON，不要markdown代码块：
{"has_person":true/false,"safety_helmet":"pass/fail/unknown","reflective_vest":"pass/fail/unknown","dangerous_behavior":"none/描述","environmental_hazard":"none/描述","equipment_issue":"none/描述","overall_status":"normal/warning/danger/unknown","risk_level":"low/medium/high","description":"简短画面描述(50字内)","suggestions":["建议1"]}

黑屏/无信号/加载中→overall_status="unknown"。"""


def _repair_truncated_json(text: str) -> dict | None:
    """尝试修复被截断的 JSON 并解析"""
    text = re.sub(r'^```(?:json)?\s*\n?', '', text.strip())
    text = re.sub(r'\n?```\s*$', '', text.strip())

    m = re.search(r'\{[\s\S]*', text)
    if not m:
        return None
    fragment = m.group()

    try:
        return json.loads(fragment)
    except json.JSONDecodeError:
        pass

    last_brace = fragment.rfind('}')
    if last_brace > 0:
        candidate = fragment[:last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    open_braces = 0
    open_brackets = 0
    in_string = False
    escape = False
    cut_pos = len(fragment)

    for idx, ch in enumerate(fragment):
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1

        if open_braces < 0 or open_brackets < 0:
            cut_pos = idx
            break

    repaired = fragment[:cut_pos]
    repaired = re.sub(r',\s*"[^"]*"\s*:\s*"?[^",}\]]*$', '', repaired)
    repaired = re.sub(r',\s*"[^"]*"\s*:\s*$', '', repaired)
    repaired = re.sub(r',\s*$', '', repaired)
    repaired += ']' * max(open_brackets, 0) + '}' * max(open_braces, 0)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    return None


def _extract_fields_regex(text: str) -> dict:
    """从 VLM 文本响应中用正则提取关键字段"""
    result = {}

    patterns = {
        "has_person": r'"has_person"\s*:\s*(true|false)',
        "safety_helmet": r'"safety_helmet"\s*:\s*"([^"]*)"',
        "reflective_vest": r'"reflective_vest"\s*:\s*"([^"]*)"',
        "overall_status": r'"overall_status"\s*:\s*"([^"]*)"',
        "risk_level": r'"risk_level"\s*:\s*"([^"]*)"',
        "dangerous_behavior": r'"dangerous_behavior"\s*:\s*"([^"]*)"',
        "environmental_hazard": r'"environmental_hazard"\s*:\s*"([^"]*)"',
        "equipment_issue": r'"equipment_issue"\s*:\s*"([^"]*)"',
        "description": r'"description"\s*:\s*"([^"]*)"',
    }

    for field, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            val = m.group(1)
            if field == "has_person":
                result[field] = val == "true"
            else:
                result[field] = val

    if "overall_status" not in result:
        result["overall_status"] = "unknown"
    if "description" not in result:
        result["description"] = text[:300]
    result["raw_response"] = text

    return result


def vlm_detect(image_path: Path) -> dict:
    """用 GLM-4.6V 进行安全检测"""
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        url = CONFIG["vlm_base_url"] + "chat/completions"
        headers = {
            "Authorization": f"Bearer {CONFIG['vlm_api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": CONFIG["vlm_model"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"}
                        },
                        {
                            "type": "text",
                            "text": VLM_PROMPT
                        }
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        result = resp.json()

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        if not content or not content.strip():
            return {"overall_status": "unknown", "description": "VLM returned empty", "raw_response": ""}

        try:
            return json.loads(content.strip())
        except json.JSONDecodeError:
            pass

        repaired = _repair_truncated_json(content)
        if repaired:
            log(f"    [VLM] JSON 修复成功")
            return repaired

        log(f"    [VLM] JSON 解析失败，使用正则提取")
        return _extract_fields_regex(content)

    except Exception as e:
        return {"error": str(e), "overall_status": "error"}


# ========================== HTML 报告 ==========================

def generate_html_report(results: list, report_path: Path):
    """生成 HTML 可视化报告"""
    html_parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>",
        "<title>CCTV 安全检测报告</title>",
        "<style>",
        "  body { font-family: 'Segoe UI', system-ui, sans-serif; margin: 0; padding: 20px; background: #0f172a; color: #e2e8f0; }",
        "  h1 { text-align: center; color: #38bdf8; margin-bottom: 30px; }",
        "  .summary { display: flex; gap: 16px; justify-content: center; margin-bottom: 30px; flex-wrap: wrap; }",
        "  .stat { background: #1e293b; padding: 16px 24px; border-radius: 12px; text-align: center; min-width: 120px; }",
        "  .stat .num { font-size: 28px; font-weight: bold; }",
        "  .stat .label { font-size: 13px; color: #94a3b8; margin-top: 4px; }",
        "  .stat.normal .num { color: #4ade80; }",
        "  .stat.warning .num { color: #fbbf24; }",
        "  .stat.danger .num { color: #f87171; }",
        "  .stat.unknown .num { color: #94a3b8; }",
        "  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); gap: 20px; }",
        "  .card { background: #1e293b; border-radius: 16px; overflow: hidden; border: 1px solid #334155; }",
        "  .card img { width: 100%; height: 240px; object-fit: cover; }",
        "  .card .info { padding: 14px; }",
        "  .card .name { font-weight: bold; font-size: 14px; margin-bottom: 8px; color: #f1f5f9; }",
        "  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }",
        "  .badge.normal { background: #166534; color: #4ade80; }",
        "  .badge.warning { background: #713f12; color: #fbbf24; }",
        "  .badge.danger { background: #7f1d1d; color: #f87171; }",
        "  .badge.unknown { background: #374151; color: #94a3b8; }",
        "  .badge.low { background: #14532d; color: #86efac; }",
        "  .badge.medium { background: #713f12; color: #fde047; }",
        "  .badge.high { background: #7f1d1d; color: #fca5a5; }",
        "  .desc { font-size: 13px; color: #cbd5e1; margin: 8px 0; line-height: 1.5; }",
        "  .hazards { font-size: 12px; color: #fbbf24; margin: 4px 0; }",
        "  .suggestions { font-size: 12px; color: #93c5fd; margin-top: 8px; }",
        "  .suggestions li { margin: 2px 0; }",
        "  .footer { text-align: center; margin-top: 30px; color: #64748b; font-size: 12px; }",
        "</style></head><body>",
        f"<h1>CCTV 安全检测报告</h1>",
        f"<p style='text-align:center;color:#94a3b8'>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 共 {len(results)} 个监控点</p>",
    ]

    counts = {"normal": 0, "warning": 0, "danger": 0, "unknown": 0, "error": 0}
    for r in results:
        s = r.get("overall_status", "unknown")
        counts[s] = counts.get(s, 0) + 1

    html_parts.append("<div class='summary'>")
    for status, label in [("normal", "正常"), ("warning", "警告"), ("danger", "危险"), ("unknown", "未知")]:
        if counts.get(status, 0) > 0:
            html_parts.append(f"<div class='stat {status}'><div class='num'>{counts[status]}</div><div class='label'>{label}</div></div>")
    html_parts.append("</div>")

    html_parts.append("<div class='grid'>")

    shots_dir = Path(CONFIG["shots_dir"])
    for r in results:
        img_name = r.get("image", "")
        status = r.get("overall_status", "unknown")
        risk = r.get("risk_level", "?")
        desc = r.get("description", "")
        hazard = r.get("environmental_hazard", "none")
        behavior = r.get("dangerous_behavior", "none")
        has_person = r.get("has_person", False)
        suggestions = r.get("suggestions", [])

        img_path = None
        if r.get("image_path"):
            p = Path(r["image_path"])
            if p.exists():
                img_path = p
        if not img_path:
            for d in sorted(shots_dir.iterdir()):
                if d.is_dir():
                    for sub in [d] + (list(d.iterdir()) if d.is_dir() else []):
                        if sub.is_dir():
                            p = sub / img_name
                            if p.exists():
                                img_path = p
                                break
                    if img_path:
                        break
                    p = d / img_name
                    if p.exists():
                        img_path = p
                        break
            if not img_path:
                p = shots_dir / img_name
                if p.exists():
                    img_path = p

        img_src = f"file:///{img_path.as_posix()}" if img_path else ""

        html_parts.append("<div class='card'>")
        if img_src:
            html_parts.append(f"<img src='{img_src}' alt='{img_name}'>")
        html_parts.append("<div class='info'>")
        html_parts.append(f"<div class='name'>{img_name}</div>")
        html_parts.append(f"<span class='badge {status}'>{status}</span> ")
        html_parts.append(f"<span class='badge {risk}'>risk: {risk}</span>")
        if has_person:
            html_parts.append(" <span class='badge unknown'>检测到人员</span>")
        if desc:
            html_parts.append(f"<div class='desc'>{desc}</div>")
        if hazard and hazard != "none":
            html_parts.append(f"<div class='hazards'>⚠ 环境隐患: {hazard}</div>")
        if behavior and behavior != "none":
            html_parts.append(f"<div class='hazards'>⚠ 危险行为: {behavior}</div>")
        if suggestions:
            html_parts.append("<div class='suggestions'><ul>")
            for s in suggestions:
                html_parts.append(f"<li>{s}</li>")
            html_parts.append("</ul></div>")
        html_parts.append("</div></div>")

    html_parts.append("</div>")
    html_parts.append(f"<div class='footer'>Generated by CCTV+VLM Pipeline v2.0 | GLM-4.6V</div>")
    html_parts.append("</body></html>")

    html_path = report_path.with_suffix(".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    return html_path


# ========================== 重新分析模式 ==========================

def reanalyze_shots(shots_subdir: Path):
    """只重新运行 VLM 检测（使用已有截图）"""
    log(f"=== 重新分析已有截图: {shots_subdir} ===")
    images = sorted(shots_subdir.glob("*.png"))
    for sub in sorted(shots_subdir.iterdir()):
        if sub.is_dir():
            images.extend(sorted(sub.glob("*.png")))

    if not images:
        log("  未找到截图文件")
        return

    log(f"  找到 {len(images)} 张截图")
    results = []
    for img_path in images:
        log(f"  检测: {img_path.name}")
        result = vlm_detect(img_path)
        result["image"] = img_path.name
        result["image_path"] = str(img_path)
        result["timestamp"] = datetime.now().isoformat()
        results.append(result)

        status = result.get("overall_status", "unknown")
        risk = result.get("risk_level", "unknown")
        desc = result.get("description", "")[:120]
        log(f"    -> status={status}, risk={risk}")
        if desc:
            log(f"    -> {desc}")
        time.sleep(1)

    report_path = shots_subdir.parent / f"vlm_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log(f"\n=== VLM 报告已保存: {report_path.name} ===")

    html_path = generate_html_report(results, report_path)
    log(f"=== HTML 报告: {html_path.name} ===")

    log("\n=== 检测摘要 ===")
    for r in results:
        name = r.get("image", "?")
        status = r.get("overall_status", "?")
        risk = r.get("risk_level", "?")
        log(f"  {name}: {status} / {risk}")


# ========================== 主流程 ==========================

def main():
    parser = argparse.ArgumentParser(description="CCTV Snapshot + VLM Safety Detection Pipeline v2.0")
    parser.add_argument("--report-only", action="store_true", help="只重新分析已有截图")
    parser.add_argument("--no-vlm", action="store_true", help="只截图不跑VLM")
    parser.add_argument("--project", type=str, default=None, help="项目过滤 (如 FFL)")
    parser.add_argument("--max-pages", type=int, default=None, help="最大翻页数")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    args = parser.parse_args()

    # 应用命令行参数
    if args.project:
        CONFIG["project_keywords"] = [args.project]
    if args.max_pages:
        CONFIG["max_pages"] = args.max_pages
    if args.headless:
        CONFIG["headless"] = True

    # --report-only 模式
    if args.report_only:
        shots_dir = Path(CONFIG["shots_dir"])
        subdirs = sorted([d for d in shots_dir.iterdir() if d.is_dir() and d.name.startswith("20")],
                        reverse=True)
        if not subdirs:
            log("未找到截图目录")
            return
        target = subdirs[0]
        log(f"重新分析最新截图目录: {target.name}")
        reanalyze_shots(target)
        return

    shots_dir = Path(CONFIG["shots_dir"])
    shots_dir.mkdir(parents=True, exist_ok=True)

    profile_dir = Path(CONFIG["profile_dir"])

    log("=" * 60)
    log("  CCTV Snapshot + VLM Safety Detection Pipeline v2.0")
    log("=" * 60)

    with sync_playwright() as p:
        context, page = launch_browser(p, profile_dir, headless=CONFIG["headless"], channel=CONFIG["channel"])

        try:
            # 检查是否已登录
            log("=== 检查登录状态 ===")
            page.goto(CONFIG["monitor_url"], wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)

            cur_url = page.url
            needs_login = LOGIN_URL_PATTERN.search(cur_url) is not None

            if not needs_login:
                grid_ctx, _, tile_count = find_grid_context(page)
                if grid_ctx is None or tile_count == 0:
                    log("  监控页无九宫格，可能需要重新选择项目或登录")
                    time.sleep(5)
                    grid_ctx, _, tile_count = find_grid_context(page)

                if grid_ctx is None or tile_count == 0:
                    needs_login = True
                    log("  仍未找到九宫格，尝试重新登录")

            if needs_login:
                log("  需要登录，开始自动登录流程...")
                login_ok = auto_login(page)
                if not login_ok:
                    log("  ❌ 登录失败!")
                    page.screenshot(path=str(shots_dir / "login_failed.png"))
                    return

                log("  ✅ 登录成功!")
                time.sleep(3)

            # 项目导航 (FFL 沙嶺)
            project_kw = CONFIG.get("project_keywords", [])
            if project_kw:
                log("=== 导航到指定项目 ===")
                try:
                    page.goto(CONFIG["home_url"], wait_until="domcontentloaded", timeout=45000)
                except Exception:
                    pass
                time.sleep(3)

                nav_ok = navigate_to_project(page, project_kw)
                if not nav_ok:
                    log("  ⚠️ 项目导航失败，尝试直接访问监控页")
                    page.goto(CONFIG["monitor_url"], wait_until="domcontentloaded", timeout=60000)
                    time.sleep(8)
                else:
                    log("  ✅ 已进入项目")
                    log("=== 导航到监控页 ===")
                    page.goto(CONFIG["monitor_url"], wait_until="domcontentloaded", timeout=60000)
                    time.sleep(8)
            else:
                log("=== 导航到监控页 ===")
                page.goto(CONFIG["monitor_url"], wait_until="domcontentloaded", timeout=60000)
                time.sleep(8)

            # 确保缩放 100%
            page.keyboard.press("Control+0")
            time.sleep(1)

            # 尝试导航到 CCTVWALL / 監控模式
            cctv_navigated = False
            for tab_text in ["CCTVWALL", "監控模式", "CCTV"]:
                try:
                    tab_clicked = page.evaluate(f"""() => {{
                        const tabs = document.querySelectorAll('[class*="tab"], [class*="nav"], [class*="mode"], .el-tabs__item, button, span');
                        for (const t of tabs) {{
                            const txt = (t.textContent || '').trim();
                            if (txt === '{tab_text}') {{ t.click(); return true; }}
                        }}
                        return false;
                    }}""")
                    if tab_clicked:
                        log(f"  已点击 {tab_text} 标签")
                        time.sleep(8)
                        cctv_navigated = True
                        break
                except Exception:
                    continue

            if not cctv_navigated:
                try:
                    page.get_by_text("CCTVWALL").first.click(timeout=5000)
                    log("  已点击 CCTVWALL (by text)")
                    time.sleep(8)
                    cctv_navigated = True
                except Exception:
                    try:
                        page.get_by_text("監控模式").first.click(timeout=5000)
                        log("  已点击 監控模式 (by text)")
                        time.sleep(8)
                        cctv_navigated = True
                    except Exception:
                        log("  ⚠️ 无法找到 CCTV/監控模式标签")

            # 截图监控页全貌
            page.screenshot(path=str(shots_dir / "monitor_page.png"))
            log(f"  监控页截图已保存 (cctv_navigated={cctv_navigated})")

            # 多页九宫格截图
            batch_dir = shots_dir / datetime.now().strftime("%Y%m%d_%H%M")
            batch_dir.mkdir(parents=True, exist_ok=True)

            project_name = " ".join(project_kw) if project_kw else "ALL"
            log(f"=== 开始多页截图 (项目: {project_name}) ===")
            captured = capture_all_pages(page, batch_dir)

            log(f"\n=== 截图完成: {len(captured)} 张 ===")
            for f in captured:
                log(f"  {f.name}")

            if not captured:
                log("  ❌ 未截到任何图片")
                return

            if args.no_vlm:
                log("  --no-vlm 模式，跳过 VLM 检测")
                log("\n完成!")
                return

            # VLM 安全检测
            log("\n=== VLM 安全检测 ===")
            results = []
            for img_path in captured:
                log(f"  检测: {img_path.name}")
                result = vlm_detect(img_path)
                result["image"] = img_path.name
                result["image_path"] = str(img_path)
                result["timestamp"] = datetime.now().isoformat()
                results.append(result)

                status = result.get("overall_status", "unknown")
                risk = result.get("risk_level", "unknown")
                desc = result.get("description", "")[:100]
                log(f"    -> status={status}, risk={risk}")
                if desc:
                    log(f"    -> {desc}")
                time.sleep(1)

            # 保存结果
            report_path = shots_dir / f"vlm_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            log(f"\n=== VLM 报告已保存: {report_path.name} ===")

            # 生成 HTML 可视化报告
            html_path = generate_html_report(results, report_path)
            log(f"=== HTML 报告: {html_path.name} ===")

            # 打印摘要
            log("\n" + "=" * 60)
            log("  检测摘要")
            log("=" * 60)
            for r in results:
                name = r.get("image", "?")
                status = r.get("overall_status", "?")
                risk = r.get("risk_level", "?")
                log(f"  {name}: {status} / {risk}")

        finally:
            context.close()

    log("\n完成!")


if __name__ == "__main__":
    main()
