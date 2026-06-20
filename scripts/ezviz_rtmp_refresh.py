#!/usr/bin/env python3
"""
EZVIZ (萤石云) RTMP地址自动刷新工具

RTMP流地址中的token(t=...)会被萤石云服务端定期作废（即使expire未过期）。
本脚本通过萤石云开放平台API自动获取新的accessToken，然后为每路摄像头
重新生成RTMP直播地址。

使用方法:
    # 设置环境变量（或在 .env 中配置）
    export EZVIZ_APP_KEY=your_app_key
    export EZVIZ_APP_SECRET=your_app_secret

    # 刷新全部11路RTMP地址
    python ezviz_rtmp_refresh.py

    # 刷新并测试连通性
    python ezviz_rtmp_refresh.py --test

    # 刷新并输出到指定文件
    python ezviz_rtmp_refresh.py --output rtmp_cache.json

前置条件:
    1. 在 https://open.ys7.com 注册开发者账号
    2. 创建应用获取 appKey 和 appSecret
    3. 确保设备 E48203280 已绑定到该应用
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# ─── 配置 ───────────────────────────────────────────────────────────────────

EZVIZ_API_BASE = "https://open.ys7.com"
EZVIZ_TOKEN_GET = f"{EZVIZ_API_BASE}/api/lapp/token/get"
EZVIZ_LIVE_ADDR_GET = f"{EZVIZ_API_BASE}/api/lapp/v2/live/address/get"

# 设备序列号（从RTMP URL路径 v3/openlive/{serial}_{ch}_{quality} 提取）
DEVICE_SERIAL = os.getenv("EZVIZ_DEVICE_SERIAL", "E48203280")

# 11路摄像头通道映射（channel → camera_id）
# 格式: (channel_no, quality, camera_id, camera_name, area)
CHANNEL_MAP = [
    (6, 1, "cam-slope-03", "斜坡03", "斜坡区域"),
    (7, 2, "cam-slope-container-01", "斜坡貨櫃01", "斜坡区域"),
    (3, 1, "cam-guard-03", "崗亭03", "岗亭区域"),
    (9, 1, "cam-construction-01", "施工區域01", "施工区域"),
    (11, 1, "cam-construction-02", "施工區域02", "施工区域"),
    (1, 1, "cam-guard-01", "崗亭01", "岗亭区域"),
    (4, 1, "cam-slope-top-intersection", "坡頂T字路口", "斜坡区域"),
    (5, 1, "cam-slope-02", "斜坡02", "斜坡区域"),
    (8, 1, "cam-slope-04", "斜坡04", "斜坡区域"),
    (10, 1, "cam-construction-03", "施工區域03", "施工区域"),
    (2, 1, "cam-guard-02", "崗亭02", "岗亭区域"),
]

# 默认缓存文件路径
DEFAULT_CACHE_PATH = Path(__file__).parent.parent / "patrol-output" / "ezviz_rtmp_cache.json"

# accessToken 有效期7天，缓存6天后自动刷新
CACHE_MAX_AGE_SECONDS = 6 * 24 * 3600  # 6天

# RTMP地址有效期（秒），30秒~720天
RTMP_EXPIRE_SECONDS = 30 * 24 * 3600  # 30天


def load_env_file() -> None:
    """从 .env 文件加载环境变量（如果存在）"""
    env_paths = [
        Path(__file__).parent.parent / "agent-toolbox" / ".env",
        Path(__file__).parent / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if not env_path.exists():
            continue
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val


def get_access_token(app_key: str, app_secret: str) -> dict:
    """
    调用萤石云API获取accessToken

    Returns:
        {"accessToken": "at.xxx", "expireTime": 1234567890, "areaDomain": "xxx"}
    Raises:
        RuntimeError: API调用失败
    """
    resp = httpx.post(
        EZVIZ_TOKEN_GET,
        data={"appKey": app_key, "appSecret": app_secret},
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != "200":
        raise RuntimeError(
            f"获取accessToken失败: code={data.get('code')}, msg={data.get('msg')}"
        )
    token_data = data["data"]
    print(f"  [OK] accessToken获取成功, 有效期至: "
          f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(token_data['expireTime']))}")
    return token_data


def get_rtmp_url(
    access_token: str,
    device_serial: str,
    channel_no: int,
    quality: int = 1,
    expire_seconds: int = RTMP_EXPIRE_SECONDS,
) -> str:
    """
    获取单路摄像头的RTMP直播地址

    Args:
        access_token: 萤石云accessToken
        device_serial: 设备序列号
        channel_no: 通道号
        quality: 1=高清(主码流), 2=流畅(子码流)
        expire_seconds: 地址有效期(秒), 30s~720天

    Returns:
        RTMP URL字符串
    Raises:
        RuntimeError: API调用失败
    """
    resp = httpx.post(
        EZVIZ_LIVE_ADDR_GET,
        data={
            "accessToken": access_token,
            "deviceSerial": device_serial,
            "channelNo": channel_no,
            "protocol": 3,  # 3=RTMP
            "quality": quality,
            "expireTime": expire_seconds,
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("code") != "200":
        raise RuntimeError(
            f"获取RTMP地址失败(ch={channel_no}): code={data.get('code')}, msg={data.get('msg')}"
        )
    url = data["data"].get("url", "")
    if not url:
        raise RuntimeError(f"RTMP地址为空(ch={channel_no})")
    return url


def test_rtmp_url(rtmp_url: str, timeout: int = 10) -> bool:
    """用ffmpeg测试RTMP地址是否可连通"""
    import subprocess

    ffmpeg = os.getenv(
        "FFMPEG_PATH",
        "C:/Users/User/.workbuddy/binaries/ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe",
    )
    try:
        result = subprocess.run(
            [ffmpeg, "-y", "-rtmp_live", "live", "-i", rtmp_url,
             "-frames:v", "1", "-f", "null", "-"],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def refresh_all_rtmp_urls(
    app_key: str,
    app_secret: str,
    test_connectivity: bool = False,
) -> dict:
    """
    刷新全部11路摄像头的RTMP地址

    Returns:
        {
            "refreshed_at": "2026-06-20T08:00:00",
            "device_serial": "E48203280",
            "access_token_expire": 1234567890,
            "cameras": [
                {"id": "cam-slope-03", "name": "斜坡03", "area": "斜坡区域",
                 "channel": 6, "quality": 1, "rtmp_url": "rtmp://..."},
                ...
            ]
        }
    """
    print("=" * 60)
    print("EZVIZ RTMP地址刷新")
    print("=" * 60)

    # Step 1: 获取accessToken
    print(f"\n[1/3] 获取accessToken (appKey={app_key[:6]}...)")
    token_data = get_access_token(app_key, app_secret)
    access_token = token_data["accessToken"]

    # Step 2: 获取每路摄像头的RTMP地址
    print(f"\n[2/3] 获取RTMP地址 (设备: {DEVICE_SERIAL}, 共{len(CHANNEL_MAP)}路)")
    cameras = []
    success_count = 0
    fail_count = 0

    for channel_no, quality, cam_id, cam_name, area in CHANNEL_MAP:
        try:
            rtmp_url = get_rtmp_url(
                access_token, DEVICE_SERIAL, channel_no, quality
            )
            cameras.append({
                "id": cam_id,
                "name": cam_name,
                "area": area,
                "channel": channel_no,
                "quality": quality,
                "rtmp_url": rtmp_url,
            })
            success_count += 1
            print(f"  [{success_count}/{len(CHANNEL_MAP)}] {cam_id} (ch={channel_no}) OK")
        except RuntimeError as e:
            fail_count += 1
            print(f"  [FAIL] {cam_id} (ch={channel_no}): {e}")
            # 仍然加入列表，但URL为空
            cameras.append({
                "id": cam_id,
                "name": cam_name,
                "area": area,
                "channel": channel_no,
                "quality": quality,
                "rtmp_url": "",
                "error": str(e),
            })

    # Step 3: 测试连通性（可选）
    if test_connectivity:
        print(f"\n[3/3] 测试RTMP连通性")
        for cam in cameras:
            if not cam["rtmp_url"]:
                print(f"  {cam['id']}: SKIP (无URL)")
                continue
            ok = test_rtmp_url(cam["rtmp_url"])
            cam["tested"] = ok
            status = "OK" if ok else "FAIL"
            print(f"  {cam['id']}: {status}")

    result = {
        "refreshed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "refreshed_at_unix": int(time.time()),
        "device_serial": DEVICE_SERIAL,
        "access_token_expire": token_data.get("expireTime"),
        "access_token_area_domain": token_data.get("areaDomain", ""),
        "cameras": cameras,
        "summary": {
            "total": len(CHANNEL_MAP),
            "success": success_count,
            "fail": fail_count,
        },
    }

    print(f"\n刷新完成: {success_count}/{len(CHANNEL_MAP)} 成功, {fail_count} 失败")
    return result


def save_cache(data: dict, cache_path: Path) -> None:
    """保存刷新结果到缓存文件"""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"缓存已保存: {cache_path}")


def load_cache(cache_path: Path) -> dict | None:
    """加载缓存文件，返回None如果不存在或损坏"""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_cache_valid(cache: dict, max_age: int = CACHE_MAX_AGE_SECONDS) -> bool:
    """检查缓存是否仍然有效（未过期）"""
    if not cache:
        return False
    refreshed_at = cache.get("refreshed_at_unix", 0)
    if not refreshed_at:
        return False
    age = int(time.time()) - refreshed_at
    return age < max_age


def get_cached_rtmp_urls(cache_path: Path | None = None) -> dict[str, str] | None:
    """
    从缓存文件读取RTMP URL映射

    Returns:
        {camera_id: rtmp_url} 字典，如果缓存无效返回None
    """
    cache_path = cache_path or DEFAULT_CACHE_PATH
    cache = load_cache(cache_path)
    if not cache or not is_cache_valid(cache):
        return None

    result = {}
    for cam in cache.get("cameras", []):
        if cam.get("rtmp_url"):
            result[cam["id"]] = cam["rtmp_url"]
    return result if result else None


def main() -> int:
    parser = argparse.ArgumentParser(description="EZVIZ RTMP地址自动刷新")
    parser.add_argument("--test", action="store_true", help="刷新后测试RTMP连通性")
    parser.add_argument("--output", type=Path, default=None, help="缓存文件输出路径")
    parser.add_argument("--force", action="store_true", help="强制刷新，即使缓存未过期")
    args = parser.parse_args()

    load_env_file()

    app_key = os.getenv("EZVIZ_APP_KEY", "")
    app_secret = os.getenv("EZVIZ_APP_SECRET", "")

    if not app_key or not app_secret:
        print("ERROR: 未配置EZVIZ凭据")
        print()
        print("请在以下位置之一设置环境变量:")
        print("  1. agent-toolbox/.env 文件中添加:")
        print("     EZVIZ_APP_KEY=你的appKey")
        print("     EZVIZ_APP_SECRET=你的appSecret")
        print("  2. 或设置环境变量:")
        print("     export EZVIZ_APP_KEY=xxx")
        print("     export EZVIZ_APP_SECRET=xxx")
        print()
        print("获取appKey/appSecret:")
        print("  1. 访问 https://open.ys7.com")
        print("  2. 登录后进入「我的应用」")
        print("  3. 创建应用或查看已有应用的appKey/appSecret")
        return 1

    cache_path = args.output or DEFAULT_CACHE_PATH

    # 检查缓存是否有效
    if not args.force:
        cache = load_cache(cache_path)
        if cache and is_cache_valid(cache):
            print(f"缓存仍然有效 (刷新于: {cache.get('refreshed_at')})")
            print(f"如需强制刷新，请使用 --force 参数")
            return 0

    # 执行刷新
    result = refresh_all_rtmp_urls(app_key, app_secret, test_connectivity=args.test)
    save_cache(result, cache_path)

    # 输出摘要
    print("\n" + "=" * 60)
    print("刷新摘要")
    print("=" * 60)
    for cam in result["cameras"]:
        url_display = cam["rtmp_url"][:60] + "..." if cam.get("rtmp_url") else "(无)"
        test_info = ""
        if "tested" in cam:
            test_info = " [TEST OK]" if cam["tested"] else " [TEST FAIL]"
        print(f"  {cam['id']}: {url_display}{test_info}")

    return 0 if result["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
