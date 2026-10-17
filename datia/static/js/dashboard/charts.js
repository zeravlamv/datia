// datia/static/js/dashboard/charts.js

// Dependency: Apache ECharts 5.x
// Dependency: global fmtMoney

function getCssVar(name, fallback) {
    try {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name);
        return v && v.trim() ? v.trim() : fallback;
    } catch (_) {
        return fallback;
    }
}

// --- ECharts Theme & Init ---
function initEChartsTheme() {
}

function getDatiaColors() {
    const accent = getCssVar('--accent', '#38bdf8');
    const accentSoft = getCssVar('--accent-soft', 'rgba(56, 189, 248, 0.35)');
    const text = getCssVar('--text', '#e4e4e7');
    const subtext = getCssVar('--text-muted', '#a1a1aa');
    return {
        text: text,
        subtext: subtext,
        grid: '#27272a',
        tooltipBg: 'rgba(24, 24, 27, 0.9)',
        tooltipBorder: '#3f3f46',
        accent: accent,
        accentSoft: accentSoft,
        palette: [accent, '#fbbf24', '#34d399', '#f472b6', '#a855f7', '#f87171']
    };
}

function applyAccentTheme(option) {
    try {
        const colors = getDatiaColors();
        if (option.tooltip) {
            option.tooltip.backgroundColor = option.tooltip.backgroundColor || colors.tooltipBg;
            option.tooltip.borderColor = option.tooltip.borderColor || colors.tooltipBorder;
            option.tooltip.textStyle = option.tooltip.textStyle || {};
            option.tooltip.textStyle.color = option.tooltip.textStyle.color || colors.text;
            if (option.tooltip.axisPointer) {
                option.tooltip.axisPointer.label = option.tooltip.axisPointer.label || {};
                option.tooltip.axisPointer.label.backgroundColor = option.tooltip.axisPointer.label.backgroundColor || colors.accent;
            }
        }
        option.axisPointer = option.axisPointer || {};
        option.axisPointer.lineStyle = option.axisPointer.lineStyle || {};
        option.axisPointer.lineStyle.color = option.axisPointer.lineStyle.color || colors.accent;
        const ensureAxisLabelColor = (ax) => {
            if (!ax) return;
            const arr = Array.isArray(ax) ? ax : [ax];
            arr.forEach(a => {
                a.axisLabel = a.axisLabel || {};
                if (!a.axisLabel.color) a.axisLabel.color = colors.subtext;
            });
        };
        ensureAxisLabelColor(option.xAxis);
        ensureAxisLabelColor(option.yAxis);
        if (option.dataZoom) {
            const dz = Array.isArray(option.dataZoom) ? option.dataZoom : [option.dataZoom];
            dz.forEach(z => {
                if (z.type === 'slider' || !z.type) {
                    z.fillerColor = z.fillerColor || colors.accentSoft;
                    z.handleStyle = z.handleStyle || {};
                    if (!z.handleStyle.color) z.handleStyle.color = colors.accent;
                    z.textStyle = z.textStyle || {};
                    if (!z.textStyle.color) z.textStyle.color = colors.subtext;
                }
            });
        }
        if (option.series) {
            const ss = Array.isArray(option.series) ? option.series : [option.series];
            ss.forEach(s => {
                s.emphasis = s.emphasis || {};
                if (s.type === 'bar') {
                    s.emphasis.itemStyle = s.emphasis.itemStyle || {};
                    if (s.emphasis.itemStyle.shadowBlur === undefined) s.emphasis.itemStyle.shadowBlur = 8;
                    if (!s.emphasis.itemStyle.shadowColor) s.emphasis.itemStyle.shadowColor = colors.accentSoft;
                } else if (s.type === 'line') {
                    s.emphasis.lineStyle = s.emphasis.lineStyle || {};
                    const baseW = (s.lineStyle && s.lineStyle.width) ? s.lineStyle.width : 3;
                    if (s.emphasis.lineStyle.width === undefined) s.emphasis.lineStyle.width = baseW + 1;
                    s.emphasis.itemStyle = s.emphasis.itemStyle || {};
                    if (s.emphasis.itemStyle.shadowBlur === undefined) s.emphasis.itemStyle.shadowBlur = 10;
                    if (!s.emphasis.itemStyle.shadowColor) s.emphasis.itemStyle.shadowColor = colors.accentSoft;
                }
            });
        }
    } catch (_) {}
    return option;
}

