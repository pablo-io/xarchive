# Spec: dark-theme-search-ui

## Objetivo

Mejorar la interfaz de usuario de xarchive con cinco cambios concretos:

1. **Tema oscuro** inspirado en el tema dark de x.com, conmutables mediante un botón en la barra superior.
2. **Simplificar la barra superior** eliminando el combobox de fuente del botón Sync (duplica el filtro "All sources" de la barra de búsqueda).
3. **Botón de búsqueda** con icono de lupa que muestra u oculta la barra de búsqueda.
4. **Compactar los campos de fecha** en la barra de búsqueda: reemplazar el input date completo por un icono de calendario + texto breve ("Inicio" / "Fin"), manteniendo la funcionalidad de filtrado.
5. **Ajustar imágenes y texto** de los post cards al tamaño disponible de la caja, en lugar de las miniaturas fijas de 96×96 px actuales.

Usuario objetivo: usuario final de xarchive que consulta sus likes y bookmarks archivados en un navegador moderno.

---

## Alcance

### Dentro del alcance (in-scope)

| # | Cambio | Capa |
|---|--------|------|
| 1 | Sistema de tema claro/oscuro con persistencia en `localStorage` | Frontend (CSS + JS mínimo en template) |
| 2 | Botón toggle de tema (icono sol/luna) en la barra superior | Frontend (template + CSS) |
| 3 | Eliminación del `<select>` de fuente en el botón Sync (estado idle) | Frontend (template `sync_button.html`) |
| 4 | Botón lupa que alterna visibilidad de la barra de búsqueda | Frontend (template + JS inline) |
| 5 | Rediseño compacto de campos de fecha en la barra de búsqueda | Frontend (template + CSS) |
| 6 | Imágenes responsivas en post cards (ajustadas a la caja) | Frontend (template + CSS) |
| 7 | Texto responsivo en post cards (ajustado a la caja) | Frontend (template + CSS) |

### Fuera del alcance (out-of-scope)

- Cualquier cambio en el backend: rutas FastAPI, modelos Pydantic, consultas SQL o esquema de la base de datos.
- Modificar la lógica de sincronización (solo se cambia la presentación del botón Sync).
- Soporte para más de dos temas (claro / oscuro).
- Cambios en la funcionalidad de búsqueda, paginación o filtros HTMX.
- Migración de Tailwind CSS de CDN a build local.
- Tests automatizados nuevos (la UI se valida manualmente con los criterios de aceptación).

---

## Requisitos funcionales — Criterios de aceptación

### RF-1: Tema oscuro con botón toggle

> **Dado** que el usuario carga la aplicación por primera vez,
> **Cuando** la página termina de renderizar,
> **Entonces** el tema por defecto es el claro (fondo `bg-gray-50`, tarjetas blancas) y el botón de tema muestra un icono de luna (🌙).

> **Dado** que el usuario está viendo la aplicación en tema claro,
> **Cuando** hace clic en el botón de tema,
> **Entonces** toda la interfaz cambia al tema oscuro con los siguientes colores:
> - Fondo de página: `#000000`
> - Fondo de tarjetas: `#16181c`
> - Texto primario: `#e7e9ea`
> - Texto secundario: `#71767b`
> - Bordes: `#2f3336`
> - Color de acento (botones, enlaces): `#1d9bf0`
> - Fondo de hover en tarjetas: `#181818`
> **Y** el botón de tema cambia a un icono de sol (☀️).

> **Dado** que el usuario activó el tema oscuro,
> **Cuando** recarga la página o la abre en una nueva pestaña,
> **Entonces** el tema oscuro se mantiene activo (persistencia en `localStorage`).

> **Dado** que el usuario está en tema oscuro,
> **Cuando** hace clic en el botón de tema,
> **Entonces** la interfaz vuelve al tema claro.

### RF-2: Eliminación del combobox duplicado en la barra superior

> **Dado** que el usuario carga la página principal,
> **Cuando** observa la barra superior (header),
> **Entonces** el botón Sync se muestra como un botón simple (sin `<select>` adyacente) que ejecuta sync de "both" (likes + bookmarks).
> **Y** no existe ningún combobox con opciones "All / Likes / Bookmarks" en la barra superior.

