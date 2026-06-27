# Industry Lifting Response

业界吊运风险主动响应：外部讯息确认 → 润色检测提示词 → 全盘 CCTV VLM 巡检 → 检测报告 → WhatsApp 待确认发送。

## Rules

- 用户提到「地盘」「11 支/路摄像头」「全盘」「全部摄像头」时，必须对**全部已启用摄像头**（当前 11 路）逐路检测。
- 检测方向默认聚焦**不安全吊运**：吊机作业、警戒区、吊运半径内人员、吊索绑扎、司索指挥、交叉作业、PPE。
- 先 `refine_detection_prompt`（结合 RAG 制度）再 `workbench_video_detection`；不得跳过提示词润色步骤。
- 检测完成后必须 `compose_patrol_detection_report` 生成 Markdown 报告，并创建 `send_whatsapp_message` 待确认项（默认收件人见 config `default_whatsapp_to`）。
- 报告生成时会将各摄像头 **JPG/PNG 标注图** 持久化到 `data/detection_reports/{report_id}/images/`，优先附带**有检测目标的摄像头**（最多 8 张）。
- 批准待确认后通过 `deliver_whatsapp_detection_report`：先发文字报告，再逐张发送标注图（toolbox 失败时自动 fallback 本地 wacli）。
- 汇总必须写清：`已完成 X/11 路摄像头检测`、检测目标数，以及 `（随文附 N 张摄像头检测标注图）`。

## Preferred Tools

- `refine_detection_prompt`
- `workbench_video_detection`
- `compose_patrol_detection_report`
- `generate_safety_alert_bundle`
- `create_pending_confirmation`
- `deliver_whatsapp_detection_report`（或 `whatsapp_send_text_confirmed` + 多张 `whatsapp_send_file_confirmed`）

## Workflow

触发工作流：`workflow_industry_lifting_incident_response` 或 `workflow_lifting_safety_patrol`

1. （可选）外部 P1 吊运讯息 → 待确认 `external_info_alert` 批准后自动启动
2. RAG 检索吊运制度 → 润色 VLM 提示词
3. 对 11 路 CCTV 逐路抽帧 + YOLO/VLM
4. 生成检测报告 + 警示文案
5. WhatsApp 发送待确认（payload 含 `file_paths` 多图列表）→ 人工批准 → 文字 + 多张标注图外发
6. **自动执行**：后端 `automation_scheduler` 默认每 6 小时运行 `workflow_lifting_safety_patrol`（任务 ID `auto_lifting_safety_patrol_6h`），并自动 WhatsApp 外发报告与标注图；可在「自动化工作流」页面查看/手动触发。

## Example Intents

| 用户说法 | 行为 |
|---------|------|
| 检测地盘 11 支 CCTV 是否有不安全吊运 | 11 路全盘 + 报告 + WhatsApp 待确认 |
| 业界吊运事故后主动巡检 | 走 `workflow_industry_lifting_incident_response` |
| 把 VLM 结果发到我 WhatsApp | 创建 `send_whatsapp_message` 待确认 |

## Boundaries

- 未完成 11 路检测前不得声称「地盘已检完」
- 外发 WhatsApp 必须经过待确认（除运维脚本 `--force-send` 外）
- 不得将单路结果冒充全盘结论
