"""Telegram bot: message in, rendered video or carousel out.

Usage:
    python -m src.telegram_bot

Polling (local): leave TELEGRAM_WEBHOOK_URL empty.
Webhook (Cloud Run): set TELEGRAM_WEBHOOK_URL and PORT.

Requires TELEGRAM_BOT_TOKEN in .env (see .env.example).
Scripts are accepted into a FIFO queue; one render runs at a time.
Each finished job is sent back to the chat that requested it.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

from telegram import InputMediaPhoto, Message, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from src.models import PipelineError, RenderResult
from src.pipeline import run

logger = logging.getLogger("auto_graphics.bot")


@dataclass
class RenderJob:
    """One queued script tied to the Telegram message that requested it."""

    message: Message
    script: str
    label: str
    position: int


render_queue: asyncio.Queue[RenderJob] = asyncio.Queue()
pending_jobs = 0
pending_lock = asyncio.Lock()
worker_started = False


class _RedactTokenFilter(logging.Filter):
    """Strip the bot token from any log line that might include a Telegram URL."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token
        # Also catch /bot<token>/ in case the token string alone is missed.
        self._bot_url = re.compile(r"/bot[^/\s]+")

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        if self._token and self._token in message:
            message = message.replace(self._token, "***")
        message = self._bot_url.sub("/bot***/", message)
        record.msg = message
        record.args = ()
        return True


