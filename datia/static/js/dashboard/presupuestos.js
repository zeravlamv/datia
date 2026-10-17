console.log("Presupuestos JS Loaded");
if (typeof window.budgetViewMode === 'undefined') window.budgetViewMode = 'grid';

// Internal State
let budgetState = {
    originalData: [], // To track changes? Or just track dirty cells.
    dirtyCells: new Set(), // Store IDs of changed cells "row-col"
    cacheParams: null,
    dirtyTotals: new Set(),
    pendingMonthValues: {}, // code -> [0, m1..m12]
    selectedYears: { baseYear: null, budgetYear: null },
    notes: {},
    dirtyNotes: new Set()
};

function ensureYearDefaults() {
    const baseInp = document.getElementById('budget-base-year');
    const budInp = document.getElementById('budget-target-year');
    const selEje = document.getElementById('sel-ejercicio');
    let curr = NaN;
    if (selEje && selEje.value && /^\d+$/.test(selEje.value)) {
        curr = parseInt(selEje.value, 10);
    } else if (typeof currEjercicio !== 'undefined' && currEjercicio && !isNaN(parseInt(currEjercicio, 10))) {
        curr = parseInt(currEjercicio, 10);
    } else {
        curr = new Date().getFullYear();
    }
    if (baseInp) baseInp.value = curr;
    if (budInp) budInp.value = curr + 1;
}

function getSelectedYears() {
    const baseInp = document.getElementById('budget-base-year');
    const budInp = document.getElementById('budget-target-year');
    const selEje = document.getElementById('sel-ejercicio');
    const curr = parseInt((selEje && selEje.value) ? selEje.value : (typeof currEjercicio !== 'undefined' ? currEjercicio : new Date().getFullYear()));
    let budgetYear = budInp ? parseInt(budInp.value || (curr + 1)) : (curr + 1);
    let baseYear = baseInp ? parseInt(baseInp.value || curr) : curr;
    if (isNaN(budgetYear) || budgetYear < 1900 || budgetYear > 2100) budgetYear = curr + 1;
    if (isNaN(baseYear) || baseYear < 1900 || baseYear > 2100) baseYear = curr;
    budgetState.selectedYears = { baseYear, budgetYear };
    return { baseYear, budgetYear };
}

function _getPctRaw() {
    const el = document.getElementById('budget-adjust-pct');
    return el ? String(el.value || '').trim() : '';
}

function _parsePct(raw) {
    if (!raw) return NaN;
    const norm = raw.replace(',', '.');
    const val = parseFloat(norm);
    if (isNaN(val)) return NaN;
    const parts = norm.split('.');
    if (parts[1] && parts[1].length > 2) return NaN;
    if (val < -100 || val > 100) return NaN;
    return val;
}

function getAdjustmentFactor() {
    const v = _parsePct(_getPctRaw());
    if (isNaN(v)) return NaN;
    return 1 + (v / 100.0);
}

async function checkBudgetExists(empresa, ejercicio) {
    try {
        const res = await fetch(`/api/financial/budgets/exists?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(ejercicio)}`);
        if (!res.ok) return { exists: false, count: 0 };
        return await res.json();
    } catch (e) {
        return { exists: false, count: 0 };
    }
}

async function generateServerBudget(empresa, ejercicio, base_year, pct) {
    const res = await fetch('/api/financial/budgets/generate', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            empresa: empresa,
            ejercicio: ejercicio,
            base_year: base_year,
            increment_pct: pct
        })
    });
    if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || 'Error HTTP');
    }
    const j = await res.json();
    if (j.status !== 'ok') {
        throw new Error(j.message || 'Error');
    }
    return j;
}
function updateGenerateButtonState() {
    const btn = document.getElementById('btn-budget-generate');
    const inp = document.getElementById('budget-adjust-pct');
    const ok = !isNaN(_parsePct(_getPctRaw()));
    if (btn) btn.disabled = false;
    if (inp) inp.setAttribute('aria-invalid', ok ? 'false' : 'true');
}

