import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class RTVI_Spider(scrapy.Spider):
    name = "rtvi"

    start_urls = ["https://rtvi.com/news/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('div.arch-block'):
            l = ItemLoader(item = NewsSitesParserItem(), selector = article)

            l.add_value('source', 'RTVI')

            l.add_css('date', 'div.date')
            l.add_css('title','h2.arch-title')
            l.add_css('link','a::attr(href)')

            yield l.load_item()