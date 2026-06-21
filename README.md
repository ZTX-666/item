# HK Site Safety Crawler MVP

This project contains a core crawler MVP for Hong Kong site safety monitoring.

It reads source definitions from `config/crawler/sources.yml`, reads monitoring topic skills from `config/crawler/skills/*.yml`, fetches configured sources, classifies matched items into P0/P1/P2, and writes alert cards as JSON.

## Quick Start

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -e ".[dev]"
```

If editable install fails on Windows because the project path contains Chinese characters, either clone the repository to an ASCII-only path or run with `PYTHONPATH=src` after installing dependencies directly:

```bash
pip install beautifulsoup4 feedparser httpx lxml pypdf pyyaml pytest ruff
$env:PYTHONPATH = "src"
```

Run one source:

```bash
python -m hk_site_safety_crawler.cli --source hko_warnsum --max-cards 10
```

Run all enabled sources:

```bash
python -m hk_site_safety_crawler.cli --max-cards 50
```

Output:

```text
output/alert_cards.json
```

## Important Files

- `config/crawler/sources.yml`: source registry
- `config/crawler/skills/*.yml`: user-editable monitoring topics
- `src/hk_site_safety_crawler/`: crawler core
- `docs/HK_SITE_SAFETY_CRAWLER_USER_HANDOFF.md`: detailed handoff for new teammates
- `docs/HK_SITE_SAFETY_CRAWLER_CODE_HANDOFF.md`: developer handoff
- `docs/HK_SITE_SAFETY_CRAWLER_SKILL_HANDOFF.md`: skill/config handoff

## Current Scope

Implemented:

- YAML config loading
- HTTP fetcher
- HKO JSON parser
- RSS parser
- `data.gov.hk` press release API parser
- generic HTML link parser
- rule-based P0/P1/P2 classification
- alert card JSON output

Not implemented yet:

- persistent database
- scheduler worker
- notification delivery
- PDF text extraction flow
- media detail page extraction
- robots.txt checker
- LLM summary integration
