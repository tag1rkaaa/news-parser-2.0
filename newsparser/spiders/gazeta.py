import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class Gazeta_Spider(scrapy.Spider):
    name = "gazeta"

    start_urls = ["https://www.gazeta.ru/news/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('a.b_ear.m_techlisting'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Газета.ру')

            l.add_css('date', 'time.b_ear-time::attr(datetime)')
            date = l.get_output_value('date')
            if date:
                l.replace_value('date', str(date))
            l.add_css('title','div.b_ear-title')
            l.add_css('link','a::attr(href)')

            link = l.get_output_value('link')

            if link:
                l.replace_value('link', "https://www.gazeta.ru/" + link)

            yield l.load_item()