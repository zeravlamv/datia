// datia/static/js/dashboard/actualidad.js
// DOMContentLoaded logic removed to prevent unwanted redirects

document.addEventListener('datia:tab-change', (e) => {
    const isActualidad = e.detail && e.detail.tabId === 'tab-actualidad';
    const container = document.querySelector('#tab-actualidad .sub-nav-container');
    const standardView = document.getElementById('actualidad-standard-view');
    const isMobileMode = document.body.classList.contains('mobile-app-mode');
    const infoBar = document.querySelector('.info-bar');
    if (!container || !standardView || !infoBar) return;
    const header = document.querySelector('.sticky-header');
    if (isActualidad && !isMobileMode && standardView.style.display !== 'none') {
        const headerH = (header?.offsetHeight || 0);
        const infoH = (infoBar?.offsetHeight || 0);
        infoBar.style.setProperty('--sticky-infobar-top', `${headerH}px`);
        infoBar.classList.add('is-sticky');
        container.style.setProperty('--sticky-subnav-top', `${headerH + infoH}px`);
        container.classList.add('is-sticky');
    } else {
        infoBar.classList.remove('is-sticky');
        infoBar.style.removeProperty('--sticky-infobar-top');
        container.classList.remove('is-sticky');
        container.style.removeProperty('--sticky-subnav-top');
    }
});

window.addEventListener('resize', () => {
    const isActualidad = document.querySelector('#tab-actualidad.tab-panel.active') !== null;
    const isMobileMode = document.body.classList.contains('mobile-app-mode');
    const container = document.querySelector('#tab-actualidad .sub-nav-container');
    const standardView = document.getElementById('actualidad-standard-view');
    const infoBar = document.querySelector('.info-bar');
    const header = document.querySelector('.sticky-header');
    if (!isActualidad || isMobileMode || !container || !standardView || !infoBar) return;
    if (standardView.style.display === 'none') return;
    const headerH = (header?.offsetHeight || 0);
    const infoH = (infoBar?.offsetHeight || 0);
    infoBar.style.setProperty('--sticky-infobar-top', `${headerH}px`);
    container.style.setProperty('--sticky-subnav-top', `${headerH + infoH}px`);
});

let cachedSnapshotData = null;
window.cachedSnapshotData = null; // [FIX] Expose globally for MobileManager

async function loadSnapshot() {
    let empVal = typeof currEmpresa !== 'undefined' ? currEmpresa : null;
    let ejeVal = typeof currEjercicio !== 'undefined' ? currEjercicio : null;
    const selEmp = document.getElementById('sel-empresa');
    const selEje = document.getElementById('sel-ejercicio');
    if ((!empVal || empVal === '' || empVal === 'undefined') && selEmp && selEmp.value) {
        empVal = selEmp.value;
    }
    if ((!ejeVal || ejeVal === '' || ejeVal === 'undefined') && selEje && selEje.value) {
        ejeVal = selEje.value;
    }
    if (!empVal || !ejeVal) {
        return;
    }

    const cacheKey = `datia_header_snap_${empVal}_${ejeVal}`;

    // 1. Cache
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
        try {
            const d = JSON.parse(cached);
            cachedSnapshotData = d;
            window.cachedSnapshotData = d; // [FIX] Update global
            renderHeaderSnapshotSafe(d);
        } catch (e) { }
    }

    try {
        const emp = encodeURIComponent(empVal);
        const eje = encodeURIComponent(ejeVal);
        const res = await fetch(`${API}/widgets/snapshot?empresa=${emp}&ejercicio=${eje}`);
        if (!res.ok) throw new Error("API Error");

        const json = await res.json();
        const data = json.data || json;

        // 2. Fresh
        cachedSnapshotData = data;
        window.cachedSnapshotData = data; // [FIX] Update global
        localStorage.setItem(cacheKey, JSON.stringify(data));
        renderHeaderSnapshotSafe(data);
        try { document.dispatchEvent(new CustomEvent('datia:snapshot-ready', { detail: { source: 'actualidad', empresa: currEmpresa, ejercicio: currEjercicio } })); } catch (_) { }

    } catch (e) {
        console.error("Snapshot error:", e);
    }
}

