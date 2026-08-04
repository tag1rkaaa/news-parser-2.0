import re
from datetime import datetime, timedelta

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


def _parse_ufatime_date(raw: str) -> str:
    """Convert '07:18', 'Вчера, 14:27', '26.06.2026, 11:48' to 'DD.MM.YYYY HH:MM'."""
    now = datetime.now()
    raw = raw.strip()

    # "Вчера, 14:27"
    match = re.match(r"вчера,\s*(\d{1,2}):(\d{2})", raw, re.IGNORECASE)
    if match:
        dt = now - timedelta(days=1)
        return dt.replace(hour=int(match.group(1)), minute=int(match.group(2))).strftime("%d.%m.%Y %H:%M")

    # "Сегодня, 09:11"
    match = re.match(r"сегодня,\s*(\d{1,2}):(\d{2})", raw, re.IGNORECASE)
    if match:
        return now.replace(hour=int(match.group(1)), minute=int(match.group(2))).strftime("%d.%m.%Y %H:%M")

    # "07:18" (time only, assume today)
    match = re.match(r"(\d{1,2}):(\d{2})$", raw)
    if match:
        return now.replace(hour=int(match.group(1)), minute=int(match.group(2))).strftime("%d.%m.%Y %H:%M")

    # "26.06.2026, 11:48"
    match = re.match(r"(\d{2}\.\d{2}\.\d{4}),\s*(\d{1,2}):(\d{2})", raw)
    if match:
        return f"{match.group(1)} {match.group(2)}:{match.group(3)}"

    return raw


class Ufatime_Spider(scrapy.Spider):
    name = "ufatime"

    start_urls = ["https://ufatime.ru/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('a.item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'UfaTime.ru')

            l.add_css('date', 'div.item_date')
            l.add_css('title', 'a::attr(title)')
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')

            if link:
                l.replace_value('link', 'https://ufatime.ru' + link)
                raw_date = l.get_output_value('date')
                l.replace_value('date', _parse_ufatime_date(raw_date))
                yield l.load_item()
