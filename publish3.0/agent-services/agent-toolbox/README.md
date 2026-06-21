# AgentToolbox

AgentToolbox wraps several existing local programs under `J:\China Oversea  Final` as agent-callable tools.

It does not merge or rewrite the original programs. It provides a unified HTTP API and a lightweight MCP stdio adapter.

## Wrapped Tools

- `rtmp_snapshot`: capture screenshots from an RTMP stream.
- `vlm_detect`: run dual YOLO construction-site detection.
- `whatsapp_search`: search archived WhatsApp messages through the existing `app-server`.
- `whatsapp_download_media`: download WhatsApp attachments through the existing `app-server`.
- `generate_report`: generate the existing Word report template.
- `notify_feishu`: push text to a Feishu custom bot webhook.

## Setup

```powershell
cd "J:\China Oversea  Final\FinalAgentSuite\agent-toolbox"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` if paths or ports are different.

## Run HTTP Server

```powershell
cd "J:\China Oversea  Final\FinalAgentSuite\agent-toolbox"
.\.venv\Scripts\Activate.ps1
python run_server.py
```

Default URL:

```text
http://127.0.0.1:8899
```

Useful endpoints:

```text
GET  /health
GET  /tools
POST /tools/call
POST /tools/rtmp_snapshot
POST /tools/vlm_detect
POST /tools/whatsapp_search
POST /tools/whatsapp_download_media
POST /tools/generate_report
POST /tools/notify_feishu
POST /integrations/feishu/events
POST /tools/feishu_get_tenant_access_token
POST /tools/feishu_send_text_message
POST /tools/feishu_send_interactive_card
POST /tools/feishu_build_safety_review_card
POST /tools/feishu_handle_event_callback
POST /tools/feishu_list_chats
POST /tools/feishu_archive_event
POST /tools/feishu_event_to_platform_event
POST /tools/fetch_hko_weather
POST /tools/fetch_hk_safety_updates
POST /tools/fetch_hk_industrial_news
POST /tools/persist_external_risk_items
POST /tools/summarize_external_risks
POST /tools/draft_daily_risk_briefing
POST /tools/init_safety_database
POST /tools/ai_archive_classifier
POST /tools/ingest_chat_hazards
POST /tools/ingest_vlm_hazards
POST /tools/dedupe_and_link_hazards
POST /tools/connect_hazard_actions
POST /tools/record_classification_feedback
```

New backend tool batches are also available through `GET /tools` and `POST /tools/call`:

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
- Future reserved operations: scheduling, platform events, review queue, project context, equipment/certificates, contractor scoring, media evidence, reports, RFI/site memo/submittal, and LLM gateway helpers. These are exposed through `GET /tools`, MCP, `POST /tools/call`, and `POST /tools/future/{tool_name}`.
- Chitung workflow tools: 24 reserved multi-agent workflow templates and supplemental missing tools under `agent_toolbox/workflow_tools/`. Use `list_workflow_templates`, `get_workflow_template`, `confirm_workflow_action`, or call a `workflow_*` tool through `POST /tools/call`.

## Examples

Capture one RTMP screenshot:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/rtmp_snapshot" `
  -ContentType "application/json" `
  -Body '{"count":1}'
```

Run VLM detection:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/vlm_detect" `
  -ContentType "application/json" `
  -Body '{"source":"J:\\China Oversea  Final\\VLM Detection\\input","conf":0.25}'
```

Search WhatsApp archive:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/whatsapp_search" `
  -ContentType "application/json" `
  -Body '{"q":"你好","limit":10}'
```

Generate report:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/generate_report" `
  -ContentType "application/json" `
  -Body '{}'
```

## MCP Adapter

Run:

```powershell
cd "J:\China Oversea  Final\FinalAgentSuite\agent-toolbox"
.\.venv\Scripts\Activate.ps1
python run_mcp.py
```

Example MCP client configuration:

```json
{
  "mcpServers": {
    "agent-toolbox": {
      "command": "J:\\China Oversea  Final\\AgentToolbox\\.venv\\Scripts\\python.exe",
      "args": ["J:\\China Oversea  Final\\AgentToolbox\\run_mcp.py"]
    }
  }
}
```

