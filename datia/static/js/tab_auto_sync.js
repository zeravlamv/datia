/* --- tab_auto_sync.js --- */
/* Synchronization, Re-indexing, and Reset logic */

// Reindex Table (AI Training)
async function reindexTable(id, tableName) {
    if (typeof showToast === 'function') showToast(`Borrando ejemplos SQL de ${tableName}...`);

    try {
        const res = await fetch(`/api/datasource/${id}/reindex`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast(data.message || `Ejemplos SQL de ${tableName} borrados.`);
        } else {
            console.error(data);
            if (typeof showToast === 'function') showToast(`❌ Error: ${data.error}`);
        }
    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') showToast(`❌ Error de conexión`);
    }
}

// Reset/Delete a table (Nuclear action)
async function resetTable(sourceId) {
    try {
        const res = await fetch(`/api/semantic/source/${sourceId}/reset`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast(`✅ ${data.message}`);
            loadMappedTables();
        } else {
            if (typeof showToast === 'function') showToast(`❌ Error: ${data.message}`);
        }
    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') showToast("❌ Error de conexión al eliminar.");
    }
}

// Trigger sync for a specific table (legacy/individual)
async function triggerTableSync(tableName) {
    const progressArea = document.getElementById('sync-progress-area');
    const progressText = document.getElementById('sync-status-text');
    const progressBar = document.getElementById('sync-progress-bar');

    progressArea.style.display = 'block';
    progressText.innerText = `Sincronizando ${tableName}...`;
    progressBar.style.width = '0%';

    try {
        const params = [];
        if (currEmpresa) params.push(`empresa_id=${encodeURIComponent(currEmpresa)}`);
        params.push(`table_name=${encodeURIComponent(tableName)}`);
        const fastBulk = localStorage.getItem('datia-fast-bulk') === 'true';
        params.push(`fast_bulk=${fastBulk}`);
        const query = params.join('&');
        const res = await fetch(`/api/etl/sync?${query}`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'started') {
            const jobId = data.job_id;
            const jobStart = Date.now();
            let stopped = false;
            const run = async () => {
                if (stopped) return;
                try {
                    const pollRes = await fetch(`/api/etl/status/${jobId}`);
                    const pollData = await pollRes.json();
                    if (pollData.status === 'running' || pollData.status === 'starting') {
                        const progress = Number(pollData.progress || 0);
                        progressBar.style.width = `${progress}%`;
                        let extra = '';
                        try {
                            const match = /(\d+)\s*\/\s*(\d+)/.exec(pollData.message || '');
                            if (match) {
                                const copied = parseInt(match[1], 10);
                                const total = parseInt(match[2], 10);
                                const remaining = Math.max(0, total - copied);
                                extra += ` · Restantes: ${remaining}`;
                            }
                        } catch (_) {}
                        if (progress > 0 && progress < 100) {
                            const elapsed = Date.now() - jobStart;
                            const totalMs = (elapsed * 100) / progress;
                            const remainingMs = Math.max(0, totalMs - elapsed);
                            const fmt = (ms) => {
                                const s = Math.round(ms / 1000);
                                const m = Math.floor(s / 60);
                                const ss = s % 60;
                                return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
                            };
                            extra += ` · ETA: ${fmt(remainingMs)}`;
                        }
                        progressText.innerText = `${pollData.message} (${progress}%)${extra}`;
                        const delay = progress >= 90 ? 1000 : 2500;
                        setTimeout(run, delay);
                    } else if (pollData.status === 'completed') {
                        stopped = true;
                        progressBar.style.width = '100%';
                        progressText.innerText = '✅ Sincronización completada';
                        setTimeout(() => {
                            loadMappedTables();
                            progressArea.style.display = 'none';
                        }, 2000);
                    } else if (pollData.status === 'failed') {
                        stopped = true;
                        progressText.innerText = `❌ Error: ${pollData.message}`;
                        setTimeout(() => progressArea.style.display = 'none', 3000);
                    } else {
                        setTimeout(run, 2500);
                    }
                } catch (e) {
                    setTimeout(run, 2500);
                }
            };
            setTimeout(run, 2500);
        } else {
            progressText.innerText = `❌ Error: ${data.message}`;
            setTimeout(() => progressArea.style.display = 'none', 3000);
        }
    } catch (e) {
        console.error('Sync error', e);
        progressText.innerText = `❌ Error de conexión`;
        setTimeout(() => progressArea.style.display = 'none', 3000);
    }
}

