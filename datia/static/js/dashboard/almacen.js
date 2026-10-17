function loadAlmacenDashboard() {
    const valSel = document.getElementById('alm-valoracion');
    const favBtn = document.getElementById('alm-valoracion-fav');
    const favInfo = document.getElementById('alm-valoracion-fav-info');
    const perSel = document.getElementById('alm-periodo');
    if (perSel) {
        const labelTodos = (typeof gettext === 'function') ? gettext('Todos') : 'Todos';
        let opts = `<option value="0">${labelTodos}</option>`;
        for (let n = 1; n <= 12; n++) {
            opts += `<option value="${n}">${monthShort(n)}</option>`;
        }
        perSel.innerHTML = opts;
    }
    const almSel = document.getElementById('alm-almacen');
    const ubiSel = document.getElementById('alm-ubicacion');
    const tipSel = document.getElementById('alm-tipologia');
    const btnApply = document.getElementById('alm-btn-aplicar');
    const btnExport = document.getElementById('alm-btn-export');
    if (!valSel || !perSel || !almSel || !ubiSel || !tipSel || !btnApply || !btnExport) return;
    renderAlmVariacionSummary();
    fetch(`/api/inventory/filters?empresa=${currEmpresa}&ejercicio=${currEjercicio}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const named = Array.isArray(j.almacenes_named) ? j.almacenes_named : [];
        if (named.length > 0) {
            almSel.innerHTML = '<option value="">Todos</option>' + named.map(a => `<option value="${a.code}">${a.name || a.code}</option>`).join('');
        } else {
            almSel.innerHTML = '<option value="">Todos</option>' + (j.almacenes || []).map(a => `<option value="${a}">${a}</option>`).join('');
        }
        ubiSel.innerHTML = '<option value="">Todas</option>' + (j.ubicaciones || []).map(a => `<option value="${a}">${a}</option>`).join('');
        tipSel.innerHTML = '<option value="">Todas</option>' + (j.tipologias || []).map(a => `<option value="${a}">${a}</option>`).join('');
        const fav = localStorage.getItem('datia_inventory_valoracion_fav') || localStorage.getItem('datia_inventory_valoracion_last') || 'compra';
        if (Array.from(valSel.options).some(o => o.value === fav)) valSel.value = fav;
        updateValoracionFavoriteUI(valSel, favBtn, favInfo);
    }).finally(() => {
        refreshAlmacen();
    });
    if (valSel) valSel.onchange = () => {
        localStorage.setItem('datia_inventory_valoracion_last', valSel.value);
        updateValoracionFavoriteUI(valSel, favBtn, favInfo);
    };
    if (favBtn) favBtn.onclick = () => toggleValoracionFavorite(valSel, favBtn, favInfo);
    btnApply.onclick = () => refreshAlmacen();
    btnExport.onclick = () => exportAlmacenCSV();
}

function updateValoracionFavoriteUI(valSel, favBtn, favInfo) {
    const fav = localStorage.getItem('datia_inventory_valoracion_fav') || '';
    const isFav = fav && (valSel && valSel.value === fav);
    if (favBtn) {
        favBtn.classList.toggle('active', isFav);
        const txtSave = (typeof gettext === 'function') ? gettext('Guardar favorito') : 'Guardar favorito';
        const txtRemove = (typeof gettext === 'function') ? gettext('Quitar favorito') : 'Quitar favorito';
        favBtn.textContent = (isFav ? `★ ${txtRemove}` : `★ ${txtSave}`);
        favBtn.setAttribute('title', isFav ? txtRemove : txtSave);
        favBtn.setAttribute('aria-label', isFav ? txtRemove : txtSave);
    }
    if (favInfo) {
        const label = (typeof gettext === 'function') ? gettext('Favorito actual') : 'Favorito actual';
        const valText = fav ? Array.from(valSel.options).find(o => o.value === fav)?.text || fav : (typeof gettext === 'function' ? gettext('Ninguno') : 'Ninguno');
        favInfo.innerText = `${label}: ${valText}`;
    }
    if (valSel) valSel.classList.toggle('is-fav', isFav);
}

function toggleValoracionFavorite(valSel, favBtn, favInfo) {
    const fav = localStorage.getItem('datia_inventory_valoracion_fav') || '';
    const current = valSel ? (valSel.value || 'compra') : 'compra';
    const hadFav = !!fav;
    // Toggle behavior: if same -> remove; else set current
    if (hadFav && fav === current) {
        localStorage.removeItem('datia_inventory_valoracion_fav');
        const msg = (typeof gettext === 'function') ? gettext('Favorito eliminado') : 'Favorito eliminado';
        if (typeof showToast === 'function') showToast(msg);
    } else {
        localStorage.setItem('datia_inventory_valoracion_fav', current);
        const msg = (typeof gettext === 'function') ? gettext('Favorito guardado') : 'Favorito guardado';
        if (typeof showToast === 'function') showToast(msg);
    }
    updateValoracionFavoriteUI(valSel, favBtn, favInfo);
}

function getAlmFilters() {
    const valoracion = document.getElementById('alm-valoracion').value || 'compra';
    const periodo = parseInt(document.getElementById('alm-periodo').value || '0');
    const almacen = document.getElementById('alm-almacen').value || '';
    const ubicacion = document.getElementById('alm-ubicacion').value || '';
    const tipologia = document.getElementById('alm-tipologia').value || '';
    return { valoracion, periodo, almacen, ubicacion, tipologia };
}

function renderAlmVariacionSummary() {
    const f = getAlmFilters();
    const common = `&almacen=${encodeURIComponent(f.almacen)}&ubicacion=${encodeURIComponent(f.ubicacion)}&tipologia=${encodeURIComponent(f.tipologia)}`;
    fetch(`/api/inventory/variation?empresa=${currEmpresa}&ejercicio=${currEjercicio}${common}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const dom = document.getElementById('chart-alm-variacion');
        if (dom && window.echarts) {
            const inst = echarts.init(dom);
            const xs = (j.serie || []).map(s => monthShort(s.periodo));
            const ys = (j.serie || []).map(s => s.variacion !== undefined ? s.variacion : 0);
            inst.setOption({
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: xs },
                yAxis: { type: 'value', axisLabel: { show: true } },
                series: [{ type: 'line', data: ys, smooth: true }]
            });
            if (typeof attachResizeObserver === 'function') attachResizeObserver(inst, dom);
        }
        const baseVal = document.getElementById('alm-sum-base-valor');
        if (baseVal) baseVal.innerText = fmtMoney.format(j.valor_inicial || 0);
        const variacion = document.getElementById('alm-sum-variacion');
        if (variacion) variacion.innerText = fmtMoney.format(j.variacion_total || 0);
        const endValor = document.getElementById('alm-sum-end');
        if (endValor) endValor.innerText = fmtMoney.format(j.existencia_fin || 0);
        const endValorSub = document.getElementById('alm-sum-end-valor');
        if (endValorSub) endValorSub.innerText = '';
    });
}

