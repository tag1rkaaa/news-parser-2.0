from __future__ import annotations

import logging
from typing import Any

from itemadapter import ItemAdapter
from pydantic import ValidationError
from scrapy import Spider
from scrapy.exceptions import DropItem

from newsparser.items import NewsItem

log = logging.getLogger(__name__)


class PydanticValidationPipeline:
    """Validates every item against NewsItem. Drops invalid items with a
    structured log line so we can spot broken selectors quickly.

    Items are not mutated — downstream pipelines still receive the original
    item (Scrapy Item or dict). Validation purely enforces shape.
    """

    def process_item(self, item: Any, spider: Spider) -> Any:
        adapter = ItemAdapter(item)
        try:
            NewsItem.model_validate(adapter.asdict())
        except ValidationError as e:
            spider.crawler.stats.inc_value("newsparser/items_dropped/validation")
            log.warning(
                "item_validation_failed",
                extra={
                    "spider": spider.name,
                    "errors": e.errors(include_url=False, include_context=False),
                    "item": dict(adapter),
                },
            )
            raise DropItem("validation_failed") from e
        return item
