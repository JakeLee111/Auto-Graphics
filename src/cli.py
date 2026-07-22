"""Local CLI entrypoint.

Usage:
    python -m src.cli --script scripts/example_video.txt
    python -m src.cli --text "/carousel
Slide one [hooks]
Slide two [lifestyle]"
"""

import argparse
import sys
from pathlib import Path

import config
from src.models import PipelineError
from src.pipeline import run


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a scene script into a video or carousel slides."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--script", type=Path, help="Path to a script text file")
    source.add_argument("--text", type=str, help="Script text passed inline")
    parser.add_argument(
        "--template",
        default=config.DEFAULT_TEMPLATE,
        help="Template name in templates/ (default: %(default)s)",
    )
    args = parser.parse_args()

    if args.script:
        if not args.script.exists():
            print(f"Script file not found: {args.script}", file=sys.stderr)
            return 1
        message = args.script.read_text()
    else:
        message = args.text

    try:
        result = run(message, template_name=args.template)
    except PipelineError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Mode: {result.mode}")
    for path in result.paths:
        print(f"Done: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
