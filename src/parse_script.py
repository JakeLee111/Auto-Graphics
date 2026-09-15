"""Parse a script message into a video or carousel job.

Protocol:
  First line: /video or /carousel (defaults to /video if omitted)
  Video optional: hook: Your hook text | optional subline
  Carousel: thumbnail: Your title | optional subline  (always slide 1)
  Carousel optional: eyebrow: Small label above the cover title
  Body: text [photos/category] or [videos/category]

See docs/message-protocol.md.
"""

import re

import config
from src.models import ParsedScript, PipelineError, Scene

SCENE_PATTERN = re.compile(
    r"^(?P<text>.+?)\s*\[(?P<library>(?:photos|videos)/[a-z0-9_-]+)\]\s*$"
)
# Telegram may send /carousel@BotName on the first line.
MODE_PATTERN = re.compile(
    r"^/(video|carousel)(?:@[A-Za-z0-9_]+)?\s*$", re.IGNORECASE
)
# Optional spaces around the colon; fullwidth colon is normalized first.
HOOK_PREFIX = re.compile(r"^hook\s*:\s*(.+)$", re.IGNORECASE)
THUMBNAIL_PREFIX = re.compile(r"^thumbnail\s*:\s*(.+)$", re.IGNORECASE)
EYEBROW_PREFIX = re.compile(r"^eyebrow\s*:\s*(.+)$", re.IGNORECASE)

THUMBNAIL_LIBRARY = config.THUMBNAIL_LIBRARY
_INVISIBLE = "\ufeff\u200b\u200c\u200d"


def _parse_scene_line(
    line: str, line_number: int, libraries: list[str], mode: str
) -> tuple[str, str]:
    """Extract (text, library tag) from a body/carousel scene line."""
    match = SCENE_PATTERN.match(line)
    if not match:
        raise PipelineError(
            f"Line {line_number} needs a tag like [photos/lifestyle] or "
            f"[videos/coding]: {line!r}"
        )
    text = match.group("text").strip()
    library = match.group("library")
    if not text:
        raise PipelineError(f"Line {line_number} has an empty scene text.")
    if library not in libraries:
        raise PipelineError(
            f"Unknown library: {library}. Valid: {', '.join(libraries) or '(none found)'}"
        )
    if mode == "carousel" and not library.startswith("photos/"):
        raise PipelineError(
            f"Line {line_number}: /carousel only uses photo libraries. "
            f"Use [photos/...] not [{library}]."
        )
    return _expand_script_breaks(text), library


def _normalize_line(raw: str) -> str:
    """Strip Telegram/copy-paste junk so prefix lines still match."""
    line = raw.replace("\u00a0", " ")
    for char in _INVISIBLE:
        line = line.replace(char, "")
    return line.replace("：", ":").strip()


def _expand_script_breaks(text: str) -> str:
    """Turn literal \\n / \\N into real newlines before render/uppercase."""
    return re.sub(r"\\[nN]", "\n", text)


def prepare_script(message: str, implied_mode: str | None = None) -> str:
    """Normalize a Telegram/CLI message before parsing.

    implied_mode: 'video' or 'carousel' from a Telegram command handler,
    used when the first line is not /video or /carousel (Telegram sometimes
    keeps the command only as metadata).
    """
    text = (message or "").replace("\ufeff", "")
    if implied_mode not in {"video", "carousel"}:
        return text
    first = ""
    for raw in text.splitlines():
        candidate = _normalize_line(raw)
        if candidate:
            first = candidate
            break
    if MODE_PATTERN.match(first):
        return text
    return f"/{implied_mode}\n{text.lstrip()}"


def _plain_overlay_text(raw: str, line_number: int, kind: str) -> str:
    """Validate hook/thumbnail text (no library tag allowed)."""
    text = raw.strip()
    if text.endswith("]") and "[" in text:
        raise PipelineError(
            f"Line {line_number}: {kind}: has no library tag. "
            f"Write: {kind}: your text | optional subline"
        )
    if not text:
        raise PipelineError(f"Line {line_number}: {kind}: text is empty.")
    return _expand_script_breaks(text)


