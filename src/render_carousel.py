"""Render /carousel slides in the Classic Magazine 1080x1920 design.

Every color, font, size, and layout rule comes from
templates/carousel-design-tokens.json (config.CAROUSEL_TOKENS_PATH).
Edit that JSON to change the look — never hardcode design values here.

Slide types:
  cover          — yellow Outfit Bold headline + Crimson Pro italic subline,
                   centered on the visible photo
  content slide  — one Outfit Regular paragraph on a liquid-glass card,
                   centered on the visible photo; thumbnail is unchanged
                   (vignette only)

Photos fill the frame (cover-fit, sharp edges). Cover slides use a dark
vignette behind the headline. Body slides use a clear liquid-glass card
around the paragraph. No labels, numbers, arrows, or page dots.
"""

import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

import config
from src.models import PipelineError
from src.render_scene import load_rgb_image, split_dual_text

_FONT_FILES = {
    ("Outfit", 400, False): "Outfit-Regular.ttf",
    ("Outfit", 700, False): "Outfit-Bold.ttf",
    ("Crimson Pro", 400, True): "CrimsonPro-Italic.ttf",
}

_tokens_cache: dict | None = None


def load_tokens() -> dict:
    """Load and cache the carousel design tokens JSON."""
    global _tokens_cache
    if _tokens_cache is None:
        path = config.CAROUSEL_TOKENS_PATH
        if not path.exists():
            raise PipelineError(f"Carousel design tokens not found: {path}")
        _tokens_cache = json.loads(path.read_text())
    return _tokens_cache


# ---------------------------------------------------------------- utilities
def _hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
    hexstr = hexstr.lstrip("#")
    return tuple(int(hexstr[i:i + 2], 16) for i in (0, 2, 4))


def _color(name: str) -> tuple[int, int, int]:
    """Resolve a token color name (e.g. 'accent_yellow')."""
    tokens = load_tokens()
    if name not in tokens["colors"]:
        raise PipelineError(f"Unknown carousel color: {name}")
    return _hex_to_rgb(tokens["colors"][name])


def _font(
    family: str, weight: int = 400, italic: bool = False, size: int = 40
) -> ImageFont.FreeTypeFont:
    """Load one of the two template font families at the given size."""
    key = (family, weight, italic)
    if key not in _FONT_FILES:
        raise PipelineError(f"Carousel template has no font for: {key}")
    path = config.FONTS_DIR / _FONT_FILES[key]
    if not path.exists():
        raise PipelineError(
            f"Font file not found: {path}. "
            "Copy Outfit-Regular.ttf, Outfit-Bold.ttf, and "
            "CrimsonPro-Italic.ttf into fonts/."
        )
    return ImageFont.truetype(str(path), size)


def _style_font(style_key: str, size_override: int | None = None):
    """Load the font for a type_styles entry from the tokens."""
    style = load_tokens()["type_styles"][style_key]
    return _font(
        style["font"],
        style.get("weight", 400),
        style.get("style") == "italic",
        size_override or style["size"],
    )


# ---------------------------------------------------------- text primitives
def _text_w(draw, text: str, fnt, tracking: int = 0) -> float:
    """Width of text in pixels, honoring per-character letter spacing."""
    if not text:
        return 0
    if tracking == 0:
        box = draw.textbbox((0, 0), text, font=fnt)
        return box[2] - box[0]
    total = 0.0
    for ch in text:
        box = draw.textbbox((0, 0), ch, font=fnt)
        total += (box[2] - box[0]) + tracking
    return total - tracking


def _draw_tracked(
    draw, xy, text: str, fnt, fill, tracking: int = 0, center_x=None
) -> float:
    """Draw text with letter spacing; optionally centered on center_x.

    When tracking is 0, draw the whole string at once so italic kerning
    (e.g. Crimson Pro 'f') stays intact. Per-character drawing is only
    for the yellow headline's letter-spacing.
    """
    x, y = xy
    width = _text_w(draw, text, fnt, tracking)
    if center_x is not None:
        x = center_x - width / 2
    if tracking == 0:
        box = draw.textbbox((0, 0), text, font=fnt)
        draw.text((x - box[0], y), text, font=fnt, fill=fill)
        return width
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        box = draw.textbbox((0, 0), ch, font=fnt)
        x += (box[2] - box[0]) + tracking
    return width


def _wrap_paragraph(
    draw, text: str, fnt, max_width: float, tracking: int = 0
) -> list[str]:
    """Greedy word wrap for one paragraph."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if _text_w(draw, trial, fnt, tracking) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap(
    draw, text: str, fnt, max_width: float, tracking: int = 0
) -> list[str]:
    """Word wrap that honors forced newlines already present in the text."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            lines.extend(
                _wrap_paragraph(draw, paragraph, fnt, max_width, tracking)
            )
    return _balance_wrap(draw, lines, fnt, max_width, tracking)


