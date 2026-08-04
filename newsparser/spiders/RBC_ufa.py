from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class RBC_Spider(scrapy.Spider):
    name = 'rbc_ufa'

    start_urls = ['https://ufa.rbc.ru/ufa/']

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('article.info-block'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'РБК-Уфа')

            l.add_css('date', 'div.meta-info-row-date::text')
            date = l.get_output_value('date')
            if len(str(date)) > 5:
                break

            today = datetime.now().strftime("%d.%m.%Y")
            l.replace_value('date', f'{today} {date}')
            l.add_css('title', 'a.info-block-title span::text')
            l.add_css('link', 'a.info-block-title::attr(href)')

            yield l.load_item()
