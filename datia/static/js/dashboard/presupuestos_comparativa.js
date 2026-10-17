
console.log("Budget Comparison JS Loaded");

function loadBudgetComparison() {
    console.log("loadBudgetComparison() called");

    if (typeof ensureYearDefaults === 'function') {
        ensureYearDefaults();
    }

    let empVal = typeof currEmpresa !== 'undefined' && currEmpresa != null ? String(currEmpresa).trim() : '';
    const selEmp = document.getElementById('sel-empresa');
    if ((!empVal || empVal === 'undefined' || empVal === 'null') && selEmp && selEmp.value) {
        empVal = String(selEmp.value).trim();
    }
    if (!empVal || empVal === 'undefined' || empVal === 'null') {
        if (typeof window.__budgetCompRetry === 'undefined') window.__budgetCompRetry = 0;
        if (window.__budgetCompRetry < 5) {
            window.__budgetCompRetry += 1;
            setTimeout(loadBudgetComparison, 250);
            return;
        }
    } else {
        window.__budgetCompRetry = 0;
    }

    // Switch View
    const tree = document.getElementById('budget-tree-container');
    const grid = document.getElementById('budget-grid-container');
    const comp = document.getElementById('budget-comparison-container');

    if (tree) tree.style.display = 'none';
    if (grid) grid.style.display = 'none';
    if (comp) {
        comp.style.display = 'block';
        comp.innerHTML = `<div class="loading-spinner"></div> Loading Analysis...`;
    }

    // Hide Toolbar extras not needed
    // (Optional: toggle visibility of other buttons if desired)

    fetchComparisonData();
}

async function fetchComparisonData() {
    const container = document.getElementById('budget-comparison-container');
    if (!container) return;

    let empresa = (typeof currEmpresa !== 'undefined' && currEmpresa != null) ? String(currEmpresa).trim() : '';
    if (!empresa || empresa === 'undefined' || empresa === 'null') {
        const selEmp = document.getElementById('sel-empresa');
        if (selEmp && selEmp.value) {
            empresa = String(selEmp.value).trim();
        }
    }

    const budInp = document.getElementById('budget-target-year');
    const selEje = document.getElementById('sel-ejercicio');
    const curr = parseInt((selEje && selEje.value) ? selEje.value : (typeof currEjercicio !== 'undefined' ? currEjercicio : new Date().getFullYear()));
    let budgetYear = budInp ? parseInt(budInp.value || curr) : curr;

    if (isNaN(budgetYear) || budgetYear < 1900) budgetYear = curr;

    if (!empresa || empresa === 'undefined' || empresa === 'null' || isNaN(parseInt(empresa, 10))) {
        container.innerHTML = `<div style="text-align:center; color:#ef4444; padding:20px;">Selecciona una empresa antes de ver la comparativa.</div>`;
        return;
    }

    if (isNaN(budgetYear)) {
        container.innerHTML = `<div style="text-align:center; color:#ef4444; padding:20px;">Selecciona un ejercicio válido para ver la comparativa.</div>`;
        return;
    }

    try {
        const res = await fetch(`/api/financial/budgets/comparison?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(budgetYear)}`);
        if (!res.ok) throw new Error("Failed to load comparison");
        const data = await res.json();

        if (!data || data.status === 'no_data') {
            const reason = (data && data.reason) || 'Sin datos de comparativa para la empresa / ejercicio seleccionados.';
            container.innerHTML = `<div style="text-align:center; color:#e5e7eb; padding:20px;">${reason}</div>`;
            return;
        }

        renderComparisonView(data, budgetYear);
    } catch (e) {
        console.error("Comp Load Error", e);
        container.innerHTML = `<div style="text-align:center; color:#ef4444; padding:20px;">Error al cargar la comparativa.<br><small>${e.message}</small></div>`;
    }
}

