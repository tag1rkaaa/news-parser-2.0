from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class NewsparserSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    # Telegram
    telegram_bot_token: SecretStr = Field(..., alias="TELEGRAM_BOT_TOKEN")
    telegram_channel_id: int = Field(..., alias="TELEGRAM_CHANNEL_ID")
    telegram_alert_chat_id: int = Field(..., alias="TELEGRAM_ALERT_CHAT_ID")
    telegram_rate_limit_per_sec: float = Field(0.5, alias="TELEGRAM_RATE_LIMIT_PER_SEC")
    telegram_proxy_host: str | None = Field(None, alias="TELEGRAM_PROXY_HOST")
    telegram_proxy_port: int | None = Field(None, alias="TELEGRAM_PROXY_PORT")
    telegram_proxy_user: str | None = Field(None, alias="TELEGRAM_PROXY_USER")
    telegram_proxy_pass: SecretStr | None = Field(None, alias="TELEGRAM_PROXY_PASS")
    telegram_proxy_type: str = Field("socks5", alias="TELEGRAM_PROXY_TYPE")

    # Redis
    redis_host: str = Field("redis", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")
    redis_password: SecretStr | None = Field(None, alias="REDIS_PASSWORD")
    redis_dedup_ttl_seconds: int = Field(7 * 24 * 3600, alias="REDIS_DEDUP_TTL_SECONDS")

    # RabbitMQ
    rabbitmq_url: SecretStr = Field("amqp://guest:guest@rabbitmq:5672/", alias="RABBITMQ_URL")
    rabbitmq_queue: str = Field("parsed_data", alias="RABBITMQ_QUEUE")

    # Prometheus
    prometheus_port: int = Field(8000, alias="PROMETHEUS_PORT")
    prometheus_url: str = Field("http://prometheus:9090", alias="PROMETHEUS_URL")

    # Alert thresholds
    alert_last_success_max_age_seconds: int = Field(6 * 3600, alias="ALERT_LAST_SUCCESS_MAX_AGE_SECONDS")
    alert_error_rate_threshold: float = Field(0.5, alias="ALERT_ERROR_RATE_THRESHOLD")
    alert_unhealthy_spider_ratio: float = Field(0.3, alias="ALERT_UNHEALTHY_SPIDER_RATIO")
    alert_watcher_interval_seconds: int = Field(60, alias="ALERT_WATCHER_INTERVAL_SECONDS")

    # Per-domain throttling (JSON-encoded dict of domain -> delay seconds)
    domain_download_delays: dict[str, float] = Field(
        default_factory=lambda: {
            "tass.ru": 1.0,
            "kommersant.ru": 2.0,
            "rbc.ru": 1.5,
            "lenta.ru": 1.0,
        },
        alias="DOMAIN_DOWNLOAD_DELAYS",
    )

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file: Path | None = Field(PROJECT_ROOT / "logs" / "newsparser.log", alias="LOG_FILE")
    log_rotation_bytes: int = Field(50 * 1024 * 1024, alias="LOG_ROTATION_BYTES")
    log_rotation_backups: int = Field(5, alias="LOG_ROTATION_BACKUPS")

    # Filters
    region_keywords: list[str] = Field(
        default_factory=lambda: [
            "Хабиров", "Башкири", "Башкортостан", "Назаров", "башкир", "башкирский",
            "Уфа", "Уфе", "Уфы", "уфимский", "Стерлитамак", "Ишимбай", "Нефтекамск",
            "Агидель", "Мелеуз", "Бирск", "Белорецк", "Баймак", "Сибай", "Кумертау",
        ],
        alias="REGION_KEYWORDS",
    )
    ad_filter_words: list[str] = Field(
        default_factory=lambda: ["скидка", "₽", "ERID", "erid", "Erid", "Рекламный материал"],
        alias="AD_FILTER_WORDS",
    )


@lru_cache(maxsize=1)
def get_settings() -> NewsparserSettings:
    return NewsparserSettings()  # type: ignore[call-arg]
