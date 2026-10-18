// datia/static/js/dashboard/core.js

// Global Formatters
// Custom formatter to ensure dot as thousands separator and comma as decimal separator
try {
    const dbg = localStorage.getItem('datia-debug') === 'true';
    const silentErr = localStorage.getItem('datia-silent-errors') === 'true';
    if (!dbg && typeof console !== 'undefined') {
        const noop = function () { };
        console.log = noop;
        console.debug = noop;
        console.info = noop;
        console.warn = noop;
        if (silentErr) {
            console.error = noop;
        }
    }
} catch (e) { }

const fmtMoney = {
    format: function (value) {
        if (value === null || value === undefined || isNaN(value)) return '0,00 €';

        // Convert to number and fix to 2 decimals
        const num = parseFloat(value);
        const fixed = num.toFixed(2);

        // Split into integer and decimal parts
        const parts = fixed.split('.');
        const integerPart = parts[0];
        const decimalPart = parts[1];

        // Add thousands separator (dot)
        const withThousands = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');

        // Combine with comma as decimal separator and add € symbol
        return `${withThousands},${decimalPart} €`;
    }
};

const fmtNum = new Intl.NumberFormat('es-ES');
const fmtInt = new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 });
const fmtMoneySimple = {
    format: function (value) {
        if (value === null || value === undefined || isNaN(value)) return '0,00 €';
        const num = parseFloat(value);
        return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(num);
    }
};

(function () {
    if (!window.__snapshotInflight) window.__snapshotInflight = {};
    if (!window.__snapshotCache) window.__snapshotCache = {};
    window.fetchSnapshot = function (kind, empresa, ejercicio, ttlMs) {
        var k = String(kind || 'sales') + ':' + String(empresa || '') + ':' + String(ejercicio || '');
        var ttl = typeof ttlMs === 'number' ? ttlMs : 10000;
        var c = window.__snapshotCache[k];
        if (c && c.ts && (Date.now() - c.ts) < ttl && c.data !== undefined) {
            return Promise.resolve(c.data);
        }
        var f = window.__snapshotInflight[k];
        if (f) return f;
        var apiBase = (typeof API !== 'undefined' && API) ? API : '/api/datia';
        if (empresa === undefined || empresa === null || empresa === '' || ejercicio === undefined || ejercicio === null || ejercicio === '') {
            return Promise.resolve(null);
        }
        var q = '?empresa=' + encodeURIComponent(empresa) + '&ejercicio=' + encodeURIComponent(ejercicio);
        if (String(kind) === 'compras') q += '&kind=compras';
        var url = apiBase + '/widgets/snapshot' + q;
        var p = fetch(url).then(function (r) { return r.json(); }).then(function (j) {
            var d = j && (j.data || j);
            window.__snapshotCache[k] = { ts: Date.now(), data: d };
            return d;
        }).finally(function () {
            delete window.__snapshotInflight[k];
        });
        window.__snapshotInflight[k] = p;
        return p;
    };
})();
function monthShort(n) {
    const lang = (typeof APP_LANG !== 'undefined' && APP_LANG) ? APP_LANG : (document.documentElement.lang || 'es-ES');
    if (n === 0) {
        const base = String(lang || '').toLowerCase().split('-')[0];
        const startMap = { es: 'ini', en: 'start', fr: 'déb', pt: 'ini', it: 'ini', de: 'anf' };
        return startMap[base] || 'ini';
    }
    const d = new Date(2000, n - 1, 1);
    let s = d.toLocaleString(lang, { month: 'short' });
    s = (s || '').toLowerCase().replace(/\.$/, '');
    return s;
}

async function init() {
    if (window.__datia_init_done) return;
    window.__datia_init_done = true;
    try {
        const res = await fetch('/api/system/initial_setup/status?_=' + Date.now());
        if (!res.ok) {
            const overlay = document.getElementById('initial-setup-overlay');
            if (overlay) overlay.style.display = 'flex';
            return;
        }
        const status = await res.json();
        const schema = status && status.schema ? status.schema : null;
        const hasSchemaIssue = schema && schema.ok === false;
        const hasCompanies = !!status.has_companies;
        if (hasSchemaIssue || !hasCompanies) {
            const overlay = document.getElementById('initial-setup-overlay');
            if (overlay) overlay.style.display = 'flex';
            return;
        }
    } catch (e) {
        const overlay = document.getElementById('initial-setup-overlay');
        if (overlay) overlay.style.display = 'flex';
        return;
    }
    await hydrateRuntimeConfig();
    detectDevice();
    window.addEventListener('resize', detectDevice);
    const savedEmp = localStorage.getItem('datia-empresa');
    if (savedEmp && /^\d+$/.test(savedEmp)) {
        currEmpresa = parseInt(savedEmp, 10);
    } else if (savedEmp && !/^\d+$/.test(savedEmp)) {
        localStorage.removeItem('datia-empresa');
    }
    const savedEje = localStorage.getItem('datia-ejercicio');
    if (savedEje && /^\d+$/.test(savedEje)) {
        currEjercicio = parseInt(savedEje, 10);
    }

    updateSystemDate();
    await loadAppName();
    await loadGlobalUIPrefs();
    initTheme(); // Initialize Theme logic
    initSettings(); // Initialize Settings Logic
    loadErpConfig(); // Load ERP Config (Async)
    await loadFilters();

    // Init Favorites & Tabs
    initTabs();
    // Update Personal Tab name in header on initial load
    loadPersonalTabName();
    try { } catch (_) { }

    // Ensure these functions exist (loaded from other modules)
    try {
        if (typeof loadDashboard === 'function') await loadDashboard();
        if (typeof loadSnapshot === 'function') loadSnapshot(); // non-blocking
        if (typeof loadHistory === 'function') loadHistory(); // Load saved queries
        initWidgetSelection();
    } finally {
        // La pestaña favorita se aplica al final para que el arranque no la sustituya
        applyStartupTab();
        if (window.MobileManager && typeof window.MobileManager.enterPhone === 'function') {
            window.MobileManager.enterPhone();
        }
        if (window.location.hash === '#carga-inicial') {
            const openReset = function (left) {
                if (typeof window.requestFactoryReset === 'function') {
                    window.requestFactoryReset();
                    return;
                }
                if (left > 0) setTimeout(function () { openReset(left - 1); }, 400);
            };
            openReset(8);
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
        init();
    });
} else {
    init();
}

// ... existing code ...

// --- Settings Logic ---
function openSettings() {
    if (document.body.classList.contains('is-mobile')) {
        if (typeof showToast === 'function') showToast('Configuración no disponible en móvil');
        return;
    }
    const modal = document.getElementById('settings-modal-overlay');
    if (modal) {
        modal.style.display = 'flex';
        initSettings();
        try {
            const modes = (typeof SETTINGS_MODES !== 'undefined' && SETTINGS_MODES) ? SETTINGS_MODES : { user: true, dev: true, impl: true };
            const btnUser = document.getElementById('btn-tab-user');
            const btnDev = document.getElementById('btn-tab-dev');
            const btnImpl = document.getElementById('btn-tab-impl');
            if (btnUser) btnUser.style.display = modes.user ? '' : 'none';
            if (btnDev) btnDev.style.display = modes.dev ? '' : 'none';
            if (btnImpl) btnImpl.style.display = modes.impl ? '' : 'none';
            let defaultTab = 'user';
            if (modes.impl && btnImpl) defaultTab = 'impl';
            else if (modes.dev && btnDev) defaultTab = 'dev';
            switchSettingsTab(defaultTab);
        } catch (_) { }
    }
}

function closeSettings() {
    const modal = document.getElementById('settings-modal-overlay');
    if (modal) modal.style.display = 'none';
}

// 1. Datia Logo Logic
function selectDatiaLogo(btn, src) {
    // UI Selection
    document.querySelectorAll('.logo-option-btn').forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');

    // Update Header
    const headerLogo = document.getElementById('header-datia-logo');
    if (headerLogo) headerLogo.src = src;

    // Update Main AI Logo (IA Tab)
    const mainAiLogo = document.getElementById('main-ai-logo');
    if (mainAiLogo) mainAiLogo.src = src;

    // Update Datia Tab Logo
    const datiaTabLogo = document.getElementById('datia-tab-logo');
    if (datiaTabLogo) datiaTabLogo.src = src;

    // Update Sync Modal Logo
    const syncLogo = document.getElementById('sync-logo');
    if (syncLogo) syncLogo.src = src;

    // Update Favicon
    const favicon = document.getElementById('dynamic-favicon');
    if (favicon) favicon.href = src;

    // Save Preference
    localStorage.setItem('datia-selected-logo', src);
    try {
        document.cookie = 'datia-selected-logo=' + encodeURIComponent(src) + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) { }
    try {
        const csrf = (typeof getCookie === 'function' ? getCookie('csrftoken') : (window.CSRF_TOKEN || ''));
        fetch('/api/financial/preferences/ui', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ selected_logo: src })
        }).catch(() => { });
    } catch (e) { }
}

