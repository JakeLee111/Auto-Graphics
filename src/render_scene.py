"""Render scenes: background media + dual-font text overlay.

Headline (yellow Bebas Neue, UPPERCASE) + optional white Caveat subline via ` | `.
FFmpeg handles scale/pad/loop/encode.
"""

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from src.models import PipelineError, Template
from src.pick_media import is_video


def load_template(name: str) -> Template:
    """Load a template JSON from templates/<name>.json."""
    path = config.TEMPLATES_DIR / f"{name}.json"
    if not path.exists():
        raise PipelineError(f"Template not found: {path}")
    data = json.loads(path.read_text())

    font_file = config.PROJECT_ROOT / data["font_file"]
    if not font_file.exists():
        raise PipelineError(f"Font file not found: {font_file}")

    sub_font_file = None
    if data.get("sub_font_file"):
        sub_font_file = config.PROJECT_ROOT / data["sub_font_file"]
        if not sub_font_file.exists():
            raise PipelineError(f"Sub font file not found: {sub_font_file}")

    return Template(
        name=name,
        canvas_width=data["canvas_width"],
        canvas_height=data["canvas_height"],
        fps=data["fps"],
        font_file=font_file,
        font_size=data["font_size"],
        fill_color=data["fill_color"],
        stroke_color=data["stroke_color"],
        stroke_width=data["stroke_width"],
        text_y_ratio=data["text_y_ratio"],
        wrap_width_ratio=data["wrap_width_ratio"],
        max_lines=data["max_lines"],
        line_spacing_ratio=data["line_spacing_ratio"],
        body_seconds=float(
            data.get("body_seconds", config.DEFAULT_BODY_SECONDS)
        ),
        intro_cut_seconds=float(
            data.get("intro_cut_seconds", config.INTRO_CUT_SECONDS)
        ),
        intro_cut_count=int(
            data.get("intro_cut_count", config.INTRO_CUT_COUNT)
        ),
        caption_box=bool(data.get("caption_box", False)),
        caption_box_padding=int(data.get("caption_box_padding", 28)),
        caption_box_opacity=int(data.get("caption_box_opacity", 150)),
        caption_box_radius=int(data.get("caption_box_radius", 24)),
        shadow_offset=int(data.get("shadow_offset", 3)),
        shadow_blur=int(data.get("shadow_blur", 8)),
        sub_font_file=sub_font_file,
        sub_font_size=int(data.get("sub_font_size", 78)),
        sub_fill_color=data.get("sub_fill_color", "#F5C518"),
        sub_stroke_color=data.get("sub_stroke_color", "#1a1a1a"),
        sub_stroke_width=int(data.get("sub_stroke_width", 0)),
        sub_gap=int(data.get("sub_gap", -8)),
        uppercase_headline=bool(data.get("uppercase_headline", True)),
    )


def _expand_forced_breaks(text: str) -> str:
    """Turn literal \\n into real newlines (one script line = one slide)."""
    return text.replace("\\n", "\n")


def _wrap_paragraph(
    paragraph: str, font: ImageFont.FreeTypeFont, max_width: int
) -> list[str]:
    """Greedy word wrap so each line fits within max_width pixels."""
    lines: list[str] = []
    current = ""
    for word in paragraph.split():
        candidate = f"{current} {word}".strip()
        if font.getlength(candidate) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Word-wrap text; honor forced breaks from literal \\n in the script."""
    lines: list[str] = []
    for paragraph in _expand_forced_breaks(text).split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        lines.extend(_wrap_paragraph(paragraph, font, max_width))
    return lines


def _parse_color(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Parse '#rrggbb' or a named color into an RGBA tuple."""
    if color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        return (r, g, b, alpha)
    named = {
        "white": (255, 255, 255, alpha),
        "black": (0, 0, 0, alpha),
    }
    if color.lower() in named:
        return named[color.lower()]
    return (255, 255, 255, alpha)


