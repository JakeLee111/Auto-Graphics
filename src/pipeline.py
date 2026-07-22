"""Orchestrate: parse -> pick -> render (video or carousel) -> merge/export."""

from pathlib import Path

import config
from src.merge import merge_scenes
from src.models import ParsedScript, PipelineError, RenderResult
from src.parse_script import parse_script
from src.pick_media import pick_intro_clips, pick_media
from src.render_scene import load_template, render_clip, render_still


def _render_video(
    parsed: ParsedScript, template_name: str
) -> RenderResult:
    template = load_template(template_name)
    config.TEMP_DIR.mkdir(exist_ok=True)
    scene_paths: list[Path] = []

    try:
        # Intro: same hook text, N x 0.5s cuts mixed from all library/videos/.
        if parsed.hook_text is not None:
            clips = pick_intro_clips(template.intro_cut_count)
            for cut, media in enumerate(clips):
                out = config.TEMP_DIR / f"intro_{cut:02d}.mp4"
                scene_paths.append(
                    render_clip(
                        parsed.hook_text,
                        media,
                        template,
                        out,
                        template.intro_cut_seconds,
                    )
                )

        for scene in parsed.body:
            media = pick_media(scene.library)
            out = config.TEMP_DIR / f"body_{scene.index:02d}.mp4"
            scene_paths.append(
                render_clip(
                    scene.text,
                    media,
                    template,
                    out,
                    template.body_seconds,
                )
            )

        if not scene_paths:
            raise PipelineError(
                "Nothing to render. Add a hook: line and/or body scenes."
            )

        final = merge_scenes(
            scene_paths,
            template,
            has_hook=parsed.hook_text is not None,
            body_count=len(parsed.body),
        )
    finally:
        for path in scene_paths:
            path.unlink(missing_ok=True)

    return RenderResult(mode="video", paths=[final])


def _render_carousel(
    parsed: ParsedScript, template_name: str
) -> RenderResult:
    template = load_template(template_name)
    config.EXPORTS_DIR.mkdir(exist_ok=True)
    config.TEMP_DIR.mkdir(exist_ok=True)

    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = config.EXPORTS_DIR / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    slides: list[Path] = []
    slide_number = 1

    # Thumbnail is always the first carousel image.
    if parsed.thumbnail_text is not None:
        media = pick_media(config.THUMBNAIL_LIBRARY, images_only=True)
        out = out_dir / f"slide_{slide_number:02d}.jpg"
        slides.append(render_still(parsed.thumbnail_text, media, template, out))
        slide_number += 1

    for scene in parsed.body:
        media = pick_media(scene.library, images_only=True)
        out = out_dir / f"slide_{slide_number:02d}.jpg"
        slides.append(render_still(scene.text, media, template, out))
        slide_number += 1

    return RenderResult(mode="carousel", paths=slides)


def run(message: str, template_name: str = config.DEFAULT_TEMPLATE) -> RenderResult:
    """Turn a script message into a video or a set of carousel slides."""
    parsed = parse_script(message)
    if parsed.mode == "carousel":
        return _render_carousel(parsed, template_name)
    return _render_video(parsed, template_name)
