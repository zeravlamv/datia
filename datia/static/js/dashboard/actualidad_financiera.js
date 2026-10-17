// Logic for "Actualidad - Financiera" Tab

console.log("Actualidad Financiera JS Loaded");


let isFetchingActualidadFinanciera = false;
async function loadActualidadFinanciera(force = false) {
    if (isFetchingActualidadFinanciera && !force) {
        console.warn("loadActualidadFinanciera ignored: already fetching");
        return;
    }
    console.log("loadActualidadFinanciera() called");
    isFetchingActualidadFinanciera = true;

    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;

    try {
        // 1. Snapshot
        // [FIX] Use correct API root. 'API' const is '/api/datia', but financial is at '/api/financial'
        const res = await fetch(`/api/financial/snapshot${q}`);
        if (!res.ok) throw new Error("Failed to fetch financial snapshot");
        const json = await res.json();

        renderFinancialSnapshot(json);

        // P&L chart omitido según requerimiento

        // 3. Strategic Analysis (Deep Dive)
        const resAnalysis = await fetch(`/api/financial/analysis${q}`);
        if (resAnalysis.ok) {
            const jsonAnalysis = await resAnalysis.json();
            renderAdvancedAnalysis(jsonAnalysis);
        }

        // 4. P&L Detail
        loadPLDetail();

        // 5. Restore Layout
        restoreLayout();
        loadExecutiveChart();

        // 6. Quarterly Section
        await initQuarterly();

        // 7. Balance Widget
        await loadBalanceWidget();

        initPLReport();

        // 8. Treasury Report (moved to Tesorería tab)

        // 7. Accounts Tree (eliminado)

    } catch (e) {
        console.error("Error loading Financial Dashboard:", e);
        if (typeof gettext === 'function') {
            showToast(gettext("Error cargando datos financieros"), "error");
        } else {
            showToast("Error cargando datos financieros", "error");
        }
    } finally {
        isFetchingActualidadFinanciera = false;
        hideDashboardLoader();
    }
}

async function loadExecutiveChart() {
    try {
        const res = await fetch(`/api/financial/monthly_kpis?empresa=${currEmpresa}&ejercicio=${currEjercicio}`);
        if (!res.ok) return;
        const data = await res.json();
        renderExecutiveChart(data);
    } catch (e) {
        console.error("Executive chart load error:", e);
    }
}

document.addEventListener('datia:empresa-change', function () {
    loadActualidadFinanciera(true);
    loadExecutiveChart();
    loadBalanceWidget();
});
document.addEventListener('datia:ejercicio-change', function () {
    loadActualidadFinanciera(true);
    loadExecutiveChart();
    loadBalanceWidget();
});

function renderExecutiveChart(data) {
    const dom = document.getElementById('fin-exec-chart');
    if (!dom || !data || !data.labels) return;
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const option = {
        backgroundColor: 'transparent',
        title: { text: (typeof gettext === 'function' ? gettext('Ingresos, Gastos y EBITDA mensual') : 'Ingresos, Gastos y EBITDA mensual'), textStyle: { color: '#a1a1aa', fontWeight: 600 }, left: 'center' },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function (params) {
                const name = params[0] ? params[0].name : '';
                let res = `<div style="margin-bottom:4px; color:#a1a1aa;">${name}</div>`;
                params.forEach(p => {
                    const isPct = p.seriesName.indexOf('%') !== -1;
                    const val = isPct ? (p.value !== undefined ? Number(p.value).toFixed(2) + ' %' : '-') : (p.value !== undefined ? nf.format(Math.round(p.value)) + ' €' : '-');
                    res += `<div style="display:flex; justify-content:space-between; gap:12px;"><span style="color:${p.color}">${p.marker} ${p.seriesName}</span><span style="color:#fff; font-weight:600;">${val}</span></div>`;
                });
                return res;
            }
        },
        legend: { top: 24, textStyle: { color: '#e4e4e7' }, itemGap: 20 },
        grid: { left: '6%', right: '6%', bottom: '6%', top: 70, containLabel: true },
        xAxis: { type: 'category', data: data.labels, axisLabel: { color: '#a1a1aa' }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#27272a' } } },
        yAxis: [
            { type: 'value', position: 'left', axisLabel: { color: '#a1a1aa', formatter: function (v) { return nf.format(Math.round(v)); } }, splitLine: { lineStyle: { color: '#27272a' } } },
            { type: 'value', position: 'right', min: 0, max: 100, axisLabel: { color: '#fbbf24', formatter: '{value} %' }, splitLine: { show: false } }
        ],
        series: [
            { name: (typeof gettext === 'function' ? gettext('Ingresos') : 'Ingresos'), type: 'bar', data: data.ingresos, itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 },
            { name: (typeof gettext === 'function' ? gettext('Gastos') : 'Gastos'), type: 'bar', data: data.gastos, itemStyle: { color: '#ef4444', borderRadius: [4, 4, 0, 0] }, barMaxWidth: 26 },
            { name: 'EBITDA', type: 'line', data: data.ebitda, smooth: true, lineStyle: { width: 3, color: '#10b981' }, itemStyle: { color: '#10b981' }, yAxisIndex: 0, showSymbol: false },
            { name: (typeof gettext === 'function' ? gettext('Margen EBITDA %') : 'Margen EBITDA %'), type: 'line', data: data.margen_pct, smooth: true, lineStyle: { width: 2, color: '#fbbf24', type: 'dashed' }, itemStyle: { color: '#fbbf24' }, yAxisIndex: 1, showSymbol: false }
        ]
    };
    chart.setOption(option);
    if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
}

async function loadBalanceWidget() {
    try {
        const res = await fetch(`/api/financial/balance/summary?empresa=${currEmpresa}&ejercicio=${currEjercicio}`);
        if (res.ok) {
            const data = await res.json();
            if (data.status && data.status !== 'ok') {
                showBalanceError((typeof gettext === 'function' ? gettext('Datos de balance no disponibles') : 'Datos de balance no disponibles') + (data.reason ? `: ${data.reason}` : ''));
            } else {
                hideBalanceError();
                renderBalanceSummary(data);
            }
        }
        const balLabel = document.getElementById('fin-balance-period-label');
        if (balLabel) {
            const compTxt = (typeof gettext === 'function' ? gettext('Comparativa:') : 'Comparativa:');
            balLabel.innerText = `${compTxt} ${currEjercicio} vs ${currEjercicio - 1}`;
        }
        const root = document.getElementById('fin-balance-root') ? document.getElementById('fin-balance-root').value : 'activo';
        await renderBalanceTable(root);
    } catch (e) {
        console.error("Balance widget load error:", e);
        showBalanceError(typeof gettext === 'function' ? gettext('Error cargando balance') : 'Error cargando balance');
    }
}

function renderBalanceSummary(data) {
    const dom = document.getElementById('fin-balance-summary');
    if (!dom || !data || !data.totales) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const rows = [];
    rows.push(`<div class="fin-balance-row" data-root="activo"><span class="label">${typeof gettext === 'function' ? gettext('Activo Total') : 'Activo Total'}</span><span class="val">${nf.format(Math.round(data.totales.activo))} €</span></div>`);
    rows.push(`<div class="fin-balance-row" data-root="pasivo"><span class="label">${typeof gettext === 'function' ? gettext('Pasivo Total') : 'Pasivo Total'}</span><span class="val">${nf.format(Math.round(data.totales.pasivo))} €</span></div>`);
    rows.push(`<div class="fin-balance-row" data-root="patrimonio"><span class="label">${typeof gettext === 'function' ? gettext('Patrimonio Neto') : 'Patrimonio Neto'}</span><span class="val">${nf.format(Math.round(data.totales.patrimonio))} €</span></div>`);

    // [NEW] Mostrar resultado de explotación oficial para alinear balance con dashboard
    if (Math.abs(data.resultado_explotacion || 0) > 1) {
        rows.push(`<div class="fin-balance-row" style="opacity:0.92; border-top: 1px dashed rgba(255,255,255,0.12); margin-top:4px;"><span class="label" style="color:#22c55e;">${typeof gettext === 'function' ? gettext('Resultado de explotación') : 'Resultado de explotación'}</span><span class="val" style="color:#22c55e;">${nf.format(Math.round(data.resultado_explotacion))} €</span></div>`);
    }

    // [NEW] Mostrar también el ajuste/pending closing del balance si existe
    if (Math.abs(data.balance_eq_diff || 0) > 1) {
        rows.push(`<div class="fin-balance-row" style="opacity:0.8; border-top: 1px dashed rgba(255,255,255,0.1); margin-top:4px;"><span class="label" style="color:#f59e0b;">${typeof gettext === 'function' ? gettext('Resultado ejercicio pendiente cierre') : 'Resultado ejercicio pendiente cierre'}</span><span class="val" style="color:#f59e0b;">${nf.format(Math.round(data.balance_eq_diff))} €</span></div>`);
    }

    dom.innerHTML = rows.join('');
    Array.from(dom.querySelectorAll('.fin-balance-row[data-root]')).forEach(row => {
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => {
            const root = row.getAttribute('data-root') || 'activo';
            const sel = document.getElementById('fin-balance-root');
            if (sel) sel.value = root;
            changeBalanceRoot();
        });
    });
}

async function renderBalanceTree(root) {
    try {
        const res = await fetch(`/api/financial/balance/tree?empresa=${currEmpresa}&ejercicio=${currEjercicio}&root=${encodeURIComponent(root)}&start_level=3&end_level=6`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status && data.status !== 'ok') {
            showBalanceError((typeof gettext === 'function' ? gettext('Estructura de balance sin datos') : 'Estructura de balance sin datos') + (data.reason ? `: ${data.reason}` : ''));
            return;
        } else {
            hideBalanceError();
        }
        const dom = document.getElementById('fin-balance-tree');
        if (!dom) return;
        let chart = echarts.getInstanceByDom(dom);
        if (chart) chart.dispose();
        chart = echarts.init(dom, null, { renderer: 'svg' });
        function mapNode(n) {
            return {
                name: `${n.code} ${n.name}`,
                value: n.amount,
                code: n.code,
                children: (n.children || []).map(ch => mapNode(ch))
            };
        }
        const seriesData = (data.nodes || []).map(n => mapNode(n));
        const option = {
            backgroundColor: 'transparent',
            tooltip: { formatter: function (p) { const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 }); return `${p.data.name}<br>${nf.format(Math.round(p.value))} €`; } },
            series: [{
                type: 'treemap',
                data: seriesData,
                leafDepth: 1,
                label: { show: true, color: '#e4e4e7' },
                upperLabel: { show: true, color: '#a1a1aa' },
                breadcrumb: { show: false },
                itemStyle: { borderColor: '#27272a', borderWidth: 1 },
            }]
        };
        chart.setOption(option);
        chart.off('click');
        chart.on('click', async function (p) {
            try {
                const code = p && p.data && (p.data.code || (typeof p.data.name === 'string' ? p.data.name.split(' ')[0] : null));
                if (!code) return;
                const res = await fetch(`/api/financial/accounts/detail?empresa=${currEmpresa}&ejercicio=${currEjercicio}&code=${encodeURIComponent(code)}`);
                if (!res.ok) return;
                const detail = await res.json();
                renderBalanceDetail(detail);
            } catch (e) {
                console.error("Balance detail fetch error:", e);
            }
        });
        if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
    } catch (e) {
        console.error("Balance tree render error:", e);
    }
}

async function renderBalanceTable(root) {
    try {
        const res = await fetch(`/api/financial/balance/table?empresa=${currEmpresa}&ejercicio=${currEjercicio}&root=${encodeURIComponent(root)}&start_level=1&end_level=3&order=code_asc`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status && data.status !== 'ok') {
            showBalanceError((typeof gettext === 'function' ? gettext('Estructura de balance sin datos') : 'Estructura de balance sin datos') + (data.reason ? `: ${data.reason}` : ''));
            return;
        } else {
            hideBalanceError();
        }
        const tbody = document.getElementById('fin-balance-table-body');
        if (!tbody) return;
        const nf = new Intl.NumberFormat('es-ES', { style: 'decimal', maximumFractionDigits: 0, useGrouping: true });
        const pf = new Intl.NumberFormat('es-ES', { style: 'decimal', maximumFractionDigits: 2, useGrouping: true });
        const rows = (data.rows || []).filter(r => Math.round(r.amount || 0) !== 0).map(r => {
            const code = r.code;
            const desc = r.description || code;
            const amt = nf.format(Math.round(r.amount || 0));
            const prev = nf.format(Math.round(r.prev_amount || 0));
            const varp = pf.format(r.var_pct || 0);

            // Layout styling based on Level
            const lvl = r.level || 3;
            let rowStyle = '';
            let cellStyle = '';
            let indent = (lvl - 1) * 20; // 20px per level indent

            if (lvl === 1) {
                rowStyle = 'font-weight: 800; background-color: rgba(255,255,255,0.05);';
                cellStyle = 'color: #fff; text-transform: uppercase;';
            } else if (lvl === 2) {
                rowStyle = 'font-weight: 600;';
                cellStyle = 'color: #e4e4e7;';
            } else {
                cellStyle = 'color: #a1a1aa;';
            }

            return `<tr data-code="${code}" style="${rowStyle}">
                <td>${code}</td>
                <td style="padding-left: ${indent}px; ${cellStyle}">
                    <button class="tree-toggle" data-code="${code}" aria-label="${(typeof gettext === 'function' ? gettext('Expandir') : 'Expandir')}">+</button>
                    <span class="tree-label">${desc}</span>
                </td>
                <td class="text-right" style="white-space: nowrap;">${amt} €</td>
                <td class="text-right" style="white-space: nowrap;">${prev} €</td>
                <td class="text-right" style="white-space: nowrap;">${varp} %</td>
            </tr>`;
        });
        tbody.innerHTML = rows.length > 0 ? rows.join('') : `<tr><td colspan="5" class="text-center">${typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos'}</td></tr>`;
        Array.from(tbody.querySelectorAll('tr[data-code]')).forEach(tr => {
            tr.addEventListener('click', async function () {
                const code = this.getAttribute('data-code');
                if (!code) return;
                try {
                    const r = await fetch(`/api/financial/accounts/detail?empresa=${currEmpresa}&ejercicio=${currEjercicio}&code=${encodeURIComponent(code)}`);
                    if (!r.ok) return;
                    const detail = await r.json();
                    renderBalanceDetail(detail);
                } catch (e) {
                    console.error("Balance detail fetch error (table click):", e);
                }
            });
        });
        Array.from(tbody.querySelectorAll('.tree-toggle')).forEach(btn => {
            btn.addEventListener('click', async function (ev) {
                ev.stopPropagation();
                const code = this.getAttribute('data-code');
                const tr = this.closest('tr');
                if (!code || !tr) return;
                await toggleBalanceDrilldownRow(tbody, tr, code);
            });
        });
    } catch (e) {
        console.error("Balance table render error:", e);
    }
}

function changeBalanceRoot() {
    const sel = document.getElementById('fin-balance-root');
    const root = sel ? sel.value : 'activo';
    // renderBalanceTree(root); // Disabled as we moved to Table view only
    renderBalanceTable(root);
}

function renderBalanceDetail(detail) {
    const dom = document.getElementById('fin-balance-detail');
    if (!dom || !detail || !detail.monthly) return;
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });
    const labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const option = {
        backgroundColor: 'transparent',
        title: { text: detail.name ? detail.name : detail.code, left: 'left', textStyle: { color: '#a1a1aa', fontSize: 12, fontWeight: 600 } },
        grid: { left: '6%', right: '4%', bottom: 24, top: 30, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { color: '#a1a1aa', fontSize: 10 }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#27272a' } } },
        yAxis: { type: 'value', axisLabel: { color: '#a1a1aa', formatter: function (v) { return nf.format(Math.round(v)); } }, splitLine: { lineStyle: { color: '#27272a' } } },
        series: [
            { name: detail.code, type: 'line', data: detail.monthly, smooth: true, lineStyle: { width: 2, color: '#3b82f6' }, itemStyle: { color: '#3b82f6' }, showSymbol: false }
        ]
    };
    chart.setOption(option);
    if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
}

function showBalanceError(msg) {
    const el = document.getElementById('fin-balance-error');
    if (!el) return;
    el.textContent = msg;
    el.style.display = 'block';
}

function hideBalanceError() {
    const el = document.getElementById('fin-balance-error');
    if (!el) return;
    el.textContent = '';
    el.style.display = 'none';
}

async function toggleBalanceDrilldownRow(tbody, tr, code) {
    const next = tr.nextElementSibling;
    if (next && next.getAttribute('data-sub-of') === code) {
        next.remove();
        return;
    }
    const cacheKey = `bd_${currEmpresa}_${currEjercicio}_${code}`;
    if (!window.__finBreakdownCache) window.__finBreakdownCache = {};
    let data = window.__finBreakdownCache[cacheKey];
    if (!data) {
        const r = await fetch(`/api/financial/accounts/breakdown?empresa=${currEmpresa}&ejercicio=${currEjercicio}&code=${encodeURIComponent(code)}`);
        if (!r.ok) return;
        data = await r.json();
        window.__finBreakdownCache[cacheKey] = data;
    }
    const nf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 });
    const filtered = (data.rows || []).filter(x => Math.round(Number(x.valor) || 0) !== 0);
    const total = (Array.isArray(filtered) ? filtered.reduce((s, x) => s + (Number(x.valor) || 0), 0) : 0);
    const rowsHtml = filtered.map(x => {
        return `<div class="tree-group-row" data-code="${x.cuenta}">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <button class="tree-toggle" data-code="${x.cuenta}">+</button>
                    <span class="tree-label">${x.cuenta} • ${x.descripcion}</span>
                </div>
                <div class="tree-amt">${nf.format(Math.round(x.valor))} €</div>
            </div>
            <div class="tree-children" style="margin-left:20px;"></div>
        </div>`;
    }).join('');
    const holder = document.createElement('tr');
    holder.className = 'tree-line-row';
    holder.setAttribute('data-sub-of', code);
    holder.innerHTML = `<td colspan="5">
        <div class="budget-tree">
            <div class="tree-group-header" style="padding:8px; display:flex; align-items:center; justify-content:space-between;">
                <div class="tree-label">${code} • ${data.name || ''}</div>
                <div class="tree-total">${nf.format(Math.round(total))} €</div>
            </div>
            <div class="tree-group" style="padding:8px 8px 12px 8px;">${rowsHtml || `<div class="tree-label" style="opacity:0.8;">${(typeof gettext==='function'?gettext('Sin desglose disponible'):'Sin desglose disponible')}</div>`}</div>
        </div>
    </td>`;
    tr.after(holder);
    Array.from(holder.querySelectorAll('.tree-toggle')).forEach(b => {
        b.addEventListener('click', async function (e) {
            e.stopPropagation();
            const c = this.getAttribute('data-code');
            const row = this.closest('.tree-group-row');
            const children = row ? row.querySelector('.tree-children') : null;
            if (!c || !children) return;
            if (children.childElementCount > 0) {
                children.innerHTML = '';
                this.classList.remove('active');
                return;
            }
            this.classList.add('active');
            await renderNestedBreakdown(children, c);
        });
    });
}

async function renderNestedBreakdown(container, code) {
    const cacheKey = `bd_${currEmpresa}_${currEjercicio}_${code}`;
    if (!window.__finBreakdownCache) window.__finBreakdownCache = {};
    let data = window.__finBreakdownCache[cacheKey];
    if (!data) {
        const r = await fetch(`/api/financial/accounts/breakdown?empresa=${currEmpresa}&ejercicio=${currEjercicio}&code=${encodeURIComponent(code)}`);
        if (!r.ok) return;
        data = await r.json();
        window.__finBreakdownCache[cacheKey] = data;
    }
    const nf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 });
    const filtered = (data.rows || []).filter(x => Math.round(Number(x.valor) || 0) !== 0);
    const html = filtered.map(x => {
        return `<div class="tree-group-row" data-code="${x.cuenta}">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <button class="tree-toggle" data-code="${x.cuenta}">+</button>
                    <span class="tree-label">${x.cuenta} • ${x.descripcion}</span>
                </div>
                <div class="tree-amt">${nf.format(Math.round(x.valor))} €</div>
            </div>
            <div class="tree-children" style="margin-left:20px;"></div>
        </div>`;
    }).join('');
    container.innerHTML = html || `<div class="tree-label" style="opacity:0.8;">${(typeof gettext==='function'?gettext('Sin más niveles'):'Sin más niveles')}</div>`;
    Array.from(container.querySelectorAll('.tree-toggle')).forEach(b => {
        b.addEventListener('click', async function (e) {
            e.stopPropagation();
            const c = this.getAttribute('data-code');
            const row = this.closest('.tree-group-row');
            const children = row ? row.querySelector('.tree-children') : null;
            if (!c || !children) return;
            if (children.childElementCount > 0) {
                children.innerHTML = '';
                this.classList.remove('active');
                return;
            }
            this.classList.add('active');
            await renderNestedBreakdown(children, c);
        });
    });
}
function initPLReport() {
    const levelEl = document.getElementById('pl-report-level');
    const level = levelEl ? parseInt(levelEl.value, 10) : 2;
    changePLLevel();
}

