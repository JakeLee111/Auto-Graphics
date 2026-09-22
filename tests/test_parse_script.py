"""Parser tests: carousel and video scripts."""

import pytest

from src.models import PipelineError
from src.parse_script import parse_script

CAROUSEL = (
    "/carousel\n"
    "thumbnail: 4 weeks recap | of my journey\n"
    "Desk setup that actually works [photos/lifestyle]\n"
    "Tools I used every day [photos/lifestyle]\n"
)


def test_carousel_parse():
    parsed = parse_script(CAROUSEL)
    assert parsed.mode == "carousel"
    assert parsed.thumbnail_text == "4 weeks recap | of my journey"
    assert len(parsed.body) == 2


def test_carousel_at_bot_username():
    script = CAROUSEL.replace("/carousel\n", "/carousel@MyGraphicsBot\n")
    parsed = parse_script(script)
    assert parsed.mode == "carousel"


def test_infer_carousel_from_thumbnail_without_mode_line():
    script = (
        "thumbnail: short title | rest of the sentence\n"
        "First clause rest of the sentence [photos/lifestyle]\n"
    )
    parsed = parse_script(script)
    assert parsed.mode == "carousel"
    assert parsed.thumbnail_text == "short title | rest of the sentence"


def test_prepare_script_prepends_carousel_command():
    from src.parse_script import prepare_script

    out = prepare_script(
        "thumbnail: title | sub\n",
        implied_mode="carousel",
    )
    assert out.startswith("/carousel\n")


def test_carousel_accepts_photos_projects():
    script = (
        "/carousel\n"
        "thumbnail: 4 weeks recap | of my journey\n"
        "This GitHub demo of what I built. [photos/projects]\n"
    )
    parsed = parse_script(script)
    assert parsed.body[0].library == "photos/projects"
    assert parsed.body[0].text == "This GitHub demo of what I built."


def test_video_parse_unchanged():
    script = (
        "/video\n"
        "hook: 4 weeks recap | of my journey\n"
        "I filmed my desk for 30 days [videos/working-space]\n"
    )
    parsed = parse_script(script)
    assert parsed.mode == "video"
    assert parsed.hook_text == "4 weeks recap | of my journey"
    assert len(parsed.body) == 1


def test_eyebrow_line_is_not_a_prefix():
    script = CAROUSEL.replace(
        "/carousel\n", "/carousel\neyebrow: my journey\n"
    )
    with pytest.raises(PipelineError, match="needs a tag"):
        parse_script(script)