// 2. Client Logo Logic
// 2. Client Logo Logic
function toggleClientLogo(checkbox) {
    const empId = currEmpresa || 'default';
    localStorage.setItem(`datia-show-client-logo-${empId}`, checkbox.checked);
    updateLogoVisibility(); // Refresh UI
}

function uploadClientLogo(input) {
    if (input.files && input.files[0]) {
        const file = input.files[0];

        // Check Size (2MB)
        if (file.size > 2 * 1024 * 1024) {
            alert("El archivo es demasiado grande (Max 2MB).");
            return;
        }

        const reader = new FileReader();
        reader.onload = function (e) {
            const base64 = e.target.result;
            const empId = currEmpresa || 'default'; // Keyed by Company
            const key = `datia-client-logo-${empId}`;

            // Save
            localStorage.setItem(key, base64);

            // Auto-enable when uploading
            localStorage.setItem(`datia-show-client-logo-${empId}`, 'true');
            const toggle = document.getElementById('settings-show-client-logo');
            if (toggle) toggle.checked = true;

            // Update UI
            updateLogoVisibility();

            // Update Preview
            const preview = document.getElementById('client-logo-preview');
            const previewContainer = document.getElementById('client-logo-preview-container');
            if (preview && previewContainer) {
                preview.src = base64;
                previewContainer.style.display = 'block';
            }
        }
        reader.readAsDataURL(file);
    }
}

function removeClientLogo() {
    const empId = currEmpresa || 'default';
    const key = `datia-client-logo-${empId}`;
    localStorage.removeItem(key);
    // Also disable toggle? Maybe better to leave user preference but it won't show anything.

    // Hide UI
    updateLogoVisibility();

    const previewContainer = document.getElementById('client-logo-preview-container');
    if (previewContainer) previewContainer.style.display = 'none';

    // Clear input
    document.getElementById('client-logo-upload').value = "";
}

function initWidgetSelection() {
    const selectors = ['.flip-card', '.fin-ratio-item', '.fin-analysis-card', '.mobile-runtime-widget', '.alm-card'];
    const sel = selectors.join(',');
    document.addEventListener('click', function (e) {
        const target = e.target.closest(sel);
        if (!target) return;
        document.querySelectorAll(sel).forEach(n => n.removeAttribute('aria-selected'));
        target.setAttribute('aria-selected', 'true');
    });
}

// Flip Effect Logic
function changeFlipEffect(effect) {
    // Remove existing modes
    document.body.classList.remove('flip-mode-vertical', 'flip-mode-book', 'flip-mode-standard');

    // Add new mode
    if (effect && effect !== 'standard') {
        document.body.classList.add(`flip-mode-${effect}`);
    }

    // Save
    localStorage.setItem('datia-flip-effect', effect);
}

function updateLogoVisibility() {
    const empId = currEmpresa || 'default';
    const hasLogo = localStorage.getItem(`datia-client-logo-${empId}`);
    let showClient = localStorage.getItem(`datia-show-client-logo-${empId}`) === 'true';

    // EXCLUSION: Never show client logo on Datia Landing tabs
    const activeTab = document.querySelector('.tab-panel.active');
    if (activeTab) {
        const id = activeTab.id;
        if (id === 'tab-datia' || id === 'tab-datia-wow' || id === 'tab-datia-2') {
            showClient = false;
        }
    }

    // List of all logo elements to update
    const targets = [
        'header-datia-logo',
        'main-ai-logo',
        'datia-tab-logo',
        'sync-logo'
    ];

    targets.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        // Store default if not already stored
        if (!el.hasAttribute('data-default-src')) {
            el.setAttribute('data-default-src', el.src);
        }

        if (hasLogo && showClient) {
            // OVERRIDE
            el.src = hasLogo;
        } else {
            // RESTORE
            const savedDatiaLogo = localStorage.getItem('datia-selected-logo');
            if (savedDatiaLogo) {
                el.src = savedDatiaLogo;
            } else {
                const def = el.getAttribute('data-default-src');
                if (def) el.src = def;
            }
        }
    });
}

function renderClientLogo(src) {
    // Legacy support or direct call - redirected to updateLogoVisibility
    // But we need to update preview locally if called
    const preview = document.getElementById('client-logo-preview');
    const previewContainer = document.getElementById('client-logo-preview-container');
    if (preview && previewContainer && src) {
        preview.src = src;
        previewContainer.style.display = 'block';
    }
    updateLogoVisibility();
}


let GLOBAL_CONFIG_CACHE = null;

function loadEtlAutoSettings() {
    const toggle = document.getElementById('settings-etl-auto-enabled');
    const input = document.getElementById('settings-etl-interval-hours');
    if (!toggle && !input) return;

    fetch('/api/config/global')
        .then(res => res.ok ? res.json() : Promise.reject(res.status))
        .then(cfg => {
            GLOBAL_CONFIG_CACHE = cfg || {};
            const enabled = GLOBAL_CONFIG_CACHE.etl_auto_incremental_enabled !== false;
            const intervalRaw = GLOBAL_CONFIG_CACHE.etl_auto_incremental_interval_hours;
            const interval = parseInt(intervalRaw !== undefined ? intervalRaw : '4', 10);
            if (toggle) toggle.checked = enabled;
            if (input) input.value = isNaN(interval) ? 4 : interval;
        })
        .catch(err => console.error('Failed to load global config', err));
}

function saveGlobalConfigPatch(patch) {
    GLOBAL_CONFIG_CACHE = GLOBAL_CONFIG_CACHE || {};
    Object.keys(patch).forEach(k => {
        GLOBAL_CONFIG_CACHE[k] = patch[k];
    });
    fetch('/api/config/global', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : ''
        },
        body: JSON.stringify({ settings: GLOBAL_CONFIG_CACHE })
    }).catch(err => console.error('Failed to save global config', err));
}

window.toggleEtlAutoEnabled = function (checkbox) {
    const enabled = !!checkbox.checked;
    saveGlobalConfigPatch({ etl_auto_incremental_enabled: enabled });
    if (typeof showToast === 'function') {
        showToast(enabled ? 'Incremental automático activado' : 'Incremental automático desactivado');
    }
};

window.changeEtlIntervalHours = function (input) {
    let v = parseInt(input.value || '4', 10);
    if (isNaN(v)) v = 4;
    if (v < 1) v = 1;
    if (v > 24) v = 24;
    input.value = String(v);
    saveGlobalConfigPatch({ etl_auto_incremental_interval_hours: v });
    if (typeof showToast === 'function') {
        showToast('Incremental cada ' + v + 'h');
    }
};

