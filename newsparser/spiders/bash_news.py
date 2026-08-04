import scrapy
from newsparser.items import NewsSitesParserItem
from scrapy.loader import ItemLoader

class Bashnews_Spider(scrapy.Spider):
    name = "bash_news"

    start_urls = ["https://bash.news/"]
    
    custom_settings = {'ITEM_PIPELINES': {
        "newsparser.pipelines.RedisPipeline": 1}
    }

    def parse(self, response):

        for article in response.css('article.news-line-item'):
            l = ItemLoader(item=NewsSitesParserItem(), selector=article)

            l.add_value('source', 'БСТ')

            l.add_css('date', 'time::text')
            date = l.get_output_value('date')
            l.replace_value('date', str(date))

            l.add_css('title','a::attr(title)')
            l.add_css('link','a::attr(href)')
            link = l.get_output_value('link')
            l.replace_value('link', 'https://bash.news' + link)

            yield l.load_item()