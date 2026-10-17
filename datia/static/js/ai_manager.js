/* AI Manager Script */
class AIReportManager {
    static init() {
        // Ensure overlay exists (if requested dynamically)
    }

    static lastHtml = '';
    static lastPdfHtml = '';
    static lastKind = '';
    static lastModelUsed = '';
    static lastRawData = {};
    static lastOrigin = 'ia-general';

    static showProFromAnswer(answerPayload, queryText = '') {
        const overlay = document.getElementById('ai-report-overlay');
        const processingView = document.getElementById('ai-thinking-view');
        const resultView = document.getElementById('ai-result-view');
        if (!overlay || !processingView || !resultView) return;

        overlay.style.display = 'flex';
        processingView.style.display = 'none';
        resultView.style.display = 'block';
        resultView.innerHTML = '';

        try {
            document.documentElement.style.overflow = 'hidden';
            document.documentElement.style.height = '100vh';
            document.body.style.overflow = 'hidden';
            document.body.style.height = '100vh';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
        } catch (_) { }

        const now = new Date();
        const lang = (window.APP_LANG || 'es-ES');
        let dateStr = '';
        try { dateStr = now.toLocaleString(lang); } catch (_) { dateStr = now.toISOString(); }

        const empresa = (typeof currEmpresa !== 'undefined' ? currEmpresa : '');
        const ejercicio = (typeof currEjercicio !== 'undefined' ? currEjercicio : '');

        const title = "Informe Ejecutivo";
        const source = (answerPayload && answerPayload.source) ? String(answerPayload.source) : 'ai';
        const type = (answerPayload && answerPayload.type) ? String(answerPayload.type) : 'text';
        const key = (answerPayload && answerPayload.key) ? String(answerPayload.key) : '—';

        const html = AIReportManager._buildProHtml({
            title,
            empresa,
            ejercicio,
            dateStr,
            queryText: queryText || '',
            answerPayload: answerPayload || {},
        });

        resultView.innerHTML = html.screenHtml;

        AIReportManager.lastHtml = html.pdfHtml || '';
        AIReportManager.lastPdfHtml = html.pdfHtml || '';
        AIReportManager.lastKind = 'chat';
        AIReportManager.lastOrigin = 'ia-chat';
        AIReportManager.lastModelUsed = (answerPayload && (answerPayload.model_used || answerPayload.model || '')) || '';
        AIReportManager.lastRawData = { payload: answerPayload || {}, query: queryText || '' };

        const actions = document.createElement('div');
        actions.className = 'ai-pro-actions';
        actions.innerHTML = `
            <button class="btn-glow" style="padding:6px 12px; font-size:0.85rem;" onclick="AIReportManager.downloadPDF(this)">
                <i class="fas fa-file-pdf"></i> Descargar PDF
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.85rem; border-color:#38bdf8; color:#e2e8f0;" onclick="AIReportManager.showInfografia(this)">
                <i class="fas fa-chart-area"></i> Infografía
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.85rem; border-color:#8b5cf6; color:#e2e8f0;" onclick="AIReportManager.generateNotebookLmPodcast(this)">
                <i class="fas fa-headphones"></i> Podcast NotebookLM
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.85rem;" onclick="AIReportManager.saveReport()">
                <i class="fas fa-save"></i> Guardar
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.85rem;" onclick="AIReportManager.close()">
                Cerrar
            </button>
        `;
        resultView.appendChild(actions);

        try {
            AIReportManager._renderProCharts(answerPayload, resultView);
        } catch (_) { }
    }

