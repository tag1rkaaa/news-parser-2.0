import json
from datetime import datetime
from urllib.parse import urljoin

import scrapy

from newsparser.items import NewsSitesParserItem


class Bashinform_Spider(scrapy.Spider):
    name = "bashinform"

    start_urls = ["https://www.bashinform.ru/feed"]

    custom_settings = {"ITEM_PIPELINES": {
        "newsparser.pipelines.RedisPipeline": 1,
    }}

    def parse(self, response):
        for script in response.css("script::text").getall():
            if '["ShallowReactive"' in script or '"ShallowReactive"' in script:
                raw = script.strip()
                break
        else:
            self.logger.error("Nuxt data script not found")
            return

        try:
            arr = json.loads(raw)
        except json.JSONDecodeError as e:
            self.logger.error("JSON parse error: %s", e)
            return

        if not isinstance(arr, list):
            self.logger.error("Top-level data is not a list")
            return

        for item in arr:
            if isinstance(item, dict) and "matters" in item:
                matters_ref = item["matters"]
                if not isinstance(matters_ref, int):
                    continue
                matters_arr = arr[matters_ref]
                if not isinstance(matters_arr, list):
                    continue
                for matter_ref in matters_arr:
                    if not isinstance(matter_ref, int):
                        continue
                    matter = arr[matter_ref]
                    if not isinstance(matter, dict):
                        continue
                    parsed = self._extract_matter(arr, matter, response)
                    if parsed:
                        yield parsed
                return

    def _extract_matter(self, arr: list, matter: dict,
                        response) -> NewsSitesParserItem | None:
        def resolve(key):
            v = matter.get(key)
            if isinstance(v, int) and v < len(arr):
                return arr[v]
            return v

        title = resolve("title")
        raw_date = resolve("published_at")
        path = resolve("path")

        if not title or not path:
            return None

        if isinstance(raw_date, str):
            try:
                dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                date = dt.strftime("%d.%m.%Y %H:%M")
            except ValueError:
                date = raw_date[:16]
        else:
            date = ""

        link = urljoin(response.url, path) if not path.startswith("http") else path

        return NewsSitesParserItem(
            source="Башинформ",
            date=date,
            title=str(title).strip(),
            link=link,
        )
