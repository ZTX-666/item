# 赤瞳安全智能平台整项目部署手册

本文档面向“别人下载当前 commit 之后，如何把整个项目部署起来”的场景。它不是某一个功能的专项说明，而是覆盖 FinalAgentSuite 整体项目、核心服务、可选模块、环境变量、启动顺序、验证命令和常见问题。

## 一、项目组成

当前仓库是赤瞳安全智能平台的集成工作区，核心入口是前端桌面工作台，后端分为 Chitung Center 和 AgentToolbox 两层。

| 模块 | 路径 | 是否必需 | 作用 |
| --- | --- | --- | --- |
| Chitung Frontend | `chitung-frontend` | 必需 | Vue/Electron 桌面工作台，包含 AI 助手、DocMate、WhatsApp、系统入口等页面 |
| Chitung Center | `chitung-center` | 必需 | AI 助手入口、意图识别、Skill/Workflow 编排、LLM 网关 |
| AgentToolbox | `agent-toolbox` | 必需 | 本地工具 HTTP/MCP 网关，封装 DocMate、WhatsApp、VLM、RTMP、报告等工具 |
| WhatsApp Archive | `whatsapp-archive/app-server` | 可选 | WhatsApp 归档搜索、附件下载 HTTP 服务，默认 8787 |
| WhatsApp Archive Web | `whatsapp-archive/app-web` | 可选 | 归档服务的独立浏览器 UI |
| CCTV Gateway | `cctv-gateway` | 可选 | C-SMART CCTV iframe 播放网关，默认 3457 |
| Chitong Lingxun / publish3.0 | `chitong-lingxun`, `publish3.0` | 可选 | WhatsApp 桌面端、wacli 运行时、Windows 发布包资料 |
| DocMate Shanshan | `docmate-shanshan` | 可选 | DocMate 独立 Electron 应用源码；平台内 DocMate 已集成到核心服务 |
| VLM Detection | `vlm-detection` | 可选 | 工地视觉识别脚本，需额外模型/推理环境 |
| RTMP Tools | `rtmp-tools` | 可选 | RTMP 截图工具 |
| Report Generators | `report-generators` | 可选 | Word/报告生成脚本 |
| Safety Templates | `safety-policy-templates-20241025` | 数据资源 | 安全制度/表单模板资源 |

通常先部署三个核心模块：`agent-toolbox`、`chitung-center`、`chitung-frontend`。其他模块根据页面功能是否需要再启动。

## 二、部署模式

### 最小可用部署

用于打开主平台、AI 助手、基础工作流、系统设置、DocMate 集成入口、WhatsApp 控制台页面：

1. AgentToolbox: `http://127.0.0.1:8899`
2. Chitung Center: `http://127.0.0.1:8999`
3. Chitung Frontend: `http://127.0.0.1:5173`

### 完整本地部署

在最小可用部署基础上，按需增加：

1. WhatsApp Archive: `http://127.0.0.1:8787`
2. CCTV Gateway: `http://127.0.0.1:3457`
3. wacli / publish3.0 运行时
4. VLM 模型与推理环境
5. DocMate 独立桌面端

## 三、拉取代码

```bash
git clone <repo-url> item
cd item
git checkout integration/whatsapp-publish-crawler
git pull
```

如果需要固定到某个交付 commit：

```bash
git checkout <commit-hash>
```

不要把本地 `.env`、数据库、WhatsApp session、模型权重、运行日志提交回仓库。

## 四、系统依赖

建议环境：

- Python 3.11 或更高版本
- Node.js 20 或更高版本
- npm
- Git
- Windows 桌面打包时需要 PowerShell 和 Electron Builder 所需运行环境

可选依赖：

- Git LFS：仓库启用了 LFS hook；如果本机提交时提示 `git-lfs was not found`，请安装 Git LFS。
- ffmpeg：如果启用视频/截图相关能力。
- wacli：如果启用 WhatsApp 登录、同步、本地数据库查询。
- VLM 模型权重：如果启用视觉检测。

## 五、环境变量

