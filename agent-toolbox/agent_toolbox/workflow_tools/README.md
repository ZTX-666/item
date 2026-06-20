# Chitung Workflow Tools

This folder contains the reserved workflow tool pack for the Chitung multi-agent safety platform.

The goal is to keep the 24 site-safety workflows in one independent folder so future development can replace placeholder steps with real engines without changing the public tool names.

## Tool Types

### 1. Workflow Tools

Each `workflow_*` tool creates a local workflow run, expands the template into ordered steps, records pending confirmations, and writes everything to the local SQLite database.

These tools do not directly send external messages, close cases, or issue stop-work orders. High-risk actions are converted into pending confirmations first.

Examples:

- `workflow_human_hazard_escalation`
- `workflow_external_risk_to_site_action`
- `workflow_daily_start_risk_briefing`
- `workflow_digital_ptw_check`
- `workflow_lifting_safety_patrol`
- `workflow_incident_near_miss_investigation`
- `workflow_stop_work_and_resume_review`
- `workflow_weather_emergency_response`

### 2. Supplemental Reserved Tools

These fill gaps found while mapping the 24 workflows.

Examples:

- `risk_to_detection_prompt`
- `permit_to_work_checker`
- `stop_work_order_generator`
- `incident_timeline_builder`
- `read_rectification_replies`
- `weather_emergency_workflow`
- `audit_package_generator`
- `feishu_parse_message_event`

They currently return structured placeholder results and reserve stable API contracts for later implementation.

### 3. Workflow Management Tools

- `list_workflow_templates`
- `get_workflow_template`
- `confirm_workflow_action`

## Database Tables

The tool pack creates these local tables in `safety_platform.db`:

- `workflow_runs`
- `workflow_steps`
- `pending_confirmations`
- `agent_messages`
- `workflow_artifacts`
- `workflow_event_links`

## Calling Pattern

All tools are registered in AgentToolbox and can be called through:

```text
POST /tools/call
```

Example:

```json
{
  "name": "workflow_human_hazard_escalation",
  "arguments": {
    "project_id": "default",
    "requested_by": "safety_officer",
    "source": "local_chatbox",
    "trigger_payload": {
      "area": "B2",
      "contractor": "示例分判商",
      "description": "疑似吊运警戒区不足，现场证据不足"
    },
    "require_confirmation": true
  }
}
```

The return value includes:

- `workflow_run_id`
- workflow plan
- ordered steps
- required agents
- required tools
- pending confirmations

## Development Notes

Future implementation should preserve public tool names and request schemas. Replace placeholder internals step by step:

1. Connect real camera and VLM engines for visual steps.
2. Connect local RAG and OCR for knowledge steps.
3. Connect precise DOCX templates for document steps.
4. Connect Feishu/WhatsApp callbacks for communication steps.
5. Keep human confirmation before external send, formal notice, stop-work order, resume-work approval, and case closure.
