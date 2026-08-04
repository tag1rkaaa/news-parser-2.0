from __future__ import annotations

from datetime import datetime
from typing import Any

from scrapy.http import Response

from newsparser.core import BaseNewsSpider, DateFormat, DetailFollowMixin
from newsparser.core.selectors import absolute_url

# Region filter values (was a buggy `==` chain in the legacy spider).
ALLOWED_REGIONS = frozenset({"Башкортостан", "Башкортостан / Эксклюзив"})


class KommersantV2Spider(DetailFollowMixin, BaseNewsSpider):
    """Multi-selector listing example. Kommersant has 4 different listing
    layouts on the same page (top-news, top-news main, top-news hot,
    in-section). Each yields a follow request; freshness + region filter
    happen on the article page.
    """

    name = "kommersant_v2"
    source_name = "Коммерсант"
    base_url = "https://www.kommersant.ru"
    start_urls = ["https://www.kommersant.ru/regions/2"]
    feed_type = "local"

    # These three are required by the base class but unused — we override parse().
    listing_selector = "article"
    link_selector = "a::attr(href)"
    title_selector = "a::text"
    date_format = DateFormat.DMY_DOT

    # Each tuple = (CSS for the article block, CSS for the link, CSS for the title)
    LAYOUTS = (
        ("article.top_news__item", "a::attr(href)", "a::text"),
        ("article.top_news_main", "a::attr(href)", "a::text"),
        ("div.top_news_hot", "a::attr(href)", ".top_news_hot__text h1::text"),
        (
            "article.uho",
            "h2.title_20.uho__name.m-title_24 > a.uho__link.uho__link--overlay::attr(href)",
            "h2.title_20.uho__name.m-title_24 > a.uho__link.uho__link--overlay::text",
        ),
    )

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for block_sel, link_sel, title_sel in self.LAYOUTS:
            for article in response.css(block_sel):
                raw_link = article.css(link_sel).get()
                title = article.css(title_sel).get()
                if not raw_link or not title:
                    continue
                clean_link = raw_link.split("?")[0]
                link = absolute_url(self.base_url, clean_link)
                if link is None:
                    continue
                yield response.follow(
                    link,
                    callback=self.parse_article,
                    meta={"source": self.source_name, "title": title.strip(), "link": link},
                )

    def parse_article(self, response: Response) -> Any:
        meta = response.meta
        region = response.css("a.decor::text").get()
        if region not in ALLOWED_REGIONS:
            return
        date = response.css("time.doc_header__publish_time::text").get()
        if not date or date[:10] != datetime.now().strftime("%d.%m.%Y"):
            return
        yield {
            "source": meta["source"],
            "title": meta["title"],
            "link": meta["link"],
            "date": date,
        }
