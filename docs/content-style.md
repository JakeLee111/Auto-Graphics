# Auto Graphics content style

## Purpose

Guidelines for TikTok video and carousel copy in this project (CS students, junior AI / software engineers).

## Context

Format and tags: `docs/message-protocol.md`.  
This doc covers **what** to write and **how** it should feel — not the `/video` / `/carousel` syntax.

## Audience

Computer science students and junior AI / software engineers.

## Voice

- Clear and beginner-friendly — informative, not academic
- Tips and insights that solve a real pain (staying updated, where to learn, free paths)
- Dense enough to save or rewatch, but each slide must be understandable on first read
- Do not use Jake journey / tutorial skill tone unless the user asks

## Naming resources

Only name platforms or resources from large, well-known organizations.

**OK examples:** Hugging Face, CS50 / Harvard, Google Colab, Kaggle, OpenAI, Google AI, Meta AI, Microsoft Learn, edX

**Avoid:** individual creators, personal newsletters, niche blogs, influencer channels — unless the user names them

Prefer category advice (“org blogs”, “official docs”) over listing many product names.

## Pick the shape: story vs how-to

Decide from the user’s request before writing.

| Shape | When | Body headlines |
| --- | --- | --- |
| **Story** | User shares what happened (“what I did”, “how I got X”, experience, rejections, what changed) | Short story beats — **no** `Step 1`, `Step 2` |
| **How-to** | User wants instructions the viewer can follow (“do this”, checklist, tutorial tips) | `Step 1`, `Step 2` only when each line is a real action |

Do **not** force numbered steps onto a story. Numbered steps are for instructions, not for narrative beats.

### Shared rules (both shapes)

- Brief headline | detail in the subline
- One idea per slide/clip
- Use `\n` when a break helps reading
- Hook / thumbnail: outcome or pain | short subline; `\n` in headline when clearer

### Story shape

- Hook / thumbnail: `How I got …` / what happened | short context (not “in 6 steps” unless the user asks for a count)
- Body: story beat labels only — what happened, what failed, what changed
- Keep “I” / experience voice when the user told a personal story
- A short actionable closer is fine without numbering (e.g. `That is what worked`)

```text
/video
hook: How I got a remote\nAI SWE job | not LinkedIn spam
LinkedIn felt dead | Huge competition.\n90% of my apps rejected [videos/lifestyle]
I moved to Facebook | Developer and hiring\ngroups in my country [videos/working-space]
Headhunters post there | Less competition.\nThey push you for commission [videos/projects]
```

### How-to shape

- Hook / thumbnail: outcome | count when useful (`in 6 steps`, `with 3 projects`)
- Body: `Step N: short label | compact explanation`
- Only number lines that are instructions to follow

```text
/video
hook: How to get a remote\nAI SWE job | in 6 steps
Step 1: Build proof | Finish 2 to 3 small\nprojects you can demo [videos/projects]
Step 2: Show AI skills | RAG, APIs, or fine-tuning\non Hugging Face or Google Colab [videos/coding]
```

### Brief headers, detail in subline

| Bad (long header) | Good |
| --- | --- |
| The problem is auto-apply spam flooding every job post | LinkedIn felt dead |
| Make your GitHub easy for recruiters to skim in 10 seconds | Clean up GitHub |

Header stays short. Put the “why / how / what happened” in the subline.

## Library tags

Use only folders that exist. Match the shot meaning; mix tags across a script.

**Video body:** `coding`, `projects`, `lifestyle`, `working-space`  
**Carousel body:** `lifestyle` only → always `[photos/lifestyle]`  
**Carousel cover:** `thumbnail:` only (from `photos/thumbnails/`)

| Category | Meaning |
| --- | --- |
| `coding` | Laptop, learning, typing, study (videos) |
| `projects` | Builds, demos, GitHub, portfolio (videos) |
| `lifestyle` | Soft journey / life beats; **all carousel body slides** |
| `working-space` | Desk, monitors, setup (videos only) |

- Do **not** use `[videos/broll]` or photo tags other than `[photos/lifestyle]`
- Carousel body = `[photos/lifestyle]` on every body line; video body = `[videos/...]` only

## Carousel habits

- Thumbnail: pain, promise, or story hook | short subline
- Body: one beat per slide, `headline | subline`
- Follow `docs/message-protocol.md` for `/carousel` format and tags

## Video habits

- Hook: outcome or story promise | short subline (no library tag)
- Body: brief header | compact subline `[videos/category]`
- Follow `docs/message-protocol.md` for `/video` format and tags

## On-slide text (fonts)

The render font may break or mis-draw special Unicode characters.

**Avoid:** arrows and similar symbols (`→`, `←`, `↔`, `⇒`, `➜`, etc.), fancy dashes, emoji, and other non-basic punctuation unless you know the font supports them.

**Use instead:** plain words or ASCII separators. Use `\n` for same-slide line breaks.

| Bad | Good |
| --- | --- |
| Learn → build → repeat | Learn, build, repeat |
| Learn → build → repeat | Learn - build - repeat |
| A → B | A to B |

Prefer commas or short words (`to`, `then`) over symbols when listing a sequence.

## Process

1. Decide story vs how-to from the user’s request.
2. Write hook/thumbnail (outcome or “how I …”; add a step count only for how-to).
3. Write body beats: short header | compact subline; add `\n` where it helps. Use `Step N` only for real instructions.
4. Tag from current stock (videos: lifestyle/coding/projects/working-space; carousel body: always photos/lifestyle).
5. Name only large trusted orgs; drop individual creators.
6. Avoid Unicode arrows and fancy symbols in on-slide text (see above).
7. Read each slide once — if it needs a second pass to understand, shorten the header or split with `\n`.
