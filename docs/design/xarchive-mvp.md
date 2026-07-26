# Technical Design: xarchive MVP

**File path:** `docs/design/xarchive-mvp.md`
**Status:** Draft
**Spec reference:** `docs/spec/xarchive-mvp.md`

---

## 1. Architecture Overview

### 1.1 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOCAL MACHINE                               │
│                                                                     │
│  ┌───────────┐    HTTP/JSON     ┌──────────────────────────────┐   │
│  │           │ ───────────────> │                              │   │
│  │  Browser  │    HTMX reqs     │       FastAPI (uvicorn)      │   │
│  │  (user)   │ <─────────────── │                              │   │
│  │           │    HTML frags    │  ┌────────┐  ┌───────────┐  │   │
│  └───────────┘                  │  │Jinja2  │  │  Routes   │  │   │
│                                 │  │Templ.  │  │ posts/sync│  │   │
│                                 │  └────────┘  └─────┬─────┘  │   │
│                                 │                    │         │   │
│                                 │              ┌─────┴──────┐  │   │
│                                 │              │  aiosqlite  │  │   │
│                                 │              └─────┬──────┘  │   │
│                                 └────────────────────┼─────────┘   │
│                                                      │             │
│                                                      │ SQL I/O     │
│                                                      ▼             │
│                                 ┌──────────────────────────────┐   │
│                                 │   data/xarchive.db (SQLite)  │   │
│                                 │   posts | sync_log           │   │
│                                 └──────────────────────────────┘   │
│                                                                     │
│                                 ┌──────────────────────────────┐   │
│                                 │   xurl CLI (subprocess)      │   │
│                                 │   `xurl likes`               │   │
│                                 │   `xurl bookmarks`           │   │
│                                 └──────────────┬───────────────┘   │
│                                                │                   │
└────────────────────────────────────────────────┼───────────────────┘
                                                 │ HTTPS (X API v2)
                                                 ▼
                                        ┌─────────────────┐
                                        │   X.com API     │
                                        │   (external)    │
                                        └─────────────────┘
```

### 1.2 Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        app/main.py                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  FastAPI app factory                                      │  │
│  │  • lifespan: init_db() → yield → close_db()              │  │
│  │  • mount: Jinja2Templates("app/templates")               │  │
│  │  • mount: StaticFiles("app/static") → /static            │  │
│  │  • include_router: posts_router → prefix=""               │  │
│  │  • include_router: sync_router → prefix=""                │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────┬──────────────────────────────┬───────────────────┘
               │                              │
    ┌──────────▼──────────┐       ┌───────────▼───────────┐
    │  app/routes/posts.py│       │  app/routes/sync.py   │
    │                     │       │                       │
    │  GET /              │       │  POST /sync           │
    │  GET /posts         │       │  GET /sync/status     │
    │  GET /posts/load-more│      │                       │
    │  GET /api/posts     │       │  GET /api/sync/status │
    └────────┬────────────┘       └───────────┬───────────┘
             │                                │
             │         ┌──────────┐           │
             └────────>│ app/db.py│<──────────┘
                      │          │
                      │ get_db() │
                      │ upsert_post()
                      │ search_posts()
                      │ get_posts()
                      │ create_sync_log()
                      │ update_sync_log()
                      │ init_db()
                      └────┬─────┘
                           │
                      ┌────▼─────┐
                      │app/config│
                      │.py       │
                      │DB_PATH   │
                      │PAGE_SIZE │
                      └──────────┘

    ┌─────────────────────────────────────────────────┐
    │  app/models.py                                  │
    │  • Post (Pydantic) — read model for templates   │
    │  • SyncLog (Pydantic) — sync status model       │
    │  • XurlPostInput (Pydantic) — xurl JSON input   │
    └─────────────────────────────────────────────────┘
```

### 1.3 Dependency Graph

