# 香港地盘安全爬虫系统详细使用交接文档

## 1. 给接手同事的快速说明

这个项目是一个香港地盘安全信息监听系统的 MVP。它目前不是完整后台系统，而是一套可以运行的核心爬虫骨架。

它已经能做到：

1. 从 YAML 读取要抓取的信息源。
2. 从 YAML 读取用户要监听的主题、关键词和 P0/P1/P2 分级规则。
3. 抓取官方 API、RSS 和公开 HTML 页面。
4. 把抓取结果解析成统一的 item。
5. 根据主题 Skill 配置做关键词匹配和告警分级。
6. 输出统一格式的 Alert Card JSON，后续可接后台、Email、Teams、Telegram 或 WhatsApp。

它暂时还没有做到：

1. 没有数据库。
2. 没有长期定时任务。
3. 没有后台页面。
4. 没有真实通知发送。
5. 官方 PDF 专用解析和媒体详情页解析还只是预留方向。
6. 大模型摘要还没有接入，当前摘要是纯脚本截断和关键词拼接。

## 2. 适合谁阅读

这份文档适合以下角色：

- 接手开发的 Python 工程师
- 负责配置关键词和信息源的产品/运营同事
- 负责部署和运维的同事
- 需要理解系统范围和风险的项目负责人

如果只想快速运行，请看第 5 节。

如果要改关键词或新增监听主题，请看第 8 节。

如果要继续开发生产版，请看第 13 节。

## 3. 当前分支和仓库

GitHub 仓库：

```text
https://github.com/ZTX-666/item
```

当前交付分支：

```text
hk-site-safety-crawler-mvp
```

建议接手同事先 clone 这个分支：

```bash
git clone -b hk-site-safety-crawler-mvp https://github.com/ZTX-666/item.git
cd item
```

Windows 注意：建议 clone 到英文路径，例如：

```text
C:\work\item
```

不要放在包含中文字符的路径下。当前本地目录 `C-SMART测试` 在 `pip install -e` 时曾触发 setuptools 的 cp950 编码问题。

## 4. 项目目录说明

```text
.
├── README.md
├── pyproject.toml
├── HK_SITE_SAFETY_MONITORING_HANDOFF.md
├── config/
│   └── crawler/
│       ├── sources.yml
│       └── skills/
│           ├── site-safety.yml
│           ├── scaffolding-fire-risk.yml
│           ├── lifting-safety.yml
│           └── hot-weather-work.yml
├── docs/
│   ├── HK_SITE_SAFETY_CRAWLER_CODE_HANDOFF.md
│   ├── HK_SITE_SAFETY_CRAWLER_SKILL_HANDOFF.md
│   └── HK_SITE_SAFETY_CRAWLER_USER_HANDOFF.md
├── src/
│   └── hk_site_safety_crawler/
│       ├── __init__.py
│       ├── cards.py
│       ├── cli.py
│       ├── config.py
│       ├── fetcher.py
│       ├── models.py
│       ├── parsers.py
│       ├── rules.py
│       └── runner.py
└── tests/
    └── test_rules_and_cards.py
```

重点文件：

- `config/crawler/sources.yml`：所有网站/API/RSS 的来源注册表。
- `config/crawler/skills/*.yml`：用户可编辑的监听主题和关键词规则。
- `src/hk_site_safety_crawler/`：核心 Python 代码。
- `output/alert_cards.json`：默认运行输出文件，已被 `.gitignore` 忽略。

## 5. 本地环境准备

推荐 Python 版本：

```text
Python 3.11+
```

