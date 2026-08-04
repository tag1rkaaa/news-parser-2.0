from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Literal

import redis.asyncio as aioredis

from newsparser.core.settings_loader import NewsparserSettings, get_settings
from services.log_setup import setup_logging
from services.telegram import TelegramSender

log = logging.getLogger(__name__)

Severity = Literal["warning", "critical"]
HEALTH_HASH_PREFIX = "newsparser:health:"


@dataclass(slots=True)
class SpiderHealth:
    name: str
    last_success_ts: float
    items_scraped: int
    errors: int
    items_dropped: int
    run_duration: float
    health: Literal["healthy", "degraded", "down"]

    @classmethod
    def from_redis(cls, name: str, raw: dict[str, str]) -> "SpiderHealth | None":
        if not raw:
            return None
        try:
            return cls(
                name=name,
                last_success_ts=float(raw.get("last_success_ts", 0)),
                items_scraped=int(raw.get("items_scraped", 0)),
                errors=int(raw.get("errors", 0)),
                items_dropped=int(raw.get("items_dropped", 0)),
                run_duration=float(raw.get("run_duration", 0)),
                health=raw.get("health", "down"),  # type: ignore[arg-type]
            )
        except (ValueError, TypeError):
            log.warning("malformed_health_record", extra={"name": name, "raw": raw})
            return None


class AlertWatcher:
    """Periodically inspects Redis-stored health records (written by
    `extensions/stats_collector.py`) and posts Telegram alerts.

    Deduplication: each rule fires at most once per spider per cooldown window.
    """

    COOLDOWN_SECONDS = 30 * 60  # don't spam — 30 min between repeat alerts

    def __init__(self, settings: NewsparserSettings) -> None:
        self._settings = settings
        self._redis: aioredis.Redis | None = None
        self._last_fired: dict[tuple[str, str], float] = {}

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
        await TelegramSender.acquire()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
        await TelegramSender.release()

    async def run_forever(self) -> None:
        while True:
            try:
                await self.tick()
            except Exception:
                log.exception("alert_tick_failed")
            await asyncio.sleep(self._settings.alert_watcher_interval_seconds)

    async def tick(self) -> None:
        records = await self._load_all_health()
        if not records:
            return

        now = time.time()
        for h in records:
            try:
                if h.last_success_ts and (now - h.last_success_ts) > self._settings.alert_last_success_max_age_seconds:
                    age_h = (now - h.last_success_ts) / 3600
                    await self._fire(
                        h.name,
                        "stale",
                        "critical",
                        f"⚠️ Спайдер <b>{h.name}</b> молчит {age_h:.1f}ч (последний успех)",
                    )
                    await asyncio.sleep(1)

                total = h.items_scraped + h.errors
                if total > 0 and (h.errors / total) > self._settings.alert_error_rate_threshold:
                    await self._fire(
                        h.name,
                        "errors",
                        "warning",
                        f"⚠️ Спайдер <b>{h.name}</b>: error rate {h.errors}/{total}",
                    )
                    await asyncio.sleep(1)

                if h.health == "down":
                    await self._fire(
                        h.name,
                        "down",
                        "critical",
                        f"🛑 Спайдер <b>{h.name}</b> упал (items=0, см. логи)",
                    )
                    await asyncio.sleep(1)
            except Exception:
                log.exception("alert_rule_failed", extra={"spider": h.name})

        unhealthy = sum(1 for h in records if h.health != "healthy")
        ratio = unhealthy / len(records)
        if ratio > self._settings.alert_unhealthy_spider_ratio:
            await self._fire(
                "__global__",
                "mass_failure",
                "critical",
                f"🔥 Глобально: {unhealthy}/{len(records)} спайдеров не в healthy ({ratio:.0%})",
            )

    async def _load_all_health(self) -> list[SpiderHealth]:
        assert self._redis is not None
        result: list[SpiderHealth] = []
        async for key in self._redis.scan_iter(match=f"{HEALTH_HASH_PREFIX}*"):
            name = key.removeprefix(HEALTH_HASH_PREFIX)
            raw = await self._redis.hgetall(key)
            health = SpiderHealth.from_redis(name, raw)
            if health is not None:
                result.append(health)
        return result

    async def _fire(self, spider: str, rule: str, severity: Severity, text: str) -> None:
        key = (spider, rule)
        now = time.time()
        last = self._last_fired.get(key, 0.0)
        if now - last < self.COOLDOWN_SECONDS:
            return
        self._last_fired[key] = now
        try:
            sender = await TelegramSender.acquire()
            log.warning("alert_fire", extra={"spider": spider, "rule": rule, "severity": severity})
            await sender.send_alert(f"[{severity.upper()}] {text}")
        except Exception:
            log.exception("alert_send_failed", extra={"spider": spider, "rule": rule})


async def _main() -> None:
    watcher = AlertWatcher(get_settings())
    await watcher.setup()
    try:
        await watcher.run_forever()
    finally:
        await watcher.close()


if __name__ == "__main__":
    setup_logging("alert_watcher")
    asyncio.run(_main())
