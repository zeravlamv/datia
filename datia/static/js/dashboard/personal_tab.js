(function () {
    const PersonalTab = {
        state: {
            name: 'Pestaña Personal',
            widgets: [],
            grouped: true
        },
        catalog: [
            { key: 'sales_1d', title: 'Ventas (1 Día)', type: 'sales', period: '1d', domId: 'val-sales-1d' },
            { key: 'sales_7d', title: 'Ventas (7 Días)', type: 'sales', period: '7d', domId: 'val-sales-7d' },
            { key: 'sales_30d', title: 'Ventas (30 Días)', type: 'sales', period: '30d', domId: 'val-sales-30d' },
            { key: 'ticket_1d', title: 'Ticket (1 Día)', type: 'ticket', period: '1d', domId: 'val-ticket-1d' },
            { key: 'ticket_7d', title: 'Ticket (7 Días)', type: 'ticket', period: '7d', domId: 'val-ticket-7d' },
            { key: 'ticket_30d', title: 'Ticket (30 Días)', type: 'ticket', period: '30d', domId: 'val-ticket-30d' },
            { key: 'margin_1d', title: 'Margen (1 Día)', type: 'margin', period: '1d', domId: 'val-margin-1d' },
            { key: 'margin_7d', title: 'Margen (7 Días)', type: 'margin', period: '7d', domId: 'val-margin-7d' },
            { key: 'margin_30d', title: 'Margen (30 Días)', type: 'margin', period: '30d', domId: 'val-margin-30d' },
            { key: 'kpi_neto', title: 'Total Ventas (Anual)', type: 'neto', period: 'year', domId: 'kpi-neto' },
            { key: 'kpi_coste', title: 'Total Costes (Anual)', type: 'coste', period: 'year', domId: 'kpi-coste' },
            { key: 'kpi_margen', title: 'Margen Global (Anual)', type: 'margin', period: 'year', domId: 'kpi-margen' },
            { key: 'kpi_ticket', title: 'Ticket Medio (Anual)', type: 'ticket', period: 'year', domId: 'kpi-ticket' },
            { key: 'compras_1d', title: 'Compras (1 Día)', type: 'compras', period: '1d', domId: 'val-compras-1d' },
            { key: 'compras_7d', title: 'Compras (7 Días)', type: 'compras', period: '7d', domId: 'val-compras-7d' },
            { key: 'compras_30d', title: 'Compras (30 Días)', type: 'compras', period: '30d', domId: 'val-compras-30d' },
            { key: 'ticket_compra_1d', title: 'Ticket Compra (1 Día)', type: 'ticket_compra', period: '1d', domId: 'val-ticket-compra-1d' },
            { key: 'ticket_compra_7d', title: 'Ticket Compra (7 Días)', type: 'ticket_compra', period: '7d', domId: 'val-ticket-compra-7d' },
            { key: 'ticket_compra_30d', title: 'Ticket Compra (30 Días)', type: 'ticket_compra', period: '30d', domId: 'val-ticket-compra-30d' },
            { key: 'ops_compra_1d', title: 'Operaciones Compra (1 Día)', type: 'ops_compra', period: '1d', domId: 'val-ops-compra-1d' },
            { key: 'ops_compra_7d', title: 'Operaciones Compra (7 Días)', type: 'ops_compra', period: '7d', domId: 'val-ops-compra-7d' },
            { key: 'ops_compra_30d', title: 'Operaciones Compra (30 Días)', type: 'ops_compra', period: '30d', domId: 'val-ops-compra-30d' },
            { key: 'compras_year', title: 'Compras (Total Año)', type: 'compras_year', period: 'year', domId: 'val-compras-year' },
            { key: 'ticket_compra_year', title: 'Ticket Compra (Anual)', type: 'ticket_compra_year', period: 'year', domId: 'val-ticket-compra-year' },
            { key: 'chart_activity_compras', title: 'Evolución Compras Mensual', type: 'chart', period: 'month', domId: 'chart-activity-compras' },
            { key: 'top_zonas_compra', title: 'Top Zonas Compra', type: 'chart', period: 'month', domId: 'chart-top-zonas-compra' },
            { key: 'top_proveedores', title: 'Top Proveedores', type: 'chart', period: 'month', domId: 'chart-top-proveedores' },
            { key: 'top_articulos_compra', title: 'Top Artículos Compra', type: 'chart', period: 'month', domId: 'chart-top-articulos-compra' },
            { key: 'kpi_proveedores', title: 'Proveedores activos (Año)', type: 'kpi_proveedores', period: 'year', domId: 'val-kpi-proveedores' },
            { key: 'alm_base', title: 'Existencias: Valor inicial', type: 'alm_base', period: 'year', domId: 'alm-sum-base-valor' },
            { key: 'alm_variacion', title: 'Existencias: Variación', type: 'alm_variacion', period: 'year', domId: 'alm-sum-variacion' },
            { key: 'alm_end', title: 'Existencias: Fin de año', type: 'alm_end', period: 'year', domId: 'alm-sum-end' },
            { key: 'fin_ingresos', title: 'Ingresos Totales (Fin)', type: 'fin_ingresos', period: 'year', domId: 'fin-val-ingresos' },
            { key: 'fin_gastos', title: 'Gastos Totales (Fin)', type: 'fin_gastos', period: 'year', domId: 'fin-val-gastos' },
            { key: 'fin_resultado', title: 'EBITDA (Fin)', type: 'fin_resultado', period: 'year', domId: 'fin-val-resultado' }
        ],
        dedupe() {
            const seen = new Set();
            this.state.widgets = this.state.widgets.filter(w => {
                if (!w || !w.key) return false;
                if (seen.has(w.key)) return false;
                seen.add(w.key);
                return true;
            });
        },
        setStarState(key, active) {
            try {
                const btn = document.querySelector('.act-fav-btn[data-key="' + key + '"]');
                if (!btn) return;
                if (active) {
                    btn.classList.remove('inactive');
                    btn.title = 'Añadido a Pestaña Personal';
                } else {
                    btn.classList.add('inactive');
                    btn.title = 'Añadir a Pestaña Personal';
                }
            } catch (_) {}
        },
        _toast(msg, isError) {
            try { if (typeof showToast === 'function') showToast(msg, !!isError); } catch (_) {}
        },
        async init() {
            if (typeof window.FavoriteStore !== 'undefined') {
                try { await window.FavoriteStore.init(); } catch (_) {}
                this.state.name = typeof window.FavoriteStore.name === 'string' ? window.FavoriteStore.name : this.state.name;
                const keys = typeof window.FavoriteStore.getFavorites === 'function' ? window.FavoriteStore.getFavorites() : [];
                if (Array.isArray(keys) && keys.length > 0) {
                    const map = {};
                    this.catalog.forEach(it => { map[it.key] = it; });
                    this.state.widgets = keys.map(k => {
                        const it = map[k];
                        return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                    });
                } else {
                    await this.load();
                }
            } else {
                await this.load();
            }
            this.dedupe();
            this.bindTitle();
            const navBtn = document.getElementById('nav-tab-personal');
            if (navBtn) navBtn.textContent = this.state.name;
            if (typeof window.StarInjector === 'undefined') {
                this.attachFavOverlays();
                this.attachFavOverlaysCompras();
                this.setupComprasObserver();
            }
            this.render();
            this.enableDrag();
            window.PersonalTab = this;
            document.addEventListener('datia:snapshot-ready', () => { this.render(); if (typeof window.StarInjector === 'undefined') this.attachFavOverlaysCompras(); });
            document.addEventListener('datia:kpis-ready', () => { this.render(); });
            document.addEventListener('datia:tab-change', (e) => {
                try {
                    const id = e && e.detail && e.detail.tabId;
                    if (id === 'tab-personal') this.render();
                    if (id === 'sub-compras') { if (typeof window.StarInjector === 'undefined') { this.attachFavOverlaysCompras(); this.setupComprasObserver(); } }
                } catch (_) {}
            });
            document.addEventListener('datia:favorites-change', (e) => {
                try {
                    const detail = e && e.detail ? e.detail : {};
                    if (typeof detail.name === 'string') {
                        this.state.name = detail.name;
                        const navBtn2 = document.getElementById('nav-tab-personal');
                        if (navBtn2) navBtn2.textContent = this.state.name;
                    }
                    const keys = Array.isArray(detail.keys) ? detail.keys : [];
                    const map = {};
                    this.catalog.forEach(it => { map[it.key] = it; });
                    this.state.widgets = keys.map(k => {
                        const it = map[k];
                        return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                    });
                    this.dedupe();
                    this.render();
                } catch (_) {}
            });
        },
        async ensureDataCaches() {
            try {
                const apiBase = (typeof API !== 'undefined' && API) ? API : '/api/datia';
                const emp = (typeof currEmpresa !== 'undefined' && currEmpresa) ? currEmpresa : (new URLSearchParams(window.location.search).get('empresa') || '');
                const eje = (typeof currEjercicio !== 'undefined' && currEjercicio) ? currEjercicio : (new URLSearchParams(window.location.search).get('ejercicio') || '');
                const q = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(eje)}`;
                if (!window.cachedSnapshotData) {
                    if (typeof loadSnapshot === 'function') {
                        try { await loadSnapshot(); } catch (_) {}
                    } else {
                        try {
                            const r = await fetch(`${apiBase}/widgets/snapshot${q}`);
                            const j = await r.json();
                            const d = j && (j.data || j);
                            if (d) {
                                window.cachedSnapshotData = d;
                                try { document.dispatchEvent(new CustomEvent('datia:snapshot-ready', { detail: { source: 'personal' } })); } catch (_) {}
                            }
                        } catch (_) {}
                    }
                }
                if (!window.cachedKpiData) {
                    try {
                        const r = await fetch(`${apiBase}/widgets/ventas_resumen${q}`);
                        const j = await r.json();
                        const d = j && (j.data || j);
                        if (d) {
                            window.cachedKpiData = d;
                            try { document.dispatchEvent(new CustomEvent('datia:kpis-ready', { detail: { source: 'personal' } })); } catch (_) {}
                        }
                    } catch (_) {}
                }
                if (!window.cachedComprasSnapshotData) {
                    const needCompras = Array.isArray(this.state.widgets) && this.state.widgets.some(w => {
                        const t = w && w.type ? String(w.type) : '';
                        return t === 'compras' || t === 'ticket_compra' || t === 'ops_compra' || t === 'compras_year' || t === 'ticket_compra_year' || t === 'kpi_proveedores';
                    });
                    const comprasPanel = document.getElementById('sub-compras');
                    const comprasVisible = comprasPanel && (comprasPanel.classList.contains('active') || comprasPanel.style.display !== 'none');
                    if (needCompras || comprasVisible) {
                        try {
                            if (typeof window.fetchSnapshot === 'function') {
                                const d2 = await window.fetchSnapshot('compras', emp, eje, 10000);
                                if (d2) window.cachedComprasSnapshotData = d2;
                            } else if (typeof loadSnapshotCompras === 'function') {
                                try { await loadSnapshotCompras(); } catch (_) {}
                            } else {
                                try {
                                    const r2 = await fetch(`${apiBase}/widgets/snapshot${q}&kind=compras`);
                                    const j2 = await r2.json();
                                    const d2b = j2 && (j2.data || j2);
                                    if (d2b) window.cachedComprasSnapshotData = d2b;
                                } catch (_) {}
                            }
                        } catch (_) {}
                    }
                }
            } catch (_) {}
        },
        setupComprasObserver() {
            try {
                if (typeof window.StarInjector !== 'undefined') return;
                if (this._comprasObs) return;
                const cont = document.getElementById('sub-compras');
                if (!cont) return;
                const obs = new MutationObserver(() => { this.attachFavOverlaysCompras(); });
                obs.observe(cont, { childList: true, subtree: true });
                this._comprasObs = obs;
            } catch (_) {}
        },
        attachFavOverlaysCompras() {
            if (typeof window.StarInjector !== 'undefined') return;
            const cont = document.getElementById('sub-compras');
            if (!cont) return;
            const headers = Array.from(cont.querySelectorAll('.flip-card-front .v2-kpi-header'));
            if (!headers || headers.length === 0) return;
            const map = {};
            this.catalog.forEach(it => { map[it.domId] = it; });
            headers.forEach(header => {
                const front = header.closest('.flip-card-front');
                if (!front) return;
                const val = front.querySelector('[id^="val-"], [id^="chart-"]');
                if (!val || !val.id) return;
                const domId = val.id;
                const w = map[domId] || { key: domId, title: domId, type: 'sales', period: '1d', domId };
                let actions = header.querySelector('.kpi-actions');
                let injected = false;
                if (!actions) {
                    actions = document.createElement('div');
                    actions.className = 'kpi-actions';
                    const flipBtn = header.querySelector('.flip-btn');
                    if (flipBtn) {
                        actions.appendChild(flipBtn);
                    }
                    header.appendChild(actions);
                }
                const exists = actions.querySelector('.act-fav-btn[data-key="' + w.key + '"]');
                if (!exists) {
                    const btn = document.createElement('button');
                    const isActive = this.state.widgets.some(x => x.key === w.key);
                    btn.className = 'act-fav-btn' + (isActive ? '' : ' inactive');
                    btn.setAttribute('data-key', w.key);
                    btn.title = isActive ? 'Añadido a Pestaña Personal' : 'Añadir a Pestaña Personal';
                    btn.textContent = '★';
                    btn.onclick = () => {
                        if (this.toggleWidget(w)) {
                            btn.classList.remove('inactive');
                            btn.title = 'Añadido a Pestaña Personal';
                        } else {
                            btn.classList.add('inactive');
                            btn.title = 'Añadir a Pestaña Personal';
                        }
                    };
                    actions.appendChild(btn);
                    injected = true;
                }
                if (!injected) {
                    const hasOverlay = front.querySelector('.act-fav-overlay');
                    if (!hasOverlay) {
                        const overlay = document.createElement('div');
                        overlay.className = 'act-fav-overlay';
                        const btn2 = document.createElement('button');
                        const isActive2 = this.state.widgets.some(x => x.key === w.key);
                        btn2.className = 'act-fav-btn' + (isActive2 ? '' : ' inactive');
                        btn2.setAttribute('data-key', w.key);
                        btn2.title = isActive2 ? 'Añadido a Pestaña Personal' : 'Añadir a Pestaña Personal';
                        btn2.textContent = '★';
                        btn2.onclick = () => {
                            if (this.toggleWidget(w)) {
                                btn2.classList.remove('inactive');
                                btn2.title = 'Añadido a Pestaña Personal';
                            } else {
                                btn2.classList.add('inactive');
                                btn2.title = 'Añadir a Pestaña Personal';
                            }
                        };
                        overlay.appendChild(btn2);
                        front.appendChild(overlay);
                    }
                }
            });
        },
        bindTitle() {
            const titleEl = document.getElementById('personal-tab-title');
            const inputEl = document.getElementById('personal-title-input');
            const btnSave = document.getElementById('personal-title-save');
            if (!titleEl) return;
            titleEl.textContent = this.state.name;
            if (inputEl) inputEl.value = this.state.name;
            if (btnSave && inputEl) {
                btnSave.onclick = () => {
                    const name = inputEl.value.trim() || 'Pestaña Personal';
                    this.state.name = name;
                    titleEl.textContent = name;
                    this.save();
                };
            }
        },
        attachFavOverlays() {
            if (typeof window.StarInjector !== 'undefined') return;
            const allowed = new Set(['sub-ventas', 'sub-compras', 'sub-almacen', 'sub-financiera']);
            this.catalog.forEach(w => {
                const el = document.getElementById(w.domId);
                if (!el) return;
                const sub = el.closest('.sub-tab');
                const subId = sub ? sub.id : '';
                if (!allowed.has(subId)) return;
                const front = el.closest('.flip-card-front') || el.closest('.flip-card') || el.closest('.alm-card');
                let header = null;
                if (front) {
                    header = front.querySelector('.v2-kpi-header') || front.querySelector('.fin-card-header') || front.querySelector('.alm-card-title') || front.querySelector('.alm-card-header') || front.querySelector('.fin-kpi-label');
                } else {
                    header = el.closest('.v2-kpi-header') || el.closest('.fin-card-header') || el.closest('.alm-card-title') || el.closest('.alm-card-header') || el.closest('.fin-kpi-label');
                }
                if (!header && front) {
                    const hasOverlay = front.querySelector('.act-fav-overlay');
                    if (!hasOverlay) {
                        const overlay = document.createElement('div');
                        overlay.className = 'act-fav-overlay';
                        const btn2 = document.createElement('button');
                        const isActive2 = this.state.widgets.some(x => x.key === w.key);
                        btn2.className = 'act-fav-btn' + (isActive2 ? '' : ' inactive');
                        btn2.setAttribute('data-key', w.key);
                        btn2.title = isActive2 ? 'Añadido a Pestaña Personal' : 'Añadir a Pestaña Personal';
                        btn2.textContent = '★';
                        btn2.onclick = () => {
                            if (this.toggleWidget(w)) {
                                btn2.classList.remove('inactive');
                                btn2.title = 'Añadido a Pestaña Personal';
                            } else {
                                btn2.classList.add('inactive');
                                btn2.title = 'Añadir a Pestaña Personal';
                            }
                        };
                        overlay.appendChild(btn2);
                        front.appendChild(overlay);
                    }
                    return;
                }
                let actions = header.querySelector('.kpi-actions');
                if (!actions) {
                    actions = document.createElement('div');
                    actions.className = 'kpi-actions';
                    const flipBtn = header.querySelector('.flip-btn');
                    if (flipBtn) {
                        actions.appendChild(flipBtn);
                    }
                    header.appendChild(actions);
                }
                const existing = actions.querySelector('.act-fav-btn[data-key="' + w.key + '"]');
                if (existing) return;
                const btn = document.createElement('button');
                const isActive = this.state.widgets.some(x => x.key === w.key);
                btn.className = 'act-fav-btn' + (isActive ? '' : ' inactive');
                btn.setAttribute('data-key', w.key);
                btn.title = isActive ? 'Añadido a Pestaña Personal' : 'Añadir a Pestaña Personal';
                btn.textContent = '★';
                btn.onclick = () => {
                    if (this.toggleWidget(w)) {
                        btn.classList.remove('inactive');
                        btn.title = 'Añadido a Pestaña Personal';
                    } else {
                        btn.classList.add('inactive');
                        btn.title = 'Añadir a Pestaña Personal';
                    }
                };
                actions.appendChild(btn);
            });
        },
        toggleWidget(w) {
            try {
                if (typeof window.FavoriteStore !== 'undefined' && typeof window.FavoriteStore.toggle === 'function') {
                    window.FavoriteStore.toggle(w.key);
                    return this.state.widgets.some(x => x.key === w.key);
                }
            } catch (_) {}
            this.dedupe();
            const idx = this.state.widgets.findIndex(x => x.key === w.key);
            if (idx >= 0) {
                this.state.widgets = this.state.widgets.filter(x => x.key !== w.key);
                this.render();
                this.save();
                this.setStarState(w.key, false);
                this._toast('Widget eliminado', false);
                return false;
            }
            const exists = this.state.widgets.some(x => x.key === w.key);
            if (!exists) {
                this.state.widgets.push({ key: w.key, title: w.title, type: w.type, period: w.period });
            }
            this.render();
            this.save();
            this.setStarState(w.key, true);
            this._toast('Widget añadido', false);
            return true;
        },
        _getOrigin(w) {
            try {
                if (typeof window.WidgetRegistry !== 'undefined' && window.WidgetRegistry.map) {
                    const it = window.WidgetRegistry.map[w.key];
                    if (it && it.origin) return it.origin;
                }
            } catch (_) {}
            try {
                if (/^alm_/.test(w.type || w.key)) return 'almacen';
                if (/^fin_/.test(w.type || w.key)) return 'financiera';
                if (['sales','ticket','margin','neto','coste'].includes(w.type)) return 'ventas';
                if (['compras','ticket_compra','ops_compra','kpi_proveedores','compras_year','ticket_compra_year'].includes(w.type)) return 'compras';
            } catch (_) {}
            return 'ventas';
        },
        render() {
            const list = document.getElementById('personal-widget-list');
            if (!list) return;
            list.innerHTML = '';
            try { list.classList.toggle('grouped', !!this.state.grouped); } catch (_) {}
            this.dedupe();
            if (!this.state.widgets || this.state.widgets.length === 0) {
                const actives = Array.from(document.querySelectorAll('.act-fav-btn:not(.inactive)')).map(b => b.getAttribute('data-key')).filter(Boolean);
                if (actives.length > 0) {
                    const map = {};
                    this.catalog.forEach(it => { map[it.key] = it; });
                    this.state.widgets = actives.map(k => {
                        const it = map[k];
                        return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                    });
                    this.save();
                } else {
                    try {
                        const cached = localStorage.getItem('datia-personal-tab-layout');
                        if (cached) {
                            const c = JSON.parse(cached);
                            if (c && Array.isArray(c.widgets) && c.widgets.length > 0) {
                                this.state.widgets = c.widgets;
                            } else if (c && c.widgets && typeof c.widgets === 'object') {
                                const keys = Object.keys(c.widgets).filter(k => c.widgets[k]);
                                const map2 = {};
                                this.catalog.forEach(it => { map2[it.key] = it; });
                                this.state.widgets = keys.map(k => {
                                    const it = map2[k];
                                    return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                                });
                            }
                        }
                    } catch (_) {}
                    if (!this.state.widgets || this.state.widgets.length === 0) {
                        const map3 = {};
                        this.catalog.forEach(it => { map3[it.key] = it; });
                        const defaults = ['compras_1d'];
                        this.state.widgets = defaults.map(k => {
                            const it = map3[k];
                            return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                        });
                    }
                }
            }
            const snap = window.cachedSnapshotData || null;
            const kpi = window.cachedKpiData || null;
            if (this.state.grouped) {
                const groups = { ventas: [], compras: [], almacen: [], financiera: [] };
                this.state.widgets.forEach(w => {
                    const origin = this._getOrigin(w);
                    (groups[origin] || groups['ventas']).push(w);
                });
                const order = ['ventas','compras','almacen','financiera'];
                const labels = { ventas: 'Ventas', compras: 'Compras', almacen: 'Existencias', financiera: 'Financiera' };
                let idx = 0;
                order.forEach(group => {
                    const arr = groups[group];
                    if (!arr || arr.length === 0) return;
                    const section = document.createElement('div');
                    section.className = 'personal-group group-' + group;
                    const title = document.createElement('div');
                    title.className = 'personal-group-title';
                    title.textContent = labels[group];
                    const grid = document.createElement('div');
                    grid.className = 'personal-group-grid';
                    section.appendChild(title);
                    section.appendChild(grid);
                    arr.forEach(w => {
                        const card = document.createElement('div');
                        card.className = 'personal-card';
                        card.draggable = true;
                        card.dataset.index = String(idx);
                        const header = document.createElement('div');
                        header.className = 'personal-card-title';
                        const badge = document.createElement('span');
                        badge.className = 'personal-origin-badge origin-' + this._getOrigin(w);
                        badge.textContent = labels[this._getOrigin(w)];
                        const titleSpan = document.createElement('span');
                        titleSpan.textContent = w.title;
                        const removeBtn = document.createElement('button');
                        removeBtn.className = 'personal-remove';
                        removeBtn.textContent = '✕';
                        removeBtn.onclick = () => {
                            this.dedupe();
                            this.state.widgets = this.state.widgets.filter(x => x.key !== w.key);
                            this.render();
                            this.save();
                            this.setStarState(w.key, false);
                            this._toast('Widget eliminado', false);
                        };
                        header.appendChild(titleSpan);
                        header.appendChild(badge);
                        header.appendChild(removeBtn);
                        card.appendChild(header);
                        const valEl = document.createElement('div');
                        valEl.className = 'personal-card-value';
                        valEl.textContent = this._formatValue(w, snap, kpi);
                        card.appendChild(valEl);
                        grid.appendChild(card);
                        idx++;
                    });
                    list.appendChild(section);
                });
            } else {
                this.state.widgets.forEach((w, i) => {
                    const card = document.createElement('div');
                    card.className = 'personal-card';
                    card.draggable = true;
                    card.dataset.index = String(i);
                    const header = document.createElement('div');
                    header.className = 'personal-card-title';
                    const badge = document.createElement('span');
                    const labels = { ventas: 'Ventas', compras: 'Compras', almacen: 'Existencias', financiera: 'Financiera' };
                    badge.className = 'personal-origin-badge origin-' + this._getOrigin(w);
                    badge.textContent = labels[this._getOrigin(w)];
                    const titleSpan = document.createElement('span');
                    titleSpan.textContent = w.title;
                    const removeBtn = document.createElement('button');
                    removeBtn.className = 'personal-remove';
                    removeBtn.textContent = '✕';
                    removeBtn.onclick = () => {
                        this.dedupe();
                        this.state.widgets = this.state.widgets.filter(x => x.key !== w.key);
                        this.render();
                        this.save();
                        this.setStarState(w.key, false);
                        this._toast('Widget eliminado', false);
                    };
                    header.appendChild(titleSpan);
                    header.appendChild(badge);
                    header.appendChild(removeBtn);
                    card.appendChild(header);
                    const valEl = document.createElement('div');
                    valEl.className = 'personal-card-value';
                    valEl.textContent = this._formatValue(w, snap, kpi);
                    card.appendChild(valEl);
                    list.appendChild(card);
                });
            }
        },
        _formatValue(w, snap, kpi) {
            try {
                if (typeof window.WidgetRegistry !== 'undefined' && typeof window.WidgetRegistry.getValue === 'function') {
                    return window.WidgetRegistry.getValue(w.key);
                }
            } catch (_) {}
            try {
                if (w.period === 'year' && kpi) {
                    if (w.type === 'neto') return this._fmtMoney(kpi.neto);
                    if (w.type === 'coste') return this._fmtMoney(kpi.coste);
                    if (w.type === 'margin') return ((kpi.margen !== undefined ? kpi.margen : (kpi.margin || 0))).toFixed(2) + '%';
                    if (w.type === 'ticket') return this._fmtMoney(kpi.ticket);
                } else if (snap) {
                    const p = 'm_' + w.period;
                    const data = snap[p] || {};
                    if (w.type === 'sales') return this._fmtMoney(data.neto || 0);
                    if (w.type === 'ticket') return this._fmtMoney(data.ticket || 0);
                    if (w.type === 'margin') return ((data.margin || 0)).toFixed(2) + '%';
                }
                const compras = typeof window !== 'undefined' ? (window.cachedComprasSnapshotData || null) : null;
                if (compras) {
                    const p2 = 'm_' + w.period;
                    const d2 = compras[p2] || {};
                    if (w.type === 'compras') return this._fmtMoney(d2.neto || 0);
                    if (w.type === 'ticket_compra') return this._fmtMoney(d2.ticket || 0);
                    if (w.type === 'ops_compra') return String((d2.albaranes !== undefined ? d2.albaranes : (d2.ops || 0)));
                    if (w.period === 'year' && w.type === 'compras_year') {
                        if (typeof compras.global_neto !== 'undefined') return this._fmtMoney(compras.global_neto || 0);
                    }
                    if (w.period === 'year' && w.type === 'ticket_compra_year') {
                        if (typeof compras.global_ticket !== 'undefined') return this._fmtMoney(compras.global_ticket || 0);
                    }
                    if (w.period === 'year' && w.type === 'kpi_proveedores') {
                        if (typeof compras.global_entities !== 'undefined') return String(compras.global_entities || 0);
                    }
                }
                const fin = typeof window !== 'undefined' ? (window.cachedFinancialData || null) : null;
                if (fin) {
                    if (w.type === 'fin_ingresos') return this._fmtMoney(fin.ingresos || 0);
                    if (w.type === 'fin_gastos') return this._fmtMoney(fin.gastos || 0);
                    if (w.type === 'fin_resultado') return this._fmtMoney(fin.resultado || 0);
                }
                if (w.type === 'alm_base') {
                    const elBase = document.getElementById('alm-sum-base-valor');
                    if (elBase && elBase.textContent) return elBase.textContent;
                }
                if (w.type === 'alm_variacion') {
                    const elVar = document.getElementById('alm-sum-variacion');
                    if (elVar && elVar.textContent) return elVar.textContent;
                }
                if (w.type === 'alm_end') {
                    const elEnd = document.getElementById('alm-sum-end');
                    if (elEnd && elEnd.textContent) return elEnd.textContent;
                }
            } catch (e) { }
            return '-';
        },
        _fmtMoney(n) {
            try {
                return new Intl.NumberFormat((window.APP_LANG || 'es-ES'), { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n || 0));
            } catch (e) { return Number(n || 0).toFixed(2); }
        },
        enableDrag() {
            const list = document.getElementById('personal-widget-list');
            if (!list) return;
            let fromIdx = null;
            let overIdx = null;
            let draggingEl = null;
            list.addEventListener('dragstart', (e) => {
                const t = e.target.closest('.personal-card');
                if (!t) return;
                fromIdx = Number(t.dataset.index || -1);
                draggingEl = t;
                t.classList.add('dragging');
                if (e.dataTransfer) {
                    e.dataTransfer.effectAllowed = 'move';
                    try { e.dataTransfer.setData('text/plain', String(fromIdx)); } catch (_) { }
                }
            });
            list.addEventListener('dragenter', (e) => {
                e.preventDefault();
                if (e.dataTransfer) {
                    try { e.dataTransfer.dropEffect = 'move'; } catch (_) { }
                }
            });
            list.addEventListener('dragend', (e) => {
                const t = e.target.closest('.personal-card');
                if (t) t.classList.remove('dragging');
                Array.from(list.querySelectorAll('.personal-card')).forEach(c => c.classList.remove('drag-over'));
                fromIdx = null;
                overIdx = null;
                draggingEl = null;
            });
            list.addEventListener('dragover', (e) => {
                e.preventDefault();
                const cards = Array.from(list.querySelectorAll('.personal-card'));
                if (e.dataTransfer) {
                    try { e.dataTransfer.dropEffect = 'move'; } catch (_) { }
                }
                const x = e.clientX;
                const y = e.clientY;
                overIdx = cards.length;
                // Temporarily ignore the dragging element for hit-test
                const draggingRect = draggingEl ? draggingEl.getBoundingClientRect() : null;
                cards.forEach(c => c.classList.remove('drag-over'));
                for (let i = 0; i < cards.length; i++) {
                    const rect = cards[i].getBoundingClientRect();
                    const withinX = x >= rect.left && x <= rect.right;
                    const withinY = y >= rect.top && y <= rect.bottom;
                    if (withinX && withinY) { overIdx = i; cards[i].classList.add('drag-over'); break; }
                    // Fallback: vertical ordering if pointer below mid
                    const mid = rect.top + rect.height / 2;
                    if (y < mid && x >= rect.left) { overIdx = Math.min(overIdx, i); cards[i].classList.add('drag-over'); break; }
                }
            });
            list.addEventListener('drop', (e) => {
                e.preventDefault();
                Array.from(list.querySelectorAll('.personal-card')).forEach(c => c.classList.remove('drag-over'));
                if (fromIdx === null) return;
                if (overIdx === null) overIdx = this.state.widgets.length;
                let toIdx = overIdx;
                if (toIdx < 0) toIdx = 0;
                if (toIdx > this.state.widgets.length) toIdx = this.state.widgets.length;
                if (fromIdx === toIdx || fromIdx === toIdx - 1) {
                    fromIdx = null; overIdx = null; return;
                }
                this.reorderWidgets(fromIdx, toIdx);
                fromIdx = null;
                overIdx = null;
                draggingEl = null;
            });
        },
        reorderWidgets(fromIdx, toIdx) {
            if (fromIdx < 0 || fromIdx >= this.state.widgets.length) return;
            if (toIdx < 0) toIdx = 0;
            if (toIdx > this.state.widgets.length) toIdx = this.state.widgets.length;
            const originalLen = this.state.widgets.length;
            const item = this.state.widgets.splice(fromIdx, 1)[0];
            if (toIdx > fromIdx) toIdx = toIdx - 1;
            this.state.widgets.splice(toIdx, 0, item);
            const len = this.state.widgets.length;
            const unique = new Set(this.state.widgets.map(x => x.key)).size === len;
            if (!unique || len !== originalLen) {
                const keys = Array.from(new Set(this.state.widgets.map(x => x.key)));
                this.state.widgets = keys.map(k => {
                    return (item.key === k ? item : (this.state.widgets.find(x => x.key === k) || { key: k }));
                });
            }
            this.render();
            this.save();
        },
        runTests() {
            const results = [];
            const invariant = !document.getElementById('personal-title-input') && !document.getElementById('personal-title-save');
            results.push({ test: 'nombre-invariable', pass: invariant });
            const original = JSON.parse(JSON.stringify(this.state.widgets));
            if (this.state.widgets.length >= 3) {
                const before = this.state.widgets.map(w => w.key).join(',');
                this.reorderWidgets(0, this.state.widgets.length);
                const after = this.state.widgets.map(w => w.key).join(',');
                const expected = original.slice(1).map(w => w.key).concat(original[0].key).join(',');
                results.push({ test: 'reordenar-primero-al-final', pass: after === expected });
                this.state.widgets = original;
                this.render();
                this.save();
            } else {
                results.push({ test: 'reordenar-primero-al-final', pass: true });
            }
            const lenBefore = this.state.widgets.length;
            if (lenBefore > 0) this.reorderWidgets(lenBefore - 1, 0);
            const lenAfter = this.state.widgets.length;
            const uniq = new Set(this.state.widgets.map(x => x.key)).size === lenAfter;
            results.push({ test: 'integridad', pass: lenBefore === lenAfter && uniq });
            this.state.widgets = original;
            this.render();
            this.save();
            const allPass = results.every(r => r.pass);
            try { console.table(results); } catch (_) { }
            if (typeof showToast === 'function') showToast(allPass ? 'Pruebas Pestaña Personal OK ✅' : 'Pruebas Pestaña Personal fallan ❌', !allPass);
        },
        async load() {
            try {
                // Local fallback to avoid empty UI if backend returns blank
                try {
                    const cached = localStorage.getItem('datia-personal-tab-layout');
                    if (cached) {
                        const c = JSON.parse(cached);
                        if (c && typeof c === 'object') {
                            if (c.name) this.state.name = c.name;
                            if (Array.isArray(c.widgets)) this.state.widgets = c.widgets;
                        }
                    }
                } catch (_) {}
                const res = await fetch('/api/financial/preferences/layout');
                const data = await res.json();
                const v = (data && typeof data === 'object' && data.layout && typeof data.layout === 'object') ? data.layout : data;
                const ct = v && v.custom_tab ? v.custom_tab : null;
                if (ct) {
                    this.state.name = ct.name || this.state.name;
                    if (Array.isArray(ct.widgets)) {
                        this.state.widgets = ct.widgets;
                    } else if (ct.widgets && typeof ct.widgets === 'object') {
                        const keys = Object.keys(ct.widgets).filter(k => ct.widgets[k]);
                        const map = {};
                        this.catalog.forEach(it => { map[it.key] = it; });
                        this.state.widgets = keys.map(k => {
                            const it = map[k];
                            return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                        });
                    } else if (Array.isArray(v.custom_tab_keys)) {
                        const keys = v.custom_tab_keys;
                        const map = {};
                        this.catalog.forEach(it => { map[it.key] = it; });
                        this.state.widgets = keys.map(k => {
                            const it = map[k];
                            return it ? { key: it.key, title: it.title, type: it.type, period: it.period } : { key: k, title: k, type: 'sales', period: '1d' };
                        });
                    } else {
                        this.state.widgets = [];
                    }
                    try { localStorage.setItem('datia-personal-tab-layout', JSON.stringify({ name: this.state.name, widgets: this.state.widgets })); } catch (_) {}
                }
            } catch (e) { /* silent */ }
        },
        async save() {
            try {
                const headers = { 'Content-Type': 'application/json' };
                let token = null;
                try { if (typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) token = CSRF_TOKEN; } catch (_) {}
                if (!token) {
                    try {
                        const name = 'csrftoken';
                        const value = `; ${document.cookie}`;
                        const parts = value.split(`; ${name}=`);
                        if (parts.length === 2) token = decodeURIComponent(parts.pop().split(';').shift());
                    } catch (_) {}
                }
                if (token) headers['X-CSRFToken'] = token;
                const getRes = await fetch('/api/financial/preferences/layout');
                const current = await getRes.json();
                const base = (current && typeof current === 'object' && current.layout && typeof current.layout === 'object') ? current.layout : (current || {});
                const keys = this.state.widgets.map(w => w.key);
                const merged = Object.assign({}, base, { custom_tab: { name: this.state.name, widgets: this.state.widgets }, custom_tab_keys: keys });
                const res = await fetch('/api/financial/preferences/layout', {
                    method: 'POST',
                    headers,
                    body: JSON.stringify({ layout: merged })
                });
                if (!res.ok) {
                    this._toast('Error al guardar configuración', true);
                } else {
                    await res.json();
                }
                try { localStorage.setItem('datia-personal-tab-layout', JSON.stringify({ name: this.state.name, widgets: this.state.widgets })); } catch (_) {}
            } catch (e) { }
        }
    };
    document.addEventListener('DOMContentLoaded', function () {
        const el = document.getElementById('tab-personal');
        if (el) {
            PersonalTab.init();
            try {
                const run = localStorage.getItem('datia-test-personal') === 'true';
                if (run) PersonalTab.runTests();
            } catch (_) { }
        }
    });
    (function immediateInit() {
        try {
            const el = document.getElementById('tab-personal');
            if (el && document.readyState !== 'loading' && !window.PersonalTab) {
                PersonalTab.init();
                try {
                    const run = localStorage.getItem('datia-test-personal') === 'true';
                    if (run) PersonalTab.runTests();
                } catch (_) { }
            }
        } catch (_) {}
    })();
})();
