# 文稿修改助手 — 项目完整开发文档

> 本文档面向开发者/AI智能体，包含项目的全部需求、架构设计、交互流程、技术选型、完整代码及后续开发路线图。阅读本文档后可直接进入开发。

---

## 一、项目概述

### 1.1 项目名称
文稿修改助手（暂定名）

### 1.2 项目定位
基于"人机协同工具，界面越简单越好"的理念，打造一款**语音驱动的文稿修改软件**。用户粘贴文字后，通过语音或文字向 AI 下达修改指令，AI 输出修改建议，用户确认后一键替换。

### 1.3 核心理念
- **界面极简**：像一个写字板，没有多余按钮
- **语音优先**：说话就能改，不用打字
- **人机协同**：AI 只提建议，人来拍板
- **手动自由**：随时可以手动编辑，和 AI 修改互不干扰

### 1.4 目标用户
- 机关/企业中需要频繁修改文稿的工作人员
- 特别是建筑行业（中国建筑国际集团）的公文、方案、报告撰写者
- 习惯口述指令、不擅长逐字打字修改的用户

---

## 二、完整交互流程

```
用户操作流程：

1. 粘贴/输入文稿
   └→ 极简编辑器，像写字板一样

2. 下达修改指令（三种方式）
   ├→ 语音：点麦克风，说"第一段太啰嗦，精简一下"
   ├→ 文字：在右侧浮窗输入"把第一段改得更正式一些"
   └→ 选中：在编辑器选中文字，点"AI改这段"

3. AI 处理
   └→ 定位段落 → 理解意图 → 生成修改文

4. 展示修改对比（Diff 视图）
   ├→ 红色删除线 = 旧文
   └→ 绿色 = 新文

5. 用户决策
   ├→ 采纳替换 → 自动替换到编辑器
   ├→ 拒绝 → 跳过，原文不变
   └→ 重说 → 重新下达指令

6. 随时可手动编辑
   └→ 光标定位直接改，和 AI 修改互不干扰
```

---

## 三、技术选型与架构

### 3.1 技术栈

| 层 | 技术 | 选型理由 |
|----|------|---------|
| **编辑器** | Tiptap（基于 ProseMirror） | MIT 开源，UI 完全自定义，自定义 Node/Mark 机制适合魔改，TypeScript 现代架构 |
| **语音识别** | Web Speech API | 浏览器原生，零依赖，Chrome 支持中文，开发阶段够用 |
| **大模型** | 豆包 API / 任意 OpenAI 兼容 API | 中国大陆可直连，中文能力强，价格合理 |
| **前端框架** | Vue 3 + TypeScript（推荐）或 React | Tiptap 对两者都有官方适配 |
| **后端** | Node.js / Python FastAPI | 用于代理 LLM API 调用，避免前端暴露 API Key |
| **部署** | 腾讯云 Linux 服务器 | 用户团队已有腾讯云资源 |

### 3.2 为什么选 Tiptap 而不是 OnlyOffice / Etherpad

| 维度 | Tiptap | OnlyOffice | Etherpad |
|------|--------|-----------|----------|
| UI 自由度 | ★★★★★ | ★★★☆☆ | ★★★☆☆ |
| 代码可读性 | ★★★★★ | ★★☆☆☆ | ★★★☆☆ |
| 魔改友好度 | ★★★★★ | ★★☆☆☆ | ★★★☆☆ |
| 富文本支持 | ★★★★☆ | ★★★★★ | ★★☆☆☆ |
| 协同编辑 | ★★☆☆☆(需额外方案) | ★★★★★ | ★★★★★ |
| 开源协议 | MIT | AGPL v3 | Apache 2.0 |
| 体积 | 轻量 | 995MB | 中等 |

**结论**：本项目核心是"极简界面 + 深度定制"，Tiptap 完全契合。协同编辑可后续通过 Y.js 补充。

### 3.3 系统架构

```
┌─────────────────────────────────────────────────┐
│                   浏览器前端                      │
│                                                  │
│  ┌──────────────────┐  ┌──────────────────────┐  │
│  │   Tiptap 编辑器   │  │   AI 浮窗面板        │  │
│  │   (纯文本/富文本) │  │   - 语音输入         │  │
│  │   - 文字编辑      │  │   - 指令文字输入      │  │
│  │   - 选中高亮      │  │   - Diff 对比展示    │  │
│  │   - 手动修改      │  │   - 采纳/拒绝按钮    │  │
│  └──────────────────┘  └──────────────────────┘  │
│           │                      │               │
│           │    修改指令 + 选中文本  │               │
│           └──────────┬───────────┘               │
│                      ▼                           │
│            ┌──────────────────┐                  │
│            │   指令解析模块    │                  │
│            │   - 段落定位      │                  │
│            │   - 意图识别      │                  │
│            └────────┬─────────┘                  │
│                     │                            │
└─────────────────────┼────────────────────────────┘
                      │ HTTP API
                      ▼
┌──────────────────────────────────────────────────┐
│               后端 API 服务                       │
│                                                   │
│  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  API 代理     │  │  Prompt 构造模块           │ │
│  │  - 鉴权       │  │  - 注入全文上下文          │ │
│  │  - 限流       │  │  - 注入选中文本            │ │
│  │  - 日志       │  │  - 注入修改指令            │ │
│  └──────┬───────┘  └──────────┬─────────────────┘ │
│         │                      │                  │
│         └──────────┬───────────┘                  │
│                    ▼                              │
│         ┌────────────────────┐                   │
│         │  豆包/大模型 API     │                   │
│         │  (OpenAI 兼容格式)   │                   │
│         └────────────────────┘                   │
└──────────────────────────────────────────────────┘
```