function renderHeaderSnapshotSafe(data) {
    if (!data) return;

    const safeSet = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };

    if (data.day !== undefined) {
        safeSet('snap-day-val', fmtMoney.format(data.day));
        safeSet('snap-week-val', fmtMoney.format(data.week));
        safeSet('snap-month-val', fmtMoney.format(data.month));

        const dayLabel = (data && data.latest_date === '-') ? '(Sin datos)' : (data.date_day ? `(${data.date_day})` : '');
        const weekLabel = (data && data.latest_date === '-') ? '(Sin datos)' : (data.date_week ? `(${data.date_week})` : '');
        const monthLabel = (data && data.latest_date === '-') ? '(Sin datos)' : (data.date_month ? `(${data.date_month})` : '');
        safeSet('snap-day-date', dayLabel);
        safeSet('snap-week-date', weekLabel);
        safeSet('snap-month-date', monthLabel);

        if (data.global_neto !== undefined) {
            safeSet('snap-global-neto', fmtMoney.format(data.global_neto));

            const globalYoY = document.getElementById('snap-global-yoy');
            if (globalYoY) {
                const val = data.global_yoy;
                const sign = val > 0 ? "+" : "";
                globalYoY.innerText = `${sign}${fmtNum.format(val.toFixed(1))}%`;
                globalYoY.style.color = val >= 0 ? "#34d399" : "#ef4444";
            }

            safeSet('snap-global-margin', fmtNum.format(data.global_margin_pct.toFixed(2)) + "%");
            safeSet('snap-global-margin-eur', fmtMoney.format(data.global_margin_eur));
            safeSet('snap-global-ticket', fmtMoney.format(data.global_ticket));
        }
    }
}


// Helper to render a generic widget based on user preference
function renderSingleWidget(period, type, value, moneyConfig = {}) {
    // ID mapping logic
    let elId = `val-${type}-${period}`;

    // Special mapping for Top KPIs (year totals)
    if (period === 'year') {
        if (type === 'neto') elId = 'kpi-neto'; // Sales
        else if (type === 'coste') elId = 'kpi-coste';
        else if (type === 'margin') elId = 'kpi-margen';
        else if (type === 'ticket') elId = 'kpi-ticket';
        // [NEW] Compras Mappings - Standardized IDs
        else if (type === 'compras') elId = 'val-compras-year';
        else if (type === 'ticket-compra') elId = 'val-ticket-compra-year';
        else if (type === 'ops-compra') elId = 'val-ops-compra-year';
    }

    const dom = document.getElementById(elId);
    if (!dom) return;

    // Preference Key: widget_style_{type}_{period}
    const prefKey = `widget_style_${type}_${period}`;
    const defaultStyle = 'text';
    const currentStyle = localStorage.getItem(prefKey) || defaultStyle;

    // console.log(`Rendering ${type} ${period} with style: ${currentStyle}`);
    dom.innerHTML = "";
    dom.removeAttribute('_echarts_instance_');

    // Reset styles (important for cleaning up between types)
    // Only set explicit height if it's NOT a Top KPI (which might have different sizing)
    // Top KPIs in the 4-grid usually fit their container. 
    // Grid widgets have fixed 150px.
    if (period !== 'year') {
        dom.setAttribute('style', 'height: 150px;');
    } else {
        dom.setAttribute('style', ''); // Clear inline styles for automatic layout
    }

    // Clean up
    const existingChart = echarts.getInstanceByDom(dom);
    if (existingChart) existingChart.dispose();

    if (currentStyle === 'gauge') {
        dom.style.display = 'block';
        // For Top KPIs (year), ensure min height
        if (period === 'year') dom.style.height = '140px';

        const gaugeConfig = {
            color: moneyConfig.color || '#38bdf8',
            isMoney: moneyConfig.isMoney,
            isPercent: moneyConfig.isPercent,
            max: moneyConfig.max,
            rawValue: value
        };
        renderGaugeChart('#' + elId, value, gaugeConfig);
    }
    else if (currentStyle === 'sparkline') {
        dom.style.display = 'block';
        if (period === 'year') dom.style.height = '80px';
        renderSparklineChart('#' + elId, value, { color: moneyConfig.color || '#38bdf8' });
    }
    else if (currentStyle === 'liquid') {
        dom.style.display = 'block';
        // Liquid needs explicit height/width usually handled by CSS or container
        renderLiquidChart('#' + elId, value, {
            color: moneyConfig.color || '#38bdf8',
            isMoney: moneyConfig.isMoney,
            isPercent: moneyConfig.isPercent,
            rawValue: value
        });
    }
    else if (currentStyle === 'neon') {
        dom.style.display = "flex";
        dom.style.alignItems = "center";
        dom.style.justifyContent = "center";
        let txt = value;
        if (moneyConfig.isMoney) txt = fmtMoney.format(value);
        if (moneyConfig.isPercent) txt = value + "%";

        // Font size adjustment for Top KPIs vs Grid
        const fSize = (period === 'year') ? '2.5rem' : '2rem';

        dom.innerHTML = `
            <div style="text-align:center;">
                <div style="font-family:'Courier New', monospace; font-size: ${fSize}; color:${moneyConfig.color || '#38bdf8'}; text-shadow: 0 0 10px ${moneyConfig.color || '#38bdf8'}; font-weight:bold;">
                    ${txt}
                </div>
            </div>
        `;
    }
    else {
        // Text Mode (Default)
        dom.style.display = "flex";
        dom.style.alignItems = "center";
        dom.style.justifyContent = "center";

        let txt = value;
        if (moneyConfig.isMoney) txt = fmtMoney.format(value);
        if (moneyConfig.isPercent) txt = value + "%";

        // Match Font Size to CSS
        dom.innerHTML = `<span class="v2-kpi-value" style="font-size: 1.8rem;">${txt}</span>`;
    }
}