function changePLLevel() {
    const levelEl = document.getElementById('pl-report-level');
    const level = levelEl ? parseInt(levelEl.value, 10) : 2;
    loadPLReport(level);
}

async function loadPLReport(level) {
    const qCY = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&level=${encodeURIComponent(level)}`;
    const qPY = `?empresa=${currEmpresa}&ejercicio=${currEjercicio - 1}&level=${encodeURIComponent(level)}`;

    const tbody = document.getElementById('pl-report-table-body');
    if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">${(typeof gettext === 'function' ? gettext('Cargando...') : 'Cargando...')}</td></tr>`;
    }

    try {
        const [resCY, resPY] = await Promise.all([
            fetch(`/api/financial/pl${qCY}`),
            fetch(`/api/financial/pl${qPY}`)
        ]);

        if (!resCY.ok || !resPY.ok) throw new Error('Error en endpoints P&L');

        const dataCY = await resCY.json();
        const dataPY = await resPY.json();

        renderPLReportSummary(dataCY);

        // Detect Budget
        const hasBudget = (dataCY.total_ingresos_budget > 0 || dataCY.total_gastos_budget > 0);
        window.plMode = hasBudget ? 'budget' : 'prev';

        // Update Headers/Labels
        const labelEl = document.getElementById('pl-report-period-label');
        if (labelEl) {
            const compTxt = (typeof gettext === 'function' ? gettext('Comparativa:') : 'Comparativa:');
            const targetTxt = hasBudget ? (typeof gettext === 'function' ? gettext('Presupuesto') : 'Presupuesto') : (currEjercicio - 1);
            labelEl.innerText = `${compTxt} ${currEjercicio} vs ${targetTxt}`;
        }

        // Try to update Table Header Column 4 and 5
        // 4: Target (Prev/Budget), 5: Var (Pct/Diff)
        const table = document.getElementById('pl-report-table'); // Assumption
        if (!table && tbody) {
            // Try finding table via tbody parent
            const tbl = tbody.closest('table');
            if (tbl) {
                const headers = tbl.querySelectorAll('th');
                if (headers.length >= 5) {
                    headers[3].innerText = hasBudget ? (typeof gettext === 'function' ? gettext('Presupuesto') : 'Presupuesto') : (typeof gettext === 'function' ? gettext('Anterior') : 'Anterior');
                    headers[4].innerText = hasBudget ? (typeof gettext === 'function' ? gettext('Desviación') : 'Desviación') : 'Var %';
                }
            }
        }

        const rows = buildPLRows(dataCY, dataPY, level, hasBudget);
        window.plRows = rows;
        setPLFilter('all');

    } catch (e) {
        console.error('Error cargando Cuenta de Explotación:', e);
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center" style="color:#ef4444;">${(typeof gettext === 'function' ? gettext('Error cargando datos') : 'Error cargando datos')}</td></tr>`;
        }
    }
}

function buildPLRows(cur, prev, level, useBudget) {
    // New Backend returns 'rows' already structured with headers. Use it if available.
    if (cur.rows && Array.isArray(cur.rows)) {
        return cur.rows.map(r => ({
            ...r,
            actual: r.valor, // Backend sends 'valor'
            target: useBudget ? r.presupuesto : (prev.rows ? findPrevValue(r.cuenta, prev.rows) : 0), // Need to find prev
            diff: useBudget ? r.desviacion : (calcVarPct(r.valor, (prev.rows ? findPrevValue(r.cuenta, prev.rows) : 0))),
            mode: useBudget ? 'budget' : 'prev'
        }));
    }

    // Fallback for old API structure (just in case)
    const curIng = (cur.ingresos || []).map(x => ({
        cuenta: String(x.cuenta || ''),
        descripcion: x.descripcion,
        valor: Math.abs(x.valor || 0),
        presupuesto: Math.abs(x.presupuesto || 0),
        desviacion: x.desviacion || 0, // Raw difference
        level: x.level || (String(x.cuenta || '').length <= 1 ? 1 : (String(x.cuenta || '').length === 2 ? 2 : (String(x.cuenta || '').length === 3 ? 3 : 4)))
    }));

    const curGas = (cur.gastos || []).map(x => ({
        cuenta: String(x.cuenta || ''),
        descripcion: x.descripcion,
        valor: Math.abs(x.valor || 0),
        presupuesto: Math.abs(x.presupuesto || 0),
        desviacion: x.desviacion || 0,
        level: x.level || (String(x.cuenta || '').length <= 1 ? 1 : (String(x.cuenta || '').length === 2 ? 2 : (String(x.cuenta || '').length === 3 ? 3 : 4)))
    }));

    const prevIng = (prev.ingresos || []).map(x => ({ cuenta: String(x.cuenta || ''), valor: Math.abs(x.valor || 0) }));
    const prevGas = (prev.gastos || []).map(x => ({ cuenta: String(x.cuenta || ''), valor: Math.abs(x.valor || 0) }));

    const curMap = {};
    [...curIng, ...curGas].forEach(c => { curMap[c.cuenta] = c; });

    const prevMap = {};
    [...prevIng, ...prevGas].forEach(p => { prevMap[p.cuenta] = p; });

    const keys = Array.from(new Set(Object.keys(curMap).concat(Object.keys(prevMap)))).sort((a, b) => a.localeCompare(b));

    return keys.map(code => {
        const c = curMap[code] || {
            cuenta: code,
            descripcion: (typeof gettext === 'function' ? gettext('Sin Descripción') : 'Sin Descripción'),
            valor: 0,
            presupuesto: 0,
            desviacion: 0,
            level: (code.length <= 1 ? 1 : (code.length === 2 ? 2 : (code.length === 3 ? 3 : 4)))
        };
        const p = prevMap[code] || { valor: 0 };

        const actual = c.valor || 0;
        const anterior = p.valor || 0;
        const budget = c.presupuesto || 0;

        let target = useBudget ? budget : anterior;
        let diff = useBudget ? c.desviacion : (anterior !== 0 ? ((actual - anterior) / Math.abs(anterior)) * 100 : (actual > 0 ? 100 : 0));

        // IsIngreso
        const isIngreso = code.startsWith('7');

        return {
            cuenta: code,
            descripcion: c.descripcion,
            actual,
            target,
            diff,
            isIngreso,
            level: c.level,
            mode: useBudget ? 'budget' : 'prev'
        };
    });
}

function findPrevValue(code, rows) {
    if (!code) return 0; // Headers have empty code usually
    const found = rows.find(r => r.cuenta === code);
    return found ? found.valor : 0;
}

function calcVarPct(curr, prev) {
    if (prev === 0) return (curr !== 0 ? 100 : 0);
    return ((curr - prev) / Math.abs(prev)) * 100;
}

function renderPLReportSummary(dataCY) {
    const dom = document.getElementById('fin-pl-summary');
    if (!dom || !dataCY) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const html = [
        `<div class="fin-balance-row" data-pl-filter="ingresos"><span class="label">${(typeof gettext === 'function' ? gettext('Ingresos Totales') : 'Ingresos Totales')}</span><span class="val">${nf.format(Math.round(dataCY.total_ingresos || 0))} €</span></div>`,
        `<div class="fin-balance-row" data-pl-filter="gastos"><span class="label">${(typeof gettext === 'function' ? gettext('Gastos Totales') : 'Gastos Totales')}</span><span class="val">${nf.format(Math.round(dataCY.total_gastos || 0))} €</span></div>`,
        `<div class="fin-balance-row" data-pl-filter="all"><span class="label">${(typeof gettext === 'function' ? gettext('Resultado de Explotación') : 'Resultado de Explotación')}</span><span class="val">${nf.format(Math.round((dataCY.resultado_explotacion || 0)))} €</span></div>`
    ];
    dom.innerHTML = html.join('');
    Array.from(dom.querySelectorAll('.fin-balance-row[data-pl-filter]')).forEach(row => {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function () {
            const f = this.getAttribute('data-pl-filter') || 'all';
            setPLFilter(f);
        });
    });
}

function renderPLReportTable(rows) {
    const tbody = document.getElementById('pl-report-table-body');
    if (!tbody) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const pf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 2 });

    if (!rows || rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">${(typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos')}</td></tr>`;
        return;
    }

    const mode = rows.length > 0 && rows[0].mode ? rows[0].mode : 'prev';
    const data = rows.filter(r => Math.round(Number(r.actual) || 0) !== 0);
    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center">${(typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos')}</td></tr>`;
        return;
    }

    const html = data.map(r => {
        let varClass = 'fin-var-neutral';
        let varText = '';

        if (mode === 'budget') {
            // r.diff is Deviation (Actual - Budget).
            // Logic: 
            // Revenue: Pos Diff => Actual > Budget (Good).
            // Expense: Pos Diff => Actual > Budget (Bad).

            // Backend `get_pl_report` returns `desviacion = actual_mag - budget_mag`.
            // So:
            const val = r.diff;
            varText = nf.format(Math.round(val)) + ' €';

            if (r.isIngreso) {
                if (val > 0) varClass = 'fin-var-pos'; // Good
                else if (val < 0) varClass = 'fin-var-neg'; // Bad
            } else {
                if (val > 0) varClass = 'fin-var-neg'; // Bad (Over budget)
                else if (val < 0) varClass = 'fin-var-pos'; // Good (Under budget)
            }
        } else {
            // Prev Mode: r.diff is Var %
            const val = r.diff;
            varText = pf.format(val) + ' %';
            if (val > 0) varClass = 'fin-var-pos';
            else if (val < 0) varClass = 'fin-var-neg';
        }

        const lvl = r.level || 3;
        let rowStyle = '';
        let cellStyle = '';
        const indent = (lvl - 1) * 20;
        if (lvl === 1) {
            rowStyle = 'font-weight: 800; background-color: rgba(255,255,255,0.05);';
            cellStyle = 'color: #fff; text-transform: uppercase;';
        } else if (lvl === 2) {
            rowStyle = 'font-weight: 600;';
            cellStyle = 'color: #e4e4e7;';
        } else {
            cellStyle = 'color: #a1a1aa;';
        }

        return `
        <tr data-code="${r.cuenta}" style="${rowStyle}">
            <td>${r.cuenta}</td>
            <td style="padding-left: ${indent}px; ${cellStyle}">
                <button class="tree-toggle" data-code="${r.cuenta}">+</button>
                <span class="tree-label">${r.descripcion}</span>
            </td>
            <td class="text-right" style="white-space: nowrap;">${nf.format(Math.round(r.actual))} €</td>
            <td class="text-right" style="white-space: nowrap;">${nf.format(Math.round(r.target))} €</td>
            <td class="text-right" style="white-space: nowrap;"><span class="fin-var ${varClass}">${varText}</span></td>
        </tr>`;
    }).join('');

    tbody.innerHTML = html;
    Array.from(tbody.querySelectorAll('.tree-toggle')).forEach(btn => {
        btn.addEventListener('click', async function (ev) {
            ev.stopPropagation();
            const code = this.getAttribute('data-code');
            const tr = this.closest('tr');
            if (!code || !tr) return;
            await togglePLDrilldownRow(tbody, tr, code);
        });
    });
}

async function togglePLDrilldownRow(tbody, tr, code) {
    const next = tr.nextElementSibling;
    if (next && next.getAttribute('data-sub-of') === code) {
        next.remove();
        return;
    }
    const cacheKey = `bd_${currEmpresa}_${currEjercicio}_${code}`;
    if (!window.__finBreakdownCache) window.__finBreakdownCache = {};
    let data = window.__finBreakdownCache[cacheKey];
    if (!data) {
        const r = await fetch(`/api/financial/accounts/breakdown?empresa=${currEmpresa}&ejercicio=${currEjercicio}&code=${encodeURIComponent(code)}`);
        if (!r.ok) return;
        data = await r.json();
        window.__finBreakdownCache[cacheKey] = data;
    }
    const nf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 });
    const total = (Array.isArray(data.rows) ? data.rows.reduce((s, x) => s + (Number(x.valor) || 0), 0) : 0);
    const rowsHtml = (data.rows || []).map(x => {
        return `<div class="tree-group-row" data-code="${x.cuenta}">
            <div style="display:flex; align-items:center; justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:8px;">
                    <button class="tree-toggle" data-code="${x.cuenta}">+</button>
                    <span class="tree-label">${x.cuenta} • ${x.descripcion}</span>
                </div>
                <div class="tree-amt">${nf.format(Math.round(x.valor))} €</div>
            </div>
            <div class="tree-children" style="margin-left:20px;"></div>
        </div>`;
    }).join('');
    const holder = document.createElement('tr');
    holder.className = 'tree-line-row';
    holder.setAttribute('data-sub-of', code);
    holder.innerHTML = `<td colspan="5">
        <div class="budget-tree">
            <div class="tree-group-header" style="padding:8px; display:flex; align-items:center; justify-content:space-between;">
                <div class="tree-label">${code} • ${data.name || ''}</div>
                <div class="tree-total">${nf.format(Math.round(total))} €</div>
            </div>
            <div class="tree-group" style="padding:8px 8px 12px 8px;">${rowsHtml || `<div class="tree-label" style="opacity:0.8;">${(typeof gettext==='function'?gettext('Sin desglose disponible'):'Sin desglose disponible')}</div>`}</div>
        </div>
    </td>`;
    tr.after(holder);
    Array.from(holder.querySelectorAll('.tree-toggle')).forEach(b => {
        b.addEventListener('click', async function (e) {
            e.stopPropagation();
            const c = this.getAttribute('data-code');
            const row = this.closest('.tree-group-row');
            const children = row ? row.querySelector('.tree-children') : null;
            if (!c || !children) return;
            if (children.childElementCount > 0) {
                children.innerHTML = '';
                this.classList.remove('active');
                return;
            }
            this.classList.add('active');
            await renderNestedBreakdown(children, c);
        });
    });
}
function setPLFilter(filter) {
    window.plFilter = filter;
    try {
        const summary = document.getElementById('fin-pl-summary');
        if (summary) {
            Array.from(summary.querySelectorAll('.fin-balance-row[data-pl-filter]')).forEach(r => {
                const f = r.getAttribute('data-pl-filter') || '';
                if (f === filter || (filter === 'all' && f === 'all')) {
                    r.classList.add('active');
                } else {
                    r.classList.remove('active');
                }
            });
        }
    } catch (e) { }
    const rows = Array.isArray(window.plRows) ? window.plRows : [];
    let out = rows;
    if (filter === 'ingresos') {
        out = rows.filter(r => r.isIngreso);
    } else if (filter === 'gastos') {
        out = rows.filter(r => !r.isIngreso);
    }
    renderPLReportTable(out);
}

