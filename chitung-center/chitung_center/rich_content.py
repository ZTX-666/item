from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chitung_center.chat_attachment_service import (
    attachment_meta,
    chat_attachment_api_url,
    normalize_asset_ref,
    resolve_chat_attachment_path,
)


def build_sql_rich_blocks(plan: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    sql = str(plan.get("sql") or "").strip()
    if sql:
        blocks.append({"kind": "code", "title": "SQL", "language": "sql", "text": sql})

    if not result.get("ok", True):
        error = str(result.get("error") or result.get("summary") or "查询失败")
        blocks.append({"kind": "markdown", "title": "错误", "text": error})
        return blocks

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if plan.get("kind") == "tables":
        tables = [str(item) for item in data.get("tables") if isinstance(data.get("tables"), list) and item]
        if tables:
            blocks.append({"kind": "list", "title": "数据库表", "items": tables})
        return blocks

    columns = [str(item) for item in data.get("columns") if isinstance(data.get("columns"), list) and item]
    rows = [row for row in data.get("rows") if isinstance(data.get("rows"), list) and isinstance(row, dict)]
    if columns and rows:
        blocks.append(
            {
                "kind": "table",
                "title": "查询结果",
                "columns": columns,
                "rows": rows,
                "total": int(data.get("total") or len(rows)),
                "limit": int(data.get("limit") or len(rows)),
                "offset": int(data.get("offset") or 0),
            }
        )
        blocks.extend(_whatsapp_media_blocks_from_rows(rows))
    return blocks


def build_wacli_rich_blocks(args_text: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if args_text:
        blocks.append({"kind": "code", "title": "wacli 命令", "language": "bash", "text": f"wacli {args_text}"})
    if not result.get("ok", True):
        blocks.append(
            {
                "kind": "markdown",
                "title": "执行失败",
                "text": str(result.get("error") or result.get("summary") or "未知错误"),
            }
        )
        return blocks

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    fallback_rows = data.get("fallback_rows") if isinstance(data.get("fallback_rows"), list) else []
    if fallback_rows:
        columns = list(fallback_rows[0].keys()) if fallback_rows and isinstance(fallback_rows[0], dict) else []
        blocks.append(
            {
                "kind": "table",
                "title": "本地库回退结果",
                "columns": columns,
                "rows": [row for row in fallback_rows if isinstance(row, dict)],
                "total": len(fallback_rows),
            }
        )
        return blocks

    stdout = str(data.get("stdout") or "").strip()
    if stdout:
        parsed_table = _parse_fixed_width_table(stdout)
        if parsed_table:
            blocks.append({"kind": "table", "title": "命令输出", **parsed_table})
        else:
            blocks.append({"kind": "code", "title": "命令输出", "language": "text", "text": stdout})
    return blocks


def build_rag_rich_blocks(answer: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    text = str(answer.get("answer") or "").strip()
    if text:
        blocks.append({"kind": "markdown", "title": "知识库回答", "text": text})
    citations = answer.get("citations") if isinstance(answer.get("citations"), list) else []
    if citations:
        items = []
        for item in citations:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source_file_name") or item.get("source") or "知识库")
            chunk = item.get("chunk_index")
            items.append(f"{source}#{chunk}" if chunk is not None else source)
        if items:
            blocks.append({"kind": "list", "title": "引用来源", "items": items})
    matches = answer.get("matches") if isinstance(answer.get("matches"), list) else []
    rows = []
    for item in matches:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "来源": str(item.get("source_file_name") or item.get("source") or ""),
                "片段": str(item.get("text") or item.get("content") or "")[:160],
                "相关度": item.get("score"),
            }
        )
    if rows:
        blocks.append(
            {
                "kind": "table",
                "title": "检索片段",
                "columns": ["来源", "片段", "相关度"],
                "rows": rows,
                "total": len(rows),
            }
        )
    return blocks


def build_policy_rich_blocks(policy_result: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    data = policy_result.get("data") if isinstance(policy_result.get("data"), dict) else policy_result
    hits = data.get("hits") if isinstance(data.get("hits"), list) else data.get("items") if isinstance(data.get("items"), list) else []
    rows = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "章节": str(item.get("section") or item.get("title") or ""),
                "内容": str(item.get("text") or item.get("content") or item.get("snippet") or "")[:200],
            }
        )
    if rows:
        blocks.append(
            {
                "kind": "table",
                "title": "制度条款检索",
                "columns": ["章节", "内容"],
                "rows": rows,
                "total": len(rows),
            }
        )
    return blocks


