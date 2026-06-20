#!/usr/bin/env python3
"""
赤瞳守护者 — 巡检脚本
RTMP截帧 → YOLO双模型检测(工人PPE+施工机械) → ROI裁剪 → GLM-4v VLM(语义精分) → 标注输出

支持每2小时自动巡检11路工地摄像头，输出检测标注图和JSON报告。
RTMP不可用时自动回退到本地真实施工现场截图。
可独立运行，也可接入赤瞳系统 chitung-center API。

Usage:
    python nightly_patrol.py                  # 单次巡检全部摄像头(默认hybrid模式)
    python nightly_patrol.py --camera cam-01  # 只巡检指定摄像头
    python nightly_patrol.py --yolo-only      # 仅YOLO检测，不调VLM
    python nightly_patrol.py --loop           # 每2小时自动巡检(后台持续运行)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
from PIL import Image

# ─── 配置 ───────────────────────────────────────────────────────────────────

# 11路真实工地RTMP流
CAMERAS: list[dict[str, str]] = [
    {
        "id": "cam-slope-03",
        "name": "斜坡03",
        "area": "斜坡区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_6_1?expire=1843920402&id=987542176923750400&c=122083786b&t=389924b692745975bc71a1fc3dd9b25619b81438807a275d73584937a14f1539&ev=100",
    },
    {
        "id": "cam-slope-container-01",
        "name": "斜坡貨櫃01",
        "area": "斜坡区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_7_2?expire=1843920403&id=987542182618390528&c=122083786b&t=70de41b3ed10dc4a6d4c5106b109453ae85e1e3dd8b56fc96d74aa7ef301a9b8&ev=100",
    },
    {
        "id": "cam-guard-03",
        "name": "崗亭03",
        "area": "岗亭区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_3_1?expire=1843920394&id=987542144455352320&c=122083786b&t=2f337046d679fc43da4d4137d04381b7c80eac650e88c045bbf8381feb80d86e&ev=100",
    },
    {
        "id": "cam-construction-01",
        "name": "施工區域01",
        "area": "施工区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_9_1?expire=1843920407&id=987542197595897856&c=122083786b&t=8a9e754865f7e8ab8b32a57afab11b5d23a50b80c394fefafa171e04b385cebe&ev=100",
    },
    {
        "id": "cam-construction-02",
        "name": "施工區域02",
        "area": "施工区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_11_1?expire=1843920410&id=987542211702964224&c=122083786b&t=4aa6c914caee546093774557b308f8d95702b4113c28021002c794895fcbe31c&ev=100",
    },
    {
        "id": "cam-guard-01",
        "name": "崗亭01",
        "area": "岗亭区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_1_1?expire=1843920388&id=987542118474366976&c=122083786b&t=f1d6f039a568290ebf83e7a14cd8dd9cc0095ae6df76ae5e0f5816c1bbafb73c&ev=100",
    },
    {
        "id": "cam-slope-top-intersection",
        "name": "坡頂T字路口",
        "area": "斜坡区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_4_1?expire=1843920398&id=987542157776801792&c=122083786b&t=51d412022c6cc42ef36705b390d3a6ec87fd997dad6610127352b8fdb2d349ca&ev=100",
    },
    {
        "id": "cam-slope-02",
        "name": "斜坡02",
        "area": "斜坡区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_5_1?expire=1843920399&id=987542164091019264&c=122083786b&t=7455a2d80f6f74df9ab142d39bc20d9e3628ff790dd425dd122f7808842324c7&ev=100",
    },
    {
        "id": "cam-slope-04",
        "name": "斜坡04",
        "area": "斜坡区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_8_1?expire=1843920405&id=987542190475743232&c=122083786b&t=f7b811a3c3986ec6752defc41658b0ffdf87a7cd12ac5777a21c3a05cc2b71a2&ev=100",
    },
    {
        "id": "cam-construction-03",
        "name": "施工區域03",
        "area": "施工区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_10_1?expire=1843920409&id=987542205265182720&c=122083786b&t=f855cc6ab6611705e989d4ca6c57cb912560c85657966a378f95f02e17149094&ev=100",
    },
    {
        "id": "cam-guard-02",
        "name": "崗亭02",
        "area": "岗亭区域",
        "rtmp_url": "rtmp://vtmsgpzl.ezvizlife.com:1935/v3/openlive/E48203280_2_1?expire=1843920391&id=987542131204300800&c=122083786b&t=9e1647c78140a1a3ae10231bdcb773554c3bba988df2def58d7efc7bc0fb6442&ev=100",
    },
]

# YOLO 配置 — 双模型：工人PPE + 施工机械
YOLO_WORKER_MODEL = os.getenv(
    "YOLO_WORKER_MODEL",
    "E:/China Oversea  Final/VLM Detection/weights/worker/yolo26x_worker.pt",
)
YOLO_MACHINERY_MODEL = os.getenv(
    "YOLO_MACHINERY_MODEL",
    "E:/China Oversea  Final/VLM Detection/weights/machinery/yolo26l_machinery.pt",
)
YOLO_CONF_THRESHOLD = 0.45
YOLO_IMG_SIZE = 640

# 工人/PPE模型类别 (仅保留安全相关类别)
WORKER_CLASSES = [0, 1, 2, 3, 4, 5, 7]  # Hardhat, Mask, NO-Hardhat, NO-Mask, NO-Safety Vest, Person, Safety Vest
WORKER_CLASS_NAMES = {
    0: "安全帽", 1: "口罩", 2: "未戴安全帽", 3: "未戴口罩",
    4: "未穿反光衣", 5: "人员", 6: "安全锥", 7: "反光衣",
    8: "机械", 9: "电线杆", 10: "车辆",
}
# 机械模型类别
MACHINERY_CLASS_NAMES = {
    0: "挖掘机", 1: "泥头车", 2: "推土机", 3: "装载机",
    4: "流动式起重机", 5: "塔式起重机", 6: "压路机", 7: "水泥搅拌车",
}
# 高风险类别（触发VLM重点分析）
HIGH_RISK_LABELS = {"未戴安全帽", "未戴口罩", "未穿反光衣"}

# VLM 配置 (智谱 GLM-4v 视觉大模型 — glm-4.6 不支持图片输入)
VLM_BASE_URL = os.getenv("SECUREEYE_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
VLM_API_KEY = os.getenv("SECUREEYE_API_KEY", "4cb731d5cc93418caf5377642e02ee46.dqOXpohUxR4LbPFG")
VLM_MODEL = os.getenv("SECUREEYE_MODEL", "glm-4v")
VLM_TIMEOUT = int(os.getenv("SECUREEYE_TIMEOUT_SECONDS", "60"))
VLM_MAX_CONCURRENCY = int(os.getenv("SECUREEYE_MAX_CONCURRENCY", "4"))

# ffmpeg 路径 — 优先使用现代版本，回退到 EVCapture 版本
FFMPEG_BIN = os.getenv(
    "FFMPEG_BIN",
    "C:/Users/User/.workbuddy/binaries/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe",
)

# RTMP 配置
RTMP_CAPTURE_TIMEOUT = 12  # 秒，单路摄像头截帧超时
RTMP_RETRIES = 1  # 重试次数(总尝试=RETRIES+1)

# 测试图片目录 — RTMP不可用时回退到真实施工现场截图
TEST_IMAGES_DIR = os.getenv(
    "TEST_IMAGES_DIR",
    "E:/China Oversea  Final/3311 AI",
)

# 输出目录
OUTPUT_BASE = Path(os.getenv(
    "PATROL_OUTPUT_DIR",
    "E:/China Oversea  Final/FinalAgentSuite/patrol-output",
))

# EZVIZ RTMP缓存文件路径
RTMP_CACHE_PATH = OUTPUT_BASE / "ezviz_rtmp_cache.json"

# 日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("nightly_patrol")


# ─── EZVIZ RTMP 自动刷新 ────────────────────────────────────────────────────

def _load_env_for_ezviz() -> None:
    """从 .env 文件加载 EZVIZ 凭据（如果尚未在环境变量中）"""
    if os.getenv("EZVIZ_APP_KEY") and os.getenv("EZVIZ_APP_SECRET"):
        return
    env_path = Path(__file__).parent.parent / "agent-toolbox" / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key.startswith("EZVIZ_") and key not in os.environ:
                os.environ[key] = val


def _load_rtmp_cache() -> dict | None:
    """加载RTMP缓存文件"""
    if not RTMP_CACHE_PATH.exists():
        return None
    try:
        with open(RTMP_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _is_cache_valid(cache: dict, max_age: int = 6 * 24 * 3600) -> bool:
    """检查缓存是否有效（6天内刷新过）"""
    refreshed_at = cache.get("refreshed_at_unix", 0)
    if not refreshed_at:
        return False
    return (int(time.time()) - refreshed_at) < max_age


def refresh_ezviz_rtmp_urls(force: bool = False) -> bool:
    """
    通过EZVIZ开放平台API刷新全部RTMP地址

    Returns:
        True如果刷新成功，False如果失败（无凭据或API错误）
    """
    _load_env_for_ezviz()
    app_key = os.getenv("EZVIZ_APP_KEY", "")
    app_secret = os.getenv("EZVIZ_APP_SECRET", "")

    if not app_key or not app_secret:
        log.warning("未配置EZVIZ凭据(EZVIZ_APP_KEY/EZVIZ_APP_SECRET)，跳过RTMP刷新")
        log.info("获取凭据: https://open.ys7.com → 我的应用 → appKey/appSecret")
        return False

    # 检查缓存是否仍然有效
    if not force:
        cache = _load_rtmp_cache()
        if cache and _is_cache_valid(cache):
            refreshed = cache.get("refreshed_at", "?")
            log.info(f"RTMP缓存有效 (刷新于 {refreshed})，跳过刷新")
            return True

    log.info("开始刷新EZVIZ RTMP地址...")
    try:
        import httpx
        # Step 1: 获取accessToken
        resp = httpx.post(
            "https://open.ys7.com/api/lapp/token/get",
            data={"appKey": app_key, "appSecret": app_secret},
            timeout=15,
        )
        token_data = resp.json()
        if token_data.get("code") != "200":
            log.error(f"获取accessToken失败: {token_data.get('msg')}")
            return False

        access_token = token_data["data"]["accessToken"]
        expire_time = token_data["data"].get("expireTime", 0)
        log.info(f"  accessToken获取成功, 有效期至: "
                 f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expire_time))}")

        # Step 2: 获取每路摄像头的RTMP地址
        device_serial = os.getenv("EZVIZ_DEVICE_SERIAL", "E48203280")
        # 从CAMERAS列表提取通道号（解析URL路径中的 {serial}_{ch}_{quality}）
        import re
        cameras_data = []
        success = 0
        for cam in CAMERAS:
            url = cam["rtmp_url"]
            # 从URL路径提取通道号和质量
            match = re.search(rf"{device_serial}_(\d+)_(\d+)", url)
            if not match:
                log.warning(f"  {cam['id']}: 无法从URL提取通道号, 保留旧URL")
                cameras_data.append({**cam, "rtmp_url": url})
                continue
            channel_no = int(match.group(1))
            quality = int(match.group(2))

            try:
                resp = httpx.post(
                    "https://open.ys7.com/api/lapp/v2/live/address/get",
                    data={
                        "accessToken": access_token,
                        "deviceSerial": device_serial,
                        "channelNo": channel_no,
                        "protocol": 3,  # RTMP
                        "quality": quality,
                        "expireTime": 30 * 24 * 3600,  # 30天
                    },
                    timeout=15,
                )
                addr_data = resp.json()
                if addr_data.get("code") != "200":
                    log.warning(f"  {cam['id']} (ch={channel_no}): {addr_data.get('msg')}")
                    cameras_data.append({**cam, "rtmp_url": url})  # 保留旧URL
                    continue
                new_url = addr_data["data"].get("url", "")
                if new_url:
                    cameras_data.append({**cam, "rtmp_url": new_url})
                    success += 1
                    log.info(f"  {cam['id']} (ch={channel_no}): RTMP地址已更新")
                else:
                    cameras_data.append({**cam, "rtmp_url": url})
                    log.warning(f"  {cam['id']} (ch={channel_no}): 返回空URL, 保留旧URL")
            except Exception as e:
                log.warning(f"  {cam['id']} (ch={channel_no}): {e}")
                cameras_data.append({**cam, "rtmp_url": url})

        # Step 3: 保存缓存
        cache = {
            "refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "refreshed_at_unix": int(time.time()),
            "device_serial": device_serial,
            "access_token_expire": expire_time,
            "cameras": cameras_data,
            "summary": {"total": len(CAMERAS), "success": success, "fail": len(CAMERAS) - success},
        }
        RTMP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(RTMP_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        log.info(f"RTMP刷新完成: {success}/{len(CAMERAS)} 成功, 缓存已保存")
        return success > 0

    except Exception as e:
        log.error(f"RTMP刷新异常: {e}")
        return False


def get_cameras_with_fresh_rtmp() -> list[dict[str, str]]:
    """
    获取摄像头列表，优先使用EZVIZ缓存的最新RTMP地址

    优先级:
    1. EZVIZ缓存（如果有效）
    2. 硬编码的CAMERAS列表（回退）
    """
    cache = _load_rtmp_cache()
    if cache and _is_cache_valid(cache):
        cached_cameras = cache.get("cameras", [])
        if cached_cameras:
            # 用缓存中的URL更新CAMERAS列表
            url_map = {c["id"]: c.get("rtmp_url", "") for c in cached_cameras if c.get("rtmp_url")}
            if url_map:
                refreshed = cache.get("refreshed_at", "?")
                log.info(f"使用EZVIZ缓存RTMP地址 (刷新于 {refreshed}, {len(url_map)}路)")
                return [
                    {**cam, "rtmp_url": url_map.get(cam["id"], cam["rtmp_url"])}
                    for cam in CAMERAS
                ]
    return CAMERAS


# ─── 数据结构 ─────────────────────────────────────────────────────────────────

@dataclass
class Detection:
    bbox: list[float]  # [x1, y1, x2, y2]
    label: str
    confidence: float
    source: str = "yolo"  # "yolo" | "vlm" | "hybrid"
    description: str = ""
    severity: str = ""  # "low" | "medium" | "high" | "critical"
    suggested_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "bbox": self.bbox,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "description": self.description,
            "severity": self.severity,
            "suggested_action": self.suggested_action,
        }


@dataclass
class CameraResult:
    camera_id: str
    camera_name: str
    area: str
    success: bool
    snapshot_path: str | None = None
    annotated_path: str | None = None
    detections: list[Detection] = field(default_factory=list)
    error: str = ""
    yolo_time_ms: int = 0
    vlm_time_ms: int = 0
    source_mix: str = "yolo"  # "yolo" | "vlm" | "hybrid"

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "area": self.area,
            "success": self.success,
            "snapshot_path": self.snapshot_path,
            "annotated_path": self.annotated_path,
            "detection_count": len(self.detections),
            "detections": [d.to_dict() for d in self.detections],
            "error": self.error,
            "yolo_time_ms": self.yolo_time_ms,
            "vlm_time_ms": self.vlm_time_ms,
            "source_mix": self.source_mix,
        }


# ─── 测试图片回退 ──────────────────────────────────────────────────────────────

_test_images_cache: list[Path] | None = None


def get_test_images() -> list[Path]:
    """获取测试图片列表（RTMP不可用时回退）"""
    global _test_images_cache
    if _test_images_cache is None:
        test_dir = Path(TEST_IMAGES_DIR)
        if test_dir.exists():
            _test_images_cache = sorted(test_dir.glob("*.jpg"))
        else:
            _test_images_cache = []
    return _test_images_cache


def get_fallback_test_image(camera_index: int) -> Path | None:
    """根据摄像头索引获取回退测试图片"""
    images = get_test_images()
    if not images:
        return None
    return images[camera_index % len(images)]


# ─── 中文字体支持 ──────────────────────────────────────────────────────────────

_chinese_font = None


def get_chinese_font(size: int = 20):
    """加载支持中文的字体"""
    global _chinese_font
    if _chinese_font is None:
        from PIL import ImageFont
        # 尝试常见中文字体路径
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",    # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",   # 黑体
            "C:/Windows/Fonts/simsun.ttc",   # 宋体
            "C:/Windows/Fonts/Deng.ttf",     # 等线
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                _chinese_font = ImageFont.truetype(fp, size)
                break
        if _chinese_font is None:
            _chinese_font = ImageFont.load_default()
    return _chinese_font


# ─── RTMP 截帧 (使用 ffmpeg subprocess) ────────────────────────────────────────

def capture_rtmp_frame(rtmp_url: str, output_path: Path, timeout: int = RTMP_CAPTURE_TIMEOUT) -> bool:
    """用 ffmpeg subprocess 从 RTMP 流截取一帧"""
    import subprocess

    for attempt in range(RTMP_RETRIES + 1):
        try:
            cmd = [
                FFMPEG_BIN,
                "-y",
                "-rtmp_live", "live",
                "-rw_timeout", str(timeout * 1000000),  # microseconds
                "-i", rtmp_url,
                "-frames:v", "1",
                "-q:v", "2",
                str(output_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 5,
            )
            if output_path.exists() and output_path.stat().st_size > 1000:
                return True
            log.warning(f"  ffmpeg attempt {attempt+1}/{RTMP_RETRIES+1} failed, rc={result.returncode}")
            if result.stderr:
                # Show last useful line
                lines = [l for l in result.stderr.strip().split("\n") if l.strip()]
                if lines:
                    log.warning(f"  ffmpeg: {lines[-1][:120]}")
        except subprocess.TimeoutExpired:
            log.warning(f"  ffmpeg attempt {attempt+1}/{RTMP_RETRIES+1} timed out ({timeout}s)")
        except Exception as e:
            log.warning(f"  ffmpeg attempt {attempt+1}/{RTMP_RETRIES+1} error: {e}")

        if attempt < RTMP_RETRIES:
            time.sleep(2)

    return False


# ─── YOLO 检测 ──────────────────────────────────────────────────────────────────

_worker_model = None
_machinery_model = None


def get_yolo_models():
    """懒加载双模型：工人PPE + 施工机械"""
    global _worker_model, _machinery_model
    if _worker_model is None:
        from ultralytics import YOLO
        log.info(f"加载工人/PPE模型: {YOLO_WORKER_MODEL}")
        _worker_model = YOLO(YOLO_WORKER_MODEL)
        log.info(f"加载施工机械模型: {YOLO_MACHINERY_MODEL}")
        _machinery_model = YOLO(YOLO_MACHINERY_MODEL)
    return _worker_model, _machinery_model


def run_yolo_detection(image_path: str) -> list[Detection]:
    """运行双模型 YOLO 检测：工人PPE + 施工机械"""
    worker_model, machinery_model = get_yolo_models()
    detections: list[Detection] = []

    # 1. 工人/PPE 检测
    w_results = worker_model.predict(
        image_path, conf=YOLO_CONF_THRESHOLD, imgsz=YOLO_IMG_SIZE,
        classes=WORKER_CLASSES, verbose=False,
    )
    if w_results and w_results[0].boxes is not None:
        for xyxy, conf, cls_id in zip(
            w_results[0].boxes.xyxy.tolist(),
            w_results[0].boxes.conf.tolist(),
            w_results[0].boxes.cls.tolist(),
        ):
            cid = int(cls_id)
            label_zh = WORKER_CLASS_NAMES.get(cid, str(cid))
            x1, y1, x2, y2 = (float(v) for v in xyxy)
            detections.append(Detection(
                bbox=[round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                label=label_zh,
                confidence=float(conf),
                source="yolo",
            ))

    # 2. 施工机械检测
    m_results = machinery_model.predict(
        image_path, conf=YOLO_CONF_THRESHOLD, imgsz=YOLO_IMG_SIZE,
        verbose=False,
    )
    if m_results and m_results[0].boxes is not None:
        for xyxy, conf, cls_id in zip(
            m_results[0].boxes.xyxy.tolist(),
            m_results[0].boxes.conf.tolist(),
            m_results[0].boxes.cls.tolist(),
        ):
            cid = int(cls_id)
            label_zh = MACHINERY_CLASS_NAMES.get(cid, str(cid))
            x1, y1, x2, y2 = (float(v) for v in xyxy)
            detections.append(Detection(
                bbox=[round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
                label=label_zh,
                confidence=float(conf),
                source="yolo",
            ))

    return detections


# ─── ROI 裁剪 ─────────────────────────────────────────────────────────────────

def crop_roi(image_path: str, bbox: list[float], padding_ratio: float = 0.15, target_size: int = 640) -> str:
    """从原图按 bbox 裁剪 ROI 区域，四周 pad，resize，返回 base64"""
    img = Image.open(image_path).convert("RGB")  # 强制转RGB，避免RGBA图片无法保存为JPEG
    w, h = img.size
    x1, y1, x2, y2 = bbox

    # 计算 padding
    bw = x2 - x1
    bh = y2 - y1
    pad_x = bw * padding_ratio
    pad_y = bh * padding_ratio

    # 扩展并裁剪到边界
    cx1 = max(0, int(x1 - pad_x))
    cy1 = max(0, int(y1 - pad_y))
    cx2 = min(w, int(x2 + pad_x))
    cy2 = min(h, int(y2 + pad_y))

    cropped = img.crop((cx1, cy1, cx2, cy2))
    cropped = cropped.resize((target_size, target_size), Image.LANCZOS)

    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ─── VLM 大模型调用 ────────────────────────────────────────────────────────────

def build_vlm_prompt(label: str, context: str = "") -> str:
    ctx = f"摄像头位置: {context}。" if context else ""
    return (
        f"你是工地安全监控专家。{ctx}"
        f"YOLO小模型检测到的目标类别为: {label}。\n"
        f"请基于图中实际情况分析该区域的安全状况：\n"
        f"1. 确认目标是否真实存在及状态\n"
        f"2. 判断是否存在安全隐患(如未佩戴PPE、机械违规操作等)\n"
        f"3. 评估风险等级并给出处置建议\n"
        f"请严格按JSON格式返回，不要有多余文字:\n"
        f'{{"description": "简要描述画面内容和安全状况(中文)", '
        f'"severity": "low|medium|high|critical", '
        f'"suggested_action": "处置建议(中文)"}}'
    )


def _parse_vlm_json(text: str) -> dict[str, str]:
    """从 LLM 返回文本中提取 JSON"""
    import re
    text = text.strip()

    # 直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 从 markdown 代码块提取
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 正则匹配 JSON 结构
    m = re.search(r'\{[^{}]*"description"[^{}]*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # fallback
    return {
        "description": text[:200] if text else "VLM返回解析失败",
        "severity": "medium",
        "suggested_action": "建议人工复核",
    }


async def call_vlm_api(base64_image: str, prompt: str) -> dict[str, str]:
    """调用智谱 GLM-4.6 VLM API"""
    url = f"{VLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {VLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }
        ],
        "temperature": 0.3,
        "max_tokens": 300,
    }

    async with httpx.AsyncClient(timeout=VLM_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return _parse_vlm_json(content)


async def vlm_enhance_batch(
    image_path: str,
    detections: list[Detection],
    context: str = "",
) -> list[Detection]:
    """对 YOLO 检测结果批量调 VLM 增强"""
    if not detections:
        return detections

    semaphore = asyncio.Semaphore(VLM_MAX_CONCURRENCY)
    results: list[Detection] = []

    async def enhance_one(idx: int) -> Detection:
        det = detections[idx]
        try:
            async with semaphore:
                b64 = crop_roi(image_path, det.bbox)
                prompt = build_vlm_prompt(det.label, context)
                vlm_result = await call_vlm_api(b64, prompt)

            return Detection(
                bbox=det.bbox,
                label=det.label,
                confidence=det.confidence,
                source="hybrid",
                description=vlm_result.get("description", ""),
                severity=vlm_result.get("severity", "medium"),
                suggested_action=vlm_result.get("suggested_action", ""),
            )
        except Exception as e:
            log.warning(f"  VLM增强失败 [{det.label}]: {e}")
            return Detection(
                bbox=det.bbox,
                label=det.label,
                confidence=det.confidence,
                source="yolo",
                description="VLM增强失败，保留YOLO原始结果",
                severity="medium",
                suggested_action="建议人工复核",
            )

    tasks = [enhance_one(i) for i in range(len(detections))]
    results = await asyncio.gather(*tasks)
    return list(results)


# ─── 图像标注 ─────────────────────────────────────────────────────────────────

SEVERITY_COLORS = {
    "critical": (0, 0, 255),    # 红
    "high": (0, 102, 255),      # 橙
    "medium": (0, 255, 255),    # 黄
    "low": (0, 255, 102),       # 绿
    "": (128, 128, 128),        # 灰
}

# 中文字体 (PIL)
_zh_font = None
_zh_font_small = None

def _get_zh_font(size: int = 22):
    global _zh_font, _zh_font_small
    if _zh_font is None or _zh_font_small is None:
        from PIL import ImageFont
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "C:/Windows/Fonts/simsun.ttc",     # 宋体
        ]
        font_path = None
        for fp in font_paths:
            if os.path.exists(fp):
                font_path = fp
                break
        if font_path:
            _zh_font = ImageFont.truetype(font_path, size)
            _zh_font_small = ImageFont.truetype(font_path, 16)
        else:
            _zh_font = ImageFont.load_default()
            _zh_font_small = ImageFont.load_default()
    return _zh_font if size >= 20 else _zh_font_small


def draw_annotations(image_path: str, detections: list[Detection], output_path: str, camera_name: str):
    """在图片上绘制检测框和标签（支持中文）"""
    from PIL import Image as PILImage, ImageDraw as PILDraw, ImageFont

    img = PILImage.open(image_path).convert("RGB")
    draw = PILDraw.Draw(img)
    font = _get_zh_font(22)
    font_small = _get_zh_font(16)

    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det.bbox]
        # PIL颜色用RGB, OpenCV用BGR
        severity_bgr = SEVERITY_COLORS.get(det.severity, (128, 128, 128))
        color_rgb = (severity_bgr[2], severity_bgr[1], severity_bgr[0])

        # 画框
        thickness = 4 if det.severity in ("high", "critical") else 3
        for t in range(thickness):
            draw.rectangle([x1-t, y1-t, x2+t, y2+t], outline=color_rgb)

        # 标签文本
        label_parts = [det.label, f"{det.confidence:.0%}"]
        if det.source == "hybrid":
            label_parts.append(f"[{det.severity}]")
        label_text = " ".join(label_parts)

        # 标签背景
        bbox = draw.textbbox((0, 0), label_text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.rectangle([x1, y1 - th - 8, x1 + tw + 8, y1], fill=color_rgb)
        draw.text((x1 + 4, y1 - th - 6), label_text, fill=(255, 255, 255), font=font)

        # VLM描述（如果有）
        if det.description and det.source == "hybrid":
            desc = det.description[:60]
            if det.suggested_action:
                desc += f" | 建议: {det.suggested_action[:40]}"
            bbox2 = draw.textbbox((0, 0), desc, font=font_small)
            dw, dh = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
            draw.rectangle([x1, y2 + 2, x1 + dw + 8, y2 + dh + 8], fill=color_rgb)
            draw.text((x1 + 4, y2 + 4), desc, fill=(255, 255, 255), font=font_small)

    # 顶部信息栏
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    info = f"[{camera_name}] {timestamp} | 检测目标: {len(detections)}个"
    info_bbox = draw.textbbox((0, 0), info, font=font)
    iw, ih = info_bbox[2] - info_bbox[0], info_bbox[3] - info_bbox[1]
    draw.rectangle([0, 0, img.size[0], ih + 12], fill=(0, 0, 0))
    draw.text((10, 4), info, fill=(255, 255, 255), font=font)

    # 底部模型信息
    model_info = f"YOLO双模型(工人PPE+机械) + VLM({VLM_MODEL}) | 阈值:{YOLO_CONF_THRESHOLD}"
    mi_bbox = draw.textbbox((0, 0), model_info, font=font_small)
    mw, mh = mi_bbox[2] - mi_bbox[0], mi_bbox[3] - mi_bbox[1]
    draw.rectangle([0, img.size[1] - mh - 8, img.size[0], img.size[1]], fill=(0, 0, 0))
    draw.text((10, img.size[1] - mh - 6), model_info, fill=(200, 200, 200), font=font_small)

    img.save(output_path, "JPEG", quality=92)


# ─── 主巡检流程 ────────────────────────────────────────────────────────────────

def _get_test_image_fallback(cam_id: str) -> str | None:
    """RTMP不可用时，从本地真实施工现场截图中选一张作为回退"""
    test_dir = Path(TEST_IMAGES_DIR)
    if not test_dir.exists():
        return None
    images = sorted(test_dir.glob("*.jpg"))
    if not images:
        return None
    # 用cam_id的确定性hash选图，确保每次同一摄像头选同一张
    import hashlib
    idx = int(hashlib.md5(cam_id.encode()).hexdigest(), 16) % len(images)
    return str(images[idx])


async def patrol_camera(camera: dict[str, str], output_dir: Path, vlm_enabled: bool = True) -> CameraResult:
    """巡检单路摄像头"""
    cam_id = camera["id"]
    cam_name = camera["name"]
    area = camera["area"]
    log.info(f"=== 巡检摄像头: {cam_name} ({cam_id}) ===")

    result = CameraResult(camera_id=cam_id, camera_name=cam_name, area=area, success=False)

    # 1. RTMP 截帧
    snapshot_path = output_dir / f"{cam_id}_snapshot.jpg"
    log.info(f"  截帧中... (超时{RTMP_CAPTURE_TIMEOUT}s)")
    rtmp_ok = capture_rtmp_frame(camera["rtmp_url"], snapshot_path)

    if not rtmp_ok:
        # 回退到本地测试图片
        log.warning(f"  RTMP截帧失败，尝试本地回退...")
        test_img = _get_test_image_fallback(cam_id)
        if test_img:
            import shutil
            shutil.copy2(test_img, str(snapshot_path))
            result.error = f"RTMP不可用，使用本地回退图: {Path(test_img).name}"
            log.info(f"  ✓ 本地回退: {Path(test_img).name}")
        else:
            result.error = "RTMP截帧失败且无本地回退图"
            log.warning(f"  ✗ {result.error}")
            return result
    else:
        log.info(f"  ✓ RTMP截帧成功: {snapshot_path.name}")

    result.snapshot_path = str(snapshot_path)

    # 2. YOLO 检测
    t0 = time.perf_counter()
    try:
        detections = run_yolo_detection(str(snapshot_path))
    except Exception as e:
        result.error = f"YOLO检测失败: {e}"
        log.warning(f"  ✗ {result.error}")
        return result
    result.yolo_time_ms = int((time.perf_counter() - t0) * 1000)
    log.info(f"  ✓ YOLO检测: {len(detections)}个目标 ({result.yolo_time_ms}ms)")

    # 3. VLM 增强（如果开启且有检测到目标）
    if vlm_enabled and detections:
        t0 = time.perf_counter()
        try:
            detections = await vlm_enhance_batch(str(snapshot_path), detections, context=cam_name)
            hybrid_count = sum(1 for d in detections if d.source == "hybrid")
            result.source_mix = "hybrid" if hybrid_count > 0 else "yolo"
            log.info(f"  ✓ VLM增强: {hybrid_count}/{len(detections)} 成功")
        except Exception as e:
            log.warning(f"  ✗ VLM增强整体失败: {e}")
            result.source_mix = "yolo"
        result.vlm_time_ms = int((time.perf_counter() - t0) * 1000)
    elif vlm_enabled and not detections:
        log.info(f"  - 无检测目标，跳过VLM")
    else:
        result.source_mix = "yolo"

    result.detections = detections

    # 4. 绘制标注图
    annotated_path = output_dir / f"{cam_id}_annotated.jpg"
    draw_annotations(str(snapshot_path), detections, str(annotated_path), cam_name)
    result.annotated_path = str(annotated_path)
    log.info(f"  ✓ 标注图已保存: {annotated_path.name}")

    result.success = True
    return result


async def run_patrol(vlm_enabled: bool = True, camera_filter: str | None = None) -> dict[str, Any]:
    """执行完整巡检"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_BASE / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    cameras = get_cameras_with_fresh_rtmp()
    if camera_filter:
        cameras = [c for c in cameras if c["id"] == camera_filter or c["name"] == camera_filter]
        if not cameras:
            log.error(f"未找到摄像头: {camera_filter}")
            return {"error": f"Camera not found: {camera_filter}"}

    log.info(f"═══ 赤瞳守护者夜间巡检启动 ═══")
    log.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"摄像头数量: {len(cameras)}")
    log.info(f"VLM增强: {'开启' if vlm_enabled else '关闭'} (模型: {VLM_MODEL})")
    log.info(f"YOLO置信度阈值: {YOLO_CONF_THRESHOLD}")
    log.info(f"输出目录: {output_dir}")
    log.info(f"═══════════════════════════════")

    results: list[CameraResult] = []
    for camera in cameras:
        result = await patrol_camera(camera, output_dir, vlm_enabled=vlm_enabled)
        results.append(result)

    # 汇总
    success_count = sum(1 for r in results if r.success)
    total_detections = sum(len(r.detections) for r in results)
    hybrid_count = sum(1 for r in results if r.source_mix == "hybrid")
    high_risk = sum(
        1 for r in results for d in r.detections
        if d.severity in ("high", "critical")
    )

    summary = {
        "patrol_id": timestamp,
        "timestamp": datetime.now().isoformat(),
        "camera_count": len(cameras),
        "success_count": success_count,
        "fail_count": len(cameras) - success_count,
        "total_detections": total_detections,
        "hybrid_cameras": hybrid_count,
        "high_risk_count": high_risk,
        "vlm_enabled": vlm_enabled,
        "vlm_model": VLM_MODEL if vlm_enabled else None,
        "yolo_model": "dual(worker+machinery)",
        "yolo_conf_threshold": YOLO_CONF_THRESHOLD,
        "cameras": [r.to_dict() for r in results],
    }

    # 保存 JSON 报告
    report_path = output_dir / "patrol_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 保存文本摘要
    summary_path = output_dir / "summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"赤瞳守护者巡检报告\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"摄像头总数: {len(cameras)}\n")
        f.write(f"成功巡检: {success_count}\n")
        f.write(f"失败: {len(cameras) - success_count}\n")
        f.write(f"总检测目标: {total_detections}\n")
        f.write(f"高风险目标: {high_risk}\n")
        f.write(f"VLM增强: {'开启' if vlm_enabled else '关闭'}\n\n")

        for r in results:
            status = "✓" if r.success else "✗"
            f.write(f"[{status}] {r.camera_name} ({r.camera_id})\n")
            if r.error:
                f.write(f"    错误: {r.error}\n")
            else:
                f.write(f"    检测目标: {len(r.detections)} | 来源: {r.source_mix}\n")
                f.write(f"    YOLO耗时: {r.yolo_time_ms}ms | VLM耗时: {r.vlm_time_ms}ms\n")
                for d in r.detections:
                    sev_tag = f" [{d.severity}]" if d.severity else ""
                    f.write(f"    - {d.label} ({d.confidence:.0%}){sev_tag} <{d.source}>\n")
                    if d.description:
                        f.write(f"      描述: {d.description}\n")
                    if d.suggested_action:
                        f.write(f"      建议: {d.suggested_action}\n")
            f.write("\n")

    log.info(f"═══ 巡检完成 ═══")
    log.info(f"成功: {success_count}/{len(cameras)} | 检测目标: {total_detections} | 高风险: {high_risk}")
    log.info(f"报告: {report_path}")
    log.info(f"摘要: {summary_path}")
    log.info(f"输出目录: {output_dir}")
    log.info(f"═══════════════")

    return summary


