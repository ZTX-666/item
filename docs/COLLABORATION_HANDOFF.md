# 赤瞳安全智能平台 — 协作交接文档

> 仓库：`https://github.com/ZTX-666/item`  
> 更新：2026-06-20  
> 用途：供前后端对接与最终审核同事快速接手

---

## 1. 仓库里有什么

本仓库是 **FinalAgentSuite 核心代码包**，不含模型权重、虚拟环境、运行输出和密钥。

| 目录 | 角色 | 默认端口 |
| --- | --- | --- |
| `chitung-frontend` | Electron + Vue 桌面工作台 | 5173 |
| `chitung-center` | FastAPI 中台（意图路由、工作流、LLM 网关） | 8999 |
| `agent-toolbox` | 工具箱 HTTP/MCP 网关（129+ 工具） | 8899 |
| `rtmp-tools` | RTMP 摄像头截图 | — |
| `vlm-detection` | YOLO 双模型检测脚本 | — |
| `report-generators` | Word 报告生成 | — |
| `chitong-lingxun` | 赤瞳灵讯 WhatsApp 桌面客户端源码 | — |
| `docmate-shanshan` | 闪闪文档 Electron 编辑器源码 | — |
| `scripts` | 独立巡检脚本 `nightly_patrol.py` | — |
| `safety-policy-templates-20241025` | 159 个安全制度表格模板 | — |

**未纳入仓库（需本地自备）：**

- YOLO 权重：`worker/yolo26x_worker.pt`、`machinery/yolo26l_machinery.pt`（约 164MB）
- PaddleOCRSharp 源码：在父目录 `01-PaddleOCRSharp`，耀耀慧读 OCR 参考实现
- ffmpeg 二进制、Python 虚拟环境、萤石云 RTMP token

---

## 2. 三层架构（前后端对接重点）

```text
chitung-frontend (Vue/Electron)
        │  HTTP
        ▼
chitung-center (FastAPI 中台)
        │  toolbox_client
        ▼
agent-toolbox (FastAPI 工具箱)
        │
        ├── rtmp-tools / vlm-detection / secureeye_vlm
        ├── 飞书 / WhatsApp / 表格 / OCR / 报告工具
        └── SQLite: safety_platform.db（本地 workspace，不入库）
```

**原则：前端只调 `chitung-center`，不直连 toolbox、脚本或数据库。**

---

## 3. 本地启动（Windows）

### 3.1 环境变量

复制示例配置后填写（**勿提交 `.env`**）：

```powershell
copy "agent-toolbox\.env.example" "agent-toolbox\.env"
copy "chitung-center\.env.example" "chitung-center\.env"
copy "chitung-frontend\.env.example" "chitung-frontend\.env"
```

关键项：

| 变量 | 说明 |
| --- | --- |
| `AGENT_TOOLBOX_BASE_URL` | center 指向 toolbox，默认 `http://127.0.0.1:8899` |
| `VITE_CHITUNG_CENTER_URL` | 前端指向 center，默认 `http://127.0.0.1:8999` |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | 仅配在 `chitung-center\.env` |
| `SECUREEYE_*` | VLM 视觉大模型，配在 `agent-toolbox\.env` |
| `FEISHU_APP_ID` / `FEISHU_APP_SECRET` | 飞书机器人（可选） |

### 3.2 启动顺序

```powershell
# Terminal 1 — 工具箱
cd agent-toolbox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py

# Terminal 2 — 中台
cd chitung-center
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_server.py

# Terminal 3 — 前端
cd chitung-frontend
npm install
npm run desktop:dev
```

端口冲突时可改用 8898 / 9000 / 5174，并同步修改 `.env`。

### 3.3 健康检查

```powershell
Invoke-WebRequest http://127.0.0.1:8899/health
Invoke-WebRequest http://127.0.0.1:8999/health
```

---

## 4. 审核同事优先关注的 API

### 4.1 视觉巡检（赤瞳守护者）

| 层级 | 端点 | 说明 |
| --- | --- | --- |
| 前端 → center | `POST /api/visual/patrol-draft` | 触发巡检草稿 |
| center → toolbox | `POST /tools/run_vlm_detection_batch` | YOLO 检测 |
| center → toolbox | `POST /tools/secureeye_analyze_batch` | VLM 增强（hybrid 模式） |
| center → toolbox | `POST /tools/secureeye_merge_results` | 合并 YOLO+VLM |

请求体示例（hybrid 模式）：

```json
{
  "camera_url": "rtmp://...",
  "area": "B2",
  "count": 1,
  "analysis_mode": "hybrid",
  "vlm_enhance_conf_threshold": 0.6
}
```

独立脚本（不依赖服务）：`scripts/nightly_patrol.py`

```powershell
cd scripts
python nightly_patrol.py --camera cam-slope-03
python nightly_patrol.py --loop --interval 7200
```

### 4.2 聊天与中台

| 端点 | 说明 |
| --- | --- |
| `POST /api/chat/message` | 本地 Chat Box 自然语言入口 |
| `POST /integrations/feishu/events` | 飞书事件回调 |

