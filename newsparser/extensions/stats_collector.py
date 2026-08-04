from __future__ import annotations

import logging
import time
from typing import Any, Self
from urllib.parse import urlparse

import redis
from prometheus_client import Counter, Gauge, Histogram
from scrapy import Spider, signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured
from scrapy.http import Response

from newsparser.core.settings_loader import get_settings

log = logging.getLogger(__name__)

# Module-level metrics so multiple spiders in the same process share registry.
ITEMS_SCRAPED = Counter(
    "newsparser_items_scraped_total",
    "Items successfully scraped (passed all pipelines)",
    ["spider", "source"],
)
ITEMS_DROPPED = Counter(
    "newsparser_items_dropped_total",
    "Items dropped, by reason",
    ["spider", "reason"],
)
ERRORS_TOTAL = Counter(
    "newsparser_errors_total",
    "Errors caught by signals, by type",
    ["spider", "type"],
)
REQUEST_DURATION = Histogram(
    "newsparser_request_duration_seconds",
    "Per-domain response latency",
    ["spider", "domain"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 60),
)
LAST_SUCCESS = Gauge(
    "newsparser_spider_last_success_timestamp",
    "Unix timestamp of last successful spider run",
    ["spider"],
)
RUN_DURATION = Histogram(
    "newsparser_spider_run_duration_seconds",
    "Wall-clock duration of a spider run",
    ["spider"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)
SPIDER_HEALTH = Gauge(
    "newsparser_spider_health",
    "Per-spider health: 0=down, 1=degraded, 2=healthy",
    ["spider"],
)

HEALTH_HASH_PREFIX = "newsparser:health:"


class SpiderStatsExtension:
    """Listens to Scrapy signals and translates them into Prometheus metrics +
    a Redis hash (read by `services/alert_watcher.py`). Decoupled from the
    Prometheus exporter — exporter only owns the HTTP server.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        password = cfg.redis_password.get_secret_value() if cfg.redis_password else None
        # Sync redis client — writes are tiny, infrequent, and happen from signal
        # handlers (not on the hot path). Async would force every handler to be
        # awaitable for no real benefit.
        try:
            self._redis: redis.Redis | None = redis.Redis(
                host=cfg.redis_host,
                port=cfg.redis_port,
                db=cfg.redis_db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self._redis.ping()
        except (redis.RedisError, OSError) as e:
            log.warning("stats_redis_unavailable", extra={"err": str(e)})
            self._redis = None
        self._start_ts: dict[str, float] = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        if not crawler.settings.getbool("NEWSPARSER_STATS_ENABLED", True):
            raise NotConfigured
        ext = cls()
        s = crawler.signals
        s.connect(ext.spider_opened, signal=signals.spider_opened)
        s.connect(ext.spider_closed, signal=signals.spider_closed)
        s.connect(ext.item_scraped, signal=signals.item_scraped)
        s.connect(ext.item_dropped, signal=signals.item_dropped)
        s.connect(ext.spider_error, signal=signals.spider_error)
        s.connect(ext.response_received, signal=signals.response_received)
        return ext

    def spider_opened(self, spider: Spider) -> None:
        self._start_ts[spider.name] = time.time()
        SPIDER_HEALTH.labels(spider=spider.name).set(1)  # degraded until we see items

    def spider_closed(self, spider: Spider, reason: str) -> None:
        duration = time.time() - self._start_ts.get(spider.name, time.time())
        RUN_DURATION.labels(spider=spider.name).observe(duration)

        stats = spider.crawler.stats.get_stats()
        items = int(stats.get("item_scraped_count", 0))
        errors = int(stats.get("spider_exceptions", 0))
        dropped = sum(int(v) for k, v in stats.items() if k.startswith("newsparser/items_dropped/"))
        responses = int(stats.get("response_received_count", 0))

        # A spider is healthy if it found items (even if dedup dropped them),
        # or if it received responses without errors.
        found_items = items + dropped

        health: str
        if reason == "finished" and found_items > 0 and errors == 0:
            health = "healthy"
            SPIDER_HEALTH.labels(spider=spider.name).set(2)
            LAST_SUCCESS.labels(spider=spider.name).set(time.time())
        elif reason == "finished" and responses > 0 and errors == 0:
            health = "healthy"
            SPIDER_HEALTH.labels(spider=spider.name).set(2)
            LAST_SUCCESS.labels(spider=spider.name).set(time.time())
        elif found_items > 0 or responses > 0:
            health = "degraded"
            SPIDER_HEALTH.labels(spider=spider.name).set(1)
            LAST_SUCCESS.labels(spider=spider.name).set(time.time())
        else:
            health = "down"
            SPIDER_HEALTH.labels(spider=spider.name).set(0)

        self._write_health(
            spider.name,
            {
                "last_success_ts": time.time() if health != "down" else 0,
                "items_scraped": items,
                "errors": errors,
                "items_dropped": dropped,
                "run_duration": duration,
                "health": health,
                "finish_reason": reason,
            },
        )

    def item_scraped(self, item: Any, spider: Spider) -> None:
        from itemadapter import ItemAdapter
        source = str(ItemAdapter(item).get("source", "")) or "unknown"
        ITEMS_SCRAPED.labels(spider=spider.name, source=source).inc()

    def item_dropped(self, item: Any, response: Response, exception: BaseException, spider: Spider) -> None:
        reason = str(exception) or type(exception).__name__
        ITEMS_DROPPED.labels(spider=spider.name, reason=reason).inc()

    def spider_error(self, failure: Any, response: Response, spider: Spider) -> None:
        err_type = failure.type.__name__ if hasattr(failure, "type") else "unknown"
        ERRORS_TOTAL.labels(spider=spider.name, type=err_type).inc()

    def response_received(self, response: Response, request: Any, spider: Spider) -> None:
        download_latency = request.meta.get("download_latency")
        if download_latency is None:
            return
        domain = urlparse(response.url).netloc.lower().removeprefix("www.")
        REQUEST_DURATION.labels(spider=spider.name, domain=domain).observe(float(download_latency))

    def _write_health(self, spider: str, payload: dict[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            self._redis.hset(
                f"{HEALTH_HASH_PREFIX}{spider}",
                mapping={k: str(v) for k, v in payload.items()},
            )
            self._redis.expire(f"{HEALTH_HASH_PREFIX}{spider}", 7 * 24 * 3600)
        except redis.RedisError:
            log.exception("stats_health_write_failed", extra={"spider": spider})
