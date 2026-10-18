/* --- tab_auto_core.js --- */
/* Core functionality: Tabs, Favorites, Notifications */

function switchAutoTab(tabId) {
    // Hide all tabs
    document.querySelectorAll('.auto-subtab').forEach(el => el.style.display = 'none');
    // Remove active class
    document.querySelectorAll('.auto-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    // Ensure stars are correct (e.g. if switching deselects something visually, though logic relies on storage)
    if (typeof updateAllStars === 'function') updateAllStars();

    // Show target
    const target = document.getElementById(tabId);
    if (target) target.style.display = 'block';

    // Activate button
    const btnId = 'btn-tab-' + tabId.replace('subtab-', '');
    const btn = document.getElementById(btnId);
    if (btn) {
        btn.classList.add('active');
    }

    // [FIX] Load data for specific tabs
    if (tabId === 'subtab-relationships') {
        if (typeof loadRelations === 'function') loadRelations();
    } else if (tabId === 'subtab-context') {
        if (typeof loadContext === 'function') loadContext();
    } else if (tabId === 'subtab-dashboard') {
        if (typeof loadDashboardStats === 'function') loadDashboardStats();
    } else if (tabId === 'subtab-standard-fields') {
        if (typeof loadStandardFields === 'function') loadStandardFields();
    } else if (tabId === 'subtab-sync') {
        if (typeof prepareSyncScreen === 'function') prepareSyncScreen();
    }
}


function toggleFavoriteTab(e, tabId) {
    if (e) e.stopPropagation(); // Don't switch tab
    const currentFav = localStorage.getItem('datia-fav-auto-tab');
    console.log('[AutoTab] Toggle Favorite. Current:', currentFav, 'Target:', tabId);

    if (currentFav === tabId) {
        // Unset
        localStorage.removeItem('datia-fav-auto-tab');
        showStatus('Favorito eliminado', 'success');
    } else {
        // Set
        localStorage.setItem('datia-fav-auto-tab', tabId);
        showStatus('Pestaña guardada como favorita', 'success');
    }

    // Force update all stars immediately
    updateAllStars();
}

function updateAllStars() {
    const saved = localStorage.getItem('datia-fav-auto-tab');
    document.querySelectorAll('.auto-tab-btn').forEach(btn => {
        const targetTab = btn.getAttribute('data-tab');
        const star = btn.querySelector('.fav-star');
        if (star && targetTab) {
            const isFav = saved === targetTab;
            // [FIX] Force color update with priority to prevent CSS override
            const color = isFav ? '#fbbf24' : 'rgba(255,255,255,0.2)';
            star.style.setProperty('color', color, 'important');
        }
    });
}

// Init Favorites
function initFavoriteTab() {
    console.log('[AutoTab] Initializing Favorites...');
    const saved = localStorage.getItem('datia-fav-auto-tab');

    // 1. Create Stars FIRST to ensure they exist for any subsequent logic
    document.querySelectorAll('.auto-tab-btn').forEach(btn => {
        const tabId = btn.getAttribute('data-tab');
        if (!tabId) return;

        // Prevent duplicates
        if (btn.querySelector('.fav-star')) return;

        const star = document.createElement('span');
        star.className = 'fav-star';
        star.innerHTML = '★';
        star.style.marginLeft = '8px';
        star.style.fontSize = '1.1rem';
        star.style.cursor = 'pointer';
        star.style.transition = 'color 0.2s';
        star.title = 'Marcar como inicio';

        // Click handler
        star.onclick = (e) => toggleFavoriteTab(e, tabId);

        // Hover logic (visual feedback)
        // Hover logic (visual feedback)
        star.onmouseover = () => {
            if (localStorage.getItem('datia-fav-auto-tab') !== tabId) {
                star.style.setProperty('color', '#fbbf24', 'important');
            }
        };
        star.onmouseout = () => {
            if (localStorage.getItem('datia-fav-auto-tab') !== tabId) {
                star.style.setProperty('color', 'rgba(255,255,255,0.2)', 'important');
            }
        };

        btn.appendChild(star);

        // [UX] Add Double Click to Button (Consistency with Core)
        btn.ondblclick = (e) => {
            e.preventDefault();
            toggleFavoriteTab(e, tabId);
        };
    });

    // 2. Set Initial Star Colors
    updateAllStars();

    // 3. Switch to Saved Tab (or Default)
    // 3. Switch to Saved Tab (or Default)
    // [FIX] Ensure we only restore if it is actually a SUB-TAB
    if (saved && saved.startsWith('subtab-')) {
        console.log('[AutoTab] Restoring saved tab:', saved);
        switchAutoTab(saved);
    } else {
        console.log('[AutoTab] No saved sub-tab, defaulting to dashboard');
        switchAutoTab('subtab-dashboard');
    }
}

function showStatus(msg, type) {
    const el = document.getElementById('cx-status');
    if (el) {
        el.innerText = msg;
        if (type === 'success') {
            el.style.background = 'rgba(16, 185, 129, 0.2)';
            el.style.color = '#34d399';
        } else {
            el.style.background = 'rgba(239, 68, 68, 0.2)';
            el.style.color = '#ef4444';
        }
    } else {
        // Fallback if cx-status is not visible (e.g. valid toast)
        if (typeof showToast === 'function') showToast(msg);
    }
}

// Global Context Logic
function getCurrentEmpresa() {
    try {
        if (typeof currEmpresa !== 'undefined' && currEmpresa) return currEmpresa;
        const sel = document.getElementById('sel-empresa');
        if (sel && sel.value) return sel.value;
        const params = new URLSearchParams(window.location.search);
        const p = params.get('empresa');
        if (p) return p;
    } catch (e) {}
    return '';
}

function empresaListQuery() {
    const emp = getCurrentEmpresa();
    if (emp && /^\d+$/.test(String(emp))) {
        return `empresa=${encodeURIComponent(emp)}`;
    }
    return '';
}

let cxRetry = 0;

async function loadContext() {
    try {
        const emp = getCurrentEmpresa();
        if (!emp || !/^\d+$/.test(emp)) {
            if (cxRetry < 10) {
                cxRetry++;
                setTimeout(loadContext, 500);
            }
            showStatus('Selecciona una empresa antes de cargar contexto', 'error');
            return;
        }
        const res = await fetch(`/api/semantic/context/${emp}`);
        const data = await res.json();

        if (data.status === 'ok' && data.context) {
            // console.log("Context loaded:", data.context);
            if (data.context.descripcion_negocio) {
                const el = document.getElementById('cx-description');
                if (el) el.value = data.context.descripcion_negocio;
                showStatus('Sincronizado', 'success');
                cxRetry = 0;
            }
        } else {
            console.warn("No context found or error:", data);
        }
    } catch (e) {
        console.error("Error loading context", e);
        showStatus('Error: ' + e.message, 'error');
    }
}

async function saveContext() {
    const btn = document.querySelector('button[onclick="saveContext()"]');
    if (btn) btn.innerHTML = '⏳ Guardando...';

    try {
        const emp = getCurrentEmpresa();
        if (!emp || !/^\d+$/.test(emp)) {
            const savedEmp = localStorage.getItem('datia-empresa') || '';
            if (savedEmp && /^\d+$/.test(savedEmp)) {
                const res2 = await fetch(`/api/semantic/context/${savedEmp}`);
                const data2 = await res2.json();
                showStatus(data2.status === 'ok' ? 'Sincronizado' : 'Error', data2.status === 'ok' ? 'success' : 'error');
                return;
            }
            showStatus('Selecciona una empresa antes de guardar contexto', 'error');
            return;
        }
        const content = document.getElementById('cx-description').value;

        const headers = { 'Content-Type': 'application/json' };
        if (typeof CSRF_TOKEN !== 'undefined') headers['X-CSRFToken'] = CSRF_TOKEN;
        const res = await fetch(`/api/semantic/context/${emp}`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                key: 'descripcion_negocio',
                content: content
            })
        });

        const data = await res.json();
        if (data.status === 'saved') {
            showStatus('Guardado correctamente', 'success');
            await loadContext();
            showStatus('Sincronizado', 'success');
        } else {
            showStatus('Error: ' + (data.message || 'Desconocido'), 'error');
        }
    } catch (e) {
        console.error(e);
        showStatus('Error de conexión', 'error');
    } finally {
        if (btn) btn.innerHTML = '💾 Guardar Contexto';
    }
}