> **Dado** que el usuario hace clic en el botón Sync simplificado,
> **Cuando** la petición HTMX se envía,
> **Entonces** se sincronizan tanto likes como bookmarks (valor `source_type=both`).

### RF-3: Botón de búsqueda (lupa) para mostrar/ocultar la barra de búsqueda

> **Dado** que el usuario carga la página principal,
> **Cuando** la página termina de renderizar,
> **Entonces** la barra de búsqueda está oculta por defecto y se muestra un botón con icono de lupa (🔍) en la barra superior.

> **Dado** que la barra de búsqueda está oculta,
> **Cuando** el usuario hace clic en el botón de lupa,
> **Entonces** la barra de búsqueda se muestra con una transición suave (slide-down o fade-in).

> **Dado** que la barra de búsqueda está visible,
> **Cuando** el usuario hace clic en el botón de lupa,
> **Entonces** la barra de búsqueda se oculta con una transición suave.

> **Dado** que el usuario realizó una búsqueda y la barra está visible,
> **Cuando** recarga la página con parámetros de búsqueda en la URL (ej. `?q=hola`),
> **Entonces** la barra de búsqueda se muestra automáticamente visible (para que el usuario vea los filtros activos).

### RF-4: Campos de fecha compactos en la barra de búsqueda

> **Dado** que la barra de búsqueda está visible,
> **Cuando** el usuario observa los campos de fecha,
> **Entonces** cada campo se muestra como un botón/label compacto con un icono de calendario (📅) y un texto breve: "Inicio" para `date_from` y "Fin" para `date_to`.
> **Y** al hacer clic en el label/botón se abre el input type="date" nativo del navegador (el input puede estar oculto visualmente pero funcional).

> **Dado** que el usuario seleccionó una fecha en el campo "Inicio",
> **Cuando** el campo pierde el foco,
> **Entonces** el label muestra la fecha seleccionada en formato corto (ej. "📅 2025-01-15") o el texto "Inicio" si no hay fecha.

> **Dado** que hay fechas seleccionadas en los campos de fecha,
> **Cuando** el formulario se envía vía HTMX,
> **Entonces** los valores `date_from` y `date_to` se envían correctamente como parámetros de consulta (mismo comportamiento que actualmente).

### RF-5: Imágenes responsivas en post cards

> **Dado** que un post tiene imágenes adjuntas,
> **Cuando** se renderiza el post card,
> **Entonces** las imágenes se ajustan al ancho disponible de la caja del post (no tienen un tamaño fijo de 96×96 px).
> **Y** las imágenes mantienen su aspect ratio (no se distorsionan).
> **Y** se muestran en un grid flexible que se adapta al ancho de la tarjeta.

> **Dado** que el usuario cambia entre tema claro y oscuro,
> **Cuando** las imágenes se renderizan,
> **Entonces** el borde de las imágenes usa el color de borde del tema activo (`border-gray-200` en claro, `border-[#2f3336]` en oscuro).

### RF-6: Texto responsivo en post cards

> **Dado** que un post tiene texto largo,
> **Cuando** se renderiza el post card,
> **Entonces** el texto se ajusta al ancho completo disponible de la caja.
> **Y** no se desborda horizontalmente.
> **Y** utiliza `break-words` para cortar palabras largas si es necesario.

> **Dado** que el usuario está en tema oscuro,
> **Cuando** observa el texto de un post,
> **Entonces** el texto se muestra en color `#e7e9ea` sobre fondo `#16181c` con contraste legible.

---

## Casos borde

