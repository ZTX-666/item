const fs = require('fs')
const path = require('path')

const desktop = path.join(process.env.USERPROFILE || '', 'Desktop')
const outPath = path.join(desktop, 'DocMate产品发布说明.doc')
const version = 'v4.1.25'
const docDate = new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })

const html = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:w="urn:schemas-microsoft-com:office:word"
      xmlns="http://www.w3.org/TR/REC-html40">
<head>
<meta charset="utf-8">
<meta name="ProgId" content="Word.Document">
<meta name="Generator" content="DocMate">
<!--[if gte mso 9]><xml>
<w:WordDocument>
  <w:View>Print</w:View>
  <w:Zoom>100</w:Zoom>
  <w:DoNotOptimizeForBrowser/>
</w:WordDocument>
</xml><![endif]-->
<style>
  body { font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif; font-size: 11pt; line-height: 1.75; color: #1a1a1a; }
  .cover { text-align: center; padding: 48pt 0 36pt 0; page-break-after: always; }
  .cover-logo { font-size: 28pt; font-weight: bold; color: #007acc; letter-spacing: 2pt; }
  .cover-sub { font-size: 16pt; color: #333; margin-top: 12pt; font-weight: normal; }
  .cover-tag { font-size: 12pt; color: #666; margin-top: 24pt; }
  .cover-meta { font-size: 10.5pt; color: #888; margin-top: 48pt; line-height: 2; }
  h1 { font-size: 18pt; color: #007acc; margin-top: 24pt; border-bottom: 2pt solid #007acc; padding-bottom: 6pt; }
  h2 { font-size: 13pt; color: #222; margin-top: 16pt; }
  h3 { font-size: 11.5pt; color: #333; margin-top: 12pt; }
  p { margin: 6pt 0; text-align: justify; }
  ul, ol { margin: 6pt 0 6pt 20pt; }
  li { margin-bottom: 4pt; }
  table { width: 100%; border-collapse: collapse; margin: 10pt 0; font-size: 10.5pt; }
  th { background: #f0f4f8; color: #222; font-weight: bold; border: 1pt solid #ccc; padding: 6pt 8pt; text-align: left; }
  td { border: 1pt solid #ccc; padding: 6pt 8pt; vertical-align: top; }
  .callout { background: #f0f7ff; border-left: 4pt solid #007acc; padding: 10pt 14pt; margin: 10pt 0; }
  .callout-warn { background: #fff8f0; border-left-color: #e6a23c; }
  .callout-green { background: #f0fdf4; border-left-color: #16a34a; }
  .toc { background: #fafafa; border: 1pt solid #e5e5e5; padding: 12pt 16pt; margin: 12pt 0; }
  .toc ol { margin-left: 16pt; }
  .footer { text-align: center; color: #999; font-size: 9.5pt; margin-top: 36pt; border-top: 1pt solid #eee; padding-top: 12pt; }
  .page-break { page-break-before: always; }
</style>
</head>
<body>

<!-- 封面 -->
<div class="cover">
  <p class="cover-logo">DocMate 闪闪文档</p>
  <p class="cover-sub">产品发布说明文档</p>
  <p class="cover-tag">AI 驱动的轻型桌面文稿修改助手 · Windows 便携版</p>
  <p class="cover-meta">
    产品版本：${version}<br>
    文档版本：V1.1<br>
    发布日期：${docDate}<br>
    文档密级：内部公开<br>
    适用对象：产品、业务、售前及终端用户
  </p>
</div>

<!-- 修订记录 -->
<h1>文档修订记录</h1>
<table>
  <tr><th width="12%">版本</th><th width="18%">日期</th><th width="15%">修订人</th><th>修订说明</th></tr>
  <tr><td>V1.0</td><td>2026 年 6 月</td><td>产品组</td><td>初版产品介绍</td></tr>
  <tr><td>V1.1</td><td>${docDate}</td><td>产品组</td><td>参照企业级轻型桌面应用发布规范重构文档结构，补充架构、场景、交付与 FAQ</td></tr>
</table>

<!-- 目录 -->
<h1>目录</h1>
<div class="toc">
<ol>
  <li>产品摘要</li>
  <li>背景与行业痛点</li>
  <li>产品定位与愿景</li>
  <li>目标用户与典型画像</li>
  <li>核心价值与差异化</li>
  <li>产品架构概览</li>
  <li>功能模块详解</li>
  <li>功能能力矩阵</li>
  <li>典型用户路径</li>
  <li>场景化解决方案</li>
  <li>交互设计与体验原则</li>
  <li>安全、合规与数据策略</li>
  <li>部署交付与运行要求</li>
  <li>快速上手指南</li>
  <li>常见问题 FAQ</li>
  <li>产品规划方向</li>
  <li>术语表</li>
</ol>
</div>

<div class="page-break"></div>

<!-- 1. 产品摘要 -->
<h1>1. 产品摘要</h1>
<p>
  <b>DocMate 闪闪文档</b>（以下简称「DocMate」）是一款面向 Windows 平台的<b>轻型 AI 桌面文稿修改助手</b>。
  产品以「专业编辑器 + Agent 对话改稿 + 可视化 Diff 确认」为核心闭环，帮助用户在方案撰写、材料修订、制度起草、汇报整理等高频办公场景中，
  以自然语言驱动改稿，同时保持<b>改动可见、决策在人、结果可溯</b>。
</p>
<div class="callout">
  <b>Executive Summary</b><br>
  DocMate 不是「一键覆盖全文的黑盒写作工具」，而是<b>可控的 AI 改稿工作台</b>：AI 负责理解与生成，用户负责预览与确认。
  这一设计对标 Cursor 等 Agent 型生产力工具在代码领域的交互范式，并将其迁移至中文长文档改稿场景。
</div>
<table>
  <tr><th width="22%">项目</th><th>说明</th></tr>
  <tr><td>产品名称</td><td>DocMate 闪闪文档</td></tr>
  <tr><td>当前版本</td><td>${version}</td></tr>
  <tr><td>产品形态</td><td>Windows 便携桌面应用（Electron + Vue 3）</td></tr>
  <tr><td>交付方式</td><td>精简运行包 publish40，双击 DocMate.vbs 即可启动</td></tr>
  <tr><td>核心场景</td><td>文稿修改、润色、删除/替换、口语转正式、风险扫描、知识库辅助改稿</td></tr>
  <tr><td>设计原则</td><td>AI 辅助 · 人做决策 · Diff 先行 · 本地可控</td></tr>
</table>

<!-- 2. 背景与痛点 -->
<h1>2. 背景与行业痛点</h1>
<p>在政企数字化、项目管理与综合办公场景中，文档改稿长期存在以下效率与质量矛盾：</p>
<table>
  <tr><th width="28%">痛点</th><th>现状描述</th><th width="32%">DocMate 应对策略</th></tr>
  <tr>
    <td><b>改稿定位成本高</b></td>
    <td>用户需手动查找段落、复制粘贴、对照修改，长文档尤其耗时</td>
    <td>Agent 按语义自动定位段落，支持段落序号、原文锚点、模糊匹配</td>
  </tr>
  <tr>
    <td><b>AI 改稿不可控</b></td>
    <td>部分 AI 写作工具直接覆盖全文，误改难发现、难撤销</td>
    <td>红删绿增 Diff 预览 + Apply/拒绝双确认，改动写入前必须过审</td>
  </tr>
  <tr>
    <td><b>风格不一致</b></td>
    <td>多人协作或 AI 批量生成后，术语、语气、格式难以统一</td>
    <td>知识库检索 + 偏好学习，逐步对齐组织/个人表达习惯</td>
  </tr>
  <tr>
    <td><b>工具链割裂</b></td>
    <td>编辑、AI 对话、版本对比分散在多个窗口与产品间</td>
    <td>编辑器、Agent 面板、Diff 预览、历史记录一体化集成</td>
  </tr>
  <tr>
    <td><b>部署门槛高</b></td>
    <td>企业内网环境对安装包、依赖、配置要求严格</td>
    <td>便携包交付，支持本地工作区，API 密钥应用内配置</td>
  </tr>
</table>

<!-- 3. 产品定位 -->
<h1>3. 产品定位与愿景</h1>
<h2>3.1 产品定位</h2>
<p>
  DocMate 定位于<b>「轻型桌面级 AI 改稿工作台」</b>，介于传统 Word 编辑与云端 AI 写作平台之间：
  保留桌面应用的响应速度与本地文件掌控力，同时引入 Agent 型交互与 Diff 确认机制，满足专业用户对<b>效率</b>与<b>可控性</b>的双重诉求。
</p>
<h2>3.2 产品愿景</h2>
<p>让每一次文档修改都<b>说得清、看得见、点得准、追得到</b>——用户用一句话描述意图，系统给出透明 Diff，用户一键确认后落稿，全过程可回溯。</p>
<h2>3.3 产品边界（明确不做什么）</h2>
<ul>
  <li>不替代完整 OA 或协同办公套件，聚焦「单篇文稿的深度改稿」</li>
  <li>不默认自动写入修改，所有 Agent 方案须经用户 Apply 确认</li>
  <li>不强制云端存储，文稿默认保存在用户本地工作区</li>
</ul>

<!-- 4. 目标用户 -->
<h1>4. 目标用户与典型画像</h1>
<table>
  <tr><th width="18%">用户类型</th><th width="35%">典型角色</th><th>核心诉求</th></tr>
  <tr>
    <td><b>专业写作者</b></td>
    <td>方案工程师、咨询顾问、政策研究员</td>
    <td>快速润色、结构调整、术语统一，且不能误改关键表述</td>
  </tr>
  <tr>
    <td><b>管理岗位</b></td>
    <td>项目经理、部门负责人、数字化转型专员</td>
    <td>口述/草稿快速成稿，材料定稿前风险排查</td>
  </tr>
  <tr>
    <td><b>综合办公人员</b></td>
    <td>行政、文秘、综合文字岗</td>
    <td>高频修订汇报、制度、通知，操作路径短、学习成本低</td>
  </tr>
  <tr>
    <td><b>IT 管理员</b></td>
    <td>信息化负责人、桌面应用管理员</td>
    <td>便携部署、依赖清晰、数据不出本地工作区</td>
  </tr>
</table>

<div class="page-break"></div>

<!-- 5. 核心价值 -->
<h1>5. 核心价值与差异化</h1>
<table>
  <tr><th width="22%">价值维度</th><th>用户收益</th><th width="28%">DocMate 差异化</th></tr>
  <tr>
    <td><b>效率提升</b></td>
    <td>减少 60%+ 手动定位与复制粘贴时间（视文档长度与改稿频次而定）</td>
    <td>Agent 无选区改稿 + 选区 Bubble Menu 双入口</td>
  </tr>
  <tr>
    <td><b>质量可控</b></td>
    <td>降低 AI 误改风险，改稿结果可预期</td>
    <td>编辑器与 Agent 面板红删绿增双向同步 Diff</td>
  </tr>
  <tr>
    <td><b>风格一致</b></td>
    <td>输出符合组织话术与行业术语</td>
    <td>知识库 RAG + 偏好引擎持续学习</td>
  </tr>
  <tr>
    <td><b>体验统一</b></td>
    <td>一个窗口完成写、改、审、定</td>
    <td>编辑器 / Agent / 历史 / 设置一体化布局</td>
  </tr>
  <tr>
    <td><b>轻量交付</b></td>
    <td>无需复杂安装与 IT 审批流程</td>
    <td>publish 便携包 + VBS/BAT 一键启动</td>
  </tr>
</table>
<div class="callout-green">
  <b>与通用 AI 聊天工具的差异：</b>DocMate 的 Agent 输出不是「一段建议文字」，而是<b>结构化修改方案</b>（原文锚点 + 新文本 + 操作类型），
  并自动映射到编辑器 Diff 视图，形成「对话 → 预览 → 确认 → 落稿」的完整闭环。
</div>

<!-- 6. 架构 -->
<h1>6. 产品架构概览</h1>
<p>DocMate 采用经典的三层轻型桌面架构，兼顾启动速度与功能扩展性：</p>
<table>
  <tr><th width="20%">层级</th><th>组件</th><th>职责</th></tr>
  <tr>
    <td><b>表现层</b></td>
    <td>Vue 3 前端 · TipTap 编辑器 · Agent 面板</td>
    <td>文稿编辑、Diff 渲染、对话交互、语音输入、设置管理</td>
  </tr>
  <tr>
    <td><b>能力层</b></td>
    <td>AI 路由 · 改稿引擎 · 知识库检索 · 偏好引擎</td>
    <td>任务分发（修改/润色/问答/风险扫描等）、段落定位、RAG 增强、行为学习</td>
  </tr>
  <tr>
    <td><b>基础层</b></td>
    <td>Electron 主进程 · 本地文件系统 · IPC 通信</td>
    <td>工作区管理、文件读写、模型 API 调用、交互日志持久化</td>
  </tr>
</table>
<h2>6.1 核心改稿闭环</h2>
<p><b>用户指令</b> → AI 任务路由 → 生成 RevisionResult → 编辑器 Diff 预览 → 用户 Apply/拒绝 → 写入正文 → 历史记录 & 偏好学习</p>
<h2>6.2 关键交互模块</h2>
<ul>
  <li><b>EditorPanel：</b>富文本编辑、Diff 高亮、快捷键采纳/拒绝</li>
  <li><b>AiPanel：</b>Agent 对话、Diff 卡片、任务终止、修改历史</li>
  <li><b>AiBubbleMenu：</b>选区快捷改稿、语音输入</li>
  <li><b>KnowledgeBaseModal：</b>参考文档导入与检索</li>
  <li><b>PreferencePanel：</b>风格偏好与自动学习开关</li>
</ul>

<div class="page-break"></div>

<!-- 7. 功能模块 -->
<h1>7. 功能模块详解</h1>

<h2>7.1 智能 Agent 改稿引擎</h2>
<p>Agent 面板是 DocMate 的核心交互入口，支持类 Cursor 的自然语言改稿体验：</p>
<ul>
  <li><b>无选区改稿：</b>直接描述「删除最后一段」「把第二章改正式」，AI 自动定位目标段落</li>
  <li><b>选区增强：</b>选中文字后，Agent 自动携带选区上下文，改稿更精准</li>
  <li><b>多任务类型：</b>修改、润色、口语转正式、问答、风险扫描、表格处理</li>
  <li><b>流式思考：</b>展示 AI 推理过程，支持任务中途终止</li>
  <li><b>段落澄清：</b>定位歧义时主动给出候选段落，用户点选后继续</li>
</ul>

<h2>7.2 可视化 Diff 与确认机制</h2>
<ul>
  <li><b>红删：</b>待删除原文以红色背景 + 删除线标记（编辑器 + Agent 卡片同步）</li>
  <li><b>绿增：</b>新增内容以绿色背景展示，替换场景红绿并列对比</li>
  <li><b>Apply 采纳：</b>确认后将 Diff 落稿；预览失败时仍可通过直接改稿路径执行</li>
  <li><b>拒绝/撤销：</b>Esc 拒绝当前 Diff，不改动正文</li>
  <li><b>重新生成：</b>对同一指令最多 3 次重新生成备选方案</li>
</ul>

<h2>7.3 选区操作条（Bubble Menu）</h2>
<ul>
  <li>鼠标选中文字后，编辑器上方浮层操作条自动出现</li>
  <li>支持直接输入改稿指令，与 Agent 面板共享改稿逻辑</li>
  <li>集成语音输入，适合口述改稿、移动办公场景</li>
  <li>交互层与 Tippy 浮层深度适配，输入框可正常聚焦与提交</li>
</ul>

<h2>7.4 文稿与工作区</h2>
<ul>
  <li>左侧文件树管理 Markdown 工作区文稿</li>
  <li>支持新建文稿、导入外部文件、打开本地工作区文件夹</li>
  <li>TipTap 富文本引擎，支持标题、段落、列表、表格、加粗等常用格式</li>
  <li>标题栏快捷入口：文件 / 导入 / 新建 / AI 助手 / 工作区</li>
</ul>

<h2>7.5 知识库（RAG）</h2>
<ul>
  <li>导入参考文档（Word 等），自动分块索引</li>
  <li>改稿时检索相关知识片段，注入 AI 上下文</li>
  <li>适用于制度对标、术语统一、方案参照等场景</li>
</ul>

<h2>7.6 偏好学习与风格记忆</h2>
<ul>
  <li>自动记录用户的 Apply / 拒绝 / 重新生成行为</li>
  <li>支持配置正式度、常用表述、禁用词、行业术语</li>
  <li>偏好引擎定期 digest，让 AI 输出逐步贴合用户习惯</li>
</ul>

<h2>7.7 风险扫描</h2>
<ul>
  <li>对全文或指定范围进行表述与合规风险扫描</li>
  <li>按高/中/低分级展示风险条目，附原因与修改建议</li>
  <li>支持定位原文、采纳建议、忽略条目</li>
</ul>

<h2>7.8 修改历史</h2>
<ul>
  <li>Agent 面板「历史」Tab 记录每次改稿的时间、指令、原文、新文及状态</li>
  <li>便于回溯「谁在什么时间做了什么修改决策」</li>
</ul>

<!-- 8. 功能矩阵 -->
<h1>8. 功能能力矩阵</h1>
<table>
  <tr>
    <th>能力项</th><th>修改</th><th>润色</th><th>删除</th><th>新增</th><th>问答</th><th>风险扫描</th><th>语音</th>
  </tr>
  <tr><td>Agent 对话</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>—</td></tr>
  <tr><td>选区 Bubble Menu</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>—</td><td>—</td><td>✓</td></tr>
  <tr><td>Diff 预览</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>—</td><td>—</td><td>—</td></tr>
  <tr><td>知识库增强</td><td>✓</td><td>✓</td><td>—</td><td>✓</td><td>✓</td><td>—</td><td>—</td></tr>
  <tr><td>偏好学习</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>—</td><td>—</td><td>—</td></tr>
  <tr><td>修改历史</td><td>✓</td><td>✓</td><td>✓</td><td>✓</td><td>—</td><td>—</td><td>—</td></tr>
</table>

<div class="page-break"></div>

<!-- 9. 用户路径 -->
<h1>9. 典型用户路径</h1>
<h2>9.1 路径 A：Agent 无选区改稿（推荐）</h2>
<ol>
  <li>打开 DocMate，加载或新建工作区文稿</li>
  <li>按 Ctrl+M 打开 Agent 面板，输入自然语言指令</li>
  <li>AI 返回修改方案，对话区展示红删绿增 Diff 卡片</li>
  <li>Diff 自动同步至编辑器，用户审阅确认</li>
  <li>点击 Apply 或 Ctrl+Enter 采纳，修改写入正文</li>
</ol>
<h2>9.2 路径 B：选区精准改稿</h2>
<ol>
  <li>在编辑器中选中目标段落或句子</li>
  <li>Bubble Menu 弹出，输入改稿指令或使用语音输入</li>
  <li>编辑器内展示 Diff 预览，确认后采纳</li>
</ol>
<h2>9.3 路径 C：定稿前质检</h2>
<ol>
  <li>完成文稿初稿</li>
  <li>Agent 输入「扫描全文风险」或类似指令</li>
  <li>逐条审阅风险条目，定位原文并决定是否采纳建议</li>
  <li>结合知识库参考，做最后一轮术语与风格统一</li>
</ol>

<!-- 10. 场景化方案 -->
<h1>10. 场景化解决方案</h1>
<table>
  <tr><th width="22%">场景</th><th>用户指令示例</th><th>产品行为</th><th width="22%">预期收益</th></tr>
  <tr>
    <td><b>方案润色</b></td>
    <td>「把第三节改得更正式，适合向领导汇报」</td>
    <td>定位第三节 → 生成正式化 Diff → 用户确认落稿</td>
    <td>分钟级完成段落级润色</td>
  </tr>
  <tr>
    <td><b>段落删除</b></td>
    <td>「删除关于 SSDS 资金的那段」</td>
    <td>定位目标段 → 红色删除线预览 → Apply 后移除</td>
    <td>避免手动查找与误删</td>
  </tr>
  <tr>
    <td><b>口语转书面</b></td>
    <td>「把这段口语改成公文表述」</td>
    <td>选区或 Agent 定位 → 红绿 Diff 对比 → 确认</td>
    <td>口述草稿快速成稿</td>
  </tr>
  <tr>
    <td><b>术语统一</b></td>
    <td>「按知识库里的制度模板统一术语」</td>
    <td>知识库 RAG 增强 → 批量替换建议 → 逐条确认</td>
    <td>多文档风格一致</td>
  </tr>
  <tr>
    <td><b>定稿质检</b></td>
    <td>「扫描全文有没有表述风险」</td>
    <td>风险条目分级列出 → 定位 + 建议 → 人工决策</td>
    <td>降低定稿返工率</td>
  </tr>
</table>

<!-- 11. 交互设计 -->
<h1>11. 交互设计与体验原则</h1>
<table>
  <tr><th width="25%">设计原则</th><th>具体体现</th></tr>
  <tr><td><b>Diff 先行</b></td><td>任何 Agent 改稿方案默认进入预览态，不直接覆盖正文</td></tr>
  <tr><td><b>双通道输入</b></td><td>Agent 面板（全局改稿）+ Bubble Menu（选区改稿）互补</td></tr>
  <tr><td><b>反馈即时</b></td><td>流式思考日志、Toast 提示、Diff 同步状态标签</td></tr>
  <tr><td><b>操作可逆</b></td><td>Esc 拒绝、重新生成、修改历史追溯</td></tr>
  <tr><td><b>快捷键友好</b></td><td>Ctrl+M 打开 Agent · Ctrl+B 切换文件树 · Ctrl+Enter 采纳 · Esc 拒绝</td></tr>
  <tr><td><b>面板可拖拽</b></td><td>Agent 面板支持拖拽 reposition，不遮挡编辑区</td></tr>
</table>

<!-- 12. 安全合规 -->
<h1>12. 安全、合规与数据策略</h1>
<ul>
  <li><b>本地优先：</b>工作区文稿存储在用户指定本地目录，不强制上传云端</li>
  <li><b>API 调用：</b>大模型推理通过用户配置的 API 密钥发起，密钥应用内管理</li>
  <li><b>人工确认：</b>所有 AI 改稿须经 Apply 确认，系统不自动静默修改</li>
  <li><b>交互日志：</b>改稿采纳/拒绝行为本地记录，用于偏好学习，用户可配置</li>
  <li><b>知识库数据：</b>参考文档分块索引存储于本地，改稿时按需检索</li>
</ul>
<div class="callout-warn">
  <b>提示：</b>涉及敏感内容的文稿，建议在部署前明确大模型 API 的数据处理协议，并优先选用符合组织合规要求的模型服务。
</div>

<div class="page-break"></div>

<!-- 13. 部署 -->
<h1>13. 部署交付与运行要求</h1>
<h2>13.1 交付物清单</h2>
<table>
  <tr><th>文件/目录</th><th>说明</th></tr>
  <tr><td>DocMate.vbs</td><td>推荐启动入口，自动检测并安装依赖</td></tr>
  <tr><td>启动DocMate.bat</td><td>备用启动脚本，含依赖安装与日志</td></tr>
  <tr><td>安装依赖.bat</td><td>手动安装 node_modules</td></tr>
  <tr><td>dist/</td><td>前端构建产物</td></tr>
  <tr><td>electron/</td><td>Electron 主进程与 AI 服务</td></tr>
  <tr><td>使用说明.txt</td><td>版本说明与快速指引</td></tr>
</table>
<h2>13.2 系统要求</h2>
<table>
  <tr><th>项目</th><th>最低要求</th><th>推荐配置</th></tr>
  <tr><td>操作系统</td><td>Windows 10 64 位</td><td>Windows 11 64 位</td></tr>
  <tr><td>内存</td><td>4 GB</td><td>8 GB 及以上</td></tr>
  <tr><td>磁盘空间</td><td>500 MB（含依赖）</td><td>1 GB 及以上</td></tr>
  <tr><td>网络</td><td>调用大模型 API 时需联网</td><td>稳定宽带连接</td></tr>
  <tr><td>其他</td><td>首次运行需 Node.js（可自动引导安装）</td><td>Node.js LTS 预装</td></tr>
</table>

<!-- 14. 快速上手 -->
<h1>14. 快速上手指南</h1>
<ol>
  <li><b>启动应用：</b>双击 <code>DocMate.vbs</code>（首次运行自动安装依赖，约 1–3 分钟）</li>
  <li><b>配置模型：</b>Agent 面板 → 设置 → 填写大模型 API 地址与密钥</li>
  <li><b>创建工作区：</b>标题栏「工作区」选择本地文件夹，或「新建」创建文稿</li>
  <li><b>开始改稿：</b>Ctrl+M 打开 Agent，输入如「把第一段改简洁一些」</li>
  <li><b>确认落稿：</b>审阅 Diff 后点击 Apply 或 Ctrl+Enter</li>
  <li><b>导入参考：</b>知识库中导入制度/模板文档，改稿时自动检索增强</li>
</ol>

<h2>14.1 常用快捷键</h2>
<table>
  <tr><th width="35%">快捷键</th><th>功能</th></tr>
  <tr><td>Ctrl + M</td><td>打开 / 聚焦 Agent 面板</td></tr>
  <tr><td>Ctrl + B</td><td>显示 / 隐藏文件树</td></tr>
  <tr><td>Ctrl + Enter</td><td>采纳当前 Diff 修改</td></tr>
  <tr><td>Esc</td><td>拒绝当前 Diff 修改</td></tr>
</table>

<!-- 15. FAQ -->
<h1>15. 常见问题 FAQ</h1>
<h3>Q1：Agent 改稿后编辑器没有显示红色/绿色标记？</h3>
<p>点击 Agent 对话中的 Diff 卡片同步预览；若定位失败，仍可直接点击 Apply，系统将尝试直接改稿。</p>
<h3>Q2：Apply 按钮点击后没有反应？</h3>
<p>请确认 ${version} 及以上版本；确保目标段落仍存在于文档中；必要时先点击 Diff 卡片「预览」再 Apply。</p>
<h3>Q3：首次启动失败或弹出乱码？</h3>
<p>请使用 DocMate.vbs 或 启动DocMate.bat 启动，勿通过 PowerShell 重定向 stderr；若缺少依赖，双击「安装依赖.bat」。</p>
<h3>Q4：是否支持 Mac / Linux？</h3>
<p>当前版本仅交付 Windows 便携包；跨平台版本在规划中。</p>
<h3>Q5：文稿保存在哪里？</h3>
<p>保存在用户打开的本地工作区文件夹内，Markdown 格式，可用任意文本编辑器打开。</p>

<!-- 16. 规划 -->
<h1>16. 产品规划方向</h1>
<table>
  <tr><th width="18%">阶段</th><th>方向</th><th>预期价值</th></tr>
  <tr>
    <td><b>近期</b></td>
    <td>Diff 定位准确率优化 · Apply 链路稳定性 · 启动体验改进</td>
    <td>降低上手门槛，提升改稿成功率</td>
  </tr>
  <tr>
    <td><b>中期</b></td>
    <td>多文档批注 · 版本对比 · 更多导入格式</td>
    <td>覆盖更完整改稿审校流程</td>
  </tr>
  <tr>
    <td><b>远期</b></td>
    <td>团队协作 · 企业私有化部署 · 插件生态</td>
    <td>从个人工具延伸至组织级改稿平台</td>
  </tr>
</table>

<!-- 17. 术语表 -->
<h1>17. 术语表</h1>
<table>
  <tr><th width="22%">术语</th><th>说明</th></tr>
  <tr><td>Agent</td><td>DocMate 中的 AI 对话改稿助手，类似 Cursor 的 Agent 模式</td></tr>
  <tr><td>Diff</td><td>修改差异可视化，红色表示删除、绿色表示新增</td></tr>
  <tr><td>Apply</td><td>用户确认采纳 AI 修改方案，写入正文</td></tr>
  <tr><td>RAG</td><td>检索增强生成，改稿时引用知识库相关内容</td></tr>
  <tr><td>工作区</td><td>用户指定的本地文件夹，存放 DocMate 管理的文稿</td></tr>
  <tr><td>便携包</td><td>publish40 精简运行目录，含源码、构建产物与启动脚本</td></tr>
</table>

<div class="callout" style="margin-top: 24pt;">
  <b>结语</b><br>
  DocMate 闪闪文档致力于成为专业写作者最可信赖的 AI 改稿工作台——<b>效率接近 AI，可控性接近人工审校</b>。
  我们期待与您一起，把「说一句话就能改稿」变成安全、透明、可回溯的日常办公能力。
</div>

<p class="footer">
  DocMate 闪闪文档 · 产品发布说明文档 V1.1 · ${version}<br>
  本文档供内部评审与对外初步介绍使用，内容随产品迭代持续更新
</p>

</body>
</html>`

fs.writeFileSync(outPath, '\ufeff' + html, 'utf8')
console.log('已更新: ' + outPath)
