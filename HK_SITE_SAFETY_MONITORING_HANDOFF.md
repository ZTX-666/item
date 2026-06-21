# 香港地盘安全、天气、政策与工业新闻监听系统交接文档

## 1. 项目背景

本系统面向香港地盘工作的项目经理、安全经理、工程经理和承建商管理团队，用脚本持续监听以下信息：

- 香港工业界 / 建造业工业意外新闻
- 香港天文台恶劣天气警告
- 劳工处、屋宇署、房屋署 / 房委会、发展局、建造业议会等机构的新政策、新制度、新通告
- 香港本地媒体对工业意外、地盘安全、承建商事故、判罚和监管行动的报道

系统目标不是取代官方判断，而是建立一个「早发现、快分级、可追踪、有人确认」的信息雷达。官方来源作为事实基准，媒体来源作为早期线索，所有严重事故和制度变化都需要进入通知和确认闭环。

## 2. 监听范围总览

系统分为四条主线：

1. 工业意外监听
   - 来源：政府新闻公报、劳工处职安警示、媒体报道
   - 目标：发现致命 / 严重工伤、暂时停工通知书、承建商检控、判罚、复工条件

2. 恶劣天气监听
   - 来源：香港天文台 Open Data API / RSS
   - 目标：实时发现八号风球、红雨、黑雨、雷暴、山泥倾泻、酷热、火灾危险等会影响地盘作业的天气信号

3. 政策制度监听
   - 来源：劳工处、屋宇署、房屋署 / 房委会、发展局、建造业议会
   - 目标：发现新通告、新作业备考、表格变更、承建商监管制度、智慧工地安全系统要求

4. 媒体线索监听
   - 来源：香港01、星岛头条 / 星岛日报、明报、东方日报、香港商报等
   - 目标：在官方新闻稿发布前尽早发现事故，并补充现场、地盘、承建商、工序、历史背景等信息

## 3. 必须监听的官方来源

### 3.1 政府新闻公报 RSS

- 名称：香港特区政府新闻公报 RSS
- URL: `https://www.info.gov.hk/gia/rss/general_zh.xml`
- 类型：RSS
- 优先级：最高
- 建议频率：2-5 分钟
- 用途：
  - 捕捉劳工处、发展局、屋宇署、房屋署等政府部门新闻稿
  - 捕捉致命工作意外、暂时停工通知书、承建商监管行动、政策公布

监听字段：

- `title`
- `link`
- `pubDate`
- `description`
- 正文详情页内容
- 发布部门
- 是否包含 PDF / 附件链接

关键词：

- `致命工作意外`
- `严重工作意外`
- `工业意外`
- `工伤`
- `劳工处高度关注`
- `暂时停工通知书`
- `承建商`
- `分判商`
- `发展局`
- `暂停投标`
- `屋宇署`
- `房屋署`
- `工务工程`
- `检控`
- `定罪`
- `复工`

处理规则：

- 命中 `致命工作意外`、`暂时停工通知书`、`暂停投标` 时，直接列为 P0。
- 命中劳工处但未有伤亡细节时，列为 P1，等待详情页解析。
- 命中发展局、承建商监管、工务工程安全制度时，列为 P1。

### 3.2 劳工处职安警示

- 名称：劳工处职安警示
- URL: `https://www.labour.gov.hk/tc/news/work_safety_alert.htm`
- 类型：HTML + PDF
- 优先级：最高
- 建议频率：30-60 分钟

用途：

- 职安警示通常在严重或致命事故后发布，说明事故概要和预防措施。
- 对地盘经理最有执行价值，适合转化为检查清单。

需要监听：

- 主索引页是否新增年份链接
- 年份页是否新增 PDF / 文字版
- PDF 标题、发布日期、事故类别
- PDF 正文中的预防措施

重点工序关键词：

- `高处工作`
- `棚架`
- `竹棚架`
- `吊运`
- `天秤`
- `叉式起重车`
- `流动式起重机`
- `密闭空间`
- `触电`
- `防火`
- `拆卸`
- `升降工作台`
- `物件堕下`

输出字段：

- `alert_title`
- `alert_year`
- `pdf_url`
- `accident_type`
- `work_process`
- `hazard_type`
- `recommended_precautions`
- `source_published_at`

### 3.3 香港天文台天气警告 API

#### 3.3.1 警告摘要 API

- 名称：香港天文台 Weather Warning Summary
- URL: `https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc`
- 类型：JSON API
- 优先级：最高
- 建议频率：1-3 分钟

监听字段：

- `code`
- `name`
- `actionCode`
- `issueTime`
- `expireTime`
- `updateTime`

重点 warning code：