try {
    if (typeof echarts !== 'undefined' && !echarts.__accent_patched) {
        const __origInit = echarts.init;
        echarts.init = function(dom, theme, opts) {
            const inst = __origInit.call(this, dom, theme, opts);
            const __origSet = inst.setOption;
            inst.setOption = function(option, notMerge, lazyUpdate) {
                const themed = applyAccentTheme(option || {});
                return __origSet.call(this, themed, notMerge, lazyUpdate);
            };
            return inst;
        };
        echarts.__accent_patched = true;
    }
} catch (_) {}
// Helper: Resize observer for responsiveness
function attachResizeObserver(chartInstance, container) {
    if (!container || !chartInstance) return;
    const resizeObserver = new ResizeObserver(() => {
        chartInstance.resize();
    });
    resizeObserver.observe(container);
}

// Helper to format months
function formatMonthLabel(val) {
    let n = parseFloat(val);
    if (!isNaN(n) && n >= 1 && n <= 12) { // Allow floats like 1.0
        // Adjust if n is float but Represents integer
        if (Math.abs(n - Math.round(n)) < 0.001) n = Math.round(n);

        // Month is 0-indexed in JS Date
        const d = new Date(2024, n - 1, 1);
        if (typeof gettext === 'function') {
            const monthNames = [
                gettext('Ene'), gettext('Feb'), gettext('Mar'), gettext('Abr'), gettext('May'), gettext('Jun'),
                gettext('Jul'), gettext('Ago'), gettext('Sep'), gettext('Oct'), gettext('Nov'), gettext('Dic')
            ];
            return monthNames[n - 1];
        }
        const m = d.toLocaleDateString('es-ES', { month: 'short' });
        return m.charAt(0).toUpperCase() + m.slice(1);
    }
    return val;
}


// --- Main Renderers ---

function renderActivityChart(data, style = 'bar', selector = "#chart-activity") {
    // Overload check: if style looks like selector, swap
    if (typeof style === 'string' && (style.startsWith('#') || style.startsWith('.'))) {
        selector = style;
        style = 'bar'; // default back to bar if not specified
    }
    // Hard override if style isn't one of valid types
    if (!['bar', 'line', 'area'].includes(style)) style = 'bar';

    const dom = document.querySelector(selector);
    if (!dom) return;
    if (!data || !data.labels) {
        console.warn('renderActivityChart: No data or labels provided');
        return;
    }

    // Dispose if exists
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();

    chart = echarts.init(dom, null, { renderer: 'svg' });
    const colors = getDatiaColors();

    // Determine Series Type based on Style
    let seriesType = 'bar'; // Default 'bar'
    let showArea = false;
    let smooth = false;

    if (style === 'line') {
        seriesType = 'line';
        smooth = true;
        showArea = false;
    } else if (style === 'area') {
        seriesType = 'line';
        smooth = true;
        showArea = true;
    }
    // style == 'bar' -> seriesType 'bar', showArea false

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: colors.tooltipBg,
            borderColor: colors.tooltipBorder,
            textStyle: { color: colors.text },
            axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } }
        },
        legend: {
            data: [gettext('Ventas Netas'), gettext('Margen %')],
            textStyle: { color: colors.text },
            bottom: 0
        },
        grid: {
            left: '5%', right: '5%', bottom: '10%', top: '15%', // Increased spacing
            containLabel: true,
            borderColor: colors.grid
        },
        xAxis: [
            {
                type: 'category',
                boundaryGap: (seriesType === 'bar'), // Bars need gap
                data: data.labels.map(l => formatMonthLabel(l)),
                axisLabel: { 
                    color: colors.subtext, 
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 12,
                    margin: 14 // More spacing
                },
                axisLine: { show: false },
                axisTick: { show: false }
            }
        ],
        yAxis: [
            {
                type: 'value',
                axisLabel: { 
                    color: colors.subtext, 
                    formatter: (v) => fmtMoney.format(v),
                    fontFamily: 'Inter, sans-serif',
                    fontSize: 11
                },
                splitLine: { lineStyle: { color: '#27272a', type: 'dashed' } }
            },
            {
                type: 'value',
                name: gettext('Margen %'),
                min: 0,
                max: 100,
                position: 'right',
                axisLabel: { 
                    color: '#fbbf24', 
                    formatter: '{value} %',
                    fontFamily: 'Inter, sans-serif' 
                },
                splitLine: { show: false }
            }
        ],
        series: [
            {
                name: gettext('Ventas Netas'),
                type: seriesType,
                smooth: smooth,
                // Bar specific styling
                barMaxWidth: 30,
                itemStyle: {
                    borderRadius: (seriesType === 'bar' ? [4, 4, 0, 0] : 0),
                    color: '#38bdf8'
                },
                lineStyle: { width: 3, color: '#38bdf8' },
                showSymbol: (style !== 'bar'), // Show points on lines? Maybe false for cleaner look
                // Area specific
                areaStyle: showArea ? {
                    opacity: 0.8,
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(56, 189, 248, 0.5)' },
                        { offset: 1, color: 'rgba(56, 189, 248, 0.01)' }
                    ])
                } : null,
                emphasis: { focus: 'series' },
                data: data.neto
            },
            {
                name: gettext('Margen %'),
                type: 'line',
                yAxisIndex: 1,
                smooth: true,
                lineStyle: { width: 2, color: '#fbbf24', type: 'dashed' },
                showSymbol: false,
                data: data.margen
            }
        ]
    };

    chart.setOption(applyAccentTheme(option));
    attachResizeObserver(chart, dom);
}

