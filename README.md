# Marginalia

Marginalia is an open-source, personalised "learn anything" app. Tell it what you want to learn, how deep you want to go and how you like to learn. It checks where you're starting from with a few quick questions, plans a course you can edit, writes each section just in time as you reach it, and lets you highlight any passage and ask about it in the margin, where an AI tutor answers with the whole lesson in view.

![Reading a section, with a tutor thread in the margin beside the highlighted passage](docs/screenshots/reader.png)

## What it does

- **Intake:** your goal, a depth (overview, practitioner or rigorous), a learning style (visual, reading, hands-on or intuition first) and anything you already know, followed by 3-4 multiple-choice diagnostic questions (or skip them).
- **An outline you control:** the answers become a short learner profile and a course outline. Rename, reorder, add or remove modules and sections, or ask the model to rework it ("more hands-on, skip the history"). Nothing is written until you start.
- **Just-in-time sections:** a section is researched and written when you open it, and the next one is prefetched. Blocks appear as they stream in: explanations with maths (KaTeX), code, Mermaid diagrams (used heavily for visual learners), worked examples, callouts and exercises with progressive hints and solutions. When web research is on, each section lists its sources.
- **Highlight-and-ask:** select any passage and ask a question. The thread is anchored to that block and quote, and the tutor sees the passage, the blocks around it, the whole section, its research notes and your learner profile. Follow up, resolve or delete threads like comments in a document.
- **Works everywhere:** a responsive web app with light and dark themes, and a command line that generates a whole course end to end.

<p>
  <img src="docs/screenshots/outline.png" alt="The editable course outline" width="49%">
  <img src="docs/screenshots/mobile.png" alt="Reading on a phone" width="22%">
  <img src="docs/screenshots/dark.png" alt="Dark mode" width="27%">
</p>

## Quick start (Docker)

