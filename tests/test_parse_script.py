"""Parser tests: optional eyebrow line and unchanged video behavior."""

import pytest

from src.models import PipelineError
from src.parse_script import parse_script

CAROUSEL = (
    "/carousel\n"
    "thumbnail: 4 weeks recap | of my journey\n"
    "Desk setup that actually works [photos/lifestyle]\n"
    "Tools I used every day [photos/lifestyle]\n"
)


def test_carousel_without_eyebrow():
    parsed = parse_script(CAROUSEL)
    assert parsed.mode == "carousel"
    assert parsed.eyebrow_text is None
    assert parsed.thumbnail_text == "4 weeks recap | of my journey"
    assert len(parsed.body) == 2


def test_carousel_with_eyebrow():
    script = CAROUSEL.replace(
        "/carousel\n", "/carousel\neyebrow: my journey\n"
    )
    parsed = parse_script(script)
    assert parsed.eyebrow_text == "my journey"


def test_eyebrow_exact_user_line():
    script = (
        "/carousel\n"
        "eyebrow: If I Had To Start Over\n"
        "thumbnail: short title | rest of the sentence\n"
        "First clause | rest of the sentence [photos/lifestyle]\n"
    )
    parsed = parse_script(script)
    assert parsed.eyebrow_text == "If I Had To Start Over"
    assert parsed.thumbnail_text == "short title | rest of the sentence"


def test_eyebrow_space_before_colon():
    script = CAROUSEL.replace(
        "/carousel\n", "/carousel\neyebrow : If I Had To Start Over\n"
    )
    parsed = parse_script(script)
    assert parsed.eyebrow_text == "If I Had To Start Over"


def test_carousel_at_bot_username():
    script = CAROUSEL.replace("/carousel\n", "/carousel@MyGraphicsBot\n")
    parsed = parse_script(script)
    assert parsed.mode == "carousel"


def test_infer_carousel_from_eyebrow_without_mode_line():
    script = (
        "eyebrow: If I Had To Start Over\n"
        "thumbnail: short title | rest of the sentence\n"
        "First clause | rest of the sentence [photos/lifestyle]\n"
    )
    parsed = parse_script(script)
    assert parsed.mode == "carousel"
    assert parsed.eyebrow_text == "If I Had To Start Over"


def test_prepare_script_prepends_carousel_command():
    from src.parse_script import prepare_script

    out = prepare_script(
        "eyebrow: If I Had To Start Over\n"
        "thumbnail: title | sub\n",
        implied_mode="carousel",
    )
    assert out.startswith("/carousel\n")


def test_eyebrow_rejected_in_video_mode():
    script = (
        "/video\n"
        "eyebrow: my journey\n"
        "Some scene [videos/coding]\n"
    )
    with pytest.raises(PipelineError, match="only for /carousel"):
        parse_script(script)


def test_only_one_eyebrow_allowed():
    script = CAROUSEL.replace(
        "/carousel\n",
        "/carousel\neyebrow: one\neyebrow: two\n",
    )
    with pytest.raises(PipelineError, match="one eyebrow"):
        parse_script(script)


def test_eyebrow_must_not_have_library_tag():
    script = CAROUSEL.replace(
        "/carousel\n", "/carousel\neyebrow: label [photos/lifestyle]\n"
    )
    with pytest.raises(PipelineError, match="no library tag"):
        parse_script(script)


def test_carousel_accepts_photos_projects():
    script = (
        "/carousel\n"
        "thumbnail: 4 weeks recap | of my journey\n"
        "This GitHub demo | of what I built [photos/projects]\n"
    )
    parsed = parse_script(script)
    assert parsed.body[0].library == "photos/projects"


def test_video_parse_unchanged():
    script = (
        "/video\n"
        "hook: 4 weeks recap | of my journey\n"
        "I filmed my desk for 30 days [videos/working-space]\n"
    )
    parsed = parse_script(script)
    assert parsed.mode == "video"
    assert parsed.hook_text == "4 weeks recap | of my journey"
    assert parsed.eyebrow_text is None
    assert len(parsed.body) == 1
