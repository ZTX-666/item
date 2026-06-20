# Chitung Center Architecture

## Boundary

`chitung-center` is the orchestration layer. It does not replace existing tools.

```text
Local Web / Bot / Desktop
        |
        v
Chitung Center
  - intent router
  - skill loader
  - LLM gateway
  - action cards
  - audit log
        |
        v
AgentToolbox
  - VLM/OCR/document/WhatsApp/SQLite tools
        |
        v
Local data and existing software
```

## Reserved Future Software Slots

- `赤瞳灵讯`: WhatsApp archive/search/send/group messaging.
- `闪闪文档`: Word templates, form prefill, safety report generation.
- `耀耀慧读`: OCR, table extraction, policy parsing.
- `飞书`: approvals, bot commands, notification confirmation.
- `中海通`: enterprise system sync and robot interaction.
- `OpenClaw`: optional reference/adapter, not an MVP dependency.

## Security

- Sensitive data remains local by default.
- Cloud LLM calls must use sanitized and compact context only.
- Dynamic extension is limited to `SKILL.md` instructions.
- Privileged actions must go through built-in audited tools.

## Next Implementation Steps

1. Add real `fetch_hko_weather` and `fetch_hk_industrial_news` tools in AgentToolbox.
2. Add card confirmation workflows for WhatsApp/Feishu sending.
3. Add a small local web UI for chat and cards.
4. Add SQLite-backed task history for Chitung Center itself.
5. Replace rule-only routing with rule-first plus LLM fallback.