```
config.py          (no internal deps — leaf node)
    ↑
models.py          (no internal deps — leaf node)
    ↑
db.py              (depends on: config, models)
    ↑
routes/posts.py    (depends on: db, models, config)
routes/sync.py     (depends on: db, models, config)
    ↑
main.py            (depends on: db, routes/posts, routes/sync)
    ↑
templates/         (depends on: models — uses Post fields)
```

---

## 2. Component Design

### 2.1 `app/config.py` — Application Settings

**Purpose:** Single source of truth for all configurable values.

```
Module-level constants:
    DB_PATH: Path = Path("data/xarchive.db")
    PAGE_SIZE: int = 20
    XURL_COMMAND: str = "xurl"
    SYNC_TIMEOUT_SECONDS: int = 120
    HOST: str = "127.0.0.1"
    PORT: int = 8000
```

### 2.2 `app/models.py` — Pydantic Models

**Purpose:** Type-safe data transfer between layers.

#### `XurlPostInput` (validates xurl JSON output)
```
Fields:
    id: str
    text: str
    author_id: str
    author_username: str
    author_name: str
    author_avatar: str
    created_at: str
    media_urls: list[str] = []
    url: str
```

#### `Post` (read model for templates and API)
```
Fields:
    id: str
    text: str
    author_id: str
    author_username: str
    author_name: str
    author_avatar: str
    created_at: str
    source: str
    media_urls: list[str]
    url: str
    imported_at: str

Derived properties:
    @property created_at_display -> str — "Jan 15, 2025"
    @property is_like -> bool
    @property is_bookmark -> bool
```

#### `SyncLog` (sync status tracking)
```
Fields:
    id: int | None = None
    source_type: str
    started_at: str
    finished_at: str | None = None
    status: str = "running"
    posts_new: int = 0
    posts_updated: int = 0
    error_message: str | None = None
```

### 2.3 `app/db.py` — Database Layer

#### Connection Management

```
Module-level state:
    _db: aiosqlite.Connection | None = None

async def get_db() -> aiosqlite.Connection
async def init_db()
async def close_db()
```

#### Migrations (Schema)

```python
_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS posts (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        author_id TEXT NOT NULL,
        author_username TEXT NOT NULL,
        author_name TEXT NOT NULL,
        author_avatar TEXT NOT NULL,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL,
        media_urls TEXT NOT NULL DEFAULT '[]',
        url TEXT NOT NULL,
        imported_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_posts_author_username ON posts(author_username)",
    "CREATE INDEX IF NOT EXISTS idx_posts_source ON posts(source)",
    """
    CREATE TABLE IF NOT EXISTS sync_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_type TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        posts_new INTEGER NOT NULL DEFAULT 0,
        posts_updated INTEGER NOT NULL DEFAULT 0,
        error_message TEXT
    )
    """,
]
```

#### CRUD Helpers

```
async def upsert_post(post: XurlPostInput, source: str, now: str) -> str
    — "new" | "updated", INSERT OR REPLACE, merge source

async def get_posts(page=1, per_page=PAGE_SIZE, source="all") -> tuple[list[dict], int]

async def search_posts(q, username, date_from, date_to, source, page, per_page) -> tuple[list[dict], int]

async def create_sync_log(source_type: str) -> int

async def update_sync_log(log_id, status, posts_new=0, posts_updated=0, error_message=None)

async def get_last_sync_log() -> dict | None

def row_to_post_dict(row) -> dict
```

### 2.4 `app/routes/posts.py` — Post Routes

```
Router: APIRouter()

GET / → index(request) — full HTML page
GET /posts → list_posts(request, q, username, date_from, date_to, source, page) — HTML fragment
GET /posts/load-more → load_more(request, ...) — cards-only HTML fragment
GET /api/posts → api_list_posts(...) — JSON
```

### 2.5 `app/routes/sync.py` — Sync Routes

```
Router: APIRouter()
Module state: _sync_lock, _sync_in_progress

POST /sync → trigger_sync(request, source_type="both") — HTML fragment + HX-Trigger header
GET /sync/status → sync_status(request) — HTML fragment
GET /api/sync/status → api_sync_status() — JSON
async def _run_xurl_sync(xurl_cmd) -> tuple[int, int]
```

