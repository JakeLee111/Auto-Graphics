"""Data types shared across the pipeline."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Scene:
    """One scene parsed from the script: its text and source library."""

    index: int
    text: str
    library: str


@dataclass(frozen=True)
class ParsedScript:
    """A fully parsed job: mode, optional hook/thumbnail text, and body scenes.

    hook_text: video intro overlay (no library). Clips from all library/videos/.
    thumbnail_text: carousel first slide (no library). Photo from photos/thumbnails/.
    eyebrow_text: optional small label above the carousel cover title.
    """

    mode: str  # "video" | "carousel"
    hook_text: str | None
    thumbnail_text: str | None
    body: list[Scene]
    eyebrow_text: str | None = None


@dataclass(frozen=True)
class Template:
    """Fixed visual style loaded from a JSON file in templates/."""

    name: str
    canvas_width: int
    canvas_height: int
    fps: int
    font_file: Path
    font_size: int
    fill_color: str
    stroke_color: str
    stroke_width: int
    text_y_ratio: float
    wrap_width_ratio: float
    max_lines: int
    line_spacing_ratio: float
    body_seconds: float
    intro_cut_seconds: float
    intro_cut_count: int
    caption_box: bool
    caption_box_padding: int
    caption_box_opacity: int
    caption_box_radius: int
    shadow_offset: int
    shadow_blur: int
    # Dual-font (headline + subline). sub_font_file None = single-font mode.
    sub_font_file: Path | None
    sub_font_size: int
    sub_fill_color: str
    sub_stroke_color: str
    sub_stroke_width: int
    # Extra vertical gap after headline before subline (can be negative to hug).
    sub_gap: int
    uppercase_headline: bool


@dataclass
class RenderResult:
    """Output of a pipeline run."""

    mode: str
    paths: list[Path] = field(default_factory=list)


class PipelineError(Exception):
    """User-facing pipeline failure with a clear message."""