- `WTCSGNL`: 热带气旋警告信号
- `WRAIN`: 暴雨警告信号
- `WTS`: 雷暴警告
- `WL`: 山泥倾泻警告
- `WFNTSA`: 新界北部水浸特别报告
- `WMSGNL`: 强烈季候风信号
- `WHOT`: 酷热天气警告
- `WCOLD`: 寒冷天气警告
- `WFIRE`: 火灾危险警告

#### 3.3.2 警告详情 API

- 名称：香港天文台 Weather Warning Information
- URL: `https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warningInfo&lang=tc`
- 类型：JSON API
- 优先级：最高
- 建议频率：1-3 分钟

监听字段：

- `warningStatementCode`
- `subtype`
- `contents`
- `updateTime`

地盘行动建议：

- 八号或以上风球：P0，通知暂停户外高危工序、棚架、吊运、天秤、外墙作业。
- 黑雨 / 红雨：P0，通知检查排水、斜坡、临时工程、露天电力装置。
- 雷暴：P1 或 P0，若有吊运、高空、金属棚架、天秤操作则升 P0。
- 山泥倾泻 / 新界北部水浸：P0/P1，根据项目位置判断。
- 酷热天气：P1，通知热压力、饮水、休息、轮班、通风措施。
- 火灾危险：P1，结合防火、热工序、棚架保护网、易燃物储存。

### 3.4 屋宇署通告函件

- 名称：屋宇署 Circular Letters
- URL: `https://www.bd.gov.hk/tc/resources/codes-and-references/practice-notes-and-circular-letters/index_circulars.html`
- 类型：HTML + PDF
- 优先级：高
- 建议频率：1-3 小时

监听内容：

- 新通告函件
- 既有通告标题变更
- PDF 链接变更
- 年份分组新增

重点关键词：

- `棚架`
- `竹棚架`
- `阻燃`
- `防火`
- `保护网`
- `保护幕`
- `防水油布`
- `塑胶帆布`
- `天秤`
- `塔式起重机`
- `台风`
- `雨季`
- `建筑地盘安全`
- `注册承建商`
- `小型工程`
- `表格`

输出字段：

- `title`
- `year`
- `pdf_url`
- `published_or_detected_at`
- `topic_tags`
- `affected_roles`
- `effective_date`
- `summary`

### 3.5 屋宇署专业人士角

- 名称：Corner for AP, RSE, RGE, RI and RC
- URL: `https://www.bd.gov.hk/tc/resources/corner-for-rbp-rc/index.html`
- 类型：HTML + PDF
- 优先级：高
- 建议频率：1-3 小时

监听内容：

- 新 / 修订 Practice Notes
- 注册承建商通告摘要
- 指定表格更新
- 对认可人士、注册结构工程师、注册岩土工程师、注册检验人员、注册承建商的要求

重点分类：

- `PNAP`
- `PNRC`
- `PNRI`
- `APP`
- `ADM`
- `MW`
- `注册承建商`
- `授权签署人`
- `技术合格人士`

### 3.6 屋宇署 Practice Notes 索引

- 名称：屋宇署 Practice Notes and Circular Letters Index
- URL: `https://www.bd.gov.hk/tc/resources/codes-and-references/practice-notes-and-circular-letters/index.html`
- 类型：HTML + PDF
- 优先级：高
- 建议频率：1-3 小时

监听内容：

- PNAP 正式文件修订
- PNRC 正式文件修订
- PNRI 正式文件修订
- 作业备考编号、标题、PDF、版本日期变化

触发规则：

- 新增 / 修订 PNAP、PNRC、PNRI：P1
- 涉及棚架、防火、吊运、天秤、注册承建商、小型工程：P0/P1

### 3.7 房委会 / 房屋署工地安全提示

- 名称：香港房屋委员会及房屋署工地安全提示
- URL: `https://www.housingauthority.gov.hk/mini-site/site-safety/tc/publications/alerts/index.html`
- 类型：HTML + PDF / 附件
- 优先级：高
- 建议频率：1-3 小时

监听内容：

- 房屋署工地安全提示
- 房屋署转发的劳工处、屋宇署、CIC 安全消息
- 承建商提醒
- 会议、研讨会、安全策略资料

重点关键词：

- `工地安全`
- `吊运安全`
- `防火`
- `棚架`
- `酷热`
- `恶劣天气`
- `天秤`
- `安全通道`
- `关键项目`
- `房屋委员会新工程工地安全策略`

### 3.8 房委会 RSS 频道

- 名称：房委会 RSS 频道索引
- URL: `https://www.housingauthority.gov.hk/tc/global-elements/rss-feed/index.html`
- 类型：HTML 索引 / RSS
- 优先级：中高
- 建议频率：15-30 分钟

监听内容：

- 新闻稿
- 招标公告：工程及服务合约
- 商业楼宇招标公告

