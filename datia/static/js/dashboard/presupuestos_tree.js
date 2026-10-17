if (typeof window.budgetViewMode === 'undefined') window.budgetViewMode = 'grid';
window.budgetTreeState = window.budgetTreeState || { expanded: new Set(), lastKey: '', skipAutoExpandOnce: false, lastAction: null };
function _bt_key() {
    const baseInp = document.getElementById('budget-base-year');
    const budInp = document.getElementById('budget-target-year');
    const baseYear = baseInp ? parseInt(baseInp.value || String(currEjercicio)) : parseInt(currEjercicio);
    const budgetYear = budInp ? parseInt(budInp.value || String(parseInt(currEjercicio) + 1)) : (parseInt(currEjercicio) + 1);
    const key = `${currEmpresa}:${baseYear}:${budgetYear}`;
    window.budgetTreeState.lastKey = key;
    return key;
}
function _bt_loadExpanded() {
    try {
        const k = _bt_key();
        const s = localStorage.getItem(`presupuestos:tree:expanded:${k}`) || '[]';
        const arr = JSON.parse(s);
        window.budgetTreeState.expanded = new Set(Array.isArray(arr) ? arr : []);
    } catch (e) { }
}
function _bt_saveExpanded() {
    try {
        const k = window.budgetTreeState.lastKey || _bt_key();
        const arr = Array.from(window.budgetTreeState.expanded || new Set());
        localStorage.setItem(`presupuestos:tree:expanded:${k}`, JSON.stringify(arr));
    } catch (e) { }
}
function toggleExpandAllTree(expand) {
    if (window.budgetViewMode === 'tree' && window.budgetTreeState.cache) {
        const { nodesIng, nodesGas, budData } = window.budgetTreeState.cache;
        function collectCodes(list) {
            const acc = [];
            (list || []).forEach(n => {
                if (n && n.code) acc.push(n.code);
                if (n && Array.isArray(n.children) && n.children.length) {
                    acc.push(...collectCodes(n.children));
                }
            });
            return acc;
        }
        if (expand) {
            window.budgetTreeState.expanded = new Set([...collectCodes(nodesIng), ...collectCodes(nodesGas)]);
            _bt_saveExpanded();
        } else {
            window.budgetTreeState.expanded = new Set();
            _bt_saveExpanded();
        }
        renderBudgetTree({ ingresos: { nodes: nodesIng, start_level: 3 }, gastos: { nodes: nodesGas, start_level: 3 } }, budData);
        return;
    }
    window.budgetTreeState.lastAction = expand ? 'expand_all' : 'collapse_all';
    if (!expand) window.budgetTreeState.skipAutoExpandOnce = true;
    loadBudgetTree('reload');
}
async function loadBudgetTree(mode = 'reload') {
    window.budgetViewMode = 'tree';
    ensureYearDefaults();
    const { baseYear, budgetYear } = getSelectedYears();
    const grid = document.getElementById('budget-grid-container');
    const tree = document.getElementById('budget-tree-container');
    const comp = document.getElementById('budget-comparison-container');
    if (tree) tree.innerHTML = `<div class="loading-spinner"></div> Loading...`;
    if (grid) grid.style.display = 'none';
    if (comp) {
        comp.style.display = 'none';
        comp.innerHTML = '';
    }
    if (tree) tree.style.display = 'block';
    _bt_loadExpanded();
    try {
        const qBud = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(budgetYear)}&base_year=${encodeURIComponent(baseYear)}&group_filter=PL`;
        const qIng = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(baseYear)}&root=ingresos&start_level=3&end_level=6`;
        const qGas = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(baseYear)}&root=gastos&start_level=3&end_level=6`;
        const [budRes, ingRes, gasRes] = await Promise.all([
            fetch(`/api/financial/budgets${qBud}`),
            fetch(`/api/financial/accounts/tree${qIng}`),
            fetch(`/api/financial/accounts/tree${qGas}`)
        ]);
        if (!budRes.ok || !ingRes.ok || !gasRes.ok) {
            if (tree) tree.innerHTML = `<div style="text-align:center; color:#ef4444;">Error cargando datos</div>`;
            return;
        }
        const budData = await budRes.json();
        const ingData = await ingRes.json();
        const gasData = await gasRes.json();
        budgetState.originalData = (budData && Array.isArray(budData.rows)) ? budData.rows : [];
        const nodesIngRaw = Array.isArray(ingData.nodes) ? ingData.nodes : [];
        const nodesGasRaw = Array.isArray(gasData.nodes) ? gasData.nodes : [];
        function deriveGroupNodesFromRows(rows, rootChar) {
            const set = new Set();
            (rows || []).forEach(r => {
                const c = String(r.cuenta || '');
                if (c.startsWith(rootChar) && c.length >= 3) set.add(c.slice(0, 3));
            });
            return Array.from(set).sort((a, b) => parseInt(a) - parseInt(b)).map(code => ({ code, name: code, level: 3, amount: 0, parent_code: null, children: [] }));
        }
        const nodesIng = nodesIngRaw.length ? nodesIngRaw : deriveGroupNodesFromRows(budData.rows, '7');
        const nodesGas = nodesGasRaw.length ? nodesGasRaw : deriveGroupNodesFromRows(budData.rows, '6');
        window.budgetTreeState.cache = { nodesIng, nodesGas, budData };
        function collectCodes(list) {
            const acc = [];
            (list || []).forEach(n => {
                if (n && n.code) acc.push(n.code);
                if (n && Array.isArray(n.children) && n.children.length) {
                    acc.push(...collectCodes(n.children));
                }
            });
            return acc;
        }
        if (window.budgetTreeState.lastAction === 'expand_all') {
            window.budgetTreeState.expanded = new Set([...collectCodes(nodesIng), ...collectCodes(nodesGas)]);
            window.budgetTreeState.lastAction = null;
            _bt_saveExpanded();
        } else if (window.budgetTreeState.lastAction === 'collapse_all') {
            window.budgetTreeState.expanded = new Set();
            window.budgetTreeState.lastAction = null;
            _bt_saveExpanded();
        } else if (window.budgetTreeState.expanded.size === 0 && !window.budgetTreeState.skipAutoExpandOnce) {
            // Por defecto, mantener grupos plegados (no auto-expandir)
            window.budgetTreeState.expanded = new Set();
        }
        renderBudgetTree({ ingresos: ingData, gastos: gasData }, budData);
        window.budgetTreeState.skipAutoExpandOnce = false;
    } catch (e) {
        if (tree) tree.innerHTML = `<div style="text-align:center; color:#ef4444;">Error cargando datos</div>`;
    }
}
function renderBudgetTree(treeData, budData) {
    const container = document.getElementById('budget-tree-container');
    if (!container) return;
    const nf = new Intl.NumberFormat(typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES', { maximumFractionDigits: 0, useGrouping: true });
    const monthsHdr = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    const baseYear = budData && budData.meta ? budData.meta.base_year : (parseInt(currEjercicio) - 1);
    const budgetYear = budData && budData.meta ? budData.meta.budget_year : parseInt(currEjercicio);
    const rows = (budData && Array.isArray(budData.rows)) ? budData.rows : [];
    const map = {};
    rows.forEach(r => { map[String(r.cuenta)] = r; });
    function sumMonthsByPrefix(prefix, which) {
        const arr = new Array(12).fill(0);
        rows.forEach(r => {
            if (String(r.cuenta).startsWith(prefix)) {
                const src = which === 'base' ? (Array.isArray(r.base?.months) ? r.base.months : new Array(12).fill(0)) : (Array.isArray(r.presupuesto?.months) ? r.presupuesto.months : new Array(12).fill(0));
                for (let i = 0; i < 12; i++) arr[i] += Math.round(parseFloat(src[i] || 0));
            }
        });
        return arr;
    }
    function buildGroupBlock(node, level) {
        const codeCell = `<td class="col-code">${node.code}</td>`;
        const typeCell = `<td class="col-type">Grupo</td>`;
        const monthsCount = 12;
        const descCell = `<td class="col-desc" colspan="${1 + monthsCount}"><button class="tree-toggle ${window.budgetTreeState.expanded.has(node.code) ? 'active' : ''}" data-code="${node.code}" onclick="toggleTreeNode(this)">${window.budgetTreeState.expanded.has(node.code) ? '▾' : '▸'}</button><span class="tree-label tree-group ${window.budgetTreeState.expanded.has(node.code) ? 'is-open' : ''}" style="margin-left:${(level - 3) * 16}px">${node.name}</span></td>`;
        let html = `<tr class="tree-group-header">${codeCell}${descCell}</tr>`;
        if (window.budgetTreeState.expanded.has(node.code)) {
            const accounts = rows.filter(r => String(r.cuenta).startsWith(node.code));
            accounts.forEach(row => {
                const baseMonthsA = Array.isArray(row.base?.months) ? row.base.months : new Array(12).fill(0);
                let budMonthsA = Array.isArray(row.presupuesto?.months) ? row.presupuesto.months : new Array(12).fill(0);
                const baseTotalA = typeof row.base?.total === 'number' ? row.base.total : baseMonthsA.reduce((a, b) => a + (parseFloat(b) || 0), 0);
                let budTotalA = typeof row.presupuesto?.total === 'number' ? row.presupuesto.total : budMonthsA.reduce((a, b) => a + (parseFloat(b) || 0), 0);
                const cfg = (row.presupuesto && row.presupuesto.config) ? row.presupuesto.config : {};
                const hasAugBase = ((parseFloat(baseMonthsA[7]) || 0) !== 0);
                const agostoFull = (cfg.agosto_full === true) ? true : hasAugBase;
                const linePct = (cfg.line_pct != null) ? (parseFloat(cfg.line_pct) || 0) : 0;
                budgetState.controls[row.cuenta] = { agosto_full: agostoFull, line_pct: linePct };
                html += `
                    <tr class="budget-row-base tree-line-row">
                        <td class="col-code">${row.cuenta}</td>
                        <td class="col-desc"><span class="tree-label tree-line" style="margin-left:${(level - 2) * 16}px">${row.descripcion}</span></td>
                        <td class="col-total">${baseTotalA !== 0 ? nf.format(Math.round(baseTotalA)) : ''}</td>
                        ${baseMonthsA.map((val) => `<td class="col-month">${((parseFloat(val) || 0) !== 0) ? nf.format(Math.round(parseFloat(val) || 0)) : ''}</td>`).join('')}
                    </tr>
                    <tr class="budget-row-presupuesto tree-line-row">
                        <td class="col-code">&nbsp;</td>
                        <td class="col-desc">
                            <div class="budget-controls">
                                <span>${(typeof gettext === 'function' ? gettext('Agosto') : 'Agosto')}</span>
                                <input type="checkbox" class="budget-aug-check" data-code="${row.cuenta}" ${budgetState.controls[row.cuenta].agosto_full ? 'checked' : ''} onchange="onAgostoToggle(this)">
                                <span>${(typeof gettext === 'function' ? gettext('Línea %') : 'Línea %')}</span>
                                <input type="text" class="budget-line-pct" inputmode="decimal" data-code="${row.cuenta}" value="${String(budgetState.controls[row.cuenta].line_pct).replace('.', ',')}" placeholder="Ej: 5,25" onchange="onLinePctChange(this)">
                            </div>
                        </td>
                        <td class="col-total">
                            <input type="text" class="budget-input-total" data-code="${row.cuenta}" value="${budTotalA !== 0 ? nf.format(Math.round(budTotalA)) : ''}" step="any" onchange="onTotalChange(this)">
                        </td>
                        ${budMonthsA.map((val, idx) => {
                    const m = idx + 1;
                    const noteVal = (row.presupuesto && row.presupuesto.notes && row.presupuesto.notes[m]) ? String(row.presupuesto.notes[m]) : '';
                    return `
                            <td class="col-month">
                                <div class="month-cell">
                                    <input type="text" class="budget-input" data-code="${row.cuenta}" data-month="${m}" value="${val !== 0 ? String(Math.round(val)) : ''}" placeholder="" step="any" onchange="markDirty(this)">
                                    <button class="note-btn" title="${(typeof gettext === 'function' ? gettext('Notas') : 'Notas')}" data-code="${row.cuenta}" data-month="${m}" onclick="toggleNote(this)">📝</button>
                                    <input type="text" class="note-input" data-code="${row.cuenta}" data-month="${m}" value="${noteVal}" placeholder="${(typeof gettext === 'function' ? gettext('Añadir nota') : 'Añadir nota')}" style="display:none" onchange="onNoteChange(this)">
                                </div>
                            </td>`;
                }).join('')}
                    </tr>
                    `;
            });
        }
        return html;
    }
    function normalizeNodes(rootObj, rows, rootChar) {
        let nodes = Array.isArray(rootObj.nodes) ? rootObj.nodes : [];
        if (!nodes.length) {
            const set = new Set();
            (rows || []).forEach(r => {
                const c = String(r.cuenta || '');
                if (c.startsWith(rootChar) && c.length >= 3) set.add(c.slice(0, 3));
            });
            nodes = Array.from(set).sort((a, b) => parseInt(a) - parseInt(b)).map(code => ({ code, name: code, level: (rootObj.start_level || 3), amount: 0, parent_code: null, children: [] }));
        } else {
            nodes = nodes.slice().sort((a, b) => parseInt(a.code) - parseInt(b.code));
        }
        return nodes;
    }
    function renderRoot(rootObj, title, rootChar) {
        const nodes = normalizeNodes(rootObj, rows, rootChar);
        let html = `
        <table class="budget-table budget-tree">
            <thead>
                <tr>
                    <th class="col-code">Cuenta</th>
                    <th class="col-desc">Descripción</th>
                    <th class="col-total">Total</th>
                    ${monthsHdr.map(m => `<th class="col-month">${m}</th>`).join('')}
                </tr>
            </thead>
            <tbody>
        `;
        nodes.forEach(n => { html += buildGroupBlock(n, rootObj.start_level || 3); });
        html += `</tbody></table>`;
        return html;
    }
    let htmlAll = '';
    htmlAll += renderRoot(treeData.ingresos, 'Ingresos', '7');
    htmlAll += renderRoot(treeData.gastos, 'Gastos', '6');
    container.innerHTML = htmlAll;
}
function toggleTreeNode(btn) {
    const code = btn.getAttribute('data-code');
    if (!code) return;
    if (window.budgetTreeState.expanded.has(code)) {
        window.budgetTreeState.expanded.delete(code);
    } else {
        window.budgetTreeState.expanded.add(code);
    }
    _bt_saveExpanded();
    loadBudgetTree('reload');
}