function renderComparisonView(data, year) {
    const container = document.getElementById('budget-comparison-container');
    if (!container) return;

    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0, useGrouping: true });

    // Calculate Summary KPIs
    // We can sum from table data locally or use totals if provided.
    // Let's use charts.monthly sums for quick KPIs
    const realIncIdx = data.charts.monthly.real_income || [];
    const budIncIdx = data.charts.monthly.budget_income || [];
    const realExpIdx = data.charts.monthly.real_expense || [];
    const budExpIdx = data.charts.monthly.budget_expense || [];

    const sumArr = (arr) => arr.reduce((a, b) => a + (parseFloat(b) || 0), 0);
    const totRealInc = sumArr(realIncIdx);
    const totBudInc = sumArr(budIncIdx);
    const totRealExp = sumArr(realExpIdx);
    const totBudExp = sumArr(budExpIdx);

    const diffInc = totRealInc - totBudInc;
    const diffExp = totRealExp - totBudExp; // Real expense > Budget is BAD (usually). 

    // HTML Structure
    let html = `
    <div style="display: flex; flex-direction: column; gap: 20px;">
        
        <!-- KPIs Summary -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px;">
            <div class="glass-panel" style="padding: 15px; text-align: center;">
                <div style="color: #a1a1aa; font-size: 0.9rem;">Ingresos Real</div>
                <div style="font-size: 1.4rem; font-weight: bold; color: #fff;">${nf.format(totRealInc)} €</div>
                <div style="font-size: 0.85rem; color: ${diffInc >= 0 ? '#10b981' : '#ef4444'};">
                    ${diffInc >= 0 ? '+' : ''}${nf.format(diffInc)} vs Presup.
                </div>
            </div>
             <div class="glass-panel" style="padding: 15px; text-align: center;">
                <div style="color: #a1a1aa; font-size: 0.9rem;">Ingresos Presup.</div>
                <div style="font-size: 1.4rem; font-weight: bold; color: #fff;">${nf.format(totBudInc)} €</div>
            </div>
            <div class="glass-panel" style="padding: 15px; text-align: center;">
                <div style="color: #a1a1aa; font-size: 0.9rem;">Gastos Real</div>
                <div style="font-size: 1.4rem; font-weight: bold; color: #fff;">${nf.format(totRealExp)} €</div>
                <div style="font-size: 0.85rem; color: ${diffExp <= 0 ? '#10b981' : '#ef4444'};">
                    ${diffExp > 0 ? '+' : ''}${nf.format(diffExp)} vs Presup.
                </div>
            </div>
             <div class="glass-panel" style="padding: 15px; text-align: center;">
                <div style="color: #a1a1aa; font-size: 0.9rem;">Gastos Presup.</div>
                <div style="font-size: 1.4rem; font-weight: bold; color: #fff;">${nf.format(totBudExp)} €</div>
            </div>
        </div>

        <!-- Charts Row -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
             <!-- Monthly Evolution -->
             <div class="glass-panel" style="padding: 20px;">
                <h4 style="margin:0 0 15px 0; color:#fff; font-weight:500;">Evolución Mensual (Ingresos vs Gastos)</h4>
                <div id="chart-comp-monthly" style="width: 100%; height: 300px;"></div>
             </div>
             <!-- Cumulative Deviation -->
             <div class="glass-panel" style="padding: 20px;">
                <h4 style="margin:0 0 15px 0; color:#fff; font-weight:500;">Acumulado Prespuestado vs Real</h4>
                <div id="chart-comp-cumulative" style="width: 100%; height: 300px;"></div>
             </div>
        </div>


        <!-- Detail Table (Refundación) -->
        <div class="glass-panel" style="padding: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h4 style="margin:0; color:#fff; font-weight:500;">Detalle por Cuenta</h4>
            </div>
            <div class="budget-comp-container">
                <table class="budget-comp-table">
                    <thead>
                        <tr>
                            <th class="comp-col-code">Cuenta</th>
                            <th class="comp-col-desc">Descripción</th>
                            <th class="comp-col-val">Real (${year})</th>
                            <th class="comp-col-val">Presupuesto</th>
                            <th class="comp-col-var">Variación</th>
                        </tr>
                    </thead>
                    <tbody>
                    ${(data.table || []).map(row => {
        const valDiff = row.desviacion;
        const isIngreso = row.is_ingreso;

        // LOGIC: Red = Bad, Green = Good
        let isBad = false;
        if (isIngreso) {
            // Income: Less than budget is BAD
            isBad = valDiff < 0;
        } else {
            // Expense: More than budget is BAD
            isBad = valDiff > 0;
        }

        // Colors
        const colorClass = isBad ? 'text-danger' : 'text-success';
        const badgeClass = isBad ? 'negative' : 'positive';

        // Arrows logic: strictly mathematical direction
        // Up = Positive Diff, Down = Negative Diff
        const arrow = valDiff > 0 ? 'bi-arrow-up-short' : (valDiff < 0 ? 'bi-arrow-down-short' : 'bi-dash');

        const diffStr = (valDiff > 0 ? '+' : '') + nf.format(valDiff);
        const pctStr = (isFinite(row.desviacion_pct) ? Math.abs(row.desviacion_pct).toFixed(1) : '0.0') + '%';

        return `
                        <tr>
                            <td class="comp-col-code">${row.cuenta}</td>
                            <td class="comp-col-desc" title="${row.descripcion}">${row.descripcion}</td>
                            <td class="comp-col-val" style="font-weight:600;">${nf.format(row.real)}</td>
                            <td class="comp-col-val muted">${nf.format(row.presupuesto)}</td>
                            <td class="comp-col-var">
                                <div class="var-cell">
                                    <span class="var-val ${colorClass}">${diffStr}</span>
                                    <span class="var-badge ${badgeClass}">
                                        <i class="bi ${arrow}"></i> ${pctStr}
                                    </span>
                                </div>
                            </td>
                        </tr>
                        `;
    }).join('')}
                    </tbody>
                </table>
            </div>
        </div>

    </div>
    `;

    container.innerHTML = html;

    // Render Charts with ECharts
    renderCompCharts(data);
}

