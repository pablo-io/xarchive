# xarchive

Local X.com (Twitter) likes and bookmarks archive with search.

## What it does

xarchive synchronizes your X.com likes and bookmarks into a local SQLite database via the [`xurl`](https://github.com/uog-ai/xurl) CLI, and presents them in a searchable web interface.

- **Browse** all synced likes and bookmarks in a card-based UI
- **Search** by text content, author username, or date range
- **Sync** manually from the web UI — fetch latest likes/bookmarks on demand
- **100% local** — runs on your machine, no external dependencies beyond xurl

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + uvicorn |
| Database | SQLite (via aiosqlite, raw SQL) |
| Frontend | Jinja2 + HTMX + Tailwind CSS (CDN) |
| Data source | xurl CLI |

## Quick start

### Prerequisites

- Python 3.11+
- [`xurl`](https://github.com/uog-ai/xurl) CLI installed and authenticated

### Setup

```bash
# Clone and enter the project
cd xarchive

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the dev server
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 in your browser.

### Commands

| Command | Description |
|---------|-------------|
| `uvicorn app.main:app --reload` | Start dev server with hot reload |
| `pytest` | Run all tests |
| `pytest tests/e2e/` | Run E2E browser tests only |
| `pytest --cov=app --cov-report=term-missing` | Run tests with coverage report |

## Project structure

```
xarchive/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app factory, lifespan, mounts, routers
│   ├── config.py        # Settings: DB_PATH, PAGE_SIZE, constants
│   ├── db.py            # aiosqlite connection, migrations, CRUD helpers
│   ├── models.py        # Pydantic models for Post, SyncLog, XurlPostInput
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── posts.py     # GET /, GET /posts, GET /posts/load-more, GET /api/posts
│   │   └── sync.py      # POST /sync, GET /sync/status, GET /api/sync/status
│   ├── templates/       # Jinja2 templates (frontend phase)
│   └── static/          # Static assets (CSS, images)
├── data/                # gitignored — SQLite database
├── tests/               # Test suite (test phase)
├── docs/                # Specs, designs, ADRs
├── pyproject.toml
├── .gitignore
└── README.md
```

## License

MIT
