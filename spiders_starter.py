"""Entrypoint: discover and run every spider in newsparser.spiders.

Replaces the legacy starter that imported 25 spider classes by name. New
spiders are picked up automatically; no edit needed here.

Run modes:
    python spiders_starter.py            # one pass (every spider, then exit)
    python spiders_starter.py --rss-only # skip Scrapy, only poll RSS
    python spiders_starter.py --loop=N   # repeat every N seconds (long-running)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from typing import Iterable

from scrapy.spiderloader import SpiderLoader
from scrapy.utils.project import get_project_settings

from services.log_setup import setup_logging
from services.rabbitmq import RabbitMQPublisher
from services.rss_runner import RssRunner
from services.telegram import TelegramSender

log = logging.getLogger(__name__)


def _discover_spider_names() -> list[str]:
    settings = get_project_settings()
    loader = SpiderLoader.from_settings(settings)
    return sorted(loader.list())


def _run_scrapy(spider_names: Iterable[str]) -> None:
    names = list(spider_names)
    import json
    names_json = json.dumps(names)
    code = (
        "import json; from scrapy.crawler import CrawlerProcess; "
        "from scrapy.utils.project import get_project_settings; "
        f"_names = json.loads({json.dumps(names_json)}); "
        "s=get_project_settings(); p=CrawlerProcess(s); "
        "[p.crawl(n) for n in _names]; p.start()"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
    )


async def _run_rss() -> None:
    from newsparser.core.settings_loader import get_settings

    runner = RssRunner(get_settings())
    await runner.setup()
    try:
        await runner.run_once()
    finally:
        await runner.close()


async def _shutdown_services() -> None:
    await TelegramSender.release()
    await RabbitMQPublisher.release()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--rss-only", action="store_true", help="Skip Scrapy, only poll RSS")
    p.add_argument("--scrapy-only", action="store_true", help="Skip RSS, only run Scrapy spiders")
    p.add_argument("--loop", type=int, default=0, help="Repeat every N seconds (0 = single pass)")
    p.add_argument("--spider", action="append", help="Restrict to named spider(s); may be repeated")
    return p.parse_args()


def _setup_signal_handlers(stop: asyncio.Event) -> None:
    def _on_sig(*_: object) -> None:
        log.info("shutdown_signal_received")
        stop.set()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _on_sig)
        except (ValueError, OSError):
            pass  # SIGTERM not available on Windows


def main() -> None:
    args = _parse_args()
    setup_logging("starter")

    if args.loop:
        from services.redis_metrics import RedisMetricsCollector
        collector = RedisMetricsCollector()
        collector.start()
        asyncio.run(_loop_forever(args))
    else:
        _single_pass(args)
        asyncio.run(_shutdown_services())


def _single_pass(args: argparse.Namespace) -> None:
    if not args.scrapy_only:
        asyncio.run(_run_rss())

    if not args.rss_only:
        names = args.spider or _discover_spider_names()
        log.info("starting_scrapy_pass", extra={"count": len(names)})
        _run_scrapy(names)


async def _loop_forever(args: argparse.Namespace) -> None:
    stop = asyncio.Event()
    _setup_signal_handlers(stop)
    interval = max(args.loop, 60)
    while not stop.is_set():
        start = time.monotonic()
        try:
            tasks = []
            if not args.scrapy_only:
                tasks.append(_run_rss())
            if not args.rss_only:
                names = args.spider or _discover_spider_names()
                log.info("starting_scrapy_pass", extra={"count": len(names)})
                tasks.append(asyncio.to_thread(_run_scrapy, names))
            if tasks:
                await asyncio.gather(*tasks)
        except Exception:
            log.exception("pass_failed")
        elapsed = time.monotonic() - start
        sleep_for = max(0.0, interval - elapsed)
        log.info("pass_done", extra={"elapsed": round(elapsed, 1), "sleep": round(sleep_for, 1)})
        try:
            await asyncio.wait_for(stop.wait(), timeout=sleep_for)
        except asyncio.TimeoutError:
            continue
    await _shutdown_services()


if __name__ == "__main__":
    main()
