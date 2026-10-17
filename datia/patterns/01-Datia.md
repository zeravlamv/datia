Patron de funcionamiento de Datia (Identidad)
==============================================
Este patrón define la pestaña "Datia", que actúa como el corazón filosófico y punto de identidad de la aplicación.

1. Objetivo del Módulo
----------------------
- **Branding**: Reforzar la identidad visual y los valores de la marca (Privacidad, Potencia, Universalidad).
- **Educación**: Explicar al usuario cómo funciona el sistema ("Privacidad por Diseño", "Vectorización").
- **Estética**: Servir como showcase de las capacidades de diseño UI (Glassmorphism, Animaciones).

2. Componentes Visuales (`tab_datia.html`)
------------------------------------------
### 2.1 Hero Section
- **Fondo**: Imagen `bg_datia_v2.png` con overlay de gradiente radial intenso para foco visual.
- **Logo Dinámico**:
  - Script inline autoejecutable para recuperar el logo seleccionado (`datia-selected-logo`) de `localStorage`.
  - Efectos CSS: `logo-glow` (pulso) y `float` (levitación suave).

### 2.2 Value Grid (Grid de Valor)
- Tres tarjetas con iconografía SVG explicando los pilares:
  1. **Universal & Multilingüe**: Conexión agnóstica (SAGE, SAP) y soporte de idiomas.
  2. **Multi-Empresa**: Gestión centralizada de razones sociales.
  3. **Seguridad Granular**: RBAC y privacidad de datos.

### 2.3 Deep Dive Showcase (Ilustración)
- Sección visual (`glass-showcase`) que explica el pipeline de AI en 3 pasos:
  1. Conexión.
  2. Vectorización Local.
  3. Razonamiento Profundo.
- Usa `ai_feature_v2.png` como ancla visual.

3. Estilos Específicos
----------------------
Este módulo encapsula sus propios estilos críticos para garantizar un "Wow Effect" independiente del tema global.
- **Fuentes**: Usa `JetBrains Mono` para el footer técnico ("Powered by...").
- **Animaciones**:
  - `fadeInDown`: Entrada dramática del título.
  - `pulse`: Respiración del aura del logo.
  - `float`: Movimiento orgánico del logo.

4. Footer Técnico
-----------------
Lista la pila tecnológica explícitamente para transparencia con el usuario técnico:
- Python, Django, Ollama, PostgreSQL, Vector DB.

IMPORTANTE: Este patrón es puramente visual y estático. No realiza llamadas a API ni gestiona datos de negocio.