/* --- NEW SYNC LOGIC --- */
async function triggerSync() {
    const btn = document.getElementById('btn-sync');
    const progressArea = document.getElementById('sync-progress-area');

    // [NEW] Smart Check: Prevent sync if nothing pending
    if (window._mappedSources) {
        const tabContainer = document.getElementById('tab-auto');
        const syncTypeRadio = tabContainer.querySelector('input[name="sync-type"]:checked');
        const syncType = syncTypeRadio ? syncTypeRadio.value : 'all';

        if (syncType === 'trained') {
            const tableCheckboxes = document.querySelectorAll('.chk-sync-table:checked');
            if (tableCheckboxes.length > 0) {
                console.log(`🚀 Forzando sincronización de ${tableCheckboxes.length} tablas seleccionadas.`);
            } else {
                const pendingTrained = window._mappedSources.filter(s =>
                    s.is_active === false || !s.last_sync
                );
                if (pendingTrained.length === 0) {
                    const modal = document.getElementById('sync-confirm-modal');
                    if (modal) {
                        modal.style.display = 'flex';
                        return;
                    }
                }
            }
        }
    }
    performSync();
}

async function loadSyncTables() {
    const container = document.getElementById('sync-tables-list');
    try {
        const empresaQuery = (typeof empresaListQuery === 'function') ? empresaListQuery() : '';
        const res = await fetch('/api/semantic/active-tables' + (empresaQuery ? `?${empresaQuery}` : ''));
        const data = await res.json();

        if (data.status === 'ok' && data.tables.length > 0) {
            container.innerHTML = data.tables.map(t => {
                const isVirtual = !t.physical_name;
                return `
                <label style="display: flex; align-items: center; gap: 0.75rem; padding: 8px; border-radius: 6px; cursor: pointer; transition: background 0.2s; min-width: 0;" onmouseover="this.style.background='rgba(255,255,255,0.05)'" onmouseout="this.style.background='transparent'">
                    <input type="checkbox" class="chk-sync-table" value="${t.id}" checked style="accent-color: #a855f7; width: 16px; height: 16px; flex-shrink: 0;">
                    <span style="color: #e4e4e7; font-size: 0.85rem; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        ${isVirtual ? '📡' : ''} ${t.name}
                    </span>
                    <span style="color: ${isVirtual ? '#60a5fa' : '#71717a'}; font-size: 0.75rem; margin-left: auto; flex-shrink: 0;">
                        ${isVirtual ? 'Virtual' : t.physical_name}
                    </span>
                </label>
            `}).join('');
        } else {
            container.innerHTML = '<div style="padding: 1rem; text-align: center; color: #71717a; font-size: 0.8rem;">No hay tablas configuradas.</div>';
        }
    } catch (e) {
        container.innerHTML = `<div style="padding: 1rem; text-align: center; color: #ef4444; font-size: 0.8rem;">Error: ${e.message}</div>`;
    }
}

function toggleSyncOptions() {
    const syncType = document.querySelector('input[name="sync-type"]:checked').value;
    const listContainer = document.getElementById('sync-tables-list-container');
    const stdContainer = document.getElementById('standard-tables-selector');

    if (syncType === 'trained' || syncType === 'all') {
        listContainer.style.display = 'block';
        if (document.getElementById('sync-tables-list').children.length <= 1) {
            loadSyncTables();
        }
    } else {
        listContainer.style.display = 'none';
    }
    if (stdContainer) stdContainer.style.display = (syncType === 'standard' || syncType === 'all') ? 'block' : 'none';
}

function goTrainPhrases() {
    if (typeof switchAutoTab === 'function') switchAutoTab('subtab-training');
}

function markSyncStep(step) {
    document.querySelectorAll('#sync-steps [data-step]').forEach(el => {
        const on = el.getAttribute('data-step') === step;
        el.style.borderColor = on ? '#10b981' : 'rgba(255,255,255,0.12)';
        el.style.color = on ? '#fff' : '#a1a1aa';
    });
}