def _balance_wrap(
    draw, lines: list[str], fnt, max_width: float, tracking: int = 0
) -> list[str]:
    """Pull a word down when the last line is a single orphan word."""
    if len(lines) < 2:
        return lines
    last_words = lines[-1].split()
    prev_words = lines[-2].split()
    if len(last_words) != 1 or len(prev_words) < 3:
        return lines
    trial = f"{prev_words[-1]} {lines[-1]}"
    if _text_w(draw, trial, fnt, tracking) > max_width:
        return lines
    balanced = list(lines)
    balanced[-2] = " ".join(prev_words[:-1])
    balanced[-1] = trial
    return balanced


def _check_max_lines(lines: list[str], limit: int, what: str) -> None:
    """Fail with a clear message when text wraps past the design limit."""
    if len(lines) > limit:
        raise PipelineError(
            f"{what} is too long ({len(lines)} lines, max {limit}). "
            "Shorten the text."
        )


def _centered_multiline(
    draw, lines: list[str], fnt, center_x, top_y, fill, line_height,
    tracking: int = 0,
) -> float:
    """Draw centered lines top-down; return y after the last line."""
    y = top_y
    for line in lines:
        _draw_tracked(
            draw, (0, y), line, fnt, fill, tracking, center_x=center_x
        )
        y += line_height
    return y


def _join_dual(text: str) -> str:
    """Body copy as one paragraph. A leftover `|` is joined with a space."""
    heading, body = split_dual_text(text)
    if not heading:
        return body or ""
    if not body:
        return heading
    return f"{heading} {body}"


# --------------------------------------------------------------- background
def _build_background(media_path: Path):
    """COVER fit: scale the photo to fill 1080x1920, then center-crop.

    Sharp edges. No blur fill and no feathered photo edges.
    """
    tokens = load_tokens()
    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]

    photo, temp = load_rgb_image(media_path)
    try:
        scale = max(width / photo.width, height / photo.height)
        new_w = max(1, int(photo.width * scale))
        new_h = max(1, int(photo.height * scale))
        resized = photo.resize((new_w, new_h), Image.Resampling.LANCZOS)
        left = (new_w - width) // 2
        top = (new_h - height) // 2
        cropped = resized.crop((left, top, left + width, top + height))
        return cropped.convert("RGBA"), (0, 0, width, height)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def _apply_vignette(canvas: Image.Image, box: tuple) -> Image.Image:
    """Soft dark ellipse behind the text, centered on the visible photo."""
    tokens = load_tokens()
    v = tokens["background"]["vignette"]
    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]
    px, py, cw, ch = box
    cx, cy = px + cw / 2, py + ch / 2
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    rw = cw * v["width_pct_of_photo"]
    rh = ch * v["height_pct_of_photo"]
    draw.ellipse(
        [cx - rw / 2, cy - rh / 2, cx + rw / 2, cy + rh / 2],
        fill=int(255 * v["opacity"]),
    )
    mask = mask.filter(ImageFilter.GaussianBlur(v["blur_radius_px"]))
    dark = Image.new("RGBA", (width, height), _color(v["color"]) + (255,))
    dark.putalpha(mask)
    return Image.alpha_composite(canvas, dark)


def _rounded_rect_mask(
    size: tuple[int, int], radius: int, inset: int = 0
) -> Image.Image:
    """Opaque rounded rectangle, optionally inset, as an L mask."""
    width, height = size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [inset, inset, width - 1 - inset, height - 1 - inset],
        radius=max(1, radius - inset),
        fill=255,
    )
    return mask


def _apply_liquid_glass(canvas: Image.Image, box: tuple) -> Image.Image:
    """Even clear glass card behind body text. Cover slides do not use this."""
    card = load_tokens()["body_card"]
    left, top, right, bottom = (int(round(value)) for value in box)
    margin = 8
    left = max(margin, left)
    top = max(margin, top)
    right = min(canvas.width - margin, right)
    bottom = min(canvas.height - margin, bottom)
    width = right - left
    height = bottom - top
    if width < 16 or height < 16:
        return canvas

    radius = min(int(card["radius_px"]), width // 3, height // 2)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [
            left + 4,
            top + int(card["lift_shadow_offset_y_px"]),
            right - 4,
            bottom + 10,
        ],
        radius=radius,
        fill=(0, 0, 0, int(card["lift_shadow_opacity"])),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(int(card["lift_shadow_blur_px"])))
    canvas = Image.alpha_composite(canvas, shadow)

    magnify = float(card["lens_magnify"])
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    sample_w = width / magnify
    sample_h = height / magnify
    sample_left = max(0, int(center_x - sample_w / 2))
    sample_top = max(0, int(center_y - sample_h / 2))
    sample_right = min(canvas.width, int(center_x + sample_w / 2))
    sample_bottom = min(canvas.height, int(center_y + sample_h / 2))
    glass = (
        canvas.crop((sample_left, sample_top, sample_right, sample_bottom))
        .resize((width, height), Image.Resampling.LANCZOS)
        .filter(ImageFilter.GaussianBlur(int(card["backdrop_blur_px"])))
    )
    glass = ImageEnhance.Color(glass).enhance(float(card["color_enhance"]))
    glass = ImageEnhance.Contrast(glass).enhance(float(card["contrast_enhance"]))

    mask = _rounded_rect_mask((width, height), radius)
    wash = Image.new(
        "RGBA", (width, height), (255, 255, 255, int(card["fill_alpha"]))
    )
    glass = Image.alpha_composite(glass, wash)

    rim_width = max(1, int(card["rim_width_px"]))
    ring = ImageChops.subtract(
        mask,
        _rounded_rect_mask((width, height), radius, rim_width),
    )
    rim = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    rim.putalpha(
        ring.point(lambda p: int(p * int(card["rim_alpha"]) / 255))
    )
    glass = Image.alpha_composite(glass, rim)

    glass.putalpha(ImageChops.multiply(glass.split()[-1], mask))
    card_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    card_layer.paste(glass, (left, top), glass)
    return Image.alpha_composite(canvas, card_layer)