function budgetHeaderYear() {
    const sel = document.getElementById('sel-ejercicio');
    const raw = (sel && sel.value) ? sel.value : (typeof currEjercicio !== 'undefined' ? currEjercicio : new Date().getFullYear());
    const year = parseInt(raw, 10);
    return isNaN(year) ? new Date().getFullYear() : year;
}

function budgetHeaderEmpresa() {
    let empresa = (typeof currEmpresa !== 'undefined' && currEmpresa != null) ? String(currEmpresa).trim() : '';
    if (!empresa || empresa === 'undefined' || empresa === 'null') {
        const selEmp = document.getElementById('sel-empresa');
        if (selEmp && selEmp.value) empresa = String(selEmp.value).trim();
    }
    return empresa;
}

async function loadBudgetDashboard() {
    const root = document.getElementById('budget-dashboard-root');
    if (!root) return;
    const empresa = budgetHeaderEmpresa();
    const year = budgetHeaderYear();
    if (!empresa || isNaN(parseInt(empresa, 10))) {
        root.innerHTML = `<div style="text-align:center; color:#e5e7eb; padding:28px;">Selecciona una empresa para ver el control del ejercicio.</div>`;
        return;
    }
    root.innerHTML = `<div style="text-align:center; color:#a1a1aa; padding:28px;">Cargando control de ${year}...</div>`;
    try {
        const res = await fetch(`/api/financial/budgets/comparison?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(year)}`);
        if (!res.ok) throw new Error('No se ha podido leer la comparativa');
        const data = await res.json();
        renderBudgetDashboard(data, year);
    } catch (e) {
        root.innerHTML = `<div style="text-align:center; color:#fca5a5; padding:28px;">No se ha podido cargar el control de ${year}.</div>`;
    }
}

