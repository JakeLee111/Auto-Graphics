# Message Protocol

## Purpose

Define the exact format of the text message (Telegram or CLI) that turns a script into a finished vertical video or a TikTok carousel.

## Context

```text
library/
  photos/
    thumbnails/   ← carousel slide 1 only
    lifestyle/    ← soft carousel body slides
    projects/     ← build / demo / GitHub carousel body slides
  videos/
    lifestyle/
    coding/
    projects/
    working-space/
```

Body tags are always `kind/category`, e.g. `[photos/lifestyle]` or `[videos/coding]`.

**Current stock (use only these):**

| Mode | Valid body tags |
| --- | --- |
| `/video` | `[videos/lifestyle]`, `[videos/coding]`, `[videos/projects]`, `[videos/working-space]` |
| `/carousel` | `[photos/lifestyle]`, `[photos/projects]` |

Carousel cover always uses `photos/thumbnails/` via the `thumbnail:` line (no tag on that line).

## Process

1. First line: `/video` or `/carousel`.
2. **Video:** optional `hook: text | subline` (no library tag) → 3s intro from all videos.
3. **Carousel:** required `thumbnail: text | subline` (no library tag) → **always slide 1** from `photos/thumbnails/`.
4. Then body lines with `[photos/...]` or `[videos/...]`.
5. `/carousel` body lines must use `[photos/...]`.
6. One script line = one slide. Cover is `thumbnail:` only (first beat). Body: group 2–3 related sentences on one line when they are the same idea. Use `\n` between those sentences, and inside text to wrap (e.g. lists). New slide on a topic shift.
7. **Carousel `|` is cover-only.** `thumbnail: left | right` → yellow uppercase headline + white italic subline. Body slides: full sentences, no `|`. `\n` = new visual line. Body max 6 lines.

### Carousel design (Classic Magazine)

Carousel slides render at 1080×1920 (9:16, full TikTok frame) from `templates/carousel-design-tokens.json`:

- **Cover (slide 1):** yellow Outfit Bold headline (text before `|`) + Crimson Pro italic subline (text after `|`). Centered on the photo. A dark vignette sits behind the headline.
- **Body slides:** one Outfit Regular paragraph, centered on a clear liquid-glass card. No vignette.
- Photos fill the 1080×1920 frame (cover-fit, sharp edges).
- No labels, numbers, page dots, or SWIPE — never write those into the script.
- Design limits: cover headline max 3 lines, italic max 2, body max 6. Too-long text fails with a clear error.

### Video example

```text
/video
hook: 4 weeks recap | of my journey
I filmed my real desk for 30 days [videos/working-space]
Follow for the tools I used [videos/coding]
```

### Carousel example

```text
/carousel
thumbnail: 4 weeks recap | of my journey
Desk setup that actually works.\nTools I used every day. [photos/lifestyle]
This GitHub demo of what I built. [photos/projects]
```

### Forced line breaks (same slide)

```text
/carousel
thumbnail: AI & SWE project ideas | 3 builds you can finish
Project 1: RAG Q&A.\n1. Load PDFs\n2. Chunk by section\n3. Retrieve top chunks [photos/projects]
```

- Slide 1 = random photo from `library/photos/thumbnails/` + thumbnail text  
- Slide 2+ = body lines from their categories  
- `\n` = new visual line on that slide (not a new slide)

## FAQ/Troubleshoot

- **Carousel needs a thumbnail:** — add `thumbnail: your title` before body slides.
- **No photos in photos/thumbnails** — add `.jpg/.png/.heic` files there.
- **hook: / thumbnail: has no library tag** — correct; do not put `[...]` on those lines.
- **Headline/body too long** — carousel caps lines (cover headline 3, italic 2, body 6). On the cover, split with `|` so the left side is a short clause. On body slides, split into another slide or add `\n` — do not rewrite the words. Do not use `|` on body slides.
- **Font file not found (Outfit / Crimson Pro)** — copy `Outfit-Regular.ttf`, `Outfit-Bold.ttf`, `CrimsonPro-Italic.ttf` into `fonts/`.
- **Want numbers on separate lines** — write `\n` between them on the same script line; do not press Enter (that starts a new slide).
- **Body slides too short / too many** — group 2–3 related sentences on one line with `\n` between them. Cover stays `thumbnail:` only.
- **`|` on a body slide** — not a new line. Cover only. Write the full sentence; use `\n` for a break.
- **Unknown library** — photos: `lifestyle`, `projects` (+ `thumbnails` for cover). Videos: `lifestyle`, `coding`, `projects`, `working-space`.
