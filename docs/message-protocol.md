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
4. **Carousel:** optional `eyebrow: small label` (no library tag) → tiny gold label above the cover title. Omit it and the cover has no label.
5. Then body lines with `[photos/...]` or `[videos/...]`.
6. `/carousel` body lines must use `[photos/...]`.
7. One script line = one slide. Use `\n` inside headline or subline text to force a new visual line on the same slide (e.g. numbered lists).
8. **Carousel `|`:** `thumbnail:` and every body line must be `short heading | rest of that sentence`. Left = heading (max 2 lines). Right = body (max 4 lines). No `|` means the whole line is the heading and will fail if it wraps past 2 lines.

### Carousel design (Minimal Mono Chic)

Carousel slides render at 1080×1920 (9:16, full TikTok frame) from `templates/carousel-design-tokens.json`:

- **Cover (slide 1):** eyebrow (if given) + big uppercase title with **one** word auto-styled in gold italic + subtitle (text after `|`) + SWIPE footer.
- **Body slides:** auto-numbered `01, 02, ...` + heading (text before `|`) + body (text after `|`) + page dots.
- Numbering, the accent word, and page dots are generated — never write them in the script.
- Design limits: title max 3 lines, heading max 2, body max 4. Too-long text fails with a clear error.

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
eyebrow: my journey
thumbnail: 4 weeks recap | of my journey
Desk setup | that actually works [photos/lifestyle]
This GitHub demo | of what I built [photos/projects]
```

`eyebrow:` is optional — leave it out for a cover with no label.

### Forced line breaks (same slide)

```text
/carousel
thumbnail: AI & SWE project ideas | 3 builds you can finish
Project 1: RAG Q&A | 1. Load PDFs\n2. Chunk by section\n3. Retrieve top chunks\n4. Answer from context [photos/projects]
```

- Slide 1 = random photo from `library/photos/thumbnails/` + thumbnail text  
- Slide 2+ = body lines from their categories  
- `\n` = new visual line on that slide (not a new slide)

## FAQ/Troubleshoot

- **Carousel needs a thumbnail:** — add `thumbnail: your title` before body slides.
- **No photos in photos/thumbnails** — add `.jpg/.png/.heic` files there.
- **hook: / thumbnail: / eyebrow: has no library tag** — correct; do not put `[...]` on those lines.
- **Headline/heading/body too long** — carousel caps lines (title 3, heading 2, body 4). Split with `|` so the left side is a short clause; do not rewrite the words.
- **Slide heading is too long (4 lines, max 2)** — the body line had no `|`, so the whole sentence became the heading. Add `clause | rest`.
- **Font file not found (Outfit / Instrument Serif)** — copy `Outfit-Regular.ttf`, `Outfit-Bold.ttf`, `InstrumentSerif-Italic.ttf` into `fonts/`.
- **Want numbers on separate lines** — write `\n` between them on the same script line; do not press Enter (that starts a new slide).
- **Unknown library** — photos: `lifestyle`, `projects` (+ `thumbnails` for cover). Videos: `lifestyle`, `coding`, `projects`, `working-space`.
