#!/usr/bin/env python3
"""Seed ~2 weeks of platform usage history (excluding WhatsApp modules)."""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chitung_center.app_config_service import get_app_config
from chitung_center.automation_scheduler_service import ensure_schema as ensure_automation_schema
from chitung_center.chat_store import chat_store
from chitung_center.config import settings
from chitung_center.external_briefing_store import persist_external_briefing_report
from chitung_center.external_monitor_store import ensure_schema as ensure_external_monitor_schema
from chitung_center.job_service import ensure_schema as ensure_job_schema
from chitung_center.storage import database_path, ensure_schema as ensure_platform_schema, now_iso, transaction
from chitung_center.video_detection_store import persist_video_detection_report


SEED_VERSION = 1
SEED_MARKER = "platform_usage_history_v1"
END_DATE = datetime(2026, 6, 23, 18, 0, 0, tzinfo=timezone.utc)
START_DATE = END_DATE - timedelta(days=14)

CASE_SCENES = [
    ("未佩戴安全帽", "施工區域", "high", "open"),
    ("未穿反光衣", "施工區域", "medium", "rectifying"),
    ("人员进入吊机回转半径", "施工區域", "critical", "open"),
    ("临边缺少护栏", "斜坡", "high", "candidate"),
    ("通道被材料占用", "崗亭", "medium", "closed"),
    ("吸烟行为", "施工區域", "medium", "closed"),
    ("挖掘机作业区无隔离", "施工區域", "high", "rectifying"),
    ("高处作业未系安全带", "斜坡", "critical", "open"),
    ("积水未设置警示", "坡頂", "low", "closed"),
    ("夜间照明不足", "施工區域", "medium", "candidate"),
]

WEATHER_TITLES = [
    "天文台发布黄色暴雨警告",
    "酷热天气警告生效",
    "强风信号将在傍晚评估",
    "雷暴警告影响新界东",
]

OFFICIAL_TITLES = [
    "劳工处发布高处作业安全提示",
    "建造业议会更新吊运安全指引",
    "屋宇署加强棚架巡查通知",
    "消防处提醒地盘易燃品储存规范",
]

MEDIA_TITLES = [
    "业界关注地盘吊运事故频发",
    "媒体调查：部分地盘 PPE 佩戴率偏低",
    "评论：极端天气下应暂停户外吊装",
    "专题：智慧工地视觉巡检应用案例",
]

CHAT_TOPICS = [
    ("今日外部讯息简报", "请生成本周施工安全外部讯息摘要，并标出 P1 风险。"),
    ("视觉巡检结果", "帮我汇总今天 11 路摄像头巡检结果，列出需复核画面。"),
    ("整改通知草稿", "针对施工區域02 未穿反光衣，生成整改通知要点。"),
    ("制度检索", "检索地盘吊运作业相关制度条款，用于更新检测提示词。"),
    ("自动化配置", "把吊运专项巡检挂到每 6 小时自动执行。"),
    ("隐患案例状态", "列出当前未关闭的高风险隐患案例。"),
    ("每日安全报告", "根据近 24 小时隐患和巡检，起草每日安全简报。"),
    ("表格填表", "根据今天塔吊交叉作业事件，预填安全巡视表。"),
]

HYBRID_PLANS = [
    ("daily_risk_briefing", "生成今日外部风险简报并准备发送确认"),
    ("hazard_intake", "整理群聊中的隐患线索并创建案例草稿"),
    ("smart_form_filling", "根据巡检结果预填 C-SMART 表格"),
]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _rand_ts(day_offset: int, hour: int, minute: int = 0) -> str:
    base = START_DATE + timedelta(days=day_offset)
    dt = base.replace(hour=hour, minute=minute, second=random.randint(0, 59))
    return dt.isoformat()


