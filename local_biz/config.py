"""Configuration and environment loading."""

import os
from pathlib import Path

# Try loading .env from the project root
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())


def get_places_api_key():
    key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not key:
        raise SystemExit(
            "GOOGLE_PLACES_API_KEY not set. "
            "Add it to .env or export it as an environment variable."
        )
    return key


def get_anthropic_api_key():
    return os.environ.get("ANTHROPIC_API_KEY")


# Directories — configurable via env vars, sensible defaults
OUTPUT_DIR = Path(os.environ.get("LOCAL_BIZ_OUTPUT", "./output"))
DEMOS_DIR = OUTPUT_DIR / "demos"
RESULTS_DIR = OUTPUT_DIR / "results"
TEMPLATES_DIR = Path(os.environ.get("LOCAL_BIZ_TEMPLATES", "./templates"))

# HTTP headers for fetching business websites
USER_AGENT = "local-biz-cli/0.1 (lead-research)"
SCRAPE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}
