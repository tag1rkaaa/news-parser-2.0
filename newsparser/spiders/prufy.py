from datetime import datetime
import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Prufy_Spider(scrapy.Spider):
    name = "prufy"

    start_urls = ["https://prufy.ru/news"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):
        for article in response.css('div.lenta-item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'Пруфы')

            l.add_css('title', 'div.news-name::text')
            title = l.get_output_value('title')
            if title is None:
                continue  # Skip this article if the title is None

            l.add_css('link', 'a.news-name-a::attr(href)')
            link = l.get_output_value('link')
            if link is None:
                continue  # Skip this article if the link is None

            if link:
                yield response.follow(link, self.parse_article, meta={'source': 'Пруфы', 'title': title,
                                                                      'link': 'https://prufy.ru' + link})


    def parse_article(self, response):
        date = response.css('meta[itemprop="datePublished"]::attr(content)').get()

        datetime_obj = datetime.fromisoformat(date)

       
        formatted_date = datetime_obj.strftime("%d.%m.%Y %H:%M")
        
        if date[:10] == datetime.now().strftime('%Y-%m-%d'):


            yield {
                'source': response.meta['source'],
                'date': formatted_date,
                'title': response.meta['title'],
                'link': response.meta['link']
            }
        else:
            pass