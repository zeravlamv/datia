let isLoadingPool = false;
let poolBanks = [];
let poolInstruments = [];
function getSelectedFilters() {
    const selBank = document.getElementById('pool-bank');
    const selTipo = document.getElementById('pool-tipo');
    const bankId = selBank && selBank.value ? parseInt(selBank.value) : null;
    const tipo = selTipo && selTipo.value ? selTipo.value : null;
    return { bankId, tipo };
}
function computeFilteredFromSummary(summary, bankId, tipo) {
    const items = (summary && summary.items) ? summary.items : [];
    const filtered = items.filter(it => {
        if (bankId && it.bank_id !== bankId) return false;
        if (tipo && it.tipo !== tipo) return false;
        return true;
    });
    let total_limite = 0, total_dispuesto = 0;
    const byBankMap = {};
    for (const it of filtered) {
        total_limite += Number(it.limite || 0);
        total_dispuesto += Number(it.dispuesto || 0);
        const k = it.bank_id || 0;
        if (!byBankMap[k]) byBankMap[k] = { bank_id: k, bank: it.bank || '', limite: 0, dispuesto: 0 };
        byBankMap[k].limite += Number(it.limite || 0);
        byBankMap[k].dispuesto += Number(it.dispuesto || 0);
    }
    const banks = Object.values(byBankMap).map(b => {
        const disponible = Math.max(b.limite - b.dispuesto, 0);
        const up = b.limite > 0 ? Math.round((b.dispuesto / b.limite) * 10000) / 100 : 0;
        return { ...b, disponible, utilizacion_pct: up };
    });
    const total_disponible = Math.max(total_limite - total_dispuesto, 0);
    return {
        totals: {
            limite: Math.round(total_limite * 100) / 100,
            dispuesto: Math.round(total_dispuesto * 100) / 100,
            disponible: Math.round(total_disponible * 100) / 100,
            utilizacion_pct: total_limite > 0 ? Math.round((total_dispuesto / total_limite) * 10000) / 100 : 0
        },
        banks
    };
}
function filterMaturities(d, bankId, tipo) {
    if (!d) return { series: [], detalles: [] };
    const details = d.detalles || [];
    if (!bankId && !tipo) return d;
    const allowed = new Set();
    for (const it of poolInstruments) {
        if (bankId && it.bank_id !== bankId) continue;
        if (tipo && it.tipo !== tipo) continue;
        allowed.add(it.id);
    }
    const buckets = {};
    for (const row of details) {
        if (!allowed.has(row.instrument_id)) continue;
        const ym = row.fecha.slice(0, 7);
        if (!buckets[ym]) buckets[ym] = 0;
        buckets[ym] += Number(row.cuota || 0);
    }
    const series = Object.keys(buckets).sort().map(k => ({ periodo: k, cuota: Math.round(buckets[k] * 100) / 100 }));
    return { series, detalles: details };
}
async function loadPoolFilters() {
    try {
        const kBank = 'datia-pool-bank';
        const kTipo = 'datia-pool-tipo';
        const resB = await fetch(`/api/financial/pool/banks?empresa=${currEmpresa}`);
        if (resB.ok) {
            poolBanks = await resB.json();
            const sel = document.getElementById('pool-bank');
            if (sel) {
                const prev = localStorage.getItem(kBank) || '';
                sel.innerHTML = '';
                const optAll = document.createElement('option'); optAll.value = ''; optAll.textContent = '-- Todos --'; sel.appendChild(optAll);
                for (const b of poolBanks) {
                    const o = document.createElement('option');
                    o.value = String(b.id);
                    o.textContent = b.nombre || ('Bank ' + b.id);
                    sel.appendChild(o);
                }
                sel.value = prev;
                sel.addEventListener('change', function () {
                    localStorage.setItem(kBank, sel.value || '');
                    try {
                        fetch('/api/financial/pool/preferences', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '' },
                            body: JSON.stringify({ default_bank_id: sel.value ? parseInt(sel.value) : null })
                        }).catch(()=>{});
                    } catch (_) {}
                    loadPoolBancario(true);
                    loadPoolAccounts();
                });
            }
        }
        const resI = await fetch(`/api/financial/pool/instruments?empresa=${currEmpresa}`);
        if (resI.ok) {
            const lst = await resI.json();
            poolInstruments = lst.map(x => ({ id: x.id, bank_id: x.bank_id, tipo: x.tipo }));
            const tipos = Array.from(new Set(lst.map(x => x.tipo).filter(Boolean))).sort();
            const selT = document.getElementById('pool-tipo');
            if (selT) {
                const prevT = localStorage.getItem(kTipo) || '';
                selT.innerHTML = '';
                const optAllT = document.createElement('option'); optAllT.value = ''; optAllT.textContent = '-- Todos --'; selT.appendChild(optAllT);
                for (const t of tipos) {
                    const o = document.createElement('option');
                    o.value = t;
                    o.textContent = t;
                    selT.appendChild(o);
                }
                selT.value = prevT;
                selT.addEventListener('change', function () {
                    localStorage.setItem(kTipo, selT.value || '');
                    try {
                        fetch('/api/financial/pool/preferences', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '' },
                            body: JSON.stringify({ default_tipo: selT.value || null })
                        }).catch(()=>{});
                    } catch (_) {}
                    loadPoolBancario(true);
                });
            }
        }
        try {
            const resPref = await fetch('/api/financial/pool/preferences');
            if (resPref.ok) {
                const p = await resPref.json();
                const selB = document.getElementById('pool-bank');
                const selT2 = document.getElementById('pool-tipo');
                if (p && selB && p.default_bank_id) {
                    selB.value = String(p.default_bank_id);
                    localStorage.setItem(kBank, selB.value || '');
                }
                if (p && selT2 && p.default_tipo) {
                    selT2.value = p.default_tipo;
                    localStorage.setItem(kTipo, selT2.value || '');
                }
            }
        } catch (_) {}
        loadPoolAccounts();
    } catch (e) {
        console.error('Pool filters error', e);
    }
}
async function loadPoolBancario(force = false) {
    if (isLoadingPool && !force) return;
    isLoadingPool = true;
    try {
        const hastaSel = document.getElementById('pool-hasta-mes');
        const hastaVal = hastaSel && hastaSel.value ? `&hasta_mes=${encodeURIComponent(hastaSel.value)}` : '';
        const q = `?empresa=${currEmpresa}&ejercicio=${currEjercicio}${hastaVal}`;
        const res = await fetch(`/api/financial/pool/summary${q}`);
        if (res.ok) {
            const data = await res.json();
            window.cachedPoolSummary = data;
            const { bankId, tipo } = getSelectedFilters();
            const f = computeFilteredFromSummary(data, bankId, tipo);
            renderPoolSummary({ totales: f.totals });
            renderPoolConcentration({ banks: f.banks });
        }
        const resM = await fetch(`/api/financial/pool/maturities?empresa=${currEmpresa}&horizon=12`);
        if (resM.ok) {
            const data = await resM.json();
            const { bankId, tipo } = getSelectedFilters();
            const filtered = filterMaturities(data, bankId, tipo);
            renderPoolMaturities(filtered);
        }
    } catch (e) {
        console.error("Pool Bancario error:", e);
        showToast(typeof gettext === 'function' ? gettext('Error cargando Pool Bancario') : 'Error cargando Pool Bancario', true);
    } finally {
        isLoadingPool = false;
    }
}
function renderPoolSummary(d) {
    if (!d || !d.totales) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const t = d.totales;
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('pool-kpi-limite', nf.format(t.limite) + ' €');
    set('pool-kpi-dispuesto', nf.format(t.dispuesto) + ' €');
    set('pool-kpi-disponible', nf.format(t.disponible) + ' €');
    set('pool-kpi-utilizacion', (typeof t.utilizacion_pct === 'number' ? t.utilizacion_pct.toFixed(2) : '--') + ' %');
}
function renderPoolConcentration(d) {
    const dom = document.getElementById('pool-concentration-chart');
    if (!dom || !d || !d.banks) return;
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });
    const labels = d.banks.map(x => x.bank || ('Bank ' + x.bank_id));
    const limites = d.banks.map(x => Number(x.limite || 0));
    const utilizados = d.banks.map(x => Number(x.dispuesto || 0));
    const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        legend: { data: ['Límite', 'Dispuesto'], top: 10, textStyle: { color: '#e4e4e7' } },
        grid: { left: '6%', right: '6%', bottom: '6%', top: 50, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { color: '#a1a1aa' }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#27272a' } } },
        yAxis: { type: 'value', axisLabel: { color: '#a1a1aa' }, splitLine: { lineStyle: { color: '#27272a' } } },
        series: [
            { name: 'Límite', type: 'bar', data: limites, itemStyle: { color: '#3b82f6' }, barMaxWidth: 28 },
            { name: 'Dispuesto', type: 'bar', data: utilizados, itemStyle: { color: '#ef4444' }, barMaxWidth: 28 }
        ]
    };
    chart.setOption(option);
    if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
}
function renderPoolMaturities(d) {
    const dom = document.getElementById('pool-maturities-chart');
    if (!dom || !d || !d.series) return;
    let chart = echarts.getInstanceByDom(dom);
    if (chart) chart.dispose();
    chart = echarts.init(dom, null, { renderer: 'svg' });
    const labels = d.series.map(x => x.periodo);
    const cuotas = d.series.map(x => Number(x.cuota || 0));
    const option = {
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis' },
        grid: { left: '6%', right: '6%', bottom: '6%', top: 40, containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { color: '#a1a1aa' }, axisTick: { show: false }, axisLine: { lineStyle: { color: '#27272a' } } },
        yAxis: { type: 'value', axisLabel: { color: '#a1a1aa' }, splitLine: { lineStyle: { color: '#27272a' } } },
        series: [{ name: 'Cuota', type: 'line', data: cuotas, smooth: true, lineStyle: { width: 3, color: '#10b981' }, showSymbol: false }]
    };
    chart.setOption(option);
    if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
}
async function loadPoolAccounts() {
    const { bankId } = getSelectedFilters();
    const box = document.getElementById('pool-accounts-list');
    if (!box) return;
    if (!bankId) {
        box.innerHTML = '';
        return;
    }
    const res = await fetch(`/api/financial/pool/accounts?empresa=${currEmpresa}&bank_id=${bankId}`);
    if (!res.ok) {
        box.innerHTML = '';
        return;
    }
    const rows = await res.json();
    renderPoolAccounts(rows);
}
function renderPoolAccounts(rows) {
    const box = document.getElementById('pool-accounts-list');
    if (!box) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES');
    let html = '<table><thead><tr><th>IBAN</th><th>Alias</th><th>Uso</th><th>Activo</th><th></th></tr></thead><tbody>';
    for (const r of rows) {
        const activeText = r.activo ? 'Sí' : 'No';
        html += `<tr data-id="${r.id}" data-bank="${r.bank_id}" data-iban="${r.iban}" data-alias="${r.alias || ''}" data-uso="${r.uso || ''}" data-activo="${r.activo ? '1' : '0'}">
            <td>${r.iban}</td>
            <td>${r.alias || ''}</td>
            <td>${r.uso || ''}</td>
            <td>${activeText}</td>
            <td style="text-align:right; display:flex; gap:6px; justify-content:flex-end;">
                <button class="btn-contrast-outline acc-toggle">${r.activo ? 'Desactivar' : 'Activar'}</button>
                <button class="btn-danger acc-del">Eliminar</button>
            </td>
        </tr>`;
    }
    html += '</tbody></table>';
    box.innerHTML = html;
}
async function createPoolAccount() {
    const { bankId } = getSelectedFilters();
    const iban = document.getElementById('pool-acc-iban');
    const alias = document.getElementById('pool-acc-alias');
    const uso = document.getElementById('pool-acc-uso');
    const activo = document.getElementById('pool-acc-activo');
    if (!bankId || !iban || !alias || !uso || !activo) return;
    const payload = {
        bank_id: bankId,
        iban: iban.value.trim(),
        alias: alias.value.trim(),
        uso: uso.value.trim(),
        activo: !!activo.checked
    };
    if (!payload.iban) return;
    await fetch(`/api/financial/pool/accounts?empresa=${currEmpresa}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '' },
        body: JSON.stringify(payload)
    });
    iban.value = '';
    alias.value = '';
    uso.value = '';
    activo.checked = true;
    loadPoolAccounts();
}
async function togglePoolAccount(row) {
    const id = parseInt(row.getAttribute('data-id'));
    const bank_id = parseInt(row.getAttribute('data-bank'));
    const iban = row.getAttribute('data-iban') || '';
    const alias = row.getAttribute('data-alias') || '';
    const uso = row.getAttribute('data-uso') || '';
    const activo = row.getAttribute('data-activo') === '1' ? false : true;
    const payload = { bank_id, iban, alias, uso, activo };
    await fetch(`/api/financial/pool/accounts/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '' },
        body: JSON.stringify(payload)
    });
    loadPoolAccounts();
}
async function deletePoolAccount(row) {
    const id = parseInt(row.getAttribute('data-id'));
    await fetch(`/api/financial/pool/accounts/${id}`, {
        method: 'DELETE',
        headers: { 'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '' }
    });
    loadPoolAccounts();
}
document.addEventListener('DOMContentLoaded', function () {
    const tab = document.getElementById('sub-pool');
    if (tab) {
        const observer = new MutationObserver(() => {
            if (tab.style.display !== 'none') loadPoolBancario();
        });
        observer.observe(tab, { attributes: true, attributeFilter: ['style'] });
    }
    const sel = document.getElementById('pool-hasta-mes');
    if (sel) {
        const k = 'datia-pool-hasta-mes';
        const val = localStorage.getItem(k) || '';
        sel.value = val;
        sel.addEventListener('change', function () {
            localStorage.setItem(k, sel.value || '');
            loadPoolBancario(true);
        });
    }
    loadPoolFilters();
    const btnAdd = document.getElementById('pool-acc-add');
    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            createPoolAccount();
        });
    }
    const list = document.getElementById('pool-accounts-list');
    if (list) {
        list.addEventListener('click', function (e) {
            const t = e.target;
            if (!t) return;
            const row = t.closest('tr');
            if (!row) return;
            if (t.classList.contains('acc-toggle')) {
                togglePoolAccount(row);
            } else if (t.classList.contains('acc-del')) {
                deletePoolAccount(row);
            }
        });
    }
});
document.addEventListener('datia:empresa-change', function () { loadPoolFilters(); loadPoolBancario(true); loadPoolAccounts(); });
document.addEventListener('datia:ejercicio-change', function () { loadPoolBancario(true); });
