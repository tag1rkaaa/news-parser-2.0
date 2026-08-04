import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Sterlegrad_Spider(scrapy.Spider):
    name = 'sterlegrad'

    start_urls = ['https://sterlegrad.ru/']

    custom_settings = {
        'ITEM_PIPELINES': {"newsparser.pipelines.KeyWordsCheck": 1},
        'DOWNLOAD_DELAY': 2,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
    }

    def parse(self, response):
        for article in response.css('div.gxnews > div'):
            link = article.css('a::attr(href)').get()
            title = article.css('a span::text').get()
            if not link or not title:
                continue
            yield response.follow(
                link, self.parse_article,
                meta={'source': 'Стерлеград', 'title': title.strip()},
            )

    def parse_article(self, response):
        date = response.css('time::attr(datetime)').get()
        if not date:
            date = response.css('meta[property="article:published_time"]::attr(content)').get()
        if not date:
            return
        try:
            from datetime import datetime, timezone, timedelta
            UFA_TZ = timezone(timedelta(hours=5))
            dt = datetime.fromisoformat(date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UFA_TZ)
            date = dt.astimezone(UFA_TZ).strftime("%d.%m.%Y %H:%M")
        except (ValueError, TypeError):
            pass
        yield {
            'source': response.meta['source'],
            'date': date,
            'title': response.meta['title'],
            'link': response.url,
        }
