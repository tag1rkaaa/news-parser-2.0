from __future__ import annotations

import asyncio
import logging
import ssl
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Literal

import aiohttp
import feedparser
import redis.asyncio as aioredis

from newsparser.core.settings_loader import NewsparserSettings, get_settings
from services.log_setup import setup_logging
from services.rabbitmq import RabbitMQPublisher
from services.telegram import TelegramSender

log = logging.getLogger(__name__)

# Skip entries older than this (seconds).
_RSS_MAX_AGE = 6 * 3600

FeedKind = Literal["local_rss", "federal_rss"]


@dataclass(frozen=True, slots=True)
class FeedSource:
    url: str
    label: str
    kind: FeedKind


# Single source of truth (was a dict literal scattered in rss_parser.py).
RSS_SOURCES: tuple[FeedSource, ...] = (
    FeedSource("https://proural.info/rss/yandex/", "Независимая Уральская газета", "local_rss"),
    FeedSource("https://aspektymedia.ru/feed/", "Аспекты медиа", "local_rss"),
    FeedSource("https://ren.tv/export/global/rss.xml", "РЕН-ТВ", "federal_rss"),
    FeedSource("https://ria.ru/export/rss2/archive/index.xml", "РИА Новости", "federal_rss"),
    FeedSource("https://lenta.ru/rss/google-newsstand/main/", "Лента.ру", "federal_rss"),
    FeedSource("https://novayagazeta.ru/feed/rss", "Новая Газета", "federal_rss"),
    FeedSource("https://ura.news/rss", "URA.RU", "federal_rss"),
    FeedSource("https://www.vedomosti.ru/rss/news", "Ведомости", "federal_rss"),
    FeedSource("https://www.uralinform.ru/rss/all.rss", "Уралинформбюро", "federal_rss"),
    FeedSource("http://www.moscow-post.su/export/moscow-post.rss", "MoscowPost", "federal_rss"),
    FeedSource("https://www.interfax.ru/rss.asp", "Интерфакс", "federal_rss"),
    FeedSource("https://iz.ru/xml/rss/all.xml", "Известия", "federal_rss"),
    FeedSource("https://rg.ru/xml/index.xml", "Российская газета", "federal_rss"),
    FeedSource("https://regnum.ru/rss/news", "Регнум", "federal_rss"),
    FeedSource("https://glasnarod.ru/feed/", "Глас Народа", "federal_rss"),
    FeedSource("https://kazanfirst.ru/feed", "Kazan First", "federal_rss"),
    FeedSource("https://ufa.aif.ru/rss/googlenews", "АиФ Уфа", "local_rss"),
    FeedSource("https://ufacitynews.ru/rss/lucky/", "UfacityNews", "local_rss"),
    FeedSource("https://gtrk.tv/news.rss.xml", "ГТРК Башкортостан", "local_rss"),
    FeedSource("https://utv.ru/rss.xml", "UTV", "local_rss"),
    FeedSource("https://sobkor02.ru/rss.php", "Собкор02", "local_rss"),
    FeedSource("https://www.idelreal.org/api/", "ИдельРеалии", "local_rss"),
    FeedSource("https://trishurupa.ru/feed", "Три Шурупа", "local_rss"),
    FeedSource("https://news102.ru/feed/", "News102", "local_rss"),
)


def _clean(text: str) -> str:
    return (
        text.replace("<strong>", "")
        .replace("</strong>", "")
        .replace("<p>", "")
        .replace("</p>", "")
        .replace("<a href", "")
        .strip()
    )


class RssRunner:
    """Polls RSS feeds in parallel. Filters federal feeds by regional keywords,
    dedups via Redis (shared with the Scrapy pipeline), forwards to Telegram +
    RabbitMQ. Replaces the legacy synchronous rss_parser.py.
    """

    def __init__(self, settings: NewsparserSettings) -> None:
        self._settings = settings
        self._keywords = settings.region_keywords
        self._redis: aioredis.Redis | None = None
        self._http: aiohttp.ClientSession | None = None

    async def setup(self) -> None:
        self._redis = aioredis.from_url(
            f"redis://{self._settings.redis_host}:{self._settings.redis_port}/{self._settings.redis_db}",
            password=(
                self._settings.redis_password.get_secret_value()
                if self._settings.redis_password
                else None
            ),
            decode_responses=True,
        )
        timeout = aiohttp.ClientTimeout(total=20)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx, ttl_dns_cache=300)
        self._http = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={"User-Agent": "Mozilla/5.0 (newsparser/2.0)"},
        )
        await TelegramSender.acquire()
        await RabbitMQPublisher.acquire()

    async def close(self) -> None:
        if self._http is not None:
            await self._http.close()
        if self._redis is not None:
            await self._redis.aclose()
        await TelegramSender.release()
        await RabbitMQPublisher.release()

    async def run_once(self) -> None:
        sem = asyncio.Semaphore(5)
        async def _limited(s: FeedSource) -> None:
            async with sem:
                await self._process_feed(s)
        await asyncio.gather(*(_limited(s) for s in RSS_SOURCES), return_exceptions=True)

    async def _process_feed(self, source: FeedSource) -> None:
        assert self._http is not None
        try:
            async with self._http.get(source.url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                body = await resp.text()
        except Exception:
            log.warning("rss_fetch_failed", extra={"source": source.label})
            return

        parsed = feedparser.parse(body)
        now = time.time()
        for entry in parsed.entries:
            if not (
                getattr(entry, "title", "")
                and getattr(entry, "link", "")
            ):
                continue
            pub = getattr(entry, "published_parsed", None)
            if pub is None:
                continue
            if time.mktime(pub) < now - _RSS_MAX_AGE:
                continue
            await self._handle_entry(source, entry, pub)

    async def _handle_entry(self, source: FeedSource, entry: object,
                            pub_parsed: object) -> None:
        title = getattr(entry, "title", "")
        link = getattr(entry, "link", "")
        if not title or not link:
            return

        if source.kind == "federal_rss" and not any(w in title for w in self._keywords):
            return

        try:
            dt = datetime.fromtimestamp(time.mktime(pub_parsed))
        except (ValueError, TypeError):
            return

        if not await self._mark_seen(link):
            return

        description = _clean(getattr(entry, "description", ""))
        first_sentence = description.split(".")[0] if description else ""
        date_str = dt.strftime("%d.%m.%Y %H:%M")
        body = (
            f"Источник: {source.label}\n\n{title}\n\n"
            f"{first_sentence}\n\nДата публикации: {date_str}\n{link}"
        ).strip()

        tg = await TelegramSender.acquire()
        rmq = await RabbitMQPublisher.acquire()
        await asyncio.gather(tg.send_news(body), rmq.publish(body))

    async def _mark_seen(self, link: str) -> bool:
        """Atomic 'set-if-new' with TTL. Returns True if this is the first sight."""
        assert self._redis is not None
        key = f"newsparser:seen:{link}"
        return bool(await self._redis.set(key, "1", nx=True, ex=self._settings.redis_dedup_ttl_seconds))


async def _main() -> None:
    runner = RssRunner(get_settings())
    await runner.setup()
    try:
        await runner.run_once()
    finally:
        await runner.close()


if __name__ == "__main__":
    setup_logging("rss_runner")
    asyncio.run(_main())
