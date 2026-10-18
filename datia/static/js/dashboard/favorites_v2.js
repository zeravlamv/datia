(function () {
    function createStarButton(key, initialActive) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'act-fav-btn' + (initialActive ? '' : ' inactive');
        btn.setAttribute('data-key', key);
        btn.setAttribute('aria-pressed', initialActive ? 'true' : 'false');
        btn.title = initialActive ? 'Añadido a Pestaña Personal' : 'Añadir a Pestaña Personal';
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" fill="currentColor"/></svg>';
        btn.onclick = async function (e) {
            try { e.preventDefault(); e.stopPropagation(); } catch (_) { }
            var favs = FavoriteStore.getFavorites();
            var isActive = favs.indexOf(key) >= 0;
            var nextActive = !isActive;
            StarInjector.setStarActive(key, nextActive);
            try { await FavoriteStore.toggle(key); } catch (_) { }
        };
        return btn;
    }
    function fmtMoney(n) {
        try {
            return new Intl.NumberFormat((window.APP_LANG || 'es-ES'), { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n || 0));
        } catch (e) { return Number(n || 0).toFixed(2); }
    }
    function fmtPlain(n) {
        try {
            return new Intl.NumberFormat((window.APP_LANG || 'es-ES'), { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n || 0));
        } catch (e) { return Number(n || 0).toFixed(2); }
    }
    function getParam(name) {
        try {
            var v = new URLSearchParams(window.location.search).get(name);
            if (v) return v;
        } catch (_) { }
        if (name === 'empresa') return typeof currEmpresa !== 'undefined' ? currEmpresa : '';
        if (name === 'ejercicio') return typeof currEjercicio !== 'undefined' ? currEjercicio : '';
        return '';
    }
    var WidgetRegistry = {
        map: {},
        list: [
            { key: 'sales_1d', type: 'sales', period: '1d', domId: 'val-sales-1d', origin: 'ventas' },
            { key: 'sales_7d', type: 'sales', period: '7d', domId: 'val-sales-7d', origin: 'ventas' },
            { key: 'sales_30d', type: 'sales', period: '30d', domId: 'val-sales-30d', origin: 'ventas' },
            { key: 'ticket_1d', type: 'ticket', period: '1d', domId: 'val-ticket-1d', origin: 'ventas' },
            { key: 'ticket_7d', type: 'ticket', period: '7d', domId: 'val-ticket-7d', origin: 'ventas' },
            { key: 'ticket_30d', type: 'ticket', period: '30d', domId: 'val-ticket-30d', origin: 'ventas' },
            { key: 'margin_1d', type: 'margin', period: '1d', domId: 'val-margin-1d', origin: 'ventas' },
            { key: 'margin_7d', type: 'margin', period: '7d', domId: 'val-margin-7d', origin: 'ventas' },
            { key: 'margin_30d', type: 'margin', period: '30d', domId: 'val-margin-30d', origin: 'ventas' },
            { key: 'kpi_neto', type: 'neto', period: 'year', domId: 'kpi-neto', origin: 'ventas' },
            { key: 'kpi_coste', type: 'coste', period: 'year', domId: 'kpi-coste', origin: 'ventas' },
            { key: 'kpi_margen', type: 'margin', period: 'year', domId: 'kpi-margen', origin: 'ventas' },
            { key: 'kpi_ticket', type: 'ticket', period: 'year', domId: 'kpi-ticket', origin: 'ventas' },
            { key: 'compras_1d', type: 'compras', period: '1d', domId: 'val-compras-1d', origin: 'compras' },
            { key: 'compras_7d', type: 'compras', period: '7d', domId: 'val-compras-7d', origin: 'compras' },
            { key: 'compras_30d', type: 'compras', period: '30d', domId: 'val-compras-30d', origin: 'compras' },
            { key: 'ticket_compra_1d', type: 'ticket_compra', period: '1d', domId: 'val-ticket-compra-1d', origin: 'compras' },
            { key: 'ticket_compra_7d', type: 'ticket_compra', period: '7d', domId: 'val-ticket-compra-7d', origin: 'compras' },
            { key: 'ticket_compra_30d', type: 'ticket_compra', period: '30d', domId: 'val-ticket-compra-30d', origin: 'compras' },
            { key: 'ops_compra_1d', type: 'ops_compra', period: '1d', domId: 'val-ops-compra-1d', origin: 'compras' },
            { key: 'ops_compra_7d', type: 'ops_compra', period: '7d', domId: 'val-ops-compra-7d', origin: 'compras' },
            { key: 'ops_compra_30d', type: 'ops_compra', period: '30d', domId: 'val-ops-compra-30d', origin: 'compras' },
            { key: 'compras_year', type: 'compras_year', period: 'year', domId: 'val-compras-year', origin: 'compras' },
            { key: 'ticket_compra_year', type: 'ticket_compra_year', period: 'year', domId: 'val-ticket-compra-year', origin: 'compras' },
            { key: 'kpi_proveedores', type: 'kpi_proveedores', period: 'year', domId: 'val-kpi-proveedores', origin: 'compras' },
            { key: 'alm_base', type: 'alm_base', period: 'year', domId: 'alm-sum-base-valor', origin: 'almacen' },
            { key: 'alm_variacion', type: 'alm_variacion', period: 'year', domId: 'alm-sum-variacion', origin: 'almacen' },
            { key: 'alm_end', type: 'alm_end', period: 'year', domId: 'alm-sum-end', origin: 'almacen' },
            { key: 'fin_ingresos', type: 'fin_ingresos', period: 'year', domId: 'fin-val-ingresos', origin: 'financiera' },
            { key: 'fin_gastos', type: 'fin_gastos', period: 'year', domId: 'fin-val-gastos', origin: 'financiera' },
            { key: 'fin_resultado', type: 'fin_resultado', period: 'year', domId: 'fin-val-resultado', origin: 'financiera' },
            { key: 'fin_otros_ingresos', type: 'fin_otros_ingresos', period: 'year', domId: 'fin-val-otros-ingresos', origin: 'financiera', kind: 'kpi', title: 'Otros ingresos' },
            { key: 'fin_otros_gastos', type: 'fin_otros_gastos', period: 'year', domId: 'fin-val-otros-gastos', origin: 'financiera', kind: 'kpi', title: 'Otros gastos' },
            { key: 'fin_exec_chart', type: 'chart', period: 'year', domId: 'fin-exec-chart', origin: 'financiera', kind: 'chart', title: 'Gráfico ejecutivo' },
            { key: 'chart_activity', type: 'chart', period: 'month', domId: 'chart-activity', origin: 'ventas', kind: 'chart', title: 'Evolución de ventas' },
            { key: 'chart_clients', type: 'chart', period: 'year', domId: 'chart-clients', origin: 'ventas', kind: 'chart', title: 'Top clientes' },
            { key: 'chart_products', type: 'chart', period: 'year', domId: 'chart-products', origin: 'ventas', kind: 'chart', title: 'Top artículos' },
            { key: 'sales_uninv_albaranes', type: 'kpi', period: 'year', domId: 'sales-uninv-albaranes', origin: 'ventas', kind: 'kpi', title: 'Albaranes no facturados' },
            { key: 'sales_uninv_lineas', type: 'kpi', period: 'year', domId: 'sales-uninv-lineas', origin: 'ventas', kind: 'kpi', title: 'Líneas no facturadas' },
            { key: 'sales_uninv_importe', type: 'kpi', period: 'year', domId: 'sales-uninv-importe', origin: 'ventas', kind: 'kpi', title: 'Importe no facturado' },
            { key: 'ops_compra_year', type: 'ops_compra_year', period: 'year', domId: 'val-ops-compra-year', origin: 'compras', kind: 'kpi', title: 'Operaciones de compra (año)' },
            { key: 'chart_activity_compras', type: 'chart', period: 'month', domId: 'chart-activity-compras', origin: 'compras', kind: 'chart', title: 'Evolución de compras' },
            { key: 'top_zonas_compra', type: 'chart', period: 'year', domId: 'chart-top-zonas-compra', origin: 'compras', kind: 'chart', title: 'Top zonas de compra' },
            { key: 'top_proveedores', type: 'chart', period: 'year', domId: 'chart-top-proveedores', origin: 'compras', kind: 'chart', title: 'Top proveedores' },
            { key: 'top_articulos_compra', type: 'chart', period: 'year', domId: 'chart-top-articulos-compra', origin: 'compras', kind: 'chart', title: 'Top artículos de compra' },
            { key: 'alm_total_valor', type: 'kpi', period: 'year', domId: 'alm-total-valor', origin: 'almacen', kind: 'kpi', title: 'Stock valorado' },
            { key: 'alm_total_unidades', type: 'kpi', period: 'year', domId: 'alm-total-unidades', origin: 'almacen', kind: 'kpi', title: 'Unidades de stock' },
            { key: 'alm_expiring', type: 'kpi', period: 'year', domId: 'alm-expiring', origin: 'almacen', kind: 'kpi', title: 'Próximos a caducar' },
            { key: 'alm_critical', type: 'kpi', period: 'year', domId: 'alm-critical', origin: 'almacen', kind: 'kpi', title: 'Stock crítico' },
            { key: 'chart_alm_variacion', type: 'chart', period: 'year', domId: 'chart-alm-variacion', origin: 'almacen', kind: 'chart', title: 'Variación de existencias' },
            { key: 'chart_alm_almacen', type: 'chart', period: 'year', domId: 'chart-alm-almacen', origin: 'almacen', kind: 'chart', title: 'Stock por almacén' },
            { key: 'chart_alm_abc', type: 'chart', period: 'year', domId: 'chart-alm-abc', origin: 'almacen', kind: 'chart', title: 'Pareto ABC' },
            { key: 'ratios_core_liquidez', type: 'kpi', period: 'year', domId: 'ratios-core-liquidez', origin: 'ratios', kind: 'kpi', title: 'Liquidez' },
            { key: 'ratios_core_margen', type: 'kpi', period: 'year', domId: 'ratios-core-margen', origin: 'ratios', kind: 'kpi', title: 'Margen EBITDA' },
            { key: 'ratios_core_solvencia', type: 'kpi', period: 'year', domId: 'ratios-core-solvencia', origin: 'ratios', kind: 'kpi', title: 'Solvencia' },
            { key: 'ratios_core_endeudamiento', type: 'kpi', period: 'year', domId: 'ratios-core-endeudamiento', origin: 'ratios', kind: 'kpi', title: 'Endeudamiento' },
            { key: 'ratios_radar', type: 'chart', period: 'year', domId: 'ratios-radar-chart', origin: 'ratios', kind: 'chart', title: 'Mapa de ratios' },
            { key: 'ratios_rentabilidad', type: 'chart', period: 'year', domId: 'ratios-rentabilidad-chart', origin: 'ratios', kind: 'chart', title: 'Rentabilidad' },
            { key: 'ratio_liquidez_corriente', type: 'kpi', period: 'year', domId: 'ratio-liquidez-corriente-val', origin: 'ratios', kind: 'kpi', title: 'Liquidez corriente' },
            { key: 'ratio_test_acido', type: 'kpi', period: 'year', domId: 'ratio-test-acido-val', origin: 'ratios', kind: 'kpi', title: 'Test ácido' },
            { key: 'ratio_disponibilidad', type: 'kpi', period: 'year', domId: 'ratio-disponibilidad-val', origin: 'ratios', kind: 'kpi', title: 'Disponibilidad' },
            { key: 'ratio_fondo_maniobra', type: 'kpi', period: 'year', domId: 'ratio-fondo-maniobra-val', origin: 'ratios', kind: 'kpi', title: 'Fondo de maniobra' },
            { key: 'ratio_endeudamiento', type: 'kpi', period: 'year', domId: 'ratio-endeudamiento-val', origin: 'ratios', kind: 'kpi', title: 'Endeudamiento' },
            { key: 'ratio_autonomia', type: 'kpi', period: 'year', domId: 'ratio-autonomia-val', origin: 'ratios', kind: 'kpi', title: 'Autonomía' },
            { key: 'ratio_garantia', type: 'kpi', period: 'year', domId: 'ratio-garantia-val', origin: 'ratios', kind: 'kpi', title: 'Garantía' },
            { key: 'ratio_calidad_deuda', type: 'kpi', period: 'year', domId: 'ratio-calidad-deuda-val', origin: 'ratios', kind: 'kpi', title: 'Calidad de la deuda' },
            { key: 'ratio_rotacion_activos', type: 'kpi', period: 'year', domId: 'ratio-rotacion-activos-val', origin: 'ratios', kind: 'kpi', title: 'Rotación de activos' },
            { key: 'ratio_rotacion_stock', type: 'kpi', period: 'year', domId: 'ratio-rotacion-stock-val', origin: 'ratios', kind: 'kpi', title: 'Rotación de stock' },
            { key: 'ratio_periodo_cobro', type: 'kpi', period: 'year', domId: 'ratio-periodo-cobro-val', origin: 'ratios', kind: 'kpi', title: 'Período de cobro' },
            { key: 'ratio_periodo_pago', type: 'kpi', period: 'year', domId: 'ratio-periodo-pago-val', origin: 'ratios', kind: 'kpi', title: 'Período de pago' },
            { key: 'ratio_margen_bruto', type: 'kpi', period: 'year', domId: 'ratio-margen-bruto-val', origin: 'ratios', kind: 'kpi', title: 'Margen bruto' },
            { key: 'ratio_margen_neto', type: 'kpi', period: 'year', domId: 'ratio-margen-neto-val', origin: 'ratios', kind: 'kpi', title: 'Margen neto' },
            { key: 'ratio_roa', type: 'kpi', period: 'year', domId: 'ratio-roa-val', origin: 'ratios', kind: 'kpi', title: 'ROA' },
            { key: 'ratio_roe', type: 'kpi', period: 'year', domId: 'ratio-roe-val', origin: 'ratios', kind: 'kpi', title: 'ROE' },
            { key: 'ratio_cobertura_interes', type: 'kpi', period: 'year', domId: 'ratio-cobertura-interes-val', origin: 'ratios', kind: 'kpi', title: 'Cobertura de intereses' },
            { key: 'ratio_cobertura_deuda', type: 'kpi', period: 'year', domId: 'ratio-cobertura-deuda-val', origin: 'ratios', kind: 'kpi', title: 'Cobertura de deuda' },
            { key: 'ratio_margen_ebitda', type: 'kpi', period: 'year', domId: 'ratio-margen-ebitda-val', origin: 'ratios', kind: 'kpi', title: 'Margen EBITDA' },
            { key: 'tes_pendiente_cobro', type: 'kpi', period: 'year', domId: 'kpi-pendiente-cobro', origin: 'tesoreria', kind: 'kpi', title: 'Pendiente de cobro' },
            { key: 'tes_impagados', type: 'kpi', period: 'year', domId: 'kpi-impagados', origin: 'tesoreria', kind: 'kpi', title: 'Períodos de cobro' },
            { key: 'tes_dias_cobro', type: 'kpi', period: 'year', domId: 'kpi-dias-cobro', origin: 'tesoreria', kind: 'kpi', title: 'Días de cobro' },
            { key: 'tes_pendiente_pago', type: 'kpi', period: 'year', domId: 'kpi-pendiente-pago', origin: 'tesoreria', kind: 'kpi', title: 'Pendiente de pago' },
            { key: 'tes_ratio_cobro', type: 'kpi', period: 'year', domId: 'kpi-ratio-cobro', origin: 'tesoreria', kind: 'kpi', title: 'Ratio de cobro' },
            { key: 'tes_ratio_pago', type: 'kpi', period: 'year', domId: 'kpi-ratio-pago', origin: 'tesoreria', kind: 'kpi', title: 'Ratio de pago' },
            { key: 'tes_ratio_tesoreria', type: 'kpi', period: 'year', domId: 'kpi-ratio-tesoreria', origin: 'tesoreria', kind: 'kpi', title: 'Ratio de tesorería' },
            { key: 'tes_ratio_endeudamiento', type: 'kpi', period: 'year', domId: 'kpi-ratio-endeudamiento', origin: 'tesoreria', kind: 'kpi', title: 'Ratio de endeudamiento' },
            { key: 'tes_cash', type: 'kpi', period: 'year', domId: 'kpi-cash', origin: 'tesoreria', kind: 'kpi', title: 'Tesorería disponible' },
            { key: 'tes_wc', type: 'kpi', period: 'year', domId: 'kpi-wc', origin: 'tesoreria', kind: 'kpi', title: 'Fondo de maniobra' },
            { key: 'chart_aging_cobros', type: 'chart', period: 'year', domId: 'chart-aging-cobros', origin: 'tesoreria', kind: 'chart', title: 'Cobros por período' },
            { key: 'chart_aging_pagos', type: 'chart', period: 'year', domId: 'chart-aging-pagos', origin: 'tesoreria', kind: 'chart', title: 'Pagos por período' },
            { key: 'chart_tes_clientes', type: 'chart', period: 'year', domId: 'chart-tesoreria-clientes', origin: 'tesoreria', kind: 'chart', title: 'Saldos de clientes' },
            { key: 'chart_tes_proveedores', type: 'chart', period: 'year', domId: 'chart-tesoreria-proveedores', origin: 'tesoreria', kind: 'chart', title: 'Saldos de proveedores' },
            { key: 'chart_tes_bancos', type: 'chart', period: 'year', domId: 'chart-tesoreria-bancos', origin: 'tesoreria', kind: 'chart', title: 'Saldos de bancos' },
            { key: 'chart_tes_evolucion', type: 'chart', period: 'year', domId: 'chart-tesoreria-evolucion', origin: 'tesoreria', kind: 'chart', title: 'Ingresos y gastos' },
            { key: 'chart_tes_forecast', type: 'chart', period: 'year', domId: 'tes-chart-forecast', origin: 'tesoreria', kind: 'chart', title: 'Previsión de caja' },
            { key: 'balance_summary', type: 'kpi', period: 'year', domId: 'fin-balance-summary', origin: 'balances', kind: 'block', title: 'Resumen del balance' },
            { key: 'balance_chart', type: 'chart', period: 'year', domId: 'fin-balance-detail', origin: 'balances', kind: 'chart', title: 'Gráfico del balance' },
            { key: 'pl_summary', type: 'kpi', period: 'year', domId: 'fin-pl-summary', origin: 'balances', kind: 'block', title: 'Resumen de explotación' },
            { key: 'quarter_chart', type: 'chart', period: 'year', domId: 'fin-quarter-chart', origin: 'balances', kind: 'chart', title: 'Comparativa trimestral' },
            { key: 'anatomy_waffle', type: 'chart', period: 'year', domId: 'fin-anatomy-waffle', origin: 'anatomia', kind: 'chart', title: 'Mapa de gastos' },
            { key: 'anatomy_per100', type: 'chart', period: 'year', domId: 'fin-anatomy-per100-pie', origin: 'anatomia', kind: 'chart', title: 'Por cada 100 €' },
            { key: 'anatomy_forecast', type: 'chart', period: 'year', domId: 'fin-anatomy-forecast-chart', origin: 'anatomia', kind: 'chart', title: 'Previsión' },
            { key: 'budget_ingresos', type: 'kpi', period: 'year', domId: 'budget-dash-ingresos', origin: 'presupuestos', kind: 'kpi', title: 'Ingresos del ejercicio' },
            { key: 'budget_gastos', type: 'kpi', period: 'year', domId: 'budget-dash-gastos', origin: 'presupuestos', kind: 'kpi', title: 'Gastos del ejercicio' },
            { key: 'budget_resultado', type: 'kpi', period: 'year', domId: 'budget-dash-resultado', origin: 'presupuestos', kind: 'kpi', title: 'Resultado del ejercicio' },
            { key: 'budget_monthly', type: 'chart', period: 'year', domId: 'chart-dash-monthly', origin: 'presupuestos', kind: 'chart', title: 'Presupuesto mes a mes' },
            { key: 'budget_cumulative', type: 'chart', period: 'year', domId: 'chart-dash-cumulative', origin: 'presupuestos', kind: 'chart', title: 'Resultado acumulado' }
        ],
        init: function () {
            var self = this;
            self.list.forEach(function (it) { self.map[it.key] = it; });
        },
        getValue: function (key) {
            var it = this.map[key];
            if (!it) return '-';
            var type = it.type;
            var period = it.period;
            var snap = window.cachedSnapshotData || null;
            var kpi = window.cachedKpiData || null;
            var compras = window.cachedComprasSnapshotData || null;
            var fin = window.cachedFinancialData || null;
            var inv = window.cachedInventoryVariation || null;
            if (type === 'neto' && period === 'year' && kpi) return fmtMoney(kpi.neto || 0);
            if (type === 'coste' && period === 'year' && kpi) return fmtMoney(kpi.coste || 0);
            if (type === 'margin') {
                if (period === 'year' && kpi) return ((kpi.margen !== undefined ? kpi.margen : (kpi.margin || 0))).toFixed(2) + '%';
                if (snap) {
                    var p = 'm_' + period;
                    var d = snap[p] || {};
                    return ((d.margin || 0)).toFixed(2) + '%';
                }
            }
            if (type === 'ticket' && snap) {
                var p0 = 'm_' + period;
                var d0 = snap[p0] || {};
                return fmtMoney(d0.ticket || 0);
            }
            if (type === 'sales' && snap) {
                var p1 = 'm_' + period;
                var d1 = snap[p1] || {};
                return fmtMoney(d1.neto || 0);
            }
            if (compras) {
                var p2 = 'm_' + period;
                var d2 = compras[p2] || {};
                if (type === 'compras') return fmtMoney(d2.neto || 0);
                if (type === 'ticket_compra') return fmtMoney(d2.ticket || 0);
                if (type === 'ops_compra') return String((d2.albaranes !== undefined ? d2.albaranes : (d2.ops || 0)));
                if (period === 'year') {
                    if (type === 'compras_year') return fmtMoney(compras.global_neto || 0);
                    if (type === 'ticket_compra_year') return fmtMoney(compras.global_ticket || 0);
                    if (type === 'kpi_proveedores') return String(compras.global_entities || 0);
                }
            }
            if (fin) {
                if (type === 'fin_ingresos') return fmtMoney(fin.ingresos || 0);
                if (type === 'fin_gastos') return fmtMoney(fin.gastos || 0);
                if (type === 'fin_resultado') return fmtMoney(fin.resultado || 0);
            }
            if (inv) {
                if (type === 'alm_base') return fmtPlain(inv.valor_inicial || 0);
                if (type === 'alm_variacion') return fmtPlain(inv.variacion_total || 0);
                if (type === 'alm_end') return fmtPlain(inv.existencia_fin || 0);
            }
            var node = it && it.domId ? document.getElementById(it.domId) : null;
            if (node && it.kind !== 'chart') {
                var txt = (node.innerText || '').replace(/\s+/g, ' ').trim();
                if (txt && txt !== '--' && txt !== '...' && txt !== '-') return txt.length > 180 ? txt.slice(0, 180) : txt;
            }
            FavoriteStore.ensureCaches();
            return '-';
        }
    };
    var FavoriteStore = {
        ready: false,
        name: 'Pestaña Personal',
        keys: [],
        init: async function () {
            try {
                var cached = null;
                try { cached = localStorage.getItem('datia-personal-tab-layout'); } catch (_) { }
                if (cached) {
                    var c = JSON.parse(cached);
                    if (c && typeof c === 'object') {
                        if (c.name) this.name = c.name;
                        if (Array.isArray(c.widgets)) this.keys = c.widgets.map(function (w) { return w.key; });
                    }
                }
            } catch (_) { }
            try {
                var res = await fetch('/api/financial/preferences/layout');
                var data = await res.json();
                var v = (data && typeof data === 'object' && data.layout && typeof data.layout === 'object') ? data.layout : data;
                var ct = v && v.custom_tab ? v.custom_tab : null;
                if (ct) {
                    this.name = ct.name || this.name;
                    if (Array.isArray(ct.widgets)) {
                        this.keys = ct.widgets.map(function (w) { return w.key || w; });
                    } else if (ct.widgets && typeof ct.widgets === 'object') {
                        this.keys = Object.keys(ct.widgets).filter(function (k) { return ct.widgets[k]; });
                    } else if (Array.isArray(v.custom_tab_keys)) {
                        this.keys = v.custom_tab_keys.slice();
                    }
                }
                this.ready = true;
                try { document.dispatchEvent(new CustomEvent('datia:favorites-change', { detail: { keys: this.keys, name: this.name } })); } catch (_) { }
                try { localStorage.setItem('datia-personal-tab-layout', JSON.stringify({ name: this.name, widgets: this.keys.map(function (k) { return { key: k }; }) })); } catch (_) { }
            } catch (_) { }
        },
        getFavorites: function () { return this.keys.slice(); },
        setName: async function (name) {
            this.name = name || this.name;
            try { localStorage.setItem('datia-personal-tab-layout', JSON.stringify({ name: this.name, widgets: this.keys.map(function (k) { return { key: k }; }) })); } catch (_) { }
            await this.persist();
            try { document.dispatchEvent(new CustomEvent('datia:favorites-change', { detail: { keys: this.keys, name: this.name } })); } catch (_) { }
        },
        toggle: async function (key) {
            var exists = this.keys.indexOf(key) >= 0;
            if (exists) this.keys = this.keys.filter(function (k) { return k !== key; });
            else this.keys.push(key);
            try { localStorage.setItem('datia-personal-tab-layout', JSON.stringify({ name: this.name, widgets: this.keys.map(function (k) { return { key: k }; }) })); } catch (_) { }
            await this.persist();
            try { document.dispatchEvent(new CustomEvent('datia:favorites-change', { detail: { keys: this.keys, name: this.name } })); } catch (_) { }
        },
        persist: async function () {
            try {
                var headers = { 'Content-Type': 'application/json' };
                var token = null;
                try { if (typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) token = CSRF_TOKEN; } catch (_) { }
                if (!token) {
                    try {
                        var name = 'csrftoken';
                        var value = '; ' + document.cookie;
                        var parts = value.split('; ' + name + '=');
                        if (parts.length === 2) token = decodeURIComponent(parts.pop().split(';').shift());
                    } catch (_) { }
                }
                if (token) headers['X-CSRFToken'] = token;
                var getRes = await fetch('/api/financial/preferences/layout');
                var current = await getRes.json();
                var base = (current && typeof current === 'object' && current.layout && typeof current.layout === 'object') ? current.layout : (current || {});
                var merged = Object.assign({}, base, { custom_tab: { name: this.name, widgets: this.keys.map(function (k) { return { key: k }; }) }, custom_tab_keys: this.keys.slice() });
                await fetch('/api/financial/preferences/layout', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify({ layout: merged })
                });
            } catch (_) { }
        },
        ensureCaches: async function () {
            try {
                var apiBase = (typeof API !== 'undefined' && API) ? API : '/api/datia';
                var emp = getParam('empresa');
                var eje = getParam('ejercicio');
                var q = '?empresa=' + encodeURIComponent(emp) + '&ejercicio=' + encodeURIComponent(eje);
                if (!window.cachedSnapshotData) {
                    try {
                        var d = null;
                        if (typeof window.fetchSnapshot === 'function') {
                            d = await window.fetchSnapshot('sales', emp, eje, 10000);
                        } else {
                            var r = await fetch(apiBase + '/widgets/snapshot' + q);
                            var j = await r.json();
                            d = j && (j.data || j);
                        }
                        if (d) {
                            window.cachedSnapshotData = d;
                            try { document.dispatchEvent(new CustomEvent('datia:snapshot-ready', { detail: { source: 'favorites_v2' } })); } catch (_) { }
                        }
                    } catch (_) { }
                }
                if (!window.cachedKpiData) {
                    try {
                        var r2 = await fetch(apiBase + '/widgets/ventas_resumen' + q);
                        var j2 = await r2.json();
                        var d2 = j2 && (j2.data || j2);
                        if (d2) {
                            window.cachedKpiData = d2;
                            try { document.dispatchEvent(new CustomEvent('datia:kpis-ready', { detail: { source: 'favorites_v2' } })); } catch (_) { }
                        }
                    } catch (_) { }
                }
                if (!window.cachedComprasSnapshotData) {
                    var favs = FavoriteStore.getFavorites();
                    var needCompras = Array.isArray(favs) && favs.some(function (k) { return /compras|compra|ops_compra|kpi_proveedores/.test(String(k || '')); });
                    var comprasPanel = document.getElementById('sub-compras');
                    var comprasVisible = comprasPanel && (comprasPanel.classList.contains('active') || comprasPanel.style.display !== 'none');
                    if (needCompras || comprasVisible) {
                        try {
                            var d3 = null;
                            if (typeof window.fetchSnapshot === 'function') {
                                d3 = await window.fetchSnapshot('compras', emp, eje, 10000);
                            } else {
                                var r3 = await fetch(apiBase + '/widgets/snapshot' + q + '&kind=compras');
                                var j3 = await r3.json();
                                d3 = j3 && (j3.data || j3);
                            }
                            if (d3) window.cachedComprasSnapshotData = d3;
                        } catch (_) { }
                    }
                }
                if (!window.cachedFinancialData) {
                    try {
                        var rf = await fetch('/api/financial/snapshot' + q);
                        var jf = await rf.json();
                        if (jf && typeof jf === 'object') window.cachedFinancialData = jf;
                    } catch (_) { }
                }
                if (!window.cachedInventoryVariation) {
                    try {
                        var ri = await fetch('/api/inventory/variation' + q + '&almacen=&ubicacion=&tipologia=');
                        var ji = await ri.json();
                        var di = ji && (ji || null);
                        if (di && di.status === 'ok') {
                            window.cachedInventoryVariation = {
                                valor_inicial: di.valor_inicial || 0,
                                variacion_total: di.variacion_total || 0,
                                existencia_fin: di.existencia_fin || 0
                            };
                        }
                    } catch (_) { }
                }
                try { document.dispatchEvent(new CustomEvent('datia:favorites-data-ready', { detail: { ok: true } })); } catch (_) { }
            } catch (_) { }
        }
    };
    var StarInjector = {
        updateStars: function () {
            try {
                var favs = FavoriteStore.getFavorites();
                document.querySelectorAll('.act-fav-btn[data-key]').forEach(function (btn) {
                    var key = btn.getAttribute('data-key');
                    if (!key) return;
                    if (favs.indexOf(key) >= 0) {
                        btn.classList.remove('inactive');
                        btn.title = 'Añadido a Pestaña Personal';
                    } else {
                        btn.classList.add('inactive');
                        btn.title = 'Añadir a Pestaña Personal';
                    }
                });
            } catch (_) { }
        },
        cardOf: function (el) {
            return el.closest('.flip-card-front')
                || el.closest('.fin-kpi-card')
                || el.closest('.alm-card')
                || el.closest('.alm-chart-block')
                || el.closest('.glass-panel')
                || el.closest('.fin-card-simple')
                || el.closest('.fin-grid-item')
                || el;
        },
        injectOne: function (item) {
            var el = document.getElementById(item.domId);
            if (!el) return;
            if (el.querySelector('.act-fav-btn[data-key="' + item.key + '"]')) return;
            var card = this.cardOf(el);
            if (card.querySelector('.act-fav-btn[data-key="' + item.key + '"]')) return;
            var shared = WidgetRegistry.list.filter(function (it) {
                var node = document.getElementById(it.domId);
                return node && card.contains(node);
            });
            var favs = FavoriteStore.getFavorites();
            var active = favs.indexOf(item.key) >= 0;
            var btn = createStarButton(item.key, active);
            if (shared.length > 1 || card === el) {
                var host = el;
                if (window.getComputedStyle(host).position === 'static') host.style.position = 'relative';
                var overlay = document.createElement('div');
                overlay.className = 'act-fav-overlay';
                overlay.appendChild(btn);
                host.appendChild(overlay);
                return;
            }
            var header = card.querySelector('.v2-kpi-header, .fin-card-header, .fin-kpi-title, .alm-card-title, .alm-chart-title, .fin-kpi-label, h3');
            if (!header) {
                if (window.getComputedStyle(card).position === 'static') card.style.position = 'relative';
                var overlay2 = document.createElement('div');
                overlay2.className = 'act-fav-overlay';
                overlay2.appendChild(btn);
                card.appendChild(overlay2);
                return;
            }
            var actions = header.querySelector('.kpi-actions');
            if (!actions) {
                actions = document.createElement('div');
                actions.className = 'kpi-actions';
                header.appendChild(actions);
            }
            actions.appendChild(btn);
        },
        run: function () {
            var self = this;
            WidgetRegistry.list.forEach(function (item) { self.injectOne(item); });
            this.updateStars();
        },
        init: function () {
            this.run();
            document.addEventListener('datia:tab-change', function () { StarInjector.run(); });
            document.addEventListener('datia:subtab-change', function () { StarInjector.run(); });
            document.addEventListener('datia:favorites-change', function () { StarInjector.updateStars(); });
        },
        setStarActive: function (key, active) {
            try {
                document.querySelectorAll('.act-fav-btn[data-key="' + key + '"]').forEach(function (btn) {
                    if (active) {
                        btn.classList.remove('inactive');
                        btn.title = 'Añadido a Pestaña Personal';
                        btn.setAttribute('aria-pressed', 'true');
                    } else {
                        btn.classList.add('inactive');
                        btn.title = 'Añadir a Pestaña Personal';
                        btn.setAttribute('aria-pressed', 'false');
                    }
                });
            } catch (_) { }
        }
    };
    WidgetRegistry.init();
    window.WidgetRegistry = WidgetRegistry;
    window.FavoriteStore = FavoriteStore;
    window.StarInjector = StarInjector;
    document.addEventListener('DOMContentLoaded', function () {
        FavoriteStore.init();
        FavoriteStore.ensureCaches();
        StarInjector.init();
    });
})();