仓库只提交 `.env.example`，不提交真实 `.env`。首次部署时按需复制：

```bash
cp agent-toolbox/.env.example agent-toolbox/.env
cp chitung-center/.env.example chitung-center/.env
cp chitung-frontend/.env.example chitung-frontend/.env
cp cctv-gateway/.env.example cctv-gateway/.env
```

### AgentToolbox

路径：`agent-toolbox/.env`

常用配置：

```text
AGENT_TOOLBOX_HOST=127.0.0.1
AGENT_TOOLBOX_PORT=8899
WHATSAPP_ARCHIVE_BASE_URL=http://127.0.0.1:8787
```

WhatsApp / wacli 可选配置：

```text
WACLI_BIN=
WACLI_WORKDIR=
WACLI_STORE_DIR=
```

VLM / RTMP / 报告相关路径大多有仓库相对默认值。只有你的目录布局不同，才需要显式填写绝对路径。

### Chitung Center

路径：`chitung-center/.env`

常用配置：

```text
CHITUNG_CENTER_HOST=127.0.0.1
CHITUNG_CENTER_PORT=8999
AGENT_TOOLBOX_BASE_URL=http://127.0.0.1:8899
```

LLM 配置：

```text
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

也可使用兼容别名：

```text
GLM_API_KEY=
ZHIPU_API_KEY=
ZHIPUAI_API_KEY=
DOCMATE_API_KEY=
DOCMATE_API_URL=https://open.bigmodel.cn/api/paas/v4/chat/completions
DOCMATE_MODEL=glm-5.1
```

如果不配置 LLM，部分自然语言 Skill/Workflow 只能走降级路径或无法完整执行。

### Chitung Frontend

路径：`chitung-frontend/.env`

```text
VITE_CHITUNG_CENTER_URL=http://127.0.0.1:8999
CHITUNG_CENTER_URL=http://127.0.0.1:8999
VITE_CCTV_GATEWAY_URL=http://127.0.0.1:3457
```

修改前端 `.env` 后必须重启 Vite。

### CCTV Gateway

路径：`cctv-gateway/.env`

```text
CCTV_GATEWAY_HOST=127.0.0.1
CCTV_GATEWAY_PORT=3457
CSMART_ORG_ID=
CSMART_GATEWAY=
CCTV_PLAYER_URL=
CSMART_BEARER=
```

真实 bearer/token 只放本地 `.env`，不要提交。

## 六、安装依赖

### 1. AgentToolbox

```bash
cd agent-toolbox
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Windows PowerShell：

