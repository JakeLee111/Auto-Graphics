"""Render /carousel slides in the "Minimal Mono Chic" 1080x1920 design.

Every color, font, size, and position comes from
templates/carousel-design-tokens.json (config.CAROUSEL_TOKENS_PATH).
Edit that JSON to change the look — never hardcode design values here.

Slide types:
  cover          — eyebrow (optional) + divider + title (one gold italic
                   accent word) + subtitle + SWIPE footer with arrow
  content slide  — index number (01, 02, ...) + heading + body + page dots
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config
from src.models import PipelineError
from src.render_scene import load_rgb_image, split_dual_text

# Fixed footer label on the cover slide (design decision, not user copy).
FOOTER_LABEL = "swipe"

# Vertical nudge so the larger italic accent word sits on the title baseline.
ACCENT_BASELINE_OFFSET = -14

# Short connector words that make the best single accent word in a title.
CONNECTOR_WORDS = {
    "a", "an", "and", "at", "for", "i", "in", "is", "my",
    "of", "on", "or", "the", "to", "vs", "with", "your",
}

# Too small to read as the gold italic accent (tiny "i" / "a" / "an").
WEAK_ACCENT_WORDS = {"a", "an", "i"}

_FONT_FILES = {
    ("Outfit", 400, False): "Outfit-Regular.ttf",
    ("Outfit", 700, False): "Outfit-Bold.ttf",
    ("Instrument Serif", 400, True): "InstrumentSerif-Italic.ttf",
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
def _hex_to_rgba(hexstr: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Parse '#rrggbb' or '#rrggbbaa' into an RGBA tuple."""
    hexstr = hexstr.lstrip("#")
    if len(hexstr) == 8:
        r, g, b, a = (int(hexstr[i:i + 2], 16) for i in (0, 2, 4, 6))
        return (r, g, b, a)
    r, g, b = (int(hexstr[i:i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, alpha)


def _color(name_or_hex: str, alpha: int = 255) -> tuple[int, int, int, int]:
    """Resolve a token color name (e.g. 'accent_gold') or raw hex string."""
    tokens = load_tokens()
    if name_or_hex in tokens["colors"]:
        return _hex_to_rgba(tokens["colors"][name_or_hex], alpha)
    return _hex_to_rgba(name_or_hex, alpha)


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
            "Copy the carousel fonts into fonts/."
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
    """Draw text with letter spacing; optionally centered on center_x."""
    x, y = xy
    width = _text_w(draw, text, fnt, tracking)
    if center_x is not None:
        x = center_x - width / 2
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        box = draw.textbbox((0, 0), ch, font=fnt)
        x += (box[2] - box[0]) + tracking
    return width


def _wrap_paragraph(draw, text: str, fnt, max_width: float) -> list[str]:
    """Greedy word wrap for one paragraph."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if _text_w(draw, trial, fnt) <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _wrap(draw, text: str, fnt, max_width: float) -> list[str]:
    """Word wrap that honors forced newlines already present in the text."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            lines.extend(_wrap_paragraph(draw, paragraph, fnt, max_width))
    return _balance_wrap(draw, lines, fnt, max_width)


def _balance_wrap(
    draw, lines: list[str], fnt, max_width: float
) -> list[str]:
    """Pull a word down when the last line is a single orphan word."""
    if len(lines) < 2:
        return lines
    last_words = lines[-1].split()
    prev_words = lines[-2].split()
    if len(last_words) != 1 or len(prev_words) < 3:
        return lines
    trial = f"{prev_words[-1]} {lines[-1]}"
    if _text_w(draw, trial, fnt) > max_width:
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
    draw, lines: list[str], fnt, center_x, top_y, fill, line_height
) -> float:
    """Draw centered lines top-down; return y after the last line."""
    y = top_y
    for line in lines:
        _draw_tracked(draw, (0, y), line, fnt, fill, center_x=center_x)
        y += line_height
    return y


# --------------------------------------------------------------- background
def _cover_photo(media_path: Path, width: int, height: int) -> Image.Image:
    """Load a photo (HEIC ok) and crop it to fully cover the canvas."""
    img, temp = load_rgb_image(media_path)
    scale = max(width / img.width, height / img.height)
    new_w = max(1, int(img.width * scale))
    new_h = max(1, int(img.height * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    cropped = resized.crop((left, top, left + width, top + height))
    if temp is not None:
        temp.unlink(missing_ok=True)
    return cropped


def _apply_scrim(photo: Image.Image) -> Image.Image:
    """Darken top and bottom with the token gradient so text stays legible."""
    tokens = load_tokens()
    overlay = tokens["background"]["overlay"]
    stops = overlay["stops"]
    width, height = photo.size

    gradient = Image.new("L", (1, height), 0)
    for y in range(height):
        pos = y / (height - 1)
        for i in range(len(stops) - 1):
            a, b = stops[i], stops[i + 1]
            if a["position"] <= pos <= b["position"]:
                t = (pos - a["position"]) / (
                    b["position"] - a["position"] + 1e-9
                )
                opacity = a["opacity"] + t * (b["opacity"] - a["opacity"])
                break
        else:
            opacity = stops[-1]["opacity"]
        gradient.putpixel((0, y), int(opacity * 255))

    gradient = gradient.resize((width, height))
    scrim = Image.new("RGBA", (width, height), _hex_to_rgba(overlay["color"]))
    scrim.putalpha(gradient)
    return Image.alpha_composite(photo.convert("RGBA"), scrim)


def _background(media_path: Path) -> Image.Image:
    tokens = load_tokens()
    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]
    return _apply_scrim(_cover_photo(media_path, width, height))


def _text_shadow(overlay: Image.Image) -> Image.Image:
    """Black gaussian shadow from the overlay's alpha channel."""
    spec = load_tokens()["text_shadow"]
    alpha = overlay.getchannel("A")
    opacity = int(round(spec["opacity"] * 255))
    faded = alpha.point(lambda p: int(p * opacity / 255))
    black = Image.new("L", overlay.size, 0)
    shadow = Image.merge("RGBA", (black, black, black, faded))
    shifted = Image.new("RGBA", overlay.size, (0, 0, 0, 0))
    shifted.paste(shadow, (spec["offset"], spec["offset"]))
    blur = spec["blur"]
    if blur:
        shifted = shifted.filter(ImageFilter.GaussianBlur(blur))
    return shifted


def _composite_text(base: Image.Image, overlay: Image.Image) -> Image.Image:
    """Lay shadow + type on top of the photo."""
    out = Image.alpha_composite(base.convert("RGBA"), _text_shadow(overlay))
    return Image.alpha_composite(out, overlay)


# --------------------------------------------------------------- components
def _swipe_arrow(draw, cx: float, cy: float, col, scale: float = 1.0) -> None:
    """Minimal chevron pointing right, next to the footer label."""
    s = 14 * scale
    lw = max(2, int(3 * scale))
    draw.line([(cx - s, cy - s), (cx + s * 0.4, cy)], fill=col, width=lw)
    draw.line([(cx + s * 0.4, cy), (cx - s, cy + s)], fill=col, width=lw)


def _page_dots(draw, cx: float, cy: float, total: int, active: int) -> None:
    """Row of page dots; the active one is gold."""
    tokens = load_tokens()["components"]["page_dots"]
    radius = tokens["radius"]
    gap = tokens["gap"]
    x0 = cx - (total - 1) * gap / 2
    for i in range(total):
        x = x0 + i * gap
        fill = _color("dot_active") if i == active else _color("dot_inactive")
        draw.ellipse([x - radius, cy - radius, x + radius, cy + radius], fill=fill)


# ------------------------------------------------------------- title layout
def _accent_key(word: str) -> str:
    return word.lower().strip(".,!?'\"")


def pick_accent_word(words: list[str]) -> int:
    """Index of the ONE title word to render in the gold italic accent.

    Prefers a short connector word (in/my/the/...); skips tiny ones
    (i/a/an). Otherwise the shortest word with 3+ letters.
    The wording never changes — only the styling.
    """
    for i, word in enumerate(words):
        key = _accent_key(word)
        if key in CONNECTOR_WORDS and key not in WEAK_ACCENT_WORDS:
            return i
    long_enough = [
        i for i, word in enumerate(words) if len(_accent_key(word)) >= 3
    ]
    pool = long_enough or list(range(len(words)))
    return min(pool, key=lambda i: len(_accent_key(words[i])))


def _title_word_width(draw, word: str, accent: bool, fonts: dict) -> float:
    if accent:
        return _text_w(draw, word.lower(), fonts["accent"])
    return _text_w(draw, word.upper(), fonts["title"], fonts["tracking"])


def _layout_title(draw, headline: str, fonts: dict, max_width: float):
    """Split the title into wrapped lines of (word, is_accent) pairs."""
    paragraphs = [p for p in headline.split("\n") if p.strip()]
    all_words = [w for p in paragraphs for w in p.split()]
    accent_index = pick_accent_word(all_words)

    lines: list[list[tuple[str, bool]]] = []
    word_index = 0
    for paragraph in paragraphs:
        current: list[tuple[str, bool]] = []
        current_width = 0.0
        for word in paragraph.split():
            accent = word_index == accent_index
            word_index += 1
            width = _title_word_width(draw, word, accent, fonts)
            trial = current_width + (fonts["space"] if current else 0) + width
            if current and trial > max_width:
                lines.append(current)
                current = [(word, accent)]
                current_width = width
            else:
                current.append((word, accent))
                current_width = trial
        if current:
            lines.append(current)
    return lines


# ----------------------------------------------------------------- renders
def render_cover(
    text: str,
    eyebrow: str | None,
    media_path: Path,
    out_path: Path,
) -> Path:
    """Render slide 1: optional eyebrow, title with accent word, subtitle."""
    tokens = load_tokens()
    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]
    margin = tokens["safe_margins"]["left"]
    layout = tokens["slide_layouts"]["poster_thumbnail"]

    img = _background(media_path)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if eyebrow:
        eb = tokens["type_styles"]["eyebrow"]
        _draw_tracked(
            draw, (0, layout["eyebrow_y"]), eyebrow.upper(),
            _style_font("eyebrow"), _color(eb["color"]),
            tracking=eb["letter_spacing"], center_x=width / 2,
        )
        dl = tokens["type_styles"]["divider_line"]
        draw.line(
            [
                (width / 2 - dl["width"] / 2, layout["divider_y"]),
                (width / 2 + dl["width"] / 2, layout["divider_y"]),
            ],
            fill=_color(dl["color"]),
            width=dl["thickness"],
        )

    headline, subline = split_dual_text(text)
    if not headline:
        raise PipelineError(f"Empty thumbnail text: {text!r}")

    t_style = tokens["type_styles"]["title"]
    a_style = t_style["accent_word"]
    title_font = _style_font("title")
    accent_font = _font(
        a_style["font"], a_style.get("weight", 400), True, a_style["size"]
    )
    fonts = {
        "title": title_font,
        "accent": accent_font,
        "tracking": t_style["letter_spacing"],
        "space": title_font.getlength(" ") + t_style["letter_spacing"],
    }

    title_lines = _layout_title(draw, headline, fonts, width - 2 * margin)
    _check_max_lines(title_lines, t_style["max_lines"], "Thumbnail headline")

    line_height = t_style["line_height"]
    y = layout["title_block_center_y"] - len(title_lines) * line_height / 2
    for line in title_lines:
        widths = [
            _title_word_width(draw, word, accent, fonts)
            for word, accent in line
        ]
        total = sum(widths) + fonts["space"] * (len(line) - 1)
        x = width / 2 - total / 2
        for (word, accent), word_width in zip(line, widths):
            if accent:
                draw.text(
                    (x, y + ACCENT_BASELINE_OFFSET),
                    word.lower(),
                    font=accent_font,
                    fill=_color(a_style["color"]),
                )
            else:
                _draw_tracked(
                    draw, (x, y), word.upper(), title_font,
                    _color(t_style["color"]), tracking=fonts["tracking"],
                )
            x += word_width + fonts["space"]
        y += line_height

    if subline:
        sub = tokens["type_styles"]["subtitle"]
        sub_font = _style_font("subtitle")
        sub_lines = _wrap(draw, subline, sub_font, width * sub["max_width_pct"])
        _centered_multiline(
            draw, sub_lines, sub_font, width / 2,
            y + layout["subtitle_gap_after_title"] - line_height,
            _color(sub["color"]), sub["line_height"],
        )

    fl = tokens["type_styles"]["footer_label"]
    footer_y = height - layout["footer_y_from_bottom"]
    label = FOOTER_LABEL.upper()
    footer_font = _style_font("footer_label")
    label_width = _text_w(draw, label, footer_font, fl["letter_spacing"])
    _draw_tracked(
        draw, (0, footer_y), label, footer_font, _color(fl["color"]),
        tracking=fl["letter_spacing"], center_x=width / 2 - 30,
    )
    _swipe_arrow(
        draw, width / 2 + label_width / 2 + 10, footer_y + 14,
        _color(fl["color"]),
    )

    _composite_text(img, overlay).convert("RGB").save(out_path, quality=92)
    return out_path


def render_content_slide(
    text: str,
    position: int,
    total: int,
    media_path: Path,
    out_path: Path,
) -> Path:
    """Render body slide N: index number, heading, body text, page dots.

    Args:
        text: Scene text, optionally 'heading | body'.
        position: 0-based index among body slides (drives 01, 02, ...).
        total: Number of body slides. Page dots also count the cover,
            so the gold dot matches the Instagram pager.
    """
    tokens = load_tokens()
    width = tokens["canvas"]["width"]
    height = tokens["canvas"]["height"]
    margin = tokens["safe_margins"]["left"]
    layout = tokens["slide_layouts"]["content_slide"]

    img = _background(media_path)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    heading, body = split_dual_text(text)
    if not heading:
        raise PipelineError(f"Empty slide text: {text!r}")

    idx = tokens["type_styles"]["index_number"]
    index_font = _style_font("index_number")
    _draw_tracked(
        draw, (0, layout["index_number_y"]), f"{position + 1:02d}",
        index_font, _color(idx["color"]),
        tracking=2, center_x=width / 2,
    )

    head = tokens["type_styles"]["content_heading"]
    head_font = _style_font("content_heading")
    head_width = width - 2 * margin
    head_lines = _wrap(draw, heading, head_font, head_width)
    _check_max_lines(head_lines, head["max_lines"], "Slide heading")
    heading_y = (
        layout["index_number_y"]
        + idx["size"]
        + layout["gap_after_index"]
    )
    y = _centered_multiline(
        draw, head_lines, head_font, width / 2, heading_y,
        _color(head["color"]), head["line_height"],
    )

    if body:
        body_style = tokens["type_styles"]["body_text"]
        body_font = _style_font("body_text")
        body_width = width * body_style["max_width_pct"]
        body_lines = _wrap(draw, body, body_font, body_width)
        _check_max_lines(body_lines, body_style["max_lines"], "Slide body")
        _centered_multiline(
            draw, body_lines, body_font, width / 2,
            y + layout["gap_after_heading"],
            _color(body_style["color"]), body_style["line_height"],
        )

    # Cover is Instagram slide 1 (SWIPE, no dots). Dots include it so
    # the gold dot matches the app pager.
    _page_dots(
        draw, width / 2, height - layout["dots_y_from_bottom"],
        total + 1, position + 1,
    )

    _composite_text(img, overlay).convert("RGB").save(out_path, quality=92)
    return out_path
