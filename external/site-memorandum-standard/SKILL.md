---
name: site-memorandum-standard
description: >-
  Generates the standard Site Memorandum (SITE MEMORANDUM / 工地备忘录) **first page
  only**—letterhead, routing block, subject, body, responsibility line, company
  block—matching the user’s Word template field map (1–13) and the layout of a
  reference PDF page 1. Handles Q&A for recipients and body, optional upstream-memo
  rewrite, workspace search for similar memos, persisted project/company/signatory
  defaults, **company letterhead in Word headers**, and a **skill-local contact registry**
  in **`data/contacts.xlsx`** (简称 → 英文姓名/中文检索名/职位/公司/电子签名路径) for To/Copy To/Attn. and optional **e-signature** tied to the signatory. Use when the user asks for 标准版 site memo、SITE MEMORANDUM 第一页、
  工地备忘录标准模板、按 Word 模板生成备忘录主函、联络人库、Excel 联系人、联系人简称、电子签名、**一步生成**，或附带/提及本技能名。
---

# Site Memorandum — Standard (Page 1)

## Goal

Produce **one page** of a Site Memorandum: the **main instruction letter** (same information tier as reference PDF page 1). **Do not** draft continuation pages, circulation slips, or “received by / action / information” reply forms unless the user explicitly asks.

## One-shot generation (一步生成) — default

Users often want **one instruction → one `.docx`**, without rounds of “请确认”.

**When to use:** the user says **一步生成 / 直接生成 / 不要逐步确认 / 不要问答 / 出 Word**，或**一条消息里**已给出收件、抄送、落款、主题/正文要点等足够信息。

**Agent behaviour (mandatory):**

1. **Parse once** from the user message; **resolve** 简称 / 中文名 / 英文名 → `abbrev` by **loading `data/contacts.xlsx` in-process** (same logic as `scripts/contacts_tool.py`, **do not** require the user to run CLI).  
2. **Apply defaults** (below) for anything not given — **do not** open Q&A loops for optional refinements.  
3. **Generate Word in exactly one shell invocation:** run **`scripts/generate_site_memo_docx.py` once** with all flags (resolver + signatory + **auto company** from `--signatory-contact` when `--company` is omitted — **no second command** to fetch company). **Do not** paste `python …` / `pip …` into the chat (see **Chat output hygiene**).  
4. Reply with **only** the **`.docx` absolute path** + optional **one short** line (e.g. what was defaulted).  
5. **Only** stop to ask if **blocking**: e.g. a recipient cannot be resolved **and** the user gave no literal To text.

### Chat output hygiene（省略 run — 默认）

- **一步生成 / 日常出稿：** 对话里 **不展示** 完整 shell 命令流水线；**后台执行**且 **Word 生成应为单次 shell 调用**（`generate_site_memo_docx.py` 已内含联系人解析、落款公司自动填充、**以及签名图存在性判断：有则插入、无则跳过**。**禁止**再单独 `python -c` 查公司、**禁止**为电子签名路径再多跑一次预检）。用户应看到 **结果路径** 与 **极简说明**。  
- **例外：** 用户明确要「复制命令自己跑」、**依赖未安装**需排查、或 **CI/无 Agent 环境** 时，再给出可复制的 `pip` / `python …` 片段。  
- **维护 Excel：** 用户自己在表格里改即可；**不必**为每次改表在聊天里演示 `contacts_tool.py`（除非用户要同步数据库或排查解析）。

**Default values (one-shot):**

| Field | Default if omitted |
|--------|---------------------|
| Your Ref. | `N/A` |
| Pages | `Page 1 of 1` |
| Fax No. | `N/A` |
| Attn. | `-` |
| Date | Session “today” (authoritative calendar date in context) |
| Our Ref. | Next from `.site-memo-standard.json` if present; else `EI-YYYY-NNNN` style placeholder the user can replace |
| Upstream memo rewrite | **No** unless user pasted upstream text |
| By Hand / By Email | Omit |
| Project | User snippet or first line of intent; else `TBD` / `（项目名称待补）` **one** placeholder only |
| Body (11) | 1–2 formal sentences from user intent; unknown facts → **one** closing line e.g. `（图纸编号、位置及责任划分以工程师书面确认为准）` — **not** multiple “待确认” bullets |
| Company (12) | If **`--signatory-contact`** is set and **`--company` is omitted or empty**, the generator **reads `company` from that Excel row** (one shell call — no separate lookup). Else `.site-memo-standard.json` `companyName` if you add that path later; else `（公司名称待补）` once |
| Workspace memo search | **Skip** in one-shot unless user asked “参考历史 memo” |