function renderBudgetDashboard(data, year) {
    const root = document.getElementById('budget-dashboard-root');
    if (!root) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0, useGrouping: true });
    const monthly = (data.charts && data.charts.monthly) || {};
    const sumArr = (arr) => (arr || []).reduce((a, b) => a + (parseFloat(b) || 0), 0);
    const realInc = sumArr(monthly.real_income);
    const budInc = sumArr(monthly.budget_income);
    const realExp = sumArr(monthly.real_expense);
    const budExp = sumArr(monthly.budget_expense);
    const realNet = realInc - realExp;
    const budNet = budInc - budExp;
    const hasBudget = (data.table || []).some(row => Math.abs(Number(row.presupuesto) || 0) > 0.004);
    const money = (n) => `${nf.format(n)} €`;
    const gap = (real, bud, higherIsBetter) => {
        const d = real - bud;
        const good = higherIsBetter ? d >= 0 : d <= 0;
        const color = good ? '#86efac' : '#fca5a5';
        const sign = d > 0 ? '+' : '';
        return `<div style="font-size:0.82rem; color:${color};">${sign}${nf.format(d)} vs presupuesto</div>`;
    };

    if (!hasBudget) {
        root.innerHTML = `
            <div style="display:flex; flex-direction:column; gap:16px;">
                <div>
                    <h2 style="margin:0; color:#fff; font-size:1.35rem;">Control presupuestario ${year}</h2>
                    <div style="color:#a1a1aa; margin-top:6px;">Ejercicio seleccionado en la cabecera.</div>
                </div>
                <div style="padding:16px 18px; border-radius:12px; border:1px solid rgba(251,191,36,0.35); background:rgba(251,191,36,0.08); color:#fde68a;">
                    No hay presupuesto guardado para ${year}. El real del ejercicio sí está disponible. Prepáralo en Presupuestos: el año base puede ser este ejercicio y el destino, el siguiente.
                    <div style="margin-top:12px;">
                        <button type="button" onclick="switchSubTab('sub-presupuestos')" style="background:#2563eb; color:#fff; border:0; border-radius:8px; padding:8px 14px; cursor:pointer;">Ir a Presupuestos</button>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px;">
                    <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Ingresos reales</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realInc)}</div></div>
                    <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Gastos reales</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realExp)}</div></div>
                    <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Resultado real</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realNet)}</div></div>
                </div>
            </div>`;
        return;
    }

    const ranked = (data.table || []).slice().sort((a, b) => Math.abs(b.desviacion || 0) - Math.abs(a.desviacion || 0)).slice(0, 12);
    root.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:16px;">
            <div>
                <h2 style="margin:0; color:#fff; font-size:1.35rem;">Control presupuestario ${year}</h2>
                <div style="color:#a1a1aa; margin-top:6px;">Real contra presupuesto del ejercicio seleccionado.</div>
            </div>
            <div style="display:grid; grid-template-columns:repeat(3, minmax(0,1fr)); gap:12px;">
                <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Ingresos</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realInc)}</div><div style="color:#a1a1aa; font-size:0.8rem;">Presupuesto ${money(budInc)}</div>${gap(realInc, budInc, true)}</div>
                <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Gastos</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realExp)}</div><div style="color:#a1a1aa; font-size:0.8rem;">Presupuesto ${money(budExp)}</div>${gap(realExp, budExp, false)}</div>
                <div class="glass-panel" style="padding:16px;"><div style="color:#a1a1aa; font-size:0.8rem;">Resultado</div><div style="color:#fff; font-size:1.35rem; font-weight:700;">${money(realNet)}</div><div style="color:#a1a1aa; font-size:0.8rem;">Presupuesto ${money(budNet)}</div>${gap(realNet, budNet, true)}</div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                <div class="glass-panel" style="padding:16px;"><h3 style="margin:0 0 10px; color:#fff; font-size:1rem;">Mes a mes</h3><div id="chart-dash-monthly" style="height:280px;"></div></div>
                <div class="glass-panel" style="padding:16px;"><h3 style="margin:0 0 10px; color:#fff; font-size:1rem;">Resultado acumulado</h3><div id="chart-dash-cumulative" style="height:280px;"></div></div>
            </div>
            <div class="glass-panel" style="padding:16px;">
                <h3 style="margin:0 0 10px; color:#fff; font-size:1rem;">Cuentas que más se apartan</h3>
                <table class="budget-comp-table"><thead><tr><th>Cuenta</th><th>Descripción</th><th>Real</th><th>Presupuesto</th><th>Desviación</th></tr></thead><tbody>
                ${ranked.map(row => {
                    const diff = Number(row.desviacion) || 0;
                    const bad = row.is_ingreso ? diff < 0 : diff > 0;
                    const color = bad ? '#fca5a5' : '#86efac';
                    const sign = diff > 0 ? '+' : '';
                    return `<tr><td>${row.cuenta}</td><td>${row.descripcion || ''}</td><td>${nf.format(row.real)}</td><td>${nf.format(row.presupuesto)}</td><td style="color:${color}">${sign}${nf.format(diff)}</td></tr>`;
                }).join('')}
                </tbody></table>
            </div>
        </div>`;
    renderDashCharts(data);
}

function renderDashCharts(data) {
    if (!window.echarts) return;
    const labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const monthly = data.charts.monthly;
    const cumulative = data.charts.cumulative;
    const axis = { axisLine: { lineStyle: { color: '#555' } }, axisLabel: { color: '#a1a1aa' }, splitLine: { lineStyle: { color: '#333' } } };
    const monthDom = document.getElementById('chart-dash-monthly');
    if (monthDom) {
        const chart = echarts.init(monthDom);
        chart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { textStyle: { color: '#ccc' } },
            grid: { left: 48, right: 16, bottom: 28, top: 36 },
            xAxis: { type: 'category', data: labels, ...axis },
            yAxis: { type: 'value', ...axis },
            series: [
                { name: 'Ingresos real', type: 'bar', data: monthly.real_income, itemStyle: { color: '#34d399' } },
                { name: 'Ingresos presupuesto', type: 'bar', data: monthly.budget_income, itemStyle: { color: '#065f46' } },
                { name: 'Gastos real', type: 'bar', data: monthly.real_expense, itemStyle: { color: '#f87171' } },
                { name: 'Gastos presupuesto', type: 'bar', data: monthly.budget_expense, itemStyle: { color: '#7f1d1d' } }
            ]
        });
    }
    const cumDom = document.getElementById('chart-dash-cumulative');
    if (cumDom) {
        const chart = echarts.init(cumDom);
        chart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { textStyle: { color: '#ccc' } },
            grid: { left: 48, right: 16, bottom: 28, top: 36 },
            xAxis: { type: 'category', data: labels, ...axis },
            yAxis: { type: 'value', ...axis },
            series: [
                { name: 'Resultado real', type: 'line', smooth: true, data: cumulative.real_income.map((inc, i) => inc - cumulative.real_expense[i]), itemStyle: { color: '#60a5fa' } },
                { name: 'Resultado presupuesto', type: 'line', smooth: true, lineStyle: { type: 'dashed' }, data: cumulative.budget_income.map((inc, i) => inc - cumulative.budget_expense[i]), itemStyle: { color: '#a78bfa' } }
            ]
        });
    }
}

function renderCompCharts(data) {
    const theme = (typeof getTheme === 'function' ? getTheme() : 'dark'); // Fallback
    const labels = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];

    // 1. Monthly Chart
    const domMonthly = document.getElementById('chart-comp-monthly');
    if (domMonthly) {
        const chart = echarts.init(domMonthly, theme);
        const option = {
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            legend: { top: 0, textStyle: { color: '#ccc' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            textStyle: { fontFamily: 'Inter, sans-serif' },
            xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#555' } } },
            yAxis: { type: 'value', axisLabel: { formatter: '{value} €' }, axisLine: { lineStyle: { color: '#555' } }, splitLine: { lineStyle: { color: '#333' } } },
            series: [
                {
                    name: 'Ingresos Real',
                    type: 'bar',
                    data: data.charts.monthly.real_income,
                    itemStyle: { color: '#10b981' }
                },
                {
                    name: 'Ingresos Presup.',
                    type: 'bar',
                    data: data.charts.monthly.budget_income,
                    itemStyle: { color: '#059669', opacity: 0.6 } // Darker green
                },
                {
                    name: 'Gastos Real',
                    type: 'bar',
                    data: data.charts.monthly.real_expense,
                    itemStyle: { color: '#ef4444' }
                },
                {
                    name: 'Gastos Presup.',
                    type: 'bar',
                    data: data.charts.monthly.budget_expense,
                    itemStyle: { color: '#b91c1c', opacity: 0.6 } // Darker red
                }
            ]
        };
        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
    }

    // 2. Cumulative Chart
    const domCum = document.getElementById('chart-comp-cumulative');
    if (domCum) {
        const chart = echarts.init(domCum, theme);
        const option = {
            tooltip: { trigger: 'axis' },
            legend: { top: 0, textStyle: { color: '#ccc' } },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            textStyle: { fontFamily: 'Inter, sans-serif' },
            xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#555' } } },
            yAxis: { type: 'value', axisLabel: { formatter: '{value} €' }, axisLine: { lineStyle: { color: '#555' } }, splitLine: { lineStyle: { color: '#333' } } },
            series: [
                {
                    name: 'Resultado Real (Acum)',
                    type: 'line',
                    smooth: true,
                    // Calc result: Income - Expense
                    data: data.charts.cumulative.real_income.map((inc, i) => inc - data.charts.cumulative.real_expense[i]),
                    itemStyle: { color: '#3b82f6' },
                    areaStyle: { opacity: 0.1 }
                },
                {
                    name: 'Resultado Presup. (Acum)',
                    type: 'line',
                    smooth: true,
                    data: data.charts.cumulative.budget_income.map((inc, i) => inc - data.charts.cumulative.budget_expense[i]),
                    itemStyle: { color: '#6366f1' },
                    lineStyle: { type: 'dashed' }
                }
            ]
        };
        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
    }
}
