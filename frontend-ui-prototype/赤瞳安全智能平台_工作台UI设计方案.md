# 赤瞳安全智能平台 — 工作台 UI 设计方案

> 本文档是赤瞳平台的前端 UI 完整设计方案，采用**工作台（Workbench）**模式，替代之前的"侧边栏导航 + 页面切换 + AI 聊天面板"三栏布局。
>
> 核心变化：**从"切页面看信息"变成"一屏看全、就地展开、AI 即时响应"**。

---

## 一、为什么从三栏布局改为工作台

### 1.1 原方案的问题

| 问题 | 具体表现 | 影响 |
|------|---------|------|
| **信息割裂** | 6 个导航页面，每次只能看一个 | 安全主任需要在隐患台账、巡检、风险雷达之间频繁切换 |
| **AI 面板边缘化** | Copilot Panel 在右侧 380px，像附加功能 | AI 感弱，用户容易忽视 |
| **切换成本高** | 切页面丢失上下文 | 刚在巡检看到的问题，切到台账要重新找 |
| **概览不可见** | 不知道整体安全状态 | 必须主动去看各个页面才能发现问题 |

### 1.2 工作台模式的核心区别

```
原方案：侧边栏导航 → 切换页面 → 打开 Copilot 面板 → 切回页面
工作台：一屏总览 → Command Bar 输入 → 就地展开面板 → 完成后回到总览
```

**三条设计铁律：**

1. **Status First** — 打开软件第一眼看到的是安全状态数字，不是聊天框
2. **AI as Command Bar** — AI 是顶部命令栏，不是右侧面板；随叫随到，不占固定空间
3. **Expand, Not Switch** — 点击任何面板原地展开，概览缩小到底部，不丢失上下文

---

## 二、工作台布局架构

### 2.1 总体结构（从上到下 5 层）

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 1: Header Bar（44px）                                       │
│  品牌 logo | 地盘名称 | 系统状态灯 | 告警数 | 用户                │
├──────────────────────────────────────────────────────────────────┤
│ Layer 2: Command Bar（48px，AI 主入口）                            │
│  [AI🔴] [地盘/区域▼] | 输入指令... | [Go]                         │
├──────────────────────────────────────────────────────────────────┤
│ Layer 3: Status Strip（60px，5 个指标卡片）                        │
│  [未闭环 5] [超期 2] [今日巡检 14] [天气预警] [本周闭环 8]          │
├──────────────────────────────────────────────────────────────────┤
│ Layer 4: Widget Grid（弹性，核心内容区）                           │
│  ┌──────────────┬──────────────────┐                            │
│  │  Camera      │  Active hazards   │                            │
│  │  Feeds 2x2   │  (列表 + 操作)    │                            │
│  │              ├──────────┬───────┤                            │
│  │              │Quick     │Risk   │                            │
│  │              │Forms     │Radar  │                            │
│  └──────────────┴──────────┴───────┘                            │
├──────────────────────────────────────────────────────────────────┤
│ Layer 5: Activity Feed（弹性，时间线）                              │
│  ● 14:32 VLM 检测到未戴安全帽 → [确认] [忽略]                     │
│  ● 13:00 超期提醒：B2 临边护栏 → [发送提醒] [标记闭环]             │
│  ● 11:15 已生成 T006_B2.docx                                     │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 各层职责

| 层 | 高度 | 内容 | 交互 |
|----|------|------|------|
| **Header** | 44px | 品牌、地盘切换、系统状态、告警 | 点击地盘切换、点击告警跳转 |
| **Command Bar** | 48px | AI 输入框 + 上下文选择器 | 输入指令、Ctrl+K 聚焦 |
| **Status Strip** | 60px | 5 个关键指标数字 | 点击指标跳转到对应 Widget |
| **Widget Grid** | 弹性 | 摄像头、隐患、表格、风险 | 点击 Widget 展开、Widget 内操作 |
| **Activity Feed** | 弹性 | 最近活动时间线 | 每条可操作（确认/忽略/查看） |

### 2.3 Command Bar 详细设计

Command Bar 是 AI 的**唯一主入口**，替代之前的 Copilot Panel。