### 4.3 五个 MVP Workflow（待打通确认链）

1. 外部风险简报 — `fetch_hko_weather` → `draft_daily_risk_briefing`
2. 隐患整改 — `create_safety_case` → `generate_rectification_notice`
3. 表格填报 — `search_form_templates` → `generate_docx_from_template`
4. 证书检查 — `query_expiring_certificates`
5. 报告草稿 — `draft_daily_safety_report`

---

## 5. 当前完成度（2026-06-20）

| 模块 | 状态 | 审核要点 |
| --- | --- | --- |
| 三层服务骨架 | ✅ 可启动 | 端口、health、`.env` 路径一致 |
| AgentToolbox 工具池 | ✅ 129+ 工具注册 | 区分「已注册」vs「端到端可用」 |
| 视觉 YOLO+VLM hybrid | ✅ 脚本+API | RTMP token 过期时用本地回退图 |
| 飞书机器人 | ⚠️ 部分 | 缺消息解析、卡片确认执行链 |
| 前端页面 | ⚠️ 部分 | 部分 mock 数据，需显示真实连接状态 |
| Workflow/Skill 产品化 | ❌ 15% | 先跑通 5 条 MVP 闭环 |

**P0 断点（建议同事先审）：**

1. `feishu_parse_message_event` + `route_feishu_message_to_center`
2. `feishu_parse_card_action` + `execute_confirmed_feishu_action`
3. 前端去掉伪成功 mock，统一走 center API
4. 视觉链路 E2E：`snapshot → detect → create_case → 人工确认`

---

## 6. 目录内关键源码入口

```text
chitung-center/chitung_center/
  app.py                    # FastAPI 主应用
  visual_patrol_service.py  # 视觉巡检编排 ★
  orchestrator.py           # 聊天编排
  toolbox_client.py         # 调 toolbox

agent-toolbox/agent_toolbox/
  app.py                    # 工具路由注册
  tools/rtmp.py             # RTMP 截图
  tools/vlm.py              # YOLO 检测
  tools/secureeye_vlm.py      # VLM 大模型增强 ★
  tools/feishu.py             # 飞书工具

chitung-frontend/src/
  pages/VisualPatrolPage.vue  # 视觉巡检页 ★
  services/chitungApi.ts      # 前端 API 封装 ★

scripts/nightly_patrol.py     # 11 路摄像头独立巡检 ★
```

---

## 7. 安全与协作规范

1. **不要提交** `.env`、数据库、API Key、RTMP token、模型权重。
2. 云端 LLM 密钥只放在 `chitung-center\.env`；VLM 密钥在 `agent-toolbox\.env`。
3. 外发消息（飞书/WhatsApp）必须人工确认，禁止自动群发。
4. 分支建议：`main` 稳定、`dev` 日常开发、功能分支 `feat/xxx`。
5. PR 审核清单：API 契约变更、`.env.example` 同步、无密钥泄露、health 可过。

---

## 8. 外部依赖清单（clone 后自备）

| 资源 | 建议路径 | 用途 |
| --- | --- | --- |
| YOLO worker 模型 | `vlm-detection/weights/worker/yolo26x_worker.pt` | PPE/人员检测 |
| YOLO machinery 模型 | `vlm-detection/weights/machinery/yolo26l_machinery.pt` | 施工机械 |
| ffmpeg | 系统 PATH 或 `.env` 指定 | RTMP 截帧 |
| PaddleOCRSharp | 父目录 `01-PaddleOCRSharp` | 耀耀慧读 Windows OCR |
| 测试现场图 | 15 张 `.jpg`（RTMP 不可用时回退） | nightly_patrol 回退 |

---

## 9. 验收清单（接手后 30 分钟自测）

- [ ] 三层服务 health 全部 200
- [ ] 前端能打开工作台，显示 center 连接状态
- [ ] `POST /api/visual/patrol-draft`（yolo_only）返回 candidates
- [ ] hybrid 模式返回 `description` / `severity` 字段
- [ ] `python scripts/nightly_patrol.py --camera cam-slope-03` 生成报告
- [ ] `agent-toolbox` 下 `pytest tests/test_secureeye_vlm.py -v` 通过
- [ ] 仓库内无 `.env`、无 `.pt` 权重文件

---

## 10. 参考文档（本地完整版，含更多细节）

以下文档在本地 `FinalAgentSuite` 根目录，**未全部上传**（部分含敏感信息需脱敏后单独分享）：

- `赤瞳安全智能平台_完成度差距与开发路线_2026-06-20.md`
- `飞书机器人五阶段实施工具清单.md`
- `赤瞳守护者_零上下文接手开发手册.md`
- `docs/VISUAL_GUARDIAN_INTEGRATION_2026-06-20.md`

有问题优先看本文件 + `README.md`，再查上述本地文档。

---

*交接文档结束 — 审核同事可从 §3 启动、§4 API、§5 完成度、§9 验收清单开始。*
