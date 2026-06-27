# URL Fetch

抓取公开网页 URL，提取正文、标题与关键链接。

## Rules

- 仅抓取 http/https 公开页面，禁止 localhost 与内网地址。
- 默认返回可读正文摘要，不返回完整 HTML 源码。
- 对媒体页面只提取标题与摘要段落，完整内容需用户打开原链接确认。
- 抓取结果用于风险监测、制度参考或项目背景调研时，必须标注来源 URL。

## Preferred Tools

- `fetch_url_content`

## Boundaries

- 不抓取需要登录的页面
- 不批量爬取同一站点
