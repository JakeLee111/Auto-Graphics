"""Pick a media file from a library category folder, avoiding recent repeats."""

import json
import random
from pathlib import Path

import config
from src.models import PipelineError


def _load_usage_log() -> dict[str, list[str]]:
    if not config.USAGE_LOG_PATH.exists():
        return {}
    try:
        return json.loads(config.USAGE_LOG_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_usage_log(log: dict[str, list[str]]) -> None:
    config.USAGE_LOG_PATH.write_text(json.dumps(log, indent=2))


def list_media(library: str, images_only: bool = False) -> list[Path]:
    """Return media files in library/<kind>/<category>/, sorted by name.

    Args:
        library: Tag like 'photos/hooks' or 'videos/coding'.
        images_only: If True, only return image files.
    """
    folder = config.library_folder(library)
    if not folder.is_dir():
        raise PipelineError(f"Library folder does not exist: {folder}")
    extensions = config.IMAGE_EXTENSIONS if images_only else config.MEDIA_EXTENSIONS
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )


def pick_media(library: str, images_only: bool = False) -> Path:
    """Pick a random file from the category, skipping recently used ones.

    For photos/ tags, prefers images. Falls back to any media only when
    images_only was requested and the folder has no photos (caller may
    extract a still from video).
    """
    # Photos libraries should prefer real images.
    if library.startswith("photos/"):
        images_only = True

    files = list_media(library, images_only=images_only)
    if not files and images_only and library.startswith("photos/"):
        raise PipelineError(
            f"No photos in '{library}'. "
            f"Add .jpg/.jpeg/.png files to library/{library}/"
        )
    if not files and images_only:
        files = list_media(library, images_only=False)
    if not files:
        kind_hint = (
            ".jpg/.jpeg/.png" if library.startswith("photos/")
            else ".mp4/.mov (or photos)"
        )
        raise PipelineError(
            f"No media files in library '{library}'. "
            f"Add {kind_hint} files to library/{library}/"
        )

    log = _load_usage_log()
    recent = set(log.get(library, [])[-config.RECENT_SKIP_COUNT:])
    fresh = [p for p in files if p.name not in recent]
    choice = random.choice(fresh if fresh else files)

    history = log.get(library, [])
    history.append(choice.name)
    log[library] = history[-20:]
    _save_usage_log(log)

    return choice


def list_all_videos() -> list[Path]:
    """Return every video file under library/videos/*/, sorted by path."""
    videos_root = config.LIBRARY_DIR / "videos"
    if not videos_root.is_dir():
        return []
    files: list[Path] = []
    for category in videos_root.iterdir():
        if not category.is_dir():
            continue
        for path in category.iterdir():
            if path.is_file() and path.suffix.lower() in config.VIDEO_EXTENSIONS:
                files.append(path)
    return sorted(files)


def pick_intro_clips(count: int) -> list[Path]:
    """Pick `count` video clips from the whole videos/ tree for the hook intro.

    Prefers unique files; if there are fewer files than cuts, reuses with shuffle.
    """
    files = list_all_videos()
    if not files:
        raise PipelineError(
            "No videos for the hook intro. "
            "Add .mp4/.mov files under library/videos/<category>/"
        )

    shuffled = files[:]
    random.shuffle(shuffled)
    picks: list[Path] = []
    while len(picks) < count:
        for path in shuffled:
            picks.append(path)
            if len(picks) >= count:
                break
        random.shuffle(shuffled)

    # Log under a synthetic key so intro clips rotate over time.
    log = _load_usage_log()
    history = log.get("videos/*", [])
    for path in picks:
        history.append(path.name)
    log["videos/*"] = history[-40:]
    _save_usage_log(log)

    return picks


def is_video(path: Path) -> bool:
    """True when the file is a video by extension."""
    return path.suffix.lower() in config.VIDEO_EXTENSIONS


def is_image(path: Path) -> bool:
    """True when the file is an image by extension."""
    return path.suffix.lower() in config.IMAGE_EXTENSIONS