## Feishu

For one-way push notifications, set:

```text
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
```

Then call `POST /tools/notify_feishu`.

For two-way chat, connect this HTTP API from LangBot, AstrBot, OpenClaw, or a custom Feishu bot.

For Feishu OpenAPI bot integration, set:

```text
FEISHU_APP_ID=
FEISHU_APP_SECRET=
FEISHU_VERIFICATION_TOKEN=
FEISHU_ENCRYPT_KEY=
```

Recommended Feishu platform setup:

- Enable bot capability and add the bot to target chats.
- Grant message sending permissions for `im/v1/messages`.
- Configure event subscription callback URL to `POST /integrations/feishu/events`.
- Subscribe to message receive events and card interaction events as needed.

Useful tools:

- `feishu_send_text_message`: send text by `chat_id` / `open_id`.
- `feishu_build_safety_review_card`: build or send a safety approval card.
- `feishu_handle_event_callback`: handle event payloads and URL verification challenge.
- `feishu_event_to_platform_event`: convert Feishu messages into local platform events.

## Safety Hazard Intake

The safety tools keep all data local in SQLite by default. Configure:

```text
SAFETY_POLICY_TEMPLATES_DIR=E:\China Oversea  Final\safety-policy-templates-20241025
SAFETY_DATABASE_PATH=E:\China Oversea  Final\FinalAgentSuite\agent-toolbox\workspace\safety_platform.db
```

Initialize the database:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/init_safety_database" `
  -ContentType "application/json" `
  -Body '{}'
```

Ingest a chat hazard:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/ingest_chat_hazards" `
  -ContentType "application/json" `
  -Body '{"messages":[{"id":"msg-1","chat":"B2 safety group","sender":"SO","text":"B2区临边护栏被拆，明天必须整改，照片见附件","attachments":["E:/demo/b2-edge.jpg"]}]}'
```

Ingest VLM detections:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/ingest_vlm_hazards" `
  -ContentType "application/json" `
  -Body '{"detections":{"images":[{"image":"E:/demo/cam01.jpg","detections":[{"class_name":"Person","confidence":0.91},{"class_name":"NO-Hardhat","confidence":0.88},{"class_name":"mobile_crane","confidence":0.74}]}]},"area":"B2区"}'
```

Then call `dedupe_and_link_hazards` and `connect_hazard_actions` to merge repeated candidates and create form/action suggestions.

## External Risk Monitoring

`fetch_hko_weather` uses the Hong Kong Observatory Open Data API:

```text
https://data.weather.gov.hk/weatherAPI/opendata/weather.php
```

It fetches current weather, active warnings, warning details, special weather tips, local forecast, and 9-day forecast by default.

`fetch_hk_safety_updates` only uses approved Hong Kong sources:

- Official: Labour Department, Housing Authority/Housing Department, Development Bureau, Buildings Department, Occupational Safety and Health Council.
- Media: HK01 and Sing Tao.

Fetch weather:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/fetch_hko_weather" `
  -ContentType "application/json" `
  -Body '{"lang":"tc"}'
```

Fetch government and media safety updates:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/fetch_hk_safety_updates" `
  -ContentType "application/json" `
  -Body '{"limit_per_source":5}'
```

Fetch only industrial accident news from HK01 and Sing Tao:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/fetch_hk_industrial_news" `
  -ContentType "application/json" `
  -Body '{"limit_per_source":5}'
```

Draft a daily external-risk briefing from fetched inputs:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8899/tools/draft_daily_risk_briefing" `
  -ContentType "application/json" `
  -Body '{"items":[{"source":"demo","source_name":"demo","title":"天文台暴雨警告生效","risk_level":"high","matched_keywords":["暴雨"]}]}'
```

## Safety

- Original programs remain separate.
- Every tool call creates a task directory under `workspace/tasks`.
- Only registered tools can run.
- Do not expose this service to the public internet without authentication.
- Keep `.env` private.