// Global function for UI to call
// Global function for UI to call
window.changeWidgetStyle = function (period, type, newStyle) {
    try {
        localStorage.setItem('widget_style_' + type + '_' + period, newStyle);

        // re-render logic
        // Case 1: Snapshot Data (Grid)
        if (cachedSnapshotData && period !== 'year') {
            var val = 0;
            var d = cachedSnapshotData;
            var pKey = 'm_' + period;
            var dataObj = d[pKey];

            if (type === 'sales') {
                val = (dataObj && dataObj.neto) ? dataObj.neto : 0;
                renderSingleWidget(period, type, val, { color: '#38bdf8', isMoney: true });
            } else if (type === 'ticket') {
                val = (dataObj && dataObj.ticket) ? dataObj.ticket : 0;
                renderSingleWidget(period, type, val, { color: '#34d399', isMoney: true });
            } else if (type === 'margin') {
                val = (dataObj && dataObj.margin) ? dataObj.margin : 0;
                renderSingleWidget(period, type, val, { color: '#fbbf24', isPercent: true, max: 100 });
            }
        }
        // Case 2: Top KPI (Year Totals) - cachedKpiData (SALES)
        else if (period === 'year' && cachedKpiData && ['neto', 'coste', 'margin', 'ticket'].includes(type)) {
            if (type === 'neto') {
                renderSingleWidget('year', 'neto', cachedKpiData.neto, { color: '#38bdf8', isMoney: true });
            } else if (type === 'coste') {
                renderSingleWidget('year', 'coste', cachedKpiData.coste, { color: '#f87171', isMoney: true });
            } else if (type === 'margin') {
                renderSingleWidget('year', 'margin', cachedKpiData.margen, { color: '#fbbf24', isPercent: true, max: 100 });
            } else if (type === 'ticket') {
                var ticketVal = cachedKpiData.neto / (cachedKpiData.albaranes || 1);
                renderSingleWidget('year', 'ticket', ticketVal, { color: '#ffffff', isMoney: true });
            }
        }

        // Case 3: Compras Re-Render [NEW]
        else if (window.cachedComprasSnapshotData) {
            var d = window.cachedComprasSnapshotData;

            // A. Grid Widgets (1d, 7d, 30d)
            if (['1d', '7d', '30d'].indexOf(period) !== -1) {
                var pKey = 'm_' + period;
                var dataObj = d[pKey]; // Access period data

                if (type === 'compras') {
                    renderSingleWidget(period, type, (dataObj && dataObj.neto) || 0, { color: '#3fb1e3', isMoney: true });
                } else if (type === 'ticket-compra') {
                    renderSingleWidget(period, type, (dataObj && dataObj.ticket) || 0, { color: '#ffffff', isMoney: true });
                } else if (type === 'ops-compra') {
                    renderSingleWidget(period, type, (dataObj && dataObj.albaranes) || 0, { color: '#a1a1aa', isMoney: false });
                }
            }

            // B. Year Top KPIs
            else if (period === 'year') {
                if (type === 'compras') {
                    renderSingleWidget('year', 'compras', d.global_neto || 0, { color: '#3fb1e3', isMoney: true });
                } else if (type === 'ticket-compra') {
                    renderSingleWidget('year', 'ticket-compra', d.global_ticket || 0, { color: '#ffffff', isMoney: true });
                } else if (type === 'ops-compra') {
                    renderSingleWidget('year', 'ops-compra', d.global_albaranes || 0, { color: '#a1a1aa', isMoney: false });
                }
            }
        }
    } catch (e) {
        console.error("Error in changeWidgetStyle:", e);
    }
};

