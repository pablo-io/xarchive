# Diseño — dark-theme-search-ui

Sin fase de arquitectura: el cambio sigue los patrones existentes del proyecto.
Ver docs/spec/dark-theme-search-ui.md para requisitos y criterios de aceptación.

## Resumen de diseño

Todos los cambios se limitan a la capa de presentación: templates Jinja2, CSS en `custom.css` y JS inline en los templates. No se tocan rutas FastAPI, modelos ni consultas.

**Estrategia de tema oscuro:** Se usan variables CSS definidas en `custom.css` bajo un selector `[data-theme="dark"]` en el `<html>`. Las clases de Tailwind existentes se complementan con clases utilitarias personalizadas (ej. `.card-bg`, `.text-primary`) que apuntan a las variables CSS. El JS de toggle cambia el atributo `data-theme` y persiste en `localStorage` con la clave `xarchive-theme`.

**Estrategia de barra de búsqueda:** La barra se envuelve en un `<div id="search-bar-wrapper">` con clase CSS `hidden` por defecto. Un botón 🔍 en el header alterna la clase `hidden` con una transición suave. Si la URL contiene parámetros de búsqueda (`q`, `username`, `date_from`, `date_to`, `source`), la barra se muestra automáticamente al cargar.

**Estrategia de fechas compactas:** Los inputs `type="date"` se envuelven en `<label>` con estilo de botón compacto. El input real se oculta visualmente (`sr-only`) pero sigue siendo funcional. Un `<span>` muestra el icono 📅 + texto "Inicio"/"Fin" o la fecha seleccionada.

**Estrategia de imágenes responsivas:** Se reemplaza `w-24 h-24` por un grid CSS de 2 columnas (responsive hasta 4) con `object-cover` y `aspect-square`, ajustándose al ancho disponible de la tarjeta.

---

## Task Breakdown

### Tarea 1: Simplificar botón Sync
**Tipo:** Frontend
**Descripción:** Eliminar el `<select>` del estado idle del botón Sync en `sync_button.html`. El botón debe enviar directamente `source_type=both` sin mostrar un combobox. Los estados "running", "success" y "error" ya usan `value="both"` y no necesitan cambios. Se reemplaza el `<form>` con `<select>` + `<button>` por un `<button>` simple con `name="source_type" value="both"` dentro de un `<form>` mínimo.
**Archivos a crear:** —
**Archivos a modificar:** `app/templates/partials/sync_button.html`
**Contrato:**
- Entrada: template Jinja2 con variable `state` (idle|running|success|error)
- Salida: HTML del botón Sync sin `<select>`. En estado idle, un `<form hx-post="/sync">` contiene solo un `<button type="submit" name="source_type" value="both">` con el texto "🔄 Sync".
- El atributo `hx-target="#sync-button"` y `hx-swap="outerHTML"` se mantienen.
**Criterios de aceptación:**
- [ ] En estado idle, no existe ningún `<select>` en el HTML renderizado.
- [ ] En estado idle, el botón tiene `name="source_type"` y `value="both"`.
- [ ] Al hacer clic en el botón Sync en estado idle, se envía una petición POST a `/sync` con `source_type=both`.
- [ ] Los estados "running", "success" y "error" siguen funcionando correctamente (sin cambios en su lógica).
- [ ] No existe ningún combobox con opciones "All / Likes / Bookmarks" en la barra superior.
**Dependencias:** ninguna
**Tamaño:** S

---

### Tarea 2: Sistema de tema oscuro — CSS variables y JS toggle
**Tipo:** Frontend
**Descripción:** Implementar el sistema de tema oscuro completo: (1) variables CSS en `custom.css` bajo `[data-theme="dark"]` con los colores de x.com dark theme, (2) clases utilitarias personalizadas que mapean a las variables, (3) JS inline en `base.html` que lee `localStorage` al cargar, aplica el tema al `<html>`, y expone una función `toggleTheme()` para el botón. La clave de localStorage es `xarchive-theme`.
**Archivos a crear:** —
**Archivos a modificar:** `app/static/css/custom.css`, `app/templates/base.html`
**Contrato:**
- CSS: variables en `:root` (tema claro) y `[data-theme="dark"]` (tema oscuro):
  - `--bg-page`: `#f9fafb` (claro) / `#000000` (oscuro)
  - `--bg-card`: `#ffffff` (claro) / `#16181c` (oscuro)
  - `--text-primary`: `#111827` (claro) / `#e7e9ea` (oscuro)
  - `--text-secondary`: `#6b7280` (claro) / `#71767b` (oscuro)
  - `--border-color`: `#e5e7eb` (claro) / `#2f3336` (oscuro)
  - `--accent-color`: `#2563eb` (claro) / `#1d9bf0` (oscuro)
  - `--bg-hover`: `#f3f4f6` (claro) / `#181818` (oscuro)
