/* --- tab_auto_mapping.js --- */
/* Mapping, Semantics, Filters */

async function loadMappedTables() {
    ensureFilterUI();
    const container = document.getElementById('mapped-tables-list');
    if (!container) return;

    container.innerHTML = '<div style="color: #a1a1aa; font-size: 0.8rem; text-align: center; padding: 1rem;">Cargando...</div>';

    try {
        const empresaQuery = (typeof empresaListQuery === 'function') ? empresaListQuery() : '';
        const res = await fetch('/api/semantic/mapped-sources' + (empresaQuery ? `?${empresaQuery}` : ''));
        const data = await res.json();

        if (data.status === 'ok' && data.sources.length > 0) {
            const seen = new Set();
            window._mappedSources = data.sources.filter(s => {
                const key = String(s.table || s.name || '').trim().toLowerCase();
                if (!key || seen.has(key)) return false;
                seen.add(key);
                return true;
            });
            renderMappedList();
        } else {
            // Empty state
            container.innerHTML = `
                    <div style="text-align: center; padding: 2rem 1rem; color: #71717a; font-size: 0.85rem;">
                        <div style="font-style: italic;">${data.message || 'No hay tablas mapeadas aún.'}</div>
                    </div>
                `;
        }
    } catch (e) {
        console.warn("Could not load mapped tables", e);
        container.innerHTML = `<div style="text-align: center; padding: 1rem; color: #ef4444; font-size: 0.8rem;">⚠️ Error al cargar tablas: ${e.message}</div>`;
    }
}

/* --- FILTER UI LOGIC --- */
function ensureFilterUI() {
    const container = document.getElementById('mapped-tables-list');
    if (!container) return;

    if (document.getElementById('map-filter-controls')) return;

    const filterHTML = `
        <div id="map-filter-controls" class="map-filter-group">
            <div class="map-filter-label">Vista:</div>
            <button onclick="applyMapFilter('all')" id="btn-filter-all" class="map-filter-btn active" aria-selected="true">Todas</button>
            <button onclick="applyMapFilter('physical')" id="btn-filter-physical" class="map-filter-btn">💾 Migradas</button>
            <button onclick="applyMapFilter('virtual')" id="btn-filter-virtual" class="map-filter-btn">📡 Virtuales</button>
        </div>
    `;
    container.insertAdjacentHTML('beforebegin', filterHTML);
    applyMapFilter(window.currentMapFilter || 'all');
}

window.currentMapFilter = 'all';

function applyMapFilter(type) {
    window.currentMapFilter = type;
    document.querySelectorAll('.map-filter-btn').forEach(btn => {
        btn.classList.remove('active');
        btn.removeAttribute('aria-selected');
    });
    const activeBtn = document.getElementById(`btn-filter-${type}`);
    if (activeBtn) {
        activeBtn.classList.add('active');
        activeBtn.setAttribute('aria-selected', 'true');
    }
    renderMappedList();
}