```
┌──────────────────────────────────────────────────────────────┐
│  [AI🔴]  [B2▼]  │  输入指令...                    │  [Go]   │
│   品牌标识  上下文   │  placeholder 提示可做操作       │  发送   │
└──────────────────────────────────────────────────────────────┘
```

**组件分解：**

- **AI 标识**：红色圆形，内含"AI"字样，点击展开历史对话
- **上下文选择器**：下拉选择当前地盘/区域，AI 自动感知上下文
- **输入框**：支持文本、粘贴图片、拖拽文件、Ctrl+K 全局聚焦
- **Go 按钮**：红色主按钮，发送指令

**输入后的交互（三种响应模式）：**

| 模式 | 触发 | 展示方式 | 示例 |
|------|------|---------|------|
| **Inline Reply** | 查询类 | Command Bar 下方弹出小气泡 | "B2 区有 3 条未闭环隐患" |
| **Overlay Panel** | 执行类 | 整个 Widget Grid 区域被覆盖，展示 AI 处理过程 + 结果卡片 | 隐患确认卡片 + 通知草稿 |
| **Widget Update** | 数据类 | 对应 Widget 刷新数据 | 台账新增一条隐患 |

**Overlay Panel 的生命周期：**

```
1. 用户在 Command Bar 输入 → 按 Enter
2. Widget Grid 区域淡出，Overlay Panel 从上方滑入
3. Overlay Panel 显示：ProgressChain → 对话流 → 结果卡片 → 操作按钮
4. 用户操作完毕（确认/忽略/关闭）→ Overlay Panel 淡出
5. Widget Grid 淡入，数据已更新
```

---

## 三、Widget Grid 设计

### 3.1 网格布局

```
默认布局（grid-template-areas）：

"cameras  hazards"
"cameras  forms"
"feed     radar"

具体 CSS：
.workbench-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto 1fr;
  grid-template-areas:
    "cameras  hazards"
    "cameras  forms"
    "feed     radar";
  gap: 12px;
  padding: 12px;
}
```

### 3.2 四个 Widget 的定义

#### Widget 1: Camera Feeds

| 属性 | 值 |
|------|---|
| 位置 | grid-area: cameras |
| 内容 | 2x2 摄像头网格，每个显示实时画面 + 检测框 |
| 状态标签 | LIVE（红色）/ OK（绿色）/ OFF（灰色） |
| 交互 | 点击某个摄像头 → 原地展开为大画面 + 检测详情 |
| AI 触发 | 点击"立即巡检"按钮 → Overlay Panel 显示巡检工作流 |

**Widget 内布局：**

```
┌──────────────────────────────────────┐
│ Camera feeds            Last: 14:32  │
│ ┌──────────┐  ┌──────────┐          │
│ │ B2-Z1    │  │ B2-Z2    │          │
│ │ [LIVE]   │  │ [OK]     │          │
│ │ 🔴检测框 │  │          │          │
│ └──────────┘  └──────────┘          │
│ ┌──────────┐  ┌──────────┐          │
│ │ A3-Z1    │  │ C1-Z1    │          │
│ │ [OK]     │  │ [OFF]    │          │
│ └──────────┘  └──────────┘          │
│                        [Inspect all] │
└──────────────────────────────────────┘
```

#### Widget 2: Active Hazards

| 属性 | 值 |
|------|---|
| 位置 | grid-area: hazards |
| 内容 | 活跃隐患列表（最多显示 5 条） |
| 行样式 | 风险色条 + 描述 + 区域 + 状态 + 操作 |
| 交互 | 点击"Notify"→ Overlay Panel 生成通知；点击"View all"→ 展开完整台账 |
| 数据来源 | safety_cases WHERE status != 'closed' |

**行样式规范：**

```
┌────────────────────────────────────────────┐
│ 🔴 Edge guardrail missing    B2  1d overdue  Notify │
│    ^风险色条     ^描述           ^区域  ^状态    ^操作 │
└────────────────────────────────────────────┘

CSS:
.hazard-row {
  display: grid;
  grid-template-columns: 8px 1fr 40px 80px 48px;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 6px;
  align-items: center;
}
.hazard-row--high { background: #FEF2F2; }
.hazard-row--medium { background: #FEF3C7; }
.hazard-row--low { background: #F0FDF4; }
.hazard-row--pending { background: #F9FAFB; }
```

