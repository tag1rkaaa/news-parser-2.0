from datetime import datetime
import scrapy

from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class Gorobzor_Spider(scrapy.Spider):
    name = "gorobzor"
    start_urls = ["https://gorobzor.ru/novosti"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('article.c-news-n-card'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Горобзор')

            l.add_css('date', 'time.c-news-n-card__date::attr(datetime)')
            date = l.get_output_value('date')

            if not date:
                continue

            date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
            now = datetime.today()

            if now.date() != date_obj.date():
                break

            try:
                from datetime import timezone, timedelta
                UFA_TZ = timezone(timedelta(hours=5))
                dt = datetime.fromisoformat(date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UFA_TZ)
                date = dt.astimezone(UFA_TZ).strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                pass
            l.replace_value('date', date)
            l.add_css('title','h3.c-news-n-card__h')
            l.add_css('link','a.c-news-n-card__more::attr(href)')
            link = l.get_output_value('link')
            if link:
                l.replace_value('link',"https://gorobzor.ru" + link )

            yield l.load_item()