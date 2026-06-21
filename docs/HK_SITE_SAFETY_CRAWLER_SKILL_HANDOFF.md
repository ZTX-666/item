# 香港地盘安全爬虫与 Skill 配置交接文档

## 1. 目标

本交接文档补充 `HK_SITE_SAFETY_MONITORING_HANDOFF.md`，重点说明第一版爬虫如何落地，以及如何让用户通过 Skill/配置文件修改要监听的网站、关键词和告警规则。

核心原则：

- 爬虫本体固定，负责采集、解析、去重和入库。
- 用户关注主题通过 YAML Skill 配置维护，不写死在代码里。
- 官方来源作为事实基准，媒体来源只作为早期线索。
- P0 告警必须由规则确定，并保留人工确认。
- 大模型不是爬虫核心，只作为摘要、实体抽取和行动建议的可选增强。

## 2. 已生成文件

```text
config/crawler/sources.yml
config/crawler/skills/site-safety.yml
config/crawler/skills/scaffolding-fire-risk.yml
config/crawler/skills/lifting-safety.yml
config/crawler/skills/hot-weather-work.yml
.cursor/skills/hk-site-safety-crawler/SKILL.md
docs/HK_SITE_SAFETY_CRAWLER_SKILL_HANDOFF.md
```

文件用途：

- `sources.yml`：所有可采集来源的注册表，包括 URL、类型、频率、parser 名称和启用状态。
- `site-safety.yml`：默认综合监听主题，覆盖工业意外、恶劣天气、政策和媒体线索。
- `scaffolding-fire-risk.yml`：棚架、防火、阻燃、保护网和热工序主题。
- `lifting-safety.yml`：天秤、吊运、起重机和物件堕下主题。
- `hot-weather-work.yml`：酷热天气、热压力和户外作业主题。
- `.cursor/skills/hk-site-safety-crawler/SKILL.md`：给 Cursor Agent 使用的项目级维护指引。

## 3. 来源分类

### 3.1 放心做

这些来源优先使用官方 API/RSS：

- 香港天文台天气警告摘要 API
- 香港天文台天气警告详情 API
- 香港特区政府新闻公报 RSS
- `data.gov.hk` 新闻公报搜索 API

第一版 P0 天气、政府新闻和官方确认事故，应优先依赖这些来源。

### 3.2 可以做

这些来源使用公开 HTML/PDF 低频抓取：

- 劳工处职安警示
- 屋宇署通告函件
- 屋宇署 Practice Notes
- 房委会及房屋署工地安全提示
- 房委会 RSS 索引
- 发展局工务技术通告
- 建造业议会安全讯息

建议频率为 1-6 小时。采集时保存原始 HTML/PDF hash，便于排查网页结构变化。

### 3.3 谨慎做

媒体来源只抓公开列表、标题、链接、发布时间和短摘要：

- 香港01
- 星岛头条 / 星岛日报
- 明报
- 东方日报
- 香港商报

要求：

- 遵守 robots.txt 和网站条款。
- 不绕过登录、付费墙、验证码或反爬。
- 不保存或转发媒体全文。
- 命中后默认标记为 `media_lead`，需要官方来源交叉核验。

## 4. 推荐系统架构

```text
Scheduler
  -> Source Registry Loader
  -> Fetch Workers
  -> Parser Layer
  -> Normalized Item Store
  -> Skill Rule Engine
  -> Classification / Deduplication
  -> Alert Generator
  -> Notification + Acknowledgement
```

推荐技术栈：

- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Celery 或 APScheduler
- httpx
- feedparser
- BeautifulSoup / lxml
- pdfplumber 或 pypdf
- Alembic / SQLAlchemy
- Docker Compose

## 5. Parser 设计

建议 parser 名称与 `sources.yml` 中的 `parser` 字段保持一致。

必须实现：

- `hko_warnsum`
- `hko_warning_info`
- `rss_generic`
- `gov_press_api`
- `labour_work_safety_alert`
- `bd_circulars`
- `bd_practice_notes`
- `housing_site_safety`
- `housing_rss_index`
- `devb_technical_circulars`
- `cic_safety_messages`
- `media_search_generic`
- `media_section_generic`

统一输出字段：

```yaml
source_name: string
source_url: string
title: string
url: string
published_at: datetime | null
detected_at: datetime
content_text: string
content_hash: string
language: zh-HK | en | unknown
item_type: accident | weather | policy | circular | safety_alert | media_report
trust_level: official | quasi_official | media_lead
attachments:
  - url: string
    type: pdf | image | html
```

## 6. Skill 配置机制

业务监听主题放在：

```text
config/crawler/skills/*.yml
```

每个主题配置一个独立 YAML。爬虫运行时读取所有 `enabled: true` 的主题，对采集到的 item 做关键词匹配和告警分级。

