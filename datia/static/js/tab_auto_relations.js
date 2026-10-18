/* --- tab_auto_relations.js --- */
/* Relationship Editor Logic */

async function loadRelations() {
    const listBody = document.getElementById('relations-list-body');
    const sourceSel = document.getElementById('rel-source-table');
    const targetSel = document.getElementById('rel-target-table');

    // Populate Table Dropdowns if empty
    if (sourceSel.options.length <= 1) {
        try {
            const empresaQuery = (typeof empresaListQuery === 'function') ? empresaListQuery() : '';
            const res = await fetch('/api/semantic/active-tables' + (empresaQuery ? `?${empresaQuery}` : ''));
            const data = await res.json();
            if (data.status === 'ok') {
                const opts = data.tables.map(t => {
                    const isVirtual = !t.physical_name;
                    const label = isVirtual ? `📡 ${t.name} (Virtual)` : `${t.name} (${t.physical_name})`;
                    return `<option value="${t.id}">${label}</option>`;
                }).join('');
                sourceSel.innerHTML = '<option value="">-- Origen --</option>' + opts;
                targetSel.innerHTML = '<option value="">-- Destino --</option>' + opts;
            }
        } catch (e) {
            console.error("Error loading tables for relations", e);
        }
    }

    try {
        const empVal = parseInt(currEmpresa, 10);
        if (!empVal || !/^\d+$/.test(String(currEmpresa))) {
            listBody.innerHTML = '<tr><td colspan="6" style="padding: 1rem; text-align: center; color: #ef4444;">empresa debe ser numérica</td></tr>';
            return;
        }
        const res = await fetch(`/api/relationships?empresa=${empVal}`);
        const data = await res.json();

        if (data.status === 'ok') {
            if (data.relations.length === 0) {
                listBody.innerHTML = '<tr><td colspan="6" style="padding: 2rem; text-align: center; color: #71717a;">No hay relaciones definidas.</td></tr>';
            } else {
                listBody.innerHTML = data.relations.map(r => `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 1rem; color: #fff;">
                            ${r.source_is_virtual ? '📡' : ''} ${r.source_table}
                            ${r.source_is_virtual ? '<span style="font-size:0.7rem; color:#60a5fa; display:block;">(Virtual)</span>' : ''}
                        </td>
                        <td style="padding: 1rem; color: #a1a1aa; font-family: monospace;">${r.source_field}</td>
                        <td style="padding: 1rem; text-align: center; color: #3b82f6; font-weight: bold;">${r.cardinality_label || r.cardinality}</td>
                        <td style="padding: 1rem; color: #fff;">
                            ${r.target_is_virtual ? '📡' : ''} ${r.target_table}
                            ${r.target_is_virtual ? '<span style="font-size:0.7rem; color:#60a5fa; display:block;">(Virtual)</span>' : ''}
                        </td>
                        <td style="padding: 1rem; color: #a1a1aa; font-family: monospace;">${r.target_field}</td>
                        <td style="padding: 1rem; text-align: right;">
                            <div style="display: flex; gap: 8px; justify-content: flex-end;">
                                <button onclick="editRelation(${r.id}, '${r.source_id}', '${r.source_field_id}', '${r.target_id}', '${r.target_field_id}', '${r.cardinality}')" 
                                    style="background: none; border: none; cursor: pointer; color: #a855f7; opacity: 0.7; transition: opacity 0.2s;" 
                                    title="Editar"
                                    onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
                                    ✏️
                                </button>
                                <button onclick="deleteRelation(${r.id})" 
                                    style="background: none; border: none; cursor: pointer; color: #ef4444; opacity: 0.7; transition: opacity 0.2s;" 
                                    title="Eliminar"
                                    onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
                                    🗑️
                                </button>
                            </div>
                        </td>
                    </tr>
                `).join('');
            }
        }
    } catch (e) {
        listBody.innerHTML = '<tr><td colspan="6" style="padding: 1rem; text-align: center; color: #ef4444;">Error al cargar relaciones.</td></tr>';
    }
}

async function loadRelFields(side) {
    const tableId = document.getElementById(`rel-${side}-table`).value;
    const fieldSel = document.getElementById(`rel-${side}-field`);

    fieldSel.innerHTML = '<option value="">Cargando...</option>';
    fieldSel.disabled = true;

    if (!tableId) {
        fieldSel.innerHTML = '<option value="">-- Campo --</option>';
        return;
    }

    try {
        const resFields = await fetch(`/api/relationships?table_id=${tableId}`);
        const data = await resFields.json();

        if (data.status === 'ok') {
            const opts = data.fields.map(f => `<option value="${f.id}">${f.name} (${f.type})</option>`).join('');
            fieldSel.innerHTML = '<option value="">-- Seleccionar --</option>' + opts;
            fieldSel.disabled = false;
        } else {
            fieldSel.innerHTML = `<option value="">Error: ${data.message}</option>`;
            console.error("API Error loading fields:", data.message);
        }

    } catch (e) {
        console.error(e);
        fieldSel.innerHTML = `<option value="">Error JS: ${e.message}</option>`;
    }
}

