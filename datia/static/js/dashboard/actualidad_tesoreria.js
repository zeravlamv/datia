/**
 * Actualidad Tesorería Logic
 * Handles data fetching and rendering for the Treasury Dashboard.
 */

async function loadTesoreriaData() {
    // 1. Context
    const selEmp = document.getElementById('sel-empresa');
    const selEje = document.getElementById('sel-ejercicio');
    let empresa = selEmp && selEmp.value ? selEmp.value : ((typeof currEmpresa !== 'undefined' && currEmpresa) ? currEmpresa : (new URLSearchParams(window.location.search).get('empresa') || ''));
    let ejercicio = selEje && selEje.value ? selEje.value : ((typeof currEjercicio !== 'undefined' && currEjercicio) ? currEjercicio : (new URLSearchParams(window.location.search).get('ejercicio') || ''));
    empresa = String(empresa || '').trim();
    ejercicio = String(ejercicio || '').trim();

    console.log(`[Tesoreria] Loading for ${empresa}/${ejercicio}`);

    if (!empresa || !ejercicio) {
        console.warn("[Tesoreria] Context not ready");
        setTimeout(() => { try { loadTesoreriaData(); } catch (_) {} }, 250);
        return;
    }

    // Show Loading state if needed
    // ...

    try {
        const url = `/api/financial/treasury?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(ejercicio)}`;
        console.log(`[Tesoreria] Fetching ${url}`);
        const extras = ['extra-pendiente-cobro','extra-impagados','extra-dias-cobro','extra-pendiente-pago'];
        extras.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = 'Calculando…'; });
        const response = await fetch(url);
        const data = await response.json();
        console.log("[Tesoreria] Data received:", data);

        if (data && data.meta && data.meta.data_available) {
            console.log("[Tesoreria] Rendering KPIs...");
            renderTesoreriaKPIs(data.kpis, data.aging);
            renderTesoreriaCharts(data.charts);
            if (window.cacheAgingData) window.cacheAgingData(data.aging);
            if (window.renderAgingReceivablesChart) window.renderAgingReceivablesChart(data.aging);
            if (window.renderAgingPayablesChart) window.renderAgingPayablesChart(data.aging);
            if (window.ensureTesoreriaPolling) window.ensureTesoreriaPolling();
            renderTesoreriaEvolution(empresa, ejercicio);
            await loadTesoreriaForecast(empresa, ejercicio);
        } else {
            console.warn("[Tesoreria] No treasury data available (meta.data_available is false/missing)");
            if (data) console.warn("Meta:", data.meta);
            const ids = ['kpi-pendiente-cobro','kpi-impagados','kpi-dias-cobro','kpi-pendiente-pago','kpi-ratio-cobro','kpi-ratio-pago','kpi-ratio-tesoreria','kpi-ratio-endeudamiento'];
            ids.forEach(id => { const el = document.getElementById(id); if (el) el.textContent = 'Sin datos'; });
            ['extra-pendiente-cobro','extra-impagados','extra-dias-cobro','extra-pendiente-pago'].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = '—'; });
            ['chart-tesoreria-clientes','chart-tesoreria-proveedores','chart-tesoreria-bancos','chart-tesoreria-evolucion'].forEach(id => {
                const dom = document.getElementById(id);
                if (!dom) return;
                const inst = window.echarts ? echarts.getInstanceByDom(dom) : null;
                if (inst) inst.dispose();
                dom.innerText = 'Sin datos';
            });
        }
    } catch (error) {
        console.error("Error loading treasury data:", error);
        showToast("Error al cargar tesorería", "error");
    }
}