document.addEventListener('DOMContentLoaded', () => {
    ensureYearDefaults();
    updateGenerateButtonState();
    const inp = document.getElementById('budget-adjust-pct');
    if (inp) inp.addEventListener('input', updateGenerateButtonState);
    // Auto-load handled by core.js or user interaction
    // try {
    //    loadBudgetComparison();
    // } catch (e) {
    //    console.warn("Init load failed", e);
    // }
});
async function loadPresupuestos(mode = 'reload') {
    console.log("loadPresupuestos() called");

    const container = document.getElementById('budget-grid-container');
    if (!container) return;

    container.innerHTML = `<div class="loading-spinner"></div> Loading...`;
    const tree = document.getElementById('budget-tree-container');
    const comp = document.getElementById('budget-comparison-container');
    if (tree) {
        tree.style.display = 'none';
        tree.innerHTML = '';
    }
    if (comp) {
        comp.style.display = 'none';
        comp.innerHTML = '';
    }
    container.style.display = 'block';
    window.budgetViewMode = 'grid';

    ensureYearDefaults();
    const { baseYear, budgetYear } = getSelectedYears();
    const q = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(budgetYear)}&base_year=${encodeURIComponent(baseYear)}&group_filter=PL`;
    try {
        const factor = getAdjustmentFactor();
        const pctVal = _parsePct(_getPctRaw());
        const exists = await checkBudgetExists(currEmpresa, budgetYear);
        if (mode === 'generate') {
            if (isNaN(factor)) {
                if (exists && exists.exists) {
                    const res0 = await fetch(`/api/financial/budgets${q}`);
                    if (!res0.ok) throw new Error("Failed to fetch budgets");
                    const data0 = await res0.json();
                    renderBudgetGrid(data0, NaN);
                } else {
                    showToast(`No existe presupuesto para ${budgetYear}. Indique un porcentaje para generarlo.`, "error");
                    container.innerHTML = `<div style="text-align:center; color:#ef4444;">Sin presupuesto para ${budgetYear}</div>`;
                }
                return;
            }
            if (exists && exists.exists) {
                showBudgetReplaceConfirm(budgetYear, async (action) => {
                    if (action === 'replace') {
                        try {
                            const gen = await generateServerBudget(currEmpresa, budgetYear, baseYear, isNaN(pctVal) ? 0 : pctVal);
                            showToast(`Presupuesto generado (${gen.generated_records})`, "success");
                        } catch (e) {
                            showToast("Error generando presupuesto: " + (e.message || e), "error");
                        }
                    }
                    hideBudgetReplaceConfirm();
                    const res2 = await fetch(`/api/financial/budgets${q}`);
                    if (!res2.ok) throw new Error("Failed to fetch budgets");
                    const data2 = await res2.json();
                    renderBudgetGrid(data2, factor);
                });
                return;
            } else {
                try {
                    const gen = await generateServerBudget(currEmpresa, budgetYear, baseYear, isNaN(pctVal) ? 0 : pctVal);
                    showToast(`Presupuesto generado (${gen.generated_records})`, "success");
                } catch (e) {
                    showToast("Error generando presupuesto: " + (e.message || e), "error");
                }
            }
        } else {
            hideBudgetReplaceConfirm();
        }
        const res = await fetch(`/api/financial/budgets${q}`);
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status === 'error') {
            throw new Error(data.message || 'No se ha podido leer el presupuesto');
        }
        renderBudgetGrid(data, factor);

    } catch (e) {
        console.error("Budget Load Error", e);
        const detail = String(e.message || '').replace(/<[^>]+>/g, '').slice(0, 180);
        container.innerHTML = `<div style="text-align:center; color:#fca5a5; padding:28px;">No se ha podido cargar la entrada de presupuestos.<br><span style="color:#a1a1aa; font-size:0.85rem;">${detail}</span></div>`;
    }
}

function renderBudgetGrid(data, factor) {
    const container = document.getElementById('budget-grid-container');
    if (!container) return;

    budgetState.dirtyCells.clear();
    budgetState.dirtyTotals.clear();
    budgetState.pendingMonthValues = {};
    budgetState.controls = {};
    budgetState.dirtyControls = new Set();
    const rows = (data && Array.isArray(data.rows)) ? data.rows : [];
    budgetState.originalData = rows || [];

    const monthsHdr = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0, useGrouping: true });
    const baseYear = data && data.meta ? data.meta.base_year : (parseInt(currEjercicio) - 1);
    const budgetYear = data && data.meta ? data.meta.budget_year : parseInt(currEjercicio);

    let html = `
    <table class="budget-table">
        <thead>
            <tr>
                <th class="col-code">Cuenta</th>
                <th class="col-type">Tipo</th>
                <th class="col-desc">Descripción</th>
                <th class="col-total">Total</th>
                ${monthsHdr.map(m => `<th class="col-month">${m}</th>`).join('')}
            </tr>
        </thead>
        <tbody>
    `;

    if (!rows || rows.length === 0) {
        html += `<tr><td colspan="${3 + monthsHdr.length + 1}" style="text-align:center; padding:20px; color:#a1a1aa;">Sin cuentas disponibles (Revisa tu Plan de Cuentas)</td></tr>`;
    } else {
        rows.forEach(row => {
            const baseMonths = Array.isArray(row.base?.months) ? row.base.months : new Array(12).fill(0);
            let budMonths = Array.isArray(row.presupuesto?.months) ? row.presupuesto.months : new Array(12).fill(0);
            const baseTotal = typeof row.base?.total === 'number' ? row.base.total : 0;
            let budTotal = typeof row.presupuesto?.total === 'number' ? row.presupuesto.total : 0;
            const budSum = budMonths.reduce((a, b) => a + (parseFloat(b) || 0), 0);
            const baseSum = baseMonths.reduce((a, b) => a + (parseFloat(b) || 0), 0);
            if (budSum === 0 && baseSum !== 0 && !isNaN(factor)) {
                budMonths = baseMonths.map(v => Math.round((parseFloat(v) || 0) * factor));
                budTotal = budMonths.reduce((a, b) => a + (parseFloat(b) || 0), 0);
            }

            const trBase = `
            <tr class="budget-row-base">
                <td class="col-code">${row.cuenta}</td>
                <td class="col-type">Base ${baseYear}</td>
                <td class="col-desc">${row.descripcion}</td>
                <td class="col-total">${baseTotal !== 0 ? nf.format(Math.round(baseTotal)) : '-'}</td>
                ${baseMonths.map((val) => `
                    <td class="col-month">${((parseFloat(val) || 0) !== 0) ? nf.format(Math.round(parseFloat(val) || 0)) : '-'}</td>
                `).join('')}
            </tr>`;

            const cfg = (row.presupuesto && row.presupuesto.config) ? row.presupuesto.config : {};
            const hasAugBase = ((parseFloat(baseMonths[7]) || 0) !== 0);
            const agostoFull = (cfg.agosto_full === true) ? true : hasAugBase;
            const linePct = (cfg.line_pct != null) ? (parseFloat(cfg.line_pct) || 0) : 0;
            budgetState.controls[row.cuenta] = { agosto_full: agostoFull, line_pct: linePct };
            const trBud = `
            <tr class="budget-row-presupuesto">
                <td class="col-code">&nbsp;</td>
                <td class="col-type">Presupuesto ${budgetYear}</td>
                <td class="col-desc">
                    <div class="budget-controls">
                        <span>${(typeof gettext === 'function' ? gettext('Agosto') : 'Agosto')}</span>
                        <input type="checkbox" class="budget-aug-check" data-code="${row.cuenta}" ${budgetState.controls[row.cuenta].agosto_full ? 'checked' : ''} onchange="onAgostoToggle(this)">
                        <span>${(typeof gettext === 'function' ? gettext('Línea %') : 'Línea %')}</span>
                        <input type="text" class="budget-line-pct" inputmode="decimal" data-code="${row.cuenta}" value="${String(budgetState.controls[row.cuenta].line_pct).replace('.', ',')}" placeholder="Ej: 5,25" onchange="onLinePctChange(this)">
                    </div>
                </td>
                <td class="col-total">
                    <input type="text"
                        class="budget-input-total"
                        data-code="${row.cuenta}"
                        value="${budTotal !== 0 ? nf.format(Math.round(budTotal)) : ''}"
                        step="any"
                        onchange="onTotalChange(this)">
                </td>
                ${budMonths.map((val, idx) => `
                    <td class="col-month">
                        <input type="text"
                            class="budget-input"
                            data-code="${row.cuenta}"
                            data-month="${idx + 1}"
                            value="${val !== 0 ? String(Math.round(val)) : ''}"
                            placeholder="-"
                            step="any"
                            onchange="markDirty(this)">
                    </td>
                `).join('')}
            </tr>`;

            html += trBase + trBud;
        });
    }

    html += `</tbody></table>`;
    const hasBudget = rows.some(row => Math.abs(Number(row.presupuesto && row.presupuesto.total) || 0) > 0.004);
    const hasBase = rows.some(row => Math.abs(Number(row.base && row.base.total) || 0) > 0.004);
    let banner = '';
    if (rows.length && !hasBudget && hasBase) {
        banner = `<div style="margin-bottom:14px; padding:12px 14px; border:1px solid rgba(96,165,250,0.35); background:rgba(59,130,246,0.08); border-radius:10px; color:#dbeafe; font-size:0.92rem;">El año ${budgetYear} todavía no tiene importes. Debajo está el año base ${baseYear}. Pulsa Generar para copiarlo con el ajuste.</div>`;
    }
    container.innerHTML = banner + html;
}

function markDirty(input) {
    input.style.backgroundColor = 'rgba(251, 191, 36, 0.1)'; // Yellow tint
    input.style.color = '#fbbf24';

    const key = `${input.dataset.code}|${input.dataset.month}`;
    // We don't store value in Set, just the fact it changed. We read value at Save time.
    input.classList.add('is-dirty');

    // Re-calc local total for UI consistency (optional but good)
    recalcRowTotal(input);
    // Formatear con miles tras cambio
    try {
        const raw = String(input.value || '').trim();
        const num = parseFormattedInt(raw);
        input.value = num ? String(num) : '';
    } catch (e) { }
}

function recalcRowTotal(changedInput) {
    const row = changedInput.closest('tr');
    if (!row) return;
    const inputs = row.querySelectorAll('input.budget-input');
    let sum = 0;
    inputs.forEach(inp => {
        const v = parseFormattedInt(inp.value);
        sum += (isNaN(v) ? 0 : v);
    });

    const totalInput = row.querySelector('.budget-input-total');
    if (totalInput) {
        totalInput.value = formatThousands(sum);
    }
}

function onTotalChange(totalInput) {
    const newTotal = parseFormattedInt(totalInput.value);
    const row = totalInput.closest('tr');
    if (!row) return;

    const code = totalInput.dataset.code;
    // Get original months to compute weights
    const original = (budgetState.originalData || []).find(r => String(r.cuenta) === String(code));
    const months = original && Array.isArray(original.presupuesto?.months) ? original.presupuesto.months : new Array(12).fill(0);
    const sum = months.reduce((a, b) => a + (parseFloat(b) || 0), 0);
    const dist = [0];
    if (sum > 0) {
        for (let i = 0; i < 12; i++) {
            const w = (parseFloat(months[i]) || 0) / sum;
            dist.push(Math.round(newTotal * w));
        }
        // Adjust rounding drift
        const drift = newTotal - dist.slice(1).reduce((a, b) => a + b, 0);
        if (drift !== 0) {
            // add drift to last month
            dist[12] = dist[12] + drift;
        }
    } else {
        const base = Math.floor(newTotal / 12);
        const rem = newTotal - (base * 12);
        for (let i = 0; i < 12; i++) dist.push(base);
        for (let i = 0; i < rem; i++) dist[12 - i] = dist[12 - i] + 1;
    }
    budgetState.pendingMonthValues[code] = dist; // 0..12, index 1..12 are months
    budgetState.dirtyTotals.add(code);
    totalInput.classList.add('is-dirty');
    totalInput.value = formatThousands(newTotal);
}

function onAgostoToggle(el) {
    const code = el.dataset.code;
    const checked = !!el.checked;
    if (!budgetState.controls[code]) budgetState.controls[code] = { agosto_full: checked, line_pct: 0 };
    budgetState.controls[code].agosto_full = checked;
    budgetState.dirtyControls.add(code);
    recalcByControls(code);
}

function onLinePctChange(el) {
    const code = el.dataset.code;
    const raw = String(el.value || '').trim();
    if (raw === '') {
        if (!budgetState.controls[code]) budgetState.controls[code] = { agosto_full: false, line_pct: null };
        budgetState.controls[code].line_pct = null;
        budgetState.dirtyControls.add(code);
        const rowBud = el.closest('tr');
        const rowBase = rowBud ? rowBud.previousElementSibling : null;
        const budInputs = rowBud ? rowBud.querySelectorAll('input.budget-input') : [];
        const baseCells = rowBase ? rowBase.querySelectorAll('td.col-month') : [];
        const dist = [0];
        let sum = 0;
        for (let i = 0; i < 12; i++) {
            const baseVal = parseFormattedInt(baseCells[i] ? baseCells[i].textContent : '');
            if (!isNaN(baseVal) && baseVal !== 0) {
                budInputs[i].value = String(baseVal);
                budInputs[i].classList.add('is-dirty');
                dist[i + 1] = baseVal;
                sum += baseVal;
            } else {
                budInputs[i].value = '';
                budInputs[i].classList.add('is-dirty');
                dist[i + 1] = 0;
            }
        }
        const totalInput = rowBud.querySelector('.budget-input-total');
        if (totalInput) {
            totalInput.value = formatThousands(sum);
            totalInput.classList.add('is-dirty');
        }
        budgetState.pendingMonthValues[code] = dist;
        budgetState.dirtyTotals.add(code);
        return;
    }
    const norm = raw.replace(',', '.');
    let pct = parseFloat(norm);
    if (isNaN(pct)) pct = 0;
    if (pct < -100 || pct > 100) {
        showToast((typeof gettext === 'function' ? gettext('Porcentaje fuera de rango (-100 a 100)') : 'Porcentaje fuera de rango (-100 a 100)'), 'error');
        pct = Math.max(-100, Math.min(100, pct));
    }
    el.value = String(pct).replace('.', ',');
    if (!budgetState.controls[code]) budgetState.controls[code] = { agosto_full: false, line_pct: 0 };
    if (pct === 0) {
        budgetState.controls[code].line_pct = 0;
        budgetState.dirtyControls.add(code);
        // Duplicar Base -> Presupuesto (neutral)
        const rowBud = el.closest('tr');
        const rowBase = rowBud ? rowBud.previousElementSibling : null;
        const budInputs = rowBud ? rowBud.querySelectorAll('input.budget-input') : [];
        const baseCells = rowBase ? rowBase.querySelectorAll('td.col-month') : [];
        const dist = [0];
        let sum = 0;
        for (let i = 0; i < 12; i++) {
            const baseVal = parseFormattedInt(baseCells[i] ? baseCells[i].textContent : '');
            if (!isNaN(baseVal) && baseVal !== 0) {
                budInputs[i].value = String(baseVal);
                budInputs[i].classList.add('is-dirty');
                dist[i + 1] = baseVal;
                sum += baseVal;
            } else {
                budInputs[i].value = '';
                budInputs[i].classList.add('is-dirty');
                dist[i + 1] = 0;
            }
        }
        const totalInput = rowBud.querySelector('.budget-input-total');
        if (totalInput) {
            totalInput.value = formatThousands(sum);
            totalInput.classList.add('is-dirty');
        }
        budgetState.pendingMonthValues[code] = dist;
        budgetState.dirtyTotals.add(code);
        return;
    }
    budgetState.controls[code].line_pct = pct;
    budgetState.dirtyControls.add(code);
    recalcByControls(code);
}

function recalcByControls(code) {
    const totalInput = document.querySelector(`.budget-input-total[data-code="${code}"]`);
    const row = totalInput ? totalInput.closest('tr') : null;
    if (!row || !totalInput) return;
    const inputs = row.querySelectorAll('input.budget-input');
    let months = [];
    inputs.forEach(inp => {
        months.push(parseFormattedInt(inp.value));
    });
    const cfg = budgetState.controls[code] || { agosto_full: false, line_pct: 0 };
    const factor = 1 + (parseFloat(cfg.line_pct || 0) / 100.0);
    months = months.map(v => Math.round((parseFloat(v) || 0) * factor));
    let total = months.reduce((a, b) => a + (parseFloat(b) || 0), 0);
    let dist = [0];
    if (cfg.agosto_full) {
        const original = (budgetState.originalData || []).find(r => String(r.cuenta) === String(code));
        const baseMonths = original && Array.isArray(original.base?.months) ? original.base.months : new Array(12).fill(0);
        const considered = [];
        for (let i = 1; i <= 12; i++) {
            const baseVal = parseFloat(baseMonths[i - 1] || 0);
            const isValid = !isNaN(baseVal) && baseVal !== 0;
            if (i === 8) {
                if (isValid) considered.push(i); // incluir agosto si base tiene valor
                // si no es válido, no incluir agosto
            } else {
                if (isValid) considered.push(i);
            }
        }
        const count = considered.length;
        // limpiar resaltado previo
        inputs.forEach(inp => inp.classList.remove('calc-included'));
        if (count === 0) {
            console.warn('BudgetCalc: sin meses base válidos para cuenta', code);
            // fallback: distribuir entre 11 meses excluyendo agosto
            const baseEven = Math.floor(total / 11);
            const remEven = total - (baseEven * 11);
            for (let i = 1; i <= 12; i++) dist[i] = (i === 8) ? 0 : baseEven;
            for (let k = 0, i = 12; k < remEven && i >= 1; i--) {
                if (i === 8) continue;
                dist[i] = dist[i] + 1;
                k++;
            }
        } else {
            const avg = Math.floor(total / count);
            const rem = total - (avg * count);
            for (let i = 1; i <= 12; i++) dist[i] = 0;
            considered.forEach(m => { dist[m] = avg; });
            // ajustar residuo al último considerado
            dist[considered[considered.length - 1]] += rem;
            // resaltar celdas consideradas
            inputs.forEach(inp => {
                const m = parseInt(inp.dataset.month, 10);
                if (considered.includes(m)) inp.classList.add('calc-included');
            });
            try {
                console.log('BudgetCalc', {
                    cuenta: code,
                    baseMonthsUsed: considered,
                    count,
                    total,
                    average: avg
                });
            } catch (e) { }
        }
    } else {
        const base = Math.floor(total / 11);
        const rem = total - (base * 11);
        for (let i = 1; i <= 12; i++) dist[i] = (i === 8) ? 0 : base;
        for (let k = 0, i = 12; k < rem && i >= 1; i--) {
            if (i === 8) continue;
            dist[i] = dist[i] + 1;
            k++;
        }
    }
    budgetState.pendingMonthValues[code] = dist;
    budgetState.dirtyTotals.add(code);
    for (let i = 0; i < inputs.length; i++) {
        inputs[i].value = String(dist[i + 1]);
        inputs[i].classList.add('is-dirty');
    }
    total = dist.slice(1).reduce((a, b) => a + b, 0);
    totalInput.value = formatThousands(total);
    totalInput.classList.add('is-dirty');
}

async function saveBudgetGrid() {
    const btn = document.querySelector('button[onclick="saveBudgetGrid()"]');
    if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Guardando...'; }
    const changes = [];
    // Include total distributions
    if (budgetState.dirtyTotals.size > 0) {
        budgetState.dirtyTotals.forEach(code => {
            const arr = budgetState.pendingMonthValues[code] || [0];
            for (let m = 1; m <= 12; m++) {
                changes.push({
                    cuenta: code,
                    period: m,
                    value: parseFloat(arr[m] || 0)
                });
            }
        });
    } else {
        // Fallback: old behavior for monthly edits (if any)
        const dirtyInputs = document.querySelectorAll('.budget-input.is-dirty');
        dirtyInputs.forEach(inp => {
            const val = parseFormattedInt(inp.value);
            changes.push({
                cuenta: inp.dataset.code,
                period: parseInt(inp.dataset.month),
                value: val
            });
        });
    }

    // [FIX] Check for ANY changes (grid, controls, or notes) before proceeding
    const hasGridChanges = changes.length > 0;
    const hasControlChanges = budgetState.dirtyControls && budgetState.dirtyControls.size > 0;
    const hasNoteChanges = budgetState.dirtyNotes && budgetState.dirtyNotes.size > 0;

    if (!hasGridChanges && !hasControlChanges && !hasNoteChanges) {
        showToast((typeof gettext === 'function' ? gettext("No hay cambios pendientes") : "No hay cambios pendientes"), "info");
        if (btn) { btn.disabled = false; btn.innerHTML = 'Guardar Cambios'; }
        return;
    }

    try {
        const res = await fetch('/api/financial/budgets/save', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                empresa: currEmpresa,
                ejercicio: (document.getElementById('budget-target-year')?.value ? parseInt(document.getElementById('budget-target-year').value) : parseInt(currEjercicio)),
                changes: changes,
                controls: Array.from(budgetState.dirtyControls || new Set()).map(code => ({
                    cuenta: code,
                    agosto_full: !!(budgetState.controls[code] && budgetState.controls[code].agosto_full),
                    line_pct: parseFloat(budgetState.controls[code] && budgetState.controls[code].line_pct || 0)
                })),
                notes: Array.from(budgetState.dirtyNotes || new Set()).map(key => {
                    const [code, period] = String(key).split('|');
                    const p = parseInt(period);
                    const text = budgetState.notes[code] && budgetState.notes[code][p] ? String(budgetState.notes[code][p]) : '';
                    return { cuenta: code, period: p, text: text };
                })
            })
        });

        if (!res.ok) {
            const msg = await res.text();
            showToast("Error HTTP " + res.status + ": " + msg, "error");
            return;
        }
        const json = await res.json();

        if (json.status === 'ok') {
            showToast(`Guardados ${json.saved_cells} registros`, "success");
            if (json.saved_notes && json.saved_notes > 0) {
                showToast(`Guardadas ${json.saved_notes} notas`, "success");
            }
            // Reload to refresh totals and clean dirty state
            if (window.budgetViewMode === 'tree') {
                loadBudgetTree('reload');
            } else {
                loadPresupuestos();
            }
        } else {
            showToast("Error guardando: " + json.message, "error");
        }
    } catch (e) {
        console.error("Save Error", e);
        showToast("Error de conexión", "error");
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = 'Guardar Cambios'; }
    }
}

function showBudgetReplaceConfirm(year, onAction) {
    const el = document.getElementById('budget-inline-confirm');
    if (!el) return;
    el.innerHTML = `
        <div class="msg">Ya existe presupuesto para ${year}. ¿Desea reemplazar los datos?</div>
        <div class="actions">
          <button class="btn-elegant" id="btn-replace">Reemplazar</button>
          <button class="btn-elegant" id="btn-keep">Mantener</button>
        </div>`;
    el.classList.add('show');
    const b1 = el.querySelector('#btn-replace');
    const b2 = el.querySelector('#btn-keep');
    if (b1) b1.onclick = () => onAction && onAction('replace');
    if (b2) b2.onclick = () => onAction && onAction('keep');
}
function hideBudgetReplaceConfirm() {
    const el = document.getElementById('budget-inline-confirm');
    if (el) { el.classList.remove('show'); el.innerHTML = ''; }
}

function parseFormattedInt(s) {
    if (s === null || s === undefined) return 0;
    const t = String(s).replace(/\./g, '').replace(/,/g, '.');
    const n = parseFloat(t);
    return isNaN(n) ? 0 : Math.round(n);
}
function formatThousands(n) {
    return new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0, useGrouping: true }).format(Math.round(n || 0));
}

function toggleNote(btn) {
    const code = btn.dataset.code;
    const month = parseInt(btn.dataset.month);
    const cell = btn.closest('.month-cell');
    if (!cell) return;
    const inp = cell.querySelector('.note-input');
    if (!inp) return;
    const isHidden = inp.style.display === 'none';
    inp.style.display = isHidden ? 'block' : 'none';
    if (isHidden) {
        inp.focus();
    }
}

function onNoteChange(input) {
    const code = input.dataset.code;
    const month = parseInt(input.dataset.month);
    const text = String(input.value || '').trim();
    if (!budgetState.notes[code]) budgetState.notes[code] = {};
    budgetState.notes[code][month] = text;
    budgetState.dirtyNotes.add(`${code}|${month}`);
    input.classList.add('is-dirty');
}