---

## 四、界面设计规范

### 4.1 整体布局

```
┌──────────────────────────────────────────────────────────────┐
│  文稿修改助手                                    人机协同·语音优先 │
├──────────────────────────────────────────┬───────────────────┤
│  ↶ ↷ │ B I │ ✨AI改这段                │  ● AI助手    就绪  │
├──────────────────────────────────────────┤                   │
│                                          │                   │
│                                          │  [对话消息区域]    │
│          编辑区域                         │                   │
│    (极简写字板风格)                       │  ┌─────────────┐ │
│                                          │  │ 红色删除线旧文│ │
│    - 粘贴文字进来                         │  │ 绿色新文预览  │ │
│    - 随时手动改                           │  ├─────────────┤ │
│    - 选中文字可触发AI                     │  │ 采纳 │ 拒绝  │ │
│                                          │  └─────────────┘ │
│                                          │                   │
│                                          ├───────────────────┤
│                                          │ [输入框] 🎤 📤   │
└──────────────────────────────────────────┴───────────────────┘
```

### 4.2 设计原则

1. **编辑区占 70% 宽度**，AI 面板占 30%（380px），可折叠
2. **编辑区工具栏极简**：只有撤销/重做/加粗/斜体 + "AI改这段"按钮
3. **AI 面板**：聊天气泡风格，用户消息右对齐蓝色，AI 消息左对齐灰色
4. **Diff 展示**：红色删除线旧文 + 绿色新文，上下排列
5. **语音按钮**：麦克风图标，录音时变红+脉冲动画
6. **配色**：白色主背景，蓝色强调色，文字深灰，边框极淡

### 4.3 交互细节

| 交互 | 行为 |
|------|------|
| 点击麦克风 | 开始录音，按钮变红脉冲，状态显示"正在听..." |
| 录音结束 | 自动将语音转文字填入输入框，自动发送 |
| 输入框按回车 | 发送修改指令 |
| 选中文字 + 点"AI改这段" | 自动打开 AI 面板，以选中文本为修改目标 |
| Ctrl+M | 快捷键：打开 AI 面板并聚焦输入框 |
| 点击"采纳替换" | AI 建议文本替换到编辑器对应段落，Diff 区变灰+显示"已替换" |
| 点击"拒绝" | 跳过，Diff 区显示"已跳过" |
| 直接在编辑器打字 | 正常编辑，和 AI 修改完全独立 |

---

## 五、大模型对接方案

### 5.1 Prompt 设计（核心）

这是整个系统最关键的部分——如何构造 Prompt 让大模型精准输出修改建议。

```
System Prompt:

你是一个专业的中文文稿修改助手。用户会给你一段文稿和一条修改指令。
你需要：
1. 找到需要修改的文本片段
2. 按照修改指令生成修改后的文本
3. 严格按照 JSON 格式输出

输出格式（严格遵守）：
{
  "old_text": "需要被替换的原文（必须与原文完全一致）",
  "new_text": "修改后的新文本",
  "reason": "简要说明修改理由（一句话）"
}

注意：
- old_text 必须与原文逐字一致，包括标点符号
- new_text 应该自然衔接上下文
- 只输出 JSON，不要输出其他内容
```

```
User Prompt:

以下是文稿全文：
---
{document_full_text}
---

{selected_text ? `用户选中的文本：\n---\n${selected_text}\n---` : ''}

修改指令：{user_command}

请按照修改指令，输出修改建议的 JSON。
```

### 5.2 API 调用示例（后端）

```python
# Python FastAPI 后端示例
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI()

class RevisionRequest(BaseModel):
    document_text: str       # 文稿全文
    selected_text: str = "" # 选中的文本（可选）
    command: str             # 修改指令

class RevisionResponse(BaseModel):
    old_text: str
    new_text: str
    reason: str

DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DOUBAO_API_KEY = "your-api-key-here"  # 从环境变量读取
DOUBAO_MODEL = "doubao-pro-32k"       # 或其他模型

SYSTEM_PROMPT = """你是一个专业的中文文稿修改助手。用户会给你一段文稿和一条修改指令。
你需要：
1. 找到需要修改的文本片段
2. 按照修改指令生成修改后的文本
3. 严格按照 JSON 格式输出

输出格式（严格遵守）：
{
  "old_text": "需要被替换的原文（必须与原文完全一致）",
  "new_text": "修改后的新文本",
  "reason": "简要说明修改理由（一句话）"
}

注意：
- old_text 必须与原文逐字一致，包括标点符号
- new_text 应该自然衔接上下文
- 只输出 JSON，不要输出其他内容"""

@app.post("/api/revise", response_model=RevisionResponse)
async def revise_text(req: RevisionRequest):
    user_content = f"以下是文稿全文：\n---\n{req.document_text}\n---\n"
    if req.selected_text:
        user_content += f"用户选中的文本：\n---\n{req.selected_text}\n---\n"
    user_content += f"修改指令：{req.command}\n\n请按照修改指令，输出修改建议的 JSON。"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DOUBAO_API_URL,
            headers={
                "Authorization": f"Bearer {DOUBAO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DOUBAO_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            },
            timeout=30.0
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="LLM API 调用失败")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    import json
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM 返回格式异常")

    return RevisionResponse(
        old_text=result["old_text"],
        new_text=result["new_text"],
        reason=result.get("reason", "")
    )
```

### 5.3 前端调用后端 API