function renderMappedList() {
    const container = document.getElementById('mapped-tables-list');
    if (!container || !window._mappedSources) return;

    const allSources = window._mappedSources;
    let sourcesToShow = [];

    if (window.currentMapFilter === 'all') {
        sourcesToShow = allSources;
    } else if (window.currentMapFilter === 'physical') {
        sourcesToShow = allSources.filter(s => !s.is_virtual);
    } else if (window.currentMapFilter === 'virtual') {
        sourcesToShow = allSources.filter(s => s.is_virtual);
    }

    if (sourcesToShow.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:2rem; color:#52525b; font-size:0.8rem;">No hay tablas para este filtro.</div>`;
        return;
    }

    const physicalSources = sourcesToShow.filter(s => !s.is_virtual);
    const virtualSources = sourcesToShow.filter(s => s.is_virtual);

    const renderCard = (s, isVirtual) => {
        // Simplified status: PEND if not active (needs sync), SYNC if active (synced)
        const isPending = !s.is_active;
        const statusBadge = isPending ? '🔄 PEND' : '✅ SYNC';
        const statusColor = isPending ? '#f59e0b' : '#10b981';
        const statusBg = isPending ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)';

        let syncDateInfo = '';
        if (s.last_sync) {
            const date = new Date(s.last_sync);
            const formatted = date.toLocaleString('es-ES', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
            syncDateInfo = `<div style="font-size: 0.7rem; color: #71717a; margin-top: 4px;">
                    📅 ${formatted}
                </div>`;
        }


        return `
            <div onclick="restoreMapping('${s.table}')" class="mapped-table-card"
                    style="cursor: pointer; padding: 1.25rem; margin-bottom: 0.75rem; 
                        background: ${isVirtual ? 'rgba(59, 130, 246, 0.03)' : 'rgba(139, 92, 246, 0.03)'};
                        border: 1px solid ${isVirtual ? 'rgba(59, 130, 246, 0.1)' : 'rgba(139, 92, 246, 0.1)'}; 
                        border-radius: 12px; color: #e4e4e7; transition: all 0.2s ease; position: relative;"
                    onmouseover="this.style.background='${isVirtual ? 'rgba(59, 130, 246, 0.08)' : 'rgba(139, 92, 246, 0.08)'}'; this.style.borderColor='${isVirtual ? 'rgba(59, 130, 246, 0.25)' : 'rgba(139, 92, 246, 0.25)'}'; this.querySelector('.delete-btn').style.display='inline-block';"
                    onmouseout="this.style.background='${isVirtual ? 'rgba(59, 130, 246, 0.03)' : 'rgba(139, 92, 246, 0.03)'}'; this.style.borderColor='${isVirtual ? 'rgba(59, 130, 246, 0.1)' : 'rgba(139, 92, 246, 0.1)'}'; this.querySelector('.delete-btn').style.display='none';">

                <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                    <span style="font-size: 1.5rem; line-height: 1;">${isVirtual ? '📡' : '💾'}</span>
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-weight: 600; font-size: 1.05rem; color: #fff; line-height: 1.3;">
                            ${s.name || s.table}
                        </div>
                        <div style="font-size: 0.75rem; color: #a1a1aa; font-family: monospace; margin-top: 2px;">
                            ${s.table}
                        </div>
                    </div>
                </div>

                <div onclick="event.stopPropagation()" style="display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        ${isVirtual ? '<span style="font-size:0.65rem; font-weight:700; padding:4px 8px; border-radius:6px; background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.3); text-transform:uppercase;">VIRTUAL</span>' : ''}
                        
                        <span style="font-size:0.65rem; font-weight:700; padding:4px 8px; border-radius:6px; background:${statusBg}; color:${statusColor}; border:1px solid ${statusColor}33; text-transform:uppercase;">
                            ${statusBadge}
                        </span>
                        
                        ${syncDateInfo}
                    </div>
                    
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <button onclick="event.stopPropagation(); reindexTable(${s.id}, '${(s.name || s.table).replace(/'/g, "\\'")}');" 
                                title="Regenerar preguntas de ejemplo"
                                style="background: #7c3aed; border: 1px solid #a855f7; color: #fff; padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.background='#6d28d9'" 
                                onmouseout="this.style.background='#7c3aed'">
                            ⚡ Re-Entrenar
                        </button>
                        
                        <button class="delete-btn" 
                                onclick="event.stopPropagation(); showNuclearModal('${s.table}', () => resetTable(${s.id}));" 
                                title="Eliminar tabla"
                                style="display: none; background: #ef4444; border: 1px solid #dc2626; color: #fff; padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                                onmouseover="this.style.background='#dc2626'" 
                                onmouseout="this.style.background='#ef4444'">
                            🗑️ Eliminar
                        </button>
                    </div>
                </div>
            </div>
        `;
    };
    let html = '';

    if (physicalSources.length > 0) {
        html += `<div style="color: #a1a1aa; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin: 1.5rem 0 0.75rem 0; padding-left: 4px;">Tablas Físicas (DatiaDB)</div>`;
        html += physicalSources.map(s => renderCard(s, false)).join('');
    }

    if (virtualSources.length > 0) {
        html += `<div style="color: #60a5fa; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin: 2rem 0 0.75rem 0; padding-left: 4px;">Tablas Virtuales (Conexión Directa)</div>`;
        html += virtualSources.map(s => renderCard(s, true)).join('');
    }

    container.innerHTML = html;
}

function restoreMapping(tableName) {
    const sel = document.getElementById('sel-source-table');
    sel.value = tableName;
    // If value not in list (search filter?), we might need to add it or reset filter
    if (sel.value !== tableName) {
        // Force add option if missing
        const opt = document.createElement('option');
        opt.value = tableName;
        opt.text = tableName;
        sel.add(opt);
        sel.value = tableName;
    }
    loadColumns();
}