function renderTesoreriaKPIs(kpis, aging) {
    if (!kpis) return;

    // Formatters
    const fmtMoney = (v) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
    const fmtNum = (v) => new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(v);

    document.getElementById('kpi-pendiente-cobro').textContent = fmtMoney(kpis.receivables);
    document.getElementById('kpi-impagados').textContent = fmtMoney(kpis.cartera_importe_cobros);
    document.getElementById('kpi-dias-cobro').textContent = fmtNum(kpis.dso) + " días";
    document.getElementById('kpi-pendiente-pago').textContent = fmtMoney(kpis.payables);
    const cashEl = document.getElementById('kpi-cash');
    if (cashEl) cashEl.textContent = fmtMoney(kpis.cash || 0);
    const wcEl = document.getElementById('kpi-wc');
    if (wcEl) wcEl.textContent = fmtMoney(kpis.working_capital || 0);

    document.getElementById('kpi-ratio-cobro').textContent = fmtNum(kpis.dso) + " días"; // Using DSO for now
    document.getElementById('kpi-ratio-pago').textContent = fmtNum(kpis.dpo) + " días"; // Using DPO

    // Ratios
    // Tesoreria (Liquidez)
    // Ratios
    // Tesoreria (Liquidez) ~ (Working Capital / Payables) + 1
    let liqRatio = 0;
    const payables = kpis.payables || 0;
    const wc = kpis.working_capital || 0;

    if (payables > 0) {
        liqRatio = (wc / payables) + 1;
    }

    const liqEl = document.getElementById('kpi-ratio-tesoreria');
    if (liqEl) liqEl.textContent = fmtNum(liqRatio);

    const endEl = document.getElementById('kpi-ratio-endeudamiento');
    if (endEl) endEl.textContent = "-"; // Requires Equity data not present in snapshot

    // Extras: suma total del campo Importe (Cartera)
    try {
        const tot = (typeof kpis.cartera_importe_total === 'number') ? kpis.cartera_importe_total : 0;
        const totCobros = (typeof kpis.cartera_importe_cobros === 'number') ? kpis.cartera_importe_cobros : 0;
        const totPagos = (typeof kpis.cartera_importe_pagos === 'number') ? kpis.cartera_importe_pagos : 0;
        const setTxt = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = fmtMoney(val); };
        setTxt('extra-pendiente-cobro', totCobros);
        setTxt('extra-dias-cobro', tot);
        setTxt('extra-pendiente-pago', totPagos);
        const ov = aging && aging.receivables_cartera ? aging.receivables_cartera : null;
        if (ov) {
            const el = document.getElementById('extra-impagados');
            if (el) {
                const html = [
                    `30: <span class="aging-amount" data-bucket="0-30">${fmtMoney(ov['0-30']||0)}</span>`,
                    `60: <span class="aging-amount" data-bucket="30-60">${fmtMoney(ov['30-60']||0)}</span>`,
                    `90: <span class="aging-amount" data-bucket="60-90">${fmtMoney(ov['60-90']||0)}</span>`,
                    `>90: <span class="aging-chip critical aging-amount" data-bucket=">90">${fmtMoney(ov['>90']||0)}</span>`
                ].join(' • ');
                el.innerHTML = html;
                if (!el.dataset.boundClick) {
                    el.addEventListener('click', (ev) => {
                        const target = ev.target.closest('.aging-amount');
                        if (!target) return;
                        const bucket = target.getAttribute('data-bucket');
                        if (!bucket) return;
                        openCarteraBucketModal(bucket);
                    }, { passive: true });
                    el.dataset.boundClick = '1';
                }
            }
        } else {
            const el = document.getElementById('extra-impagados');
            if (el) el.textContent = '—';
        }
    } catch (e) {
        const el = document.getElementById('extra-impagados');
        if (el) el.textContent = '—';
        console.warn("[Tesoreria] Extras render error:", e);
    }

    // Warning discreto: diferencias contable vs cartera (cobro/pago)
    try {
        const thr = 0.5; // umbral mínimo en euros
        const recCont = typeof kpis.receivables === 'number' ? kpis.receivables : 0;
        const recCart = typeof kpis.cartera_importe_cobros === 'number' ? kpis.cartera_importe_cobros : 0;
        const payCont = typeof kpis.payables === 'number' ? kpis.payables : 0;
        const payCart = typeof kpis.cartera_importe_pagos === 'number' ? kpis.cartera_importe_pagos : 0;
        const warnCobro = Math.abs(recCont - recCart) > thr;
        const warnPago = Math.abs(payCont - payCart) > thr;
        const elCobro = document.getElementById('warn-pendiente-cobro');
        const elPago = document.getElementById('warn-pendiente-pago');
        if (elCobro) elCobro.classList.toggle('visible', warnCobro);
        if (elPago) elPago.classList.toggle('visible', warnPago);
    } catch (e) {
        console.warn("[Tesoreria] Warn compute error:", e);
    }
}

