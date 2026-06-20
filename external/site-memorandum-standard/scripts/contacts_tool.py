# -*- coding: utf-8 -*-
"""CLI for site-memorandum-standard contact registry."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from contact_db import Contact, ContactDB, default_db_path, parse_aliases


def cmd_list(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    if not db.contacts:
        print("(no contacts)")
        return 0
    for c in db.contacts:
        als = ", ".join(c.aliases) if c.aliases else "-"
        comp = c.company or "-"
        sig = c.signature_image or "-"
        nzh = c.name_zh or "-"
        print(f"{c.abbrev}\t{c.name}\t{nzh}\t{c.title}\t{comp}\t{als}\t{sig}")
    return 0


def cmd_add(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    c = Contact(
        abbrev=args.abbrev,
        name=args.name,
        name_zh=(args.name_zh or "").strip(),
        title=args.title or "",
        company=args.company or "",
        aliases=parse_aliases(args.aliases),
        signature_image=(args.signature_image or "").strip(),
    )
    _, action = db.upsert(c)
    db.save()
    print(json.dumps({"ok": True, "action": action, "abbrev": c.abbrev}, ensure_ascii=False))
    return 0


def cmd_set(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    cur = db.find(args.abbrev)
    if not cur:
        print(json.dumps({"ok": False, "error": "abbrev not found"}, ensure_ascii=False), file=sys.stderr)
        return 1
    name = cur.name if args.name is None else args.name
    name_zh = cur.name_zh if args.name_zh is None else (args.name_zh or "").strip()
    title = cur.title if args.title is None else args.title
    company = cur.company if args.company is None else args.company
    aliases = cur.aliases if args.aliases is None else parse_aliases(args.aliases)
    if getattr(args, "clear_signature", False):
        sig = ""
    elif args.signature_image is None:
        sig = cur.signature_image
    else:
        sig = (args.signature_image or "").strip()
    c = Contact(
        abbrev=args.abbrev,
        name=name,
        name_zh=name_zh,
        title=title,
        company=company,
        aliases=aliases,
        signature_image=sig,
    )
    db.upsert(c)
    db.save()
    print(json.dumps({"ok": True, "action": "updated", "abbrev": c.abbrev}, ensure_ascii=False))
    return 0


def cmd_remove(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    ok = db.remove(args.abbrev)
    if not ok:
        print(json.dumps({"ok": False, "error": "abbrev not found"}, ensure_ascii=False), file=sys.stderr)
        return 1
    db.save()
    print(json.dumps({"ok": True, "action": "removed", "abbrev": args.abbrev}, ensure_ascii=False))
    return 0


def cmd_show(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    c = db.find(args.token)
    if not c:
        print(json.dumps({"ok": False, "error": "not found"}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "ok": True,
                "abbrev": c.abbrev,
                "name": c.name,
                "name_zh": c.name_zh,
                "name_on_memo": c.memo_english_name(),
                "title": c.title,
                "company": c.company,
                "aliases": c.aliases,
                "signature_image": c.signature_image,
                "memo_line": c.to_memo_line(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_resolve(db: ContactDB, args: argparse.Namespace) -> int:
    db.load()
    style = args.style
    out: dict[str, str] = {}
    try:
        if args.to:
            out["to"] = db.resolve_tokens([args.to], style=style)
        if args.copy_to:
            out["copy_to"] = db.resolve_tokens([args.copy_to], style=style)
        if args.attn:
            out["attn"] = db.resolve_tokens([args.attn], style=style)
    except LookupError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps({"ok": True, **out}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Contact registry for site-memorandum-standard")
    ap.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Override contacts store path (.xlsx preferred, or legacy .json)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List all contacts (TSV columns)")
    p_list.set_defaults(func=cmd_list)

    p_add = sub.add_parser("add", help="Add or replace by abbrev")
    p_add.add_argument("--abbrev", required=True)
    p_add.add_argument("--name", required=True, help="English / roman name")
    p_add.add_argument("--name-zh", dest="name_zh", default="", help="中文姓名")
    p_add.add_argument("--title", default="")
    p_add.add_argument("--company", default="")
    p_add.add_argument("--aliases", default=None, help="Comma-separated extra lookup tokens")
    p_add.add_argument(
        "--signature-image",
        default="",
        help="E-signature file path (absolute or relative to skill root), e.g. assets/signatures/xsy.png",
    )
    p_add.set_defaults(func=cmd_add)

    p_set = sub.add_parser("set", help="Patch fields for existing abbrev")
    p_set.add_argument("--abbrev", required=True)
    p_set.add_argument("--name", default=None, help="English / roman name")
    p_set.add_argument("--name-zh", dest="name_zh", default=None, help="中文姓名; omit to keep")
    p_set.add_argument("--title", default=None)
    p_set.add_argument("--company", default=None)
    p_set.add_argument("--aliases", default=None)
    p_set.add_argument(
        "--signature-image",
        default=None,
        help="Set e-signature path; omit to keep existing",
    )
    p_set.add_argument(
        "--clear-signature",
        action="store_true",
        help="Remove stored signature_image for this abbrev",
    )
    p_set.set_defaults(func=cmd_set)

    p_rm = sub.add_parser("remove", help="Delete by abbrev")
    p_rm.add_argument("--abbrev", required=True)
    p_rm.set_defaults(func=cmd_remove)

    p_show = sub.add_parser("show", help="Show one contact by abbrev/name/alias")
    p_show.add_argument("token")
    p_show.set_defaults(func=cmd_show)

    p_res = sub.add_parser("resolve", help="Resolve memo fields from abbrevs (comma-separated per field)")
    p_res.add_argument("--to", default=None)
    p_res.add_argument("--copy-to", dest="copy_to", default=None)
    p_res.add_argument("--attn", default=None)
    p_res.add_argument(
        "--style",
        choices=("name_title", "name_only"),
        default="name_title",
        help="Memo line format",
    )
    p_res.set_defaults(func=cmd_resolve)

    args = ap.parse_args()
    db = ContactDB(args.db or default_db_path())
    return int(args.func(db, args))


if __name__ == "__main__":
    raise SystemExit(main())