function refreshAlmacen() {
    const f = getAlmFilters();
    renderAlmVariacionSummary();
    const common = `&almacen=${encodeURIComponent(f.almacen)}&ubicacion=${encodeURIComponent(f.ubicacion)}&tipologia=${encodeURIComponent(f.tipologia)}`;
    fetch(`/api/inventory/snapshot?empresa=${currEmpresa}&ejercicio=${currEjercicio}&valoracion=${encodeURIComponent(f.valoracion)}&periodo=${f.periodo}${common}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const v = document.getElementById('alm-total-valor');
        const u = document.getElementById('alm-total-unidades');
        const e = document.getElementById('alm-expiring');
        const c = document.getElementById('alm-critical');
        if (v) v.innerText = fmtMoney.format(j.total_valor || 0);
        if (u) u.innerText = fmtInt.format(j.total_unidades || 0);
        if (e) {
            e.innerText = fmtInt.format(j.expiring || 0);
            e.classList.toggle('danger', (j.expiring || 0) > 0);
        }
        if (c) {
            c.innerText = fmtInt.format(j.critical || 0);
            c.classList.toggle('danger', (j.critical || 0) > 0);
        }
    });
    // Eliminados: distribución por tipología y evolución mensual
    fetch(`/api/inventory/by_warehouse?empresa=${currEmpresa}&ejercicio=${currEjercicio}&periodo=${f.periodo}&metric=valor&valoracion=${encodeURIComponent(f.valoracion)}${common}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const dom = document.getElementById('chart-alm-almacen');
        if (!dom || !window.echarts) return;
        const inst = echarts.init(dom);
        const items = (j.items || []).filter(i => (i.valor !== undefined ? i.valor : 0) > 0);
        const cats = items.map(i => (i.almacen_name || i.almacen));
        const vals = items.map(i => (i.valor !== undefined ? i.valor : 0));
        inst.setOption({
            tooltip: { trigger: 'axis' },
            grid: { left: 160, right: 20, top: 20, bottom: 20, containLabel: true },
            xAxis: { type: 'value' },
            yAxis: { type: 'category', data: cats, axisLabel: { interval: 0 } },
            series: [{ type: 'bar', data: vals, barCategoryGap: '30%' }]
        });
        if (typeof attachResizeObserver === 'function') attachResizeObserver(inst, dom);
    });
    renderAlmMaster();
    renderAlmExpiring();
}

