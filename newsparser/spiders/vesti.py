import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class Vesti_Spider(scrapy.Spider):
    name = "vesti"

    start_urls = ["https://www.vesti.ru/news"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('.news-feed-item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Вести')

            l.add_css('date', 'time::text')
            l.add_css('title','.news-feed-item__caption::text')
            l.add_css('link','a::attr(href)')

            link = l.get_output_value('link')
            if link:
                l.replace_value('link', 'https://www.vesti.ru' + link)

                yield l.load_item()