**Do not** in one-shot mode: ask “是否基于上家 memo”、逐项追问图纸/位置、反复请确认 Fax/Attn. — those belong to **Collaborative** mode only.

## Company letterhead (mandatory for Word)

The original template includes the **company logo + bilingual company name** at the very top. **Every `.docx` generated under this skill must include that graphic in the document header** (not inline in body), unless the user explicitly waives it for a one-off.

1. **One-time asset**  
   - Path: `assets/letterhead.png` **next to this skill’s** `SKILL.md` (same folder level: `site-memorandum-standard/assets/letterhead.png`).  
   - The engineer exports once from the official Word/PDF/snippet (see `assets/PLACE-LETTERHEAD-HERE.txt`).  
   - **Do not redraw** corporate marks from memory; use the user’s supplied PNG.

2. **Generation**  
   - Implemented by **`scripts/generate_site_memo_docx.py`** (`python-docx`, header `letterhead.png`). The agent **runs it in the shell** when producing `.docx`; **omit** pasting the full command in chat unless the user asks (see **Chat output hygiene**).  
   - If `letterhead.png` is missing, the generator still runs but may insert a **reminder line in the Word header**; tell the user to add the PNG and regenerate. Do not silently ship “final” Word without fixing this unless they waive.

3. **Sizing**  
   - Default picture width ~**6.2 in** in header; reduce if the logo overlaps margins. Keep aspect ratio (width only).

4. **Plain-text / Markdown output**  
   - Paste-ready body cannot embed the image; prepend a single line: `[Letterhead: same as Word header / 见 assets/letterhead.png]`.

## Contact registry (联络人库)

Purpose: store **英文姓名 `name`**（**Site Memo 函件与 Word 中凡「姓名」一律只用此字段**）、**中文姓名 `name_zh`**（**仅**用于对话里叫人、以及 `find()` 检索匹配，**不得写入** Memo 的 To/Attn/Copy/落款打印姓名）、**职位 `title`、简称 `abbrev`** (plus optional **`company`**, **`aliases`**, **`signature_image`**) so the user can say **「To 用 xsy」「抄送 徐思源」** 等仍能解析到同一联系人；**`signature_image`** 供 **负责人 (field 13)** 电子签名图。

### Storage

- **Primary path:** `data/contacts.xlsx` beside `SKILL.md` (same skill folder). Edit in **Excel / WPS**; no chat required. See `data/README-CONTACTS.txt` for column headers.  
- **Legacy:** `data/contacts.json` — if present on first load, it is **imported once** into `contacts.xlsx`, backed up as `contacts.json.bak`, then removed.  
- **Override:** `--db` on CLI / `--contacts-db` on the Word script may point to another `.xlsx` (or a legacy `.json`).  
- **Do not** move the default file into random workspace paths unless the user asks.

### Columns (Excel row = one person)

| Column | Meaning |
|--------|---------|
| `abbrev` | 简称（主键，必填） |
| `name` | 英文姓名（Memo 函件显示） |
| `name_zh` | 中文姓名（仅检索/对话，不写进 Memo） |
| `title` | 职位 |
| `company` | 公司（用于 To 行拼接；可空） |
| `aliases` | 别名，单元格内逗号分隔 |
| `signature_image` | 电子签名图路径（绝对或相对技能根目录） |

Equivalent JSON object (for reference only):

```json
{ "abbrev": "xsy", "name": "Xu Siyuan", "name_zh": "徐思源", "title": "ASM", "company": "", "aliases": ["徐工"], "signature_image": "assets/signatures/xsy.png" }
```

