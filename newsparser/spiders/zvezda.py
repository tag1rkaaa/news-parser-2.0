from datetime import datetime
import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Zvezda_Spider(scrapy.Spider):
    name = "zvezda"
    
    start_urls = ["https://tvzvezda.ru/news/search/башкирия"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.KeyWordsCheck": 1}
    }
   
    def parse(self, response):

        for article in response.css('z-news-snippet.has-overlay.ng-star-inserted'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')
            l.add_css('title','div.text.h4::text')
            title = l.get_output_value('title')
            #title.strip()
            source = 'Звезда'
            if link:
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': title, 'link': 'https://tvzvezda.ru' + link})

    
    
    
    def parse_article(self, response):
    
        date = response.css('div.mt-2.mb-1 span::text').getall()
        if len(date) > 1:
            #print(date)
            date = date[1]
            current_date = str(date[:10])
            if current_date == datetime.now().strftime('%Y-%m-%d'):
                yield {
                    'source': response.meta['source'],
                    'date': date,
                    'title': response.meta['title'],
                    'link': response.meta['link']
                    }
            else:
                pass
        else:
            pass