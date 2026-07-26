# Spec: xarchive MVP

## 1. Objective

**What we're building:** A local-only web application that synchronizes a user's X.com (Twitter) likes and bookmarks into a local SQLite database via the `xurl` CLI, and presents them in a searchable, modern web interface.

**Why:** X.com provides no native way to browse, search, or archive your own likes and bookmarks effectively. xarchive gives the user a permanent, searchable, offline-capable local archive of the posts they've liked or bookmarked.

**Who is the user:** A single local user (the developer). No multi-user support, no authentication, no network exposure.

**What success looks like:**
- The user can view all their synced likes and bookmarks in a clean, responsive card-based UI
- The user can search across all posts by text content, author username, or date range
- The user can trigger a manual sync from the web UI that fetches the latest likes/bookmarks from X.com via `xurl`
- The entire system runs locally with zero external dependencies beyond the `xurl` CLI and Python

---

## 2. Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend framework | **FastAPI** + **uvicorn** | Async Python. No alternative async framework. |
| Database | **SQLite** via **aiosqlite** | Raw SQL only. No ORM. |
| Templating | **Jinja2** | Server-side rendering via FastAPI's `HTMLResponse`. |
| Interactivity | **HTMX** | No custom JavaScript beyond HTMX. Loaded via CDN. |
| Styling | **Tailwind CSS** | Loaded via CDN (`<script src="https://cdn.tailwindcss.com">`). No build step. |
| Data source | **xurl CLI** | `xurl likes` and `xurl bookmarks`. Outputs JSON from official X API v2. |
| Test runner | **pytest** + **pytest-asyncio** | Unit and integration tests for backend. |
| E2E tests | **pytest-playwright** | Browser-level tests for critical flows. |
| Auth | **None** | xurl handles OAuth 2.0 PKCE externally. The web app is an unauthenticated local viewer. |

### Dependency list (for `pyproject.toml`)

```
fastapi
uvicorn[standard]
aiosqlite
jinja2
python-multipart        # for form data in HTMX requests
httpx                   # for TestClient in tests

# dev/test
pytest
pytest-asyncio
pytest-playwright
```

---

## 3. Commands

| Command | Purpose |
|---------|---------|
| `uvicorn app.main:app --reload` | Start development server with hot reload |
| `pytest` | Run all tests (unit + integration) |
| `pytest tests/e2e/` | Run E2E browser tests only |
| `pytest --cov=app --cov-report=term-missing` | Run tests with coverage report |

---

## 4. Project Structure

```
xarchive/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app factory, middleware, static/template mounts
│   ├── config.py            # Settings: DB path, constants
│   ├── db.py                # aiosqlite connection pool, raw SQL helpers, migrations
│   ├── models.py            # Pydantic models / dataclasses for Post, SyncResult
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── posts.py         # GET /, GET /posts (list, search, paginate)
│   │   └── sync.py          # POST /sync (trigger), GET /sync/status (poll)
│   ├── templates/
│   │   ├── base.html        # HTML shell: <head> with Tailwind+HTMX CDN, nav, footer
│   │   ├── index.html       # Main page: search bar + sync button + post list container
│   │   └── partials/
│   │       ├── post_card.html    # Single post card (author avatar, text, media, metadata)
│   │       ├── post_list.html    # List of post_cards + "Load more" pagination
│   │       ├── search_bar.html   # Search form (text, username, date range)
│   │       └── sync_button.html  # Sync button with loading/success/error states
│   └── static/
│       └── css/
│           └── custom.css   # Minimal custom styles beyond Tailwind utilities
├── data/                    # gitignored — local SQLite database
│   └── xarchive.db
├── tests/
│   ├── conftest.py          # Fixtures: test DB, test client, sample data
│   ├── test_db.py           # Tests for db.py helpers
│   ├── test_models.py       # Tests for model validation
│   ├── test_routes/
│   │   ├── test_posts.py    # Tests for post listing, search, pagination
│   │   └── test_sync.py     # Tests for sync flow (with mocked subprocess)
│   └── e2e/
│       ├── conftest.py      # Playwright fixtures
│       └── test_sync_flow.py  # Full sync → view → search flow in browser
├── docs/
│   ├── spec/
│   ├── design/
│   └── adr/
├── .gitignore
├── pyproject.toml
├── AGENTS.md
└── README.md
```

---