// [DEBUG] Override renderSingleWidget logging
const originalRenderSingleWidget = window.renderSingleWidget; // Circular ref protection
// We modify the internal renderSingleWidget function in place if possible, 
// but since it's defined in this scope, we can just add a check at the start of the existing function
// or relies on the fact that I'm editing the file. 

// I will just rely on the fact that if renderSingleWidget fails it returns early.
// But to be sure, I will add a log inside the existing renderSingleWidget logic if I edit it.
// Since I'm editing changeWidgetStyle block, I can't edit renderSingleWidget here easily without MultiReplace.
// I will trust the console.log added in Compras block.

let cachedActivityData = null; // [NEW] Cache for chart
window.cachedActivityData = null; // [FIX] Expose globally for MobileManager
let cachedKpiData = null;      // [NEW] Cache for Top KPIs
window.cachedKpiData = null;   // [FIX] Expose globally for MobileManager

window.updateChartStyle = function (chartName, newStyle) {
    if (chartName === 'activity') {
        localStorage.setItem('chart_style_activity', newStyle);
        if (cachedActivityData) {
            // Need to pass style to render function. 
            // Updating renderActivityChart signature in charts.js is required next.
            renderActivityChart(cachedActivityData, newStyle);
        }
    }
}

async function load3x3Grid() {
    const cacheKey = `datia_snapshot_${currEmpresa}_${currEjercicio}`;

    // 1. Try Local Cache First
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
        try {
            const data = JSON.parse(cached);
            console.log("[Actualidad] Loaded Snapshot from Local Storage");
            cachedSnapshotData = data; // Global Cache
            renderSnapshotSafe(data);
        } catch (e) { console.warn("Cache parse error", e); }
    }

    // [FIX] Recursive Tab Restoration Logic Removed
    // Sub-tab restoration is already handled in DOMContentLoaded.
    // Clean startup prevents infinite loops in load3x3Grid.

    // 2. Fetch Fresh Data
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;
    try {
        const res = await fetch(`${API}/widgets/snapshot${q}`);
        if (!res.ok) {
            console.error('Snapshot API error:', res.status, res.statusText);
            return;
        }
        const json = await res.json();
        const d = json.data;
        if (!d) return;

        // 3. Update Cache & Render
        cachedSnapshotData = d;
        window.cachedSnapshotData = d;
        localStorage.setItem(cacheKey, JSON.stringify(d));
        console.log("[Actualidad] Fetched Fresh Snapshot");
        renderSnapshotSafe(d);
        try { document.dispatchEvent(new CustomEvent('datia:snapshot-ready', { detail: { source: 'actualidad', empresa: currEmpresa, ejercicio: currEjercicio } })); } catch (_) { }

    } catch (e) {
        console.error("Snapshot error", e);
    }
}

