import scrapy
from newsparser.items import NewsSitesParserItem, Get_date
from scrapy.loader import ItemLoader

class NTV_Spider(scrapy.Spider):
    name = "ntv"

    start_urls = ["https://www.ntv.ru/novosti/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }

    def parse(self, response):

        for article in response.css('div.list-card.news-list-widget__item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'НТВ')

            l.add_css('date', 'p.cap.cap-xs.list-card__time')
            date = l.get_output_value("date")
            current_time = Get_date()
            time = current_time.current_date(date)

            if date:
                l.replace_value('date', time)

            l.add_css('title','p.c.c-m.list-card__title')
            l.add_css('link','a.router-ui.hov-b::attr(href)')

            link = l.get_output_value('link')
            if link:
                l.replace_value('link', "https://www.ntv.ru" + link)

            yield l.load_item()