function initSettings() {
    // 0. Restore Flip Effect
    const savedFlip = localStorage.getItem('datia-flip-effect') || 'standard';
    changeFlipEffect(savedFlip);
    const flipSelect = document.getElementById('settings-flip-effect');
    if (flipSelect) flipSelect.value = savedFlip;

    // 1. Restore Datia Logo
    const savedLogo = localStorage.getItem('datia-selected-logo');
    if (savedLogo) {
        const headerLogo = document.getElementById('header-datia-logo');
        if (headerLogo) headerLogo.src = savedLogo;

        const mainAiLogo = document.getElementById('main-ai-logo');
        if (mainAiLogo) mainAiLogo.src = savedLogo;

        const datiaTabLogo = document.getElementById('datia-tab-logo');
        if (datiaTabLogo) datiaTabLogo.src = savedLogo;

        const syncLogo = document.getElementById('sync-logo');
        if (syncLogo) syncLogo.src = savedLogo;

        const favicon = document.getElementById('dynamic-favicon');
        if (favicon) favicon.href = savedLogo;

        // Mark grid item as selected (need to check src attribute match)
        document.querySelectorAll('.logo-option-btn').forEach(btn => {
            const img = btn.querySelector('img');
            // Check if src ends with the saved filename or matches
            if (img && (img.getAttribute('src') === savedLogo || img.src === savedLogo || savedLogo.includes(img.getAttribute('src')))) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
    }

    // 2. Restore Client Logo & Toggle
    // Use currEmpresa from global scope
    const empId = currEmpresa || 'default';
    const savedClient = localStorage.getItem(`datia-client-logo-${empId}`);
    const showClient = localStorage.getItem(`datia-show-client-logo-${empId}`) === 'true';

    // Restore Toggle
    const toggle = document.getElementById('settings-show-client-logo');
    if (toggle) toggle.checked = showClient;

    if (savedClient) {
        // Just update preview, visibility handled below
        renderClientLogo(savedClient);
    } else {
        // Reset if no logo for this company
        const previewContainer = document.getElementById('client-logo-preview-container');
        if (previewContainer) previewContainer.style.display = 'none';
    }

    // Apply Visibility Rules
    updateLogoVisibility();

    // 3. Load AI Models (Dropdowns)
    loadAiModels();
    loadPersonalTabName();

    // 4. Estado del carrusel (User Mode)
    try {
        const chk = document.getElementById('settings-status-carousel-enabled');
        const inp = document.getElementById('settings-status-carousel-interval');
        const enabled = (localStorage.getItem('datia-status-carousel-enabled') || 'true') !== 'false';
        const interval = parseInt(localStorage.getItem('datia-status-carousel-interval') || '7', 10);
        if (chk) chk.checked = enabled;
        if (inp) inp.value = interval;
    } catch (_) { }
    try {
        const appInput = document.getElementById('settings-app-name');
        if (appInput) {
            const v = (typeof window.__APP_NAME !== 'undefined' ? window.__APP_NAME : (localStorage.getItem('datia-app-name') || 'Datia'));
            appInput.value = v;
        }
    } catch (_) { }
    try {
        const voiceToggle = document.getElementById('settings-voice-notify');
        if (voiceToggle) {
            const saved = localStorage.getItem('datia-voice-notify');
            voiceToggle.checked = saved === 'true';
        }
    } catch (_) { }
    try {
        loadEtlAutoSettings();
    } catch (_) { }

    // Inicializar Sidebar de Actualidad
    try {
        initActualidadSidebar();
    } catch (_) { }
}

// ==========================================
// ACTUALIDAD SIDEBAR LOGIC
// ==========================================
function initActualidadSidebar() {
    const sidebar = document.getElementById('actualidad-sidebar');
    if (!sidebar) return;

    // Restaurar estado colapsado
    const isCollapsed = localStorage.getItem('datia-sidebar-collapsed') === 'true';
    if (isCollapsed) {
        sidebar.classList.add('collapsed');
    }

    // Restaurar grupos expandidos
    const groups = sidebar.querySelectorAll('.sidebar-group');
    groups.forEach(g => {
        const id = g.getAttribute('data-group');
        const state = localStorage.getItem(`datia-sidebar-group-${id}`);
        // Por defecto, si no hay estado, dejamos como está en el HTML (expandido)
        if (state === 'false') {
            g.classList.remove('expanded');
        } else if (state === 'true') {
            g.classList.add('expanded');
        }
    });

    // Escuchar cambios de subpestaña para actualizar la clase 'active' en el menú
    document.addEventListener('subTabChanged', function(e) {
        const tabId = e.detail;
        updateSidebarActiveState(tabId);
    });
}

function toggleActualidadSidebar() {
    const sidebar = document.getElementById('actualidad-sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    localStorage.setItem('datia-sidebar-collapsed', isCollapsed ? 'true' : 'false');
    
    // Disparar resize de ECharts al terminar la transición
    setTimeout(() => {
        if (window.dispatchEvent) {
            window.dispatchEvent(new Event('resize'));
        }
    }, 300);
}

function toggleSidebarGroup(headerEl) {
    const sidebar = document.getElementById('actualidad-sidebar');
    // Si está colapsado, el click en el header podría expandir el menú entero, o no hacer nada
    if (sidebar && sidebar.classList.contains('collapsed')) {
        toggleActualidadSidebar(); // Expande el menú completo
        return;
    }

    const group = headerEl.closest('.sidebar-group');
    if (!group) return;
    group.classList.toggle('expanded');
    
    const id = group.getAttribute('data-group');
    if (id) {
        localStorage.setItem(`datia-sidebar-group-${id}`, group.classList.contains('expanded') ? 'true' : 'false');
    }
}

function updateSidebarActiveState(tabId) {
    const sidebar = document.getElementById('actualidad-sidebar');
    if (!sidebar) return;
    
    // Quitar active a todos
    sidebar.querySelectorAll('.sidebar-item').forEach(btn => btn.classList.remove('active'));
    
    // Poner active al seleccionado
    const activeBtn = sidebar.querySelector(`.sidebar-item[data-tab="${tabId}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        // Asegurarse de que el grupo padre esté expandido
        const group = activeBtn.closest('.sidebar-group');
        if (group && !group.classList.contains('expanded') && !sidebar.classList.contains('collapsed')) {
            group.classList.add('expanded');
            const id = group.getAttribute('data-group');
            if (id) localStorage.setItem(`datia-sidebar-group-${id}`, 'true');
        }
    }
}



// Ajustes de Carrusel
function toggleStatusCarouselEnabled(checkbox) {
    try {
        const val = !!checkbox.checked;
        localStorage.setItem('datia-status-carousel-enabled', val ? 'true' : 'false');
        if (typeof showToast === 'function') showToast(val ? 'Carrusel activado' : 'Carrusel desactivado');
    } catch (e) {
        console.error('toggleStatusCarouselEnabled error', e);
    }
}
function changeStatusCarouselInterval(input) {
    try {
        let v = parseInt(input.value || '7', 10);
        if (isNaN(v)) v = 7;
        v = Math.max(3, Math.min(15, v));
        input.value = String(v);
        localStorage.setItem('datia-status-carousel-interval', String(v));
        if (typeof showToast === 'function') showToast(`Intervalo ajustado a ${v}s`);
    } catch (e) {
        console.error('changeStatusCarouselInterval error', e);
    }
}

function toggleVoiceNotify(input) {
    try {
        const val = !!input.checked;
        localStorage.setItem('datia-voice-notify', val ? 'true' : 'false');
        if (typeof showToast === 'function') showToast(val ? 'Voz activada' : 'Voz desactivada');
    } catch (e) { }
}

// Compartición de informes (Histórico)
let _currentShareId = null;
function openShareModal(id, queryText) {
    _currentShareId = id;
    const modal = document.getElementById('share-modal');
    if (!modal) return;
    const label = document.getElementById('share-target-label');
    if (label) label.textContent = (queryText || '').slice(0, 80);
    const pub = document.getElementById('share-public-toggle');
    const users = document.getElementById('share-usernames-input');
    if (pub) pub.checked = false;
    if (users) users.value = '';
    modal.style.display = 'flex';
}
function closeShareModal() {
    const modal = document.getElementById('share-modal');
    if (modal) modal.style.display = 'none';
    _currentShareId = null;
}
async function submitShare() {
    const pub = document.getElementById('share-public-toggle');
    const users = document.getElementById('share-usernames-input');
    const isPublic = pub ? !!pub.checked : false;
    const raw = users ? (users.value || '') : '';
    const list = raw.split(',').map(s => s.trim()).filter(Boolean);
    if (!_currentShareId) {
        closeShareModal();
        return;
    }
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;
        const res = await fetch(`${API}/ai/history/${_currentShareId}/share`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ is_public: isPublic, users: list })
        });
        const data = await res.json();
        if (data.status === 'shared') {
            if (typeof showToast === 'function') showToast('Informe compartido');
            closeShareModal();
            if (typeof loadHistoricoView === 'function') loadHistoricoView();
        } else {
            if (typeof showToast === 'function') showToast('Error al compartir', true);
        }
    } catch (e) {
        console.error('submitShare error', e);
        if (typeof showToast === 'function') showToast('Error de conexión', true);
    }
}

async function loadAiModels() {
    const selChat = document.getElementById('setting-ai-model');
    const selReport = document.getElementById('setting-report-model');
    const selSem = document.getElementById('setting-semantic-model');
    const selSql = document.getElementById('setting-sql-training-model');

    const selects = [selChat, selReport, selSem, selSql].filter(Boolean);
    if (selects.length === 0) return;

    try {
        const res = await fetch('/api/datia/ai/models');
        const data = await res.json();

        let models = data.models || [];
        if (models.length === 0) {
            // Fallback: Models actually installed on this system
            models = [
                'qwen2.5:3b-instruct-q4_k_m',
                'qwen2.5:7b',
                'qwen2.5:14b-instruct-q4_k_m',
                'qwen2.5:14b',
                'qwen3:30b',
                'qwen3:30b-instruct-q4_k_m',
                'qwen3:72b',
                'qwen3:72b-instruct-q4_k_m',
                'llama3.1:8b',
                'mistral:latest'
            ];
        }

        try {
            const saved = [
                localStorage.getItem('datia-ai-model'),
                localStorage.getItem('datia-report-model'),
                localStorage.getItem('datia-semantic-model'),
                localStorage.getItem('datia-sql-training-model')
            ].filter(v => v && v.length);
            saved.forEach(v => { if (!models.includes(v)) models.push(v); });
        } catch (_) { }

        const opts = models.map(m => `<option value="${m}">${m}</option>`).join('');

        if (selChat) selChat.innerHTML = opts;
        if (selReport) selReport.innerHTML = opts;
        if (selSem) selSem.innerHTML = opts;
        if (selSql) selSql.innerHTML = opts;

        // Restore Selection
        const savedAi = localStorage.getItem('datia-ai-model');
        if (selChat && savedAi && models.includes(savedAi)) selChat.value = savedAi;

        const savedReport = localStorage.getItem('datia-report-model');
        if (selReport && savedReport && models.includes(savedReport)) selReport.value = savedReport;

        const savedSem = localStorage.getItem('datia-semantic-model');
        if (selSem && savedSem && models.includes(savedSem)) selSem.value = savedSem;

        const savedSql = localStorage.getItem('datia-sql-training-model');
        if (selSql && savedSql && models.includes(savedSql)) selSql.value = savedSql;

    } catch (e) {
        console.error("Error loading models", e);
        if (selChat) selChat.innerHTML = '<option value="">Error cargando modelos</option>';
        if (selReport) selReport.innerHTML = '<option value="">Error cargando modelos</option>';
        if (selSem) selSem.innerHTML = '<option value="">Error cargando modelos</option>';
        if (selSql) selSql.innerHTML = '<option value="">Error cargando modelos</option>';
    }
}

// [NEW] ERP Config Logic
async function loadErpConfig() {
    try {
        const res = await fetch(`${API}/config/erp`);
        const data = await res.json();

        const labelContainer = document.getElementById('erp-label-container');
        const headerLabel = document.getElementById('header-erp-name');
        const input = document.getElementById('settings-erp-name');

        if (data.name) {
            if (headerLabel) headerLabel.innerText = data.name;
            if (labelContainer) labelContainer.style.display = 'flex'; // Use flex for alignment
            if (input) input.value = data.name;
        } else {
            if (labelContainer) labelContainer.style.display = 'none';
        }
    } catch (e) {
        console.error("Error loading ERP config", e);
    }
}

window.saveErpConfig = async () => {
    const input = document.getElementById('settings-erp-name');
    if (!input) return;

    const name = input.value;
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;

        const res = await fetch(`${API}/config/erp`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ name: name })
        });
        const data = await res.json();

        if (data.status === 'saved') {
            showToast("Integración ERP actualizada ✅");
            loadErpConfig(); // Refresh UI
        } else {
            showToast("Error guardando ERP ❌: " + (data.error || "Desconocido"));
        }
    } catch (e) {
        showToast("Error de conexión ❌");
    }
};

async function loadPersonalTabName() {
    try {
        const res = await fetch('/api/financial/preferences/layout');
        const data = await res.json();
        const v = (data && typeof data === 'object' && data.layout && typeof data.layout === 'object') ? data.layout : data;
        const name = (v && v.custom_tab && v.custom_tab.name) ? v.custom_tab.name : 'Pestaña Personal';
        const input = document.getElementById('settings-personal-tab-name');
        if (input) input.value = name;
        const nav = document.getElementById('nav-tab-personal');
        if (nav) nav.textContent = name;
        const titleEl = document.getElementById('personal-tab-title');
        if (titleEl) titleEl.textContent = name;
    } catch (e) { }
}

window.savePersonalTabName = async () => {
    const input = document.getElementById('settings-personal-tab-name');
    if (!input) return;
    const name = (input.value || '').trim() || 'Pestaña Personal';
    try {
        const getRes = await fetch('/api/financial/preferences/layout');
        const current = await getRes.json();
        const base = (current && typeof current === 'object' && current.layout && typeof current.layout === 'object') ? current.layout : (current || {});
        const widgets = base && base.custom_tab && Array.isArray(base.custom_tab.widgets) ? base.custom_tab.widgets : [];
        const merged = Object.assign({}, base, { custom_tab: { name, widgets } });
        const headers = { 'Content-Type': 'application/json' };
        let token = null;
        try { if (typeof CSRF_TOKEN !== 'undefined' && CSRF_TOKEN) token = CSRF_TOKEN; } catch (_) { }
        if (!token) {
            try {
                const nameC = 'csrftoken';
                const value = `; ${document.cookie}`;
                const parts = value.split(`; ${nameC}=`);
                if (parts.length === 2) token = decodeURIComponent(parts.pop().split(';').shift());
            } catch (_) { }
        }
        if (token) headers['X-CSRFToken'] = token;
        const postRes = await fetch('/api/financial/preferences/layout', {
            method: 'POST',
            headers,
            body: JSON.stringify({ layout: merged })
        });
        await postRes.json();
        const nav = document.getElementById('nav-tab-personal');
        if (nav) nav.textContent = name;
        const titleEl = document.getElementById('personal-tab-title');
        if (titleEl) titleEl.textContent = name;
        // Sincronizar localStorage para que al recargar no recupere el nombre anterior
        try {
            const cached = localStorage.getItem('datia-personal-tab-layout');
            const layout = cached ? JSON.parse(cached) : {};
            layout.name = name;
            localStorage.setItem('datia-personal-tab-layout', JSON.stringify(layout));
        } catch (_) { }
        // Sincronizar con PersonalTab si está activo
        try {
            if (window.PersonalTab && window.PersonalTab.state) {
                window.PersonalTab.state.name = name;
            }
        } catch (_) { }
        if (typeof showToast === 'function') showToast('Nombre de pestaña actualizado ✅');
    } catch (e) {
        if (typeof showToast === 'function') showToast('Error al guardar ❌', true);
    }
};

// (Nombre de Pestaña Personal) Deshabilitado en este nivel de jerarquía

// Global Save Function
window.saveAiModels = () => {
    const aiModel = document.getElementById('setting-ai-model').value;
    const reportModelEl = document.getElementById('setting-report-model');
    const reportModel = reportModelEl ? reportModelEl.value : '';
    const semanticModel = document.getElementById('setting-semantic-model').value;
    const sqlModel = document.getElementById('setting-sql-training-model').value;

    if (aiModel) localStorage.setItem('datia-ai-model', aiModel);
    else localStorage.removeItem('datia-ai-model');

    if (reportModel) localStorage.setItem('datia-report-model', reportModel);
    else localStorage.removeItem('datia-report-model');

    if (semanticModel) localStorage.setItem('datia-semantic-model', semanticModel);
    else localStorage.removeItem('datia-semantic-model');

    if (sqlModel) localStorage.setItem('datia-sql-training-model', sqlModel);
    else localStorage.removeItem('datia-sql-training-model');

    if (typeof showToast === 'function') showToast("Modelos AI actualizados 🤖");
};

/* --- Delete Confirmation Logic (Fix for Missing Modal) --- */
let _currentDeleteId = null;

function showDeleteConfirmation(id, query) {
    _currentDeleteId = id;
    const modal = document.getElementById('delete-confirm-modal');
    if (!modal) {
        console.error("Delete modal not found");
        return;
    }

    const textEl = document.getElementById('delete-confirm-text');
    if (textEl) {
        textEl.innerText = `¿Eliminar "${query}"?`;
    }

    modal.style.display = 'flex';

    // Bind Confirm Button
    const btn = document.getElementById('btn-confirm-delete');
    if (btn) {
        // Clear previous event listeners by cloning
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);

        newBtn.onclick = async function () {
            // UI Feedback
            newBtn.disabled = true;
            newBtn.innerHTML = 'Eliminando...';

            try {
                const emp = encodeURIComponent(currEmpresa);
                const url = `${API}/ai/history/${_currentDeleteId}?empresa=${emp}`;
                const res = await fetch(url, { method: 'DELETE' });
                const json = await res.json();

                if (json.status === 'deleted') {
                    if (typeof showToast === 'function') showToast('🗑️ Eliminado correctamente');
                    if (typeof loadHistoricoView === 'function') loadHistoricoView();
                } else {
                    if (typeof showToast === 'function') showToast('❌ Error al eliminar', true);
                }
            } catch (e) {
                console.error(e);
                if (typeof showToast === 'function') showToast('❌ Error de conexión', true);
            } finally {
                closeDeleteConfirmation();
                newBtn.disabled = false;
                newBtn.innerHTML = 'Eliminar';
            }
        };
    }
}

function closeDeleteConfirmation() {
    const modal = document.getElementById('delete-confirm-modal');
    if (modal) modal.style.display = 'none';
    _currentDeleteId = null;
}

async function hydrateRuntimeConfig() {
    try {
        const res = await fetch('/api/config/runtime?_=' + Date.now());
        if (!res.ok) return;
        const cfg = await res.json();
        if (!cfg || cfg.error) return;
        const write = function (key, value) {
            if (value) localStorage.setItem(key, value);
        };
        write('datia-ai-model', cfg.llm_chat);
        write('datia-report-model', cfg.llm_report);
        write('datia-semantic-model', cfg.llm_semantic);
        write('datia-sql-training-model', cfg.llm_sql_training);
        write('datia-ollama-host', cfg.ollama_host);
        if (cfg.ai_provider) localStorage.setItem('datia-ai-provider', cfg.ai_provider);
        if (cfg.gemini_model) localStorage.setItem('datia-gemini-model', cfg.gemini_model);
        if (cfg.perf_preset) localStorage.setItem('datia-perf-preset', cfg.perf_preset);
        localStorage.setItem('datia-show-sql', cfg.show_sql ? 'true' : 'false');
        localStorage.setItem('datia-training-mode', cfg.training_mode ? 'true' : 'false');
        localStorage.setItem('datia-auto-load', cfg.auto_load_actualidad === false ? 'false' : 'true');
        localStorage.setItem('datia-fast-bulk', cfg.fast_bulk ? 'true' : 'false');
        localStorage.setItem('datia-mobile-mode', cfg.mobile_specialized ? 'true' : 'false');
        if (cfg.app_name && window.DatiaBranding && typeof window.DatiaBranding.setAppName === 'function') {
            window.DatiaBranding.setAppName(cfg.app_name);
        }
        if (window.MobileManager && typeof window.MobileManager.setMode === 'function') {
            window.MobileManager.setMode(!!cfg.mobile_specialized);
        }
    } catch (e) { }
}

function readMainFavorite() {
    const legacyFav = localStorage.getItem('datia-fav-tab');
    let favTab = localStorage.getItem('datia-fav-main-tab');
    if (!favTab && legacyFav) {
        favTab = legacyFav;
        localStorage.setItem('datia-fav-main-tab', legacyFav);
        localStorage.removeItem('datia-fav-tab');
    }
    if (favTab && (favTab.startsWith('subtab-') || favTab.startsWith('sub-'))) {
        localStorage.removeItem('datia-fav-main-tab');
        favTab = null;
    }
    return favTab ? String(favTab).trim() : null;
}

function applyStartupTab() {
    const autoLoad = localStorage.getItem('datia-auto-load') !== 'false';
    const favTab = readMainFavorite();
    const favBtn = favTab ? document.querySelector('.header-tabs .tab-btn[data-tab-id="' + favTab + '"]') : null;
    const favPanel = favTab ? document.getElementById(favTab) : null;

    if (favTab && (favBtn || favPanel)) {
        switchTab(favTab);
    } else if (!favTab && autoLoad && document.getElementById('tab-actualidad')) {
        switchTab('tab-actualidad');
    } else if (!favTab && !document.querySelector('.header-tabs .tab-btn.active')) {
        switchTab('tab-ia');
    }

    updateFavoriteUI(favTab);
}

function initTabs() {
    applyStartupTab();
}

// [NEW] Auto Load Toggle
function toggleAutoLoad(checkbox) {
    localStorage.setItem('datia-auto-load', checkbox.checked);
    showToast(checkbox.checked ? "Auto-Carga Activada 🚀" : "Auto-Carga Desactivada (Usará Favorito)");
}

function setFavoriteTab(tabId) {
    const currentFav = localStorage.getItem('datia-fav-main-tab');

    if (currentFav === tabId) {
        // Toggle OFF if already favorite
        localStorage.removeItem('datia-fav-main-tab');
        showToast("Favorito eliminado");
    } else {
        // Set NEW favorite
        localStorage.setItem('datia-fav-main-tab', tabId);
        showToast("Pestaña fijada como inicial 📌");
    }
    updateFavoriteUI(localStorage.getItem('datia-fav-main-tab'));
}

// [FIX] Clean block for updateFavoriteUI and showToast
function updateFavoriteUI(favTabId) {
    document.querySelectorAll('.header-tabs .tab-btn').forEach(btn => {
        const tabId = btn.getAttribute('data-tab-id');
        if (!tabId) return;

        btn.classList.toggle('is-favorite', favTabId === tabId);

        const legacySpan = btn.querySelector('.fav-pin');
        if (legacySpan) legacySpan.remove();
    });
}

function showToast(msg) {
    let div = document.getElementById('datia-toast');
    if (div) div.remove();

    div = document.createElement('div');
    div.id = 'datia-toast';
    div.innerText = msg;
    div.style.cssText = `
        position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
        background: #3f3f46; color: white; padding: 8px 16px; 
        border-radius: 20px; font-size: 0.85rem; z-index: 20001;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1);
        animation: fadeInOut 2.5s ease forwards;
    `;
    document.body.appendChild(div);
    setTimeout(() => { if (div) div.remove(); }, 2600);
}

// Add CSS animation dynamically
const styleTag = document.createElement('style');
styleTag.innerHTML = `@keyframes fadeInOut { 0% {opacity:0; transform:translate(-50%, 10px);} 10% {opacity:1; transform:translate(-50%, 0);} 90% {opacity:1; transform:translate(-50%, 0);} 100% {opacity:0; transform:translate(-50%, -10px);} }`;
document.head.appendChild(styleTag);


function updateSystemDate() {
    const now = new Date();
    // Use dynamic language from HTML tag or fallback to es
    // [FIX] Prefer explicit global APP_LANG (injected by template) over DOM lang
    const lang = (typeof APP_LANG !== 'undefined' && APP_LANG) ? APP_LANG : (document.documentElement.lang || 'es');

    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const dateStr = now.toLocaleDateString(lang, options);
    // Capitalize first letter
    const finalStr = dateStr.charAt(0).toUpperCase() + dateStr.slice(1);

    const dateEl = document.getElementById('sys-date');
    if (dateEl) dateEl.innerText = finalStr;
}

function switchTab(tabId) {
    try {
        console.log('[switchTab] Attempting switch to:', tabId);

        // [FIX] Mobile Mode Cleanup (ISS-052) - Wrapped in try-catch to prevent desktop crash
        try {
            if (tabId !== 'tab-actualidad') {
                document.body.classList.remove('mobile-app-mode');
            } else {
                // Let MobileManager decide based on config and screen size
                if (typeof MobileManager !== 'undefined' && typeof MobileManager.applyRuntimeView === 'function') {
                    MobileManager.applyRuntimeView();
                }
            }
        } catch (err) {
            console.warn("[switchTab] Mobile cleanup warning:", err);
        }

        // 1. Force hide ALL panels first
        document.querySelectorAll('.tab-panel').forEach(p => {
            p.classList.remove('active');
            // Force reset style to ensure clean state
            p.style.display = 'none';
            p.style.opacity = '';
            p.style.visibility = '';
        });

        // 2. Find and activate target
        const target = document.getElementById(tabId);

        if (target) {
            // Force layout reflow
            void target.offsetWidth;

            target.classList.add('active');

            // Explicitly force display block to override any hidden state
            target.style.display = 'block';
            target.style.opacity = '1';
            target.style.visibility = 'visible';

            console.log('[switchTab] Target activated:', tabId);
        } else {
            console.error('[switchTab] CRITICAL ERROR: Target ID not found:', tabId);
            // Emergency fallback: Search by partial ID or class
            const fallback = document.querySelector(`[id*="${tabId.replace('tab-', '')}"]`);
            if (fallback && fallback.classList.contains('tab-panel')) {
                console.log('[switchTab] Fallback target found:', fallback.id);
                fallback.classList.add('active');
                fallback.style.display = 'block';
            }
        }

        // 3. Update Buttons State
        document.querySelectorAll('.header-tabs .tab-btn').forEach(btn => {
            const dataId = btn.getAttribute('data-tab-id');
            const onclickAttr = btn.getAttribute('onclick');
            const match = onclickAttr && onclickAttr.match(/switchTab\('([^']+)'\)/);
            const btnTabId = dataId || (match ? match[1] : null);

            if (btnTabId === tabId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // 4. Update Logo Visibility
        if (typeof updateLogoVisibility === 'function') {
            updateLogoVisibility();
        }

        // 5. Dispatch Event for other scripts
        
        if (tabId === 'tab-actualidad') {
            const savedSubTab = localStorage.getItem('datia-fav-act-tab');
            const key = '__datia_act_fav_restored';
            const already = !!(window && window[key]);
            if (!already) {
                if (window) window[key] = true;
                if (savedSubTab && typeof switchSubTab === 'function') {
                    setTimeout(() => switchSubTab(savedSubTab), 10);
                } else if (typeof switchSubTab === 'function') {
                    setTimeout(() => switchSubTab('sub-ventas'), 10);
                }
            }
        }

        const event = new CustomEvent('datia:tab-change', { detail: { tabId: tabId } });
        document.dispatchEvent(event);
        if (tabId === 'tab-personal' && typeof window.PersonalTab !== 'undefined' && typeof window.PersonalTab.render === 'function') {
            window.PersonalTab.render();
        }

    } catch (e) {
        console.error("[switchTab] FATAL ERROR:", e);
        alert("Error de navegación: " + e.message);
    }
}

function switchSubTab(subTabId) {
    // Ocultar todas las sub-pestañas
    document.querySelectorAll('.sub-tab').forEach(tab => {
        tab.style.display = 'none';
        tab.classList.remove('active');
    });

    // Desactivar botones de sub-navegación
    document.querySelectorAll('.sub-nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Mostrar sub-pestaña objetivo
    const target = document.getElementById(subTabId);
    if (target) {
        target.style.display = 'flex';
        target.classList.add('active');
    }

    // Activar botón correspondiente
    const activeBtn = Array.from(document.querySelectorAll('.sub-nav-btn')).find(btn =>
        btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(subTabId)
    );
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
    
    // Activar botón del nuevo sidebar lateral
    document.querySelectorAll('.sidebar-item').forEach(btn => btn.classList.remove('active'));
    const activeSidebarBtn = document.querySelector(`.sidebar-item[data-tab="${subTabId}"]`);
    if (activeSidebarBtn) {
        activeSidebarBtn.classList.add('active');
    }
    
    // Disparar evento para que otras pestañas sepan que ha cambiado
    document.dispatchEvent(new CustomEvent('subTabChanged', { detail: subTabId }));

    if ((subTabId === 'sub-financiera' || subTabId === 'sub-balances' || subTabId === 'sub-informes') && typeof loadActualidadFinanciera === 'function') {
        setTimeout(loadActualidadFinanciera, 50);
    }
    if (subTabId === 'sub-ratios' && typeof loadActualidadRatios === 'function') {
        setTimeout(loadActualidadRatios, 50);
    }
    if (subTabId === 'sub-financiera' || subTabId === 'sub-balances' || subTabId === 'sub-informes') {
        setTimeout(() => {
            try {
                const csrf = (typeof getCookie === 'function' ? getCookie('csrftoken') : '');
                fetch('/api/ai/context/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ empresa: currEmpresa, ejercicio: currEjercicio, kind: 'financiera' })
                }).then(r => r.json()).then(() => {
                    try { if (window.VOA && typeof window.VOA.notify === 'function') window.VOA.notify('AI_CONTEXT_READY', { kind: 'financiera', empresa: currEmpresa, ejercicio: currEjercicio }); } catch (_) { }
                }).catch(() => { });
            } catch (_) { }
        }, 50);
    }
    if (subTabId === 'sub-anatomia' && typeof loadUtilityAnatomy === 'function') {
        const anatomyYearEl = document.getElementById('fin-anatomy-year');
        if (anatomyYearEl && currEjercicio) {
            anatomyYearEl.value = String(currEjercicio);
        }
        setTimeout(loadUtilityAnatomy, 50);
    }

    // [FIX] Cargar Dashboard de Compras
    if (subTabId === 'sub-compras') {
        if (typeof loadComprasDashboard === 'function') {
            loadComprasDashboard();
            // Resize charts after delay
            setTimeout(() => {
                const charts = ['chart-activity-compras', 'chart-top-proveedores', 'chart-top-articulos-compra'];
                if (window.echarts) {
                    charts.forEach(id => {
                        const dom = document.getElementById(id);
                        if (dom) {
                            const inst = echarts.getInstanceByDom(dom);
                            if (inst) inst.resize();
                        }
                    });
                }
            }, 300);
        }
    }

    // [FIX] Cargar Editor Móvil (ISS-050)
    if (subTabId === 'sub-movil') {
        if (window.MobileManager && typeof window.MobileManager.renderBuilder === 'function') {
            // Force visibility check and delayed render
            setTimeout(() => {
                const container = document.getElementById('tab-actualidad-movil');
                if (container) container.style.display = 'block';
                window.MobileManager.renderBuilder();
                if (typeof window.MobileManager.refreshNgrokUrl === 'function') {
                    window.MobileManager.refreshNgrokUrl();
                }
                console.log("Mobile Editor Rendered via switchSubTab");
            }, 300);
        }
    }

    if (subTabId === 'sub-ventas') {
        if (typeof loadDashboard === 'function') {
            setTimeout(() => { loadDashboard(); }, 50);
        }
        setTimeout(() => {
            try {
                const csrf = (typeof getCookie === 'function' ? getCookie('csrftoken') : '');
                fetch('/api/ai/context/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
                    body: JSON.stringify({ empresa: currEmpresa, ejercicio: currEjercicio, kind: 'ventas' })
                }).then(r => r.json()).then(() => {
                    try { if (window.VOA && typeof window.VOA.notify === 'function') window.VOA.notify('AI_CONTEXT_READY', { kind: 'ventas', empresa: currEmpresa, ejercicio: currEjercicio }); } catch (_) { }
                }).catch(() => { });
            } catch (_) { }
        }, 50);
        try {
            if (typeof loadUninvoicedLinesSalesCard === 'function') {
                setTimeout(loadUninvoicedLinesSalesCard, 60);
            }
        } catch (_) { }
    }

    if (subTabId === 'sub-clientes') {
        if (typeof loadClientesDashboard === 'function') {
            setTimeout(() => { loadClientesDashboard(); }, 50);
        }
    }

    if (subTabId === 'sub-proveedores') {
        if (typeof loadProveedoresDashboard === 'function') {
            setTimeout(() => { loadProveedoresDashboard(); }, 50);
        }
    }

    if (subTabId === 'sub-articulos') {
        if (typeof loadArticulosDashboard === 'function') {
            setTimeout(() => { loadArticulosDashboard(); }, 50);
        }
    }

    // [NEW] Cargar Presupuestos solo si hay empresa seleccionada
    if (subTabId === 'sub-presupuestos-dashboard') {
        if (typeof loadBudgetDashboard === 'function') {
            setTimeout(loadBudgetDashboard, 40);
        }
    }

    if (subTabId === 'sub-presupuestos') {
        if (typeof loadPresupuestos === 'function') {
            setTimeout(() => { loadPresupuestos(); }, 40);
        }
    }

    if (subTabId === 'sub-almacen') {
        if (typeof loadAlmacenDashboard === 'function') {
            setTimeout(() => {
                loadAlmacenDashboard();
                setTimeout(() => {
                    if (window.echarts) {
                        ['chart-alm-distribucion', 'chart-alm-evolucion', 'chart-alm-almacen', 'chart-alm-abc'].forEach(id => {
                            const dom = document.getElementById(id);
                            if (dom) {
                                const inst = echarts.getInstanceByDom(dom);
                                if (inst) inst.resize();
                            }
                        });
                    }
                }, 300);
            }, 50);
        }
    }

    if (subTabId === 'sub-tesoreria') {
        if (typeof loadTesoreriaData === 'function') {
            setTimeout(loadTesoreriaData, 50);
        }
    }

    if (subTabId === 'sub-prediccion') {
        if (typeof initPrediccion === 'function') {
            setTimeout(() => { initPrediccion(); }, 50);
        }
    }

    if (subTabId === 'sub-anatomia') {
        if (typeof loadUtilityAnatomy === 'function') {
            setTimeout(() => { try { loadUtilityAnatomy(); } catch (e) { } }, 50);
        }
    }
    try {
        const ev = new CustomEvent('datia:subtab-change', { detail: { subTabId } });
        document.dispatchEvent(ev);
    } catch (_) { }
}

async function loadFilters() {
    const selEmp = document.getElementById('sel-empresa');
    const selEje = document.getElementById('sel-ejercicio');

    try {
        const res = await fetch(`${API}/filters`);
        if (!res.ok) throw new Error(`Status ${res.status}`);

        const data = await res.json();

        if (data && data.error && data.error.code === 'MISSING_CORE_TABLE') {
            if (typeof showInitialSetupOverlay === 'function') {
                showInitialSetupOverlay();
            }
        }

        if (data.empresas && Array.isArray(data.empresas) && data.empresas.length > 0) {
            selEmp.innerHTML = data.empresas.map(e => {
                const code = e.code || e;
                const name = e.name || `Empresa ${code}`;
                return `<option value="${code}" ${code == currEmpresa ? 'selected' : ''}>${name}</option>`;
            }).join('');
        } else {
            selEmp.innerHTML = '<option disabled>Sin Empresas</option>';
        }

        if (data.ejercicios && Array.isArray(data.ejercicios) && data.ejercicios.length > 0) {
            var list = data.ejercicios.slice();
            var cn = parseInt(currEjercicio || '0', 10);
            if (!isNaN(cn) && cn >= 2008 && cn <= 2026 && list.indexOf(cn) === -1) {
                list.push(cn);
                list.sort(function (a, b) { return b - a; });
            }
            selEje.innerHTML = list.map(e => `<option value="${e}" ${e == currEjercicio ? 'selected' : ''}>${e}</option>`).join('');
        } else {
            selEje.innerHTML = '<option disabled>Sin Ejercicios</option>';
        }
        const anatomyYearEl = document.getElementById('fin-anatomy-year');
        if (anatomyYearEl && currEjercicio) {
            anatomyYearEl.value = String(currEjercicio);
        }
        if (selEmp && selEmp.value) {
            currEmpresa = parseInt(selEmp.value, 10);
        }
        if (selEje && selEje.value && /^\d+$/.test(selEje.value)) {
            currEjercicio = parseInt(selEje.value, 10);
        }
        if (typeof ensureYearDefaults === 'function') {
            try { ensureYearDefaults(); } catch (_) { }
        }
        const dashPanel = document.getElementById('sub-presupuestos-dashboard');
        const dashActive = dashPanel && dashPanel.classList.contains('active');
        const presupPanel = document.getElementById('sub-presupuestos');
        const presupActive = presupPanel && presupPanel.classList.contains('active');
        if (dashActive && typeof loadBudgetDashboard === 'function' && currEmpresa && !isNaN(currEmpresa)) {
            setTimeout(() => { try { loadBudgetDashboard(); } catch (_) { } }, 50);
        } else if (presupActive && typeof loadPresupuestos === 'function' && currEmpresa && !isNaN(currEmpresa)) {
            setTimeout(() => { try { loadPresupuestos(); } catch (_) { } }, 50);
        }
        try {
            const selectedOpt = selEmp && selEmp.options[selEmp.selectedIndex];
            const empName = selectedOpt ? selectedOpt.textContent : (selEmp && selEmp.value ? `Empresa ${selEmp.value}` : '');
            if (empName) {
                window.__EMPRESA_NAME = empName;
                localStorage.setItem('datia-empresa-name', empName);
                try {
                    const ev2 = new CustomEvent('datia:empresa-change', { detail: { code: currEmpresa, name: empName } });
                    document.dispatchEvent(ev2);
                } catch (_) { }
                applyEmpresaName(empName);
            }
        } catch (_) { }
        const panelAnat = document.getElementById('sub-anatomia');
        if (panelAnat && (panelAnat.classList.contains('active') || panelAnat.style.display !== 'none')) {
            if (typeof loadUtilityAnatomy === 'function') {
                setTimeout(() => { try { loadUtilityAnatomy(); } catch (e) { } }, 25);
            }
        }

    } catch (e) {
        console.error("Filter error", e);
        selEmp.innerHTML = `<option disabled>Error: ${e.message}</option>`;
        selEje.innerHTML = `<option disabled>Error</option>`;

        // Show global error in AI box for visibility
        const resp = document.getElementById('ai-chat-container');
        if (resp) {
            const errDiv = document.createElement('div');
            errDiv.innerText = `System Error: ${e.message}`;
            resp.appendChild(errDiv);
        }
    }
}

window.applyFilters = () => {
    const emp = parseInt(document.getElementById('sel-empresa').value, 10);
    const eje = parseInt(document.getElementById('sel-ejercicio').value, 10);

    // Save to LocalStorage for persistence
    localStorage.setItem('datia-empresa', String(emp));
    localStorage.setItem('datia-ejercicio', String(eje));
    try {
        const selEmpEl = document.getElementById('sel-empresa');
        const opt = selEmpEl && selEmpEl.options[selEmpEl.selectedIndex];
        const nm = opt ? opt.textContent : `Empresa ${emp}`;
        localStorage.setItem('datia-empresa-name', nm);
        window.__EMPRESA_NAME = nm;
        try {
            const ev2 = new CustomEvent('datia:empresa-change', { detail: { code: emp, name: nm } });
            document.dispatchEvent(ev2);
        } catch (_) { }
        applyEmpresaName(nm);
    } catch (_) { }

    window.location.href = `?empresa=${emp}&ejercicio=${eje}`;
};

// Sync Logic
async function openSyncModal() {
    document.getElementById('sync-modal').style.display = 'flex';
    const bar = document.getElementById('sync-progress');
    const statusEl = document.getElementById('sync-status-text');

    bar.style.width = '0%';
    statusEl.innerText = "Iniciando conexión...";

    try {
        const res = await fetch(`${API}/sync/trigger?empresa=${currEmpresa}&ejercicio=${currEjercicio}`, {
            method: 'POST'
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;

            // Split by double newline which splits event data blocks
            const parts = buffer.split('\n\n');
            // The last part might be incomplete, keep it in buffer
            buffer = parts.pop();

            for (let part of parts) {
                const lines = part.split('\n');
                for (let line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const jsonStr = line.replace('data: ', '').trim();
                            if (!jsonStr) continue;
                            const data = JSON.parse(jsonStr);

                            // Update UI
                            if (data.percent) bar.style.width = data.percent + '%';
                            if (data.message) statusEl.innerText = `${data.step}: ${data.message}`;

                            if (data.step === 'Done' || data.percent === 100) {
                                setTimeout(() => {
                                    closeModal();
                                    location.reload();
                                }, 1000);
                            }
                            if (data.step === 'Error') {
                                statusEl.innerText = "Error Critico: " + data.message;
                                statusEl.style.color = 'red';
                            }

                        } catch (e) { console.warn("Stream parse error", e); }
                    }
                }
            }
        }

    } catch (e) {
        statusEl.innerText = "Error de Conexión: " + e;
    }
}

function closeModal() {
    document.getElementById('sync-modal').style.display = 'none';
}


// Theme Logic
window.setAccentColor = function (color) {
    if (!color) return;

    // 1. Apply to DOM (Base Accent)
    document.documentElement.style.setProperty('--accent', color);

    // 2. Calculate Derived Colors
    let r = 0, g = 0, b = 0;
    if (color.length === 4) {
        // #abc -> #aabbcc
        r = parseInt(color[1] + color[1], 16);
        g = parseInt(color[2] + color[2], 16);
        b = parseInt(color[3] + color[3], 16);
    } else if (color.length === 7) {
        // #aabbcc
        r = parseInt(color.slice(1, 3), 16);
        g = parseInt(color.slice(3, 5), 16);
        b = parseInt(color.slice(5, 7), 16);
    }

    // Glow: 50% opacity
    document.documentElement.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.5)`);

    // Border: 30% opacity (Subtle and elegant)
    document.documentElement.style.setProperty('--accent-border', `rgba(${r}, ${g}, ${b}, 0.3)`);

    // Subtle Text: 80% opacity (For non-active but colored elements, if needed)
    document.documentElement.style.setProperty('--accent-text-subtle', `rgba(${r}, ${g}, ${b}, 0.8)`);

    // 3. Save
    localStorage.setItem('datia-accent-color', color);
    try {
        document.cookie = 'datia-accent-color=' + encodeURIComponent(color) + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) { }
    try {
        const csrf = (typeof getCookie === 'function' ? getCookie('csrftoken') : (window.CSRF_TOKEN || ''));
        fetch('/api/financial/preferences/ui', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ accent_color: color })
        }).catch(() => { });
    } catch (e) { }

    // 4. Update UI
    const picker = document.getElementById('custom-color-picker');
    if (picker) picker.value = color;

    // Reset Legacy
    document.body.classList.remove('theme-green');
    const toggle = document.getElementById('theme-toggle-checkbox');
    if (toggle) toggle.checked = false;
};

