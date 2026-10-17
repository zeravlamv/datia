Patron de diseño: Datia WOW (NF-001)
=====================================
Este patrón define la estética y principios de la vista "Datia 1" (versión Apple/Sage).

1. Principios de Diseño
-----------------------
- **Floating Content**: Nada está encerrado en cajas ("cards") visibles con bordes duros. El contenido flota sobre el fondo.
- **Sin Marcos**: Evitar `border: 1px solid`. Usar espacio negativo para separar elementos.
- **Tipografía**:
  - Títulos masivos (Display).
  - Fuentes limpias (Inter/SF Pro).
  - Alto contraste pero suave (blanco sobre negro puro).
- **Fondos**:
  - Evitar degradados complejos o "manchas" de color saturadas.
  - Usar negro profundo (`#000000` o `#050505`) o gris muy oscuro (`#0a0a0a`).
  - Sutil "Grain" o ruido para textura premium si es posible.

2. Estructura del Componente
----------------------------
- Hero Section: Logo y título centrado, muy grande, sin distracciones.
- Feature Grid: Iconos y texto organizados en rejilla invisible.
- Deep Dive: Sección explicativa con scroll suave o aparición progresiva.

3. Integración
--------------
- Se carga en `dashboard.html` como `#tab-datia-wow`.
- Debe coexistir con `#tab-datia` original para comparación.
