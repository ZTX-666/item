# Hazard Intake

把聊天、照片说明、VLM 识别结果归档为安全隐患线索。

## Rules

- 先判断是否涉及安全、整改、事故、临边、吊运、电气、消防、PPE、密闭空间、酷热天气。
- 只把必要摘要交给 LLM，原始聊天、图片、视频、附件路径均留在本地。
- 需要发送整改通知、同步企业系统或关闭案件时，必须先生成卡片给人工确认。

## Preferred Tools

- `ingest_chat_hazards`
- `ingest_vlm_hazards`
- `dedupe_and_link_hazards`
- `connect_hazard_actions`
- `record_classification_feedback`
