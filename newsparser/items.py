from __future__ import annotations

import re
from datetime import datetime

import scrapy
from itemloaders.processors import MapCompose, TakeFirst
from pydantic import BaseModel, ConfigDict, Field, field_validator
from w3lib.html import remove_tags


def _strip_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# ---- Legacy Scrapy item (kept for the 25 existing spiders) ----

class NewsSitesParserItem(scrapy.Item):
    source = scrapy.Field(output_processor=TakeFirst())
    date = scrapy.Field(
        input_processor=MapCompose(_strip_ws, remove_tags),
        output_processor=TakeFirst(),
    )
    title = scrapy.Field(
        input_processor=MapCompose(_strip_ws, remove_tags),
        output_processor=TakeFirst(),
    )
    link = scrapy.Field(output_processor=TakeFirst())


class Get_date:  # noqa: N801 — kept for compatibility with imports in legacy spiders
    def current_date(self, time: str | None = None) -> str:
        today = datetime.today().strftime("%Y.%m.%d")
        return f"{today} {time}" if time is not None else today


# ---- Modern Pydantic item (used by validation pipeline + new spiders) ----

class NewsItem(BaseModel):
    """Canonical news item. Built from either dict-yielding spiders or
    NewsSitesParserItem via ItemAdapter — both convert cleanly through
    `NewsItem.model_validate(adapter.asdict())`.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    source: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    link: str = Field(min_length=1, max_length=2000)
    date: str = Field(default="", max_length=200)

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, v: object) -> str:
        if v is None:
            return ""
        return _strip_ws(remove_tags(str(v)))

    @field_validator("link")
    @classmethod
    def _validate_link(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"link must be absolute, got: {v!r}")
        return v
