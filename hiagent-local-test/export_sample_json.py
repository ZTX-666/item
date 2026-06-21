"""
不经过网络：从本机 wacli.db 导出 JSON，上传到 HiAgent 对话里做离线测试。

用法：
  python export_sample_json.py
  python export_sample_json.py --q 关键词 --limit 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from local_test_server import _find_wacli_db, _query_messages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q", default="", help="搜索关键词")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("-o", "--output", default="sample_messages.json")
    args = parser.parse_args()

    db = _find_wacli_db()
    if not db:
        raise SystemExit("未找到 wacli.db，请先运行赤瞳灵讯并完成 sync，或设置 WACLI_DB_PATH")

    items = _query_messages(db, args.q, args.limit)
    out = Path(args.output)
    payload = {
        "source": "chitong-local-export",
        "db": str(db),
        "query": args.q,
        "count": len(items),
        "items": items,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {len(items)} rows -> {out.resolve()}")
    print("可将此 JSON 文件上传到 HiAgent 对话中，验证智能体能否解析检索结果。")


if __name__ == "__main__":
    main()