- **`abbrev`**: primary key (unique, case-insensitive).  
- **`name`**: English / roman name — **sole name source for all Site Memo text** (To / Attn / Copy / signatory line).  
- **`name_zh`**: 中文姓名 (optional). **Lookup / conversation only**; also matched by `find()` so users can refer by Chinese; **never** paste into memo body or Word routing/signatory name runs.  
- **`aliases`**: optional extra tokens that also resolve (e.g. 昵称).  
- **`signature_image`**: optional string — **absolute path** or path **relative to the skill folder** (parent of `scripts/`). PNG/JPG recommended. Empty string means no e-sig for that row. See `assets/signatures/PLACE-SIGNATURE-IMAGES-HERE.txt`.

### E-signature (电子签名) and field 13

- The **printed** signatory block is **英文姓名 (`name`) + 职位** (field **13**); **`name_zh` is not printed**.  
- When generating `.docx` with **`--signatory-contact <abbrev>`**, the script sets **English `name` + title** from that contact and, **in the same single run**, reads `signature_image`: **if the file exists → insert the image above the rule line** (`____`); **if the path is empty or the file is missing → skip the image** (no placeholder paragraph, no error, no second shell to “check” first). Then **printed English name**, then **title**. Width default **2.2 in** (`--signature-width-inches`).  
- **Agent:** **never** run an extra command only to verify whether a signature PNG exists; the generator already does that internally.  
- **`--signature-image`** on the generator is only for the **literal-path** case (no `signatory-contact`); if **`--signatory-contact` is set**, the Excel **`signature_image`** cell wins.

### Memo line format (resolved)

- Person segment is **always English `name`** (fallback **`abbrev`** if `name` empty — avoid; keep `name` filled). **`name_zh` is never used here.**  
- Default with title: **`Name (Title)`**; if `company` set: **`Company — Name (Title)`**.  
- Override with `--contact-style name_only` on the Word script when needed.

### CLI（可选 — 无 Cursor / 排查时用）

日常 **一步出 Memo** 不必在对话里 **run** 这些；用户可直接改 **`contacts.xlsx`**。仅在 **无 Agent、自动化脚本、或排查解析** 时使用：

```bash
python scripts/contacts_tool.py list
python scripts/contacts_tool.py add --abbrev xsy --name "Xu Siyuan" --name-zh "徐思源" --title "ASM" --company "" --aliases "徐工,XSY" --signature-image "assets/signatures/xsy.png"
python scripts/contacts_tool.py set --abbrev xsy --title "Senior ASM"
python scripts/contacts_tool.py set --abbrev xsy --signature-image "assets/signatures/xsy.png"
python scripts/contacts_tool.py set --abbrev xsy --clear-signature
python scripts/contacts_tool.py show xsy
python scripts/contacts_tool.py resolve --to xsy --copy-to "hwk, xsy"
python scripts/contacts_tool.py remove --abbrev xsy
```

The user normally **edits `data/contacts.xlsx` in Excel**. The agent may **silently** run `contacts_tool.py` when the user asks to sync DB from pasted rows — **without** dumping commands unless requested.

### Dialogue → database (agent behaviour)

When the user says e.g. **「记录联系人：简称 hwk，英文名 …，中文名 …，职位 xxx」** or **「把 xsy 的职位改成 …」** or **「xsy 的电子签名图在 …」**:

1. **Execute** `contacts_tool.py add` / `set` **in the shell** (or merge the `.xlsx` carefully); **do not** paste full commands unless the user asks.  
2. Reply with a **one-line confirmation** (and optional `show` summary **as text**, not a command block).  
3. On ambiguity (duplicate `name`), ask which `abbrev` to keep.  
4. For **signature_image**, prefer paths under **`assets/signatures/`** so the skill folder stays self-contained.

### Using contacts when drafting the memo

