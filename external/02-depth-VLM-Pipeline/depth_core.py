"""Depth Anything V2 Small 相对深度推理（CLI 与 HTTP 共用）。"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import yaml

from depth_anything_v2.dpt import DepthAnythingV2

ROOT = Path(__file__).resolve().parent

VITS_CFG = {
    "encoder": "vits",
    "features": 64,
    "out_channels": [48, 96, 192, 384],
}


def load_depth_config(path: Path | None = None) -> dict:
    cfg_path = path or ROOT / "config_depth.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else (ROOT / p).resolve()


def pick_device(requested: str = "auto") -> str:
    req = (requested or "auto").lower()
    if req == "cpu":
        return "cpu"
    if req == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("配置为 cuda 但当前无可用 GPU")
        return "cuda"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@dataclass
class DepthBundle:
    model: DepthAnythingV2
    device: str
    input_size: int
    use_fp16: bool


def load_depth_model(cfg: dict | None = None) -> DepthBundle:
    cfg = cfg or load_depth_config()
    mcfg = cfg["model"]
    weights = resolve_path(mcfg["weights"])
    if not weights.is_file():
        raise FileNotFoundError(
            f"权重不存在: {weights}\n请先运行: python scripts/download_depth_weights.py"
        )

    device = pick_device(cfg.get("inference", {}).get("device", "auto"))
    use_fp16 = bool(cfg.get("inference", {}).get("fp16", True)) and device == "cuda"

    model = DepthAnythingV2(**VITS_CFG)
    try:
        state = torch.load(str(weights), map_location="cpu", weights_only=True)
    except TypeError:
        state = torch.load(str(weights), map_location="cpu")
    model.load_state_dict(state)
    model = model.to(device).eval()

    input_size = int(mcfg.get("input_size", 518))
    return DepthBundle(model=model, device=device, input_size=input_size, use_fp16=False)


def _infer_raw_depth(bundle: DepthBundle, image_bgr: np.ndarray) -> np.ndarray:
    """返回与输入同分辨率的相对深度 float32（值越大通常越近）。"""
    t0 = time.perf_counter()
    depth = bundle.model.infer_image(image_bgr, bundle.input_size)
    depth = np.asarray(depth, dtype=np.float32)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return depth, elapsed_ms


def normalize_depth(depth: np.ndarray) -> np.ndarray:
    dmin = float(depth.min())
    dmax = float(depth.max())
    if dmax - dmin < 1e-8:
        return np.zeros_like(depth, dtype=np.float32)
    return ((depth - dmin) / (dmax - dmin)).astype(np.float32)


def depth_colormap_bgr(depth: np.ndarray, *, grayscale: bool = False) -> np.ndarray:
    import matplotlib

    norm = normalize_depth(depth)
    u8 = (norm * 255.0).astype(np.uint8)
    if grayscale:
        return cv2.cvtColor(u8, cv2.COLOR_GRAY2BGR)
    cmap = matplotlib.colormaps.get_cmap("Spectral_r")
    rgb = (cmap(u8)[:, :, :3] * 255).astype(np.uint8)
    return rgb[:, :, ::-1].copy()


def depth_stats_in_boxes(
    depth: np.ndarray,
    boxes: list[dict[str, Any]],
    *,
    frame_norm: bool = True,
) -> list[dict[str, Any]]:
    """为每个检测框计算深度统计（用于 VLM / GPS 融合辅助）。"""
    d = normalize_depth(depth) if frame_norm else depth.astype(np.float32)
    h, w = d.shape[:2]
    stats: list[dict[str, Any]] = []
    for i, box in enumerate(boxes):
        xyxy = box.get("bbox_xyxy") or box.get("xyxy")
        if not xyxy or len(xyxy) != 4:
            continue
        x1, y1, x2, y2 = (int(max(0, v)) for v in xyxy)
        x2 = min(w, x2)
        y2 = min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        roi = d[y1:y2, x1:x2]
        med = float(np.median(roi))
        stats.append(
            {
                "index": i,
                "bbox_xyxy": [x1, y1, x2, y2],
                "depth_median_norm": round(med, 4),
                "depth_mean_norm": round(float(roi.mean()), 4),
                "class_name": box.get("class_name"),
                "model": box.get("model"),
            }
        )

    stats.sort(key=lambda x: x["depth_median_norm"], reverse=True)
    for rank, row in enumerate(stats, start=1):
        row["depth_rank"] = rank
    return stats


def run_depth_predict(
    bundle: DepthBundle,
    image_bgr: np.ndarray,
    *,
    boxes: list[dict[str, Any]] | None = None,
    return_vis: bool = True,
) -> dict[str, Any]:
    depth, infer_ms = _infer_raw_depth(bundle, image_bgr)
    norm = normalize_depth(depth)
    out: dict[str, Any] = {
        "height": int(image_bgr.shape[0]),
        "width": int(image_bgr.shape[1]),
        "depth_type": "relative",
        "encoder": "vits",
        "infer_ms": round(infer_ms, 2),
        "device": bundle.device,
        "depth_min": round(float(depth.min()), 6),
        "depth_max": round(float(depth.max()), 6),
    }
    if boxes:
        out["box_depth_stats"] = depth_stats_in_boxes(depth, boxes)
    if return_vis:
        vis = depth_colormap_bgr(depth)
        split = np.ones((image_bgr.shape[0], 50, 3), dtype=np.uint8) * 255
        combined = cv2.hconcat([image_bgr, split, vis])
        ok, buf = cv2.imencode(".jpg", combined, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if ok:
            out["vis_image_base64"] = base64.b64encode(buf.tobytes()).decode("ascii")
        ok2, buf2 = cv2.imencode(".png", (norm * 65535).astype(np.uint16))
        if ok2:
            out["depth_u16_png_base64"] = base64.b64encode(buf2.tobytes()).decode("ascii")
    return out


def decode_image_bytes(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片")
    return img