    static _escapeHtml(s) {
        const str = String(s == null ? '' : s);
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    static _looksLikeHtml(s) {
        const t = String(s == null ? '' : s);
        return /<\w+[\s>]/.test(t);
    }

    static _fmtNumber(n, decimals) {
        try {
            return new Intl.NumberFormat((window.APP_LANG || 'es-ES'), { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(Number(n || 0));
        } catch (_) {
            const v = Number(n || 0);
            return (isFinite(v) ? v.toFixed(decimals) : String(n));
        }
    }

    static _parseNumberLike(v) {
        if (typeof v === 'number') return isFinite(v) ? v : null;
        if (v == null) return null;
        let s = String(v).trim();
        if (!s) return null;
        const hadPct = /%$/.test(s);
        s = s.replace(/[%\s]/g, '');
        s = s.replace(/eur$/i, '').replace(/€$/g, '');
        s = s.trim();
        if (!/^-?[\d.,]+$/.test(s)) return null;

        const lastComma = s.lastIndexOf(',');
        const lastDot = s.lastIndexOf('.');
        let decSep = null;
        if (lastComma >= 0 && lastDot >= 0) {
            decSep = (lastComma > lastDot) ? ',' : '.';
        } else if (lastComma >= 0) {
            decSep = ',';
        } else if (lastDot >= 0) {
            decSep = '.';
        }

        let norm = s;
        if (decSep === ',') {
            norm = norm.replace(/\./g, '').replace(',', '.');
        } else if (decSep === '.') {
            norm = norm.replace(/,/g, '');
        }
        const num = Number(norm);
        if (!isFinite(num)) return null;
        return hadPct ? (num) : num;
    }

    static _formatValueForColumn(col, v) {
        const colName = String(col || '');
        const raw = v;
        const n = AIReportManager._parseNumberLike(v);
        const hadEuro = (typeof raw === 'string') && (/€/.test(raw) || /eur/i.test(raw));
        const hadPct = (typeof raw === 'string') && /%/.test(raw);

        let decimals = 2;
        if (hadPct || colName.includes('%') || colName.toLowerCase().includes('pct')) decimals = 1;
        if (colName.toLowerCase().includes('días') || colName.toLowerCase().includes('dias')) decimals = 0;
        if (colName.toLowerCase().includes('id') || colName.toLowerCase().includes('código') || colName.toLowerCase().includes('codigo')) decimals = 0;

        if (n == null) return { text: (raw === 0 ? '0' : (raw || '')), isNum: false };
        const txt = AIReportManager._fmtNumber(n, decimals);
        if (hadPct || colName.includes('%')) return { text: txt + ' %', isNum: true };
        if (hadEuro || colName.includes('€') || /importe|saldo|cobros|pagos|caja/i.test(colName)) return { text: txt + ' €', isNum: true };
        return { text: txt, isNum: true };
    }

    static _fmtKpiValue(k) {
        const v = k && k.value;
        const suffix = (k && k.suffix) ? String(k.suffix) : '';
        if (typeof v !== 'number') return (v === 0 ? '0' : (v || '--'));
        const dec = (k && typeof k.decimals === 'number') ? k.decimals : null;
        if (suffix === '€') return `${AIReportManager._fmtNumber(v, 2)} €`;
        if (suffix === '%') return `${AIReportManager._fmtNumber(v, dec == null ? 1 : dec)} %`;
        if (suffix) return `${AIReportManager._fmtNumber(v, 2)} ${suffix}`;
        return AIReportManager._fmtNumber(v, dec == null ? 2 : dec);
    }

    static _buildTable(table) {
        const cols = Array.isArray(table && table.columns) ? table.columns : [];
        const rows = Array.isArray(table && table.rows) ? table.rows : [];
        if (!cols.length || !rows.length) return '';
        let out = `<div class="ai-pro-table-wrap"><table class="ai-pro-table"><thead><tr>`;
        cols.forEach(c => { out += `<th>${AIReportManager._escapeHtml(c)}</th>`; });
        out += `</tr></thead><tbody>`;
        rows.slice(0, 40).forEach(r => {
            out += `<tr>`;
            (r || []).forEach((cell, idx) => {
                const col = (cols[idx] || '').toString();
                const f = AIReportManager._formatValueForColumn(col, cell);
                out += `<td class="${f.isNum ? 'num' : ''}">${AIReportManager._escapeHtml(f.text)}</td>`;
            });
            out += `</tr>`;
        });
        out += `</tbody></table></div>`;
        return out;
    }

    static _buildExplainSection(payload) {
        const key = String((payload && payload.key) || '');
        const kpis = Array.isArray(payload && payload.kpis) ? payload.kpis : [];
        if (!kpis.length) return '';

        const get = (label) => {
            const t = (label || '').toLowerCase();
            return kpis.find(x => String(x && x.label || '').toLowerCase() === t);
        };
        const kCash = get('caja');
        const kRec = get('cobros pendientes');
        const kPay = get('pagos pendientes');
        const kCar = get('cartera (importe)') || get('cartera (importe)');
        const kCarCob = get('cartera cobros');
        const kCarPag = get('cartera pagos');
        const kOver90 = get('vencido >90d');

        let items = [];
        if (key === 'tesoreria_resumen') {
            const cash = kCash ? Number(kCash.value || 0) : 0;
            const rec = kRec ? Number(kRec.value || 0) : 0;
            const pay = kPay ? Number(kPay.value || 0) : 0;
            const car = kCar ? Number(kCar.value || 0) : 0;
            const carCob = kCarCob ? Number(kCarCob.value || 0) : 0;
            const carPag = kCarPag ? Number(kCarPag.value || 0) : 0;
            const over90 = kOver90 ? Number(kOver90.value || 0) : 0;
            const netCar = carCob - carPag;
            const pctOver90 = (carCob > 0) ? (over90 / carCob * 100) : 0;
            items = [
                `Caja actual: <strong>${AIReportManager._escapeHtml(AIReportManager._fmtNumber(cash, 2))} €</strong>.`,
                `Cartera pendiente (importe): <strong>${AIReportManager._escapeHtml(AIReportManager._fmtNumber(car, 2))} €</strong> (cobros ${AIReportManager._escapeHtml(AIReportManager._fmtNumber(carCob, 2))} € · pagos ${AIReportManager._escapeHtml(AIReportManager._fmtNumber(carPag, 2))} €). Neto cartera: <strong>${AIReportManager._escapeHtml(AIReportManager._fmtNumber(netCar, 2))} €</strong>.`,
                `Riesgo de morosidad: vencido >90 días <strong>${AIReportManager._escapeHtml(AIReportManager._fmtNumber(over90, 2))} €</strong> (${AIReportManager._escapeHtml(AIReportManager._fmtNumber(pctOver90, 1))}% del cobro pendiente).`,
                `Lectura rápida: cuentas 43 (cobros) ${AIReportManager._escapeHtml(AIReportManager._fmtNumber(rec, 2))} € vs cuentas 40/41 (pagos) ${AIReportManager._escapeHtml(AIReportManager._fmtNumber(pay, 2))} €; prioriza gestión de vencimientos y negociación de pagos.`
            ];
        } else if (key === 'financiera_ratios') {
            items = [
                `Estos ratios se calculan desde PGC y sirven como “semáforos” por categoría: <strong>liquidez</strong>, <strong>solvencia</strong>, <strong>gestión</strong>, <strong>rentabilidad</strong> y <strong>cobertura</strong>.`,
                `Guía rápida: liquidez y test ácido evalúan corto plazo; endeudamiento/garantía/autonomía miden estructura; periodos de cobro/pago y rotaciones explican eficiencia; ROA/ROE y márgenes miden rentabilidad.`,
                `Usa la tabla “Ratios” para ver todos los valores (incluye los que estén N/D por falta de base contable suficiente).`,
            ];
        } else {
            const top = kpis.slice(0, 6).map(k => {
                const lbl = AIReportManager._escapeHtml(k.label || '—');
                const val = AIReportManager._escapeHtml(AIReportManager._fmtKpiValue(k));
                return `${lbl}: <strong>${val}</strong>`;
            });
            items = [
                `Indicadores clave: ${top.join(' · ')}.`,
                `Interpretación: los KPIs superiores explican el estado del ámbito consultado; usa “Detalle” para ver la composición y concentración.`,
                `Acción sugerida: identifica el 20% de partidas que explican el 80% del impacto y fija objetivos de mejora medibles (margen, caja, rotación, concentración).`,
            ];
        }

        return `<div class="ai-pro-section"><h2>Interpretación (CFO)</h2><ul>${items.map(x => `<li>${x}</li>`).join('')}</ul></div>`;
    }

    static _extractYearsFromColumns(cols) {
        const out = [];
        (cols || []).forEach(c => {
            const s = String(c || '');
            const m = s.match(/\b(20\d{2})\b/g);
            if (m) m.forEach(y => out.push(parseInt(y, 10)));
        });
        const uniq = Array.from(new Set(out.filter(n => Number.isFinite(n))));
        uniq.sort((a, b) => b - a);
        return uniq;
    }

    static _metricKeyFromColumn(col) {
        const s = String(col || '').toLowerCase();
        if (/(var|variaci)/.test(s) && /%/.test(s)) return 'var_pct';
        if (/precio/.test(s) && /medio/.test(s)) return 'precio_medio';
        if (/(ops|operac)/.test(s)) return 'ops';
        if (/margen/.test(s) && /%/.test(s)) return 'margen_pct';
        if (/margen/.test(s)) return 'margen';
        if (/coste/.test(s) || /costo/.test(s) || /gasto/.test(s)) return 'coste';
        if (/venta/.test(s) || /ingreso/.test(s)) return 'ventas';
        return null;
    }

    static _yearFromColumn(col) {
        const s = String(col || '');
        const m = s.match(/\b(20\d{2})\b/);
        if (!m) return null;
        const y = parseInt(m[1], 10);
        return Number.isFinite(y) ? y : null;
    }

    static _buildPdfTableSmart(tt) {
        const cols = Array.isArray(tt && tt.columns) ? tt.columns : [];
        const rows = Array.isArray(tt && tt.rows) ? tt.rows : [];
        if (!cols.length || !rows.length) return '';

        const years = AIReportManager._extractYearsFromColumns(cols);
        const hasComparison = years.length >= 2;
        const isWide = cols.length >= 10;

        if (!(hasComparison && isWide)) {
            const head = cols.map(c => `<th>${AIReportManager._escapeHtml(c)}</th>`).join('');
            const body = rows.slice(0, 35).map(r => {
                const cells = (r || []).map((cell, idx) => {
                    const col = (cols[idx] || '').toString();
                    const f = AIReportManager._formatValueForColumn(col, cell);
                    return `<td>${AIReportManager._escapeHtml(f.text)}</td>`;
                }).join('');
                return `<tr>${cells}</tr>`;
            }).join('');
            return `<table border="1" cellpadding="4" cellspacing="0"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
        }

        const yTop = years[0];
        const yPrev = years[1];
        const idxMap = {};
        let varIdx = null;
        for (let i = 1; i < cols.length; i++) {
            const col = cols[i];
            const key = AIReportManager._metricKeyFromColumn(col);
            if (!key) continue;
            if (key === 'var_pct') {
                varIdx = i;
                continue;
            }
            const y = AIReportManager._yearFromColumn(col);
            if (!y) continue;
            if (!idxMap[key]) idxMap[key] = {};
            idxMap[key][y] = i;
        }

        const metricOrder = [
            { key: 'ventas', label: `Ventas (${yTop}/${yPrev})`, fmt: 'Ventas (€)' },
            { key: 'coste', label: `Coste (${yTop}/${yPrev})`, fmt: 'Coste (€)' },
            { key: 'margen', label: `Margen (${yTop}/${yPrev})`, fmt: 'Margen (€)' },
            { key: 'margen_pct', label: `Margen % (${yTop}/${yPrev})`, fmt: 'Margen %' },
            { key: 'ops', label: `Ops (${yTop}/${yPrev})`, fmt: 'Ops' },
            { key: 'precio_medio', label: `Precio medio (${yTop}/${yPrev})`, fmt: 'Precio medio (€)' },
        ];

        const headCols = [
            `<th>${AIReportManager._escapeHtml(cols[0] || 'Item')}</th>`,
            `<th>Ejercicio</th>`,
            ...metricOrder.map(m => `<th>${AIReportManager._escapeHtml(m.label)}</th>`),
            `<th>Var %</th>`
        ].join('');

        const baseLimit = Math.min(28, rows.length);
        const body = rows.slice(0, baseLimit).map(r => {
            const label = (r && r[0] != null) ? String(r[0]) : '';
            const buildRow = (year, showLabel, showVar) => {
                let tds = '';
                tds += `<td>${showLabel ? AIReportManager._escapeHtml(label) : ''}</td>`;
                tds += `<td>${AIReportManager._escapeHtml(String(year))}</td>`;
                metricOrder.forEach(m => {
                    const idx = (idxMap[m.key] || {})[year];
                    const raw = (idx != null) ? (r || [])[idx] : null;
                    const f = AIReportManager._formatValueForColumn(m.fmt, raw);
                    tds += `<td>${AIReportManager._escapeHtml(f.text)}</td>`;
                });
                if (showVar && varIdx != null) {
                    const fv = AIReportManager._formatValueForColumn('Var %', (r || [])[varIdx]);
                    tds += `<td>${AIReportManager._escapeHtml(fv.text)}</td>`;
                } else {
                    tds += `<td></td>`;
                }
                return `<tr>${tds}</tr>`;
            };
            return buildRow(yTop, true, true) + buildRow(yPrev, false, false);
        }).join('');

        return `<table border="1" cellpadding="4" cellspacing="0"><thead><tr>${headCols}</tr></thead><tbody>${body}</tbody></table>`;
    }

    static _buildProHtml(ctx) {
        const title = ctx.title || 'Informe';
        const empresa = ctx.empresa;
        const ejercicio = ctx.ejercicio;
        const dateStr = ctx.dateStr || '';
        const queryText = ctx.queryText || '';
        const payload = ctx.answerPayload || {};

        const type = payload.type || 'text';
        const key = payload.key || '—';
        const source = payload.source || 'ai';

        const badges = [
            `<span class="ai-pro-badge">Tipo: ${AIReportManager._escapeHtml(type)}</span>`,
            `<span class="ai-pro-badge">Origen: ${AIReportManager._escapeHtml(source)}</span>`,
            `<span class="ai-pro-badge">Clave: ${AIReportManager._escapeHtml(key)}</span>`
        ].join('');

        const header = `
            <div class="ai-pro-header">
                <div class="ai-pro-title">
                    <h1>${AIReportManager._escapeHtml(title)}</h1>
                    <div class="ai-pro-meta">Empresa ${AIReportManager._escapeHtml(empresa)} · Ejercicio ${AIReportManager._escapeHtml(ejercicio)} · ${AIReportManager._escapeHtml(dateStr)}</div>
                </div>
                <div class="ai-pro-badges">${badges}</div>
            </div>
        `;

        const qBlock = queryText
            ? `<div class="ai-pro-section"><h2>Consulta</h2><p>${AIReportManager._escapeHtml(queryText)}</p></div>`
            : '';

        const kpis = Array.isArray(payload.kpis) ? payload.kpis : [];
        const kpisShown = (String(payload.key || '') === 'financiera_ratios') ? kpis : kpis.slice(0, 10);
        const isRatios = (String(payload.key || '') === 'financiera_ratios');
        const groupOrder = ['liquidez', 'solvencia', 'gestion', 'rentabilidad', 'cobertura'];
        const groupLabels = { liquidez: 'Liquidez', solvencia: 'Solvencia', gestion: 'Gestión', rentabilidad: 'Rentabilidad', cobertura: 'Cobertura' };

        const renderKpiCard = (k) => `
            <div class="ai-pro-kpi">
                <div class="label">${AIReportManager._escapeHtml(k.label || '—')}</div>
                <div class="value" style="color:${AIReportManager._escapeHtml(k.color || '#fff')}">${AIReportManager._escapeHtml(AIReportManager._fmtKpiValue(k))}</div>
                <div class="sub">${(typeof k.change === 'number') ? (AIReportManager._fmtNumber(k.change, 1) + ' %') : AIReportManager._escapeHtml(k.change || '').replace(/\b(vs\s+\d{4}:)/i, '<strong>$1</strong>')}</div>
            </div>
        `;

        let kpiBody = '';
        if (isRatios) {
            const byGroup = {};
            kpisShown.forEach(k => {
                const g = String(k && k.group || 'otros');
                if (!byGroup[g]) byGroup[g] = [];
                byGroup[g].push(k);
            });
            kpiBody = groupOrder
                .filter(g => (byGroup[g] || []).length)
                .map(g => `
                    <div class="ai-pro-kpi-group">
                        <div class="ai-pro-group-title">${AIReportManager._escapeHtml(groupLabels[g] || g)}</div>
                        <div class="ai-pro-kpis">
                            ${(byGroup[g] || []).map(renderKpiCard).join('')}
                        </div>
                    </div>
                `).join('');
            const leftovers = Object.keys(byGroup).filter(g => !groupOrder.includes(g));
            if (leftovers.length) {
                leftovers.forEach(g => {
                    kpiBody += `
                        <div class="ai-pro-kpi-group">
                            <div class="ai-pro-group-title">${AIReportManager._escapeHtml(groupLabels[g] || g)}</div>
                            <div class="ai-pro-kpis">
                                ${(byGroup[g] || []).map(renderKpiCard).join('')}
                            </div>
                        </div>
                    `;
                });
            }
        } else {
            kpiBody = `<div class="ai-pro-kpis">${kpisShown.map(renderKpiCard).join('')}</div>`;
        }

        const kpiBlock = kpis.length ? `
            <div class="ai-pro-section">
                <h2>Indicadores</h2>
                ${kpiBody}
            </div>
        ` : '';

        let answerText = payload.answer || payload.text || '';
        let answerHtml = '';
        if (AIReportManager._looksLikeHtml(answerText)) {
            answerHtml = String(answerText);
        } else {
            answerHtml = `<p>${AIReportManager._escapeHtml(String(answerText)).replace(/\n/g, '<br>')}</p>`;
        }
        const narrativeBlock = `
            <div class="ai-pro-section">
                <h2>Resumen</h2>
                ${answerHtml}
            </div>
        `;

        const tables = Array.isArray(payload.tables) ? payload.tables : (payload.table ? [payload.table] : []);
        const tableBlock = tables.length ? `
            <div class="ai-pro-section">
                <h2>Detalle</h2>
                ${tables.map(t => `
                    <div style="margin-top:10px;">
                        <div class="ai-pro-subtitle">${AIReportManager._escapeHtml((t && t.title) || 'Tabla')}</div>
                        ${AIReportManager._buildTable(t)}
                    </div>
                `).join('')}
            </div>
        ` : '';

        const explainBlock = AIReportManager._buildExplainSection(payload);

        const chartShell = (payload.chart_config || payload.chart_pareto || payload.chart_pareto_clients || payload.chart_pareto_products || payload.chart_concentration) ? `
            <div class="ai-pro-section">
                <h2>Gráficos</h2>
                <div id="ai-pro-chart-main" style="min-height:260px;"></div>
                <div id="ai-pro-chart-secondary" style="min-height:260px; margin-top:12px;"></div>
            </div>
        ` : '';

        const screenHtml = `<div class="ai-pro-report">${header}${qBlock}${kpiBlock}${explainBlock}${narrativeBlock}${chartShell}${tableBlock}</div>`;

        const metaLine = `Empresa ${AIReportManager._escapeHtml(empresa)} · Ejercicio ${AIReportManager._escapeHtml(ejercicio)} · ${AIReportManager._escapeHtml(dateStr)}`;
        const pdfHeader = `<h1>${AIReportManager._escapeHtml(title)}</h1><p><small>${metaLine}</small></p>`;

        const pdfQuery = queryText ? `<h2>Consulta</h2><p>${AIReportManager._escapeHtml(queryText)}</p>` : '';

        const pdfKpis = kpis.length
            ? `<h2>Indicadores</h2><table border="1" cellpadding="4" cellspacing="0"><thead><tr><th>Indicador</th><th>Valor</th><th>Δ</th></tr></thead><tbody>${
                kpisShown.map(k => {
                    const ch = (typeof k.change === 'number') ? (AIReportManager._fmtNumber(k.change, 1) + ' %') : (k.change || '');
                    return `<tr><td>${AIReportManager._escapeHtml(k.label || '—')}</td><td class="text-right">${AIReportManager._escapeHtml(AIReportManager._fmtKpiValue(k))}</td><td class="text-right">${AIReportManager._escapeHtml(ch)}</td></tr>`;
                }).join('')
            }</tbody></table>`
            : '';

        const pdfExplain = explainBlock ? (`<h2>Interpretación (CFO)</h2>` + explainBlock.replace(/<div class="ai-pro-section"><h2>Interpretación \(CFO\)<\/h2>/, '').replace(/<\/div>\s*$/, '')) : '';
        const pdfNarrative = `<h2>Resumen</h2>${AIReportManager._looksLikeHtml(answerText) ? String(answerText) : `<p>${AIReportManager._escapeHtml(String(answerText)).replace(/\n/g, '<br>')}</p>`}`;

        let pdfTable = '';
        if (tables.length) {
            pdfTable = tables.map(t => {
                const tt = t || {};
                const built = AIReportManager._buildPdfTableSmart(tt);
                if (!built) return '';
                return `<h2>${AIReportManager._escapeHtml(tt.title || 'Detalle')}</h2>${built}`;
            }).join('');
        }

        const pdfHtml = `<div>${pdfHeader}${pdfQuery}${pdfKpis}${pdfExplain}${pdfNarrative}${pdfTable}</div>`;

        return { screenHtml, pdfHtml };
    }

    static _renderProCharts(answerPayload, rootEl) {
        if (typeof renderAiChart !== 'function') return;
        const main = rootEl.querySelector('#ai-pro-chart-main');
        const secondary = rootEl.querySelector('#ai-pro-chart-secondary');
        if (!main || !secondary) return;

        const pickMain = answerPayload && (answerPayload.chart_config || answerPayload.chart_pareto_clients || answerPayload.chart_pareto || answerPayload.chart_pareto_products);
        const pickSecondary = answerPayload && (answerPayload.chart_concentration || answerPayload.chart_quarters);

        if (pickMain) renderAiChart(main, pickMain);
        if (pickSecondary) renderAiChart(secondary, pickSecondary);
    }

    static async openReport(kind, origin = 'ia-general') {
        const overlay = document.getElementById('ai-report-overlay');
        const processingView = document.getElementById('ai-thinking-view');
        const resultView = document.getElementById('ai-result-view');
        const statusText = document.getElementById('ai-thinking-text');
        const thinkingLogo = document.getElementById('ai-thinking-logo');
        const timerEl = document.getElementById('ai-timer-elapsed');
        const timerRing = document.getElementById('ai-timer-ring');

        // 1. Reset State
        overlay.style.display = 'flex';
        processingView.style.display = 'flex';
        resultView.style.display = 'none';
        resultView.innerHTML = ''; // Clear previous
        try {
            document.documentElement.style.overflow = 'hidden';
            document.documentElement.style.height = '100vh';
            document.body.style.overflow = 'hidden';
            document.body.style.height = '100vh';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
        } catch (_) {}

        document.body.classList.add('ai-processing'); // For border effect

        // 2. Preparar UI de espera (logo, cronómetro, carrusel)
        try {
            // Logo: usar el activo en cabecera o el guardado
            const headerLogo = document.getElementById('header-datia-logo');
            if (thinkingLogo && headerLogo && headerLogo.src) {
                thinkingLogo.src = headerLogo.src;
            } else {
                const savedLogo = localStorage.getItem('datia-selected-logo');
                if (thinkingLogo && savedLogo) thinkingLogo.src = savedLogo;
            }
        } catch (_) { }

        let startTs = performance.now();
        AIReportManager._timerTick = null;
        const fmt2 = (n) => (n < 10 ? '0' + n : '' + n);
        const updateTimer = () => {
            const ms = performance.now() - startTs;
            const mm = Math.floor(ms / 60000);
            const ss = Math.floor((ms % 60000) / 1000);
            if (timerEl) timerEl.innerText = `${fmt2(mm)}:${fmt2(ss)}`;
            // anillo conic-progress (ciclo de 7s por defecto)
            const base = parseInt(localStorage.getItem('datia-status-carousel-interval') || '7', 10);
            const deg = Math.min(360, ((ms % (base * 1000)) / (base * 1000)) * 360);
            if (timerRing) timerRing.style.setProperty('--ai-timer-deg', `${deg}deg`);
        };
        updateTimer();
        AIReportManager._timerTick = setInterval(updateTimer, 1000);

        // Carrusel de mensajes dinámicos
        const carouselEnabled = (localStorage.getItem('datia-status-carousel-enabled') || 'true') !== 'false';
        let carouselStop = null;
        if (carouselEnabled) {
            AIReportManager.loadStatusMessages().then(({ slides, intervalMs }) => {
                AIReportManager.initCarousel(slides, intervalMs);
                AIReportManager.attachKeyboardControls();
            }).catch(() => {
                // fallback a mensajes estáticos si falla carga
                const fallback = [
                    "Conectando con motor de conocimiento...",
                    "Analizando KPIs financieros...",
                    "Detectando patrones en ventas y compras...",
                    "Generando narrativa ejecutiva..."
                ];
                AIReportManager.initCarousel(fallback.map(t => ({ text: t })), 7000);
                AIReportManager.attachKeyboardControls();
            });
        }

        // 3. Secuencia de mensajes de estado textual mínimo
        const messages = [
            "Conectando con motor de conocimiento...",
            "Analizando KPIs financieros...",
            "Detectando patrones en ventas...",
            "Generando estrategia ejecutiva..."
        ];
        let msgIdx = 0;
        statusText.innerText = messages[0];

        const interval = setInterval(() => {
            msgIdx++;
            if (msgIdx < messages.length) {
                statusText.innerText = messages[msgIdx];
            }
        }, 1500); // Change text every 1.5s

        try {
            if (origin === 'ia2') {
                const resp = await fetch(`/api/financial/infografia?empresa=${currEmpresa}&ejercicio=${currEjercicio}`);
                const dto = await resp.json();
                if (!resp.ok || dto.status !== 'ok') {
                    throw new Error(dto.message || 'Error generando infografía');
                }
                const cssHref = '/static/css/infografia_story.css';
                try {
                    let linkEl = document.querySelector('link[data-infografia="1"]');
                    if (!linkEl) {
                        linkEl = document.createElement('link');
                        linkEl.rel = 'stylesheet';
                        linkEl.href = cssHref;
                        linkEl.setAttribute('data-infografia', '1');
                        document.head.appendChild(linkEl);
                    }
                } catch (_) { }
                try {
                    const overlay = document.getElementById('ai-report-overlay');
                    const card = document.querySelector('#ai-report-overlay .ai-modal-card');
                    const inner = document.querySelector('#ai-report-overlay .ai-modal-card-inner');
                    const res = document.getElementById('ai-result-view');
                    // Para infografía IA2 queremos página scrollable, no encajada a 100vh
                    if (overlay) {
                        overlay.style.overflow = 'auto';
                        overlay.style.alignItems = 'flex-start';
                    }
                    if (card) {
                        card.style.width = '100%';
                        card.style.maxWidth = '1400px';
                        card.style.minHeight = 'auto';
                        card.style.background = 'transparent';
                        card.style.border = 'none';
                        card.style.boxShadow = 'none';
                        card.style.padding = '0';
                        card.style.margin = '32px auto';
                    }
                    if (inner) {
                        inner.style.padding = '0';
                        inner.style.background = 'transparent';
                    }
                    if (res) {
                        res.style.width = '100%';
                        res.style.height = 'auto';
                        res.style.maxHeight = 'none';
                        res.style.padding = '0';
                        res.style.overflow = 'auto';
                        res.style.display = 'block';
                        res.style.alignItems = '';
                        res.style.justifyContent = '';
                        res.style.position = 'relative';
                    }
                } catch (_) {}
                const finalHtml = AIReportManager._buildStoryHtml(dto);
                clearInterval(interval);
                try { clearInterval(AIReportManager._timerTick); } catch (_) { }
                processingView.style.display = 'none';
                resultView.style.display = 'block';
                resultView.innerHTML = finalHtml;
                resultView.style.overflow = 'auto';
                document.body.classList.remove('ai-processing');
                AIReportManager.lastHtml = finalHtml || '';
                AIReportManager.lastKind = kind;
                AIReportManager.lastModelUsed = 'JSON';
                AIReportManager.lastRawData = dto || {};
                AIReportManager.lastOrigin = origin || 'ia2';
                const actions = document.createElement('div');
                actions.style.display = 'flex';
                actions.style.justifyContent = 'flex-end';
                actions.style.gap = '10px';
                actions.style.marginTop = '12px';
                actions.innerHTML = `
                    <span style="color:#a1a1aa; font-size:0.8rem; margin-right:auto;">Origen: JSON • Empresa ${dto.empresa} • ${dto.ejercicio}</span>
                    <button class="btn-glow" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.downloadPDF(this)">
                        <i class="fas fa-file-pdf"></i> Descargar PDF
                    </button>
                    <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem; border-color:#38bdf8; color:#e2e8f0;" onclick="AIReportManager.showInfografia(this)">
                        <i class="fas fa-chart-area"></i> Infografía
                    </button>
                    <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem; border-color:#8b5cf6; color:#e2e8f0;" onclick="AIReportManager.generateNotebookLmPodcast(this)">
                        <i class="fas fa-headphones"></i> Podcast NotebookLM
                    </button>
                    <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.close()">
                        Cerrar
                    </button>
                `;
                resultView.appendChild(actions);
                return;
            }
            // 3. API Call START (Async Polling Architecture)
            let devModel = (function () {
                try {
                    const report = localStorage.getItem('datia-report-model');
                    if (report && report.length) return report;
                    const chat = localStorage.getItem('datia-ai-model');
                    if (chat && chat.length) return chat;
                    return origin === 'ia2' ? 'qwen2.5:14b-instruct-q4_k_m' : 'mistral:latest';
                } catch (_) { return origin === 'ia2' ? 'qwen2.5:14b-instruct-q4_k_m' : 'mistral:latest'; }
            })();

            const controller = new AbortController();
            // Polling doesn't block, so safety timer can be huge or removed (polling manages itself)
            AIReportManager._abortTimer = setTimeout(() => { try { controller.abort(); } catch (_) { } }, 720000); // 12 min hard limit

            try {
                await fetch('/api/ai/context/build', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': CSRF_TOKEN
                    },
                    body: JSON.stringify({
                        empresa: currEmpresa,
                        ejercicio: currEjercicio,
                        kind: kind
                    })
                });
            } catch (_) { }

            // Step 3.1: Start Job
            const startResp = await fetch('/api/ai/report/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify({
                    empresa: currEmpresa,
                    ejercicio: currEjercicio,
                    kind: kind,
                    model: devModel,
                    role: (origin === 'ia2' ? 'Controller Financiero / CFO' : null)
                })
            });

            const startData = await startResp.json();

            if (startData.status !== 'pending' && startData.status !== 'success') {
                throw new Error(startData.message || "Error iniciando generación");
            }

            const reqId = startData.request_id || startData.saved_id; // Support mixed returns if any

            // Step 3.2: Polling Loop
            let finalHtml = null;
            let finalData = null;

            const pollInterval = 2000; // 2 seconds
            let attempts = 0;
            const maxAttempts = 360; // ~12 minutes

            while (attempts < maxAttempts) {
                await new Promise(r => setTimeout(r, pollInterval));
                attempts++;

                try {
                    const pollResp = await fetch(`/api/ai/report/progress/${reqId}`);
                    const pollData = await pollResp.json();

                    if (pollData.status === 'ok') {
                        // Check if result is ready (Top level 'result' from improved API)
                        if (pollData.result) {
                            finalData = pollData.result;
                            finalHtml = finalData.html;
                            break; // DONE!
                        }

                        // Optional: Update loading text with latest event
                        if (pollData.events && pollData.events.length > 0) {
                            const lastEv = pollData.events[pollData.events.length - 1];
                            if (lastEv.message) statusText.innerText = lastEv.message;
                            if (lastEv.status === 'error') throw new Error(lastEv.error || "Error en proceso backend");
                        }
                    }
                } catch (pollErr) {
                    console.warn("Polling glitch:", pollErr);
                    // Don't break on temporary network glitch, just retry
                }
            }

            if (!finalData || !finalHtml) {
                throw new Error("Timeout: El servidor tardó demasiado en responder (Polling Exceeded)");
            }

            try { clearTimeout(AIReportManager._abortTimer); } catch (_) { }
            try { clearTimeout(AIReportManager._safetyTimer); } catch (_) { }

            // 4. Wait for mimimum animation time (e.g. 4 seconds) - Optional clean up
            clearInterval(interval);
            try { clearInterval(AIReportManager._timerTick); } catch (_) { }

            // Show Result
            processingView.style.display = 'none';
            resultView.style.display = 'block';
            resultView.innerHTML = finalHtml;
            document.body.classList.remove('ai-processing'); // Stop spinning border

            // Persist last report metadata for Save
            AIReportManager.lastHtml = finalHtml || '';
            AIReportManager.lastKind = kind;
            AIReportManager.lastModelUsed = finalData.model_used || '';
            AIReportManager.lastRawData = finalData.raw_data || {};
            AIReportManager.lastOrigin = origin || 'ia-general';

            // Meta badge: Context source & model used
            try {
                const meta = document.createElement('div');
                meta.style.color = '#a1a1aa';
                meta.style.fontSize = '0.8rem';
                meta.style.margin = '8px 0';
                const reason = finalData.reason || '—';
                const req = finalData.requested_model || '—';
                const used = finalData.model_used || '—';
                meta.innerText = `Contexto: ${finalData.context_source || '—'} • Modelo solicitado: ${req} • Usado: ${used} • Motivo: ${reason}`;
                resultView.appendChild(meta);
            } catch (_) { }

            try {
                const raw = finalData.raw_data || {};
                const kpis = raw.kpis || raw.kpis_globales || {};
                const señales = raw['señales'] || {};
                const productosNeg = Array.isArray(raw['productos_negativos']) ? raw['productos_negativos'] : [];
                const clientesRiesgo = Array.isArray(raw['clientes_riesgo']) ? raw['clientes_riesgo'] : [];
                const pareto = raw['pareto'] || {};

                const margenPct = (typeof (kpis.margen_beneficio_pct ?? kpis.margen_op_pct) === 'number')
                    ? (kpis.margen_beneficio_pct ?? kpis.margen_op_pct)
                    : (señales.margen_pct ?? 0);
                const prodNegCount = Number.isFinite(señales.productos_negativos_count) ? señales.productos_negativos_count : productosNeg.length;
                const cliRiskCount = Number.isFinite(señales.clientes_riesgo_count) ? señales.clientes_riesgo_count : clientesRiesgo.length;
                const concPct = Number.isFinite(señales.concentracion_pct) ? señales.concentracion_pct : (pareto.top_share_pct ?? 0);
                const mesesYoyCaida = Number.isFinite(señales.meses_yoy_caida) ? señales.meses_yoy_caida : 0;

                const topProds = productosNeg.slice(0, 3).map(p => (p.nombre || p.articulo || '—')).join(', ');
                const topClients = clientesRiesgo.slice(0, 3).map(c => (c.nombre || c.cliente || '—')).join(', ');

                const evidence = document.createElement('div');
                evidence.className = 'ai-report-section ai-evidence-section';
                evidence.innerHTML = `
                    <h3><i class="fas fa-chart-line"></i> Evidencia cuantitativa</h3>
                    <ul class="ai-evidence-list">
                        <li>Margen medio: <b>${(Number.isFinite(margenPct) ? margenPct.toFixed(2) : '—')}%</b></li>
                        <li>Productos con margen negativo: <b>${prodNegCount}</b>${topProds ? ' (top: ' + topProds + ')' : ''}</li>
                        <li>Clientes en riesgo: <b>${cliRiskCount}</b>${topClients ? ' (top: ' + topClients + ')' : ''}</li>
                        <li>Concentración de ventas (top clientes): <b>${(Number.isFinite(concPct) ? concPct.toFixed(2) : '—')}%</b></li>
                        <li>Meses con caída interanual (YoY): <b>${(Number.isFinite(mesesYoyCaida) ? mesesYoyCaida : '—')}</b></li>
                    </ul>
                `;
                resultView.appendChild(evidence);
            } catch (_) { }

            // Append Actions (Saved Indicator + PDF)
            const actions = document.createElement('div');
            actions.style.display = 'flex';
            actions.style.justifyContent = 'flex-end';
            actions.style.alignItems = 'center';
            actions.style.gap = '10px';
            actions.style.marginTop = '15px';

            let savedHtml = '';
            // Backend Auto-Saves now, assume saved if success
            if (finalData.status === 'success') {
                savedHtml = `<span style="color:#4ade80; font-size:0.8rem; margin-right:auto;"><i class="fas fa-check-circle"></i> Guardado automático</span>`;
            }

            actions.innerHTML = `
                ${savedHtml}
                <button class="btn-glow" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.downloadPDF(this)">
                    <i class="fas fa-file-pdf"></i> Descargar PDF
                </button>
                <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem; border-color:#8b5cf6; color:#e2e8f0;" onclick="AIReportManager.generateNotebookLmPodcast(this)">
                    <i class="fas fa-headphones"></i> Podcast NotebookLM
                </button>
                <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.close()">
                    Cerrar
                </button>
            `;
            resultView.appendChild(actions);
            try { if (window.VOA && typeof window.VOA.notify === 'function') window.VOA.notify('AI_REPORT_COMPLETED', { kind: kind }); } catch (_) { }

        } catch (error) {
            clearInterval(interval);
            try { clearInterval(AIReportManager._timerTick); } catch (_) { }
            try { clearTimeout(AIReportManager._abortTimer); } catch (_) { }
            try { clearTimeout(AIReportManager._safetyTimer); } catch (_) { } // Ensure clear safety timer in catch block too

            this.showError(error.message);
        }
    }

    // --- UI Helpers (Carousel & Messages) ---
    static async loadStatusMessages() {
        // Try to fetch from JSON if available, else static
        // Simulating async for compatibility
        return {
            slides: [
                { text: "Conectando con motor neuronal..." },
                { text: "Analizando tendencias de mercado..." },
                { text: "Contrastando KPIs financieros..." },
                { text: "Detectando anomalías en ventas..." },
                { text: "Redactando informe ejecutivo..." }
            ],
            intervalMs: 5000
        };
    }

    static initCarousel(slides, intervalMs) {
        const container = document.getElementById('ai-carousel-text');
        if (!container) return;

        let currentIndex = 0;
        let intervalId = null;
        let isPaused = false;

        const showSlide = (index) => {
            const slide = slides[index];
            // Simple fade out/in
            container.style.opacity = '0';
            setTimeout(() => {
                container.innerText = slide.text;
                container.style.opacity = '1';
            }, 300);
        };

        const nextSlide = () => {
            currentIndex = (currentIndex + 1) % slides.length;
            showSlide(currentIndex);
        };

        const prevSlide = () => {
            currentIndex = (currentIndex - 1 + slides.length) % slides.length;
            showSlide(currentIndex);
        };

        // Controls
        const btnNext = document.getElementById('ai-carousel-next');
        const btnPrev = document.getElementById('ai-carousel-prev');
        const btnPause = document.getElementById('ai-carousel-pause');

        if (btnNext) btnNext.onclick = (e) => { e.stopPropagation(); nextSlide(); restartInterval(); };
        if (btnPrev) btnPrev.onclick = (e) => { e.stopPropagation(); prevSlide(); restartInterval(); };
        if (btnPause) btnPause.onclick = (e) => {
            e.stopPropagation();
            isPaused = !isPaused;
            btnPause.innerHTML = isPaused ? '<i class="fas fa-play"></i>' : '<i class="fas fa-pause"></i>';
            if (isPaused) clearInterval(intervalId);
            else restartInterval();
        };

        const restartInterval = () => {
            if (intervalId) clearInterval(intervalId);
            if (!isPaused) intervalId = setInterval(nextSlide, intervalMs);
        };

        // Init
        showSlide(0);
        restartInterval();

        // Cleaner hook
        AIReportManager.__carouselCleaner = () => {
            if (intervalId) clearInterval(intervalId);
        };
    }

    // [NEW] PDF Download Handler
    static async downloadPDF(btnOrEvent) {
        let btn = null;
        try {
            if (btnOrEvent && typeof btnOrEvent.closest === 'function') {
                btn = btnOrEvent.closest('button');
            } else {
                const e = btnOrEvent || window.event;
                btn = e && e.target ? e.target.closest('button') : null;
            }
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando PDF...';
            }

            const payload = {
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                html: AIReportManager.lastPdfHtml || AIReportManager.lastHtml,
                title: "Informe Financiero Estratégico",
                raw_data: AIReportManager.lastRawData || {}
            };

            const response = await fetch('/api/ai/report/export/pdf', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify(payload)
            });

            const contentType = (response.headers.get('content-type') || '').toLowerCase();

            if (!response.ok) {
                let msg = 'No se pudo generar el PDF';
                try {
                    if (contentType.includes('application/json')) {
                        const j = await response.json();
                        msg = (j && (j.message || j.error)) ? String(j.message || j.error) : msg;
                    } else {
                        const t = await response.text();
                        msg = t ? String(t).slice(0, 200) : msg;
                    }
                } catch (_) {}
                if (typeof showToast === 'function') showToast('❌ ' + msg);
                if (btn) { btn.innerHTML = '<i class="fas fa-file-pdf"></i> Descargar PDF'; btn.disabled = false; }
                return;
            }

            if (contentType.includes('application/json') || contentType.includes('text/html')) {
                let msg = 'No se pudo generar el PDF';
                try {
                    const t = await response.text();
                    msg = t ? String(t).slice(0, 200) : msg;
                } catch (_) {}
                if (typeof showToast === 'function') showToast('❌ ' + msg, true);
                if (btn) { btn.innerHTML = '<i class="fas fa-file-pdf"></i> Descargar PDF'; btn.disabled = false; }
                return;
            }

            const buf = await response.arrayBuffer();
            try {
                const head = new TextDecoder('ascii').decode(buf.slice(0, 5));
                if (head !== '%PDF-') {
                    if (typeof showToast === 'function') showToast('❌ Respuesta inválida: no es un PDF', true);
                    if (btn) { btn.innerHTML = '<i class="fas fa-file-pdf"></i> Descargar PDF'; btn.disabled = false; }
                    return;
                }
            } catch (_) {}

            const blob = new Blob([buf], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const cd = response.headers.get('content-disposition') || '';
            const m = cd.match(/filename\*?=(?:UTF-8''|\"?)([^\";\n]+)\"?/i);
            const serverName = m ? decodeURIComponent(m[1]) : '';
            a.download = serverName || `Informe_Financiero_${currEmpresa}_${currEjercicio}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);
            if (btn) { btn.innerHTML = '<i class="fas fa-file-pdf"></i> Descargar PDF'; btn.disabled = false; }
        } catch (e) {
            console.error(e);
            if (typeof showToast === 'function') showToast('❌ Error generando PDF');
            if (btn) { btn.innerHTML = '<i class="fas fa-file-pdf"></i> Descargar PDF'; btn.disabled = false; }
        }
    }

    static async generateNotebookLmPodcast(btnOrEvent) {
        let btn = null;
        try {
            if (btnOrEvent && typeof btnOrEvent.closest === 'function') {
                btn = btnOrEvent.closest('button');
            } else {
                const e = btnOrEvent || window.event;
                btn = e && e.target ? e.target.closest('button') : null;
            }
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generando Podcast...';
            }

            const payload = {
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                html: AIReportManager.lastPdfHtml || AIReportManager.lastHtml,
                raw_data: AIReportManager.lastRawData || {}
            };

            const response = await fetch('/api/ai/notebooklm/podcast', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                let msg = 'Error conectando con NotebookLM';
                try {
                    const j = await response.json();
                    msg = (j && (j.message || j.error)) ? String(j.message || j.error) : msg;
                } catch (_) {}
                if (typeof showToast === 'function') showToast('❌ ' + msg, true);
            } else {
                const data = await response.json();
                if (typeof showToast === 'function') showToast('✅ Podcast generado. (Simulación MCP)', false);
                console.log("NotebookLM MCP Response:", data);
            }
        } catch (e) {
            console.error(e);
            if (typeof showToast === 'function') showToast('❌ Error de conexión MCP');
        } finally {
            if (btn) { 
                btn.innerHTML = '<i class="fas fa-headphones"></i> Podcast NotebookLM'; 
                btn.disabled = false; 
            }
        }
    }

    static async showInfografia(_btnOrEvent) {
        const overlay = document.getElementById('ai-report-overlay');
        const resultView = document.getElementById('ai-result-view');
        if (!overlay || !resultView) return;

        const empresa = (typeof currEmpresa !== 'undefined' ? currEmpresa : '');
        const ejercicio = (typeof currEjercicio !== 'undefined' ? currEjercicio : '');

        const rd = AIReportManager.lastRawData || {};
        const payload = (rd && rd.payload) ? rd.payload : {};
        const queryText = (rd && rd.query) ? rd.query : '';
        if (!payload || (typeof payload !== 'object')) {
            if (typeof showToast === 'function') showToast('❌ No hay datos para generar infografía', true);
            return;
        }

        try {
            const cssHref = '/static/css/infografia_story.css';
            let linkEl = document.querySelector('link[data-infografia="1"]');
            if (!linkEl) {
                linkEl = document.createElement('link');
                linkEl.rel = 'stylesheet';
                linkEl.href = cssHref;
                linkEl.setAttribute('data-infografia', '1');
                document.head.appendChild(linkEl);
            }
        } catch (_) { }

        try {
            const card = document.querySelector('#ai-report-overlay .ai-modal-card');
            const inner = document.querySelector('#ai-report-overlay .ai-modal-card-inner');
            if (overlay) { overlay.style.overflow = 'hidden'; }
            if (card) { card.style.width = '100%'; card.style.maxWidth = 'none'; card.style.minHeight = '100vh'; card.style.background = 'transparent'; card.style.border = 'none'; card.style.boxShadow = 'none'; card.style.padding = '0'; }
            if (inner) { inner.style.padding = '0'; inner.style.background = 'transparent'; }
            if (resultView) { resultView.style.width = '100vw'; resultView.style.height = '100vh'; resultView.style.maxHeight = '100vh'; resultView.style.padding = '0'; resultView.style.overflow = 'auto'; resultView.style.display = 'flex'; resultView.style.alignItems = 'flex-start'; resultView.style.justifyContent = 'center'; resultView.style.position = 'relative'; }
        } catch (_) {}

        let finalHtml = "";
        try {
            const res = await fetch(`/api/financial/infografia?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(ejercicio)}`);
            if (res.ok) {
                const dto = await res.json();
                if (dto && dto.status === "ok") {
                    finalHtml = AIReportManager._buildStoryHtml(dto);
                }
            }
        } catch (e) {
            console.warn("Infografía financiera no disponible, usando layout genérico:", e);
        }
        if (!finalHtml) {
            finalHtml = AIReportManager._buildUniversalInfografiaHtml({ empresa, ejercicio, queryText, payload });
        }

        resultView.innerHTML = finalHtml;
        resultView.style.overflow = 'auto';
        try { AIReportManager._renderProCharts(payload, resultView); } catch (_) { }
        try { AIReportManager._fitInfografiaToViewport(); window.addEventListener('resize', AIReportManager._fitInfografiaToViewport); } catch (_) {}

        AIReportManager.lastHtml = finalHtml || '';
        AIReportManager.lastPdfHtml = finalHtml || '';
        AIReportManager.lastOrigin = (AIReportManager.lastOrigin || '') + ':infografia';
        try {
            if (typeof showToast === 'function') showToast('✅ Infografía generada', false);
        } catch (_) { }
    }

    static _buildUniversalInfografiaHtml(ctx) {
        const empresa = ctx.empresa || '';
        const ejercicio = ctx.ejercicio || '';
        const queryText = ctx.queryText || '';
        const payload = ctx.payload || {};

        const title = (payload && (payload.title || payload.key)) ? String(payload.title || payload.key) : 'Infografía';
        const answerText = (payload && (payload.text || payload.html)) ? String(payload.text || payload.html) : '';
        const isHtml = AIReportManager._looksLikeHtml(answerText);
        const summaryBlock = isHtml ? answerText : `<p>${AIReportManager._escapeHtml(answerText).replace(/\n/g, '<br>')}</p>`;

        const kpis = Array.isArray(payload.kpis) ? payload.kpis : [];
        const kpiCards = kpis.length ? `
            <div class="story-kpi-cards">
                ${kpis.slice(0, 6).map(k => {
                    const lab = AIReportManager._escapeHtml(String(k.label || 'KPI'));
                    const val = (k.value === null || k.value === undefined) ? '' : String(k.value);
                    return `<div class="story-kpi"><div class="val">${AIReportManager._escapeHtml(val)}</div><div class="label">${lab}</div></div>`;
                }).join('')}
            </div>` : '';

        const table = (payload.table && typeof payload.table === 'object') ? payload.table : null;
        const tCols = (table && Array.isArray(table.columns)) ? table.columns : [];
        const tRows = (table && Array.isArray(table.rows)) ? table.rows : [];
        const tableHtml = (tCols.length && tRows.length) ? (() => {
            const head = tCols.slice(0, 8).map(c => `<th>${AIReportManager._escapeHtml(c)}</th>`).join('');
            const body = tRows.slice(0, 12).map(r => {
                const cells = (r || []).slice(0, 8).map((cell, idx) => {
                    const col = (tCols[idx] || '').toString();
                    const f = AIReportManager._formatValueForColumn(col, cell);
                    return `<td>${AIReportManager._escapeHtml(f.text)}</td>`;
                }).join('');
                return `<tr>${cells}</tr>`;
            }).join('');
            const tt = AIReportManager._escapeHtml(String(table.title || 'Detalle'));
            return `<div class="inf-section"><h2>${tt}</h2><table border="1" cellpadding="4" cellspacing="0">${head ? `<thead><tr>${head}</tr></thead>` : ''}<tbody>${body}</tbody></table></div>`;
        })() : '';

        const chartsHtml = `
            <div class="inf-section">
                <h2>Gráficas</h2>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div id="ai-pro-chart-main" style="min-height:260px;"></div>
                    <div id="ai-pro-chart-secondary" style="min-height:260px;"></div>
                </div>
            </div>`;

        const header = `
            <section class="story-banner">
                <div class="story-banner-chips">
                    <span class="chip">${AIReportManager._escapeHtml(title)}</span>
                    <span class="chip">Empresa ${AIReportManager._escapeHtml(String(empresa))}</span>
                    <span class="chip">Ejercicio ${AIReportManager._escapeHtml(String(ejercicio))}</span>
                </div>
            </section>`;

        const q = queryText ? `<div class="inf-section"><h2>Consulta</h2><div>${AIReportManager._escapeHtml(String(queryText))}</div></div>` : '';
        const resumen = `<div class="inf-section"><h2>Resumen</h2>${summaryBlock || '<p>—</p>'}</div>`;

        return `<div class="infografia-root"><div class="infografia-card">${header}${q}${kpiCards}${resumen}${tableHtml}${chartsHtml}</div></div>`;
    }

    static saveReport() {
        // Legacy manual save if needed, but auto-save is preferred now.
        // Keeping logic just in case user wants to force re-save or legacy flows.
        AIReportManager.saveReportLegacy();
    }

    static async saveReportLegacy() {
        // ... (Original Save Logic moved here if needed, or simplified) ... 
        try {
            const payload = {
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                kind: AIReportManager.lastKind || 'ventas',
                origin: AIReportManager.lastOrigin || 'ia-general',
                html: AIReportManager.lastHtml || '',
                model_used: AIReportManager.lastModelUsed || '',
                raw_data: AIReportManager.lastRawData || {}
            };
            const res = await fetch('/api/ai/report/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify(payload)
            });
        } catch (e) { }
    }