1. Resolve routing in-process from **`contacts.xlsx`** (same rules as `contacts_tool.py resolve`); pass **`--to-contact` / `--copy-to-contact` / `--attn-contact`** to the Word generator (comma-separated abbrevs). **Do not** paste `resolve` shell commands in chat for one-shot.  
2. If a token does not resolve, **do not guess** — ask once for a literal line or an Excel row fix.  
3. Literal overrides: if the user supplies full **To** text, **omit** `*_contact` flags and use literals.  
4. For **落款 + 电子签名**: use **`--signatory-contact <abbrev>`** so **English `name`, title, and `signature_image`** stay aligned; do not pass **`--signature-image`** at the same time unless the user explicitly overrides. **Do not** put `name_zh` in any memo field text.

## Reference layout (PDF page 1)

Match this **reading order** and tone (formal site correspondence). Optional header row used on some prints: `By Hand` / `By Email` (ask once; omit both if unknown).

```text
[Company letterhead image — Word: page header]

SITE MEMORANDUM

Our Ref. : …          Date : …
Your Ref.: …          Pages: …

To       : …
Attn.    : …
Copy To  : …
Fax No.  : …

Project  : … (English line; optional second line 中文项目名)

Re       : … (title; bilingual acceptable if project standard)

[Body paragraphs: background / basis, scope, instructions, interface, programme & reply if needed]

责任: …（责任划分；如无则写「（待工程师确认）」）

[Company name]
[Optional: e-signature image — same person as signatory]
_______________________
[Signatory name]
[Signatory title]
```

## Template field map (Word — numbered 1–13)

Use these numbers when merging user input. **Label fix:** field **3** is **Your Ref. (对方参考编号)**; do not mislabel as 我方.

| # | Label | Rule |
|---|--------|------|
| 1 | Our Ref. (我方参考编号) | Allocate from state file sequence; increment after accepted output. |
| 2 | Date | Authoritative “today” from session/user context (local calendar). |
| 3 | Your Ref. (对方参考编号) | If user supplied an incoming memo, extract; else `-` or `N/A`. |
| 4 | Pages | For **this skill**, default **`1`** unless the user explicitly wants multi-page letter content counted. |
| 5 | To（模板占位为「寄送人」；语义为收件方） | Q&A or **resolve from `contacts.xlsx`** via `abbrev` / `aliases` / `name` / `name_zh`. |
| 6 | Attn. (提醒) | Q&A or **contact resolve** (same as 5). |
| 7 | Copy To (抄送人) | Q&A or **contact resolve**; multiple abbrevs → newline-joined lines. |
| 8 | Fax No. | Q&A only if applicable; else `-`. |
| 9 | Project (项目名称) | If empty in state JSON, ask once, then persist; reuse on later runs unless overridden. |
| 10 | Re (工程指令标题) | Concise subject from user intent and/or upstream memo. |
| 11 | Body (工程指令内容) | Collaborative draft from engineer facts; see **Body** below. |
| 12 | Company (公司名称) | If empty in state JSON, ask once, then persist. |
| 13 | Signatory (负责人 + 职位) | If empty in state JSON, ask once, then persist (two lines under rule line). **Word:** optional **e-signature image** from **`signature_image`** in `contacts.xlsx` when using `--signatory-contact` (image above printed name/title, same person). |

**Note on “12 fields”:** the Word file numbers **1–13**; some teams count **12** by grouping **12+13** or excluding auto fields (**1,2,4,10**). Always honour whatever the user pastes at skill start; map their list to rows **5–11** and **9,12,13** as needed.

## State file (project-scoped)

**Path:** `.site-memo-standard.json` at workspace root (create/update as needed).

```json
{
  "ourRefPrefix": "NAH-B/CS/CSF(SIM)/BS(FS)",
  "lastOurRefSeq": 0,
  "projectNameEn": "",
  "projectNameZh": "",
  "companyName": "",
  "signatoryName": "",
  "signatoryTitle": "",
  "deliveryMethod": ""
}
```

- **Our Ref. format:** follow project convention (example from reference: `NAH-B/CS/CSF(SIM)/BS(FS)/0589`). If unclear, ask once for `ourRefPrefix` pattern and fixed-width sequence rules; then reuse.
- **Persist:** `projectNameEn`, `projectNameZh` (optional second line), `companyName`, `signatoryName`, `signatoryTitle`, `deliveryMethod`.
- After the user accepts the memo, increment `lastOurRefSeq` and save.