注意：

- 页面本身可能不直接暴露所有 RSS URL。开发时应先解析页面内隐藏链接；若无法取得稳定 RSS，则退回 HTML 差异监听。

## 4. 必须加入的官方补充来源

### 4.1 发展局工务技术通告

- 名称：Development Bureau Technical Circulars (Works)
- URL: `https://www.devb.gov.hk/tc/publications_and_press_releases/technical_circulars/works/index.html`
- 类型：HTML + PDF
- 优先级：高
- 建议频率：3-6 小时

监听主题：

- 智慧工地安全系统
- 工务合约安全要求
- 承建商监管制度
- 工务工程采购要求
- 工程合约条款
- 安全审核
- 承建商名册
- 暂停投标

重点关键词：

- `Smart Site Safety System`
- `智慧工地安全系统`
- `SSSS`
- `site safety`
- `contractor management`
- `Contractor Management Handbook`
- `suspension from tendering`
- `public works contracts`
- `approved contractors`
- `safety audit`
- `improvement action plan`

告警规则：

- 涉及强制要求、合约条款、安全系统、承建商监管：P1。
- 涉及暂停投标、承建商名册移除、严重事故后的监管行动：P0。

### 4.2 发展局新闻稿 / 政府新闻公报

- 来源：政府新闻公报 RSS
- URL: `https://www.info.gov.hk/gia/rss/general_zh.xml`
- 类型：RSS + HTML
- 优先级：高

监听主题：

- 发展局对承建商或分判商采取规管行动
- 暂停投标
- 要求独立安全审核
- 要求提交改善行动计划
- 工务工程安全要求

### 4.3 建造业议会 CIC Safety Alerts / Messages

- 名称：Construction Industry Council Safety Alerts / Messages
- URL: `https://www.cic.hk/tc/safety/alerts-messages`
- 类型：HTML + PDF
- 优先级：中高
- 建议频率：1-3 小时

监听主题：

- 行业安全讯息
- 棚架
- 防火
- 吊运
- 酷热工作
- Life First
- 智慧工地安全系统标签计划
- 安全训练课程
- 设计安全

重点关键词：

- `安全讯息`
- `安全提示`
- `棚架`
- `防火`
- `吊运`
- `酷热天气`
- `生命第一`
- `Smart Site Safety System`
- `Safety Message`
- `Safety Alert`

### 4.4 劳工处最新动向

- 名称：劳工处最新动向
- URL: `https://www.labour.gov.hk/tc/news/highlights.php`
- 类型：HTML
- 优先级：中
- 建议频率：3-6 小时

监听主题：

- 职安健制度
- 专题网页
- 宣传活动
- 执法重点
- 新服务 / 新应用
- 安全计划

重点关键词：

- `职业安全`
- `职安健`
- `安全健康`
- `专题网页`
- `建造业`
- `安全警示`
- `系统性的安全警示`
- `密闭空间`
- `投诉热线`

## 5. 媒体工业界新闻监听来源

媒体来源的定位是「早期线索」。媒体报道可能快于官方新闻稿，但也可能存在信息不完整或未经确认的问题。因此系统必须标注来源类型，并尽量与政府新闻公报、劳工处、警方、消防、屋宇署、房屋署、发展局消息交叉核验。

### 5.1 香港01

- 名称：香港01
- 推荐入口：`https://www.hk01.com/search/%E5%B7%A5%E6%A5%AD%E6%84%8F%E5%A4%96`
- 类型：搜索页 / 分类页 HTML
- 优先级：中高
- 建议频率：5-10 分钟

监听内容：

- 突发工业意外
- 地盘工伤
- 承建商回应
- 医管局 / 房署 / 劳工处回应
- 工权会回应

抽取字段：

- `title`
- `url`
- `published_at`
- `location`
- `site_name`
- `contractor`
- `subcontractor`
- `injury_or_fatality`
- `accident_type`
- `work_process`
- `official_response`

关键词：

- `工业意外`
- `地盘`
- `夺命`
- `工伤`
- `工友`
- `承建商`
- `分判商`
- `劳工处`
- `暂时停工通知书`

### 5.2 星岛头条 / 星岛日报

- 名称：星岛头条 / 星岛日报
- 推荐入口：`https://www.stheadline.com/search/%E5%B7%A5%E6%A5%AD%E6%84%8F%E5%A4%96`
- 类型：搜索页 / 分类页 HTML
- 优先级：中高
- 建议频率：5-10 分钟

监听内容：

- 突发工业意外
- 旧案背景
- 承建商牌照 / 换承建商 / 钉牌资料
- 检控和案件进展

抽取字段：

