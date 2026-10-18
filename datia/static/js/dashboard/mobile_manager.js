/**
 * Mobile View Manager for Actualidad Pattern
 * Handles Drag & Drop configuration and Runtime rendering
 */

const MobileManager = {
    config: {
        mode: 'standard', // 'standard' | 'custom'
        layout: [] // List of widget IDs
    },
    phoneSection: 'Ventas',
    _phoneReady: false,
    defaultLayout: {
        Ventas: ['widget-sales-1d', 'widget-sales-30d', 'widget-margin-1d', 'widget-kpi-neto', 'widget-kpi-margen', 'widget-chart-activity', 'widget-chart-products'],
        Compras: ['widget-compras-1d', 'widget-compras-30d', 'widget-kpi-compras-neto', 'widget-chart-top-proveedores'],
        Financiera: ['widget-fin-ingresos', 'widget-fin-gastos', 'widget-fin-resultado', 'widget-fin-liquidez', 'widget-fin-margen']
    },
    _isPhone: function () {
        return document.documentElement.classList.contains('is-phone') || window.innerWidth <= 900;
    },
    widgetsForSection: function () {
        const section = this.phoneSection || 'Ventas';
        const saved = (this.config.layout || []).filter(id => {
            const widget = this.widgets.find(item => item.id === id);
            return widget && widget.tab === section;
        });
        if (saved.length) return saved;
        return this.defaultLayout[section] || [];
    },
    _getEmpresaId: function () {
        let e = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
        const sel = document.getElementById('sel-empresa');
        if (!e && sel && sel.value) e = sel.value;
        return e || '';
    },
    _getLang: function () {
        const l = typeof window.APP_LANG !== 'undefined' && window.APP_LANG ? window.APP_LANG : 'es-ES';
        return l;
    },
    _api: function (path) {
        if (!path.startsWith('/')) path = '/' + path;
        return '/api' + path;
    },
    _finKey: function (emp, ej) {
        return `datia_fin_snapshot_${emp || ''}_${ej || ''}`;
    },
    _getFinCache: function (emp, ej) {
        try {
            const raw = localStorage.getItem(this._finKey(emp, ej));
            if (!raw) return null;
            const obj = JSON.parse(raw);
            const ttl = 300000;
            if (!obj || !obj.ts || !obj.data) return null;
            if ((Date.now() - obj.ts) > ttl) return null;
            return obj.data;
        } catch (e) {
            return null;
        }
    },
    _setFinCache: function (emp, ej, data) {
        try {
            localStorage.setItem(this._finKey(emp, ej), JSON.stringify({ ts: Date.now(), data }));
        } catch (e) { }
    },

    // Available widgets catalog
    widgets: [
        // --- VENTAS ---
        { id: 'widget-sales-1d', type: 'sales', title: 'Ventas (1 Día)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-sales-7d', type: 'sales', title: 'Ventas (7 Días)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-sales-30d', type: 'sales', title: 'Ventas (30 Días)', group: 'Ventas', tab: 'Ventas' },

        { id: 'widget-ticket-1d', type: 'ticket', title: 'Ticket (1 Día)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-ticket-7d', type: 'ticket', title: 'Ticket (7 Días)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-ticket-30d', type: 'ticket', title: 'Ticket (30 Días)', group: 'Ventas', tab: 'Ventas' },

        { id: 'widget-margin-1d', type: 'margin', title: 'Margen (1 Día)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-margin-7d', type: 'margin', title: 'Margen (7 Días)', group: 'Ventas', tab: 'Ventas' },
        { id: 'widget-margin-30d', type: 'margin', title: 'Margen (30 Días)', group: 'Ventas', tab: 'Ventas' },

        { id: 'widget-kpi-neto', type: 'kpi', title: 'Total Ventas (Anual)', group: 'KPI Anual', tab: 'Ventas' },
        { id: 'widget-kpi-coste', type: 'kpi', title: 'Total Costes (Anual)', group: 'KPI Anual', tab: 'Ventas' },
        { id: 'widget-kpi-margen', type: 'kpi', title: 'Margen Global (Anual)', group: 'KPI Anual', tab: 'Ventas' },
        { id: 'widget-kpi-ticket', type: 'kpi', title: 'Ticket Medio (Anual)', group: 'KPI Anual', tab: 'Ventas' },

        // --- COMPRAS ---
        { id: 'widget-compras-1d', type: 'compras', title: 'Compras (1 Día)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-compras-7d', type: 'compras', title: 'Compras (7 Días)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-compras-30d', type: 'compras', title: 'Compras (30 Días)', group: 'Compras', tab: 'Compras' },

        { id: 'widget-ticket-compra-1d', type: 'ticket-compra', title: 'Ticket Compra (1 Día)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-ticket-compra-7d', type: 'ticket-compra', title: 'Ticket Compra (7 Días)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-ticket-compra-30d', type: 'ticket-compra', title: 'Ticket Compra (30 Días)', group: 'Compras', tab: 'Compras' },

        { id: 'widget-ops-compra-1d', type: 'ops-compra', title: 'Operaciones (1 Día)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-ops-compra-7d', type: 'ops-compra', title: 'Operaciones (7 Días)', group: 'Compras', tab: 'Compras' },
        { id: 'widget-ops-compra-30d', type: 'ops-compra', title: 'Operaciones (30 Días)', group: 'Compras', tab: 'Compras' },

        { id: 'widget-kpi-compras-neto', type: 'kpi', title: 'Total Compras (Anual)', group: 'KPI Anual', tab: 'Compras' },
        { id: 'widget-val-kpi-ticket-compra', type: 'kpi', title: 'Ticket Medio Compra (Anual)', group: 'KPI Anual', tab: 'Compras' },
        { id: 'widget-val-kpi-ops-compra', type: 'kpi', title: 'Total Operaciones (Anual)', group: 'KPI Anual', tab: 'Compras' },
        { id: 'widget-val-kpi-proveedores', type: 'kpi', title: 'Proveedores Activos', group: 'KPI Anual', tab: 'Compras' },

        // --- FINANCIERA (Enabled) ---
        { id: 'widget-fin-ingresos', type: 'financial', title: 'Ingresos Totales (Fin)', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-gastos', type: 'financial', title: 'Gastos Totales (Fin)', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-resultado', type: 'financial', title: 'EBITDA (Fin)', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-liquidez', type: 'financial', title: 'Ratio Liquidez', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-margen', type: 'financial', title: 'Margen %', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-solvencia', type: 'financial', title: 'Solvencia', group: 'Financiera', tab: 'Financiera' },
        { id: 'widget-fin-endeudamiento', type: 'financial', title: 'Endeudamiento', group: 'Financiera', tab: 'Financiera' },

        // --- GRÁFICOS (Placeholders) ---
        { id: 'widget-chart-activity', type: 'chart', title: 'Gráfico: Evolución Ventas', group: 'Gráficos', tab: 'Ventas' },
        { id: 'widget-chart-clients', type: 'chart', title: 'Gráfico: Top Clientes', group: 'Gráficos', tab: 'Ventas' },
        { id: 'widget-chart-products', type: 'chart', title: 'Gráfico: Top Artículos', group: 'Gráficos', tab: 'Ventas' },
        { id: 'widget-chart-map', type: 'chart', title: 'Gráfico: Top Zonas', group: 'Gráficos', tab: 'Ventas' },

        { id: 'widget-chart-activity-compras', type: 'chart', title: 'Gráfico: Evolución Compras', group: 'Gráficos', tab: 'Compras' },
        { id: 'widget-chart-top-proveedores', type: 'chart', title: 'Gráfico: Top Proveedores', group: 'Gráficos', tab: 'Compras' },
        { id: 'widget-chart-top-articulos-compra', type: 'chart', title: 'Gráfico: Top Artículos Compra', group: 'Gráficos', tab: 'Compras' },

        // { id: 'widget-fin-chart-activity', type: 'chart', title: 'Gráfico: Evolución Financiera', group: 'Gráficos', tab: 'Financiera' }
    ],

    init: async function () {
        console.log("MobileManager Initializing...");
        await this.loadConfig();
        this.setupDragAndDrop();
        this.setupExternalDraggables();
        this.applyRuntimeView(); // Check if we need to switch view

        // [NEW] Responsive Listener
        window.addEventListener('resize', () => this.applyRuntimeView());
    },


    _migrateConfig: function (conf) {
        if (!conf || !conf.layout) return conf;

        let dirty = false;
        const migrations = {
            'widget-fin-neto': 'widget-kpi-neto',
            'widget-fin-coste': 'widget-kpi-coste',
            'widget-fin-margin': 'widget-kpi-margen'
        };

        conf.layout = conf.layout.map(id => {
            if (migrations[id]) {
                dirty = true;
                return migrations[id];
            }
            return id;
        });

        if (dirty) {
            console.log("Migrated legacy widget IDs");
            this.saveConfig(); // Persist changes if we are modifying the active config
        }
        return conf;
    },

    loadConfig: async function () {
        try {
            // 1. Try LocalStorage first (Immediate Feedback)
            const local = localStorage.getItem('datia_mobile_config');
            if (local) {
                try {
                    let parsed = JSON.parse(local);
                    this.config = this._migrateConfig(parsed); // [FIX] Apply migration
                    console.log("Loaded mobile config from LocalStorage:", this.config);
                    this.updateUIControls();
                } catch (e) {
                    console.error("Error parsing local config", e);
                }
            }

            // 2. Fetch from Backend (Persistence)
            const empRaw = this._getEmpresaId();
            if (!empRaw) return;
            const emp = encodeURIComponent(empRaw);

            // Construct correct URL: /api/mobile/config
            const finalUrl = this._api(`/mobile/config?empresa=${emp}`);
            console.log("Fetching mobile config from:", finalUrl);

            try {
                const remoteRes = await fetch(finalUrl);

                if (remoteRes.ok) {
                    const remote = await remoteRes.json();
                    console.log("Loaded mobile config from Backend:", remote);

                    // Strategy: Remote wins if it exists, to ensure cross-device sync
                    this.config = this._migrateConfig(remote); // [FIX] Apply migration

                    // Update local storage to match remote
                    localStorage.setItem('datia_mobile_config', JSON.stringify(this.config));

                    this.updateUIControls();
                } else {
                    console.warn("Failed to fetch mobile config from backend. Status:", remoteRes.status);
                }
            } catch (fetchErr) {
                console.warn("Backend fetch failed (offline?)", fetchErr);
            }
        } catch (e) {
            console.error("Failed to load mobile config", e);
        }
    },

    saveConfig: async function () {
        try {
            // 1. Save to LocalStorage (Optimistic)
            localStorage.setItem('datia_mobile_config', JSON.stringify(this.config));

            // 2. Save to Backend
            const empRaw = this._getEmpresaId();
            if (!empRaw) {
                this.showToast("Selecciona una empresa para guardar la configuración móvil");
                return;
            }
            const emp = encodeURIComponent(empRaw);
            const finalUrl = this._api(`/mobile/config?empresa=${emp}`);

            const res = await fetch(finalUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify(this.config)
            });

            if (res.ok) {
                console.log("Mobile config saved to backend");
                this.showToast("Configuración móvil guardada");
            } else {
                console.warn("Backend save failed");
            }
        } catch (e) {
            console.error("Failed to save mobile config", e);
        }
    },

    updateUIControls: function () {
        // Update Implementer Mode Switch
        const switchEl = document.getElementById('settings-mobile-mode');
        if (switchEl) {
            switchEl.checked = this.config.mode === 'custom';
        }

        // Update Tab Visibility (if in mobile view)
        this.applyRuntimeView();

        // Update Nav Button Visibility (ISS-051)
        const btnMovil = document.getElementById('btn-sub-movil');
        if (btnMovil) {
            // If we are using Modal now, we might hide the sub-tab button or keep it as shortcut
            // Since user complained "Pestaña Movil no existe", we show it if mode is custom
            // Since user complained "Pestaña Movil no existe", we show it if mode is custom
            // [FIX] Always show button (User Request 17/01/2026)
            btnMovil.style.display = 'inline-block'; // (this.config.mode === 'custom') ? 'inline-block' : 'none';
        }
    },

    toggleMode: function (checkbox) {
        this.config.mode = checkbox.checked ? 'custom' : 'standard';
        this.saveConfig();
        this.updateUIControls();
        if (checkbox.checked) {
            fetch(this._api('/system/mobile_server/start'), {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            }).then(r => r.json()).then(() => {
                this.showToast('Servidor móvil iniciado');
                setTimeout(() => this.checkMobileServer(), 1000);
            }).catch(() => { });
        } else {
            fetch(this._api('/system/mobile_server/stop'), {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            }).then(() => {
                this.showToast('Servidor móvil detenido');
            }).catch(() => { });
        }
    },

    checkMobileServer: function () {
        fetch(this._api('/system/mobile_server/status'))
            .then(r => r.json())
            .then(s => {
                if (s && s.running) this.showToast('Móvil activo en 8001');
                else this.showToast('Móvil no responde');
            })
            .catch(() => { });
    },

    // --- BUILDER LOGIC ---

    openEditor: function () {
        // ISS-050: Open Modal Logic
        const modal = document.getElementById('mobile-editor-modal');

        // Strategy 1: If Modal exists (Dashboard V1/V2 mixed mode)
        if (modal) {
            modal.style.display = 'flex';
            setTimeout(() => this.renderBuilder(), 200);
            return;
        }

        // Strategy 2: Tab Mode (Dashboard V2)
        // Ensure the sub-tab is activated
        if (typeof switchSubTab === 'function') {
            switchSubTab('sub-movil');

            // [FIX] Force visibility check and delayed render
            // The container might be hidden by animation or display:none initially
            setTimeout(() => {
                const container = document.getElementById('tab-actualidad-movil');
                if (container) container.style.display = 'block';

                this.renderBuilder();
                this.refreshNgrokUrl();
                console.log("Mobile Editor Rendered via Tab Switch");
            }, 300); // Increased timeout to 300ms
        } else {
            console.error("switchSubTab function not found");
        }
    },

    closeEditor: function () {
        // Just switch back to a default tab, e.g., Sales
        if (typeof switchSubTab === 'function') {
            switchSubTab('sub-ventas');
        }
    },

    renderBuilder: function () {
        const sourceContainer = document.getElementById('mobile-builder-source');
        const targetContainer = document.getElementById('mobile-builder-target');

        if (!sourceContainer || !targetContainer) return;

        // Render Source (Available Widgets) - TREE VIEW
        sourceContainer.innerHTML = '';

        // Group widgets by Tab
        const grouped = this.widgets.reduce((acc, w) => {
            const tab = w.tab || 'Otros';
            if (!acc[tab]) acc[tab] = [];
            acc[tab].push(w);
            return acc;
        }, {});

        // Create Tabs/Accordion
        Object.keys(grouped).forEach((tabName, index) => {
            // Category Header
            const header = document.createElement('div');
            header.className = 'mb-category-header';
            const selectedCount = grouped[tabName].filter(w => this.config.layout.includes(w.id)).length;
            const countBadge = selectedCount > 0 ? `<span class="mb-count">${selectedCount}</span>` : '';

            header.innerHTML = `
                <span>${tabName}</span>
                <div style="display:flex; align-items:center; gap:10px;">
                    ${countBadge}
                    <span class="mb-chevron">▼</span>
                </div>
            `;

            // Container for items
            const content = document.createElement('div');
            content.className = 'mb-category-content';

            // Toggle Logic
            header.onclick = () => {
                const isHidden = content.style.display === 'none';
                content.style.display = isHidden ? 'block' : 'none';
                header.querySelector('.mb-chevron').innerText = isHidden ? '▲' : '▼';
            };

            // Auto-expand removed as per user request (Project Context 17/01/2026)
            /*
            if (index === 0) {
                content.style.display = 'block';
                header.querySelector('.mb-chevron').innerText = '▲';
            }
            */

            grouped[tabName].forEach(w => {
                const el = this.createWidgetElement(w);
                content.appendChild(el);
            });

            sourceContainer.appendChild(header);
            sourceContainer.appendChild(content);
        });

        // Render Target (Selected Layout)
        targetContainer.innerHTML = '';
        // [NEW] Ensure Financial Data is loaded (ISS-Fix)
        const dFin = window.cachedFinancialData;
        if (!dFin && this.config.layout.some(id => id.startsWith('widget-fin-'))) {
            const emp = currEmpresa;
            const ej = currEjercicio;
            const cached = this._getFinCache(emp, ej);
            if (cached) {
                window.cachedFinancialData = cached;
                this.refreshWidgets();
            } else {
                const q = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(ej)}`;
                fetch(`/api/financial/snapshot${q}`)
                    .then(res => res.json())
                    .then(json => {
                        window.cachedFinancialData = json;
                        this._setFinCache(emp, ej, json);
                        this.refreshWidgets();
                    })
                    .catch(e => console.error("[Mobile] Financial Fetch Error (runtime)", e));
            }
        }

        if (this.config.layout.length === 0) {
            targetContainer.innerHTML = '<div style="color: #71717a; text-align: center; padding: 20px;">Arrastra widgets aquí</div>';
        }

        this.config.layout.forEach(wId => {
            const wDef = this.widgets.find(x => x.id === wId);
            if (wDef) {
                const el = this.createWidgetElement(wDef, true);
                targetContainer.appendChild(el);
            } else {
                // If widget definition is missing (e.g. legacy ID), show fallback or ignore
                // Let's show a fallback to allow removal
                const fallback = { id: wId, title: 'Widget Desconocido', group: 'Unknown' };
                const el = this.createWidgetElement(fallback, true);
                el.style.border = '1px dashed #ef4444';
                targetContainer.appendChild(el);
            }
        });
    },

    createWidgetElement: function (widget, isTarget = false) {
        const div = document.createElement('div');
        div.className = 'mobile-widget-item';
        div.draggable = true;
        div.dataset.id = widget.id;

        // [NEW] Visual Feedback: Check if already in layout
        if (!isTarget && this.config.layout.includes(widget.id)) {
            div.classList.add('is-selected');
        }

        div.innerHTML = `
            <div class="mw-handle">⋮⋮</div>
            <div class="mw-content">
                <div class="mw-title">${widget.title}</div>
                <div class="mw-group">${widget.group}</div>
            </div>
            ${isTarget ? '<button class="mw-remove" onclick="MobileManager.removeWidget(this)">×</button>' : ''}
        `;

        // Proper event binding
        div.addEventListener('dragstart', (e) => this.handleDragStart(e));
        div.addEventListener('dragend', (e) => this.handleDragEnd(e));

        // Add styles dynamically if not present

        return div;
    },

    setupDragAndDrop: function () {
        // [NEW] 1. Tab Button Logic (Auto-switch & Drop)
        const btnMovil = document.getElementById('btn-sub-movil');
        if (btnMovil) {
            btnMovil.addEventListener('dragover', (e) => {
                e.preventDefault(); // Allow drop/interaction
                // Auto-switch tab
                if (!btnMovil.classList.contains('active') && typeof switchSubTab === 'function') {
                    switchSubTab('sub-movil');
                }
            });

            btnMovil.addEventListener('drop', (e) => {
                e.preventDefault();
                const externalId = e.dataTransfer.getData('text/plain');

                // Process drop
                if (externalId && externalId.startsWith('widget-')) {
                    if (!this.config.layout.includes(externalId)) {
                        this.config.layout.push(externalId);
                        this.renderBuilder();
                        this.saveConfig();
                    }
                } else {
                    this.updateLayoutFromDOM();
                }
            });
        }

        const target = document.getElementById('mobile-builder-target');
        if (!target) return;

        // Desktop Events
        target.addEventListener('dragover', e => {
            e.preventDefault();
            const afterElement = this.getDragAfterElement(target, e.clientY);
            const draggable = document.querySelector('.dragging') || document.querySelector('.external-dragging');

            if (!draggable) return;

            if (afterElement == null) {
                target.appendChild(draggable);
            } else {
                target.insertBefore(draggable, afterElement);
            }
        });

        target.addEventListener('drop', e => {
            e.preventDefault();
            // Check if it's an external drop (from flip card)
            const externalId = e.dataTransfer.getData('text/plain');
            this.handleDropLogic(externalId);
        });

        // Setup Touch Events for Mobile support
        this.setupTouchEvents();
    },

    // Centralized Drop Logic
    handleDropLogic: function (widgetId) {
        if (widgetId && widgetId.startsWith('widget-')) {
            // It's a valid widget ID
            if (!this.config.layout.includes(widgetId)) {
                this.config.layout.push(widgetId);
                this.renderBuilder(); // Re-render everything to show correct style
                this.saveConfig();
            }
        } else {
            // Internal reorder
            this.updateLayoutFromDOM();
        }
    },

    setupTouchEvents: function () {
        // We need to attach touch listeners to all draggables (both source list and external cards)
        // Since external cards are dynamic, we might need a global delegate or re-attach.
        // For now, let's attach to the source list and target list.

        const containers = [
            document.getElementById('mobile-builder-source'),
            document.getElementById('mobile-builder-target')
        ];

        containers.forEach(container => {
            if (!container) return;

            container.addEventListener('touchstart', (e) => this.handleTouchStart(e), { passive: false });
            container.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
            container.addEventListener('touchend', (e) => this.handleTouchEnd(e));
        });

        // External cards touch support needs to be added in setupExternalDraggables
    },

    // Touch State
    touchDragItem: null,
    touchGhost: null,

    handleTouchStart: function (e) {
        const el = e.target.closest('.mobile-widget-item');
        if (!el) return;

        e.preventDefault(); // Prevent scrolling

        this.touchDragItem = el;
        el.classList.add('dragging');

        // Create ghost
        this.touchGhost = el.cloneNode(true);
        this.touchGhost.style.position = 'fixed';
        this.touchGhost.style.width = el.offsetWidth + 'px';
        this.touchGhost.style.opacity = '0.8';
        this.touchGhost.style.zIndex = '9999';
        this.touchGhost.style.pointerEvents = 'none'; // Click through

        const touch = e.touches[0];
        this.touchGhost.style.left = (touch.clientX - 20) + 'px';
        this.touchGhost.style.top = (touch.clientY - 20) + 'px';

        document.body.appendChild(this.touchGhost);
    },

    handleTouchMove: function (e) {
        if (!this.touchDragItem || !this.touchGhost) return;
        e.preventDefault();

        const touch = e.touches[0];
        this.touchGhost.style.left = (touch.clientX - 20) + 'px';
        this.touchGhost.style.top = (touch.clientY - 20) + 'px';

        // Simulate DragOver logic
        const target = document.getElementById('mobile-builder-target');
        if (!target) return;
        const box = target.getBoundingClientRect();

        if (touch.clientX >= box.left && touch.clientX <= box.right &&
            touch.clientY >= box.top && touch.clientY <= box.bottom) {

            // Inside drop zone
            const afterElement = this.getDragAfterElement(target, touch.clientY);
            // Visual feedback only (move original element or placeholder)
            // If dragging from source, we don't move the original source item visually until drop
            if (this.touchDragItem.parentElement.id === 'mobile-builder-target') {
                if (afterElement == null) {
                    target.appendChild(this.touchDragItem);
                } else {
                    target.insertBefore(this.touchDragItem, afterElement);
                }
            }
        }
    },

    handleTouchEnd: function (e) {
        if (!this.touchDragItem) return;

        const touch = e.changedTouches[0];
        const target = document.getElementById('mobile-builder-target');
        if (!target) {
            if (this.touchGhost) this.touchGhost.remove();
            if (this.touchDragItem) this.touchDragItem.classList.remove('dragging');
            this.touchDragItem = null;
            this.touchGhost = null;
            return;
        }
        const box = target.getBoundingClientRect();

        // Check drop
        if (touch.clientX >= box.left && touch.clientX <= box.right &&
            touch.clientY >= box.top && touch.clientY <= box.bottom) {

            const widgetId = this.touchDragItem.dataset.id;

            // If from source, handle logic
            if (this.touchDragItem.parentElement.id === 'mobile-builder-source') {
                this.handleDropLogic(widgetId);
            } else {
                // Reorder
                this.updateLayoutFromDOM();
            }
        }

        // Cleanup
        if (this.touchGhost) this.touchGhost.remove();
        this.touchDragItem.classList.remove('dragging');
        this.touchDragItem = null;
        this.touchGhost = null;
    },

    setupExternalDraggables: function () {
        // Map of DOM ID -> Widget ID
        const map = {
            'val-sales-1d': 'widget-sales-1d',
            'val-sales-7d': 'widget-sales-7d',
            'val-sales-30d': 'widget-sales-30d',
            'val-ticket-1d': 'widget-ticket-1d',
            'val-margin-1d': 'widget-margin-1d',

            // Fixed: Added Compras mappings
            'val-compras-1d': 'widget-compras-1d',
            'val-compras-7d': 'widget-compras-7d',
            'val-compras-30d': 'widget-compras-30d',
            'val-ticket-compra-1d': 'widget-ticket-compra-1d',

            // [FIX] Correct Mapping for KPIs
            'kpi-neto': 'widget-kpi-neto',
            'kpi-coste': 'widget-kpi-coste',
            'kpi-margen': 'widget-kpi-margen',
            'kpi-ticket': 'widget-kpi-ticket',

            // [FIX] Missing Grid Mappings
            'val-ticket-7d': 'widget-ticket-7d',
            'val-ticket-30d': 'widget-ticket-30d',
            'val-margin-7d': 'widget-margin-7d',
            'val-margin-30d': 'widget-margin-30d',

            // [FIX] Financial Widgets Mappings (ISS-UserReq)
            'fin-val-ingresos': 'widget-fin-ingresos',
            'fin-val-gastos': 'widget-fin-gastos',
            'fin-val-resultado': 'widget-fin-resultado',
            'fin-val-liquidez': 'widget-fin-liquidez',
            'fin-val-margen': 'widget-fin-margen',
            'fin-val-solvencia': 'widget-fin-solvencia',
            'fin-val-endeudamiento': 'widget-fin-endeudamiento'
        };

        // Enable Tab Switching on Drag Hover
        const btnMovil = document.getElementById('btn-sub-movil');
        if (btnMovil) {
            btnMovil.addEventListener('dragenter', () => {
                if (typeof switchSubTab === 'function') {
                    switchSubTab('sub-movil');
                    // Render builder after switch
                    setTimeout(() => this.renderBuilder(), 100);
                }
            });
        }

        // Run immediately and then retry just in case
        const apply = () => {
            Object.keys(map).forEach(domId => {
                const valEl = document.getElementById(domId);
                if (valEl) {
                    const card = valEl.closest('.flip-card');
                    if (card && !card.hasAttribute('draggable')) {
                        card.setAttribute('draggable', 'true');
                        card.style.cursor = 'grab';

                        card.addEventListener('dragstart', (e) => {
                            e.dataTransfer.setData('text/plain', map[domId]);
                            e.dataTransfer.effectAllowed = 'copy';
                            card.classList.add('external-dragging');
                            console.log('External drag started:', map[domId]);
                        });

                        card.addEventListener('dragend', () => {
                            card.classList.remove('external-dragging');
                        });

                        // [NEW] Touch Support for External Cards
                        card.addEventListener('touchstart', (e) => {
                            e.preventDefault();
                            this.touchDragItem = card; // Store card as item
                            card.dataset.id = map[domId]; // Ensure ID is available

                            // Ghost
                            this.touchGhost = card.cloneNode(true);
                            this.touchGhost.style.position = 'fixed';
                            this.touchGhost.style.width = '200px'; // Smaller for drag
                            this.touchGhost.style.height = '100px';
                            this.touchGhost.style.opacity = '0.8';
                            this.touchGhost.style.zIndex = '9999';
                            this.touchGhost.style.pointerEvents = 'none';

                            const t = e.touches[0];
                            this.touchGhost.style.left = (t.clientX - 100) + 'px';
                            this.touchGhost.style.top = (t.clientY - 50) + 'px';

                            document.body.appendChild(this.touchGhost);
                        }, { passive: false });

                        card.addEventListener('touchmove', (e) => this.handleTouchMove(e), { passive: false });
                        card.addEventListener('touchend', (e) => this.handleTouchEnd(e));
                    }
                }
            });
        };

        apply();
        setTimeout(apply, 2000); // Retry once after data load
    },

    handleDragStart: function (e) {
        const el = e.target.closest('.mobile-widget-item');
        if (!el) return;

        // If dragging from source, clone it first
        if (el.parentElement.id === 'mobile-builder-source') {
            const clone = el.cloneNode(true);
            clone.classList.add('dragging');
            // Add remove button to clone if not present
            if (!clone.querySelector('.mw-remove')) {
                clone.innerHTML += '<button class="mw-remove" onclick="MobileManager.removeWidget(this)">×</button>';
            }

            // Re-bind events to clone
            clone.addEventListener('dragstart', (ev) => this.handleDragStart(ev));
            clone.addEventListener('dragend', (ev) => this.handleDragEnd(ev));

            // We append clone to target immediately to simulate drag? 
            // No, standard HTML5 drag moves the element.
            // If we want to "copy" from source, we need to let the original stay.

            // Hack: We don't move the source element. We let the "drop" logic handle creation.
            // But for visual feedback, we mark it.
            el.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'copy';
            e.dataTransfer.setData('text/plain', el.dataset.id);

        } else {
            el.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', el.dataset.id);
        }
    },

    handleDragEnd: function (e) {
        const el = e.target.closest('.mobile-widget-item');
        if (el) el.classList.remove('dragging');

        // If we dragged from source, we don't want to move the source item.
        // The drop handler takes care of creating new item.

        const target = document.getElementById('mobile-builder-target');
        // Clean up any mess
    },

    getDragAfterElement: function (container, y) {
        const draggableElements = [...container.querySelectorAll('.mobile-widget-item:not(.dragging)')];

        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    },

    removeWidget: function (btn) {
        btn.parentElement.remove();
        this.updateLayoutFromDOM();
    },

    updateLayoutFromDOM: function () {
        const target = document.getElementById('mobile-builder-target');
        const items = target.querySelectorAll('.mobile-widget-item');
        this.config.layout = Array.from(items).map(el => el.dataset.id);
        this.saveConfig();
        this.renderMobileRuntime();

        // [FIX] Update Builder Source List to reflect selection state (colors)
        // We need to re-render the source list so that items removed from target
        // lose their 'is-selected' class.
        this.renderBuilder();
    },

    // --- RUNTIME LOGIC ---

    applyRuntimeView: function () {
        // [MODIFIED] More robust mobile detection (width OR userAgent)
        // 1024px covers iPads in portrait, but landscape might be wider.
        // We also check touch capability as a hint.
        const isSmallScreen = window.innerWidth < 1024;
        const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

        // [FIX] Force mobile view if user agent indicates mobile, regardless of orientation
        const isMobileUserAgent = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

        // Force mobile view if we are on a "mobile-like" device, even if rotated (landscape)
        // We assume if width < 1366 AND isTouch, it might be a tablet in landscape
        const isTabletLandscape = window.innerWidth <= 1366 && isTouch;

        const isMobile = isSmallScreen || isTabletLandscape || isMobileUserAgent;
        const isCustom = this.config.mode === 'custom';

        if (this._isPhone()) {
            if (this._phoneReady) return;
            this._showPhone();
            this._phoneReady = true;
            return;
        }
        this._phoneReady = false;

        const standardContainer = document.getElementById('actualidad-standard-view');
        const customContainer = document.getElementById('actualidad-mobile-view');
        const settingsBtn = document.getElementById('btn-settings');
        const emptyStateContainer = document.getElementById('mobile-empty-state'); // Need to create this if not exists

        // Debug visibility
        console.log(`[MobileManager] Apply View: Width=${window.innerWidth}, Touch=${isTouch}, UA=${isMobileUserAgent}, Custom=${isCustom} -> Mobile Detected? ${isMobile}`);

        // Logic Branching:
        // 1. Mobile Device + Custom Mode ON -> Show Mobile View
        // 2. Mobile Device + Custom Mode OFF -> Show Empty State / "License Required" (NOT Desktop View)
        // 3. Desktop Device -> Show Desktop View (Standard)

        if (isMobile) {
            // [FIX] Ensure logo is correct on rotation
            const headerLogo = document.getElementById('header-datia-logo');
            if (headerLogo) {
                // [FIX] Use correct key 'datia-selected-logo'
                const savedLogo = localStorage.getItem('datia-selected-logo');
                if (savedLogo) headerLogo.src = savedLogo;

                // Also respect client logo override if present (mirroring core.js)
                const empId = currEmpresa || 'default';
                const hasClientLogo = localStorage.getItem(`datia-client-logo-${empId}`);
                const showClient = localStorage.getItem(`datia-show-client-logo-${empId}`) === 'true';

                if (hasClientLogo && showClient) {
                    headerLogo.src = hasClientLogo;
                }
            }

            if (isCustom) {
                // CASE 1: Mobile App Mode
                if (standardContainer) standardContainer.style.display = 'none';
                if (customContainer) {
                    customContainer.style.display = 'block';
                    this.renderMobileRuntime();
                }
                this.toggleEmptyState(false);
                document.body.classList.add('mobile-app-mode');
                if (settingsBtn) settingsBtn.style.display = 'none';
            } else {
                // CASE 2: Mobile but App Mode Disabled (License check simulation)
                if (standardContainer) standardContainer.style.display = 'none'; // Hide desktop view
                if (customContainer) customContainer.style.display = 'none';

                // Show "License Required" or Default Message
                this.toggleEmptyState(true);

                document.body.classList.remove('mobile-app-mode');
                if (settingsBtn) settingsBtn.style.display = ''; // Allow settings to enable it back
            }
        } else {
            // CASE 3: Desktop
            if (standardContainer) standardContainer.style.display = 'block';
            if (customContainer) customContainer.style.display = 'none';
            this.toggleEmptyState(false);
            document.body.classList.remove('mobile-app-mode');
            if (settingsBtn) settingsBtn.style.display = '';
        }
    },

    _showPhone: function () {
        const standardContainer = document.getElementById('actualidad-standard-view');
        const customContainer = document.getElementById('actualidad-mobile-view');
        if (standardContainer) standardContainer.style.display = 'none';
        if (customContainer) customContainer.style.display = 'block';
        document.body.classList.add('phone-shell');
        document.body.classList.remove('mobile-app-mode');
        this.toggleEmptyState(false);
        document.querySelectorAll('#sel-empresa, #sel-ejercicio').forEach(select => {
            select.style.display = '';
        });
        this.renderMobileRuntime();
    },

    enterPhone: async function () {
        if (!this._isPhone()) return;
        if (typeof switchTab === 'function') switchTab('tab-actualidad');
        await this.loadConfig();
        this._phoneReady = false;
        this.applyRuntimeView();
    },

    setPhoneSection: function (name, button) {
        this.phoneSection = name;
        document.querySelectorAll('.mobile-section-nav button').forEach(item => {
            item.classList.toggle('is-on', item.dataset.section === name);
        });
        if (button) button.classList.add('is-on');
        this._phoneReady = false;
        this.renderMobileRuntime();
        this._phoneReady = true;
    },

    toggleEmptyState: function (show) {
        // [FIX] Strict Header Cleanup for Empty State
        const headerTabs = document.querySelector('.header-tabs');
        const headerFilters = document.querySelector('.filters');
        const sysDate = document.getElementById('sys-date');
        const erpLabel = document.getElementById('erp-label-container');

        // Always try to update logo first
        const headerLogo = document.getElementById('header-datia-logo');
        if (headerLogo) {
            const savedLogo = localStorage.getItem('datia-selected-logo');
            if (savedLogo) headerLogo.src = savedLogo;

            // Client Override
            const empId = currEmpresa || 'default';
            const hasClientLogo = localStorage.getItem(`datia-client-logo-${empId}`);
            const showClient = localStorage.getItem(`datia-show-client-logo-${empId}`) === 'true';
            if (hasClientLogo && showClient) headerLogo.src = hasClientLogo;
        }

        if (show) {
            // Hide everything except Logo and User/Logout
            if (headerTabs) headerTabs.style.display = 'none';
            if (sysDate) sysDate.style.display = 'none';
            if (erpLabel) erpLabel.style.display = 'none';

            // For filters, we might want to keep Logout visible. 
            // The logout button is INSIDE .filters usually, or near it.
            // Let's hide the selects but keep the user info if possible.
            // Based on HTML structure: .filters > select, select, .header-separator, div(user info)
            if (headerFilters) {
                // Hide selects
                const selects = headerFilters.querySelectorAll('select');
                selects.forEach(s => s.style.display = 'none');
                // Hide separators
                const seps = headerFilters.querySelectorAll('.header-separator');
                seps.forEach(s => s.style.display = 'none');
            }

        } else {
            // Restore everything
            if (headerTabs) headerTabs.style.display = '';
            if (sysDate) sysDate.style.display = '';
            if (erpLabel) erpLabel.style.display = ''; // Or whatever its original state was

            if (headerFilters) {
                const selects = headerFilters.querySelectorAll('select');
                selects.forEach(s => s.style.display = '');
                const seps = headerFilters.querySelectorAll('.header-separator');
                seps.forEach(s => s.style.display = '');
            }
        }

        let el = document.getElementById('mobile-empty-state-msg');
        if (!el) {
            el = document.createElement('div');
            el.id = 'mobile-empty-state-msg';
            el.innerHTML = `
                <div class="mobile-empty-state-msg">
                    <div class="mobile-empty-state-icon">📱</div>
                    <h3>Vista Móvil Desactivada</h3>
                    <p>Activa el "Modo Especializado" en la configuración o contacta con soporte para habilitar tu licencia móvil.</p>
                </div>
            `;
            // Append after header or main container
            const main = document.querySelector('main') || document.body;
            main.appendChild(el);
        }
        el.style.display = show ? 'block' : 'none';
    },

    renderMobileRuntime: function () {
        console.log("[Mobile] Rendering Runtime View...");
        const container = document.getElementById('mobile-runtime-content');
        if (!container) return;

        // [FIX] Update Logo (ISS-053)
        const headerLogo = document.getElementById('header-datia-logo');
        if (headerLogo) {
            const savedLogo = localStorage.getItem('datia-selected-logo');
            if (savedLogo) headerLogo.src = savedLogo;

            // Client Override
            const empId = currEmpresa || 'default';
            const hasClientLogo = localStorage.getItem(`datia-client-logo-${empId}`);
            const showClient = localStorage.getItem(`datia-show-client-logo-${empId}`) === 'true';
            if (hasClientLogo && showClient) headerLogo.src = hasClientLogo;

        } else {
            console.warn("[Mobile] Header Logo element not found!");
        }

        container.innerHTML = '';

        // [FIX] Load Data if missing (ISS-053)
        // Check if data is really empty or just not loaded
        const hasSnapshot = window.cachedSnapshotData && Object.keys(window.cachedSnapshotData).length > 0;

        if (!hasSnapshot && typeof loadSnapshot === 'function') {
            console.log("[Mobile] Missing Snapshot Data. Triggering loadSnapshot()...");
            loadSnapshot().then(() => {
                console.log("[Mobile] Snapshot Loaded. Refreshing Widgets...");
                this.refreshWidgets();
            });
        } else {
            console.log("[Mobile] Snapshot Data present:", window.cachedSnapshotData);
        }

        // Load Compras if needed
        const hasCompras = window.cachedComprasSnapshotData && Object.keys(window.cachedComprasSnapshotData).length > 0;
        if (!hasCompras && typeof loadSnapshotCompras === 'function') {
            console.log("[Mobile] Missing Compras Data. Triggering loadSnapshotCompras()...");
            loadSnapshotCompras().then(() => this.refreshWidgets());
        }

        // Ensure Financial Data is loaded if financial widgets are present
        const hasFin = window.cachedFinancialData && Object.keys(window.cachedFinancialData).length > 0;
        const activeIds = this._isPhone() ? this.widgetsForSection() : (this.config.layout || []);
        if (!hasFin && activeIds.some(id => id.startsWith('widget-fin-'))) {
            const emp = currEmpresa;
            const ej = currEjercicio;
            const cached = this._getFinCache(emp, ej);
            if (cached) {
                window.cachedFinancialData = cached;
                this.refreshWidgets();
            } else {
                const qFin = `?empresa=${encodeURIComponent(emp)}&ejercicio=${encodeURIComponent(ej)}`;
                fetch(`/api/financial/snapshot${qFin}`)
                    .then(res => res.json())
                    .then(json => {
                        window.cachedFinancialData = json;
                        this._setFinCache(emp, ej, json);
                        this.refreshWidgets();
                    })
                    .catch(e => console.error("[Mobile] Financial Fetch Error (runtime)", e));
            }
        }

        // [NEW] Ensure Chart Data is loaded
        const hasCharts = window.cachedActivityData && Object.keys(window.cachedActivityData).length > 0;
        if (!hasCharts && activeIds.some(id => id.includes('chart-activity'))) {
            console.log("[Mobile] Missing Chart Data. Fetching...");
            const q = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(currEjercicio)}`;
            fetch(`${API}/widgets/actividad_mensual${q}`)
                .then(res => res.json())
                .then(json => {
                    window.cachedActivityData = json.data; // Cache global
                    console.log("[Mobile] Chart Data Loaded. Refreshing...");
                    this.refreshWidgets();
                })
                .catch(e => console.error("[Mobile] Chart Fetch Error", e));
        }

        const widgetIds = this._isPhone() ? this.widgetsForSection() : (this.config.layout || []);
        if (!widgetIds.length) {
            container.innerHTML = '<div style="text-align:center; padding:20px; color:#71717a;">No hay tarjetas para esta sección.</div>';
            return;
        }

        widgetIds.forEach(wId => {
            const widget = this.widgets.find(x => x.id === wId);
            if (widget) {
                const el = document.createElement('div');
                el.className = 'mobile-runtime-widget';

                if (widget.type === 'chart') {
                    el.classList.add('mobile-runtime-chart');
                    el.innerHTML = `
                        <div class="mrw-header">${widget.title}</div>
                        <div class="mrw-chart-container" id="mob-chart-${widget.id}">
                            <div class="mrw-spinner spinner-border text-light spinner-border-sm" role="status"></div>
                        </div>
                    `;
                } else {
                    // Standard Value Widget
                    el.innerHTML = `
                        <div class="mrw-header">${widget.title}</div>
                        <div class="mrw-value" id="mob-val-${widget.id}">
                            <div class="mrw-spinner spinner-border text-light spinner-border-sm" role="status"></div>
                        </div>
                    `;
                }

                container.appendChild(el);
                // Bind immediately if data exists
                this.bindWidgetData(widget.id);
            }
        });
    },

    refreshWidgets: function () {
        console.log("[Mobile] Refreshing all widgets...");
        const ids = this._isPhone() ? this.widgetsForSection() : (this.config.layout || []);
        ids.forEach(wId => this.bindWidgetData(wId));
    },

    bindWidgetData: function (widgetId) {
        let val = null;
        // [FIX] Robust Formatter
        const money = (v) => {
            if (v === null || v === undefined) return '--';
            const lang = this._getLang();
            return new Intl.NumberFormat(lang, { style: 'currency', currency: 'EUR' }).format(v);
        };

        // Logic to bind data from global cached objects
        // [FIX] Explicitly check window properties
        const dSnap = window.cachedSnapshotData;
        const dKpi = window.cachedKpiData;
        const dCompras = window.cachedComprasSnapshotData;
        const dChart = window.cachedActivityData; // [NEW]

        // [NEW] Financial Data (Stored in window by actualidad_financiera.js renderFinancialSnapshot)
        // We need to capture it. Since we don't have a global cache object for financial yet, 
        // we might need to fetch it or assume it's there. 
        // Let's create a global for financial data in renderFinancialSnapshot: window.cachedFinancialData
        const dFin = window.cachedFinancialData;

        if (dSnap || dKpi || dCompras || dChart || dFin) {

            if (widgetId.startsWith('widget-fin-') && dFin) {
                switch (widgetId) {
                    case 'widget-fin-ingresos': val = money(dFin.ingresos); break;
                    case 'widget-fin-gastos': val = money(dFin.gastos); break;
                    case 'widget-fin-resultado': val = money(dFin.resultado); break;
                    case 'widget-fin-liquidez': val = dFin.ratios ? dFin.ratios.liquidez : null; break;
                    case 'widget-fin-margen': val = dFin.ratios ? dFin.ratios.margen : null; break;
                    case 'widget-fin-solvencia': val = dFin.ratios ? dFin.ratios.solvencia : null; break;
                    case 'widget-fin-endeudamiento': val = dFin.ratios ? dFin.ratios.endeudamiento : null; break;
                }
                const finEl = document.getElementById(`mob-val-${widgetId}`);
                if (finEl) {
                    if (widgetId === 'widget-fin-margen' || widgetId === 'widget-fin-endeudamiento') {
                        finEl.innerText = (val === null || val === undefined || isNaN(Number(val))) ? '--' : Number(val).toFixed(2) + '%';
                    } else if (widgetId === 'widget-fin-liquidez' || widgetId === 'widget-fin-solvencia') {
                        finEl.innerText = (val === null || val === undefined || isNaN(Number(val))) ? '--' : Number(val).toFixed(2);
                    } else {
                        finEl.innerText = val === null || val === undefined ? '--' : val;
                    }
                }
                return;
            }

            // 1. CHARTS
            if (widgetId === 'widget-chart-activity' && dChart) {
                // [NEW] Render Chart
                requestAnimationFrame(() => {
                    if (typeof renderActivityChart === 'function') {
                        const containerId = `#mob-chart-${widgetId}`;
                        // Clear spinner
                        const container = document.querySelector(containerId);
                        if (container) {
                            const spinner = container.querySelector('.spinner-border');
                            if (spinner) spinner.remove();

                            // Force bar style for mobile for now, or use saved preference
                            const savedStyle = localStorage.getItem('chart_style_activity') || 'bar';
                            renderActivityChart(dChart, savedStyle, containerId);
                        }
                    }
                });
                val = 'CHART_RENDERED';
            }
            // 1B. TOP CHARTS (Clients, Products, Map)
            else if (widgetId === 'widget-chart-clients') {
                this._loadAndRenderTopChart(widgetId, 'top_clientes', '#818cf8', 'cachedTopClients');
                val = 'LOADING';
            }
            else if (widgetId === 'widget-chart-products') {
                this._loadAndRenderTopChart(widgetId, 'top_articulos', '#fbbf24', 'cachedTopProducts');
                val = 'LOADING';
            }
            else if (widgetId === 'widget-chart-map') {
                this._loadAndRenderTopChart(widgetId, 'mapa_ventas', '#34d399', 'cachedTopZones');
                val = 'LOADING';
            }
            // 1C. TOP CHARTS (Compras)
            else if (widgetId === 'widget-chart-top-proveedores') {
                this._loadAndRenderTopChart(widgetId, 'top_proveedores', '#f472b6', 'cachedTopProveedores');
                val = 'LOADING';
            }
            else if (widgetId === 'widget-chart-top-articulos-compra') {
                this._loadAndRenderTopChart(widgetId, 'top_articulos_compra', '#fbbf24', 'cachedTopProductsCompra');
                val = 'LOADING';
            }

            // 2. COMPRAS (Purchases) - Strict Separation [FIX]
            else if ((widgetId.includes('compras') || widgetId.includes('compra')) && dCompras) {
                // A. Grid (1d, 7d, 30d)
                if (widgetId.includes('1d')) {
                    if (widgetId.includes('ticket-compra')) val = money(dCompras.m_1d?.ticket);
                    else if (widgetId.includes('ops-compra')) val = (dCompras.m_1d?.albaranes || 0);
                    else if (widgetId.includes('compras')) val = money(dCompras.m_1d?.neto);
                }
                else if (widgetId.includes('7d')) {
                    if (widgetId.includes('ticket-compra')) val = money(dCompras.m_7d?.ticket);
                    else if (widgetId.includes('ops-compra')) val = (dCompras.m_7d?.albaranes || 0);
                    else if (widgetId.includes('compras')) val = money(dCompras.m_7d?.neto);
                }
                else if (widgetId.includes('30d')) {
                    if (widgetId.includes('ticket-compra')) val = money(dCompras.m_30d?.ticket);
                    else if (widgetId.includes('ops-compra')) val = (dCompras.m_30d?.albaranes || 0);
                    else if (widgetId.includes('compras')) val = money(dCompras.m_30d?.neto);
                }
                // B. Global KPIs (Year)
                else {
                    if (widgetId === 'widget-kpi-compras-neto') val = money(dCompras.global_neto);
                    else if (widgetId === 'widget-val-kpi-ticket-compra') val = money(dCompras.global_ticket);
                    else if (widgetId === 'widget-val-kpi-ops-compra') val = (dCompras.global_albaranes || 0);
                    else if (widgetId === 'widget-val-kpi-proveedores') val = (dCompras.active_providers || 0);
                }
            }

            // 3. VENTAS (Sales) - From Snapshot
            else if (dSnap) {
                // A. Grid
                if (widgetId.includes('sales')) {
                    if (widgetId.includes('1d')) val = money(dSnap.m_1d?.neto);
                    else if (widgetId.includes('7d')) val = money(dSnap.m_7d?.neto);
                    else if (widgetId.includes('30d')) val = money(dSnap.m_30d?.neto);
                }
                else if (widgetId.includes('ticket') && !widgetId.includes('compra')) { // [FIX] Exclude compra
                    if (widgetId.includes('1d')) val = money(dSnap.m_1d?.ticket);
                    else if (widgetId.includes('7d')) val = money(dSnap.m_7d?.ticket);
                    else if (widgetId.includes('30d')) val = money(dSnap.m_30d?.ticket);
                }
                else if (widgetId.includes('margin') && !widgetId.includes('fin')) {
                    if (widgetId.includes('1d')) val = (dSnap.m_1d?.margin || 0).toFixed(1) + '%';
                    else if (widgetId.includes('7d')) val = (dSnap.m_7d?.margin || 0).toFixed(1) + '%';
                    else if (widgetId.includes('30d')) val = (dSnap.m_30d?.margin || 0).toFixed(1) + '%';
                }
                // B. Global KPIs (Year)
                else if (widgetId === 'widget-kpi-neto' && dSnap.global_neto !== undefined) val = money(dSnap.global_neto);
                else if (widgetId === 'widget-kpi-coste' && dSnap.global_margin_eur !== undefined) val = money(dSnap.global_neto - dSnap.global_margin_eur); // Approx
                else if (widgetId === 'widget-kpi-margen' && dSnap.global_margin_pct !== undefined) val = dSnap.global_margin_pct.toFixed(2) + '%';
                else if (widgetId === 'widget-kpi-ticket' && dSnap.global_ticket !== undefined) val = money(dSnap.global_ticket);
            }

            // 4. FINANCIAL
            else if (widgetId.startsWith('widget-fin-') && dFin) {
                switch (widgetId) {
                    case 'widget-fin-ingresos': val = money(dFin.ingresos); break;
                    case 'widget-fin-gastos': val = money(dFin.gastos); break;
                    case 'widget-fin-resultado': val = money(dFin.resultado); break;
                    case 'widget-fin-liquidez': val = dFin.ratios.liquidez; break;
                    case 'widget-fin-margen': val = dFin.ratios.margen; break;
                    case 'widget-fin-solvencia': val = dFin.ratios.solvencia; break;
                    case 'widget-fin-endeudamiento': val = dFin.ratios.endeudamiento; break;
                }

                // Special formatting
                if (widgetId === 'widget-fin-margen') {
                    // Pre-formatted in updateKPIValue, but here we have raw number
                    const el = document.getElementById(`mob-val-${widgetId}`);
                    if (el) el.innerText = val !== null ? val.toFixed(2) + "%" : '--';
                    return; // Done
                }
                if (['widget-fin-liquidez', 'widget-fin-solvencia'].includes(widgetId)) {
                    const el = document.getElementById(`mob-val-${widgetId}`);
                    if (el) el.innerText = val !== null ? val.toFixed(2) : '--';
                    return; // Done
                }
                if (widgetId === 'widget-fin-endeudamiento') {
                    const el = document.getElementById(`mob-val-${widgetId}`);
                    if (el) el.innerText = val !== null ? val.toFixed(2) + "%" : '--';
                    return; // Done
                }
            }

            // Fallback for Financial legacy
            else if (widgetId.includes('fin-') && dKpi) {
                if (widgetId.includes('neto')) val = money(dKpi.neto);
                else if (widgetId.includes('coste')) val = money(dKpi.coste);
                else if (widgetId.includes('margin')) val = dKpi.margen + '%';
            }
        }

        const el = document.getElementById(`mob-val-${widgetId}`);
        if (el) {
            if (val !== null && val !== '--') {
                el.innerText = val;
                // Remove spinner if exists
                if (el.querySelector('.spinner-border')) el.innerHTML = val;
            } else {
                // Keep spinner if we are still loading, otherwise show --
                // We assume if this function is called, we attempted to load data.
                // If val is still null, it means data is missing for this specific widget.
                if (el.querySelector('.spinner-border')) {
                    // Check if we are really done loading
                    // For now, let's leave spinner or set --
                    // If we have ANY data object, we probably loaded.
                    if (dSnap || dKpi || dCompras) {
                        el.innerText = '--';
                    }
                }
            }
        }
    },

    _loadAndRenderTopChart: function (widgetId, endpoint, color, cacheKey) {
        const containerId = `#mob-chart-${widgetId}`;

        // 1. Check Cache
        if (window[cacheKey]) {
            this._safeRenderBarChart(containerId, window[cacheKey], color);
            return;
        }

        // 2. Fetch
        const q = `?empresa=${encodeURIComponent(currEmpresa)}&ejercicio=${encodeURIComponent(currEjercicio)}&limit=5`;
        fetch(`${API}/widgets/${endpoint}${q}`)
            .then(res => res.json())
            .then(json => {
                const data = json.data.data; // Wrapper madness: json.data -> {data: []}
                window[cacheKey] = data; // Cache Global
                this._safeRenderBarChart(containerId, data, color);
            })
            .catch(e => console.error(`[Mobile] Error loading ${widgetId}`, e));
    },

    _safeRenderBarChart: function (containerId, data, color) {
        requestAnimationFrame(() => {
            const container = document.querySelector(containerId);
            if (container) {
                // Clear Spinner
                const spinner = container.querySelector('.spinner-border');
                if (spinner) spinner.remove();

                if (typeof renderBarChart === 'function') {
                    renderBarChart(containerId, data, color);
                } else {
                    console.error("renderBarChart not found!");
                    container.innerText = "Error: renderBarChart missing";
                }
            }
        });
    },

    refreshNgrokUrl: async function () {
        const box = document.getElementById('ngrok-url-box');
        const input = document.getElementById('ngrok-url-value');
        if (!box || !input) return;
        try {
            const res = await fetch(this._api('/system/ngrok/url'));
            const data = await res.json();
            if (data && data.url) {
                input.value = data.url;
                box.hidden = false;
                const status = document.getElementById('ngrok-url-status');
                if (status) status.textContent = 'Túnel ya abierto. Ábrelo en el móvil.';
            }
        } catch (e) { }
    },

    openNgrok: async function () {
        const btn = document.getElementById('btn-ngrok-open');
        const box = document.getElementById('ngrok-url-box');
        const input = document.getElementById('ngrok-url-value');
        const status = document.getElementById('ngrok-url-status');
        if (btn) btn.disabled = true;
        if (box) box.hidden = false;
        if (status) status.textContent = 'Abriendo el túnel...';
        try {
            const res = await fetch(this._api('/system/ngrok/open'), {
                method: 'POST',
                headers: { 'X-CSRFToken': (typeof getCookie === 'function' ? getCookie('csrftoken') : '') }
            });
            const data = await res.json();
            if (data && data.url) {
                if (input) input.value = data.url;
                if (status) {
                    status.textContent = data.already
                        ? 'El túnel ya estaba abierto.'
                        : 'Túnel listo. Copia la dirección y ábrela en el móvil.';
                }
            } else if (status) {
                status.textContent = (data && data.message) || 'No se pudo obtener la dirección.';
            }
        } catch (e) {
            if (status) status.textContent = 'No se pudo contactar con el servidor.';
        } finally {
            if (btn) btn.disabled = false;
        }
    },

    copyNgrokUrl: function () {
        const input = document.getElementById('ngrok-url-value');
        if (!input || !input.value) return;
        const done = () => this.showToast('Dirección copiada');
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(input.value).then(done).catch(() => {
                input.select();
                document.execCommand('copy');
                done();
            });
            return;
        }
        input.select();
        document.execCommand('copy');
        done();
    },

    showToast: function (msg) {
        // Reuse core showToast if available, otherwise console
        if (typeof window.showToast === 'function') {
            window.showToast(msg);
        } else {
            console.log("TOAST:", msg);
        }
    }
};

// Auto-init
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('dashboard-container') || document.getElementById('actualidad-standard-view')) {
        MobileManager.init();
    }
});

// Expose to window
window.MobileManager = MobileManager;
