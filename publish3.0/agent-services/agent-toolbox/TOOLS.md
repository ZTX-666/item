# AgentToolbox Tool Inventory

This inventory records the local programs wrapped by AgentToolbox.

## New Backend Tool Batches

These tools are first-pass backend capabilities for Chitung Center. Some are fully working rule/SQLite tools; some are deliberate placeholders that reserve stable APIs before wiring the final engines.

- Form templates: `search_form_templates`, `get_form_template_detail`, `suggest_forms_for_case`, `prefill_form_fields`, `generate_docx_from_template`, `export_form_record`
- Case workflow: `create_safety_case`, `update_safety_case_status`, `assign_safety_case`, `add_case_evidence`, `generate_rectification_notice`, `generate_warning_letter`, `close_case_with_review`
- Local queries: `query_safety_cases`, `query_external_risks`, `query_form_records`, `query_pending_actions`, `get_dashboard_metrics`, `export_safety_data`
- Communications: `list_whatsapp_groups`, `draft_group_message`, `send_group_message_with_confirm`, `archive_sent_notification`, `extract_hazards_from_recent_chats`, `summarize_chat_group_daily`
- VLM/CCTV workflows: `capture_camera_snapshot`, `run_vlm_detection_batch`, `classify_vlm_hazard`, `create_case_from_vlm`, `compare_vlm_before_after`, `schedule_camera_patrol`
- Documents/OCR: `ocr_document_or_image`, `extract_tables_from_document`, `classify_document_type`, `extract_certificate_fields`, `check_certificate_expiry`, `summarize_policy_document`, `search_policy_clauses`
- Audit/permissions: `record_tool_audit`, `record_llm_audit`, `list_audit_logs`, `manage_user_roles`, `check_action_permission`
- Prompt templates: `list_prompt_templates`, `render_prompt_template`
- External risk to forms: `link_external_risk_to_forms`
- Open-source reference adapters: `list_reference_adapters`, `map_mcp_construction_tool`, `normalize_visual_safety_event`, `evaluate_hazard_zone_rules`, `recommend_visual_safety_pipeline`, `draft_safety_report_from_events`
- Future reserved operations: scheduling, platform events, review queue, project context, equipment/certificates, contractor scoring, media evidence, reports, RFI/site memo/submittal, and LLM gateway helpers. These are generated from `future_operations.py` and exposed through `GET /tools`, MCP, `POST /tools/call`, and `POST /tools/future/{tool_name}`.
- Chitung workflow tools: 24 reserved multi-agent workflow templates plus supplemental missing tools for PTW, stop-work orders, incident timelines, weather emergency actions, Feishu message parsing, and audit packages. These live under `agent_toolbox/workflow_tools/` and are exposed through `GET /tools`, MCP, and `POST /tools/call`.

Reference adapters do not copy third-party project code into AgentToolbox. They reserve stable local tool contracts inspired by `MCP-construction`, `HazardLens`, `Construction-PPE-Detection`, `Construction-Hazard-Detection`, and `SafetyVision`. If a reference project is adopted later, its implementation can replace the adapter internals without changing Chitung Center workflows.

## rtmp_snapshot

- Source: `J:\China Oversea  Final\FinalAgentSuite\rtmp-tools\rtmp_snapshot.py`
- Runtime: Python + OpenCV
- Input: RTMP URL, output count, interval, optional file prefix
- Output: JPEG screenshots in the task directory
- Wrapper endpoint: `POST /tools/rtmp_snapshot`

## vlm_detect

- Source: `J:\China Oversea  Final\FinalAgentSuite\vlm-detection\detect.py`
- Runtime: Python + ultralytics + OpenCV + YAML, preferably through the existing conda environment
- Input: image path or image directory, confidence, device, model selection
- Output: annotated images and `detections_*.json`
- Wrapper endpoint: `POST /tools/vlm_detect`

## whatsapp_search

- Source: `J:\China Oversea  Final\FinalAgentSuite\whatsapp-archive\app-server`
- Runtime: Node/Express service on `http://127.0.0.1:8787`
- Input: keyword, optional chat JID, limit
- Output: matching archived WhatsApp messages
- Wrapper endpoint: `POST /tools/whatsapp_search`

## whatsapp_download_media

- Source: `J:\China Oversea  Final\FinalAgentSuite\whatsapp-archive\app-server`
- Runtime: Node/Express service on `http://127.0.0.1:8787`
- Input: WhatsApp message ID, optional destination directory
- Output: downloaded attachment metadata
- Wrapper endpoint: `POST /tools/whatsapp_download_media`

## generate_report

- Source: `J:\China Oversea  Final\FinalAgentSuite\report-generators\generate_community_doc.py`
- Runtime: Python + python-docx
- Input: fixed template for now, optional output path
- Output: generated Word document
- Wrapper endpoint: `POST /tools/generate_report`

## notify_feishu

- Source: AgentToolbox built-in adapter
- Runtime: Feishu custom bot webhook
- Input: text message
- Output: Feishu webhook API response
- Wrapper endpoint: `POST /tools/notify_feishu`

## Feishu OpenAPI Bot Tools

