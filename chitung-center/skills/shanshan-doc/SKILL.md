# shanshan-doc — 闪闪文档 Skill

Tool sequence: read → generate → preview → confirm → apply

## Rules
1. NEVER apply changes before user preview and confirmation
2. For high/medium risk changes, require explicit re-confirmation
3. Output file must have a _modified suffix unless user specifies

## Workflow
1. Call docmate_read_docx with file_path → get doc_id + structure
2. Call docmate_generate_changeset with doc_id + instruction → get changeset_id + preview_cards
3. Show preview_cards to user, collect accepted_change_ids
4. Call docmate_apply_changeset with changeset_id + accepted_change_ids + save_as

## EHS Safety Rules
- Risk level HIGH: must show warning banner and require second confirmation
- Risk level MEDIUM: highlight with orange indicator
- Risk level LOW: approve by default
- Never modify content that affects safety compliance without user review
