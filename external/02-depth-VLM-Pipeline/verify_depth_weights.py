#!/usr/bin/env python3
"""校验 Depth Anything V2 Small 权重并可做一次试推理。"""
from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent


def main() -> int:
    from depth_core import load_depth_config, load_depth_model, resolve_path, run_depth_predict

    cfg = load_depth_config()
    weights = resolve_path(cfg["model"]["weights"])
    if not weights.is_file():
        print(f"FAIL 缺少权重: {weights}")
        print("请运行: python scripts/download_depth_weights.py")
        return 1
    mb = weights.stat().st_size / (1024 * 1024)
    print(f"OK 权重: {weights.name} ({mb:.1f} MB)")

    bundle = load_depth_model(cfg)
    print(f"OK 模型已加载 | device={bundle.device} | input_size={bundle.input_size}")

    dummy = np.zeros((480, 640, 3), dtype=np.uint8)
    dummy[200:280, 280:360] = (0, 200, 0)
    out = run_depth_predict(bundle, dummy, return_vis=False)
    print(
        f"OK 试推理 infer_ms={out['infer_ms']} depth_range=({out['depth_min']}, {out['depth_max']})"
    )

    sample = ROOT / "input"
    imgs = list(sample.glob("*.jpg")) + list(sample.glob("*.png"))
    if imgs:
        bgr = cv2.imread(str(imgs[0]))
        if bgr is not None:
            out2 = run_depth_predict(bundle, bgr, return_vis=False)
            print(f"OK 样本图 {imgs[0].name} infer_ms={out2['infer_ms']}")

    print("DEPTH_WEIGHTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
