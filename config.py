"""Central paths and defaults for the Auto Graphics pipeline."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env")

LIBRARY_DIR = PROJECT_ROOT / "library"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
FONTS_DIR = PROJECT_ROOT / "fonts"
SFX_DIR = PROJECT_ROOT / "sfx"
# Imported SFX filenames (replace files in sfx/ to swap sounds).
SFX_TYPING = SFX_DIR / "Keyboard-Typing.mp3"
SFX_CLICK = SFX_DIR / "mouse-click.mp3"
# How long of the typing track to keep under the intro (seconds).
SFX_TYPING_SECONDS = 3.0
EXPORTS_DIR = PROJECT_ROOT / "exports"
TEMP_DIR = PROJECT_ROOT / "temp"
USAGE_LOG_PATH = PROJECT_ROOT / "usage_log.json"

DEFAULT_TEMPLATE = "hook"
DEFAULT_BODY_SECONDS = 2.0
INTRO_CUT_SECONDS = 0.5
INTRO_CUT_COUNT = 6

# Top-level media kinds under library/
MEDIA_KINDS = ("photos", "videos")

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
FONT_EXTENSIONS = {".ttf", ".otf"}

# Carousel thumbnail slides always come from this library tag.
THUMBNAIL_LIBRARY = "photos/thumbnails"

# Number of most recent picks per library to avoid repeating.
RECENT_SKIP_COUNT = 3

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))


def library_folder(tag: str) -> Path:
    """Resolve a tag like 'photos/hooks' to library/photos/hooks/."""
    return LIBRARY_DIR / Path(tag)


def valid_libraries() -> list[str]:
    """Return tags for every category folder: photos/hooks, videos/coding, ..."""
    tags: list[str] = []
    if not LIBRARY_DIR.is_dir():
        return tags
    for kind in MEDIA_KINDS:
        kind_dir = LIBRARY_DIR / kind
        if not kind_dir.is_dir():
            continue
        for category in sorted(p.name for p in kind_dir.iterdir() if p.is_dir()):
            tags.append(f"{kind}/{category}")
    return tags


def list_templates() -> list[str]:
    """Return template names (without .json) from templates/."""
    if not TEMPLATES_DIR.is_dir():
        return []
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.json"))


def list_fonts() -> list[str]:
    """Return font filenames in fonts/."""
    if not FONTS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in FONTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS
    )


def list_sfx() -> list[str]:
    """Return sound-effect filenames in sfx/."""
    if not SFX_DIR.is_dir():
        return []
    return sorted(
        p.name for p in SFX_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".wav", ".mp3", ".m4a", ".aac"}
    )