async function editRelation(id, sourceId, fromId, targetId, toId, cardinality) {
    // 1. Populate fields
    document.getElementById('rel-source-table').value = sourceId;
    // Trigger load fields manually or await it? 
    // We need to wait for fields to load before setting value
    await loadRelFields('source');
    document.getElementById('rel-source-field').value = fromId;

    document.getElementById('rel-target-table').value = targetId;
    await loadRelFields('target');
    document.getElementById('rel-target-field').value = toId;

    document.getElementById('rel-cardinality').value = cardinality;

    // 2. Change Add Button to Update
    const btnContainer = document.querySelector('button[onclick="addRelation()"]').parentNode;

    // Store original button if not already stored
    if (!window._originalAddBtn) {
        window._originalAddBtn = btnContainer.innerHTML;
    }

    btnContainer.innerHTML = `
        <label style="opacity:0">Btn</label>
        <div style="display:flex; gap:0.5rem;">
            <button onclick="updateRelation(${id})" class="btn-glow"
                style="padding: 8px 16px; background: #a855f7; border-color: #c084fc; flex:1;">
                💾 Guardar
            </button>
            <button onclick="cancelEditRelation()" 
                style="padding: 8px; background: transparent; border: 1px solid #3f3f46; color:#a1a1aa; border-radius:6px; cursor:pointer;">
                ❌
            </button>
        </div>
    `;

    // Scroll to form
    document.getElementById('rel-source-table').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function cancelEditRelation() {
    const btnContainer = document.querySelector('button[onclick^="updateRelation"]').parentNode.parentNode;
    if (window._originalAddBtn) {
        btnContainer.innerHTML = window._originalAddBtn;
    }
    // Clear form
    document.getElementById('rel-source-table').value = "";
    document.getElementById('rel-source-field').innerHTML = '<option value="">-- Campo --</option>';
    document.getElementById('rel-source-field').disabled = true;

    document.getElementById('rel-target-table').value = "";
    document.getElementById('rel-target-field').innerHTML = '<option value="">-- Campo --</option>';
    document.getElementById('rel-target-field').disabled = true;

    document.getElementById('rel-cardinality').value = "N-1";
}

async function updateRelation(id) {
    const sourceId = document.getElementById('rel-source-table').value;
    const fromId = document.getElementById('rel-source-field').value;
    const targetId = document.getElementById('rel-target-table').value;
    const toId = document.getElementById('rel-target-field').value;
    const card = document.getElementById('rel-cardinality').value;

    if (!sourceId || !fromId || !targetId || !toId) {
        if (typeof showToast === 'function') showToast('⚠️ Completa todos los campos');
        return;
    }

    try {
        // DELETE OLD (Simple update strategy since endpoint might not support PUT yet or we want to ensure clean state)
        // Ideally we should have PUT /api/relationships/{id}. 
        // Checking API... The standard usually implies DELETE + CREATE if structure changes significantly, 
        // but let's assume we can DELETE then CREATE to reuse logic, OR check if we can implement PUT.
        // For safety and speed: DELETE then CREATE.

        await fetch(`/api/relationships/${id}`, { method: 'DELETE' });

        const res = await fetch('/api/relationships', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_id: sourceId,
                from_field_id: fromId,
                target_id: targetId,
                to_field_id: toId,
                cardinality: card
            })
        });

        const data = await res.json();

        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast('✅ Relación actualizada');
            cancelEditRelation(); // Reset UI
            loadRelations();
        } else {
            if (typeof showToast === 'function') showToast('❌ Error: ' + data.message);
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('❌ Error de conexión');
    }
}

async function deleteRelation(id) {
    if (!confirm('¿Borrar esta relación?')) return;

    try {
        const res = await fetch(`/api/relationships/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast('🗑️ Relación eliminada');
            loadRelations();
        } else {
            alert('Error: ' + data.message);
        }
    } catch (e) {
        alert('Error de conexión');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const relBtn = document.getElementById('btn-tab-relationships');
    if (relBtn) {
        relBtn.addEventListener('click', () => {
            loadRelations();
        });
    }
});