## 5. Business Rules

These rules are **invariants** — they must hold in every code path and must never be violated by any feature addition.

| # | Rule | Enforcement |
|---|------|-------------|
| BR-1 | **Never query the X timeline.** Only sync likes and bookmarks. | No route or function calls `xurl` with any command other than `likes` or `bookmarks`. |
| BR-2 | **Read posts from SQLite only.** The web UI never fetches data from X.com directly. | All GET routes query the local database. No route imports or calls the X API. |
| BR-3 | **Database lives at `data/xarchive.db`.** | Path is defined in `app/config.py` and used everywhere. `data/` is gitignored. |
| BR-4 | **Each post stores exactly these fields:** `id`, `text`, `author_id`, `author_username`, `author_name`, `author_avatar`, `created_at`, `source`, `media_urls`, `url`, `imported_at`. | Schema in `db.py` migration matches this exactly. No extra columns, no missing columns. |
| BR-5 | **Search by text, username, or date.** | Search route supports all three parameters. At least one must be provided for a search query. |
| BR-6 | **Sync is manual from the web UI.** | No cron jobs, no background schedulers, no automatic sync. Sync only runs when the user clicks the button. |
| BR-7 | **No authentication.** | No auth middleware, no login routes, no session management. The app binds to localhost only. |
| BR-8 | **UI must look modern and professional.** | Tailwind CSS with a consistent design system. Card-based layout. Responsive on mobile and desktop. |

---

## 6. User Stories

### US-1: View all imported posts
**As a** user,
**I want to** see all my synced likes and bookmarks on the main page,
**so that** I can browse my archived posts in a clean layout.

**Acceptance criteria:**
- [ ] Main page (`GET /`) renders a list of post cards
- [ ] Each card displays: author avatar, author name (@username), post text, post date, source badge (like/bookmark), media thumbnails if present, and a link to the original post
- [ ] Posts are ordered by `created_at` descending (newest first) by default
- [ ] Posts are paginated — 20 posts per page with a "Load more" button that uses HTMX to append the next page
- [ ] Source badge visually distinguishes likes from bookmarks (e.g., different color or icon)
- [ ] Empty state: when no posts exist, show a friendly message prompting the user to sync

### US-2: Search posts
**As a** user,
**I want to** search my posts by text content, author username, or date range,
**so that** I can find specific posts in my archive.

**Acceptance criteria:**
- [ ] Search bar is visible on the main page at the top
- [ ] Text search: matches against post `text` field (case-insensitive `LIKE %query%`)
- [ ] Username search: matches against `author_username` field (case-insensitive exact match or `LIKE`)
- [ ] Date search: filter by `created_at` with optional `from` and `to` date inputs
- [ ] Search can be combined: text + username + date range all applied simultaneously
- [ ] Search results replace the post list via HTMX (no full page reload)
- [ ] Clear/reset button to remove all filters and return to the full list
- [ ] Result count is displayed (e.g., "42 results for 'python'")
- [ ] Empty results show a "No posts found" message

### US-3: Manual sync
**As a** user,
**I want to** trigger a sync of my likes and/or bookmarks from the web UI,
**so that** my local archive stays up to date with X.com.

**Acceptance criteria:**
- [ ] Sync button is visible in the navigation/header area
- [ ] Clicking sync calls `POST /sync` which runs `xurl likes` and/or `xurl bookmarks`
- [ ] During sync: button shows a loading spinner and is disabled (prevents double-click)
- [ ] On success: button shows a success message with count of new/updated posts (e.g., "Synced 15 new posts")
- [ ] On error: button shows an error message (e.g., "Sync failed: xurl not found" or "Sync failed: auth expired")
- [ ] After successful sync, the post list automatically refreshes to show new content
- [ ] Sync is idempotent: running it twice with no new posts produces zero changes
- [ ] Sync uses upsert: if a post already exists, update it rather than creating a duplicate

### US-4: Modern responsive UI
**As a** user,
**I want** the interface to look professional and work well on any screen size,
**so that** I enjoy using the application.

