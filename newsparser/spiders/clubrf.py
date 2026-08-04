from datetime import datetime

import scrapy
from itemloaders.processors import MapCompose
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader
from w3lib.html import remove_tags


class Clubrf_Spider(scrapy.Spider):
    name = "clubrf"

    start_urls = ["http://club-rf.ru/news"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('div.content-box'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            region = l.get_css('span.region',MapCompose(remove_tags))

            if "Республика Башкортостан" in region:

                l.add_value('source', 'Клуб Регионов РФ')

                l.add_css('date', 'span.date')
                date = l.get_output_value('date')

                date_obj = datetime.strptime(date, "%d.%m.%Y")
                now = datetime.today()

                if now.date() != date_obj.date():
                    break

                l.add_css('title','h4')
                l.add_css('link','h4 a::attr(href)')

            else:
                break

            yield l.load_item()