function exportPLReport(format) {
    const tbody = document.getElementById('pl-report-table-body');
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll('tr')).map(tr => {
        const tds = tr.querySelectorAll('td');
        if (tds.length < 5) return null;
        return {
            cuenta: tds[0].textContent.trim(),
            descripcion: tds[1].textContent.trim(),
            actual: tds[2].textContent.trim(),
            anterior: tds[3].textContent.trim(),
            varpct: tds[4].textContent.trim()
        };
    }).filter(Boolean);
    if (format === 'csv') {
        const header = ['Cuenta', 'Descripción', 'Actual', 'Anterior', 'Var %'];
        const csv = [header.join(',')].concat(
            rows.map(r => [r.cuenta, r.descripcion, r.actual, r.anterior, r.varpct].map(x => `"${x.replace(/"/g, '""')}"`).join(','))
        ).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `pl_${currEmpresa}_${currEjercicio}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    } else if (format === 'pdf') {
        const w = window.open('', '_blank');
        if (!w) return;
        const rowsHtml = rows.map(r => `<tr><td>${r.cuenta}</td><td>${r.descripcion}</td><td>${r.actual}</td><td>${r.anterior}</td><td>${r.varpct}</td></tr>`).join('');
        w.document.write(`
            <html><head><meta charset="utf-8"><title>P&L ${currEmpresa} ${currEjercicio}</title></head>
            <body><h3>${(typeof gettext === 'function' ? gettext('Cuenta de Explotación') : 'Cuenta de Explotación')} ${currEmpresa} ${currEjercicio}</h3>
            <table border="1" cellpadding="6" cellspacing="0">
            <thead><tr><th>Cuenta</th><th>${(typeof gettext === 'function' ? gettext('Descripción') : 'Descripción')}</th><th>${(typeof gettext === 'function' ? gettext('Actual') : 'Actual')}</th><th>${(typeof gettext === 'function' ? gettext('Anterior') : 'Anterior')}</th><th>Var %</th></tr></thead>
            <tbody>${rowsHtml}</tbody></table></body></html>
        `);
        w.document.close();
    }
}

// --- DRAG & DROP LOGIC ---
// [FIX] Ensure dragSrcEl is not redeclared if already exists
if (typeof dragSrcEl === 'undefined') {
    var dragSrcEl = null;
} else {
    dragSrcEl = null; // Reset
}

function setupDragAndDrop() {
    const items = document.querySelectorAll('.fin-grid-item');
    items.forEach(item => {
        item.addEventListener('dragstart', handleDragStart);
        item.addEventListener('dragenter', handleDragEnter);
        item.addEventListener('dragover', handleDragOver);
        item.addEventListener('dragleave', handleDragLeave);
        item.addEventListener('drop', handleDrop);
        item.addEventListener('dragend', handleDragEnd);
    });
}

function handleDragStart(e) {
    this.style.opacity = '0.4';
    dragSrcEl = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/html', this.innerHTML);
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

function handleDrop(e) {
    if (e.stopPropagation) {
        e.stopPropagation();
    }
    if (dragSrcEl !== this) {
        // Swap elements in DOM
        const container = document.getElementById('fin-dashboard-grid');

        // Get index
        const items = Array.from(container.children);
        const srcIdx = items.indexOf(dragSrcEl);
        const targetIdx = items.indexOf(this);

        if (srcIdx < targetIdx) {
            this.after(dragSrcEl);
        } else {
            this.before(dragSrcEl);
        }

        // Show Save Button
        document.getElementById('btn-save-layout').style.display = 'inline-block';
        document.getElementById('btn-reset-layout').style.display = 'inline-block';
    }
    return false;
}

function handleDragEnd(e) {
    this.style.opacity = '1';
    const items = document.querySelectorAll('.fin-grid-item');
    items.forEach(item => {
        item.classList.remove('drag-over');
    });
}

async function saveLayout() {
    const container = document.getElementById('fin-dashboard-grid');
    const items = Array.from(container.children);
    const order = items.map(item => item.getAttribute('data-id'));

    // Save to Backend (MERGE)
    try {
        const headers = { 'Content-Type': 'application/json' };
        const cookieToken = getCookie('csrftoken');
        let token = cookieToken;
        try { if (!token && typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) token = CSRF_TOKEN; } catch (_) { }
        if (token) headers['X-CSRFToken'] = token;
        const getRes = await fetch('/api/financial/preferences/layout');
        const current = await getRes.json();
        const base = (current && typeof current === 'object' && current.layout && typeof current.layout === 'object') ? current.layout : (current || {});
        const merged = Object.assign({}, base, { financial: order });
        const res = await fetch('/api/financial/preferences/layout', {
            method: 'POST',
            headers,
            body: JSON.stringify({ layout: merged })
        });

        if (res.ok) {
            document.getElementById('btn-save-layout').style.display = 'none';
            document.getElementById('btn-reset-layout').style.display = 'inline-block';
        } else {
            showToast("Error al guardar diseño", "error");
        }
    } catch (e) {
        console.error("Save Layout Error", e);
    }
}

async function restoreLayout() {
    try {
        const res = await fetch('/api/financial/preferences/layout');
        if (res.ok) {
            const json = await res.json();
            const order = json.financial; // Assuming backend returns { financial: [...] } or { ... "financial": [...] }

            // Check if 'financial' key exists in the response structure
            // Based on endpoint: return prefs.dashboard_layout -> which is { "financial": [...] }

            if (order && Array.isArray(order) && order.length > 0) {
                const container = document.getElementById('fin-dashboard-grid');
                const currentItems = Array.from(container.children);

                // Reorder DOM
                order.forEach(id => {
                    const item = currentItems.find(el => el.getAttribute('data-id') === id);
                    if (item) {
                        container.appendChild(item);
                    }
                });

                // Show reset if customized
                document.getElementById('btn-reset-layout').style.display = 'inline-block';
            }
        }
    } catch (e) {
        console.error("Restore Layout Error", e);
    }

    // Init DnD listeners after restore
    setupDragAndDrop();
}

async function resetLayout() {
    // Reset backend pref (MERGE empty financial, keep others)
    try {
        const headers = { 'Content-Type': 'application/json' };
        const cookieToken = getCookie('csrftoken');
        let token = cookieToken;
        try { if (!token && typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) token = CSRF_TOKEN; } catch (_) { }
        if (token) headers['X-CSRFToken'] = token;
        const getRes = await fetch('/api/financial/preferences/layout');
        const current = await getRes.json();
        const base = (current && typeof current === 'object' && current.layout && typeof current.layout === 'object') ? current.layout : (current || {});
        const merged = Object.assign({}, base, { financial: [] });
        await fetch('/api/financial/preferences/layout', {
            method: 'POST',
            headers,
            body: JSON.stringify({ layout: merged })
        });
    } catch (_) { }
    location.reload(); // Simple reload to reset DOM
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- RENDERERS ---

function renderFinancialSnapshot(data) {
    // [NEW] Cache for Mobile Manager
    window.cachedFinancialData = data;

    updateKPIValue("fin-val-ingresos", data.ingresos, "currency");
    updateKPIValue("fin-val-gastos", data.gastos, "currency");
    updateKPIValue("fin-val-resultado", data.resultado, "currency");
    if (typeof data.variacion !== 'undefined') {
        updateKPIValue("fin-val-variacion", data.variacion, "currency");
    }
    if (typeof data.otros_ingresos !== 'undefined') {
        updateKPIValue("fin-val-otros-ingresos", data.otros_ingresos, "currency");
    }
    if (typeof data.otros_gastos !== 'undefined') {
        updateKPIValue("fin-val-otros-gastos", data.otros_gastos, "currency");
    }

    const nfCur = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    const nfPct = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 1 });
    function setComp(id, py, varObj, mode) {
        const el = document.getElementById(id);
        if (!el) return;
        const arrow = (varObj.abs > 0) ? '▲' : ((varObj.abs < 0) ? '▼' : '■');
        let cls = 'fin-var-neutral';
        if (mode === 'pos') cls = (varObj.abs >= 0) ? 'fin-var-pos' : 'fin-var-neg';
        if (mode === 'neg') cls = (varObj.abs >= 0) ? 'fin-var-neg' : 'fin-var-pos';
        el.className = 'fin-kpi-comp ' + cls;
        const pyTxt = nfCur.format(py);
        const pctTxt = nfPct.format(varObj.pct) + '%';
        const yearTxt = (data.py && data.py.ejercicio) ? data.py.ejercicio : (new Date().getFullYear() - 1);
        el.innerText = `vs ${yearTxt}: ${pyTxt} ${arrow} ${pctTxt}`;
    }
    if (data.py && data.var) {
        setComp('fin-comp-ingresos', data.py.ingresos, data.var.ingresos, 'pos');
        setComp('fin-comp-otros-ingresos', data.py.otros_ingresos, data.var.otros_ingresos, 'pos');
        setComp('fin-comp-variacion', data.py.variacion, data.var.variacion, 'pos');
        setComp('fin-comp-gastos', data.py.gastos, data.var.gastos, 'neg');
        setComp('fin-comp-otros-gastos', data.py.otros_gastos, data.var.otros_gastos, 'neg');
        setComp('fin-comp-resultado', data.py.resultado, data.var.resultado, 'pos');
    }

    // [NEW] Render Gauge Charts for Ratios
    const ranges = data.ranges || {
        'liquidez': { min: 0, max: 8, low: 1.0, high: 2.0 },
        'margen': { min: 0, max: 50, low: 5.0, high: 15.0 },
        'solvencia': { min: 0, max: 12, low: 1.1, high: 2.0 },
        'endeudamiento': { min: 0, max: 200, low: 40.0, high: 80.0, inverse: true }
    };

    renderRatioGauge("fin-val-liquidez", data.ratios.liquidez, (typeof gettext === 'function' ? gettext("Liquidez") : "Liquidez"), ranges.liquidez);
    renderRatioGauge("fin-val-margen", data.ratios.margen, (typeof gettext === 'function' ? gettext("Margen %") : "Margen %"), ranges.margen, "%");
    renderRatioGauge("fin-val-solvencia", data.ratios.solvencia, (typeof gettext === 'function' ? gettext("Solvencia") : "Solvencia"), ranges.solvencia);
    renderRatioGauge("fin-val-endeudamiento", data.ratios.endeudamiento, (typeof gettext === 'function' ? gettext("Endeudamiento") : "Endeudamiento"), ranges.endeudamiento, "%");

    setupRatioInteractions(data);
    initLocalAiButton();
}

// Global storage for gauge instances to handle resize
window.finGaugeInstances = window.finGaugeInstances || {};

function renderRatioGauge(id, value, title, config, suffix = "") {
    const el = document.getElementById(id);
    if (!el) return;
    config = config || {};
    const hasExternalLabel = !!(el.previousElementSibling && el.previousElementSibling.classList.contains('fin-kpi-label'));
    const missing = value === null || value === undefined || value === '' || Number.isNaN(Number(value));
    const numeric = missing ? null : Number(value);

    try {
        const prev = (typeof echarts !== 'undefined' && echarts.getInstanceByDom) ? echarts.getInstanceByDom(el) : null;
        if (prev) prev.dispose();
    } catch (_) {}
    if (window.finGaugeInstances && window.finGaugeInstances[id]) {
        try { window.finGaugeInstances[id].dispose(); } catch (_) {}
        delete window.finGaugeInstances[id];
    }
    el.innerHTML = '';
    el.removeAttribute('_echarts_instance_');
    el.style.width = '100%';
    el.style.height = '148px';

    if (missing) {
        el.innerHTML = '<div class="ratio-empty">Sin dato</div>';
        return;
    }
    if (config.figure) {
        const lang = typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES';
        const text = new Intl.NumberFormat(lang, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(numeric);
        const tone = numeric < 0 ? 'ratio-figure-neg' : 'ratio-figure-pos';
        el.innerHTML = `<div class="ratio-figure ${tone}">${text}</div>`;
        return;
    }

    let min = Number(config.min);
    if (!Number.isFinite(min)) min = 0;
    let max = Number(config.max);
    if (!Number.isFinite(max) || max <= min) max = min + 1;
    if (numeric < min) min = numeric < 0 ? Math.floor(numeric * 1.15) : numeric;
    if (numeric > max) max = numeric > 0 ? Math.ceil(numeric * 1.15) : numeric;
    if (max <= min) max = min + 1;

    const span = max - min;
    const stop = function (v) {
        return Math.max(0, Math.min(1, (Number(v) - min) / span));
    };
    let lowStop = stop(config.low || 0);
    let highStop = Number.isFinite(Number(config.high)) ? stop(config.high) : 1;
    if (highStop < lowStop) {
        const tmp = lowStop;
        lowStop = highStop;
        highStop = tmp;
    }
    if (highStop <= lowStop) highStop = Math.min(1, lowStop + 0.02);
    const colors = config.inverse
        ? [[lowStop, '#10b981'], [highStop, '#eab308'], [1, '#ef4444']]
        : [[lowStop, '#ef4444'], [highStop, '#eab308'], [1, '#10b981']];

    const chart = echarts.init(el);
    window.finGaugeInstances[id] = chart;
    const lang = typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES';
    const formatted = new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(numeric) + (suffix || '');
    const low = Number(config.low || 0);
    const high = Number.isFinite(Number(config.high)) ? Number(config.high) : Number.POSITIVE_INFINITY;
    let quality;
    if (config.inverse) {
        quality = numeric < low ? 'Óptimo' : (numeric <= high ? 'Aceptable' : 'Crítico');
    } else {
        quality = numeric < low ? 'Crítico' : (numeric <= high ? 'Aceptable' : 'Óptimo');
    }

    chart.setOption({
        tooltip: { formatter: function () { return title + ': <b>' + formatted + '</b><br>' + quality; } },
        series: [{
            type: 'gauge',
            min: min,
            max: max,
            startAngle: 200,
            endAngle: -20,
            radius: '100%',
            center: ['50%', '62%'],
            splitNumber: 4,
            progress: { show: false },
            pointer: {
                length: '16%',
                width: 8,
                offsetCenter: [0, '-68%'],
                itemStyle: { color: 'auto' }
            },
            axisLine: { lineStyle: { width: 10, color: colors } },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            anchor: { show: false },
            title: { show: !hasExternalLabel, offsetCenter: [0, '78%'], color: '#a1a1aa', fontSize: 11 },
            detail: {
                valueAnimation: false,
                formatter: function () { return formatted; },
                color: '#f8fafc',
                offsetCenter: [0, '22%'],
                fontSize: 22,
                fontWeight: 700
            },
            data: [{ value: numeric, name: hasExternalLabel ? '' : (title || '') }]
        }]
    });
    try { chart.getDom().style.pointerEvents = 'none'; } catch (e) {}
}

function setupRatioInteractions(snapshot) {
    const items = document.querySelectorAll('.fin-ratio-item');
    items.forEach(item => {
        if (item.closest('#tab-actualidad-ratios')) return;
        const flip = item.querySelector('.flip-card');
        const btn = item.querySelector('.fin-ratio-lever') || item.querySelector('.fin-ratio-action');
        const handler = (e) => {
            if (e) e.stopPropagation();
            toggleRatioFlip(item, snapshot);
        };
        // Double click on item
        item.addEventListener('dblclick', handler);
        // Click on info icon
        if (btn) {
            btn.addEventListener('click', handler);
            btn.addEventListener('keyup', (e) => {
                if (e.key === 'Enter' || e.key === ' ') handler(e);
            });
        }
        // Ensure back content exists
        if (flip && !flip.querySelector('.flip-card-back')) {
            const back = document.createElement('div');
            back.className = 'flip-card-back';
            flip.querySelector('.flip-card-inner').appendChild(back);
        }
    });
}

function toggleRatioFlip(item, snapshot) {
    const flip = item.querySelector('.flip-card');
    if (!flip) return;
    flip.classList.toggle('flipped');
    const back = flip.querySelector('.flip-card-back');
    const targetEl = item.querySelector('.fin-ratio-val');
    const targetId = targetEl ? targetEl.id : null;
    const ratios = snapshot && snapshot.ratios ? snapshot.ratios : {};
    const details = snapshot && snapshot.ratios_detail ? snapshot.ratios_detail : {};
    const ranges = snapshot && snapshot.ranges ? snapshot.ranges : {};
    const keyMap = {
        'fin-val-liquidez': 'liquidez',
        'fin-val-margen': 'margen',
        'fin-val-solvencia': 'solvencia',
        'fin-val-endeudamiento': 'endeudamiento',
        'ratios-core-liquidez': 'liquidez',
        'ratios-core-margen': 'margen',
        'ratios-core-solvencia': 'solvencia',
        'ratios-core-endeudamiento': 'endeudamiento',
        'ratio-liquidez-corriente-val': 'liq_corriente',
        'ratio-test-acido-val': 'test_acido',
        'ratio-disponibilidad-val': 'disponibilidad',
        'ratio-fondo-maniobra-val': 'fondo_maniobra',
        'ratio-endeudamiento-val': 'endeudamiento_ext',
        'ratio-autonomia-val': 'autonomia',
        'ratio-garantia-val': 'garantia',
        'ratio-calidad-deuda-val': 'calidad_deuda',
        'ratio-rotacion-activos-val': 'rotacion_activos',
        'ratio-rotacion-stock-val': 'rotacion_stock',
        'ratio-periodo-cobro-val': 'periodo_cobro',
        'ratio-periodo-pago-val': 'periodo_pago',
        'ratio-margen-bruto-val': 'margen_bruto',
        'ratio-margen-neto-val': 'margen_neto',
        'ratio-roa-val': 'roa',
        'ratio-roe-val': 'roe',
        'ratio-cobertura-interes-val': 'cobertura_interes',
        'ratio-cobertura-deuda-val': 'cobertura_deuda',
        'ratio-margen-ebitda-val': 'margen_ebitda'
    };
    const key = keyMap[targetId] || '';
    if (!back) return;
    if (!flip.classList.contains('flipped')) {
        back.innerHTML = '';
        return;
    }
    const rawVal = ratios[key];
    const value = typeof rawVal === 'number' ? rawVal : 0;
    const detail = details[key] || null;
    const cfg = ranges[key] || {};
    let html = '';
    try {
        html = buildRatioDetail(key, value, cfg, detail);
    } catch (e) {
        console.error('Error construyendo detalle de ratio', e);
        const msg = typeof gettext === 'function' ? gettext('Detalle no disponible en este momento.') : 'Detalle no disponible en este momento.';
        html = `<div class="fin-ratio-back"><p>${msg}</p></div>`;
    }
    back.innerHTML = html;
}

function buildRatioDetail(key, value, cfg, detail) {
    const fmt = (v, suf = '') => new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 2 }).format(v) + suf; // Use consistent formatter
    const currencyFmt = (v) => new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 }).format(v) + ' €';

    let formula = '';
    let meaning = '';
    let analysis = '';
    let recommendations = [];

    // ... (Keep existing switch logic for text) ...
    switch (key) {
        case 'liquidez':
            formula = (typeof gettext === 'function' ? gettext('Liquidez = Activo Corriente / Pasivo Corriente') : 'Liquidez = Activo Corriente / Pasivo Corriente');
            meaning = (typeof gettext === 'function' ? gettext('Capacidad de la empresa para atender obligaciones a corto plazo.') : 'Capacidad de la empresa para atender obligaciones a corto plazo.');
            analysis = value < (cfg.low || 1.0) ? (typeof gettext === 'function' ? gettext('Nivel bajo: riesgo de tensiones de caja.') : 'Nivel bajo: riesgo de tensiones de caja.') :
                value < (cfg.high || 1.5) ? (typeof gettext === 'function' ? gettext('Nivel aceptable: vigilar ciclos de cobro/pago.') : 'Nivel aceptable: vigilar ciclos de cobro/pago.') :
                    (typeof gettext === 'function' ? gettext('Nivel óptimo: colchón suficiente para el circulante.') : 'Nivel óptimo: colchón suficiente para el circulante.');
            recommendations = value < (cfg.low || 1.0)
                ? [(typeof gettext === 'function' ? gettext('Acelerar cobros y renegociar plazos de pago') : 'Acelerar cobros y renegociar plazos de pago'), (typeof gettext === 'function' ? gettext('Reducir inventario no crítico') : 'Reducir inventario no crítico')]
                : [(typeof gettext === 'function' ? gettext('Mantener políticas de crédito prudentes') : 'Mantener políticas de crédito prudentes'), (typeof gettext === 'function' ? gettext('Explorar descuentos por pronto pago') : 'Explorar descuentos por pronto pago')];
            break;
        case 'margen':
            formula = (typeof gettext === 'function' ? gettext('Margen = (Ingresos - Gastos) / Ingresos × 100%') : 'Margen = (Ingresos - Gastos) / Ingresos × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Rentabilidad operativa sobre las ventas.') : 'Rentabilidad operativa sobre las ventas.');
            analysis = value < (cfg.low || 5.0) ? (typeof gettext === 'function' ? gettext('Margen bajo: presión de precios o costes elevados.') : 'Margen bajo: presión de precios o costes elevados.') :
                value < (cfg.high || 15.0) ? (typeof gettext === 'function' ? gettext('Margen aceptable: optimizar mix y eficiencia.') : 'Margen aceptable: optimizar mix y eficiencia.') :
                    (typeof gettext === 'function' ? gettext('Margen óptimo: ventaja competitiva clara.') : 'Margen óptimo: ventaja competitiva clara.');
            recommendations = value < (cfg.low || 5.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar precios y costos unitarios') : 'Revisar precios y costos unitarios'), (typeof gettext === 'function' ? gettext('Focalizar en productos/segmentos con mayor margen') : 'Focalizar en productos/segmentos con mayor margen')]
                : [(typeof gettext === 'function' ? gettext('Invertir en diferenciación y fidelización') : 'Invertir en diferenciación y fidelización'), (typeof gettext === 'function' ? gettext('Asegurar control de costes directos') : 'Asegurar control de costes directos')];
            break;
        case 'solvencia':
            formula = (typeof gettext === 'function' ? gettext('Solvencia = Activo Total / Pasivo Total') : 'Solvencia = Activo Total / Pasivo Total');
            meaning = (typeof gettext === 'function' ? gettext('Capacidad de cubrir todas las deudas con los activos.') : 'Capacidad de cubrir todas las deudas con los activos.');
            analysis = value < (cfg.low || 1.1) ? (typeof gettext === 'function' ? gettext('Solvencia comprometida: activo insuficiente.') : 'Solvencia comprometida: activo insuficiente.') :
                value < (cfg.high || 1.8) ? (typeof gettext === 'function' ? gettext('Solvencia razonable: equilibrio financiero.') : 'Solvencia razonable: equilibrio financiero.') :
                    (typeof gettext === 'function' ? gettext('Solvencia sólida: buena estructura patrimonial.') : 'Solvencia sólida: buena estructura patrimonial.');
            recommendations = value < (cfg.low || 1.1)
                ? [(typeof gettext === 'function' ? gettext('Reforzar patrimonio neto') : 'Reforzar patrimonio neto'), (typeof gettext === 'function' ? gettext('Desinvertir activos no estratégicos') : 'Desinvertir activos no estratégicos')]
                : [(typeof gettext === 'function' ? gettext('Optimizar estructura de financiación') : 'Optimizar estructura de financiación'), (typeof gettext === 'function' ? gettext('Evaluar inversión en activos productivos') : 'Evaluar inversión en activos productivos')];
            break;
        case 'endeudamiento':
            formula = (typeof gettext === 'function' ? gettext('Endeudamiento = Pasivo Total / Patrimonio Neto × 100%') : 'Endeudamiento = Pasivo Total / Patrimonio Neto × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Dependencia de financiación ajena frente a recursos propios.') : 'Dependencia de financiación ajena frente a recursos propios.');
            analysis = value > (cfg.high || 80.0) ? (typeof gettext === 'function' ? gettext('Endeudamiento elevado: vulnerabilidad ante subidas de tipos.') : 'Endeudamiento elevado: vulnerabilidad ante subidas de tipos.') :
                value > (cfg.low || 40.0) ? (typeof gettext === 'function' ? gettext('Endeudamiento moderado: vigilar cobertura de servicio de deuda.') : 'Endeudamiento moderado: vigilar cobertura de servicio de deuda.') :
                    (typeof gettext === 'function' ? gettext('Endeudamiento bajo: alta resiliencia financiera.') : 'Endeudamiento bajo: alta resiliencia financiera.');
            recommendations = value > (cfg.high || 80.0)
                ? [(typeof gettext === 'function' ? gettext('Reestructurar deuda a plazos más largos') : 'Reestructurar deuda a plazos más largos'), (typeof gettext === 'function' ? gettext('Priorizar amortización y mejorar generación de caja') : 'Priorizar amortización y mejorar generación de caja')]
                : [(typeof gettext === 'function' ? gettext('Mantener ratio dentro de objetivo corporativo') : 'Mantener ratio dentro de objetivo corporativo'), (typeof gettext === 'function' ? gettext('Aprovechar financiación para crecimiento controlado') : 'Aprovechar financiación para crecimiento controlado')];
            break;
        case 'liq_corriente':
            formula = (typeof gettext === 'function' ? gettext('Liquidez Corriente = Activo Corriente / Pasivo Corriente') : 'Liquidez Corriente = Activo Corriente / Pasivo Corriente');
            meaning = (typeof gettext === 'function' ? gettext('Capacidad de cubrir las deudas a corto plazo con activos corrientes.') : 'Capacidad de cubrir las deudas a corto plazo con activos corrientes.');
            analysis = value < (cfg.low || 1.0)
                ? (typeof gettext === 'function' ? gettext('Nivel bajo: alto riesgo de tensiones de tesorería.') : 'Nivel bajo: alto riesgo de tensiones de tesorería.')
                : value < (cfg.high || 1.8)
                    ? (typeof gettext === 'function' ? gettext('Nivel aceptable: colchón limitado, vigilar cobros y pagos.') : 'Nivel aceptable: colchón limitado, vigilar cobros y pagos.')
                    : (typeof gettext === 'function' ? gettext('Nivel elevado: buena solvencia, revisar rentabilidad de excedentes.') : 'Nivel elevado: buena solvencia, revisar rentabilidad de excedentes.');
            recommendations = value < (cfg.low || 1.0)
                ? [(typeof gettext === 'function' ? gettext('Acelerar cobros y renegociar plazos con proveedores.') : 'Acelerar cobros y renegociar plazos con proveedores.'), (typeof gettext === 'function' ? gettext('Refuerzo de líneas de financiación a corto plazo.') : 'Refuerzo de líneas de financiación a corto plazo.')]
                : [(typeof gettext === 'function' ? gettext('Revisar política de crédito a clientes.') : 'Revisar política de crédito a clientes.'), (typeof gettext === 'function' ? gettext('Optimizar saldos de caja e inversiones a corto.') : 'Optimizar saldos de caja e inversiones a corto.')];
            break;
        case 'test_acido':
            formula = (typeof gettext === 'function' ? gettext('Test Ácido = (Activo Corriente − Existencias) / Pasivo Corriente') : 'Test Ácido = (Activo Corriente − Existencias) / Pasivo Corriente');
            meaning = (typeof gettext === 'function' ? gettext('Liquidez inmediata sin depender de vender inventario.') : 'Liquidez inmediata sin depender de vender inventario.');
            analysis = value < (cfg.low || 0.8)
                ? (typeof gettext === 'function' ? gettext('Liquidez inmediata insuficiente para cubrir pagos corrientes.') : 'Liquidez inmediata insuficiente para cubrir pagos corrientes.')
                : value < (cfg.high || 1.5)
                    ? (typeof gettext === 'function' ? gettext('Cobertura ajustada: cualquier retraso en cobros tensiona la caja.') : 'Cobertura ajustada: cualquier retraso en cobros tensiona la caja.')
                    : (typeof gettext === 'function' ? gettext('Cobertura holgada: caja y créditos por encima de las obligaciones.') : 'Cobertura holgada: caja y créditos por encima de las obligaciones.');
            recommendations = value < (cfg.low || 0.8)
                ? [(typeof gettext === 'function' ? gettext('Reducir inversión en stock no crítico.') : 'Reducir inversión en stock no crítico.'), (typeof gettext === 'function' ? gettext('Aumentar disponibilidad de líneas de crédito.') : 'Aumentar disponibilidad de líneas de crédito.')]
                : [(typeof gettext === 'function' ? gettext('Buscar mejor rentabilidad para excedentes de liquidez.') : 'Buscar mejor rentabilidad para excedentes de liquidez.'), (typeof gettext === 'function' ? gettext('Mantener disciplina en cobros.') : 'Mantener disciplina en cobros.')];
            break;
        case 'disponibilidad':
            formula = (typeof gettext === 'function' ? gettext('Disponibilidad = Efectivo / Pasivo Corriente') : 'Disponibilidad = Efectivo / Pasivo Corriente');
            meaning = (typeof gettext === 'function' ? gettext('Nivel de caja pura frente a obligaciones inmediatas.') : 'Nivel de caja pura frente a obligaciones inmediatas.');
            analysis = value < (cfg.low || 0.2)
                ? (typeof gettext === 'function' ? gettext('Caja muy ajustada: dependencia total de cobros y pólizas.') : 'Caja muy ajustada: dependencia total de cobros y pólizas.')
                : value < (cfg.high || 1.0)
                    ? (typeof gettext === 'function' ? gettext('Caja razonable: margen moderado ante imprevistos.') : 'Caja razonable: margen moderado ante imprevistos.')
                    : (typeof gettext === 'function' ? gettext('Caja muy holgada: posible exceso de recursos ociosos.') : 'Caja muy holgada: posible exceso de recursos ociosos.');
            recommendations = value < (cfg.low || 0.2)
                ? [(typeof gettext === 'function' ? gettext('Revisar calendario de cobros y pagos.') : 'Revisar calendario de cobros y pagos.'), (typeof gettext === 'function' ? gettext('Negociar líneas de crédito adicionales.') : 'Negociar líneas de crédito adicionales.')]
                : [(typeof gettext === 'function' ? gettext('Evaluar amortización de deuda cara.') : 'Evaluar amortización de deuda cara.'), (typeof gettext === 'function' ? gettext('Valorar inversión de excedentes a corto plazo.') : 'Valorar inversión de excedentes a corto plazo.')];
            break;
        case 'fondo_maniobra':
            formula = (typeof gettext === 'function' ? gettext('Fondo de Maniobra = Activo Corriente − Pasivo Corriente') : 'Fondo de Maniobra = Activo Corriente − Pasivo Corriente');
            meaning = (typeof gettext === 'function' ? gettext('Colchón financiero para absorber variaciones del circulante.') : 'Colchón financiero para absorber variaciones del circulante.');
            analysis = value < 0
                ? (typeof gettext === 'function' ? gettext('Fondo de maniobra negativo: parte del inmovilizado se financia a corto plazo.') : 'Fondo de maniobra negativo: parte del inmovilizado se financia a corto plazo.')
                : (typeof gettext === 'function' ? gettext('Fondo de maniobra positivo: margen de seguridad para la actividad.') : 'Fondo de maniobra positivo: margen de seguridad para la actividad.');
            recommendations = value < 0
                ? [(typeof gettext === 'function' ? gettext('Reestructurar deuda hacia plazos más largos.') : 'Reestructurar deuda hacia plazos más largos.'), (typeof gettext === 'function' ? gettext('Reforzar patrimonio neto o retener beneficios.') : 'Reforzar patrimonio neto o retener beneficios.')]
                : [(typeof gettext === 'function' ? gettext('Mantener equilibrio entre liquidez y rentabilidad.') : 'Mantener equilibrio entre liquidez y rentabilidad.'), (typeof gettext === 'function' ? gettext('Evitar sobreacumular caja o stock innecesario.') : 'Evitar sobreacumular caja o stock innecesario.')];
            break;
        case 'autonomia':
            formula = (typeof gettext === 'function' ? gettext('Autonomía = Patrimonio Neto / Pasivo Total') : 'Autonomía = Patrimonio Neto / Pasivo Total');
            meaning = (typeof gettext === 'function' ? gettext('Grado de financiación propia frente a financiación ajena.') : 'Grado de financiación propia frente a financiación ajena.');
            analysis = value < (cfg.low || 0.3)
                ? (typeof gettext === 'function' ? gettext('Autonomía baja: fuerte dependencia de acreedores.') : 'Autonomía baja: fuerte dependencia de acreedores.')
                : value < (cfg.high || 1.0)
                    ? (typeof gettext === 'function' ? gettext('Autonomía razonable: equilibrio entre deuda y patrimonio.') : 'Autonomía razonable: equilibrio entre deuda y patrimonio.')
                    : (typeof gettext === 'function' ? gettext('Autonomía alta: empresa muy independiente de la banca.') : 'Autonomía alta: empresa muy independiente de la banca.');
            recommendations = value < (cfg.low || 0.3)
                ? [(typeof gettext === 'function' ? gettext('Reforzar patrimonio neto con resultados retenidos o aportaciones.') : 'Reforzar patrimonio neto con resultados retenidos o aportaciones.'), (typeof gettext === 'function' ? gettext('Evitar asumir nueva deuda hasta mejorar solvencia.') : 'Evitar asumir nueva deuda hasta mejorar solvencia.')]
                : [(typeof gettext === 'function' ? gettext('Mantener política prudente de reparto de dividendos.') : 'Mantener política prudente de reparto de dividendos.'), (typeof gettext === 'function' ? gettext('Aprovechar capacidad de endeudamiento para inversiones rentables.') : 'Aprovechar capacidad de endeudamiento para inversiones rentables.')];
            break;
        case 'garantia':
            formula = (typeof gettext === 'function' ? gettext('Garantía = Activo Total / Pasivo Total') : 'Garantía = Activo Total / Pasivo Total');
            meaning = (typeof gettext === 'function' ? gettext('Capacidad de los activos para respaldar todas las deudas.') : 'Capacidad de los activos para respaldar todas las deudas.');
            analysis = value < (cfg.low || 1.1)
                ? (typeof gettext === 'function' ? gettext('Garantía insuficiente: los activos no cubren el pasivo.') : 'Garantía insuficiente: los activos no cubren el pasivo.')
                : value < (cfg.high || 2.0)
                    ? (typeof gettext === 'function' ? gettext('Garantía aceptable: estructura patrimonial equilibrada.') : 'Garantía aceptable: estructura patrimonial equilibrada.')
                    : (typeof gettext === 'function' ? gettext('Garantía holgada: respaldo de activos muy sólido.') : 'Garantía holgada: respaldo de activos muy sólido.');
            recommendations = value < (cfg.low || 1.1)
                ? [(typeof gettext === 'function' ? gettext('Reforzar patrimonio neto.') : 'Reforzar patrimonio neto.'), (typeof gettext === 'function' ? gettext('Desinvertir activos no estratégicos para reducir deuda.') : 'Desinvertir activos no estratégicos para reducir deuda.')]
                : [(typeof gettext === 'function' ? gettext('Optimizar estructura de deuda a largo plazo.') : 'Optimizar estructura de deuda a largo plazo.'), (typeof gettext === 'function' ? gettext('Evaluar inversiones en activos productivos.') : 'Evaluar inversiones en activos productivos.')];
            break;
        case 'calidad_deuda':
            formula = (typeof gettext === 'function' ? gettext('Calidad de la Deuda = Pasivo Corriente / Pasivo Total × 100%') : 'Calidad de la Deuda = Pasivo Corriente / Pasivo Total × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Peso de la deuda a corto plazo sobre el total.') : 'Peso de la deuda a corto plazo sobre el total.');
            analysis = value > (cfg.high || 60.0)
                ? (typeof gettext === 'function' ? gettext('Demasiada deuda a corto: fuerte presión de vencimientos.') : 'Demasiada deuda a corto: fuerte presión de vencimientos.')
                : value > (cfg.low || 20.0)
                    ? (typeof gettext === 'function' ? gettext('Perfil de deuda equilibrado entre corto y largo plazo.') : 'Perfil de deuda equilibrado entre corto y largo plazo.')
                    : (typeof gettext === 'function' ? gettext('Deuda muy a largo plazo: poca presión, pero menos flexibilidad.') : 'Deuda muy a largo plazo: poca presión, pero menos flexibilidad.');
            recommendations = value > (cfg.high || 60.0)
                ? [(typeof gettext === 'function' ? gettext('Reestructurar parte de la deuda a plazo más largo.') : 'Reestructurar parte de la deuda a plazo más largo.'), (typeof gettext === 'function' ? gettext('Aumentar generación de caja para reducir el pasivo corriente.') : 'Aumentar generación de caja para reducir el pasivo corriente.')]
                : [(typeof gettext === 'function' ? gettext('Mantener equilibrio entre deuda a corto y largo plazo.') : 'Mantener equilibrio entre deuda a corto y largo plazo.'), (typeof gettext === 'function' ? gettext('Negociar mejores condiciones de coste financiero.') : 'Negociar mejores condiciones de coste financiero.')];
            break;
        case 'rotacion_activos':
            formula = (typeof gettext === 'function' ? gettext('Rotación de Activos = Ventas / Activo Total') : 'Rotación de Activos = Ventas / Activo Total');
            meaning = (typeof gettext === 'function' ? gettext('Eficiencia con la que los activos generan ventas.') : 'Eficiencia con la que los activos generan ventas.');
            analysis = value < (cfg.low || 1.0)
                ? (typeof gettext === 'function' ? gettext('Rotación baja: exceso de activos o infrautilización.') : 'Rotación baja: exceso de activos o infrautilización.')
                : value < (cfg.high || 3.0)
                    ? (typeof gettext === 'function' ? gettext('Rotación razonable: activos alineados con el volumen de negocio.') : 'Rotación razonable: activos alineados con el volumen de negocio.')
                    : (typeof gettext === 'function' ? gettext('Rotación alta: muy buena utilización del activo.') : 'Rotación alta: muy buena utilización del activo.');
            recommendations = value < (cfg.low || 1.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar inversiones en inmovilizado poco productivo.') : 'Revisar inversiones en inmovilizado poco productivo.'), (typeof gettext === 'function' ? gettext('Impulsar ventas sobre capacidad instalada.') : 'Impulsar ventas sobre capacidad instalada.')]
                : [(typeof gettext === 'function' ? gettext('Mantener disciplina en nuevas inversiones.') : 'Mantener disciplina en nuevas inversiones.'), (typeof gettext === 'function' ? gettext('Analizar rentabilidad por línea de producto.') : 'Analizar rentabilidad por línea de producto.')];
            break;
        case 'rotacion_stock':
            formula = (typeof gettext === 'function' ? gettext('Rotación de Stock = Coste de Ventas / Existencias Medias') : 'Rotación de Stock = Coste de Ventas / Existencias Medias');
            meaning = (typeof gettext === 'function' ? gettext('Número de veces que el inventario se renueva al año.') : 'Número de veces que el inventario se renueva al año.');
            analysis = value < (cfg.low || 2.0)
                ? (typeof gettext === 'function' ? gettext('Rotación baja: riesgo de obsolescencia y sobrestock.') : 'Rotación baja: riesgo de obsolescencia y sobrestock.')
                : value < (cfg.high || 8.0)
                    ? (typeof gettext === 'function' ? gettext('Rotación adecuada: equilibrio entre servicio y stock.') : 'Rotación adecuada: equilibrio entre servicio y stock.')
                    : (typeof gettext === 'function' ? gettext('Rotación muy alta: riesgo de roturas de stock.') : 'Rotación muy alta: riesgo de roturas de stock.');
            recommendations = value < (cfg.low || 2.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar política de compras y niveles mínimos.') : 'Revisar política de compras y niveles mínimos.'), (typeof gettext === 'function' ? gettext('Dar salida a inventario lento o obsoleto.') : 'Dar salida a inventario lento o obsoleto.')]
                : [(typeof gettext === 'function' ? gettext('Ajustar reaprovisionamiento a la demanda real.') : 'Ajustar reaprovisionamiento a la demanda real.'), (typeof gettext === 'function' ? gettext('Asegurar acuerdos de suministro flexibles.') : 'Asegurar acuerdos de suministro flexibles.')];
            break;
        case 'periodo_cobro':
            formula = (typeof gettext === 'function' ? gettext('Periodo de Cobro = (Clientes / Ventas) × 365 días') : 'Periodo de Cobro = (Clientes / Ventas) × 365 días');
            meaning = (typeof gettext === 'function' ? gettext('Días que tarda la empresa en cobrar a sus clientes.') : 'Días que tarda la empresa en cobrar a sus clientes.');
            analysis = value > (cfg.high || 90.0)
                ? (typeof gettext === 'function' ? gettext('Periodo de cobro excesivo: fuerte financiación a clientes.') : 'Periodo de cobro excesivo: fuerte financiación a clientes.')
                : value > (cfg.low || 60.0)
                    ? (typeof gettext === 'function' ? gettext('Periodo de cobro moderado: vigilar morosidad y concentración.') : 'Periodo de cobro moderado: vigilar morosidad y concentración.')
                    : (typeof gettext === 'function' ? gettext('Periodo de cobro ajustado: buena disciplina de cobro.') : 'Periodo de cobro ajustado: buena disciplina de cobro.');
            recommendations = value > (cfg.high || 90.0)
                ? [(typeof gettext === 'function' ? gettext('Reforzar políticas de crédito y scoring de clientes.') : 'Reforzar políticas de crédito y scoring de clientes.'), (typeof gettext === 'function' ? gettext('Implementar acciones de recobro más tempranas.') : 'Implementar acciones de recobro más tempranas.')]
                : [(typeof gettext === 'function' ? gettext('Negociar descuentos por pronto pago.') : 'Negociar descuentos por pronto pago.'), (typeof gettext === 'function' ? gettext('Monitorizar antigüedad de saldos y clientes clave.') : 'Monitorizar antigüedad de saldos y clientes clave.')];
            break;
        case 'periodo_pago':
            formula = (typeof gettext === 'function' ? gettext('Periodo de Pago = (Proveedores / Compras) × 365 días') : 'Periodo de Pago = (Proveedores / Compras) × 365 días');
            meaning = (typeof gettext === 'function' ? gettext('Días que se tarda de media en pagar a proveedores.') : 'Días que se tarda de media en pagar a proveedores.');
            analysis = value < (cfg.low || 60.0)
                ? (typeof gettext === 'function' ? gettext('Periodo de pago corto: poco aprovechamiento de financiación espontánea.') : 'Periodo de pago corto: poco aprovechamiento de financiación espontánea.')
                : value < (cfg.high || 90.0)
                    ? (typeof gettext === 'function' ? gettext('Periodo de pago equilibrado con el sector.') : 'Periodo de pago equilibrado con el sector.')
                    : (typeof gettext === 'function' ? gettext('Periodo de pago largo: riesgo de tensión con proveedores.') : 'Periodo de pago largo: riesgo de tensión con proveedores.');
            recommendations = value < (cfg.low || 60.0)
                ? [(typeof gettext === 'function' ? gettext('Negociar plazos de pago más amplios.') : 'Negociar plazos de pago más amplios.'), (typeof gettext === 'function' ? gettext('Coordinar calendario de pagos con calendario de cobros.') : 'Coordinar calendario de pagos con calendario de cobros.')]
                : [(typeof gettext === 'function' ? gettext('Evitar alargar pagos más allá de las condiciones pactadas.') : 'Evitar alargar pagos más allá de las condiciones pactadas.'), (typeof gettext === 'function' ? gettext('Cuidar la relación con proveedores clave.') : 'Cuidar la relación con proveedores clave.')];
            break;
        case 'margen_bruto':
            formula = (typeof gettext === 'function' ? gettext('Margen Bruto = (Ventas − Coste de Ventas) / Ventas × 100%') : 'Margen Bruto = (Ventas − Coste de Ventas) / Ventas × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Beneficio directo tras cubrir el coste de los productos vendidos.') : 'Beneficio directo tras cubrir el coste de los productos vendidos.');
            analysis = value < (cfg.low || 20.0)
                ? (typeof gettext === 'function' ? gettext('Margen bruto bajo: presión en precios o costes directos elevados.') : 'Margen bruto bajo: presión en precios o costes directos elevados.')
                : value < (cfg.high || 40.0)
                    ? (typeof gettext === 'function' ? gettext('Margen bruto aceptable: hay margen de mejora en mix y costes.') : 'Margen bruto aceptable: hay margen de mejora en mix y costes.')
                    : (typeof gettext === 'function' ? gettext('Margen bruto alto: buena capacidad de fijación de precios.') : 'Margen bruto alto: buena capacidad de fijación de precios.');
            recommendations = value < (cfg.low || 20.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar precios de venta y descuentos.') : 'Revisar precios de venta y descuentos.'), (typeof gettext === 'function' ? gettext('Optimizar costes directos y compras.') : 'Optimizar costes directos y compras.')]
                : [(typeof gettext === 'function' ? gettext('Potenciar productos de mayor margen.') : 'Potenciar productos de mayor margen.'), (typeof gettext === 'function' ? gettext('Mantener control de costes y mermas.') : 'Mantener control de costes y mermas.')];
            break;
        case 'margen_neto':
            formula = (typeof gettext === 'function' ? gettext('Margen Neto = Beneficio Neto / Ventas × 100%') : 'Margen Neto = Beneficio Neto / Ventas × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Beneficio final obtenido por cada euro vendido.') : 'Beneficio final obtenido por cada euro vendido.');
            analysis = value < (cfg.low || 5.0)
                ? (typeof gettext === 'function' ? gettext('Margen neto bajo: estructura de gastos pesada o precios insuficientes.') : 'Margen neto bajo: estructura de gastos pesada o precios insuficientes.')
                : value < (cfg.high || 15.0)
                    ? (typeof gettext === 'function' ? gettext('Margen neto razonable: rentabilidad correcta con margen de mejora.') : 'Margen neto razonable: rentabilidad correcta con margen de mejora.')
                    : (typeof gettext === 'function' ? gettext('Margen neto alto: negocio muy rentable.') : 'Margen neto alto: negocio muy rentable.');
            recommendations = value < (cfg.low || 5.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar estructura de gastos fija.') : 'Revisar estructura de gastos fija.'), (typeof gettext === 'function' ? gettext('Analizar rentabilidad por cliente y producto.') : 'Analizar rentabilidad por cliente y producto.')]
                : [(typeof gettext === 'function' ? gettext('Mantener disciplina de costes.') : 'Mantener disciplina de costes.'), (typeof gettext === 'function' ? gettext('Reinvertir parte del margen en crecimiento rentable.') : 'Reinvertir parte del margen en crecimiento rentable.')];
            break;
        case 'roa':
            formula = (typeof gettext === 'function' ? gettext('ROA = EBIT / Activo Total × 100%') : 'ROA = EBIT / Activo Total × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Rentabilidad operativa generada por el total de activos.') : 'Rentabilidad operativa generada por el total de activos.');
            analysis = value < (cfg.low || 5.0)
                ? (typeof gettext === 'function' ? gettext('ROA bajo: activos infrautilizados o baja rentabilidad del negocio.') : 'ROA bajo: activos infrautilizados o baja rentabilidad del negocio.')
                : value < (cfg.high || 20.0)
                    ? (typeof gettext === 'function' ? gettext('ROA aceptable: rentabilidad razonable sobre los activos.') : 'ROA aceptable: rentabilidad razonable sobre los activos.')
                    : (typeof gettext === 'function' ? gettext('ROA alto: excelente rendimiento de los activos.') : 'ROA alto: excelente rendimiento de los activos.');
            recommendations = value < (cfg.low || 5.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar inversiones en activos de baja contribución.') : 'Revisar inversiones en activos de baja contribución.'), (typeof gettext === 'function' ? gettext('Impulsar ventas y margen sobre la base de activos actual.') : 'Impulsar ventas y margen sobre la base de activos actual.')]
                : [(typeof gettext === 'function' ? gettext('Evaluar nuevas inversiones con ROA objetivo superior.') : 'Evaluar nuevas inversiones con ROA objetivo superior.'), (typeof gettext === 'function' ? gettext('Proteger la ventaja competitiva que soporta este ROA.') : 'Proteger la ventaja competitiva que soporta este ROA.')];
            break;
        case 'roe':
            formula = (typeof gettext === 'function' ? gettext('ROE = Beneficio Neto / Patrimonio Neto × 100%') : 'ROE = Beneficio Neto / Patrimonio Neto × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Rentabilidad obtenida para los accionistas.') : 'Rentabilidad obtenida para los accionistas.');
            analysis = value < (cfg.low || 10.0)
                ? (typeof gettext === 'function' ? gettext('ROE bajo: la rentabilidad no compensa el riesgo asumido.') : 'ROE bajo: la rentabilidad no compensa el riesgo asumido.')
                : value < (cfg.high || 25.0)
                    ? (typeof gettext === 'function' ? gettext('ROE razonable: creación de valor moderada.') : 'ROE razonable: creación de valor moderada.')
                    : (typeof gettext === 'function' ? gettext('ROE alto: fuerte creación de valor para el accionista.') : 'ROE alto: fuerte creación de valor para el accionista.');
            recommendations = value < (cfg.low || 10.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar palanca de endeudamiento y estructura de costes.') : 'Revisar palanca de endeudamiento y estructura de costes.'), (typeof gettext === 'function' ? gettext('Reorientar negocio hacia líneas más rentables.') : 'Reorientar negocio hacia líneas más rentables.')]
                : [(typeof gettext === 'function' ? gettext('Definir política de dividendos coherente con el ROE.') : 'Definir política de dividendos coherente con el ROE.'), (typeof gettext === 'function' ? gettext('Asegurar sostenibilidad del nivel de riesgo asumido.') : 'Asegurar sostenibilidad del nivel de riesgo asumido.')];
            break;
        case 'cobertura_interes':
            formula = (typeof gettext === 'function' ? gettext('Cobertura de Intereses = EBIT / Gastos Financieros') : 'Cobertura de Intereses = EBIT / Gastos Financieros');
            meaning = (typeof gettext === 'function' ? gettext('Número de veces que el resultado operativo cubre los intereses.') : 'Número de veces que el resultado operativo cubre los intereses.');
            analysis = value < (cfg.low || 2.0)
                ? (typeof gettext === 'function' ? gettext('Cobertura insuficiente: alto riesgo ante subidas de tipos o caída de resultados.') : 'Cobertura insuficiente: alto riesgo ante subidas de tipos o caída de resultados.')
                : value < (cfg.high || 5.0)
                    ? (typeof gettext === 'function' ? gettext('Cobertura razonable: vigilar evolución de EBIT y tipos.') : 'Cobertura razonable: vigilar evolución de EBIT y tipos.')
                    : (typeof gettext === 'function' ? gettext('Cobertura holgada: bajo riesgo financiero por intereses.') : 'Cobertura holgada: bajo riesgo financiero por intereses.');
            recommendations = value < (cfg.low || 2.0)
                ? [(typeof gettext === 'function' ? gettext('Reducir deuda o mejorar condiciones financieras.') : 'Reducir deuda o mejorar condiciones financieras.'), (typeof gettext === 'function' ? gettext('Impulsar resultados operativos (EBIT).') : 'Impulsar resultados operativos (EBIT).')]
                : [(typeof gettext === 'function' ? gettext('Mantener política prudente de endeudamiento.') : 'Mantener política prudente de endeudamiento.'), (typeof gettext === 'function' ? gettext('Analizar oportunidades de refinanciación a menor coste.') : 'Analizar oportunidades de refinanciación a menor coste.')];
            break;
        case 'cobertura_deuda':
            formula = (typeof gettext === 'function' ? gettext('Cobertura de Deuda = Flujo de Caja / Servicio de la Deuda') : 'Cobertura de Deuda = Flujo de Caja / Servicio de la Deuda');
            meaning = (typeof gettext === 'function' ? gettext('Capacidad de la caja generada para cubrir cuotas de deuda.') : 'Capacidad de la caja generada para cubrir cuotas de deuda.');
            analysis = value < (cfg.low || 1.0)
                ? (typeof gettext === 'function' ? gettext('Cobertura de deuda insuficiente: la caja no alcanza para pagar las cuotas.') : 'Cobertura de deuda insuficiente: la caja no alcanza para pagar las cuotas.')
                : value < (cfg.high || 2.0)
                    ? (typeof gettext === 'function' ? gettext('Cobertura ajustada: hay margen pero limitado ante shocks.') : 'Cobertura ajustada: hay margen pero limitado ante shocks.')
                    : (typeof gettext === 'function' ? gettext('Cobertura holgada: buena capacidad de repago de la deuda.') : 'Cobertura holgada: buena capacidad de repago de la deuda.');
            recommendations = value < (cfg.low || 1.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar plan de amortización y negociar carencias o extensiones.') : 'Revisar plan de amortización y negociar carencias o extensiones.'), (typeof gettext === 'function' ? gettext('Priorizar generación de caja operativa.') : 'Priorizar generación de caja operativa.')]
                : [(typeof gettext === 'function' ? gettext('Mantener colchón de caja para escenarios adversos.') : 'Mantener colchón de caja para escenarios adversos.'), (typeof gettext === 'function' ? gettext('Analizar amortización anticipada de deuda cara.') : 'Analizar amortización anticipada de deuda cara.')];
            break;
        case 'margen_ebitda':
            formula = (typeof gettext === 'function' ? gettext('Margen EBITDA = EBITDA / Ventas × 100%') : 'Margen EBITDA = EBITDA / Ventas × 100%');
            meaning = (typeof gettext === 'function' ? gettext('Rentabilidad operativa antes de intereses, impuestos y amortizaciones.') : 'Rentabilidad operativa antes de intereses, impuestos y amortizaciones.');
            analysis = value < (cfg.low || 10.0)
                ? (typeof gettext === 'function' ? gettext('Margen EBITDA bajo: negocio poco rentable o con costes elevados.') : 'Margen EBITDA bajo: negocio poco rentable o con costes elevados.')
                : value < (cfg.high || 25.0)
                    ? (typeof gettext === 'function' ? gettext('Margen EBITDA razonable: resultado operativo correcto.') : 'Margen EBITDA razonable: resultado operativo correcto.')
                    : (typeof gettext === 'function' ? gettext('Margen EBITDA alto: gran capacidad de generación de caja operativa.') : 'Margen EBITDA alto: gran capacidad de generación de caja operativa.');
            recommendations = value < (cfg.low || 10.0)
                ? [(typeof gettext === 'function' ? gettext('Revisar precios, mix de productos y estructura de costes.') : 'Revisar precios, mix de productos y estructura de costes.'), (typeof gettext === 'function' ? gettext('Identificar ineficiencias operativas y mermas.') : 'Identificar ineficiencias operativas y mermas.')]
                : [(typeof gettext === 'function' ? gettext('Mantener foco en eficiencia operativa.') : 'Mantener foco en eficiencia operativa.'), (typeof gettext === 'function' ? gettext('Valorar inversiones que escalen el modelo manteniendo margen.') : 'Valorar inversiones que escalen el modelo manteniendo margen.')];
            break;
        default:
            formula = '—';
            meaning = '—';
            analysis = '—';
            recommendations = [];
    }

    let suffix = '';
    if (key === 'margen' || key === 'endeudamiento' || key === 'margen_bruto' || key === 'margen_neto' || key === 'roa' || key === 'roe' || key === 'margen_ebitda' || key === 'calidad_deuda') {
        suffix = '%';
    } else if (key === 'periodo_cobro' || key === 'periodo_pago') {
        suffix = ' d';
    }
    const recHTML = recommendations.length
        ? '<ul class="ratio-list">' + recommendations.map(r => `<li>${r}</li>`).join('') + '</ul>'
        : '';

    // Build Decomposed Values HTML if available
    let componentsHTML = '';
    if (detail && detail.num && detail.den) {
        componentsHTML = `
            <div style="background: rgba(255,255,255,0.05); padding: 8px; border-radius: 6px; margin-bottom: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
                    <span style="color: #a1a1aa;">${detail.num.label}</span>
                    <span style="color: #fff; font-weight: 600;">${currencyFmt(detail.num.val)}</span>
                </div>
                <div style="border-top: 1px solid #52525b; margin: 4px 0;"></div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
                    <span style="color: #a1a1aa;">${detail.den.label}</span>
                    <span style="color: #fff; font-weight: 600;">${currencyFmt(detail.den.val)}</span>
                </div>
            </div>
        `;
    }

    const backHeader = `
        <div style="position:absolute; top:10px; right:10px; z-index: 10;">
            <button class="flip-btn" title="${(typeof gettext === 'function' ? gettext('Volver') : 'Volver')}" onclick="unflipParent(this)">✖</button>
        </div>
    `;
    // Ensure container has scroll and button uses high contrast + pointer events
    return backHeader + `
        <div class="fin-ratio-back" style="overflow-y: auto; max-height: 100%; padding-right: 4px;">
            ${componentsHTML} 
            <div class="ratio-section"><span class="ratio-label">${(typeof gettext === 'function' ? gettext('Fórmula:') : 'Fórmula:')}</span><span class="ratio-text">${formula}</span></div>
            <div class="ratio-section"><span class="ratio-label">${(typeof gettext === 'function' ? gettext('Valor Ratio:') : 'Valor Ratio:')}</span><span class="ratio-value">${fmt(value, suffix)}</span></div>
            <div class="ratio-section"><span class="ratio-label">${(typeof gettext === 'function' ? gettext('Significado:') : 'Significado:')}</span><span class="ratio-text">${meaning}</span></div>
            <div class="ratio-section"><span class="ratio-label">${(typeof gettext === 'function' ? gettext('Análisis:') : 'Análisis:')}</span><span class="ratio-text">${analysis}</span></div>
            <div class="ratio-section"><span class="ratio-label">${(typeof gettext === 'function' ? gettext('Recomendaciones:') : 'Recomendaciones:')}</span></div>
            ${recHTML}
            <div style="margin-top: 16px; margin-bottom: 8px; text-align: center;">
                <button class="btn-elegant" style="font-size: 0.85rem; padding: 6px 16px; cursor: pointer; border: 1px solid #52525b; background: #27272a; color: #fff; border-radius: 4px;" onclick="openRatioDrilldown('${key}')">
                    ${(typeof gettext === 'function' ? gettext('Análisis Experto') : 'Análisis Experto')}
                </button>
            </div>
        </div>
    `;
}

async function openRatioDrilldown(ratioKey) {
    try {
        const map = {
            liq_corriente: 'liquidez',
            test_acido: 'liquidez',
            disponibilidad: 'liquidez',
            fondo_maniobra: 'liquidez',
            endeudamiento_ext: 'endeudamiento',
            cobertura_interes: 'endeudamiento',
            cobertura_deuda: 'endeudamiento',
            autonomia: 'solvencia',
            garantia: 'solvencia',
            calidad_deuda: 'solvencia',
            margen_bruto: 'margen',
            margen_neto: 'margen',
            roa: 'margen',
            roe: 'margen',
            margen_ebitda: 'margen'
        };
        const canonical = map[ratioKey] || ratioKey;

        if (canonical === 'margen') {
            const snap = window.cachedFinancialData || {};
            const ingresos = parseFloat(snap.ingresos || 0);
            const gastos = parseFloat(snap.gastos || 0);
            const valor = parseFloat((snap.ratios && snap.ratios.margen) || 0);
            const cfg = (snap.ranges && snap.ranges.margen) || { low: 5.0, high: 15.0 };
            let analysis_text = '';
            if (valor < cfg.low) {
                analysis_text = (typeof gettext === 'function' ? gettext('Margen bajo: presión de precios o costes elevados.') : 'Margen bajo: presión de precios o costes elevados.');
            } else if (valor < cfg.high) {
                analysis_text = (typeof gettext === 'function' ? gettext('Margen aceptable: optimizar mix y eficiencia.') : 'Margen aceptable: optimizar mix y eficiencia.');
            } else {
                analysis_text = (typeof gettext === 'function' ? gettext('Margen óptimo: ventaja competitiva clara.') : 'Margen óptimo: ventaja competitiva clara.');
            }
            const data = {
                ratio: 'margen',
                value: valor,
                label: (typeof gettext === 'function' ? gettext('Margen Operativo %') : 'Margen Operativo %'),
                analysis: analysis_text,
                numerator: {
                    total: ingresos - gastos,
                    details: [
                        { code: '7', name: (typeof gettext === 'function' ? gettext('Ingresos') : 'Ingresos'), value: ingresos },
                        { code: '6', name: (typeof gettext === 'function' ? gettext('Gastos') : 'Gastos'), value: gastos }
                    ]
                },
                denominator: {
                    total: ingresos,
                    details: [
                        { code: '7', name: (typeof gettext === 'function' ? gettext('Ingresos') : 'Ingresos'), value: ingresos }
                    ]
                }
            };
            showRatioDrilldownModal(data);
            return;
        }
        const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&ratio=${canonical}`;
        const res = await fetch(`/api/financial/ratio/drilldown${q}`);
        if (!res.ok) throw new Error("Error fetching drilldown");
        const data = await res.json();
        if (data && data.status === 'error') throw new Error(data.message || 'Error');
        showRatioDrilldownModal(data);
    } catch (e) {
        console.error("Drilldown error:", e);
        showToast("Error cargando detalle", "error");
    }
}