### 2.6 `app/main.py` — Application Entry Point

```python
@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield
    await close_db()

app = FastAPI(title="xarchive", lifespan=lifespan)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(posts.router)
app.include_router(sync.router)
```

### 2.7 Templates

- `base.html` — HTML shell with Tailwind + HTMX CDN, header/content/scripts blocks
- `index.html` — extends base, search bar + post list with HTMX auto-load
- `partials/post_card.html` — single post card (avatar, name, text, media, source badge)
- `partials/post_list.html` — result count + cards loop + load-more button
- `partials/post_cards_only.html` — cards + load-more for append pagination
- `partials/search_bar.html` — search form with HTMX
- `partials/sync_button.html` — sync button with idle/running/success/error states

---

## 3. Data Flow

### Initial Page Load
```
GET / → FastAPI renders index.html → HTMX sees hx-get="/posts" hx-trigger="load"
→ GET /posts → search_posts(page=1) → HTML fragment with cards
```

### Search Flow
```
Form submit → HTMX GET /posts?q=python&username=... → search_posts with filters → HTML fragment swapped into #post-list
```

### Load More (Pagination)
```
Click "Load more" → HTMX GET /posts/load-more?page=2 → post_cards_only.html → hx-swap="beforeend" into #post-cards
```

### Sync Flow
```
POST /sync → asyncio.create_subprocess_exec("xurl", "likes") → upsert_posts → HX-Trigger: postsChanged → post list auto-refreshes
```

---

## 4. Sync Process — Detailed Design

### Subprocess Lifecycle
```
trigger_sync()
    if _sync_in_progress → return error
    _sync_in_progress = True
    for src in ["likes", "bookmarks"]:
        log_id = create_sync_log(src)
        try:
            new, updated = _run_xurl_sync(src)
            update_sync_log(log_id, "success", new, updated)
        except:
            update_sync_log(log_id, "error", error_message=str(e))
    _sync_in_progress = False
    return sync_button partial + HX-Trigger: postsChanged
```

### Error Classification
| Exception | User message |
|-----------|--------------|
| FileNotFoundError | "xurl CLI not found. Install it first." |
| asyncio.TimeoutError | "Sync timed out after 120s. Try again." |
| RuntimeError (non-zero exit) | "Sync failed: {stderr_summary}" |
| json.JSONDecodeError | "Sync failed: unexpected response from xurl." |
| pydantic.ValidationError | Skip item, log warning |
| aiosqlite.Error | "Sync failed: database error." |

---

## 5. Search & Pagination

### SQL Query Builder Pattern
```
conditions = ["1=1"]
if q: "posts.text LIKE ?" → f"%{q}%"
if username: "posts.author_username LIKE ?" → f"%{username}%"
if date_from: "posts.created_at >= ?" → f"{date_from}T00:00:00Z"
if date_to: "posts.created_at <= ?" → f"{date_to}T23:59:59Z"
if source != "all": "source LIKE ?" → f"%{source}%"
WHERE = " AND ".join(conditions)
COUNT → SELECT COUNT(*) FROM posts WHERE {WHERE}
DATA → SELECT * FROM posts WHERE {WHERE} ORDER BY created_at DESC LIMIT ? OFFSET ?
```

### Pagination
```
OFFSET = (page - 1) * per_page
Two endpoints: GET /posts (replace), GET /posts/load-more (append)
```

---

## 6. File Tree (Complete)