```powershell
cd agent-toolbox
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

### 2. Chitung Center

```bash
cd chitung-center
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
```

Windows PowerShell：

```powershell
cd chitung-center
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..
```

### 3. Chitung Frontend

```bash
cd chitung-frontend
npm install
cd ..
```

### 4. 可选：WhatsApp Archive

```bash
cd whatsapp-archive/app-server
npm install
cd ../..
```

可选浏览器 UI：

```bash
cd whatsapp-archive/app-web
npm install
cd ../..
```

### 5. 可选：CCTV Gateway

```bash
cd cctv-gateway
npm install
cd ..
```

### 6. 可选：DocMate 独立桌面端

平台内 DocMate 已通过核心服务集成。只有需要单独运行原 DocMate 桌面端时才安装：

```bash
cd docmate-shanshan
npm install
cd ..
```

### 7. 可选：VLM Detection

```bash
cd vlm-detection
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd ..
```

模型权重通常不在仓库中，需要按项目实际交付位置放置或在 `agent-toolbox/.env` 中指定。

## 七、启动顺序

建议按以下顺序启动。

### 1. AgentToolbox

```bash
cd agent-toolbox
.venv/bin/python run_server.py
```

默认地址：

```text
http://127.0.0.1:8899
```

### 2. Chitung Center

```bash
cd chitung-center
.venv/bin/python run_server.py
```

默认地址：

```text
http://127.0.0.1:8999
```

### 3. Chitung Frontend

浏览器开发模式：

```bash
cd chitung-frontend
npm run dev -- --host 127.0.0.1
```

访问：

```text
http://127.0.0.1:5173/
```

Electron 桌面开发模式：

```bash
cd chitung-frontend
npm run desktop:dev
```

打包目录构建：

```bash
cd chitung-frontend
npm run desktop:build
```

### 4. 可选：WhatsApp Archive

如果要使用归档搜索/附件下载，启动 8787 服务：

```bash
cd whatsapp-archive/app-server
WHATSCLI_DB_PATH=/absolute/path/to/wacli.db npm start
```

如果没有显式设置 `WHATSCLI_DB_PATH`，服务会按默认 store 目录查找数据库。

可选 Web UI：

```bash
cd whatsapp-archive/app-web
npm run dev
```

### 5. 可选：CCTV Gateway

```bash
cd cctv-gateway
npm start
```

默认地址：

```text
http://127.0.0.1:3457
```

### 6. 可选：DocMate 独立桌面端

```bash
cd docmate-shanshan
npm run electron:dev
```

平台内 AI 助手调用 DocMate Skill 时，不要求单独启动这个独立桌面端；它主要用于维护原 DocMate 产品。

## 八、功能入口

核心前端地址：

```text
http://127.0.0.1:5173/
```

常用页面：

- `/#/center/assistant`：AI 助手，统一自然语言入口。
- `/#/docmate/documents`：DocMate 文档审阅/改稿入口。
- `/#/lingxun/whatsapp`：WhatsApp 控制台，登录配对、同步、SQLite 查询、命令工具。
- 系统设置页面：配置后端地址、连接器、部分运行时参数。

## 九、验证命令

### 核心服务健康检查

```bash
curl -sS http://127.0.0.1:8899/health
curl -sS http://127.0.0.1:8999/health
curl -sS -I http://127.0.0.1:5173/
```

如果启用了 WhatsApp Archive：

```bash
curl -sS http://127.0.0.1:8787/api/health
```

如果启用了 CCTV Gateway：

```bash
curl -sS -I http://127.0.0.1:3457/
```

### 后端测试

```bash
PYTHONPATH=agent-toolbox chitung-center/.venv/bin/pytest \
  agent-toolbox/tests/test_docmate_docx.py \
  agent-toolbox/tests/test_whatsapp_wacli.py -q

PYTHONPATH=chitung-center chitung-center/.venv/bin/pytest \
  chitung-center/tests/test_docmate_service.py \
  chitung-center/tests/test_orchestrator_capabilities.py \
  chitung-center/tests/test_whatsapp_adapter_service.py \
  chitung-center/tests/test_whatsapp_local_service.py -q
```

完整后端测试：

```bash
cd agent-toolbox
PYTHONPATH=. ../chitung-center/.venv/bin/pytest tests -q

cd ../chitung-center
PYTHONPATH=. .venv/bin/pytest tests -q
```

### 前端测试与构建

```bash
cd chitung-frontend
npm run test:assistant
npm run test:whatsapp-ops
node scripts/verify-docmate-frontend-contract.mjs
npm run build
```

### 可选模块测试

CCTV Gateway：

```bash
cd cctv-gateway
npm test
```

DocMate 独立端：

```bash
cd docmate-shanshan
npm run build
```

## 十、WhatsApp 部署说明

WhatsApp 相关能力有两层：

1. wacli 本地能力：登录、配对、同步、本地 SQLite 查询、命令行操作。
2. WhatsApp Archive app-server：归档搜索和附件下载 HTTP 服务。

部署建议：

- 先在 `/#/lingxun/whatsapp` 完成 QR 或配对码登录。
- 确认 wacli 同步生成或更新本地 `wacli.db`。
- 如果需要归档搜索/附件下载，再启动 `whatsapp-archive/app-server` 并让它指向同一个 `wacli.db`。
- AI 助手里的 WhatsApp 自然语言操作通过 `whatsapp-wacli-ops` 和 `whatsapp-sql-query` Skill 进入。

注意：