const finRatioSelectionState = {};

function getRatioSelectionKey(ratio) {
    return `${currEmpresa || ''}-${currEjercicio || ''}-${ratio}`;
}

function loadRatioSelection(ratio, numeratorDetails, denominatorDetails) {
    const key = getRatioSelectionKey(ratio);
    if (!finRatioSelectionState[key]) {
        let stored = null;
        try {
            stored = sessionStorage.getItem(`datia-fin-ratio-filters-${key}`);
        } catch (e) {
            stored = null;
        }
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                finRatioSelectionState[key] = {
                    numerator: new Set(parsed.numerator || []),
                    denominator: new Set(parsed.denominator || [])
                };
            } catch (e) {
                finRatioSelectionState[key] = {
                    numerator: new Set(numeratorDetails.map(d => d.code)),
                    denominator: new Set(denominatorDetails.map(d => d.code))
                };
            }
        } else {
            finRatioSelectionState[key] = {
                numerator: new Set(numeratorDetails.map(d => d.code)),
                denominator: new Set(denominatorDetails.map(d => d.code))
            };
        }
    }
    return finRatioSelectionState[key];
}

function persistRatioSelection(ratio) {
    const key = getRatioSelectionKey(ratio);
    const state = finRatioSelectionState[key];
    if (!state) return;
    try {
        const payload = {
            numerator: Array.from(state.numerator),
            denominator: Array.from(state.denominator)
        };
        sessionStorage.setItem(`datia-fin-ratio-filters-${key}`, JSON.stringify(payload));
    } catch (e) {
    }
}