async function prepareSyncScreen() {
    const hint = document.getElementById('sync-years-hint');
    const years = document.getElementById('inp-years-count');
    if (typeof loadSyncTables === 'function') loadSyncTables();
    const emp = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
    if (!emp) return;
    const yearBox = document.getElementById('sel-ejercicio');
    const year = yearBox ? yearBox.value : '';
    try {
        const res = await fetch(`/api/etl/sync/readiness?empresa_id=${encodeURIComponent(emp)}${year ? `&year=${encodeURIComponent(year)}` : ''}`);
        const data = await res.json();
        if (years && !years.dataset.userSet && data.suggested_years) {
            years.value = String(data.suggested_years);
        }
        if (hint) {
            if (data.job_running) {
                hint.textContent = 'Hay una copia en marcha. Espera a que termine antes de lanzar otra.';
            } else if (data.has_metrics) {
                const listed = (data.years || []).join(', ');
                hint.textContent = listed
                    ? `Ya hay totales de esta empresa (${listed}). Si no cambias el número, solo se actualizará el ejercicio seleccionado.`
                    : 'Ya hay totales de esta empresa. Si no cambias el número, solo se actualizará el ejercicio seleccionado.';
            } else {
                hint.textContent = 'Primera carga: se copian los ejercicios indicados. La siguiente vez bastará con el ejercicio nuevo.';
            }
        }
        const btn = document.getElementById('btn-sync');
        if (btn && data.job_running) {
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.innerText = 'Copia en marcha';
        }
    } catch (_) {}
}

async function showSyncResult() {
    const box = document.getElementById('sync-result');
    const emp = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
    if (!box || !emp) return;
    const yearBox = document.getElementById('sel-ejercicio');
    const year = yearBox ? yearBox.value : '';
    box.style.display = 'block';
    try {
        const res = await fetch(`/api/etl/sync/readiness?empresa_id=${encodeURIComponent(emp)}${year ? `&year=${encodeURIComponent(year)}` : ''}`);
        const data = await res.json();
        const listed = (data.years || []).join(', ') || 'ninguno';
        const ready = data.chat_ready
            ? `El chat ya puede leer los totales${year ? ` de ${year}` : ''}.`
            : 'El chat todavía no tiene totales de este ejercicio.';
        box.innerHTML = `<div style="padding:12px 14px; border:1px solid rgba(16,185,129,0.35); border-radius:10px; background:rgba(16,185,129,0.08);">
            <div>Totales guardados: ${data.metrics_rows}. Ejercicios: ${listed}.</div>
            <div style="margin-top:6px;">${ready}</div>
            <div style="margin-top:6px; color:#a1a1aa;">Las frases no se han entrenado. Usa el botón Entrenar frases cuando quieras.</div>
        </div>`;
    } catch (_) {
        box.textContent = 'La copia ha terminado. Abre Entrenar frases cuando quieras.';
    }
}

function toggleAllSyncTables() {
    const boxes = Array.from(document.querySelectorAll('.chk-sync-table'));
    const allOn = boxes.length > 0 && boxes.every(chk => chk.checked);
    boxes.forEach(chk => { chk.checked = !allOn; });
}