async function loadTables() {
    const sel = document.getElementById('sel-source-table');
    sel.innerHTML = '<option>Cargando...</option>';

    // Trigger loading mapped tables list too
    loadMappedTables();

    try {
        const titleSelect = document.getElementById('sel-source-table');
        const currentVal = titleSelect.value; // Capture current selection (if any)

        const res = await fetch('/api/semantic/tables');
        const data = await res.json();
        if (data.status === 'ok') {
            // Sort alphabetically
            data.tables.sort();
            titleSelect.innerHTML = '<option value="">-- Selecciona una tabla --</option>' +
                data.tables.map(t => `<option value="${t}">${t}</option>`).join('');

            // Restore selection if it existed and is valid (or force add it back?)
            if (currentVal && currentVal !== 'Cargando...') {
                titleSelect.value = currentVal;
                // If value didn't stick (not in new list), forcing it is tricky without adding option.
                // But usually mapped tables ARE in the list.
                if (titleSelect.value !== currentVal) {
                    // Re-add it
                    const opt = document.createElement('option');
                    opt.value = currentVal;
                    opt.text = currentVal;
                    titleSelect.add(opt);
                    titleSelect.value = currentVal;
                }
            }

        } else {
            console.error("API Error:", data.message);
            titleSelect.innerHTML = `< option > Error: ${data.message}</option > `;
        }
    } catch (e) {
        console.error(e);
        const titleSelect = document.getElementById('sel-source-table');
        if (titleSelect) titleSelect.innerHTML = '<option>Error de conexión</option>';
    }
}

