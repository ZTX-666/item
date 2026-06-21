# Daily Risk Briefing

生成每日安全风险简报，覆盖香港天气、香港工伤意外新闻、项目内部隐患和待整改事项。

## Rules

- 外部天气和新闻属于内置模块“晴晴外部风险监测”，不是第三方插件。
- 简报应分为天气预警、外部事故警示、项目内部重点风险、今日建议动作。
- 如果涉及向群组推送，必须先让用户确认发送范围和内容。

## Tools

- `fetch_hko_weather`
- `fetch_hk_safety_updates`
- `fetch_hk_industrial_news`
- `persist_external_risk_items`
- `summarize_external_risks`
- `draft_daily_risk_briefing`
- `send_group_message`

## Config

来源、关键词和媒体抓取边界放在同目录 `config.json`。用户可通过 Skill 配置修改启用来源和关键词；媒体来源只抓公开列表的标题、链接和短摘要，不抓全文、不绕过登录或付费墙。