| Caso | Comportamiento esperado |
|------|------------------------|
| El usuario tiene `localStorage` deshabilitado | El tema se mantiene en claro por defecto durante la sesión. No se producen errores en consola. |
| El usuario cambia el tema mientras la barra de búsqueda está abierta | La barra de búsqueda mantiene su estado (abierta/cerrada) y los colores se actualizan correctamente. |
| Un post no tiene imágenes | El post card se renderiza sin la sección de imágenes. No hay espacio vacío residual. |
| Un post tiene más de 4 imágenes | Se muestran máximo 4 imágenes (límite actual), ajustadas al ancho disponible. |
| Una imagen tiene proporciones extremas (muy ancha o muy alta) | La imagen se recorta con `object-cover` dentro de su celda del grid, manteniendo aspect ratio. |
| El texto de un post contiene URLs muy largas | El texto usa `break-words` para que no desborde la tarjeta. |
| El navegador no soporta `color-scheme` o variables CSS | Se usa el fallback de clases de Tailwind; el tema claro funciona correctamente. |
| El usuario abre la app con parámetros de búsqueda en la URL (`?q=test&date_from=2025-01-01`) | La barra de búsqueda se muestra automáticamente visible al cargar. |
| Redimensión de ventana (responsive) | Las imágenes del post card se reflowan correctamente al cambiar el ancho de la ventana. |
| El botón Sync se usa rápidamente múltiples veces | El lock existente en el backend previene syncs simultáneos. El botón muestra el estado "Syncing..." correctamente. |

---

## Restricciones

1. **Sin backend nuevo:** Todos los cambios son de capa de presentación (templates HTML, CSS, JS inline). No se añaden rutas, modelos ni consultas nuevas.
2. **Tailwind CSS vía CDN:** Se mantiene el CDN de Tailwind. Las variables CSS personalizadas para el tema oscuro se definen en `custom.css`.
3. **HTMX intacto:** La lógica de búsqueda, paginación y sync vía HTMX no se modifica. Los atributos `hx-get`, `hx-trigger`, `hx-swap` etc. permanecen funcionales.
4. **JS mínimo:** El JavaScript necesario se limita a: (a) toggle de tema con `localStorage`, (b) toggle de visibilidad de la barra de búsqueda. No se introduce ningún framework JS.
5. **Accesibilidad básica:** Los botones de toggle deben tener `aria-label` descriptivos. Los iconos decorativos usan `aria-hidden="true"`. El contraste en tema oscuro debe ser legible (ratio ≥ 4.5:1 para texto normal).
6. **Compatibilidad:** Navegadores modernos (Chrome, Firefox, Edge, Safari últimos 2 años). No se requiere soporte para IE11.
7. **Persistencia ligera:** La preferencia de tema se guarda en `localStorage` bajo la clave `xarchive-theme`. No se guarda en la base de datos ni en cookies.

---

## Supuestos

1. **Interpretación de "Elimina el la barra superior":** Se interpreta como "elimina el combobox (select) de la barra superior", no como "elimina toda la barra superior". La barra superior (header) se mantiene con el título "xarchive", el botón Sync simplificado, el botón de tema y el botón de búsqueda.
2. **Sync sin selector de fuente:** Al eliminar el `<select>` del botón Sync, se asume que el botón siempre enviará `source_type=both` (sincronizar likes y bookmarks simultáneamente).
3. **Barra de búsqueda oculta por defecto:** Se asume que la barra de búsqueda debe estar oculta al cargar la página sin filtros, y visible cuando la URL contiene parámetros de búsqueda.
4. **Iconos emoji como placeholders:** Se usarán emojis (🌙, ☀️, 🔍, 📅) como iconos iniciales. Si se desea, pueden reemplazarse por SVG inline en una iteración posterior.
5. **Fecha en formato ISO corto:** Cuando se selecciona una fecha, se muestra en formato `YYYY-MM-DD` (el valor nativo del input date).
6. **Grid de imágenes responsivo:** Las imágenes se mostrarán en un grid CSS de 2 columnas en pantallas pequeñas y hasta 4 columnas en pantallas más anchas, ajustándose al contenedor.

---

ARQUITECTURA: no requerida — Todos los cambios están contenidos en la capa de presentación (templates Jinja2, CSS y JS inline). No se introducen nuevos componentes, servicios, dependencias externas ni cambios en el modelo de datos o contratos de API. Los patrones existentes (Tailwind + HTMX + Jinja2) son suficientes para implementar la funcionalidad.
