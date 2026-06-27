#!/usr/bin/env python3
"""Detect drift between spaced and no-space Chitung workspace copies."""

from __future__ import annotations

import filecmp
import sys
from pathlib import Path

CANONICAL = Path(r"E:\ChinaOverSeaFinal")
LEGACY = Path(r"E:\ChinaOverSea Final")
IGNORE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "dist",
    "release",
    "__pycache__",
    ".pytest_cache",
    "data",
    "rag_chroma",
    "patrol-output",
    "wacli",
    ".cursor",
    ".local-change-backups",
    "publish80",
    "publish4",
}
COMPARE_ROOTS = [
    "chitung-frontend/src",
    "chitung-center/chitung_center",
    "chitung-center/skills",
    "chitung-center/tests",
    "chitung-center/workflows",
    "agent-toolbox/agent_toolbox",
    "scripts",
    "cctv-gateway/src",
]


def compare_trees(left: Path, right: Path, rel: str = "") -> tuple[list[str], list[str], list[str]]:
    only_left: list[str] = []
    only_right: list[str] = []
    diff: list[str] = []
    left_dir = left / rel if rel else left
    right_dir = right / rel if rel else right
    if not left_dir.exists() and not right_dir.exists():
        return only_left, only_right, diff
    if not left_dir.exists():
        only_right.append(rel or ".")
        return only_left, only_right, diff
    if not right_dir.exists():
        only_left.append(rel or ".")
        return only_left, only_right, diff

    cmp = filecmp.dircmp(str(left_dir), str(right_dir), ignore=list(IGNORE_DIRS))
    base = f"{rel}/" if rel else ""
    for name in cmp.left_only:
        if (left_dir / name).is_file():
            only_left.append(f"{base}{name}")
    for name in cmp.right_only:
        if (right_dir / name).is_file():
            only_right.append(f"{base}{name}")
    for name in cmp.diff_files:
        diff.append(f"{base}{name}")
    for sub in cmp.common_dirs:
        if sub in IGNORE_DIRS:
            continue
        ol, orr, df = compare_trees(left, right, f"{base}{sub}".rstrip("/"))
        only_left.extend(ol)
        only_right.extend(orr)
        diff.extend(df)
    return only_left, only_right, diff


def main() -> int:
    print("=" * 60)
    print("赤瞳工作区同步检查")
    print(f"  正式目录: {CANONICAL}")
    print(f"  旧目录:   {LEGACY}")
    print("=" * 60)

    if not CANONICAL.exists() or not LEGACY.exists():
        print("[FAIL] 其中一个目录不存在")
        return 1

    total_only_legacy = 0
    total_only_canonical = 0
    total_diff = 0

    for root in COMPARE_ROOTS:
        left = CANONICAL / root
        right = LEGACY / root
        if not left.exists() and not right.exists():
            continue
        only_canonical, only_legacy, diff = compare_trees(left, right)
        if not (only_canonical or only_legacy or diff):
            print(f"[OK] {root}")
            continue
        print(f"[DRIFT] {root}")
        for item in only_canonical:
            print(f"  仅正式目录: {item}")
        for item in only_legacy:
            print(f"  仅旧目录:   {item}")
        for item in diff:
            print(f"  内容不同:   {item}")
        total_only_canonical += len(only_canonical)
        total_only_legacy += len(only_legacy)
        total_diff += len(diff)

    print("-" * 60)
    if total_only_canonical or total_only_legacy or total_diff:
        print(
            f"结果: 发现漂移 — 仅正式 {total_only_canonical} · 仅旧 {total_only_legacy} · 不同 {total_diff}"
        )
        print("修复: 以 E:\\ChinaOverSeaFinal 为准，运行 scripts\\unify_to_nospace.py 或手动同步。")
        return 1

    print("结果: 关键源码树已一致，未发现漂移。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