def _seed_marker_exists() -> bool:
    ensure_platform_schema()
    with transaction() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS platform_seed_runs (
                marker TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                applied_at TEXT NOT NULL,
                summary_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        row = conn.execute("SELECT 1 FROM platform_seed_runs WHERE marker = ?", (SEED_MARKER,)).fetchone()
    return row is not None


def _record_seed(summary: dict[str, Any]) -> None:
    with transaction() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO platform_seed_runs (marker, version, applied_at, summary_json)
            VALUES (?, ?, ?, ?)
            """,
            (SEED_MARKER, SEED_VERSION, now_iso(), _json(summary)),
        )


def _ensure_workflow_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id TEXT UNIQUE NOT NULL,
            workflow_name TEXT NOT NULL,
            title TEXT,
            trigger_source TEXT,
            trigger_payload_json TEXT NOT NULL DEFAULT '{}',
            channel TEXT,
            user_id TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            idempotency_key TEXT UNIQUE,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workflow_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_step_id TEXT UNIQUE NOT NULL,
            workflow_run_id TEXT NOT NULL,
            sequence_no INTEGER NOT NULL,
            step_name TEXT NOT NULL,
            agent_name TEXT,
            tool_name TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            input_payload_json TEXT NOT NULL DEFAULT '{}',
            output_payload_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending_confirmations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            confirmation_id TEXT UNIQUE NOT NULL,
            action_type TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            risk_level TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending',
            source_channel TEXT,
            source_user_id TEXT,
            workflow_run_id TEXT,
            decided_by TEXT,
            decided_at TEXT,
            decision_notes TEXT,
            result_payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS safety_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_key TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'candidate',
            source_type TEXT,
            source_id TEXT,
            scene TEXT,
            risk_level TEXT,
            area TEXT,
            contractor TEXT,
            description TEXT,
            recommended_action TEXT,
            template_ids_json TEXT NOT NULL DEFAULT '[]',
            classification_id INTEGER,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            evidence_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def seed_jobs(conn: sqlite3.Connection) -> int:
    ensure_job_schema()
    count = 0
    templates = [
        ("external_info_monitor", "外部讯息定时监听", "external_info", "success"),
        ("rag_upload", "RAG 制度文档入库", "rag", "success"),
        ("automation_workflow", "吊运专项自动巡检", "automation_scheduler", "success"),
        ("skill_test", "视觉巡检 Skill 验证", "visual_patrol", "success"),
        ("agent_workflow", "隐患 intake 工作流", "agent_orchestrator", "success"),
    ]
    for day in range(15):
        for hour, (job_type, title, module, status) in [
            (8, templates[0]),
            (10, templates[1 % len(templates)]),
            (14, templates[2]),
            (17, templates[3]),
        ]:
            if random.random() < 0.15:
                continue
            created = _rand_ts(day, hour, random.randint(0, 59))
            finished = (datetime.fromisoformat(created) + timedelta(minutes=random.randint(3, 45))).isoformat()
            job_id = f"job_seed_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT OR IGNORE INTO job_runs (
                    job_id, job_type, title, status, progress, source_module, request_json,
                    result_json, created_at, started_at, finished_at, updated_at
                ) VALUES (?, ?, ?, ?, 100, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    job_type,
                    title,
                    status if random.random() > 0.08 else "failed",
                    module,
                    _json({"seed": True, "day": day}),
                    _json({"ok": True, "summary": f"{title}完成"}),
                    created,
                    created,
                    finished,
                    finished,
                ),
            )
            count += 1
    return count


def seed_external_monitor(conn: sqlite3.Connection) -> tuple[int, int]:
    # Schema is ensured in main() before the shared transaction opens.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS risk_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id TEXT UNIQUE NOT NULL,
            report_id TEXT,
            source_category TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT,
            title TEXT NOT NULL,
            summary TEXT,
            priority TEXT NOT NULL,
            risk_level TEXT,
            emoji_tag TEXT NOT NULL DEFAULT '📰',
            keywords_json TEXT DEFAULT '[]',
            location TEXT,
            event_date TEXT,
            recommended_action TEXT,
            is_confirmed INTEGER DEFAULT 1,
            payload_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS external_risk_briefing_reports (
            report_id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_run_id TEXT,
            title TEXT,
            summary TEXT,
            briefing_text TEXT,
            report_images_json TEXT DEFAULT '[]',
            report_links_json TEXT DEFAULT '[]',
            tool_results_json TEXT DEFAULT '[]',
            config_json TEXT DEFAULT '{}',
            payload_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    run_count = 0
    card_count = 0
    for day in range(15):
        started = _rand_ts(day, 8, 15)
        finished = (datetime.fromisoformat(started) + timedelta(minutes=random.randint(2, 12))).isoformat()
        run_id = f"monitor-seed-{day:02d}-{uuid.uuid4().hex[:6]}"
        wf_id = f"wf-brief-{day:02d}-{uuid.uuid4().hex[:8]}"
        cards = random.randint(2, 6)
        conn.execute(
            """
            INSERT OR IGNORE INTO external_monitor_runs (
                run_id, status, started_at, finished_at, duration_ms, workflow_run_id,
                card_count, new_raw_count, new_event_count, duplicate_count, alert_count,
                source_count, summary_json, created_at, updated_at
            ) VALUES (?, 'success', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                started,
                finished,
                random.randint(120000, 720000),
                wf_id,
                cards,
                cards + random.randint(0, 3),
                max(1, cards - 1),
                random.randint(0, 2),
                random.randint(0, 1),
                3,
                _json({"seed": True, "trigger": "schedule"}),
                started,
                finished,
            ),
        )
        run_count += 1

        report_id = wf_id
        conn.execute(
            """
            INSERT OR IGNORE INTO external_risk_briefing_reports (
                workflow_run_id, title, summary, briefing_text,
                report_images_json, report_links_json, tool_results_json,
                config_json, payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, '[]', '[]', '[]', ?, ?, ?, ?)
            """,
            (
                wf_id,
                f"赤瞳示范项目 · 外部安全讯息简报 {started[:10]}",
                f"汇总近 24 小时天气、官方与媒体讯息，识别 {cards} 条需关注风险。",
                f"【{started[:10]} 简报】今日需关注施工區域 PPE 与极端天气叠加风险；"
                f"官方发布高处作业提示；媒体持续讨论吊运安全。建议加强 11 路 CCTV 巡检频次。",
                _json({"lookback_hours": 24}),
                _json({"seed": True}),
                started,
                finished,
            ),
        )

        batch: list[dict[str, Any]] = []
        if day % 2 == 0:
            batch.append(
                {
                    "title": random.choice(WEATHER_TITLES),
                    "summary": "预计下午有骤雨，户外吊装需评估暂停。",
                    "priority": "P1",
                    "risk_level": "high",
                    "source_category": "weather",
                    "source_name": "香港天文台",
                    "keywords": ["暴雨", "天气"],
                    "recommended_action": "评估户外吊运是否暂停",
                }
            )
        batch.append(
            {
                "title": random.choice(OFFICIAL_TITLES),
                "summary": "监管方强调高处作业许可与 PPE 合规。",
                "priority": "P2",
                "risk_level": "medium",
                "source_category": "official",
                "source_name": "劳工处",
                "keywords": ["高处作业", "PPE"],
                "recommended_action": "对照制度开展自查",
            }
        )
        if day % 3 == 0:
            batch.append(
                {
                    "title": random.choice(MEDIA_TITLES),
                    "summary": "业界讨论吊运事故教训，建议加强视觉巡检。",
                    "priority": "P1" if day > 10 else "P2",
                    "risk_level": "high" if day > 10 else "medium",
                    "source_category": "media",
                    "source_name": "明报",
                    "keywords": ["吊运", "事故"],
                    "recommended_action": "启动吊运专项巡检",
                }
            )
        for card in batch:
            card_id = card.get("card_id") or uuid.uuid4().hex[:12]
            conn.execute(
                """
                INSERT OR IGNORE INTO risk_cards (
                    card_id, report_id, source_category, source_name, source_url, title, summary,
                    priority, risk_level, emoji_tag, keywords_json, recommended_action,
                    is_confirmed, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                """,
                (
                    card_id,
                    str(report_id),
                    card.get("source_category", "media"),
                    card.get("source_name", ""),
                    card.get("source_url") or "",
                    card.get("title", ""),
                    card.get("summary"),
                    card.get("priority", "P2"),
                    card.get("risk_level"),
                    card.get("emoji_tag", "📰"),
                    _json(card.get("keywords", [])),
                    card.get("recommended_action"),
                    _json({"seed": True}),
                    started,
                    finished,
                ),
            )
            card_count += 1
    return run_count, card_count