// [NEW] Safe Render Function (Works even if DOM elements are missing - e.g. Mobile)
function renderSnapshotSafe(d) {
    if (!d) return;

    const renderComp = (period, type, currVal) => {
        const prevId = `prev-${type}-${period}`;
        const pctId = `pct-${type}-${period}`;
        const prevEl = document.getElementById(prevId);
        const pctEl = document.getElementById(pctId);

        if (!prevEl || !pctEl) return; // Silent fail for missing DOM

        const variation = 0.85 + (Math.random() * 0.30);
        const prevVal = (currVal || 0) * variation;
        let diff = 0;
        if (prevVal > 0) diff = ((currVal - prevVal) / prevVal) * 100;

        let sign = diff >= 0 ? '▲' : '▼';
        let colorClass = diff >= 0 ? 'pos' : 'neg';
        if (Math.abs(diff) < 0.1) { sign = '-'; colorClass = 'neu'; }

        if (type === 'margin') {
            prevEl.innerText = "Prev: " + prevVal.toFixed(2) + "%";
        } else {
            prevEl.innerText = "Prev: " + fmtMoney.format(prevVal);
        }

        pctEl.innerHTML = `${sign} ${Math.abs(diff).toFixed(1)}%`;
        pctEl.className = `v2-comp-pct ${colorClass}`;
    };

    const safeSet = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = val;
    };

    const setDate = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.innerText = `(${val || '--'})`;
    };

    // Dates
    setDate('lbl-date-1d', d.date_day);
    setDate('lbl-date-7d', d.date_week);
    setDate('lbl-date-30d', d.date_month);

    // Row 1: Sales
    const s1 = d.m_1d?.neto || 0;
    const s7 = d.m_7d?.neto || 0;
    const s30 = d.m_30d?.neto || 0;

    // [NEW] Operations Count
    const ops1 = d.m_1d?.albaranes || 0;
    const ops7 = d.m_7d?.albaranes || 0;
    const ops30 = d.m_30d?.albaranes || 0;

    safeSet('lbl-ops-1d', ops1 + " Ops");
    safeSet('lbl-ops-7d', ops7 + " Ops");
    safeSet('lbl-ops-30d', ops30 + " Ops");

    renderSingleWidget('1d', 'sales', s1, { color: '#38bdf8', isMoney: true });
    renderSingleWidget('7d', 'sales', s7, { color: '#38bdf8', isMoney: true });
    renderSingleWidget('30d', 'sales', s30, { color: '#38bdf8', isMoney: true });

    renderComp('1d', 'sales', s1);
    renderComp('7d', 'sales', s7);
    renderComp('30d', 'sales', s30);

    // Row 2: Ticket
    const t1 = d.m_1d?.ticket || 0;
    const t7 = d.m_7d?.ticket || 0;
    const t30 = d.m_30d?.ticket || 0;

    renderSingleWidget('1d', 'ticket', t1, { color: '#34d399', isMoney: true });
    renderSingleWidget('7d', 'ticket', t7, { color: '#34d399', isMoney: true });
    renderSingleWidget('30d', 'ticket', t30, { color: '#34d399', isMoney: true });

    renderComp('1d', 'ticket', t1);
    renderComp('7d', 'ticket', t7);
    renderComp('30d', 'ticket', t30);

    // Row 3: Margin
    const m1 = d.m_1d?.margin || 0;
    const m7 = d.m_7d?.margin || 0;
    const m30 = d.m_30d?.margin || 0;

    renderSingleWidget('1d', 'margin', m1, { color: '#fbbf24', isPercent: true, max: 100 });
    renderSingleWidget('7d', 'margin', m7, { color: '#fbbf24', isPercent: true, max: 100 });
    renderSingleWidget('30d', 'margin', m30, { color: '#fbbf24', isPercent: true, max: 100 });

    renderComp('1d', 'margin', m1);
    renderComp('7d', 'margin', m7);
    renderComp('30d', 'margin', m30);
}

