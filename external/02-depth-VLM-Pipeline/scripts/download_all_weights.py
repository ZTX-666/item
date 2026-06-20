#!/usr/bin/env python3
"""下载检测 + 深度全部权重。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    scripts = [
        ROOT / "scripts" / "download_detect_weights.py",
        ROOT / "scripts" / "download_depth_weights.py",
    ]
    for s in scripts:
        print("==>", s.name)
        r = subprocess.run([sys.executable, str(s)], cwd=str(ROOT))
        if r.returncode != 0:
            return r.returncode
    print("ALL_WEIGHTS_DOWNLOAD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
