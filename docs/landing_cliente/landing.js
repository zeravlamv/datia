/* =============================================
   DATIA — Landing Cliente · landing.js
   ============================================= */

const SCREENSHOTS = [
    {
        file: 'Captura1.JPG',
        tag: 'Inteligencia Artificial',
        title: 'Asistente IA Conversacional',
        desc: 'Interactúa con tu negocio a través del lenguaje natural. Haz cualquier pregunta sobre ventas, costes o clientes y obtén respuestas precisas en segundos, directamente de tus datos reales. Sin tecnicismos, sin esperas.'
    },
    {
        file: 'Captura2.JPG',
        tag: 'Financiera',
        title: 'Dashboard Financiero Completo',
        desc: 'Visualiza ingresos, gastos y EBITDA mes a mes en un resumen ejecutivo claro. Indicadores de liquidez, margen, solvencia y endeudamiento actualizados en tiempo real para tomar decisiones con total seguridad.'
    },
    {
        file: 'Captura3.JPG',
        tag: 'Estrategia',
        title: 'Anatomía de la Utilidad',
        desc: 'Descompone visualmente el beneficio de tu empresa: ¿cuánto va a costes de ventas, gastos administrativos o impuestos? Compara ejercicios de un vistazo y detecta dónde se pierde (o se gana) rentabilidad.'
    },
    {
        file: 'Captura4.JPG',
        tag: 'Histórico & Tendencias',
        title: 'Evolución Financiera Interactiva',
        desc: 'Analiza la tendencia de ingresos, gastos y resultado neto desde 2022 hasta hoy en un gráfico multianual interactivo. Filtra por periodos, amplía rangos y detecta estacionalidades o cambios de ciclo en tu negocio.'
    },
    {
        file: 'Captura5.JPG',
        tag: 'IA Predictiva',
        title: 'Predicción Financiera con IA',
        desc: 'Proyecta los próximos meses con escenarios configurables: ajusta cobros anticipados, diferimiento de pagos o probabilidad de impago. La IA genera un informe profesional de tesorería y riesgo de liquidez de forma automática.'
    },
    {
        file: 'Captura6.JPG',
        tag: 'Acceso Móvil',
        title: 'Vista Móvil Personalizable',
        desc: 'Configura qué métricas quieres ver en tu móvil: ventas, compras, financiera… arrastra y ordena los widgets desde el escritorio y accede a tu cuadro de mando siempre actualizado desde cualquier dispositivo.'
    },
    {
        file: 'Captura7.JPG',
        tag: 'Inteligencia Artificial',
        title: 'Análisis IA con Informes Detallados',
        desc: 'Pregunta un resumen anual y la IA genera un diagnóstico completo: situación financiera, eficiencia de compras, posición de mercado, top clientes y recomendaciones estratégicas. Todo con gráficos comparativos automáticos.'
    },
    {
        file: 'Captura8.JPG',
        tag: 'Dashboard Personal',
        title: 'Panel CBAGES — Tu Cuadro Personal',
        desc: 'Crea tu propio panel con los KPIs que más te importan. Añade métricas de ventas, compras o existencias con un clic, ordénalas a tu gusto y tenlas siempre disponibles en tu vista favorita.'
    },
    {
        file: 'Captura9.JPG',
        tag: 'Tesorería',
        title: 'Control de Tesorería en Tiempo Real',
        desc: 'Monitoriza pendiente de cobro, impagados, días de cobro y pago, saldos bancarios y posición con proveedores. Gráficos comparativos de ingresos vs. gastos para anticipar tensiones de tesorería antes de que ocurran.'
    },
    {
        file: 'Captura10.JPG',
        tag: 'Presupuestos',
        title: 'Gestión de Presupuestos por Cuenta',
        desc: 'Define objetivos anuales cuenta a cuenta, genera presupuestos con ajuste porcentual automático y compara Real vs. Presupuesto mes a mes. Exporta en árbol o en grid y detecta desviaciones al instante.'
    },
    {
        file: 'Captura11.JPG',
        tag: 'Historial IA',
        title: 'Histórico de Consultas IA',
        desc: 'Guarda tus análisis favoritos y vuelve a ejecutarlos en cualquier momento con los datos más recientes. Ninguna consulta se vuelve a hacer desde cero: reutiliza, actualiza y comparte informes ya estructurados.'
    },
    {
        file: 'Captura12.JPG',
        tag: 'Informes IA',
        title: 'Informe Ejecutivo de Ventas Semestral',
        desc: 'El motor IA sintetiza automáticamente los datos de ventas en un informe estructurado: resumen ejecutivo, hallazgos clave, ticket medio por mes y clientes destacados. Listo para presentar a dirección sin ningún trabajo manual.'
    }
];