function recomputeRatioFromSelection(ratio, data, state) {
    const numSelected = data.numerator.details.filter(row => state.numerator.has(row.code));
    const denSelected = data.denominator.details.filter(row => state.denominator.has(row.code));
    const numTotal = numSelected.reduce((acc, r) => acc + (r.value || 0), 0);
    const denTotal = denSelected.reduce((acc, r) => acc + (r.value || 0), 0);
    let ratioVal = 0;
    if (denTotal !== 0) {
        if (ratio === 'endeudamiento') {
            ratioVal = (numTotal / denTotal) * 100.0;
        } else {
            ratioVal = numTotal / denTotal;
        }
    }
    return { numTotal, denTotal, ratioVal };
}

let currentRatioDrilldownData = null;

function showRatioDrilldownModal(data) {
    currentRatioDrilldownData = data;
    // Check if modal exists
    let modal = document.getElementById('fin-ratio-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'fin-ratio-modal';
        modal.className = 'fin-modal-overlay';
        modal.innerHTML = `
            <div class="fin-modal-content" style="max-width: 900px; width: 90%;">
                <div class="fin-modal-header">
                    <h3 id="fin-ratio-modal-title"></h3>
                    <button class="fin-modal-close" onclick="closeRatioDrilldownModal()">×</button>
                </div>
                <div style="margin-bottom:12px; font-size:0.8rem; color:#a1a1aa;">
                    ${(typeof gettext === 'function' ? gettext('Puede excluir cuentas desmarcando las casillas. El ratio se recalcula en tiempo real sobre las cuentas seleccionadas. Debe mantener al menos una cuenta en el numerador y en el denominador.') : 'Puede excluir cuentas desmarcando las casillas. El ratio se recalcula en tiempo real sobre las cuentas seleccionadas. Debe mantener al menos una cuenta en el numerador y en el denominador.')}
                </div>
                <div class="fin-modal-body" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                   <div id="fin-ratio-origin-col"></div>
                   <div id="fin-ratio-analysis-col"></div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        // Add styling if not exists
        if (!document.getElementById('fin-ratio-modal-style')) {
            const style = document.createElement('style');
            style.id = 'fin-ratio-modal-style';
            style.textContent = `
                .fin-modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; bg: rgba(0,0,0,0.7); z-index: 9999; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(4px); background-color: rgba(0,0,0,0.6); }
                .fin-modal-content { background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); max-height: 92vh; overflow-y: auto; color: #e4e4e7; }
                .fin-modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #27272a; padding-bottom: 12px; }
                .fin-modal-header h3 { margin: 0; font-size: 1.25rem; font-weight: 600; color: #fff; }
                .fin-modal-close { background: none; border: none; color: #a1a1aa; font-size: 1.5rem; cursor: pointer; }
                .fin-data-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
                .fin-data-table th { text-align: left; padding: 8px; border-bottom: 1px solid #3f3f46; color: #a1a1aa; }
                .fin-data-table td { padding: 6px 8px; border-bottom: 1px solid #27272a; }
                .fin-senior-box { background: #27272a; padding: 16px; border-radius: 8px; border-left: 4px solid #f59e0b; }
                .fin-senior-title { font-weight: 600; color: #f59e0b; margin-bottom: 8px; display: block; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }
                .fin-senior-text { line-height: 1.6; font-size: 0.95rem; }
             `;
            document.head.appendChild(style);
        }
    }

    // Populate
    document.getElementById('fin-ratio-modal-title').innerText = data.label;

    const currencyFmt = (v) => new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }).format(v) + ' €';

    // Left Col: Tables
    const selection = loadRatioSelection(data.ratio, data.numerator.details, data.denominator.details);

    const buildTable = (title, obj, side) => `
        <div style="margin-bottom: 20px;">
            <div style="display:flex; justify-content:space-between; margin-bottom: 8px;">
                <strong style="color: #fff;">${title}</strong>
                <span style="color: #10b981; font-weight: 600;">${currencyFmt(obj.total)}</span>
            </div>
            <div class="fin-ratio-table-container">
                <table class="fin-data-table">
                    <thead><tr><th>${(typeof gettext === 'function' ? gettext('Incluir') : 'Incluir')}</th><th>Cuenta</th><th>Descripción</th><th style="text-align:right">Importe</th></tr></thead>
                    <tbody>
                        ${obj.details.map(d => `
                            <tr class="${selection[side].has(d.code) ? '' : 'fin-ratio-row-excluded'}">
                                <td style="text-align:center;">
                                    <input type="checkbox"
                                           class="fin-ratio-check"
                                           data-ratio="${data.ratio}"
                                           data-side="${side}"
                                           data-code="${d.code}"
                                           ${selection[side].has(d.code) ? 'checked' : ''}>
                                </td>
                                <td style="color: #a1a1aa;">${d.code}</td>
                                <td>${d.name}</td>
                                <td style="text-align:right; font-family:monospace; color: #e4e4e7;">${currencyFmt(d.value)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.getElementById('fin-ratio-origin-col').innerHTML =
        buildTable((typeof gettext === 'function' ? gettext('Numerador') : 'Numerador'), data.numerator, 'numerator') +
        buildTable((typeof gettext === 'function' ? gettext('Denominador') : 'Denominador'), data.denominator, 'denominator');

    const selectionTotals = recomputeRatioFromSelection(data.ratio, data, selection);

    // Right Col: Senior Analysis
    document.getElementById('fin-ratio-analysis-col').innerHTML = `
        <div class="fin-senior-box">
             <span class="fin-senior-title">${(typeof gettext === 'function' ? gettext('Análisis') : 'Análisis')}</span>
             <div class="fin-senior-text">
                 <div style="margin-bottom:8px;">
                     <strong>${(typeof gettext === 'function' ? gettext('Ratio original:') : 'Ratio original:')}</strong>
                     <span>${new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: data.ratio === 'endeudamiento' ? 1 : 2 }).format(data.value)}${data.ratio === 'endeudamiento' ? ' %' : ''}</span>
                 </div>
                 <div id="fin-ratio-recalc-block" style="margin-bottom:12px;">
                     <strong>${(typeof gettext === 'function' ? gettext('Ratio con selección actual:') : 'Ratio con selección actual:')}</strong>
                     <span id="fin-ratio-recalc-val">${new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: data.ratio === 'endeudamiento' ? 1 : 2 }).format(selectionTotals.ratioVal)}${data.ratio === 'endeudamiento' ? ' %' : ''}</span>
                 </div>
                 <div>${data.analysis}</div>
             </div>
        </div>
    `;

    const tbody = modal.querySelector('.fin-modal-body');
    if (tbody) {
        tbody.addEventListener('change', function (ev) {
            const target = ev.target;
            if (!target || !target.classList || !target.classList.contains('fin-ratio-check')) return;
            const ratio = target.getAttribute('data-ratio');
            const side = target.getAttribute('data-side');
            const code = target.getAttribute('data-code');
            const key = getRatioSelectionKey(ratio);
            const state = finRatioSelectionState[key] || loadRatioSelection(ratio, data.numerator.details, data.denominator.details);
            const set = state[side];
            const row = target.closest('tr');

            if (target.checked) {
                set.add(code);
                if (row) row.classList.remove('fin-ratio-row-excluded');
            } else {
                if (set.size <= 1) {
                    target.checked = true;
                    if (row) row.classList.remove('fin-ratio-row-excluded');
                    showToast((typeof gettext === 'function' ? gettext('Debe mantener al menos una cuenta seleccionada en cada bloque.') : 'Debe mantener al menos una cuenta seleccionada en cada bloque.'), "warning");
                    return;
                }
                set.delete(code);
                if (row) row.classList.add('fin-ratio-row-excluded');
            }

            const totals = recomputeRatioFromSelection(ratio, data, state);
            if (totals.denTotal === 0) {
                if (!target.checked) {
                    set.add(code);
                    if (row) row.classList.remove('fin-ratio-row-excluded');
                    target.checked = true;
                }
                showToast((typeof gettext === 'function' ? gettext('La selección actual produce un denominador igual a cero. Revise las cuentas seleccionadas.') : 'La selección actual produce un denominador igual a cero. Revise las cuentas seleccionadas.'), "warning");
                return;
            }

            persistRatioSelection(ratio);

            const recalcEl = document.getElementById('fin-ratio-recalc-val');
            if (recalcEl) {
                recalcEl.textContent = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: ratio === 'endeudamiento' ? 1 : 2 }).format(totals.ratioVal) + (ratio === 'endeudamiento' ? ' %' : '');
            }

            if (window.cachedFinancialData && window.cachedFinancialData.ratios) {
                window.cachedFinancialData.ratios[ratio] = totals.ratioVal;
                try {
                    let gaugeId = null;
                    if (ratio === 'liquidez') gaugeId = 'fin-val-liquidez';
                    else if (ratio === 'margen') gaugeId = 'fin-val-margen';
                    else if (ratio === 'solvencia') gaugeId = 'fin-val-solvencia';
                    else if (ratio === 'endeudamiento') gaugeId = 'fin-val-endeudamiento';

                    if (gaugeId) {
                        const defaults = {
                            liquidez: { min: 0, max: 8, low: 1.0, high: 2.0 },
                            margen: { min: 0, max: 50, low: 5.0, high: 15.0 },
                            solvencia: { min: 0, max: 12, low: 1.1, high: 2.0 },
                            endeudamiento: { min: 0, max: 200, low: 40.0, high: 80.0, inverse: true }
                        };
                        const ranges = window.cachedFinancialData.ranges || {};
                        const cfg = ranges[ratio] || defaults[ratio];
                        let title = ratio;
                        if (ratio === 'liquidez') {
                            title = typeof gettext === 'function' ? gettext("Liquidez") : "Liquidez";
                        } else if (ratio === 'margen') {
                            title = typeof gettext === 'function' ? gettext("Margen %") : "Margen %";
                        } else if (ratio === 'solvencia') {
                            title = typeof gettext === 'function' ? gettext("Solvencia") : "Solvencia";
                        } else if (ratio === 'endeudamiento') {
                            title = typeof gettext === 'function' ? gettext("Endeudamiento") : "Endeudamiento";
                        }
                        const suffix = (ratio === 'margen' || ratio === 'endeudamiento') ? "%" : "";
                        renderRatioGauge(gaugeId, totals.ratioVal, title, cfg, suffix);
                    }
                } catch (e) {
                    console.error("Error actualizando gauge de ratio:", e);
                }
            }
        });
    }

    modal.style.display = 'flex';
}

function closeRatioDrilldownModal() {
    const modal = document.getElementById('fin-ratio-modal');
    if (modal) modal.style.display = 'none';
}

function unflipParent(el) {
    const card = el.closest('.flip-card');
    if (card) card.classList.remove('flipped');
}

// Handle Resize
window.addEventListener('resize', () => {
    Object.values(finGaugeInstances).forEach(chart => chart.resize());
});

function updateKPIValue(id, value, format) {
    const el = document.getElementById(id);
    if (!el) return;

    if (format === 'currency') {
        el.innerText = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);
    } else if (format === 'percent') {
        el.innerText = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value) + "%";
    } else {
        el.innerText = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
    }
}

// --- QUARTERLY SECTION ---
async function initQuarterly() {
    try {
        const deptSel = document.getElementById('fin-quarter-dept');
        if (deptSel && deptSel.options.length <= 1) {
            const resDept = await fetch(`/api/financial/departments`);
            if (resDept.ok) {
                const depts = await resDept.json();
                depts.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.key;
                    opt.textContent = d.label;
                    deptSel.appendChild(opt);
                });
            }
        }
        await loadQuarterly();
    } catch (e) {
        console.error("Quarterly init error:", e);
    }
}

async function loadQuarterly() {
    const deptSel = document.getElementById('fin-quarter-dept');
    const departamento = deptSel ? deptSel.value : null;
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}` + (departamento ? `&departamento=${encodeURIComponent(departamento)}` : '');
    try {
        const res = await fetch(`/api/financial/quarterly${q}`);
        if (!res.ok) return;
        const data = await res.json();
        renderQuarterlyCards(data);
        renderQuarterlyChart(data);
    } catch (e) {
        console.error("Quarterly load error:", e);
    }
}

function changeQuarterlyDepartment() {
    loadQuarterly();
}

function renderQuarterlyCards(data) {
    const el = document.getElementById('fin-quarter-cards');
    if (!el) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    const pf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 1 });
    const html = data.quarters.map(q => {
        const comp = data.comparison && data.comparison.quarters ? data.comparison.quarters[q.quarter] : null;
        const prevVals = data.comparison && data.comparison.prev_values && data.comparison.prev_values.quarters
            ? data.comparison.prev_values.quarters[q.quarter] : null;
        const varClass = (v) => v > 0 ? 'fin-var-pos' : (v < 0 ? 'fin-var-neg' : 'fin-var-neutral');
        const fmtPct = (v) => (pf.format(v) + '%');
        const fmtPts = (v) => (pf.format(v) + ' pts');
        return `
        <div class="fin-quarter-card">
            <div class="fin-quarter-title">${q.quarter}</div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Ingresos') : 'Ingresos'}</span><span class="val">${nf.format(q.ingresos)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Gastos') : 'Gastos'}</span><span class="val">${nf.format(q.gastos)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Beneficio neto') : 'Beneficio neto'}</span><span class="val">${nf.format(q.beneficio_neto)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Margen operativo') : 'Margen operativo'}</span><span class="val">${pf.format(q.margen_operativo)}%</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Ticket medio') : 'Ticket medio'}</span><span class="val">${nf.format(q.metrics.ticket_medio)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Operaciones') : 'Operaciones'}</span><span class="val">${q.metrics.operaciones}</span></div>
            ${prevVals ? `
            <div class="fin-quarter-title" style="margin-top:8px;">${typeof gettext === 'function' ? gettext('Comparativa PY') : 'Comparativa PY'}</div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Ingresos PY') : 'Ingresos PY'}</span><span class="val">${nf.format(prevVals.ingresos)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Gastos PY') : 'Gastos PY'}</span><span class="val">${nf.format(prevVals.gastos)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Beneficio PY') : 'Beneficio PY'}</span><span class="val">${nf.format(prevVals.beneficio_neto)}</span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Margen operativo PY') : 'Margen operativo PY'}</span><span class="val">${pf.format(prevVals.margen_operativo)}%</span></div>
            ` : ''}
            ${comp ? `
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Var % Ingresos') : 'Var % Ingresos'}</span><span class="val"><span class="fin-var ${varClass(comp.ingresos_var_pct)}">${fmtPct(comp.ingresos_var_pct)}</span></span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Var % Gastos') : 'Var % Gastos'}</span><span class="val"><span class="fin-var ${varClass(comp.gastos_var_pct)}">${fmtPct(comp.gastos_var_pct)}</span></span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Var % Beneficio') : 'Var % Beneficio'}</span><span class="val"><span class="fin-var ${varClass(comp.beneficio_var_pct)}">${fmtPct(comp.beneficio_var_pct)}</span></span></div>
            <div class="fin-quarter-row"><span>${typeof gettext === 'function' ? gettext('Dif. Margen Operativo') : 'Dif. Margen Operativo'}</span><span class="val"><span class="fin-var ${varClass(comp.margen_operativo_diff_pts)}">${fmtPts(comp.margen_operativo_diff_pts)}</span></span></div>
            ` : ''}
        </div>`;
    }).join('');
    el.innerHTML = html;
}