标准安装方式：

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
```

如果在 Windows 中文路径下安装失败，请改用：

```bash
pip install beautifulsoup4 feedparser httpx lxml pypdf pyyaml pytest ruff
$env:PYTHONPATH = "src"
```

Linux/macOS 对应写法：

```bash
export PYTHONPATH=src
```

## 6. 快速运行

查看 CLI 参数：

```bash
python -m hk_site_safety_crawler.cli --help
```

只跑香港天文台天气警告摘要：

```bash
python -m hk_site_safety_crawler.cli --source hko_warnsum --max-cards 10
```

只跑政府新闻 RSS：

```bash
python -m hk_site_safety_crawler.cli --source gov_press_rss --max-cards 10
```

跑所有已启用来源，最多输出 50 张卡片：

```bash
python -m hk_site_safety_crawler.cli --max-cards 50
```

指定输出文件：

```bash
python -m hk_site_safety_crawler.cli --source hko_warnsum --output output/hko_warnsum_cards.json
```

带确认链接：

```bash
python -m hk_site_safety_crawler.cli --source gov_press_rss --ack-base-url https://internal.example.com/alerts
```

运行完成后会输出类似：

```json
{"output": "output\\alert_cards.json", "card_count": 0, "error_count": 0}
```

`card_count: 0` 不代表失败，只代表本次抓取没有命中已配置的关键词。

## 7. 输出 Alert Card 格式

输出文件默认位置：

```text
output/alert_cards.json
```

顶层结构：

```json
{
  "schema_version": 1,
  "card_count": 1,
  "error_count": 0,
  "cards": [],
  "errors": []
}
```

单张卡片示例：

```json
{
  "severity": "P0",
  "category": "site_safety",
  "title": "[P0][site_safety] 劳工处高度关注一宗致命工作意外",
  "summary": "劳工处高度关注一宗涉及地盘的致命工作意外。 命中关键词：致命工作意外、地盘。",
  "source_name": "香港特区政府新闻公报 RSS",
  "source_type": "official",
  "published_at": null,
  "detected_at": "2026-06-21T18:00:00+08:00",
  "matched_keywords": ["致命工作意外", "地盘"],
  "recommended_action": ["通知项目经理和安全经理。"],
  "url": "https://www.info.gov.hk/example",
  "ack_url": "https://internal.example.com/alerts/abc/ack",
  "render_payload": {
    "schema_version": 1,
    "classification_reason": "Matched P0 keyword: 致命工作意外",
    "requires_human_review": true
  }
}
```

后续后台、Teams、Email、WhatsApp 都应优先使用 `render_payload` 渲染，而不是重新拼字段。

## 8. 如何修改用户要监听的关键词

用户关注主题都在：

```text
config/crawler/skills/*.yml
```

例如 `lifting-safety.yml` 是天秤与吊运安全。

如果用户说：

```text
我要把吊运安全也加入“吊船、吊篮、吊架”这几个关键词。
```

修改：

```yaml
keywords:
  include:
    - 天秤
    - 塔式起重机
    - 吊运
    - 吊船
    - 吊篮
    - 吊架
```

如果某些词经常误报，加入 `exclude`：

```yaml
keywords:
  exclude:
    - 招聘
    - 二手买卖
    - 广告
```

修改后不需要改 Python 代码，只需要重新运行爬虫或重启 worker。

## 9. 如何新增一个监听主题

例子：新增“密闭空间安全”。

新建文件：

```text
config/crawler/skills/confined-space-safety.yml
```

内容示例：

```yaml
name: confined-space-safety
display_name: 密闭空间安全
description: 监听密闭空间、气体检测、缺氧、中毒和相关事故或职安警示。
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
    - 昏迷
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

recommended_actions:
  - 检查密闭空间作业许可证、气体检测和通风安排。
  - 检查救援程序、看守人员和应急设备。
```

然后运行：

```bash
python -m hk_site_safety_crawler.cli --max-cards 20
```

## 10. 如何新增信息源

信息源都在：

```text
config/crawler/sources.yml
```

新增一个 RSS 源示例：

```yaml
  - name: example_rss
    display_name: 示例 RSS
    category: official
    source_type: rss
    trust_level: official
    url: "https://example.com/rss.xml"
    poll_interval_seconds: 600
    priority: medium
    parser: rss_generic
    enabled: true
```

新增一个普通 HTML 列表页示例：

```yaml
  - name: example_html
    display_name: 示例 HTML 页面
    category: official
    source_type: html
    trust_level: official
    url: "https://example.com/news"
    poll_interval_seconds: 3600
    priority: medium
    parser: html_generic
    enabled: true
```

如果新增来源需要特殊结构解析，需要在 `parsers.py` 增加专用 parser，并在 `parse_document()` 中注册。

## 11. 来源可信度规则

当前约定：

```text
official       官方来源
quasi_official 半官方/行业机构来源，例如 CIC
media_lead     媒体线索
```

处理原则：

- `official` 可以作为事实基准。
- `quasi_official` 可作为高可信行业信息，但仍建议保留来源标记。
- `media_lead` 只能作为早期线索，不应直接作为官方确认事实。

媒体来源命中时，系统会把 `requires_human_review` 标记为 `true`。

## 12. P0/P1/P2 分级逻辑

代码位置：

```text
src/hk_site_safety_crawler/rules.py
```

分级顺序：

1. 判断 item 的 source 是否在 topic scope 中。
2. 如果命中 `exclude`，直接跳过。
3. 如果没有命中 `include`，跳过。
4. 如果命中 P0 单关键词，输出 P0。
5. 如果命中 P0 组合关键词，输出 P0。
6. 如果命中 P1 单关键词，输出 P1。
7. 如果命中 P1 组合关键词，输出 P1。
8. 如果是媒体且规则要求复核，输出 P1。
9. 其余匹配项输出 P2。

P0 例子：

```yaml
p0:
  any_keywords:
    - 致命工作意外
    - 暂时停工通知书
  combined_keywords:
    - [地盘, 死亡]
    - [天秤, 严重工伤]
```

重要原则：

- P0 必须可解释、可审计。
- 不要让大模型单独决定 P0。
- 大模型可以后续用于摘要，但最终分级仍应由规则控制。

## 13. 当前代码如何继续开发成生产版

### 第一阶段：持久化和定时任务

建议新增：

- PostgreSQL
- SQLAlchemy
- Alembic
- Celery 或 APScheduler

建议表：

- `sources`
- `raw_fetches`
- `items`
- `classifications`
- `alerts`
- `notifications`
- `source_health`

第一阶段目标：

- 定时抓取。
- 抓取结果入库。
- 按 URL/hash 去重。
- 生成 alerts。
- 记录 source health。

### 第二阶段：官方 HTML/PDF parser

优先实现：

- 劳工处职安警示 parser
- 屋宇署通告 parser
- 房屋署工地安全提示 parser
- 发展局技术通告 parser
- CIC 安全讯息 parser

PDF 流程：

```text
发现 PDF 链接
  -> 下载 PDF
  -> 计算 hash
  -> 保存原始文件
  -> pypdf/pdfplumber 抽文本
  -> 抽取标题、日期、编号和正文
  -> 进入规则匹配
```

扫描件 PDF 后续再接 OCR。

### 第三阶段：通知闭环

优先实现：

- Email
- Microsoft Teams webhook
- 告警确认 URL
- 未确认 P0 提醒
- 通知失败重试

确认链接建议：

```text
https://internal.example.com/alerts/{alert_id}/ack
```

### 第四阶段：后台页面

最小后台：

- 告警列表
- 告警详情
- 来源健康状态
- Skill 配置查看
- P0 确认状态

### 第五阶段：大模型增强

大模型只做辅助：

- 摘要
- 实体抽取
- 建议行动
- 媒体与官方事件合并判断

不要让大模型做：

- 抓取
- 绕过反爬
- 最终 P0 判定
- 官方事实确认

## 14. 测试和质量检查

运行单元测试：

```bash
python -m pytest
```

运行 Ruff：

```bash
python -m ruff check src tests
```

运行语法编译检查：

```bash
python -m compileall src tests
```

当前已验证：

- 单元测试通过。
- Ruff 通过。
- CLI help 可运行。
- `hko_warnsum` 真实抓取无错误。

## 15. 常见问题

### 15.1 `card_count` 为 0 是否失败

不是。

这通常表示抓到了内容，但没有命中当前 Skill 的关键词。看 `error_count` 是否为 0。如果 `error_count` 是 0，说明抓取链路正常。

### 15.2 为什么媒体不能直接作为 P0

媒体报道可能快，但可能信息不完整或需要官方确认。系统可以把媒体严重事故列为 P1 并要求人工复核，但真正 P0 应依赖官方来源或非常明确的规则。

### 15.3 是否一定要大模型

不一定。

MVP 可以纯脚本运行。大模型后续只用于提高卡片摘要质量、抽取地点/承建商/工序和生成建议行动。

### 15.4 为什么不要保存媒体全文

版权和合规风险较高。建议只保存标题、链接、短摘要、命中关键词和检测时间。

### 15.5 如何判断一个来源坏了

生产版需要记录：

- 最近成功时间
- 连续失败次数
- HTTP status
- item 数量
- 内容 hash 是否变化

如果连续抓取成功但 item 数量突然为 0，也应该报警，因为可能是网页结构变了。

## 16. 合规和安全要求

必须遵守：

- 优先用官方 API/RSS。
- HTML/PDF 低频抓取。
- 设置合理 User-Agent。
- 遵守 robots.txt 和网站条款。
- 不绕过登录、付费墙、验证码或反爬。
- 不保存或转发媒体全文。
- 告警中保留原文链接。
- P0 必须人工确认。

## 17. Git 工作流建议

当前分支：

```bash
git checkout hk-site-safety-crawler-mvp
```

开发新功能建议新建分支：

```bash
git checkout -b feature/add-database-storage
```

提交前检查：

```bash
python -m pytest
python -m ruff check src tests
```

提交：

```bash
git add .
git commit -m "Add database storage for crawler items"
git push -u origin feature/add-database-storage
```

## 18. 接手 Checklist

接手同事建议按这个顺序检查：

- [ ] Clone `hk-site-safety-crawler-mvp` 分支。
- [ ] 确认路径不包含中文字符。
- [ ] 创建 venv 并安装依赖。
- [ ] 运行 `python -m pytest`。
- [ ] 运行 `python -m ruff check src tests`。
- [ ] 运行 `python -m hk_site_safety_crawler.cli --source hko_warnsum --max-cards 10`。
- [ ] 阅读 `config/crawler/sources.yml`。
- [ ] 阅读 `config/crawler/skills/site-safety.yml`。
- [ ] 尝试新增一个测试关键词并重新运行。
- [ ] 决定下一步是先接数据库、定时任务还是通知渠道。

## 19. 最重要的设计结论

这个系统的正确边界是：

```text
爬虫负责稳定采集
规则负责确定分级
Skill/YAML 负责业务可配置
卡片负责统一展示
人工负责确认 P0
大模型只负责辅助理解和表达
```

不要把这些职责混在一起。这样系统后续才容易维护、审计和交接。