- 群名可以给用户自然输入；后端可以在执行前解析为 JID。
- 发送消息属于写操作，应保留安全确认和审计。
- `whatsapp_archive` 未启动时，`/health` 可能显示该工具 unavailable；这只影响归档搜索/附件下载，不代表核心平台不可用。

## 十一、DocMate 部署说明

平台内 DocMate 能力由三部分组成：

1. 前端 `chitung-frontend` 的 DocMate 页面和 AI 助手入口。
2. `chitung-center` 的 `docmate-edit` Skill/Workflow 和 LLM 编排。
3. `agent-toolbox` 的文档读取、变更集、应用修改、下载等工具接口。

部署建议：

- 优先配置 `chitung-center/.env` 中的 LLM key。
- 通过 `/#/docmate/documents` 上传 `.docx` 并进行改稿验证。
- 只有要维护原独立 DocMate 产品时，才单独运行 `docmate-shanshan`。

## 十二、本地数据与目录

常见运行时目录：

- `agent-toolbox/workspace`：AgentToolbox 本地工作区。
- `agent-toolbox/workspace/wacli/wacli.db`：常见 wacli 本地数据库位置。
- `chitung-center/data`：Center 本地数据、RAG、审计日志等。
- `chitung-frontend/dist`：前端构建产物。
- `chitung-frontend/release`：Electron 打包产物。

这些运行时数据通常不应提交。

## 十三、常见问题

### 端口被占用

```bash
lsof -nP -iTCP:8899 -sTCP:LISTEN
lsof -nP -iTCP:8999 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:8787 -sTCP:LISTEN
lsof -nP -iTCP:3457 -sTCP:LISTEN
```

### 前端连不上后端

检查：

- `chitung-frontend/.env` 中 `VITE_CHITUNG_CENTER_URL`
- `curl http://127.0.0.1:8999/health`
- 修改 `.env` 后是否重启 Vite

### Center 连不上 AgentToolbox

检查：

- `chitung-center/.env` 中 `AGENT_TOOLBOX_BASE_URL`
- `curl http://127.0.0.1:8899/health`

### AI 助手不能理解复杂指令

检查：

- `chitung-center/.env` 中 LLM key 是否配置。
- `/health` 中 `llm_configured` 是否为 true。
- 对应 Skill/Workflow 是否存在于 `chitung-center/skills` 和 `chitung-center/workflows`。

### WhatsApp 搜索失败

检查：

- wacli 是否已登录并同步。
- `wacli.db` 是否存在。
- `whatsapp-archive/app-server` 是否启动。
- `WHATSCLI_DB_PATH` 是否指向正确数据库。
- `curl http://127.0.0.1:8787/api/health` 是否返回 `ok: true`。

### VLM 或摄像头功能不可用

检查：

- 模型权重是否存在。
- `vlm-detection` Python 依赖是否安装。
- `agent-toolbox/.env` 中相关路径是否需要覆盖。
- CCTV Gateway 是否启动并配置 C-SMART 参数。

### Git LFS hook 报错

如果提交时出现：

```text
This repository is configured for Git LFS but 'git-lfs' was not found
```

安装 Git LFS 后再提交。不要把大模型、数据库、运行截图等大文件绕过 hook 提交。

## 十四、安全要求

- 真实 `.env` 不提交。
- API key、Feishu secret、C-SMART token、WhatsApp session 不提交。
- 本地数据库、聊天记录、附件、二维码 payload 不提交。
- AgentToolbox、Chitung Center、WhatsApp Archive 默认只绑定 `127.0.0.1`。
- 如需对外暴露，必须额外加鉴权、网络隔离和审计。

## 十五、推荐交付检查清单

交付别人前，至少确认：

- `git status` 没有误提交 `.env`、数据库、模型、日志。
- 三个核心服务可启动：8899、8999、5173。
- `/health` 检查通过。
- 前端能打开 AI 助手、DocMate、WhatsApp 页面。
- `npm run build` 通过。
- 关键 Python 测试通过。
- 文档中的本地路径没有写死为个人机器路径。