- `title`
- `url`
- `published_at`
- `district`
- `site_name`
- `developer_or_client`
- `main_contractor`
- `historical_accidents`
- `regulatory_context`

### 5.3 明报新闻网

- 名称：明报新闻网
- 推荐入口：`https://news.mingpao.com/ins/%E6%B8%AF%E8%81%9E/web_tc/section/20260621/s00001`
- 类型：即时港闻 / 港闻 HTML
- 优先级：中
- 建议频率：10-15 分钟

监听内容：

- 工业意外
- 地盘工伤
- 裁判法院判刑
- 承建商罚款
- 制度失效描述

特别价值：

- 明报常报道法庭判罚和裁判官对安全制度的描述，适合做事故复盘和承建商风险评分。

### 5.4 东方日报

- 名称：东方日报
- 推荐入口：`https://orientaldaily.on.cc/section/%E8%A6%81%E8%81%9E%E6%B8%AF%E8%81%9E`
- 类型：港闻 HTML
- 优先级：中
- 建议频率：10-15 分钟

监听内容：

- 现场事故
- 警方初步分类
- 救援情况
- 伤亡情况
- 医管局 / 劳工处回应

### 5.5 香港商报

- 名称：香港商报
- 推荐入口：`https://www.hkcd.com/hkcdweb/index.html`
- 类型：新闻 HTML
- 优先级：中
- 建议频率：10-15 分钟

监听内容：

- 劳工处新闻稿转载
- 发展局、房署、屋宇署消息
- 事故和政策报道

### 5.6 可后续扩展的媒体 / 组织来源

后续可加入：

- 香港电台新闻
- TVB 新闻
- Now 新闻
- 有线新闻
- 香港经济日报
- 工业伤亡权益会
- 香港建造业总工会

这些来源可作为第二阶段扩展，不建议第一版全部加入，避免误报和维护成本过高。

## 6. 告警等级设计

### 6.1 P0：立即通知

P0 应在 1-3 分钟内推送给安全经理、项目经理和相关负责人。

触发条件：

- 八号或以上热带气旋警告
- 黑色暴雨警告
- 红色暴雨警告
- 致命工作意外
- 严重工伤且涉及地盘 / 吊运 / 天秤 / 棚架 / 高处工作
- 劳工处发出暂时停工通知书
- 发展局暂停承建商投标
- 屋宇署要求立即行动或涉及注册承建商纪律 / 检控
- 房屋署要求所有承建商全面检查

通知内容必须包括：

- 事件标题
- 来源
- 时间
- 地点
- 涉及部门 / 承建商
- 初步影响
- 建议行动
- 原文链接
- 确认按钮 / 确认链接

### 6.2 P1：重要通知

P1 应在 5-15 分钟内推送。

触发条件：

- 职安警示
- 系统性的安全警示
- 屋宇署 / 房屋署即时安全提示
- 发展局技术通告
- CIC 安全讯息
- 主流媒体确认的严重地盘事故
- 红雨 / 雷暴 / 山泥倾泻 / 酷热天气，对项目作业有影响

### 6.3 P2：每日摘要 / 普通更新

触发条件：

- 作业备考修订
- 表格更新
- 普通政策新闻
- 招标公告
- 未获官方确认的媒体线索
- 一般安全宣传

处理方式：

- 可进入每日摘要
- 不一定即时推送
- 若关键词命中项目名称、承建商名称或当前工序，则升为 P1

## 7. 关键词体系

### 7.1 工业意外关键词

- `致命工作意外`
- `严重工作意外`
- `工业意外`
- `工伤`
- `工殇`
- `工友`
- `死亡`
- `不治`
- `昏迷`
- `被困`
- `坠下`
- `堕下`
- `高处堕下`
- `被夹`
- `被压`
- `物件堕下`
- `触电`
- `吊运`
- `天秤`
- `塔式起重机`
- `棚架`
- `竹棚`
- `密闭空间`
- `叉式起重车`
- `升降工作台`

### 7.2 政府监管关键词

- `暂时停工通知书`
- `停工`
- `复工`
- `检控`
- `传票`
- `定罪`
- `罚款`
- `暂停投标`
- `承建商名册`
- `除名`
- `注册承建商`
- `纪律处分`
- `独立安全审核`
- `改善行动计划`
- `安全管理系统`

### 7.3 天气关键词

- `八号`
- `九号`
- `十号`
- `热带气旋`
- `红色暴雨`
- `黑色暴雨`
- `雷暴`
- `山泥倾泻`
- `水浸`
- `强烈季候风`
- `酷热`
- `火灾危险`
- `寒冷`

### 7.4 政策制度关键词

