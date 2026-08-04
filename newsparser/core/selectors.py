from __future__ import annotations

from urllib.parse import urljoin, urlparse

from parsel import Selector


def safe_first(selector: Selector, css: str, *, default: str = "") -> str:
    value = selector.css(css).get()
    return value.strip() if value else default


def absolute_url(base: str, link: str | None) -> str | None:
    """Always returns a fully-qualified URL or None.

    Handles three cases collapsed in legacy spiders:
      * already absolute → returned as is
      * leading-slash relative → urljoin
      * scheme-relative // → urljoin
    """
    if not link:
        return None
    link = link.strip()
    parsed = urlparse(link)
    if parsed.scheme and parsed.netloc:
        return link
    return urljoin(base, link)


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")
