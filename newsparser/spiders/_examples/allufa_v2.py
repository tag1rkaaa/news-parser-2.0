from newsparser.core import BaseNewsSpider, DateFormat, ListingOnlyMixin


class AllUfaV2Spider(ListingOnlyMixin, BaseNewsSpider):
    """Listing-only example. All the per-spider boilerplate that the legacy
    `allufa.py` carried (custom_settings, ItemLoader assembly, date strptime,
    URL join, today check) collapses into seven declarative lines.
    """

    name = "allufa_v2"
    source_name = "телеканал Вся Уфа"
    base_url = "https://allufa.ru"
    start_urls = ["https://allufa.ru/news/"]
    feed_type = "local"

    listing_selector = "div.col-xl-4.col-md-6"
    link_selector = "a::attr(href)"
    title_selector = "a.news__card__image img::attr(alt)"
    date_selector = "p.news__card__date.text-light::text"
    date_format = DateFormat.DMY_DOT
