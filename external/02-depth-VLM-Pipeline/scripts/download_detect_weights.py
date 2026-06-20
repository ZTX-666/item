#!/usr/bin/env python3
"""下载 YOLO26x 统一检测权重（人+机械）。"""
from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "weights" / "unified" / "yolo26x_unified.pt"
REPO = "yihong1120/Construction-Hazard-Detection"
HF_FILE = "models/yolo26/pt/yolo26x.pt"


def main() -> int:
    DST.parent.mkdir(parents=True, exist_ok=True)
    if DST.is_file() and DST.stat().st_size > 50_000_000:
        print(f"已存在: {DST} ({DST.stat().st_size / (1024**2):.1f} MB)")
        return 0
    print(f"下载 {REPO} / {HF_FILE} ...")
    path = hf_hub_download(repo_id=REPO, filename=HF_FILE, local_dir=str(DST.parent / "_hf"))
    import shutil

    shutil.copy2(path, DST)
    print("完成 ->", DST)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
