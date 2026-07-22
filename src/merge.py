"""Merge rendered scene clips and mix fixed-rule sound effects.

SFX rule:
  - keyboard typing at the start of the video (t=0, trimmed to intro length)
  - mouse click on each body scene that starts at/after the intro (~3s)
"""

import subprocess
from datetime import datetime
from pathlib import Path

import config
from src.models import Template
from src.render_scene import run_ffmpeg


def _concat_silent(scene_paths: list[Path], out_path: Path) -> Path:
    """Join muted clips with the concat demuxer (copy, no re-encode)."""
    if len(scene_paths) == 1:
        run_ffmpeg(["-i", str(scene_paths[0]), "-c", "copy", str(out_path)])
        return out_path

    list_path = config.TEMP_DIR / "concat_list.txt"
    list_path.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in scene_paths)
    )
    run_ffmpeg(
        [
            "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy",
            str(out_path),
        ]
    )
    list_path.unlink(missing_ok=True)
    return out_path


def _mix_sfx(
    silent_video: Path,
    out_path: Path,
    template: Template,
    has_hook: bool,
    body_count: int,
) -> Path:
    """Typing at t=0; mouse clicks from the body (after intro / 3s)."""
    typing = config.SFX_TYPING
    click = config.SFX_CLICK
    if not typing.exists() or not click.exists():
        silent_video.replace(out_path)
        return out_path

    if has_hook:
        intro_end_ms = int(
            template.intro_cut_count * template.intro_cut_seconds * 1000
        )
        typing_seconds = min(
            config.SFX_TYPING_SECONDS,
            template.intro_cut_count * template.intro_cut_seconds,
        )
    else:
        intro_end_ms = 0
        typing_seconds = config.SFX_TYPING_SECONDS

    # (path, delay_ms, is_typing)
    events: list[tuple[Path, int, bool]] = [(typing, 0, True)]

    for i in range(body_count):
        start_ms = intro_end_ms + int(i * template.body_seconds * 1000)
        if has_hook:
            events.append((click, start_ms, False))
        elif i > 0:
            events.append((click, start_ms, False))

    inputs: list[str] = ["-i", str(silent_video)]
    filter_parts: list[str] = []
    for idx, (sfx_path, delay, is_typing) in enumerate(events):
        inputs.extend(["-i", str(sfx_path)])
        if is_typing:
            fade_start = max(0.0, typing_seconds - 0.4)
            filter_parts.append(
                f"[{idx + 1}:a]atrim=0:{typing_seconds},"
                f"afade=t=out:st={fade_start}:d=0.4,"
                f"adelay={delay}|{delay},volume=0.8[a{idx}]"
            )
        else:
            filter_parts.append(
                f"[{idx + 1}:a]adelay={delay}|{delay},volume=0.95[a{idx}]"
            )

    mix_inputs = "".join(f"[a{i}]" for i in range(len(events)))
    filter_parts.append(
        f"{mix_inputs}amix=inputs={len(events)}:dropout_transition=0:normalize=0[aout]"
    )
    filter_complex = ";".join(filter_parts)

    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(silent_video),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    duration = result.stdout.strip() or "0"

    run_ffmpeg(
        [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", duration,
            str(out_path),
        ]
    )
    return out_path


def merge_scenes(
    scene_paths: list[Path],
    template: Template,
    has_hook: bool,
    body_count: int,
) -> Path:
    """Concat clips in order, mix SFX, write exports/YYYYMMDD_HHMMSS.mp4."""
    config.EXPORTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    silent_path = config.TEMP_DIR / f"silent_{stamp}.mp4"
    out_path = config.EXPORTS_DIR / f"{stamp}.mp4"

    _concat_silent(scene_paths, silent_path)
    try:
        _mix_sfx(silent_path, out_path, template, has_hook, body_count)
    finally:
        silent_path.unlink(missing_ok=True)

    return out_path