```typescript
// 替换 Demo 中的 simulateRevision 函数
async function callRevisionAPI(
  documentText: string,
  selectedText: string,
  command: string
): Promise<{ old_text: string; new_text: string; reason: string }> {
  const response = await fetch('/api/revise', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_text: documentText,
      selected_text: selectedText,
      command: command
    })
  });

  if (!response.ok) {
    throw new Error(`API 错误: ${response.status}`);
  }

  return await response.json();
}
```

---

## 六、项目目录结构（推荐）

```
doc-editor/
├── package.json
├── tsconfig.json
├── vite.config.ts
├── index.html
├── public/
│   └── favicon.ico
├── src/
│   ├── main.ts                    # 入口
│   ├── App.vue                    # 根组件
│   ├── components/
│   │   ├── EditorPanel.vue        # 左侧编辑器面板
│   │   ├── AiPanel.vue           # 右侧 AI 浮窗
│   │   ├── DiffView.vue          # 修改对比组件
│   │   ├── VoiceInput.vue        # 语音输入组件
│   │   └── ToolBar.vue           # 极简工具栏
│   ├── composables/
│   │   ├── useEditor.ts           # Tiptap 编辑器封装
│   │   ├── useVoice.ts            # 语音识别封装
│   │   ├── useAiRevision.ts      # AI 修改逻辑封装
│   │   └── useDiff.ts            # Diff 对比逻辑
│   ├── extensions/
│   │   ├── RevisionMark.ts        # 自定义 Tiptap 扩展：修改标记
│   │   └── CommentMark.ts        # 自定义 Tiptap 扩展：批注标记
│   ├── api/
│   │   └── revision.ts            # 后端 API 调用
│   ├── types/
│   │   └── index.ts               # TypeScript 类型定义
│   └── styles/
│       └── main.css               # 全局样式
├── server/
│   ├── main.py                    # FastAPI 后端入口
│   ├── requirements.txt
│   ├── config.py                  # 配置（API Key 从环境变量读取）
│   └── api/
│       └── revise.py              # 修改接口
└── docker-compose.yml             # 部署配置
```

---

## 七、Tiptap 编辑器集成方案

### 7.1 安装依赖

```bash
npm install @tiptap/vue-3 @tiptap/starter-kit @tiptap/extension-placeholder
```

### 7.2 基础编辑器组件

```vue
<!-- src/components/EditorPanel.vue -->
<template>
  <div class="editor-wrap">
    <div class="editor-toolbar">
      <button @click="editor.chain().focus().undo().run()" title="撤销">
        <i class="fas fa-undo"></i>
      </button>
      <button @click="editor.chain().focus().redo().run()" title="重做">
        <i class="fas fa-redo"></i>
      </button>
      <div class="toolbar-sep"></div>
      <button
        @click="editor.chain().focus().toggleBold().run()"
        :class="{ active: editor.isActive('bold') }"
        title="加粗"
      >
        <i class="fas fa-bold"></i>
      </button>
      <button
        @click="editor.chain().focus().toggleItalic().run()"
        :class="{ active: editor.isActive('italic') }"
        title="斜体"
      >
        <i class="fas fa-italic"></i>
      </button>
      <div class="toolbar-sep"></div>
      <button class="ai-selection-btn" @click="handleAiSelection">
        <i class="fas fa-wand-magic-sparkles"></i> AI改这段
      </button>
    </div>
    <div class="editor-body">
      <EditorContent :editor="editor" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'

const emit = defineEmits<{
  (e: 'ai-selection', text: string): void
}>()

const editor = useEditor({
  extensions: [
    StarterKit,
    Placeholder.configure({
      placeholder: '在此粘贴或输入文稿...',
    }),
  ],
  content: '',
  editorProps: {
    attributes: {
      class: 'prose-editor',
    },
  },
})

function handleAiSelection() {
  const { from, to } = editor.value.state.selection
  const selectedText = editor.value.state.doc.textBetween(from, to, '\n')
  if (selectedText.trim()) {
    emit('ai-selection', selectedText)
  }
}

// 暴露方法给父组件
defineExpose({
  getFullText: () => editor.value.getText(),
  replaceText: (oldText: string, newText: string) => {
    // 在文档中查找并替换
    const { state } = editor.value
    const docText = state.doc.textContent
    const index = docText.indexOf(oldText)
    if (index !== -1) {
      // 计算 ProseMirror 位置
      let pos = 0
      let found = false
      state.doc.descendants((node, nodePos) => {
        if (found) return false
        if (node.isText && node.text) {
          const textIndex = node.text.indexOf(oldText)
          if (textIndex !== -1) {
            pos = nodePos + textIndex
            found = true
            return false
          }
        }
      })
      if (found) {
        editor.value.chain().focus()
          .setTextSelection({ from: pos, to: pos + oldText.length })
          .insertContent(newText)
          .run()
      }
    }
  }
})
</script>

<style scoped>
.prose-editor {
  outline: none;
  font-size: 15px;
  line-height: 1.9;
  min-height: 100%;
}
.prose-editor p {
  margin-bottom: 0.8em;
}
.prose-editor ::selection {
  background: rgba(37, 99, 235, 0.15);
}
/* ... 其他样式与 Demo 一致 ... */
</style>
```

### 7.3 自定义 Tiptap 扩展：修改标记

```typescript
// src/extensions/RevisionMark.ts
import { Mark, markInputRule, markPasteRule } from '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    revisionMark: {
      setRevisionMark: () => ReturnType
      toggleRevisionMark: () => ReturnType
      unsetRevisionMark: () => ReturnType
    }
  }
}

export const RevisionMark = Mark.create({
  name: 'revisionMark',

  parseHTML() {
    return [{ tag: 'span[data-revision]' }]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      {
        ...HTMLAttributes,
        'data-revision': '',
        style: 'background-color: #fef2f2; text-decoration: line-through; color: #dc2626;',
      },
    ]
  },

  addCommands() {
    return {
      setRevisionMark:
        () =>
        ({ commands }) => {
          return commands.setMark(this.name)
        },
      toggleRevisionMark:
        () =>
        ({ commands }) => {
          return commands.toggleMark(this.name)
        },
      unsetRevisionMark:
        () =>
        ({ commands }) => {
          return commands.unsetMark(this.name)
        },
    }
  },
})
```

