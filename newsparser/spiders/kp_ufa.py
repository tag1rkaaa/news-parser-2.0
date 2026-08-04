import re
from datetime import datetime, timedelta

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


def _parse_relative_time(raw: str) -> str:
    """Convert '13 минут назад', 'час назад', etc. to 'DD.MM.YYYY HH:MM'."""
    now = datetime.now()
    lower = raw.lower()

    num_match = re.search(r"(\d+)", lower)
    num = int(num_match.group(1)) if num_match else 1

    if "минут" in lower or "мин" in lower:
        dt = now - timedelta(minutes=num)
    elif "час" in lower:
        dt = now - timedelta(hours=num)
    elif "секунд" in lower or "сек" in lower:
        dt = now - timedelta(seconds=num)
    elif "дн" in lower:
        dt = now - timedelta(days=num)
    else:
        return raw

    return dt.strftime("%d.%m.%Y %H:%M")


class KP_Spider(scrapy.Spider):
    name = "kp_ufa"

    start_urls = ["https://www.ufa.kp.ru/online/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('[class*="sc-1tputnk-12"]'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Комсомольская Правда Уфа')

            l.add_css('date', '[class*="sc-1tputnk-9"]')
            date = l.get_output_value('date')

            if "вчера" in date:
                break

            l.add_css('title', 'a[class*="sc-1tputnk-2"]')
            l.add_css('link', 'a[class*="sc-1tputnk-2"]::attr(href)')
            link = l.get_output_value('link')

            if link:
                l.replace_value('link', "https://www.ufa.kp.ru" + link)
                l.replace_value('date', _parse_relative_time(date))
                yield l.load_item()