window.pickAccentFromScreen = async function () {
    try {
        if ('EyeDropper' in window) {
            const d = new EyeDropper();
            const res = await d.open();
            if (res && res.sRGBHex) setAccentColor(res.sRGBHex);
        } else {
            const input = document.getElementById('custom-color-picker');
            if (input) input.click();
            if (typeof showToast === 'function') showToast('Tu navegador no soporta cuenta gotas');
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('Selección cancelada');
    }
};

function initTheme() {
    // 1. Restore Custom Accent
    const savedAccent = localStorage.getItem('datia-accent-color');
    if (savedAccent) {
        setAccentColor(savedAccent);
    } else {
        // Fallback: Legacy Logic
        const toggleCheckbox = document.getElementById('theme-toggle-checkbox');
        const savedTheme = localStorage.getItem('datia-theme');
        const isGreen = savedTheme === 'green';

        if (isGreen) {
            document.body.classList.add('theme-green');
            if (toggleCheckbox) toggleCheckbox.checked = true;
        }

        if (toggleCheckbox) {
            toggleCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    document.body.classList.add('theme-green');
                    localStorage.setItem('datia-theme', 'green');
                    // Clear custom
                    localStorage.removeItem('datia-accent-color');
                    document.documentElement.style.removeProperty('--accent');
                    document.documentElement.style.removeProperty('--accent-glow');
                    document.documentElement.style.removeProperty('--accent-border');
                    document.documentElement.style.removeProperty('--accent-text-subtle');
                } else {
                    document.body.classList.remove('theme-green');
                    localStorage.setItem('datia-theme', 'violet');
                }
            });
        }
    }
}

