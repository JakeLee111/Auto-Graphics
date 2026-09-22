# Auto Graphics

Turn a text script into a vertical TikTok video or a photo carousel. Each scene ends with a `[library]` tag; the pipeline picks media, burns Bold Editorial text on top, and exports the result.

## How it works

1. You send a script starting with `/video` or `/carousel`.
2. For video: optional `hook:` line = 3s intro (background flips every 0.5s with the same text), then body lines at 2s each.
3. For carousel: required `thumbnail:` line becomes **slide 1** (photo from `photos/thumbnails/`), then body slides follow.
4. Video gets fixed-rule SFX (keyboard typing at start, mouse click on body scenes). No background music — add that later yourself.
5. Output lands in `exports/` (CLI) or is sent back on Telegram.

Full protocol: [docs/message-protocol.md](docs/message-protocol.md).

## Setup (local)

Requirements: Python 3.11+, FFmpeg (`brew install ffmpeg`).

```bash
cd "Auto Graphics"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Put media here:

```text
library/photos/<category>/   ← .jpg .jpeg .png   (for /carousel)
library/videos/<category>/   ← .mp4 .mov         (for /video)
```

Video categories: `lifestyle`, `coding`, `projects`, `working-space`.  
Photo categories: `lifestyle` and `projects` for carousel body, plus `thumbnails` for carousel cover.  
Tags look like `[photos/lifestyle]`, `[photos/projects]`, or `[videos/working-space]`.  
`hook:` has **no** tag — intro mixes 6 clips from all of `library/videos/`.

## Usage (CLI)

```bash
python -m src.cli --script scripts/example_video.txt
python -m src.cli --script scripts/example_carousel.txt
```

## Aesthetic templates

### Video (`templates/hook.json`)

- Headline: Bebas Neue, yellow `#F5C518`, UPPERCASE
- Subline: Caveat Bold, white, letter case (after a `|` in the text)
- Soft shadow, no caption box, no smiley
- Write scenes like: `4 weeks recap | of my journey [videos/lifestyle]`
- Video intro: `hook: 4 weeks recap | of my journey` (no library tag)

### Carousel — Classic Magazine (`templates/carousel-design-tokens.json`)

Carousels render at 1080×1920 (9:16, full TikTok frame). The photo fills the
frame (cover-fit, sharp edges). Cover uses a dark vignette; body slides use a
clear liquid-glass card around the paragraph.
Fonts: Outfit Bold (yellow cover headline), Crimson Pro Italic (cover subline),
Outfit Regular (body) — files in `fonts/`:

- **Cover:** `headline | subline` → yellow uppercase + white italic, centered
- **Body slides:** full sentences as one centered white paragraph on a liquid-glass card. `\n` starts a new visual line. Do not use `|` on body slides.
- No labels, numbers, page dots, or SWIPE

Edit the tokens JSON to change colors, sizes, vignette, or the body card —
the renderer (`src/render_carousel.py`) reads everything from it.

Tune sizes/colors in the JSONs. Browse more fonts at [Google Fonts](https://fonts.google.com).

## Sound effects

Your imported files in `sfx/`:

- `Keyboard-Typing.mp3` — plays at the start (trimmed to the 3s intro)
- `mouse-click.mp3` — plays on each body scene after the intro

No background music (add that later yourself).

## Telegram bot

1. Create a bot with [@BotFather](https://t.me/BotFather).
2. `cp .env.example .env` and set `TELEGRAM_BOT_TOKEN`.
3. Run locally (polling):

```bash
python -m src.telegram_bot
```

Commands: `/start`, `/help`, `/options` (lists templates, fonts, SFX, libraries).

Send a full multiline script starting with `/video` or `/carousel`.

## Cloud Run webhook (starts when you message)

This bot cannot stay running inside a local editor agent. Use Google Cloud Run (or similar) instead:

1. Put your real media in `library/` before building the image (or sync later via volume/GCS).
2. Build and deploy:

```bash
gcloud run deploy auto-graphics \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --timeout 300 \
  --set-env-vars "TELEGRAM_BOT_TOKEN=YOUR_TOKEN,TELEGRAM_WEBHOOK_URL=https://YOUR_SERVICE_URL"
```

3. After deploy, set `TELEGRAM_WEBHOOK_URL` to the Cloud Run HTTPS URL (no trailing slash) and redeploy so the bot registers the webhook on startup.
4. Message the bot on Telegram — Cloud Run wakes, renders, replies, then sleeps.

`Dockerfile` is included. Keep secrets in Cloud Run env vars, not in git.

### Simpler always-on alternative (VPS)

```bash
sudo apt update && sudo apt install -y ffmpeg python3-venv
# clone repo, venv, pip install, .env with token only (no WEBHOOK_URL)
python -m src.telegram_bot   # or systemd — see earlier docs pattern
```

## Project layout

```text
library/
  photos/<category>/   photos for /carousel   → tag [photos/category]
  videos/<category>/   clips for /video       → tag [videos/category]
templates/      visual styles (hook.json)
fonts/          .ttf / .otf files
sfx/            Keyboard-Typing.mp3, mouse-click.mp3
exports/        finished videos and carousel slides
scripts/        example scripts
src/            pipeline code
docs/           message protocol SOP
Dockerfile      Cloud Run image
```

## Troubleshooting

- **Unknown library** — tag must be `photos/category` or `videos/category` and the folder must exist.
- **/carousel only uses photo libraries** — use `[photos/...]`.
- **Telegram ignores /video scripts** — bot registers `/video` and `/carousel` as commands.
- **Conflict: terminated by other getUpdates** — two bots are polling the same token. Stop the extra one (other terminal or Cloud Run), then `python -m src.telegram_bot` once.
- **FFmpeg failed** — ensure `ffmpeg` is on PATH.
- **"Slide body is too long"** — carousel body max 6 lines. Split onto another slide or add `\n`. Do not put `|` on body slides.
- **No photos in photos/thumbnails** — add `.jpg/.png/.heic` files there for slide 1.