// Modal detalle por cuenta contable (Pendiente de cobro)
function openReceivablesBreakdownModal() {
    const empresa = document.getElementById('sel-empresa').value;
    const ejercicio = document.getElementById('sel-ejercicio').value;
    let overlay = document.getElementById('treasury-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'treasury-overlay';
        overlay.className = 'treasury-overlay';
        overlay.innerHTML = `
            <div class="treasury-modal" role="dialog" aria-modal="true" aria-labelledby="treasury-title">
                <div class="treasury-header">
                    <div id="treasury-title">Detalle por cuenta (Clientes 43*)</div>
                    <button class="treasury-close" onclick="document.getElementById('treasury-overlay').style.display='none'" aria-label="Cerrar">×</button>
                </div>
                <div class="treasury-actions">
                    <button id="treasury-back" class="kpi-detail-chip" type="button" aria-label="Volver" style="display:none;">Atrás</button>
                    <button id="treasury-close-2" class="kpi-detail-chip" type="button" aria-label="Cerrar modal" onclick="document.getElementById('treasury-overlay').style.display='none'">Cerrar</button>
                </div>
                <div class="treasury-breadcrumb" id="treasury-breadcrumb"></div>
                <div class="treasury-meta">
                    <span class="label">Cartera:</span> <span id="treasury-cartera-total">--</span>
                    <span class="sep">•</span>
                    <span class="label">Saldos:</span> <span id="treasury-contable-total">--</span>
                    <span class="sep">•</span>
                    <span class="label">Dif.:</span> <span id="treasury-diff-total">--</span>
                </div>
                <div class="treasury-body">
                    <div id="treasury-loading">Cargando…</div>
                    <table class="treasury-table" id="treasury-table" style="display:none;">
                        <thead>
                            <tr><th>Cuenta</th><th>Descripción</th><th class="val">Saldo</th><th class="val">Cartera</th><th class="val">Dif.</th></tr>
                        </thead>
                        <tbody id="treasury-tbody"></tbody>
                    </table>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    }
    overlay.style.display = 'flex';
    overlay.dataset.stack = JSON.stringify([{ parent: '43', level: 3, title: '43*' }]);
    const loading = document.getElementById('treasury-loading');
    const table = document.getElementById('treasury-table');
    const tbody = document.getElementById('treasury-tbody');
    const metaSpan = document.getElementById('treasury-cartera-total');
    const fmtMoney = (v) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
    if (tbody) tbody.innerHTML = '';
    if (loading) loading.style.display = 'block';
    if (table) table.style.display = 'none';
    try {
        const k = (window.cachedFinancialData && window.cachedFinancialData.kpis) ? window.cachedFinancialData.kpis : null;
        const val = k && typeof k.cartera_importe_cobros === 'number' ? k.cartera_importe_cobros : null;
        if (metaSpan && val !== null) metaSpan.textContent = fmtMoney(val);
        if (metaSpan && val === null) {
            fetch(`/api/financial/treasury?empresa=${empresa}&ejercicio=${ejercicio}`)
                .then(r => r.json())
                .then(d => {
                    const v = (d && d.kpis && typeof d.kpis.cartera_importe_cobros === 'number') ? d.kpis.cartera_importe_cobros : 0;
                    metaSpan.textContent = fmtMoney(v);
                })
                .catch(() => {});
        }
    } catch {}
    loadReceivablesBreakdownInitial(empresa, ejercicio);
    const breadcrumb = document.getElementById('treasury-breadcrumb');
    const backBtn = document.getElementById('treasury-back');
    const fmtCrumb = () => {
        try {
            const stack = JSON.parse(overlay.dataset.stack || '[]');
            if (breadcrumb) {
                breadcrumb.innerHTML = stack.map((s, idx) => {
                    const label = s.title || s.parent;
                    return `<span class="crumb" data-idx="${idx}">${label}</span>${idx < stack.length-1 ? '<span class="sep">›</span>' : ''}`;
                }).join('');
                breadcrumb.querySelectorAll('.crumb').forEach(el => {
                    el.addEventListener('click', () => {
                        const targetIdx = parseInt(el.getAttribute('data-idx'), 10);
                        const st = JSON.parse(overlay.dataset.stack || '[]').slice(0, targetIdx+1);
                        overlay.dataset.stack = JSON.stringify(st);
                        const top = st[st.length-1];
                        if (st.length === 1) {
                            loadReceivablesBreakdownInitial(empresa, ejercicio);
                        } else {
                            loadReceivablesBreakdownDetail(empresa, ejercicio, top.parent, top.level);
                        }
                        backBtn.style.display = st.length > 1 ? 'inline-flex' : 'none';
                        fmtCrumb();
                    });
                });
            }
        } catch {}
    };
    fmtCrumb();
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            try {
                const st = JSON.parse(overlay.dataset.stack || '[]');
                if (st.length <= 1) return;
                const newStack = st.slice(0, st.length-1);
                overlay.dataset.stack = JSON.stringify(newStack);
                const top = newStack[newStack.length-1];
                if (newStack.length === 1) {
                    loadReceivablesBreakdownInitial(empresa, ejercicio);
                } else {
                    loadReceivablesBreakdownDetail(empresa, ejercicio, top.parent, top.level);
                }
                backBtn.style.display = newStack.length > 1 ? 'inline-flex' : 'none';
                fmtCrumb();
            } catch {}
        });
    }
    tbody.addEventListener('click', (e) => {
        const tr = e.target.closest('tr[data-code]');
        if (!tr) return;
        const code = tr.getAttribute('data-code');
        if (code && code.length === 3) {
            loadReceivablesBreakdownFlat(empresa, ejercicio, code);
        } else {
            const nextLevel = 7;
            loadReceivablesBreakdownDetail(empresa, ejercicio, code, nextLevel);
        }
        try {
            const st = JSON.parse(overlay.dataset.stack || '[]');
            const pushItem = code && code.length === 3 ? { parent: code, level: 'flat', title: code } : { parent: code, level: 7, title: code };
            st.push(pushItem);
            overlay.dataset.stack = JSON.stringify(st);
            if (backBtn) backBtn.style.display = 'inline-flex';
        } catch {}
        fmtCrumb();
    }, { passive: true });
}

function openCarteraBucketModal(bucket) {
    const empresa = document.getElementById('sel-empresa').value;
    const ejercicio = document.getElementById('sel-ejercicio').value;
    let overlay = document.getElementById('bucket-overlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'bucket-overlay';
        overlay.className = 'treasury-overlay';
        overlay.innerHTML = `
            <div class="treasury-modal" role="dialog" aria-modal="true" aria-labelledby="bucket-title">
                <div class="treasury-header">
                    <div id="bucket-title">Clientes por periodo ${bucket}</div>
                    <button class="treasury-close" onclick="document.getElementById('bucket-overlay').style.display='none'" aria-label="Cerrar">×</button>
                </div>
                <div class="treasury-meta"><span class="label">Total periodo:</span> <span id="bucket-total">--</span></div>
                <div class="treasury-body">
                    <div id="bucket-loading">Cargando…</div>
                    <table class="treasury-table" id="bucket-table" style="display:none;">
                        <thead><tr><th>Cliente</th><th class="val">Importe</th></tr></thead>
                        <tbody id="bucket-tbody"></tbody>
                    </table>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
    } else {
        const title = overlay.querySelector('#bucket-title');
        if (title) title.textContent = `Clientes por periodo ${bucket}`;
    }
    overlay.style.display = 'flex';
    const loading = document.getElementById('bucket-loading');
    const table = document.getElementById('bucket-table');
    const tbody = document.getElementById('bucket-tbody');
    if (tbody) tbody.innerHTML = '';
    if (loading) loading.style.display = 'block';
    if (table) table.style.display = 'none';
    fetch(`/api/financial/treasury/cartera_clients_bucket?empresa=${empresa}&ejercicio=${ejercicio}&bucket=${encodeURIComponent(bucket)}`)
        .then(r => r.json())
        .then(json => {
            const rows = Array.isArray(json.rows) ? json.rows : [];
            const fmtMoney = (v) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
            let total = 0.0;
            rows.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${row.name || row.code}</td><td class="val">${fmtMoney(row.value || 0)}</td>`;
                tbody.appendChild(tr);
                total += parseFloat(row.value || 0);
            });
            const ttl = document.getElementById('bucket-total');
            if (ttl) ttl.textContent = fmtMoney(total);
            if (rows.length === 0) {
                const tr = document.createElement('tr');
                tr.innerHTML = `<td colspan="2" class="val">Sin datos</td>`;
                tbody.appendChild(tr);
            }
        })
        .catch(e => {
            if (loading) loading.textContent = 'Error al cargar clientes';
            console.error("Bucket clients error", e);
        })
        .finally(() => {
            if (loading) loading.style.display = 'none';
            if (table) table.style.display = 'table';
        });
}

function populateReceivablesTable(rows, empresa, ejercicio) {
    const loading = document.getElementById('treasury-loading');
    const table = document.getElementById('treasury-table');
    const tbody = document.getElementById('treasury-tbody');
    const fmtMoney = (v) => new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(v);
    if (tbody) tbody.innerHTML = '';
    (rows || []).forEach(row => {
        const tr = document.createElement('tr');
        tr.setAttribute('data-code', row.cuenta);
        tr.innerHTML = `<td>${row.cuenta}</td><td>${row.descripcion || ''}</td><td class="val">${fmtMoney(row.saldo || 0)}</td><td class="val cartera-val">--</td><td class="val dif-val">--</td>`;
        tbody.appendChild(tr);
    });
    const codes = (rows || []).map(r => r.cuenta).join(',');
    const metaCartera = document.getElementById('treasury-cartera-total');
    const metaContable = document.getElementById('treasury-contable-total');
    const metaDiff = document.getElementById('treasury-diff-total');
    let contableTotal = 0.0;
    (rows || []).forEach(r => { contableTotal += parseFloat(r.saldo || 0); });
    if (metaContable) metaContable.textContent = fmtMoney(contableTotal);
    fetch(`/api/financial/treasury/cartera_importe_codes?empresa=${empresa}&ejercicio=${ejercicio}&codes=${encodeURIComponent(codes)}`)
        .then(r => r.json())
        .then(json => {
            const map = json && json.map ? json.map : {};
            let carteraTotal = 0.0;
            document.querySelectorAll('#treasury-tbody tr').forEach(tr => {
                const code = tr.getAttribute('data-code');
                const val = parseFloat(map[code] || 0);
                carteraTotal += val;
                const td = tr.querySelector('.cartera-val');
                if (td) td.textContent = fmtMoney(val);
                const saldoText = tr.children[2]?.textContent || '0';
                const saldoNum = Number(saldoText.replace(/\./g,'').replace(',', '.').replace(/[^\d.-]/g,'')) || 0;
                const diff = saldoNum - val;
                const tdDiff = tr.querySelector('.dif-val');
                if (tdDiff) tdDiff.textContent = fmtMoney(diff);
            });
            if (metaCartera) metaCartera.textContent = fmtMoney(carteraTotal);
            if (metaDiff) metaDiff.textContent = fmtMoney(contableTotal - carteraTotal);
        })
        .catch(() => {
            // Leave placeholders
        })
        .finally(() => {
            if (loading) loading.style.display = 'none';
            if (table) table.style.display = 'table';
        });
}

function loadReceivablesBreakdownInitial(empresa, ejercicio) {
    const loading = document.getElementById('treasury-loading');
    const table = document.getElementById('treasury-table');
    if (loading) loading.style.display = 'block';
    if (table) table.style.display = 'none';
    fetch(`/api/financial/treasury/receivables_breakdown?empresa=${empresa}&ejercicio=${ejercicio}&level=3`)
        .then(r => r.json())
        .then(json => populateReceivablesTable(Array.isArray(json.rows) ? json.rows : [], empresa, ejercicio))
        .catch(e => {
            if (loading) loading.textContent = 'Error al cargar detalle';
            console.error("Receivables breakdown error", e);
        });
}

function loadReceivablesBreakdownDetail(empresa, ejercicio, parent, level) {
    const loading = document.getElementById('treasury-loading');
    const table = document.getElementById('treasury-table');
    if (loading) loading.style.display = 'block';
    if (table) table.style.display = 'none';
    fetch(`/api/financial/treasury/receivables_breakdown_detail?empresa=${empresa}&ejercicio=${ejercicio}&parent=${encodeURIComponent(parent)}&level=${level}`)
        .then(r => r.json())
        .then(json => populateReceivablesTable(Array.isArray(json.rows) ? json.rows : [], empresa, ejercicio))
        .catch(e => {
            if (loading) loading.textContent = 'Error al cargar subcuentas';
            console.error("Receivables breakdown detail error", e);
        });
}

function loadReceivablesBreakdownFlat(empresa, ejercicio, parent) {
    const loading = document.getElementById('treasury-loading');
    const table = document.getElementById('treasury-table');
    if (loading) loading.style.display = 'block';
    if (table) table.style.display = 'none';
    fetch(`/api/financial/treasury/receivables_breakdown_flat?empresa=${empresa}&ejercicio=${ejercicio}&parent=${encodeURIComponent(parent)}`)
        .then(r => r.json())
        .then(json => populateReceivablesTable(Array.isArray(json.rows) ? json.rows : [], empresa, ejercicio))
        .catch(e => {
            if (loading) loading.textContent = 'Error al cargar desglose máximo';
            console.error("Receivables breakdown flat error", e);
        });
}
document.addEventListener('DOMContentLoaded', () => {
    const card = document.getElementById('card-pendiente-cobro');
    if (card) {
        card.addEventListener('click', openReceivablesBreakdownModal);
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                openReceivablesBreakdownModal();
            }
        });
    }
    const mark = document.getElementById('mark-pendiente-cobro');
    if (mark) {
        mark.addEventListener('click', (e) => {
            e.stopPropagation();
            openReceivablesBreakdownModal();
        });
        mark.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                openReceivablesBreakdownModal();
            }
        });
    }
});

function renderTesoreriaCharts(charts) {
    if (!charts) return;

    // 1. Clients
    renderBarChartTesoreria('chart-tesoreria-clientes', charts.top_clients, '#3b82f6');

    // 2. Suppliers
    renderBarChartTesoreria('chart-tesoreria-proveedores', charts.top_suppliers, '#ef4444');

    // 3. Banks
    const banks = Array.isArray(charts.banks) ? charts.banks.filter(it => {
        const code = String(it.code || '').trim();
        const val = Math.round(Number(it.value) || 0);
        return code.startsWith('572') && val !== 0;
    }) : [];
    renderBarChartTesoreria('chart-tesoreria-bancos', banks, '#10b981');
}

function renderBarChartTesoreria(domId, dataList, color) {
    const chartDom = document.getElementById(domId);
    if (!chartDom) return;

    if (!Array.isArray(dataList) || dataList.length === 0) {
        const inst = window.echarts ? echarts.getInstanceByDom(chartDom) : null;
        if (inst) inst.dispose();
        chartDom.innerText = 'Sin datos';
        return;
    }
    const myChart = echarts.init(chartDom);

    const names = dataList.map(item => item.name);
    const values = dataList.map(item => item.value);

    const option = {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: names, axisLabel: { rotate: 45, interval: 0, fontSize: 10, width: 90, overflow: 'truncate' } },
        yAxis: { type: 'value' },
        series: [{
            data: values,
            type: 'bar',
            itemStyle: { color: color }
        }]
    };
    myChart.setOption(option);

    // Resize observer
    new ResizeObserver(() => myChart.resize()).observe(chartDom);
}

async function renderTesoreriaEvolution(empresa, ejercicio) {
    // Fetch Monthly KPIs for Line Chart
    try {
        const response = await fetch(`/api/financial/monthly_kpis?empresa=${empresa}&ejercicio=${ejercicio}`);
        const data = await response.json();

        const chartDom = document.getElementById('chart-tesoreria-evolucion');
        if (!chartDom) return;
        const myChart = echarts.init(chartDom);

        const option = {
            tooltip: { trigger: 'axis' },
            legend: { data: ['Ingresos', 'Gastos'] },
            grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
            xAxis: { type: 'category', data: data.labels },
            yAxis: { type: 'value' },
            series: [
                { name: 'Ingresos', type: 'line', data: data.ingresos, smooth: true, itemStyle: { color: '#3b82f6' } },
                { name: 'Gastos', type: 'line', data: data.gastos, smooth: true, itemStyle: { color: '#ef4444' } }
            ]
        };
        myChart.setOption(option);
        new ResizeObserver(() => myChart.resize()).observe(chartDom);

    } catch (e) {
        console.error("Error evolution", e);
    }
}

async function loadTesoreriaForecast(empresa, ejercicio) {
    try {
        const q = `?empresa=${empresa}&ejercicio=${ejercicio}`;
        const res = await fetch(`/api/financial/treasury/forecast${q}`);
        if (!res.ok) return;
        const json = await res.json();
        renderTesoreriaForecast(json);
    } catch (e) {
        console.error("Error forecast", e);
    }
}

function renderTesoreriaForecast(data) {
    const dom = document.getElementById('tes-chart-forecast');
    if (!dom) return;
    const noData = (!data || !Array.isArray(data.forecast) || data.forecast.length === 0 || data.forecast.every(x => !x || (((x.inflow || 0) === 0) && ((x.outflow || 0) === 0) && ((x.balance || 0) === 0))));
    if (noData) {
        const emp = document.getElementById('sel-empresa')?.value || currEmpresa;
        const eje = document.getElementById('sel-ejercicio')?.value || currEjercicio;
        fetch(`/api/financial/treasury?empresa=${emp}&ejercicio=${eje}`).then(r => r.ok ? r.json() : null).then(snap => {
            const cash = (snap && snap.kpis && typeof snap.kpis.cash === 'number') ? snap.kpis.cash : (typeof snap?.cash === 'number' ? snap.cash : 0);
            if (cash > 0) {
                let chart = echarts.getInstanceByDom(dom);
                if (chart) chart.dispose();
                chart = echarts.init(dom, null, { renderer: 'svg' });
                const labels = Array.from({ length: 6 }).map((_, i) => `Mes ${i + 1}`);
                const zero = Array(labels.length).fill(0);
                const bal = Array(labels.length).fill(cash);
                chart.setOption({
                    backgroundColor: 'transparent',
                    legend: { textStyle: { color: '#9ca3af' }, top: 0 },
                    grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
                    xAxis: { type: 'category', data: labels, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
                    yAxis: [{ type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151', type: 'dashed' } } }, { type: 'value', axisLabel: { color: '#3b82f6' }, splitLine: { show: false } }],
                    series: [
                        { name: 'Cobros', type: 'bar', stack: 'flow', data: zero, itemStyle: { color: '#10b981' } },
                        { name: 'Pagos', type: 'bar', stack: 'flow', data: zero, itemStyle: { color: '#ef4444' } },
                        { name: 'Saldo Proyectado', type: 'line', yAxisIndex: 1, data: bal, itemStyle: { color: '#3b82f6' }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6 }
                    ]
                });
                new ResizeObserver(() => chart.resize()).observe(dom);
            } else {
                dom.innerText = 'Sin datos';
            }
        }).catch(() => { dom.innerText = 'Sin datos'; });
        return;
    }
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });
    const labels = data.forecast.map(x => x.period);
    const inflows = data.forecast.map(x => x.inflow || 0);
    const outflows = data.forecast.map(x => x.outflow || 0);
    const balance = data.forecast.map(x => x.balance || 0);
    chart.setOption({
        backgroundColor: 'transparent',
        legend: { data: ['Cobros', 'Pagos', 'Saldo Proyectado'], textStyle: { color: '#9ca3af' }, top: 0 },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '15%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { color: '#9ca3af' }, axisLine: { lineStyle: { color: '#374151' } } },
        yAxis: [{ type: 'value', axisLabel: { color: '#9ca3af' }, splitLine: { lineStyle: { color: '#374151', type: 'dashed' } } }, { type: 'value', axisLabel: { color: '#3b82f6' }, splitLine: { show: false } }],
        series: [
            { name: 'Cobros', type: 'bar', stack: 'flow', data: inflows, itemStyle: { color: '#10b981' } },
            { name: 'Pagos', type: 'bar', stack: 'flow', data: outflows, itemStyle: { color: '#ef4444' } },
            { name: 'Saldo Proyectado', type: 'line', yAxisIndex: 1, data: balance, itemStyle: { color: '#3b82f6' }, lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6 }
        ]
    });
    new ResizeObserver(() => chart.resize()).observe(dom);
}
// Attach to Global Scope or Init
window.loadTesoreriaData = loadTesoreriaData;

/* Event Listener for Tab Switching */
document.addEventListener('datia:subtab-change', (e) => {
    if (e.detail && e.detail.subTabId === 'sub-tesoreria') {
        loadTesoreriaData();
        // Resize Charts after visible
        setTimeout(() => {
            const charts = ['chart-tesoreria-clientes', 'chart-tesoreria-proveedores', 'chart-tesoreria-bancos', 'chart-tesoreria-evolucion'];
            if (window.echarts) {
                charts.forEach(id => {
                    const dom = document.getElementById(id);
                    if (dom) {
                        const inst = echarts.getInstanceByDom(dom);
                        if (inst) inst.resize();
                    }
                });
            }
        }, 300);
    }
});