// Settings Tab Logic
window.switchSettingsTab = function (tabName) {
    try {
        const modes = (typeof SETTINGS_MODES !== 'undefined' && SETTINGS_MODES) ? SETTINGS_MODES : { user: true, dev: true, impl: true };
        if (tabName === 'dev' && !modes.dev) { if (typeof showToast === 'function') showToast('Modo no permitido'); return; }
        if (tabName === 'impl' && !modes.impl) { if (typeof showToast === 'function') showToast('Modo no permitido'); return; }
    } catch (_) { }
    // 1. Update Buttons
    document.querySelectorAll('.settings-tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.id === `btn-tab-${tabName}`) {
            btn.classList.add('active');
        }
    });

    // 2. Update Panels
    document.querySelectorAll('.settings-tab-content').forEach(panel => {
        panel.classList.remove('active');
        panel.style.display = 'none'; // Ensure hidden
    });

    const target = document.getElementById(`settings-tab-${tabName}`);
    if (target) {
        target.classList.add('active');
        target.style.display = 'block'; // Ensure visible
    }
};

document.addEventListener('DOMContentLoaded', init);

// --- Favorite Tooltip Logic ---
window.toggleFavTooltip = function (enabled) {
    if (enabled) {
        document.body.classList.add('show-fav-tooltip');
        localStorage.setItem('datia-fav-tooltip', 'true');
    } else {
        document.body.classList.remove('show-fav-tooltip');
        localStorage.setItem('datia-fav-tooltip', 'false');
    }
}

