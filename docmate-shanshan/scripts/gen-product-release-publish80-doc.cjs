const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'))
const desktop = path.join(process.env.USERPROFILE || '', 'Desktop')
const outPath = path.join(desktop, 'DocMate产品发布说明.doc')
const version = `v${pkg.version}`
const docVersion = 'V1.4'
const publishName = 'publish80'
const docDate = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
})

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
  body { font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif; font-size: 11pt; line-height: 1.75; color: #1f2933; }
  .cover { text-align: center; padding: 52pt 0 38pt 0; page-break-after: always; }
  .cover-logo { font-size: 30pt; font-weight: bold; color: #007acc; letter-spacing: 2pt; }
  .cover-sub { font-size: 16pt; color: #222; margin-top: 12pt; }
  .cover-tag { font-size: 12pt; color: #666; margin-top: 24pt; }
  .cover-meta { font-size: 10.5pt; color: #777; margin-top: 48pt; line-height: 2; }
  h1 { font-size: 18pt; color: #007acc; margin-top: 24pt; border-bottom: 2pt solid #007acc; padding-bottom: 6pt; }
  h2 { font-size: 13pt; color: #111827; margin-top: 16pt; }
  h3 { font-size: 11.5pt; color: #374151; margin-top: 12pt; }
  p { margin: 6pt 0; text-align: justify; }
  ul, ol { margin: 6pt 0 6pt 20pt; }
  li { margin-bottom: 4pt; }
  table { width: 100%; border-collapse: collapse; margin: 10pt 0; font-size: 10.5pt; }
  th { background: #eef6ff; color: #111827; font-weight: bold; border: 1pt solid #cbd5e1; padding: 6pt 8pt; text-align: left; }
  td { border: 1pt solid #cbd5e1; padding: 6pt 8pt; vertical-align: top; }
  .callout { background: #f0f7ff; border-left: 4pt solid #007acc; padding: 10pt 14pt; margin: 10pt 0; }
  .callout-green { background: #f0fdf4; border-left-color: #16a34a; }
  .callout-warn { background: #fff7ed; border-left-color: #f59e0b; }
  .toc { background: #fafafa; border: 1pt solid #e5e7eb; padding: 12pt 16pt; margin: 12pt 0; }
  .page-break { page-break-before: always; }
  .footer { text-align: center; color: #888; font-size: 9.5pt; margin-top: 36pt; border-top: 1pt solid #eee; padding-top: 12pt; }
  code { font-family: Consolas, monospace; background: #f3f4f6; padding: 1pt 3pt; }
</style>
</head>
<body>

<div class="cover">
  <p class="cover-logo">DocMate 闪闪文档</p>
  <p class="cover-sub">产品发布说明文档</p>
  <p class="cover-tag">面向中国建筑国际集团人力与党建场景的 AI 文稿修改助手</p>
  <p class="cover-meta">
    产品版本：${version}<br>
    发布包：${publishName}<br>
    文档版本：${docVersion}<br>
    发布日期：${docDate}<br>
    文档密级：内部公开<br>
    适用对象：业务用户、产品评审、售前演示、内部试点推广
  </p>
</div>

<h1>文档修订记录</h1>
<table>
  <tr><th width="12%">版本</th><th width="18%">日期</th><th width="15%">修订人</th><th>修订说明</th></tr>
  <tr><td>V1.0</td><td>2026 年 6 月</td><td>产品组</td><td>初版产品介绍</td></tr>
  <tr><td>V1.1</td><td>2026 年 6 月</td><td>产品组</td><td>补充 Agent 改稿、Diff 预览、知识库与偏好学习说明</td></tr>
  <tr><td>V1.2</td><td>2026 年 6 月</td><td>产品组</td><td>补充三栏布局、暗色 UI、面板浮窗与动画增强</td></tr>
  <tr><td>V1.3</td><td>2026 年 6 月</td><td>产品组</td><td>补充“闪闪”助手命名、角色提示词和自动学习详细设置</td></tr>
  <tr><td>${docVersion}</td><td>${docDate}</td><td>产品组</td><td>基于 ${publishName} 更新 Bubble 与闪闪任务同步、在线语音识别和交付信息</td></tr>
</table>

<h1>目录</h1>
<div class="toc">
<ol>
  <li>产品摘要</li>
  <li>本版发布亮点</li>
  <li>产品定位与适用场景</li>
  <li>核心功能说明</li>
  <li>闪闪助手角色与工作方式</li>
  <li>Bubble 与聊天同步改稿流程</li>
  <li>语音识别方案</li>
  <li>自动学习习惯设置</li>
  <li>安全合规与数据策略</li>
  <li>部署交付与快速上手</li>
  <li>FAQ 与后续规划</li>
</ol>
</div>

<div class="page-break"></div>

<h1>1. 产品摘要</h1>
<p>
  <b>DocMate 闪闪文档</b>是一款面向 Windows 平台的便携式 AI 文稿修改助手。本产品聚焦机关、企业、公文、制度、党建材料、人力文档等专业文字场景，
  通过“编辑器 + 闪闪聊天面板 + Bubble 选区操作条 + Diff 确认”的一体化工作流，让用户用自然语言完成润色、精简、正式化、风险检查和口语转公文。
</p>
<div class="callout">
  <b>核心原则：</b>闪闪只提出修改建议，不自动替换原文。每次修改均先以 Diff 方式展示，由用户明确采纳或拒绝，确保“AI 提效、人做决策、结果可控”。
</div>
<table>
  <tr><th width="22%">项目</th><th>说明</th></tr>
  <tr><td>产品名称</td><td>DocMate 闪闪文档</td></tr>
  <tr><td>助手名称</td><td>闪闪</td></tr>
  <tr><td>当前版本</td><td>${version}（${publishName}）</td></tr>
  <tr><td>产品形态</td><td>Windows 便携桌面应用（Electron + Vue 3 + TipTap）</td></tr>
  <tr><td>推荐启动</td><td><code>${publishName}/DocMate.vbs</code> 或 <code>${publishName}/启动DocMate.bat</code></td></tr>
  <tr><td>核心能力</td><td>智能改稿、Diff 预览、选区同步、闪闪聊天、在线/本地语音识别、知识库、自动学习习惯</td></tr>
</table>

<h1>2. 本版发布亮点</h1>
<table>
  <tr><th width="24%">亮点</th><th>说明</th><th width="24%">用户价值</th></tr>
  <tr>
    <td><b>Bubble 与闪闪任务同步</b></td>
    <td>选中文字后在 Bubble 面板发起的任务，会同步进入右侧闪闪聊天区，包含用户指令、当前选区、Thinking 状态和最终 Diff 卡片。</td>
    <td>避免“两套任务入口不同步”，选区改稿也有完整聊天上下文。</td>
  </tr>
  <tr>
    <td><b>闪闪助手品牌化</b></td>
    <td>右侧 Agent 面板统一改名为“闪闪”，开场白更新为“你好！我是闪闪文档助手，你的文稿修改搭档……”</td>
    <td>降低工具感，形成明确产品心智。</td>
  </tr>
  <tr>
    <td><b>默认角色提示词</b></td>
    <td>主进程默认注入“闪闪文档”角色提示词，明确服务中国建筑国际集团人力部门和党建部门，遵循合规优先、保留原意、不编造等原则。</td>
    <td>输出更贴近企业公文和党建、人力场景。</td>
  </tr>
  <tr>
    <td><b>在线优先语音识别</b></td>
    <td>模型配置中新增语音识别模式：在线优先、仅在线、仅本地。在线模式支持 OpenAI 兼容 <code>/audio/transcriptions</code> 接口。</td>
    <td>联网时更快得到文字，失败时可自动回退本地 Whisper tiny。</td>
  </tr>
  <tr>
    <td><b>自动学习详细设置</b></td>
    <td>用户可自行选择学习来源、学习频率、隐私记录、保留条数、部门场景、风险敏感度等。</td>
    <td>让“学习习惯”从单一开关升级为可控配置。</td>
  </tr>
</table>

<h1>3. 产品定位与适用场景</h1>
<h2>3.1 产品定位</h2>
<p>
  DocMate 定位为<b>轻型桌面级 AI 改稿工作台</b>。它不是通用聊天机器人，也不是自动生成全文的黑盒写作工具，而是围绕“已有文字的修改、审校、确认替换”建立的专业辅助工具。
</p>
<h2>3.2 重点服务场景</h2>
<table>
  <tr><th width="18%">部门场景</th><th>常见文档</th><th>重点要求</th></tr>
  <tr>
    <td><b>人力部门</b></td>
    <td>人事通知、招聘启事、绩效考核文件、培训方案、制度修订稿、劳动合同补充条款</td>
    <td>正式、规范、体面；涉及薪酬、职级、考核结果时措辞严谨无歧义。</td>
  </tr>
  <tr>
    <td><b>党建部门</b></td>
    <td>党委文件、学习通知、组织生活方案、述职报告、民主生活会材料、思想汇报、主题党日活动方案</td>
    <td>政治站位高、术语规范、政策引用准确，不将政治术语口语化。</td>
  </tr>
  <tr>
    <td><b>综合办公</b></td>
    <td>会议材料、工作方案、汇报提纲、通知公告、总结报告</td>
    <td>表达清晰、结构严谨、风格统一、定稿前可风险检查。</td>
  </tr>
</table>

<h1>4. 核心功能说明</h1>
<h2>4.1 闪闪聊天面板</h2>
<ul>
  <li>支持无选区自然语言改稿，例如“把第二段改正式”“删掉最后一段”“文末加总结”。</li>
  <li>自动携带全文、当前选区、历史对话、知识库片段和用户偏好。</li>
  <li>输出 Diff 卡片，用户点击卡片可同步到编辑器预览。</li>
  <li>支持任务终止、重新生成、修改历史折叠查看。</li>
</ul>
<h2>4.2 Bubble 选区操作条</h2>
<ul>
  <li>用户选中文字后自动出现，支持快捷“正式、精简、润色、风险”等胶囊按钮。</li>
  <li>支持 <code>/</code> 斜杠菜单和自然语言输入。</li>
  <li>本版起 Bubble 发起的任务会统一进入闪闪聊天区，任务、选区和结果保持同步。</li>
</ul>
<h2>4.3 Diff 预览与确认替换</h2>
<ul>
  <li>红色代表删除，绿色代表新增，适配暗色主题。</li>
  <li>采纳前不会改写正文；用户可通过 Ctrl+Enter 采纳，Esc 拒绝。</li>
  <li>采纳/拒绝带确认动画，减少误操作感知成本。</li>
</ul>
<h2>4.4 知识库与偏好</h2>
<ul>
  <li>支持导入制度、模板、参考材料，系统自动分块检索并注入相关上下文。</li>
  <li>支持写作偏好设置和自动学习，逐步沉淀用户常用表达、避免用词和领域术语。</li>
</ul>

<div class="page-break"></div>

<h1>5. 闪闪助手角色与工作方式</h1>
<h2>5.1 开场白</h2>
<div class="callout-green">
  你好！我是闪闪文档助手，你的文稿修改搭档。<br><br>
  我的工作方式很简单：你把文字粘贴进来，告诉我要怎么改，我来出修改建议！
</div>
<h2>5.2 默认角色提示词摘要</h2>
<p>系统默认将闪闪定义为“闪闪文档”的文稿修改助手，服务于中国建筑国际集团的人力部门和党建部门。核心行为边界如下：</p>
<ul>
  <li>闪闪是公文写作辅助工具，不是内容创作者。</li>
  <li>根据用户指令对已有文字润色、精简、正式化、风格转换或风险检查。</li>
  <li>保留原文核心意思和事实，不添加原文没有的事实、数据或观点。</li>
  <li>涉及人事制度、党建表述时，优先确保法规、政策和党内规范表述准确。</li>
  <li>风险检查输出风险列表，修改类任务输出可对比、可采纳的建议文本。</li>
</ul>

<h1>6. Bubble 与聊天同步改稿流程</h1>
<p>本版对改稿入口进行了重构：Bubble 面板不再单独调用编辑器 AI，而是统一调用右侧闪闪面板的任务管线。</p>
<table>
  <tr><th width="22%">步骤</th><th>系统行为</th><th>用户感知</th></tr>
  <tr><td>选中文字</td><td>编辑器锁定当前选区，保持蓝色高亮</td><td>知道本次任务针对哪段文字</td></tr>
  <tr><td>Bubble 输入指令</td><td>指令转发到闪闪面板，自动打开/聚焦聊天区</td><td>右侧聊天区出现用户指令和选区摘要</td></tr>
  <tr><td>闪闪分析</td><td>同一条任务流处理 Thinking、任务路由、段落定位和生成</td><td>Bubble 显示“已同步到右侧闪闪面板”状态</td></tr>
  <tr><td>生成方案</td><td>聊天区展示 Diff 卡片，同时编辑器显示红删绿增</td><td>用户在一个上下文内审阅修改建议</td></tr>
  <tr><td>采纳或拒绝</td><td>采纳写入正文，拒绝清除 Diff，并同步修改历史</td><td>结果可控、历史可追溯</td></tr>
</table>

<h1>7. 语音识别方案</h1>
<h2>7.1 当前能力</h2>
<p>DocMate 支持在闪闪面板内语音输入。用户点击麦克风开始录音，再次点击结束录音并转为文字。识别后的文字会进入闪闪输入框并可直接提交为任务。</p>
<h2>7.2 publish80 新增：在线优先识别</h2>
<table>
  <tr><th width="24%">模式</th><th>说明</th><th width="24%">适用场景</th></tr>
  <tr><td><b>在线优先（推荐）</b></td><td>优先调用 OpenAI 兼容 <code>/audio/transcriptions</code> 接口，失败后自动回退本地 Whisper tiny。</td><td>有网络、希望识别更快更准</td></tr>
  <tr><td><b>仅在线</b></td><td>只使用联网语音识别，失败时直接提示错误。</td><td>企业已有稳定语音识别服务</td></tr>
  <tr><td><b>仅本地</b></td><td>使用本地 <code>@xenova/transformers</code> Whisper tiny 模型，首次加载较慢。</td><td>无网络或敏感环境</td></tr>
</table>
<div class="callout-warn">
  <b>语音建议：</b>如果允许联网，推荐接入企业可用的 OpenAI 兼容 Whisper 服务，或智谱、火山、阿里、讯飞等具备低延迟 ASR 的服务网关。当前产品已预留“在线接口地址”和“语音模型”配置。
</div>

<h1>8. 自动学习习惯设置</h1>
<p>本版将“自动学习我的偏好”从单一开关升级为可细分配置，让用户决定闪闪如何学习、学习什么、保存多久以及如何应用。</p>
<table>
  <tr><th width="24%">设置项</th><th>说明</th></tr>
  <tr><td>启用自动学习</td><td>是否根据用户采纳/拒绝记录总结写作偏好。</td></tr>
  <tr><td>应用方式</td><td>可选“只作为建议约束”或“自动用于每次生成”。</td></tr>
  <tr><td>学习频率</td><td>可选每 5 / 10 / 20 次操作自动总结一次。</td></tr>
  <tr><td>学习来源</td><td>可选择是否学习采纳修改、拒绝修改、常用指令、手动术语。</td></tr>
  <tr><td>隐私与记录</td><td>可选择是否保存文本片段、是否保存被拒绝原文。</td></tr>
  <tr><td>文稿场景</td><td>可选综合公文、人力部门、党建部门。</td></tr>
  <tr><td>风险敏感度</td><td>可选标准、严格、最高。</td></tr>
  <tr><td>词语与术语</td><td>可维护倾向用词、避免用词和行业术语。</td></tr>
</table>

<h1>9. 安全合规与数据策略</h1>
<ul>
  <li><b>API Key 安全：</b>大模型和语音识别 API 调用在 Electron 主进程完成，不暴露到前端页面。</li>
  <li><b>人做决策：</b>AI 只生成建议，修改必须经用户采纳或拒绝。</li>
  <li><b>本地工作区：</b>用户文稿默认保存在本地工作区，便于管理和迁移。</li>
  <li><b>偏好可控：</b>用户可关闭自动学习，或限制学习来源和保留记录数量。</li>
  <li><b>联网语音：</b>如启用在线语音识别，音频会发送至所配置的语音服务，需遵守企业数据合规要求。</li>
</ul>

<div class="page-break"></div>

<h1>10. 部署交付与快速上手</h1>
<h2>10.1 交付物</h2>
<table>
  <tr><th width="28%">文件/目录</th><th>说明</th></tr>
  <tr><td><code>${publishName}/DocMate.vbs</code></td><td>推荐启动入口，双击启动应用。</td></tr>
  <tr><td><code>${publishName}/启动DocMate.bat</code></td><td>备用启动脚本，含依赖检测。</td></tr>
  <tr><td><code>${publishName}/安装依赖.bat</code></td><td>首次运行依赖缺失时可手动安装。</td></tr>
  <tr><td><code>${publishName}/dist/</code></td><td>前端构建产物。</td></tr>
  <tr><td><code>${publishName}/electron/</code></td><td>主进程、AI 服务、语音识别、文件工作区逻辑。</td></tr>
</table>
<h2>10.2 快速上手</h2>
<ol>
  <li>双击 <code>${publishName}/DocMate.vbs</code> 启动。</li>
  <li>在模型配置中填写大模型 API 地址、API Key 和模型名称。</li>
  <li>如需快速语音识别，在“语音识别”里选择“在线优先”，并配置兼容接口。</li>
  <li>将文稿粘贴到编辑器，或导入现有文档。</li>
  <li>选中文字后用 Bubble 输入指令，或在右侧闪闪面板直接对话。</li>
  <li>审阅 Diff 后按 Ctrl+Enter 采纳，或 Esc 拒绝。</li>
</ol>
<h2>10.3 常用快捷键</h2>
<table>
  <tr><th width="30%">快捷键</th><th>功能</th></tr>
  <tr><td>Ctrl + K</td><td>打开 / 聚焦闪闪面板</td></tr>
  <tr><td>Ctrl + B</td><td>显示 / 隐藏文件侧栏</td></tr>
  <tr><td>Ctrl + Enter</td><td>采纳当前 Diff 修改</td></tr>
  <tr><td>Esc</td><td>拒绝当前 Diff 修改</td></tr>
</table>

<h1>11. FAQ 与后续规划</h1>
<h3>Q1：为什么 Bubble 发起任务后右侧也会出现消息？</h3>
<p>这是 publish80 的核心改造。Bubble 和闪闪面板现在使用同一条任务管线，方便保留选区、指令、思考过程和结果卡片。</p>
<h3>Q2：在线语音识别一定能用吗？</h3>
<p>取决于所配置的服务是否兼容 <code>/audio/transcriptions</code> 接口。若选择“在线优先”，在线失败后会自动回退本地识别。</p>
<h3>Q3：自动学习会不会保存敏感内容？</h3>
<p>用户可以在“写作偏好”中关闭保存文本片段，或关闭自动学习；也可以限制记录保留条数。</p>
<h3>Q4：闪闪会自动替换我的原文吗？</h3>
<p>不会。闪闪只给修改建议，所有改动必须经用户采纳后才会写入正文。</p>
<h2>后续规划</h2>
<ul>
  <li>语音识别增加更多企业 ASR 服务预设。</li>
  <li>Bubble 与闪闪面板增加任务状态更细粒度的同步提示。</li>
  <li>支持多文档批量审校、版本对比和导出修订报告。</li>
  <li>进一步优化大文档下的编辑器性能和 chunk 分包体积。</li>
</ul>

<p class="footer">
  DocMate 闪闪文档 · 产品发布说明文档 ${docVersion} · ${version} · ${publishName}<br>
  本文档供内部评审、试点推广和用户培训使用，内容随产品迭代持续更新。
</p>

</body>
</html>`

fs.mkdirSync(desktop, { recursive: true })
fs.writeFileSync(outPath, '\ufeff' + html, 'utf8')
console.log('已更新: ' + outPath)