**Acceptance criteria:**
- [ ] Layout is responsive: works on mobile (320px+), tablet, and desktop
- [ ] Post cards have consistent spacing, rounded corners, subtle shadows
- [ ] Typography uses a clean sans-serif font (Tailwind default)
- [ ] Color palette is cohesive — dark text on light background, accent color for interactive elements
- [ ] Author avatar is displayed as a rounded image (40x40px)
- [ ] Media thumbnails are displayed in a grid below the post text (if media exists)
- [ ] Navigation/header is sticky at the top
- [ ] No horizontal scrolling at any viewport width
- [ ] Loading states use skeleton screens or spinners (not blank spaces)

---

## 7. Data Model

### Table: `posts`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | X.com post ID (snowflake ID, stored as text) |
| `text` | TEXT | NOT NULL | Full text content of the post |
| `author_id` | TEXT | NOT NULL | X.com user ID of the post author |
| `author_username` | TEXT | NOT NULL | @handle of the post author (without @) |
| `author_name` | TEXT | NOT NULL | Display name of the post author |
| `author_avatar` | TEXT | NOT NULL | URL to the author's profile image |
| `created_at` | TEXT | NOT NULL | ISO 8601 timestamp of when the post was created on X.com |
| `source` | TEXT | NOT NULL | `"like"`, `"bookmark"`, or `"like,bookmark"` if both |
| `media_urls` | TEXT | NOT NULL DEFAULT `'[]'` | JSON array of media URLs (images, videos) attached to the post |
| `url` | TEXT | NOT NULL | Canonical URL to the post on X.com (e.g., `https://x.com/user/status/123`) |
| `imported_at` | TEXT | NOT NULL | ISO 8601 timestamp of when the post was last imported/updated |

**Indexes:**
- `idx_posts_created_at` ON `posts(created_at DESC)` — default sort order
- `idx_posts_author_username` ON `posts(author_username)` — username search
- `idx_posts_source` ON `posts(source)` — filter by source

**Design decisions:**
- `id` is TEXT because X.com snowflake IDs exceed SQLite's INTEGER range
- `created_at` and `imported_at` are TEXT in ISO 8601 format for consistent sorting and parsing
- `media_urls` is stored as a JSON-encoded TEXT array (parsed in Python, not in SQL)
- `source` can be `"like,bookmark"` when a post appears in both collections — this avoids duplicate rows while preserving provenance
- Upsert strategy: `INSERT OR REPLACE` on `id` — if a post is re-synced, all fields are refreshed and `source` is merged (if existing source is `"like"` and new sync finds it in bookmarks, update to `"like,bookmark"`)

### Table: `sync_log`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Sequential log ID |
| `source_type` | TEXT | NOT NULL | `"likes"` or `"bookmarks"` — what was synced |
| `started_at` | TEXT | NOT NULL | ISO 8601 timestamp when sync started |
| `finished_at` | TEXT | NULL | ISO 8601 timestamp when sync completed (NULL if in progress) |
| `status` | TEXT | NOT NULL DEFAULT `'running'` | `"running"`, `"success"`, or `"error"` |
| `posts_new` | INTEGER | NOT NULL DEFAULT `0` | Count of newly inserted posts |
| `posts_updated` | INTEGER | NOT NULL DEFAULT `0` | Count of updated posts |
| `error_message` | TEXT | NULL | Error details if `status = 'error'` |

**Purpose:** Tracks sync history for debugging and lets the UI show when the last sync occurred.

---

## 8. Route Design

### HTML Routes (serve Jinja2 templates)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `GET` | `/` | `routes.posts.index` | Main page — renders `index.html` with initial post list, search bar, and sync button |

### HTMX Partial Routes (return HTML fragments)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `GET` | `/posts` | `routes.posts.list_posts` | Returns paginated, searchable post list as HTML fragment. Query params: `q` (text), `username`, `date_from`, `date_to`, `source` (like/bookmark/all), `page` (int, default 1). Used for initial load and search/filter. |
| `GET` | `/posts/load-more` | `routes.posts.load_more` | Returns next page of posts as HTML fragment (no search bar wrapper). Query params: same as `/posts` plus `page`. Appended to existing list via HTMX `hx-swap="beforeend"`. |

### Action Routes (HTMX POST endpoints)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `POST` | `/sync` | `routes.sync.trigger_sync` | Triggers sync. Form param: `source_type` (`"likes"`, `"bookmarks"`, or `"both"`). Spawns `xurl` subprocess, processes results into DB, returns updated sync button HTML with result message. |
| `GET` | `/sync/status` | `routes.sync.sync_status` | Returns current sync status as HTML fragment. Used for polling during long syncs. Returns the sync button partial with current state (idle/running/success/error). |

