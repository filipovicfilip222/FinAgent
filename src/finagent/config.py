"""Centralised configuration.

All runtime knobs come from environment variables (loaded from a local ``.env``
file if present). Nothing secret is ever hard-coded — see ``.env.example`` for the
full list. ``get_settings()`` is cached so the ``.env`` file is read once.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    # src/finagent/config.py -> project root is three parents up.
    return Path(__file__).resolve().parents[2]


# Load .env from the project root (no-op if the file is absent). Real environment
# variables always win over the file, which is what we want in CI / containers.
load_dotenv(_project_root() / ".env", override=False)


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-5"
    reflect_model: str = ""  # falls back to `model` when empty
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Tools
    sec_user_agent: str = "FinAgent/0.1 (contact@example.com)"
    web_search_provider: str = "anthropic"
    tavily_api_key: str = ""

    # RAG
    embedding_provider: str = "voyage"
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    openai_embedding_model: str = "text-embedding-3-small"
    chroma_dir: str = "data/chroma"

    @property
    def effective_reflect_model(self) -> str:
        return self.reflect_model or self.model

    @property
    def project_root(self) -> Path:
        return _project_root()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        llm_provider=_get("LLM_PROVIDER", "anthropic").lower() or "anthropic",
        anthropic_api_key=_get("ANTHROPIC_API_KEY"),
        model=_get("FINAGENT_MODEL", "claude-sonnet-5"),
        reflect_model=_get("FINAGENT_REFLECT_MODEL"),
        openai_api_key=_get("OPENAI_API_KEY"),
        openai_model=_get("OPENAI_MODEL", "gpt-4o"),
        sec_user_agent=_get("SEC_EDGAR_USER_AGENT", "FinAgent/0.1 (contact@example.com)"),
        web_search_provider=_get("WEB_SEARCH_PROVIDER", "anthropic").lower() or "anthropic",
        tavily_api_key=_get("TAVILY_API_KEY"),
        embedding_provider=_get("EMBEDDING_PROVIDER", "voyage").lower() or "voyage",
        voyage_api_key=_get("VOYAGE_API_KEY"),
        voyage_model=_get("VOYAGE_MODEL", "voyage-3"),
        openai_embedding_model=_get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        chroma_dir=_get("CHROMA_DIR", "data/chroma"),
    )
