import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader
from datetime import datetime



class TASS_Spider(scrapy.Spider):
    name = "tass"
    start_urls = ["https://tass.ru/tag/bashkortostan"]

    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('a.tass_pkg_link-v5WdK'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'ТАСС')
            source = l.get_output_value('source')


            l.add_css('date', 'div.tass_pkg_marker-JPOGl.tass_pkg_marker--font_weight_black-abSnD.tass_pkg_marker--color_primary-ZDD1e::text')

            l.add_css('title','div.tass_pkg_title_wrapper-i0jgn')
            l.add_css('link','a.tass_pkg_link-v5WdK::attr(href)')
            title = l.get_output_value('title')
            link = l.get_output_value('link')

            #yield l.load_item()

            if link:
                yield response.follow(link, self.parse_article, meta={'source': source, 'title': title,
                                                                      'link': "https://tass.ru" +
                                                                              link})


    def parse_article(self, response):
        date = response.css('span[ca-tsm]::text').get()
        timestamp = response.css('span[ca-ts]::attr(ca-ts)').get()
        timestamp_corrected = int(timestamp) / 1000
        date_from_article = datetime.fromtimestamp(timestamp_corrected).date()

        current_date = datetime.today()


        if current_date.date() == date_from_article:

            yield {
                'source': response.meta['source'],
                'date': date,
                'title': response.meta['title'],
                'link': response.meta['link']
            }
        else:
            pass