function renderBarChart(selector, items, barColor) {
    const dom = document.querySelector(selector);
    if (!dom) return;

    // Auto-height based on items
    const rowHeight = 44;
    const minHeight = 260;
    const calcHeight = Math.max(minHeight, items.length * rowHeight + 80);
    dom.style.height = calcHeight + "px";
    // Expand parent card to avoid clipping
    try {
        const card = dom.closest('.flip-card');
        if (card) {
            const extra = 140; // header + paddings
            card.style.height = (calcHeight + extra) + 'px';
        }
    } catch (_) {}

    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();

    chart = echarts.init(dom, null, { renderer: 'svg' });
    const colors = getDatiaColors();

    // Helper: wrap at word boundaries
    const wrapLabel = (text, max = 28) => {
        const t = String(text || '');
        if (t.length <= max) return t;
        const idx = t.lastIndexOf(' ', max);
        const cut = idx > 0 ? idx : max;
        return t.slice(0, cut) + '\n' + t.slice(cut);
    };

    const categories = items.map(c => wrapLabel(c.label || c.nombre || c.Item, 28));
    const values = items.map(c => c.neto || c.val);

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            backgroundColor: colors.tooltipBg,
            borderColor: colors.tooltipBorder,
            textStyle: { color: colors.text, fontFamily: 'Inter, sans-serif' },
            padding: [10, 15],
            formatter: function (params) {
                const p = params[0];
                const rawName = items[p.dataIndex].label || items[p.dataIndex].nombre || items[p.dataIndex].Item;
                return `<div style="font-weight:600; margin-bottom:6px; color:#fff; font-size:13px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px">${rawName}</div>
                        <div style="display:flex; justify-content:space-between; gap:20px; align-items:center">
                            <span style="color:${p.color.colorStops ? p.color.colorStops[1].color : p.color}; font-size:12px">● Ventas</span>
                            <span style="font-weight:700; color:#fff; font-size:14px">${fmtMoney.format(p.value)}</span>
                        </div>`;
            }
        },
        grid: {
            left: '6%', 
            right: '12%',
            bottom: '4%', 
            top: '8%',
            containLabel: true
        },
        xAxis: {
            type: 'value',
            position: 'top',
            axisLabel: { 
                color: colors.subtext, 
                formatter: (v) => v.toLocaleString('es-ES', { notation: "compact" }) + '€',
                fontFamily: 'Inter, sans-serif' 
            },
            splitLine: { lineStyle: { color: '#27272a', type: 'dashed' } }
        },
        yAxis: {
            type: 'category',
            data: categories,
            inverse: true, // Rank 1 at top
            axisLabel: {
                color: colors.text,
                width: 220,
                overflow: 'break',
                lineHeight: 15,
                fontSize: 12,
                fontFamily: 'Inter, sans-serif',
                interval: 0 // Show all
            },
            axisLine: { show: false },
            axisTick: { show: false }
        },
        series: [
            {
                name: gettext('Ventas'),
                type: 'bar',
                data: values,
                cursor: 'default',
                itemStyle: {
                    borderRadius: [0, 18, 18, 0],
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: adjustColorOpacity(barColor, 0.4) }, 
                        { offset: 1, color: barColor }
                    ])
                },
                barWidth: 18,
                label: {
                    show: true,
                    position: 'right',
                    formatter: (p) => fmtMoney.format(p.value),
                    color: '#fff',
                    fontWeight: 600,
                    fontFamily: 'Inter, sans-serif',
                    distance: 10
                },
                // Add subtle track background
                showBackground: true,
                backgroundStyle: {
                    color: 'rgba(255, 255, 255, 0.02)',
                    borderRadius: [0, 18, 18, 0]
                },
                // Animation
                animationDuration: 1000,
                animationEasing: 'elasticOut'
            }
        ]
    };

    chart.setOption(applyAccentTheme(option));
    attachResizeObserver(chart, dom);
    // Explicit resize after init to catch style height change
    chart.resize();
}

