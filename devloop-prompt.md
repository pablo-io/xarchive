# Prompt para /devloop — xarchive MVP

```
/devloop xarchive: cliente web que sincroniza likes y bookmarks de X.com via xurl CLI a SQLite local y los muestra con FastAPI + HTMX
```

## Stack

- Backend: **FastAPI** + **uvicorn** (dev server)
- DB: **SQLite** + **aiosqlite** (async, raw SQL, sin ORM)
- Frontend: **Jinja2** + **HTMX** + **Tailwind CSS** (CDN, sin build step)
- Data source: **xurl CLI** (oficial X API v2) — comandos `xurl likes` y `xurl bookmarks`
- Tests: **pytest** + **pytest-asyncio** + **pytest-playwright**
- Auth: xurl OAuth 2.0 PKCE (la app web no maneja auth)

## Reglas de negocio

1. **No consultar el timeline** — solo sincronizar likes y bookmarks
2. Los likes y bookmarks se pueden consultar pero directo de la base de datos, no de x.com
3. La DB está en `data/xarchive.db` (gitignored)
4. Cada post guarda: id, text, author_id, author_username, author_name, author_avatar, created_at, source (like|bookmark), media_urls (JSON array), url, imported_at
5. Es posible buscar por texto, username o fecha
6. Sincronización debe hacerse desde la interfaz web de forma manual
7. La vista web no necesita login es solo un visor local
8. La UI debe verse moderna y profesional