You need Docker and an API key for [Claude](https://console.anthropic.com/) (the default) or OpenAI.

```bash
cp .env.example .env          # then set ANTHROPIC_API_KEY (or LLM_PROVIDER=openai + OPENAI_API_KEY)
docker compose up --build     # or: make up
```

Open <http://localhost:8000>. Postgres runs in its own container, and migrations run automatically when the app starts.

No API key yet? Set `LLM_PROVIDER=fake` in `.env` to run with an offline stand-in model that writes clearly generic placeholder content, then click **Try the demo course** on the home page. The demo course is a real, hand-written course on Bayesian thinking (with diagrams, maths, code, exercises and a margin thread) that needs no model to read.

## Local development

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 22.22+ (Node 24 LTS recommended) and Docker (for Postgres) or a Postgres of your own.

```bash
make setup     # uv sync + npm ci
cp .env.example .env
make dev       # Postgres in Docker, API with auto-reload on :8000, Vite on :5173
```

Open <http://localhost:5173>. The Vite dev server proxies `/api` to the API. `make help` lists the other targets, and the API docs are at <http://localhost:8000/docs>.

## Configuration

Settings come from environment variables or `.env` (see [`.env.example`](.env.example) and [`app/settings.py`](app/settings.py)).

| Variable | Default | What it does |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `fake` (offline demo content) |
| `ANTHROPIC_API_KEY` | | Claude API key. Without it, the SDK's own credential lookup is used |
| `LLM_MODEL` | `claude-opus-5-5` / `gpt-6.1-sol` | Override the model, e.g. `claude-sonnet-5-5` for lower cost |
| `ANTHROPIC_REFUSAL_FALLBACKS` | `true` | Retry requests declined by Claude's safety classifiers on Anthropic's recommended fallback model |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | | OpenAI, or any OpenAI-compatible server (vLLM, Ollama, ...) |
| `OPENAI_API_MODE` | `responses` | `chat` uses Chat Completions, for OpenAI-compatible servers |
| `RESEARCH_BACKEND` | `web` | `web` researches each section with the provider's web search before writing it; `none` skips research |
| `RESEARCH_MAX_SEARCHES` | `3` | Web searches allowed per section |
| `EFFORT_*` | `low` / `medium` | How hard the model thinks for diagnostics, planning, research, sections and the tutor |
| `DATABASE_URL` | local Postgres | Any Postgres connection string, including Supabase's |
| `LLM_CACHE` | `false` | Reuse stored responses for identical requests (the CLI turns this on) |

**Costs.** With the defaults, each section costs one research call (with up to three web searches) and one writing call, and tutor questions are `low`-effort calls that reuse a cached copy of the section. Sections are only written when opened, so an abandoned course costs little. For a cheaper setup, use `LLM_MODEL=claude-sonnet-5-5` and `RESEARCH_BACKEND=none`.

### Using Supabase

Marginalia works with any Postgres, including [Supabase](https://supabase.com/):

1. In your Supabase project, open **Connect** and copy a connection string. The session pooler (port 5432) or the direct connection is simplest. The transaction pooler (port 6543) also works: Marginalia switches to PgBouncer-safe settings for it automatically.
2. Set `DATABASE_URL` to it in `.env` (`postgres://` and `?sslmode=require` forms are both fine) and run `uv run alembic upgrade head`.

The migration enables row-level security on Marginalia's tables, so Supabase's auto-generated REST API doesn't expose them. The app connects as the tables' owner, which RLS doesn't restrict.

## Command line

```bash
uv run marginalia generate "how vaccines work" --depth overview --style visual --out vaccines.md
uv run marginalia demo                  # add the demo course
uv run marginalia export <course-id>    # print a course as Markdown
```

`generate` runs the whole pipeline end to end (the diagnostic questions, which it asks interactively in a terminal, then planning, research and every section) and saves the course in the database too, so you can open it in the app.

## How it works

```mermaid
flowchart LR
  A["Goal, depth, style"] --> B["Diagnostic questions"]
  B --> C["Learner profile + outline"]
  C --> D["You edit the outline"]
  D --> E["Open a section"]
  E --> F["Research notes (web search)"]
  F --> G["Write the section as blocks"]
  G --> H["Read; the next section is prefetched"]
  H --> I["Highlight and ask"]
  I --> J["Tutor reply in the margin"]
```

- **Backend:** FastAPI, SQLModel/SQLAlchemy 2 (async, asyncpg) and Alembic on Postgres. Generation runs as background jobs whose progress lives on the section row: a section is claimed atomically in the database, completed blocks are saved while the response streams, and a job lost to a restart can be reclaimed once it's stale.
- **LLM layer** ([`app/llm`](app/llm)): one interface with three providers. Every request uses structured outputs validated against Pydantic schemas, so there's no JSON scraping, token counting or cut-off repair. On Anthropic, effort is set per task, responses stream, refusals are handled and server-side refusal fallbacks are on. Prompts are Jinja templates in [`app/llm/templates`](app/llm/templates).
- **Web app** ([`frontend`](frontend)): Vite, React 19, TypeScript, Tailwind CSS v4, TanStack Query and React Router. Highlights are anchored by block id plus the quote and the text around it, found again in the rendered text and painted with the CSS Custom Highlight API, so the lesson's DOM is never modified. FastAPI serves the production build from the same origin.

| Path | What's there |
|---|---|
| `app/course` | Courses and sections: diagnostics, planning, outline editing, just-in-time generation and their API |
| `app/tutor` | Highlight-and-ask threads and the tutor |
| `app/llm` | Providers, prompts, structured-output schemas and the response cache |
| `app/cli.py` | The `marginalia` command |
| `alembic/` | Database migrations |
| `frontend/src` | The web app: `pages`, `components`, and `lib` for anchoring, outline editing and margin layout |
| `tests/` | Python tests |

## Tests

```bash
make test        # Python (pytest) and web app (Vitest) tests
make lint        # ruff and TypeScript checks
TEST_DATABASE_URL=postgresql://marginalia:marginalia@localhost:5432/marginalia_test uv run pytest
```

The Python tests drive the whole flow through the API with the offline fake model, so they need no API key. They use SQLite unless `TEST_DATABASE_URL` points at a Postgres database (which they reset). The Anthropic and OpenAI adapters are tested against mocked SDK clients. CI runs everything, with the Python tests on Postgres.

## Roadmap

Adaptive exercises graded against stored solutions, folding good tutor answers back into the course, flagging passages many learners ask about, and more: see [docs/ROADMAP.md](docs/ROADMAP.md).

## Credits

Marginalia started as an import of [**textbook_quality**](https://github.com/VikParuchuri/textbook_quality) by [**Vik Paruchuri**](https://github.com/VikParuchuri), released under the MIT License. Its course-generation pipeline, content-block model, prompt ideas and database layer are the foundation Marginalia builds on, and its commit history is preserved in this repository. Thank you, Vik.

Marginalia is inspired by Endless (endless.academy), an earlier learning product by Vik Paruchuri. **Marginalia is an independent project and is not affiliated with, endorsed by, or sponsored by Vik Paruchuri or Endless.** See [NOTICE](NOTICE) for full attribution.

## Licence

MIT. See [LICENSE](LICENSE), which keeps the original textbook_quality copyright notice alongside Marginalia's.