- `新措施`
- `新制度`
- `修订`
- `作业备考`
- `通告函件`
- `技术通告`
- `智慧工地安全系统`
- `Smart Site Safety System`
- `SSSS`
- `PNAP`
- `PNRC`
- `PNRI`
- `表格`
- `小型工程`
- `认可人士`
- `注册结构工程师`
- `注册承建商`

## 8. 推荐系统架构

### 8.1 总体架构

建议使用以下架构：

- 采集层：Python crawler workers
- 队列层：Redis Queue / Celery / APScheduler
- 数据层：PostgreSQL
- 文件层：本地对象存储或 S3-compatible storage
- 解析层：HTML parser、RSS parser、PDF text extractor、OCR fallback
- 分类层：规则引擎 + 可选 LLM 摘要
- 通知层：Email、Teams、Telegram、WhatsApp Business
- 后台层：FastAPI + React / Next.js
- 运维层：Docker Compose，后续可迁移 Kubernetes

### 8.2 推荐技术栈

第一版：

- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Celery 或 APScheduler
- BeautifulSoup / lxml
- feedparser
- httpx
- pypdf / pdfplumber
- Playwright：只用于需要渲染的媒体页面
- SQLAlchemy / Alembic
- Docker Compose

可选：

- OpenAI / Azure OpenAI / 本地 LLM 用于摘要、分类、行动建议
- Sentry 用于错误追踪
- Grafana / Prometheus 用于监控

### 8.3 采集流程

1. Scheduler 读取 source 配置。
2. 对每个 source 发起 HTTP 请求。
3. 根据类型解析：
   - RSS: `feedparser`
   - JSON API: `httpx + json`
   - HTML: `BeautifulSoup`
   - PDF: 下载后抽取文本
4. 生成标准化 item。
5. 用 URL、标题、发布时间、内容 hash 去重。
6. 保存原始内容和解析内容。
7. 执行关键词匹配和分级。
8. 生成摘要和建议行动。
9. 创建 alert。
10. 推送通知。
11. 等待负责人确认。

## 9. 数据库设计建议

### 9.1 `sources`

用于存放监听源配置。

字段：

- `id`
- `name`
- `category`: `official`, `weather`, `media`, `policy`, `industry`
- `url`
- `source_type`: `rss`, `json_api`, `html`, `pdf_index`
- `priority`
- `poll_interval_seconds`
- `enabled`
- `parser_name`
- `created_at`
- `updated_at`

### 9.2 `raw_fetches`

用于保存每次抓取结果。

字段：

- `id`
- `source_id`
- `fetched_at`
- `status_code`
- `content_hash`
- `raw_content_path`
- `error_message`
- `duration_ms`

### 9.3 `items`

用于保存标准化新闻 / 通告 / 天气警告。

字段：

- `id`
- `source_id`
- `external_id`
- `title`
- `url`
- `published_at`
- `detected_at`
- `content_text`
- `content_hash`
- `language`
- `department`
- `source_reliability`
- `item_type`: `accident`, `weather`, `policy`, `media_report`, `circular`, `safety_alert`
- `created_at`

### 9.4 `item_entities`

用于保存抽取实体。

字段：

- `id`
- `item_id`
- `entity_type`: `location`, `contractor`, `department`, `hazard`, `weather_warning`, `site`, `person_role`
- `entity_value`
- `confidence`

### 9.5 `classifications`

字段：

- `id`
- `item_id`
- `severity`: `P0`, `P1`, `P2`
- `category`: `industrial_accident`, `weather`, `policy`, `site_action`, `media_lead`
- `matched_keywords`
- `reason`
- `requires_human_review`
- `created_at`

### 9.6 `alerts`

字段：

- `id`
- `item_id`
- `severity`
- `title`
- `message`
- `recommended_action`
- `status`: `new`, `sent`, `acknowledged`, `resolved`, `ignored`
- `assigned_to`
- `created_at`
- `sent_at`
- `acknowledged_at`
- `resolved_at`

### 9.7 `notifications`

字段：

- `id`
- `alert_id`
- `channel`: `email`, `teams`, `telegram`, `whatsapp`
- `recipient`
- `status`
- `sent_at`
- `error_message`

### 9.8 `source_health`

字段：

- `id`
- `source_id`
- `checked_at`
- `is_healthy`
- `last_success_at`
- `last_error`
- `consecutive_failures`

## 10. 解析器设计

### 10.1 RSS 解析器

适用：

- 政府新闻公报 RSS
- 房委会 RSS
- 后续可接入其他 RSS

输出：

- `title`
- `link`
- `published_at`
- `summary`
- `source`

### 10.2 JSON API 解析器

适用：

- 香港天文台 API

输出：

- `warning_code`
- `warning_name`
- `action_code`
- `issue_time`
- `expire_time`
- `details`

### 10.3 HTML 列表页解析器

适用：

