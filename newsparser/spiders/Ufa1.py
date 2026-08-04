from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Ufa1_Spider(scrapy.Spider):
    name = "Ufa1"

    start_urls = ["https://ufa1.ru/text/"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.xpath('//article[@data-test = "archive-record-item"]'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Ufa1.ru')

            l.add_css('date', 'time::attr(datetime)')
            date = l.get_output_value('date')

            date_obj = datetime.strptime(str(date[:10]), "%Y-%m-%d")
            now = datetime.today()

            if now.date() != date_obj.date():
                break
            l.replace_value('date', str(date[:10]))
            l.add_css('title','h2 a::attr(title)')
            l.add_css('link','a::attr(href)')
            link = l.get_output_value('link')
            l.replace_value('link', "https://ufa1.ru" + link)

            yield l.load_item()