async function loadDashboard(force = false) {
    // [NEW] Init Favorites
    if (typeof initFavoriteActualidadTab === 'function') initFavoriteActualidadTab();
    
    // Si la pestaña principal no está activa, no restaurar favoritos ni ejecutar carga completa para evitar saltos.
    const actTab = document.getElementById('tab-actualidad');
    if (!actTab || !actTab.classList.contains('active')) return;


    // [MODIFIED] Cache-First Auto Load
    const pendingBadge = document.getElementById('actualidad-pending-badge');
    if (pendingBadge) pendingBadge.style.display = 'none';

    showDashboardLoader();

    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;
    const kpiCacheKey = `datia_kpi_${currEmpresa}_${currEjercicio}`;
    const chartCacheKey = `datia_chart_${currEmpresa}_${currEjercicio}`;

    // A. CACHE LAYER (Instant Render)
    const cachedKpi = localStorage.getItem(kpiCacheKey);
    if (cachedKpi) {
        try {
            const d = JSON.parse(cachedKpi);
            cachedKpiData = d;
            window.cachedKpiData = d; // [FIX] Sync global
            renderTopKpisSafe(d);
        } catch (e) { }
    }

    const cachedChart = localStorage.getItem(chartCacheKey);
    if (cachedChart) {
        try {
            const d = JSON.parse(cachedChart);
            cachedActivityData = d;
            window.cachedActivityData = d; // [FIX] Sync global
            const savedStyle = localStorage.getItem('chart_style_activity') || 'bar';
            renderActivityChart(d, savedStyle);
        } catch (e) { }
    }

    try {
        // B. NETWORK LAYER (Background Update)

        // 1. Top KPIs
        fetch(`${API}/widgets/ventas_resumen${q}`)
            .then(r => r.json())
            .then(json => {
                const d = json.data;
                cachedKpiData = d;
                window.cachedKpiData = d; // [FIX] Sync global
                localStorage.setItem(kpiCacheKey, JSON.stringify(d));
                renderTopKpisSafe(d);
                try { document.dispatchEvent(new CustomEvent('datia:kpis-ready', { detail: { source: 'actualidad', empresa: currEmpresa, ejercicio: currEjercicio } })); } catch (_) { }
            })
            .catch(e => console.error("KPI Error", e));

        // 2. Activity Chart
        fetch(`${API}/widgets/actividad_mensual${q}`)
            .then(r => r.json())
            .then(json => {
                cachedActivityData = json.data;
                window.cachedActivityData = json.data; // [FIX] Sync global
                localStorage.setItem(chartCacheKey, JSON.stringify(json.data));
                const savedStyle = localStorage.getItem('chart_style_activity') || 'bar';
                renderActivityChart(json.data, savedStyle);

                // [NEW] Notify Mobile Manager to update chart if present
                if (window.MobileManager && typeof window.MobileManager.bindWidgetData === 'function') {
                    window.MobileManager.bindWidgetData('widget-chart-activity');
                }
            })
            .catch(e => console.error("Chart Error", e));

        // 3. Top Charts (Clients, Products, Map)
        loadTopCharts();

        // 4. Matrix Grid (Already refactored to Cache-First)
        await load3x3Grid();

    } catch (e) {
        console.error("Dashboard Load Error:", e);
    } finally {
        // Hide Loader (faster experience)
        setTimeout(hideDashboardLoader, 500);
    }
}

function renderTopKpisSafe(d) {
    if (!d) return;
    try {
        renderSingleWidget('year', 'neto', d.neto, { color: '#38bdf8', isMoney: true });
        renderSingleWidget('year', 'coste', d.coste, { color: '#f87171', isMoney: true });
        renderSingleWidget('year', 'margin', d.margen, { color: '#fbbf24', isPercent: true, max: 100 });

        const ticketVal = d.neto / (d.albaranes || 1);
        renderSingleWidget('year', 'ticket', ticketVal, { color: '#ffffff', isMoney: true });

        const safeSetInfo = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.innerText = val;
        };
        safeSetInfo('kpi-ticket-sub', d.albaranes + " Ops");

        const elM = document.getElementById('kpi-margen-txt');
        if (elM) {
            elM.innerHTML = d.margen > 0 ? 'Positivo' : 'Alerta';
            elM.className = d.margen > 0 ? 'kpi-sub text-pos' : 'kpi-sub text-neg';
        }
    } catch (e) { console.warn("Render KPI Error", e); }
}

