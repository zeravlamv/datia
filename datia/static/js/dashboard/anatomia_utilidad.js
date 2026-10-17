let _anatomyLoadToken = 0;
let _anatomyProgressInterval = null;

let _currentTipId = null;
let _tipsActive = false;
let _prophetInfoShown = false;
let _tipVariantIndex = 0;
let _tipLastVariantAt = 0;

const anatomyTips = [
    { id: 1, minPct: 0, maxPct: 35, icon: 'fas fa-database', title: 'Extrayendo Anatomía', text: 'DATIA está consultando tu histórico contable para desglosar la utilidad mes a mes.', variants: [
        'DATIA está consultando tu histórico contable para desglosar la utilidad mes a mes.',
        'Este paso prepara la base: ingresos, costes y gastos para calcular la utilidad neta.',
        'Si tardase, suele deberse a volumen de datos o a agregaciones trimestrales.'
    ]},
    { id: 2, minPct: 35, maxPct: 55, icon: 'fas fa-chart-pie', title: 'Calculando Common Size', text: 'Analizamos el peso de cada partida de gasto frente a los ingresos totales (base 100).', variants: [
        'Analizamos el peso de cada partida de gasto frente a los ingresos totales (base 100).',
        'Así puedes comparar trimestres aunque cambie el tamaño del negocio.',
        'El objetivo es entender qué “se come” el margen, no solo el total.'
    ]},
    { id: 3, minPct: 55, maxPct: 85, icon: 'fas fa-robot', title: 'Modelo Prophet (IA)', text: 'Prophet evalúa tendencias y estacionalidad usando los "Años de entrenamiento" configurados.', variants: [
        'Prophet evalúa tendencia y estacionalidad usando los “Años de entrenamiento” configurados.',
        'No “adivina” eventos futuros; proyecta patrones del histórico.',
        'Más años = más estabilidad; menos años = más sensibilidad a cambios recientes.'
    ]},
    { id: 4, minPct: 85, maxPct: 100, icon: 'fas fa-chart-line', title: 'Bandas de Confianza', text: 'Generamos escenarios Low y High para estimar el rango probable del forecast.', variants: [
        'Generamos escenarios Low y High para estimar el rango probable del forecast.',
        'Bandas anchas = más incertidumbre (más ruido o menos histórico útil).',
        'Cuando el forecast termina, el panel se actualiza con el resultado final.'
    ]}
];

function initAnatomyTips() {
    const dismissed = localStorage.getItem('datia-hide-anatomy-tips');
    if (dismissed === 'true') return false;
    
    const overlay = document.getElementById('fin-tips-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
        void overlay.offsetWidth; // Force reflow
        overlay.classList.add('show');
        _tipsActive = true;
        _currentTipId = null;
    }
    return true;
}

function updateAnatomyTipForProgress(pct) {
    if (!_tipsActive) return;
    
    const pb = document.getElementById('fin-tips-progress-bar');
    if (pb) pb.style.width = pct + '%';
    
    const tip = anatomyTips.find(t => pct >= t.minPct && pct <= t.maxPct) || anatomyTips[anatomyTips.length - 1];
    const now = Date.now();
    
    if (!tip) return;
    const variants = (tip.variants && tip.variants.length) ? tip.variants : [tip.text];

    const icon = document.getElementById('fin-tip-icon');
    const title = document.getElementById('fin-tip-title');
    const text = document.getElementById('fin-tip-text');

    if (tip.id !== _currentTipId) {
        _currentTipId = tip.id;
        _tipVariantIndex = 0;
        _tipLastVariantAt = now;
        if (icon) icon.className = tip.icon;
        if (title) title.innerText = tip.title;
        if (text) text.innerText = variants[0] || tip.text;

        if (title) {
            title.style.animation = 'none';
            title.offsetHeight;
            title.style.animation = null;
        }
        if (text) {
            text.style.animation = 'none';
            text.offsetHeight;
            text.style.animation = null;
        }
    } else if (variants.length > 1 && (now - _tipLastVariantAt) > 6500) {
        _tipVariantIndex = (_tipVariantIndex + 1) % variants.length;
        _tipLastVariantAt = now;
        if (text) {
            text.innerText = variants[_tipVariantIndex] || tip.text;
            text.style.animation = 'none';
            text.offsetHeight;
            text.style.animation = null;
        }
    }
    
    if (pct >= 100) {
        setTimeout(() => { closeAnatomyTips(false); }, 1200);
    }
}

function closeAnatomyTips(fromButton) {
    const overlay = document.getElementById('fin-tips-overlay');
    const cb = document.getElementById('fin-tips-dont-show');
    
    if (cb && cb.checked) {
        localStorage.setItem('datia-hide-anatomy-tips', 'true');
    }
    
    if (overlay) {
        overlay.classList.remove('show');
        setTimeout(() => { overlay.style.display = 'none'; }, 300);
    }
    _tipsActive = false;
}

function setAnatomyProgressIndeterminate(on) {
    var bar = document.getElementById('fin-anatomy-progress-bar');
    var tipBar = document.getElementById('fin-tips-progress-bar');
    if (bar) bar.classList.toggle('indeterminate', !!on);
    if (tipBar) tipBar.classList.toggle('indeterminate', !!on);
}

function updateAnatomyProgress(pct, text) {
    var container = document.getElementById('fin-anatomy-progress-container');
    var bar = document.getElementById('fin-anatomy-progress-bar');
    var txt = document.getElementById('fin-anatomy-progress-text');
    var pctEl = document.getElementById('fin-anatomy-progress-pct');
    if (!container || !bar) return;
    
    if (pct < 0) {
        if (_anatomyProgressInterval) clearInterval(_anatomyProgressInterval);
        setAnatomyProgressIndeterminate(false);
        container.style.display = 'none';
        closeAnatomyTips(false);
        var legendBox = document.getElementById('fin-anatomy-legend');
        var waffleBox = document.getElementById('fin-anatomy-waffle');
        var forecastBox = document.getElementById('fin-anatomy-forecast');
        if (legendBox) legendBox.style.opacity = '1';
        if (waffleBox) waffleBox.style.opacity = '1';
        if (forecastBox) forecastBox.style.opacity = '1';
        return;
    }
    
    container.style.display = 'block';
    bar.style.width = pct + '%';
    if (txt && text) txt.innerText = text;
    if (pctEl) pctEl.innerText = Math.round(pct) + '%';
    
    updateAnatomyTipForProgress(pct);
    
    if (pct >= 100) {
        if (_anatomyProgressInterval) clearInterval(_anatomyProgressInterval);
        setAnatomyProgressIndeterminate(false);
        var legendBox = document.getElementById('fin-anatomy-legend');
        var waffleBox = document.getElementById('fin-anatomy-waffle');
        var forecastBox = document.getElementById('fin-anatomy-forecast');
        if (legendBox) legendBox.style.opacity = '1';
        if (waffleBox) waffleBox.style.opacity = '1';
        if (forecastBox) forecastBox.style.opacity = '1';
        setTimeout(function() { container.style.display = 'none'; }, 800);
    }
}

function stopAnatomySmoothProgress() {
    if (_anatomyProgressInterval) {
        clearInterval(_anatomyProgressInterval);
        _anatomyProgressInterval = null;
    }
    setAnatomyProgressIndeterminate(false);
}

function startAnatomySmoothProgress(startPct, capPct, text) {
    stopAnatomySmoothProgress();
    setAnatomyProgressIndeterminate(true);
    let current = startPct;
    let cap = capPct;
    let startedAt = Date.now();
    updateAnatomyProgress(current, text);

    _anatomyProgressInterval = setInterval(function () {
        if (current < cap) {
            let remaining = cap - current;
            let delta = Math.max(0.08, Math.min(0.9, remaining * 0.08));
            current = Math.min(cap, current + delta);
        } else {
            let t = (Date.now() - startedAt) / 1000;
            current = cap - 0.6 + ((Math.sin(t * 2.2) + 1) * 0.3);
        }
        updateAnatomyProgress(current);
    }, 250);
}

function startAnatomySimulatedProgress(startPct, endPct, durationMs, text) {
    if (_anatomyProgressInterval) clearInterval(_anatomyProgressInterval);
    updateAnatomyProgress(startPct, text);
    
    let current = startPct;
    let stepMs = 200;
    let stepPct = (endPct - startPct) / (durationMs / stepMs);
    
    _anatomyProgressInterval = setInterval(function() {
        current += stepPct;
        if (current >= endPct) {
            current = endPct;
            clearInterval(_anatomyProgressInterval);
        }
        updateAnatomyProgress(current);
    }, stepMs);
}

function shouldShowProphetInfo() {
    if (_prophetInfoShown) return false;
    try {
        if (window && window.__datia_prophet_info_shown) return false;
    } catch (_) { }
    try {
        return localStorage.getItem('datia-anatomy-prophet-help-dismissed') !== 'true';
    } catch (_) {
        return true;
    }
}

function closeProphetInfoModal() {
    var overlay = document.getElementById('fin-prophet-info-overlay');
    if (!overlay) return;
    try {
        var dismiss = document.getElementById('fin-prophet-info-dismiss');
        if (dismiss && dismiss.checked) {
            try { localStorage.setItem('datia-anatomy-prophet-help-dismissed', 'true'); } catch (_) { }
        }
    } catch (_) { }
    overlay.style.display = 'none';
    try { document.body.classList.remove('modal-open'); } catch (_) { }
}

