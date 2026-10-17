let initialSetupJobId = null;
let initialSetupPolling = null;
let initialSetupEmpresas = [];
let initialSetupSelectedEmpresas = [];

async function initialSetupCheckStatus() {
    try {
        const res = await fetch('/api/system/initial_setup/status?_=' + Date.now());
        if (res.ok) {
            const data = await res.json();
            if (!data.has_companies && !data.initial_setup_completed) {
                showInitialSetupOverlay();
            }
        } else {
            showInitialSetupOverlay();
            if (window.showToast) window.showToast('Error al comprobar el estado inicial del sistema.', true);
        }
    } catch (e) {
        console.error('InitialSetup status error:', e);
        showInitialSetupOverlay();
        if (window.showToast) window.showToast('Error al comprobar el estado inicial del sistema.', true);
    }
}

async function loadMssqlDatabases() {
    const select = document.getElementById('initial-setup-mssql-db');
    const hint = document.getElementById('initial-setup-mssql-db-hint');
    if (!select) return;
    try {
        const res = await fetch('/api/etl/mssql/databases?_=' + Date.now());
        if (!res.ok) {
            throw new Error('HTTP ' + res.status);
        }
        const data = await res.json();
        const names = Array.isArray(data)
            ? data
            : (Array.isArray(data.databases) ? data.databases : []);
        select.innerHTML = '';
        if (!names.length) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No se han detectado bases de datos MSSQL accesibles';
            select.appendChild(opt);
            if (hint) {
                hint.style.display = 'block';
                hint.textContent = 'Revisa la configuración MSSQL en el fichero .env o el acceso de red.';
            }
            return;
        }
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Selecciona una base de datos...';
        placeholder.disabled = true;
        placeholder.selected = true;
        select.appendChild(placeholder);
        names.forEach(function (name) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        });
        select.onchange = function () {
            const val = select.value || '';
            loadMssqlEmpresasForDb(val);
        };
        if (hint) {
            hint.style.display = 'block';
            hint.textContent = 'Solo se usará para lectura de datos (Empresas, ventas, compras, etc.).';
        }
    } catch (e) {
        console.error('InitialSetup MSSQL DB load error:', e);
        if (select) {
            select.innerHTML = '';
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'Error al cargar bases de datos MSSQL';
            select.appendChild(opt);
        }
        if (hint) {
            hint.style.display = 'block';
            hint.textContent = 'No se ha podido conectar al servidor MSSQL. Verifica las credenciales y la red.';
        }
        if (window.showToast) window.showToast('Error al cargar las bases de datos MSSQL.', true);
    }
}

async function loadMssqlEmpresasForDb(dbName) {
    const section = document.getElementById('initial-setup-empresa-section');
    const list = document.getElementById('initial-setup-empresa-list');
    initialSetupEmpresas = [];
    initialSetupSelectedEmpresas = [];
    if (!section || !list) return;
    if (!dbName) {
        section.style.display = 'none';
        list.innerHTML = '<div style="color:#a1a1aa;">Selecciona una base de datos para ver las empresas disponibles.</div>';
        return;
    }
    section.style.display = 'block';
    list.innerHTML = '<div style="color:#a1a1aa;">Cargando empresas…</div>';
    try {
        const res = await fetch('/api/etl/mssql/empresas?db=' + encodeURIComponent(dbName));
        if (!res.ok) {
            throw new Error('HTTP ' + res.status);
        }
        const data = await res.json();
        const items = Array.isArray(data) ? data : (Array.isArray(data.items) ? data.items : []);
        initialSetupEmpresas = items;
        if (!items.length) {
            list.innerHTML = '<div style="color:#a1a1aa;">No se han encontrado empresas en la base seleccionada.</div>';
            return;
        }
        list.innerHTML = '';
        initialSetupSelectedEmpresas = [];
        items.forEach(function (item) {
            const code = item.empresa;
            const name = item.nombre || '';
            const id = 'initial-setup-emp-' + String(code);
            const row = document.createElement('label');
            row.setAttribute('for', id);
            row.style.display = 'flex';
            row.style.alignItems = 'center';
            row.style.gap = '6px';
            row.style.padding = '2px 4px';
            const input = document.createElement('input');
            input.type = 'checkbox';
            input.id = id;
            input.value = String(code);
            input.checked = true;
            input.onchange = function () {
                const v = String(code);
                if (input.checked) {
                    if (!initialSetupSelectedEmpresas.includes(v)) {
                        initialSetupSelectedEmpresas.push(v);
                    }
                } else {
                    initialSetupSelectedEmpresas = initialSetupSelectedEmpresas.filter(function (x) { return x !== v; });
                }
            };
            const text = document.createElement('span');
            text.textContent = String(code) + ' · ' + name;
            row.appendChild(input);
            row.appendChild(text);
            list.appendChild(row);
            const v = String(code);
            if (!initialSetupSelectedEmpresas.includes(v)) {
                initialSetupSelectedEmpresas.push(v);
            }
        });
    } catch (e) {
        console.error('InitialSetup empresas load error:', e);
        list.innerHTML = '<div style="color:#fca5a5;">Error al cargar las empresas de la base seleccionada.</div>';
        if (window.showToast) window.showToast('Error al cargar las empresas desde MSSQL.', true);
    }
}

