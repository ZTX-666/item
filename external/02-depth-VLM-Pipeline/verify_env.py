#!/usr/bin/env python3
"""校验检测与深度环境、权重。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    for name in ("verify_weights.py", "verify_depth_weights.py"):
        print("==>", name)
        r = subprocess.run([sys.executable, str(ROOT / name)], cwd=str(ROOT))
        if r.returncode != 0:
            return r.returncode
    print("ENV_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