- 劳工处最新动向
- 劳工处职安警示
- 屋宇署通告
- 房屋署工地安全提示
- 媒体搜索页

要求：

- 提取列表中的标题、URL、日期
- 若列表无日期，则用 `detected_at`
- 对每个新 URL 进入详情页抓取

### 10.4 PDF 解析器

适用：

- 劳工处职安警示
- 屋宇署通告
- 发展局技术通告
- CIC 安全讯息

要求：

- 下载 PDF
- 保存文件 hash
- 抽取文本
- 若文本为空，进入 OCR 队列
- 抽取标题、发布日期、编号、有效日期、关键词

### 10.5 媒体页面解析器

适用：

- 香港01
- 星岛
- 明报
- 东方
- 香港商报

要求：

- 优先使用搜索页 / 分类页
- 必须设置合理 User-Agent
- 遵守 robots.txt 和网站条款
- 控制请求频率
- 如果页面需要 JS 渲染，再用 Playwright
- 不要绕过登录、付费墙、验证码或反爬机制

## 11. 交叉核验规则

### 11.1 媒体与官方关联

当媒体报道命中工业意外，应尝试在 24 小时内关联：

- 政府新闻公报
- 劳工处新闻稿
- 劳工处职安警示
- 警方 / 消防公开信息
- 房屋署 / 医管局 / 发展局回应

关联条件：

- 地点相同
- 日期相近
- 伤亡人数相同
- 承建商相同
- 工序 / 事故类型相同

### 11.2 可信度分级

- A 级：政府 / 官方来源
- B 级：主流媒体且有官方回应
- C 级：主流媒体但未有官方回应
- D 级：社交媒体 / 未核实线索

第一版建议只做 A、B、C，暂不接入 D。

### 11.3 升级规则

- 媒体 C 级报道若出现 `死亡`、`不治`、`昏迷`、`被困`，先列 P1。
- 若同一事件被两家或以上主流媒体报道，升 P1。
- 若官方确认，按官方内容重新定级，可能升 P0。

## 12. 通知模板

### 12.1 P0 工业意外模板

标题：

`[P0][工业意外] {标题}`

正文：

```text
事件：{title}
来源：{source_name}
时间：{published_at}
地点：{location}
涉及单位：{contractor_or_department}
事故类型：{accident_type}
伤亡情况：{injury_or_fatality}

系统判断：{classification_reason}
建议行动：
1. 通知项目经理和安全经理。
2. 检查本项目是否有相同工序或类似风险。
3. 如涉及吊运/棚架/高处/天秤，安排即时复查。
4. 等待或查阅官方后续通告。

原文：{url}
请确认已读：{ack_url}
```

### 12.2 P0 天气模板

标题：

`[P0][恶劣天气] {warning_name}`

正文：

```text
警告：{warning_name}
代码：{warning_code}
发出时间：{issue_time}
更新时间：{update_time}

建议行动：
1. 检查是否需要暂停户外高危工序。
2. 检查棚架、天秤、临时结构、排水、电力装置。
3. 通知现场负责人确认执行天气应变程序。

详情：{url}
请确认已读：{ack_url}
```

### 12.3 P1 政策制度模板

标题：

`[P1][政策/通告] {标题}`

正文：

```text
文件：{title}
来源：{source_name}
发布时间：{published_at}
影响对象：{affected_roles}

摘要：
{summary}

建议行动：
1. 由安全经理/工程经理阅读原文。
2. 判断是否影响当前工程、承建商或分判商。
3. 如涉及新表格、新检查要求或强制措施，更新项目内部流程。

原文：{url}
```

## 13. 后台功能需求

### 13.1 首页仪表板

显示：

- 今日 P0/P1/P2 数量
- 未确认 P0
- 当前天气警告
- 最近工业意外
- 最近政策通告
- 采集源健康状态

### 13.2 事件列表

筛选：

- 日期
- 来源
- 分类
- 告警等级
- 是否已确认
- 是否官方确认
- 关键词
- 承建商
- 地点

### 13.3 事件详情页

显示：

- 标题
- 来源
- 原文链接
- 正文摘要
- 关键词命中
- 抽取实体
- 关联事件
- 系统建议行动
- 确认记录

### 13.4 来源管理

功能：

- 新增 / 停用来源
- 修改抓取频率
- 修改 parser
- 查看最近抓取状态
- 查看错误日志

### 13.5 关键词管理

功能：

- 新增关键词
- 设置关键词所属分类
- 设置关键词默认等级
- 设置升降级规则

### 13.6 通知设置

功能：

- 按等级配置通知渠道
- 按项目配置负责人
- 设置值班表
- 设置夜间通知规则

## 14. 开发里程碑

### 第 1 周：官方源采集

目标：