const IMG_BASE = '../../datia_pro/';

let currentIdx = 0;

function buildGallery() {
    const grid = document.getElementById('gallery-grid');
    if (!grid) return;
    SCREENSHOTS.forEach((s, i) => {
        const card = document.createElement('div');
        card.className = 'gallery-card';
        card.setAttribute('data-idx', i);
        card.innerHTML = `
      <div class="gallery-card-img">
        <img src="${IMG_BASE}${s.file}" alt="${s.title}" loading="lazy">
        <div class="gallery-card-overlay">
          <div class="gallery-card-overlay-icon">&#x2B0C;</div>
        </div>
      </div>
      <div class="gallery-card-body">
        <span class="gallery-card-tag">${s.tag}</span>
        <div class="gallery-card-title">${s.title}</div>
        <div class="gallery-card-desc">${s.desc}</div>
      </div>
    `;
        card.addEventListener('click', () => openLightbox(i));
        grid.appendChild(card);
    });
}

function openLightbox(idx) {
    currentIdx = idx;
    updateLightbox();
    const lb = document.getElementById('lightbox');
    lb.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lb = document.getElementById('lightbox');
    lb.classList.remove('active');
    document.body.style.overflow = '';
}

function updateLightbox() {
    const s = SCREENSHOTS[currentIdx];
    document.getElementById('lb-img').src = IMG_BASE + s.file;
    document.getElementById('lb-img').alt = s.title;
    document.getElementById('lb-tag').textContent = s.tag;
    document.getElementById('lb-title').textContent = s.title;
    document.getElementById('lb-desc').textContent = s.desc;
    document.getElementById('lb-counter').textContent = `${currentIdx + 1} / ${SCREENSHOTS.length}`;
}

function lbPrev() {
    currentIdx = (currentIdx - 1 + SCREENSHOTS.length) % SCREENSHOTS.length;
    updateLightbox();
}

function lbNext() {
    currentIdx = (currentIdx + 1) % SCREENSHOTS.length;
    updateLightbox();
}

// Scroll reveal
function revealOnScroll() {
    const cards = document.querySelectorAll('.gallery-card, .feature-card');
    const io = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.style.opacity = '1';
                e.target.style.transform = 'translateY(0)';
                io.unobserve(e.target);
            }
        });
    }, { threshold: 0.1 });
    cards.forEach(c => {
        c.style.opacity = '0';
        c.style.transform = 'translateY(24px)';
        c.style.transition = 'opacity 0.5s ease, transform 0.5s ease, border-color 0.25s, box-shadow 0.25s';
        io.observe(c);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    buildGallery();
    revealOnScroll();

    // Lightbox events
    document.getElementById('lb-close').addEventListener('click', closeLightbox);
    document.getElementById('lb-prev').addEventListener('click', lbPrev);
    document.getElementById('lb-next').addEventListener('click', lbNext);
    document.getElementById('lightbox').addEventListener('click', (e) => {
        if (e.target === document.getElementById('lightbox')) closeLightbox();
    });

    // Keyboard navigation
    document.addEventListener('keydown', (e) => {
        const lb = document.getElementById('lightbox');
        if (!lb.classList.contains('active')) return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') lbPrev();
        if (e.key === 'ArrowRight') lbNext();
    });
});
