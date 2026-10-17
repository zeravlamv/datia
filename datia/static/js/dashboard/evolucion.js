/**
 * evolución.js - Lógica interactiva para la pestaña de Evolución Financiera
 * Basado en ECharts para animaciones fluidas y reactividad.
 */

(function () {
    let evolChart = null;
    let evolChartYear = null;
    let abortController = null; // Para cancelar peticiones anteriores
    let empresaAutoLoadArmed = false;
    function getCssVar(name, fallback) {
        try {
            const v = getComputedStyle(document.documentElement).getPropertyValue(name);
            return v && v.trim() ? v.trim() : fallback;
        } catch (_) {
            return fallback;
        }
    }
    const ACCENT = getCssVar('--accent', '#38bdf8');
    const ACCENT_SOFT = getCssVar('--accent-soft', 'rgba(56, 189, 248, 0.35)');
    const TEXT_MUTED = getCssVar('--text-muted', '#a1a1aa');

    // Función principal de inicialización
    function initEvolucion() {
        initYearSelects();
        bindReloadHooks();

        // Inicializamos gráficos y datos
        // NOTA: Usamos ResizeObserver en initCharts, así que no dependemos tanto del timeout
        setTimeout(() => {
            initCharts();
            loadAllData();
        }, 100);

        // Event listener para el botón de refresco
        const btn = document.getElementById('btn-refresh-evol');
        if (btn) {
            btn.onclick = loadAllData;
        }
    }

    // Rellenamos los selectores de años (predeterminados)
    function initYearSelects() {
        const startSelect = document.getElementById('evol-year-start');
        const endSelect = document.getElementById('evol-year-end');
        if (!startSelect || !endSelect) return;

        // Si ya tienen opciones, no reiniciamos
        if (startSelect.options.length > 0) return;

        const currentYear = (typeof currEjercicio !== 'undefined' && currEjercicio && !isNaN(currEjercicio)) ? parseInt(currEjercicio, 10) : new Date().getFullYear();
        const minYear = 2011;

        startSelect.innerHTML = '';
        endSelect.innerHTML = '';

        for (let y = currentYear; y >= minYear; y--) {
            startSelect.add(new Option(y, y));
            endSelect.add(new Option(y, y));
        }

        // OPTIMIZACIÓN: Rango inicial de 5 años para carga rápida
        startSelect.value = Math.max(minYear, currentYear - 4);
        endSelect.value = currentYear;
    }

    // Inicializamos los objetos ECharts con ResizeObserver
    function initCharts() {
        const chartDom = document.getElementById('evol-chart-main');
        const chartYearDom = document.getElementById('evol-chart-year');

        // 1. Inicialización Gráfico Mensual
        if (chartDom) {
            if (!evolChart) evolChart = echarts.init(chartDom);

            // Observer para redimensionar automáticamente cuando la pestaña se muestra
            const observer = new ResizeObserver(() => {
                if (evolChart) evolChart.resize();
            });
            observer.observe(chartDom);
        }

        // 2. Inicialización Gráfico Anual
        if (chartYearDom) {
            if (!evolChartYear) evolChartYear = echarts.init(chartYearDom);

            const observerYear = new ResizeObserver(() => {
                if (evolChartYear) evolChartYear.resize();
            });
            observerYear.observe(chartYearDom);
        }
    }

    // Carga orquestada de datos con Timeout y Abort
    async function loadAllData() {
        const startYear = document.getElementById('evol-year-start').value;
        const endYear = document.getElementById('evol-year-end').value;
        const empVal = getSafeEmpresa();
        if (!empVal) {
            toggleLoader('evol-loading', false);
            toggleLoader('evol-year-loading', false);
            return;
        }

        // Cancelar petición anterior si existe
        if (abortController) abortController.abort();
        abortController = new AbortController();
        const signal = abortController.signal;

        toggleLoader('evol-loading', true);
        toggleLoader('evol-year-loading', true);

        try {
            // Paralelizamos con timeout de seguridad (10s)
            const timeoutId = setTimeout(() => abortController.abort(), 10000);

            const [resMonth, resYear] = await Promise.all([
                fetchData(startYear, endYear, 'month', signal),
                fetchData(startYear, endYear, 'year', signal)
            ]);

            clearTimeout(timeoutId);

            if (resMonth) renderChart(resMonth);
            renderYearChart(resYear || []);

        } catch (err) {
            if (err.name === 'AbortError') {
                console.warn("Petición cancelada o timeout.");
            } else {
                console.error("Error global cargando datos:", err);
            }
        } finally {
            // Asegurar que los loaders se van SIEMPRE
            toggleLoader('evol-loading', false);
            toggleLoader('evol-year-loading', false);
        }
    }

    function bindReloadHooks() {
        if (empresaAutoLoadArmed) return;
        empresaAutoLoadArmed = true;
        document.addEventListener('datia:empresa-change', function () {
            setTimeout(function () { try { loadAllData(); } catch (e) { } }, 50);
        });
        document.addEventListener('datia:subtab-change', function (ev) {
            const id = ev && ev.detail ? ev.detail.subTabId : '';
            if (id === 'sub-evolucion') {
                setTimeout(function () {
                    try {
                        initCharts();
                        loadAllData();
                    } catch (e) { }
                }, 50);
            }
        });
    }

    function getSafeEmpresa() {
        let empVal = typeof currEmpresa !== 'undefined' ? currEmpresa : null;
        const selEmp = document.getElementById('sel-empresa');
        if ((!empVal || empVal === '' || empVal === 'undefined') && selEmp && selEmp.value) {
            empVal = selEmp.value;
        }
        return empVal;
    }

    async function fetchData(start, end, groupBy, signal) {
        try {
            const empVal = getSafeEmpresa();
            if (!empVal) return null;
            const emp = encodeURIComponent(empVal);
            const url = `/api/financial/evolution/evolution?empresa=${emp}&start_year=${start}&end_year=${end}&group_by=${groupBy}`;
            const response = await fetch(url, { signal });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const res = await response.json();
            if (res.status === 'ok') return res.data;

            console.error("Error API:", res.meta?.error);
            return null;
        } catch (e) {
            if (e.name !== 'AbortError') console.error(`Fallo fetch ${groupBy}:`, e);
            return null;
        }
    }

    function toggleLoader(id, show) {
        const el = document.getElementById(id);
        if (el) el.style.display = show ? 'flex' : 'none';
    }

    // Renderizado Gráfico Mensual (Con Zoom y Animación)
    function renderChart(data) {
        if (!evolChart) return;

        // Force resize antes de pintar por si acaso
        evolChart.resize();

        // Aseguramos formato de Eje X
        const periods = data.map(d => String(d.periodo));
        const ingresos = data.map(d => d.ingresos);
        const gastos = data.map(d => d.gastos);
        const resultados = data.map(d => d.resultado);

        const option = {
            backgroundColor: 'transparent',
            // Efecto de Entrada
            animationDuration: 2000,
            animationEasing: 'cubicOut',

            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(24, 24, 27, 0.95)',
                borderColor: '#3f3f46',
                textStyle: { color: '#f4f4f5' },
                axisPointer: { type: 'shadow' },
                formatter: function (params) {
                    let res = `<div style="margin-bottom:4px; color:#a1a1aa;">${params[0].name}</div>`;
                    params.forEach(p => {
                        const val = fmtInt.format(Math.round(p.value)) + ' €';
                        res += `<div style="display:flex; justify-content:space-between; gap:12px;"><span style="color:${p.color}">${p.marker} ${p.seriesName}</span><span style="color:#fff; font-weight:600;">${val}</span></div>`;
                    });
                    return res;
                }
            },
            grid: {
                left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true
            },
            dataZoom: [
                {
                    type: 'slider', show: true, xAxisIndex: [0],
                    // Importante: start 0, end 100 para ver todo
                    start: 0, end: 100,
                    bottom: 10, height: 20,
                    borderColor: 'transparent', backgroundColor: 'rgba(255,255,255,0.05)',
                    fillerColor: ACCENT_SOFT,
                    handleStyle: { color: ACCENT },
                    textStyle: { color: TEXT_MUTED }
                },
                { type: 'inside', xAxisIndex: [0], zoomOnMouseWheel: true }
            ],
            xAxis: {
                type: 'category',
                data: periods,
                axisLabel: { color: TEXT_MUTED },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } },
                axisLabel: { color: TEXT_MUTED }
            },
            series: [
                {
                    name: 'Ingresos', type: 'bar', data: ingresos,
                    itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#34d399' }, { offset: 1, color: '#059669' }]), borderRadius: [4, 4, 0, 0] },
                    barWidth: '40%',
                    animationDelay: (idx) => idx * 10
                },
                {
                    name: 'Gastos', type: 'bar', data: gastos,
                    itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: '#ff453a' }, { offset: 1, color: '#dc2626' }]), borderRadius: [4, 4, 0, 0] },
                    barWidth: '40%',
                    animationDelay: (idx) => idx * 10 + 100
                },
                {
                    name: 'Resultado', type: 'line', data: resultados,
                    smooth: true, symbol: 'none',
                    itemStyle: { color: '#facc15' },
                    lineStyle: { width: 3, shadowBlur: 10, shadowColor: 'rgba(250, 204, 21, 0.4)' },
                    z: 5,
                    animationDelay: 500
                }
            ]
        };
        evolChart.setOption(option, true);
    }

    // Renderizado Gráfico Anual (Resumen con Animación)
    function renderYearChart(data) {
        if (!evolChartYear) return;

        // Force resize antes de pintar
        evolChartYear.resize();

        if (!data || data.length === 0) {
            console.warn("No hay datos anuales para mostrar");
            evolChartYear.clear();
            return;
        }

        // FIX: Aseguramos que los años sean strings para que ECharts los trate como categorías discretas
        const years = data.map(d => String(d.anio));
        const ingresos = data.map(d => d.ingresos);
        const gastos = data.map(d => d.gastos);
        const resultados = data.map(d => d.resultado);

        const option = {
            backgroundColor: 'transparent',
            // WOW Effect: Animation
            animationDuration: 2500,
            animationEasing: 'elasticOut',
            tooltip: {
                trigger: 'axis',
                backgroundColor: 'rgba(24, 24, 27, 0.95)',
                borderColor: '#3f3f46',
                textStyle: { color: '#f4f4f5' },
                axisPointer: { type: 'shadow' },
                formatter: function (params) {
                    let res = `<div style="margin-bottom:4px; color:#a1a1aa;">${params[0].name}</div>`;
                    params.forEach(p => {
                        const val = fmtInt.format(Math.round(p.value)) + ' €';
                        res += `<div style="display:flex; justify-content:space-between; gap:12px;"><span style="color:${p.color}">${p.marker} ${p.seriesName}</span><span style="color:#fff; font-weight:600;">${val}</span></div>`;
                    });
                    return res;
                }
            },
            grid: {
                left: '3%', right: '4%', bottom: '5%', top: '10%', containLabel: true
            },
            xAxis: {
                type: 'category',
                data: years,
                axisLabel: { color: '#e4e4e7', fontSize: 12, fontWeight: 'bold' },
                axisLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
            },
            yAxis: {
                type: 'value',
                splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)', type: 'dashed' } },
                axisLabel: { color: TEXT_MUTED }
            },
            series: [
                {
                    name: 'Ingresos',
                    type: 'bar',
                    // FIX: Eliminamos 'stack' y 'barGap' para usar el layout por defecto (side-by-side)
                    data: ingresos,
                    itemStyle: { color: '#34d399', borderRadius: [4, 4, 0, 0] },
                    barWidth: '30%',
                    label: { show: true, position: 'top', formatter: '{c}', color: '#fff', fontSize: 10, distance: 5 },
                    animationDelay: (idx) => idx * 100 // Escalonado
                },
                {
                    name: 'Gastos',
                    type: 'bar',
                    data: gastos,
                    itemStyle: { color: '#ff453a', borderRadius: [4, 4, 0, 0] },
                    barWidth: '30%',
                    label: { show: true, position: 'top', formatter: '{c}', color: '#fff', fontSize: 10, distance: 5 },
                    animationDelay: (idx) => idx * 100 + 100 // Escalonado + Offset
                },
                {
                    name: 'Resultado',
                    type: 'line',
                    data: resultados,
                    smooth: true,
                    itemStyle: { color: '#facc15' },
                    lineStyle: { width: 4, type: 'dotted' },
                    label: { show: true, position: 'bottom', color: '#facc15', formatter: '{@score}' },
                    animationDelay: 1000
                }
            ]
        };
        // Not Merge para limpiar configuración anterior sucia y evitar fantasmas
        evolChartYear.setOption(option, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEvolucion);
    } else {
        initEvolucion();
    }
})();