    static showError(msg) {
        const processingView = document.getElementById('ai-thinking-view');
        const resultView = document.getElementById('ai-result-view');
        processingView.style.display = 'none';
        resultView.style.display = 'block';
        resultView.innerHTML = `
            <div style="text-align:center; color:#ef4444; padding:20px;">
                <h3 style="margin-bottom:10px;">❌ Error de Análisis</h3>
                <p>${msg}</p>
                <button onclick="AIReportManager.close()" class="btn-secondary" style="margin-top:20px;">Cerrar</button>
            </div>
        `;
        document.body.classList.remove('ai-processing');
    }

    static close() {
        const overlay = document.getElementById('ai-report-overlay');
        overlay.style.display = 'none';
        document.body.classList.remove('ai-processing');
        try {
            document.documentElement.style.overflow = '';
            document.documentElement.style.height = '';
            document.body.style.overflow = '';
            document.body.style.height = '';
            document.body.style.position = '';
            document.body.style.width = '';
        } catch (_) {}
        if (AIReportManager.__carouselCleaner) {
            try { AIReportManager.__carouselCleaner(); } catch (_) { }
            AIReportManager.__carouselCleaner = null;
        }
        try { clearInterval(AIReportManager._timerTick); } catch (_) { }
        AIReportManager._timerTick = null;
        try { clearTimeout(AIReportManager._abortTimer); } catch (_) { }
        AIReportManager._abortTimer = null;
        try { clearTimeout(AIReportManager._safetyTimer); } catch (_) { }
        AIReportManager._safetyTimer = null;
        AIReportManager.detachKeyboardControls();
    }