def _split_dual_text(text: str) -> tuple[str, str | None]:
    """Split 'HEADLINE | subline' into parts. No pipe = headline only."""
    if "|" not in text:
        return text.strip(), None
    left, right = text.split("|", 1)
    headline = left.strip()
    subline = right.strip() or None
    return headline, subline


def _draw_lines(
    overlay: Image.Image,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    start_y: int,
    line_height: int,
    fill: tuple[int, int, int, int],
    stroke_fill: tuple[int, int, int, int],
    stroke_width: int,
    template: Template,
) -> int:
    """Draw wrapped lines centered; return y after the last line."""
    if not lines:
        return start_y

    # Soft drop shadow for the whole block.
    if template.shadow_blur > 0:
        shadow = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        y = start_y
        for line in lines:
            x = (template.canvas_width - font.getlength(line)) / 2 + template.shadow_offset
            shadow_draw.text(
                (x, y + template.shadow_offset),
                line,
                font=font,
                fill=(0, 0, 0, 230),
            )
            y += line_height
        shadow = shadow.filter(ImageFilter.GaussianBlur(template.shadow_blur))
        overlay.alpha_composite(shadow)

    draw = ImageDraw.Draw(overlay)
    y = start_y
    for line in lines:
        x = (template.canvas_width - font.getlength(line)) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        y += line_height
    return y


def build_text_overlay(
    text: str,
    template: Template,
    *,
    center_vertically: bool = False,
) -> Image.Image:
    """Draw dual-font text (headline + optional subline) on a transparent canvas.

    Horizontal centering is always on. When center_vertically is True, the full
    text block is also centered on the canvas mid-point; otherwise text_y_ratio.
    """
    overlay = Image.new(
        "RGBA", (template.canvas_width, template.canvas_height), (0, 0, 0, 0)
    )

    headline_raw, subline = _split_dual_text(text)
    if not headline_raw:
        raise PipelineError(f"Empty headline text: {text!r}")

    headline = (
        headline_raw.upper() if template.uppercase_headline else headline_raw
    )

    headline_font = ImageFont.truetype(str(template.font_file), template.font_size)
    max_width = int(template.canvas_width * template.wrap_width_ratio)
    headline_lines = _wrap_text(headline, headline_font, max_width)
    if len(headline_lines) > template.max_lines:
        raise PipelineError(
            f"Headline is too long ({len(headline_lines)} lines, "
            f"max {template.max_lines}): {headline!r}"
        )

    # Optional caption box around the full text block (headline + subline).
    headline_line_height = int(template.font_size * template.line_spacing_ratio)

    sub_lines: list[str] = []
    sub_font = None
    sub_line_height = 0
    if subline and template.sub_font_file is not None:
        sub_font = ImageFont.truetype(
            str(template.sub_font_file), template.sub_font_size
        )
        sub_lines = _wrap_text(subline, sub_font, max_width)
        sub_line_height = int(template.sub_font_size * 1.15)

    block_height = headline_line_height * len(headline_lines)
    if sub_lines:
        block_height += template.sub_gap + sub_line_height * len(sub_lines)

    if center_vertically:
        start_y = int((template.canvas_height - block_height) / 2)
    else:
        start_y = int(template.canvas_height * template.text_y_ratio)

    if template.caption_box and headline_lines:
        all_widths = [headline_font.getlength(line) for line in headline_lines]
        if sub_font and sub_lines:
            all_widths.extend(sub_font.getlength(line) for line in sub_lines)
        block_width = max(all_widths) if all_widths else 0
        pad = template.caption_box_padding
        box_left = (template.canvas_width - block_width) / 2 - pad
        box_top = start_y - pad
        box_right = (template.canvas_width + block_width) / 2 + pad
        box_bottom = start_y + block_height + pad
        box_layer = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
        ImageDraw.Draw(box_layer).rounded_rectangle(
            [box_left, box_top, box_right, box_bottom],
            radius=template.caption_box_radius,
            fill=(0, 0, 0, template.caption_box_opacity),
        )
        overlay = Image.alpha_composite(overlay, box_layer)

    y_after = _draw_lines(
        overlay,
        headline_lines,
        headline_font,
        start_y,
        headline_line_height,
        _parse_color(template.fill_color),
        _parse_color(template.stroke_color),
        template.stroke_width,
        template,
    )

    if sub_font and sub_lines:
        _draw_lines(
            overlay,
            sub_lines,
            sub_font,
            y_after + template.sub_gap,
            sub_line_height,
            _parse_color(template.sub_fill_color),
            _parse_color(template.sub_stroke_color),
            template.sub_stroke_width,
            template,
        )

    return overlay