def build_briefing_rich_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    briefing_text = str(data.get("briefing_text") or "").strip()
    if briefing_text:
        blocks.append({"kind": "markdown", "title": "简报正文", "text": briefing_text})

    for item in data.get("report_images") if isinstance(data.get("report_images"), list) else []:
        if not isinstance(item, dict):
            continue
        url = normalize_asset_ref(str(item.get("url") or item.get("image_url") or item.get("path") or ""))
        if not url:
            continue
        blocks.append(
            {
                "kind": "image",
                "title": str(item.get("title") or item.get("source") or "简报配图"),
                "url": url,
                "caption": str(item.get("caption") or item.get("title") or ""),
            }
        )

    link_items: list[dict[str, str]] = []
    for item in data.get("report_links") if isinstance(data.get("report_links"), list) else []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        link_items.append(
            {
                "title": str(item.get("title") or "外部更新"),
                "url": url,
                "source": str(item.get("source") or item.get("source_name") or "外部来源"),
            }
        )
    if link_items:
        blocks.append({"kind": "links", "title": "参考链接", "links": link_items})
    return blocks


def build_visual_patrol_rich_blocks(draft: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    source = str(draft.get("source") or draft.get("image_path") or "").strip()
    if source:
        url = normalize_asset_ref(source)
        if url:
            blocks.append({"kind": "image", "title": "巡检原图", "url": url, "caption": str(draft.get("area") or "")})

    snapshot = draft.get("snapshot")
    if isinstance(snapshot, dict):
        for file_item in snapshot.get("files") if isinstance(snapshot.get("files"), list) else []:
            if not isinstance(file_item, dict):
                continue
            path = str(file_item.get("path") or "").strip()
            url = normalize_asset_ref(path)
            if url:
                blocks.append(
                    {
                        "kind": "image",
                        "title": "抓拍截图",
                        "url": url,
                        "caption": str(file_item.get("name") or Path(path).name),
                    }
                )

    candidates = draft.get("candidates") if isinstance(draft.get("candidates"), list) else []
    if candidates:
        titles = [str(item.get("title") or "") for item in candidates if isinstance(item, dict) and item.get("title")]
        if titles:
            blocks.append({"kind": "list", "title": "巡检候选", "items": titles[:8]})
    return blocks


def build_video_detection_rich_blocks(report: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    summary = report.get("summary")
    if isinstance(summary, dict):
        text = str(summary.get("text") or "").strip()
        if text:
            blocks.append({"kind": "markdown", "title": "巡检摘要", "text": text})
    elif isinstance(summary, str) and summary.strip():
        blocks.append({"kind": "markdown", "title": "巡检摘要", "text": summary.strip()})

    seen_urls: set[str] = set()
    cameras = report.get("cameras") if isinstance(report.get("cameras"), list) else [report]
    for camera in cameras:
        if not isinstance(camera, dict):
            continue
        camera_name = str(camera.get("camera_name") or camera.get("camera_id") or "摄像头")
        for key, label in (("annotated_url", "标注图"), ("snapshot_url", "截图")):
            raw = str(camera.get(key) or camera.get(key.replace("_url", "_path")) or "").strip()
            url = normalize_asset_ref(raw)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            blocks.append(
                {
                    "kind": "image",
                    "title": f"{camera_name} · {label}",
                    "url": url,
                    "caption": camera_name,
                }
            )

    detections = report.get("detections") if isinstance(report.get("detections"), list) else []
    rows = []
    for item in detections[:12]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "标签": str(item.get("label") or item.get("class_name") or ""),
                "置信度": item.get("confidence") or item.get("conf"),
                "区域": str(item.get("area") or item.get("camera_name") or ""),
            }
        )
    if rows:
        blocks.append(
            {
                "kind": "table",
                "title": "检测明细",
                "columns": ["标签", "置信度", "区域"],
                "rows": rows,
                "total": len(rows),
            }
        )
    return blocks


def block_from_local_path(path_str: str, title: str) -> dict[str, Any] | None:
    cleaned = str(path_str or "").strip()
    if not cleaned:
        return None
    if cleaned.startswith("/api/"):
        suffix = Path(cleaned.split("?")[0]).suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
            return {"kind": "image", "title": title, "url": cleaned}
        return {"kind": "file", "title": title, "url": cleaned, "file_name": Path(cleaned).name}

    resolved = resolve_chat_attachment_path(cleaned)
    if resolved:
        meta = attachment_meta(resolved)
        url = chat_attachment_api_url(cleaned)
        if meta["is_image"]:
            return {
                "kind": "image",
                "title": title,
                "url": url,
                "caption": meta["file_name"],
            }
        return {
            "kind": "file",
            "title": title,
            "url": url,
            "path": cleaned,
            "file_name": meta["file_name"],
            "mime": meta["mime"],
            "size": meta["size"],
        }

    url = normalize_asset_ref(cleaned)
    if not url:
        return None
    if Path(cleaned).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        return {"kind": "image", "title": title, "url": url, "caption": Path(cleaned).name}
    return {"kind": "file", "title": title, "url": url, "path": cleaned, "file_name": Path(cleaned).name}