    static showSavedReport(html, kind = 'ventas', origin = 'ia-general') {
        const overlay = document.getElementById('ai-report-overlay');
        const processingView = document.getElementById('ai-thinking-view');
        const resultView = document.getElementById('ai-result-view');
        if (!overlay || !processingView || !resultView) return;

        // Show overlay and render saved HTML
        overlay.style.display = 'flex';
        processingView.style.display = 'none';
        resultView.style.display = 'block';
        resultView.innerHTML = html || '<div style="color:#a1a1aa;">(Informe vacío)</div>';

        // Persist metadata for potential future actions
        AIReportManager.lastHtml = html || '';
        AIReportManager.lastKind = kind || 'ventas';
        AIReportManager.lastOrigin = origin || 'ia-general';

        // Minimal actions: PDF + Clone
        const actions = document.createElement('div');
        actions.style.display = 'flex';
        actions.style.justifyContent = 'flex-end';
        actions.style.gap = '10px';
        actions.style.marginTop = '15px';
        actions.innerHTML = `
            <span style="color:#a1a1aa; font-size:0.8rem; margin-right:auto;">Origen: ${origin} • Tipo: ${kind} (Histórico)</span>
            <button class="btn-glow" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.downloadPDF(this)">
                <i class="fas fa-file-pdf"></i> Descargar PDF
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem; border-color:#38bdf8; color:#e2e8f0;" onclick="AIReportManager.showInfografia(this)">
                <i class="fas fa-chart-area"></i> Infografía
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem; border-color:#8b5cf6; color:#e2e8f0;" onclick="AIReportManager.generateNotebookLmPodcast(this)">
                <i class="fas fa-headphones"></i> Podcast NotebookLM
            </button>
            <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.close()">
                Cerrar
            </button>
        `;
        resultView.appendChild(actions);
    }

