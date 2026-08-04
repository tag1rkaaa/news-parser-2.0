from __future__ import annotations

import logging
from typing import Any

from itemadapter import ItemAdapter
from scrapy import Spider
from scrapy.exceptions import DropItem

from newsparser.core.settings_loader import get_settings

log = logging.getLogger(__name__)


class KeywordFilterPipeline:
    """Drops items whose title doesn't mention any of the configured regional
    keywords. Only active when the spider declares `feed_type = "federal"` (set
    via spider attribute or `NEWSPARSER_FEED_TYPE` setting). Local sites pass
    through unfiltered.
    """

    def __init__(self) -> None:
        self._keywords = get_settings().region_keywords

    def process_item(self, item: Any, spider: Spider) -> Any:
        feed_type = self._feed_type(spider)
        if feed_type != "federal":
            return item

        adapter = ItemAdapter(item)
        title = adapter.get("title") or ""
        if not any(kw in title for kw in self._keywords):
            spider.crawler.stats.inc_value("newsparser/items_dropped/no_keyword")
            log.info("keyword_filter_dropped", extra={"spider": spider.name, "title": title[:120]})
            raise DropItem("no_keyword")
        return item

    @staticmethod
    def _feed_type(spider: Spider) -> str:
        # Spider attribute wins; fall back to per-spider setting.
        return (
            getattr(spider, "feed_type", None)
            or spider.settings.get("NEWSPARSER_FEED_TYPE", "local")
        )