function renderAiChart(container, config) {
    if (config && config.echarts_option) {
        let chart = echarts.getInstanceByDom(container);
        if (chart) chart.dispose();
        chart = echarts.init(container, null, { renderer: 'svg' });
        chart.setOption(applyAccentTheme(config.echarts_option));
        attachResizeObserver(chart, container);
        return;
    }

    if (!config || !config.data || !config.data.datasets) {
        container.innerHTML = `<div style="color:red; p:20px;">Error: Datos inválidos</div>`;
        return;
    }

    let chart = echarts.getInstanceByDom(container);
    if (chart) chart.dispose();

    chart = echarts.init(container, null, { renderer: 'svg' });
    const colors = getDatiaColors();
    const type = config.type === 'radial' ? 'pie' : (config.type || 'bar');
    const isPie = type === 'pie' || type === 'doughnut';

    let option = {
        backgroundColor: 'transparent',
        tooltip: {
            backgroundColor: colors.tooltipBg,
            borderColor: colors.tooltipBorder,
            textStyle: { color: colors.text }
        },
        color: colors.palette
    };

    if (isPie) {
        const dataset = config.data.datasets[0] || {};
        const labels = config.data.labels || [];
        const data = labels.map((l, i) => ({
            name: l,
            value: dataset.data[i]
        }));

        option = {
            ...option,
            tooltip: {
                trigger: 'item',
                formatter: function (params) {
                    const val = typeof params.value === 'number' ? params.value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : params.value;
                    return `${params.name}: <b>${val}</b> (${params.percent}%)`;
                }
            },
            legend: {
                bottom: 0,
                textStyle: { color: colors.text }
            },
            series: [{
                type: 'pie',
                radius: ['40%', '70%'],
                center: ['50%', '50%'],
                itemStyle: {
                    borderRadius: 5,
                    borderColor: '#18181b',
                    borderWidth: 2
                },
                label: { color: colors.text },
                data: data
            }]
        };
    } else {
        // Bar / Line
        let labels = config.data.labels || [];
        
        // [FIX ISS-053] Ensure labels is an array to prevent .map crash
        if (!Array.isArray(labels)) {
            console.warn("System Error: Labels is not an array", labels);
            labels = []; 
        }

        // [FIX] Apply Month Formatting if labels are 1..12 or look like months
        labels = labels.map(l => formatMonthLabel(l));

        const datasets = config.data.datasets || [];

        // [FIX] Force Vertical if it looks like time series (Months)
        // Check if labels are month names (short or long, Spanish or English, or just formatted)
        // Since we just ran formatMonthLabel, they should be "Ene", "Feb"... if they were 1..12
        const monthNames = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const isMonthly = labels.some(l => monthNames.includes(l));

        let isHorizontal = config.indexAxis === 'y';
        if (isMonthly) {
            isHorizontal = false;
        }

        option = {
            ...option,
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                backgroundColor: colors.tooltipBg,
                borderColor: colors.tooltipBorder,
                textStyle: { fontFamily: 'Inter, sans-serif' },
                formatter: function (params) {
                    let res = `<div style="font-family: 'Inter', sans-serif; font-size: 0.85rem; margin-bottom: 4px; color: #a1a1aa;">${params[0].name}</div>`;
                    params.forEach(p => {
                        const val = typeof p.value === 'number' ? p.value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €' : p.value;
                        res += `<div style="display: flex; justify-content: space-between; gap: 15px; font-family: 'Inter', sans-serif;">
                                    <span style="color: ${p.color}">${p.marker} ${p.seriesName}</span>
                                    <span style="font-weight: 600; color: #fff;">${val}</span>
                                </div>`;
                    });
                    return res;
                }
            },
            legend: { 
                textStyle: { color: colors.text, fontFamily: 'Inter, sans-serif' }, 
                top: 0,
                itemGap: 20
            },
            grid: { left: '5%', right: '5%', bottom: '5%', top: '15%', containLabel: true },
            xAxis: isHorizontal ? {
                type: 'value',
                axisLabel: { 
                    color: colors.subtext, 
                    fontFamily: 'Inter, sans-serif',
                    formatter: (v) => v.toLocaleString('es-ES', { notation: "compact" }) 
                },
                splitLine: { lineStyle: { color: '#27272a' } }
            } : {
                type: 'category',
                data: labels,
                axisLabel: { 
                    color: colors.subtext, 
                    rotate: -30, 
                    interval: 0,
                    fontFamily: 'Inter, sans-serif',
                    margin: 14
                },
            },
            yAxis: isHorizontal ? {
                type: 'category',
                data: labels,
                axisLabel: { 
                    color: colors.subtext, 
                    width: 140, 
                    overflow: 'truncate',
                    fontFamily: 'Inter, sans-serif'
                }
            } : {
                type: 'value',
                axisLabel: { 
                    color: colors.subtext, 
                    fontFamily: 'Inter, sans-serif',
                    formatter: (v) => v.toLocaleString('es-ES', { notation: "compact" }) + '€' 
                },
                splitLine: { lineStyle: { color: '#27272a' } }
            },
            series: datasets.map(ds => ({
                name: ds.label,
                type: type === 'bar' ? 'bar' : 'line',
                data: ds.data,
                smooth: true,
                barMaxWidth: 60,
                itemStyle: { borderRadius: [4, 4, 0, 0] },
                label: {
                    show: type === 'bar', // [FIX] Hide labels for Lines to avoid clutter/overlap
                    position: isHorizontal ? 'right' : 'top',
                    color: colors.text,
                    formatter: (p) => {
                        return typeof p.value === 'number' ? p.value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : p.value;
                    },
                    fontFamily: 'Inter, sans-serif',
                    fontWeight: 600
                },
                lineStyle: { width: 3 },
                symbol: 'circle', // Cleaner than empty circle
                symbolSize: 6
            }))
        };
    }

    chart.setOption(applyAccentTheme(option));
    attachResizeObserver(chart, container);
}