async function loadColumns() {
    const table = document.getElementById('sel-source-table').value;
    const container = document.getElementById('fields-container');
    const editor = document.getElementById('mapping-editor');

    // Reset Progress UI
    const progWrapper = document.getElementById('gen-progress-wrapper');
    if (progWrapper) progWrapper.style.display = 'none';
    const progBar = document.getElementById('gen-progress-bar');
    if (progBar) progBar.style.width = '0%';
    const detailText = document.getElementById('gen-detail-text');
    if (detailText) detailText.innerText = '';

    if (!table) {
        editor.style.display = 'none';
        return;
    }

    editor.style.display = 'block';
    container.innerHTML = '<div style="padding:2rem; text-align:center;">Cargando columnas...</div>';

    // Auto preset business name
    document.getElementById('business-table-name').value = table;

    // Display Active Model
    const activeModel = localStorage.getItem('datia-semantic-model') || 'Default (qwen2.5:3b)';
    const modelDisplay = document.getElementById('semantic-model-display');
    if (modelDisplay) {
        modelDisplay.innerText = `Modelo: ${activeModel} `;
        modelDisplay.title = "Configurable en Opciones de Desarrollador";
    }

    try {
        const safeTable = encodeURIComponent(table);
        let emp = '';
        try { 
            if (typeof getCurrentEmpresa === 'function') {
                emp = getCurrentEmpresa();
            } else if (typeof currEmpresa !== 'undefined') {
                emp = currEmpresa;
            }
        } catch (e) {}
        const hasEmp = emp && /^\d+$/.test(String(emp));
        const url = hasEmp 
            ? `/api/semantic/columns/${safeTable}?empresa=${emp}` 
            : `/api/semantic/columns/${safeTable}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error("Status " + res.status);

        const data = await res.json();

        if (data.status === 'ok') {
            // Populate Table Metadata (Context) if available
            if (data.table_metadata) {
                if (data.table_metadata.description) {
                    document.getElementById('table-context').value = data.table_metadata.description;
                }
                if (data.table_metadata.business_name) {
                    document.getElementById('business-table-name').value = data.table_metadata.business_name;
                }
            }

            // NF-016: Load is_virtual checkbox state
            const isVirtual = data.is_virtual || false;
            document.getElementById('chk-is-virtual').checked = isVirtual;

            if (data.columns.length === 0) {
                container.innerHTML = '<div style="padding:2rem; text-align:center; color: #f59e0b;">No se encontraron columnas en esta tabla.</div>';
                return;
            }
            container.innerHTML = data.columns.map((col, idx) => {

                const isMapped = col.is_mapped;
                const isActive = col.is_active;
                // Fix: Checkbox reflects "I want this synced" (Active), not "It is physically there" (Mapped)
                const isChecked = isActive;

                // Style logic...
                const rowStyle = isMapped
                    ? 'border-left: 3px solid #10b981; background: rgba(16, 185, 129, 0.05);'
                    : (isActive ? 'border-left: 3px solid #f59e0b; background: rgba(245, 158, 11, 0.05);' : 'border-left: 3px solid transparent;');

                return `
        <div class="field-row" data-status="${isMapped ? 'migrated' : 'pending'}" style="display: grid; grid-template-columns: 40px 1fr 1fr 2fr 100px 120px 50px; gap: 0.8rem; padding: 0.8rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); align-items: start; ${rowStyle}">
                        <div style="display: flex; justify-content: center;">
                            <input type="checkbox" class="chk-field" data-idx="${idx}" ${isChecked ? 'checked' : ''} style="accent-color: var(--accent);">
                        </div>
                        <div style="font-family: monospace; color: ${isMapped ? '#d1d5db' : '#a1a1aa'}; font-size: 0.85rem; word-break: break-all;">
                            ${col.name}
                            ${isMapped ? '<span style="font-size:0.7rem; color:#10b981; display:block;">(Migrado)</span>' : ''}
                            ${col.is_auto_detected ? '<span style="font-size:0.65rem; color:#a78bfa; border:1px solid #a78bfa; border-radius:3px; padding:0 2px; margin-top:2px; display:inline-block;" title="Detectado automáticamente por Repositorio Global">✨ Auto-Detect</span>' : ''}
                            <input type="hidden" class="inp-orig" value="${col.name}">
                            <input type="hidden" class="inp-type" value="${col.type}">
                        </div>
                        <div>
                            <input type="text" class="inp-bus" placeholder="${col.name}" value="${col.business_name || col.name}" 
                                style="width: 100%; background: rgba(0,0,0,0.2); border: 1px solid #3f3f46; border-radius: 4px; color: #fff; padding: 4px 8px; font-size: 0.85rem;">
                        </div>
                        <div>
                            <textarea class="inp-desc" placeholder="Qué significa este dato..." rows="1" oninput="this.style.color='#ffffff'"
                                style="width: 100%; background: rgba(0,0,0,0.2); border: 1px solid #3f3f46; border-radius: 4px; color: ${col.description ? '#ffffff' : '#a1a1aa'}; padding: 4px 8px; font-size: 0.85rem; resize: vertical;">${col.description || ''}</textarea>
                        </div>
                        <div>
                            <select class="inp-usage" style="width: 100%; background: #18181b; border: 1px solid #52525b; border-radius: 4px; color: #fff; padding: 4px; font-size: 0.8rem;">
                                <option value="dimension" ${col.usage === 'dimension' ? 'selected' : ''}>Agrupador</option>
                                <option value="metric" ${col.usage === 'metric' ? 'selected' : ''}>Métrica</option>
                                <option value="date" ${col.usage === 'date' ? 'selected' : ''}>Fecha</option>
                                <option value="data" ${(col.usage === 'data' || col.usage === 'none') ? 'selected' : ''}>Dato</option>
                            </select>
                        </div>
                        <div>
                            <select class="inp-meta" style="width: 100%; background: #18181b; border: 1px solid #52525b; border-radius: 4px; color: #fff; padding: 4px; font-size: 0.8rem;">
                                <option value="Standard" ${col.metadata === 'Standard' ? 'selected' : ''}>Estándar</option>
                                <option value="General" ${col.metadata === 'General' ? 'selected' : ''}>General</option>
                                <option value="Finanzas" ${col.metadata === 'Finanzas' ? 'selected' : ''}>Finanzas</option>
                                <option value="RRHH" ${col.metadata === 'RRHH' ? 'selected' : ''}>RRHH</option>
                                <option value="Comercial" ${col.metadata === 'Comercial' ? 'selected' : ''}>Comercial</option>
                                <option value="Sensible" ${col.metadata === 'Sensible' ? 'selected' : ''}>Sensible</option>
                            </select>
                        </div>
                            <div style="display: flex; justify-content: center;">
                            <input type="checkbox" class="inp-key" title="Es Clave Primaria" ${col.is_key ? 'checked' : ''} 
                                style="accent-color: #f59e0b; width: 16px; height: 16px; cursor: pointer;">
                        </div>
                    </div>
    `;
            }).join('');
        } else {
            container.innerHTML = `< div style = "padding:1rem; color:#ef4444;" > Error API: ${data.message}</div > `;
        }
    } catch (e) {
        console.error(e);
        container.innerHTML = `< div style = "padding:1rem; color:#ef4444;" > Error de conexión: ${e.message}</div > `;
    }
}

async function autoGenerateSemantics() {
    const btn = document.getElementById('btn-auto-gen');
    const table = document.getElementById('sel-source-table').value;
    const context = document.getElementById('table-context').value;
    const rows = document.querySelectorAll('.field-row');

    if (!table) {
        if (typeof showToast === 'function') showToast("⚠️ Por favor, selecciona una tabla.");
        return;
    }

    const fieldsToProcess = [];
    let checkedCount = 0;

    rows.forEach(row => {
        if (row.style.display === 'none') return; // Skip hidden logic

        const chk = row.querySelector('.chk-field');
        if (chk.checked) checkedCount++;

        const currentDesc = row.querySelector('.inp-desc').value.trim();

        if (chk.checked && currentDesc === "") {
            const busName = row.querySelector('.inp-bus').value;
            const origName = row.querySelector('.inp-orig').value;
            fieldsToProcess.push({
                id: origName,
                label: busName || origName,
                type: row.querySelector('.inp-type').value
            });
        }
    });

    if (fieldsToProcess.length === 0) {
        if (checkedCount > 0) {
            if (typeof showToast === 'function') showToast("⚠️ Los campos ya tienen descripción. Borra el texto para regenerarla.");
        } else {
            if (typeof showToast === 'function') showToast("⚠️ Selecciona al menos un campo.");
        }
        btn.innerHTML = '✨ Auto-Generar Semántica';
        btn.disabled = false;
        return;
    }

    // BATCH PROCESSING
    const total = fieldsToProcess.length;
    const BATCH_SIZE = total < 10 ? 1 : 5;
    let processed = 0;
    let successCount = 0;

    btn.disabled = true;

    try {
        const progWrapper = document.getElementById('gen-progress-wrapper');
        const progBar = document.getElementById('gen-progress-bar');
        const detailText = document.getElementById('gen-detail-text');

        progWrapper.style.display = 'block';
        progBar.style.width = '0%';
        detailText.innerText = 'Inicializando motor semántico...';

        for (let i = 0; i < total; i += BATCH_SIZE) {
            const chunk = fieldsToProcess.slice(i, i + BATCH_SIZE);
            const currentPercent = Math.round(((processed + chunk.length) / total) * 100);

            btn.innerHTML = `✨ Generando... ${currentPercent}% `;
            progBar.style.width = `${currentPercent}% `;
            const fieldNames = chunk.map(f => f.id).join(', ');
            detailText.innerText = `✨ Analizando: ${fieldNames}...`;

            const activeRowElements = [];
            chunk.forEach(field => {
                rows.forEach(r => {
                    if (r.querySelector('.inp-orig').value === field.id) {
                        r.classList.add('generating-active');
                        const ta = r.querySelector('.inp-desc');
                        ta.value = "⚡ Pensando...";
                        ta.classList.add('thinking-text');
                        if (i === 0 || i % 10 === 0) {
                            r.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                        activeRowElements.push({ row: r, input: ta });
                    }
                });
            });

            try {
                const semanticModel = localStorage.getItem('datia-semantic-model') || '';
                const res = await fetch('/api/semantic/generate-metadata', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        table_name: table,
                        table_context: context,
                        fields: chunk,
                        model: semanticModel,
                        empresa_id: (function(){ 
                            try { 
                                const e = (typeof getCurrentEmpresa === 'function') ? getCurrentEmpresa() : (typeof currEmpresa !== 'undefined' ? currEmpresa : ''); 
                                return /^\d+$/.test(String(e)) ? parseInt(e, 10) : null; 
                            } catch(_){ return null; } 
                        })()
                    })
                });

                const data = await res.json();

                if (data.status === 'ok' && data.descriptions) {
                    rows.forEach(row => {
                        const origName = row.querySelector('.inp-orig').value;
                        let description = data.descriptions[origName];

                        if (!description) {
                            const lowerOrig = origName.toLowerCase();
                            const foundKey = Object.keys(data.descriptions).find(k => k.toLowerCase() === lowerOrig);
                            if (foundKey) description = data.descriptions[foundKey];
                        }

                        if (description) {
                            const descInput = row.querySelector('.inp-desc');
                            descInput.value = description;
                            row.classList.remove('generating-active');
                            descInput.classList.remove('thinking-text');
                            descInput.style.color = '#fff';
                            row.animate([
                                { backgroundColor: 'rgba(52, 211, 153, 0.3)' },
                                { backgroundColor: 'transparent' }
                            ], { duration: 800 });
                            successCount++;
                        } else {
                            const descInput = row.querySelector('.inp-desc');
                            row.classList.remove('generating-active');
                            descInput.classList.remove('thinking-text');
                            if (descInput.value === "⚡ Pensando...") {
                                descInput.value = "";
                                descInput.placeholder = "No se pudo generar. Inténtalo de nuevo.";
                            }
                        }
                    });
                }
            } catch (err) {
                console.error("Batch error", err);
                activeRowElements.forEach(item => {
                    item.row.classList.remove('generating-active');
                    item.input.classList.remove('thinking-text');
                    item.input.value = "";
                });
            }
            processed += chunk.length;
            await new Promise(r => setTimeout(r, 100));
        }

        if (successCount > 0) {
            showStatus(`✅ Proceso finalizado.${successCount} campos generados.`, 'success');
        } else {
            showStatus('⚠️ No se generaron descripciones.', 'error');
        }

    } catch (e) {
        console.error(e);
        showStatus('Error de conexión general', 'error');
    } finally {
        btn.innerHTML = '✨ Auto-Generar Semántica';
        btn.disabled = false;
        setTimeout(() => {
            const pw = document.getElementById('gen-progress-wrapper');
            if (pw) pw.style.display = 'none';
            const pb = document.getElementById('gen-progress-bar');
            if (pb) pb.style.width = '0%';
            const dt = document.getElementById('gen-detail-text');
            if (dt) dt.innerText = '';
        }, 1500);
    }
}

async function saveMapping() {
    const btn = document.querySelector('button[onclick="saveMapping()"]');
    const status = document.getElementById('save-map-status');
    btn.innerHTML = '⏳ Guardando...';
    status.innerText = '';

    try {
        const table = document.getElementById('sel-source-table').value;
        const context = document.getElementById('table-context').value;
        const bsName = document.getElementById('business-table-name').value;
        const rows = document.querySelectorAll('.field-row');

        const fields = [];
        rows.forEach(row => {
            const chk = row.querySelector('.chk-field');
            if (chk.checked) {
                fields.push({
                    name: row.querySelector('.inp-orig').value,
                    type: row.querySelector('.inp-type').value,
                    business_name: row.querySelector('.inp-bus').value,
                    description: row.querySelector('.inp-desc').value,
                    metadata: row.querySelector('.inp-meta').value,
                    usage: row.querySelector('.inp-usage').value,
                    is_key: row.querySelector('.inp-key').checked,
                    selected: true
                });
            }
        });

        if (fields.length > 0) {
            const norm = (s) => {
                let x = String(s || '').trim().toLowerCase();
                x = x.replace(/\s+/g, '_').replace(/\./g, '_').replace(/[^a-z0-9_]/g, '');
                if (x === 'id') x = 'source_id';
                if (x === '"order"' || x === 'order') x = 'order';
                return x;
            };
            const seen = new Set();
            const dups = new Set();
            fields.forEach(f => {
                const n = norm(f.business_name || f.name);
                if (seen.has(n)) dups.add(n); else seen.add(n);
            });
            if (dups.size > 0) {
                const dupList = Array.from(dups).join(', ');
                if (typeof showToast === 'function') showToast(`❌ Nombres de negocio duplicados: ${dupList}`);
                rows.forEach(row => {
                    const chk = row.querySelector('.chk-field');
                    if (!chk.checked) return;
                    const bn = row.querySelector('.inp-bus').value || row.querySelector('.inp-orig').value;
                    const n = norm(bn);
                    if (dups.has(n)) {
                        row.style.borderLeft = '3px solid #ef4444';
                        row.style.background = 'rgba(239, 68, 68, 0.06)';
                    }
                });
                btn.innerHTML = '💾 Guardar Mapeo';
                status.innerText = 'Duplicados en nombres de negocio';
                status.style.color = '#ef4444';
                return;
            }
        }

        if (fields.length === 0) {
            if (typeof showToast === 'function') showToast("⚠️ Selecciona al menos un campo.");
            btn.innerHTML = '💾 Guardar Mapeo';
            return;
        }

        const isVirtual = document.getElementById('chk-is-virtual').checked;
        const empVal = parseInt(currEmpresa, 10);
        if (!empVal || !/^\d+$/.test(String(currEmpresa))) {
            status.innerText = 'empresa debe ser numérica';
            status.style.color = '#ef4444';
            btn.innerHTML = '💾 Guardar Mapeo';
            return;
        }

        const res = await fetch('/api/semantic/mapping', {
            method: 'POST',
            body: JSON.stringify({
                empresa_id: empVal,
                table_name: table,
                business_name: bsName,
                table_description: context,
                table_context: context, // [FIX] Send explicit context
                is_virtual: isVirtual,
                fields: fields
            })
        });

        const data = await res.json();
        if (data.status === 'ok') {
            status.innerText = 'Guardado Correctamente ✅';
            status.style.color = '#34d399';
            loadMappedTables();
        } else {
            status.innerText = 'Error: ' + data.message;
            status.style.color = '#ef4444';
        }

    } catch (e) {
        console.error(e);
        status.innerText = 'Error de conexión';
        status.style.color = '#ef4444';
    } finally {
        btn.innerHTML = '💾 Guardar Mapeo';
    }
}

function filterTables() {
    const query = document.getElementById('table-search-input').value.toLowerCase();
    const sel = document.getElementById('sel-source-table');
    const options = Array.from(sel.options);

    options.forEach(opt => {
        if (opt.value === "") return;
        const text = opt.text.toLowerCase();
        if (text.includes(query)) {
            opt.style.display = "";
        } else {
            opt.style.display = "none";
        }
    });
}

function applyBulkUsage(selectEl) {
    const val = selectEl.value;
    if (!val) return;
    const allSelects = document.querySelectorAll('.inp-usage');
    allSelects.forEach(sel => {
        sel.value = val;
        sel.dispatchEvent(new Event('change'));
    });
    selectEl.value = "";
}

function applyBulkTag(selectEl) {
    const val = selectEl.value;
    if (!val) return;
    const rows = document.querySelectorAll('.field-row');
    rows.forEach(row => {
        const sel = row.querySelector('.inp-meta');
        if (sel) sel.value = val;
    });
}

function toggleAllFields(source) {
    const checkboxes = document.querySelectorAll('.chk-field');
    checkboxes.forEach(chk => {
        chk.checked = source.checked;
    });
}

function applyStatusFilter(select) {
    const filter = select.value;
    const rows = document.querySelectorAll('.field-row');
    rows.forEach(row => {
        const status = row.getAttribute('data-status');
        if (filter === 'all') {
            row.style.display = 'grid';
        } else if (filter === 'migrated' && status === 'migrated') {
            row.style.display = 'grid';
        } else if (filter === 'pending' && status === 'pending') {
            row.style.display = 'grid';
        } else {
            row.style.display = 'none';
        }
    });
}

function applyDescriptionFilter(select) {
    const filter = select.value;
    const rows = document.querySelectorAll('.field-row');
    rows.forEach(row => {
        const descInput = row.querySelector('.inp-desc');
        const description = descInput ? descInput.value.trim() : '';
        if (filter === 'all') {
            row.style.display = 'grid';
        } else if (filter === 'with' && description !== '') {
            row.style.display = 'grid';
        } else if (filter === 'without' && description === '') {
            row.style.display = 'grid';
        } else {
            row.style.display = 'none';
        }
    });
}

function applyUsageFilter(select) {
    const filter = select.value;
    const rows = document.querySelectorAll('.field-row');
    rows.forEach(row => {
        const usageSelect = row.querySelector('.inp-usage');
        const usage = usageSelect ? usageSelect.value : '';
        if (filter === 'all') {
            row.style.display = 'grid';
        } else if (usage === filter) {
            row.style.display = 'grid';
        } else {
            row.style.display = 'none';
        }
    });
}

// Update semantic model display
function updateModelDisplay() {
    const modelDisplay = document.getElementById('model-name-text');
    if (modelDisplay) {
        const semanticModel = localStorage.getItem('datia-semantic-model') || '';
        if (semanticModel) {
            modelDisplay.innerText = `Modelo: ${semanticModel} `;
            modelDisplay.parentElement.style.color = '#a78bfa';
        } else {
            modelDisplay.innerText = 'Sin modelo configurado';
            modelDisplay.parentElement.style.color = '#71717a';
        }
    }
}