#### Widget 3: Quick Forms

| 属性 | 值 |
|------|---|
| 位置 | grid-area: forms |
| 内容 | 常用表格快捷入口 + 天气关联推荐 |
| 按钮样式 | Pill 形状，按类别着色 |
| 交互 | 点击模板 → Overlay Panel 启动填表工作流 |
| 智能推荐 | 根据天气预警/当前隐患自动推荐相关表格（如热应激→T150） |

**推荐逻辑：**

```python
def get_recommended_forms(weather_warnings, active_hazards):
    forms = []
    # 天气关联
    for w in weather_warnings:
        if "酷热" in w:
            forms.extend(["T150", "T151", "T152"])
        if "暴雨" in w:
            forms.extend(["T066", "T067"])
    # 隐患关联
    for h in active_hazards:
        if h.type == "临边":
            forms.append("T006")
        if h.type == "吊运":
            forms.append("T032")
    return list(set(forms))[:6]  # 最多6个
```

#### Widget 4: Risk Radar

| 属性 | 值 |
|------|---|
| 位置 | grid-area: radar |
| 内容 | 天气预警 + 安全新闻 + 3 日预报 |
| 预警样式 | 高亮色条 + 图标 + 摘要 |
| 交互 | 点击"Generate T150"→ 触发填表；点击详情 → 展开完整风险雷达 |
| 数据来源 | hko_weather_check + accident_news_search，30 分钟刷新 |

### 3.3 Activity Feed 设计

**每一行活动项的结构：**

```
┌───────────────────────────────────────────────────────────┐
│ 🔴 VLM detected: No hard hat - C1 Zone 1      14:32      │
│    Confirm  |  Ignore                                     │
└───────────────────────────────────────────────────────────┘

CSS:
.feed-item {
  display: grid;
  grid-template-columns: 12px 1fr 60px;
  grid-template-rows: auto auto;
  gap: 0 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-gray-100);
}
.feed-item__icon { grid-row: 1 / 3; align-self: start; margin-top: 2px; }
.feed-item__text { font-size: 13px; font-weight: 500; }
.feed-item__time { font-size: 11px; color: var(--color-gray-400); text-align: right; }
.feed-item__actions { grid-column: 2; font-size: 12px; color: var(--color-blue-500); }
```

**活动类型与图标色：**

| 类型 | 图标色 | 示例 |
|------|--------|------|
| VLM 检测 | 红色 ● | "VLM detected: No hard hat" |
| 超期提醒 | 橙色 ● | "Overdue reminder: Edge guardrail B2" |
| 文件生成 | 绿色 ● | "Form generated: T006_B2.docx" |
| 通知发送 | 蓝色 ● | "Notification sent to Site safety group" |
| 天气预警 | 红色 ● | "Hot weather warning issued" |

---

## 四、Overlay Panel 设计（核心交互）

### 4.1 什么是 Overlay Panel

当用户在 Command Bar 输入指令后，Widget Grid 区域被一个浮层面板覆盖，展示 AI 处理过程和结果。这是工作台模式最核心的交互组件。

```
正常状态：                        Overlay 状态：
┌──────────────────────────┐    ┌──────────────────────────┐
│  Widget Grid (可见)       │    │  Overlay Panel (覆盖)     │
│  ┌────┬────┬────┐        │    │  ┌──────────────────────┐  │
│  │Cam │Haz │Form│        │    │  │  AI Header + Close    │  │
│  ├────┼────┼────┤        │    │  ├──────────────────────┤  │
│  │    │Rad │Feed│        │    │  │  ProgressChain        │  │
│  └────┴────┴────┘        │    │  │  ● Classify ✓         │  │
│                           │    │  │  ● Generate ◐         │  │
│                           │    │  │  ○ Confirm             │  │
│                           │    │  ├──────────────────────┤  │
│                           │    │  │  Result Cards         │  │
│                           │    │  │  [Hazard] [Notify]   │  │
│                           │    │  ├──────────────────────┤  │
│                           │    │  │  Action Buttons       │  │
│                           │    │  │  [Send] [Edit] [Skip] │  │
│                           │    │  └──────────────────────┘  │
└──────────────────────────┘    └──────────────────────────┘
```

### 4.2 Overlay Panel 的内部结构

