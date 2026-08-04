"""Scrapy project settings — wired through pydantic-settings.

All secrets live in .env. All tunable thresholds live in
newsparser.core.settings_loader.NewsparserSettings. This file only translates
those into Scrapy framework knobs and assembles middleware/pipeline/extension
chains.
"""
from __future__ import annotations

import logging.config
import ssl
from pathlib import Path

from services.log_setup import ExtraFieldsFormatter
from newsparser.core.settings_loader import get_settings

_cfg = get_settings()

BOT_NAME = "newsparser"
SPIDER_MODULES = ["newsparser.spiders"]
NEWSPIDER_MODULE = "newsparser.spiders"

# ---- SSL — skip verification for sites with self-signed certs ----
DOWNLOADER_CLIENT_TLS_VERIFY = False
TLS_VERIFIER_ENABLED = False

# ---- HTTP behavior ----
ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_TIMEOUT = 20
DOWNLOAD_DELAY = 0.5
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.7",
}

# Retry — aggressive sites (e.g. sterlegrad 429) still get one retry.
RETRY_ENABLED = True
RETRY_TIMES = 2
RETRY_HTTP_CODES = [408, 429, 500, 502, 503, 504]

# AutoThrottle — lightweight; max 10 s delay.
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
AUTOTHROTTLE_DEBUG = False

# Per-domain delay map (consumed by slot config)
import os
DOWNLOAD_SLOTS = {
    domain: {"delay": delay, "concurrency": 1}
    for domain, delay in _cfg.domain_download_delays.items()
}

# HTTP cache — 1 hour TTL, stored in a Docker volume.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600
HTTPCACHE_DIR = "/tmp/httpcache"

# ---- Pipelines ----
ITEM_PIPELINES = {
    "newsparser.pipelines.PydanticValidationPipeline": 100,
    "newsparser.pipelines.KeywordFilterPipeline": 200,
    "newsparser.pipelines.RedisDedupPipeline": 300,
    "newsparser.pipelines.NotifyPipeline": 400,
}

# ---- Middlewares ----
DOWNLOADER_MIDDLEWARES = {
    "newsparser.middlewares.PrufyHtmlFixMiddleware": 300,
    "newsparser.middlewares.UserAgentRotationMiddleware": 400,
    "newsparser.middlewares.RetryWithBackoffMiddleware": 540,
}

# ---- Extensions ----
EXTENSIONS = {
    "newsparser.extensions.SpiderStatsExtension": 500,
}

# ---- Async/reactor ----
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
FEED_EXPORT_ENCODING = "utf-8"

# ---- Logging — suppress noise ----
LOG_LEVEL = _cfg.log_level
LOG_FORMAT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
LOG_ENABLED = True
LOG_STDOUT = False

if _cfg.log_file is not None:
    Path(_cfg.log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": "services.log_setup.ExtraFieldsFormatter",
                    "fmt": LOG_FORMAT,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": _cfg.log_level,
                },
                "file": {
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "filename": str(_cfg.log_file),
                    "maxBytes": _cfg.log_rotation_bytes,
                    "backupCount": _cfg.log_rotation_backups,
                    "encoding": "utf-8",
                    "level": _cfg.log_level,
                },
            },
            "root": {
                "level": _cfg.log_level,
                "handlers": ["console", "file"],
            },
        }
    )