### API Routes (JSON — for programmatic access, optional)

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `GET` | `/api/posts` | `routes.posts.api_list_posts` | JSON API returning posts. Same query params as `/posts`. Returns `{ posts: [...], total: int, page: int, per_page: int }`. |
| `GET` | `/api/sync/status` | `routes.sync.api_sync_status` | JSON endpoint returning last sync info: `{ status, started_at, finished_at, posts_new, posts_updated, error_message }`. |

### Route detail: `GET /posts`

**Query parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | `""` | Text search — matches against `posts.text` (case-insensitive LIKE) |
| `username` | string | `""` | Username filter — matches against `posts.author_username` (case-insensitive) |
| `date_from` | string (YYYY-MM-DD) | `""` | Start of date range (inclusive) |
| `date_to` | string (YYYY-MM-DD) | `""` | End of date range (inclusive) |
| `source` | string | `"all"` | Filter by source: `"like"`, `"bookmark"`, or `"all"` |
| `page` | int | `1` | Page number for pagination |

**Response:** HTML fragment containing `post_list.html` partial with post cards and pagination controls.

### Route detail: `POST /sync`

**Form parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `source_type` | string | `"both"` | What to sync: `"likes"`, `"bookmarks"`, or `"both"` |

**Behavior:**
1. Insert a row into `sync_log` with `status = 'running'`
2. For each source type, spawn subprocess: `xurl likes` or `xurl bookmarks`
3. Parse JSON stdout from xurl
4. For each post in the output, upsert into `posts` table (merge source if needed)
5. Update `sync_log` row with `status = 'success'`, counts, and `finished_at`
6. On any error: update `sync_log` with `status = 'error'` and `error_message`
7. Return rendered `sync_button.html` partial showing result

**Response:** HTML fragment (`sync_button.html`) with success/error state and post count.

---

## 9. Sync Flow

### Sequence diagram

```
User            Browser (HTMX)         FastAPI              SQLite            xurl CLI          X.com API
 │                  │                     │                    │                  │                  │
 │  Click "Sync"    │                     │                    │                  │                  │
 │─────────────────>│                     │                    │                  │                  │
 │                  │  POST /sync         │                    │                  │                  │
 │                  │  source_type=both   │                    │                  │                  │
 │                  │────────────────────>│                    │                  │                  │
 │                  │                     │  INSERT sync_log   │                  │                  │
 │                  │                     │  (status=running)  │                  │                  │
 │                  │                     │───────────────────>│                  │                  │
 │                  │                     │                    │                  │                  │
 │                  │                     │  subprocess:       │                  │                  │
 │                  │                     │  `xurl likes`      │                  │                  │
 │                  │                     │───────────────────────────────────────>│  HTTP request    │
 │                  │                     │                    │                  │─────────────────>│
 │                  │                     │                    │                  │  JSON response   │
 │                  │                     │                    │                  │<─────────────────│
 │                  │                     │  JSON stdout       │                  │                  │
 │                  │                     │<───────────────────────────────────────│                  │
 │                  │                     │                    │                  │                  │
 │                  │                     │  For each post:    │                  │                  │
 │                  │                     │  INSERT OR REPLACE │                  │                  │
 │                  │                     │  + merge source    │                  │                  │
 │                  │                     │───────────────────>│                  │                  │
 │                  │                     │                    │                  │                  │
 │                  │                     │  (repeat for `xurl bookmarks`)        │                  │
 │                  │                     │───────────────────────────────────────>│  ...             │
 │                  │                     │<───────────────────────────────────────│                  │
 │                  │                     │                    │                  │                  │
 │                  │                     │  UPDATE sync_log   │                  │                  │
 │                  │                     │  (status=success)  │                  │                  │
 │                  │                     │───────────────────>│                  │                  │
 │                  │                     │                    │                  │                  │
 │                  │  HTML fragment      │                    │                  │                  │
 │                  │  (sync_button.html  │                    │                  │                  │
 │                  │   with result)      │                    │                  │                  │
 │                  │<────────────────────│                    │                  │                  │
 │  See "Synced     │                     │                    │                  │                  │
 │  23 new posts"   │                     │                    │                  │                  │
 │<─────────────────│                     │                    │                  │                  │
 │                  │                     │                    │                  │                  │
 │                  │  GET /posts         │  (auto-refresh     │                  │                  │
 │                  │  (triggered by      │   post list)       │                  │                  │
 │                  │   hx-trigger)       │                    │                  │                  │
 │                  │────────────────────>│  SELECT posts...   │                  │                  │
 │                  │                     │───────────────────>│                  │                  │
 │                  │  HTML fragment      │                    │                  │                  │
 │                  │<────────────────────│                    │                  │                  │
```