```
┌──────────────────────────────────────────────────────────┐
│  [AI🔴] Chitung is analyzing...                  [Close] │  ← Header
├──────────────────────────────────────────────────────────┤
│  ● Classify hazard      Done ✓                           │  ← ProgressChain
│  ● Generate notification  Working...                      │
│  ○ Confirm and send                                       │
├──────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐  ┌─────────────────────────┐  │  ← Result Cards
│  │ Hazard record        │  │ Notification draft       │  │
│  │ Type: Edge opening    │  │ Target: WhatsApp group  │  │
│  │ Risk: High 🔴        │  │ Content: B2 guardrail.. │  │
│  │ Area: B2             │  │                         │  │
│  │ Deadline: 06-17      │  │                         │  │
│  │ CASE-001 ✓           │  │                         │  │
│  └─────────────────────┘  └─────────────────────────┘  │
├──────────────────────────────────────────────────────────┤
│  [Send notification]  [Edit]  [Generate T006]  [Skip]    │  ← Actions
└──────────────────────────────────────────────────────────┘
```

### 4.3 Overlay Panel 的状态流转

```
Opening:
  Widget Grid → opacity: 0, translateY(10px)
  Overlay Panel → opacity: 1, translateY(0), 动画 200ms ease-out

Running:
  ProgressChain 实时更新（SSE 推送 step_update 事件）

Waiting:
  某步骤 requires_confirm=True → ProgressChain 暂停 → 展示结果卡片

Closing:
  用户点击操作按钮 → 执行操作
  Overlay Panel → opacity: 0, translateY(-10px), 动画 200ms ease-in
  Widget Grid → opacity: 1, 数据已更新
```

### 4.4 Inline Reply 模式（小查询不覆盖整个面板）

对于简单的查询（如"B2 区有多少隐患？"），不需要覆盖 Widget Grid，而是在 Command Bar 下方弹出一个小气泡：

```
┌──────────────────────────────────────────────────────────┐
│  [AI🔴] [B2▼] │ B2 区有多少未闭环隐患？              [Go] │  ← Command Bar
├──────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐    │
│  │  B2 区目前有 3 条未闭环隐患，其中 1 条超期。       │    │  ← Inline Reply
│  │  [查看隐患台账]  [生成简报]                        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  Widget Grid (仍然可见，只是被气泡部分遮挡)                │
│  ...                                                     │
```

**Inline Reply 触发条件：**

| 意图 | 模式 | 原因 |
|------|------|------|
| hazard_query | Inline Reply | 查询不需要大面板 |
| form_fill | Overlay Panel | 需要展示预填卡片 |
| hazard_report | Overlay Panel | 需要确认卡片 + 通知草稿 |
| inspection | Overlay Panel | 需要展示巡检进度 + 结果 |
| daily_briefing | Overlay Panel | 需要展示简报卡片 |

---

## 五、Widget 展开模式（Expand）

### 5.1 展开交互

点击 Widget 标题栏的"展开"图标 → Widget 原地扩展为全宽，其他 Widget 缩小为底部标签栏。

```
正常状态：                           展开状态：
┌──────────┬───────────┐           ┌───────────────────────────┐
│ Cameras  │ Hazards   │           │ Risk Radar (expanded)     │
│          │           │    →      │                           │
│          ├─────┬─────┤           │ [完整天气预警详情]          │
│          │Forms│Radar│           │ [安全新闻列表]             │
│          │     │     │           │ [3日预报详情]              │
└──────────┴─────┴─────┘           │                           │
                                    ├───────────────────────────┤
                                    │ Overview: [5] [2] [14]   │  ← 底部缩略
                                    │ [Cam] [Haz] [Forms]      │
                                    └───────────────────────────┘
```

### 5.2 展开时的组件状态

```vue
<!-- 展开状态管理 -->
<script setup>
const expandedWidget = ref<string | null>(null)

function expandWidget(widgetName: string) {
  expandedWidget.value = widgetName
}

function collapseWidget() {
  expandedWidget.value = null
}
</script>

<template>
  <div class="workbench" :class="{ 'workbench--expanded': expandedWidget }">
    <!-- 展开时隐藏，正常时显示 -->
    <WidgetGrid v-if="!expandedWidget" />
    
    <!-- 展开的面板 -->
    <ExpandedPanel v-if="expandedWidget" :name="expandedWidget" @close="collapseWidget">
      <component :is="expandedComponent" />
    </ExpandedPanel>
    
    <!-- 底部缩略概览（展开时显示） -->
    <OverviewBar v-if="expandedWidget" @navigate="expandWidget" />
  </div>
</template>
```