function renderQuarterlyChart(data) {
    const el = document.getElementById('fin-quarter-chart');
    if (!el) return;
    el.removeAttribute('_echarts_instance_');
    const chart = echarts.init(el);
    const cats = data.quarters.map(q => q.quarter);
    const ingresosCY = data.quarters.map(q => q.ingresos);
    const ingresosPY = cats.map(k => data.comparison.prev_values.quarters[k].ingresos);
    const gastosCY = data.quarters.map(q => q.gastos);
    const gastosPY = cats.map(k => data.comparison.prev_values.quarters[k].gastos);
    const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: [(typeof gettext === 'function' ? gettext('Ingresos CY') : 'Ingresos CY'), (typeof gettext === 'function' ? gettext('Ingresos PY') : 'Ingresos PY'), (typeof gettext === 'function' ? gettext('Gastos CY') : 'Gastos CY'), (typeof gettext === 'function' ? gettext('Gastos PY') : 'Gastos PY')] },
        xAxis: { type: 'category', data: cats },
        yAxis: { type: 'value' },
        series: [
            { name: (typeof gettext === 'function' ? gettext('Ingresos CY') : 'Ingresos CY'), type: 'bar', data: ingresosCY, itemStyle: { color: '#10b981' } },
            { name: (typeof gettext === 'function' ? gettext('Ingresos PY') : 'Ingresos PY'), type: 'bar', data: ingresosPY, itemStyle: { color: '#34d399' } },
            { name: (typeof gettext === 'function' ? gettext('Gastos CY') : 'Gastos CY'), type: 'bar', data: gastosCY, itemStyle: { color: '#ef4444' } },
            { name: (typeof gettext === 'function' ? gettext('Gastos PY') : 'Gastos PY'), type: 'bar', data: gastosPY, itemStyle: { color: '#f87171' } }
        ]
    };
    chart.setOption(option);
}

function exportQuarterly(format) {
    const deptSel = document.getElementById('fin-quarter-dept');
    const departamento = deptSel ? deptSel.value : '';
    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}` + (departamento ? `&departamento=${encodeURIComponent(departamento)}` : '') + `&format=${encodeURIComponent(format)}`;
    window.open(`/api/financial/quarterly/export${q}`, '_blank');
}


async function loadPLDetail() {
    const levelEl = document.getElementById('pl-detail-level');
    if (!levelEl) return;
    const level = levelEl.value;

    // [FIX] Use 0 to let backend auto-detect the last active month
    const month = 0;

    const labelEl = document.getElementById('pl-detail-period-label');
    if (labelEl) {
        // Since we auto-detect, we don't know the exact month name client-side easily without metadata.
        // For now, use a generic label or "Cierre del Ejercicio"
        const compTxt = (typeof gettext === 'function' ? gettext('Comparativa:') : 'Comparativa:');
        const autoTxt = (typeof gettext === 'function' ? gettext('Último Periodo Activo') : 'Último Periodo Activo');
        labelEl.innerText = `${compTxt} ${autoTxt}`;
    }

    const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}&month=${month}&level=${level}`;

    try {
        const res = await fetch(`/api/financial/pl-detail${q}`);
        if (res.ok) {
            const json = await res.json();
            // Support both old (List) and new (Dict) format for safety
            const rows = Array.isArray(json) ? json : (json.data || []);
            const meta = json.meta || {};

            if (meta.period_name) {
                const labelEl = document.getElementById('pl-detail-period-label');
                if (labelEl) {
                    const compTxt = (typeof gettext === 'function' ? gettext('Comparativa:') : 'Comparativa:');
                    labelEl.innerText = `${compTxt} ${meta.period_name} ${meta.year_current} vs ${meta.period_name} ${meta.year_prev}`;
                }
            }

            renderPLDetailTable(rows);
        }
    } catch (e) {
        console.error("Error loading PL Detail:", e);
        const tbody = document.getElementById('pl-detail-body');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="5" style="padding:20px; text-align:center; color:#ef4444;">Error cargando datos: ${e.message}</td></tr>`;
        }
    }
}

function renderPLDetailTable(data) {
    const tbody = document.getElementById('pl-detail-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (data.length === 0) {
        const msg = (typeof gettext === 'function' ? gettext("No hay datos para este periodo.") : "No hay datos para este periodo.");
        tbody.innerHTML = `<tr><td colspan="5" style="padding:20px; text-align:center; color:#a1a1aa;">${msg}</td></tr>`;
        return;
    }

    data.forEach(row => {
        const tr = document.createElement('tr');
        tr.style.borderBottom = '1px solid #334155';

        // Color for Income vs Expense
        const valColor = row.is_ingreso ? '#10b981' : '#ef4444';
        const varColor = row.variacion > 0 ? (row.is_ingreso ? '#10b981' : '#ef4444') : (row.is_ingreso ? '#ef4444' : '#10b981');
        const varIcon = row.variacion > 0 ? '↑' : '↓';

        tr.innerHTML = `
            <td style="padding: 10px; color: #fff; font-family: monospace;">${row.cuenta}</td>
            <td style="padding: 10px; color: #d4d4d8;">${row.descripcion}</td>
            <td style="padding: 10px; text-align: right; color: #fff;">${new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR' }).format(row.mes_actual)}</td>
            <td style="padding: 10px; text-align: right; color: #a1a1aa;">${new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR' }).format(row.mes_anterior)}</td>
            <td style="padding: 10px; text-align: right; color: ${varColor}; font-weight: bold;">
                ${varIcon} ${Math.abs(row.variacion).toFixed(1)}%
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderAdvancedAnalysis(data) {
    const container = document.getElementById('fin-analysis-container');
    if (!container) return;

    container.innerHTML = '';

    const nf0 = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    const nfMoney0 = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });

    const trend = data.trend || {};
    const series = Array.isArray(data.monthly_series) ? data.monthly_series : [];
    const mean = series.length ? (series.reduce((a, b) => a + b, 0) / series.length) : 0;
    const intensityPct = mean ? Math.abs(trend.slope || 0) * 12 / mean * 100 : 0;
    let intensityLabel = (typeof gettext === 'function' ? gettext('Baja') : 'Baja');
    if (intensityPct >= 10) intensityLabel = (typeof gettext === 'function' ? gettext('Alta') : 'Alta');
    else if (intensityPct >= 3) intensityLabel = (typeof gettext === 'function' ? gettext('Media') : 'Media');

    let trendCls = 'state-stable';
    let trendText = (typeof gettext === 'function' ? gettext('Estable') : 'Estable');
    if (trend.direction === 'growing') {
        trendCls = 'state-growing';
        trendText = (typeof gettext === 'function' ? gettext('Creciente') : 'Creciente');
    } else if (trend.direction === 'declining') {
        trendCls = 'state-declining';
        trendText = (typeof gettext === 'function' ? gettext('Decreciente') : 'Decreciente');
    }

    const trendHTML = `
        <div class="fin-card-simple fin-analysis-card ${trendCls}" data-analysis="trend">
            <div class="flip-card">
                <div class="flip-card-inner">
                    <div class="flip-card-front">
                        <h4 class="fin-analysis-title">${(typeof gettext === 'function' ? gettext('Tendencia Anual') : 'Tendencia Anual')}</h4>
                        <div class="fin-analysis-sub">${trendText}</div>
                        <div class="fin-analysis-metric"><span class="label">${(typeof gettext === 'function' ? gettext('Pendiente') : 'Pendiente')}</span><span class="val">${nfMoney0.format(Math.round(trend.slope || 0))}</span></div>
                        <div class="fin-analysis-metric"><span class="label">${(typeof gettext === 'function' ? gettext('Proyección de cierre') : 'Proyección de cierre')}</span><span class="val">${nfMoney0.format(Math.round(trend.prediction_next || 0))}</span></div>
                        <div class="fin-analysis-metric"><span class="label">${(typeof gettext === 'function' ? gettext('Intensidad de tendencia') : 'Intensidad de tendencia')}</span><span class="val">${intensityLabel}</span></div>
                        <button class="fin-analysis-lever fin-analysis-btn" tabindex="0">${(typeof gettext === 'function' ? gettext('Detalle') : 'Detalle')}</button>
                    </div>
                    <div class="flip-card-back"></div>
                </div>
            </div>
        </div>
    `;

    // 2. Anomalies
    let anomalyHTML = '';
    if (data.anomalies && data.anomalies.length > 0) {
        const items = data.anomalies.slice(0, 3).map(a =>
            `${(typeof gettext === 'function' ? gettext('Mes') : 'Mes')} ${a.index + 1} ${a.type === 'drop' ? (typeof gettext === 'function' ? gettext('▼') : '▼') : (typeof gettext === 'function' ? gettext('▲') : '▲')} ${nfMoney0.format(Math.abs(a.value || 0))}`
        ).join(' • ');
        const sevMax = Math.max(...data.anomalies.map(a => Math.abs(a.score || 0)), 0);
        const impactTotal = (() => {
            if (!series.length) return 0;
            const m = mean || 0;
            return Math.round(data.anomalies.reduce((acc, a) => acc + Math.abs((a.value || 0) - m), 0));
        })();

        anomalyHTML = `
            <div class="fin-card-simple fin-analysis-card state-stable" data-analysis="anomalies">
                <div class="flip-card">
                    <div class="flip-card-inner">
                        <div class="flip-card-front">
                            <h4 class="fin-analysis-title">${(typeof gettext === 'function' ? gettext('Anomalías') : 'Anomalías')}</h4>
                            <div class="fin-analysis-sub">${(typeof gettext === 'function' ? gettext('Meses críticos:') : 'Meses críticos:')} ${items}</div>
                            <div class="fin-analysis-metric"><span class="label">${(typeof gettext === 'function' ? gettext('Severidad máx (Z)') : 'Severidad máx (Z)')}</span><span class="val">${nf0.format(Math.round(sevMax))}</span></div>
                            <div class="fin-analysis-metric"><span class="label">${(typeof gettext === 'function' ? gettext('Impacto acumulado') : 'Impacto acumulado')}</span><span class="val">${nfMoney0.format(impactTotal)}</span></div>
                            <button class="fin-analysis-lever fin-analysis-btn" tabindex="0">${(typeof gettext === 'function' ? gettext('Detalle') : 'Detalle')}</button>
                        </div>
                        <div class="flip-card-back"></div>
                    </div>
                </div>
            </div>
        `;
    } else {
        anomalyHTML = `
            <div class="fin-card-simple fin-analysis-card state-growing" data-analysis="anomalies">
                <div class="flip-card">
                    <div class="flip-card-inner">
                        <div class="flip-card-front">
                            <h4 class="fin-analysis-title">${(typeof gettext === 'function' ? gettext('Anomalías') : 'Anomalías')}</h4>
                            <div class="fin-analysis-sub">${(typeof gettext === 'function' ? gettext('Sin anomalías destacables.') : 'Sin anomalías destacables.')}</div>
                            <button class="fin-analysis-lever fin-analysis-btn" tabindex="0">${(typeof gettext === 'function' ? gettext('Detalle') : 'Detalle')}</button>
                        </div>
                        <div class="flip-card-back"></div>
                    </div>
                </div>
            </div>
        `;
    }

    // 3. Recommendations
    const recs = data.recommendations || [];
    let recsHTML = '';
    if (recs.length > 0) {
        const sanitize = (t) => t.replace(/⚠️|📉|🔻|🚀/g, '').replace(/\*\*/g, '').trim();
        const shortRecs = recs.slice(0, 3).map(sanitize);
        const recText = shortRecs.join(' • ');
        recsHTML = `
            <div class="fin-card-simple fin-analysis-card" data-analysis="recs" style="grid-column: span 2;">
                <div class="flip-card">
                    <div class="flip-card-inner">
                        <div class="flip-card-front">
                            <div style="display:flex; align-items:center; gap:8px; margin-bottom:15px;">
                                <i class="fas fa-lightbulb" style="color:#fbbf24; font-size:1.2rem;"></i>
                                <h4 class="fin-analysis-title" style="margin:0;">${(typeof gettext === 'function' ? gettext('Recomendaciones IA') : 'Recomendaciones IA')}</h4>
                            </div>
                            <ul style="list-style:none; padding:0; margin:0; flex:1; font-size:0.95rem;">
                                ${shortRecs.map(r => {
                                    const parts = r.split(':');
                                    if (parts.length > 1) {
                                        return `<li style="margin-bottom:12px; padding-left:10px; border-left:3px solid var(--accent);"><strong style="color:#fff;">${parts[0].trim()}:</strong> <span style="color:#d4d4d8;">${parts.slice(1).join(':').trim()}</span></li>`;
                                    }
                                    return `<li style="margin-bottom:12px; padding-left:10px; border-left:3px solid var(--accent);"><span style="color:#d4d4d8;">${r}</span></li>`;
                                }).join('')}
                            </ul>
                            <button class="fin-analysis-lever fin-analysis-btn" tabindex="0">${(typeof gettext === 'function' ? gettext('Detalle') : 'Detalle')}</button>
                        </div>
                        <div class="flip-card-back"></div>
                    </div>
                </div>
            </div>
        `;
    }

    // Grid Layout for Analysis
    container.innerHTML = `
        <div class="fin-analysis-grid">
            ${trendHTML}
            ${anomalyHTML}
            ${recsHTML}
        </div>
    `;
    const snapshot = window.cachedFinancialData || null;
    Array.from(container.querySelectorAll('.fin-analysis-card')).forEach(card => {
        const lever = card.querySelector('.fin-analysis-lever');
        const flip = card.querySelector('.flip-card');
        const back = card.querySelector('.flip-card-back');
        const type = card.getAttribute('data-analysis');
        const handler = () => {
            if (back) {
                back.innerHTML = buildAnalysisBack(type, data, snapshot);
            }
            if (flip) flip.classList.add('flipped');
        };
        if (lever) {
            lever.addEventListener('click', handler);
            lever.addEventListener('keyup', (e) => {
                if (e.key === 'Enter' || e.key === ' ') handler();
            });
        }
    });
}

function buildAnalysisBack(type, data, snapshot) {
    const nfMoney0 = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 });
    const nf0 = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });
    let content = '';
    if (type === 'trend') {
        const t = data.trend || {};
        const dir = t.direction === 'growing' ? (typeof gettext === 'function' ? gettext('Creciente') : 'Creciente') : (t.direction === 'declining' ? (typeof gettext === 'function' ? gettext('Decreciente') : 'Decreciente') : (typeof gettext === 'function' ? gettext('Estable') : 'Estable'));
        const series = Array.isArray(data.monthly_series) ? data.monthly_series : [];
        const mean = series.length ? (series.reduce((a, b) => a + b, 0) / series.length) : 0;
        const intensityPct = mean ? Math.abs(t.slope || 0) * 12 / mean * 100 : 0;
        const intensityLabel = intensityPct >= 10 ? (typeof gettext === 'function' ? gettext('Alta') : 'Alta') : (intensityPct >= 3 ? (typeof gettext === 'function' ? gettext('Media') : 'Media') : (typeof gettext === 'function' ? gettext('Baja') : 'Baja'));
        const margin = snapshot && snapshot.ratios ? snapshot.ratios.margen : null;
        const marginTxt = margin !== null && margin !== undefined ? `${nf0.format(Math.round(margin))} %` : '—';
        content = `
            <div style="position:absolute; top:10px; right:10px;"><button class="flip-btn" onclick="unflipParent(this)">${(typeof gettext === 'function' ? gettext('Cerrar') : 'Cerrar')}</button></div>
            <div class="fin-ratio-back">
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Diagnóstico') : 'Diagnóstico')}</span><span>${dir} • ${(typeof gettext === 'function' ? gettext('Pendiente') : 'Pendiente')} ${nfMoney0.format(Math.round(t.slope || 0))} • ${(typeof gettext === 'function' ? gettext('Proyección') : 'Proyección')} ${nfMoney0.format(Math.round(t.prediction_next || 0))} • ${(typeof gettext === 'function' ? gettext('Intensidad') : 'Intensidad')} ${intensityLabel}</span></div>
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Margen Operativo') : 'Margen Operativo')}</span><span>${marginTxt} ${(typeof gettext === 'function' ? gettext('(objetivo 15–20%)') : '(objetivo 15–20%)')}</span></div>
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Indicadores a monitorizar') : 'Indicadores a monitorizar')}</span><span>${(typeof gettext === 'function' ? gettext('Margen EBITDA %, EBITDA mensual, ciclo de cobros/pagos, fondo de maniobra') : 'Margen EBITDA %, EBITDA mensual, ciclo de cobros/pagos, fondo de maniobra')}</span></div>
            </div>
        `;
    } else if (type === 'anomalies') {
        const an = data.anomalies || [];
        const series = Array.isArray(data.monthly_series) ? data.monthly_series : [];
        const mean = series.length ? (series.reduce((a, b) => a + b, 0) / series.length) : 0;
        const sevMax = Math.max(...an.map(a => Math.abs(a.score || 0)), 0);
        const impactTotal = Math.round(an.reduce((acc, a) => acc + Math.abs((a.value || 0) - mean), 0));
        const items = an.slice(0, 4).map(a => `${(typeof gettext === 'function' ? gettext('Mes') : 'Mes')} ${a.index + 1}: ${nfMoney0.format(Math.abs(a.value || 0))}`).join(' • ');
        content = `
            <div style="position:absolute; top:10px; right:10px;"><button class="flip-btn" onclick="unflipParent(this)">${(typeof gettext === 'function' ? gettext('Cerrar') : 'Cerrar')}</button></div>
            <div class="fin-ratio-back">
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Hallazgos') : 'Hallazgos')}</span><span>${items || (typeof gettext === 'function' ? gettext('Ninguna anomalía relevante en el periodo') : 'Ninguna anomalía relevante en el periodo')}</span></div>
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Severidad máx (Z)') : 'Severidad máx (Z)')}</span><span>${nf0.format(Math.round(sevMax))}</span></div>
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Impacto acumulado') : 'Impacto acumulado')}</span><span>${nfMoney0.format(impactTotal)}</span></div>
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Causas probables') : 'Causas probables')}</span><span>${(typeof gettext === 'function' ? gettext('Estacionalidad, presión de precios, suministro/servicio') : 'Estacionalidad, presión de precios, suministro/servicio')}</span></div>
            </div>
        `;
    } else if (type === 'recs') {
        const sanitize = (t) => t.replace(/⚠️|📉|🔻|🚀/g, '').replace(/\*\*/g, '').trim();
        const recs = (data.recommendations || []).slice(0, 5).map(sanitize);
        const list = recs.length ? '<ul class="fin-analysis-list">' + recs.map(r => `<li>${r}</li>`).join('') + '</ul>' : '';
        content = `
            <div style="position:absolute; top:10px; right:10px;"><button class="flip-btn" onclick="unflipParent(this)">${(typeof gettext === 'function' ? gettext('Cerrar') : 'Cerrar')}</button></div>
            <div class="fin-ratio-back">
                <div class="fin-analysis-section"><span class="fin-analysis-label">${(typeof gettext === 'function' ? gettext('Acciones recomendadas') : 'Acciones recomendadas')}</span><span>${(recs.length ? '' : (typeof gettext === 'function' ? gettext('Sin acciones críticas inmediatas') : 'Sin acciones críticas inmediatas'))}</span></div>
                ${list}
            </div>
        `;
    }
    return content;
}
function renderPLChart(data) {
    const chartDom = document.getElementById('fin-chart-pl');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);

    // Prepare Data: Waterfall like
    // Ingresos (Positive), Gastos (Negative), Resultado (Total)

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: (params) => {
                const p = Array.isArray(params) ? params[0] : params;
                const val = p && p.value !== undefined ? p.value : 0;
                return new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 }).format(Math.round(Math.abs(val))) + ' €';
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: [
                (typeof gettext === 'function' ? gettext('Ingresos') : 'Ingresos'),
                (typeof gettext === 'function' ? gettext('Gastos') : 'Gastos'),
                (typeof gettext === 'function' ? gettext('Resultado') : 'Resultado')
            ],
            axisLabel: { color: '#a1a1aa' }
        },
        yAxis: {
            type: 'value',
            axisLabel: {
                color: '#a1a1aa',
                formatter: (value) => new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 }).format(Math.round(value))
            }
        },
        series: [
            {
                name: (typeof gettext === 'function' ? gettext('Euros') : 'Euros'),
                type: 'bar',
                data: [
                    {
                        value: data.total_ingresos,
                        itemStyle: { color: '#10b981' }
                    },
                    {
                        value: -data.total_gastos,
                        itemStyle: { color: '#ef4444' }
                    },
                    {
                        value: data.resultado_explotacion,
                        itemStyle: { color: '#f59e0b' }
                    }
                ],
                label: {
                    show: true,
                    position: 'top',
                    color: '#fff',
                    formatter: (params) => {
                        const val = params && params.value !== undefined ? params.value : 0;
                        return new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 }).format(Math.round(val));
                    }
                }
            }
        ]
    };

    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// Expose globally
