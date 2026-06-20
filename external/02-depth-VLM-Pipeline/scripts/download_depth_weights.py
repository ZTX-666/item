#!/usr/bin/env python3
"""从 Hugging Face 下载 Depth Anything V2 Small 权重。"""
from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parent.parent
DST_DIR = ROOT / "weights" / "depth"
FILENAME = "depth_anything_v2_vits.pth"
REPO_ID = "depth-anything/Depth-Anything-V2-Small"


def main() -> int:
    DST_DIR.mkdir(parents=True, exist_ok=True)
    dst = DST_DIR / FILENAME
    if dst.is_file() and dst.stat().st_size > 1_000_000:
        print(f"已存在，跳过下载: {dst} ({dst.stat().st_size / (1024**2):.1f} MB)")
        return 0

    print(f"下载 {REPO_ID} / {FILENAME} ...")
    path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=str(DST_DIR),
    )
    print("完成 ->", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
