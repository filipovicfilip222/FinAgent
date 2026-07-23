"""Test configuration: force offline-safe providers so the suite never needs a key
or the network. SEC reads the committed fixtures; web search is stubbed; the LLM is
the deterministic mock.
"""

import os

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("WEB_SEARCH_PROVIDER", "stub")
os.environ.setdefault("SEC_EDGAR_MODE", "cache")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from finagent.config import get_settings  # noqa: E402

get_settings.cache_clear()
