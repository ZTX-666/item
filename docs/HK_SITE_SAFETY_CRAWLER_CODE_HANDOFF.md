# 香港地盘安全爬虫核心代码交接文档

## 1. 本次交付内容

本次交付的是可运行的 MVP 核心代码，不包含完整生产后台。

它完成以下闭环：

```text
读取来源配置
  -> 读取主题 Skill 配置
  -> 抓取 API/RSS/HTML
  -> 解析成标准 item
  -> 按关键词和规则分 P0/P1/P2
  -> 输出 Alert Card JSON
```

## 2. 目录结构

```text
pyproject.toml
README.md
config/crawler/sources.yml
config/crawler/skills/*.yml
src/hk_site_safety_crawler/
  __init__.py
  cards.py
  cli.py
  config.py
  fetcher.py
  models.py
  parsers.py
  rules.py
  runner.py
tests/test_rules_and_cards.py
docs/HK_SITE_SAFETY_CRAWLER_CODE_HANDOFF.md
```

## 3. 核心模块说明

### `models.py`

定义系统内部标准数据结构：

- `SourceConfig`
- `TopicSkill`
- `FetchedDocument`
- `NormalizedItem`
- `Classification`
- `AlertCard`

后续接数据库时，建议直接按这些模型设计表结构。

### `config.py`

负责读取：

- `config/crawler/sources.yml`
- `config/crawler/skills/*.yml`

用户后续修改关键词、来源范围和 P0/P1/P2 规则时，主要改 `config/crawler/skills/*.yml`。

### `fetcher.py`

负责 HTTP 抓取。

当前支持：

- 普通 URL 抓取
- `data.gov.hk` 新闻公报 API 当日查询

后续建议补充：

- robots.txt 检查
- backoff retry
- source health 记录
- conditional request：`ETag` / `Last-Modified`

### `parsers.py`

负责把不同来源统一成 `NormalizedItem`。

当前支持：

- `hko_warnsum`
- `hko_warning_info`
- `rss_generic`
- `gov_press_api`
- generic HTML link parser

后续需要补充：

- 劳工处职安警示专用 parser
- 屋宇署 Practice Notes parser
- 房屋署工地安全提示 parser
- 发展局技术通告 parser
- CIC 安全讯息 parser
- PDF 下载和文本抽取
- 媒体详情页 parser

### `rules.py`

负责 Skill 规则匹配。

匹配顺序：

1. 检查 source 是否在 topic scope 内。
2. 检查 exclude keywords。
3. 检查 include keywords。
4. 先判 P0。
5. 再判 P1。
6. 否则默认 P2。

媒体来源 `trust_level = media_lead` 时，默认 `requires_human_review = true`。

### `cards.py`

负责生成可渲染卡片。

输出包含：

- 标题
- 摘要
- 来源
- 发布/检测时间
- 命中关键词
- 分级原因
- 建议行动
- 原文链接
- 确认链接
- `render_payload`

前端、Email、Teams、Telegram/WhatsApp 可共用 `render_payload` 做不同渠道渲染。

### `runner.py`

串起完整流程，提供 `run_once()`。

生产环境中，scheduler 或 Celery worker 应调用这个逻辑，或将其拆分为 fetch/parse/classify/card 多个任务。

### `cli.py`

命令行入口。

示例：

```bash
python -m hk_site_safety_crawler.cli --source hko_warnsum --max-cards 10
```

输出：

```text
output/alert_cards.json
```

## 4. Alert Card 输出格式

输出 JSON 顶层结构：

```json
{
  "schema_version": 1,
  "card_count": 1,
  "error_count": 0,
  "cards": [],
  "errors": []
}
```

单张卡片结构：

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
  "ack_url": "https://internal/alerts/abc/ack",
  "render_payload": {}
}
```

## 5. 本地运行

安装：

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
```

Windows 注意：

如果项目路径包含中文字符，`pip install -e ".[dev]"` 可能因 setuptools editable install 的 `.pth` 编码问题失败。建议生产/开发仓库 clone 到英文路径，例如：

```text
C:\work\item
```

如果暂时不能移动目录，可以直接安装依赖并用 `PYTHONPATH=src` 运行：

```bash
pip install beautifulsoup4 feedparser httpx lxml pypdf pyyaml pytest ruff
$env:PYTHONPATH = "src"
```

运行测试：

```bash
pytest
```

运行爬虫：

```bash
python -m hk_site_safety_crawler.cli --max-cards 20
```

仅运行天文台警告摘要：

```bash
python -m hk_site_safety_crawler.cli --source hko_warnsum --max-cards 20
```

带确认链接：

```bash
python -m hk_site_safety_crawler.cli --source gov_press_rss --ack-base-url https://internal.example.com/alerts
```

## 6. 上传到 GitHub 分支

目标仓库：

```text
https://github.com/ZTX-666/item
```

如果当前目录还不是 git repo，建议开发者执行：

```bash
git init
git remote add origin https://github.com/ZTX-666/item.git
git checkout -b hk-site-safety-crawler-mvp
git add .
git commit -m "Add Hong Kong site safety crawler MVP"
git push -u origin hk-site-safety-crawler-mvp
```

如果仓库已经存在并已 clone：

```bash
git checkout -b hk-site-safety-crawler-mvp
git add .
git commit -m "Add Hong Kong site safety crawler MVP"
git push -u origin hk-site-safety-crawler-mvp
```

然后在 GitHub 上从 `hk-site-safety-crawler-mvp` 创建 PR。

## 7. 下一步开发建议

优先级 1：

- 加 PostgreSQL 表：`sources`、`raw_fetches`、`items`、`classifications`、`alerts`。
- 加 scheduler：Celery Beat 或 APScheduler。
- 加去重入库：按 `content_hash` 和 URL 去重。
- 加 P0 通知：Email 或 Teams。

优先级 2：

- 完成官方 HTML/PDF 专用 parser。
- 实现 PDF 下载、hash、文本抽取。
- 记录 source health。
- 网页结构变化报警。

优先级 3：

- 接入媒体详情页。
- 媒体与官方消息交叉核验。
- LLM 摘要、实体抽取、建议行动。
- 后台列表和告警确认页面。

## 8. 重要约束

- 不要把用户关键词写死在 parser 里。
- P0 必须由规则决定，不让大模型单独决定。
- 媒体来源只作为线索，不作为官方事实。
- 不抓登录、付费、验证码或需要绕过反爬的内容。
- 不保存或转发媒体全文。