- 完成政府 RSS、天文台 API、劳工处、屋宇署、房屋署、发展局、CIC 的基础采集。

交付：

- source 配置表
- RSS 解析器
- JSON API 解析器
- HTML 列表页解析器
- PDF 下载功能
- PostgreSQL 基础表
- 去重逻辑

验收标准：

- 能抓取政府新闻公报 RSS
- 能抓取天文台 warnsum / warningInfo
- 能发现屋宇署 / 劳工处页面新增链接
- 能保存 item 和 raw fetch

### 第 2 周：媒体源采集

目标：

- 加入香港01、星岛、明报、东方、香港商报。

交付：

- 媒体搜索页 / 分类页解析器
- 媒体详情页解析器
- 媒体关键词过滤
- 媒体来源可信度标记

验收标准：

- 能抓取至少 5 个媒体来源
- 能识别工业意外新闻
- 能抽取标题、URL、时间、地点、伤亡关键词

### 第 3 周：分类与交叉核验

目标：

- 建立规则引擎和官方 / 媒体关联逻辑。

交付：

- P0/P1/P2 分级规则
- 关键词体系
- 事件实体抽取
- 媒体与官方事件关联
- 基础摘要生成

验收标准：

- 致命意外能自动 P0
- 天文台八号 / 黑雨能自动 P0
- 媒体未确认意外能标记为媒体线索
- 官方确认后能关联同一事件

### 第 4 周：通知闭环

目标：

- 推送告警，并追踪负责人确认。

交付：

- Email 通知
- Teams / Telegram / WhatsApp Business 至少一种即时通知
- 告警确认链接
- `alerts` 和 `notifications` 表
- 通知失败重试

验收标准：

- P0 能在 1-3 分钟内推送
- 收件人能确认已读
- 后台能看到未确认 P0

### 第 5 周：管理面板

目标：

- 提供可视化后台给安全团队使用。

交付：

- 首页仪表板
- 事件列表
- 事件详情
- 来源管理
- 关键词管理
- 通知设置

验收标准：

- 用户能搜索历史事件
- 用户能查看来源健康
- 用户能修改关键词和通知规则

### 第 6 周起：可靠性强化

目标：

- 提升长期运行稳定性。

交付：

- PDF OCR fallback
- 网页结构变化检测
- source health dashboard
- 每日摘要
- 审计日志
- 错误报警
- 备份策略

验收标准：

- 连续运行 7 天无人工干预
- 来源失败会报警
- 每日摘要能自动发出

## 15. 运维与合规注意事项

### 15.1 请求频率

建议：

- 天文台 API：1-3 分钟
- 政府 RSS：2-5 分钟
- 官方 HTML / PDF：1-6 小时
- 媒体页面：5-15 分钟

注意：

- 媒体来源不要高频抓取。
- 必须设置 User-Agent。
- 必须遵守 robots.txt、网站条款和版权要求。
- 不要绕过验证码、登录、付费墙或反爬机制。

### 15.2 数据保留

建议：

- 原始 HTML / JSON / PDF：保留 180 天
- 标准化 item：长期保留
- 通知记录：至少保留 2 年
- 确认记录：至少保留 2 年

### 15.3 版权与使用

系统内部可以保存用于检索和告警的摘要与链接，但不应对外重新发布媒体全文。通知中建议只包含摘要、短引用和原文链接。

### 15.4 人工确认

所有 P0 必须有人确认。

建议确认角色：

- 项目经理
- 安全经理
- 地盘总管
- 夜间 / 假日值班人

## 16. 第一版 source 配置示例

