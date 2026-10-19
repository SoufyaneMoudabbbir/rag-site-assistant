"""Settings, read once from environment variables (and an optional .env file)."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


# --- LLM (any OpenAI-compatible API: DeepSeek, OpenAI, Mistral, a local Ollama...)
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").strip() or "https://api.deepseek.com"
LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or "deepseek-flash"

# --- Embeddings (run locally on CPU, no API key needed)
EMBED_MODEL = os.getenv("EMBED_MODEL", "").strip() or "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

# --- Storage
DATA_DIR = Path(os.getenv("DATA_DIR", "") or ROOT / "data")
DB_PATH = DATA_DIR / "assistant.db"

# --- Admin
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
# Anyone can log in with this password and look around, but cannot change anything.
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "").strip() or "demo"

# --- Abuse protection for a public demo
RATE_LIMIT_MESSAGES = _int("RATE_LIMIT_MESSAGES", 20)  # per visitor IP...
RATE_LIMIT_WINDOW = _int("RATE_LIMIT_WINDOW", 600)  # ...per this many seconds
DAILY_MESSAGE_LIMIT = _int("DAILY_MESSAGE_LIMIT", 500)  # all visitors together
MAX_MESSAGE_CHARS = 600
MAX_HISTORY_TURNS = 6

# --- Retrieval
TOP_K = 5

# --- Static files
DEMO_SITE_DIR = ROOT / "demo-site"
WIDGET_DIST = ROOT / "widget" / "dist"
ADMIN_DIST = ROOT / "admin" / "dist"