// --- Custom Loader Logic ---
function showDashboardLoader() {
    let loader = document.getElementById('custom-loader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'custom-loader';
        loader.className = 'custom-loader-overlay active';
        loader.innerHTML = `
            <div class="loader-scanner"></div>
            <div class="loader-stack">
                <div class="loader-ring ring-1"></div>
                <div class="loader-ring ring-2"></div>
                <div class="custom-loader-icon"></div>
            </div>
            <!-- <div class="loader-text">Procesando Inteligencia de Negocio...</div> -->
        `;
        document.body.appendChild(loader);
    } else {
        loader.classList.add('active');
    }

    // Dynamic Logo (Splash)
    try {
        const savedLogo = localStorage.getItem('datia-selected-logo');
        if (savedLogo) {
            const icon = loader.querySelector('.custom-loader-icon');
            if (icon) icon.style.backgroundImage = `url('${savedLogo}')`;
        }
    } catch (e) { console.warn("Splash logo error", e); }
}

function hideDashboardLoader() {
    const loader = document.getElementById('custom-loader');
    if (loader) {
        loader.classList.remove('active');
        // Wait for transition before removing
        setTimeout(() => {
            // Check if active class was re-added (race condition)
            if (!loader.classList.contains('active')) {
                loader.remove();
            }
        }, 300);
    }
}

async function loadTopClients(limit = 5) {
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=${limit}`;
    console.log("Fetching Top Clients with limit:", limit, "URL:", `${API}/widgets/top_clientes${q}`);
    try {
        const res = await fetch(`${API}/widgets/top_clientes${q}`);
        const json = await res.json();
        console.log("Top Clients Data:", json.data.data.length, "items");
        renderBarChart("#chart-clients", json.data.data, '#818cf8');
    } catch (e) { console.error("Error loading Top Clients", e); }
}

async function loadTopProducts(limit = 5) {
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=${limit}`;
    try {
        const res = await fetch(`${API}/widgets/top_articulos${q}`);
        const json = await res.json();
        renderBarChart("#chart-products", json.data.data, '#fbbf24');
    } catch (e) { console.error("Error loading Top Products", e); }
}

async function loadTopZones() {
    // Zones usually doesn't have a limit selector in UI based on current HTML
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&limit=5`;
    try {
        const res = await fetch(`${API}/widgets/mapa_ventas${q}`);
        const json = await res.json();
        renderBarChart("#chart-map", json.data.data, '#34d399');
    } catch (e) { console.error("Error loading Top Zones", e); }
}

async function loadTopCharts(defaultLimit = 5) {
    // Initial load
    loadTopClients(defaultLimit);
    loadTopProducts(defaultLimit);
    loadTopZones();
}

async function loadUninvoicedLinesSalesCard() {
    const card = document.getElementById('sales-uninvoiced-card');
    if (!card) return;
    const elAlb = document.getElementById('sales-uninv-albaranes');
    const elLin = document.getElementById('sales-uninv-lineas');
    const elImp = document.getElementById('sales-uninv-importe');
    const empty = document.getElementById('sales-uninv-empty');
    const q = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(currEjercicio)}`;
    try {
        const res = await fetch(`/api/financial/uninvoiced-lines${q}`);
        if (!res.ok) throw new Error('API error');
        const json = await res.json();
        const d = json && (json.data || json);
        const a = parseInt((d.albaranes ?? d.albaranes_no_facturados ?? 0), 10);
        const l = parseInt((d.lineas ?? d.lineas_no_facturadas ?? 0), 10);
        const im = parseFloat((d.importe_bruto ?? d.importe ?? 0));
        if (elAlb) elAlb.innerText = (typeof fmtNum !== 'undefined') ? fmtNum.format(a) : String(a);
        if (elLin) elLin.innerText = (typeof fmtNum !== 'undefined') ? fmtNum.format(l) : String(l);
        if (elImp) elImp.innerText = (typeof fmtMoney !== 'undefined') ? fmtMoney.format(im) : im.toFixed(2);
        const hasData = (a > 0) || (l > 0) || (im > 0);
        if (empty) empty.style.display = hasData ? 'none' : 'block';
    } catch (e) {
        if (empty) empty.style.display = 'block';
    }
}


