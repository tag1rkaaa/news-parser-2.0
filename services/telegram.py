from __future__ import annotations

import asyncio
import logging
from typing import Self

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter

from newsparser.core.settings_loader import NewsparserSettings, get_settings

log = logging.getLogger(__name__)


class TelegramSender:
    """Async Telegram client with per-process singleton, rate limiting and
    automatic backoff on flood control errors.

    Usage:
        sender = await TelegramSender.acquire()
        await sender.send_news(text)
        await sender.send_alert(text)
        # On graceful shutdown:
        await TelegramSender.release()
    """

    _instance: "TelegramSender | None" = None
    _lock = asyncio.Lock()

    def __init__(self, settings: NewsparserSettings) -> None:
        self._settings = settings

        proxy_url: str | None = None
        if settings.telegram_proxy_host and settings.telegram_proxy_port:
            scheme = settings.telegram_proxy_type or "socks5"
            user = settings.telegram_proxy_user or ""
            pwd = settings.telegram_proxy_pass.get_secret_value() if settings.telegram_proxy_pass else ""
            if user and pwd:
                proxy_url = f"{scheme}://{user}:{pwd}@{settings.telegram_proxy_host}:{settings.telegram_proxy_port}"
            elif user:
                proxy_url = f"{scheme}://{user}@{settings.telegram_proxy_host}:{settings.telegram_proxy_port}"
            else:
                proxy_url = f"{scheme}://{settings.telegram_proxy_host}:{settings.telegram_proxy_port}"
            log.info("telegram_proxy_configured", extra={"proxy": proxy_url})

        self._bot: Bot = Bot(
            token=settings.telegram_bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            session=AiohttpSession(proxy=proxy_url),
        )
        # Telegram caps ~30 msg/sec per bot, ~1 msg/sec per chat. Be conservative.
        self._channel_semaphore = asyncio.Semaphore(1)
        self._alert_semaphore = asyncio.Semaphore(1)
        self._min_interval = 1.0 / max(settings.telegram_rate_limit_per_sec, 0.1)
        self._last_send_at = 0.0

    @classmethod
    async def acquire(cls) -> Self:
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(get_settings())
        return cls._instance  # type: ignore[return-value]

    @classmethod
    async def release(cls) -> None:
        async with cls._lock:
            if cls._instance is not None:
                await cls._instance._bot.session.close()
                cls._instance = None

    async def send_news(self, text: str) -> None:
        await self._send(self._settings.telegram_channel_id, text, self._channel_semaphore)

    async def send_alert(self, text: str) -> None:
        await self._send(self._settings.telegram_alert_chat_id, text, self._alert_semaphore)

    async def _send(self, chat_id: int, text: str, semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            await self._respect_rate_limit()
            attempt = 0
            while True:
                try:
                    await self._bot.send_message(chat_id, text, disable_web_page_preview=True)
                    return
                except TelegramRetryAfter as e:
                    attempt += 1
                    wait = float(e.retry_after) + 0.5
                    log.warning("telegram_flood_control", extra={"retry_after": wait, "attempt": attempt})
                    await asyncio.sleep(wait)
                except Exception:
                    log.exception("telegram_send_failed", extra={"chat_id": chat_id})
                    return  # don't crash the pipeline on TG errors

    async def _respect_rate_limit(self) -> None:
        loop = asyncio.get_event_loop()
        now = loop.time()
        elapsed = now - self._last_send_at
        if elapsed < self._min_interval:
            await asyncio.sleep(self._min_interval - elapsed)
        self._last_send_at = loop.time()
