from __future__ import annotations

from typing import Any, ClassVar, Literal

import scrapy
from scrapy.http import Response

from newsparser.core.date_utils import DateFormat, is_today, parse_news_date
from newsparser.core.selectors import absolute_url, safe_first

FeedType = Literal["local", "federal"]


class BaseNewsSpider(scrapy.Spider):
    """Base for news listing spiders.

    Concrete spiders set declarative attributes (source_name, base_url, selectors,
    date_format, feed_type) and optionally override `extract_link` / `extract_title`
    / `parse_article` for edge cases. The default `parse()` walks the listing,
    normalizes URLs, filters by today's date and yields either an item directly
    (ListingOnlyMixin) or schedules a detail request (DetailFollowMixin).
    """

    # Required overrides
    source_name: str = ""
    base_url: str = ""
    listing_selector: str = ""
    link_selector: str = ""
    title_selector: str = ""
    date_selector: str | None = None

    # Behavior
    date_format: DateFormat = DateFormat.AUTO
    url_slice: tuple[int, int] | None = None
    feed_type: FeedType = "local"
    stop_on_old_date: bool = True  # break on the first non-today item

    custom_settings: ClassVar[dict[str, Any]] = {
        # Pipelines are wired centrally in settings.py — spiders only declare feed_type.
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.__abstractmethods__ if hasattr(cls, "__abstractmethods__") else True:
            for required in ("source_name", "base_url", "listing_selector"):
                if not getattr(cls, required, ""):
                    # Allow examples to remain abstract by checking name suffix
                    if cls.__name__.startswith("Abstract"):
                        return
                    raise TypeError(f"{cls.__name__} must define `{required}`")

    # ------------ overridable extraction hooks ------------

    def extract_link(self, article_sel: Any) -> str | None:
        return absolute_url(self.base_url, safe_first(article_sel, self.link_selector))

    def extract_title(self, article_sel: Any) -> str | None:
        return safe_first(article_sel, self.title_selector) or None

    def extract_date_raw(self, article_sel: Any) -> str | None:
        if not self.date_selector:
            return None
        return safe_first(article_sel, self.date_selector) or None

    # ------------ default parse ------------

    def parse(self, response: Response, **kwargs: Any) -> Any:
        for article in response.css(self.listing_selector):
            link = self.extract_link(article)
            title = self.extract_title(article)
            if not link or not title:
                continue

            raw_date = self.extract_date_raw(article)
            parsed_date = parse_news_date(raw_date, self.date_format, url_slice=self.url_slice) if raw_date else None

            if raw_date and parsed_date and not is_today(parsed_date):
                if self.stop_on_old_date:
                    break
                continue

            yield from self.dispatch(response, link=link, title=title, date_raw=raw_date)

    # Subclasses (via mixin) decide whether to yield item or follow link.
    def dispatch(self, response: Response, *, link: str, title: str, date_raw: str | None) -> Any:
        raise NotImplementedError("Mix in ListingOnlyMixin or DetailFollowMixin")


class ListingOnlyMixin:
    """Yield items directly from listing without visiting article pages."""

    def dispatch(self: BaseNewsSpider, response: Response, *, link: str, title: str, date_raw: str | None) -> Any:  # type: ignore[misc]
        yield {
            "source": self.source_name,
            "title": title,
            "link": link,
            "date": date_raw or "",
        }


class DetailFollowMixin:
    """Follow each link to fetch and parse the article page."""

    def dispatch(self: BaseNewsSpider, response: Response, *, link: str, title: str, date_raw: str | None) -> Any:  # type: ignore[misc]
        yield response.follow(
            link,
            callback=self.parse_article,
            meta={"source": self.source_name, "title": title, "link": link, "date_raw": date_raw},
        )

    def parse_article(self: BaseNewsSpider, response: Response) -> Any:  # type: ignore[misc]
        raise NotImplementedError(f"{type(self).__name__} must implement parse_article()")