def parse_script(
    message: str, implied_mode: str | None = None
) -> ParsedScript:
    """Turn a raw message into a validated ParsedScript."""
    message = prepare_script(message, implied_mode)
    libraries = config.valid_libraries()
    mode = "video"
    mode_explicit = False
    hook_text: str | None = None
    thumbnail_text: str | None = None
    eyebrow_text: str | None = None
    body: list[Scene] = []
    body_index = 0
    saw_content = False

    for line_number, raw_line in enumerate(message.splitlines(), start=1):
        line = _normalize_line(raw_line)
        if not line:
            continue

        mode_match = MODE_PATTERN.match(line)
        if mode_match:
            if saw_content:
                raise PipelineError(
                    f"Line {line_number}: /video or /carousel must be the first content line."
                )
            mode = mode_match.group(1).lower()
            mode_explicit = True
            continue

        thumb_match = THUMBNAIL_PREFIX.match(line)
        if thumb_match:
            if mode != "carousel":
                if not mode_explicit and hook_text is None:
                    mode = "carousel"
                else:
                    raise PipelineError(
                        "thumbnail: is only for /carousel mode."
                    )
            if thumbnail_text is not None:
                raise PipelineError("Only one thumbnail: line is allowed.")
            thumbnail_text = _plain_overlay_text(
                thumb_match.group(1), line_number, "thumbnail"
            )
            saw_content = True
            continue

        eyebrow_match = EYEBROW_PREFIX.match(line)
        if eyebrow_match:
            if mode != "carousel":
                if not mode_explicit and hook_text is None:
                    mode = "carousel"
                else:
                    raise PipelineError(
                        "eyebrow: is only for /carousel mode."
                    )
            if eyebrow_text is not None:
                raise PipelineError("Only one eyebrow: line is allowed.")
            eyebrow_text = _plain_overlay_text(
                eyebrow_match.group(1), line_number, "eyebrow"
            )
            saw_content = True
            continue

        hook_match = HOOK_PREFIX.match(line)
        if hook_match:
            if mode == "carousel":
                raise PipelineError(
                    "hook: is only for /video mode. Use thumbnail: for /carousel."
                )
            if hook_text is not None:
                raise PipelineError("Only one hook: line is allowed.")
            hook_text = _plain_overlay_text(
                hook_match.group(1), line_number, "hook"
            )
            saw_content = True
            continue

        text, library = _parse_scene_line(line, line_number, libraries, mode)
        body_index += 1
        body.append(Scene(index=body_index, text=text, library=library))
        saw_content = True

    if mode == "video" and hook_text is None and not body:
        raise PipelineError(
            "No scenes found. Example:\n"
            "/video\n"
            "hook: 4 weeks recap | of my journey\n"
            "Body line [videos/lifestyle]"
        )
    if mode == "carousel":
        if thumbnail_text is None:
            raise PipelineError(
                "Carousel needs a thumbnail: line as the first slide.\n"
                "Example:\n"
                "/carousel\n"
                "thumbnail: 4 weeks recap | of my journey\n"
                "Slide two [photos/lifestyle]"
            )
        if THUMBNAIL_LIBRARY not in libraries:
            raise PipelineError(
                f"Missing folder library/{THUMBNAIL_LIBRARY}/. "
                "Create it and add thumbnail photos (.jpg/.png)."
            )
        if not body:
            raise PipelineError(
                "Carousel needs at least one body slide after thumbnail:.\n"
                "Example:\n"
                "/carousel\n"
                "thumbnail: 4 weeks recap | of my journey\n"
                "Slide two [photos/lifestyle]"
            )

    return ParsedScript(
        mode=mode,
        hook_text=hook_text,
        thumbnail_text=thumbnail_text,
        body=body,
        eyebrow_text=eyebrow_text,
    )