## Interaction modes (pick one)

### A. One-shot (默认)

Follow **「One-shot generation」** above: **parse → defaults → silent Word generation → done.**

### B. Collaborative（仅当用户明确要求）

Use only when the user asks for **草稿讨论、逐步确认、审阅后再出稿、必须参考历史 memo 全文**等。

1. **Ingest** pasted field table / upstream memo.  
2. **Upstream memo?** Ask once if unclear; if yes, extract Your Ref. and rewrite obligations.  
3. **Recipients / Fax** — Q&A if not inferable from `contacts.xlsx`.  
4. **Subject** — refine with user.  
5. **Body** — collect 图纸/位置/分判/界面/工期; optional **workspace search** for similar memos; draft → feedback loop.  
6. **Delivery method** — ask if needed.  
7. **Pages / Our Ref.** — as in state file rules.  
8. **After user accepts** — update `.site-memo-standard.json` and Our Ref. sequence.

## Output (paste-ready)

Render **exactly** in this block shape (labels English as below). **Fields 5–7 and 13 names:** English from the **`name`** column in `contacts.xlsx` only — **do not** emit `name_zh` in this block.

Other bilingual lines (e.g. Project) remain allowed if the project standard requires them.

```text
SITE MEMORANDUM

Our Ref.    : 1
Date        : 2
Your Ref.   : 3
Pages       : 4

To          : 5
Attn.       : 6
Copy To     : 7
Fax No.     : 8

Project     : 9

Re          : 10

11

12
_______________________

[13 负责人姓名]
[13 职位]
```

Replace numbers with final text. Use `-` for unused optional fields if the reference PDF does.

## Word (.docx) output

- **Implementation:** skill file **`scripts/generate_site_memo_docx.py`** — the agent **runs it in the shell**; **one-shot replies should not** enumerate the full command (see **Chat output hygiene**).  
- **Dependencies (install once per machine if missing):** `python-docx`, `openpyxl` — only mention `pip install …` when execution fails or the user asks.  
- **Routing table layout (standard template):** **6 rows × 4 columns** — rows **1–4** are `[label | value | label | value]` (`Our Ref.`/`Date`, `Your Ref.`/`Pages`, `To`/`Attn.`, `Copy To`/`Fax No.`); rows **5–6** put **`Project :`** and **`Re :`** in column 1 and **merge columns 2–4** for long text. Style **`Table Grid`** (or locale equivalents) for full grid lines.  
- **Contacts (CLI flags on the generator):** `--to-contact`, `--copy-to-contact`, `--attn-contact` (comma / space / 中文顿号 separated abbrevs); `--contacts-db` override; `--contact-style name_title|name_only`.  
- **Signatory + e-sig:** `--signatory-contact <abbrev>` (uses `name`, `title`, `signature_image`, and **`company` for field 12 when `--company` is omitted**); **`--signature-image`** only when **not** using `--signatory-contact`; **`--signature-width-inches`** (default `2.2`).  
- Pass other field values via the same script’s flags; **`--body-file`** (UTF-8 path) overrides **`--body`** when long Chinese text would break shell quoting — still **one** `generate_site_memo_docx.py` invocation. Default **`assets/letterhead.png`** unless `--letterhead` override.

## Quality rules

- Formal, auditable tone; no invented drawing numbers or site facts — mark **（待工程师确认）**.  
- If **upstream → downstream**, separate **分判须执行** vs **总包/其他工种**.  
- Keep output to **page-one letter content**; do not append PDF-style “-- 1 of 3 --” or reply-grid text unless requested.

## Optional file output

- Markdown: `SITE-MEMORANDUM-{OurRefCompact}-{YYYYMMDD}.md` (OurRef with `/` → `-` in filename).  
- Word: `.docx` from the skill generator (header **`assets/letterhead.png`**); **execute silently**, path-only reply in one-shot.