- Source: Feishu Open Platform server APIs and event callbacks
- Runtime: Python + `requests` + local SQLite
- Inputs: app credentials in `.env`, `chat_id`/`open_id`, text/card payloads, callback payloads
- Outputs: Feishu API responses, local event archive, platform event payloads
- Callback endpoint: `POST /integrations/feishu/events`
- Wrapper endpoints:
  - `POST /tools/feishu_get_tenant_access_token`
  - `POST /tools/feishu_send_text_message`
  - `POST /tools/feishu_send_interactive_card`
  - `POST /tools/feishu_build_safety_review_card`
  - `POST /tools/feishu_handle_event_callback`
  - `POST /tools/feishu_list_chats`
  - `POST /tools/feishu_archive_event`
  - `POST /tools/feishu_event_to_platform_event`

Planned platform use:

- Safety review cards for hazards, external-risk briefings, report approval, and form confirmation.
- Feishu message events converted into local `platform_events`.
- All outgoing card actions require human confirmation before affecting safety cases or notifications.

## fetch_hko_weather

- Source: Hong Kong Observatory Open Data API
- Runtime: Python + `requests`
- Input: language and optional HKO `dataType` list
- Output: raw official weather JSON plus active warning summary and rule-based risk level
- Wrapper endpoint: `POST /tools/fetch_hko_weather`

## fetch_hk_safety_updates

- Source: approved Hong Kong official and media sources
- Runtime: Python + `requests`
- Input: source whitelist, keyword list, per-source limit
- Output: matched government/media updates with source, title, URL, matched keywords, and risk level
- Wrapper endpoint: `POST /tools/fetch_hk_safety_updates`
- Default official sources: Labour Department, Housing Authority/Housing Department, Development Bureau, Buildings Department, Occupational Safety and Health Council
- Default media sources: HK01, Sing Tao

## fetch_hk_industrial_news

- Source: HK01 and Sing Tao only
- Runtime: Python + `requests`
- Input: optional media source whitelist, keyword list, per-source limit
- Output: matched industrial-accident news items with source, URL, keywords, and risk level
- Wrapper endpoint: `POST /tools/fetch_hk_industrial_news`

## persist_external_risk_items

- Source: fetched weather/news/government update results
- Runtime: Python + local SQLite
- Input: weather result, safety update result, or direct external risk items
- Output: inserted/updated counts in `external_risk_items`
- Wrapper endpoint: `POST /tools/persist_external_risk_items`

## summarize_external_risks

- Source: fetched weather/news/government update results
- Runtime: Python rule summarizer, future LLM prompt enhancement
- Input: weather result, safety update result, or direct external risk items
- Output: risk counts, highest risk level, grouped items, recommended actions
- Wrapper endpoint: `POST /tools/summarize_external_risks`

## draft_daily_risk_briefing

- Source: external risk summary
- Runtime: Python Markdown drafter, future LLM prompt enhancement
- Input: weather result, safety update result, direct items, optional project/audience/language
- Output: Markdown briefing draft
- Wrapper endpoint: `POST /tools/draft_daily_risk_briefing`

## init_safety_database

- Source: AgentToolbox built-in SQLite schema initializer
- Runtime: Python standard library `sqlite3`
- Input: optional `reset`
- Output: local `safety_platform.db`
- Wrapper endpoint: `POST /tools/init_safety_database`

## ai_archive_classifier

- Source: AgentToolbox built-in rule classifier for safety archive intake
- Runtime: Python, local SQLite
- Input: source type, text/description, area, contractor, evidence paths, raw payload
- Output: safety classification, risk level, recommended action, optional `safety_cases` record
- Wrapper endpoint: `POST /tools/ai_archive_classifier`

## ingest_chat_hazards

- Source: ChitongLingxun/WhatsApp-style messages or existing WhatsApp archive search
- Runtime: Python, optional WhatsApp archive service
- Input: direct `messages` array or query parameters `q`, `chat`, `limit`
- Output: classified chat hazards, source message rows, candidate safety cases
- Wrapper endpoint: `POST /tools/ingest_chat_hazards`

## ingest_vlm_hazards

- Source: `vlm_detect` JSON output
- Runtime: Python, local SQLite
- Input: `detections` object or `vlm_result_path`
- Output: visual hazard candidates from PPE violations and plant/person combinations
- Wrapper endpoint: `POST /tools/ingest_vlm_hazards`

## dedupe_and_link_hazards

- Source: local `safety_platform.db`
- Runtime: Python, local SQLite
- Input: optional case ID/status/limit
- Output: duplicate groups and merged evidence on keeper cases
- Wrapper endpoint: `POST /tools/dedupe_and_link_hazards`

## connect_hazard_actions

- Source: local `safety_cases`
- Runtime: Python, local SQLite
- Input: case ID or status, optional form suggestion flag
- Output: next-step action suggestions and `form_records` suggestions
- Wrapper endpoint: `POST /tools/connect_hazard_actions`

## record_classification_feedback

- Source: safety officer manual review
- Runtime: Python, local SQLite
- Input: classification/case ID and corrected scene, risk, status, or notes
- Output: feedback record for future classifier tuning
- Wrapper endpoint: `POST /tools/record_classification_feedback`