def aggregate_rich_blocks_from_chat_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[list[dict[str, Any]]] = []
    top_level = payload.get("rich_blocks")
    if isinstance(top_level, list):
        groups.append([item for item in top_level if isinstance(item, dict)])

    for card in payload.get("cards") if isinstance(payload.get("cards"), list) else []:
        if not isinstance(card, dict):
            continue
        card_blocks = card.get("rich_blocks")
        if isinstance(card_blocks, list):
            groups.append([item for item in card_blocks if isinstance(item, dict)])
        data = card.get("data")
        if isinstance(data, dict):
            data_blocks = data.get("rich_blocks")
            if isinstance(data_blocks, list):
                groups.append([item for item in data_blocks if isinstance(item, dict)])

    for result in payload.get("tool_results") if isinstance(payload.get("tool_results"), list) else []:
        if not isinstance(result, dict):
            continue
        result_blocks = result.get("rich_blocks")
        if isinstance(result_blocks, list):
            groups.append([item for item in result_blocks if isinstance(item, dict)])
    return merge_rich_blocks(*groups)


def _whatsapp_media_blocks_from_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        msg_id = str(row.get("msg_id") or row.get("message_id") or "").strip()
        if not msg_id or msg_id in seen:
            continue
        media_type = str(row.get("media_type") or row.get("mime_type") or "").strip().lower()
        filename = str(row.get("filename") or row.get("file_name") or "whatsapp-media").strip()
        local_path = str(row.get("local_path") or "").strip()
        if not media_type and not local_path:
            continue
        seen.add(msg_id)
        url = f"/api/whatsapp/media/{msg_id}"
        if media_type.startswith("image/") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            blocks.append(
                {
                    "kind": "image",
                    "title": "WhatsApp 图片",
                    "url": url,
                    "caption": str(row.get("text") or row.get("body") or filename)[:120],
                }
            )
            continue
        blocks.append(
            {
                "kind": "file",
                "title": "WhatsApp 附件",
                "url": url,
                "file_name": filename,
                "mime": media_type or "application/octet-stream",
            }
        )
        if len(blocks) >= 6:
            break
    return blocks


def merge_rich_blocks(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        for block in group:
            if not isinstance(block, dict):
                continue
            key = f"{block.get('kind')}:{block.get('title')}:{block.get('text', '')[:40]}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(block)
    return merged


def format_sql_reply_text(plan: dict[str, Any], result: dict[str, Any]) -> str:
    if not result.get("ok", True):
        return f"WhatsApp SQLite 查询失败：{result.get('error') or result.get('summary') or '未知错误'}。"

    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    if plan.get("kind") == "tables":
        tables = data.get("tables") if isinstance(data.get("tables"), list) else []
        preview = "、".join(str(item) for item in tables[:12])
        suffix = "等" if len(tables) > 12 else ""
        return f"WhatsApp 本地库表名读取完成，共 {len(tables)} 个表：{preview}{suffix}。"

    columns = data.get("columns") if isinstance(data.get("columns"), list) else []
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    total = int(data.get("total") or len(rows))
    preview_cols = "、".join(str(item) for item in columns[:6])
    header = f"WhatsApp SQLite 只读查询完成，共 {total} 行（展示 {len(rows)} 行）。字段：{preview_cols}。"
    table_md = format_markdown_table(columns, rows)
    if table_md:
        return f"{header}\n\n{table_md}"
    return header


def format_markdown_table(columns: list[Any], rows: list[dict[str, Any]], max_rows: int = 20) -> str:
    if not columns or not rows:
        return ""
    safe_columns = [str(column) for column in columns]
    header = "| " + " | ".join(safe_columns) + " |"
    separator = "| " + " | ".join("---" for _ in safe_columns) + " |"
    body: list[str] = []
    for row in rows[:max_rows]:
        cells = []
        for column in safe_columns:
            value = row.get(column, "")
            text = _cell_text(value)
            cells.append(text)
        body.append("| " + " | ".join(cells) + " |")
    suffix = ""
    if len(rows) > max_rows:
        suffix = f"\n\n*仅展示前 {max_rows} 行。*"
    return "\n".join([header, separator, *body]) + suffix


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "\\|").replace("\n", " ").strip()
    if len(text) > 120:
        return text[:117] + "..."
    return text


def _parse_fixed_width_table(stdout: str) -> dict[str, Any] | None:
    lines = [line.rstrip() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    header_line = lines[0]
    if "  " not in header_line:
        return None
    columns = [cell.strip() for cell in re.split(r"\s{2,}", header_line.strip()) if cell.strip()]
    if len(columns) < 2:
        return None
    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        cells = [cell.strip() for cell in re.split(r"\s{2,}", line.strip())]
        if len(cells) < len(columns):
            continue
        row = {columns[index]: cells[index] for index in range(len(columns))}
        rows.append(row)
    if not rows:
        return None
    return {"columns": columns, "rows": rows, "total": len(rows)}
