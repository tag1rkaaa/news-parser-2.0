from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Nakanune_Spider(scrapy.Spider):
    name = "nakanune"

    start_urls = ["https://www.nakanune.ru/search/?_search=&author=&articles=1&news=1&video=1&full_text=1&keywords=1&from=&to=&region=521&tematik=&button=искать"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('div.row.newsCard'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Накануне')

            l.add_css('date', 'div.col-md-9.col-8::text')

            date = l.get_output_value('date')
            date_text = date.split('-')[0].strip()
            #print('////////////////////////////////', date_text)

            date_obj = datetime.strptime(date_text[:10], "%d.%m.%Y")
            now = datetime.today()


            if now.date() != date_obj.date():
                break

            l.replace_value('date', date_text[:10])
            l.add_css('title', 'a')
            l.add_css('link', 'a::attr(href)')

            yield l.load_item()