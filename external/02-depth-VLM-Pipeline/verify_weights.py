#!/usr/bin/env python3
"""检查检测权重存在且可被 Ultralytics 加载。"""
from __future__ import annotations

from pathlib import Path

import yaml
from ultralytics import YOLO

from detect_core import detection_mode, load_models

ROOT = Path(__file__).resolve().parent


def main() -> int:
    with (ROOT / "config.yaml").open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    mode = detection_mode(cfg)
    print(f"mode: {mode}")

    if mode == "unified":
        rel = cfg["models"].get("unified") or cfg["models"]["worker"]
        p = ROOT / rel
        if not p.is_file():
            print(f"FAIL missing unified: {p}")
            return 1
        mb = p.stat().st_size / (1024 * 1024)
        print(f"OK unified: {p.name} ({mb:.1f} MB)")
        m = YOLO(str(p))
        print("classes:", m.names)
        bundle = load_models(cfg)
        assert bundle.mode == "unified"
        print("OK load_models unified bundle")
    else:
        paths = {
            "worker": ROOT / cfg["models"]["worker"],
            "machinery": ROOT / cfg["models"]["machinery"],
        }
        for tag, p in paths.items():
            if not p.is_file():
                print(f"FAIL missing: {tag} -> {p}")
                return 1
            mb = p.stat().st_size / (1024 * 1024)
            print(f"OK file {tag}: {p.name} ({mb:.1f} MB)")
        w = YOLO(str(paths["worker"]))
        m = YOLO(str(paths["machinery"]))
        print("worker classes:", w.names)
        print("machinery classes:", m.names)

    print("ALL_WEIGHTS_LOADED_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
