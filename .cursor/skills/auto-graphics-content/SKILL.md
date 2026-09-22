---
name: auto-graphics-content
description: >-
  Writes Auto Graphics TikTok /video and /carousel scripts in protocol format
  with how-to hooks, numbered steps, brief headers, and compact sublines. Use
  when the user asks for carousel, video, TikTok script, content script, or
  tip slides in this project.
---

# Auto Graphics content

## When to use

Any request to write `/video` or `/carousel` scripts for this repo.

## Always read first

1. `docs/message-protocol.md` — syntax and tags
2. `docs/content-style.md` — voice, how-to shape, `\n`, naming rules

Do **not** use the external Jake TikTok journey skill unless the user asks.

## Default output shape

### Hook / thumbnail

- Outcome first: `How to get a remote AI SWE job`
- Number in the subline: `in 6 steps`
- Add `\n` in the headline when two short lines read clearer

### Body

- `Step 1: Short label | compact explanation [kind/category]`
- Header = brief action label only
- Subline = the detail
- Use `\n` inside headline or subline when a break helps (lists, long phrases)
- One script line = one slide/clip

### Tags

- `/carousel` body → `[photos/...]`
- `/video` body → `[videos/...]`
- If user says they only have one library (e.g. lifestyle), use that category on every body line

## Quick examples

```text
/video
hook: How to get a remote\nAI SWE job | in 6 steps
Step 1: Build proof | Finish 2 to 3 small\nprojects you can demo [videos/lifestyle]
Step 2: Show AI skills | RAG, APIs, or fine-tuning\non Hugging Face or Google Colab [videos/lifestyle]
```

```text
/carousel
thumbnail: How to get a remote\nAI SWE job | in 6 steps
Step 1: Build proof | Finish 2 to 3 small\nprojects you can demo [photos/lifestyle]
Step 2: Show AI skills | RAG, APIs, or fine-tuning\non Hugging Face or Google Colab [photos/lifestyle]
```

## Hard bans

- Flat tags like `[broll]` or `[coding]` (must be `kind/category`)
- Library tags on `hook:` / `thumbnail:` lines
- `hook:` on carousels
- Unicode arrows / fancy symbols on slides
- Naming individual creators unless the user names them
