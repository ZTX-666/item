# docmate-edit — DocMate 文档编辑 Skill

DocMate 是独立的 AI 文档编辑助手，用于 DOCX 上传、结构化读取、LLM-first changeset 生成、预览确认、提交和失败重试。它不是 WhatsApp 功能，也不调用 WhatsApp SQL、wacli 或发送确认链路。

## Preferred Tools

- `docmate_read_docx`
- `docmate_generate_changeset`
- `docmate_preview_changeset`
- `docmate_commit_changeset`
- `docmate_retry_changeset`

## Rules

1. 不得在用户预览并确认前提交修改。
2. LLM 生成的 changeset 必须以预览卡片展示，包含 before/after、risk_level、reason 和 change_id。
3. high/medium 风险变更必须提醒用户复核；涉及安全合规含义的改动视为 high。
4. commit 只提交用户选择的 accepted_change_ids，并返回 output_path/download_url。
5. 生成失败或用户反馈“定位不准/不满意”时，使用 retry，并把用户反馈传入下一次 changeset 生成。
6. 默认输出新文件，不覆盖原始 DOCX，除非用户明确指定 save_as。

## Workflow

1. Upload or receive a `.docx` file path.
2. Call `docmate_read_docx` to get `doc_id` and document structure.
3. Call `docmate_generate_changeset` with `doc_id`, instruction, and context.
4. Call `docmate_preview_changeset` and present preview cards.
5. After user confirmation, call `docmate_commit_changeset` with selected change IDs.
6. If generation or matching is unsatisfactory, call `docmate_retry_changeset` with feedback.

## Boundaries

- Do not route DocMate requests to WhatsApp SQL/wacli workflows.
- Do not send messages, create WhatsApp confirmations, or inspect `wacli.db`.
- Do not treat generic safety form filling as DocMate editing unless the user asks to edit/rewrite/replace/commit changes in a DOCX.
