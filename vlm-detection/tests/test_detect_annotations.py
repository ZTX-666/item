from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


DETECT_PATH = Path(__file__).resolve().parents[1] / "detect.py"


def load_detect_module():
    spec = importlib.util.spec_from_file_location("vlm_detection_detect", DETECT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_draw_boxes_renders_chinese_label_with_readable_text():
    detect = load_detect_module()
    image = np.full((180, 260, 3), 255, dtype=np.uint8)

    detect.draw_boxes(
        image,
        [
            {
                "bbox_xyxy": [40, 70, 180, 150],
                "class_name": "流动式起重机",
                "confidence": 0.83,
            }
        ],
        (0, 255, 255),
    )

    label_region = image[35:75, 40:230]
    dark_pixels = int(
        (
            (label_region[:, :, 0] < 80)
            & (label_region[:, :, 1] < 80)
            & (label_region[:, :, 2] < 80)
        ).sum()
    )

    assert dark_pixels > 10