def run_ffmpeg(args: list[str]) -> None:
    """Run FFmpeg quietly; surface a readable error on failure."""
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise PipelineError(f"FFmpeg failed: {result.stderr.strip()[:500]}")


def _fit_filter(template: Template) -> str:
    """Scale-to-fit and pad with black so the full media is visible (no crop)."""
    w, h = template.canvas_width, template.canvas_height
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        f"setsar=1,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,"
        f"fps={template.fps}"
    )


def render_clip(
    text: str,
    media_path: Path,
    template: Template,
    out_path: Path,
    duration: float,
) -> Path:
    """Render one muted clip with text overlay at the given duration."""
    overlay_path = out_path.with_suffix(".overlay.png")
    build_text_overlay(text, template).save(overlay_path)

    encode_args = [
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-an",
        "-t", str(duration),
        str(out_path),
    ]
    filter_graph = (
        f"[0:v]{_fit_filter(template)}[bg];[bg][1:v]overlay=0:0,format=yuv420p"
    )

    if is_video(media_path):
        input_args = ["-stream_loop", "-1", "-i", str(media_path)]
    else:
        input_args = [
            "-loop", "1",
            "-framerate", str(template.fps),
            "-i", str(media_path),
        ]

    run_ffmpeg(
        [
            *input_args,
            "-i", str(overlay_path),
            "-filter_complex", filter_graph,
            *encode_args,
        ]
    )
    overlay_path.unlink(missing_ok=True)
    return out_path


def _load_rgb_image(path: Path) -> tuple[Image.Image, Path | None]:
    """Open an image as RGB. Converts HEIC via FFmpeg when needed.

    Returns:
        (image, temp_path_to_delete_or_None)
    """
    suffix = path.suffix.lower()
    if suffix in {".heic", ".heif"}:
        config.TEMP_DIR.mkdir(exist_ok=True)
        converted = config.TEMP_DIR / f"{path.stem}_heic.jpg"
        run_ffmpeg(["-i", str(path), "-frames:v", "1", str(converted)])
        if not converted.exists():
            raise PipelineError(f"Could not convert HEIC photo: {path.name}")
        return Image.open(converted).convert("RGB"), converted
    return Image.open(path).convert("RGB"), None


def render_still(
    text: str,
    media_path: Path,
    template: Template,
    out_path: Path,
) -> Path:
    """Render one vertical JPG for carousel slides (canvas size from template)."""
    source = media_path
    temp_paths: list[Path] = []
    if is_video(media_path):
        temp_frame = out_path.with_suffix(".frame.png")
        run_ffmpeg(
            ["-i", str(media_path), "-frames:v", "1", str(temp_frame)]
        )
        source = temp_frame
        temp_paths.append(temp_frame)

    bg, heic_temp = _load_rgb_image(source)
    if heic_temp is not None:
        temp_paths.append(heic_temp)

    w, h = template.canvas_width, template.canvas_height
    scale = min(w / bg.width, h / bg.height)
    new_w = max(1, int(bg.width * scale))
    new_h = max(1, int(bg.height * scale))
    resized = bg.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    left = (w - new_w) // 2
    top = (h - new_h) // 2
    canvas.paste(resized, (left, top))

    overlay = build_text_overlay(text, template)
    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    final.save(out_path, quality=92)

    for temp in temp_paths:
        temp.unlink(missing_ok=True)
    return out_path
