from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Rbversia_Spider(scrapy.Spider):
    name = "rb_versia"
    start_urls = ["https://rb.versia.ru/news"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('div.news__item.news-card'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Версия в Башкортостане')

            l.add_css('date', 'time.info.fs-i.fw-b::text')
            date = l.get_output_value('date')

            date_obj = datetime.strptime(date[:10], "%d.%m.%Y")
            now = datetime.today()

            l.replace_value('date', date)
            l.add_css('title', 'a::attr(title)')
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')
            l.replace_value('link', 'https://rb.versia.ru' + link)

            if now.date() != date_obj.date():
                break

            yield l.load_item()