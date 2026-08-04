from __future__ import annotations

from typing import Any, Self

from scrapy import Spider
from scrapy.crawler import Crawler

from newsparser.pipelines.dedup import RedisDedupPipeline
from newsparser.pipelines.keyword_filter import KeywordFilterPipeline
from newsparser.pipelines.notify import NotifyPipeline
from newsparser.pipelines.validation import PydanticValidationPipeline


class _BaseLegacyChain:
    """Runs the new pipeline chain inside a single legacy class so that the
    25 existing spiders, which override ITEM_PIPELINES with a single class
    name, get the full new behavior without being edited.
    """

    _is_federal: bool = False

    def __init__(self) -> None:
        self._validation = PydanticValidationPipeline()
        self._keyword = KeywordFilterPipeline()
        self._dedup = RedisDedupPipeline()
        self._notify = NotifyPipeline()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        instance = cls()
        instance._dedup = RedisDedupPipeline.from_crawler(crawler)
        instance._notify = NotifyPipeline.from_crawler(crawler)
        return instance

    async def process_item(self, item: Any, spider: Spider) -> Any:
        # Force feed_type so KeywordFilter activates only for federal sites.
        spider.feed_type = "federal" if self._is_federal else "local"  # type: ignore[attr-defined]
        item = self._validation.process_item(item, spider)
        item = self._keyword.process_item(item, spider)
        item = await self._dedup.process_item(item, spider)
        item = await self._notify.process_item(item, spider)
        return item


class LegacyLocalChain(_BaseLegacyChain):
    """Drop-in for the original `RedisPipeline` (local spiders)."""

    _is_federal = False


class LegacyFederalChain(_BaseLegacyChain):
    """Drop-in for the original `KeyWordsCheck` (federal spiders)."""

    _is_federal = True


class NewsparserPipeline:
    """The original no-op pipeline kept as an alias — does nothing."""

    def process_item(self, item: Any, spider: Spider) -> Any:
        return item