async function openPreviewMSSQL() {
    const modal = document.getElementById('mssql-preview-modal');
    const body = document.getElementById('mssql-preview-body');
    if (!modal || !body) return;
    const tabContainer = document.getElementById('tab-auto');
    const syncTypeRadio = tabContainer.querySelector('input[name="sync-type"]:checked');
    const syncType = syncTypeRadio ? syncTypeRadio.value : 'all';
    const stdVentas = document.getElementById('chk-std-ventas');
    const stdCompras = document.getElementById('chk-std-compras');
    const stdFin = document.getElementById('chk-std-financiera');
    const stdExist = document.getElementById('chk-std-existencias');
    const stdSelected = [];
    if (stdVentas && stdVentas.checked) stdSelected.push('ventas');
    if (stdCompras && stdCompras.checked) stdSelected.push('compras');
    if (stdFin && stdFin.checked) stdSelected.push('financiera');
    if (stdExist && stdExist.checked) stdSelected.push('existencias');
    const yearBox = document.getElementById('sel-ejercicio');
    const currentYear = yearBox ? yearBox.value : '';
    const params = [];
    if (currEmpresa) params.push(`empresa_id=${encodeURIComponent(currEmpresa)}`);
    if (currentYear) params.push(`year=${encodeURIComponent(currentYear)}`);
    params.push(`sync_type=${encodeURIComponent(syncType)}`);
    if (stdSelected.length) params.push(`standard_tables=${encodeURIComponent(stdSelected.join(','))}`);
    if (syncType === 'trained' || syncType === 'all') {
        const tableCheckboxes = document.querySelectorAll('.chk-sync-table:checked');
        const tableIds = Array.from(tableCheckboxes).map(chk => chk.value).join(',');
        if (tableIds) params.push(`table_ids=${encodeURIComponent(tableIds)}`);
    }
    const url = `/api/etl/preview_sources?${params.join('&')}`;
    body.innerHTML = '<div style="padding:1rem; text-align:center; color:#a1a1aa;">Cargando...</div>';
    modal.style.display = 'flex';
    try {
        const res = await fetch(url);
        const data = await res.json();
        if (!res.ok || data.status !== 'ok') {
            body.innerHTML = `<div style="padding:1rem; color:#ef4444;">${data.message || 'Error al consultar origen MSSQL.'}</div>`;
            return;
        }
        if (!data.entries || data.entries.length === 0) {
            body.innerHTML = '<div style="padding:1rem; color:#a1a1aa;">Sin resultados.</div>';
            return;
        }
        const rows = data.entries.map(e => {
            const dest = e.postgres_count == null ? '—' : e.postgres_count;
            return `<div style="display:grid; grid-template-columns: 180px 1fr 90px 1fr 90px; gap: 0.75rem; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06);">
                <div style="color:#a78bfa; font-weight:600; font-size:0.85rem;">${e.domain}</div>
                <div style="color:#e4e4e7; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${e.table}">${e.table}</div>
                <div style="text-align:right; color:#34d399; font-family:monospace;">${e.count}</div>
                <div style="color:#e4e4e7; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${e.postgres_table || ''}">${e.postgres_table || '—'}</div>
                <div style="text-align:right; color:#34d399; font-family:monospace;">${dest}</div>
            </div>`;
        }).join('');
        body.innerHTML = `<div style="display:grid; grid-template-columns: 180px 1fr 90px 1fr 90px; gap: 0.75rem; padding-bottom:8px; color:#a1a1aa; font-size:0.75rem;">
            <div>Dominio</div><div>SQL Server</div><div style="text-align:right;">Filas</div><div>Postgres</div><div style="text-align:right;">Filas</div>
        </div><div style="display:flex; flex-direction:column; gap:4px;">${rows}</div>`;
    } catch (e) {
        body.innerHTML = '<div style="padding:1rem; color:#ef4444;">Error de conexión.</div>';
    }
}

function closePreviewMSSQL() {
    const modal = document.getElementById('mssql-preview-modal');
    if (modal) modal.style.display = 'none';
}

