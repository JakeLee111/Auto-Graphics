"""Telegram send helpers: original files only, albums max out at 10."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from telegram import InputMediaDocument

from src.models import RenderResult
from src.telegram_bot import TELEGRAM_ALBUM_MAX, _chunks, _send_result


def test_chunks_split_past_telegram_album_limit():
    paths = [Path(f"{i}.jpg") for i in range(23)]
    chunks = _chunks(paths)
    assert [len(c) for c in chunks] == [10, 10, 3]
    assert chunks[0][0].name == "0.jpg"
    assert chunks[-1][-1].name == "22.jpg"
    assert TELEGRAM_ALBUM_MAX == 10


def test_chunks_keep_a_short_carousel_as_one_album():
    paths = [Path(f"{i}.jpg") for i in range(4)]
    assert _chunks(paths) == [paths]


def _touch_slides(folder: Path, count: int) -> list[Path]:
    paths = []
    for i in range(count):
        path = folder / f"slide_{i:02d}.jpg"
        path.write_bytes(b"fake")
        paths.append(path)
    return paths


def _mock_message() -> MagicMock:
    message = MagicMock()
    message.reply_media_group = AsyncMock()
    message.reply_document = AsyncMock()
    return message


def test_send_result_sends_every_slide_as_files_across_albums(tmp_path):
    paths = _touch_slides(tmp_path, 11)
    message = _mock_message()
    result = RenderResult(mode="carousel", paths=paths)

    asyncio.run(_send_result(message, result))

    message.reply_media_group.assert_awaited_once()
    album = message.reply_media_group.await_args.kwargs["media"]
    assert len(album) == 10
    assert all(isinstance(item, InputMediaDocument) for item in album)
    message.reply_document.assert_awaited_once()
    doc_kwargs = message.reply_document.await_args.kwargs
    assert doc_kwargs["filename"] == "slide_10.jpg"
    assert doc_kwargs["disable_content_type_detection"] is True


def test_send_result_sends_one_carousel_file_album(tmp_path):
    paths = _touch_slides(tmp_path, 4)
    message = _mock_message()
    result = RenderResult(mode="carousel", paths=paths)

    asyncio.run(_send_result(message, result))

    message.reply_media_group.assert_awaited_once()
    album = message.reply_media_group.await_args.kwargs["media"]
    assert len(album) == 4
    assert all(isinstance(item, InputMediaDocument) for item in album)
    message.reply_document.assert_not_awaited()


def test_send_result_sends_one_carousel_file(tmp_path):
    paths = _touch_slides(tmp_path, 1)
    message = _mock_message()
    result = RenderResult(mode="carousel", paths=paths)

    asyncio.run(_send_result(message, result))

    message.reply_media_group.assert_not_awaited()
    message.reply_document.assert_awaited_once()
    assert message.reply_document.await_args.kwargs["filename"] == "slide_00.jpg"


def test_send_result_sends_video_as_file(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    message = _mock_message()
    result = RenderResult(mode="video", paths=[video])

    asyncio.run(_send_result(message, result))

    message.reply_document.assert_awaited_once()
    doc_kwargs = message.reply_document.await_args.kwargs
    assert doc_kwargs["filename"] == "clip.mp4"
    assert doc_kwargs["disable_content_type_detection"] is True
    message.reply_media_group.assert_not_awaited()