function renderAlmMaster() {
    const f = getAlmFilters();
    const q = `empresa=${currEmpresa}&ejercicio=${currEjercicio}&periodo=${f.periodo}&almacen=${encodeURIComponent(f.almacen)}&ubicacion=${encodeURIComponent(f.ubicacion)}&tipologia=${encodeURIComponent(f.tipologia)}&limit=200&offset=0`;
    fetch(`/api/inventory/master?${q}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const body = document.getElementById('alm-master-body');
        if (!body) return;
        const rows = (j.items || []).map(it => {
            return `<tr>
                <td>${it.articulo || ''}</td>
                <td>${it.descripcion || ''}</td>
                <td>${it.tipologia || ''}</td>
                <td>${it.almacen || ''}</td>
                <td>${it.ubicacion || ''}</td>
                <td style="text-align:right">${fmtInt.format(it.unidades || 0)}</td>
            </tr>`;
        }).join('');
        body.innerHTML = rows;
        renderAlmABC(j.items || []);
    });
}

function renderAlmABC(items) {
    const dom = document.getElementById('chart-alm-abc');
    if (!dom || !window.echarts) return;
    const data = (items || []).slice().sort((a, b) => (b.unidades || 0) - (a.unidades || 0));
    const xs = data.map((_, i) => i + 1);
    const bars = data.map(d => d.unidades || 0);
    let total = bars.reduce((acc, v) => acc + v, 0);
    let cum = 0;
    const line = bars.map(v => {
        cum += v;
        return total > 0 ? Math.round((cum / total) * 100) : 0;
    });
    const inst = echarts.init(dom);
    inst.setOption({
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: xs },
        yAxis: [{ type: 'value' }, { type: 'value', min: 0, max: 100 }],
        series: [
            { type: 'bar', data: bars, name: 'Unidades' },
            { type: 'line', data: line, yAxisIndex: 1, name: 'Cumulado %' }
        ]
    });
    if (typeof attachResizeObserver === 'function') attachResizeObserver(inst, dom);
}

function exportAlmacenCSV() {
    const body = document.getElementById('alm-master-body');
    if (!body) return;
    const rows = Array.from(body.querySelectorAll('tr')).map(tr => Array.from(tr.querySelectorAll('td')).map(td => `"${(td.innerText || '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const header = ['Artículo','Descripción','Tipología','Almacén','Ubicación','Unidades'].map(h => `"${h}"`).join(',');
    const csv = header + '\n' + rows;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `existencias_${currEmpresa}_${currEjercicio}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function renderAlmExpiring() {
    const f = getAlmFilters();
    const q = `empresa=${currEmpresa}&ejercicio=${currEjercicio}&periodo=${f.periodo}&almacen=${encodeURIComponent(f.almacen)}&ubicacion=${encodeURIComponent(f.ubicacion)}&tipologia=${encodeURIComponent(f.tipologia)}&days_to_expire=30&limit=200&offset=0`;
    fetch(`/api/inventory/expiring?${q}`).then(r => r.json()).then(j => {
        if (j.status !== 'ok') return;
        const body = document.getElementById('alm-expiring-body');
        if (!body) return;
        const rows = (j.items || []).sort((a,b) => {
            const da = a.caducidad ? new Date(a.caducidad) : null;
            const db = b.caducidad ? new Date(b.caducidad) : null;
            return (da && db) ? (da - db) : 0;
        }).map(it => {
            const fCad = it.caducidad ? new Date(it.caducidad).toLocaleDateString((typeof APP_LANG !== 'undefined' && APP_LANG) ? APP_LANG : (document.documentElement.lang || 'es')) : '';
            return `<tr>
                <td>${it.articulo || ''}</td>
                <td>${it.descripcion || ''}</td>
                <td>${fCad}</td>
                <td style="text-align:right">${fmtInt.format(it.unidades || 0)}</td>
            </tr>`;
        }).join('');
        body.innerHTML = rows;
    });
}
