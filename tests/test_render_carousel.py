"""Renderer tests: 1080x1920 output, accent word pick, design limits."""

import pytest
from PIL import Image

from src.models import PipelineError
from src.render_carousel import (
    load_tokens,
    pick_accent_word,
    render_content_slide,
    render_cover,
    _balance_wrap,
)


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


def test_render_cover_with_eyebrow(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    result = render_cover(
        "4 weeks recap | of my journey", "my journey", photo, out
    )
    assert result == out
    assert Image.open(out).size == _canvas_size()


def test_render_cover_without_eyebrow(photo, tmp_path):
    out = tmp_path / "cover.jpg"
    render_cover("4 weeks recap | of my journey", None, photo, out)
    assert Image.open(out).size == _canvas_size()


def test_render_content_slide(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    render_content_slide(
        "Desk setup that works | Small desk, one monitor, no clutter.",
        0, 3, photo, out,
    )
    assert Image.open(out).size == _canvas_size()


def test_render_content_slide_heading_only(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    render_content_slide("Just a heading", 1, 2, photo, out)
    assert Image.open(out).size == _canvas_size()


def test_accent_word_prefers_connector():
    words = "THINGS I STOPPED BUYING in MY 30s".split()
    assert words[pick_accent_word(words)].lower() in {"in", "my"}


def test_accent_word_skips_tiny_connectors():
    words = "I got an AI Engineer job in 2 months".split()
    assert words[pick_accent_word(words)].lower() == "in"


def test_accent_word_falls_back_to_shortest():
    words = ["remote", "job", "roadmap"]
    assert words[pick_accent_word(words)] == "job"


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


def test_heading_too_long_raises(photo, tmp_path):
    out = tmp_path / "slide.jpg"
    long_heading = "word " * 40
    with pytest.raises(PipelineError, match="too long"):
        render_content_slide(long_heading.strip(), 0, 1, photo, out)


def test_load_rgb_image_applies_exif_orientation(tmp_path):
    from src.render_scene import load_rgb_image

    path = tmp_path / "rotated.jpg"
    img = Image.new("RGB", (80, 40), (10, 200, 30))
    exif = Image.Exif()
    exif[0x0112] = 6  # 90° CW: stored landscape, display portrait
    img.save(path, format="JPEG", exif=exif)
    loaded, _temp = load_rgb_image(path)
    assert loaded.size == (40, 80)
