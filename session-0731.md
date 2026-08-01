# Session 0731 — Likes-only sync, incremental pagination, UI fixes

Fecha: 2026-07-31

## Resumen

En esta sesión se rehízo el flujo de sincronización de xarchive: se eliminó el soporte de
bookmarks (quedó solo likes), se reescribió el sync para usar la API raw de X con
paginación y persistencia de progreso ante rate limits, se añadió ordenación por fecha de
like, y se corrigieron varios bugs de la UI (duplicados en "Load more", contador,
linkify de URLs, header sin logo y botón de sync como icono).

Los cambios aquí descritos son de **código y base de datos**; no incluyen la
sincronización de datos (los 431 likes importados) ni las decisiones de datos tomadas
durante las pruebas.

---

## 1. Base de datos (`app/db.py`)

### Nuevas columnas

| Tabla | Columna | Tipo | Propósito |
|---|---|---|---|
| `posts` | `like_order` | `INTEGER NOT NULL DEFAULT 0` | Orden del like (más alto = más reciente). Se usa para listar por fecha de like en vez de `created_at`. |
| `sync_log` | `next_token` | `TEXT` | Token de paginación de la API X para retomar un sync cortado por rate limit. |
| `sync_log` | `like_order_mode` | `TEXT` | `'backfill'` o `'incremental'`, guardado junto al token para saber cómo asignar `like_order` al retomar. |

### Migración idempotente

- `_MIGRATIONS` ahora incluye las columnas nuevas en los `CREATE TABLE`.
- Se añadió `_ALTER_COLUMNS` (lista de `(tabla, columna, DDL)`) y `_ensure_column()`:
  consulta `PRAGMA table_info` y ejecuta el `ALTER TABLE ADD COLUMN` solo si la columna
  no existe. Esto permite migrar bases creadas antes de estas columnas.
- En `init_db()`, después de los `CREATE`, se ejecutan los `ALTER` y luego se crea el
  índice `idx_posts_like_order ON posts(like_order DESC)` (debe ir después del ALTER,
  porque el índice referencia la columna nueva).

### Ordenación

- `search_posts()` ordena ahora por `ORDER BY like_order DESC, created_at DESC` (antes
  solo `created_at DESC`). El listado muestra los likes más recientes primero, sin
  importar la fecha de creación del tweet.

### `upsert_post` simplificado

- Se eliminó la lógica de merging de fuentes (`bookmark,like`): el `ON CONFLICT` ahora
  simplemente hace `source = excluded.source`. Ya solo existe la fuente `'like'`.

### Búsqueda sin filtro de fuente

- `_build_post_query()`, `search_posts()` y `get_posts()` ya no aceptan el parámetro
  `source`. Se eliminó el filtro por fuente de las consultas.

### Nuevos helpers

- `delete_all_posts()` — borra todas las filas de `posts`.
- `delete_bookmark_posts()` — borra los posts cuyo `source` contiene `bookmark`
  (ya no se usa en el flujo, pero se dejó como utilidad).
- `get_sync_resume_state()` — devuelve `{'next_token', 'like_order_mode'}` del último
  sync `status != 'success'` que tenga token (o `None`).
- `save_sync_token(log_id, next_token, like_order_mode)` — persiste/limpia el token.
- `get_min_like_order()` / `get_max_like_order()` — mín/máx de `like_order` (0 si vacío).
- `set_post_like_order(post_id, like_order)` — fija el like_order de un post.
- `assign_like_orders(post_ids, base)` — asigna like_orders secuenciales (base, base-1,
  base-2, ...) a los posts nuevos, en orden de like (más reciente primero).

---

## 2. Config (`app/config.py`)

- `XURL_PAGE_SIZE: int = 5` — tamaño de página para el sync (5 likes por request).
- `SYNC_MIN_CREATED_AT: str = "2026-01-01T00:00:00Z"` — corte heurístico: no se importan
  posts con `created_at` anterior a esta fecha (solo se sincroniza 2026).

---

## 3. Sync (`app/routes/sync.py`) — reescrito

### Enfoque

`xurl likes` (subcomando) no permite paginar ni filtrar por fecha. Por eso se usa la API
raw de X: `xurl /2/users/{user_id}/liked_tweets?...`, que devuelve
`{data, includes.users, includes.media, meta.next_token}`.

### Puntos clave

- **Eliminado bookmarks**: se quitó `_SOURCE_COMMANDS`, el parámetro `source_type`
  (`both`/`bookmarks`) y los bucles sobre fuentes. `POST /sync` ahora sincroniza solo
  likes.
- **`RateLimitedError`**: excepción propia que se lanza cuando xurl devuelve 429
  (detectado por `"Too Many Requests"` en stdout o `"request failed"` en stderr).
- **Persistencia del token**: después de cada página exitosa se llama
  `save_sync_token(log_id, next_token, mode)`. Si llega un 429, el token ya quedó
  guardado y el próximo sync retoma desde ahí en vez de empezar de cero.
- **Resume**: al iniciar, `get_sync_resume_state()` da el token/modo del sync anterior
  incompleto. Si existe, la paginación arranca desde ese token.
- **Dos modos**:
  - `backfill`: DB vacía (`get_max_like_order() == 0`) → asigna like_order por debajo
    del mínimo (valores negativos decrecientes).
  - `incremental`: ya hay posts → asigna like_order por encima del máximo (valores
    positivos crecientes), de modo que los likes nuevos queden al tope.
- **Criterio de parada**: se detiene la paginación cuando (a) se encuentra un post cuyo
  `created_at < SYNC_MIN_CREATED_AT` (corte 2026), o (b) se encuentra un post ya
  existente en la DB (`upsert` → `updated`), porque los likes vienen ordenados por fecha
  de *like* y todo lo siguiente ya está sincronizado.
