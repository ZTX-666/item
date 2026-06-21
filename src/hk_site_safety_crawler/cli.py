from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runner import run_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Hong Kong site safety crawler once.")
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("config/crawler/sources.yml"),
        help="Path to source registry YAML.",
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path("config/crawler/skills"),
        help="Directory containing topic skill YAML files.",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="source_names",
        help="Limit run to one source name. Can be repeated.",
    )
    parser.add_argument("--max-sources", type=int, default=None)
    parser.add_argument("--max-cards", type=int, default=None)
    parser.add_argument("--ack-base-url", default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/alert_cards.json"),
        help="Where to write alert card JSON.",
    )
    args = parser.parse_args()

    result = run_once(
        sources_path=args.sources,
        skills_dir=args.skills_dir,
        source_names=set(args.source_names) if args.source_names else None,
        max_sources=args.max_sources,
        max_cards=args.max_cards,
        ack_base_url=args.ack_base_url,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "card_count": result["card_count"],
                "error_count": result["error_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
