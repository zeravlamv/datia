(function () {
    let ratiosLoadedKey = null;
    const DETAIL_KEYS = [
        'liquidez_corriente',
        'endeudamiento',
        'margen_ebitda'
    ];

    function formatValue(entry) {
        if (!entry || entry.available === false) {
            return { text: '—', suffix: '' };
        }
        const v = typeof entry.value === 'number' ? entry.value : 0;
        const lang = typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES';
        if (entry.unit === 'percent') {
            return { text: new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(v) + ' %', suffix: '%' };
        }
        if (entry.unit === 'eur') {
            return { text: new Intl.NumberFormat(lang, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(v), suffix: '€' };
        }
        if (entry.unit === 'days') {
            return { text: new Intl.NumberFormat(lang, { maximumFractionDigits: 1 }).format(v) + ' d', suffix: 'd' };
        }
        if (entry.unit === 'times') {
            return { text: new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(v) + '×', suffix: 'x' };
        }
        return { text: new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(v), suffix: '' };
    }

    function openRatioDetailInternal(ratioKey) {
        if (typeof openRatioDrilldown === 'function') {
            if (ratioKey === 'liquidez_corriente') {
                openRatioDrilldown('liquidez');
                return;
            }
            if (ratioKey === 'endeudamiento') {
                openRatioDrilldown('endeudamiento');
                return;
            }
            if (ratioKey === 'margen_ebitda') {
                openRatioDrilldown('margen');
                return;
            }
        }
        if (typeof showToast === 'function') {
            const msg = (typeof gettext === 'function'
                ? gettext('Detalle de partidas no disponible todavía para este ratio.')
                : 'Detalle de partidas no disponible todavía para este ratio.');
            showToast(msg, 'info');
        }
    }

    window.openRatioDetail = openRatioDetailInternal;

    const RATIO_RANGES = {
        liquidez_corriente: { min: 0, max: 8, low: 1.0, high: 2.0 },
        test_acido: { min: 0, max: 8, low: 0.8, high: 1.5 },
        disponibilidad: { min: 0, max: 4, low: 0.2, high: 1.0 },
        fondo_maniobra: { figure: true, min: 0, max: 1, low: 0, high: Number.POSITIVE_INFINITY },
        endeudamiento: { min: 0, max: 200, low: 40.0, high: 80.0, inverse: true },
        autonomia: { min: 0, max: 4, low: 0.3, high: 1.0 },
        garantia: { min: 0, max: 4, low: 1.1, high: 2.5 },
        calidad_deuda: { min: 0, max: 100, low: 20.0, high: 60.0, inverse: true },
        rotacion_activos: { min: 0, max: 10, low: 1.0, high: 3.0 },
        rotacion_stock: { min: 0, max: 20, low: 2.0, high: 8.0 },
        periodo_cobro: { min: 0, max: 180, low: 60.0, high: 90.0, inverse: true },
        periodo_pago: { min: 0, max: 180, low: 60.0, high: 90.0 },
        margen_bruto: { min: -40, max: 80, low: 20.0, high: 40.0 },
        margen_neto: { min: -40, max: 40, low: 5.0, high: 15.0 },
        roa: { min: -40, max: 60, low: 5.0, high: 20.0 },
        roe: { min: -80, max: 80, low: 10.0, high: 25.0 },
        cobertura_interes: { min: -20, max: 20, low: 2.0, high: 5.0 },
        cobertura_deuda: { min: 0, max: 5, low: 1.0, high: 2.0 },
        margen_ebitda: { min: -40, max: 50, low: 10.0, high: 25.0 }
    };

    function zoneText(status) {
        const t = typeof gettext === 'function' ? gettext : function (s) { return s; };
        if (status === 'target') return t('Zona objetivo');
        if (status === 'low') return t('Por debajo de objetivo');
        if (status === 'high') return t('Por encima de objetivo');
        return '';
    }

    function classifyRatio(value, range) {
        if (!range || typeof value !== 'number' || Number.isNaN(value)) return null;
        const low = Number(range.low);
        const high = Number.isFinite(Number(range.high)) ? Number(range.high) : Number.POSITIVE_INFINITY;
        if (range.inverse) {
            if (value > high) return { status: 'high', label: zoneText('high') };
            if (value < low) return { status: 'low', label: zoneText('low') };
            return { status: 'target', label: zoneText('target') };
        }
        if (value < low) return { status: 'low', label: zoneText('low') };
        if (value > high) return { status: 'high', label: zoneText('high') };
        return { status: 'target', label: zoneText('target') };
    }

    function ensureDetailButton(el, ratioKey) {
        if (DETAIL_KEYS.indexOf(ratioKey) === -1) return;
        if (!el) return;
        const front = el.closest('.flip-card-front');
        if (!front || front.querySelector('.ratio-detail-btn')) return;
        const header = document.createElement('div');
        header.className = 'ratio-header-inline';
        const label = front.querySelector('.fin-kpi-label');
        if (label) header.appendChild(label);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn-fin-action ratio-detail-btn';
        btn.textContent = typeof gettext === 'function' ? gettext('Partidas') : 'Partidas';
        btn.addEventListener('click', function (ev) {
            if (ev) ev.stopPropagation();
            try { openRatioDetailInternal(ratioKey); } catch (_) { }
        });
        header.appendChild(btn);
        front.insertBefore(header, front.firstChild);
    }

    function bindRatios(data) {
        const ratios = data && data.ratios ? data.ratios : {};
        const map = {
            'ratios-core-liquidez': 'liquidez_corriente',
            'ratios-core-margen': 'margen_ebitda',
            'ratios-core-solvencia': 'garantia',
            'ratios-core-endeudamiento': 'endeudamiento',
            'ratio-liquidez-corriente-val': 'liquidez_corriente',
            'ratio-test-acido-val': 'test_acido',
            'ratio-disponibilidad-val': 'disponibilidad',
            'ratio-fondo-maniobra-val': 'fondo_maniobra',
            'ratio-endeudamiento-val': 'endeudamiento',
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
        Object.keys(map).forEach(function (id) {
            const el = document.getElementById(id);
            if (!el) return;
            const key = map[id];
            const entry = ratios[key];
            if (id.indexOf('ratios-core-') !== 0) ensureDetailButton(el, key);
            const front = el.closest('.flip-card-front') || el.closest('.fin-ratio-item');
            if (front) {
                front.querySelectorAll('.ratio-mini-bar').forEach(function (bar) { bar.remove(); });
                let zoneEl = front.querySelector('.ratio-zone');
                if (!zoneEl) {
                    zoneEl = document.createElement('div');
                    zoneEl.className = 'ratio-zone';
                    front.appendChild(zoneEl);
                }
                zoneEl.textContent = '';
                zoneEl.classList.remove('ratio-zone-ok', 'ratio-zone-warn', 'ratio-zone-risk');
                const usable = entry && entry.available !== false && typeof entry.value === 'number';
                const zone = usable ? classifyRatio(entry.value, RATIO_RANGES[key]) : null;
                if (zone) {
                    zoneEl.textContent = zone.label;
                    if (zone.status === 'target') zoneEl.classList.add('ratio-zone-ok');
                    else if (zone.status === 'low') zoneEl.classList.add('ratio-zone-warn');
                    else if (zone.status === 'high') zoneEl.classList.add('ratio-zone-risk');
                    zoneEl.style.display = '';
                } else {
                    zoneEl.style.display = 'none';
                }
            }
            if (!entry || entry.available === false) el.classList.add('text-muted');
            else el.classList.remove('text-muted');
        });
    }

    function readableValue(ratios, key) {
        const entry = ratios[key];
        if (!entry || entry.available === false || typeof entry.value !== 'number') return null;
        return entry.value;
    }

    function renderKeyGauges(data) {
        if (typeof renderRatioGauge !== 'function') return;
        const ratios = data && data.ratios ? data.ratios : {};
        const t = typeof gettext === 'function' ? gettext : function (s) { return s; };
        renderRatioGauge('ratios-core-liquidez', readableValue(ratios, 'liquidez_corriente'), t('Liquidez'), RATIO_RANGES.liquidez_corriente);
        renderRatioGauge('ratios-core-margen', readableValue(ratios, 'margen_ebitda'), t('Margen EBITDA'), RATIO_RANGES.margen_ebitda, '%');
        renderRatioGauge('ratios-core-solvencia', readableValue(ratios, 'garantia'), t('Solvencia'), RATIO_RANGES.garantia);
        renderRatioGauge('ratios-core-endeudamiento', readableValue(ratios, 'endeudamiento'), t('Endeudamiento'), RATIO_RANGES.endeudamiento, '%');
    }

    function renderAllRatioGauges(data) {
        if (typeof renderRatioGauge !== 'function') return;
        const ratios = data && data.ratios ? data.ratios : {};
        const t = typeof gettext === 'function' ? gettext : function (s) { return s; };
        const valOf = function (key) { return readableValue(ratios, key); };
        renderRatioGauge('ratio-liquidez-corriente-val', valOf('liquidez_corriente'), t('Liquidez Corriente'), RATIO_RANGES.liquidez_corriente);
        renderRatioGauge('ratio-test-acido-val', valOf('test_acido'), t('Test Ácido'), RATIO_RANGES.test_acido);
        renderRatioGauge('ratio-disponibilidad-val', valOf('disponibilidad'), t('Disponibilidad'), RATIO_RANGES.disponibilidad);
        renderRatioGauge('ratio-fondo-maniobra-val', valOf('fondo_maniobra'), t('Fondo de Maniobra'), RATIO_RANGES.fondo_maniobra, '€');
        renderRatioGauge('ratio-endeudamiento-val', valOf('endeudamiento'), t('Endeudamiento'), RATIO_RANGES.endeudamiento, '%');
        renderRatioGauge('ratio-autonomia-val', valOf('autonomia'), t('Autonomía'), RATIO_RANGES.autonomia);
        renderRatioGauge('ratio-garantia-val', valOf('garantia'), t('Garantía'), RATIO_RANGES.garantia);
        renderRatioGauge('ratio-calidad-deuda-val', valOf('calidad_deuda'), t('Calidad de la Deuda'), RATIO_RANGES.calidad_deuda, '%');
        renderRatioGauge('ratio-rotacion-activos-val', valOf('rotacion_activos'), t('Rotación de Activos'), RATIO_RANGES.rotacion_activos);
        renderRatioGauge('ratio-rotacion-stock-val', valOf('rotacion_stock'), t('Rotación de Stock'), RATIO_RANGES.rotacion_stock);
        renderRatioGauge('ratio-periodo-cobro-val', valOf('periodo_cobro'), t('Periodo de Cobro'), RATIO_RANGES.periodo_cobro, 'd');
        renderRatioGauge('ratio-periodo-pago-val', valOf('periodo_pago'), t('Periodo de Pago'), RATIO_RANGES.periodo_pago, 'd');
        renderRatioGauge('ratio-margen-bruto-val', valOf('margen_bruto'), t('Margen Bruto'), RATIO_RANGES.margen_bruto, '%');
        renderRatioGauge('ratio-margen-neto-val', valOf('margen_neto'), t('Margen Neto'), RATIO_RANGES.margen_neto, '%');
        renderRatioGauge('ratio-roa-val', valOf('roa'), t('ROA'), RATIO_RANGES.roa, '%');
        renderRatioGauge('ratio-roe-val', valOf('roe'), t('ROE'), RATIO_RANGES.roe, '%');
        renderRatioGauge('ratio-cobertura-interes-val', valOf('cobertura_interes'), t('Cobertura de Intereses'), RATIO_RANGES.cobertura_interes);
        renderRatioGauge('ratio-cobertura-deuda-val', valOf('cobertura_deuda'), t('Cobertura de Deuda'), RATIO_RANGES.cobertura_deuda);
        renderRatioGauge('ratio-margen-ebitda-val', valOf('margen_ebitda'), t('Margen EBITDA'), RATIO_RANGES.margen_ebitda, '%');
    }

    function attachRatioFlipHandlers(snapshot) {
        const container = document.getElementById('tab-actualidad-ratios');
        if (!container) return;
        const items = container.querySelectorAll('.fin-ratio-item');
        items.forEach(function (item) {
            const flip = item.querySelector('.flip-card');
            const btn = item.querySelector('.fin-ratio-lever') || item.querySelector('.fin-ratio-action');
            if (!flip || item.dataset.flipBound === '1') return;
            item.dataset.flipBound = '1';
            if (!flip.querySelector('.flip-card-back')) {
                const back = document.createElement('div');
                back.className = 'flip-card-back';
                const inner = flip.querySelector('.flip-card-inner');
                if (inner) inner.appendChild(back);
            }
            const handler = function (e) {
                if (e) e.stopPropagation();
                if (typeof toggleRatioFlip === 'function') {
                    toggleRatioFlip(item, snapshot || {});
                } else {
                    flip.classList.toggle('flipped');
                }
            };
            item.addEventListener('dblclick', handler);
            if (btn) {
                btn.addEventListener('click', handler);
                btn.addEventListener('keyup', function (e) {
                    if (e.key === 'Enter' || e.key === ' ') handler(e);
                });
            }
        });
    }

    function mountRatioChart(id, dom) {
        window._ratioCharts = window._ratioCharts || {};
        if (window._ratioCharts[id]) {
            try { window._ratioCharts[id].dispose(); } catch (_) {}
        }
        const chart = echarts.init(dom, null, { renderer: 'svg' });
        window._ratioCharts[id] = chart;
        return chart;
    }

    function paintRatios(data) {
        try {
            bindRatios(data);
            renderKeyGauges(data);
            renderAllRatioGauges(data);
            renderRadar(data);
            renderRentabilidadBars(data);
        } finally {
            try { document.dispatchEvent(new CustomEvent('datia:ratios-ready')); } catch (_) {}
        }
    }

    function renderRadar(data) {
        const dom = document.getElementById('ratios-radar-chart');
        if (!dom || typeof echarts === 'undefined') return;
        const ratios = data && data.ratios ? data.ratios : {};
        const keys = [
            { key: 'liquidez_corriente', label: typeof gettext === 'function' ? gettext('Liquidez') : 'Liquidez' },
            { key: 'endeudamiento', label: typeof gettext === 'function' ? gettext('Endeudamiento %') : 'Endeudamiento %' },
            { key: 'autonomia', label: typeof gettext === 'function' ? gettext('Autonomía') : 'Autonomía' },
            { key: 'garantia', label: typeof gettext === 'function' ? gettext('Garantía') : 'Garantía' },
            { key: 'margen_ebitda', label: 'EBITDA %' },
            { key: 'margen_neto', label: typeof gettext === 'function' ? gettext('Margen Neto %') : 'Margen Neto %' }
        ];
        const lang = typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES';
        const nf = new Intl.NumberFormat(lang, { maximumFractionDigits: 2 });
        const raw = keys.map(function (k) {
            return readableValue(ratios, k.key);
        });
        const scores = raw.map(function (value, idx) {
            const range = RATIO_RANGES[keys[idx].key];
            if (value === null || !range) return 0;
            const min = range.min;
            const max = range.max;
            const clamped = Math.max(min, Math.min(max, value));
            return ((clamped - min) / (max - min)) * 100;
        });
        const chart = mountRatioChart('radar', dom);
        const option = {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'item',
                formatter: function () {
                    return keys.map(function (k, idx) {
                        const value = raw[idx];
                        const shown = value === null ? 'Sin dato' : nf.format(value);
                        return k.label + ': ' + shown;
                    }).join('<br>');
                }
            },
            radar: {
                indicator: keys.map(function (k) { return { name: k.label, max: 100 }; }),
                radius: '62%',
                center: ['50%', '52%'],
                splitNumber: 4,
                splitLine: { lineStyle: { color: 'rgba(148,163,184,0.35)' } },
                splitArea: { areaStyle: { color: ['rgba(15,23,42,0.15)', 'rgba(15,23,42,0.35)'] } },
                axisLine: { lineStyle: { color: 'rgba(148,163,184,0.4)' } },
                name: { color: '#e5e7eb', fontSize: 11 },
                axisName: { color: '#e5e7eb', fontSize: 11 }
            },
            series: [
                {
                    type: 'radar',
                    data: [
                        {
                            value: scores,
                            name: typeof gettext === 'function' ? gettext('Perfil actual') : 'Perfil actual',
                            areaStyle: { color: 'rgba(59,130,246,0.28)' },
                            lineStyle: { color: '#60a5fa', width: 2 },
                            itemStyle: { color: '#60a5fa' },
                            symbol: 'circle',
                            symbolSize: 5
                        }
                    ]
                }
            ]
        };
        chart.setOption(option);
        if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
    }

    function renderRentabilidadBars(data) {
        const dom = document.getElementById('ratios-rentabilidad-chart');
        if (!dom || typeof echarts === 'undefined') return;
        const ratios = data && data.ratios ? data.ratios : {};
        const keys = [
            { key: 'margen_bruto', label: typeof gettext === 'function' ? gettext('Margen Bruto') : 'Margen Bruto' },
            { key: 'margen_neto', label: typeof gettext === 'function' ? gettext('Margen Neto') : 'Margen Neto' },
            { key: 'roa', label: 'ROA' },
            { key: 'roe', label: 'ROE' },
            { key: 'margen_ebitda', label: 'EBITDA' }
        ];
        const labels = [];
        const values = [];
        keys.forEach(function (k) {
            labels.push(k.label);
            const value = readableValue(ratios, k.key);
            values.push(value === null ? 0 : value);
        });
        const chart = mountRatioChart('bars', dom);
        const lang = typeof APP_LANG !== 'undefined' ? APP_LANG : 'es-ES';
        const pf = new Intl.NumberFormat(lang, { maximumFractionDigits: 1 });
        const option = {
            backgroundColor: 'transparent',
            grid: { left: 8, right: 12, bottom: 8, top: 16, containLabel: true },
            xAxis: {
                type: 'category',
                data: labels,
                axisLabel: { color: '#cbd5e1', fontSize: 11, interval: 0 },
                axisTick: { show: false },
                axisLine: { lineStyle: { color: '#334155' } }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    color: '#94a3b8',
                    formatter: function (v) { return pf.format(v) + ' %'; }
                },
                splitLine: { lineStyle: { color: 'rgba(148,163,184,0.16)' } }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function (params) {
                    if (!params || !params.length) return '';
                    const p = params[0];
                    return p.name + ': ' + pf.format(p.value) + ' %';
                }
            },
            series: [
                {
                    name: 'Ratios',
                    type: 'bar',
                    data: values.map(function (v) {
                        return {
                            value: v,
                            itemStyle: {
                                color: v < 0 ? '#ef4444' : '#10b981',
                                borderRadius: v < 0 ? [0, 0, 6, 6] : [6, 6, 0, 0]
                            }
                        };
                    }),
                    barMaxWidth: 28,
                    markLine: {
                        silent: true,
                        symbol: 'none',
                        label: { show: false },
                        lineStyle: { color: '#94a3b8', type: 'solid', width: 1 },
                        data: [{ yAxis: 0 }]
                    }
                }
            ]
        };
        chart.setOption(option);
        if (typeof attachResizeObserver === 'function') attachResizeObserver(chart, dom);
    }

    window.loadActualidadRatios = function () {
        const tab = document.getElementById('sub-ratios');
        if (!tab) return;

        let empresa = typeof currEmpresa !== 'undefined' ? currEmpresa : null;
        let ejercicio = typeof currEjercicio !== 'undefined' ? currEjercicio : null;
        const selEmp = document.getElementById('sel-empresa');
        const selEje = document.getElementById('sel-ejercicio');
        if ((!empresa || empresa === '' || empresa === 'undefined') && selEmp && selEmp.value) {
            empresa = selEmp.value;
        }
        if ((!ejercicio || ejercicio === '' || ejercicio === 'undefined') && selEje && selEje.value) {
            ejercicio = selEje.value;
        }

        if (!empresa || !ejercicio) {
            setTimeout(function () {
                try { window.loadActualidadRatios(); } catch (_) { }
            }, 200);
            return;
        }

        const key = String(empresa) + '-' + String(ejercicio);
        if (ratiosLoadedKey === key && window.cachedRatiosData) {
            paintRatios(window.cachedRatiosData);
            return;
        }

        const q = '?empresa=' + encodeURIComponent(empresa) + '&ejercicio=' + encodeURIComponent(ejercicio);
        fetch('/api/financial/ratios' + q)
            .then(function (res) {
                if (!res.ok) throw new Error('Error HTTP');
                return res.json();
            })
            .then(function (data) {
                ratiosLoadedKey = key;
                window.cachedRatiosData = data;
                paintRatios(data);
                const rs = data && data.ratios ? data.ratios : {};
                const snap = { ratios: {}, ranges: {} };
                function setSnap(name, ratioKey) {
                    const e = rs[ratioKey];
                    snap.ratios[name] = e && typeof e.value === 'number' ? e.value : 0;
                }
                setSnap('liq_corriente', 'liquidez_corriente');
                setSnap('test_acido', 'test_acido');
                setSnap('disponibilidad', 'disponibilidad');
                setSnap('fondo_maniobra', 'fondo_maniobra');
                setSnap('endeudamiento_ext', 'endeudamiento');
                setSnap('autonomia', 'autonomia');
                setSnap('garantia', 'garantia');
                setSnap('calidad_deuda', 'calidad_deuda');
                setSnap('rotacion_activos', 'rotacion_activos');
                setSnap('rotacion_stock', 'rotacion_stock');
                setSnap('periodo_cobro', 'periodo_cobro');
                setSnap('periodo_pago', 'periodo_pago');
                setSnap('margen_bruto', 'margen_bruto');
                setSnap('margen_neto', 'margen_neto');
                setSnap('roa', 'roa');
                setSnap('roe', 'roe');
                setSnap('cobertura_interes', 'cobertura_interes');
                setSnap('cobertura_deuda', 'cobertura_deuda');
                setSnap('margen_ebitda', 'margen_ebitda');
                snap.ratios.liquidez = snap.ratios.liq_corriente || 0;
                snap.ratios.margen = snap.ratios.margen_ebitda || 0;
                snap.ratios.solvencia = snap.ratios.garantia || 0;
                snap.ratios.endeudamiento = snap.ratios.endeudamiento_ext || 0;
                snap.ranges = {
                    liquidez: { min: 0, max: 8, low: 1.0, high: 2.0 },
                    margen: { min: 0, max: 50, low: 5.0, high: 15.0 },
                    solvencia: { min: 0, max: 12, low: 1.1, high: 2.0 },
                    endeudamiento: { min: 0, max: 200, low: 40.0, high: 80.0, inverse: true },
                    liq_corriente: { min: 0, max: 8, low: 1.0, high: 2.0 },
                    test_acido: { min: 0, max: 8, low: 0.8, high: 1.5 },
                    disponibilidad: { min: 0, max: 4, low: 0.2, high: 1.0 },
                    fondo_maniobra: { min: 0, max: 100, low: 0, high: 0 },
                    endeudamiento_ext: { min: 0, max: 200, low: 40.0, high: 80.0, inverse: true },
                    autonomia: { min: 0, max: 4, low: 0.3, high: 1.0 },
                    garantia: { min: 0, max: 4, low: 1.1, high: 2.5 },
                    calidad_deuda: { min: 0, max: 100, low: 20.0, high: 60.0, inverse: true },
                    rotacion_activos: { min: 0, max: 10, low: 1.0, high: 3.0 },
                    rotacion_stock: { min: 0, max: 20, low: 2.0, high: 8.0 },
                    periodo_cobro: { min: 0, max: 180, low: 60.0, high: 90.0, inverse: true },
                    periodo_pago: { min: 0, max: 180, low: 60.0, high: 90.0 },
                    margen_bruto: { min: 0, max: 80, low: 20.0, high: 40.0 },
                    margen_neto: { min: 0, max: 40, low: 5.0, high: 15.0 },
                    roa: { min: 0, max: 60, low: 5.0, high: 20.0 },
                    roe: { min: 0, max: 80, low: 10.0, high: 25.0 },
                    cobertura_interes: { min: 0, max: 20, low: 2.0, high: 5.0 },
                    cobertura_deuda: { min: 0, max: 5, low: 1.0, high: 2.0 },
                    margen_ebitda: { min: 0, max: 50, low: 10.0, high: 25.0 }
                };
                attachRatioFlipHandlers(snap);
            })
            .catch(function (err) {
                console.error('Error cargando ratios financieros', err);
            });
    };

    try {
        document.addEventListener('datia:empresa-change', function () {
            try { window.loadActualidadRatios(); } catch (_) { }
        });
        document.addEventListener('datia:ejercicio-change', function () {
            try { window.loadActualidadRatios(); } catch (_) { }
        });
    } catch (_) { }
})();