function detectDevice() {
    const isSmall = window.innerWidth <= 1024;
    const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    const isUA = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    const mobile = isSmall || (isTouch && isSmall) || isUA;
    document.body.classList.toggle('is-mobile', mobile);
    document.body.classList.toggle('is-desktop', !mobile);
}

if (!window.getCookie) {
    window.getCookie = function (name) {
        var cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    };
}

// Estado Carrusel: Configuración
window.toggleStatusCarousel = function (checkbox) {
    const enabled = checkbox && checkbox.checked;
    localStorage.setItem('datia-status-carousel-enabled', enabled ? 'true' : 'false');
};
window.updateStatusCarouselInterval = function (input) {
    let val = parseInt(input && input.value ? String(input.value) : '7', 10);
    if (isNaN(val)) val = 7;
    val = Math.max(3, Math.min(15, val));
    input.value = val;
    localStorage.setItem('datia-status-carousel-interval', String(val));
};
function initFavTooltip() {
    const saved = localStorage.getItem('datia-fav-tooltip');
    // Default to true if not set, or check 'true' string
    const enabled = saved === null || saved === 'true';

    toggleFavTooltip(enabled);

    // Sync Checkbox (if it exists on this page load)
    // Note: Settings modal might be loaded later or is hidden
    const chk = document.getElementById('chk-vis-fav-tooltip');
    if (chk) chk.checked = enabled;
}

