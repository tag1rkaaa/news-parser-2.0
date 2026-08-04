import scrapy
from datetime import datetime
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class MKSet_Spider(scrapy.Spider):
    name = "mkset"

    start_urls = ["https://mkset.ru/news"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('div.mb-8'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Медиакорсеть')

            l.add_css('date', 'div.DesktopListItem_date__RdmGW')

            l.add_css('title','div.DesktopListItem_title__5_boe')
            l.add_css('link','a::attr(href)')
            link = l.get_output_value('link')

            date_obj = datetime.strptime(str(link[6:16]), "%Y-%m-%d")
            now = datetime.today()

            if now.date() != date_obj.date():
                break

            if link:
                l.replace_value('link', "https://mkset.ru" + link)

            yield l.load_item()