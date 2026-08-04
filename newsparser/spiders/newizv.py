import scrapy
from newsparser.items import NewsSitesParserItem, Get_date
from scrapy.loader import ItemLoader

class Newizv_Spider(scrapy.Spider):
    name = "newizv"

    start_urls = ["https://newizv.ru/news"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('div.mb-8'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Новые известия')

            l.add_css('date', 'div.DesktopListItem_date__RdmGW')
            date = l.get_output_value('date')
            current_date = Get_date()
            time = current_date.current_date()
            l.replace_value('date', f'{time} {str(date)[8:]}')

            l.add_css('title','div.DesktopListItem_title__5_boe')
            l.add_css('link','a::attr(href)')
            link = l.get_output_value('link')

            if "Сегодня" not in date:
                break

            if link:
                l.replace_value('link', "https://newizv.ru" + link)

            yield l.load_item()