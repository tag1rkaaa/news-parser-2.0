from datetime import datetime

import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader


class Kommersant_Spider(scrapy.Spider):
    name = 'kommersant'
    start_urls = ['https://www.kommersant.ru/regions/2']
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):


        #парсер топ-ленты
        for article in response.css('article.top_news__item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')
            l.add_css('title','a::text')
            title = l.get_output_value('title')
            title.strip() if title else None
            source = 'Коммерсант'
            if link:
                new_link = link.split('?')
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': title, 'link': 'https://www.kommersant.ru' + new_link[0]})

        #парсер заглавной новости топа
        for article in response.css('article.top_news_main'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')
            l.add_css('title', 'a::text')
            title = l.get_output_value('title')
            title.strip() if title else None
            source = 'Коммерсант'
            if link:
                new_link = link.split('?')
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': title, 'link': 'https://www.kommersant.ru' + new_link[0]})

        #парсер заглавной новости, если она с фото
        for article in response.css('div.top_news_hot'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)
            l.add_css('link', 'a::attr(href)')
            link = l.get_output_value('link')
            #new_link = link.split('?')
            title = article.css('.top_news_hot__text h1::text').getall()
            #print('///////////////////', title)
            l.add_value('title', title[1])
            title = l.get_output_value('title')
            #print('//////////////////', link)
            title.strip()
            source = 'Коммерсант'
            if link:
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': title, 'link': 'https://www.kommersant.ru' + link})

        #парсер блока "главное"
        for article in response.css('article.uho'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)
            sub_title = article.css('h3.title_15.uho__subtitle.m-title_20 > a.uho__link::text').get()
            l.add_css('link', 'h2.title_20.uho__name.m-title_24 > a.uho__link.uho__link--overlay::attr(href)')
            link = l.get_output_value('link')
            l.add_css('title', 'h2.title_20.uho__name.m-title_24 > a.uho__link.uho__link--overlay::text')
            title = l.get_output_value('title')
            full_title = f'{title}\n{sub_title}'
            l.replace_value('title', full_title)
            source = 'Коммерсант'
            if link:
                new_link = link.split('?')
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': full_title, 'link': 'https://www.kommersant.ru' + new_link[0]})


    #парсинг отдельной статьи
    def parse_article(self, response):
        region = response.css('a.decor::text').get()

        if region in {'Башкортостан', 'Башкортостан / Эксклюзив'}:
            date = response.css('time.doc_header__publish_time::text').get()
            current_date = str(date[:10])
            if current_date == datetime.now().strftime('%d.%m.%Y'):
                yield {
                    'source': response.meta['source'],
                    'date': date,
                    'title': response.meta['title'],
                    'link': response.meta['link']
                 }