### Sync implementation details

**Subprocess invocation:**
```python
# Pseudocode for app/routes/sync.py
process = await asyncio.create_subprocess_exec(
    "xurl", "likes",                    # or "bookmarks"
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
)
stdout, stderr = await process.communicate()
```

**xurl output format (expected):**
The `xurl likes` and `xurl bookmarks` commands output JSON to stdout. Expected structure:
```json
[
  {
    "id": "1234567890",
    "text": "Post content here...",
    "author_id": "9876543210",
    "author_username": "someuser",
    "author_name": "Some User",
    "author_avatar": "https://pbs.twimg.com/profile_images/...",
    "created_at": "2025-01-15T10:30:00Z",
    "media_urls": ["https://pbs.twimg.com/media/...jpg"],
    "url": "https://x.com/someuser/status/1234567890"
  }
]
```

> **Open question:** Confirm exact field names and structure of `xurl` JSON output. The field mapping may need adjustment.

**Upsert logic:**
```sql
INSERT INTO posts (id, text, author_id, author_username, author_name,
                   author_avatar, created_at, source, media_urls, url, imported_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    text = excluded.text,
    author_id = excluded.author_id,
    author_username = excluded.author_username,
    author_name = excluded.author_name,
    author_avatar = excluded.author_avatar,
    created_at = excluded.created_at,
    source = CASE
        WHEN posts.source = 'like' AND excluded.source = 'bookmark' THEN 'like,bookmark'
        WHEN posts.source = 'bookmark' AND excluded.source = 'like' THEN 'like,bookmark'
        ELSE excluded.source
    END,
    media_urls = excluded.media_urls,
    url = excluded.url,
    imported_at = excluded.imported_at;
```

**Error handling:**
| Error | Detection | User message |
|-------|-----------|--------------|
| `xurl` not installed | `FileNotFoundError` from subprocess | "Sync failed: xurl CLI not found. Install it first." |
| xurl auth expired | Non-zero exit code + stderr contains auth/error keywords | "Sync failed: xurl authentication expired. Run `xurl auth` to re-authenticate." |
| xurl network error | Non-zero exit code + stderr contains network/timeout keywords | "Sync failed: network error. Check your connection and try again." |
| Unexpected xurl output | JSON parse error | "Sync failed: unexpected response from xurl." |
| Database error | `aiosqlite.Error` | "Sync failed: database error." |

---

## 10. UI Layout

### Page structure (`base.html`)