---

## 六、设计 Token（工作台专用）

### 6.1 颜色系统

```css
:root {
  /* 品牌色 — 赤瞳红 */
  --color-brand-50: #FEF2F2;
  --color-brand-100: #FEE2E2;
  --color-brand-200: #FECACA;
  --color-brand-500: #DC2626;    /* 主色 */
  --color-brand-600: #B91C1C;
  --color-brand-800: #991B1B;
  --color-brand-900: #7F1D1D;

  /* 中性色 */
  --color-gray-50: #F9FAFB;
  --color-gray-100: #F3F4F6;
  --color-gray-200: #E5E7EB;
  --color-gray-300: #D1D5DB;
  --color-gray-400: #9CA3AF;
  --color-gray-500: #6B7280;
  --color-gray-600: #4B5563;
  --color-gray-700: #374151;
  --color-gray-800: #1F2937;
  --color-gray-900: #111827;

  /* 语义色 */
  --color-danger-50: #FEF2F2;
  --color-danger-100: #FEE2E2;
  --color-danger-500: #EF4444;
  --color-danger-800: #991B1B;

  --color-warning-50: #FFFBEB;
  --color-warning-100: #FEF3C7;
  --color-warning-500: #F59E0B;
  --color-warning-800: #92400E;

  --color-success-50: #F0FDF4;
  --color-success-100: #DCFCE7;
  --color-success-500: #10B981;
  --color-success-800: #065F46;

  --color-info-50: #EFF6FF;
  --color-info-100: #DBEAFE;
  --color-info-500: #3B82F6;
  --color-info-800: #1E40AF;

  /* 风险等级专用色 */
  --risk-high-bg: #FEF2F2;
  --risk-high-text: #991B1B;
  --risk-high-dot: #DC2626;
  --risk-medium-bg: #FEF3C7;
  --risk-medium-text: #92400E;
  --risk-medium-dot: #F59E0B;
  --risk-low-bg: #F0FDF4;
  --risk-low-text: #065F46;
  --risk-low-dot: #10B981;

  /* 摄像头状态色 */
  --cam-live: #DC2626;
  --cam-ok: #10B981;
  --cam-off: #6B7280;

  /* 面板背景 */
  --bg-header: #1F2937;
  --bg-workspace: #F9FAFB;
  --bg-widget: #FFFFFF;
  --bg-overlay: #FFFFFF;
  --bg-feed: #FFFFFF;
}

/* 暗色模式 */
[data-theme="dark"] {
  --bg-header: #111827;
  --bg-workspace: #1F2937;
  --bg-widget: #374151;
  --bg-overlay: #1F2937;
  --color-gray-900: #F9FAFB;
  --color-gray-800: #F3F4F6;
  --color-gray-700: #E5E7EB;
}
```

### 6.2 布局 Token

```css
:root {
  /* 层高度 */
  --height-header: 44px;
  --height-command-bar: 48px;
  --height-status-strip: 60px;

  /* Widget 间距 */
  --widget-gap: 12px;
  --widget-padding: 12px;
  --widget-radius: 10px;
  --widget-border: 0.5px solid var(--color-gray-200);

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 10px;
  --radius-xl: 12px;
  --radius-pill: 999px;

  /* 阴影 */
  --shadow-widget: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-overlay: 0 8px 30px rgba(0,0,0,0.12);
  --shadow-dropdown: 0 4px 12px rgba(0,0,0,0.15);

  /* 动画 */
  --duration-fast: 150ms;
  --duration-normal: 250ms;
  --duration-slow: 400ms;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in: cubic-bezier(0.7, 0, 0.84, 0);

  /* 字体 */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;

  --text-xs: 11px;
  --text-sm: 12px;
  --text-base: 13px;
  --text-md: 14px;
  --text-lg: 16px;
  --text-xl: 20px;
  --text-2xl: 24px;
  --text-metric: 28px;   /* 指标卡片数字专用 */
}
```

