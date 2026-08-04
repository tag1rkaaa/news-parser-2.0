"""Pipeline package.

Public classes (configured in settings.py ITEM_PIPELINES):
    - PydanticValidationPipeline
    - RedisDedupPipeline
    - KeywordFilterPipeline
    - NotifyPipeline

Legacy aliases (kept so existing spiders' `custom_settings = {ITEM_PIPELINES:
"newsparser.pipelines.RedisPipeline": 1}` keep working without touching 25 files):
    - RedisPipeline       → LegacyLocalChain  (validation + dedup + notify)
    - KeyWordsCheck       → LegacyFederalChain (validation + keyword + dedup + notify)
    - NewsparserPipeline  → no-op (was a placeholder in the original codebase)
"""
from newsparser.pipelines.dedup import RedisDedupPipeline
from newsparser.pipelines.keyword_filter import KeywordFilterPipeline
from newsparser.pipelines.legacy import (
    LegacyFederalChain,
    LegacyLocalChain,
    NewsparserPipeline,
)
from newsparser.pipelines.notify import NotifyPipeline
from newsparser.pipelines.validation import PydanticValidationPipeline

# Backward-compat aliases for legacy spider custom_settings.
RedisPipeline = LegacyLocalChain
KeyWordsCheck = LegacyFederalChain

__all__ = [
    "KeyWordsCheck",
    "KeywordFilterPipeline",
    "LegacyFederalChain",
    "LegacyLocalChain",
    "NewsparserPipeline",
    "NotifyPipeline",
    "PydanticValidationPipeline",
    "RedisDedupPipeline",
    "RedisPipeline",
]
