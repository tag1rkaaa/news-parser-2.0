from __future__ import annotations

import logging
from typing import Any, Self

from itemadapter import ItemAdapter
from scrapy import Spider, signals
from scrapy.crawler import Crawler

from newsparser.core.settings_loader import get_settings
from services.rabbitmq import RabbitMQPublisher
from services.telegram import TelegramSender

log = logging.getLogger(__name__)


class NotifyPipeline:
    """Sends each surviving item to Telegram + RabbitMQ.

    Async; uses singleton TelegramSender / RabbitMQPublisher so we open one TCP
    connection per backend per crawler — not per item, as the legacy code did.
    Filters out ads via configurable wordlist.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._ad_words = self._settings.ad_filter_words

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        instance = cls()
        crawler.signals.connect(instance.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(instance.spider_closed, signal=signals.spider_closed)
        return instance

    async def spider_opened(self, spider: Spider) -> None:
        await TelegramSender.acquire()
        await RabbitMQPublisher.acquire()

    async def spider_closed(self, spider: Spider) -> None:
        # Don't tear down singletons here — other spiders running in the same
        # process may still need them. The starter is responsible for the
        # process-level shutdown.
        return None

    async def process_item(self, item: Any, spider: Spider) -> Any:
        adapter = ItemAdapter(item)
        source = adapter.get("source", "")
        title = adapter.get("title", "")
        link = adapter.get("link", "")
        date_raw = adapter.get("date", "")

        text = self._format(source=str(source), title=str(title), link=str(link), date_raw=str(date_raw))

        if any(word in text for word in self._ad_words):
            spider.crawler.stats.inc_value("newsparser/items_dropped/ad")
            log.debug("notify_skipped_ad", extra={"link": link})
            return item

        tg = await TelegramSender.acquire()
        rmq = await RabbitMQPublisher.acquire()
        await tg.send_news(text)
        await rmq.publish(text)
        return item

    @staticmethod
    def _format(*, source: str, title: str, link: str, date_raw: str) -> str:
        return (
            f"Источник: {source}\n\n{title}\n\n"
            f"Дата публикации: {date_raw}\nСсылка: {link}\n"
        )