// Utility: Hex to RGBA for gradients
function adjustColorOpacity(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// --- Gauge / Radial Renderer ---
function renderGaugeChart(selector, value, config = {}) {
    const dom = document.querySelector(selector);
    if (!dom) return;

    if (typeof echarts === 'undefined') {
        console.error("ECharts not loaded!");
        dom.innerText = "Error: Lib missing";
        return;
    }

    // Dispose previous
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();

    chart = echarts.init(dom, null, { renderer: 'svg' });
    const colors = getDatiaColors();

    // Config
    const max = config.max || 100;
    const color = config.color || '#38bdf8';
    const isPercent = config.isPercent || false;
    const isMoney = config.isMoney || false;

    // Logic: 
    // For Money (Sales), we don't really have a "Max". A full ring looks boring.
    // Let's make it a "Decoration" ring.
    // If it's Money, we set progress to 75% static just for style, or 100% full circle.
    // Let's do a 75% arc to look like a "C" or HUD element.
    let progressVal = 75;
    let maxVal = 100;

    if (isPercent) {
        progressVal = value;
        maxVal = 100;
    }

    const option = {
        series: [
            {
                type: 'gauge',
                startAngle: 90,
                endAngle: -270,
                radius: '100%',
                pointer: { show: false },
                progress: {
                    show: true,
                    overlap: false,
                    roundCap: true,
                    clip: false,
                    itemStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: color },
                            { offset: 1, color: adjustColorOpacity(color, 0.1) }
                        ])
                    }
                },
                axisLine: {
                    lineStyle: {
                        width: 8,
                        color: [[1, '#27272a']]
                    }
                },
                splitLine: { show: false },
                axisTick: { show: false },
                axisLabel: { show: false },
                data: [{
                    value: progressVal,
                    name: config.title || '',
                    detail: {
                        value: value
                    }
                }],
                detail: {
                    fontSize: 28, // Matches approx 1.8rem
                    fontWeight: 700,
                    fontFamily: 'Inter, sans-serif',
                    color: '#fff',
                    offsetCenter: ['0%', '0%'], // Dead center
                    formatter: function (val) {
                        const v = config.rawValue !== undefined ? config.rawValue : val;
                        if (isMoney) return fmtMoney.format(v);
                        if (isPercent) return v.toFixed(2) + '%';
                        return v;
                    }
                }
            }
        ]
    };

    chart.setOption(applyAccentTheme(option));
    attachResizeObserver(chart, dom);
}

