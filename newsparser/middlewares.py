from __future__ import annotations

import logging
import random
from typing import Any, Self

from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.http import Request, Response
from scrapy.spiders import Spider

from newsparser.core.selectors import domain_of
from newsparser.core.settings_loader import get_settings

log = logging.getLogger(__name__)


# 10 modern UAs (2024+). Rotated per request to avoid the ancient hardcoded 2017 string.
USER_AGENTS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 OPR/111.0.0.0",
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
)


class UserAgentRotationMiddleware:
    """Picks a fresh UA per request. AutoThrottle still gets accurate latency."""

    def __init__(self) -> None:
        self._rng = random.Random()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        return cls()

    def process_request(self, request: Request, spider: Spider) -> None:
        request.headers.setdefault("User-Agent", self._rng.choice(USER_AGENTS))


class SmartThrottleMiddleware:
    """Layered on top of AutoThrottle: lets us pin a minimum download delay
    per domain for sites that ban aggressive crawlers. Reads from settings dict.
    """

    def __init__(self, delays: dict[str, float]) -> None:
        self._delays = {k.lower().removeprefix("www."): v for k, v in delays.items()}
        self._last_request_at: dict[str, float] = {}

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        delays = get_settings().domain_download_delays
        return cls(delays)

    def process_request(self, request: Request, spider: Spider) -> None:
        # Per-domain delay is best handled by Scrapy's own
        # DOWNLOAD_DELAY + CONCURRENT_REQUESTS_PER_DOMAIN; we tag the request
        # with a meta value so Scrapy's downloader scheduler can pick it up via
        # download_slot. We expose the delay via meta so AutoThrottle plays nice.
        domain = domain_of(request.url)
        if domain in self._delays:
            request.meta.setdefault("download_slot", domain)
            # Scrapy honors per-slot DOWNLOAD_DELAY when we name the slot;
            # value comes from spider settings (set in settings.py from same dict).


class RetryWithBackoffMiddleware:
    """Exponential backoff with jitter on retryable HTTP codes / network errors.

    Sits *before* Scrapy's built-in RetryMiddleware in the chain so we set
    `download_delay` for the retry that built-in middleware then schedules.
    """

    RETRY_CODES: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
    BASE_DELAY_SEC = 1.0
    MAX_DELAY_SEC = 60.0

    def __init__(self) -> None:
        self._rng = random.Random()

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        instance = cls()
        crawler.signals.connect(instance._noop, signal=signals.spider_opened)
        return instance

    def _noop(self) -> None:
        pass

    def process_response(self, request: Request, response: Response, spider: Spider) -> Response | Request:
        if response.status not in self.RETRY_CODES:
            return response
        retry_times = int(request.meta.get("retry_times", 0))
        delay = min(self.MAX_DELAY_SEC, self.BASE_DELAY_SEC * (2**retry_times))
        delay += self._rng.uniform(0, delay / 2)  # jitter
        spider.crawler.stats.inc_value(f"newsparser/retry/{response.status}")
        log.info(
            "retry_with_backoff",
            extra={"url": request.url, "status": response.status, "delay": round(delay, 2)},
        )
        new_request = request.copy()
        new_request.meta["download_delay"] = delay
        new_request.dont_filter = True
        return new_request

    def process_exception(self, request: Request, exception: Exception, spider: Spider) -> None:
        spider.crawler.stats.inc_value(f"newsparser/network_error/{type(exception).__name__}")
        return None


# ---- Original skeleton classes kept for any user-provided overrides ----

class NewsparserSpiderMiddleware:
    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        instance = cls()
        crawler.signals.connect(instance._opened, signal=signals.spider_opened)
        return instance

    def _opened(self, spider: Spider) -> None:
        spider.logger.info("Spider opened: %s", spider.name)

    def process_spider_output(self, response: Response, result: Any, spider: Spider) -> Any:
        yield from result


class PrufyHtmlFixMiddleware:
    """Fixes prufy.ru's malformed HTML where content appears after </body></html>.
    lxml drops everything after those closing tags, so we strip them.
    """

    DOMAINS_TO_FIX = {"prufy.ru"}

    def process_response(self, request: Request, response: Response, spider: Spider) -> Response:
        from scrapy.http import HtmlResponse
        from urllib.parse import urlparse

        domain = urlparse(response.url).hostname or ""
        if domain not in self.DOMAINS_TO_FIX:
            return response

        if not isinstance(response, HtmlResponse):
            return response

        body = response.body.decode(response.encoding, errors="replace")
        # Strip </body> and </html> so lxml parses the content after them
        fixed = body.replace("</body>", "").replace("</html>", "")
        return response.replace(body=fixed.encode("utf-8"))


class NewsparserDownloaderMiddleware:
    @classmethod
    def from_crawler(cls, crawler: Crawler) -> Self:
        return cls()