### 6.3 关键组件样式

```css
/* Command Bar */
.command-bar {
  height: var(--height-command-bar);
  background: var(--bg-widget);
  border: 1px solid var(--color-brand-500);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  padding: 0 8px 0 12px;
  gap: 8px;
  transition: box-shadow var(--duration-fast);
}
.command-bar:focus-within {
  box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.1);
}

/* Status Metric Card */
.metric-card {
  background: var(--bg-widget);
  border-radius: var(--radius-lg);
  padding: 10px 16px;
  text-align: center;
  border: 0.5px solid var(--color-gray-200);
  cursor: pointer;
  transition: all var(--duration-fast);
}
.metric-card:hover {
  box-shadow: var(--shadow-widget);
  transform: translateY(-1px);
}
.metric-card__label {
  font-size: var(--text-sm);
  color: var(--color-gray-500);
  margin-bottom: 2px;
}
.metric-card__value {
  font-size: var(--text-metric);
  font-weight: 500;
  line-height: 1.2;
}

/* Widget 容器 */
.widget {
  background: var(--bg-widget);
  border-radius: var(--widget-radius);
  border: var(--widget-border);
  padding: var(--widget-padding);
  box-shadow: var(--shadow-widget);
  overflow: hidden;
}
.widget__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.widget__title {
  font-size: var(--text-md);
  font-weight: 500;
  color: var(--color-gray-800);
}
.widget__action {
  font-size: var(--text-sm);
  color: var(--color-info-500);
  cursor: pointer;
}

/* Overlay Panel */
.overlay-panel {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--bg-overlay);
  border-radius: var(--widget-radius);
  padding: 16px;
  z-index: 10;
  animation: overlay-in var(--duration-normal) var(--ease-out);
  overflow-y: auto;
}
@keyframes overlay-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Inline Reply Bubble */
.inline-reply {
  position: absolute;
  top: var(--height-command-bar);
  left: 16px;
  right: 16px;
  background: var(--bg-widget);
  border-radius: var(--radius-lg);
  border: var(--widget-border);
  box-shadow: var(--shadow-dropdown);
  padding: 12px 16px;
  z-index: 10;
  animation: bubble-in var(--duration-fast) var(--ease-out);
}
@keyframes bubble-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Hazard Row */
.hazard-row {
  display: grid;
  grid-template-columns: 8px 1fr 40px 80px 48px;
  gap: 8px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  align-items: center;
  cursor: pointer;
  transition: background var(--duration-fast);
}
.hazard-row:hover { filter: brightness(0.97); }
.hazard-row--high { background: var(--risk-high-bg); }
.hazard-row--medium { background: var(--risk-medium-bg); }
.hazard-row--low { background: var(--risk-low-bg); }
.hazard-row--pending { background: var(--color-gray-50); }

/* Camera Feed Tile */
.cam-tile {
  position: relative;
  background: var(--color-gray-900);
  border-radius: var(--radius-md);
  overflow: hidden;
  aspect-ratio: 16/10;
}
.cam-tile__status {
  position: absolute;
  top: 6px;
  left: 6px;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--text-xs);
  font-weight: 500;
  color: white;
}
.cam-tile__status--live { background: var(--cam-live); }
.cam-tile__status--ok { background: var(--cam-ok); }
.cam-tile__status--off { background: var(--cam-off); }

/* Detection Box (on camera tile) */
.detection-box {
  position: absolute;
  border: 1px solid;
  border-style: dashed;
  border-radius: 2px;
}
.detection-box--high { border-color: var(--color-danger-500); }
.detection-box--medium { border-color: var(--color-warning-500); }

/* Form Pill Button */
.form-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast);
  border: 0.5px solid;
}
.form-pill--primary {
  background: var(--color-info-50);
  color: var(--color-info-800);
  border-color: var(--color-info-100);
}
.form-pill--alert {
  background: var(--color-danger-50);
  color: var(--color-danger-800);
  border-color: var(--color-danger-100);
}
.form-pill:hover {
  box-shadow: var(--shadow-widget);
  transform: translateY(-1px);
}

/* Feed Item */
.feed-item {
  display: grid;
  grid-template-columns: 12px 1fr 60px;
  grid-template-rows: auto auto;
  gap: 0 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-gray-100);
}
.feed-item__icon {
  grid-row: 1 / 3;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 5px;
}
.feed-item__text { font-size: var(--text-base); font-weight: 500; color: var(--color-gray-800); }
.feed-item__time { font-size: var(--text-sm); color: var(--color-gray-400); text-align: right; }
.feed-item__actions {
  grid-column: 2;
  font-size: var(--text-sm);
  color: var(--color-info-500);
  margin-top: 4px;
}
.feed-item__actions span { cursor: pointer; margin-right: 12px; }
.feed-item__actions span:hover { text-decoration: underline; }

/* Progress Chain (in Overlay) */
.progress-chain {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  background: var(--color-gray-50);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
}
.progress-step {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--text-sm);
  color: var(--color-gray-500);
  white-space: nowrap;
}
.progress-step--completed { color: var(--color-success-500); }
.progress-step--running { color: var(--color-info-500); }
.progress-step--running .progress-step__dot {
  animation: pulse 1s infinite;
}
.progress-step--waiting { color: var(--color-warning-500); }
.progress-step--failed { color: var(--color-danger-500); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
```

