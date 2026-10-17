/**
 * Datia Mobile App (Mobile First)
 * Desacoplado de escritorio, con selectores y gestión de logo móvil.
 */
(function () {
    const root = document.getElementById('datia-mobile');
    if (!root) return;

    const appLang = root.dataset.appLang || 'es-ES';
    window.APP_LANG = appLang;

    const state = {
        layout: [],
        caches: {}
    };

    const selEmpresa = document.getElementById('sel-mobile-empresa');
    const selEjercicio = document.getElementById('sel-mobile-ejercicio');
    const logoImg = document.getElementById('mobile-logo');
    const btnLogoConfig = document.getElementById('btn-logo-config');
    const btnLogoClientToggle = document.getElementById('btn-logo-client-toggle');
    const logoConfigPanel = document.getElementById('dm-logo-config');
    const inpLogoUrl = document.getElementById('inp-mobile-logo-url');
    const btnSaveLogo = document.getElementById('btn-save-mobile-logo');

    function getCookie(name) {
        const nameEQ = name + '=';
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i].trim();
            if (c.indexOf(nameEQ) === 0) return decodeURIComponent(c.substring(nameEQ.length));
        }
        return null;
    }

    function getEmp() {
        const v = selEmpresa ? selEmpresa.value : (root.dataset.empresa || '');
        return v;
    }
    function getEj() {
        return selEjercicio ? selEjercicio.value : (root.dataset.ejercicio || '2025');
    }

    function api(path) {
        if (!path.startsWith('/')) path = '/' + path;
        return '/api' + path;
    }
    function finKey(emp, ej) { return `datia_fin_snapshot_${emp}_${ej}`; }
    function snapKey(emp, ej) { return `datia_sales_snapshot_${emp}_${ej}`; }
    function comprasKey(emp, ej) { return `datia_compras_snapshot_${emp}_${ej}`; }
    function getCache(key, ttl = 300000) {
        try {
            const raw = localStorage.getItem(key);
            if (!raw) return null;
            const obj = JSON.parse(raw);
            if (!obj || !obj.ts || obj.data === undefined) return null;
            if ((Date.now() - obj.ts) > ttl) return null;
            return obj.data;
        } catch (e) { return null; }
    }
    function setCache(key, data) {
        try {
            localStorage.setItem(key, JSON.stringify({ ts: Date.now(), data }));
        } catch (e) { }
    }

    function getSelectedLogo() {
        return localStorage.getItem('datia-selected-logo') || getCookie('datia-selected-logo');
    }
    function getClientLogo(emp) {
        return localStorage.getItem(`datia-client-logo-${emp}`);
    }
    function getShowClient(emp) {
        return localStorage.getItem(`datia-show-client-logo-${emp}`) === 'true';
    }
    function getMobileLogo(emp) {
        return localStorage.getItem(`datia-mobile-logo-${emp}`);
    }
    function setMobileLogo(emp, url) {
        if (url) localStorage.setItem(`datia-mobile-logo-${emp}`, url);
        else localStorage.removeItem(`datia-mobile-logo-${emp}`);
    }
    function setShowClient(emp, show) {
        localStorage.setItem(`datia-show-client-logo-${emp}`, show ? 'true' : 'false');
    }

    function applyAccentToMobile() {
        try {
            const savedAccent = localStorage.getItem('datia-accent-color') || getCookie('datia-accent-color');
            if (savedAccent) document.documentElement.style.setProperty('--dm-accent', savedAccent);
        } catch (e) {}
    }

    function isUnsafeHttp(u) {
        try {
            return /^http:\/\//.test(String(u || '')) && window.location && window.location.protocol === 'https:';
        } catch (e) {
            return false;
        }
    }

    function updateLogo() {
        const emp = getEmp();
        const custom = getMobileLogo(emp);
        const client = getClientLogo(emp);
        const showClient = getShowClient(emp);
        const selected = getSelectedLogo();

        let src = '';
        if (selected) src = selected;
        else if (showClient && client) src = client;
        else if (custom) src = custom;
        if (!src || isUnsafeHttp(src)) src = '/static/logo_analytics.png';
        logoImg.src = src;
    }

    function toggleLogoConfig() {
        if (!logoConfigPanel) return;
        const visible = logoConfigPanel.style.display === 'block';
        logoConfigPanel.style.display = visible ? 'none' : 'block';
        const emp = getEmp();
        const current = getMobileLogo(emp) || '';
        if (inpLogoUrl) inpLogoUrl.value = current;
    }

    function saveLogo() {
        const emp = getEmp();
        const url = (inpLogoUrl && inpLogoUrl.value || '').trim();
        if (url) {
            setMobileLogo(emp, url);
            setShowClient(emp, false);
        } else {
            setMobileLogo(emp, null);
        }
        updateLogo();
        if (logoConfigPanel) logoConfigPanel.style.display = 'none';
    }

    function toggleClientLogo() {
        const emp = getEmp();
        const state = getShowClient(emp);
        setShowClient(emp, !state);
        updateLogo();
    }

    async function handleEmpresaChange() {
        const emp = getEmp();
        localStorage.setItem('datia-mobile-empresa', emp);
        updateLogo();
        await refreshEjercicios(emp);
        {
            const saved = localStorage.getItem('datia-mobile-ejercicio');
            const hasSaved = saved && Array.from(selEjercicio.options).some(o => o.value == saved);
            if (hasSaved) selEjercicio.value = saved;
            else if (selEjercicio.options.length) {
                selEjercicio.value = selEjercicio.options[0].value;
                localStorage.setItem('datia-mobile-ejercicio', selEjercicio.value);
            }
        }
        await loadMobileConfig();
        refreshRuntime();
    }
    function handleEjercicioChange() {
        const ej = getEj();
        localStorage.setItem('datia-mobile-ejercicio', ej);
        refreshRuntime();
    }

    function money(v) {
        if (v === null || v === undefined) return '--';
        return new Intl.NumberFormat(appLang, { style: 'currency', currency: 'EUR' }).format(v);
    }

    function refreshRuntime() {
        const container = document.getElementById('dm-runtime');
        if (!container) return;
        const emp = getEmp();
        const ej = getEj();
        container.innerHTML = `<div class="dm-grid" id="dm-grid"></div>`;
        const grid = document.getElementById('dm-grid');

        if (!state.layout || state.layout.length === 0) {
            grid.innerHTML = `
                <div class="dm-empty" style="grid-column: 1 / -1;">
                    <div class="dm-empty-icon">📱</div>
                    <h3>Sin widgets configurados</h3>
                    <p>Usa el editor de Actualidad > Móvil para definir el layout.</p>
                </div>
            `;
            return;
        }

        state.layout.forEach(id => {
            const card = document.createElement('div');
            card.className = 'dm-card';
            card.innerHTML = `
                <div class="dm-card-header">${getTitle(id)}</div>
                <div class="dm-card-value" id="dm-val-${id}"><span class="dm-spinner">Cargando...</span></div>
            `;
            grid.appendChild(card);
        });

        loadDataIfNeeded(emp, ej).then(() => {
            state.layout.forEach(bindWidget);
        });
    }

    function getTitle(id) {
        const map = {
            'widget-sales-1d': 'Ventas (1 Día)',
            'widget-sales-7d': 'Ventas (7 Días)',
            'widget-sales-30d': 'Ventas (30 Días)',
            'widget-ticket-1d': 'Ticket (1 Día)',
            'widget-ticket-7d': 'Ticket (7 Días)',
            'widget-ticket-30d': 'Ticket (30 Días)',
            'widget-margin-1d': 'Margen (1 Día)',
            'widget-margin-7d': 'Margen (7 Días)',
            'widget-margin-30d': 'Margen (30 Días)',
            'widget-kpi-neto': 'Total Ventas (Anual)',
            'widget-kpi-coste': 'Total Costes (Anual)',
            'widget-kpi-margen': 'Margen Global (Anual)',
            'widget-kpi-ticket': 'Ticket Medio (Anual)',
            'widget-compras-1d': 'Compras (1 Día)',
            'widget-compras-7d': 'Compras (7 Días)',
            'widget-compras-30d': 'Compras (30 Días)',
            'widget-ticket-compra-1d': 'Ticket Compra (1 Día)',
            'widget-ticket-compra-7d': 'Ticket Compra (7 Días)',
            'widget-ticket-compra-30d': 'Ticket Compra (30 Días)',
            'widget-ops-compra-1d': 'Operaciones (1 Día)',
            'widget-ops-compra-7d': 'Operaciones (7 Días)',
            'widget-ops-compra-30d': 'Operaciones (30 Días)',
            'widget-kpi-compras-neto': 'Total Compras (Anual)',
            'widget-val-kpi-ticket-compra': 'Ticket Medio Compra (Anual)',
            'widget-val-kpi-ops-compra': 'Total Operaciones (Anual)',
            'widget-val-kpi-proveedores': 'Proveedores Activos',
            'widget-fin-ingresos': 'Ingresos Totales (Fin)',
            'widget-fin-gastos': 'Gastos Totales (Fin)',
            'widget-fin-resultado': 'EBITDA (Fin)',
            'widget-fin-liquidez': 'Ratio Liquidez',
            'widget-fin-margen': 'Margen %',
            'widget-fin-solvencia': 'Solvencia',
            'widget-fin-endeudamiento': 'Endeudamiento'
        };
        return map[id] || id;
    }

    async function loadDataIfNeeded(emp, ej) {
        const snapK = snapKey(emp, ej);
        const finK = finKey(emp, ej);
        const compK = comprasKey(emp, ej);

        const needSales = state.layout.some(id => id.includes('sales') || id.includes('ticket') || id.includes('margin') || id.includes('kpi-'));
        const needFin = state.layout.some(id => id.startsWith('widget-fin-'));
        const needCompra = state.layout.some(id => id.includes('compra') || id.includes('compras'));

        if (needSales && !getCache(snapK)) {
            const q = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(ej)}`;
            try {
                const res = await fetch(api(`/datia/widgets/snapshot${q}`));
                const json = await res.json();
                setCache(snapK, json.data || json);
            } catch (e) { }
        }
        if (needFin && !getCache(finK)) {
            const q = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(ej)}`;
            try {
                const res = await fetch(api(`/financial/snapshot${q}`));
                const json = await res.json();
                setCache(finK, json);
            } catch (e) { }
        }
        if (needCompra && !getCache(compK)) {
            const q = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(ej)}&kind=compras`;
            try {
                const res = await fetch(api(`/datia/widgets/snapshot${q}`));
                const json = await res.json();
                setCache(compK, json.data || json);
            } catch (e) { }
        }
    }

    function bindWidget(id) {
        const emp = getEmp();
        const ej = getEj();
        const el = document.getElementById(`dm-val-${id}`);
        if (!el) return;
        let val = '--';

        const dSales = getCache(snapKey(emp, ej));
        const dFin = getCache(finKey(emp, ej));
        const dComp = getCache(comprasKey(emp, ej));

        if (dSales) {
            if (id.includes('sales')) {
                if (id.includes('1d')) val = money(dSales.m_1d?.neto);
                else if (id.includes('7d')) val = money(dSales.m_7d?.neto);
                else if (id.includes('30d')) val = money(dSales.m_30d?.neto);
            } else if (id.includes('ticket') && !id.includes('compra')) {
                if (id.includes('1d')) val = money(dSales.m_1d?.ticket);
                else if (id.includes('7d')) val = money(dSales.m_7d?.ticket);
                else if (id.includes('30d')) val = money(dSales.m_30d?.ticket);
            } else if (id.includes('margin') && !id.includes('fin')) {
                if (id.includes('1d')) val = (dSales.m_1d?.margin || 0).toFixed(1) + '%';
                else if (id.includes('7d')) val = (dSales.m_7d?.margin || 0).toFixed(1) + '%';
                else if (id.includes('30d')) val = (dSales.m_30d?.margin || 0).toFixed(1) + '%';
            } else if (id === 'widget-kpi-neto' && dSales.global_neto !== undefined) val = money(dSales.global_neto);
            else if (id === 'widget-kpi-coste' && dSales.global_margin_eur !== undefined) val = money(dSales.global_neto - dSales.global_margin_eur);
            else if (id === 'widget-kpi-margen' && dSales.global_margin_pct !== undefined) val = dSales.global_margin_pct.toFixed(2) + '%';
            else if (id === 'widget-kpi-ticket' && dSales.global_ticket !== undefined) val = money(dSales.global_ticket);
        }
        if (dComp && (id.includes('compras') || id.includes('compra') || id.includes('ops-compra'))) {
            if (id.includes('1d')) {
                if (id.includes('ticket-compra')) val = money(dComp.m_1d?.ticket);
                else if (id.includes('ops-compra')) val = (dComp.m_1d?.albaranes || 0);
                else if (id.includes('compras')) val = money(dComp.m_1d?.neto);
            } else if (id.includes('7d')) {
                if (id.includes('ticket-compra')) val = money(dComp.m_7d?.ticket);
                else if (id.includes('ops-compra')) val = (dComp.m_7d?.albaranes || 0);
                else if (id.includes('compras')) val = money(dComp.m_7d?.neto);
            } else if (id.includes('30d')) {
                if (id.includes('ticket-compra')) val = money(dComp.m_30d?.ticket);
                else if (id.includes('ops-compra')) val = (dComp.m_30d?.albaranes || 0);
                else if (id.includes('compras')) val = money(dComp.m_30d?.neto);
            } else {
                if (id === 'widget-kpi-compras-neto') val = money(dComp.global_neto);
                else if (id === 'widget-val-kpi-ticket-compra') val = money(dComp.global_ticket);
                else if (id === 'widget-val-kpi-ops-compra') val = (dComp.global_albaranes || 0);
                else if (id === 'widget-val-kpi-proveedores') val = (dComp.active_providers || 0);
            }
        }
        if (dFin && id.startsWith('widget-fin-')) {
            if (id === 'widget-fin-ingresos') val = money(dFin.ingresos);
            else if (id === 'widget-fin-gastos') val = money(dFin.gastos);
            else if (id === 'widget-fin-resultado') val = money(dFin.resultado);
            else if (id === 'widget-fin-liquidez') val = (dFin.ratios?.liquidez ?? 0).toFixed(2);
            else if (id === 'widget-fin-margen') val = (dFin.ratios?.margen ?? 0).toFixed(2) + '%';
            else if (id === 'widget-fin-solvencia') val = (dFin.ratios?.solvencia ?? 0).toFixed(2);
            else if (id === 'widget-fin-endeudamiento') val = (dFin.ratios?.endeudamiento ?? 0).toFixed(2) + '%';
        }

        el.innerText = val;
    }

    async function init() {
        await loadMobileConfig();
        applyAccentToMobile();
        updateLogo();
        await loadServerUIPrefs();
        updateLogo();
        if (logoImg) {
            logoImg.onerror = function () {
                try { this.onerror = null; this.src = '/static/logo_analytics.png'; } catch (e) {}
            };
        }
        await refreshEjercicios(getEmp());
        refreshRuntime();
        if (selEmpresa) selEmpresa.addEventListener('change', handleEmpresaChange);
        if (selEjercicio) selEjercicio.addEventListener('change', handleEjercicioChange);
        if (btnLogoConfig) btnLogoConfig.addEventListener('click', toggleLogoConfig);
        if (btnSaveLogo) btnSaveLogo.addEventListener('click', saveLogo);
        if (btnLogoClientToggle) btnLogoClientToggle.addEventListener('click', toggleClientLogo);
    }
    document.addEventListener('DOMContentLoaded', function(){ init(); });

    async function loadServerUIPrefs() {
        try {
            const res = await fetch(api('/financial/preferences/ui'));
            if (!res.ok) return;
            const json = await res.json();
            let logo = json && json.selected_logo;
            let accent = json && json.accent_color;
            if (!logo || !accent) {
                try {
                    const cfgRes = await fetch('/api/config/global');
                    if (cfgRes.ok) {
                        const cfg = await cfgRes.json();
                        if (!logo) logo = (cfg && (cfg.selected_logo || (cfg.implanter_settings && cfg.implanter_settings.selected_logo))) || '';
                        if (!accent) accent = (cfg && (cfg.accent_color || (cfg.implanter_settings && cfg.implanter_settings.accent_color))) || '';
                    }
                } catch (e) {}
            }
            if (accent) {
                document.documentElement.style.setProperty('--dm-accent', accent);
                try { localStorage.setItem('datia-accent-color', accent); } catch (e) {}
            }
            if (logo) {
                try { localStorage.setItem('datia-selected-logo', logo); } catch (e) {}
            }
        } catch (e) {}
    }

    async function loadMobileConfig() {
        try {
            const emp = getEmp();
            const res = await fetch(api(`/mobile/config?empresa=${encodeURIComponent(emp)}`));
            if (res.ok) {
                const json = await res.json();
                state.layout = json.layout || [];
            } else {
                state.layout = [];
            }
        } catch (e) {
            state.layout = [];
        }
    }

    async function refreshEjercicios(emp) {
        try {
            const res = await fetch(api(`/mobile/ejercicios?empresa=${encodeURIComponent(emp)}`));
            if (!res.ok) return;
            const arr = await res.json();
            if (!selEjercicio) return;
            const saved = localStorage.getItem('datia-mobile-ejercicio');
            selEjercicio.innerHTML = '';
            // Sort desc to show latest first
            arr.sort((a, b) => b - a).forEach(ej => {
                const opt = document.createElement('option');
                opt.value = String(ej);
                opt.textContent = String(ej);
                if (saved && String(ej) === String(saved)) opt.selected = true;
                selEjercicio.appendChild(opt);
            });
        } catch (e) { }
    }
})();
