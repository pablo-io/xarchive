# Spec: dark-theme-fixes

## Objetivo
Corregir dos bugs post-merge del feature `dark-theme-search-ui`:
1. Los campos de fecha compactos no abren el calendario nativo
2. Las imágenes de posts no se ajustan al ancho de la caja

## Bugs

### Bug 1: Calendario no abre (Issue #23)
- **Problema:** El input `type="date"` usa `sr-only` de Tailwind (`position: absolute` + `clip: rect(0,0,0,0)`), lo que impide que el clic en el `<label>` se propague correctamente al input.
- **Fix:** Reemplazar `sr-only` por `opacity: 0` + `position: absolute` con `width: 100%` y `height: 100%` sobre el label, y ajustar el label a `position: relative`.

### Bug 2: Imágenes no responsivas (Issue #24)
- **Problema:** La clase `.media-grid-item` con `width: 100%` no se aplica correctamente porque `<img>` es inline por defecto. El grid tampoco tiene ancho completo.
- **Fix:** Agregar `display: block` a `.media-grid-item` y asegurar que el grid se expanda al 100% del contenedor.

## Criterios de aceptación
- [ ] Al hacer clic en 📅 Inicio/Fin, se abre el selector de fecha nativo del navegador
- [ ] Al seleccionar una fecha, el label muestra el valor actualizado
- [ ] Las imágenes se muestran en grid responsivo ocupando el ancho disponible
- [ ] 100% de los tests pasan
- [ ] Sin regresiones en el tema oscuro

ARQUITECTURA: no requerida — Bugfixes de CSS/HTML sin cambios de backend.