function showInitialSetupOverlay() {
    const overlay = document.getElementById('initial-setup-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
}

function closeInitialSetupOverlay() {
    const overlay = document.getElementById('initial-setup-overlay');
    if (!overlay) return;
    overlay.style.display = 'none';
}

async function startInitialImport() {
    const dbInput = document.getElementById('initial-setup-mssql-db');
    const progressBar = document.getElementById('initial-setup-progress-bar');
    const progressText = document.getElementById('initial-setup-progress-text');
    const errorBox = document.getElementById('initial-setup-errors');
    const button = document.getElementById('initial-setup-start-btn');

    if (errorBox) {
        errorBox.innerHTML = '';
        errorBox.style.display = 'none';
    }

    const db = dbInput ? (dbInput.value || '').trim() : '';
    if (!db) {
        if (window.showToast) window.showToast('Selecciona o escribe una base de datos MSSQL válida.', true);
        return;
    }

    if (button) {
        button.disabled = true;
    }
    if (progressBar) {
        progressBar.style.width = '0%';
    }
    if (progressText) {
        progressText.innerText = 'Preparando importación...';
    }

    let token = null;
    if (typeof getCookie === 'function') {
        token = getCookie('csrftoken');
    }
    if (!token && typeof CSRF_TOKEN !== 'undefined') {
        token = CSRF_TOKEN;
    }

    try {
        const params = new URLSearchParams();
        params.set('mssql_database', db);
        if (initialSetupSelectedEmpresas && initialSetupSelectedEmpresas.length) {
            params.set('empresas', initialSetupSelectedEmpresas.join(','));
        }
        const res = await fetch('/api/etl/workflow/reset_sync_recalc?' + params.toString(), {
            method: 'POST',
            headers: token ? { 'X-CSRFToken': token } : {}
        });
        const data = await res.json();
        if (!res.ok || !data || !data.job_id) {
            if (window.showToast) {
                const msg = (data && (data.message || data.error)) ? (data.message || data.error) : 'No se pudo iniciar la importación inicial.';
                window.showToast('Error: ' + msg, true);
            }
            if (button) button.disabled = false;
            return;
        }
        initialSetupJobId = data.job_id;
        pollInitialSetupJob();
    } catch (e) {
        console.error('Initial import error:', e);
        if (window.showToast) window.showToast('Error de conexión al iniciar la importación.', true);
        if (button) button.disabled = false;
    }
}

async function pollInitialSetupJob() {
    const progressBar = document.getElementById('initial-setup-progress-bar');
    const progressText = document.getElementById('initial-setup-progress-text');
    const button = document.getElementById('initial-setup-start-btn');

    if (!initialSetupJobId) return;

    try {
        const res = await fetch(`/api/etl/status/${initialSetupJobId}`);
        if (!res.ok) {
            throw new Error('Status HTTP ' + res.status);
        }
        const job = await res.json();
        const pct = typeof job.progress === 'number' ? job.progress : 0;
        const message = job && job.message ? job.message : '';
        const status = job && job.status ? job.status : 'pending';

        if (progressBar) {
            progressBar.style.width = pct + '%';
        }
        if (progressText) {
            progressText.innerText = pct + '% · ' + message;
        }

        if (status === 'completed') {
            try {
                renderInitialSetupSummary(job);
            } catch (e) {
                console.error('InitialSetup summary error:', e);
            }
            if (window.showToast) window.showToast('Importación inicial completada.', false);
            initialSetupJobId = null;
            await verifyInitialSetup();
            if (button) button.disabled = false;
            return;
        }
        if (status === 'error') {
            if (window.showToast) window.showToast('Se ha producido un error durante la importación.', true);
            initialSetupJobId = null;
            if (button) button.disabled = false;
            return;
        }
        initialSetupPolling = setTimeout(pollInitialSetupJob, 3000);
    } catch (e) {
        console.error('InitialSetup polling error:', e);
        if (window.showToast) window.showToast('Error al consultar el progreso de la importación.', true);
        const button = document.getElementById('initial-setup-start-btn');
        if (button) button.disabled = false;
    }
}

async function verifyInitialSetup() {
    const errorBox = document.getElementById('initial-setup-errors');
    const verifyText = document.getElementById('initial-setup-verify-text');
    try {
        const res = await fetch('/api/system/initial_setup/verify?_=' + Date.now());
        const data = await res.json();
        if (data.status === 'ok') {
            if (verifyText) {
                verifyText.innerText = 'Verificación completada correctamente. Se ha encontrado al menos una empresa válida.';
            }
            await markInitialSetupComplete();
        } else {
            if (errorBox) {
                errorBox.style.display = 'block';
                errorBox.innerHTML = '';
                const list = document.createElement('ul');
                data.errors.forEach(function (err) {
                    const li = document.createElement('li');
                    li.innerText = err.message || 'Error desconocido.';
                    list.appendChild(li);
                });
                errorBox.appendChild(list);
            }
        }
    } catch (e) {
        console.error('InitialSetup verify error:', e);
        if (window.showToast) window.showToast('Error al verificar los datos importados.', true);
    }
}

async function markInitialSetupComplete() {
    let token = null;
    if (typeof getCookie === 'function') {
        token = getCookie('csrftoken');
    }
    if (!token && typeof CSRF_TOKEN !== 'undefined') {
        token = CSRF_TOKEN;
    }
    try {
        const res = await fetch('/api/system/initial_setup/complete', {
            method: 'POST',
            headers: token ? {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            } : {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
            if (window.showToast) window.showToast('Inicialización completada. Recargando interfaz...', false);
            setTimeout(function () {
                window.location.reload();
            }, 1200);
        } else {
            if (window.showToast) {
                const msg = data && (data.message || data.error) ? (data.message || data.error) : 'No se pudo marcar la inicialización como completada.';
                window.showToast('Error: ' + msg, true);
            }
        }
    } catch (e) {
        console.error('InitialSetup complete error:', e);
        if (window.showToast) window.showToast('Error al finalizar la inicialización.', true);
    }
}

function renderInitialSetupSummary(job) {
    if (!job || !job.summary) return;
    const overlay = document.getElementById('initial-setup-overlay');
    if (!overlay) return;
    let box = document.getElementById('initial-setup-summary');
    if (!box) {
        box = document.createElement('div');
        box.id = 'initial-setup-summary';
        box.style.marginTop = '1rem';
        box.style.maxHeight = '260px';
        box.style.overflowY = 'auto';
        box.style.fontSize = '0.85rem';
        overlay.appendChild(box);
    }
    const s = job.summary || {};
    let html = '';
    if (Array.isArray(s.tables) && s.tables.length) {
        html += '<strong>Tablas migradas</strong><ul>';
        s.tables.forEach(function (t) {
            html += '<li>' + String(t.table || '') + ': ' + String(t.rows != null ? t.rows : 0) + ' registros</li>';
        });
        html += '</ul>';
    }
    if (Array.isArray(s.metrics) && s.metrics.length) {
        html += '<strong>Tablas metrics_</strong><ul>';
        s.metrics.forEach(function (t) {
            html += '<li>' + String(t.table || '') + ': ' + String(t.rows != null ? t.rows : 0) + ' registros</li>';
        });
        html += '</ul>';
    }
    box.innerHTML = html;
}

document.addEventListener('DOMContentLoaded', function () {
    initialSetupCheckStatus();
    loadMssqlDatabases();
});

window.startInitialImport = startInitialImport;
window.closeInitialSetupOverlay = closeInitialSetupOverlay;
