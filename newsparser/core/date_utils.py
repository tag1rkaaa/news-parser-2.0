from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from enum import StrEnum

from dateutil import parser as dateutil_parser


class DateFormat(StrEnum):
    DMY_DOT = "dmy_dot"             # 25.12.2024
    DMY_DOT_TIME = "dmy_dot_time"   # 25.12.2024 14:30
    ISO = "iso"                     # 2024-12-25
    ISO_TIME = "iso_time"           # 2024-12-25T14:30:00
    RU_TEXT = "ru_text"             # "Сегодня 14:30" / "Вчера 09:00"
    IN_URL = "in_url"               # /news/2024/12/25/foo.html (slice [a:b])
    AUTO = "auto"                   # dateutil best-effort


_RU_RELATIVE = {
    "сегодня": 0,
    "today": 0,
    "вчера": 1,
    "yesterday": 1,
}

_RU_AGO = {
    "минуту": 1, "минуты": 1, "минут": 1, "мин": 1,
    "час": 1, "часа": 1, "часов": 1,
    "секунду": 1, "секунды": 1, "секунд": 1, "сек": 1,
    "день": 1, "дня": 1, "дней": 1,
}


def _strip_tz(dt: datetime) -> datetime:
    """Strip timezone info, keeping the local time as-is."""
    return dt.replace(tzinfo=None)


def _parse_ago(text: str, now: datetime) -> datetime | None:
    """Parse strings like '13 минут назад', 'час назад', '2 часа назад'."""
    lower = text.lower()
    if "назад" not in lower:
        return None
    num_match = re.search(r"(\d+)", text)
    num = int(num_match.group(1)) if num_match else 1
    if "минут" in lower or "мин" in lower:
        return now - timedelta(minutes=num)
    if "час" in lower:
        return now - timedelta(hours=num)
    if "секунд" in lower or "сек" in lower:
        return now - timedelta(seconds=num)
    if "дн" in lower:
        return now - timedelta(days=num)
    return None


def parse_news_date(
    raw: str | None,
    fmt: DateFormat = DateFormat.AUTO,
    *,
    url_slice: tuple[int, int] | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """Parse a date string and return a naive datetime with the exact time
    as it appeared on the source site. No timezone conversion.

    Returns None when parsing fails or input is empty.
    """
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None

    today = (now or datetime.now()).replace(microsecond=0)

    try:
        if fmt is DateFormat.DMY_DOT:
            return datetime.strptime(cleaned[:10], "%d.%m.%Y")
        if fmt is DateFormat.DMY_DOT_TIME:
            return datetime.strptime(cleaned[:16], "%d.%m.%Y %H:%M")
        if fmt is DateFormat.ISO:
            return datetime.strptime(cleaned[:10], "%Y-%m-%d")
        if fmt is DateFormat.ISO_TIME:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            return _strip_tz(dt)
        if fmt is DateFormat.RU_TEXT:
            return _parse_ru_relative(cleaned, today)
        if fmt is DateFormat.IN_URL:
            if url_slice is None:
                return None
            a, b = url_slice
            return datetime.strptime(cleaned[a:b], "%Y/%m/%d")
        if fmt is DateFormat.AUTO:
            ago = _parse_ago(cleaned, today)
            if ago is not None:
                return ago
            dt = dateutil_parser.parse(cleaned, dayfirst=True, fuzzy=True)
            return _strip_tz(dt)
    except (ValueError, TypeError):
        return None
    return None


def _parse_ru_relative(text: str, now: datetime) -> datetime | None:
    """Parse strings like 'Сегодня 14:30' / 'вчера 09:00' / bare 'сегодня'."""
    lower = text.lower()
    matched_day: int | None = None
    for keyword, offset in _RU_RELATIVE.items():
        if keyword in lower:
            matched_day = offset
            break
    if matched_day is None:
        return None
    base = (now - timedelta(days=matched_day)).date()
    time_match = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if time_match:
        hh, mm = int(time_match.group(1)), int(time_match.group(2))
        return datetime.combine(base, datetime.min.time().replace(hour=hh, minute=mm))
    return datetime.combine(base, datetime.min.time())


def is_today(dt: datetime | date | None, *, now: datetime | None = None) -> bool:
    if dt is None:
        return False
    target = dt.date() if isinstance(dt, datetime) else dt
    return target == (now or datetime.now()).date()


def normalize_iso(dt: datetime | None) -> str | None:
    """Render a datetime as-is: DD.MM.YYYY HH:MM"""
    if dt is None:
        return None
    return dt.strftime("%d.%m.%Y %H:%M")
