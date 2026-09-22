"""Renderer tests: 1080x1920 Classic Magazine output and design limits."""

import pytest
from PIL import Image

from src.models import PipelineError
from src.render_carousel import (
    load_tokens,
    render_content_slide,
    render_cover,
    _balance_wrap,
    _join_dual,
)


@pytest.fixture(autouse=True)
def _fresh_tokens():
    import src.render_carousel as rc
    rc._tokens_cache = None
    yield
    rc._tokens_cache = None


@pytest.fixture()
def photo(tmp_path):
    """A busy-ish test photo, larger than the canvas."""
    path = tmp_path / "photo.jpg"
    img = Image.new("RGB", (1600, 1200), (90, 120, 150))
    img.save(path)
    return path


def _canvas_size():
    tokens = load_tokens()
    return tokens["canvas"]["width"], tokens["canvas"]["height"]


def _center_pixel(path):
    img = Image.open(path)
    width, height = img.size
    return img.getpixel((width // 2, height // 2))


def test_tokens_are_classic_magazine():
    tokens = load_tokens()
    assert "Classic Magazine" in tokens["template_name"]
    assert tokens["background"]["fit_mode"] == "cover"
    assert tokens["fonts"]["accent"]["family"] == "Crimson Pro"
    assert tokens["body_card"]["kind"] == "liquid_glass"
    assert tokens["type_styles"]["body_text"]["max_lines"] == 6
    assert "fill_for_empty_space" not in tokens["background"]


def test_cover_vignette_darkens_center(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    render_cover("4 weeks recap | of my journey", photo, out)
    red, green, blue = _center_pixel(out)
    # Cover still uses the dark ellipse, so the mid-canvas is dimmer
    # than the source photo (90, 120, 150).
    assert red < 80
    assert green < 110


def test_body_liquid_glass_is_even(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    render_content_slide("Desk setup that actually works.", photo, out)
    img = Image.open(out)
    cx, cy = img.width // 2, img.height // 2
    corner = img.getpixel((2, 2))
    top = img.getpixel((cx, cy - 40))
    bottom = img.getpixel((cx, cy + 40))
    # Edges stay the photo. Glass is even — no wet highlight on top.
    assert abs(corner[1] - 120) < 15
    assert abs(top[0] - bottom[0]) < 20
    assert abs(top[1] - bottom[1]) < 20


def test_cover_fill_keeps_sharp_corners(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    render_cover("4 weeks recap | of my journey", photo, out)
    img = Image.open(out)
    corner = img.getpixel((2, 2))
    # Source photo is (90, 120, 150). Cover-fit keeps that at the edges.
    # Old blur-fill darkened corners toward ~58 red.
    assert corner[0] > 80
    assert abs(corner[1] - 120) < 15


def test_render_cover(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    result = render_cover("4 weeks recap | of my journey", photo, out)
    assert result == out
    assert Image.open(out).size == _canvas_size()


def test_render_cover_headline_only(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    render_cover("4 weeks recap", photo, out)
    assert Image.open(out).size == _canvas_size()


def test_render_content_slide(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    render_content_slide(
        "Desk setup that works.\nSmall desk, one monitor, no clutter.",
        photo, out,
    )
    assert Image.open(out).size == _canvas_size()


def test_render_content_slide_no_pipe(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    render_content_slide("Just a heading", photo, out)
    assert Image.open(out).size == _canvas_size()


def test_italic_for_has_no_fake_gap():
    from PIL import ImageDraw
    from src.render_carousel import _draw_tracked, _font

    img = Image.new("L", (400, 120), 0)
    draw = ImageDraw.Draw(img)
    fnt = _font("Crimson Pro", 400, True, 72)
    _draw_tracked(draw, (20, 20), "for", fnt, 255, tracking=0)

    ink_cols = [
        x for x in range(img.width)
        if any(img.getpixel((x, y)) > 20 for y in range(img.height))
    ]
    assert ink_cols
    gaps = [b - a for a, b in zip(ink_cols, ink_cols[1:]) if b - a > 1]
    # A real "for" is one cluster. Char-by-char italic "f" left a ~15px hole.
    assert not gaps or max(gaps) < 8


def test_join_dual_rebuilds_the_sentence():
    assert _join_dual("Desk setup | that actually works") == (
        "Desk setup that actually works"
    )
    assert _join_dual("Just a heading") == "Just a heading"


def test_balance_wrap_moves_orphan_word():
    from PIL import ImageDraw
    from src.render_carousel import _font

    img = Image.new("RGB", (400, 200), "black")
    draw = ImageDraw.Draw(img)
    fnt = _font("Outfit", 700, False, 50)
    lines = ["Because when you build a real AI", "system"]
    balanced = _balance_wrap(draw, lines, fnt, 2000)
    assert balanced[-1] == "AI system"
    assert not balanced[-2].endswith("AI")


def test_body_allows_six_lines(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    body = "Line one.\nLine two.\nLine three.\nLine four.\nLine five.\nLine six."
    render_content_slide(body, photo, out)
    assert out.exists()


def test_body_too_long_raises(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    long_body = "word " * 80
    with pytest.raises(PipelineError, match="too long"):
        render_content_slide(long_body.strip(), photo, out)


def test_load_rgb_image_applies_exif_orientation(tmp_path):
    from src.render_scene import load_rgb_image

    path = tmp_path / "rotated.jpg"
    img = Image.new("RGB", (80, 40), (10, 200, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # 90° CW: stored landscape, display portrait
    img.save(path, format="JPEG", exif=exif)
    loaded, _temp = load_rgb_image(path)
    assert loaded.size == (40, 80)
