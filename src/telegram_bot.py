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
import fcntl
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import IO

from telegram import InputMediaPhoto, Message, Update
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from src.models import PipelineError, RenderResult
from src.parse_script import prepare_script
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
_instance_lock: IO[str] | None = None
_conflict_logged = False


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


def _acquire_instance_lock() -> None:
    """Fail fast if another local python -m src.telegram_bot is already running."""
    global _instance_lock
    config.TEMP_DIR.mkdir(exist_ok=True)
    lock_path = config.TEMP_DIR / "telegram_bot.lock"
    handle = lock_path.open("w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise SystemExit(
            "Another telegram bot is already running on this Mac.\n"
            "Stop it with Ctrl+C in that terminal, then start this one again."
        )
    handle.write(str(os.getpid()))
    handle.flush()
    _instance_lock = handle


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log Telegram API errors without dumping a traceback for known conflicts."""
    global _conflict_logged
    err = context.error
    if isinstance(err, Conflict):
        if not _conflict_logged:
            _conflict_logged = True
            logger.error(
                "Another process is already polling this bot token "
                "(a second terminal, or Cloud Run). Stop that instance, "
                "then restart: python -m src.telegram_bot"
            )
        return
    logger.exception("Telegram error: %s", err)

HELP_TEXT = (
    "Send a script starting with /video or /carousel.\n\n"
    "Video example:\n"
    "/video\n"
    "hook: 4 weeks recap | of my journey\n"
    "I filmed my desk for 30 days [videos/working-space]\n\n"
    "Carousel example:\n"
    "/carousel\n"
    "eyebrow: my journey\n"
    "thumbnail: 4 weeks recap | of my journey\n"
    "Desk setup | that actually works [photos/lifestyle]\n"
    "This GitHub demo | of what I built [photos/projects]\n\n"
    "thumbnail: is always slide 1 (from photos/thumbnails).\n"
    "eyebrow: is optional — small gold label above the cover title.\n"
    "hook: has no library tag — intro mixes 6 clips from all videos.\n"
    "Body tags: [photos/...] or [videos/...].\n"
    "Carousel: always use |  (short heading | rest of the sentence).\n"
    "Video: | is optional (headline | subline).\n"
    "Carousel numbering, dots, and SWIPE are automatic.\n"
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


def _command_name(text: str) -> str | None:
    """Return 'video' or 'carousel' when the message starts with that command."""
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    match = re.match(
        r"^/(video|carousel)(?:@[A-Za-z0-9_]+)?\b", first, re.IGNORECASE
    )
    if match:
        return match.group(1).lower()
    return None


def _implied_mode(update: Update) -> str | None:
    """Mode from the first line or a Telegram bot_command entity."""
    message = update.message
    if message is None:
        return None
    text = message.text or ""
    found = _command_name(text)
    if found:
        return found
    for entity in message.entities or []:
        if entity.type != "bot_command":
            continue
        token = text[entity.offset:entity.offset + entity.length]
        name = token.lstrip("/").split("@")[0].lower()
        if name in {"video", "carousel"}:
            return name
    return None


async def handle_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Accept a script into the queue; worker renders and replies when ready."""
    global pending_jobs, worker_started

    if update.message is None:
        return

    if not worker_started:
        asyncio.create_task(_render_worker())
        worker_started = True

    raw = update.message.text or ""
    script = prepare_script(raw, implied_mode=_implied_mode(update))
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
    """Clear a leftover webhook, then start the render worker."""
    global worker_started
    if not config.TELEGRAM_WEBHOOK_URL:
        await app.bot.delete_webhook(drop_pending_updates=True)
    if not worker_started:
        # post_init runs before Application.create_task is allowed.
        asyncio.get_running_loop().create_task(_render_worker())
        worker_started = True


def build_app() -> Application:
    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(_on_startup)
        .build()
    )
    app.add_error_handler(_error_handler)
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
    _acquire_instance_lock()
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
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
