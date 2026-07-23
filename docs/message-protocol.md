# Message Protocol

## Purpose

Define the exact format of the text message (Telegram or CLI) that turns a script into a finished vertical video or a TikTok carousel.

## Context

```text
library/
  photos/
    thumbnails/   ← carousel slide 1 only
    lifestyle/    ← all carousel body slides
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
| `/carousel` | `[photos/lifestyle]` only |

Carousel cover always uses `photos/thumbnails/` via the `thumbnail:` line (no tag on that line).

## Process

1. First line: `/video` or `/carousel`.
2. **Video:** optional `hook: text | subline` (no library tag) → 3s intro from all videos.
3. **Carousel:** required `thumbnail: text | subline` (no library tag) → **always slide 1** from `photos/thumbnails/`.
4. Then body lines with `[photos/...]` or `[videos/...]`.
5. `/carousel` body lines must use `[photos/...]`.
6. One script line = one slide. Use `\n` inside headline or subline text to force a new visual line on the same slide (e.g. numbered lists).

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
Desk setup that actually works [photos/lifestyle]
Tools I used every day [photos/lifestyle]
```

### Forced line breaks (same slide)

```text
/carousel
thumbnail: AI & SWE project ideas | 3 builds you can finish
Project 1: RAG Q&A | 1. Load PDFs\n2. Chunk by section\n3. Retrieve top chunks\n4. Answer from context [photos/lifestyle]
```

- Slide 1 = random photo from `library/photos/thumbnails/` + thumbnail text  
- Slide 2+ = body lines from their categories  
- `\n` = new visual line on that slide (not a new slide)

## FAQ/Troubleshoot

- **Carousel needs a thumbnail:** — add `thumbnail: your title` before body slides.
- **No photos in photos/thumbnails** — add `.jpg/.png/.heic` files there.
- **hook: / thumbnail: has no library tag** — correct; do not put `[...]` on those lines.
- **Want numbers on separate lines** — write `\n` between them on the same script line; do not press Enter (that starts a new slide).
- **Unknown library** — photos only have `lifestyle` (+ `thumbnails` for cover). Videos: `lifestyle`, `coding`, `projects`, `working-space`.