// --- Sparkline (Mini Trend) Renderer ---
function renderSparklineChart(selector, value, config = {}) {
    const dom = document.querySelector(selector);
    if (!dom) return;

    if (typeof echarts === 'undefined') return;

    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();

    chart = echarts.init(dom, null, { renderer: 'svg' });
    const color = config.color || '#38bdf8';

    // Mock Data Generation for Visual Sparkline
    // Generate 10 points ending in 'value'
    const data = [];
    let current = value * 0.8;
    for (let i = 0; i < 9; i++) {
        data.push(current);
        current = current * (0.9 + Math.random() * 0.2); // Random walk
    }
    data.push(value); // Ensure last point is real value

    const option = {
        grid: { top: 5, bottom: 5, left: 5, right: 5 },
        xAxis: { type: 'category', show: false },
        yAxis: { type: 'value', show: false, min: 'dataMin' },
        series: [{
            type: 'line',
            data: data,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 3, color: color },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: adjustColorOpacity(color, 0.4) },
                    { offset: 1, color: adjustColorOpacity(color, 0.0) }
                ])
            }
        },
        {
            // Value Label in Center
            type: 'scatter',
            data: [0], // Dummy
            symbolSize: 0,
            markPoint: {
                data: [
                    {
                        coord: [9, value], // Point at end
                        value: fmtMoney.format(value),
                        label: {
                            show: true,
                            position: 'left',
                            color: '#fff',
                            fontSize: 20,
                            fontWeight: 'bold',
                            formatter: (p) => fmtMoney.format(value)
                        }
                    }
                ],
                symbol: 'circle',
                symbolSize: 5,
                itemStyle: { color: '#fff' }
            }
        }]
    };

    chart.setOption(option);
    attachResizeObserver(chart, dom);
}

// --- Liquid CSS Chart Renderer ---
function renderLiquidChart(selector, value, config = {}) {
    const dom = document.querySelector(selector);
    if (!dom) return;

    // Clean up
    if (typeof echarts !== 'undefined') {
        let chart = echarts.getInstanceByDom(dom);
        if (chart) chart.dispose();
    }

    const color = config.color || '#38bdf8';
    const raw = config.rawValue || 0;

    // Calculate fill height percentage
    let fillPct = 65; // Default aesthetic fill for money
    if (config.isPercent) {
        fillPct = Math.min(Math.max(raw, 0), 100);
    }

    const topOffset = 100 - fillPct;

    let txt = value;
    if (config.isMoney) txt = fmtMoney.format(raw);
    if (config.isPercent) txt = raw.toFixed(2) + '%';

    // HTML Structure
    dom.style.display = 'block';
    dom.innerHTML = `
        <div class="liquid-container" style="border-color: ${adjustColorOpacity(color, 0.5)}">
            <div class="liquid-value">${txt}</div>
            <div class="liquid-wave" style="top: ${topOffset}%; background-color: ${color}; box-shadow: 0 0 10px ${color};"></div>
            <div class="liquid-wave" style="top: ${topOffset - 5}%; background-color: ${color}; width: 210%;"></div>
        </div>
    `;
}