---

## 七、Vue 3 组件架构

### 7.1 组件树（工作台版）

```
App.vue
├── WorkbenchLayout.vue                # 工作台布局容器
│   ├── HeaderBar.vue                   # Layer 1: 顶部标题栏
│   │   ├── BrandLogo.vue               # 品牌标识
│   │   ├── SiteSelector.vue            # 地盘/区域选择
│   │   ├── SystemStatus.vue            # 系统状态灯
│   │   └── UserMenu.vue               # 用户菜单
│   ├── CommandBar.vue                   # Layer 2: AI 命令栏
│   │   ├── AiIndicator.vue             # AI 红色标识
│   │   ├── ContextSelector.vue         # 上下文选择器
│   │   ├── CommandInput.vue            # 输入框
│   │   └── InlineReply.vue             # 小查询回复气泡
│   ├── StatusStrip.vue                 # Layer 3: 状态指标条
│   │   └── MetricCard.vue             # 单个指标卡片 ×5
│   ├── WidgetGrid.vue                  # Layer 4: Widget 网格
│   │   ├── CameraFeedsWidget.vue       # 摄像头网格
│   │   │   └── CameraTile.vue          # 单个摄像头
│   │   ├── ActiveHazardsWidget.vue     # 活跃隐患列表
│   │   │   └── HazardRow.vue           # 单条隐患
│   │   ├── QuickFormsWidget.vue        # 快捷表格
│   │   │   └── FormPill.vue            # 模板胶囊按钮
│   │   ├── RiskRadarWidget.vue         # 风险雷达
│   │   │   ├── AlertCard.vue           # 预警卡片
│   │   │   └── ForecastBar.vue         # 3日预报
│   │   └── OverlayPanel.vue            # 浮层面板（AI交互）
│   │       ├── OverlayHeader.vue       # 面板标题
│   │       ├── ProgressChain.vue       # 进度链
│   │       ├── ChatBubble.vue          # 对话气泡
│   │       ├── HazardConfirmCard.vue   # 隐患确认卡片
│   │       ├── NotificationDraftCard.vue # 通知草稿卡片
│   │       ├── InspectionResultCard.vue  # 巡检结果卡片
│   │       ├── FormFillCard.vue         # 表格填充卡片
│   │       ├── DailyBriefingCard.vue    # 每日简报卡片
│   │       └── FileResultCard.vue       # 文件生成卡片
│   ├── ActivityFeed.vue                # Layer 5: 活动时间线
│   │   └── FeedItem.vue               # 单条活动
│   ├── ExpandedPanel.vue              # Widget 展开面板
│   └── OverviewBar.vue                # 展开时的底部缩略栏
├── CommandPalette.vue                  # Ctrl+K 全局命令面板
└── ToastNotification.vue              # 全局通知
```

### 7.2 Pinia Store 设计