def seed_workflows_and_cases(conn: sqlite3.Connection) -> tuple[int, int, int]:
    _ensure_workflow_schema(conn)
    wf_count = case_count = conf_count = 0
    contractors = ["中建香港", "利基工程", "协兴建筑"]
    for index, (scene, area, risk, status) in enumerate(CASE_SCENES):
        day = index % 14
        created = _rand_ts(day, 9 + index % 6, index * 3 % 60)
        updated = (datetime.fromisoformat(created) + timedelta(hours=random.randint(1, 72))).isoformat()
        case_key = f"seed-case-{index+1:03d}"
        conn.execute(
            """
            INSERT OR IGNORE INTO safety_cases (
                case_key, status, source_type, source_id, scene, risk_level, area, contractor,
                description, recommended_action, first_seen_at, last_seen_at, created_at, updated_at
            ) VALUES (?, ?, 'visual_patrol', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_key,
                status,
                f"patrol-seed-{day}",
                scene,
                risk,
                area,
                random.choice(contractors),
                f"{area}发现{scene}，需安全主任复核。",
                "通知分包整改并上传复查照片",
                created,
                updated,
                created,
                updated,
            ),
        )
        case_count += 1

        wf_id = f"wf-seed-{index+1:03d}-{uuid.uuid4().hex[:6]}"
        wf_name = random.choice(
            [
                "workflow_visual_patrol_closed_loop",
                "workflow_daily_risk_briefing",
                "workflow_lifting_safety_patrol",
                "workflow_hazard_intake",
            ]
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO workflow_runs (
                workflow_run_id, workflow_name, title, trigger_source, channel, user_id,
                status, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, 'seed_script', 'local_web', 'safety_officer', 'completed', ?, ?, ?)
            """,
            (
                wf_id,
                wf_name,
                f"历史工作流 · {scene}",
                _json({"seed": True, "case_key": case_key}),
                created,
                updated,
            ),
        )
        wf_count += 1
        for seq, (step, agent, tool) in enumerate(
            [
                ("capture_and_detect", "赤瞳守护者", "vlm_detect"),
                ("draft_case", "赤瞳守护者", "build_visual_patrol_draft"),
                ("assign_rectification", "赤瞳中台", "generate_rectification_notice"),
            ],
            start=1,
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO workflow_steps (
                    workflow_step_id, workflow_run_id, sequence_no, step_name, agent_name, tool_name,
                    status, output_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?)
                """,
                (
                    f"step-{wf_id}-{seq}",
                    wf_id,
                    seq,
                    step,
                    agent,
                    tool,
                    _json({"ok": True}),
                    created,
                    updated,
                ),
            )

        if index % 2 == 0:
            conf_id = f"conf-seed-{index+1:03d}"
            action = random.choice(["generate_rectification_notice", "send_feishu_message", "close_safety_case"])
            conf_status = random.choice(["approved", "approved", "pending", "rejected"])
            conn.execute(
                """
                INSERT OR IGNORE INTO pending_confirmations (
                    confirmation_id, action_type, title, summary, payload_json, risk_level, status,
                    source_channel, source_user_id, workflow_run_id, decided_by, decided_at,
                    result_payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'local_web', 'safety_officer', ?, ?, ?, ?, ?, ?)
                """,
                (
                    conf_id,
                    action,
                    f"确认：{scene} 后续处置",
                    "历史待确认记录（演示数据）",
                    _json({"case_key": case_key, "seed": True}),
                    risk,
                    conf_status,
                    wf_id,
                    "safety_officer" if conf_status == "approved" else None,
                    updated if conf_status == "approved" else None,
                    _json({"ok": conf_status == "approved"}),
                    created,
                    updated,
                ),
            )
            conf_count += 1
    return wf_count, case_count, conf_count


def seed_chat() -> int:
    db_path = settings.chitung_data_dir / "chitung_center.db"
    chat_store.ensure_schema()
    conn = sqlite3.connect(db_path)
    count = 0
    for index, (title, user_msg) in enumerate(CHAT_TOPICS):
        day = index % 14
        created = _rand_ts(day, 11 + index % 5, 10)
        reply_at = (datetime.fromisoformat(created) + timedelta(seconds=random.randint(8, 40))).isoformat()
        session_id = f"chat_seed_{index+1:03d}"
        conn.execute(
            """
            INSERT OR IGNORE INTO chat_sessions (
                session_id, title, channel, user_id, route, module, metadata_json,
                created_at, updated_at, message_count
            ) VALUES (?, ?, 'local_web', 'demo_user', 'center', 'assistant', ?, ?, ?, 2)
            """,
            (session_id, title, _json({"seed": True}), created, reply_at),
        )
        for role, content, ts in (
            ("user", user_msg, created),
            (
                "assistant",
                f"已处理「{title}」。这是系统上线两周以来留下的会话摘要，包含制度检索、巡检汇总与整改建议。",
                reply_at,
            ),
        ):
            conn.execute(
                """
                INSERT OR IGNORE INTO chat_messages (
                    message_id, session_id, role, content, status, intent_json, tool_results_json,
                    cards_json, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, 'completed', '{}', '[]', '[]', ?, ?)
                """,
                (f"msg_seed_{session_id}_{role}", session_id, role, content, _json({"seed": True}), ts),
            )
            count += 1
    conn.commit()
    conn.close()
    return count


def seed_automation_history(conn: sqlite3.Connection) -> int:
    count = 0
    for day in range(14):
        if day % 1 != 0 and day != 13:
            pass
        for slot in (6, 12, 18):
            started = _rand_ts(day, slot, random.randint(0, 20))
            finished = (datetime.fromisoformat(started) + timedelta(minutes=random.randint(18, 55))).isoformat()
            run_id = f"autorun_seed_{day:02d}{slot:02d}_{uuid.uuid4().hex[:6]}"
            conn.execute(
                """
                INSERT OR IGNORE INTO automation_runs (
                    run_id, task_id, triggered_by, status, started_at, finished_at,
                    workflow_run_id, result_summary, result_json, created_at
                ) VALUES (?, 'auto_lifting_safety_patrol_6h', 'scheduler', 'success', ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    started,
                    finished,
                    f"wf-auto-lift-{day:02d}{slot:02d}",
                    f"已完成 11 路吊运专项巡检，发现 {random.randint(2, 8)} 个目标。",
                    _json({"ok": True, "seed": True}),
                    started,
                ),
            )
            count += 1
    last = _rand_ts(13, 12, 10)
    conn.execute(
        """
        UPDATE automation_tasks SET last_run_at = ?, last_run_status = 'success',
            last_run_summary = ?, updated_at = ?
        WHERE task_id = 'auto_lifting_safety_patrol_6h'
        """,
        (last, "已完成 11 路吊运专项巡检（历史种子数据）", now_iso()),
    )
    return count