// Call init on load
document.addEventListener('DOMContentLoaded', () => {
    initFavTooltip();
    initFavoriteMainTab();
});

// --- Main Favorite Tab Logic (Header) ---
function initFavoriteMainTab() {
    document.querySelectorAll('.header-tabs .tab-btn').forEach(btn => {
        const tabId = btn.getAttribute('data-tab-id');
        if (!tabId) return;

        btn.ondblclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            setFavoriteTab(tabId);
        };
    });
    updateFavoriteUI(readMainFavorite());
}

function toggleFavoriteMainTab(tabId) {
    setFavoriteTab(tabId);
}

// REMOVED: updateAllMainStars function not needed anymore

const APP_NAME_DEFAULT = 'Datia';
function validateAppName(name) {
    const raw = String(name == null ? '' : name).trim();
    // Permitir vacío (sin nombre)
    if (raw === '') return { ok: true, name: '' };
    const norm = raw.replace(/\s+/g, ' ');
    if (norm.length < 2 || norm.length > 32) return { ok: false, msg: 'Longitud inválida (2–32)' };
    if (!/^[A-Za-zÁÉÍÓÚÜáéíóúüÑñ0-9 _-]{2,32}$/.test(norm)) return { ok: false, msg: 'Caracteres no permitidos' };
    return { ok: true, name: norm };
}
function applyAppName(name) {
    try {
        window.__APP_NAME = (name == null ? '' : name);
        const label = document.getElementById('app-name-label');
        if (label) label.textContent = window.__APP_NAME;
        document.title = `${window.__APP_NAME} Analytics V2`;
        const t1 = document.getElementById('nav-tab-datia');
        if (t1) t1.textContent = window.__APP_NAME;
        const t2 = document.getElementById('nav-tab-datia-wow');
        if (t2) t2.textContent = `${window.__APP_NAME} 1`;
        const t3 = document.getElementById('nav-tab-datia-2');
        if (t3) t3.textContent = `${window.__APP_NAME} 2`;
        const hDatia = document.getElementById('app-title-datia');
        if (hDatia) hDatia.textContent = window.__APP_NAME;
        const hWow = document.getElementById('app-title-datia-wow');
        if (hWow) hWow.textContent = window.__APP_NAME;
        const hD3 = document.getElementById('app-title-datia-3');
        if (hD3) hD3.textContent = window.__APP_NAME;
        const brandD2 = document.getElementById('app-brand-datia-2');
        if (brandD2) brandD2.textContent = window.__APP_NAME;
    } catch (_) { }
}
async function loadAppName() {
    try {
        const res = await fetch('/api/config/global');
        const data = await res.json();
        // Si app_name existe en la respuesta (incluso vacío) lo usamos, sin fallback a APP_NAME_DEFAULT
        let name = (data && data.app_name !== undefined) ? data.app_name
            : (localStorage.getItem('datia-app-name') || '');
        applyAppName(name);
        const input = document.getElementById('settings-app-name');
        if (input) input.value = name;
    } catch (e) {
        let name = localStorage.getItem('datia-app-name') || '';
        applyAppName(name);
        const input = document.getElementById('settings-app-name');
        if (input) input.value = name;
    }
}
async function saveAppName() {
    const input = document.getElementById('settings-app-name');
    if (!input) return;
    const r = validateAppName(input.value);
    if (!r.ok) { if (typeof showToast === 'function') showToast(r.msg, true); return; }
    const name = r.name; // Puede ser '' (vacío permitido)
    try {
        const currentRes = await fetch('/api/config/global');
        const cfg = await currentRes.json();
        cfg.app_name = name;
        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;
        await fetch('/api/config/global', { method: 'POST', headers, body: JSON.stringify({ settings: cfg }) });
        if (name) localStorage.setItem('datia-app-name', name);
        else localStorage.removeItem('datia-app-name');
        applyAppName(name);
        if (typeof showToast === 'function') showToast('Nombre guardado');
    } catch (e) {
        if (name) localStorage.setItem('datia-app-name', name);
        else localStorage.removeItem('datia-app-name');
        applyAppName(name);
        if (typeof showToast === 'function') showToast('Guardado local');
    }
}
async function resetAppName() {
    const name = APP_NAME_DEFAULT;
    try {
        const currentRes = await fetch('/api/config/global');
        const cfg = await currentRes.json();
        cfg.app_name = name;
        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;
        await fetch('/api/config/global', { method: 'POST', headers, body: JSON.stringify({ settings: cfg }) });
    } catch (e) { }
    localStorage.removeItem('datia-app-name');
    applyAppName(name);
    const input = document.getElementById('settings-app-name');
    if (input) input.value = name;
    if (typeof showToast === 'function') showToast('Nombre restablecido');
}

