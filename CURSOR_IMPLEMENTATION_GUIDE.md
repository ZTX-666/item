# 用 Cursor 实现 AI 文档助手功能 - 完整实操指南

> **目标读者**：有基础编程能力的开发者  
> **预计时间**：2-3 天完整实现所有功能  
> **技术栈**：Tiptap + React + 豆包/OpenAI API + Cursor AI 辅助编程

---

## 目录

1. [项目初始化](#1-项目初始化)
2. [接入大模型 API](#2-接入大模型-api)
3. [功能一：全文润色 + 语气切换](#3-功能一全文润色--语气切换)
4. [功能二：文档问答](#4-功能二文档问答)
5. [功能三：风险提示 + 规范性审核](#5-功能三风险提示--规范性审核)
6. [功能四：口语转正式文档](#6-功能四口语转正式文档)
7. [功能五：智能表格生成](#7-功能五智能表格生成)
8. [功能六：私人知识库对接](#8-功能六私人知识库对接)
9. [Cursor 高效开发技巧](#9-cursor-高效开发技巧)
10. [常见问题排查](#10-常见问题排查)

---

## 1. 项目初始化

### 1.1 用 Cursor 创建项目

**操作步骤**：

1. 打开 Cursor
2. 按 `Ctrl+Shift+P`（Mac: `Cmd+Shift+P`）
3. 输入 `> Cursor: New Project`
4. 选择 `React + TypeScript + Vite` 模板

**或者直接用命令行**（在 Cursor 的终端里执行）：

```bash
# 创建项目
npm create vite@latest ai-doc-editor -- --template react-ts
cd ai-doc-editor
npm install

# 安装核心依赖
npm install @tiptap/react @tiptap/pm @tiptap/starter-kit
npm install @tiptap/extension-highlight @tiptap/extension-text-align
npm install @tiptap/extension-table @tiptap/extension-image
npm install uuid marked
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### 1.2 告诉 Cursor 你要做什么

**在 Cursor 的 Chat 面板里输入**（这是最关键的一步）：

```
我要做一个 AI 文档编辑器，功能包括：
1. 基于 Tiptap 的富文本编辑
2. 接入豆包大模型 API
3. 实现全文润色、语气切换、文档问答、风险提示功能
4. 界面要简洁，左侧编辑器，右侧 AI 助手面板

请帮我：
- 创建项目结构
- 配置 Tiptap 编辑器
- 写好 API 调用封装
- 实现基础 UI 布局

使用 React + TypeScript + Tailwind CSS
```

**Cursor 会自动**：
- 创建文件结构
- 写基础代码
- 安装依赖
- 解释每段代码的作用

---

## 2. 接入大模型 API

### 2.1 选择大模型（推荐顺序）

| 模型 | API 接入难度 | 中文能力 | 推荐场景 |
|------|-------------|---------|---------|
| **豆包（Doubao）** | ⭐ 简单 | ⭐⭐⭐⭐⭐ | 国内项目首选 |
| **通义千问** | ⭐ 简单 | ⭐⭐⭐⭐⭐ | 阿里云用户 |
| **OpenAI GPT-4** | ⭐⭐ 中等 | ⭐⭐⭐⭐ | 预算充足 |
| **DeepSeek** | ⭐ 简单 | ⭐⭐⭐⭐ | 性价比高 |
| **本地模型（Ollama）** | ⭐⭐⭐ 复杂 | 取决于模型 | 数据完全私有 |

### 2.2 豆包 API 接入示例

**Step 1: 获取 API Key**
1. 访问 https://www.volcengine.com/product/doubao
2. 注册并创建应用
3. 获取 API Key

**Step 2: 创建 API 调用封装**（让 Cursor 帮你写）

在 Cursor Chat 里输入：

```
创建一个文件 src/lib/ai.ts
实现以下功能：
1. 封装豆包大模型的 API 调用
2. 支持流式输出（streaming）
3. 导出以下函数：
   - chatWithAI(messages: Message[]): AsyncGenerator<string>
   - polishText(text: string, tone: string): Promise<string>
   - checkRisks(text: string): Promise<Risk[]>
   - answerQuestion(doc: string, question: string): Promise<string>
使用 TypeScript，添加完整类型定义
```

**Cursor 会生成类似这样的代码**：

```typescript
// src/lib/ai.ts
const DOUBAO_API_URL = 'https://ark.cn-beijing.volces.com/api/v3/chat/completions';
const API_KEY = import.meta.env.VITE_DOUBAO_API_KEY;

export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface Risk {
  level: 'high' | 'medium' | 'low';
  position: number;
  length: number;
  reason: string;
  suggestion: string;
}

export async function* chatWithAI(messages: Message[]) {
  const response = await fetch(DOUBAO_API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${API_KEY}`,
    },
    body: JSON.stringify({
      model: 'ep-202502-xxxxx', // 你的模型 ID
      messages,
      stream: true,
    }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n').filter(line => line.trim());
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        const content = data.choices?.[0]?.delta?.content;
        if (content) yield content;
      }
    }
  }
}

// 全文润色
export async function polishText(text: string, tone: string): Promise<string> {
  const prompt = `请将以下文字改为${tone}的语气，保持原意不变：\n\n${text}`;
  
  let result = '';
  for await (const chunk of chatWithAI([
    { role: 'system', content: '你是一个专业的文档编辑助手' },
    { role: 'user', content: prompt },
  ])) {
    result += chunk;
  }
  
  return result;
}

// 风险提示
export async function checkRisks(text: string): Promise<Risk[]> {
  const prompt = `分析以下文档，识别潜在风险点。以 JSON 格式返回，格式为：
[
  {
    "level": "high|medium|low",
    "reason": "风险原因",
    "suggestion": "修改建议"
  }
]

文档内容：
${text}`;

  let result = '';
  for await (const chunk of chatWithAI([
    { role: 'system', content: '你是合同风险分析专家，只返回 JSON' },
    { role: 'user', content: prompt },
  ])) {
    result += chunk;
  }
  
  // 提取 JSON
  const jsonMatch = result.match(/\[[\s\S]*\]/);
  if (jsonMatch) {
    return JSON.parse(jsonMatch[0]);
  }
  return [];
}
```

### 2.3 配置环境变量

创建 `.env.local` 文件：

```bash
# .env.local
VITE_DOUBAO_API_KEY=your_api_key_here
VITE_DOUBAO_MODEL_ID=ep-202502-xxxxx
```

**⚠️ 重要**：把 `.env.local` 加到 `.gitignore`，避免 API Key 泄露！

---

## 3. 功能一：全文润色 + 语气切换

### 3.1 实现思路

```
用户点击「润色」按钮
  → 获取编辑器全文内容
  → 调用 polishText(text, tone)
  → 逐段对比原文和润色后文字
  → 展示对比界面（红色删除线 + 绿色新文）
  → 用户逐段确认是否采纳
```

### 3.2 让 Cursor 帮你实现

**在 Cursor Chat 里输入**：

```
在 src/components/ 下创建 PolishingPanel.tsx 组件：

功能需求：
1. 有 5 个语气按钮：专业正式、亲切友好、简洁直白、自信有力、客观中立
2. 点击某个语气按钮后，调用 ai.ts 里的 polishText 函数
3. 展示原文和润色后文字的对比（使用 diff 展示）
4. 每段对比旁边有「采纳」和「跳过」按钮
5. 所有段都处理完后，显示「全部应用」按钮

使用 React + TypeScript + Tailwind CSS
参考现有代码风格
```

**Cursor 会生成类似这样的组件**：

```tsx
// src/components/PolishingPanel.tsx
import { useState } from 'react';
import { polishText } from '../lib/ai';
import { DiffView } from './DiffView';

const TONES = [
  { id: 'formal', label: '专业正式', icon: '🏢' },
  { id: 'friendly', label: '亲切友好', icon: '😊' },
  { id: 'concise', label: '简洁直白', icon: '⚡' },
  { id: 'confident', label: '自信有力', icon: '💪' },
  { id: 'neutral', label: '客观中立', icon: '🎯' },
];

export function PolishingPanel({ editor }) {
  const [selectedTone, setSelectedTone] = useState<string>('');
  const [suggestions, setSuggestions] = useState<Array<{
    original: string;
    polished: string;
    accepted: boolean | null;
  }>>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  const handlePolish = async (tone: string) => {
    setIsProcessing(true);
    setSelectedTone(tone);
    
    const fullText = editor.getText();
    const paragraphs = fullText.split('\n\n').filter(p => p.trim());
    
    const newSuggestions = [];
    for (const para of paragraphs) {
      const polished = await polishText(para, tone);
      newSuggestions.push({
        original: para,
        polished,
        accepted: null,
      });
    }
    
    setSuggestions(newSuggestions);
    setIsProcessing(false);
  };

  const handleAccept = (index: number) => {
    setSuggestions(prev => prev.map((s, i) => 
      i === index ? { ...s, accepted: true } : s
    ));
  };

  const handleSkip = (index: number) => {
    setSuggestions(prev => prev.map((s, i) => 
      i === index ? { ...s, accepted: false } : s
    ));
  };

  const handleApplyAll = () => {
    const acceptedText = suggestions
      .filter(s => s.accepted)
      .map(s => s.polished)
      .join('\n\n');
    
    editor.commands.setContent(acceptedText);
    setSuggestions([]);
  };

  return (
    <div className="p-4">
      <h3 className="font-bold mb-4">全文润色</h3>
      
      {/* 语气选择 */}
      <div className="grid grid-cols-5 gap-2 mb-6">
        {TONES.map(tone => (
          <button
            key={tone.id}
            onClick={() => handlePolish(tone.label)}
            className={`p-3 rounded-lg border ${
              selectedTone === tone.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
            }`}
          >
            <div className="text-2xl mb-1">{tone.icon}</div>
            <div className="text-sm">{tone.label}</div>
          </button>
        ))}
      </div>

      {/* 处理中 */}
      {isProcessing && (
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-2 text-gray-600">AI 正在润色...</p>
        </div>
      )}

      {/* 建议列表 */}
      {suggestions.length > 0 && (
        <div>
          {suggestions.map((suggestion, index) => (
            <div key={index} className="mb-6 p-4 border rounded-lg">
              <DiffView original={suggestion.original} modified={suggestion.polished} />
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => handleAccept(index)}
                  className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
                >
                  采纳
                </button>
                <button
                  onClick={() => handleSkip(index)}
                  className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
                >
                  跳过
                </button>
              </div>
            </div>
          ))}
          
          <button
            onClick={handleApplyAll}
            className="w-full py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            全部应用
          </button>
        </div>
      )}
    </div>
  );
}
```

### 3.3 实现 DiffView 组件

**继续在 Cursor Chat 输入**：

```
创建 src/components/DiffView.tsx
实现文字对比展示组件：

输入：original: string, modified: string
展示：
  - 原文用红色删除线展示
  - 修改后文字用绿色展示
  - 如果两个文字差异不大，用高亮显示不同之处

可以使用简单的字符对比算法，或者使用 diff 库（如 diff-match-patch）
```

---

## 4. 功能二：文档问答

### 4.1 实现思路

```
用户在右侧输入框提问
  → 把全文内容作为 context 传给 AI
  → AI 回答
  → 在编辑器中高亮答案来源的段落
  → 支持多轮对话（保留上下文）
```

### 4.2 让 Cursor 帮你实现

**在 Cursor Chat 里输入**：

```
创建 src/components/ChatPanel.tsx 组件：

功能需求：
1. 顶部显示对话历史（多轮对话）
2. 底部输入框（支持文字和语音输入）
3. 用户输入问题后，调用 ai.ts 的 chatWithAI 函数
4. AI 回答时，流式显示（像 ChatGPT 一样逐字出现）
5. AI 回答完后，在编辑器中高亮相关段落
6. 支持「追问」功能（基于上下文继续对话）

额外功能：
  - 如果答案在文档某处，在答案旁边显示「查看原文」按钮
  - 点击后编辑器自动滚动到对应位置

使用 React + TypeScript + Tailwind CSS
```

**Cursor 会生成核心代码**，包括：

```tsx
// src/components/ChatPanel.tsx（核心片段）
import { useState, useRef, useEffect } from 'react';
import { chatWithAI } from '../lib/ai';

export function ChatPanel({ editor }) {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'system', content: '你是文档问答助手' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingResponse, setStreamingResponse] = useState('');
  
  const handleSend = async () => {
    if (!input.trim()) return;
    
    // 添加用户消息
    const userMessage = { role: 'user' as const, content: input };
    const newMessages = [...messages, userMessage];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setStreamingResponse('');
    
    // 构造带文档内容的 prompt
    const fullText = editor.getText();
    const contextPrompt = `基于以下文档内容回答问题：\n\n文档：\n${fullText}\n\n问题：${input}`;
    
    const messagesWithContext = [
      ...newMessages.slice(0, -1),
      { role: 'user', content: contextPrompt }
    ];
    
    // 流式接收 AI 回答
    let fullResponse = '';
    for await (const chunk of chatWithAI(messagesWithContext)) {
      fullResponse += chunk;
      setStreamingResponse(fullResponse);
    }
    
    // 添加到消息历史
    setMessages([...newMessages, { role: 'assistant', content: fullResponse }]);
    setIsLoading(false);
    setStreamingResponse('');
    
    // 尝试在文档中高亮相关段落
    highlightRelevantParagraph(fullResponse);
  };
  
  const highlightRelevantParagraph = (answer: string) => {
    // 简单实现：找到答案中提到的关键词，在编辑器中高亮
    const fullText = editor.getText();
    const sentences = answer.split('。').filter(s => s.length > 10);
    
    for (const sentence of sentences) {
      const index = fullText.indexOf(sentence);
      if (index !== -1) {
        // 使用 Tiptap 的选中功能
        editor.commands.setTextSelection({ from: index, to: index + sentence.length });
        // 添加高亮标记（需要配置 highlight 扩展）
        break; // 只高亮第一个匹配
      }
    }
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* 对话历史 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.filter(m => m.role !== 'system').map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-3 rounded-lg ${
              msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        
        {/* 流式回答 */}
        {streamingResponse && (
          <div className="flex justify-start">
            <div className="max-w-[80%] p-3 rounded-lg bg-gray-100">
              {streamingResponse}
              <span className="animate-pulse">|</span>
            </div>
          </div>
        )}
      </div>
      
      {/* 输入框 */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyPress={e => e.key === 'Enter' && handleSend()}
            placeholder="问文档任何问题..."
            className="flex-1 px-4 py-2 border rounded-lg"
          />
          <button
            onClick={handleSend}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## 5. 功能三：风险提示 + 规范性审核

### 5.1 实现思路（人机协同模式）

```
AI 扫描文档
  → 在编辑器中用 🔴🟡🟢 标记风险位置
  → 右侧显示「风险审核面板」
  → 用户逐条处理风险
  → 每条风险可以：采纳建议 / 手动修改 / 忽略
```

### 5.2 让 Cursor 帮你实现

**在 Cursor Chat 里输入**：

```
创建 src/components/RiskChecker.tsx 组件：

功能需求：
1. 点击「风险扫描」按钮后，调用 ai.ts 的 checkRisks 函数
2. 在编辑器中用不同颜色标记风险位置：
   - 高风险：红色背景 + 🔴
   - 中风险：黄色背景 + 🟡
   - 低风险：绿色背景 + 🟢
3. 右侧显示风险列表，每条风险显示：
   - 风险等级图标
   - 风险原因
   - AI 的修改建议
   - 操作按钮：【采纳建议】【手动修改】【忽略】
4. 点击某条风险，编辑器自动跳转到对应位置
5. 所有风险处理完后，显示「导出审核报告」按钮

使用 React + TypeScript + Tailwind CSS
需要操作 Tiptap 编辑器的 DOM 位置，参考 Tiptap 文档
```

**Cursor 会生成核心代码**，包括：

```tsx
// src/components/RiskChecker.tsx（核心片段）
import { useState } from 'react';
import { checkRisks, Risk } from '../lib/ai';

export function RiskChecker({ editor }) {
  const [risks, setRisks] = useState<(Risk & { id: number; resolved: boolean })[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [activeRiskId, setActiveRiskId] = useState<number | null>(null);
  
  const handleScan = async () => {
    setIsScanning(true);
    const fullText = editor.getText();
    
    const detectedRisks = await checkRisks(fullText);
    
    const risksWithId = detectedRisks.map((risk, index) => ({
      ...risk,
      id: index,
      resolved: false,
    }));
    
    setRisks(risksWithId);
    highlightRisksInEditor(risksWithId);
    setIsScanning(false);
  };
  
  const highlightRisksInEditor = (risks: Risk[]) => {
    // 方法1：使用 Tiptap 的装饰器（Decoration）
    // 方法2：直接在 DOM 上添加标记（简单但不够优雅）
    
    // 这里用简单方法演示
    const editorDom = editor.view.dom;
    const fullText = editor.getText();
    
    risks.forEach(risk => {
      const index = fullText.indexOf(risk.reason); // 简化：用原因定位
      if (index !== -1) {
        // 在实际项目中，应该用 Tiptap 的 Decoration API
        console.log('Risk found at position:', index);
      }
    });
  };
  
  const handleAcceptSuggestion = (riskId: number) => {
    const risk = risks.find(r => r.id === riskId);
    if (!risk) return;
    
    // 在编辑器中替换文本（需要准确的位置信息）
    // 这里简化：直接标记已解决
    setRisks(prev => prev.map(r => 
      r.id === riskId ? { ...r, resolved: true } : r
    ));
  };
  
  const handleIgnore = (riskId: number) => {
    setRisks(prev => prev.map(r => 
      r.id === riskId ? { ...r, resolved: true } : r
    ));
  };
  
  const scrollToRisk = (risk: Risk & { id: number }) => {
    // 在编辑器中找到对应位置并滚动
    const fullText = editor.getText();
    const index = fullText.indexOf(risk.reason);
    if (index !== -1) {
      editor.commands.setTextSelection(index);
      editor.commands.scrollIntoView();
    }
    setActiveRiskId(risk.id);
  };
  
  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-6">
        <h3 className="font-bold">风险提示</h3>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50"
        >
          {isScanning ? '扫描中...' : '开始扫描'}
        </button>
      </div>
      
      {/* 风险统计 */}
      {risks.length > 0 && (
        <div className="flex gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span>🔴</span>
            <span>{risks.filter(r => r.level === 'high' && !r.resolved).length} 高风险</span>
          </div>
          <div className="flex items-center gap-2">
            <span>🟡</span>
            <span>{risks.filter(r => r.level === 'medium' && !r.resolved).length} 中风险</span>
          </div>
          <div className="flex items-center gap-2">
            <span>🟢</span>
            <span>{risks.filter(r => r.level === 'low' && !r.resolved).length} 建议优化</span>
          </div>
        </div>
      )}
      
      {/* 风险列表 */}
      <div className="space-y-4">
        {risks.map(risk => (
          <div
            key={risk.id}
            className={`p-4 border rounded-lg ${
              risk.resolved ? 'opacity-50' : ''
            } ${activeRiskId === risk.id ? 'border-blue-500' : ''}`}
            onClick={() => scrollToRisk(risk)}
          >
            <div className="flex items-start gap-2 mb-2">
              <span className="text-xl">
                {risk.level === 'high' ? '🔴' : risk.level === 'medium' ? '🟡' : '🟢'}
              </span>
              <div className="flex-1">
                <p className="font-semibold">{risk.reason}</p>
                <p className="text-sm text-gray-600 mt-1">建议：{risk.suggestion}</p>
              </div>
            </div>
            
            {!risk.resolved && (
              <div className="flex gap-2 mt-4">
                <button
                  onClick={() => handleAcceptSuggestion(risk.id)}
                  className="px-3 py-1 bg-green-500 text-white rounded hover:bg-green-600"
                >
                  采纳建议
                </button>
                <button
                  onClick={() => scrollToRisk(risk)}
                  className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
                >
                  手动修改
                </button>
                <button
                  onClick={() => handleIgnore(risk.id)}
                  className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50"
                >
                  忽略
                </button>
              </div>
            )}
            
            {risk.resolved && (
              <div className="mt-2 text-sm text-gray-500">✅ 已处理</div>
            )}
          </div>
        ))}
      </div>
      
      {/* 导出报告 */}
      {risks.length > 0 && risks.every(r => r.resolved) && (
        <button
          onClick={() => exportReport()}
          className="w-full mt-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
        >
          导出审核报告
        </button>
      )}
    </div>
  );
}
```

---

## 6. 功能四：口语转正式文档

### 6.1 实现思路

```
用户语音输入（或粘贴口语文字）
  → 调用 AI 转写 + 改写
  → 展示对比：「口语原文」vs「正式文稿」
  → 用户可以：
      - 直接采纳
      - 在正式文稿基础上手动微调
      - 让 AI 重新改写
  → 确认后插入文档光标位置
```

### 6.2 让 Cursor 帮你实现

**在 Cursor Chat 里输入**：

```
创建 src/components/OralToFormal.tsx 组件：

功能需求：
1. 顶部有一个大文本框，用户可以粘贴或输入口语文字
2. 有「语音输入」按钮（调用 Web Speech API）
3. 点击「转为正式文档」按钮，调用 AI 改写
4. 展示对比视图：左侧口语原文，右侧正式文稿
5. 正式文稿可以手动编辑
6. 底部有操作按钮：【采纳并插入】【重新改写】【取消】

额外功能：
  - 语音输入时显示实时转写文字
  - 支持多种正式风格选择（合同风格、报告风格、邮件风格）

使用 React + TypeScript + Tailwind CSS
```

---

## 7. 功能五：智能表格生成

### 7.1 实现思路

```
用户选中一段文字
  → 点击「转为表格」按钮
  → 调用 AI 识别结构化信息
  → 展示预览表格 + 字段列表
  → 用户可以调整字段（删除、重命名、重新排序）
  → 确认后插入表格到编辑器
```

### 7.2 让 Cursor 帮你实现

**在 Cursor Chat 里输入**：

```
创建 src/components/SmartTable.tsx 组件：

功能需求：
1. 用户选中编辑器中的文字后，点击「转为表格」按钮
2. 调用 AI 分析选中文字，识别结构化信息
3. 展示预览表格（使用 HTML table 或 Tiptap Table 扩展）
4. 右侧显示字段列表，用户可以：
   - 删除不需要的字段
   - 重命名字段
   - 拖拽排序字段
5. 底部有【插入表格】【取消】按钮

AI 调用示例：
  输入：项目A预算100万工期3个月；项目B预算50万工期1个月
  输出：JSON 格式的表格数据

使用 React + TypeScript + Tailwind CSS
```

---

## 8. 功能六：私人知识库对接

### 8.1 实现思路

```
用户上传文档/填写知识库
  → 将内容向量化（embedding）
  → 存储到向量数据库（如 ChromeDB 或 Faiss）
  → AI 回答/修改时，先从知识库检索相关内容
  → 把检索结果作为 context 传给 AI
```

### 8.2 简单实现方案（无需向量数据库）

**如果你不想搭建向量数据库**，可以用简单方案：

```
用户填写「公司文档规范」（纯文本）
  → 每次调用 AI 时，把规范作为 system prompt 的一部分
  → AI 会自动遵守规范
```

**让 Cursor 帮你实现**：

```
创建 src/lib/knowledge-base.ts

功能：
1. 提供界面让用户输入/上传知识库内容
2. 将知识库内容存储到 localStorage（简单方案）或后端数据库（完整方案）
3. 每次调用 AI 时，自动将知识库内容加到 prompt 里

导出函数：
  - getKnowledgeBase(): string
  - updateKnowledgeBase(content: string): void
  - clearKnowledgeBase(): void
```

### 8.3 完整方案（使用向量数据库）

如果需要更强大的知识库功能，可以：

1. **安装向量数据库**：

```bash
npm install @chromadb/core
# 或者使用更轻量的方案
npm install localvector
```

2. **让 Cursor 帮你实现 RAG 流程**：

```
创建 src/lib/rag.ts

功能：
1. 将文档分块（chunk）
2. 使用 embedding API 将每块向量化
3. 存储到向量数据库
4. 检索时，根据问题找到最相关的块
5. 将相关块作为 context 传给 AI

参考 LangChain 的 RAG 实现
```

---

## 9. Cursor 高效开发技巧

### 9.1 使用 Cursor 的 AI 功能

| 功能 | 快捷键 | 用途 |
|------|--------|------|
| **Chat** | `Ctrl+L` | 问 AI 任何问题，生成代码 |
| **Edit** | `Ctrl+K` | 选中代码后，让 AI 修改 |
| **Compose** | `Ctrl+I` | 在空白处，让 AI 写完整函数/组件 |
| **Context** | `@` | 引用文件、文件夹、文档 |

### 9.2 高效 Prompt 模板

**生成组件**：

```
创建 [组件名].tsx
功能：[详细描述功能]
使用：[技术栈]
参考：[现有组件名] 的代码风格
导出：[需要导出的接口/函数]
```

**修改现有代码**：

```
选中代码后按 Ctrl+K，输入：
"把这个函数改成支持流式输出"
"添加错误处理"
"优化性能，使用 useMemo"
```

**调试错误**：

```
直接把错误信息粘贴到 Cursor Chat，输入：
"为什么会出现这个错误？怎么修？"
```

### 9.3 让 Cursor 理解你的项目

**创建一个 `cursor-context.md` 文件**，告诉 Cursor 你的项目信息：

```markdown
# 项目上下文

## 技术栈
- React 18 + TypeScript
- Tiptap 编辑器
- Tailwind CSS
- 豆包大模型 API

## 项目结构
- src/components/：所有 React 组件
- src/lib/：工具函数和 API 封装
- src/types/：TypeScript 类型定义

## 代码规范
- 使用函数组件 + Hooks
- 优先使用 Tailwind CSS，少用 inline style
- 所有 API 调用都放在 src/lib/ 里
- 组件命名使用 PascalCase

## 当前正在开发的功能
- [x] 基础编辑器
- [ ] 全文润色
- [ ] 文档问答
```

**然后在 Cursor Chat 里输入**：

```
@cursor-context.md 请帮我实现全文润色功能
```

Cursor 会自动读取这个文件，理解你的项目。

---

## 10. 常见问题排查

### 10.1 API 调用失败

**问题**：调用豆包 API 返回 401 错误

**解决方案**：
1. 检查 `.env.local` 里的 API Key 是否正确
2. 确认 API Key 是否已激活
3. 检查网络是否能访问 api.volcengine.com

**让 Cursor 帮你调试**：

```
我的 API 调用返回 401 错误，代码如下：
[粘贴代码]

帮我找出问题并修复
```

### 10.2 Tiptap 编辑器不更新

**问题**：调用 `editor.commands.setContent()` 后编辑器没变化

**解决方案**：
1. 确认 `editor` 对象已正确初始化
2. 在组件里打印 `editor` 看看是否为 `null`
3. 确认在 `useEffect` 里调用，或者用户点击事件里调用

### 10.3 流式输出不工作

**问题**：AI 回答是一次全部显示，不是逐字显示

**解决方案**：
1. 确认 API 调用时设置了 `stream: true`
2. 确认前端正确解析了 SSE（Server-Sent Events）格式
3. 使用 `AsyncGenerator` 逐块接收

**参考代码**（让 Cursor 生成）：

```typescript
// 正确的流式调用示例
export async function* chatWithAI(messages: Message[]) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { /* ... */ },
    body: JSON.stringify({ messages, stream: true }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    // 解析 SSE 格式
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        yield data.choices[0].delta.content;
      }
    }
  }
}
```

---

## 附录：完整项目结构

```
ai-doc-editor/
├── src/
│   ├── components/
│   │   ├── Editor.tsx              # Tiptap 编辑器主组件
│   │   ├── PolishingPanel.tsx      # 全文润色面板
│   │   ├── ChatPanel.tsx           # 文档问答面板
│   │   ├── RiskChecker.tsx         # 风险提示面板
│   │   ├── OralToFormal.tsx        # 口语转正式面板
│   │   ├── SmartTable.tsx          # 智能表格面板
│   │   └── DiffView.tsx           # 文字对比组件
│   ├── lib/
│   │   ├── ai.ts                   # AI API 调用封装
│   │   ├── knowledge-base.ts       # 知识库管理
│   │   └── rag.ts                  # RAG 检索（可选）
│   ├── types/
│   │   └── index.ts                # TypeScript 类型定义
│   ├── App.tsx                     # 主应用组件
│   ├── main.tsx                    # 入口文件
│   └── index.css                   # 全局样式
├── .env.local                       # 环境变量（不要提交到 git）
├── cursor-context.md                # 给 Cursor 的项目上下文
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

---

## 总结：开发顺序建议

```
第 1 天：
  ✅ 项目初始化 + Tiptap 编辑器
  ✅ 接入豆包 API（能跑通一个 Hello World）
  ✅ 实现全文润色功能（最简版本）

第 2 天：
  ✅ 完善全文润色（加对比界面、逐段确认）
  ✅ 实现文档问答功能
  ✅ 实现口语转正式文档

第 3 天：
  ✅ 实现风险提示功能
  ✅ 实现智能表格生成
  ✅ 接入知识库
  ✅ 测试 + 修 bug
```

---

**最后建议**：

1. **每实现一个功能就提交一次 git**，避免代码丢失
2. **多用 Cursor 的 Chat 功能**，遇到任何问题都先问 AI
3. **参考官方文档**：
   - Tiptap: https://tiptap.dev/docs
   - Cursor: https://cursor.sh/docs
   - 豆包 API: https://www.volcengine.com/docs

4. **如果卡住了**，把完整错误信息 + 相关代码粘贴到 Cursor Chat，AI 通常能直接给出解决方案

祝开发顺利！🚀