# ─── CLI 入口 ──────────────────────────────────────────────────────────────────

def run_single_patrol(vlm_enabled: bool, camera_filter: str | None) -> dict[str, Any]:
    """执行一次完整巡检"""
    return asyncio.run(run_patrol(vlm_enabled=vlm_enabled, camera_filter=camera_filter))


def main():
    import argparse
    parser = argparse.ArgumentParser(description="赤瞳守护者夜间巡检")
    parser.add_argument("--camera", type=str, default=None, help="只巡检指定摄像头(id或名称)")
    parser.add_argument("--yolo-only", action="store_true", help="仅YOLO检测，不调VLM")
    parser.add_argument("--loop", action="store_true", help="每2小时自动巡检(后台持续运行)")
    parser.add_argument("--interval", type=int, default=7200, help="循环间隔秒数(默认7200=2小时)")
    parser.add_argument("--refresh-rtmp", action="store_true", help="强制刷新EZVIZ RTMP地址后巡检")
    args = parser.parse_args()

    vlm_enabled = not args.yolo_only

    # 强制刷新RTMP地址
    if args.refresh_rtmp:
        refresh_ezviz_rtmp_urls(force=True)

    if args.loop:
        log.info(f"═══ 循环巡检模式启动 (间隔{args.interval}秒) ═══")
        round_num = 0
        while True:
            round_num += 1
            log.info(f"━━━ 第 {round_num} 轮巡检开始 ━━━")
            # 每轮巡检前尝试刷新RTMP地址（如果缓存过期）
            if round_num > 1:
                refresh_ezviz_rtmp_urls(force=False)
            try:
                summary = run_single_patrol(vlm_enabled, args.camera)
                log.info(f"第 {round_num} 轮完成: 成功{summary.get('success_count',0)}/"
                         f"{summary.get('camera_count',0)}, 检测{summary.get('total_detections',0)}个目标")
            except Exception as e:
                log.error(f"第 {round_num} 轮巡检异常: {e}", exc_info=True)

            next_time = datetime.now().strftime("%H:%M:%S")
            log.info(f"下次巡检: {args.interval}秒后 (约 {datetime.now().replace(microsecond=0)} + {args.interval}s)")
            time.sleep(args.interval)
    else:
        summary = run_single_patrol(vlm_enabled, args.camera)
        # 退出码：有失败则返回1
        if summary.get("fail_count", 0) > 0 and summary.get("success_count", 0) == 0:
            sys.exit(1)
        sys.exit(0)


if __name__ == "__main__":
    main()
