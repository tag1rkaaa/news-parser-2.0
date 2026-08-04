# Newsparser 2.0

Scrapy-based монитор российских новостных сайтов: ~25 спайдеров (`scrapy.Spider`) + RSS-агрегатор, async-доставка в Telegram + RabbitMQ, дедупликация в Redis, Prometheus-метрики и алерты при падении сайтов.

## Быстрый старт

```bash
cp .env.example .env
# Заполни TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, TELEGRAM_ALERT_CHAT_ID
docker compose -f deploy/docker-compose.yml up -d --build
```

Через 30 сек:
- Grafana — http://localhost:3000 (admin / admin), дашборд `Newsparser Overview` загружен автоматически
- Prometheus — http://localhost:9090
- RabbitMQ UI — http://localhost:15672 (guest / guest)
- Метрики краулера — http://localhost:8000/metrics

## Локальный запуск без Docker

```bash
python -m venv .venv && source .venv/bin/activate  # или .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # отредактируй
mkdir logs

# Один прогон всех спайдеров + RSS
python spiders_starter.py

# Только RSS
python spiders_starter.py --rss-only

# Только один спайдер
python spiders_starter.py --scrapy-only --spider=tass

# Долгоиграющий (каждые 10 мин), как в docker compose
python spiders_starter.py --loop=600
```

## Мониторинг

| Метрика | Что показывает | Когда тревожно |
|---|---|---|
| `newsparser_items_scraped_total{spider}` | Всего собрано item'ов | rate == 0 несколько прогонов |
| `newsparser_items_dropped_total{reason}` | Отброшено (dup / no_keyword / validation_failed) | Резкий рост `validation_failed` → менялась вёрстка |
| `newsparser_errors_total{type}` | HTTP / parsing / pipeline ошибки | > 50% от всех запросов |
| `newsparser_spider_health` | 0=down, 1=degraded, 2=healthy | долго 0 / 1 |
| `time() - newsparser_spider_last_success_timestamp` | Возраст последнего успеха | > 6h → critical |

Алерты автоматически уходят в `TELEGRAM_ALERT_CHAT_ID` (см. `services/alert_watcher.py`).

## Структура проекта

```
newsparser/
├── core/               # BaseNewsSpider, date_utils, settings_loader
├── extensions/         # Prometheus exporter + signals → metrics
├── pipelines/          # validation, dedup, keyword_filter, notify + legacy aliases
├── spiders/            # 25 legacy spiders + _examples/ on BaseNewsSpider
├── items.py            # NewsSitesParserItem (legacy) + NewsItem (pydantic v2)
├── middlewares.py      # UA rotation, smart throttle, retry-with-backoff
└── settings.py
services/               # async I/O: telegram (aiogram), rabbitmq (aio-pika), rss_runner, alert_watcher
deploy/                 # Dockerfile, docker-compose, Prometheus + Grafana provisioning
spiders_starter.py      # Entrypoint (discovery; --loop / --rss-only / --scrapy-only)
```

## Что в Фазе 1 НЕ переписывалось

Существующие 25 спайдеров продолжают работать через `pipelines.RedisPipeline` / `pipelines.KeyWordsCheck` (алиасы на новую цепочку validation→dedup→notify). Их следует постепенно мигрировать на `BaseNewsSpider` по образцу `newsparser/spiders/_examples/{allufa,tass,kommersant}_v2.py`.

## Дальнейшие улучшения (приоритет)

1. **Миграция 25 спайдеров на `BaseNewsSpider`** — устраняет копипаст и стандартизирует фильтрацию свежести.
2. **Unit-тесты** `core/date_utils.py`, `pipelines/dedup.py`, `pipelines/keyword_filter.py` (pytest + pytest-asyncio).
3. **Integration-тесты спайдеров** через VCR.py / `scrapy.utils.test`: snapshot HTML, проверка количества items.
4. **Авто-детект изменений структуры сайта**: хеш списка селекторов; алёрт при 0 items + нет HTTP-ошибок.
5. **CI/CD**: GitHub Actions с ruff, mypy, pytest, docker build, push в registry.
6. **Прозрачные прокси** для сайтов с банами (отдельный middleware с пулом).
7. **Replay-mode** для разработки спайдеров: HTTPCACHE_ENABLED=1 + сохранение HTML в fixtures.