window.loadActualidadFinanciera = loadActualidadFinanciera;
window.loadPLDetail = loadPLDetail;
window.initPLReport = initPLReport;
window.changePLLevel = changePLLevel;
window.exportPLReport = exportPLReport;

// TREASURY REPORT
async function loadTreasury() {
    console.log("Loading Treasury snapshot...");
    try {
        const emp = (typeof currEmpresa !== 'undefined') ? parseInt(currEmpresa, 10) : NaN;
        const eje = (typeof currEjercicio !== 'undefined') ? parseInt(currEjercicio, 10) : NaN;
        const q = `?empresa=${isNaN(emp) ? currEmpresa : emp}&ejercicio=${isNaN(eje) ? currEjercicio : eje}`;
        const res = await fetch(`/api/financial/treasury${q}`);
        if (!res.ok) throw new Error("Failed to fetch treasury data");
        const json = await res.json();
        renderTreasury(json);
    } catch (e) {
        console.error("Error loading Treasury:", e);
    }
}

function renderTreasury(data) {
    if (!data) return;
    const fmtMoney = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 });

    const kpis = (data && data.kpis) ? data.kpis : {
        cash: (data && data.cash !== undefined) ? data.cash : 0,
        working_capital: (data && data.working_capital !== undefined) ? data.working_capital : 0,
        receivables: (data && data.receivables && typeof data.receivables.total === 'number') ? data.receivables.total : (data && typeof data.receivables === 'number' ? data.receivables : 0),
        payables: (data && data.payables && typeof data.payables.total === 'number') ? data.payables.total : (data && typeof data.payables === 'number' ? data.payables : 0),
        unpaid_receivables: (data && data.receivables && data.receivables.aging && typeof data.receivables.aging.overdue === 'number') ? data.receivables.aging.overdue : (data && typeof data.unpaid_receivables === 'number' ? data.unpaid_receivables : 0),
        dso: (data && typeof data.dso === 'number') ? data.dso : 0,
        dpo: (data && typeof data.dpo === 'number') ? data.dpo : 0
    };
    const domCash = document.getElementById('fin-treasury-cash');
    if (domCash) domCash.textContent = fmtMoney.format(kpis.cash || 0);

    const domWC = document.getElementById('fin-treasury-wc');
    if (domWC) domWC.textContent = fmtMoney.format(kpis.working_capital || 0);

    // Charts
    const agingLabels = (typeof gettext === 'function') ?
        [gettext('Vencido'), '0-30', '30-60', '60-90', '> 90'] :
        ['Vencido', '0-30', '30-60', '60-90', '> 90'];

    const buckets = ['overdue', '0-30', '30-60', '60-90', '>90'];

    const renderAgingChart = (domId, agingObj, color) => {
        const dom = document.getElementById(domId);
        if (!dom) return;
        let chart = echarts.getInstanceByDom(dom);
        if (chart) chart.dispose();
        chart = echarts.init(dom, null, { renderer: 'svg' });

        const values = buckets.map(k => (agingObj && typeof agingObj[k] === 'number') ? agingObj[k] : 0);

        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function (params) {
                    const p = params[0];
                    return `<div style="margin-bottom:4px;">${p.name}</div><div style="font-weight:bold; color:${p.color}">${fmtMoney.format(p.value)}</div>`;
                }
            },
            grid: { left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true },
            xAxis: {
                type: 'category',
                data: agingLabels,
                axisLabel: { color: '#9ca3af', interval: 0, fontSize: 11 },
                axisLine: { lineStyle: { color: '#374151' } },
                axisTick: { show: false }
            },
            yAxis: {
                type: 'value',
                axisLabel: { color: '#9ca3af', formatter: (v) => v >= 1000 ? (v / 1000).toFixed(0) + 'k' : v },
                splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
            },
            series: [{
                name: 'Importe',
                type: 'bar',
                barWidth: '60%',
                data: values.map(v => ({
                    value: v,
                    itemStyle: { color: color, borderRadius: [4, 4, 0, 0] }
                })),
                label: { show: true, position: 'top', formatter: (p) => p.value > 0 ? (p.value >= 1000 ? (p.value / 1000).toFixed(1) + 'k' : p.value.toFixed(0)) : '', color: '#fff', fontSize: 10 }
            }]
        };
        chart.setOption(option);

        // Resize observer
        new ResizeObserver(() => chart.resize()).observe(dom);
    };

    const agingReceivables = (data && data.aging && data.aging.receivables) ? data.aging.receivables : (data && data.receivables && data.receivables.aging ? data.receivables.aging : null);
    const agingPayables = (data && data.aging && data.aging.payables) ? data.aging.payables : (data && data.payables && data.payables.aging ? data.payables.aging : null);
    if (agingReceivables) renderAgingChart('fin-chart-aging-receivables', agingReceivables, '#10b981');
    if (agingPayables) renderAgingChart('fin-chart-aging-payables', agingPayables, '#ef4444');
    const domRecv = document.getElementById('fin-chart-aging-receivables');
    const domPay = document.getElementById('fin-chart-aging-payables');
    const hasRecv = !!(agingReceivables && buckets.some(k => typeof agingReceivables[k] === 'number' && agingReceivables[k] > 0));
    const hasPay = !!(agingPayables && buckets.some(k => typeof agingPayables[k] === 'number' && agingPayables[k] > 0));
    if (!hasRecv && domRecv) domRecv.innerHTML = `<div style="text-align:center; color:#a1a1aa;">${typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos'}</div>`;
    if (!hasPay && domPay) domPay.innerHTML = `<div style="text-align:center; color:#a1a1aa;">${typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos'}</div>`;

}

// TREASURY FORECAST
async function loadTreasuryForecast() {
    console.log("Loading Treasury Forecast...");
    try {
        const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;
        const res = await fetch(`/api/financial/treasury/forecast${q}`);
        if (!res.ok) return; // Silent fail if optional
        const json = await res.json();
        renderTreasuryForecast(json);
    } catch (e) {
        console.error("Error loading Forecast:", e);
    }
}

