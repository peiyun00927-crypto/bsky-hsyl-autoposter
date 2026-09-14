"""
Configuration module for Bluesky Daily Auto-Poster.
Loads environment variables and sets defaults.
"""
import os
from pathlib import Path

# Load .env file if present
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=ENV_FILE)
    except ImportError:
        # Simple fallback parser if python-dotenv is not installed
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

# Bluesky Credentials
BSKY_HANDLE = os.getenv("BSKY_HANDLE", "").strip()
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD", "").strip()
BSKY_SERVICE_URL = os.getenv("BSKY_SERVICE_URL", "https://bsky.social").strip().rstrip("/")

# Target Website
HSYL_BASE_URL = os.getenv("HSYL_BASE_URL", "https://www.hsylkitchen.com").strip().rstrip("/")
SITEMAP_URL = f"{HSYL_BASE_URL}/sitemap.xml"

# Operational Flags
DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("1", "true", "yes")

# Storage Paths
HISTORY_FILE = BASE_DIR / "posted_history.json"
QUEUE_FILE = BASE_DIR / "post_queue.json"

# Bluesky limits
MAX_POST_CHARS = 300