---

## 八、语音识别模块

### 8.1 Web Speech API 封装

```typescript
// src/composables/useVoice.ts
import { ref } from 'vue'

interface VoiceOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  onResult?: (transcript: string, isFinal: boolean) => void
  onEnd?: (finalTranscript: string) => void
  onError?: (error: string) => void
}

export function useVoice(options: VoiceOptions = {}) {
  const isRecording = ref(false)
  const transcript = ref('')
  let recognition: SpeechRecognition | null = null

  const {
    lang = 'zh-CN',
    continuous = false,
    interimResults = true,
    onResult,
    onEnd,
    onError,
  } = options

  function start() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      onError?.('浏览器不支持语音识别，请使用 Chrome')
      return
    }

    recognition = new SpeechRecognition()
    recognition.lang = lang
    recognition.continuous = continuous
    recognition.interimResults = interimResults

    recognition.onstart = () => {
      isRecording.value = true
    }

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let result = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        result += event.results[i][0].transcript
      }
      transcript.value = result
      onResult?.(result, event.results[event.results.length - 1].isFinal)
    }

    recognition.onend = () => {
      isRecording.value = false
      onEnd?.(transcript.value)
    }

    recognition.onerror = (event) => {
      isRecording.value = false
      onError?.(event.error)
    }

    recognition.start()
  }

  function stop() {
    if (recognition) {
      recognition.stop()
      recognition = null
    }
    isRecording.value = false
  }

  function toggle() {
    if (isRecording.value) {
      stop()
    } else {
      start()
    }
  }

  return {
    isRecording,
    transcript,
    start,
    stop,
    toggle,
  }
}
```

### 8.2 生产环境替代方案

Web Speech API 在以下场景有局限：
- 仅 Chrome 支持，Firefox/Safari 不稳定
- 需要联网（Chrome 版本走 Google 服务器）
- 中国大陆可能需要翻墙

**生产环境推荐替换为：**

| 方案 | 延迟 | 离线 | 中文效果 | 费用 |
|------|------|------|---------|------|
| 讯飞 WebAPI | 低 | 否 | ★★★★★ | 按量计费 |
| 腾讯云 ASR | 低 | 否 | ★★★★☆ | 按量计费 |
| 浏览器 Web Speech | 中 | 否 | ★★★☆☆ | 免费 |
| Whisper (自部署) | 中 | 是 | ★★★★☆ | GPU 成本 |

---

## 九、完整 Demo 源码

> 以下是一个 **可直接在浏览器运行的单文件 Demo**，包含全部交互逻辑。AI 修改部分是模拟的，替换为真实 API 调用即可上线。

### 9.1 单文件 HTML Demo

文件名：`index.html`，直接双击打开即可运行。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>文稿修改助手</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #f8f8f6;
  --surface: #ffffff;
  --text: #1a1a1a;
  --text2: #666;
  --text3: #999;
  --border: #e8e8e4;
  --accent: #2563eb;
  --accent-light: #eff6ff;
  --red: #dc2626;
  --red-light: #fef2f2;
  --green: #16a34a;
  --green-light: #f0fdf4;
}
body { font-family: -apple-system, "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; display: flex; flex-direction: column; }

/* Top bar - minimal */
.topbar { height: 48px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 24px; flex-shrink: 0; }
.topbar h1 { font-size: 15px; font-weight: 500; color: var(--text); }
.topbar span { font-size: 12px; color: var(--text3); margin-left: 12px; }

/* Main layout */
.main { display: flex; flex: 1; overflow: hidden; }

/* Editor area */
.editor-wrap { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.editor-toolbar { height: 40px; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 4px; }
.toolbar-btn { width: 32px; height: 32px; border: none; background: none; border-radius: 6px; cursor: pointer; color: var(--text2); font-size: 13px; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
.toolbar-btn:hover { background: var(--bg); color: var(--text); }
.toolbar-btn.active { background: var(--accent-light); color: var(--accent); }
.toolbar-sep { width: 1px; height: 20px; background: var(--border); margin: 0 4px; }

.editor-body { flex: 1; overflow-y: auto; padding: 32px 48px; }
#editor { min-height: 100%; outline: none; font-size: 15px; line-height: 1.9; color: var(--text); caret-color: var(--accent); }
#editor:empty::before { content: "在此粘贴或输入文稿..."; color: var(--text3); pointer-events: none; }
#editor p { margin-bottom: 0.8em; }
#editor ::selection { background: rgba(37,99,235,0.15); }

/* AI Panel */
.ai-panel { width: 380px; background: var(--surface); border-left: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; transition: margin-right 0.3s; }
.ai-panel.collapsed { margin-right: -380px; }
.ai-header { height: 48px; border-bottom: 1px solid var(--border); display: flex; align-items: center; padding: 0 16px; gap: 8px; }
.ai-header .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); }
.ai-header span { font-size: 14px; font-weight: 500; }
.ai-status { font-size: 12px; color: var(--text3); margin-left: auto; }

.ai-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.ai-msg { max-width: 90%; padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.6; word-break: break-word; }
.ai-msg.user { background: var(--accent-light); color: var(--accent); align-self: flex-end; border-bottom-right-radius: 4px; }
.ai-msg.assistant { background: var(--bg); color: var(--text); align-self: flex-start; border-bottom-left-radius: 4px; }
.ai-msg .label { font-size: 11px; color: var(--text3); margin-bottom: 4px; }

/* Diff view */
.diff-box { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; margin-top: 4px; }
.diff-old { padding: 10px 14px; background: var(--red-light); font-size: 13px; line-height: 1.6; color: var(--red); text-decoration: line-through; }
.diff-new { padding: 10px 14px; background: var(--green-light); font-size: 13px; line-height: 1.6; color: var(--green); }

/* Accept/Reject buttons */
.action-row { display: flex; gap: 8px; margin-top: 4px; }
.btn-accept, .btn-reject { flex: 1; padding: 8px 0; border: none; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.15s; }
.btn-accept { background: var(--green); color: white; }
.btn-accept:hover { background: #15803d; }
.btn-reject { background: var(--bg); color: var(--text2); border: 1px solid var(--border); }
.btn-reject:hover { background: #eee; }

/* Voice input area */
.ai-input-area { padding: 12px 16px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 8px; }
.ai-input { flex: 1; padding: 8px 14px; border: 1px solid var(--border); border-radius: 20px; font-size: 13px; outline: none; transition: border-color 0.15s; }
.ai-input:focus { border-color: var(--accent); }
.ai-input::placeholder { color: var(--text3); }
.voice-btn { width: 36px; height: 36px; border-radius: 50%; border: none; background: var(--accent); color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; transition: all 0.15s; flex-shrink: 0; }
.voice-btn:hover { background: #1d4ed8; }
.voice-btn.recording { background: var(--red); animation: pulse 1s infinite; }
.send-btn { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--border); background: var(--surface); color: var(--text2); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 13px; transition: all 0.15s; flex-shrink: 0; }
.send-btn:hover { background: var(--accent-light); color: var(--accent); border-color: var(--accent); }

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.1); }
}

