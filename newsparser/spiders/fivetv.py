import re
from datetime import datetime, timedelta

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

_RU_MONTHS = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
}


def _parse_5tv_date(raw: str) -> str:
    """Convert '7:30', '2 июл', 'Сегодня, 14:00' to 'DD.MM.YYYY HH:MM'."""
    now = datetime.now()
    raw = raw.strip()

    # "7:30" (time only, today)
    match = re.match(r"(\d{1,2}):(\d{2})$", raw)
    if match:
        return now.replace(hour=int(match.group(1)), minute=int(match.group(2))).strftime("%d.%m.%Y %H:%M")

    # "2 июл" (day + month)
    match = re.match(r"(\d{1,2})\s+(\S+)", raw)
    if match:
        day = int(match.group(1))
        month = _RU_MONTHS.get(match.group(2).lower())
        if month:
            return datetime(now.year, month, day).strftime("%d.%m.%Y 00:00")

    return raw


class FiveTV_Spider(scrapy.Spider):
    name = "5tv"

    start_urls = ["https://www.5-tv.ru/news/list/russia/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('div.overflowHidden'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Пятый канал')

            l.add_css('date', 'span.labl::text')
            l.add_css('title', 'a')
            l.add_css('link', 'a::attr(href)')

            raw_date = l.get_output_value('date')
            l.replace_value('date', _parse_5tv_date(raw_date))

            yield l.load_item()
