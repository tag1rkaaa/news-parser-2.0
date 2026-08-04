from __future__ import annotations

import hashlib
import logging
from typing import Any, Self

import redis.asyncio as aioredis
from itemadapter import ItemAdapter
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import DropItem

from newsparser.core.settings_loader import get_settings

log = logging.getLogger(__name__)


class RedisDedupPipeline:
    """Async Redis-backed deduplication.

    One client per crawler, async via redis.asyncio (no reactor blocking).
    Uses `SET key NX EX <ttl>` for atomic "first sight" check; the key is a
    16-byte blake2b hash of the link to keep memory bounded.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._redis: aioredis.Redis | None = None

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        instance = cls()
        crawler.signals.connect(instance.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(instance.spider_closed, signal=signals.spider_closed)
        return instance

    async def spider_opened(self, spider: Spider) -> None:
        password = (
            self._settings.redis_password.get_secret_value()
            if self._settings.redis_password
            else None
        )
        self._redis = aioredis.from_url(
            f"redis://{self._settings.redis_host}:{self._settings.redis_port}/{self._settings.redis_db}",
            password=password,
            decode_responses=True,
            max_connections=20,
        )

    async def spider_closed(self, spider: Spider) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def process_item(self, item: Any, spider: Spider) -> Any:
        adapter = ItemAdapter(item)
        link = adapter.get("link")
        if not link:
            return item  # validation pipeline (earlier) catches this

        key = self._key(str(link))
        if self._redis is None:
            log.warning("redis_pipeline_not_initialized")
            return item
        is_new = await self._redis.set(
            key, "1", nx=True, ex=self._settings.redis_dedup_ttl_seconds
        )
        if not is_new:
            spider.crawler.stats.inc_value("newsparser/items_dropped/dup")
            raise DropItem("dup")
        return item

    @staticmethod
    def _key(link: str) -> str:
        digest = hashlib.blake2b(link.encode("utf-8"), digest_size=16).hexdigest()
        return f"newsparser:seen:{digest}"
