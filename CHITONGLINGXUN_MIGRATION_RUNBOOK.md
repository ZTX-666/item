# ChitongLingxun 迁移执行手册（可直接转发给另一个 AI）

> 目标：把 `WacliDesktop` 在 handoff 源里的 Phase 1 集成能力，稳定迁移到 `FinalAgentSuite/chitong-lingxun` 基线。  
> 原则：**不整包覆盖**，只迁移“已验证增量”，每步可回滚、可验收。

---

## 0. 结论先行（当前状态）

`chitong-lingxun` 在 `FinalAgentSuite` 中**尚未完整接入** handoff 源里的 Phase 1 改造。  
已确认缺失关键文件：

- `WacliDesktop/Views/ChitungToolboxView.xaml`
- `WacliDesktop/Views/ChitungToolboxView.xaml.cs`
- `WacliDesktop/Services/AgentToolboxClient.cs`

且 `HomeWindow.xaml` / `HomeWindow.xaml.cs` 在 source 与 target 时间戳、内容存在差异（需要以 source 增量为准迁移）。

---

## 1. 源与目标（固定路径）

### Source（有最新 Phase 1 改造）

`E:\China Oversea  Final\ChinaOverseas Final\Chitong-0602-handoff\source`

重点源目录：

- `.../WacliDesktop`
- `.../build-publish3.0.ps1`
- `.../publish3.0/start.bat`（如需同步启动逻辑）

### Target（正式统一基线）

`E:\China Oversea  Final\FinalAgentSuite\chitong-lingxun`

重点目标目录：

- `.../WacliDesktop`
- `.../build-publish3.0.ps1`

---

## 2. 迁移范围（只迁移这些）

## P0 必迁（功能接入核心）

1. `WacliDesktop/Views/ChitungToolboxView.xaml`
2. `WacliDesktop/Views/ChitungToolboxView.xaml.cs`
3. `WacliDesktop/Services/AgentToolboxClient.cs`
4. `WacliDesktop/HomeWindow.xaml`（仅迁移工具箱入口相关改动）
5. `WacliDesktop/HomeWindow.xaml.cs`（仅迁移 `ModuleTile_Click` 中 `toolbox` 分支）

## P1 条件迁移（打包与运行）

6. `build-publish3.0.ps1` 中以下逻辑：
   - `robocopy /XD .venv __pycache__ .git node_modules`
   - 相对路径 `.env` 重写
   - UTF-8 BOM 编码要求
   - `start.bat` 里 `chcp 65001 >nul`
   - 启动顺序：8899 -> 8999 -> WPF

> 注意：不要无脑覆盖整个脚本，按块对齐，保留 target 中已有可用改动。

---

## 3. 执行步骤（严格顺序）

## Step 1 — 创建安全工作分支与备份

1. 在 `FinalAgentSuite` 仓库新建分支：`feat/chitonglingxun-phase1-migration`
2. 备份目标文件到临时目录（同盘）：
   - `WacliDesktop/HomeWindow.xaml`
   - `WacliDesktop/HomeWindow.xaml.cs`
   - `build-publish3.0.ps1`

验收：分支创建成功，备份文件存在。

---

## Step 2 — 生成“差异清单”（先对比再改）

对比 source vs target：

- `WacliDesktop/HomeWindow.xaml`
- `WacliDesktop/HomeWindow.xaml.cs`
- `WacliDesktop/WacliDesktop.csproj`
- `build-publish3.0.ps1`

同时确认 source 独有文件：

- `Views/ChitungToolboxView*`
- `Services/AgentToolboxClient.cs`

验收：输出一个短清单（新增/修改/保持不变）。

---

## Step 3 — 迁移 P0 文件

执行：

1. 复制新增文件到 target 同路径
2. 合并 `HomeWindow.xaml`（仅新增 toolbox 入口按钮）
3. 合并 `HomeWindow.xaml.cs`（仅新增路由 case）

额外检查：

- `WacliDesktop.csproj` 是否需要显式包含新增文件（通常 WPF SDK 自动包含，但要核验）

验收：

- 目标目录有新增 `ChitungToolboxView` 与 `AgentToolboxClient`
- `HomeWindow` 入口可编译通过

---

## Step 4 — 迁移 P1 启动/打包脚本能力

按块合并 `build-publish3.0.ps1`：

必须保留能力：

- 忽略大目录复制（`/XD`）
- `.env` 相对路径重写（指向 `agent-services`）
- UTF-8 BOM（脚本）、`start.bat` UTF-8 无 BOM + `chcp 65001`
- 首次自动创建 venv 并安装 requirements

验收：

- 脚本可执行
- 生成产物可启动（至少服务脚本部分）

---

## Step 5 — 编译验证（WPF）

对 `WacliDesktop` 进行构建（Release x64）并确认：

1. 打开主界面后出现“赤瞳工具箱”入口
2. 点击可进入 `ChitungToolboxView`
3. 三个 Tab 正常显示（WhatsApp 搜索 / 隐患案例 / 表格模板）

验收：WPF 不崩溃，页面可打开。

---

## Step 6 — 联调验证（后端）

确保本地服务在线：

- `http://127.0.0.1:8899/health`
- `http://127.0.0.1:8999/health`

验证工具调用（至少 3 条）：

1. `/tools/query_safety_cases`
2. `/tools/search_form_templates`
3. `/tools/whatsapp_search`

说明：

- `whatsapp_search` 若依赖 `8787` 服务，需先启动本地归档/bridge；未启动时返回连接错误属预期，不算迁移失败。

---

## Step 7 — 提交与文档

提交前输出：

1. 迁移文件列表
2. 构建结果截图/日志
3. 三条接口验证结果
4. 已知问题（例如 8787 未启动）

---

## 4. 验收标准（Definition of Done）

满足全部才算“Phase 1 已迁移完成”：

1. `FinalAgentSuite/chitong-lingxun/WacliDesktop` 编译通过
2. 主界面存在“赤瞳工具箱”入口并可打开
3. `AgentToolboxClient` 可调用 8899 的基础查询工具
4. 打包脚本包含相对路径与编码防乱码能力
5. 迁移变更可回滚（有分支和备份）

---

## 5. 不要做的事（防事故）

1. 不要整目录覆盖 `WacliDesktop`。
2. 不要覆盖 `cloud-sync-api`、`hiagent-local-test` 等无关模块。
3. 不要把 source 的 `obj/bin/.venv/node_modules` 复制进目标。
4. 不要修改端口约定（8899/8999）除非同步更新所有脚本和文档。

---

## 6. 交给另一个 AI 的执行提示（可直接复制）

```text
请按 CHITONGLINGXUN_MIGRATION_RUNBOOK.md 执行，严格遵守：
1) 只迁移 P0/P1 指定文件；
2) 先做差异清单，再修改；
3) 每步给出“已完成/未完成 + 证据”；
4) 最后输出：
   - 变更文件清单
   - 编译结果
   - 三条接口联调结果
   - 已知问题与下一步建议
```

---

## 7. 后续（Phase 2 建议）

在本次迁移完成后再做：

1. 把 placeholder 的 `list_whatsapp_groups` 与 `send_group_message_with_confirm` 接入真实 `wacli` 能力；
2. 把 8787 依赖做成 WPF 内“服务状态检测 + 一键启动”；
3. 与 `chitung-center` 的 `/plan /confirm /execute` 统一，形成完整可确认闭环。