/* Toggle button */
.panel-toggle { position: absolute; right: 380px; top: 56px; width: 28px; height: 28px; border: 1px solid var(--border); border-right: none; border-radius: 6px 0 0 6px; background: var(--surface); cursor: pointer; display: flex; align-items: center; justify-content: center; color: var(--text3); font-size: 12px; z-index: 10; transition: right 0.3s; }
.panel-toggle.collapsed { right: 0; }

/* Toast */
.toast { position: fixed; top: 64px; left: 50%; transform: translateX(-50%); padding: 8px 20px; border-radius: 8px; font-size: 13px; color: white; z-index: 100; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
.toast.show { opacity: 1; }
.toast.success { background: var(--green); }
.toast.info { background: var(--accent); }

/* Responsive */
@media (max-width: 800px) {
  .ai-panel { position: absolute; right: 0; top: 48px; bottom: 0; z-index: 20; box-shadow: -4px 0 20px rgba(0,0,0,0.08); }
  .editor-body { padding: 20px; }
}
</style>
</head>
<body>

<div class="topbar">
  <h1>文稿修改助手</h1>
  <span>人机协同 · 语音优先</span>
</div>

<div class="main" style="position: relative;">
  <div class="editor-wrap">
    <div class="editor-toolbar">
      <button class="toolbar-btn" title="撤销" onclick="document.execCommand('undo')"><i class="fas fa-undo"></i></button>
      <button class="toolbar-btn" title="重做" onclick="document.execCommand('redo')"><i class="fas fa-redo"></i></button>
      <div class="toolbar-sep"></div>
      <button class="toolbar-btn" title="加粗" onclick="document.execCommand('bold')"><i class="fas fa-bold"></i></button>
      <button class="toolbar-btn" title="斜体" onclick="document.execCommand('italic')"><i class="fas fa-italic"></i></button>
      <div class="toolbar-sep"></div>
      <button class="toolbar-btn" title="选中文字后点此，发送给AI修改" id="btn-ai-selection" style="color:var(--accent);font-size:12px;width:auto;padding:0 10px;gap:4px;display:flex;align-items:center;"><i class="fas fa-wand-magic-sparkles"></i> AI改这段</button>
    </div>
    <div class="editor-body">
      <div id="editor" contenteditable="true" spellcheck="false"></div>
    </div>
  </div>

  <button class="panel-toggle" id="panelToggle" onclick="togglePanel()"><i class="fas fa-chevron-right"></i></button>

  <div class="ai-panel" id="aiPanel">
    <div class="ai-header">
      <div class="dot"></div>
      <span>AI 助手</span>
      <span class="ai-status" id="aiStatus">就绪</span>
    </div>
    <div class="ai-body" id="aiChat">
      <div class="ai-msg assistant">
        <div class="label">AI 助手</div>
        你好！我可以帮你修改文稿。你可以：<br><br>
        1. <b>语音</b>说出修改要求（点麦克风按钮）<br>
        2. <b>文字</b>输入修改指令<br>
        3. <b>选中文字</b>后点击"AI改这段"<br><br>
        例如："把第一段改得更正式一些"或"最后一段结尾太突然，加个总结"
      </div>
    </div>
    <div class="ai-input-area">
      <input class="ai-input" id="aiInput" placeholder="输入修改指令，或点麦克风语音说..." onkeydown="if(event.key==='Enter')sendCommand()">
      <button class="voice-btn" id="voiceBtn" onclick="toggleVoice()" title="语音输入"><i class="fas fa-microphone"></i></button>
      <button class="send-btn" onclick="sendCommand()" title="发送"><i class="fas fa-paper-plane"></i></button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const editor = document.getElementById('editor');
const aiChat = document.getElementById('aiChat');
const aiInput = document.getElementById('aiInput');
const voiceBtn = document.getElementById('voiceBtn');
const aiStatus = document.getElementById('aiStatus');
const panelToggle = document.getElementById('panelToggle');
const aiPanel = document.getElementById('aiPanel');

// Demo text
editor.innerHTML = `<p>关于推进中国建筑国际集团数字化转型的工作方案</p>
<p>为深入贯彻落实集团高质量发展战略部署，加快推进中国建筑国际集团数字化转型工作，提升企业核心竞争力和可持续发展能力，特制定本工作方案。</p>
<p>一、总体目标。以"数字中建"建设为引领，到2028年基本建成覆盖全业务链条的数字化管理体系，实现项目全生命周期数字化管理覆盖率达到90%以上，数据驱动决策能力显著提升。</p>
<p>二、重点任务。一是建设统一数据平台，打通各业务系统数据孤岛；二是推进智慧工地建设，实现施工过程全面感知与智能管控；三是构建数字化供应链，提升采购与物流协同效率；四是打造数字孪生平台，实现重点项目全要素数字化映射。</p>
<p>三、保障措施。加强组织领导，成立数字化转型工作领导小组；加大资金投入，确保年度数字化转型专项预算不低于营收的1.5%；强化人才保障，每年引进和培养数字化专业人才不少于200人；完善考核机制，将数字化转型成效纳入各二级单位绩效考核体系。</p>`;

let isRecording = false;
let recognition = null;
let pendingDiff = null;

function togglePanel() {
  aiPanel.classList.toggle('collapsed');
  panelToggle.classList.toggle('collapsed');
  const icon = panelToggle.querySelector('i');
  icon.className = aiPanel.classList.contains('collapsed')
    ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
}

function toggleVoice() {
  isRecording ? stopVoice() : startVoice();
}

function startVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { showToast('浏览器不支持语音识别，请使用 Chrome', 'info'); return; }
  recognition = new SR();
  recognition.lang = 'zh-CN';
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.onstart = () => {
    isRecording = true;
    voiceBtn.classList.add('recording');
    voiceBtn.innerHTML = '<i class="fas fa-stop"></i>';
    aiStatus.textContent = '正在听...';
  };
  recognition.onresult = (e) => {
    let t = '';
    for (let i = e.resultIndex; i < e.results.length; i++) t += e.results[i][0].transcript;
    aiInput.value = t;
  };
  recognition.onend = () => { stopVoice(); if (aiInput.value.trim()) sendCommand(); };
  recognition.onerror = (e) => { stopVoice(); if (e.error === 'not-allowed') showToast('请允许麦克风权限', 'info'); };
  recognition.start();
}

