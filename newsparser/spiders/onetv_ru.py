import scrapy
from newsparser.items import NewsSitesParserItem, Get_date
from scrapy.loader import ItemLoader

class One_Spider(scrapy.Spider):
    name = "1tv"

    start_urls = ["https://www.1tv.ru/news/"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }
    def parse(self, response):

        for article in response.css('article.Card_card__9ZEyG'):
            l = ItemLoader(item = NewsSitesParserItem(), selector = article)

            l.add_value('source', 'Первый канал')

            l.add_css('date', 'time.Card_date___Cuvr::text')
            date = l.get_output_value("date")
            current_time = Get_date()
            time = current_time.current_date(date)

            if date:
                l.replace_value('date', time)

            l.add_css('title', 'h3.Card_title__6ViU8::text')
            l.add_css('link', 'a::attr(href)')

            yield l.load_item()
