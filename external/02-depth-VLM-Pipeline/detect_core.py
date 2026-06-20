"""工地目标检测核心逻辑（支持单模型 unified / 双模型 dual）。"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

import cv2
import numpy as np
import yaml
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent

WORKER_COLOR = (0, 200, 0)  # BGR
MACHINERY_COLOR = (0, 140, 255)


def load_config(path: Path | None = None) -> dict:
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


def draw_boxes(image: np.ndarray, rows: list[dict], color: tuple[int, int, int]) -> None:
    for r in rows:
        x1, y1, x2, y2 = (int(v) for v in r["bbox_xyxy"])
        label = f"{r['class_name']} {r['confidence']:.2f}"
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            image,
            label,
            (x1, max(y1 - 6, 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )


def decode_image_bytes(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("无法解码图片（支持 jpg/png/webp 等）")
    return img


def encode_jpeg_b64(image: np.ndarray, quality: int = 90) -> str:
    ok, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    return base64.b64encode(buf.tobytes()).decode("ascii")


@dataclass
class ModelBundle:
    """双模型：人/PPE 模型 + 机械细分类模型（两次推理）。"""

    worker: YOLO
    machinery: YOLO
    worker_names: dict[int, str]
    machinery_names: dict[int, str]
    worker_classes: list[int] | None
    conf: float
    imgsz: int
    device: str | None
    mode: str = "dual"


@dataclass
class UnifiedBundle:
    """单模型：一次推理输出人 + 机械（粗类/车辆）。"""

    model: YOLO
    class_names: dict[int, str]
    filter_classes: list[int]
    person_class_ids: set[int]
    machinery_class_ids: set[int]
    conf: float
    imgsz: int
    device: str | None
    weights_path: Path
    mode: str = "unified"


DetectBundle = Union[ModelBundle, UnifiedBundle]


def detection_mode(cfg: dict) -> str:
    return str(cfg.get("mode", "dual")).strip().lower()


def load_models(cfg: dict | None = None) -> DetectBundle:
    cfg = cfg or load_config()
    if detection_mode(cfg) == "unified":
        return load_unified_models(cfg)
    return load_dual_models(cfg)


def load_dual_models(cfg: dict) -> ModelBundle:
    inf = cfg["inference"]
    device = inf.get("device") or None
    if device == "":
        device = None
    worker_path = resolve_path(cfg["models"]["worker"])
    machinery_path = resolve_path(cfg["models"]["machinery"])
    if not worker_path.is_file():
        raise FileNotFoundError(f"工人权重不存在: {worker_path}")
    if not machinery_path.is_file():
        raise FileNotFoundError(f"机械权重不存在: {machinery_path}")
    return ModelBundle(
        worker=YOLO(str(worker_path)),
        machinery=YOLO(str(machinery_path)),
        worker_names={int(k): v for k, v in cfg["worker_class_names"].items()},
        machinery_names={int(k): v for k, v in cfg["machinery_class_names"].items()},
        worker_classes=cfg.get("worker_classes"),
        conf=float(inf["conf"]),
        imgsz=int(inf["imgsz"]),
        device=device,
        mode="dual",
    )


def load_unified_models(cfg: dict) -> UnifiedBundle:
    inf = cfg["inference"]
    device = inf.get("device") or None
    if device == "":
        device = None
    ucfg = cfg.get("unified") or {}
    model_rel = cfg["models"].get("unified") or cfg["models"]["worker"]
    weights_path = resolve_path(model_rel)
    if not weights_path.is_file():
        raise FileNotFoundError(
            f"统一模型权重不存在: {weights_path}\n"
            "请运行: python scripts/download_weights.py"
        )
    filter_classes = [int(x) for x in ucfg.get("classes", [5, 8, 10])]
    person_ids = {int(x) for x in ucfg.get("person_class_ids", [5])}
    machinery_ids = {int(x) for x in ucfg.get("machinery_class_ids", [8, 10])}
    names = {int(k): v for k, v in cfg["worker_class_names"].items()}
    return UnifiedBundle(
        model=YOLO(str(weights_path)),
        class_names=names,
        filter_classes=filter_classes,
        person_class_ids=person_ids,
        machinery_class_ids=machinery_ids,
        conf=float(inf["conf"]),
        imgsz=int(inf["imgsz"]),
        device=device,
        weights_path=weights_path,
        mode="unified",
    )


def run_unified_detect(
    bundle: UnifiedBundle,
    image_bgr: np.ndarray,
    *,
    source_name: str = "upload",
    conf: float | None = None,
    imgsz: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """单次推理，按类别拆成 person 行与 machinery 行。"""
    conf_v = conf if conf is not None else bundle.conf
    imgsz_v = imgsz if imgsz is not None else bundle.imgsz
    results = bundle.model.predict(
        source=image_bgr,
        imgsz=imgsz_v,
        conf=conf_v,
        classes=bundle.filter_classes,
        device=bundle.device,
        verbose=False,
    )
    person_rows: list[dict] = []
    machinery_rows: list[dict] = []
    if results[0].boxes is None:
        return person_rows, machinery_rows
    for xyxy, conf_val, cls_id in zip(
        results[0].boxes.xyxy.tolist(),
        results[0].boxes.conf.tolist(),
        results[0].boxes.cls.tolist(),
    ):
        cid = int(cls_id)
        tag = "person" if cid in bundle.person_class_ids else "machinery"
        if tag == "machinery" and cid not in bundle.machinery_class_ids:
            continue
        if tag == "person" and cid not in bundle.person_class_ids:
            continue
        row = box_record(xyxy, conf_val, cid, bundle.class_names, source_name, tag)
        if tag == "person":
            person_rows.append(row)
        else:
            machinery_rows.append(row)
    return person_rows, machinery_rows


def run_detect_split(
    bundle: DetectBundle,
    image_bgr: np.ndarray,
    *,
    source_name: str = "upload",
    conf: float | None = None,
    imgsz: int | None = None,
) -> tuple[list[dict], list[dict]]:
    if isinstance(bundle, UnifiedBundle):
        return run_unified_detect(
            bundle, image_bgr, source_name=source_name, conf=conf, imgsz=imgsz
        )
    return run_dual_detect(bundle, image_bgr, source_name=source_name, conf=conf, imgsz=imgsz)


def run_dual_detect(
    bundle: ModelBundle,
    image_bgr: np.ndarray,
    *,
    source_name: str = "upload",
    conf: float | None = None,
    imgsz: int | None = None,
) -> tuple[list[dict], list[dict]]:
    conf_v = conf if conf is not None else bundle.conf
    imgsz_v = imgsz if imgsz is not None else bundle.imgsz

    w_results = bundle.worker.predict(
        source=image_bgr,
        imgsz=imgsz_v,
        conf=conf_v,
        classes=bundle.worker_classes,
        device=bundle.device,
        verbose=False,
    )
    m_results = bundle.machinery.predict(
        source=image_bgr,
        imgsz=imgsz_v,
        conf=conf_v,
        device=bundle.device,
        verbose=False,
    )
    worker_rows = collect_detections(w_results[0], bundle.worker_names, source_name, "worker")
    machinery_rows = collect_detections(
        m_results[0], bundle.machinery_names, source_name, "machinery"
    )
    return worker_rows, machinery_rows


def build_triple_images(
    image_bgr: np.ndarray, person_rows: list[dict], machinery_rows: list[dict]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    original = image_bgr.copy()
    human = image_bgr.copy()
    machine = image_bgr.copy()
    draw_boxes(human, person_rows, WORKER_COLOR)
    draw_boxes(machine, machinery_rows, MACHINERY_COLOR)
    return original, human, machine


def build_combined_annotated(
    image_bgr: np.ndarray, person_rows: list[dict], machinery_rows: list[dict]
) -> np.ndarray:
    """人（绿框）+ 机械（橙框）画在同一张图上，供大模型 few-shot 使用。"""
    vis = image_bgr.copy()
    draw_boxes(vis, person_rows, WORKER_COLOR)
    draw_boxes(vis, machinery_rows, MACHINERY_COLOR)
    return vis


def vlm_image_style(cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    style = str(cfg.get("output", {}).get("vlm_image", "combined")).strip().lower()
    return style if style in ("combined", "triple") else "combined"


def run_detect_response(
    bundle: DetectBundle,
    image_bgr: np.ndarray,
    *,
    source_name: str = "upload",
    conf: float | None = None,
    imgsz: int | None = None,
    vlm_image: str | None = None,
    cfg: dict | None = None,
) -> dict[str, Any]:
    """检测并返回 JSON；默认一张合并标注图（combined），可选三张（triple）。"""
    person_rows, machinery_rows = run_detect_split(
        bundle, image_bgr, source_name=source_name, conf=conf, imgsz=imgsz
    )
    style = (vlm_image or vlm_image_style(cfg)).lower()
    if style == "triple":
        original, human, machine = build_triple_images(image_bgr, person_rows, machinery_rows)
        images = [
            {"role": "original", "mime": "image/jpeg", "base64": encode_jpeg_b64(original)},
            {"role": "human", "mime": "image/jpeg", "base64": encode_jpeg_b64(human)},
            {"role": "machine", "mime": "image/jpeg", "base64": encode_jpeg_b64(machine)},
        ]
    else:
        combined = build_combined_annotated(image_bgr, person_rows, machinery_rows)
        images = [
            {
                "role": "annotated",
                "mime": "image/jpeg",
                "base64": encode_jpeg_b64(combined),
                "legend": {"person": "green", "machinery": "orange"},
            }
        ]

    out: dict[str, Any] = {
        "mode": bundle.mode,
        "vlm_image": style,
        "images": images,
        "detections": {
            "person": person_rows,
            "machinery": machinery_rows,
            "worker": person_rows,
        },
        "counts": {
            "person": len(person_rows),
            "machinery": len(machinery_rows),
            "worker": len(person_rows),
        },
    }
    if isinstance(bundle, UnifiedBundle):
        out["weights"] = str(bundle.weights_path)
    return out


def run_triple_detect(
    bundle: DetectBundle,
    image_bgr: np.ndarray,
    *,
    source_name: str = "upload",
    conf: float | None = None,
    imgsz: int | None = None,
) -> dict[str, Any]:
    """兼容旧调用：按 config output.vlm_image 返回（默认 combined 单图）。"""
    return run_detect_response(
        bundle,
        image_bgr,
        source_name=source_name,
        conf=conf,
        imgsz=imgsz,
    )