def _configure_logging(token: str) -> None:
    """Clear, human-readable bot logs — no httpx spam, no token in URLs."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S"))
    if token:
        handler.addFilter(_RedactTokenFilter(token))
    root.addHandler(handler)

    # Hide noisy library request dumps (those print the token in the URL).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)

HELP_TEXT = (
    "Send a script starting with /video or /carousel.\n\n"
    "Video example:\n"
    "/video\n"
    "hook: 4 weeks recap | of my journey\n"
    "I filmed my desk for 30 days [videos/working-space]\n\n"
    "Carousel example:\n"
    "/carousel\n"
    "thumbnail: 4 weeks recap | of my journey\n"
    "Slide two [photos/lifestyle]\n"
    "Slide three [photos/lifestyle]\n\n"
    "thumbnail: is always slide 1 (from photos/thumbnails).\n"
    "hook: has no library tag — intro mixes 6 clips from all videos.\n"
    "Body tags: [photos/...] or [videos/...].\n"
    "Use | to split headline (yellow, ALL CAPS) and subline (white).\n"
    "Use \\n inside text for a new visual line on the same slide.\n\n"
    "You can send several scripts at once — they queue and render one by one.\n"
    "Each finished video or carousel is sent back when that job completes.\n\n"
    "Commands: /start /help /options\n"
    "Libraries: {libraries}"
)


def _options_text() -> str:
    templates = config.list_templates() or ["(none)"]
    fonts = config.list_fonts() or ["(none)"]
    sfx = config.list_sfx() or ["(none)"]
    counts = []
    for name in config.valid_libraries():
        folder = config.library_folder(name)
        n = sum(
            1 for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in config.MEDIA_EXTENSIONS
        )
        counts.append(f"  {name}: {n} files")
    return (
        "Templates:\n  " + ", ".join(templates) + "\n\n"
        "Fonts:\n  " + ", ".join(fonts) + "\n\n"
        "SFX:\n  " + ", ".join(sfx) + "\n\n"
        "Libraries:\n" + ("\n".join(counts) if counts else "  (none)")
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    libraries = ", ".join(config.valid_libraries()) or "(none yet)"
    await update.message.reply_text(HELP_TEXT.format(libraries=libraries))


async def options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_options_text())


async def _send_result(message: Message, result: RenderResult) -> None:
    """Upload the finished video or carousel as a reply to the request message."""
    if result.mode == "carousel":
        media = []
        handles = []
        try:
            for path in result.paths:
                handle = path.open("rb")
                handles.append(handle)
                media.append(InputMediaPhoto(media=handle))
            await message.reply_media_group(media=media, write_timeout=180)
        finally:
            for handle in handles:
                handle.close()
        logger.info("Sent carousel to Telegram")
        return

    final = result.paths[0]
    with final.open("rb") as video:
        await message.reply_video(
            video=video, caption=final.name, write_timeout=180
        )
    logger.info("Sent video to Telegram")


async def _process_job(job: RenderJob) -> None:
    """Render one queued script and reply with the file (or an error)."""
    await job.message.reply_text(
        f"Rendering #{job.position} now..."
    )
    logger.info("Job #%d started: %s", job.position, job.label or "(empty)")
    started = time.monotonic()
    try:
        result = await asyncio.to_thread(run, job.script)
    except PipelineError as error:
        logger.info(
            "Job #%d failed (%.0fs): %s",
            job.position,
            time.monotonic() - started,
            error,
        )
        await job.message.reply_text(f"Error: {error}")
        return
    except Exception:
        logger.exception(
            "Job #%d crashed after %.0fs",
            job.position,
            time.monotonic() - started,
        )
        await job.message.reply_text(
            "Something broke during rendering. Check the server logs."
        )
        return

    elapsed = time.monotonic() - started
    if result.mode == "carousel":
        logger.info(
            "Job #%d carousel (%d slides) in %.0fs — uploading",
            job.position,
            len(result.paths),
            elapsed,
        )
    else:
        logger.info(
            "Job #%d video %s in %.0fs — uploading",
            job.position,
            result.paths[0].name,
            elapsed,
        )
    await _send_result(job.message, result)


async def _render_worker() -> None:
    """Drain the FIFO queue: one render at a time, send each result when done."""
    global pending_jobs
    logger.info("Render queue worker started")
    while True:
        job = await render_queue.get()
        try:
            await _process_job(job)
        finally:
            async with pending_lock:
                pending_jobs = max(0, pending_jobs - 1)
            render_queue.task_done()


async def handle_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Accept a script into the queue; worker renders and replies when ready."""
    global pending_jobs, worker_started

    if update.message is None:
        return

    if not worker_started:
        asyncio.create_task(_render_worker())
        worker_started = True

    script = update.message.text or ""
    label = next(
        (line.strip() for line in script.splitlines() if line.strip()),
        "",
    )

    async with pending_lock:
        pending_jobs += 1
        position = pending_jobs

    job = RenderJob(
        message=update.message,
        script=script,
        label=label,
        position=position,
    )
    await render_queue.put(job)

    if position == 1:
        await update.message.reply_text(
            "Queued #1 — starting now. I'll send the file when it finishes."
        )
    else:
        await update.message.reply_text(
            f"Queued #{position}. "
            "I'll send your file when this job finishes (one at a time)."
        )
    logger.info("Queued #%d: %s", position, label or "(empty)")


async def handle_mode_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """/video and /carousel are Telegram commands; the full message is the script."""
    await handle_script(update, context)


async def _on_startup(app: Application) -> None:
    """Start the single render worker when the bot application boots."""
    global worker_started
    if not worker_started:
        app.create_task(_render_worker())
        worker_started = True


def build_app() -> Application:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_on_startup)
        .build()
    )
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler("options", options))
    # Multiline scripts often start with /video or /carousel — those are commands.
    app.add_handler(CommandHandler(["video", "carousel"], handle_mode_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_script))
    return app


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and fill it in."
        )

    _configure_logging(config.TELEGRAM_BOT_TOKEN)
    app = build_app()

    if config.TELEGRAM_WEBHOOK_URL:
        webhook_path = f"/telegram/{config.TELEGRAM_BOT_TOKEN}"
        url = f"{config.TELEGRAM_WEBHOOK_URL}{webhook_path}"
        logger.info("Bot started (webhook mode)")
        logger.info("Listening on port %s", config.PORT)
        app.run_webhook(
            listen="0.0.0.0",
            port=config.PORT,
            url_path=webhook_path.lstrip("/"),
            webhook_url=url,
        )
    else:
        logger.info("Bot started (polling) — waiting for scripts")
        app.run_polling()


if __name__ == "__main__":
    main()