- Clases utilitarias: `.card-bg { background-color: var(--bg-card) }`, `.text-primary { color: var(--text-primary) }`, `.text-secondary { color: var(--text-secondary) }`, `.border-themed { border-color: var(--border-color) }`, `.bg-page { background-color: var(--bg-page) }`, `.accent { color: var(--accent-color) }`, `.bg-hover:hover { background-color: var(--bg-hover) }`.
- JS en `base.html` (antes de `</body>`):
  ```
  function getTheme() { return localStorage.getItem('xarchive-theme') || 'light'; }
  function applyTheme(t) { document.documentElement.setAttribute('data-theme', t); }
  function toggleTheme() {
    var t = getTheme() === 'dark' ? 'light' : 'dark';
    localStorage.setItem('xarchive-theme', t);
    applyTheme(t);
    updateThemeIcon(t);
  }
  function updateThemeIcon(t) {
    var btn = document.getElementById('theme-toggle');
    if (btn) btn.textContent = t === 'dark' ? '☀️' : '🌙';
  }
  applyTheme(getTheme());
  ```
- El `<body>` de `base.html` cambia `class="bg-gray-50"` a `class="bg-page"`.
**Criterios de aceptación:**
- [ ] Al cargar la página sin `localStorage`, el tema es claro (fondo `#f9fafb`, tarjetas blancas).
- [ ] Al ejecutar `toggleTheme()` en consola, el tema cambia a oscuro con los colores especificados.
- [ ] Al recargar la página con tema oscuro activo, el tema se mantiene oscuro.
- [ ] Al abrir una nueva pestaña, la preferencia de tema se comparte.
- [ ] Si `localStorage` no está disponible, no se producen errores en consola y el tema es claro por defecto.
- [ ] Las clases utilitarias `.card-bg`, `.text-primary`, `.text-secondary`, `.border-themed`, `.bg-page` funcionan correctamente en ambos temas.
**Dependencias:** ninguna
**Tamaño:** M

---

### Tarea 3: Rediseñar header con botones de tema y búsqueda
**Tipo:** Frontend
**Descripción:** Modificar el header en `index.html` para que sea compacto y contenga: (1) título "📦 xarchive", (2) botón Sync simplificado (ya sin select, de Tarea 1), (3) botón toggle de tema (🌙/☀️) con `id="theme-toggle"` y `onclick="toggleTheme()"`, (4) botón toggle de búsqueda (🔍) con `id="search-toggle"` y `onclick="toggleSearchBar()"`. El header usa las clases de tema oscuro de la Tarea 2.
**Archivos a crear:** —
**Archivos a modificar:** `app/templates/index.html`
**Contrato:**
- Header HTML:
  ```
  <header class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 border-themed">
    <div class="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between gap-2">
      <h1 class="text-xl font-bold text-primary tracking-tight">📦 xarchive</h1>
      <div class="flex items-center gap-2">
        <div id="sync-button" ...>...</div>
        <button id="search-toggle" onclick="toggleSearchBar()" aria-label="Toggle search bar"
                class="p-2 rounded-lg hover:bg-gray-100 bg-hover text-primary text-lg">🔍</button>
        <button id="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark theme"
                class="p-2 rounded-lg hover:bg-gray-100 bg-hover text-primary text-lg">🌙</button>
      </div>
    </div>
  </header>
  ```
- El `id="sync-button"` con HTMX se mantiene en su posición.
- Se añade bloque `{% block scripts %}` con el JS de `toggleSearchBar()` (definido en Tarea 4) y la inicialización del icono del tema al cargar.
**Criterios de aceptación:**
- [ ] El header muestra 4 elementos en fila: título, sync, 🔍, 🌙.
- [ ] El botón 🔍 tiene `aria-label="Toggle search bar"`.
- [ ] El botón 🌙 tiene `aria-label="Toggle dark theme"`.
- [ ] Al hacer clic en 🌙, se ejecuta `toggleTheme()` y el icono cambia a ☀️.
- [ ] En tema oscuro, el header usa fondo `#16181c` con borde `#2f3336`.
- [ ] El botón Sync simplificado (de Tarea 1) se muestra correctamente en el header.
- [ ] Los botones tienen estado hover con `bg-hover` que cambia según el tema.
**Dependencias:** Tarea 1, Tarea 2
**Tamaño:** M