function stopVoice() {
  isRecording = false;
  voiceBtn.classList.remove('recording');
  voiceBtn.innerHTML = '<i class="fas fa-microphone"></i>';
  aiStatus.textContent = '就绪';
  if (recognition) recognition.stop();
}

function sendCommand() {
  const text = aiInput.value.trim();
  if (!text) return;
  aiInput.value = '';
  addMessage('user', text);
  const sel = window.getSelection();
  processAICommand(text, sel.toString().trim());
}

document.getElementById('btn-ai-selection').addEventListener('click', () => {
  const selectedText = window.getSelection().toString().trim();
  if (!selectedText) { showToast('请先在编辑器中选中要修改的文字', 'info'); return; }
  aiInput.value = '修改这段文字';
  if (aiPanel.classList.contains('collapsed')) togglePanel();
  sendCommand();
});

// ===== AI 处理 =====
// 注意：此处是模拟实现。生产环境需替换为后端 API 调用。
// 替换方法：将 simulateRevision() 替换为 fetch('/api/revise', {...})
function processAICommand(command, selectedText) {
  aiStatus.textContent = '思考中...';
  setTimeout(() => {
    aiStatus.textContent = '就绪';
    let oldText, newText;
    if (selectedText) {
      oldText = selectedText;
      newText = simulateRevision(selectedText, command);
    } else {
      const result = findAndRevise(command);
      if (result) { oldText = result.oldText; newText = result.newText; }
      else { addMessage('assistant', '我没有找到要修改的段落。你可以：\n\n1. 选中要修改的文字后再发指令\n2. 明确指出第几段要改什么'); return; }
    }
    pendingDiff = { oldText, newText };
    showDiff(oldText, newText, command);
  }, 800 + Math.random() * 700);
}

// ----- 模拟 AI 修改（生产环境删除此函数，替换为 API 调用）-----
function simulateRevision(original, command) {
  const lower = command.toLowerCase();
  if (lower.includes('正式') || lower.includes('严肃')) {
    return original.replace(/打造/g,'构建').replace(/搞定/g,'完成').replace(/差不多/g,'基本').replace(/弄/g,'推进').replace(/加大/g,'持续强化').replace(/加强/g,'持续深化').replace(/推进/g,'深入推进').replace(/建设/g,'体系建设').replace(/提升/g,'全面提升').replace(/完善/g,'建立健全').replace(/确保/g,'切实保障');
  }
  if (lower.includes('简洁') || lower.includes('精简') || lower.includes('短')) {
    return original.replace(/，特制定本工作方案.*/,'').replace(/深入贯彻落实/g,'贯彻').replace(/加快推进/g,'推进').replace(/核心竞争力和可持续发展能力/g,'核心竞争力').replace(/全面提升/g,'提升').replace(/持续深化/g,'深化').replace(/持续强化/g,'强化').replace(/深入推进/g,'推进').replace(/建立健全/g,'建立').replace(/切实保障/g,'保障').replace(/数字化管理体系/g,'数字管理体系').replace(/项目全生命周期数字化管理覆盖率达到90%以上/g,'项目数字化管理覆盖率达90%').replace(/数据驱动决策能力显著提升/g,'数据决策能力提升');
  }
  if (lower.includes('总结') || lower.includes('结尾') || lower.includes('收尾')) {
    return original + '总之，数字化转型是集团实现高质量发展的必由之路，各部门要高度重视、扎实推进，确保各项任务按期完成。';
  }
  if (lower.includes('展开') || lower.includes('详细') || lower.includes('具体')) {
    return original.replace(/；/g,'；\n').replace(/一是/g,'第一，').replace(/二是/g,'第二，').replace(/三是/g,'第三，').replace(/四是/g,'第四，');
  }
  return original.replace(/加大/g,'持续加大').replace(/加强/g,'进一步加强').replace(/提升/g,'着力提升');
}