function openProphetInfoModal() {
    var overlay = document.getElementById('fin-prophet-info-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    try { document.body.classList.add('modal-open'); } catch (_) { }
    _prophetInfoShown = true;
    try { if (window) window.__datia_prophet_info_shown = true; } catch (_) { }

    var closeBtn = document.getElementById('fin-prophet-info-close');
    var okBtn = document.getElementById('fin-prophet-info-ok');
    if (closeBtn) closeBtn.onclick = function () { closeProphetInfoModal(); };
    if (okBtn) okBtn.onclick = function () { closeProphetInfoModal(); };

    overlay.onclick = function (e) {
        if (e && e.target === overlay) closeProphetInfoModal();
    };

    var onKey = function (e) {
        if (!e) return;
        if (e.key === 'Escape') {
            closeProphetInfoModal();
            try { document.removeEventListener('keydown', onKey); } catch (_) { }
        }
    };
    document.addEventListener('keydown', onKey);
}

function loadUtilityAnatomy() {
    var panel = document.getElementById('sub-anatomia');
    var legendBox = document.getElementById('fin-anatomy-legend');
    var waffleBox = document.getElementById('fin-anatomy-waffle');
    if (!(panel && (panel.classList.contains('active') || panel.style.display !== 'none'))) {
        if (legendBox) legendBox.innerHTML = '<div class="fin-empty">Abra la subpestaña Anatomía</div>';
        if (waffleBox) waffleBox.innerHTML = '';
        return;
    }
    var selEjeEl = document.getElementById('sel-ejercicio');
    var selYear = selEjeEl && selEjeEl.value ? parseInt(selEjeEl.value) : null;
    var currYear = (currEjercicio ? parseInt(currEjercicio) : null);
    var year = currYear || selYear || new Date().getFullYear();
    if (!year || isNaN(year)) year = new Date().getFullYear();
    var start = Math.max(2008, year - 1);
    var end = year;
    var selEmpEl = document.getElementById('sel-empresa');
    var empVal = selEmpEl && selEmpEl.value ? selEmpEl.value : (currEmpresa || '');
    if (!empVal) { 
        if (legendBox) legendBox.innerHTML = '<div class="fin-empty">Seleccione empresa</div>';
        if (waffleBox) waffleBox.innerHTML = '';
        updateAnatomyProgress(-1);
        setTimeout(function(){ try { loadUtilityAnatomy(); } catch(e){} }, 200); 
        return; 
    }
    
    var myToken = Date.now();
    _anatomyLoadToken = myToken;
    
    initAnatomyTips();
    
    if (legendBox && legendBox.innerHTML.trim() === '') {
        // Primera carga: mostrar algo base o nada
    } else {
        // Recarga: opacar contenido anterior en lugar de borrarlo
        if (legendBox) legendBox.style.opacity = '0.3';
        if (waffleBox) waffleBox.style.opacity = '0.3';
        var forecastBox = document.getElementById('fin-anatomy-forecast');
        if (forecastBox) forecastBox.style.opacity = '0.3';
    }

    startAnatomySmoothProgress(5, 48, (typeof gettext==='function'?gettext('Consultando datos base...'):'Consultando datos base...'));

    var q = '?empresa=' + encodeURIComponent(empVal) + '&start_year=' + start + '&end_year=' + end;
    fetch('/api/financial/anatomy/utility' + q).then(function(r){return r.json()}).then(function(json){
        if (_anatomyLoadToken !== myToken) return;
        stopAnatomySmoothProgress();
        updateAnatomyProgress(55, (typeof gettext==='function'?gettext('Renderizando matriz...'):'Renderizando matriz...'));
        
        setTimeout(function() {
            if (_anatomyLoadToken !== myToken) return;
            renderAnatomy(json, year);
            
            startAnatomySmoothProgress(60, 95, (typeof gettext==='function'?gettext('Calculando predicción (IA)...'):'Calculando predicción (IA)...'));
            
            var yrs = getAnatomyForecastYears();
            var fStart = Math.max(2008, year - (yrs - 1));
            loadUtilityForecast(fStart, end, myToken);
        }, 50);
    }).catch(function(e){
          if (_anatomyLoadToken !== myToken) return;
          updateAnatomyProgress(-1);
          console.error("Error en loadUtilityAnatomy:", e);
          var legend = document.getElementById('fin-anatomy-legend');
          var cont = document.getElementById('fin-anatomy-waffle');
          if (legend) { legend.innerHTML = '<div class="fin-empty">Error: ' + e.message + '</div>'; legend.style.opacity = '1'; }
          if (cont) { cont.innerHTML = '<div class="fin-empty">Sin datos disponibles</div>'; cont.style.opacity = '1'; }
      });
}

function getAnatomyForecastYears(){
    var v = 5;
    try {
        var s = localStorage.getItem('datia-anatomy-years');
        if (s) v = Math.max(1, parseInt(s));
    } catch(e) {}
    return v;
}

function changeAnatomyYears(val){
    try { localStorage.setItem('datia-anatomy-years', String(Math.max(1, parseInt(val||'5')))); } catch(e) {}
    try {
        var selEjeEl = document.getElementById('sel-ejercicio');
        var year = selEjeEl && selEjeEl.value ? parseInt(selEjeEl.value) : (currEjercicio ? parseInt(currEjercicio) : new Date().getFullYear());
        var yrs = getAnatomyForecastYears();
        var fStart = Math.max(2008, year - (yrs - 1));
        loadUtilityForecast(fStart, year);
    } catch(e) {}
}

function getAnatomyPLEq(){
    var v = false;
    try {
        var s = localStorage.getItem('datia-anatomy-pl-eq');
        v = (s === 'true');
    } catch(e) {}
    return v;
}

function changeAnatomyPLEq(val){
    try { localStorage.setItem('datia-anatomy-pl-eq', String(!!val)); } catch(e) {}
    try { loadUtilityAnatomy(); } catch(e) {}
}

function loadUtilityForecast(start, end, parentToken) {
    var panel = document.getElementById('sub-anatomia');
    if (!(panel && (panel.classList.contains('active') || panel.style.display !== 'none'))) return;
    var token = Date.now();
    window.datiaAnatomyForecastToken = token;
    fetch('/api/financial/anatomy/forecast?empresa=' + currEmpresa + '&start_year=' + start + '&end_year=' + end).then(function(r){return r.json()}).then(function(json){
        if (window.datiaAnatomyForecastToken !== token) return;
        if (parentToken && _anatomyLoadToken === parentToken) {
            stopAnatomySmoothProgress();
            updateAnatomyProgress(100, (typeof gettext==='function'?gettext('Carga completada'):'Carga completada'));
        }
        var container = document.getElementById('fin-anatomy-forecast');
        var chart = document.getElementById('fin-anatomy-forecast-chart');
        var explain = document.getElementById('fin-anatomy-forecast-explain');
        if (!container || !json || !json.forecast) return;
        var pal = (window.datiaAnatomyTotals && window.datiaAnatomyTotals.palette) ? window.datiaAnatomyTotals.palette : computeAnatomyPalette(getAnatomyBaseColor());
        var yearLbl = (json && json.year) ? json.year : (window.datiaAnatomyTotals && window.datiaAnatomyTotals.year ? (parseInt(window.datiaAnatomyTotals.year)+1) : new Date().getFullYear()+1);
        var title = container.querySelector('#fin-anatomy-forecast-title');
        if (!title) {
            title = document.createElement('div');
            title.id = 'fin-anatomy-forecast-title';
            title.className = 'fin-anatomy-section-title';
            container.insertBefore(title, chart);
        }
        title.innerText = 'Forecast '+yearLbl;
        var axis = container.querySelector('#fin-anatomy-forecast-axis');
        if (!axis) {
            axis = document.createElement('div');
            axis.id = 'fin-anatomy-forecast-axis';
            axis.className = 'fin-axis';
            container.insertBefore(axis, chart.nextSibling);
        }
        var fc = (Array.isArray(json.forecast) ? json.forecast.slice() : []);
        fc.sort(function(a,b){ return (a.quarter||0) - (b.quarter||0); });
        var labels = fc.map(function(x){ return 'Q'+(x.quarter||''); });
        var base = fc.map(function(x){ return parseFloat(x.utilidad_neta||0); });
        var low = fc.map(function(x){ return parseFloat(x.low||0); });
        var high = fc.map(function(x){ return parseFloat(x.high||0); });
        var band = high.map(function(h,i){ var l = low[i]||0; return (h - l); });
        var canvas = chart.querySelector('.fin-forecast-canvas');
        if (!canvas) {
            chart.innerHTML = '';
            canvas = document.createElement('div');
            canvas.className = 'fin-forecast-canvas';
            chart.appendChild(canvas);
        }
        try { canvas.style.height = '260px'; } catch(e) {}
        if (typeof echarts !== 'undefined') {
            var inst = echarts.getInstanceByDom(canvas);
            if (!inst) inst = echarts.init(canvas, null, { renderer: 'svg' });
            else inst.clear();
            function rgba(hex, a){
                var rgb = hexToRgb(hex);
                return 'rgba('+rgb.r+','+rgb.g+','+rgb.b+','+(a||0.35)+')';
            }
            var option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'cross' },
                    formatter: function(params){
                        var q = params[0] && params[0].axisValue || '';
                        var valUN = params.find(function(p){return p.seriesName==='Utilidad Neta'})?.value || 0;
                        var idx = labels.indexOf(q);
                        var l = low[idx]||0, h = high[idx]||0;
                        return '<div style="margin-bottom:4px;">'+q+'</div>' +
                               '<div style="display:flex;justify-content:space-between;gap:10px;"><span style="color:'+pal.un+'">'+(typeof gettext==='function'?gettext('Utilidad Neta'):'Utilidad Neta')+'</span><span style="font-weight:600;color:#fff">'+fmtMoney.format(valUN)+'</span></div>' +
                               '<div style="display:flex;justify-content:space-between;gap:10px;"><span style="color:#a1a1aa">'+(typeof gettext==='function'?gettext('Banda Low–High'):'Banda Low–High')+'</span><span style="font-weight:600;color:#fff">['+fmtMoney.format(l)+' – '+fmtMoney.format(h)+']</span></div>';
                    }
                },
                legend: { textStyle: { color: '#9ca3af' }, top: 0 },
                grid: { left: '5%', right: '5%', bottom: '5%', top: '18%', containLabel: true },
                xAxis: { type: 'category', data: labels, axisLabel: { color: '#a1a1aa' } },
                yAxis: { type: 'value', axisLabel: { color: '#a1a1aa', formatter: function(v){ return fmtMoney.format(v).replace(' €',''); } }, splitLine: { lineStyle: { color: '#27272a' } } },
                series: [
                    { name: 'Low', type: 'line', data: low, lineStyle: { width: 0 }, showSymbol: false, stack: 'interval' },
                    { name: (typeof gettext==='function'?gettext('Banda'):'Banda'), type: 'line', data: band, lineStyle: { width: 0 }, showSymbol: false, stack: 'interval', areaStyle: { color: rgba(pal.un, 0.25) } },
                    { name: (typeof gettext==='function'?gettext('Utilidad Neta'):'Utilidad Neta'), type: 'line', data: base, smooth: true, lineStyle: { width: 2, color: pal.un }, itemStyle: { color: pal.un }, showSymbol: true }
                ]
            };
            inst.setOption(option);
            if (!canvas._datiaResizeBound) {
                canvas._datiaResizeBound = true;
                window.addEventListener('resize', function(){ try { inst.resize(); } catch(e){} });
            }
        } else {
            var nf = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            var grid = document.createElement('div'); grid.className = 'fin-anatomy-bars';
            var denom = Math.max.apply(null, base.concat(low).concat(high).map(function(v){return Math.abs(v)||1;}));
            base.forEach(function(val, i){
                var row = document.createElement('div'); row.className = 'row';
                var bar = document.createElement('div'); bar.className = 'bar';
                var fill = document.createElement('div'); fill.className = 'fill'; fill.style.background = pal.un;
                fill.style.width = Math.max(0, Math.min(100, (Math.abs(val)/denom)*100))+'%';
                bar.appendChild(fill);
                var lbl = document.createElement('div'); lbl.className = 'fin-bar-label'; lbl.innerText = labels[i];
                var valEl = document.createElement('div'); valEl.className = 'fin-bar-value'; valEl.innerText = nf.format(val)+' €';
                var wrap = document.createElement('div'); wrap.style.display = 'flex'; wrap.style.alignItems = 'center';
                wrap.appendChild(lbl); wrap.appendChild(valEl);
                row.appendChild(bar); row.appendChild(wrap);
                grid.appendChild(row);
            });
            canvas.innerHTML = '';
            canvas.appendChild(grid);
        }
        var pf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
        var exp = '';
        var cyQ = (window.datiaAnatomyQuarters && Array.isArray(window.datiaAnatomyQuarters.cy)) ? window.datiaAnatomyQuarters.cy : null;
        var yoyHtml = '';
        if (cyQ) {
            yoyHtml += '<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;align-items:center;color:#a1a1aa;margin-top:8px;"><div style="font-weight:600;">'+((typeof gettext==='function'?gettext('YoY vs'):'YoY vs')+' '+end)+'</div><div>CY</div><div>Forecast</div><div>Var %</div></div>';
            base.forEach(function(v,i){
                var cyv = cyQ[i]||0;
                var varpct = cyv ? ((v - cyv) / Math.abs(cyv) * 100.0) : 0.0;
                var color = varpct >= 0 ? '#34d399' : '#ef4444';
                yoyHtml += '<div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:8px;align-items:center;">' +
                    '<div>'+labels[i]+'</div>' +
                    '<div style="white-space:nowrap;">'+fmtMoney.format(cyv)+'</div>' +
                    '<div style="white-space:nowrap;">'+fmtMoney.format(v)+'</div>' +
                    '<div style="color:'+color+';font-weight:600;white-space:nowrap;">'+pf.format(varpct)+' %</div>' +
                '</div>';
            });
        }
        var yrs = getAnatomyForecastYears();
        var startTxt = (end - (yrs - 1));
        exp += '<div style="font-weight:600; margin-top:6px;">Forecast '+yearLbl+' (Prophet trimestral)</div>';
        exp += '<div style="color:#a1a1aa;">'+(typeof gettext==='function'?gettext('Entrenado con'):'Entrenado con')+' '+yrs+' '+(typeof gettext==='function'?gettext('años'):'años')+' ('+startTxt+' → '+end+')</div>';
        exp += '<div>Factores clave: variaciones YoY, estacionalidad trimestral y efecto de impuestos sobre utilidad.</div>';
        exp += '<div>Supuestos: continuidad operativa, estacionalidad anual y marco fiscal estable.</div>';
        exp += '<div>Riesgos y oportunidades: presión de costes y demanda vs. eficiencia administrativa y mix de margen.</div>';
        exp += '<div>Método: Prophet con tendencia y estacionalidad anual, bandas de confianza.</div>';
        explain.innerHTML = (yoyHtml ? (yoyHtml + '<div class="fin-axis"></div>') : '') + exp;
        try {
            if (window.compareView && typeof window.compareView.setAnat === 'function') {
                window.compareView.setAnat({ fc: fc, cyQ: (window.datiaAnatomyQuarters ? window.datiaAnatomyQuarters.cy : null) });
            }
        } catch(e) {}
    }).catch(function(e){
        return;
    });
}

