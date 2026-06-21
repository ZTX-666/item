from __future__ import annotations

from datetime import datetime
from typing import Iterable

import httpx

from .models import FetchedDocument, SourceConfig


class Fetcher:
    def __init__(self, user_agent: str | None = None, timeout_seconds: int = 20) -> None:
        headers = {"User-Agent": user_agent or "C-SMART Site Safety Monitor/0.1"}
        self.client = httpx.Client(headers=headers, follow_redirects=True, timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def fetch(self, source: SourceConfig) -> list[FetchedDocument]:
        if source.parser == "gov_press_api":
            return list(self._fetch_gov_press_api(source))
        return [self._fetch_url(source.url, source)]

    def _fetch_url(self, url: str, source: SourceConfig) -> FetchedDocument:
        response = self.client.get(url)
        return FetchedDocument(
            source=source,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            text=response.text,
            fetched_at=datetime.now().astimezone(),
            final_url=str(response.url),
        )

    def _fetch_gov_press_api(self, source: SourceConfig) -> Iterable[FetchedDocument]:
        today = datetime.now().strftime("%Y%m%d")
        query_defaults = source.options.get("query_defaults", {})
        official_codes = source.options.get("official_codes", {})

        for official_code in official_codes.values():
            params = {
                "start": today,
                "end": today,
                "official": official_code,
                **query_defaults,
            }
            response = self.client.get(source.url, params=params)
            yield FetchedDocument(
                source=source,
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                text=response.text,
                fetched_at=datetime.now().astimezone(),
                final_url=str(response.url),
            )
