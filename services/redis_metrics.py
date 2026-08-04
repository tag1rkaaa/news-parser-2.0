from __future__ import annotations

import logging
import threading
from typing import Generator

import redis
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY

from newsparser.core.settings_loader import get_settings

log = logging.getLogger(__name__)

HEALTH_HASH_PREFIX = "newsparser:health:"


class RedisMetricsCollector:
    """Reads spider health from Redis and exposes as Prometheus metrics.
    Runs in the main process alongside the /metrics HTTP server."""

    _started = False
    _lock = threading.Lock()

    def __init__(self) -> None:
        cfg = get_settings()
        password = cfg.redis_password.get_secret_value() if cfg.redis_password else None
        self._redis = redis.Redis(
            host=cfg.redis_host,
            port=cfg.redis_port,
            db=cfg.redis_db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=2,
        )
        self._port = cfg.prometheus_port
        self._prev: dict[str, dict[str, int]] = {}
        self._cumulative: dict[str, dict[str, int]] = {}

    def start(self) -> None:
        with self._lock:
            if RedisMetricsCollector._started:
                return
            try:
                start_http_server(self._port, addr="0.0.0.0")
                RedisMetricsCollector._started = True
                log.info("redis_metrics_server_started", extra={"port": self._port})
            except OSError:
                log.exception("redis_metrics_bind_failed", extra={"port": self._port})
                return

        REGISTRY.register(self)

    def collect(self) -> Generator:
        metrics: dict[str, dict] = {}
        try:
            for key in self._redis.scan_iter(match=f"{HEALTH_HASH_PREFIX}*"):
                name = key.removeprefix(HEALTH_HASH_PREFIX)
                raw = self._redis.hgetall(key)
                if not raw:
                    continue
                metrics[name] = raw
        except Exception:
            log.exception("redis_metrics_collect_failed")
            return

        health = GaugeMetricFamily(
            "newsparser_spider_health",
            "Per-spider health: 0=down, 1=degraded, 2=healthy",
            labels=["spider"],
        )
        last_success = GaugeMetricFamily(
            "newsparser_spider_last_success_timestamp",
            "Unix timestamp of last successful spider run",
            labels=["spider"],
        )
        run_dur = GaugeMetricFamily(
            "newsparser_spider_run_duration_seconds_sub",
            "Run duration from Redis (seconds)",
            labels=["spider"],
        )
        items = CounterMetricFamily(
            "newsparser_items_scraped_total",
            "Cumulative items scraped",
            labels=["spider"],
        )
        dropped = CounterMetricFamily(
            "newsparser_items_dropped_total",
            "Cumulative items dropped",
            labels=["spider"],
        )
        errs = CounterMetricFamily(
            "newsparser_errors_total",
            "Cumulative errors",
            labels=["spider"],
        )

        health_map = {"healthy": 2, "degraded": 1, "down": 0}

        for name, raw in metrics.items():
            h = raw.get("health", "down")
            health.add_metric([name], health_map.get(h, 0))
            last_success.add_metric([name], float(raw.get("last_success_ts", 0)))
            run_dur.add_metric([name], float(raw.get("run_duration", 0)))

            for key, counter in [("items_scraped", items), ("items_dropped", dropped), ("errors", errs)]:
                cur = int(raw.get(key, 0))
                prev = self._prev.get(name, {}).get(key, 0)
                cum = self._cumulative.get(name, {}).get(key, 0)

                if cur < prev:
                    cum += prev
                elif cur > prev:
                    cum += cur - prev

                self._cumulative.setdefault(name, {})[key] = cum
                self._prev.setdefault(name, {})[key] = cur
                counter.add_metric([name], cum)

        yield health
        yield last_success
        yield run_dur
        yield items
        yield dropped
        yield errs
