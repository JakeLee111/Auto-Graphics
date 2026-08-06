"""Parse a script message into a video or carousel job.

Protocol:
  First line: /video or /carousel (defaults to /video if omitted)
  Video optional: hook: Your hook text | optional subline
  Carousel: thumbnail: Your title | optional subline  (always slide 1)
  Body: text [photos/category] or [videos/category]

See docs/message-protocol.md.
"""

import re

import config
from src.models import ParsedScript, PipelineError, Scene

SCENE_PATTERN = re.compile(
    r"^(?P<text>.+?)\s*\[(?P<library>(?:photos|videos)/[a-z0-9_-]+)\]\s*$"
)
MODE_PATTERN = re.compile(r"^/(video|carousel)\s*$", re.IGNORECASE)
HOOK_PREFIX = re.compile(r"^hook:\s*(.+)$", re.IGNORECASE)
THUMBNAIL_PREFIX = re.compile(r"^thumbnail:\s*(.+)$", re.IGNORECASE)

THUMBNAIL_LIBRARY = config.THUMBNAIL_LIBRARY


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


def _expand_script_breaks(text: str) -> str:
    """Turn literal \\n / \\N into real newlines before render/uppercase."""
    return re.sub(r"\\[nN]", "\n", text)


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


def parse_script(message: str) -> ParsedScript:
    """Turn a raw message into a validated ParsedScript."""
    libraries = config.valid_libraries()
    mode = "video"
    hook_text: str | None = None
    thumbnail_text: str | None = None
    body: list[Scene] = []
    body_index = 0
    saw_content = False

    for line_number, raw_line in enumerate(message.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        mode_match = MODE_PATTERN.match(line)
        if mode_match:
            if saw_content:
                raise PipelineError(
                    f"Line {line_number}: /video or /carousel must be the first content line."
                )
            mode = mode_match.group(1).lower()
            continue

        thumb_match = THUMBNAIL_PREFIX.match(line)
        if thumb_match:
            if mode != "carousel":
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
    )
