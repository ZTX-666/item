#!/usr/bin/env python3
"""
工地双模型 YOLO 推理：工人/PPE + 施工机械（仅检测，不训练）。

用法:
  python detect.py --source input/demo.jpg
  python detect.py --source input/ --save-img --export-json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent

CHINESE_FONT_PATHS = [
    os.getenv("CHINESE_FONT_PATH"),
    os.getenv("CJK_FONT_PATH"),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]
_LABEL_FONT = None


def load_label_font(size: int = 20):
    global _LABEL_FONT
    if _LABEL_FONT is not None:
        return _LABEL_FONT
    for font_path in CHINESE_FONT_PATHS:
        if font_path and Path(font_path).exists():
            _LABEL_FONT = ImageFont.truetype(font_path, size)
            return _LABEL_FONT
    _LABEL_FONT = ImageFont.load_default()
    return _LABEL_FONT


def label_text_fill(background_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = background_rgb
    luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
    return (0, 0, 0) if luminance >= 150 else (255, 255, 255)


def load_config(path: Path | None) -> dict:
    cfg_path = path or ROOT / "config.yaml"
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else (ROOT / p).resolve()


def box_record(xyxy, conf, cls_id, names: dict, source: str, model_tag: str) -> dict:
    x1, y1, x2, y2 = (float(v) for v in xyxy)
    cid = int(cls_id)
    return {
        "model": model_tag,
        "source": source,
        "class_id": cid,
        "class_name": names.get(cid, str(cid)),
        "confidence": round(float(conf), 4),
        "bbox_xyxy": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
        "bbox_xywh": [
            round(x1, 2),
            round(y1, 2),
            round(x2 - x1, 2),
            round(y2 - y1, 2),
        ],
    }


def collect_detections(result, names: dict, source: str, model_tag: str) -> list[dict]:
    rows: list[dict] = []
    if result.boxes is None:
        return rows
    for xyxy, conf, cls_id in zip(
        result.boxes.xyxy.tolist(),
        result.boxes.conf.tolist(),
        result.boxes.cls.tolist(),
    ):
        rows.append(box_record(xyxy, conf, cls_id, names, source, model_tag))
    return rows


def draw_boxes(image, rows: list[dict], color: tuple[int, int, int]) -> None:
    pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_image)
    font = load_label_font(20)
    color_rgb = (color[2], color[1], color[0])
    text_fill = label_text_fill(color_rgb)

    for r in rows:
        x1, y1, x2, y2 = (int(v) for v in r["bbox_xyxy"])
        label = f"{r['class_name']} {r['confidence']:.2f}"
        draw.rectangle([x1, y1, x2, y2], outline=color_rgb, width=2)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        label_left = max(0, min(x1, pil_image.size[0] - tw - 8))
        label_top = y1 - th - 8
        if label_top < 0:
            label_top = min(pil_image.size[1] - th - 8, y1 + 2)
        label_top = max(0, label_top)
        draw.rectangle([label_left, label_top, label_left + tw + 8, label_top + th + 8], fill=color_rgb)
        draw.text((label_left + 4, label_top + 2), label, fill=text_fill, font=font)

    image[:, :, :] = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)


def iter_sources(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
    return sorted(p for p in source.iterdir() if p.suffix.lower() in exts)


def main() -> int:
    ap = argparse.ArgumentParser(description="VLM-Detection 双模型工地目标检测")
    ap.add_argument("--source", type=Path, default=ROOT / "input", help="图片或目录")
    ap.add_argument("--config", type=Path, default=None, help="config.yaml 路径")
    ap.add_argument("--out", type=Path, default=ROOT / "output", help="输出目录")
    ap.add_argument("--conf", type=float, default=None, help="置信度阈值")
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--worker-only", action="store_true", help="仅跑工人/PPE 模型")
    ap.add_argument("--machinery-only", action="store_true", help="仅跑机械模型")
    ap.add_argument("--save-img", action="store_true", help="保存标注图")
    ap.add_argument("--export-json", action="store_true", help="导出 JSON")
    args = ap.parse_args()

    cfg = load_config(args.config)
    inf = cfg["inference"]
    conf = args.conf if args.conf is not None else inf["conf"]
    imgsz = args.imgsz if args.imgsz is not None else inf["imgsz"]
    device = args.device if args.device is not None else inf.get("device") or None

    worker_path = resolve_path(cfg["models"]["worker"])
    machinery_path = resolve_path(cfg["models"]["machinery"])
    if not worker_path.is_file():
        raise FileNotFoundError(f"工人权重不存在: {worker_path}")
    if not machinery_path.is_file():
        raise FileNotFoundError(f"机械权重不存在: {machinery_path}")

    run_worker = not args.machinery_only
    run_machinery = not args.worker_only

    worker_model = YOLO(str(worker_path)) if run_worker else None
    machinery_model = YOLO(str(machinery_path)) if run_machinery else None

    worker_names = {int(k): v for k, v in cfg["worker_class_names"].items()}
    machinery_names = {int(k): v for k, v in cfg["machinery_class_names"].items()}
    worker_classes = cfg.get("worker_classes")

    source = args.source if args.source.is_absolute() else (ROOT / args.source)
    sources = iter_sources(source.resolve())
    if not sources:
        print(f"未找到图片: {source}")
        return 1

    out_dir = args.out if args.out.is_absolute() else (ROOT / args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_dir = out_dir / "images"
    if args.save_img:
        img_dir.mkdir(parents=True, exist_ok=True)

    all_payload: list[dict] = []

    for img_path in sources:
        rel_name = img_path.name
        worker_rows: list[dict] = []
        machinery_rows: list[dict] = []

        if worker_model is not None:
            w_results = worker_model.predict(
                source=str(img_path),
                imgsz=imgsz,
                conf=conf,
                classes=worker_classes,
                device=device,
                verbose=False,
            )
            worker_rows = collect_detections(w_results[0], worker_names, rel_name, "worker")

        if machinery_model is not None:
            m_results = machinery_model.predict(
                source=str(img_path),
                imgsz=imgsz,
                conf=conf,
                device=device,
                verbose=False,
            )
            machinery_rows = collect_detections(m_results[0], machinery_names, rel_name, "machinery")

        merged = worker_rows + machinery_rows
        all_payload.append(
            {
                "image": rel_name,
                "detection_count": len(merged),
                "worker_count": len(worker_rows),
                "machinery_count": len(machinery_rows),
                "detections": merged,
            }
        )

        print(
            f"{rel_name}: worker={len(worker_rows)} machinery={len(machinery_rows)} total={len(merged)}"
        )

        if args.save_img:
            img = cv2.imread(str(img_path))
            if img is not None:
                draw_boxes(img, worker_rows, (0, 200, 0))
                draw_boxes(img, machinery_rows, (0, 140, 255))
                cv2.imwrite(str(img_dir / rel_name), img)

    if args.export_json:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"detections_{stamp}.json"
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "config": {
                        "worker_weights": str(worker_path),
                        "machinery_weights": str(machinery_path),
                        "conf": conf,
                        "imgsz": imgsz,
                    },
                    "images": all_payload,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        print(f"JSON -> {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