function applyGlobalLogo(src) {
    try {
        const headerLogo = document.getElementById('header-datia-logo');
        if (headerLogo && src) headerLogo.src = src;
        const mainAiLogo = document.getElementById('main-ai-logo');
        if (mainAiLogo && src) mainAiLogo.src = src;
        const datiaTabLogo = document.getElementById('datia-tab-logo');
        if (datiaTabLogo && src) datiaTabLogo.src = src;
        const syncLogo = document.getElementById('sync-logo');
        if (syncLogo && src) syncLogo.src = src;
        const favicon = document.getElementById('dynamic-favicon');
        if (favicon && src) favicon.href = src;
    } catch (_) { }
}
async function loadGlobalUIPrefs() {
    try {
        const res = await fetch('/api/config/global');
        const cfg = await res.json();
        const logo = cfg && cfg.selected_logo;
        const accent = cfg && cfg.accent_color;
        const inpLogo = document.getElementById('settings-global-logo-url');
        const inpAccent = document.getElementById('settings-global-accent-color');
        if (inpLogo && typeof logo === 'string') inpLogo.value = logo;
        if (inpAccent && typeof accent === 'string') inpAccent.value = accent;
        const hasLocalLogo = !!localStorage.getItem('datia-selected-logo');
        const hasLocalAccent = !!localStorage.getItem('datia-accent-color');
        if (!hasLocalLogo && logo) {
            localStorage.setItem('datia-selected-logo', logo);
            applyGlobalLogo(logo);
        }
        if (!hasLocalAccent && accent) {
            setAccentColor(accent);
        }
    } catch (e) { }
}
async function saveGlobalUIPrefs() {
    const inpLogo = document.getElementById('settings-global-logo-url');
    const inpAccent = document.getElementById('settings-global-accent-color');
    const logo = inpLogo && inpLogo.value ? String(inpLogo.value).trim() : '';
    const accent = inpAccent && inpAccent.value ? String(inpAccent.value).trim() : '';
    try {
        const currentRes = await fetch('/api/config/global');
        const cfg = await currentRes.json();
        if (logo) cfg.selected_logo = logo; else delete cfg.selected_logo;
        if (accent) cfg.accent_color = accent; else delete cfg.accent_color;
        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;
        await fetch('/api/config/global', { method: 'POST', headers, body: JSON.stringify({ settings: cfg }) });
        if (logo) {
            localStorage.setItem('datia-selected-logo', logo);
            applyGlobalLogo(logo);
        }
        if (accent) {
            setAccentColor(accent);
        }
        if (typeof showToast === 'function') showToast('Identidad visual guardada');
    } catch (e) {
        if (logo) {
            localStorage.setItem('datia-selected-logo', logo);
            applyGlobalLogo(logo);
        }
        if (accent) {
            setAccentColor(accent);
        }
        if (typeof showToast === 'function') showToast('Guardado local');
    }
}

function getCurrentEmpresaName() {
    try {
        const selEmp = document.getElementById('sel-empresa');
        if (selEmp && selEmp.selectedIndex >= 0) {
            const opt = selEmp.options[selEmp.selectedIndex];
            const nm = opt ? opt.textContent : '';
            if (nm) return nm;
        }
    } catch (_) { }
    const cached = localStorage.getItem('datia-empresa-name');
    if (cached) return cached;
    if (currEmpresa) return `Empresa ${currEmpresa}`;
    return '';
}

function applyEmpresaName(name) {
    const nm = String(name || getCurrentEmpresaName() || '').trim();
    try {
        if (nm) {
            const el1 = document.getElementById('company-name-datia');
            if (el1) el1.textContent = nm;
            const el2 = document.getElementById('company-name-datia-wow');
            if (el2) el2.textContent = nm;
            const el3 = document.getElementById('company-name-datia-2');
            if (el3) el3.textContent = nm;
            const el4 = document.getElementById('company-name-datia-3');
            if (el4) el4.textContent = nm;
            window.__EMPRESA_NAME = nm;
        }
    } catch (_) { }
}