function renderAnatomy(data, year) {
    var legend = document.getElementById('fin-anatomy-legend');
    var cont = document.getElementById('fin-anatomy-waffle');
    if (!legend || !cont) return;
    var dCY = null;
    var dPY = null;
    if (data && data.data) {
        dCY = data.data[year] || data.data[String(year)] || null;
        dPY = data.data[year-1] || data.data[String(year-1)] || null;
    }
    if (!dCY) {
        legend.innerHTML = '<div class="fin-empty">Sin datos disponibles</div>';
        cont.innerHTML = '<div class="fin-empty">Sin datos disponibles</div>';
        return;
    }
    function totals(d) {
        return {
            ingresos: (d.ingresos||[]).reduce(function(a,b){return a+b},0),
            costo_ventas: (d.costo_ventas||[]).reduce(function(a,b){return a+b},0),
            gastos_admin: (d.gastos_admin||[]).reduce(function(a,b){return a+b},0),
            impuestos: (d.impuestos||[]).reduce(function(a,b){return a+b},0),
            ogde: (d.otros_gastos_exp||[]).reduce(function(a,b){return a+b},0),
            utilidad_neta: (d.utilidad_neta||[]).reduce(function(a,b){return a+b},0)
        };
    }
    var tCY = totals(dCY);
    var zeroAll = function(t){ return Math.abs(t.ingresos)<1e-6 && Math.abs(t.costo_ventas)<1e-6 && Math.abs(t.gastos_admin)<1e-6 && Math.abs(t.impuestos)<1e-6 && Math.abs(t.utilidad_neta)<1e-6; };
    if (zeroAll(tCY)) {
        legend.innerHTML = '<div class="fin-empty">Sin datos disponibles</div>';
        cont.innerHTML = '<div class="fin-empty">Sin datos disponibles</div>';
        return;
    }
    var baseColor = getAnatomyBaseColor();
    var pal = computeAnatomyPalette(baseColor);
    var eq = getAnatomyPLEq();
    var partsCY = eq ? [
        {key:'costo_ventas', label:'Coste de Ventas', color:pal.cv, val:tCY.costo_ventas},
        {key:'otros_gastos_exp', label:'Otros Gastos de Explotación', color:pal.ga, val:tCY.ogde},
        {key:'utilidad_neta', label:'Utilidad Neta', color:pal.un, val:tCY.utilidad_neta}
    ] : [
        {key:'costo_ventas', label:'Coste de Ventas', color:pal.cv, val:tCY.costo_ventas},
        {key:'gastos_admin', label:'Gastos Administrativos', color:pal.ga, val:tCY.gastos_admin},
        {key:'impuestos', label:'Impuestos', color:pal.imp, val:tCY.impuestos},
        {key:'utilidad_neta', label:'Utilidad Neta', color:pal.un, val:tCY.utilidad_neta}
    ];
    var totalCY = tCY.ingresos || 1;
    var pctCY = partsCY.map(function(x){return {key:x.key,label:x.label,color:x.color,pct:((x.val/totalCY)*100)}});
    var htmlLegendCY = '<div style="font-weight:600; color:#a1a1aa;">'+year+'</div>' + pctCY.map(function(x){
        return '<div style="display:flex;align-items:center;gap:8px;"><span style="width:12px;height:12px;background:'+x.color+';display:inline-block;border-radius:2px;"></span><span>'+x.label+'</span><span style="margin-left:auto;font-weight:600;">'+x.pct.toFixed(1)+'%</span></div>';
    }).join('');
    var htmlLegendPY = '';
    var pctPY = [];
    if (dPY) {
        var tPY = totals(dPY);
        var partsPY = eq ? [
            {key:'costo_ventas', label:'Coste de Ventas', color:pal.cv, val:tPY.costo_ventas},
            {key:'otros_gastos_exp', label:'Otros Gastos de Explotación', color:pal.ga, val:tPY.ogde},
            {key:'utilidad_neta', label:'Utilidad Neta', color:pal.un, val:tPY.utilidad_neta}
        ] : [
            {key:'costo_ventas', label:'Coste de Ventas', color:pal.cv, val:tPY.costo_ventas},
            {key:'gastos_admin', label:'Gastos Administrativos', color:pal.ga, val:tPY.gastos_admin},
            {key:'impuestos', label:'Impuestos', color:pal.imp, val:tPY.impuestos},
            {key:'utilidad_neta', label:'Utilidad Neta', color:pal.un, val:tPY.utilidad_neta}
        ];
        var totalPY = tPY.ingresos || 1;
        pctPY = partsPY.map(function(x){return {key:x.key,label:x.label,color:x.color,pct:((x.val/totalPY)*100)}});
        htmlLegendPY = '<div style="font-weight:600; color:#a1a1aa;">'+(year-1)+'</div>' + pctPY.map(function(x){
            return '<div style="display:flex;align-items:center;gap:8px;"><span style="width:12px;height:12px;background:'+x.color+';display:inline-block;border-radius:2px;"></span><span>'+x.label+'</span><span style="margin-left:auto;font-weight:600;">'+x.pct.toFixed(1)+'%</span></div>';
        }).join('');
    } else {
        htmlLegendPY = '<div class="fin-empty">Sin datos del año anterior</div>';
    }
    legend.innerHTML = '<div class="fin-anatomy-compare"><div>'+htmlLegendCY+'</div><div>'+htmlLegendPY+'</div></div>';
    function renderGrid(container, pct){
        var grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = 'repeat(10, 1fr)';
        grid.style.gridAutoRows = '20px';
        grid.style.gap = '4px';
        var cells = [];
        var acc = 0;
        pct.forEach(function(x){
            var count = Math.round(x.pct);
            for (var i=0;i<count;i++){
                cells.push({color:x.color,title:x.label+' '+x.pct.toFixed(1)+'%'});
            }
            acc += count;
        });
        while (acc < 100) { cells.push({color:'rgba(255,255,255,0.08)', title:'Resto'}); acc += 1; }
        for (var i=0;i<100;i++){
            var cell = document.createElement('div');
            var item = cells[i] || {color:'#444', title:''};
            cell.style.background = item.color;
            cell.style.borderRadius = '3px';
            cell.title = item.title;
            grid.appendChild(cell);
        }
        container.appendChild(grid);
    }
    cont.innerHTML = '';
    var cmp = document.createElement('div');
    cmp.className = 'fin-anatomy-compare';
    var left = document.createElement('div');
    var right = document.createElement('div');
    cmp.appendChild(left); cmp.appendChild(right);
    cont.appendChild(cmp);
    renderGrid(left, pctCY);
    if (pctPY.length) renderGrid(right, pctPY);
    var barsWrap = document.createElement('div');
    barsWrap.className = 'fin-anatomy-bars';
    var denom = Math.max(tCY.ingresos||1, (dPY ? totals(dPY).ingresos||1 : tCY.ingresos||1));
    function makeRow(label, val, color){
        var r = document.createElement('div');
        r.className = 'row';
        var bar = document.createElement('div');
        bar.className = 'bar';
        var fill = document.createElement('div');
        fill.className = 'fill';
        fill.style.background = color;
        fill.style.width = Math.max(0, Math.min(100, (val/denom)*100))+'%';
        bar.appendChild(fill);
        var lbl = document.createElement('div');
        lbl.style.whiteSpace = 'nowrap';
        lbl.innerText = label;
        r.appendChild(bar);
        r.appendChild(lbl);
        return r;
    }
    var tPYvals = dPY ? totals(dPY) : {costo_ventas:0,gastos_admin:0,impuestos:0,utilidad_neta:0};
    var colLeft = document.createElement('div');
    var colRight = document.createElement('div');
    if (eq) {
        colLeft.appendChild(makeRow('Coste de Ventas', tCY.costo_ventas, pal.cv));
        colLeft.appendChild(makeRow('Otros Gastos de Explotación', tCY.ogde, pal.ga));
        colLeft.appendChild(makeRow('Utilidad Neta', tCY.utilidad_neta, pal.un));
        colRight.appendChild(makeRow('Coste de Ventas', tPYvals.costo_ventas, pal.cv));
        colRight.appendChild(makeRow('Otros Gastos de Explotación', tPYvals.ogde, pal.ga));
        colRight.appendChild(makeRow('Utilidad Neta', tPYvals.utilidad_neta, pal.un));
    } else {
        colLeft.appendChild(makeRow('Coste de Ventas', tCY.costo_ventas, pal.cv));
        colLeft.appendChild(makeRow('Gastos Administrativos', tCY.gastos_admin, pal.ga));
        colLeft.appendChild(makeRow('Impuestos', tCY.impuestos, pal.imp));
        colLeft.appendChild(makeRow('Utilidad Neta', tCY.utilidad_neta, pal.un));
        colRight.appendChild(makeRow('Coste de Ventas', tPYvals.costo_ventas, pal.cv));
        colRight.appendChild(makeRow('Gastos Administrativos', tPYvals.gastos_admin, pal.ga));
        colRight.appendChild(makeRow('Impuestos', tPYvals.impuestos, pal.imp));
        colRight.appendChild(makeRow('Utilidad Neta', tPYvals.utilidad_neta, pal.un));
    }
    barsWrap.appendChild(colLeft);
    barsWrap.appendChild(colRight);
    cont.appendChild(barsWrap);
    var yoyDiv = document.createElement('div');
    yoyDiv.style.marginTop = '12px';
    if (dPY) {
        var empresa = (document.getElementById('sel-empresa')?.value) || currEmpresa;
        var urlCY = '/api/financial/pl?empresa='+encodeURIComponent(empresa)+'&ejercicio='+encodeURIComponent(year)+'&level=2';
        var urlPY = '/api/financial/pl?empresa='+encodeURIComponent(empresa)+'&ejercicio='+encodeURIComponent(year-1)+'&level=2';
        Promise.all([
            fetch(urlCY).then(function(r){return r.json()}),
            fetch(urlPY).then(function(r){return r.json()})
        ]).then(function(resp){
            var rCY = resp[0] || {};
            var rPY = resp[1] || {};
            function sumByPrefixes(rows, prefixes){
                if (!rows || !rows.rows) return 0;
                var s = 0;
                prefixes.forEach(function(pref){
                    rows.rows.forEach(function(x){
                        var c = x.cuenta ? String(x.cuenta) : '';
                        if (!x.is_header && c && c.indexOf(pref) === 0) {
                            s += parseFloat(x.valor||0);
                        }
                    });
                });
                return s;
            }
            var ingCY = Math.abs(sumByPrefixes(rCY, ['70','71','72','73','74','75','76','77','78','79']));
            var ingPY = Math.abs(sumByPrefixes(rPY, ['70','71','72','73','74','75','76','77','78','79']));
            var cvCY = sumByPrefixes(rCY, ['60']);
            var cvPY = sumByPrefixes(rPY, ['60']);
            var ogdeCY = eq ? (sumByPrefixes(rCY, ['62','63','64','65','68','69','66','67'])) : 0;
            var ogdePY = eq ? (sumByPrefixes(rPY, ['62','63','64','65','68','69','66','67'])) : 0;
            var gaCY = sumByPrefixes(rCY, ['62','65','69']);
            var gaPY = sumByPrefixes(rPY, ['62','65','69']);
            var impCY = sumByPrefixes(rCY, ['63']);
            var impPY = sumByPrefixes(rPY, ['63']);
            var perCY = sumByPrefixes(rCY, ['64']);
            var perPY = sumByPrefixes(rPY, ['64']);
            var amoCY = sumByPrefixes(rCY, ['68']);
            var amoPY = sumByPrefixes(rPY, ['68']);
            var finCY = sumByPrefixes(rCY, ['66','67']);
            var finPY = sumByPrefixes(rPY, ['66','67']);
            var utilCY = eq ? (ingCY - cvCY - ogdeCY) : (ingCY - cvCY - gaCY - impCY - perCY - amoCY - finCY);
            var utilPY = eq ? (ingPY - cvPY - ogdePY) : (ingPY - cvPY - gaPY - impPY - perPY - amoPY - finPY);
            var nf = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            var pf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
            var symbol = '€';
            var rows = eq ? [
                {label:'Ingresos', cy:ingCY, py:ingPY},
                {label:'Coste de Ventas', cy:cvCY, py:cvPY},
                {label:'Otros Gastos de Explotación', cy:ogdeCY, py:ogdePY},
                {label:'Utilidad Neta', cy:utilCY, py:utilPY}
            ] : [
                {label:'Ingresos', cy:ingCY, py:ingPY},
                {label:'Coste de Ventas', cy:cvCY, py:cvPY},
                {label:'Gastos Administrativos', cy:gaCY, py:gaPY},
                {label:'Impuestos', cy:impCY, py:impPY},
                {label:'Gastos de Personal', cy:perCY, py:perPY},
                {label:'Amortizaciones y Deterioros', cy:amoCY, py:amoPY},
                {label:'Resultado Financiero', cy:finCY, py:finPY},
                {label:'Utilidad Neta', cy:utilCY, py:utilPY}
            ];
            var html = '<div style="display:grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap:8px; align-items:center; color:#a1a1aa;">' +
                '<div style="font-weight:600;">Variación interanual ('+(year-1)+'→'+year+')</div><div>PY</div><div>CY</div><div>Var %</div></div>';
            rows.forEach(function(r){
                var varpct = r.py ? ((r.cy - r.py) / r.py * 100.0) : 0.0;
                var color = varpct >= 0 ? '#34d399' : '#ef4444';
                html += '<div style="display:grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap:8px; align-items:center;">' +
                    '<div>'+r.label+'</div>' +
                    '<div style="white-space:nowrap;">'+nf.format(r.py)+' '+symbol+'</div>' +
                    '<div style="white-space:nowrap;">'+nf.format(r.cy)+' '+symbol+'</div>' +
                    '<div style="color:'+color+'; font-weight:600; white-space:nowrap;">'+pf.format(varpct)+' %</div>' +
                '</div>';
            });
            yoyDiv.innerHTML = html;
        }).catch(function(){
            yoyDiv.innerHTML = '<div class="fin-empty">YoY no disponible</div>';
        });
    } else {
        yoyDiv.innerHTML = '<div class="fin-empty">Sin datos del año anterior</div>';
    }
    cont.appendChild(yoyDiv);
    window.datiaAnatomyTotals = {year:year, cy:tCY, py:(dPY ? totals(dPY) : null), palette:pal};
    try {
        var qCY = (dCY && Array.isArray(dCY.utilidad_neta)) ? dCY.utilidad_neta.slice() : null;
        var qPY = (dPY && Array.isArray(dPY.utilidad_neta)) ? dPY.utilidad_neta.slice() : null;
        window.datiaAnatomyQuarters = { cy: qCY, py: qPY };
    } catch(e) {}
    renderExpensesSection(year);
    try { loadPer100(year); } catch(e) {}
}