function findAndRevise(command) {
  const paragraphs = editor.querySelectorAll('p');
  const lower = command.toLowerCase();
  let targetIndex = -1;
  const numMatch = command.match(/第([一二三四五六七八九十\d]+)[段部分]/);
  if (numMatch) {
    const numMap = {'一':0,'二':1,'三':2,'四':3,'五':4,'六':5,'七':6,'八':7,'九':8,'十':9};
    const n = numMatch[1];
    targetIndex = numMap[n] !== undefined ? numMap[n] : (parseInt(n) - 1);
  }
  if (lower.includes('标题') || lower.includes('开头')) targetIndex = 0;
  if (lower.includes('目标')) targetIndex = 2;
  if (lower.includes('任务')) targetIndex = 3;
  if (lower.includes('保障') || lower.includes('措施')) targetIndex = 4;
  if (lower.includes('结尾') || lower.includes('最后')) targetIndex = paragraphs.length - 1;
  if (targetIndex >= 0 && targetIndex < paragraphs.length) {
    return { oldText: paragraphs[targetIndex].textContent, newText: simulateRevision(paragraphs[targetIndex].textContent, command) };
  }
  if (paragraphs.length > 0) {
    return { oldText: paragraphs[0].textContent, newText: simulateRevision(paragraphs[0].textContent, command) };
  }
  return null;
}

function showDiff(oldText, newText, command) {
  const msgDiv = document.createElement('div');
  msgDiv.className = 'ai-msg assistant';
  msgDiv.innerHTML = `
    <div class="label">AI 助手</div>
    <div style="margin-bottom:6px;">根据你的要求"${escapeHtml(command)}"，建议修改如下：</div>
    <div class="diff-box">
      <div class="diff-old">${escapeHtml(oldText)}</div>
      <div class="diff-new">${escapeHtml(newText)}</div>
    </div>
    <div class="action-row">
      <button class="btn-accept" onclick="acceptDiff(this)">采纳替换</button>
      <button class="btn-reject" onclick="rejectDiff(this)">不改了</button>
    </div>`;
  aiChat.appendChild(msgDiv);
  aiChat.scrollTop = aiChat.scrollHeight;
}

function acceptDiff(btn) {
  if (!pendingDiff) return;
  const { oldText, newText } = pendingDiff;
  const paragraphs = editor.querySelectorAll('p');
  for (const p of paragraphs) {
    if (p.textContent.trim() === oldText.trim()) { p.textContent = newText; break; }
  }
  const msgDiv = btn.closest('.ai-msg');
  msgDiv.querySelector('.diff-box').style.opacity = '0.5';
  msgDiv.querySelector('.action-row').innerHTML = '<span style="color:var(--green);font-size:12px;"><i class="fas fa-check"></i> 已替换</span>';
  pendingDiff = null;
  showToast('已替换', 'success');
}

function rejectDiff(btn) {
  btn.closest('.ai-msg').querySelector('.action-row').innerHTML = '<span style="color:var(--text3);font-size:12px;">已跳过</span>';
  pendingDiff = null;
}

function addMessage(role, text) {
  const div = document.createElement('div');
  div.className = `ai-msg ${role}`;
  div.innerHTML = `<div class="label">${role === 'user' ? '你' : 'AI 助手'}</div>${escapeHtml(text)}`;
  aiChat.appendChild(div);
  aiChat.scrollTop = aiChat.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML.replace(/\n/g, '<br>');
}

function showToast(msg, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  setTimeout(() => toast.classList.remove('show'), 2000);
}

document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && e.key === 'm') { e.preventDefault(); if (aiPanel.classList.contains('collapsed')) togglePanel(); aiInput.focus(); }
});
</script>
</body>
</html>
```

---

## 十、后端 API 完整实现

### 10.1 FastAPI 后端

```python
# server/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import json
import os