```
┌─────────────────────────────────────────────────────────┐
│  HEADER (sticky)                                        │
│  ┌─────────────────────────────────────────────────────┐│
│  │  📦 xarchive          [Search...]    [⟳ Sync]      ││
│  └─────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────┤
│  MAIN CONTENT                                           │
│  ┌─────────────────────────────────────────────────────┐│
│  │  SEARCH BAR (collapsible on mobile)                 ││
│  │  [Text...] [Username...] [From: 📅] [To: 📅]       ││
│  │  [Source: All ▾]  [Search] [Clear]                 ││
│  ├─────────────────────────────────────────────────────┤│
│  │  RESULT COUNT: "Showing 142 posts"                  ││
│  ├─────────────────────────────────────────────────────┤│
│  │                                                     ││
│  │  ┌─────────────────────────────────────────────┐   ││
│  │  │  POST CARD                                   │   ││
│  │  │  ┌──────┐  Some User  @someuser              │   ││
│  │  │  │avatar│  · Jan 15, 2025 · 🔖 bookmark      │   ││
│  │  │  └──────┘                                    │   ││
│  │  │                                              │   ││
│  │  │  Post text content goes here...               │   ││
│  │  │                                              │   ││
│  │  │  [media thumbnail] [media thumbnail]         │   ││
│  │  │                                              │   ││
│  │  │  🔗 Open original                            │   ││
│  │  └─────────────────────────────────────────────┘   ││
│  │                                                     ││
│  │  ┌─────────────────────────────────────────────┐   ││
│  │  │  POST CARD (next post...)                    │   ││
│  │  └─────────────────────────────────────────────┘   ││
│  │                                                     ││
│  │              [ Load more ↓ ]                        ││
│  │                                                     ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

### Responsive breakpoints
- **Mobile (< 640px):** Single column cards, stacked search fields, full-width layout
- **Tablet (640px – 1024px):** Single column cards, search fields in 2-column grid
- **Desktop (> 1024px):** Max-width container (1024px), search fields in a single row

### Design tokens (Tailwind config via CDN)
- Primary accent: `blue-600` (interactive elements, sync button)
- Like badge: `red-100` background, `red-700` text, heart icon
- Bookmark badge: `yellow-100` background, `yellow-700` text, bookmark icon
- Card background: `white` with `shadow-sm`, `rounded-xl`, `border border-gray-100`
- Page background: `gray-50`
- Text primary: `gray-900`, Text secondary: `gray-500`

---

## 11. Non-Goals

The following are **explicitly excluded** from the MVP. Do not implement these.

| Non-goal | Rationale |
|----------|-----------|
| ❌ Authentication / login | Local-only viewer. Binding to localhost is sufficient security. |
| ❌ Querying X.com timeline | Business rule BR-1. Only likes and bookmarks are in scope. |
| ❌ Automatic / scheduled sync | Business rule BR-6. Sync is manual only. |
| ❌ Build step for frontend | Tailwind and HTMX via CDN. No webpack, no Vite, no npm for frontend. |
| ❌ ORM (SQLAlchemy, etc.) | Raw SQL only per stack constraint. |
| ❌ Alternative async framework | FastAPI is the only backend framework. |
| ❌ Multi-user support | Single local user. No user accounts, no permissions. |
| ❌ Export functionality | No CSV/JSON/HTML export in MVP. |
| ❌ Post deletion from X.com | Read-only archive. No write-back to X.com. |
| ❌ Real-time / WebSocket updates | HTMX polling or manual refresh is sufficient. |
| ❌ Full-text search with FTS5 | LIKE queries are sufficient for MVP. FTS5 can be added later if needed. |
| ❌ Docker / containerization | Run directly with Python/uvicorn. |
| ❌ Background task queue (Celery, etc.) | Subprocess sync is fast enough. No async job system needed. |
| ❌ Caching layer | SQLite reads are fast. No Redis or in-memory cache needed. |

---

## 12. Testing Strategy

### Test levels

| Level | Framework | Location | What to test |
|-------|-----------|----------|--------------|
| Unit | pytest + pytest-asyncio | `tests/test_db.py`, `tests/test_models.py` | DB helpers (insert, upsert, search, paginate), model validation |
| Integration | pytest + pytest-asyncio + FastAPI TestClient | `tests/test_routes/` | Route handlers return correct HTML/JSON, search params work, sync flow with mocked subprocess |
| E2E | pytest-playwright | `tests/e2e/` | Full user flow: open page → sync → see posts → search → filter |

### Test fixtures (`tests/conftest.py`)
- `test_db`: Creates a temporary SQLite database, runs migrations, yields connection, cleans up
- `app_client`: FastAPI `TestClient` (or `httpx.AsyncClient`) wired to the test database
- `sample_posts`: Insert 10-20 sample posts into the test database for query tests
- `mock_xurl`: Fixture that patches `asyncio.create_subprocess_exec` to return canned JSON

### Coverage expectations
- `app/db.py`: ≥ 90% (critical data layer)
- `app/routes/`: ≥ 80% (all route paths, error cases)
- `app/models.py`: ≥ 90% (validation logic)
- Overall: ≥ 80%

---

## 13. Boundaries

### Always do
- Run `pytest` and ensure all tests pass before considering a task complete
- Follow the business rules (BR-1 through BR-8) without exception
- Use raw SQL for all database operations — no ORM
- Keep all frontend interactivity through HTMX — no custom JavaScript
- Load Tailwind CSS and HTMX from CDN — no local build step
- Store the database at `data/xarchive.db` — configurable only via `app/config.py`
- Handle all subprocess errors gracefully with user-friendly messages

### Ask first
- Adding any new Python dependency
- Changing the database schema (adding/removing columns)
- Modifying the `xurl` subprocess invocation (command, flags, output parsing)
- Changing the pagination page size
- Adding any client-side JavaScript beyond HTMX

### Never do
- Query the X.com timeline or any X.com endpoint other than likes/bookmarks via xurl
- Read post data from X.com directly — always from SQLite
- Add authentication, sessions, or user accounts
- Add a frontend build step (webpack, Vite, esbuild, etc.)
- Use an ORM (SQLAlchemy, Tortoise, etc.)
- Commit `data/xarchive.db` to git
- Store secrets, API keys, or tokens in the codebase
- Make sync automatic or scheduled

---

## 14. Success Criteria

The MVP is complete when all of the following are true:

| # | Criterion | Verification |
|---|-----------|--------------|
| SC-1 | `uvicorn app.main:app --reload` starts without errors | Manual: run command, see "Uvicorn running on http://127.0.0.1:8000" |
| SC-2 | `GET /` returns a valid HTML page with Tailwind and HTMX loaded | Manual: open browser, inspect `<head>` for CDN scripts |
| SC-3 | After syncing, posts appear as cards on the main page | Manual: click Sync, verify cards render with all fields |
| SC-4 | Text search filters posts correctly | Automated: test route with `q=python`, verify only matching posts returned |
| SC-5 | Username search filters posts correctly | Automated: test route with `username=someuser`, verify only that user's posts |
| SC-6 | Date range search filters posts correctly | Automated: test route with `date_from` and `date_to`, verify date filtering |
| SC-7 | Pagination works — "Load more" appends next page | Automated: test `/posts/load-more?page=2` returns different posts than page 1 |
| SC-8 | Sync calls xurl subprocess and populates the database | Automated: mock subprocess, verify posts inserted into test DB |
| SC-9 | Sync handles errors gracefully (xurl not found, auth expired) | Automated: mock subprocess failure, verify error message in response |
| SC-10 | Sync is idempotent — re-syncing produces no duplicates | Automated: sync twice, verify `SELECT COUNT(*) FROM posts` unchanged after second sync |
| SC-11 | UI is responsive — no horizontal scroll at 320px width | E2E: Playwright test at 320px viewport |
| SC-12 | All tests pass: `pytest` exits 0 | Automated: CI or manual |
| SC-13 | All 8 business rules are satisfied | Code review against BR-1 through BR-8 |

---

## 15. Open Questions

| # | Question | Impact | Default assumption |
|---|----------|--------|--------------------|
| OQ-1 | What is the exact JSON output format of `xurl likes` and `xurl bookmarks`? | Determines field mapping in the sync parser. | Assume output matches the field names in the data model (Section 7). |
| OQ-2 | Does `xurl` support pagination or does it return all likes/bookmarks in one call? | Affects sync duration and whether we need progress reporting. | Assume it returns all results in a single call. |
| OQ-3 | What is the maximum number of likes/bookmarks a user might have? | Affects pagination strategy and sync timeout considerations. | Assume up to ~10,000 posts. Design for this scale. |
| OQ-4 | Should the sync button offer separate "Sync likes" / "Sync bookmarks" options, or just one "Sync all" button? | Affects the sync UI and route design. | Assume a dropdown with three options: "Sync all", "Sync likes only", "Sync bookmarks only". |
| OQ-5 | Should posts that are both liked AND bookmarked show as a single card or two separate cards? | Affects data model and UI. | Assume single card with a combined badge (e.g., "❤️🔖 like, bookmark"). |

---

## 16. Glossary

| Term | Definition |
|------|-----------|
| **xurl** | CLI tool that authenticates with X.com via OAuth 2.0 PKCE and fetches data from the X API v2. |
| **Like** | A post the user has hearted/liked on X.com. |
| **Bookmark** | A post the user has saved to their X.com bookmarks. |
| **Source** | The origin of a post in the archive: `"like"`, `"bookmark"`, or `"like,bookmark"`. |
| **Sync** | The process of fetching the latest likes/bookmarks from X.com via xurl and storing them in the local SQLite database. |
| **Upsert** | Insert a row if it doesn't exist, or update it if it does (based on primary key). |
| **HTMX** | A library that allows HTML elements to trigger AJAX requests and update the DOM without writing JavaScript. |
| **Snowflake ID** | X.com's unique identifier format for posts — a large integer stored as TEXT in SQLite. |
