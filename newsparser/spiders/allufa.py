from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class AllUfa_Spider(scrapy.Spider):
    name = "allufa"

    start_urls = ["https://allufa.ru/news/"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('div.col-xl-4.col-md-6'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'телеканал Вся Уфа')

            l.add_css('date', 'p.news__card__date.text-light')
            date = l.get_output_value('date')

            date_obj = datetime.strptime(date, "%d.%m.%Y")
            now = datetime.today()

            if now.date() == date_obj.date():
                l.add_css('title','a.news__card__image img::attr(alt)')
                l.add_css('link','a::attr(href)')
                link = l.get_output_value('link')
                l.replace_value('link', 'https://allufa.ru' + link)

                yield l.load_item()