```typescript
// stores/workbench.ts
import { defineStore } from 'pinia'

export const useWorkbenchStore = defineStore('workbench', {
  state: () => ({
    // 当前地盘
    currentSite: 'B2',
    
    // Status Strip 数据
    metrics: {
      openHazards: 5,
      overdueItems: 2,
      inspectedToday: 14,
      weatherAlert: 'Hot warning' as string | null,
      closedThisWeek: 8,
    },
    
    // Overlay Panel
    overlayVisible: false,
    overlayMode: 'none' as 'none' | 'processing' | 'result',
    
    // Widget 展开
    expandedWidget: null as string | null,
    
    // 活动流
    feedItems: [] as FeedItem[],
    
    // AI 对话历史
    aiMessages: [] as AiMessage[],
    
    // 当前工作流
    activeWorkflowId: null as string | null,
  }),
  
  actions: {
    async sendCommand(message: string) {
      // 1. 判断是否需要 Overlay Panel
      const intent = await this.classifyIntent(message)
      
      if (intent.type === 'query') {
        // Inline Reply 模式
        this.showInlineReply(message)
      } else {
        // Overlay Panel 模式
        this.openOverlay()
        await this.executeWorkflow(intent)
      }
    },
    
    openOverlay() {
      this.overlayVisible = true
      this.overlayMode = 'processing'
    },
    
    closeOverlay() {
      this.overlayVisible = false
      this.overlayMode = 'none'
    },
    
    expandWidget(name: string) {
      this.expandedWidget = name
    },
    
    collapseWidget() {
      this.expandedWidget = null
    },
  },
})
```

---

## 八、与之前方案的关键差异

| 维度 | 之前的三栏布局 | 现在的工作台 |
|------|--------------|------------|
| **AI 入口** | 右侧 Copilot Panel（380px 常驻） | 顶部 Command Bar + Overlay Panel |
| **信息可见性** | 同一时间只看一个页面 | 一屏可见所有关键信息 |
| **导航方式** | 侧边栏切换页面 | Widget Grid 就地展开 |
| **AI 空间占用** | 持续占 380px | 不使用时占 0px，使用时临时覆盖 |
| **操作路径** | 输入 → 看聊天 → 切到台账确认 | 输入 → 就地看到结果卡片 → 点击确认 → 自动更新 |
| **上下文** | 手动在 Copilot 描述 | Command Bar 上下文选择器自动注入 |
| **视觉风格** | 传统 SaaS 布局 | 安全指挥中心 / Dashboard |
| **最适合屏幕** | ≥ 1280px | ≥ 1024px（更紧凑） |

---

## 九、竞赛 Demo 的视觉流程

**8 分钟演示，重点展示"工作台 + AI 命令栏"的融合体验：**

```
第 1 分钟 — 打开即全局
  打开软件 → 一屏看到 5 个状态指标 + 4 个摄像头 + 3 条隐患 + 天气预警
  评委立刻感受到"这是一个指挥中心，不是聊天框"

第 2-3 分钟 — Command Bar 录入隐患
  点击 Command Bar → 输入"B2区临边护栏被拆"
  → Overlay Panel 滑入 → ProgressChain 动画
  → 隐患确认卡片 → 点击确认
  → 通知草稿卡片 → 点击发送
  → Overlay 关闭 → Widget Grid 更新（隐患+1，待闭环+1）

第 4-5 分钟 — 巡检触发
  在摄像头 Widget 点击"Inspect all"
  → Overlay Panel 展示巡检进度
  → VLM 检测结果卡片 → 点击"全部入库"
  → Activity Feed 自动新增一条记录

第 5-6 分钟 — 智能填表
  Command Bar 输入"帮我填 T006"
  → Overlay Panel 展示预填卡片
  → 点击"Generate Word" → 文件下载

第 6-7 分钟 — 风险雷达
  点击 Risk Radar Widget → 原地展开
  → 看到酷热天气预警 → 点击"Generate T150"
  → 填表工作流触发

第 7-8 分钟 — 数据看板
  点击 Active Hazards 的"View all"
  → 展开完整台账（带筛选、搜索、导出）
  → 在 Command Bar 问"XX公司表现如何" → AI 分析
```

---

> **总结：工作台模式的核心是"一屏看全、AI 随叫随到、操作就地完成"。安全主任不需要在多个页面间跳来跳去——打开软件就能看到所有关键信息，需要 AI 时在顶部命令栏输入，结果就地展示，确认后自动更新。这就是面向前线人员的 AI 产品该有的样子。**
