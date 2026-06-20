#!/usr/bin/env python3
"""Depth Anything V2 Small 命令行推理。"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import cv2

from depth_core import ROOT, load_depth_config, load_depth_model, run_depth_predict

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def iter_images(source: Path):
    if source.is_file():
        yield source
        return
    for p in sorted(source.rglob("*")):
        if p.suffix.lower() in IMAGE_EXTS:
            yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="Depth Anything V2 Small 相对深度")
    ap.add_argument("--source", type=str, default="input", help="图片或目录")
    ap.add_argument("--config", type=str, default="", help="config_depth.yaml 路径")
    ap.add_argument("--outdir", type=str, default="", help="输出目录，默认 output/depth")
    ap.add_argument("--input-size", type=int, default=0, help="覆盖推理边长（默认 518）")
    ap.add_argument("--save-vis", action="store_true", help="保存对比可视化图")
    ap.add_argument("--export-json", action="store_true", help="保存 JSON 元数据")
    args = ap.parse_args()

    cfg = load_depth_config(Path(args.config) if args.config else None)
    if args.input_size > 0:
        cfg["model"]["input_size"] = args.input_size
    outdir = Path(args.outdir) if args.outdir else ROOT / cfg.get("output", {}).get("dir", "output/depth")
    outdir.mkdir(parents=True, exist_ok=True)

    bundle = load_depth_model(cfg)
    source = Path(args.source)
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        print(f"源不存在: {source}")
        return 1

    files = list(iter_images(source))
    if not files:
        print(f"未找到图片: {source}")
        return 1

    print(f"设备: {bundle.device} | 模型: vits | 共 {len(files)} 张")
    for img_path in files:
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            print(f"跳过（无法读取）: {img_path}")
            continue
        result = run_depth_predict(bundle, bgr, return_vis=args.save_vis)
        stem = img_path.stem
        if args.save_vis and "vis_image_base64" in result:
            import base64

            vis_bytes = base64.b64decode(result["vis_image_base64"])
            vis_path = outdir / f"{stem}_depth_vis.jpg"
            vis_path.write_bytes(vis_bytes)
            print(f"可视化 -> {vis_path}")
        if args.export_json:
            meta = {k: v for k, v in result.items() if not k.endswith("_base64")}
            meta["source"] = str(img_path)
            meta["timestamp"] = datetime.now().isoformat(timespec="seconds")
            json_path = outdir / f"{stem}_depth.json"
            json_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"JSON -> {json_path}")
        print(
            f"{img_path.name}: infer {result['infer_ms']} ms, "
            f"depth [{result['depth_min']}, {result['depth_max']}]"
        )
    print("完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