配置结构：

```yaml
name: topic-name
display_name: 中文显示名
description: 主题说明
enabled: true

source_scope:
  include_sources:
    - gov_press_rss

keywords:
  include:
    - 关键词
  exclude:
    - 排除词

entities:
  work_process:
    - 工序词
  hazard:
    - 风险词

severity_rules:
  p0:
    any_keywords:
      - 单词命中即 P0
    combined_keywords:
      - [关键词A, 关键词B]
  p1:
    any_keywords:
      - 单词命中即 P1
  p2:
    default_for_matched_items: true

recommended_actions:
  - 建议行动
```

## 7. 用户如何新增监听主题

例子：用户想新增“密闭空间安全”。

新建：

```text
config/crawler/skills/confined-space-safety.yml
```

示例内容：

```yaml
name: confined-space-safety
display_name: 密闭空间安全
description: 监听密闭空间、气体检测、窒息、中毒和相关职安警示。
enabled: true

source_scope:
  include_sources:
    - gov_press_rss
    - gov_press_api
    - labour_work_safety_alert
    - cic_safety_messages
    - hk01_industrial_accident_search
    - stheadline_industrial_accident_search

keywords:
  include:
    - 密闭空间
    - 气体检测
    - 缺氧
    - 窒息
    - 中毒
    - 救援
  exclude:
    - 广告
    - 招聘

severity_rules:
  p0:
    combined_keywords:
      - [密闭空间, 死亡]
      - [密闭空间, 昏迷]
      - [缺氧, 工友]
  p1:
    any_keywords:
      - 密闭空间
      - 气体检测
      - 职安警示
  p2:
    default_for_matched_items: true
```

新增后不需要改 parser，只需让系统重新加载配置或重启 worker。

## 8. 告警分级规则

### P0

必须即时通知，并要求人工确认。

常见触发：

- 八号或以上热带气旋警告
- 黑色暴雨
- 致命工作意外
- 暂时停工通知书
- 发展局暂停承建商投标
- 涉及地盘、棚架、吊运、天秤等严重伤亡

### P1

重要通知，可即时或短周期汇总。

常见触发：

- 劳工处职安警示
- 房屋署工地安全提示
- CIC 安全讯息
- 发展局技术通告
- 红雨、雷暴、酷热天气等对项目有影响的信息
- 主流媒体报道但尚未官方确认的严重事故

### P2

进入每日摘要或普通列表。

常见触发：

- 普通政策通告
- 表格或 Practice Notes 更新
- 未确认媒体线索
- 一般安全宣传

## 9. 合规要求

开发时必须遵守：

- 优先使用官方 API/RSS。
- HTML/PDF 页面低频抓取。
- 设置清晰 User-Agent。
- 遵守 robots.txt 和网站条款。
- 不绕过验证码、登录、付费墙或反爬机制。
- 媒体内容不保存全文，不对外转载。
- 告警中保留原文链接和来源标记。

## 10. 第一版开发任务

第一阶段：

1. 加载 `config/crawler/sources.yml`。
2. 加载 `config/crawler/skills/*.yml`。
3. 完成天文台 API parser。
4. 完成政府 RSS parser。
5. 完成 `data.gov.hk` 新闻公报 API parser。
6. 实现 item 去重。
7. 实现关键词匹配和 P0/P1/P2 分级。
8. 保存 normalized item 和 classification。

第二阶段：

1. 实现劳工处、屋宇署、房屋署、发展局、CIC HTML/PDF parser。
2. 实现 PDF 下载、hash 和文本抽取。
3. 增加 source health 监控。
4. 增加网页结构变化报警。

第三阶段：

1. 接入香港01、星岛等媒体公开列表页。
2. 媒体只作为 `media_lead`。
3. 实现媒体与官方消息交叉核验。
4. 可选接入 LLM 做摘要、实体抽取和行动建议。

## 11. 验收标准

MVP 验收：

- 能按 `sources.yml` 定时拉取天文台 API 和政府新闻 RSS/API。
- 能读取多个 Skill 配置并按关键词匹配。
- 八号风球、黑雨、致命工作意外、暂时停工通知书能自动生成 P0。
- 媒体命中不会直接作为官方事实，只标记为线索。
- 用户新增一个 YAML 主题后，系统无需改代码即可开始监听。
- 所有告警保留原始 URL、来源、命中关键词和分级原因。

## 12. 运维注意

- 每个 source 记录最近成功时间、失败次数、最近错误。
- 抓取成功但连续多次 item 数量为 0 时报警。
- PDF 抽取失败进入 OCR fallback 队列。
- P0 通知失败必须重试并报警。
- 每日生成 source health 摘要。
- Skill 修改需要保留审计记录，包括修改人、修改时间和 diff。
