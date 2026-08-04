from __future__ import annotations

from datetime import datetime
from typing import Any

from scrapy.http import Response

from newsparser.core import BaseNewsSpider, DateFormat, DetailFollowMixin, is_today


class TassV2Spider(DetailFollowMixin, BaseNewsSpider):
    """Detail-follow example. The listing yields links; the article page is
    where we have the authoritative timestamp (epoch ms in `ca-ts` attr) and
    can decide whether the item is fresh.
    """

    name = "tass_v2"
    source_name = "ТАСС"
    base_url = "https://tass.ru"
    start_urls = ["https://tass.ru/tag/bashkortostan"]
    feed_type = "federal"

    listing_selector = "a.tass_pkg_link-v5WdK"
    link_selector = "::attr(href)"
    title_selector = "div.tass_pkg_title_wrapper-i0jgn"
    date_selector = None  # date lives only on the detail page
    date_format = DateFormat.AUTO

    def parse_article(self, response: Response) -> Any:
        meta = response.meta
        date_text = response.css("span[ca-tsm]::text").get()
        ts_ms = response.css("span[ca-ts]::attr(ca-ts)").get()
        if not ts_ms:
            return
        try:
            article_dt = datetime.fromtimestamp(int(ts_ms) / 1000)
        except (ValueError, OSError):
            return
        if not is_today(article_dt):
            return

        yield {
            "source": meta["source"],
            "title": meta["title"],
            "link": meta["link"],
            "date": date_text or article_dt.strftime("%d.%m.%Y %H:%M"),
        }