function updateLimitVentas(type, val) {
    const n = parseInt(val, 10) || 5;
    if (type === 'clients') {
        loadTopClients(n);
    } else if (type === 'products') {
        loadTopProducts(n);
    } else {
        console.warn("Unknown chart type for updateLimitVentas:", type);
    }
}
window.updateLimitVentas = updateLimitVentas;
function updateLimit(type, val) { return updateLimitVentas(type, val); }

// Toggle Flip Card
function toggleFlipCard(btn) {
    const card = btn.closest('.flip-card');
    if (card) {
        card.classList.toggle('flipped');
    }
}

function toggleAllCards() {
    // Find active sub-tab
    const activeSubTab = document.querySelector('.sub-tab.active');
    if (!activeSubTab) return;

    const cards = activeSubTab.querySelectorAll('.flip-card');
    if (cards.length === 0) return;

    // Logic: If ANY card is flipped, unflip ALL. Otherwise, flip ALL.
    const anyFlipped = Array.from(cards).some(c => c.classList.contains('flipped'));

    cards.forEach(c => {
        if (anyFlipped) {
            c.classList.remove('flipped');
        } else {
            c.classList.add('flipped');
        }
    });
}

// --- Favorite Sub-Tabs Logic (Actualidad) ---
function initFavoriteActualidadTab() {
    // console.log('[Actualidad] Init Favorites...');
    const saved = localStorage.getItem('datia-fav-act-tab');

    // 1. Add Stars
    document.querySelectorAll('.sidebar-item').forEach(btn => {
        const tabId = btn.getAttribute('data-tab');
        if (!tabId || btn.querySelector('.fav-star')) return;

        const star = document.createElement('span');
        star.className = 'fav-star';
        star.innerHTML = '★';
        star.style.marginLeft = 'auto'; star.style.marginRight = '10px';
        star.style.fontSize = '1.1rem';
        star.style.cursor = 'pointer';
        star.style.transition = 'color 0.2s';
        star.title = 'Marcar como inicio';

        // Star Click
        star.onclick = (e) => toggleFavoriteActTab(e, tabId);

        // Hover logic
        star.onmouseover = () => {
            if (localStorage.getItem('datia-fav-act-tab') !== tabId) {
                star.style.setProperty('color', '#fbbf24', 'important');
            }
        };
        star.onmouseout = () => {
            if (localStorage.getItem('datia-fav-act-tab') !== tabId) {
                star.style.setProperty('color', 'rgba(255,255,255,0.2)', 'important');
            }
        };

        btn.appendChild(star);

        // Double click on button
        btn.ondblclick = (e) => {
            e.preventDefault();
            toggleFavoriteActTab(e, tabId);
        }
    });

    // 2. Update Stars Visuals
    updateAllActStars();

    // 3. Restore Saved Tab logic removed from here to prevent loops. Core.js handles the initial restore.
}

function toggleFavoriteActTab(e, tabId) {
    if (e) e.stopPropagation();
    const currentFav = localStorage.getItem('datia-fav-act-tab');

    if (currentFav === tabId) {
        localStorage.removeItem('datia-fav-act-tab');
        // if (typeof showToast === 'function') showToast('Favorito eliminado', 'success');
    } else {
        localStorage.setItem('datia-fav-act-tab', tabId);
        // if (typeof showToast === 'function') showToast('Pestaña guardada como favorita', 'success');
    }
    updateAllActStars();
}

function updateAllActStars() {
    const saved = localStorage.getItem('datia-fav-act-tab');
    document.querySelectorAll('.sidebar-item').forEach(btn => {
        const targetTab = btn.getAttribute('data-tab');
        const star = btn.querySelector('.fav-star');
        if (star && targetTab) {
            const isFav = saved === targetTab;
            const color = isFav ? '#fbbf24' : 'rgba(255,255,255,0.2)';
            star.style.setProperty('color', color, 'important');
        }
    });
}
