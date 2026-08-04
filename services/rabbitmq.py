from __future__ import annotations

import asyncio
import logging
from typing import Self

import aio_pika
from aio_pika.abc import AbstractRobustConnection, ExchangeType

from newsparser.core.settings_loader import NewsparserSettings, get_settings

log = logging.getLogger(__name__)


class RabbitMQPublisher:
    """Singleton async publisher that reuses one robust connection + channel.

    Robust connection auto-reconnects, so brief broker outages don't kill the
    crawler. Publishes are persistent.
    """

    _instance: "RabbitMQPublisher | None" = None
    _lock = asyncio.Lock()

    def __init__(self, settings: NewsparserSettings) -> None:
        self._settings = settings
        self._conn: AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None
        self._publish_lock = asyncio.Lock()

    @classmethod
    async def acquire(cls) -> Self:
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(get_settings())
                await cls._instance._connect()
        return cls._instance  # type: ignore[return-value]

    @classmethod
    async def release(cls) -> None:
        async with cls._lock:
            if cls._instance is not None and cls._instance._conn is not None:
                await cls._instance._conn.close()
                cls._instance = None

    async def _connect(self) -> None:
        url = self._settings.rabbitmq_url.get_secret_value()
        self._conn = await aio_pika.connect_robust(url)
        self._channel = await self._conn.channel(publisher_confirms=True)
        await self._channel.declare_queue(self._settings.rabbitmq_queue, durable=True)
        self._exchange = self._channel.default_exchange

    async def publish(self, body: str) -> None:
        async with self._publish_lock:
            if self._exchange is None:
                await self._connect()
            assert self._exchange is not None
            try:
                await self._exchange.publish(
                    aio_pika.Message(
                        body=body.encode("utf-8"),
                        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    ),
                    routing_key=self._settings.rabbitmq_queue,
                )
            except Exception:
                log.exception("rabbitmq_publish_failed")
                # don't crash pipeline; robust conn will reconnect for next msg
