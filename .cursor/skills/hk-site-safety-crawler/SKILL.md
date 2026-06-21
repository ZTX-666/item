---
name: hk-site-safety-crawler
description: Configure Hong Kong site safety crawler sources, monitoring keywords, severity rules, and topic skills. Use when adding or changing crawler keywords, source scope, P0/P1/P2 rules, or handoff documentation for the site safety monitoring system.
disable-model-invocation: true
---

# HK Site Safety Crawler

Use this skill when the user asks to add, remove, or adjust crawler monitoring topics for Hong Kong site safety, weather, policy, industrial accident, or construction news sources.

## Configuration Files

- Source registry: `config/crawler/sources.yml`
- Topic skills: `config/crawler/skills/*.yml`
- Handoff document: `docs/HK_SITE_SAFETY_CRAWLER_SKILL_HANDOFF.md`

## Workflow

1. Read `config/crawler/sources.yml` to understand available sources.
2. Read the relevant file in `config/crawler/skills/`.
3. Modify only the topic config needed by the request.
4. Keep crawler code source-agnostic; do not hard-code user keywords in parser code.
5. For media sources, keep `store_full_text: false` and treat results as leads requiring review.

## Topic Skill Schema

Each topic skill should include:

```yaml
name: lowercase-topic-name
display_name: 中文显示名称
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

severity_rules:
  p0:
    any_keywords:
      - 致命工作意外
    combined_keywords:
      - [地盘, 死亡]
  p1:
    any_keywords:
      - 职安警示
  p2:
    default_for_matched_items: true
```

## Rules

- Prefer official API/RSS sources before HTML/PDF crawling.
- Keep official sources as fact baseline and media sources as early leads.
- Do not add login-only, paywalled, captcha-protected, or anti-bot bypass flows.
- Do not store or redistribute media full text.
- P0 rules must remain deterministic and auditable.
- Use LLM only for optional summary, entity extraction, and action suggestions.