- **Adaptador de formato** `_adapt_post()`: el item crudo trae solo `author_id`; el
  username/name/avatar se resuelven desde `includes.users` y las URLs de media desde
  `attachments.media_keys` → `includes.media` (campo `url` o `preview_image_url`). Arma
  `url` como `https://x.com/{username}/status/{id}`.
- **`_run_xurl_json()`**: ejecuta `xurl <path>` y parsea JSON, con manejo de
  `FileNotFoundError`, timeout y JSON inválido. Detecta 429 y lanza `RateLimitedError`.
- **Rutas**: `POST /sync` crea el log, ejecuta el sync y devuelve el fragmento del botón;
  ante `RateLimitedError` devuelve error con mensaje indicando que el progreso se guardó.

---

## 4. Modelos (`app/models.py`)

- Se eliminó `Post.is_bookmark`.
- Nueva propiedad `Post.text_html`: escapa el HTML (`html.escape`) y convierte URLs
  (`https?://[^\s<>]+`) en `<a href target="_blank" rel="noopener noreferrer">`.
- Docstrings actualizados a "likes" únicamente.

---

## 5. Rutas de posts (`app/routes/posts.py`)

- Se eliminó el parámetro `source` de `GET /posts`, `GET /posts/load-more` y
  `GET /api/posts`, y de `has_filters`.

---

## 6. Frontend (templates)

### `partials/search_bar.html`
- Eliminado el `<select>` de filtro de fuente ("All sources / Likes / Bookmarks").

### `partials/post_card.html`
- Eliminado el badge "bookmark".
- El texto ahora se renderiza con `{{ post.text_html | safe }}` para linkificar URLs.

### `partials/sync_button.html`
- Botón de sync ahora es **solo icono** (sin texto), con el mismo estilo que Buscar y
  Tema: `p-2 rounded-lg bg-hover text-primary text-lg`.
  - idle: 🔄 (`&#128260;`), en un `<form hx-post="/sync">`
  - running: 🔄 con `animate-spin`, `disabled`
  - success: ✓ (`&#10003;`), con conteos en `title`/`aria-label`
  - error: ✗ (`&#10007;`) en rojo (`text-red-500`), con mensaje en `title`
- Ya no se envía `source_type`.

### `partials/post_list.html`
- **Fix duplicados en "Load more"**: el contenedor del botón cambió de
  `id="load-more-container"` a clase `load-more-wrap`, y el botón ahora se auto-elimina
  tras cargar con `hx-on::after-request="this.closest('.load-more-wrap').remove()"`.
  Antes el botón original nunca se eliminaba y coexistía con el sucesor, lo que al hacer
  clic de nuevo re-appendeaba una página ya mostrada.
- El contador `Showing X of Y posts` ahora tiene `id="post-count"` para ser actualizado
  por la paginación.

### `partials/post_cards_only.html`
- **Fix contador**: al principio del fragmento se añadió
  `<div id="post-count" hx-swap-oob="true">Showing {{ [page * per_page, total] | min }} ...</div>`
  que actualiza el contador existente (OOB) al cargar más páginas.
- El botón "Load more" también se auto-elimina tras cargar (mismo `hx-on::after-request`).

### `index.html`
- Eliminado el logo/título `<h1>📦 xarchive</h1>` del header.
- `hasSearchParams()` ya no incluye la clave `'source'`.

### `app/main.py`
- Descripción de la app: "Local X.com (Twitter) likes archive with search".

---

## 7. Tests

- `tests/conftest.py`: `sample_posts` ya no cicla bookmark/like (todo `like`). Mocks de
  xurl reescritos al formato real `{data, includes.users, meta.next_token}`. Nuevos
  fixtures: `mock_xurl_paginated` (2 páginas), `mock_xurl_rate_limited` (página 2 → 429).
  `MOCK_POSTS` con fechas 2026 y `MOCK_POSTS_PAGE_2`.
- `tests/test_routes/test_sync.py`: tests para paginación, stop en el primer post ya
  sincronizado, rate limit con persistencia de token, resume desde token, corte 2026,
  asignación de like_order.
- `tests/test_db.py`: removidos tests de source filtering y merge de fuentes; añadidos
  tests de `delete_all_posts`, `delete_bookmark_posts`.
- `tests/test_models.py`: removidos tests de `is_bookmark`; añadidos tests de `text_html`
  (linkify y escape de HTML).
- `tests/test_frontend/test_index_header.py`: el logo ya no debe existir.
- `tests/test_frontend/test_sync_button.py`: el botón idle es icon-only (sin texto,
  `&#128260;`).
- `tests/test_routes/test_posts.py`: verifica que ya no existe el filtro de fuente.
- Tests de acceptance y js actualizados a los nuevos textos/estructuras.

---

## 8. Pruebas reales realizadas (contexto)

- Se verificó que `xurl likes` no pagina ni filtra por fecha; la API raw sí (`meta.next_token`).
- El formato real de xurl v1.3.1 es `{data, includes, meta}`, distinto del que el código
  original esperaba (lista plana), por lo que el sync antiguo estaba roto contra datos reales.
- Los `pagination_token` siguen siendo válidos tras el rate limit (probado), lo que hace
  posible retomar.
- La DB quedó con 431 likes (todos de 2026); `like_order` de -431 a -1.

## 9. Pendiente / notas

- `scripts/import_from_html.py` existía antes de esta sesión (sin cambios).
- El `like_order` de los posts importados antes de esta sesión quedaría en 0; para un
  backfill desde cero se borra la DB y se sincroniza de nuevo.