```
xarchive/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── posts.py
│   │   └── sync.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   └── partials/
│   │       ├── post_card.html
│   │       ├── post_list.html
│   │       ├── post_cards_only.html
│   │       ├── search_bar.html
│   │       └── sync_button.html
│   └── static/
│       └── css/
│           └── custom.css
├── data/
│   └── xarchive.db
├── tests/
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_models.py
│   ├── test_routes/
│   │   ├── __init__.py
│   │   ├── test_posts.py
│   │   └── test_sync.py
│   └── e2e/
│       ├── conftest.py
│       └── test_sync_flow.py
├── docs/
│   ├── spec/
│   │   └── xarchive-mvp.md
│   ├── design/
│   │   └── xarchive-mvp.md
│   └── adr/
├── .gitignore
├── pyproject.toml
├── AGENTS.md
├── devloop-prompt.md
└── README.md
```

---

## 7. Task Breakdown

### Task 1: Project scaffolding and configuration [Backend]

**Descripción:** Create the project skeleton: `pyproject.toml` with dependencies, `.gitignore`, `app/__init__.py`, `app/config.py` with all constants, and empty placeholder files for all modules.

**Archivos a crear:**
- `pyproject.toml` — project metadata, dependencies (fastapi, uvicorn[standard], aiosqlite, jinja2, python-multipart, httpx, pytest, pytest-asyncio, pytest-playwright), scripts section with `dev` and `test` commands
- `.gitignore` — ignore `data/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `data/xarchive.db`
- `app/__init__.py` — empty file
- `app/config.py` — module with constants: `DB_PATH = Path("data/xarchive.db")`, `PAGE_SIZE = 20`, `XURL_COMMAND = "xurl"`, `SYNC_TIMEOUT_SECONDS = 120`, `HOST = "127.0.0.1"`, `PORT = 8000`
- `app/routes/__init__.py` — empty file
- `README.md` — quick start, commands, project description

**Criterios de aceptación:**
- [ ] `pip install -e .` completes without errors
- [ ] `from app.config import DB_PATH, PAGE_SIZE` works in Python REPL
- [ ] `DB_PATH` is a `pathlib.Path` object
- [ ] `data/` directory is listed in `.gitignore`
- [ ] `pyproject.toml` declares all 7+ dependencies

**Tipo:** Backend
**Dependencias:** Ninguna
**Tamaño estimado:** S (3-4 archivos)

---

### Task 2: Database schema and migrations [Backend]

**Descripción:** Implement `app/db.py` with connection management (`init_db`, `close_db`, `get_db`) and schema migration.

**Archivos a crear:**
- `app/db.py` — functions: `init_db()`, `close_db()`, `get_db()`, module-level `_db` variable, `_MIGRATIONS` list with CREATE TABLE and CREATE INDEX statements

**Criterios de aceptación:**
- [ ] After `await init_db()`, `data/xarchive.db` file exists
- [ ] `posts` table has exactly 11 columns
- [ ] `sync_log` table has exactly 8 columns
- [ ] Three indexes exist
- [ ] Calling `init_db()` twice does not fail

**Tipo:** Backend
**Dependencias:** Task 1 (config.py for DB_PATH)

---

### Task 3: Pydantic models [Backend]

**Descripción:** Create `app/models.py` with three Pydantic models: `XurlPostInput`, `Post`, `SyncLog`.

**Archivos a crear:**
- `app/models.py` — classes: `XurlPostInput`, `Post`, `SyncLog`

**Criterios de aceptación:**
- [ ] `XurlPostInput.model_validate({...valid data...})` succeeds
- [ ] Missing fields raise ValidationError
- [ ] `Post(source="like").is_like == True`
- [ ] `Post(source="like,bookmark").is_like == True` and `is_bookmark == True`

**Tipo:** Backend
**Dependencias:** Ninguna

---

### Task 4: Database CRUD helpers [Backend]

**Descripción:** Add all CRUD functions to `app/db.py`: `upsert_post`, `get_posts`, `search_posts`, `create_sync_log`, `update_sync_log`, `get_last_sync_log`, `row_to_post_dict`.

**Archivos a modificar:**
- `app/db.py` — add CRUD functions

**Criterios de aceptación:**
- [ ] `upsert_post` with new post → returns "new"
- [ ] `upsert_post` with same id, different source → source merged to "like,bookmark"
- [ ] `get_posts(page=1)` returns posts ordered by `created_at DESC`
- [ ] `search_posts(q="python")` returns only posts with "python" in text
- [ ] All queries use parameterized `?` — no string interpolation
- [ ] `row_to_post_dict` parses `media_urls` from JSON string to list

**Tipo:** Backend
**Dependencias:** Task 2 (schema), Task 3 (models)

---

### Task 5: Posts routes [Backend]

**Descripción:** Implement `app/routes/posts.py` with four route handlers: `index` (GET /), `list_posts` (GET /posts), `load_more` (GET /posts/load-more), `api_list_posts` (GET /api/posts).

**Archivos a crear:**
- `app/routes/posts.py` — APIRouter with 4 GET handlers
**Archivos a modificar:**
- `app/main.py` — include posts router

**Criterios de aceptación:**
- [ ] `GET /` returns 200 with HTML containing `<html>` and HTMX CDN script tag
- [ ] `GET /posts` returns 200 with HTML fragment
- [ ] `GET /api/posts` returns valid JSON
- [ ] Empty database returns 200 with empty post list

**Tipo:** Backend
**Dependencias:** Task 4 (db helpers), Task 7 (templates)

---

### Task 6: Sync routes and xurl subprocess [Backend]

**Descripción:** Implement `app/routes/sync.py` with sync trigger, status polling, and `_run_xurl_sync` helper.

**Archivos a crear:**
- `app/routes/sync.py` — APIRouter with POST /sync, GET /sync/status, GET /api/sync/status
**Archivos a modificar:**
- `app/main.py` — include sync router

**Criterios de aceptación:**
- [ ] `POST /sync` with mocked subprocess inserts posts into DB
- [ ] Re-running sync produces no duplicates (idempotent)
- [ ] FileNotFoundError → "xurl CLI not found"
- [ ] Successful sync response includes `HX-Trigger: postsChanged`

**Tipo:** Backend
**Dependencias:** Task 4 (db helpers), Task 3 (models)

---

### Task 7: Base template and styling [Frontend]

**Descripción:** Create `base.html` (HTML shell) and `custom.css`.

**Archivos a crear:**
- `app/templates/base.html` — HTML5 shell with Tailwind + HTMX CDN, header/content/scripts blocks
- `app/static/css/custom.css` — skeleton loading animation, .htmx-indicator

**Criterios de aceptación:**
- [ ] `base.html` contains Tailwind and HTMX CDN scripts
- [ ] `base.html` defines blocks: header, content, scripts

**Tipo:** Frontend
**Dependencias:** Ninguna

---

### Task 8: Index page and post cards [Frontend]

**Descripción:** Create `index.html`, `post_card.html`, `post_list.html`, `post_cards_only.html`.

**Archivos a crear:**
- `app/templates/index.html`
- `app/templates/partials/post_card.html`
- `app/templates/partials/post_list.html`
- `app/templates/partials/post_cards_only.html`

**Criterios de aceptación:**
- [ ] `index.html` renders without errors
- [ ] Post card displays source badge with correct color
- [ ] "Load more" uses `hx-swap="beforeend"` and `hx-target="#post-cards"`
- [ ] Empty post list shows friendly message

**Tipo:** Frontend
**Dependencias:** Task 7 (base.html)

---

### Task 9: Search UI and HTMX integration [Frontend]

**Descripción:** Create `search_bar.html` partial with HTMX search form.

**Archivos a crear:**
- `app/templates/partials/search_bar.html`

**Criterios de aceptación:**
- [ ] Search form has inputs for: q, username, date_from, date_to, source
- [ ] Typing triggers HTMX request after 300ms debounce
- [ ] Clear button resets all fields
- [ ] `hx-push-url="true"` updates browser URL

**Tipo:** Frontend
**Dependencias:** Task 7 (base.html), Task 8 (post_list.html)

---

### Task 10: Sync button UI and feedback [Frontend]

**Descripción:** Create `sync_button.html` partial with states.

**Archivos a crear:**
- `app/templates/partials/sync_button.html`

**Criterios de aceptación:**
- [ ] Idle: blue "⟳ Sync" button with dropdown
- [ ] Running: spinner + disabled
- [ ] Success: green "✓ Synced N new, M updated"
- [ ] Error: red message

**Tipo:** Frontend
**Dependencias:** Task 7 (base.html)

---

### Task 11: FastAPI app wiring and lifespan [Backend]

**Descripción:** Complete `app/main.py` with FastAPI app, lifespan, template/static mounts, router includes.

**Archivos a modificar:**
- `app/main.py` — full implementation

**Criterios de aceptación:**
- [ ] `uvicorn app.main:app` starts without errors
- [ ] `GET /` returns 200 HTML response
- [ ] Database initialized on startup

**Tipo:** Backend
**Dependencias:** Task 2 (db), Task 5 (posts routes), Task 6 (sync routes)

---

### Task 12: Test fixtures and database tests [Backend]

**Descripción:** Create test fixtures and db unit tests.

**Archivos a crear:**
- `tests/__init__.py`, `tests/conftest.py`, `tests/test_db.py`

**Criterios de aceptación:**
- [ ] `pytest tests/test_db.py` passes
- [ ] Test DB created in temp directory
- [ ] Tests cover: upsert, pagination, search, sync_log

**Tipo:** Backend
**Dependencias:** Task 4 (db helpers), Task 1 (scaffolding)

---

### Task 13: Route integration tests [Backend]

**Descripción:** Create integration tests for post and sync routes.

**Archivos a crear:**
- `tests/test_routes/__init__.py`, `tests/test_routes/test_posts.py`, `tests/test_routes/test_sync.py`

**Criterios de aceptación:**
- [ ] `pytest tests/test_routes/` passes
- [ ] Tests cover: GET /, GET /posts, POST /sync, error cases

**Tipo:** Backend
**Dependencias:** Task 5 (posts routes), Task 6 (sync routes), Task 12 (test fixtures)

---

### Task 14: End-to-end integration verification [Ambos]

**Descripción:** Wire everything together, run dev server, verify all user stories.

**Criterios de aceptación:**
- [ ] `uvicorn app.main:app --reload` starts
- [ ] Full sync → view → search flow works
- [ ] `pytest` exits 0

**Tipo:** Ambos
**Dependencias:** Tasks 1-13 (all previous tasks)

---

### Dependency Graph (Task Order)

```
Task 1 (scaffolding)
    ├── Task 2 (DB schema) → Task 4 (CRUD helpers)
    │       ├── Task 5 (posts routes) ──────┐
    │       ├── Task 6 (sync routes) ───────┤
    │       └── Task 12 (DB tests)          │
    ├── Task 3 (models) → Task 4            │
    ├── Task 7 (base template)              │
    │       ├── Task 8 (index + cards) ─────┤
    │       │       └── Task 9 (search UI)  │
    │       └── Task 10 (sync button) ──────┤
    │                                       ▼
    │                            Task 11 (app wiring)
    │                                       │
    │                            Task 13 (route tests)
    │                                       │
    │                            Task 14 (E2E integration)
```

**Parallelization opportunities:**
- Tasks 2, 3, 7 can run in parallel
- Tasks 8, 9, 10 can run in parallel after Task 7
- Tasks 5, 6 can run in parallel after Task 4
- Task 12 can start after Task 4

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| xurl JSON format differs | High — sync breaks | XurlPostInput model validates; add adapter if needed |
| Large collections (10k+) | Medium — timeout | SYNC_TIMEOUT_SECONDS = 120 |
| SQLite concurrent access | Low — reads block | aiosqlite serializes; single-user app |
| HTMX version breakage | Low | Pin version in CDN URL |
| Tailwind CDN unavailable | Medium — unstyled | MVP requires CDN; future: vendor CSS |