# ----------------------------------------------------------------- renders

def render_cover(
    text: str,
    media_path: Path,
    out_path: Path,
) -> Path:
    """Render slide 1: yellow uppercase headline + italic subline."""
    tokens = load_tokens()
    canvas, box = _build_background(media_path)
    canvas = _apply_vignette(canvas, box)
    draw = ImageDraw.Draw(canvas)
    px, py, cw, ch = box
    cx, cy = px + cw / 2, py + ch / 2

    headline, subline = split_dual_text(text)
    if not headline:
        raise PipelineError(f"Empty thumbnail text: {text!r}")

    b_style = tokens["type_styles"]["headline_bold"]
    i_style = tokens["type_styles"]["headline_italic"]
    b_font = _style_font("headline_bold")
    i_font = _style_font("headline_italic")

    b_lines = _wrap(
        draw, headline.upper(), b_font,
        cw * b_style["max_width_pct_of_photo"],
        b_style["letter_spacing"],
    )
    _check_max_lines(b_lines, b_style["max_lines"], "Thumbnail headline")

    i_lines: list[str] = []
    if subline:
        i_lines = _wrap(
            draw, subline, i_font,
            cw * i_style["max_width_pct_of_photo"],
        )
        _check_max_lines(i_lines, i_style["max_lines"], "Thumbnail subline")

    total_h = len(b_lines) * b_style["line_height"]
    if i_lines:
        total_h += i_style["gap_after_bold_px"] + len(i_lines) * i_style["line_height"]

    y = cy - total_h / 2
    y = _centered_multiline(
        draw, b_lines, b_font, cx, y, _color(b_style["color"]),
        b_style["line_height"], b_style["letter_spacing"],
    )
    if i_lines:
        y = (
            cy - total_h / 2
            + len(b_lines) * b_style["line_height"]
            + i_style["gap_after_bold_px"]
        )
        _centered_multiline(
            draw, i_lines, i_font, cx, y, _color(i_style["color"]),
            i_style["line_height"],
        )

    canvas.convert("RGB").save(out_path, quality=92)
    return out_path


def render_content_slide(
    text: str,
    media_path: Path,
    out_path: Path,
) -> Path:
    """Render a body slide: one centered paragraph on a liquid-glass card."""
    tokens = load_tokens()
    canvas, box = _build_background(media_path)
    draw = ImageDraw.Draw(canvas)
    px, py, cw, ch = box
    cx, cy = px + cw / 2, py + ch / 2

    body = _join_dual(text)
    if not body:
        raise PipelineError(f"Empty slide text: {text!r}")

    style = tokens["type_styles"]["body_text"]
    fnt = _style_font("body_text")
    lines = _wrap(draw, body, fnt, cw * style["max_width_pct_of_photo"])
    _check_max_lines(lines, style["max_lines"], "Slide body")
    total_h = len(lines) * style["line_height"]
    y = cy - total_h / 2
    block_w = max(_text_w(draw, line, fnt) for line in lines)

    card = tokens["body_card"]
    canvas = _apply_liquid_glass(
        canvas,
        (
            cx - block_w / 2 - card["padding_x_px"],
            y - card["padding_y_px"],
            cx + block_w / 2 + card["padding_x_px"],
            y + total_h + card["padding_y_px"],
        ),
    )

    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    _centered_multiline(
        ImageDraw.Draw(shadow_layer),
        lines,
        fnt,
        cx + card["text_shadow_offset_x_px"],
        y + card["text_shadow_offset_y_px"],
        (0, 0, 0, int(card["text_shadow_opacity"])),
        style["line_height"],
    )
    canvas = Image.alpha_composite(
        canvas,
        shadow_layer.filter(
            ImageFilter.GaussianBlur(int(card["text_shadow_blur_px"]))
        ),
    )
    draw = ImageDraw.Draw(canvas)
    _centered_multiline(
        draw, lines, fnt, cx, y, _color(style["color"]), style["line_height"]
    )

    canvas.convert("RGB").save(out_path, quality=92)
    return out_path