async function performSync() {
    const btn = document.getElementById('btn-sync');
    const progressArea = document.getElementById('sync-progress-area');
    const progressText = document.getElementById('sync-status-text');
    const progressBar = document.getElementById('sync-progress-bar');

    document.getElementById('sync-confirm-modal').style.display = 'none';

    btn.disabled = true;
    btn.style.opacity = '0.5';
    progressArea.style.display = 'block';

    try {
        const tabContainer = document.getElementById('tab-auto');
        const syncTypeRadio = tabContainer.querySelector('input[name="sync-type"]:checked');
        const syncType = syncTypeRadio ? syncTypeRadio.value : 'all';

        const syncData = document.getElementById('chk-sync-data').checked;
        const tableCheckboxes = document.querySelectorAll('.chk-sync-table:checked');
        const tableIds = Array.from(tableCheckboxes).map(chk => chk.value).join(',');

        const stdVentas = document.getElementById('chk-std-ventas');
        const stdCompras = document.getElementById('chk-std-compras');
        const stdFin = document.getElementById('chk-std-financiera');
        const stdExist = document.getElementById('chk-std-existencias');
        const stdSelected = [];
        if (stdVentas && stdVentas.checked) stdSelected.push('ventas');
        if (stdCompras && stdCompras.checked) stdSelected.push('compras');
        if (stdFin && stdFin.checked) stdSelected.push('financiera');
        if (stdExist && stdExist.checked) stdSelected.push('existencias');
        if (syncType === 'standard' && stdSelected.length === 0) {
            if (typeof showToast === 'function') showToast('Debe seleccionar al menos una tabla estándar.');
            btn.disabled = false;
            btn.style.opacity = '1';
            progressArea.style.display = 'none';
            return;
        }
        const stdParam = (syncType === 'all' || syncType === 'standard')
            ? `standard_tables=${encodeURIComponent(stdSelected.join(','))}`
            : '';

        const empParam = currEmpresa ? `empresa_id=${encodeURIComponent(currEmpresa)}` : '';
        const syncParam = `sync_type=${syncType}`;
        const dataParam = `sync_data=${syncData}`;
        const tablesParam = tableIds ? `table_ids=${encodeURIComponent(tableIds)}` : '';

        // [NEW] Get selected Year for History Limitation
        const yearBox = document.getElementById('sel-ejercicio');
        const currentYear = yearBox ? yearBox.value : '';
        const yearParam = currentYear ? `year=${encodeURIComponent(currentYear)}` : '';
        const yearsBox = document.getElementById('inp-years-count');
        const yearsVal = yearsBox ? String(yearsBox.value || '').trim() : '';
        const yearsParam = yearsVal ? `years_count=${encodeURIComponent(yearsVal)}` : '';
        const fastBulk = localStorage.getItem('datia-fast-bulk') === 'true';
        const fastParam = `fast_bulk=${fastBulk}`;
        const queryString = [empParam, syncParam, dataParam, tablesParam, yearParam, yearsParam, fastParam, stdParam].filter(p => p).join('&');

        // [NEW] Optional pre-drop físico (Forzar carga desde 0) para Entrenadas
        const forceResetEl = document.getElementById('chk-force-reset');
        const forceReset = !!(forceResetEl && forceResetEl.checked);
        let resetIds = tableIds;
        if (forceReset && !resetIds && (syncType === 'trained' || syncType === 'all') && document.querySelectorAll('.chk-sync-table').length === 0) {
            try {
                const empresaQuery = (typeof empresaListQuery === 'function') ? empresaListQuery() : '';
                const listRes = await fetch('/api/semantic/active-tables' + (empresaQuery ? `?${empresaQuery}` : ''));
                const listData = await listRes.json();
                resetIds = (listData.tables || []).filter(t => t.physical_name).map(t => t.id).join(',');
            } catch (_) {}
        }
        if (forceReset && resetIds && (syncType === 'trained' || syncType === 'all')) {
            try {
                progressText.innerText = 'Forzando reset físico de tablas seleccionadas...';
                const preRes = await fetch(`/api/etl/drop_physical?table_ids=${encodeURIComponent(resetIds)}`, { method: 'POST' });
                let preData = {};
                try { preData = await preRes.json(); } catch (_) {}
                if (preRes.ok && preData.status === 'ok') {
                    if (typeof showToast === 'function') showToast(`🔄 Reset físico aplicado (${preData.dropped.length})`);
                } else {
                    if (typeof showToast === 'function') showToast(`⚠️ No se pudo forzar el reset físico`);
                }
            } catch (e) {
                if (typeof showToast === 'function') showToast('⚠️ Error al forzar reset físico');
            }
        }

        const forceParam = forceReset ? 'force_reset=true' : '';
        const qsFinal = [queryString, forceParam].filter(Boolean).join('&');
        const res = await fetch(`/api/etl/sync?${qsFinal}`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'busy') {
            if (typeof showToast === 'function') showToast(data.message || 'Ya hay una copia en marcha.');
            btn.disabled = true;
            btn.style.opacity = '0.5';
            btn.innerText = 'Copia en marcha';
            return;
        }
        if (data.status === 'started') {
            const jobId = data.job_id;
            const jobStart = Date.now();
            markSyncStep('copy');
            try { if (forceReset && window.__snapshotCache) window.__snapshotCache = {}; } catch (_) {}
            let stopped = false;
            const run = async () => {
                if (stopped) return;
                try {
                    const pollRes = await fetch(`/api/etl/status/${jobId}`);
                    const pollData = await pollRes.json();
                    if (pollData.status === 'running' || pollData.status === 'starting') {
                        const progress = Number(pollData.progress || 0);
                        progressBar.style.width = `${progress}%`;
                        let extra = '';
                        try {
                            const match = /(\d+)\s*\/\s*(\d+)/.exec(pollData.message || '');
                            if (match) {
                                const copied = parseInt(match[1], 10);
                                const total = parseInt(match[2], 10);
                                const remaining = Math.max(0, total - copied);
                                extra += ` · Restantes: ${remaining}`;
                            }
                        } catch (_) {}
                        if (progress > 0 && progress < 100) {
                            const elapsed = Date.now() - jobStart;
                            const totalMs = (elapsed * 100) / progress;
                            const remainingMs = Math.max(0, totalMs - elapsed);
                            const fmt = (ms) => {
                                const s = Math.round(ms / 1000);
                                const m = Math.floor(s / 60);
                                const ss = s % 60;
                                return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
                            };
                            extra += ` · ETA: ${fmt(remainingMs)}`;
                        }
                        const msg = pollData.message || '';
                        if (/m[eé]trica/i.test(msg)) markSyncStep('metrics');
                        else markSyncStep('copy');
                        progressText.innerText = `${msg} (${progress}%)${extra}`;
                        const delay = progress >= 90 ? 1000 : 2500;
                        setTimeout(run, delay);
                    } else if (pollData.status === 'completed') {
                        stopped = true;
                        progressBar.style.width = '100%';
                        markSyncStep('metrics');
                        progressText.innerText = 'Copia y totales terminados. Las frases se entrenan en el siguiente paso.';
                        btn.innerText = 'Totales listos';
                        btn.disabled = false;
                        btn.style.opacity = '1';
                        showSyncResult();
                    } else if (pollData.status === 'error') {
                        stopped = true;
                        progressText.innerText = `Error: ${pollData.error}`;
                        progressText.style.color = '#ef4444';
                        btn.disabled = false;
                        btn.style.opacity = '1';
                    } else {
                        setTimeout(run, 2500);
                    }
                } catch (e) {
                    setTimeout(run, 2500);
                }
            };
            setTimeout(run, 2500);
        } else {
            if (typeof showToast === 'function') showToast("❌ Error al iniciar sincronización.");
            btn.disabled = false;
            btn.style.opacity = '1';
        }
    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') showToast("❌ Error de conexión.");
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

/* --- NUCLEAR MODAL LOGIC --- */
function showNuclearModal(tableName, onConfirm, onCancel) {
    const msgEl = document.getElementById('nuclear-modal-msg');
    if (msgEl) {
        msgEl.innerHTML =
            `Estás a punto de REINICIAR la tabla <br><strong style="color:#fff">${tableName}</strong>.<br><br>` +
            `Esto es una acción destructiva que:<br>` +
            `1. 💥 Eliminará la tabla física en la base de datos.<br>` +
            `2. 🗑️ Borrará toda la configuración de mapeo.<br><br>` +
            `Tendrás que volver a mapear y sincronizar.`;
    }

    document.getElementById('nuclear-confirm-modal').style.display = 'flex';

    window.confirmNuclearAction = () => {
        document.getElementById('nuclear-confirm-modal').style.display = 'none';
        if (onConfirm) onConfirm();
    };

    window.cancelNuclearAction = () => {
        if (onCancel) onCancel();
    };
}

function closeNuclearModal() {
    document.getElementById('nuclear-confirm-modal').style.display = 'none';
    if (window.cancelNuclearAction) window.cancelNuclearAction();
}

async function triggerIncrementalCartera() {
    const emp = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
    if (!emp) {
        if (typeof showToast === 'function') showToast('Seleccione empresa.');
        return;
    }
    const year = (typeof currEjercicio !== 'undefined' && currEjercicio) ? parseInt(currEjercicio, 10) : new Date().getFullYear();
    try {
        const qs = `empresa_id=${encodeURIComponent(emp)}&year=${encodeURIComponent(year)}`;
        const res = await fetch(`/api/etl/incremental/cartera?${qs}`, { method: 'POST' });
        let data = {};
        try { data = await res.json(); } catch (_) {}
        if (res.status === 400) {
            if (typeof showToast === 'function') showToast(data.message || 'Baseline requerido para Cartera.');
            showBaselinePrompt('cartera');
            return;
        }
        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast('Cartera incrementada correctamente.');
        } else {
            if (typeof showToast === 'function') showToast('Error en incremental de cartera.');
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('Error de conexión en cartera.');
    }
}

async function triggerIncrementalStocks() {
    const emp = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
    if (!emp) {
        if (typeof showToast === 'function') showToast('Seleccione empresa.');
        return;
    }
    const year = (typeof currEjercicio !== 'undefined' && currEjercicio) ? parseInt(currEjercicio, 10) : new Date().getFullYear();
    try {
        const qs = `empresa_id=${encodeURIComponent(emp)}&year=${encodeURIComponent(year)}`;
        const res = await fetch(`/api/etl/incremental/stocks?${qs}`, { method: 'POST' });
        let data = {};
        try { data = await res.json(); } catch (_) {}
        if (res.status === 400) {
            if (typeof showToast === 'function') showToast(data.message || 'Baseline requerido para Existencias.');
            showBaselinePrompt('existencias');
            return;
        }
        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast('Existencias actualizadas incrementales.');
        } else {
            if (typeof showToast === 'function') showToast('Error en incremental de existencias.');
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('Error de conexión en existencias.');
    }
}

function showBaselinePrompt(domain) {
    const modal = document.getElementById('sync-confirm-modal');
    if (!modal) return;
    const card = modal.querySelector('.glass-card');
    if (!card) return;
    const iconEl = card.querySelector('div');
    const titleEl = card.querySelector('h3');
    const pEl = card.querySelector('p');
    const btns = card.querySelectorAll('button');
    if (iconEl) iconEl.textContent = '⚠️';
    if (titleEl) titleEl.textContent = 'Baseline requerido';
    if (pEl) pEl.textContent = `Se requiere Baseline de ${domain}. ¿Desea iniciarlo ahora?`;
    if (btns && btns[0]) btns[0].onclick = () => { modal.style.display = 'none'; };
    if (btns && btns[1]) {
        btns[1].textContent = 'Iniciar Baseline';
        btns[1].onclick = () => { modal.style.display = 'none'; runBaseline(domain); };
    }
    modal.style.display = 'flex';
}

async function runBaseline(domain) {
    const emp = typeof currEmpresa !== 'undefined' ? currEmpresa : '';
    if (!emp) { if (typeof showToast === 'function') showToast('Seleccione empresa.'); return; }
    const year = (typeof currEjercicio !== 'undefined' && currEjercicio) ? parseInt(currEjercicio, 10) : new Date().getFullYear();
    const progressArea = document.getElementById('sync-progress-area');
    const progressText = document.getElementById('sync-status-text');
    const progressBar = document.getElementById('sync-progress-bar');
    progressArea.style.display = 'block';
    const fastBulk = localStorage.getItem('datia-fast-bulk') === 'true';
    const qs = [
        `empresa_id=${encodeURIComponent(emp)}`,
        `sync_type=standard`,
        `standard_tables=${encodeURIComponent(domain)}`,
        `year=${encodeURIComponent(year)}`,
        `fast_bulk=${fastBulk}`
    ].join('&');
    try {
        const res = await fetch(`/api/etl/sync?${qs}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'started') {
            const jobId = data.job_id;
            const jobStart = Date.now();
            const run = async () => {
                try {
                    const pollRes = await fetch(`/api/etl/status/${jobId}`);
                    const pollData = await pollRes.json();
                    if (pollData.status === 'running' || pollData.status === 'starting') {
                        const progress = Number(pollData.progress || 0);
                        progressBar.style.width = `${progress}%`;
                        let extra = '';
                        try {
                            const match = /(\d+)\s*\/\s*(\d+)/.exec(pollData.message || '');
                            if (match) {
                                const copied = parseInt(match[1], 10);
                                const total = parseInt(match[2], 10);
                                const remaining = Math.max(0, total - copied);
                                extra += ` · Restantes: ${remaining}`;
                            }
                        } catch (_) {}
                        if (progress > 0 && progress < 100) {
                            const elapsed = Date.now() - jobStart;
                            const totalMs = (elapsed * 100) / progress;
                            const remainingMs = Math.max(0, totalMs - elapsed);
                            const fmt = (ms) => {
                                const s = Math.round(ms / 1000);
                                const m = Math.floor(s / 60);
                                const ss = s % 60;
                                return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
                            };
                            extra += ` · ETA: ${fmt(remainingMs)}`;
                        }
                        progressText.innerText = `${pollData.message} (${progress}%)${extra}`;
                        const delay = progress >= 90 ? 1000 : 2500;
                        setTimeout(run, delay);
                    } else if (pollData.status === 'completed') {
                        progressBar.style.width = '100%';
                        progressText.innerText = '✅ Baseline completado';
                        setTimeout(() => { progressArea.style.display = 'none'; }, 1500);
                        if (typeof showToast === 'function') showToast('✅ Baseline completado.');
                    } else {
                        setTimeout(run, 2500);
                    }
                } catch (_) {
                    setTimeout(run, 2500);
                }
            };
            setTimeout(run, 1500);
        } else {
            if (typeof showToast === 'function') showToast('❌ Error al iniciar baseline.');
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('❌ Error de conexión al iniciar baseline.');
    }
}
