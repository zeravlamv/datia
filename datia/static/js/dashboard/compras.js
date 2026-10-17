// Logic for "Actualidad - Compras" Tab
// Mirrors actualidad.js but for Purchase data

// Compras Dashboard Logic
console.log("Compras Logic Loaded v2");
let _comprasSnapshotPromise = null;
let _isFetchingCompras = false;
let _comprasLastTs = 0;

async function loadComprasDashboard(force = false) {
    console.log("loadComprasDashboard() called");

    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;

    try {
        // 1. Snapshot (Grid 3x3 + Global KPIs)
        // Fetches /widgets/snapshot?kind=compras
        await loadSnapshotCompras();

        // 2. Activity Chart (Monthly)
        const resChart = await fetch(`${API}/widgets/actividad_mensual_compra${q}`);
        const jsonChart = await resChart.json();
        renderComprasActivityChart(jsonChart.data);

        // 3. Top Lists
        await loadTopProveedores();
        await loadTopArticulosCompra();
        await loadTopZonasCompra();

    } catch (e) {
        console.error("Error loading Compras Dashboard:", e);
        showToast("Error cargando datos de compras", "error");
    } finally {
        hideDashboardLoader();
    }
}

async function loadSnapshotCompras() {
    if (_comprasSnapshotPromise) return _comprasSnapshotPromise;
    const now = Date.now();
    if (_isFetchingCompras) return Promise.resolve(window.cachedComprasSnapshotData || {});
    if (_comprasLastTs && (now - _comprasLastTs) < 10000 && window.cachedComprasSnapshotData) return Promise.resolve(window.cachedComprasSnapshotData || {});
    _isFetchingCompras = true;
    _comprasSnapshotPromise = (async () => {
        try {
            const d = await (typeof window.fetchSnapshot === 'function'
                ? window.fetchSnapshot('compras', currEmpresa, currEjercicio, 10000)
                : (async () => {
                    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&kind=compras`;
                    const res = await fetch(`${API}/widgets/snapshot${q}`);
                    const json = await res.json();
                    return json && (json.data || json);
                })());
            window.cachedComprasSnapshotData = d || {};
        } finally {
            _isFetchingCompras = false;
            _comprasLastTs = Date.now();
            const result = window.cachedComprasSnapshotData || {};
            _comprasSnapshotPromise = null;
            return result;
        }
    })();
    await _comprasSnapshotPromise;
    const d = window.cachedComprasSnapshotData || {};

        // --- Helper to animate numbers ---
        const setVal = (id, val, formatting = 'money') => {
            const el = document.getElementById(id);
            if (!el) {
                // Silent fail or debug log
                return;
            }
            // Use existing logic for init
            el.innerText = formatting === 'money' ? fmtMoney.format(val) :
                formatting === 'int' ? fmtInt.format(val) : val;

            if (val < 0) el.style.color = '#f87171';
        };

        // --- Helper for Comparison (Mirroring actualidad.js) ---
        const renderComp = (period, type, currData) => {
            // IDs: prev-{type}-{period}, pct-{type}-{period}
            // type: compras | ticket-compra | ops
            // period: 1d | 7d | 30d

            let prevId, pctId, prevVal, pctVal;

            // Map types to data keys
            let dataKeyPrev = 'prev';
            let dataKeyPct = 'pct';

            if (type === 'ticket-compra') {
                dataKeyPrev = 'prev_ticket';
                dataKeyPct = 'pct_ticket';
            } else if (type === 'ops') {
                dataKeyPrev = 'prev_ops';
                dataKeyPct = 'pct_ops';
            }

            if (type === 'ops') {
                // For Ops, IDs are like 'prev-ops-1d' (no 'compra' suffix in some HTML lines? Check HTML)
                // HTML Check: 'prev-ops-1d', 'val-ops-compra-1d'. consistency check needed.
                // In tab_actualidad_compras.html: 
                // Row 3: id="val-ops-compra-1d", id="prev-ops-1d" (No pct for Ops in HTML? Let's check)
                // Checking HTML content again... 
                // HTML: <span class="v2-comp-val" id="prev-ops-1d">--</span> 
                // It seems NO PCT ID for Ops in HTML row 3. Only Prev.
                prevId = `prev-ops-${period}`;
                pctId = null; // No pct placeholder in HTML for ops
            } else {
                prevId = `prev-${type}-${period}`;
                pctId = `pct-${type}-${period}`;
            }

            prevVal = currData[dataKeyPrev];
            pctVal = currData[dataKeyPct];

            const prevEl = document.getElementById(prevId);
            const pctEl = pctId ? document.getElementById(pctId) : null;

            if (prevEl) {
                if (type === 'ops') {
                    prevEl.innerText = "Prev: " + fmtInt.format(prevVal);
                } else {
                    prevEl.innerText = "Prev: " + fmtMoney.format(prevVal);
                }
            }

            if (pctEl) {
                let sign = pctVal >= 0 ? '▲' : '▼';
                let colorClass = pctVal >= 0 ? 'pos' : 'neg'; // Blue/Green vs Red
                // For Purchases: Growth matches Blue logic in Datia (Activity) usually.
                // We keep generic pos/neg classes associated with Green/Red.

                if (Math.abs(pctVal) < 0.1) { sign = '-'; colorClass = 'neu'; }

                pctEl.innerHTML = `${sign} ${Math.abs(pctVal).toFixed(1)}%`;
                pctEl.className = `v2-comp-pct ${colorClass}`;
            }
        };

        // Render Function Removed: renderWithStyle (Replaced by renderWidgetSimple)
        // Force Values with Simple        // --- 1. Global KPIs (Year) ---
        // Force Values with Simple Render (No Smart/Gauge logic)
        renderWidgetSimple('val-compras-year', d.global_neto || 0, { color: '#3fb1e3', isMoney: true });
        renderWidgetSimple('val-ticket-compra-year', d.global_ticket || 0, { color: '#ffffff', isMoney: true });
        renderWidgetSimple('val-ops-compra-year', d.global_albaranes || 0, { color: '#a1a1aa', isMoney: false, suffix: ' Ops' });

        // Restore Proveedores (Simple Render is enough)
        renderWidgetSimple('val-kpi-proveedores', d.global_entities || 0, { color: '#f472b6', isMoney: false });

        // --- 2. Snapshot Grid (3x3) ---

        // --- 2. Snapshot Grid (3x3) ---

        // Initialize Data Objects safely
        const d1 = d.m_1d || { neto: 0, ticket: 0, albaranes: 0 };
        const d7 = d.m_7d || { neto: 0, ticket: 0, albaranes: 0 };
        const d30 = d.m_30d || { neto: 0, ticket: 0, albaranes: 0 };

        // Row 1: Compras (Neto)
        renderWidgetSimple('val-compras-1d', d1.neto || 0, { color: '#3fb1e3', isMoney: true });
        renderComp('1d', 'compras', d1);

        renderWidgetSimple('val-compras-7d', d7.neto || 0, { color: '#3fb1e3', isMoney: true });
        renderComp('7d', 'compras', d7);

        renderWidgetSimple('val-compras-30d', d30.neto || 0, { color: '#3fb1e3', isMoney: true });
        renderComp('30d', 'compras', d30);

        // Row 2: Ticket Medio
        renderWidgetSimple('val-ticket-compra-1d', d1.ticket || 0, { color: '#ffffff', isMoney: true });
        renderComp('1d', 'ticket-compra', d1);

        renderWidgetSimple('val-ticket-compra-7d', d7.ticket || 0, { color: '#ffffff', isMoney: true });
        renderComp('7d', 'ticket-compra', d7);

        renderWidgetSimple('val-ticket-compra-30d', d30.ticket || 0, { color: '#ffffff', isMoney: true });
        renderComp('30d', 'ticket-compra', d30);

        // Row 3: Operaciones (Albaranes)
        renderWidgetSimple('val-ops-compra-1d', d1.albaranes || 0, { color: '#a1a1aa', isMoney: false });
        renderComp('1d', 'ops', d1);

        renderWidgetSimple('val-ops-compra-7d', d7.albaranes || 0, { color: '#a1a1aa', isMoney: false });
        renderComp('7d', 'ops', d7);

        renderWidgetSimple('val-ops-compra-30d', d30.albaranes || 0, { color: '#a1a1aa', isMoney: false });
        renderComp('30d', 'ops', d30);



        // --- Dates Labels ---
        const setLabel = (id, text) => { const el = document.getElementById(id); if (el) el.innerText = text; };
        const lbl1 = (d.latest_date === '-') ? '(Sin datos)' : `(${d.date_day || '-'})`;
        const lbl7 = (d.latest_date === '-') ? '(Sin datos)' : `(${d.date_week || '-'})`;
        const lbl30 = (d.latest_date === '-') ? '(Sin datos)' : `(${d.date_month || '-'})`;
        setLabel('lbl-date-compra-1d', lbl1);
        setLabel('lbl-date-compra-7d', lbl7);
        setLabel('lbl-date-compra-30d', lbl30);

        // --- Status Badge ---
        const badge = document.getElementById('compras-pending-badge');
        if (d.latest_date !== '-') {
            // Logic to check staleness (e.g. > 1 day) TBD
            // For now assume sync is manual
        }

    return d;
}

async function loadTopZonasCompra(limit = 10) {
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=${limit}`;
    try {
        const res = await fetch(`${API}/widgets/mapa_compras${q}`);
        const json = await res.json();
        renderTopList('chart-top-zonas-compra', json.data.data, '#a78bfa'); // Purple
    } catch (e) { console.error("Error loading Top Zonas:", e); }
}

async function loadTopProveedores(limit = 5) {
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=${limit}`;
    const res = await fetch(`${API}/widgets/top_proveedores${q}`);
    const json = await res.json();
    renderTopList('chart-top-proveedores', json.data.data, '#f472b6'); // Pink
}

async function loadTopArticulosCompra(limit = 5) {
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=${limit}`;
    const res = await fetch(`${API}/widgets/top_articulos_compra${q}`);
    const json = await res.json();
    renderTopList('chart-top-articulos-compra', json.data.data, '#fbbf24'); // Yellow
}

function renderComprasActivityChart(data) {
    const dom = document.getElementById('chart-activity-compras');
    if (!dom) return;
    const allZero = Array.isArray(data.neto) && data.neto.every(v => (v || 0) === 0);
    if (allZero) {
        const inst = echarts.getInstanceByDom(dom);
        if (inst) inst.dispose();
        dom.innerText = 'Sin datos';
        return;
    }
    const chart = echarts.init(dom);

    const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
            type: 'category',
            data: data.labels,
            axisLine: { lineStyle: { color: '#52525b' } }
        },
        yAxis: {
            type: 'value',
            splitLine: { lineStyle: { color: '#27272a' } },
            axisLabel: { formatter: (value) => fmtMoneySimple.format(value) }
        },
        series: [
            {
                name: 'Compras',
                type: 'bar',
                data: data.neto,
                itemStyle: { color: '#38bdf8', borderRadius: [4, 4, 0, 0] },
                barMaxWidth: 40
            }
        ]
    };
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

// Reuse renderTopList logic (Generic)
// We define it here to be self-contained or verify availability
// If already defined in global scope by charts.js, good. Else define.
if (typeof renderTopList === 'undefined') {
    window.renderTopList = function (domId, data, color) {
        const dom = document.getElementById(domId);
        if (!dom) return;
        if (echarts.getInstanceByDom(dom)) {
            echarts.getInstanceByDom(dom).dispose();
        }
        const rowHeight = 44;
        const minHeight = 260;
        const calcHeight = Math.max(minHeight, (Array.isArray(data) ? data.length : 0) * rowHeight + 80);
        dom.style.height = calcHeight + 'px';
        try {
            const card = dom.closest('.flip-card');
            if (card) {
                const extra = 140;
                card.style.height = (calcHeight + extra) + 'px';
            }
        } catch (_) {}
        const chart = echarts.init(dom, null, { renderer: 'svg' });

        const sorted = Array.isArray(data) ? [...data].reverse() : [];
        const wrapLabel = (text, max = 28) => {
            const t = String(text || '');
            if (t.length <= max) return t;
            const idx = t.lastIndexOf(' ', max);
            const cut = idx > 0 ? idx : max;
            return t.slice(0, cut) + '\n' + t.slice(cut);
        };
        const categories = sorted.map(i => wrapLabel(i.nombre, 28));
        const values = sorted.map(i => i.neto);

        const option = {
            backgroundColor: 'transparent',
            tooltip: { trigger: 'axis', formatter: (params) => `${params[0].name}: ${fmtMoney.format(params[0].value)}` },
            grid: { left: '6%', right: '12%', bottom: '4%', top: '8%', containLabel: true },
            xAxis: { type: 'value', show: false },
            yAxis: {
                type: 'category',
                data: categories,
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: { color: '#a1a1aa', width: 220, overflow: 'break', lineHeight: 15, fontSize: 12 }
            },
            series: [{
                type: 'bar',
                data: values,
                itemStyle: { color: color, borderRadius: [0, 18, 18, 0] },
                label: { show: true, position: 'right', color: '#fff', formatter: (p) => fmtMoneySimple.format(p.value), distance: 10 },
                showBackground: true,
                backgroundStyle: { color: 'rgba(255, 255, 255, 0.02)', borderRadius: [0, 18, 18, 0] },
                animationDuration: 1000,
                animationEasing: 'elasticOut'
            }]
        };
        chart.setOption(option);
        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => chart.resize()).observe(dom);
        } else {
            window.addEventListener('resize', () => chart.resize());
        }
    }
} else {
    // If it exists, we stick to existing, or if we need custom overrides we rename ours.
    // Existing renderTopList in actuality might differ in selector handling. 
    // To be safe, I'll use existing one if it works, or just rely on this one.
}

window.updateLimitCompras = async function (type, limit) {
    const n = parseInt(limit, 10) || 5;
    const t = String(type || '').toLowerCase();
    if (t === 'proveedores') return await loadTopProveedores(n);
    if (t === 'articulos_compra' || t === 'articulos-compra') return await loadTopArticulosCompra(n);
    if (t === 'zonas_compra' || t === 'zonas-compra') return await loadTopZonasCompra(n);
}

// [NUEVO] Renderizador Inteligente: Elige entre Texto Simple (Robustez) y Gráfico (Estilo)
function renderWidgetSmart(period, type, val, config = {}, defaultStyle = 'text') {
    let styleToRender = localStorage.getItem(`widget_style_${type}_${period}`) || defaultStyle;

    // Mapeo de ID para verificar visibilidad
    let id = `val-${type}-${period}`;
    if (period === 'year') {
        // overrides si fuera necesario, pero val-compras-year funciona
    }
    const el = document.getElementById(id);

    // [AUTO-CORRECCIÓN DE VISIBILIDAD]
    // Si el elemento existe pero tiene ancho 0 (está oculto en una pestaña inactiva),
    // ECharts fallará estrepitosamente (0x0).
    // En este caso, FORZAMOS 'text' porque el renderizado DOM sí sobrevive a display:none.
    if (el && el.offsetWidth === 0 && styleToRender !== 'text') {
        // console.log(`[SmartRender] ${id} is hidden (width 0). Forcing TEXT mode fallback.`);
        styleToRender = 'text';
    }

    if (styleToRender === 'text') {
        // Opción A: Texto Puro (Indestructible)
        renderWidgetSimple(id, val, config);

        // Asegurar que el selector UI muestre 'text' si existe
        // Usamos timeout para no bloquear y esperar a que el DOM de selectores se pinte si es dinámico
        setTimeout(() => {
            const sel = document.querySelector(`select[onchange="changeWidgetStyle('${period}', '${type}', this.value)"]`);
            if (sel) sel.value = 'text';
        }, 0);
    } else {
        // Opción B: Gráfico (ECharts) vía changeWidgetStyle Global
        // Requiere que el dato esté en caché global (window.cachedComprasSnapshotData) o se pase
        if (window.changeWidgetStyle) {
            // Nota: changeWidgetStyle repinta usando cachedComprasSnapshotData.
            // Si acabamos de cargar datos, window.cachedComprasSnapshotData ya debería estar actualizado en loadSnapshotCompras.
            window.changeWidgetStyle(period, type, savedStyle);

            // Actualizar selector UI
            setTimeout(() => {
                const sel = document.querySelector(`select[onchange="changeWidgetStyle('${period}', '${type}', this.value)"]`);
                if (sel) sel.value = savedStyle;
            }, 0);
        } else {
            console.warn("changeWidgetStyle no disponible, fallback a simple");
            renderWidgetSimple(id, val, config);
        }
    }
}

// [NUEVO] Función genérica de renderizado manual indestructible para Widgets de Compras
function renderWidgetSimple(id, value, config = {}) {
    const el = document.getElementById(id);
    if (!el) {
        console.warn(`CRITICAL: Container ${id} NOT found.`);
        return;
    }

    // Limpieza agresiva de cualquier instancia previa de ECharts
    const instance = echarts.getInstanceByDom(el);
    if (instance) instance.dispose();
    el.removeAttribute('_echarts_instance_');
    el.innerHTML = '';

    // Forzar estilos CSS inline para asegurar visibilidad y consistencia
    el.style.display = 'flex';
    el.style.alignItems = 'center';
    el.style.justifyContent = 'center';
    el.style.height = '100%';
    el.style.minHeight = '120px'; // Minimo para asegurar visualización

    el.style.color = config.color || '#ffffff';
    el.style.fontSize = '2rem';
    el.style.fontWeight = 'bold';
    el.style.fontFamily = 'Inter, sans-serif';

    // Formateo
    let textVal = value;
    if (config.isMoney) {
        textVal = fmtMoney.format(value);
    } else {
        // Int Formatting
        textVal = fmtInt.format(value);
    }

    if (config.suffix) textVal += config.suffix;

    // Inyectar el texto directamente
    el.innerText = textVal;
}

// Expose
window.loadComprasDashboard = loadComprasDashboard;
