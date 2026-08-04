from __future__ import annotations

import logging
import threading
from typing import Self

from prometheus_client import start_http_server
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured

log = logging.getLogger(__name__)


class PrometheusExporter:
    """Spawns the Prometheus /metrics HTTP server once per process.

    `process.crawl()` runs all spiders inside one process; calling
    `start_http_server` twice would bind the port twice. We guard with a
    process-wide lock + flag.
    """

    _started = False
    _lock = threading.Lock()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        if not crawler.settings.getbool("NEWSPARSER_PROMETHEUS_ENABLED", True):
            raise NotConfigured
        instance = cls()
        crawler.signals.connect(instance._on_engine_started, signal=signals.engine_started)
        instance._port = crawler.settings.getint("NEWSPARSER_PROMETHEUS_PORT", 8000)
        instance._addr = crawler.settings.get("NEWSPARSER_PROMETHEUS_ADDR", "0.0.0.0")
        return instance

    def _on_engine_started(self) -> None:
        with self._lock:
            if PrometheusExporter._started:
                return
            try:
                start_http_server(self._port, addr=self._addr)
                PrometheusExporter._started = True
                log.info("prometheus_exporter_started", extra={"port": self._port})
            except OSError:
                log.exception("prometheus_exporter_bind_failed", extra={"port": self._port})