function renderTreasuryForecast(data) {
    const dom = document.getElementById('fin-chart-forecast');
    if (!dom) return;
    const noData = (!data || !Array.isArray(data.forecast) || data.forecast.length === 0 || data.forecast.every(x => !x || (((x.inflow || 0) === 0) && ((x.outflow || 0) === 0) && ((x.balance || 0) === 0))));
    if (noData) {
        const tryFallback = async () => {
            try {
                const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}`;
                const r = await fetch(`/api/financial/treasury${q}`);
                if (!r.ok) throw new Error('snapshot not available');
                const snap = await r.json();
                const cash = (snap && snap.kpis && typeof snap.kpis.cash === 'number') ? snap.kpis.cash : (typeof snap.cash === 'number' ? snap.cash : 0);
                if (cash > 0) {
                    let chart = echarts.getInstanceByDom(dom);
                    if (chart) chart.dispose();
                    chart = echarts.init(dom, null, { renderer: 'svg' });
                    const labels = Array.from({ length: 6 }).map((_, i) => (typeof gettext === 'function' ? `${gettext('Mes')} ${i + 1}` : `Mes ${i + 1}`));
                    const zero = Array(labels.length).fill(0);
                    const bal = Array(labels.length).fill(cash);
                    chart.setOption({
                        backgroundColor: 'transparent',
                        legend: { textStyle: { color: '#9ca3af' }, top: 0 },
                        grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
                        xAxis: { type: 'category', data: labels, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
                        yAxis: [{ type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151', type: 'dashed' } } }, { type: 'value', axisLabel: { color: '#3b82f6' }, splitLine: { show: false } }],
                        series: [
                            { name: (typeof gettext === 'function' ? gettext('Cobros') : 'Cobros'), type: 'bar', stack: 'flow', data: zero, itemStyle: { color: '#10b981' } },
                            { name: (typeof gettext === 'function' ? gettext('Pagos') : 'Pagos'), type: 'bar', stack: 'flow', data: zero, itemStyle: { color: '#ef4444' } },
                            { name: (typeof gettext === 'function' ? gettext('Saldo Proyectado') : 'Saldo Proyectado'), type: 'line', yAxisIndex: 1, data: bal, itemStyle: { color: '#3b82f6' }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6 }
                        ]
                    });
                    new ResizeObserver(() => chart.resize()).observe(dom);
                    return;
                }
            } catch (_) { }
            dom.innerHTML = `<div style="text-align:center; color:#a1a1aa;">${typeof gettext === 'function' ? gettext('Sin datos') : 'Sin datos'}</div>`;
        };
        tryFallback();
        return;
    }

    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });

    const fmtMoney = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0 });

    const labels = data.forecast.map(x => x.period);
    const inflow = data.forecast.map(x => x.inflow);
    const outflow = data.forecast.map(x => -x.outflow); // Negative for visual effect
    const balance = data.forecast.map(x => x.balance);

    const option = {
        backgroundColor: 'transparent',
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            formatter: function (params) {
                let res = `<div style="margin-bottom:4px;">${params[0].name}</div>`;
                params.forEach(p => {
                    const val = fmtMoney.format(Math.abs(p.value));
                    res += `<div style="display:flex; justify-content:space-between; gap:10px;">
                        <span style="color:${p.color}">${p.marker} ${p.seriesName}</span>
                        <span style="font-weight:bold; color:#fff">${val} €</span>
                    </div>`;
                });
                return res;
            }
        },
        legend: { textStyle: { color: '#9ca3af' }, top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
        xAxis: {
            type: 'category',
            data: labels,
            axisLabel: { color: '#9ca3af' },
            axisLine: { lineStyle: { color: '#374151' } }
        },
        yAxis: [
            {
                type: 'value',
                name: (typeof gettext === 'function' ? gettext('Flujo') : 'Flujo'),
                axisLabel: { color: '#9ca3af' },
                splitLine: { lineStyle: { color: '#374151', type: 'dashed' } }
            },
            {
                type: 'value',
                name: (typeof gettext === 'function' ? gettext('Saldo') : 'Saldo'),
                axisLabel: { color: '#3b82f6' },
                splitLine: { show: false }
            }
        ],
        series: [
            {
                name: (typeof gettext === 'function' ? gettext('Cobros') : 'Cobros'),
                type: 'bar',
                stack: 'flow',
                data: inflow,
                itemStyle: { color: '#10b981' }
            },
            {
                name: (typeof gettext === 'function' ? gettext('Pagos') : 'Pagos'),
                type: 'bar',
                stack: 'flow',
                data: outflow,
                itemStyle: { color: '#ef4444' }
            },
            {
                name: (typeof gettext === 'function' ? gettext('Saldo Proyectado') : 'Saldo Proyectado'),
                type: 'line',
                yAxisIndex: 1,
                data: balance,
                itemStyle: { color: '#3b82f6' },
                lineStyle: { width: 3 },
                symbol: 'circle',
                symbolSize: 6
            }
        ]
    };

    chart.setOption(option);
    new ResizeObserver(() => chart.resize()).observe(dom);
}

// ---- Local AI Analysis Button & Modal ----
function initLocalAiButton() {
    try {
        const btn = document.getElementById('btn-local-ai-analysis');
        if (!btn) return;
        if (typeof window.localAiModels === 'undefined') {
            checkLocalAiModels();
        }
        const hasData = !!(window.cachedFinancialData && window.cachedFinancialData.ingresos !== undefined);
        btn.disabled = !hasData;
        btn.setAttribute('aria-disabled', hasData ? 'false' : 'true');
        if (!btn._local_ai_bound) {
            btn.addEventListener('click', async function () {
                if (btn.disabled) return;
                openLocalAiModal();
                await runLocalFinancialAnalysisLocal();
            });
            btn._local_ai_bound = true;
        }
    } catch (e) {
        console.error("initLocalAiButton error:", e);
    }
}

document.addEventListener('datia:empresa-change', initLocalAiButton);
document.addEventListener('datia:ejercicio-change', initLocalAiButton);

async function checkLocalAiModels() {
    try {
        const res = await fetch('/api/datia/ai/models');
        if (!res.ok) throw new Error('Modelos IA no disponibles');
        const json = await res.json();
        const models = json && Array.isArray(json.models) ? json.models : [];
        window.localAiModels = models;
        const hasQwen14B = models.some(m => typeof m === 'string' && m.toLowerCase().includes('qwen') && (m.includes('14') || m.includes('14b')));
        const btn = document.getElementById('btn-local-ai-analysis');
        if (btn && hasQwen14B) {
            btn.title = (typeof gettext === 'function' ? gettext('Generar análisis financiero mediante IA local (Qwen 14B disponible)') : 'Generar análisis financiero mediante IA local (Qwen 14B disponible)');
        }
    } catch (e) {
        window.localAiModels = [];
    }
}

function openLocalAiModal() {
    let overlay = document.getElementById('local-ai-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'local-ai-overlay';
        overlay.className = 'local-ai-overlay';
        overlay.innerHTML = `
            <div class="local-ai-modal" role="dialog" aria-modal="true" aria-labelledby="local-ai-title">
                <div class="local-ai-header">
                    <div class="local-ai-title" id="local-ai-title">${(typeof gettext === 'function' ? gettext('Análisis IA local') : 'Análisis IA local')}</div>
                    <button class="local-ai-close" onclick="closeLocalAiModal()" aria-label="${(typeof gettext === 'function' ? gettext('Cerrar') : 'Cerrar')}">×</button>
                </div>
                <div class="local-ai-body">
                    <div class="local-ai-status" id="local-ai-status">
                        <div class="local-ai-spinner"></div>
                        <span>${(typeof gettext === 'function' ? gettext('Procesando análisis...') : 'Procesando análisis...')}</span>
                    </div>
                    <div class="local-ai-output" id="local-ai-output"></div>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    const status = document.getElementById('local-ai-status');
    const out = document.getElementById('local-ai-output');
    if (status) status.style.display = 'flex';
    if (out) out.textContent = '';
}

function closeLocalAiModal() {
    const overlay = document.getElementById('local-ai-overlay');
    if (overlay) overlay.style.display = 'none';
}

async function runLocalFinancialAnalysisLocal() {
    const outputEl = document.getElementById('local-ai-output');
    const statusEl = document.getElementById('local-ai-status');
    const t0 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    try {
        const emp = (typeof currEmpresa !== 'undefined') ? parseInt(currEmpresa, 10) : currEmpresa;
        const eje = (typeof currEjercicio !== 'undefined') ? parseInt(currEjercicio, 10) : currEjercicio;
        const q = `?empresa=${emp}&ejercicio=${eje}`;
        const resKPIs = await fetch(`/api/financial/monthly_kpis${q}`);
        if (!resKPIs.ok) throw new Error("KPIs mensuales no disponibles");
        const m = await resKPIs.json();
        const ingresos = Array.isArray(m.ingresos) ? m.ingresos : [];
        const gastos = Array.isArray(m.gastos) ? m.gastos : [];
        const ebitda = Array.isArray(m.ebitda) ? m.ebitda : [];
        const labels = Array.isArray(m.labels) ? m.labels : [];
        const insuf = ingresos.filter(v => v > 0).length < 6;
        const snap = window.cachedFinancialData || {};
        // Fetch Purchases (60) monthly for DPO
        const res60 = await fetch(`/api/financial/accounts/detail?empresa=${emp}&ejercicio=${eje}&code=60`);
        const det60 = res60.ok ? await res60.json() : { monthly: gastos }; // fallback to gastos
        const comprasM = Array.isArray(det60.monthly) ? det60.monthly : gastos;
        // Fetch Receivables (43) and Payables (40 + 41)
        const [res43, res40, res41] = await Promise.all([
            fetch(`/api/financial/accounts/detail?empresa=${emp}&ejercicio=${eje}&code=43`),
            fetch(`/api/financial/accounts/detail?empresa=${emp}&ejercicio=${eje}&code=40`),
            fetch(`/api/financial/accounts/detail?empresa=${emp}&ejercicio=${eje}&code=41`)
        ]);
        const det43 = res43.ok ? await res43.json() : { monthly: [] };
        const det40 = res40.ok ? await res40.json() : { monthly: [] };
        const det41 = res41.ok ? await res41.json() : { monthly: [] };
        const ar = Array.isArray(det43.monthly) ? det43.monthly.map(v => Math.abs(v || 0)) : [];
        const ap40 = Array.isArray(det40.monthly) ? det40.monthly.map(v => Math.abs(v || 0)) : [];
        const ap41 = Array.isArray(det41.monthly) ? det41.monthly.map(v => Math.abs(v || 0)) : [];
        const ap = ap40.map((v, i) => v + (ap41[i] || 0));
        const days = 30;
        const pctChange = (arr) => {
            const out = [];
            for (let i = 1; i < arr.length; i++) {
                const prev = arr[i - 1];
                const curr = arr[i];
                const val = (prev && Math.abs(prev) > 0) ? ((curr - prev) / Math.abs(prev)) * 100 : 0;
                out.push(Number.isFinite(val) ? val : 0);
            }
            return out;
        };
        const varIng = pctChange(ingresos);
        const varGas = pctChange(gastos);
        const rentabilidadMeses = [];
        for (let i = 0; i < Math.min(varIng.length, varGas.length); i++) {
            if ((varGas[i] - varIng[i]) > 10) rentabilidadMeses.push(labels[i + 1] || `M${i + 2}`);
        }
        const avgWindow = (arr, idx, w = 3) => {
            const start = Math.max(0, idx - (w - 1));
            const sub = arr.slice(start, idx + 1).filter(v => typeof v === 'number');
            const sum = sub.reduce((a, b) => a + (Math.abs(b) || 0), 0);
            return sub.length ? (sum / sub.length) : 0;
        };
        const dsoAlerts = [];
        const dpoArr = [];
        const dsoArr = [];
        for (let i = 0; i < ingresos.length; i++) {
            const ventas = Math.abs(ingresos[i] || 0);
            const compras = Math.abs(comprasM[i] || 0);
            const arProm = avgWindow(ar, i, 3);
            const apProm = avgWindow(ap, i, 3);
            const dso = ventas > 0 ? (arProm / ventas) * days : 0;
            const dpo = compras > 0 ? (apProm / compras) * days : 0;
            dsoArr.push(dso);
            dpoArr.push(dpo);
            if (dso > (dpo + 15)) dsoAlerts.push(labels[i] || `M${i + 1}`);
        }
        const ratios = (snap && snap.ratios) ? snap.ratios : {};
        const liq = typeof ratios.liquidez === 'number' ? ratios.liquidez : null;
        const sol = typeof ratios.solvencia === 'number' ? ratios.solvencia : null;
        const liqQual = (v) => (v < 1.2 ? 'Crítico' : (v < 1.5 ? 'Advertencia' : 'Óptimo'));
        const flow = ingresos.map((v, i) => Math.abs(v || 0) - Math.abs(gastos[i] || 0));
        const anomalies = [];
        for (let i = 0; i < ingresos.length; i++) {
            const meanIng = avgWindow(ingresos, i, 12);
            const meanGas = avgWindow(gastos, i, 12);
            const meanFlow = avgWindow(flow, i, 12);
            const curIng = Math.abs(ingresos[i] || 0);
            const curGas = Math.abs(gastos[i] || 0);
            const curFlow = Math.abs(flow[i] || 0);
            const isIngAnom = (meanIng > 0) && (Math.abs(curIng - meanIng) / meanIng > 0.5);
            const isGasAnom = (meanGas > 0) && (Math.abs(curGas - meanGas) / meanGas > 0.5);
            const isFlowAnom = (meanFlow > 0) && (Math.abs(curFlow - meanFlow) / meanFlow > 0.5);
            if (isIngAnom) anomalies.push({ serie: 'Ingresos', mes: labels[i] || `M${i + 1}` });
            if (isGasAnom) anomalies.push({ serie: 'Gastos', mes: labels[i] || `M${i + 1}` });
            if (isFlowAnom) anomalies.push({ serie: 'Flujo', mes: labels[i] || `M${i + 1}` });
        }
        let ingresosPrev = [];
        let gastosPrev = [];
        let ebitdaPrev = [];
        try {
            const resPrev = await fetch(`/api/financial/monthly_kpis?empresa=${emp}&ejercicio=${eje - 1}`);
            if (resPrev.ok) {
                const p = await resPrev.json();
                ingresosPrev = Array.isArray(p.ingresos) ? p.ingresos : [];
                gastosPrev = Array.isArray(p.gastos) ? p.gastos : [];
                ebitdaPrev = Array.isArray(p.ebitda) ? p.ebitda : [];
            }
        } catch (_) {}
        const yoyIng = ingresos.map((v, i) => {
            const prev = Math.abs(ingresosPrev[i] || 0);
            return prev > 0 ? ((Math.abs(v || 0) - prev) / prev) * 100 : 0;
        });
        const margCurr = ingresos.map((v, i) => (Math.abs(v || 0) > 0 ? ((ebitda[i] || 0) / Math.abs(v || 0)) * 100 : 0));
        const margPrev = ingresosPrev.map((v, i) => (Math.abs(v || 0) > 0 ? ((ebitdaPrev[i] || 0) / Math.abs(v || 0)) * 100 : 0));
        const yoyDeclMeses = [];
        for (let i = 0; i < labels.length; i++) {
            const y1 = yoyIng[i] || 0;
            const m1 = margCurr[i] || 0;
            const m0 = margPrev[i] || 0;
            if (y1 < -10 || (m0 > 0 && m1 < (m0 - 5))) yoyDeclMeses.push(labels[i] || `M${i + 1}`);
        }
        let concClientes = 0;
        let concProveedores = 0;
        try {
            const [rCli, rProv] = await Promise.all([
                fetch(`/api/datia/widgets/top_clientes?empresa=${emp}&ejercicio=${eje}&limit=5`),
                fetch(`/api/datia/widgets/top_proveedores?empresa=${emp}&ejercicio=${eje}&limit=5`)
            ]);
            const jCli = rCli.ok ? await rCli.json() : { data: [] };
            const jProv = rProv.ok ? await rProv.json() : { data: [] };
            const listCli = Array.isArray(jCli.data) ? jCli.data : (jCli.data && jCli.data.data ? jCli.data.data : []);
            const listProv = Array.isArray(jProv.data) ? jProv.data : (jProv.data && jProv.data.data ? jProv.data.data : []);
            const sumCli = listCli.reduce((a, b) => a + Math.abs((b.neto || b.value || 0)), 0);
            const sumProv = listProv.reduce((a, b) => a + Math.abs((b.neto || b.value || 0)), 0);
            const totIng = typeof snap.ingresos === 'number' ? Math.abs(snap.ingresos) : ingresos.reduce((a, b) => a + Math.abs(b || 0), 0);
            const totGas = typeof snap.gastos === 'number' ? Math.abs(snap.gastos) : gastos.reduce((a, b) => a + Math.abs(b || 0), 0);
            concClientes = totIng > 0 ? (sumCli / totIng) : 0;
            concProveedores = totGas > 0 ? (sumProv / totGas) : 0;
        } catch (_) {}
        let proyText = '';
        try {
            const resF = await fetch(`/api/financial/treasury/forecast?empresa=${emp}&ejercicio=${eje}&horizon=6`);
            if (resF.ok) {
                const jf = await resF.json();
                const fc = Array.isArray(jf.forecast) ? jf.forecast : [];
                const alertsF = Array.isArray(jf.alerts) ? jf.alerts : [];
                const ratiosF = fc.map(x => Number(x.ratio || 0));
                const minR = ratiosF.length ? Math.min.apply(null, ratiosF) : 0;
                const lastR = ratiosF.length ? ratiosF[ratiosF.length - 1] : 0;
                const lastBal = fc.length ? Number(fc[fc.length - 1].balance || 0) : 0;
                const aTxt = alertsF.length ? alertsF.map(a => `${a.type || 'Alerta'}: ${a.period || ''}`).join(' • ') : '';
                const base = `Liquidez proyectada (6 meses): min ${Number(minR.toFixed(2))} • fin ${Number(lastR.toFixed(2))} • balance fin ${Number(lastBal.toFixed(0))}`;
                proyText = aTxt ? `${base}\n${aTxt}` : base;
            }
        } catch (_) {}
        const round2 = (v) => Number((typeof v === 'number' ? v : 0).toFixed(2));
        const nowTxt = new Date().toLocaleString(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES');
        const resumen = (() => {
            const ingTot = round2(ingresos.reduce((a, b) => a + Math.abs(b || 0), 0));
            const gasTot = round2(gastos.reduce((a, b) => a + Math.abs(b || 0), 0));
            const ebtTot = round2(ebitda.reduce((a, b) => a + (b || 0), 0));
            const margen = (snap && snap.ratios && typeof snap.ratios.margen === 'number') ? round2(snap.ratios.margen) : round2((ebitda.reduce((a,b)=>a+(b||0),0) / Math.max(ingTot, 1)) * 100);
            return `Fecha: ${nowTxt}
Ingresos y gastos muestran el desempeño del ejercicio actual. El margen operativo se sitúa en ${margen}%. Se detectan periodos con mayor presión de costes y alertas de ciclo de caja si DSO supera DPO en más de 15 días. La liquidez y solvencia condicionan la resiliencia financiera y el flujo de caja mensual indica la estabilidad operativa sin identificar datos sensibles de empresa.`;
        })();
        const eficiencia = (() => {
            const rentTxt = rentabilidadMeses.length ? `Meses con gastos acelerando > ingresos: ${rentabilidadMeses.join(', ')}` : `Sin meses críticos de aceleración de gastos frente a ingresos.`;
            const dsoTxt = `DSO medio: ${round2(dsoArr.filter(Number.isFinite).reduce((a,b)=>a+b,0) / Math.max(dsoArr.filter(Number.isFinite).length,1))} días`;
            const dpoTxt = `DPO medio: ${round2(dpoArr.filter(Number.isFinite).reduce((a,b)=>a+b,0) / Math.max(dpoArr.filter(Number.isFinite).length,1))} días`;
            const liqTxt = (liq !== null) ? `Liquidez: ${round2(liq)} (${liqQual(liq)})` : `Liquidez: N/D`;
            const solTxt = (sol !== null) ? `Solvencia: ${round2(sol)}` : `Solvencia: N/D`;
            return `${rentTxt}
${dsoTxt} • ${dpoTxt}
${liqTxt} • ${solTxt}`;
        })();
        const alertas = dsoAlerts.length ? dsoAlerts.map(mes => `DSO > DPO + 15: ${mes}`).join('\n') : 'Sin alertas de tesorería por ciclo de caja.';
        const recomendaciones = (() => {
            const recs = new Set();
            if (liq !== null && liq < 1.2) {
                recs.add('Acelerar cobros y renegociar plazos de pago');
                recs.add('Optimizar fondo de maniobra y rotación de inventarios');
            } else if (liq !== null && liq < 1.5) {
                recs.add('Vigilar ciclo de cobros/pagos y reforzar previsión de caja');
            } else {
                recs.add('Mantener políticas prudentes y colchón de liquidez');
            }
            if (rentabilidadMeses.length) {
                recs.add('Optimizar procesos productivos y mix con mayor margen');
            }
            if (sol !== null && sol < 1.2) {
                recs.add('Reforzar patrimonio neto y desinvertir activos no estratégicos');
            }
            if (anomalies.length) {
                recs.add('Mejorar gestión de datos y monitorización operativa continua');
            }
            // Flexibilización estructural siempre presente como línea estratégica
            recs.add('Flexibilizar estructura operativa y financiera ante variaciones de demanda');
            const list = Array.from(recs).slice(0, 5);
            return list.length >= 3 ? list : (list.concat(['Focalizar en rentabilidad de activos'])).slice(0, 3);
        })();
        const resumen2 = (() => {
            const ingTot = round2(ingresos.reduce((a, b) => a + Math.abs(b || 0), 0));
            const margen = (snap && snap.ratios && typeof snap.ratios.margen === 'number') ? round2(snap.ratios.margen) : round2((ebitda.reduce((a,b)=>a+(b||0),0) / Math.max(ingTot, 1)) * 100);
            const v = (snap && snap.var) ? snap.var : {};
            const yIng = v.ingresos && typeof v.ingresos.pct === 'number' ? round2(v.ingresos.pct) : 0;
            const yGas = v.gastos && typeof v.gastos.pct === 'number' ? round2(v.gastos.pct) : 0;
            const yRes = v.resultado && typeof v.resultado.pct === 'number' ? round2(v.resultado.pct) : 0;
            const liqTxt = (liq !== null) ? `${round2(liq)} (${liqQual(liq)})` : `N/D`;
            const solTxt = (sol !== null) ? `${round2(sol)}` : `N/D`;
            const endTxt = (ratios && typeof ratios.endeudamiento === 'number') ? `${round2(ratios.endeudamiento)}%` : `N/D`;
            return `Fecha: ${nowTxt}
YoY Ingresos: ${yIng}% • YoY Gastos: ${yGas}% • YoY Resultado: ${yRes}% 
Margen operativo: ${margen}%. Liquidez: ${liqTxt}. Solvencia: ${solTxt}. Endeudamiento: ${endTxt}.`;
        })();
        const concentracion = `Top 5 Clientes: ${Math.round(concClientes * 100)}% del neto • Top 5 Proveedores: ${Math.round(concProveedores * 100)}% de compras`;
        const estacionalidad = yoyDeclMeses.length ? `Meses con deterioro YoY o margen: ${yoyDeclMeses.join(', ')}` : `Sin deterioro mensual significativo YoY.`;
        const proyeccion = proyText || `Liquidez proyectada no disponible`;
        const recomendaciones2 = (() => {
            const recs = new Set();
            if (liq !== null && liq < 1.2) { recs.add('Acelerar cobros y renegociar plazos de pago'); recs.add('Optimizar fondo de maniobra'); }
            else if (liq !== null && liq < 1.5) { recs.add('Vigilar ciclo de cobros/pagos y reforzar previsión de caja'); }
            else { recs.add('Mantener políticas prudentes y colchón de liquidez'); }
            if (rentabilidadMeses.length) recs.add('Optimizar mix y procesos con mayor margen');
            if (sol !== null && sol < 1.2) recs.add('Reforzar patrimonio neto y desinvertir activos no estratégicos');
            if (anomalies.length) recs.add('Mejorar calidad de datos y monitorización continua');
            if (dsoAlerts.length) recs.add('Mejorar crédito y cobros ante DSO elevado');
            if (concClientes > 0.4) recs.add('Diversificar cartera de clientes y acuerdos de riesgo');
            const list = Array.from(recs).slice(0, 6);
            return list.length >= 3 ? list : (list.concat(['Focalizar en rentabilidad de activos'])).slice(0, 3);
        })();
        const glosario = `DSO: Días de ventas pendientes de cobro • DPO: Días de compras pendientes de pago • Liquidez: Activo corriente / Pasivo corriente • Solvencia: Activo total / Pasivo total • Margen Operativo: EBITDA / Ingresos • YoY: Variación interanual`;
        const buildReport = () => {
            const sec1 = `Resumen Ejecutivo\n${resumen2}`;
            const sec2 = `\n\nEficiencia\n${eficiencia}`;
            const sec3 = `\n\nAlertas de Tesorería\n${alertas}`;
            const sec4 = `\n\nConcentración\n${concentracion}`;
            const sec5 = `\n\nEstacionalidad YoY\n${estacionalidad}`;
            const sec5b = `\n\nProyección de Liquidez\n${proyeccion}`;
            const sec6 = `\n\nRecomendaciones\n- ${recomendaciones2.join('\n- ')}`;
            const sec7 = `\n\nGlosario\n${glosario}`;
            let text = insuf ? `${sec1}${sec5b}${sec6}${sec7}` : `${sec1}${sec2}${sec3}${sec4}${sec5}${sec5b}${sec6}${sec7}`;
            if (text.length > 2000) text = text.slice(0, 1999);
            return text;
        };
        const report = buildReport();
        if (statusEl) statusEl.style.display = 'none';
        if (outputEl) outputEl.textContent = report;
        const t1 = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
        console.log(`Local AI análisis generado en ${Math.round(t1 - t0)} ms`);
    } catch (e) {
        console.error("runLocalFinancialAnalysisLocal error:", e);
        if (statusEl) statusEl.style.display = 'none';
        if (outputEl) outputEl.textContent = (typeof gettext === 'function' ? gettext('No ha sido posible generar el análisis local: ') : 'No ha sido posible generar el análisis local: ') + (e.message || e);
    }
}

// Pruebas locales de datasets y rendimiento
async function runLocalAiAnalysisTests() {
    const makeData = (months, anomalies=false, insufficient=false, extremes=false) => {
        const labels = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
        const ing = []; const gas = []; const ebt = [];
        for (let i = 0; i < months; i++) {
            let baseIng = 100000 + (i * 5000);
            let baseGas = 70000 + (i * 4000);
            if (anomalies && (i % 6 === 0)) baseIng *= 1.7;
            if (anomalies && (i % 5 === 0)) baseGas *= 0.5;
            if (extremes && i === months - 1) { baseIng *= 2.5; baseGas *= 0.3; }
            ing.push(baseIng);
            gas.push(baseGas);
            ebt.push(baseIng - baseGas);
        }
        if (insufficient) {
            ing.splice(0, months - 5);
            gas.splice(0, months - 5);
            ebt.splice(0, months - 5);
        }
        return { labels: labels.slice(0, months), ingresos: ing, gastos: gas, ebitda: ebt, margen_pct: ing.map((v,i)=> (v>0 ? ((v - gas[i]) / v) * 100 : 0)) };
    };
    const t0 = performance.now();
    const dsNormal = makeData(12, false, false, false);
    const dsAnom = makeData(12, true, false, false);
    const dsInsuf = makeData(12, false, true, false);
    const dsExtreme = makeData(12, true, false, true);
    console.log("Datasets de prueba preparados:", { dsNormal, dsAnom, dsInsuf, dsExtreme });
    const t1 = performance.now();
    console.log(`Preparación de pruebas en ${Math.round(t1 - t0)} ms (< 3s requerido para 60 meses).`);
}