def seed_hybrid_orchestration() -> int:
    db_path = settings.chitung_data_dir / "hybrid_orchestration.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS orchestration_plans (
            plan_id TEXT PRIMARY KEY,
            session_id TEXT,
            user_input TEXT NOT NULL,
            workflow TEXT,
            planner_mode TEXT,
            status TEXT NOT NULL,
            proposed_actions_json TEXT NOT NULL DEFAULT '[]',
            selected_action_ids_json TEXT NOT NULL DEFAULT '[]',
            result_json TEXT NOT NULL DEFAULT '{}',
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    count = 0
    for index, (workflow, user_input) in enumerate(HYBRID_PLANS * 3):
        day = index % 14
        created = _rand_ts(day, 15, index * 5 % 60)
        updated = (datetime.fromisoformat(created) + timedelta(minutes=random.randint(2, 20))).isoformat()
        plan_id = f"plan_seed_{index+1:03d}"
        conn.execute(
            """
            INSERT OR IGNORE INTO orchestration_plans (
                plan_id, session_id, user_input, workflow, planner_mode, status,
                proposed_actions_json, result_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'llm', ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                f"chat_seed_{index % 8 + 1:03d}",
                user_input,
                workflow,
                random.choice(["SUCCEEDED", "SUCCEEDED", "FAILED", "PENDING_CONFIRMATION"]),
                _json([{"tool_name": "draft_daily_risk_briefing", "risk_level": "medium"}]),
                _json({"ok": True, "seed": True}),
                created,
                updated,
            ),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def _compact_video_report(day: int, cameras: list[dict[str, Any]]) -> dict[str, Any]:
    created = _rand_ts(day, 7 + day % 3, 30)
    report_id = f"video-seed-{created[2:10].replace('-', '')}-{uuid.uuid4().hex[:8]}"
    labels_pool = ["人员", "安全帽", "反光衣", "塔式起重机", "挖掘机", "泥头车"]
    camera_reports = []
    total_detections = 0
    for camera in cameras[:11]:
        detections = random.randint(0, 3)
        total_detections += detections
        camera_reports.append(
            {
                "camera_id": camera["id"],
                "camera_name": camera.get("name") or camera["id"],
                "area": camera.get("area") or "施工區域",
                "success": True,
                "detection_count": detections,
                "summary": {
                    "text": f"{'发现' if detections else '未发现'}明显风险，检测 {detections} 个目标。",
                    "risk_level": random.choice(["low", "medium", "high"]) if detections else "low",
                },
                "detections": [{"label": random.choice(labels_pool)} for _ in range(detections)],
            }
        )
    return {
        "report_id": report_id,
        "created_at": created,
        "user_question": "定时视觉巡检：PPE、机械作业半径、吊运相关风险",
        "direction": "定时视觉巡检：PPE、机械作业半径、吊运相关风险",
        "refined_prompt": "作为香港工地安全巡检专家，请检查 PPE、机械作业区隔离与吊运相关风险。",
        "prompt_source": "seed",
        "camera_count": len(camera_reports),
        "camera_ids": [c["camera_id"] for c in camera_reports],
        "camera_names": [c["camera_name"] for c in camera_reports],
        "summary": {
            "text": f"已完成 {len(camera_reports)} 路摄像头检测，共 {total_detections} 个目标。",
            "detection_count": total_detections,
            "high_risk_count": random.randint(0, 2),
            "labels": random.sample(labels_pool, k=min(4, len(labels_pool))),
        },
        "cameras": camera_reports,
        "ok": True,
        "seed": True,
    }


def seed_video_detection(cameras: list[dict[str, Any]]) -> int:
    from chitung_center.workbench_video_detection_service import _prepend_report, _read_reports

    existing = _read_reports()
    seeded_ids = {item.get("report_id") for item in existing if str(item.get("report_id", "")).startswith("video-seed-")}
    added = 0
    for day in range(14):
        report = _compact_video_report(day, cameras)
        if report["report_id"] in seeded_ids:
            continue
        persist_video_detection_report(report, settings.chitung_data_dir / "video_detection_results.db")
        _prepend_report(report)
        added += 1
    return added


def seed_reports() -> int:
    reports_dir = settings.chitung_data_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for day in range(14):
        stamp = (START_DATE + timedelta(days=day)).strftime("%Y%m%d_080000")
        path = reports_dir / f"daily_safety_{stamp}.md"
        if path.exists():
            continue
        open_cases = random.randint(1, 5)
        high_risk = random.randint(0, 2)
        path.write_text(
            "\n".join(
                [
                    "# 每日安全简报 daily_safety",
                    "",
                    f"- 生成时间：{(START_DATE + timedelta(days=day)).strftime('%Y-%m-%d %H:%M:%S')}",
                    "- 报告类型：daily_safety",
                    f"- 涉及隐患：{open_cases} 条（高风险 {high_risk} 条）",
                    "",
                    "## 巡检摘要",
                    f"- 完成 {random.randint(8, 11)}/11 路 CCTV 视觉巡检。",
                    "- 主要标签：人员、PPE、塔式起重机、泥头车。",
                    "",
                    "## 外部讯息",
                    "- 天气与官方讯息已纳入外部监听简报。",
                    "",
                    "## 建议动作",
                    "- 对高风险隐患优先发送整改通知。",
                    "- 吊运作业区加强反光衣与警戒区检查。",
                    "- 本报告为系统历史演示数据，确认后可对外发送。",
                ]
            ),
            encoding="utf-8",
        )
        count += 1
    return count


def seed_long_term_memory() -> int:
    path = settings.chitung_data_dir / "long_term_memory.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# 赤瞳长期记忆\n"
    added = 0
    notes = [
        "完成 11 路 CCTV 视觉巡检流程联调，执行中心可查看任务。",
        "外部讯息监听改为每小时自动抓取，P1 卡片进入待确认。",
        "上传 6 份安全制度 PDF 至耀耀知识库。",
        "工作台支持润色检测提示词后再批量检测。",
        "自动化页面新增 30 分钟 PPE 巡检任务。",
        "隐患案例与整改通知闭环流程打通。",
        "吊运专项巡检工作流联调，支持多图报告。",
        "长期记忆页面改为 Markdown 统一文档。",
        "外部风险卡片增加 LLM 富化开关。",
        "统一执行中心聚合 job / skill / 自动化任务。",
        "表格映射模块接入 C-SMART 自动填表脚本。",
        "DocMate 文档助手接入中台 AI 面板。",
        "视觉巡检批量接口返回 patrol-output 标注图。",
        "吊运专项巡检挂到后端 6 小时自动调度。",
    ]
    for day in range(14):
        date_str = (START_DATE + timedelta(days=day)).strftime("%Y-%m-%d")
        section = f"## {date_str}"
        if section in text:
            continue
        bullets = random.sample(notes, k=3)
        block = section + "\n\n" + "\n".join(f"- {item}" for item in bullets) + "\n"
        text = text.rstrip() + "\n\n" + block
        added += 1
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return added


def seed_audit_entries() -> int:
    path = settings.chitung_data_dir / "audit.jsonl"
    events = [
        ("workflow_completed", {"workflow_name": "workflow_daily_risk_briefing"}),
        ("visual_patrol_batch_finished", {"camera_count": 11, "success_count": 11}),
        ("tool_call_requested", {"tool_name": "search_policy_clauses"}),
        ("tool_call_completed", {"tool_name": "refine_detection_prompt", "ok": True}),
        ("tool_call_requested", {"tool_name": "workbench_video_detection"}),
        ("tool_call_completed", {"tool_name": "generate_rectification_notice", "ok": True}),
        ("confirmation_resolved", {"action_type": "generate_rectification_notice", "decision": "approved"}),
        ("rag_document_uploaded", {"collection": "safety"}),
        ("long_term_memory_updated", {"source": "daily_summary"}),
        ("external_monitor_run_finished", {"card_count": 4}),
    ]
    lines: list[str] = []
    for day in range(14):
        for hour in (8, 11, 14, 17):
            if random.random() < 0.25:
                continue
            ts = _rand_ts(day, hour, random.randint(0, 59))
            for event_type, payload in random.sample(events, k=random.randint(1, 3)):
                payload = {**payload, "seed": True}
                lines.append(
                    _json(
                        {
                            "audit_id": str(uuid.uuid4()),
                            "timestamp": ts,
                            "event_type": event_type,
                            "payload": payload,
                        }
                    )
                )
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")
    return len(lines)


def backdate_rag_meta() -> int:
    path = settings.chitung_data_dir / "rag_meta.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    count = 0
    day = 0
    for key, item in data.items():
        if key == "builtin-safety-management-rules":
            continue
        if not isinstance(item, dict):
            continue
        if item.get("seed_backdated"):
            continue
        item["created_at"] = _rand_ts(day % 10, 10 + day % 6, 0)
        item["seed_backdated"] = True
        day += 1
        count += 1
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-run even if seed marker exists")
    args = parser.parse_args()

    if _seed_marker_exists() and not args.force:
        print("SKIP: usage history already seeded (use --force to re-run)")
        return 0

    config = get_app_config()
    cameras = [c for c in config.get("cameras", []) if isinstance(c, dict) and c.get("enabled", True)]

    ensure_platform_schema()
    ensure_job_schema()
    ensure_automation_schema()
    ensure_external_monitor_schema()

    summary: dict[str, Any] = {"seed_version": SEED_VERSION, "range": [START_DATE.isoformat(), END_DATE.isoformat()]}

    with transaction() as conn:
        summary["jobs"] = seed_jobs(conn)
        monitor_runs, risk_cards = seed_external_monitor(conn)
        summary["external_monitor_runs"] = monitor_runs
        summary["risk_cards"] = risk_cards
        wf, cases, conf = seed_workflows_and_cases(conn)
        summary["workflow_runs"] = wf
        summary["safety_cases"] = cases
        summary["confirmations"] = conf
        summary["automation_runs"] = seed_automation_history(conn)

    summary["chat_messages"] = seed_chat()
    summary["hybrid_plans"] = seed_hybrid_orchestration()
    summary["video_reports"] = seed_video_detection(cameras)
    summary["markdown_reports"] = seed_reports()
    summary["memory_sections"] = seed_long_term_memory()
    summary["audit_lines"] = seed_audit_entries()
    summary["rag_meta_backdated"] = backdate_rag_meta()

    _record_seed(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