    static async executeQuery(queryText) {
        const overlay = document.getElementById('ai-report-overlay');
        const processingView = document.getElementById('ai-thinking-view');
        const resultView = document.getElementById('ai-result-view');
        const statusText = document.getElementById('ai-thinking-text');
        overlay.style.display = 'flex';
        processingView.style.display = 'flex';
        resultView.style.display = 'none';
        resultView.innerHTML = '';
        statusText.innerText = "Generando código de consulta...";
        try {
            const resp = await fetch('/api/ai/query/execute', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF_TOKEN },
                body: JSON.stringify({ empresa: currEmpresa, ejercicio: currEjercicio, query_text: queryText })
            });
            const data = await resp.json();
            if (!resp.ok || data.status !== 'success') {
                throw new Error(data.message || 'Error ejecutando consulta IA');
            }
            processingView.style.display = 'none';
            resultView.style.display = 'block';
            const section = document.createElement('div');
            section.className = 'ai-report-section ai-code-section';
            const code = document.createElement('pre');
            code.className = 'ai-code-block';
            code.innerText = JSON.stringify(data.dsl || {}, null, 2);
            const meta = document.createElement('div');
            meta.className = 'ai-code-meta';
            meta.innerText = `Resultado persistido: ${data.path || '—'} • Registros: ${data.count ?? '—'}`;
            section.innerHTML = `<h3><i class="fas fa-code"></i> Código de consulta IA</h3>`;
            section.appendChild(code);
            section.appendChild(meta);
            try {
                const hints = (data.dsl && data.dsl._hints) ? data.dsl._hints : null;
                if (hints) {
                    const hv = document.createElement('div');
                    hv.className = 'ai-code-meta';
                    const srcs = Array.isArray(hints.recommended_sources) ? hints.recommended_sources.join(', ') : '—';
                    const flds = Array.isArray(hints.recommended_fields) ? hints.recommended_fields.slice(0, 8).join(', ') : '—';
                    hv.innerHTML = `<div style="margin-top:8px; color:#a1a1aa;">
                        <b>Contexto vectorial</b> • Fuentes: ${srcs} • Columnas: ${flds}
                    </div>`;
                    section.appendChild(hv);
                }
            } catch (_) {}
            resultView.appendChild(section);
            const actions = document.createElement('div');
            actions.style.display = 'flex';
            actions.style.justifyContent = 'flex-end';
            actions.style.alignItems = 'center';
            actions.style.gap = '10px';
            actions.style.marginTop = '15px';
            actions.innerHTML = `
                <button class="btn-secondary" style="padding:6px 12px; font-size:0.8rem;" onclick="AIReportManager.close()">
                    Cerrar
                </button>
            `;
            resultView.appendChild(actions);
        } catch (e) {
            processingView.style.display = 'none';
            resultView.style.display = 'block';
            resultView.innerHTML = `<div class="ai-report-section"><h3>Error</h3><p>${e.message}</p></div>`;
        }
    }

    static _buildInfografiaHtml(dto) {
        const k = dto.kpis || {};
        const t = dto.trimestres || {};
        const v = t.ventas || {};
        const m = t.margen_pct || {};
        const e = t.ebitda || {};
        const prods = Array.isArray(dto.productos_top) ? dto.productos_top : [];
        const fin = dto.raw_fin || {};
        const ven = dto.raw_ventas || {};
        let logoSrc = '';
        try {
            const headerLogo = document.getElementById('header-datia-logo');
            if (headerLogo && headerLogo.src) logoSrc = headerLogo.src;
            if (!logoSrc) {
                const savedLogo = localStorage.getItem('datia-selected-logo');
                if (savedLogo) logoSrc = savedLogo;
            }
        } catch (_) {}
        const dateStr = new Date().toLocaleDateString('es-ES', { year: 'numeric', month: 'long', day: '2-digit' });
        const header = `
            <div class="inf-header">
                <div style="display:flex;align-items:center;gap:10px;">
                    ${logoSrc ? `<img src="${logoSrc}" alt="Logo" class="inf-brand-logo">` : ''}
                    <div>
                        <h1>Informe Financiero ${dto.ejercicio}</h1>
                        <div class="inf-subtitle">Basado en JSON de contexto • ${dateStr}</div>
                    </div>
                </div>
            </div>`;
        const kpis = `
            <div class='inf-kpi-grid'>
                <div class='inf-kpi'><div class='inf-kpi-val'>${Number(k.ventas_totales || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div><div class='inf-kpi-label'>Ventas Totales</div></div>
                <div class='inf-kpi'><div class='inf-kpi-val'>${Number(k.yoy_pct_global || 0).toFixed(2)} %</div><div class='inf-kpi-label'>Crecimiento YoY</div></div>
                <div class='inf-kpi'><div class='inf-kpi-val'>${Number(k.solvencia || 0).toFixed(2)}</div><div class='inf-kpi-label'>Ratio de Solvencia</div></div>
                <div class='inf-kpi'><div class='inf-kpi-val'>${Number(k.margen_op_pct || 0).toFixed(2)} %</div><div class='inf-kpi-label'>Margen Operativo</div></div>
            </div>`;
        const q = ['Q1','Q2','Q3','Q4'];
        const quarters = `
            <div class='inf-section'><h2>Resultados Trimestrales</h2>
            <div class='inf-quarter-grid'>
                ${q.map(qi => `
                    <div class='inf-quarter'>
                        <div class='inf-q-title'>${qi}</div>
                        <div class='inf-q-line'>Ventas: ${Number(v[qi] ?? 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                        <div class='inf-q-line'>Margen: ${Number(m[qi] ?? 0).toFixed(2)} %</div>
                        <div class='inf-q-line'>EBITDA: ${Number(e[qi] ?? 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                    </div>
                `).join('')}
            </div></div>`;
        let prod = '';
        if (prods.length) {
            prod = `
                <div class='inf-section'><h2>Rendimiento por Producto</h2>
                <div class='inf-product-grid'>
                    ${prods.map(p => `
                        <div class='inf-product'><div class='inf-prod-name'>${p.nombre}</div><div class='inf-prod-val'>${Number(p.ingresos || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div></div>
                    `).join('')}
                </div></div>`;
        }
        // Balance de situación
        const bal = fin.balance_situacion || {};
        const balHtml = `
            <div class='inf-section'><h2>Balance de Situación</h2>
                <div class='inf-table'>
                    <div class='inf-row'><div class='inf-cell inf-label'>Activo total</div><div class='inf-cell inf-value'>${Number((bal.totales||{}).activo || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div></div>
                    <div class='inf-row'><div class='inf-cell inf-label'>Pasivo total</div><div class='inf-cell inf-value'>${Number((bal.totales||{}).pasivo || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div></div>
                    <div class='inf-row'><div class='inf-cell inf-label'>Patrimonio neto</div><div class='inf-cell inf-value'>${Number((bal.totales||{}).patrimonio || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div></div>
                    <div class='inf-row'><div class='inf-cell inf-label'>Liquidez</div><div class='inf-cell inf-value'>${Number((bal.ratios||{}).liquidez || 0).toFixed(2)}</div></div>
                    <div class='inf-row'><div class='inf-cell inf-label'>Solvencia</div><div class='inf-cell inf-value'>${Number((bal.ratios||{}).solvencia || 0).toFixed(2)}</div></div>
                    <div class='inf-row'><div class='inf-cell inf-label'>Endeudamiento %</div><div class='inf-cell inf-value'>${Number((bal.ratios||{}).endeudamiento || 0).toFixed(2)} %</div></div>
                </div>
            </div>`;
        // Tesorería
        const tes = fin.tesoreria || {};
        const paretoV = ven.pareto || {};
        const cliRisk = Array.isArray(ven.clientes_riesgo) ? ven.clientes_riesgo : [];
        const prodNeg = Array.isArray(ven.productos_negativos) ? ven.productos_negativos : [];
        const insightsHtml = `
            <div class='inf-section'><h2>Análisis Ejecutivo</h2>
                <div class='inf-chip-grid'>
                    <div class='inf-chip ${Number(k.yoy_pct_global||0) < 0 ? 'inf-chip-warn':''}'>YoY: ${Number(k.yoy_pct_global||0).toFixed(2)} %</div>
                    <div class='inf-chip ${tes.tension_liquidez_detectada ? 'inf-chip-warn':''}'>Liquidez: ${tes.tension_liquidez_detectada ? 'Tensión':'OK'}</div>
                    ${paretoV.top_share_pct !== undefined ? `<div class='inf-chip ${Number(paretoV.top_share_pct||0) > 60 ? 'inf-chip-warn':''}'>Concentración: ${Number(paretoV.top_share_pct||0).toFixed(2)} %</div>` : ''}
                    <div class='inf-chip ${cliRisk.length > 0 ? 'inf-chip-warn':''}'>Clientes riesgo: ${cliRisk.length}</div>
                    <div class='inf-chip ${prodNeg.length > 0 ? 'inf-chip-warn':''}'>Productos negativos: ${prodNeg.length}</div>
                </div>
            </div>`;
        const tesHtml = `
            <div class='inf-section'><h2>Tesorería</h2>
                <div class='inf-chip-grid'>
                    <div class='inf-chip'>Disponible: ${Number(tes.disponible || tes.disponible_actual || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                    <div class='inf-chip'>Fondo Maniobra: ${Number(tes.fondo_maniobra || 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                    <div class='inf-chip'>DSO: ${Number(tes.dso || 0).toFixed(0)} días</div>
                    <div class='inf-chip'>DPO: ${Number(tes.dpo || 0).toFixed(0)} días</div>
                    <div class='inf-chip ${tes.tension_liquidez_detectada ? 'inf-chip-warn':''}'>Tensión Liquidez: ${tes.tension_liquidez_detectada ? 'Sí':'No'}</div>
                </div>
            </div>`;
        // Tendencias y Anomalías
        const ta = fin.tendencias_anomalias || {};
        const anoms = Array.isArray(ta.anomalias_detectadas) ? ta.anomalias_detectadas : [];
        const recs = Array.isArray(ta.recomendaciones_algoritmicas) ? ta.recomendaciones_algoritmicas : [];
        const taHtml = `
            <div class='inf-section'><h2>Tendencias y Anomalías</h2>
                <div class='inf-chip'>Dirección anual: ${ta.direccion_anual || 'estable'}</div>
                ${anoms.length ? `<ul class='inf-list'>${anoms.map(a => `<li>${a}</li>`).join('')}</ul>` : "<div class='inf-muted'>Sin anomalías detectadas</div>"}
                ${recs.length ? `<div class='inf-subhead'>Recomendaciones</div><ul class='inf-list'>${recs.map(r => `<li>${r}</li>`).join('')}</ul>` : ""}
            </div>`;
        // Estacionalidad (mensual)
        const est = Array.isArray(fin.estacionalidad) ? fin.estacionalidad : [];
        const meses = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];
        const estHtml = est.length ? `
            <div class='inf-section'><h2>Estacionalidad</h2>
                <div class='inf-table'>
                    ${est.map((x,i) => `
                        <div class='inf-row'><div class='inf-cell inf-label'>${meses[i] || ('Mes '+(x.mes||i+1))}</div><div class='inf-cell inf-value'>Share: ${Number(x.share_pct||0).toFixed(2)} %</div><div class='inf-cell inf-value'>YoY: ${Number(x.yoy_pct||0).toFixed(2)} %</div></div>
                    `).join('')}
                </div>
            </div>` : '';
        // P&L Análisis
        const pla = Array.isArray(fin.pl_analisis) ? fin.pl_analisis : [];
        const plHtml = pla.length ? `
            <div class='inf-section'><h2>P&L (Análisis)</h2>
                <div class='inf-table'>
                    <div class='inf-row inf-head'><div class='inf-cell inf-label'>Concepto</div><div class='inf-cell inf-value'>Real</div><div class='inf-cell inf-value'>Objetivo</div><div class='inf-cell inf-value'>Desviación</div><div class='inf-cell inf-value'>Desv. %</div></div>
                    ${pla.map(r => `
                        <div class='inf-row'><div class='inf-cell inf-label'>${r.concepto}</div><div class='inf-cell inf-value'>${Number(r.real||0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div><div class='inf-cell inf-value'>${Number(r.objetivo||0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div><div class='inf-cell inf-value'>${Number(r.desviacion_importe||0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div><div class='inf-cell inf-value'>${Number(r.desviacion_pct||0).toFixed(2)} %</div></div>
                    `).join('')}
                </div>
            </div>` : '';
        // Alertas del sistema
        const alerts = Array.isArray(fin.alertas_sistema) ? fin.alertas_sistema : [];
        const alHtml = alerts.length ? `
            <div class='inf-section'><h2>Alertas del Sistema</h2>
                <ul class='inf-list'>${alerts.map(a => `<li>${a}</li>`).join('')}</ul>
            </div>` : '';
        // Bloques comerciales (si hay ventas)
        let ventasHtml = '';
        if (ven && Object.keys(ven).length) {
            const topC = Array.isArray(ven.top_clientes) ? ven.top_clientes : [];
            const topP = Array.isArray(ven.top_productos) ? ven.top_productos : [];
            const negP = Array.isArray(ven.productos_negativos) ? ven.productos_negativos : [];
            const cliR = Array.isArray(ven.clientes_riesgo) ? ven.clientes_riesgo : [];
            const pareto = ven.pareto || {};
            const geo = Array.isArray(ven.geografia) ? ven.geografia : [];
            const evol = Array.isArray(ven.evolucion_mensual) ? ven.evolucion_mensual : [];
            const ticket = Array.isArray(ven.ticket_mensual) ? ven.ticket_mensual : [];
            ventasHtml = `
                <div class='inf-section'><h2>Ventas (Contexto)</h2>
                    ${topC.length ? `<div class='inf-subhead'>Top Clientes</div><div class='inf-table'>${topC.map(c => `<div class='inf-row'><div class='inf-cell inf-label'>${c.nombre}</div><div class='inf-cell inf-value'>${Number(c.volumen_compras||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div>`).join('')}</div>` : ''}
                    ${topP.length ? `<div class='inf-subhead'>Top Productos</div><div class='inf-table'>${topP.map(p => `<div class='inf-row'><div class='inf-cell inf-label'>${p.nombre}</div><div class='inf-cell inf-value'>${Number(p.ingresos_generados||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div>`).join('')}</div>` : ''}
                    ${negP.length ? `<div class='inf-subhead'>Productos con margen negativo</div><ul class='inf-list'>${negP.map(p => `<li>${p.nombre || p.articulo}: ${Number(p.margen||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</li>`).join('')}</ul>` : ''}
                    ${cliR.length ? `<div class='inf-subhead'>Clientes en riesgo</div><ul class='inf-list'>${cliR.map(c => `<li>${c.nombre || c.cliente}: YoY ${Number(c.yoy_pct||0).toFixed(2)} % • Peso ${Number(c.peso_pct||0).toFixed(2)} %</li>`).join('')}</ul>` : ''}
                    ${pareto.top_share_pct !== undefined ? `<div class='inf-chip-grid'><div class='inf-chip'>Concentración Top: ${Number(pareto.top_share_pct||0).toFixed(2)} %</div></div>` : ''}
                    ${geo.length ? `<div class='inf-subhead'>Geografía (Top CP)</div><div class='inf-table'>${geo.map(g => `<div class='inf-row'><div class='inf-cell inf-label'>${g.cod_postal}</div><div class='inf-cell inf-value'>${Number(g.ventas||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div>`).join('')}</div>` : ''}
                    ${evol.length ? `<div class='inf-subhead'>Evolución mensual</div><div class='inf-table'>${evol.map(r => `<div class='inf-row'><div class='inf-cell inf-label'>Mes ${r.mes}</div><div class='inf-cell inf-value'>Ventas ${Number(r.ventas||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} € • Margen ${Number(r.margen||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div>`).join('')}</div>` : ''}
                    ${ticket.length ? `<div class='inf-subhead'>Ticket mensual</div><div class='inf-table'>${ticket.map(r => `<div class='inf-row'><div class='inf-cell inf-label'>Mes ${r.mes}</div><div class='inf-cell inf-value'>${Number(r.ticket||0).toLocaleString('es-ES',{minimumFractionDigits:2,maximumFractionDigits:2})} €</div></div>`).join('')}</div>` : ''}
                </div>`;
        }
        const footer = `<div class='inf-footer'>Empresa ${dto.empresa} • ${dto.ejercicio} • Basado en ${dto.meta && dto.meta.fuentes_n ? dto.meta.fuentes_n : 1} fuente(s) • Origen: JSON</div>`;
        const metaInfo = fin.meta || {};
        const metaChips = `
            <div class='inf-chip-grid'>
                <div class='inf-chip'>Empresa: ${dto.empresa}</div>
                <div class='inf-chip'>Ejercicio: ${dto.ejercicio}</div>
                <div class='inf-chip'>Moneda: ${metaInfo.moneda || 'EUR'}</div>
                <div class='inf-chip'>Rol: ${metaInfo.rol || '—'}</div>
                <div class='inf-chip'>Modo: ${metaInfo.comparison_mode || '—'}</div>
            </div>`;
        const series = fin.series_mensuales || {};
        const sLabels = Array.isArray(series.labels) ? series.labels : [];
        const sIng = Array.isArray(series.ingresos) ? series.ingresos : [];
        const sGas = Array.isArray(series.gastos) ? series.gastos : [];
        const sEbi = Array.isArray(series.ebitda) ? series.ebitda : [];
        const sMar = Array.isArray(series.margen_pct) ? series.margen_pct : [];
        const monthsGrid = sLabels.length ? `
            <div class='inf-section'><h2>KPIs Mensuales</h2>
                <div class='inf-table'>
                    <div class='inf-row inf-head'><div class='inf-cell inf-label'>Mes</div><div class='inf-cell inf-value'>Ingresos</div><div class='inf-cell inf-value'>Gastos</div><div class='inf-cell inf-value'>EBITDA</div><div class='inf-cell inf-value'>Margen %</div></div>
                    ${sLabels.map((nm, i) => `
                        <div class='inf-row'>
                            <div class='inf-cell inf-label'>${nm}</div>
                            <div class='inf-cell inf-value'>${Number(sIng[i] ?? 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                            <div class='inf-cell inf-value'>${Number(sGas[i] ?? 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                            <div class='inf-cell inf-value'>${Number(sEbi[i] ?? 0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2})} €</div>
                            <div class='inf-cell inf-value'>${Number(sMar[i] ?? 0).toFixed(2)} %</div>
                        </div>
                    `).join('')}
                </div>
            </div>` : '';
        const mpct = Array.isArray(ven.margen_por_producto_pct) ? ven.margen_por_producto_pct : [];
        const mpctHtml = mpct.length ? `
            <div class='inf-section'><h2>Margen por Producto (%)</h2>
                <div class='inf-table'>
                    <div class='inf-row inf-head'><div class='inf-cell inf-label'>Producto</div><div class='inf-cell inf-value'>Share %</div></div>
                    ${mpct.map(x => `
                        <div class='inf-row'><div class='inf-cell inf-label'>${x.nombre}</div><div class='inf-cell inf-value'>${Number(x.share_pct||0).toFixed(2)} %</div></div>
                    `).join('')}
                </div>
            </div>` : '';
        const señales = fin['señales'] || {};
        const sigHtml = Object.keys(señales).length ? `
            <div class='inf-section'><h2>Señales Ejecutivas</h2>
                <div class='inf-chip-grid'>
                    ${Object.keys(señales).map(k => `<div class='inf-chip'>${k}: ${señales[k]}</div>`).join('')}
                </div>
            </div>` : '';
        return `<div class='infografia-root'><div class='infografia-card'>` + header + metaChips + insightsHtml + kpis + quarters + balHtml + tesHtml + taHtml + estHtml + monthsGrid + plHtml + alHtml + prod + mpctHtml + ventasHtml + sigHtml + footer + `</div></div>`;
    }

    static _buildStoryHtml(dto) {
        const k = dto.kpis || {};
        const fin = dto.raw_fin || {};
        const ven = dto.raw_ventas || {};
        const bal = fin.balance_situacion || {};
        const ratios = bal.ratios || {};
        const mesesSel = Array.isArray(fin.estacionalidad) ? fin.estacionalidad.slice(0,5) : [];
        const pla = Array.isArray(fin.pl_analisis) ? fin.pl_analisis : [];
        const fmtEur = (n) => Number(n||0).toLocaleString('es-ES', {minimumFractionDigits:2, maximumFractionDigits:2}) + ' €';
        const fmtPct = (n) => Number(n||0).toFixed(2) + ' %';
        const yoyGlobal = Number(k.yoy_pct_global || k.yoy_pct || 0);
        const trendTxt = !yoyGlobal ? '' : (yoyGlobal < 0 ? 'retrocede' : 'crece');
        const liqVal = Number(ratios.liquidez||0);
        const solVal = Number(ratios.solvencia||0);
        const liqBadge = liqVal >= 1.2 ? 'Liquidez holgada' : 'Liquidez en tensión';
        const solBadge = solVal >= 1.5 ? 'Solvencia fuerte' : 'Solvencia ajustada';
        const banner = `
            <section class='story-banner'>
                <div class='story-banner-chips'>
                    <span class='chip'>Liquidez ${ratios.liquidez > 1 ? 'OK' : 'Tensión'}</span>
                    <span class='chip'>Solvencia ${Number(ratios.solvencia||0).toFixed(2)} %</span>
                </div>
            </section>`;
        const mkGauge = (value, target, label) => {
            const v = Number(value||0);
            const t = Number(target||1);
            const ratio = Math.max(0, Math.min(1, t ? v / t : 0));
            const r = 36;
            const c = 2 * Math.PI * r;
            const dash = `${Math.round(ratio*c)} ${Math.round(c)}`;
            const valTxt = v.toFixed(2);
            return `
            <div class='gauge'>
                <svg viewBox='0 0 100 100' aria-label='${label}'>
                    <circle class='track' cx='50' cy='50' r='36'></circle>
                    <circle class='progress' cx='50' cy='50' r='36' style='stroke-dasharray:${dash};'></circle>
                </svg>
                <div>
                    <div class='g-val'>${valTxt}</div>
                    <div class='g-label'>${label} objetivo ${t.toFixed(2)}</div>
                </div>
            </div>`;
        };
        const gauges = `
            <section class='gauge-grid' aria-label='Indicadores ejecutivos'>
                ${mkGauge(ratios.liquidez, 1.20, 'Liquidez')}
                ${mkGauge(ratios.solvencia, 1.50, 'Solvencia')}
            </section>`;
        const execStory = `
            <section class="story-acts" aria-label="Resumen ejecutivo">
                <div class="story-act">
                    <div class="story-act-title">Resumen ejecutivo</div>
                    <div class="story-act-text">
                        Ventas totales ${fmtEur(k.ventas_totales)} con un margen operativo de ${fmtPct(k.margen_op_pct)} y EBITDA de ${fmtEur(k.ebitda)}.${trendTxt ? ' El negocio ' + trendTxt + ' ' + fmtPct(yoyGlobal) + ' frente al año anterior.' : ''}
                    </div>
                    <div class="story-act-chips">
                        <span class="story-act-chip">${liqBadge}</span>
                        <span class="story-act-chip">${solBadge}</span>
                    </div>
                </div>
            </section>`;
        const mkCup = (val, max, neg=false) => {
            const v = Math.abs(Number(val||0));
            const m = Math.max(1, Math.abs(Number(max||1)));
            const ratio = Math.max(0.05, Math.min(0.95, v/m));
            const h = Math.round(40 * ratio);
            const cls = neg ? 'story-cup-fill negative' : 'story-cup-fill positive';
            return `
            <svg class="story-svg" viewBox="0 0 120 80" role="img" aria-label="taza">
                <rect class="${cls}" x="20" y="${60-h}" width="60" height="${h}"></rect>
                <path class="story-cup-outline" d="M20,20 h60 v40 h-60 z"></path>
                <path class="story-cup-outline" d="M80,30 q25,0 25,15 q0,15 -25,15"></path>
            </svg>`;
        };
        const kpi = `
            <div class="story-kpi-cards">
                <div class="story-kpi" aria-label="Ventas Totales">
                    <div class="story-kpi-illustration">${mkCup(k.ventas_totales, Math.max(k.ventas_totales||1, 1))}</div>
                    <div class="val">${fmtEur(k.ventas_totales)}</div><div class="label">Ventas Totales</div>
                </div>
                <div class="story-kpi" aria-label="EBITDA">
                    <div class="story-kpi-illustration">${mkCup(k.ebitda, Math.max(Math.abs(k.ebitda||1), 1), Number(k.ebitda||0) < 0)}</div>
                    <div class="val">${fmtEur(k.ebitda)}</div><div class="label">EBITDA</div>
                </div>
                <div class="story-kpi" aria-label="Margen Operativo">
                    <div class="story-kpi-illustration">${mkCup(k.margen_op_pct, Math.max(Math.abs(k.margen_op_pct||10), 10), Number(k.margen_op_pct||0) < 0)}</div>
                    <div class="val">${fmtPct(k.margen_op_pct)}</div><div class="label">Margen Operativo</div>
                </div>
            </div>
            <div class="story-hint">Crecimiento y rentabilidad operativa en foco</div>`;
        const balance = `
            <section class="story-balance" aria-label="Solidez del balance y ratios">
              <div class="story-columns">
                <div class="story-column" aria-label="Solvencia"><h3 class="big">${Number(ratios.solvencia||0).toFixed(2)}</h3><p class="small">Solvencia</p></div>
                <div class="story-column" aria-label="Liquidez"><h3 class="big">${Number(ratios.liquidez||0).toFixed(2)}</h3><p class="small">Liquidez</p></div>
                <div class="story-column" aria-label="Patrimonio Neto"><h3 class="big">${fmtEur((bal.totales||{}).patrimonio)}</h3><p class="small">Patrimonio Neto</p></div>
              </div>
              <div class="story-chips"><span class="story-chip">Estado editorial</span></div>
            </section>`;
        const mesesMap = [
            {label:'Enero', idx:0},
            {label:'Abril', idx:3},
            {label:'Julio', idx:6},
            {label:'Octubre', idx:9},
            {label:'Diciembre', idx:11}
        ];
        const season = `
            <section class="story-season" aria-label="Estacionalidad y alertas estratégicas">
              <div class="story-season-grid">${
                mesesMap.map((mm,i) => {
                    const x = mesesSel[mm.idx] || {};
                    const cuota = (x.share_pct!==undefined) ? Number(x.share_pct).toFixed(2) : '—';
                    const yoy = (x.yoy_pct!==undefined) ? Number(x.yoy_pct).toFixed(2) : '—';
                    return `<div class='story-season-card'><div class='month'>${mm.label}</div><div class='kpis'>Cuota ${cuota} % • YoY ${yoy} %</div></div>`;
                }).join('')
              }</div>
            </section>`;
        const plHead = `<div class='row head'><div class='cell'>Concepto</div><div class='cell right'>Real</div><div class='cell right'>Objetivo</div><div class='cell right'>Desviación</div><div class='cell right'>Desv. %</div></div>`;
        const plRows = (pla.length ? pla.slice(0,6).map(r => `
            <div class='row'><div class='cell'>${r.concepto}</div><div class='cell right'>${fmtEur(r.real)}</div><div class='cell right'>${fmtEur(r.objetivo)}</div><div class='cell right'>${fmtEur(r.desviacion_importe)}</div><div class='cell right'>${Number(r.desviacion_pct||0).toFixed(2)} %</div></div>
        `).join('') : `
            <div class='row'><div class='cell'>VENTAS E INGRESOS</div><div class='cell right'>${fmtEur(k.ventas_totales)}</div><div class='cell right'>0,00 €</div><div class='cell right'>${fmtEur(k.ventas_totales)}</div><div class='cell right'>0,00 %</div></div>
            <div class='row'><div class='cell'>COMPRAS Y APROVISIONAMIENTOS</div><div class='cell right'>${fmtEur(k.compras_aprovisionamientos)}</div><div class='cell right'>0,00 €</div><div class='cell right'>${fmtEur(k.compras_aprovisionamientos)}</div><div class='cell right'>0,00 %</div></div>
            <div class='row'><div class='cell'>GASTOS DE PERSONAL</div><div class='cell right'>${fmtEur(k.gastos_personal)}</div><div class='cell right'>0,00 €</div><div class='cell right'>${fmtEur(k.gastos_personal)}</div><div class='cell right'>0,00 %</div></div>
            <div class='row'><div class='cell'>OTROS GASTOS DE EXPLOTACIÓN</div><div class='cell right'>${fmtEur(k.otros_gastos)}</div><div class='cell right'>0,00 €</div><div class='cell right'>${fmtEur(k.otros_gastos)}</div><div class='cell right'>0,00 %</div></div>
            <div class='row'><div class='cell'>RESULTADO FINANCIERO</div><div class='cell right'>${fmtEur(k.resultado_financiero)}</div><div class='cell right'>0,00 €</div><div class='cell right'>${fmtEur(k.resultado_financiero)}</div><div class='cell right'>0,00 %</div></div>
        `);
        const pl = `<section class='story-pl' aria-label='Cuenta de resultados'><div class='story-pl-table'>${plHead}${plRows}</div></section>`;
        const plBars = (() => {
            const rows = Array.isArray(pla) && pla.length ? pla.slice(0,6) : [
                {concepto:'VENTAS E INGRESOS', real:k.ventas_totales, objetivo:0},
                {concepto:'COMPRAS Y APROVISIONAMIENTOS', real:k.compras_aprovisionamientos, objetivo:0},
                {concepto:'GASTOS DE PERSONAL', real:k.gastos_personal, objetivo:0},
                {concepto:'OTROS GASTOS DE EXPLOTACIÓN', real:k.otros_gastos, objetivo:0},
                {concepto:'RESULTADO FINANCIERO', real:k.resultado_financiero, objetivo:0},
            ];
            const maxReal = Math.max(...rows.map(r => Math.abs(Number(r.real||0))), 1);
            const bars = rows.map(r => {
                const pct = Math.max(3, Math.round((Math.abs(Number(r.real||0))/maxReal)*100));
                return `<div class='pl-bar'><div class='name'>${r.concepto}</div><div class='bar'><div class='bar-fill' style='width:${pct}%;'></div></div><div class='val'>${fmtEur(r.real)}</div></div>`;
            }).join('');
            return `<section class='pl-bars' aria-label='Resumen gráfico P&L'>${bars}</section>`;
        })();
        const chips = `
            <section class='story-ops' aria-label='Ratios ampliados'>
                <div class='story-chips'>
                    <span class='story-chip'>Endeudamiento ${Number(ratios.endeudamiento||0).toFixed(2)}</span>
                    <span class='story-chip'>Fondo Maniobra ${fmtEur((fin.tesoreria||{}).fondo_maniobra)}</span>
                    <span class='story-chip'>Rotación Activos ${Number((fin.ratios||{}).rotacion_activos||0).toFixed(3)}</span>
                    <span class='story-chip'>Cobertura Intereses ${Number((fin.ratios||{}).cobertura_intereses||0).toFixed(3)}</span>
                    <span class='story-chip'>DSO/DIO/DPO ${Number((fin.tesoreria||{}).dso||0).toFixed(1)} / — / ${Number((fin.tesoreria||{}).dpo||0).toFixed(1)} días</span>
                </div>
            </section>`;
        const t = dto.trimestres || {};
        const vq = t.ventas || {};
        const mq = t.margen || t.margen_pct || {};
        const eq = t.ebitda || {};
        const yoy = t.ventas_yoy_pct || {};
        const qs = ['Q1','Q2','Q3','Q4'];
        const maxV = Math.max(...qs.map(q => Math.abs(Number(vq[q]||0))), 1);
        const maxE = Math.max(...qs.map(q => Math.abs(Number(eq[q]||0))), 1);
        const maxM = Math.max(...qs.map(q => Math.abs(Number(mq[q]||0))), 1);
        const trimes = `
            <section class='story-quarter' aria-label='Resultados Trimestrales'>
                <div class='story-quarter-grid'>
                    ${qs.map(q => {
                        const v = Number(vq[q]||0);
                        const ebi = Number(eq[q]||0);
                        const m = Number(mq[q]||0);
                        const yy = Number(yoy[q]||0);
                        const pv = Math.max(3, Math.round((Math.abs(v)/maxV)*100));
                        const pe = Math.max(3, Math.round((Math.abs(ebi)/maxE)*100));
                        const pm = Math.max(3, Math.round((Math.abs(m)/maxM)*100));
                        return `
                        <div class='story-quarter-card'>
                            <div class='q-title'>${q}</div>
                            <div class='q-line'>Ventas: ${fmtEur(v)}</div>
                            <div class='spark'><div class='spark-bar pos' style='width:${pv}%;'></div></div>
                            <div class='q-line'>Margen: ${fmtPct(m)}</div>
                            <div class='spark'><div class='spark-bar ${m<0?'neg':'pos'}' style='width:${pm}%;'></div></div>
                            <div class='q-line'>EBITDA: ${fmtEur(ebi)}</div>
                            <div class='spark'><div class='spark-bar ${ebi<0?'neg':'pos'}' style='width:${pe}%;'></div></div>
                            <div class='q-line'>YoY: ${fmtPct(yy)}</div>
                        </div>`;
                    }).join('')}
                </div>
            </section>`;
        const finRaw = dto.raw_fin || {};
        const series = finRaw.series_mensuales || {};
        const ing = series.ingresos || series.ventas || [];
        const ebi = series.ebitda || [];
        const mpct = series.margen_pct || [];
        const mkMini = (arr, useNeg=false) => {
            if (!Array.isArray(arr) || arr.length === 0) return "<div class='mini-spark'></div>";
            const vals = arr.map(v => Number(v||0));
            const max = Math.max(...vals.map(x => Math.abs(x)), 1);
            return `<div class='mini-spark'>` + vals.map(v => {
                const h = Math.max(3, Math.round((Math.abs(v)/max)*28));
                const cls = (useNeg && v<0) ? 'mini-bar neg' : 'mini-bar';
                return `<div class='${cls}' style='height:${h}px'></div>`;
            }).join('') + `</div>`;
        };
        const monthly = `
            <section class='story-monthly' aria-label='Series mensuales'>
                <div class='story-monthly-grid'>
                    <div class='monthly-card'><div class='monthly-title'>Ingresos</div>${mkMini(ing)}</div>
                    <div class='monthly-card'><div class='monthly-title'>EBITDA</div>${mkMini(ebi,true)}</div>
                    <div class='monthly-card'><div class='monthly-title'>Margen %</div>${mkMini(mpct,true)}</div>
                </div>
            </section>`;
        const topProds = Array.isArray(dto.productos_top) ? dto.productos_top.slice(0,3) : [];
        const salesTop = topProds.length ? `
            <section class='story-sales'>
                <div class='story-sales-top' aria-label='Top Productos'>
                    ${topProds.map(p => `<div>${p.nombre||'Producto'} — ${fmtEur(p.ingresos||0)}</div>`).join('')}
                </div>
            </section>` : ``;
        const ventasRaw = dto.raw_ventas || {};
        const topClientes = Array.isArray(ventasRaw.top_clientes) ? ventasRaw.top_clientes.slice(0,3) : [];
        const customersTop = topClientes.length ? `
            <section class='story-sales'>
                <div class='story-customers-top' aria-label='Top Clientes'>
                    ${topClientes.map(c => `<div>${c.nombre||'Cliente'} — ${fmtEur(c.volumen_compras||0)}</div>`).join('')}
                </div>
            </section>` : ``;
        const paretoPct = Number(((ventasRaw.pareto||{}).top_share_pct) || ((ventasRaw.señales||{}).concentracion_pct) || 0);
        const clientesRiesgoCount = Number(((ventasRaw.señales||{}).clientes_riesgo_count) || (Array.isArray(ventasRaw.clientes_riesgo)?ventasRaw.clientes_riesgo.length:0) || 0);
        const productosNegCount = Number(((ventasRaw.señales||{}).productos_negativos_count) || (Array.isArray(ventasRaw.productos_negativos)?ventasRaw.productos_negativos.length:0) || 0);
        const opsVentasChips = `
            <section class='story-ops' aria-label='Señales comerciales'>
                <div class='story-chips'>
                    <span class='story-chip ${paretoPct>60?'warn':''}'>Concentración Pareto ${paretoPct.toFixed(2)} %</span>
                    <span class='story-chip ${clientesRiesgoCount>0?'warn':''}'>Clientes riesgo ${clientesRiesgoCount}</span>
                    <span class='story-chip ${productosNegCount>0?'warn':''}'>Productos negativos ${productosNegCount}</span>
                </div>
            </section>`;
        const balRaw = finRaw.balance_situacion || {};
        const desg = balRaw.desglose || {};
        const act = desg.activo || {};
        const pas = desg.pasivo || {};
        const actCorr = Number(act.corriente||0), actNo = Number(act.no_corriente||0);
        const pasCorr = Number(pas.corriente||0), pasNo = Number(pas.no_corriente||0);
        const balDesg = (actCorr||actNo||pasCorr||pasNo) ? `
            <section class='story-ops' aria-label='Desglose Balance'>
                <div class='story-chips'>
                    <span class='story-chip'>Activo Corr. ${fmtEur(actCorr)}</span>
                    <span class='story-chip'>Activo No Corr. ${fmtEur(actNo)}</span>
                    <span class='story-chip'>Pasivo Corr. ${fmtEur(pasCorr)}</span>
                    <span class='story-chip'>Pasivo No Corr. ${fmtEur(pasNo)}</span>
                </div>
            </section>` : ``;
        const alerts = finRaw.alertas_sistema || finRaw.tendencias_anomalias || [];
        const alertsHtml = Array.isArray(alerts) && alerts.length ? `
            <section class='story-alerts' aria-label='Alertas del sistema'>
                ${alerts.slice(0,3).map(a => `<div class='story-alert'>${typeof a==='string'?a:(a.title||a.msg||'Alerta')}</div>`).join('')}
            </section>` : ``;
        const tes = fin.tesoreria || {};
        const dso = Number(tes.dso||tes.periodo_medio_cobro_dias||0);
        const dio = Number(tes.dio||tes.periodo_medio_almacenamiento_dias||0);
        const dpo = Number(tes.dpo||tes.periodo_medio_pago_dias||0);
        const ccc = (isNaN(dso)?0:dso) + (isNaN(dio)?0:dio) - (isNaN(dpo)?0:dpo);
        const gov = `
            <section class='story-govern' aria-label='Gobierno del desempeño'>
                <div class='gov-grid'>
                    <div class='gov-card'>
                        <div class='gov-title'>Caja (CCC)</div>
                        <div class='gov-desc'>Ciclo de conversión de efectivo</div>
                        <div class='gov-kpi'>DSO ${isNaN(dso)?'—':dso.toFixed(1)} • DIO ${isNaN(dio)?'—':dio.toFixed(1)} • DPO ${isNaN(dpo)?'—':dpo.toFixed(1)} • CCC ${ccc.toFixed(1)} días</div>
                        <span class='gov-chip ${ccc>45?'warn':''}'>Objetivo CCC ≤ 45 días</span>
                    </div>
                    <div class='gov-card'>
                        <div class='gov-title'>Rentabilidad</div>
                        <div class='gov-desc'>EBITDA y Margen Operativo</div>
                        <div class='gov-kpi'>EBITDA ${fmtEur(k.ebitda)} • Margen ${fmtPct(k.margen_op_pct)}</div>
                        <span class='gov-chip ${Number(k.ebitda||0)<0?'warn':''}'>Objetivo EBITDA ≥ 0</span>
                    </div>
                    <div class='gov-card'>
                        <div class='gov-title'>Solidez</div>
                        <div class='gov-desc'>Liquidez y Solvencia</div>
                        <div class='gov-kpi'>Liquidez ${Number(ratios.liquidez||0).toFixed(2)} • Solvencia ${Number(ratios.solvencia||0).toFixed(2)}</div>
                        <span class='gov-chip ${(Number(ratios.liquidez||0)<1.2||Number(ratios.solvencia||0)<1.5)?'warn':''}'>Objetivo L≥1,20 • S≥1,50</span>
                    </div>
                </div>
            </section>`;
        const headerBrand = `<div style='color:#71717a; font-size:12px;'>Empresa ${dto.empresa} • Ejercicio ${dto.ejercicio} • Origen JSON</div>`;
        const road = `
            <div class='story-road'>
                <svg class='story-road-svg' viewBox='0 0 600 64' aria-label='Camino editorial'>
                    <path class='road-path' d='M0,32 C120,10 240,50 360,20 C480,45 600,30 600,30'></path>
                    <ellipse class='coffee-bean' cx='60' cy='28' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='120' cy='36' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='180' cy='26' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='240' cy='42' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='300' cy='30' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='360' cy='40' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='420' cy='24' rx='6' ry='4'></ellipse>
                    <ellipse class='coffee-bean' cx='480' cy='36' rx='6' ry='4'></ellipse>
                </svg>
            </div>`;
        const doc = `
            <div class='story-root'>
              <div class='story-stage'>
              <main class='story-container'>
                <section class='story-hero'><div class='story-hero-content'><div class='story-hero-brand'><div class='story-brand-text'><h1 class='story-title'>Informe Financiero ${dto.ejercicio}</h1><p class='story-subtitle'>${headerBrand}</p><p class='story-claim'>Basado en JSON de contexto</p></div></div><div class='story-timeline'></div></div></section>
                ${banner}
                ${road}
                ${gauges}
                ${execStory}
                ${kpi}
                ${balance}
                ${season}
                ${pl}
                ${plBars}
                ${gov}
                ${monthly}
                ${salesTop}
                ${customersTop}
                ${opsVentasChips}
                ${balDesg}
                ${alertsHtml}
                <section class="story-acts">
                    <div class="story-act">
                        <div class="story-act-title">Contexto</div>
                        <div class="story-act-text">El ejercicio ${dto.ejercicio} cierra con ventas de ${fmtEur(k.ventas_totales)} y un margen operativo de ${fmtPct(k.margen_op_pct)}. El EBITDA asciende a ${fmtEur(k.ebitda)}.</div>
                        <div class="story-act-chips">
                            <span class="story-act-chip">Patrimonio Neto ${fmtEur((bal.totales||{}).patrimonio)}</span>
                            <span class="story-act-chip">Liquidez ${Number(ratios.liquidez||0).toFixed(2)}</span>
                            <span class="story-act-chip">Solvencia ${Number(ratios.solvencia||0).toFixed(2)}</span>
                        </div>
                    </div>
                    <div class="story-act">
                        <div class="story-act-title">Conflicto</div>
                        <div class="story-act-text">Se identifican factores que presionan la cuenta: ${Number(k.yoy_pct_global||0) < 0 ? 'caída interanual' : 'crecimiento moderado'} de ${fmtPct(k.yoy_pct_global)}, ${Number(ratios.liquidez||0) < 1.2 ? 'tensión de liquidez' : 'liquidez adecuada'} y focos de riesgo comercial.</div>
                        <div class="story-act-chips">
                            ${Number((ven.pareto||{}).top_share_pct||0) ? `<span class="story-act-chip ${Number((ven.pareto||{}).top_share_pct||0) > 60 ? 'warn':''}">Concentración ${fmtPct((ven.pareto||{}).top_share_pct)}</span>` : ''}
                            <span class="story-act-chip ${Array.isArray(ven.clientes_riesgo)&&ven.clientes_riesgo.length>0?'warn':''}">Clientes riesgo ${(Array.isArray(ven.clientes_riesgo)?ven.clientes_riesgo.length:0)}</span>
                            <span class="story-act-chip ${Array.isArray(ven.productos_negativos)&&ven.productos_negativos.length>0?'warn':''}">Productos negativos ${(Array.isArray(ven.productos_negativos)?ven.productos_negativos.length:0)}</span>
                            ${Number((fin.tesoreria||{}).dso||0) ? `<span class="story-act-chip ${Number((fin.tesoreria||{}).dso||0) > 45 ? 'warn':''}">DSO ${Number((fin.tesoreria||{}).dso||0).toFixed(0)} días</span>` : ''}
                        </div>
                    </div>
                    <div class="story-act">
                        <div class="story-act-title">Decisión</div>
                        <div class="story-act-text">Priorizar liquidez si ${Number(ratios.liquidez||0).toFixed(2)} < 1,20; diversificar cartera si concentración > 60%; revisar estructura de costes si el EBITDA es negativo; activar plan de cobro si DSO elevado.</div>
                        <div class="story-cta">
                            <button class="story-btn">Plan de acción CFO</button>
                        </div>
                    </div>
                    <div class="story-act">
                        <div class="story-act-title">Seguimiento</div>
                        <div class="story-act-text">Validar el impacto de las medidas con tres indicadores clave de control.</div>
                        <div class="story-act-chips">
                            <span class="story-act-chip ${((isNaN(ccc)?0:ccc)>45)?'warn':''}">CCC ${isNaN(ccc)?'—':ccc.toFixed(1)} ≤ 45</span>
                            <span class="story-act-chip ${Number(k.ebitda||0)<0?'warn':''}">EBITDA ${fmtEur(k.ebitda)} ≥ 0</span>
                            <span class="story-act-chip ${(Number(ratios.liquidez||0)<1.2||Number(ratios.solvencia||0)<1.5)?'warn':''}">L ${Number(ratios.liquidez||0).toFixed(2)} / S ${Number(ratios.solvencia||0).toFixed(2)}</span>
                        </div>
                    </div>
                </section>
                ${chips}
                ${trimes}
              </main>
              </div>
            </div>`;
        return doc;
    }
    static _fitInfografiaToViewport() {
        const rv = document.getElementById('ai-result-view');
        const card = rv && (rv.querySelector('.infografia-card') || rv.querySelector('.story-container'));
        if (!rv || !card) return;
        const stage = rv.querySelector('.story-stage');
        if (stage && card.classList.contains('story-container')) {
            try {
                const sw = stage.clientWidth;
                const cw = card.scrollWidth;
                if (!sw || !cw) return;
                let scale = 1;
                if (cw > sw) {
                    scale = sw / cw;
                    if (scale < 0.9) scale = 0.9;
                    card.style.transform = `scale(${scale})`;
                    card.style.transformOrigin = 'top center';
                } else {
                    card.style.transform = 'none';
                }
            } catch (_) {}
            return;
        }
        const vw = rv.clientWidth;
        const vh = rv.clientHeight;
        const cw = card.offsetWidth;
        const ch = card.offsetHeight;
        if (!cw || !ch) return;
        const scale = Math.min(vw / cw, vh / ch);
        card.style.transform = `scale(${scale})`;
        card.style.transformOrigin = 'top left';
    }


    static attachKeyboardControls() {
        try {
            if (AIReportManager._kbdHandler) return;
            const prev = () => {
                const btn = document.getElementById('ai-carousel-prev');
                if (btn) btn.click();
            };
            const next = () => {
                const btn = document.getElementById('ai-carousel-next');
                if (btn) btn.click();
            };
            const toggle = () => {
                const btn = document.getElementById('ai-carousel-pause');
                if (btn) btn.click();
            };
            AIReportManager._kbdHandler = function (e) {
                if (!document.getElementById('ai-thinking-view')) return;
                if (e.key === 'ArrowLeft') { e.preventDefault(); prev(); }
                else if (e.key === 'ArrowRight') { e.preventDefault(); next(); }
                else if (e.key === ' ') { e.preventDefault(); toggle(); }
            };
            document.addEventListener('keydown', AIReportManager._kbdHandler);
        } catch (_) { }
    }
    static detachKeyboardControls() {
        try {
            if (AIReportManager._kbdHandler) {
                document.removeEventListener('keydown', AIReportManager._kbdHandler);
                AIReportManager._kbdHandler = null;
            }
        } catch (_) { }
    }
}
