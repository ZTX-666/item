#!/usr/bin/env python3
"""
检测 + 相对深度 一条龙（供大模型 few-shot）。

输出:
  output/pipeline/<stem>_annotated.jpg   人+机械合并标注图
  output/pipeline/<stem>_pipeline.json   检测框 + 框内深度统计
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import cv2

from depth_core import load_depth_config, load_depth_model, run_depth_predict
from detect_core import (
    ROOT,
    build_combined_annotated,
    load_config,
    load_models,
    run_detect_split,
)

OUT = ROOT / "output" / "pipeline"


def main() -> int:
    ap = argparse.ArgumentParser(description="检测+深度 pipeline")
    ap.add_argument("--source", type=Path, default=ROOT / "input")
    ap.add_argument("--conf", type=float, default=None)
    args = ap.parse_args()

    src = args.source if args.source.is_absolute() else ROOT / args.source
    images = [src] if src.is_file() else sorted(
        p for p in src.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    )
    if not images:
        print("无图片:", src)
        return 1

    det_bundle = load_models(load_config())
    depth_bundle = load_depth_model(load_depth_config())
    OUT.mkdir(parents=True, exist_ok=True)

    for img_path in images:
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            continue
        persons, machinery = run_detect_split(
            det_bundle, bgr, source_name=img_path.name, conf=args.conf
        )
        all_boxes = persons + machinery
        depth_out = run_depth_predict(
            depth_bundle, bgr, boxes=all_boxes, return_vis=False
        )
        annotated = build_combined_annotated(bgr, persons, machinery)
        stem = img_path.stem
        cv2.imwrite(str(OUT / f"{stem}_annotated.jpg"), annotated)
        payload = {
            "image": img_path.name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "detections": {"person": persons, "machinery": machinery},
            "depth": {k: v for k, v in depth_out.items() if not k.endswith("_base64")},
        }
        (OUT / f"{stem}_pipeline.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{img_path.name}: person={len(persons)} machinery={len(machinery)} -> {OUT}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