app = FastAPI(title="文稿修改助手 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== 配置 =====
DOUBAO_API_URL = os.getenv("LLM_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
DOUBAO_API_KEY = os.getenv("LLM_API_KEY", "")
DOUBAO_MODEL = os.getenv("LLM_MODEL", "doubao-pro-32k")

SYSTEM_PROMPT = """你是一个专业的中文文稿修改助手。用户会给你一段文稿和一条修改指令。
你需要：
1. 找到需要修改的文本片段
2. 按照修改指令生成修改后的文本
3. 严格按照 JSON 格式输出

输出格式（严格遵守）：
{
  "old_text": "需要被替换的原文（必须与原文完全一致，包括标点）",
  "new_text": "修改后的新文本",
  "reason": "简要说明修改理由（一句话）"
}

注意：
- old_text 必须与原文逐字一致，包括标点符号
- new_text 应该自然衔接上下文
- 只输出 JSON，不要输出其他内容"""

# ===== 请求/响应模型 =====
class RevisionRequest(BaseModel):
    document_text: str
    selected_text: str = ""
    command: str

class RevisionResponse(BaseModel):
    old_text: str
    new_text: str
    reason: str

# ===== 接口 =====
@app.post("/api/revise", response_model=RevisionResponse)
async def revise_text(req: RevisionRequest):
    user_content = f"以下是文稿全文：\n---\n{req.document_text}\n---\n"
    if req.selected_text:
        user_content += f"用户选中的文本：\n---\n{req.selected_text}\n---\n"
    user_content += f"修改指令：{req.command}\n\n请按照修改指令，输出修改建议的 JSON。"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            DOUBAO_API_URL,
            headers={
                "Authorization": f"Bearer {DOUBAO_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": DOUBAO_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.3,
                "response_format": {"type": "json_object"}
            }
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"LLM API 调用失败: {resp.status_code}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="LLM 返回格式异常")

    # 校验必要字段
    if "old_text" not in result or "new_text" not in result:
        raise HTTPException(status_code=502, detail="LLM 返回缺少必要字段")

    # 校验 old_text 在原文中存在
    if result["old_text"] not in req.document_text:
        # 尝试模糊匹配（去除首尾空白）
        trimmed = result["old_text"].strip()
        if trimmed not in req.document_text:
            raise HTTPException(status_code=502, detail="LLM 返回的 old_text 在原文中找不到")

    return RevisionResponse(
        old_text=result["old_text"],
        new_text=result["new_text"],
        reason=result.get("reason", "")
    )

# ===== 健康检查 =====
@app.get("/api/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 10.2 依赖文件

```txt
# server/requirements.txt
fastapi==0.115.0
uvicorn==0.30.0
httpx==0.27.0
pydantic==2.9.0
```

### 10.3 环境变量配置

```bash
# .env
LLM_API_URL=https://ark.cn-beijing.volces.com/api/v3/chat/completions
LLM_API_KEY=your-api-key-here
LLM_MODEL=doubao-pro-32k
```

### 10.4 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./server
    ports:
      - "8000:8000"
    environment:
      - LLM_API_URL=${LLM_API_URL}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_MODEL=${LLM_MODEL}
    restart: unless-stopped

  web:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./dist:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - api
    restart: unless-stopped
```

### 10.5 Nginx 配置

```nginx
# nginx.conf
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

---

## 十一、开发路线图

### Phase 1：核心功能（2-3 周）
- [ ] Tiptap 编辑器集成（Vue 3 + TypeScript）
- [ ] AI 浮窗面板组件
- [ ] 语音输入（Web Speech API）
- [ ] 后端 API 对接豆包
- [ ] Diff 对比展示
- [ ] 采纳/拒绝交互

### Phase 2：体验优化（1-2 周）
- [ ] 修改历史记录（撤销 AI 修改）
- [ ] 连续对话（AI 记住上文）
- [ ] 快捷指令（"正式化""精简""加总结"等一键操作）
- [ ] 加载状态优化（流式输出 + 打字机效果）
- [ ] 语音识别替换为讯飞/腾讯云 ASR

### Phase 3：企业级功能（2-4 周）
- [ ] 用户鉴权（登录/权限）
- [ ] 文稿模板库
- [ ] 批量修改（一次下达多个修改指令）
- [ ] 修改日志审计（谁改了什么、何时改的）
- [ ] 导出 Word/PDF
- [ ] 部署到腾讯云 + 域名 + HTTPS

### Phase 4：协同编辑（可选）
- [ ] Y.js + WebSocket 实现多人实时协作
- [ ] 光标位置同步
- [ ] 修改冲突解决

---

## 十二、关键注意事项

### 12.1 LLM 输出可靠性
- 大模型有时不按 JSON 格式输出，必须做 `try/catch` 解析
- `old_text` 必须与原文逐字一致，否则替换会失败——后端需做校验
- 建议设置 `response_format: {"type": "json_object"}` 强制 JSON 输出
- 长文档注意 Token 限制，可能需要分段处理

### 12.2 语音识别
- Web Speech API 仅 Chrome 支持，其他浏览器需降级为文字输入
- Chrome 版 Web Speech 需联网（走 Google 服务器），中国大陆可能不稳定
- 生产环境务必替换为讯飞/腾讯云 ASR

### 12.3 安全
- LLM API Key 永远放在后端，不可暴露到前端
- 后端做限流（每用户每分钟 N 次）
- 用户文稿可能包含敏感信息，日志需脱敏

### 12.4 Tiptap 替换文本
- Tiptap 基于 ProseMirror，替换文本需操作 ProseMirror 的 Transaction
- 不能简单地 `innerHTML` 替换，会丢失格式和光标位置
- 参考 `EditorPanel.vue` 中的 `replaceText` 方法

---

## 十三、备选方案参考

如果 Tiptap 不满足需求，以下方案可作为备选：

| 方案 | 适用场景 | 备注 |
|------|---------|------|
| OnlyOffice Document Server | 需要完整 Word/Excel/PPT 能力 | AGPL v3，需要企业版才能去品牌 |
| Collabora Online | 已有 Nextcloud 环境 | 对 .docx 兼容性不如 OnlyOffice |
| Etherpad | 只需纯文本协同编辑 | 极简，但富文本能力弱 |
| ProseMirror（Tiptap 底层） | 需要更底层的编辑器控制 | 学习曲线陡，但自由度最高 |
| WPS WebOffice API | 已有 WPS 企业授权 | 非开源，商业方案 |

---

*文档版本：v1.0 | 生成时间：2026-06-13 | 面向开发者/AI智能体*