```yaml
sources:
  - name: gov_press_rss
    display_name: 政府新闻公报 RSS
    category: official
    source_type: rss
    url: https://www.info.gov.hk/gia/rss/general_zh.xml
    poll_interval_seconds: 180
    priority: high
    parser: rss_generic

  - name: hko_warnsum
    display_name: 天文台天气警告摘要
    category: weather
    source_type: json_api
    url: https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warnsum&lang=tc
    poll_interval_seconds: 60
    priority: critical
    parser: hko_warnsum

  - name: hko_warning_info
    display_name: 天文台天气警告详情
    category: weather
    source_type: json_api
    url: https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=warningInfo&lang=tc
    poll_interval_seconds: 60
    priority: critical
    parser: hko_warning_info

  - name: labour_work_safety_alert
    display_name: 劳工处职安警示
    category: official
    source_type: html
    url: https://www.labour.gov.hk/tc/news/work_safety_alert.htm
    poll_interval_seconds: 3600
    priority: high
    parser: labour_work_safety_alert

  - name: bd_circular_letters
    display_name: 屋宇署通告函件
    category: policy
    source_type: html
    url: https://www.bd.gov.hk/tc/resources/codes-and-references/practice-notes-and-circular-letters/index_circulars.html
    poll_interval_seconds: 7200
    priority: high
    parser: bd_circulars

  - name: bd_practice_notes
    display_name: 屋宇署 Practice Notes
    category: policy
    source_type: html
    url: https://www.bd.gov.hk/tc/resources/codes-and-references/practice-notes-and-circular-letters/index.html
    poll_interval_seconds: 7200
    priority: high
    parser: bd_practice_notes

  - name: housing_site_safety_alerts
    display_name: 房委会/房屋署工地安全提示
    category: official
    source_type: html
    url: https://www.housingauthority.gov.hk/mini-site/site-safety/tc/publications/alerts/index.html
    poll_interval_seconds: 7200
    priority: high
    parser: housing_site_safety

  - name: devb_technical_circulars
    display_name: 发展局工务技术通告
    category: policy
    source_type: html
    url: https://www.devb.gov.hk/tc/publications_and_press_releases/technical_circulars/works/index.html
    poll_interval_seconds: 21600
    priority: high
    parser: devb_technical_circulars

  - name: cic_safety_messages
    display_name: 建造业议会安全讯息
    category: industry
    source_type: html
    url: https://www.cic.hk/tc/safety/alerts-messages
    poll_interval_seconds: 7200
    priority: medium_high
    parser: cic_safety_messages

  - name: hk01_industrial_accident_search
    display_name: 香港01 工业意外搜索
    category: media
    source_type: html
    url: https://www.hk01.com/search/%E5%B7%A5%E6%A5%AD%E6%84%8F%E5%A4%96
    poll_interval_seconds: 600
    priority: medium_high
    parser: media_search_generic

  - name: stheadline_industrial_accident_search
    display_name: 星岛头条 工业意外搜索
    category: media
    source_type: html
    url: https://www.stheadline.com/search/%E5%B7%A5%E6%A5%AD%E6%84%8F%E5%A4%96
    poll_interval_seconds: 600
    priority: medium_high
    parser: media_search_generic
```

## 17. 主要风险

### 17.1 网页结构变化

媒体和政府网页结构可能变化，导致解析失败。

缓解：

- source health 监控
- 抓取成功但 item 数量突然为 0 时报警
- 保存 raw HTML 便于调试

### 17.2 媒体误报 / 信息不完整

媒体可能早于官方，但信息可能不完整。

缓解：

- 媒体来源默认标记为线索
- 与官方来源交叉核验
- 通知中明确标注「媒体报道，待官方确认」

### 17.3 PDF 抽取失败

部分 PDF 可能为扫描件。

缓解：

- 先用文本抽取
- 失败则进入 OCR 队列
- OCR 结果标记 confidence

### 17.4 通知疲劳

过多 P1/P2 会导致用户忽略告警。

缓解：

- P0 即时推送
- P1 可批量或按项目相关性推送
- P2 进入每日摘要
- 支持误报标记和关键词调优

## 18. 交付给开发团队的优先级

必须先做：

1. 天文台 API P0 告警
2. 政府新闻公报 RSS
3. 劳工处职安警示
4. 屋宇署通告 / Practice Notes
5. 房屋署工地安全提示
6. P0 通知闭环

第二批：

1. 发展局技术通告
2. CIC 安全讯息
3. 劳工处最新动向
4. 香港01、星岛、明报、东方、香港商报
5. 媒体与官方交叉核验

第三批：

1. OCR
2. 后台管理
3. 每日摘要
4. 承建商风险评分
5. 项目相关性模型

## 19. 最小可行版本 MVP

MVP 范围：

- 采集：
  - 政府新闻公报 RSS
  - 天文台 warnsum / warningInfo
  - 劳工处职安警示
  - 屋宇署通告函件
  - 香港01 / 星岛搜索页

- 分类：
  - 工业意外
  - 恶劣天气
  - 政策通告

- 告警：
  - P0 即时通知
  - P1 每 30 分钟汇总
  - P2 每日摘要

- 后台：
  - 事件列表
  - 事件详情
  - 确认状态

MVP 预计开发周期：

- 2-3 周可上线内部使用
- 6 周可上线完整生产版本

## 20. 结论

该系统的核心价值是把香港地盘经理需要关注的信息从「人工刷网页」变成「系统持续监听、自动分级、及时通知、人工确认」。官方来源确保准确性，媒体来源提高发现速度，天气 API 提供近实时风险信号，政策与通告监听保证项目及时跟上监管要求。

第一版应优先保证 P0 的准确和及时，包括恶劣天气、致命工业意外、暂时停工通知书、承建商暂停投标。后续再逐步加入更复杂的媒体交叉核验、PDF OCR、承建商风险评分和项目相关性分析。