function exportAnatomyCSV() {
    var year = (typeof currEjercicio !== 'undefined' && currEjercicio) ? parseInt(currEjercicio) : (document.getElementById('sel-ejercicio')?.value ? parseInt(document.getElementById('sel-ejercicio').value) : new Date().getFullYear());
    var cont = document.getElementById('fin-anatomy-legend');
    if (!cont) return;
    var rows = [['Categoria','PY ('+(year-1)+')','CY ('+year+')','Var %']];
    // Parse legends by columns
    var cols = cont.querySelectorAll('.fin-anatomy-compare > div');
    var mapPY = {}, mapCY = {};
    function parseCol(col, map){
        var divs = col.querySelectorAll('div');
        divs.forEach(function(d){
            var spans = d.querySelectorAll('span');
            if (spans.length>=3){
                var label = spans[1].innerText;
                var pct = spans[2].innerText;
                map[label] = pct;
            }
        });
    }
    if (cols.length>=1) parseCol(cols[0], mapCY);
    if (cols.length>=2) parseCol(cols[1], mapPY);
    var labels = getAnatomyPLEq() ? ['Coste de Ventas','Otros Gastos de Explotación','Utilidad Neta'] : ['Coste de Ventas','Gastos Administrativos','Impuestos','Utilidad Neta'];
    labels.forEach(function(lbl){
        var py = parseFloat(String(mapPY[lbl]||'0').replace('%',''))||0;
        var cy = parseFloat(String(mapCY[lbl]||'0').replace('%',''))||0;
        var vp = (cy - py).toFixed(1) + '%';
        rows.push([lbl, mapPY[lbl]||'', mapCY[lbl]||'', vp]);
    });
    var csv = rows.map(function(r){return r.join(',')}).join('\n');
    var blob = new Blob([csv], {type:'text/csv'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'anatomia_utilidad_'+year+'.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function exportAnatomyPNG() {
    var year = (typeof currEjercicio !== 'undefined' && currEjercicio) ? parseInt(currEjercicio) : (document.getElementById('sel-ejercicio')?.value ? parseInt(document.getElementById('sel-ejercicio').value) : new Date().getFullYear());
    var cont = document.getElementById('fin-anatomy-waffle');
    if (!cont) return;
    var canvas = document.createElement('canvas');
    var rect = cont.getBoundingClientRect();
    canvas.width = Math.max(300, Math.floor(rect.width));
    canvas.height = 220;
    var ctx = canvas.getContext('2d');
    ctx.fillStyle = '#1f1f22';
    ctx.fillRect(0,0,canvas.width,canvas.height);
    var grid = cont.querySelector('div');
    if (grid) {
        var boxes = grid.children;
        var cols = 10;
        var size = 18;
        var gap = 4;
        var startX = 10;
        var startY = 10;
        for (var i=0;i<boxes.length;i++){
            var r = Math.floor(i/cols);
            var c = i%cols;
            var x = startX + c*(size+gap);
            var y = startY + r*(size+gap);
            var color = window.getComputedStyle(boxes[i]).backgroundColor;
            ctx.fillStyle = color;
            ctx.fillRect(x,y,size,size);
        }
    }
    var a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = 'anatomia_utilidad_'+year+'.png';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

function renderExpensesSection(year){
    var wrap = document.getElementById('fin-anatomy-expenses');
    if (!wrap) return;
    var token = Date.now();
    window.datiaAnatomyExpensesToken = token;
    wrap.innerHTML = '';
    var empresa = (document.getElementById('sel-empresa')?.value) || currEmpresa;
    if (!empresa) return;
    var pal = (window.datiaAnatomyTotals && window.datiaAnatomyTotals.palette) ? window.datiaAnatomyTotals.palette : computeAnatomyPalette(getAnatomyBaseColor());
    var urlCY = '/api/financial/pl?empresa='+encodeURIComponent(empresa)+'&ejercicio='+encodeURIComponent(year)+'&level=2';
    var urlPY = '/api/financial/pl?empresa='+encodeURIComponent(empresa)+'&ejercicio='+encodeURIComponent(year-1)+'&level=2';
    Promise.all([
        fetch(urlCY).then(function(r){return r.json()}),
        fetch(urlPY).then(function(r){return r.json()})
    ]).then(function(resp){
        if (window.datiaAnatomyExpensesToken !== token) return;
        var rCY = resp[0] || {};
        var rPY = resp[1] || {};
        function sumByPrefixes(rows, prefixes){
            if (!rows || !rows.rows) return 0;
            var s = 0;
            prefixes.forEach(function(pref){
                rows.rows.forEach(function(x){
                    var c = x.cuenta ? String(x.cuenta) : '';
                    if (!x.is_header && c && c.indexOf(pref) === 0) {
                        s += parseFloat(x.valor||0);
                    }
                });
            });
            return s;
        }
        var defs = (getAnatomyPLEq() ? [
            {label:'Compras y Aprovisionamientos', prefixes:['60'], color:pal.cv},
            {label:'Otros Gastos de Explotación', prefixes:['62','63','64','65','68','69','66','67'], color:shadeHex(pal.ga, -0.05)}
        ] : [
            {label:'Compras y Aprovisionamientos', prefixes:['60'], color:pal.cv},
            {label:'Gastos de Personal', prefixes:['64'], color:shadeHex(pal.ga, -0.05)},
            {label:'Otros Gastos de Explotación', prefixes:['62','63','65','69'], color:shadeHex(pal.ga, -0.15)},
            {label:'Amortizaciones y Deterioros', prefixes:['68'], color:pal.imp},
            {label:'Resultado Financiero', prefixes:['66','67'], color:shadeHex(pal.imp, 0.1)}
        ]);
        var nf = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        var leftCol = document.createElement('div');
        var rightCol = document.createElement('div');
        var bars = document.createElement('div');
        bars.className = 'fin-anatomy-bars';
        var denom = 1;
        var vals = defs.map(function(m){
            var cy = sumByPrefixes(rCY, m.prefixes);
            var py = sumByPrefixes(rPY, m.prefixes);
            denom = Math.max(denom, Math.abs(cy), Math.abs(py), 1);
            return {m:m, cy:cy, py:py};
        });
        vals.forEach(function(v){
            var rowCY = document.createElement('div');
            rowCY.className = 'row';
            var barCY = document.createElement('div'); barCY.className = 'bar';
            var fillCY = document.createElement('div'); fillCY.className = 'fill';
            fillCY.style.background = v.m.color;
            fillCY.style.width = Math.max(0, Math.min(100, (Math.abs(v.cy)/denom)*100))+'%';
            barCY.appendChild(fillCY);
            var labelCY = document.createElement('div'); labelCY.className = 'fin-bar-label';
            labelCY.innerText = v.m.label + ' ('+nf.format(v.cy)+' €)';
            rowCY.appendChild(barCY); rowCY.appendChild(labelCY);
            leftCol.appendChild(rowCY);
            var rowPY = document.createElement('div');
            rowPY.className = 'row';
            var barPY = document.createElement('div'); barPY.className = 'bar';
            var fillPY = document.createElement('div'); fillPY.className = 'fill';
            fillPY.style.background = v.m.color;
            fillPY.style.width = Math.max(0, Math.min(100, (Math.abs(v.py)/denom)*100))+'%';
            barPY.appendChild(fillPY);
            var labelPY = document.createElement('div'); labelPY.className = 'fin-bar-label';
            labelPY.innerText = v.m.label + ' ('+nf.format(v.py)+' €)';
            rowPY.appendChild(barPY); rowPY.appendChild(labelPY);
            rightCol.appendChild(rowPY);
        });
        var title = document.createElement('div');
        title.className = 'fin-anatomy-section-title';
        title.innerText = 'Desglose de Gastos';
        wrap.appendChild(title);
        var axis = document.createElement('div');
        axis.className = 'fin-axis';
        wrap.appendChild(axis);
        bars.appendChild(leftCol); bars.appendChild(rightCol);
        wrap.appendChild(bars);
        var yoY = document.createElement('div');
        yoY.style.marginTop = '8px';
        var pf = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
        var grid = '<div style="display:grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap:8px; align-items:center; color:#a1a1aa;"><div style="font-weight:600;">YoY Gastos</div><div>PY</div><div>CY</div><div>Var %</div></div>';
        vals.forEach(function(v){
            var varpct = v.py ? ((v.cy - v.py) / Math.abs(v.py) * 100.0) : 0.0;
            var color = varpct >= 0 ? '#ef4444' : '#34d399'; // en gastos, bajar es verde
            grid += '<div style="display:grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap:8px; align-items:center;">' +
                '<div>'+v.m.label+'</div>' +
                '<div style="white-space:nowrap;">'+nf.format(v.py)+' €</div>' +
                '<div style="white-space:nowrap;">'+nf.format(v.cy)+' €</div>' +
                '<div style="color:'+color+'; font-weight:600; white-space:nowrap;">'+pf.format(varpct)+' %</div>' +
            '</div>';
        });
        yoY.innerHTML = grid;
        wrap.appendChild(yoY);
        // Detalle de variación interanual (contribuciones)
        var totalPY = vals.reduce(function(a,v){return a + (v.py||0)}, 0);
        var totalCY = vals.reduce(function(a,v){return a + (v.cy||0)}, 0);
        var totalDelta = totalCY - totalPY;
        var detail = document.createElement('div');
        detail.className = 'fin-yoy-detail';
        var head = '<div class="fin-anatomy-section-title">Detalle de variación interanual (Contribuciones)</div>';
        head += '<div class="fin-yoy-detail-grid"><div style="font-weight:600;">Componente</div><div style="font-weight:600;">Δ (CY−PY)</div><div style="font-weight:600;">Contribución</div></div>';
        var body = '';
        vals.forEach(function(v){
            var delta = (v.cy||0) - (v.py||0);
            var share = totalDelta !== 0 ? (delta / Math.abs(totalDelta) * 100.0) : 0.0;
            var color = delta >= 0 ? '#ef4444' : '#34d399'; // incremento de gasto: rojo; reducción: verde
            body += '<div class="fin-yoy-detail-grid">' +
                '<div>'+v.m.label+'</div>' +
                '<div style="white-space:nowrap; color:'+color+';">'+nf.format(delta)+' €</div>' +
                '<div style="white-space:nowrap;">'+pf.format(share)+' %</div>' +
            '</div>';
        });
        detail.innerHTML = head + body;
        wrap.appendChild(detail);
    }).catch(function(e){
        return;
    });
}

function getAnatomyBaseColor(){
    var c = null;
    try { c = localStorage.getItem('datia-anatomy-color'); } catch(e) { c = null; }
    if (!c) c = '#c08a5c';
    return c;
}

function hexToRgb(hex){
    var h = hex.replace('#','');
    if (h.length===3) h = h.split('').map(function(x){return x+x}).join('');
    var r = parseInt(h.substring(0,2),16);
    var g = parseInt(h.substring(2,4),16);
    var b = parseInt(h.substring(4,6),16);
    return {r:r,g:g,b:b};
}

function rgbToHsl(r,g,b){
    r/=255; g/=255; b/=255;
    var max = Math.max(r,g,b), min = Math.min(r,g,b);
    var h,s,l = (max+min)/2;
    if (max===min){ h=0; s=0; }
    else {
        var d = max-min;
        s = l>0.5 ? d/(2-max-min) : d/(max+min);
        switch(max){
            case r: h = (g-b)/d + (g<b?6:0); break;
            case g: h = (b-r)/d + 2; break;
            default: h = (r-g)/d + 4;
        }
        h/=6;
    }
    return {h:h,s:s,l:l};
}

function hslToHex(h,s,l){
    function hue2rgb(p,q,t){
        if (t<0) t+=1;
        if (t>1) t-=1;
        if (t<1/6) return p + (q-p)*6*t;
        if (t<1/2) return q;
        if (t<2/3) return p + (q-p)*(2/3 - t)*6;
        return p;
    }
    var q = l < 0.5 ? l*(1+s) : l + s - l*s;
    var p = 2*l - q;
    var r = Math.round(hue2rgb(p,q,h+1/3)*255);
    var g = Math.round(hue2rgb(p,q,h)*255);
    var b = Math.round(hue2rgb(p,q,h-1/3)*255);
    var hh = '#'+[r,g,b].map(function(x){var s=x.toString(16);return s.length===1?'0'+s:s}).join('');
    return hh;
}

function shadeHex(hex, deltaL){
    var rgb = hexToRgb(hex);
    var hsl = rgbToHsl(rgb.r,rgb.g,rgb.b);
    var l = Math.max(0, Math.min(1, hsl.l + deltaL));
    return hslToHex(hsl.h, hsl.s, l);
}

function computeAnatomyPalette(baseHex){
    return {
        cv: shadeHex(baseHex, -0.15),
        ga: baseHex,
        imp: shadeHex(baseHex, -0.25),
        un: shadeHex(baseHex, -0.4)
    };
}

function changeAnatomyColor(val){
    try { localStorage.setItem('datia-anatomy-color', val); } catch(e) {}
    try { loadUtilityAnatomy(); } catch(e) {}
}

document.addEventListener('DOMContentLoaded', function(){
    var panel = document.getElementById('sub-anatomia');
    var colorInput = document.getElementById('fin-anatomy-color');
    if (colorInput) { try { colorInput.value = getAnatomyBaseColor(); } catch(e) {} }
    var yearsSel = document.getElementById('fin-anatomy-years');
    if (yearsSel) { try { yearsSel.value = String(getAnatomyForecastYears()); } catch(e) {} }
    var eqSel = document.getElementById('fin-anatomy-pl-eq');
    if (eqSel) { try { eqSel.checked = getAnatomyPLEq(); } catch(e) {} }
    if (panel && (panel.classList.contains('active') || panel.style.display !== 'none')) {
        setTimeout(function(){ try { loadUtilityAnatomy(); } catch(e){} }, 100);
    }
});

document.addEventListener('datia:tab-change', function(e){
    var isAct = e && e.detail && e.detail.tabId === 'tab-actualidad';
    var active = document.getElementById('sub-anatomia');
    if (isAct && active && active.classList.contains('active')) {
        setTimeout(function(){ try { loadUtilityAnatomy(); } catch(e){} }, 50);
    }
});

function loadPer100(year){
    var panel = document.getElementById('sub-anatomia');
    var pie = document.getElementById('fin-anatomy-per100-pie');
    if (!panel || !pie) return;
    var emp = (document.getElementById('sel-empresa')?.value) || currEmpresa;
    if (!emp) return;
    var eq = getAnatomyPLEq();
    var pal = (window.datiaAnatomyTotals && window.datiaAnatomyTotals.palette) ? window.datiaAnatomyTotals.palette : computeAnatomyPalette(getAnatomyBaseColor());
    pie.innerHTML = '';
    fetch('/api/financial/per100?empresa='+encodeURIComponent(emp)+'&ejercicio='+encodeURIComponent(year)+'&eq='+(eq?'true':'false')).then(function(r){return r.json()}).then(function(json){
        var parts = (json && json.cy && Array.isArray(json.cy.parts)) ? json.cy.parts.slice() : [];
        var colorMap = {
            'costo_ventas': pal.cv,
            'otros_gastos_exp': pal.ga,
            'gastos_admin': pal.ga,
            'impuestos': pal.imp,
            'personal': shadeHex(pal.ga, -0.1),
            'amort': shadeHex(pal.ga, -0.2),
            'financiero': shadeHex(pal.ga, -0.3),
            'utilidad_neta': pal.un
        };
        var labelMap = {
            'costo_ventas':'Coste de Ventas',
            'otros_gastos_exp':'Otros Gastos de Explotación',
            'gastos_admin':'Gastos Administrativos',
            'impuestos':'Impuestos',
            'personal':'Gastos de Personal',
            'amort':'Amortizaciones y Deterioros',
            'financiero':'Resultado Financiero',
            'utilidad_neta':'Utilidad Neta'
        };
        var nfMoney = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        var nfPct = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 1 });
        var canvas = pie.querySelector('.fin-per100-pie-canvas');
        if (!canvas) {
            canvas = document.createElement('div');
            canvas.className = 'fin-per100-pie-canvas';
            canvas.style.width = '100%';
            canvas.style.height = '420px';
            pie.appendChild(canvas);
        }
        if (typeof echarts !== 'undefined') {
            var inst = echarts.getInstanceByDom(canvas);
            if (!inst) inst = echarts.init(canvas, null, { renderer: 'svg' });
            else inst.clear();
            var dataPie = parts.map(function(p){
                var baseHex = colorMap[p.key] || '#888';
                var grad = new echarts.graphic.RadialGradient(0.5, 0.5, 1, [
                    { offset: 0, color: shadeHex(baseHex, 0.22) },
                    { offset: 0.7, color: baseHex },
                    { offset: 1, color: shadeHex(baseHex, -0.18) }
                ]);
                return {
                    key: p.key,
                    name: labelMap[p.key] || (p.key||'').replace('_',' '),
                    value: Math.max(0, Number(p.pct||0)),
                    amount: Number(p.amount||0),
                    itemStyle: { color: grad, shadowBlur: 12, shadowColor: 'rgba(0,0,0,0.25)', shadowOffsetX: 0, shadowOffsetY: 3 }
                };
            });
            try { 
                canvas.setAttribute('role','img'); 
                canvas.setAttribute('aria-label','Distribución del coste por cada 100 euros de ingresos');
            } catch(e) {}
            var applyPer100Option = function(){
                var w = canvas.clientWidth || pie.clientWidth || 0;
                var isNarrow = w < 720;
                var labelFormatter = isNarrow ? function(p){ return nfPct.format(p.value||0)+'%'; } : function(p){ return p.name+' '+nfPct.format(p.value||0)+'%'; };
                var centerY = isNarrow ? '58%' : '56%';
                var thr = isNarrow ? 6 : 4;
                if ((canvas.clientWidth || pie.clientWidth || 0) < 420) { thr = 100; }
                var seriesData = dataPie.map(function(d){
                    var forceShow = (d && (d.key === 'costo_ventas' || d.key === 'utilidad_neta'));
                    var show = forceShow || ((Number(d.value||0)) >= thr);
                    return Object.assign({}, d, {
                        label: { show: show },
                        labelLine: { show: show }
                    });
                });
                try {
                    var visCount = seriesData.filter(function(d){ return d && d.label && d.label.show; }).length;
                    var newH = isNarrow ? 460 : 440;
                    if (visCount > 5) newH = isNarrow ? 520 : 480;
                    canvas.style.height = newH + 'px';
                } catch(e) {}
                var option = {
                    aria: { enabled: true },
                    tooltip: {
                        trigger: 'item',
                        formatter: function (params) {
                            var valPct = nfPct.format(params.value||0);
                            var amt = nfMoney.format((params.data&&params.data.amount)||0);
                            return params.name+': '+valPct+'% • '+amt+' €';
                        }
                    },
                    legend: { 
                        type: 'scroll',
                        orient: 'horizontal', 
                        left: 'center', 
                        top: isNarrow ? null : 6,
                        bottom: isNarrow ? 6 : null,
                        textStyle: { color: '#a1a1aa' } 
                    },
                    series: [{
                        type: 'pie',
                        center: ['50%', centerY],
                        radius: isNarrow ? ['58%','82%'] : ['65%','88%'],
                        top: '6%',
                        bottom: '8%',
                        avoidLabelOverlap: true,
                        minShowLabelAngle: 5,
                        startAngle: 90,
                        label: { 
                            show: true, 
                            position: 'outside', 
                            formatter: labelFormatter, 
                            color: '#e4e4e7', 
                            fontWeight: 600,
                            fontSize: isNarrow ? 11 : 12,
                            alignTo: 'edge',
                            edgeDistance: isNarrow ? '6%' : '8%',
                            bleedMargin: 6,
                            borderColor: 'rgba(0,0,0,0.4)',
                            borderWidth: 2
                        },
                        labelLine: { 
                            show: true, 
                            length: isNarrow ? 10 : 16, 
                            length2: isNarrow ? 6 : 10, 
                        lineStyle: { color: '#71717a' } 
                        },
                        labelLayout: function(){ return { hideOverlap: true, moveOverlap: 'shiftY' }; },
                        emphasis: { scale: true, scaleSize: 6, itemStyle: { shadowBlur: 18, shadowColor: 'rgba(0,0,0,0.35)' } },
                        data: seriesData
                    }],
                    animationDuration: 600,
                    animationEasing: 'cubicOut'
                };
                inst.setOption(option, true);
                try { inst.resize(); } catch(e){}
                try { canvas.dataset.isNarrow = isNarrow ? '1' : '0'; } catch(e){}
            };
            applyPer100Option();
            try { prefetchPL4(((document.getElementById('sel-empresa') && document.getElementById('sel-empresa').value) ? document.getElementById('sel-empresa').value : currEmpresa), year); } catch(e){}
            inst.off('click');
            inst.on('click', function(evt){
                try {
                    var d = evt && evt.data ? evt.data : null;
                    var key = d && d.key ? d.key : null;
                    if (!key) return;
                    if (key === 'utilidad_neta') {
                        openPer100Modal('Utilidad Neta', '<div class=\"fin-modal-loading\">El resultado no tiene desglose directo de cuentas</div>');
                        return;
                    }
                    var empSel = (document.getElementById('sel-empresa')?.value) || currEmpresa;
                    var prefixes = [];
                    var eq = getAnatomyPLEq();
                    if (key === 'costo_ventas') prefixes = ['60'];
                    else if (key === 'otros_gastos_exp') prefixes = ['62','63','64','65','66','67','68','69'];
                    else if (key === 'gastos_admin') prefixes = ['62','65','69'];
                    else if (key === 'impuestos') prefixes = ['63'];
                    else if (key === 'personal') prefixes = ['64'];
                    else if (key === 'amort') prefixes = ['68'];
                    else if (key === 'financiero') prefixes = ['66','67'];
                    openPer100Modal(labelMap[key] || key, '<div class=\"fin-modal-loading\">Cargando...</div>');
                    var cached = getPL4FromCache(empSel, year);
                    var useData = function(pl){
                        try {
                            var rows = pl && pl.rows ? pl.rows : [];
                            var nf = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                            var filt = rows.filter(function(x){
                                var c = x && x.cuenta ? String(x.cuenta) : '';
                                return !x.is_header && prefixes.some(function(p){ return c.indexOf(p) === 0; });
                            });
                            filt.sort(function(a,b){ return String(a.cuenta).localeCompare(String(b.cuenta)); });
                            var html = '<table class=\"fin-modal-table\" aria-label=\"Desglose nivel 4\"><thead><tr><th>Cuenta</th><th>Descripción</th><th>Importe</th></tr></thead><tbody>';
                            html += filt.map(function(x){
                                var imp = nf.format(parseFloat(x.valor||0))+' €';
                                var code = String(x.cuenta||'');
                                return '<tr data-code=\"'+code+'\"><td>'+code+'</td><td>'+String(x.descripcion||'')+'</td><td>'+imp+'</td></tr>';
                            }).join('');
                            html += '</tbody></table>';
                            openPer100Modal(labelMap[key] || key, html, function(modalBody){
                                try {
                                    var overlay = modalBody.closest('.fin-modal-overlay');
                                    function attachEvents(targetBody){
                                        var rows = targetBody.querySelectorAll('table.fin-modal-table tbody tr[data-code]');
                                        rows.forEach(function(tr){
                                            tr.style.cursor = 'pointer';
                                            tr.addEventListener('click', function(){
                                                var code = tr.getAttribute('data-code');
                                                if (!code) return;
                                                try { overlay.dataset.prevHtml = targetBody.innerHTML; } catch(e){}
                                                targetBody.innerHTML = '<div class=\"fin-modal-loading\">Cargando detalle de '+code+'...</div>';
                                                loadAccountBreakdown(empSel, year, code, labelMap[key] || key, targetBody);
                                                try {
                                                    var backBtn = overlay.querySelector('.fin-modal-back');
                                                    if (backBtn) { backBtn.style.display = 'inline-block'; backBtn.disabled = false; }
                                                } catch(e){}
                                            });
                                        });
                                    }
                                    attachEvents(modalBody);
                                    try { overlay._restore = function(b){ attachEvents(b); }; } catch(e) {}
                                } catch(e) {}
                            });
                        } catch(e) {
                            openPer100Modal(labelMap[key] || key, '<div class=\"fin-modal-loading\">Error al cargar</div>');
                        }
                    };
                    if (cached) {
                        useData(cached);
                    } else {
                        var url = '/api/financial/pl?empresa='+encodeURIComponent(empSel)+'&ejercicio='+encodeURIComponent(year)+'&level=4';
                        fetch(url).then(function(r){return r.json()}).then(function(pl){
                            try { setPL4Cache(empSel, year, pl); } catch(_){}
                            useData(pl);
                        }).catch(function(){
                            openPer100Modal(labelMap[key] || key, '<div class=\"fin-modal-loading\">Error de red</div>');
                        });
                    }
                } catch(e) {}
            });
            if (!canvas._datiaResizeBound) {
                canvas._datiaResizeBound = true;
                window.addEventListener('resize', function(){ 
                    try { 
                        inst.resize(); 
                        var prev = canvas.dataset && canvas.dataset.isNarrow ? canvas.dataset.isNarrow : '';
                        var nowNarrow = ((canvas.clientWidth || pie.clientWidth || 0) < 720) ? '1' : '0';
                        if (prev !== nowNarrow) { applyPer100Option(); }
                    } catch(e){} 
                });
            }
        } else {
            var list = document.createElement('div');
            list.style.display = 'grid';
            list.style.gridTemplateColumns = 'repeat(2, 1fr)';
            list.style.gap = '10px';
            parts.forEach(function(p){
                var item = document.createElement('div');
                item.style.display = 'flex';
                item.style.alignItems = 'center';
                item.style.gap = '8px';
                var dot = document.createElement('span');
                dot.style.width = '14px';
                dot.style.height = '14px';
                dot.style.borderRadius = '2px';
                dot.style.background = colorMap[p.key] || '#888';
                var lbl = document.createElement('span');
                lbl.style.fontSize = '0.9rem';
                lbl.innerText = (labelMap[p.key] || (p.key||'').replace('_',' ')) + ' ' + nfPct.format(p.pct||0) + '%';
                item.appendChild(dot); item.appendChild(lbl);
                list.appendChild(item);
            });
            pie.appendChild(list);
        }
    }).catch(function(){
        pie.innerHTML = '<div class=\"fin-empty\">No disponible</div>';
    });
}

function setPL4Cache(emp, year, pl){
    try {
        if (!window.datiaPL4Cache) window.datiaPL4Cache = {};
        if (!window.datiaPL4Cache[emp]) window.datiaPL4Cache[emp] = {};
        window.datiaPL4Cache[emp][String(year)] = pl;
    } catch(e) {}
}

function getPL4FromCache(emp, year){
    try {
        var m = window.datiaPL4Cache || {};
        var e = m[emp] || {};
        return e[String(year)] || null;
    } catch(e) {
        return null;
    }
}

function prefetchPL4(emp, year){
    try {
        var cached = getPL4FromCache(emp, year);
        if (cached) return Promise.resolve(cached);
        var url = '/api/financial/pl?empresa='+encodeURIComponent(emp)+'&ejercicio='+encodeURIComponent(year)+'&level=4';
        return fetch(url).then(function(r){return r.json()}).then(function(pl){
            try { setPL4Cache(emp, year, pl); } catch(_){}
            return pl;
        }).catch(function(){ return null; });
    } catch(e) {
        return Promise.resolve(null);
    }
}
function openPer100Modal(title, bodyHtml, onReady){
    try {
        var old = document.querySelector('.fin-modal-overlay');
        if (old) old.parentNode.removeChild(old);
    } catch(e) {}
    var overlay = document.createElement('div');
    overlay.className = 'fin-modal-overlay';
    overlay.setAttribute('role','dialog');
    overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label', 'Desglose de cuentas nivel 4');
    var modal = document.createElement('div');
    modal.className = 'fin-modal';
    var header = document.createElement('div');
    header.className = 'fin-modal-header';
    var left = document.createElement('div');
    left.className = 'fin-modal-left';
    var btnBack = document.createElement('button');
    btnBack.className = 'fin-modal-back';
    btnBack.setAttribute('aria-label','Volver');
    btnBack.innerText = 'Volver';
    btnBack.style.display = 'inline-block';
    btnBack.disabled = true;
    btnBack.addEventListener('click', function(){
        try {
            var prev = overlay && overlay.dataset ? overlay.dataset.prevHtml : '';
            if (prev) {
                body.innerHTML = prev;
                btnBack.style.display = 'none';
                btnBack.disabled = true;
                if (typeof overlay._restore === 'function') {
                    try { overlay._restore(body); } catch(e){}
                }
                overlay.dataset.prevHtml = '';
            }
        } catch(e) {}
    });
    var titleEl = document.createElement('div');
    titleEl.className = 'fin-modal-title';
    titleEl.textContent = title || 'Desglose';
    left.appendChild(btnBack);
    left.appendChild(titleEl);
    header.appendChild(left);
    var btn = document.createElement('button');
    btn.className = 'fin-modal-close';
    btn.setAttribute('aria-label','Cerrar');
    btn.innerText = 'Cerrar';
    btn.addEventListener('click', function(){ try { document.body.removeChild(overlay); } catch(e){} });
    header.appendChild(btn);
    var body = document.createElement('div');
    body.className = 'fin-modal-body';
    body.innerHTML = bodyHtml || '';
    modal.appendChild(header);
    modal.appendChild(body);
    overlay.appendChild(modal);
    overlay.addEventListener('click', function(e){ if (e.target === overlay) { try { document.body.removeChild(overlay); } catch(_){ } } });
    document.body.appendChild(overlay);
    try { btn.focus(); } catch(e) {}
    window.addEventListener('keydown', function esc(e){ if (e.key==='Escape'){ try { document.body.removeChild(overlay); } catch(_){ } window.removeEventListener('keydown', esc); } });
    try { if (typeof onReady === 'function') onReady(body); } catch(e) {}
}

function loadAccountBreakdown(emp, year, code, title, container){
    try {
        var key = emp+'_'+year+'_'+code;
        if (!window.datiaBreakdownCache) window.datiaBreakdownCache = {};
        var cached = window.datiaBreakdownCache[key];
        var render = function(dto){
            try {
                var nf = new Intl.NumberFormat('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                var rows = (dto && dto.rows) ? dto.rows : [];
                if (!rows.length) {
                    container.innerHTML = '<div class=\"fin-modal-loading\">Sin detalle adicional para '+code+'</div>';
                    return;
                }
                var html = '<table class=\"fin-modal-table\" aria-label=\"Detalle por cuenta\"><thead><tr><th>Cuenta</th><th>Descripción</th><th>Importe</th></tr></thead><tbody>';
                html += rows.map(function(r){
                    var imp = nf.format(parseFloat(r.valor||0))+' €';
                    return '<tr><td>'+String(r.cuenta||'')+'</td><td>'+String(r.descripcion||'')+'</td><td>'+imp+'</td></tr>';
                }).join('');
                html += '</tbody></table>';
                container.innerHTML = html;
            } catch(e) {
                container.innerHTML = '<div class=\"fin-modal-loading\">Error al mostrar detalle</div>';
            }
        };
        if (cached) {
            render(cached);
            try {
                var ov0 = container.closest('.fin-modal-overlay');
                var back0 = ov0 ? ov0.querySelector('.fin-modal-back') : null;
                if (back0) { back0.style.display = 'inline-block'; back0.disabled = false; }
            } catch(e){}
            return;
        }
        var url = '/api/financial/accounts/breakdown?empresa='+encodeURIComponent(emp)+'&ejercicio='+encodeURIComponent(year)+'&code='+encodeURIComponent(code);
        fetch(url).then(function(r){
            if (!r.ok) throw new Error('status '+r.status);
            return r.json()
        }).then(function(dto){
            try { window.datiaBreakdownCache[key] = dto; } catch(_){}
            render(dto);
            try {
                var ov = container.closest('.fin-modal-overlay');
                var backBtn = ov ? ov.querySelector('.fin-modal-back') : null;
                if (backBtn) { backBtn.style.display = 'inline-block'; backBtn.disabled = false; }
            } catch(e){}
        }).catch(function(){
            var url2 = '/api/financial/pl?empresa='+encodeURIComponent(emp)+'&ejercicio='+encodeURIComponent(year)+'&level=6';
            fetch(url2).then(function(r){
                if (!r.ok) throw new Error('status '+r.status);
                return r.json()
            }).then(function(pl){
                try {
                    var rows = (pl && pl.rows) ? pl.rows : [];
                    var filt = rows.filter(function(x){
                        var c = x && x.cuenta ? String(x.cuenta) : '';
                        return c.indexOf(code) === 0 && !x.is_header;
                    }).map(function(x){
                        return { cuenta: String(x.cuenta||''), descripcion: String(x.descripcion||''), valor: Math.abs(parseFloat(x.valor||0)) };
                    });
                    var dto = { rows: filt };
                    try { window.datiaBreakdownCache[key] = dto; } catch(_){}
                    render(dto);
                    try {
                        var ov2 = container.closest('.fin-modal-overlay');
                        var back2 = ov2 ? ov2.querySelector('.fin-modal-back') : null;
                        if (back2) { back2.style.display = 'inline-block'; back2.disabled = false; }
                    } catch(e){}
                } catch(e) {
                    container.innerHTML = '<div class=\"fin-modal-loading\">Error de red</div>';
                }
            }).catch(function(){
                container.innerHTML = '<div class=\"fin-modal-loading\">Error de red</div>';
            });
        });
    } catch(e) {
        container.innerHTML = '<div class=\"fin-modal-loading\">Error</div>';
    }
}

(function(){
    var panel = document.getElementById('sub-anatomia');
    if (panel && (panel.classList.contains('active') || panel.style.display !== 'none')) {
        setTimeout(function(){ try { loadUtilityAnatomy(); } catch(e){} }, 50);
    }
})();

window.addEventListener('load', function(){
    var panel = document.getElementById('sub-anatomia');
    if (panel && (panel.classList.contains('active') || panel.style.display !== 'none')) {
        setTimeout(function(){ try { loadUtilityAnatomy(); } catch(e){} }, 50);
    }
});

function toggleAnatomyFormulas(open){
    var el = document.getElementById('fin-anatomy-formulas');
    if (!el) return;
    if (typeof open === 'boolean') {
        el.style.display = open ? 'block' : 'none';
        return;
    }
    var d = window.getComputedStyle(el).display;
    el.style.display = d === 'none' ? 'block' : 'none';
}
