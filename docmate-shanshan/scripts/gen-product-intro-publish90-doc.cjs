const fs = require('fs')
const path = require('path')

const root = path.join(__dirname, '..')
const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf-8'))
const desktop = path.join(process.env.USERPROFILE || '', 'Desktop')
const outPath = path.join(desktop, 'DocMate闪闪文档产品介绍.doc')
const version = `v${pkg.version}`
const publishName = 'publish90'
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
  .cover { text-align: center; padding: 58pt 0 40pt 0; page-break-after: always; }
  .cover-logo { font-size: 30pt; font-weight: bold; color: #007acc; letter-spacing: 2pt; }
  .cover-sub { font-size: 16pt; color: #222; margin-top: 12pt; }
  .cover-tag { font-size: 12pt; color: #555; margin-top: 24pt; }
  .cover-meta { font-size: 10.5pt; color: #777; margin-top: 48pt; line-height: 2; }
  h1 { font-size: 18pt; color: #007acc; margin-top: 24pt; border-bottom: 2pt solid #007acc; padding-bottom: 6pt; }
  h2 { font-size: 13pt; color: #111827; margin-top: 16pt; }
  p { margin: 6pt 0; text-align: justify; }
  ul, ol { margin: 6pt 0 6pt 20pt; }
  li { margin-bottom: 4pt; }
  table { width: 100%; border-collapse: collapse; margin: 10pt 0; font-size: 10.5pt; }
  th { background: #eef6ff; color: #111827; font-weight: bold; border: 1pt solid #cbd5e1; padding: 6pt 8pt; text-align: left; }
  td { border: 1pt solid #cbd5e1; padding: 6pt 8pt; vertical-align: top; }
  .callout { background: #f0f7ff; border-left: 4pt solid #007acc; padding: 10pt 14pt; margin: 10pt 0; }
  .green { background: #f0fdf4; border-left-color: #16a34a; }
  .footer { text-align: center; color: #888; font-size: 9.5pt; margin-top: 36pt; border-top: 1pt solid #eee; padding-top: 12pt; }
  .page-break { page-break-before: always; }
  code { font-family: Consolas, monospace; background: #f3f4f6; padding: 1pt 3pt; }
</style>
</head>
<body>

<div class="cover">
  <p class="cover-logo">DocMate 闪闪文档</p>
  <p class="cover-sub">AI 文稿修改助手产品介绍</p>
  <p class="cover-tag">人机协同 · 可控改稿 · 自我进化 · 本地便携</p>
  <p class="cover-meta">
    产品版本：${version}<br>
    发布包：${publishName}<br>
    文档版本：V1.0（对外首发版）<br>
    发布日期：${docDate}<br>
    适用对象：客户交流、产品演示、试点推广、内部培训
  </p>
</div>

<h1>1. 产品一句话</h1>
<p>
  <b>DocMate 闪闪文档</b>是一款面向 Windows 桌面的 AI 文稿修改助手。用户在编辑器中写作或粘贴文稿，
  通过自然语言告诉「闪闪」要如何修改，系统生成可对比的修改建议，由用户确认后再写入正文。
</p>
<div class="callout">
  <b>核心定位：</b>DocMate 不是替用户“自动改完”的黑盒工具，而是一个人机协同的改稿工作台。AI 负责理解意图、定位文本、生成建议；用户负责判断、采纳与定稿。
</div>

<h1>2. 为什么需要 DocMate</h1>
<table>
  <tr><th width="26%">常见痛点</th><th>DocMate 的解决方式</th></tr>
  <tr><td>长文档改稿定位慢</td><td>支持选区操作，也支持直接说“第二段改正式”“删除结尾”等自然语言指令。</td></tr>
  <tr><td>AI 改稿不可控</td><td>所有修改先展示红删绿增 Diff，用户明确采纳后才落稿。</td></tr>
  <tr><td>表达风格难统一</td><td>可结合知识库、术语和个人偏好，让输出逐步贴近组织语言和个人习惯。</td></tr>
  <tr><td>口述内容难成文</td><td>支持语音输入与口语转正式表达，快速把想法整理成可编辑文稿。</td></tr>
  <tr><td>部署和数据管理复杂</td><td>Windows 便携包交付，本地工作区保存文稿，模型接口和 Key 在应用内配置。</td></tr>
</table>

<h1>3. 人机协同工作流</h1>
<ol>
  <li><b>用户提出意图：</b>选中文本后用 Bubble 操作条，或在右侧闪闪面板直接输入指令。</li>
  <li><b>AI 分析与生成：</b>闪闪根据全文、选区、历史对话、知识库和偏好生成修改建议。</li>
  <li><b>系统展示 Diff：</b>编辑器内同步显示红删绿增，用户清楚看到每一处变化。</li>
  <li><b>用户决策落稿：</b>用户可采纳、拒绝、重新生成或继续追问，最终结果由人确认。</li>
</ol>
<div class="callout green">
  <b>产品原则：</b>AI 提效，人来把关。任何影响正文的修改都必须经过用户确认，确保效率提升与结果可控同时成立。
</div>

<h1>4. 自我进化能力</h1>
<p>
  DocMate 内置偏好学习机制。用户在日常使用中采纳或拒绝 AI 修改后，系统可以在本地记录可控的交互信号，
  总结用户偏好的表达方式、常用术语、避免用词和常见修改指令，让后续建议更贴近用户的真实写作习惯。
</p>
<table>
  <tr><th width="24%">能力</th><th>说明</th><th width="24%">价值</th></tr>
  <tr><td>偏好学习</td><td>根据采纳、拒绝和常用指令总结写作倾向。</td><td>越用越懂用户。</td></tr>
  <tr><td>知识库参考</td><td>导入制度、模板、术语和参考材料，生成时检索相关内容。</td><td>输出更贴近组织语境。</td></tr>
  <tr><td>任务级偏好注入</td><td>不同任务只注入相关偏好，例如风险扫描更关注合规敏感度。</td><td>减少无关偏好干扰。</td></tr>
  <tr><td>可控隐私设置</td><td>用户可关闭自动学习，或限制保存示例和保留条数。</td><td>兼顾进化能力与数据边界。</td></tr>
</table>

<div class="page-break"></div>

<h1>5. 核心功能</h1>
<h2>5.1 闪闪聊天改稿</h2>
<p>右侧闪闪面板支持连续对话式改稿。用户可以要求润色、精简、正式化、补充、删除、总结、问答或风险检查。</p>

<h2>5.2 选区 Bubble 快捷操作</h2>
<p>选中文本后自动出现轻量操作条，支持正式、精简、润色、风险等快捷动作，也可直接输入自然语言指令。</p>

<h2>5.3 Diff 预览与确认</h2>
<p>AI 修改不会直接覆盖原文。系统用红删绿增方式展示变化，用户按 Ctrl+Enter 采纳，或按 Esc 拒绝。</p>

<h2>5.4 语音输入</h2>
<p>支持在线优先语音识别，也可回退本地模型。用户可以口述修改要求或草稿内容，再由闪闪整理为正式表达。</p>

<h2>5.5 知识库与偏好</h2>
<p>用户可导入模板、制度、参考资料，配合偏好学习形成个人和组织的写作上下文。</p>

<h1>6. 典型应用场景</h1>
<table>
  <tr><th width="24%">场景</th><th>典型指令</th><th width="28%">输出价值</th></tr>
  <tr><td>汇报材料润色</td><td>“把第二段改得更正式、更有层次”</td><td>提升表达质量，保留原意。</td></tr>
  <tr><td>制度通知审校</td><td>“检查是否有风险或歧义”</td><td>提前发现敏感表述和不清晰条款。</td></tr>
  <tr><td>会议口述整理</td><td>“把这段口语整理成正式通知”</td><td>快速从口述转为可用文稿。</td></tr>
  <tr><td>长文档局部修改</td><td>“删除结尾重复内容”“第三段精简一半”</td><td>减少手动定位和复制粘贴。</td></tr>
  <tr><td>组织风格统一</td><td>“参考知识库模板改写这段”</td><td>对齐术语、格式和表达习惯。</td></tr>
</table>

<h1>7. 安全与交付</h1>
<ul>
  <li><b>本地工作区：</b>文稿默认保存在本机工作区，便于用户掌控和迁移。</li>
  <li><b>主进程调用模型：</b>API Key 在 Electron 主进程侧使用，不暴露给前端页面。</li>
  <li><b>便携交付：</b>交付包为 <code>${publishName}/DocMate.vbs</code>，双击即可启动。</li>
  <li><b>单任务执行：</b>同一时间只允许一个 AI 任务运行，避免并发改稿造成上下文混乱。</li>
  <li><b>用户确认：</b>所有写入正文的修改都需要用户确认，不做无提示自动覆盖。</li>
</ul>

<h1>8. 快速上手</h1>
<ol>
  <li>双击 <code>${publishName}/DocMate.vbs</code> 启动 DocMate。</li>
  <li>在模型配置中填写 API 地址、API Key 和模型名称。</li>
  <li>粘贴或导入一篇文稿。</li>
  <li>选中文字使用 Bubble 快捷操作，或在右侧闪闪面板输入修改指令。</li>
  <li>查看 Diff，确认无误后采纳修改。</li>
</ol>

<p class="footer">
  DocMate 闪闪文档 · 产品介绍 V1.0 · ${version} · ${publishName}<br>
  人机协同的 AI 文稿修改助手，让每一次改稿可见、可控、可进化。
</p>

</body>
</html>`

fs.mkdirSync(desktop, { recursive: true })
fs.writeFileSync(outPath, `\ufeff${html}`, 'utf8')
console.log(`已生成: ${outPath}`)