---

### Tarea 4: Toggle de visibilidad de barra de búsqueda
**Tipo:** Frontend
**Descripción:** Implementar la lógica JS para mostrar/ocultar la barra de búsqueda con transición suave. La barra se envuelve en un `<div id="search-bar-wrapper">` en `index.html`. Por defecto tiene clase `hidden`. La función `toggleSearchBar()` alterna la visibilidad. Si la URL contiene parámetros de búsqueda (`q`, `username`, `date_from`, `date_to`, `source` con valores no vacíos), la barra se muestra automáticamente al cargar. Se añade la función JS en el bloque `{% block scripts %}` de `index.html`.
**Archivos a crear:** —
**Archivos a modificar:** `app/templates/index.html`, `app/static/css/custom.css`
**Contrato:**
- Wrapper en `index.html`:
  ```
  <div id="search-bar-wrapper" class="search-bar-wrapper hidden">
    {% include "partials/search_bar.html" %}
  </div>
  ```
- CSS en `custom.css`:
  ```
  .search-bar-wrapper { overflow: hidden; transition: max-height 300ms ease-in-out, opacity 300ms ease-in-out; }
  .search-bar-wrapper.hidden { max-height: 0; opacity: 0; pointer-events: none; display: block; }
  .search-bar-wrapper:not(.hidden) { max-height: 500px; opacity: 1; pointer-events: auto; }
  ```
- JS en `index.html` (bloque `{% block scripts %}`):
  ```
  function toggleSearchBar() {
    var w = document.getElementById('search-bar-wrapper');
    w.classList.toggle('hidden');
  }
  function hasSearchParams() {
    var p = new URLSearchParams(window.location.search);
    return ['q','username','date_from','date_to','source'].some(function(k) {
      var v = p.get(k); return v && v !== '' && v !== 'all';
    });
  }
  if (hasSearchParams()) {
    var w = document.getElementById('search-bar-wrapper');
    if (w) w.classList.remove('hidden');
  }
  ```
**Criterios de aceptación:**
- [ ] Al cargar la página sin parámetros de búsqueda, la barra está oculta.
- [ ] Al hacer clic en 🔍, la barra se muestra con transición suave (slide-down/fade-in).
- [ ] Al hacer clic en 🔍 nuevamente, la barra se oculta con transición suave.
- [ ] Al cargar la página con `?q=test`, la barra se muestra automáticamente visible.
- [ ] Al cargar la página con `?date_from=2025-01-01`, la barra se muestra automáticamente visible.
- [ ] Al cargar la página con `?source=all` (sin otros filtros), la barra permanece oculta (valor "all" se ignora).
- [ ] La transición CSS tiene duración ~300ms con easing.
- [ ] Cambiar el tema mientras la barra está abierta no afecta su estado de visibilidad.
**Dependencias:** Tarea 2, Tarea 3
**Tamaño:** M

---

### Tarea 5: Compactar campos de fecha en barra de búsqueda
**Tipo:** Frontend
**Descripción:** Reemplazar los inputs `type="date"` de `search_bar.html` por un diseño compacto: un `<label>` con estilo de botón que contiene un icono 📅 y texto "Inicio" (para `date_from`) o "Fin" (para `date_to`). El input `type="date"` real se oculta con `sr-only` pero sigue siendo funcional. Al seleccionar una fecha, el label muestra la fecha en formato `YYYY-MM-DD`. Se necesita JS inline para actualizar el texto del label al cambiar la fecha.
**Archivos a crear:** —
**Archivos a modificar:** `app/templates/partials/search_bar.html`, `app/static/css/custom.css`
**Contrato:**
- HTML para cada campo de fecha (ejemplo `date_from`):
  ```
  <label for="search-date-from" class="date-compact-btn" id="label-date-from">
    <input type="date" id="search-date-from" name="date_from"
           value="{{ date_from | default('') }}"
           class="search-field sr-only"
           onchange="updateDateLabel('date-from', this.value)">
    <span class="date-compact-text">📅 {{ date_from if date_from else 'Inicio' }}</span>
  </label>
  ```
