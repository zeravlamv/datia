# Infografía Financiera - Tema Café

## Objetivo
Página única de 90% × 90% del viewport, sin scroll, que presenta KPIs y análisis financiero con estética inspirada en el sector café. Integra narrativa CFO, elementos gráficos (tazas, camino, pilares, triángulos), accesibilidad AA y diseño responsivo.

## Arquitectura
- HTML: generado desde el overlay IA2 por `AIReportManager._buildStoryHtml` y exportado en pruebas por `test_ai2_pdf`.
- CSS: `datia/static/css/infografia_story.css` (editorial) con clases del tema café: road, beans, gauges, sparklines, barras P&L.
- JS: `datia/static/js/ai_manager.js` construye el HTML con:
  - KPIs en tazas SVG (`mkCup`).
  - Gauges Liquidez/Solvencia.
  - Camino editorial con granos (`story-road`).
  - Tarjetas trimestrales con sparklines y P&L compacto.

## Datos y patrón
- Origen de datos: `/api/financial/infografia` (JSON con `kpis`, `balance_situacion.ratios`, `pl_analisis`, `estacionalidad`, `trimestres`).
- Patrón: 09‑Financiera (endpoints/servicios/Frontend ECharts SVG).

## Accesibilidad
- Semántica: `main`, `section` y `aria-label` por bloque.
- Contraste: paleta AA; variantes `warn/danger` con suficiente contraste.
- Motion: `prefers-reduced-motion` para transiciones suaves.
- Teclado: overlay con foco visible y CTA manipulables.

## Responsivo
- Grid adaptativo para KPI, columnas y trimestral.
- Contenedor `story-stage` centrado (90vw × 90vh) y `overflow:hidden` con autoescala.

## Pruebas
- `datia/tests/test_infografia_cafe_html.py`: valida presencia de `gauge-grid` y `story-quarter-grid`.
- Export de prueba: `python manage.py test_ai2_pdf --empresa <id> --ejercicio <año> --force_fallback`.

## Mantenimiento
- Variables CSS para colores y componentes.
- Extensible: añadir bloques (alertas, clientes riesgo, Pareto) reutilizando las mismas clases.