- CSS en `custom.css`:
  ```
  .date-compact-btn { display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.375rem 0.75rem; border: 1px solid var(--border-color); border-radius: 0.5rem; cursor: pointer; font-size: 0.875rem; background: var(--bg-card); color: var(--text-primary); transition: background 150ms; }
  .date-compact-btn:hover { background: var(--bg-hover); }
  .date-compact-text { white-space: nowrap; }
  ```
- JS inline (en `search_bar.html` o `base.html`):
  ```
  function updateDateLabel(id, value) {
    var span = document.querySelector('#label-' + id + ' .date-compact-text');
    if (span) span.textContent = value ? '📅 ' + value : (id === 'date-from' ? 'Inicio' : 'Fin');
  }
  ```
**Criterios de aceptación:**
- [ ] Los campos de fecha se muestran como botones compactos con 📅 + "Inicio" / "Fin".
- [ ] Al hacer clic en el botón compacto, se abre el selector de fecha nativo del navegador.
- [ ] Al seleccionar una fecha, el texto cambia a "📅 2025-01-15" (formato ISO).
- [ ] Al limpiar la fecha, el texto vuelve a "Inicio" o "Fin".
- [ ] Los valores `date_from` y `date_to` se envían correctamente como parámetros de consulta HTMX.
- [ ] En tema oscuro, el botón compacto usa fondo `#16181c`, borde `#2f3336` y texto `#e7e9ea`.
- [ ] El input `type="date"` real es invisible (`sr-only`) pero accesible por teclado.
**Dependencias:** Tarea 2, Tarea 4
**Tamaño:** S

---

### Tarea 6: Imágenes responsivas en post cards
**Tipo:** Frontend
**Descripción:** Cambiar las imágenes de los post cards de tamaño fijo `w-24 h-24` a un grid responsivo que se ajuste al ancho disponible de la tarjeta. Se usa un grid CSS de 2 columnas en pantallas pequeñas y hasta 4 columnas en pantallas anchas. Las imágenes usan `aspect-square` y `object-cover` para mantener proporciones. Los bordes usan las variables CSS de tema.
**Archivos a crear:** —
**Archivos a modificar:** `app/templates/partials/post_card.html`, `app/static/css/custom.css`
**Contrato:**
- HTML en `post_card.html` (reemplazar el `<div class="flex gap-2 mt-2 flex-wrap">`):
  ```
  <div class="media-grid mt-2">
    {% for url in post.media_urls[:4] %}
    <img src="{{ url }}"
         class="media-grid-item object-cover rounded-lg border border-themed"
         alt="media attachment" loading="lazy">
    {% endfor %}
  </div>
  ```
- CSS en `custom.css`:
  ```
  .media-grid { display: grid; gap: 0.5rem; grid-template-columns: repeat(2, 1fr); }
  @media (min-width: 640px) { .media-grid { grid-template-columns: repeat(4, 1fr); } }
  .media-grid-item { aspect-ratio: 1 / 1; width: 100%; }
  ```
- El texto del post (`<p>`) ya usa `break-words` y `whitespace-pre-wrap`. Verificar que en tema oscuro usa `color: var(--text-primary)`.
**Criterios de aceptación:**
- [ ] Las imágenes se muestran en grid de 2 columnas en pantallas < 640px.
- [ ] Las imágenes se muestran en grid de 4 columnas en pantallas >= 640px.
- [ ] Las imágenes mantienen aspect ratio 1:1 sin distorsión (`aspect-square` + `object-cover`).
- [ ] Las imágenes se ajustan al ancho disponible de la tarjeta (no tienen tamaño fijo de 96x96px).
- [ ] Al cambiar el tamaño de la ventana, las imágenes se reflowan correctamente.
- [ ] En tema oscuro, el borde de las imágenes usa `#2f3336`.
- [ ] En tema claro, el borde de las imágenes usa `#e5e7eb`.
- [ ] Un post sin imágenes no muestra espacio vacío residual.
- [ ] Un post con más de 4 imágenes muestra máximo 4 (límite `[:4]` se mantiene).
- [ ] El texto del post no se desborda horizontalmente y usa `break-words`.
- [ ] En tema oscuro, el texto del post usa color `#e7e9ea` sobre fondo `#16181c`.
**Dependencias:** Tarea 2
**Tamaño:** S
