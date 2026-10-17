async function loadStandardFields() {
    const statusEl = document.getElementById('sf-status');
    if (statusEl) {
        statusEl.innerText = 'Cargando...';
        statusEl.style.background = 'rgba(59,130,246,0.2)';
        statusEl.style.color = '#60a5fa';
    }
    try {
        const q = (document.getElementById('sf-search')?.value || '').trim();
        const role = document.getElementById('sf-role-filter')?.value || '';
        const params = new URLSearchParams();
        if (q) params.append('q', q);
        if (role) params.append('role', role);
        const res = await fetch(`/api/semantic/standard-fields?${params.toString()}`);
        const data = await res.json();
        if (data.status !== 'ok') {
            throw new Error(data.message || 'Error desconocido');
        }
        renderStandardFields(data.items || []);
        if (statusEl) {
            statusEl.innerText = `Cargado (${(data.items || []).length})`;
            statusEl.style.background = 'rgba(16,185,129,0.2)';
            statusEl.style.color = '#34d399';
        }
    } catch (e) {
        console.error('Error al cargar StandardFields', e);
        if (statusEl) {
            statusEl.innerText = 'Error';
            statusEl.style.background = 'rgba(239,68,68,0.2)';
            statusEl.style.color = '#ef4444';
        }
        if (typeof showToast === 'function') showToast('❌ Error al cargar Campos Estándar');
    }
}

function renderStandardFields(items) {
    const container = document.getElementById('standard-fields-list');
    if (!container) return;
    if (!items || items.length === 0) {
        container.innerHTML = '<div style="padding: 2rem; text-align: center; color: #52525b;">No hay resultados</div>';
        return;
    }
    const rows = [];
    for (const it of items) {
        const id = `sf-${it.name}`;
        const disabled = '';
        const roleOptions = ['DIMENSION','METRIC','DATE','PK','FK']
            .map(r => `<option value="${r}" ${it.semantic_role === r ? 'selected':''}>${r}</option>`).join('');
        rows.push(`
            <div style="display: grid; grid-template-columns: 180px 180px 1fr 140px 80px 100px; gap: 0.6rem; padding: 0.6rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); align-items:center;">
                <input id="${id}-name" type="text" value="${it.name}" ${disabled} style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
                <input id="${id}-business" type="text" value="${htmlEscape(it.business_name || '')}" ${disabled} style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
                <textarea id="${id}-desc" rows="2" style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem; resize: vertical;">${htmlEscape(it.description || '')}</textarea>
                <select id="${id}-role" ${disabled} style="background: #09090b; border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
                    ${roleOptions}
                </select>
                <input id="${id}-iskey" type="checkbox" ${it.is_key ? 'checked':''} ${disabled} style="accent-color: var(--accent);">
                <div style="display:flex; gap:0.5rem; align-items:center;">
                    ${it.fix_type ? '<span style="font-size:0.7rem; color:#a78bfa;">System</span>' : ''}
                    <button onclick="saveStandardField('${id}', ${it.fix_type ? 'true':'false'})" class="btn-glow" style="padding: 0 0.6rem;">💾</button>
                    <button onclick="deleteStandardField('${id}', ${it.fix_type ? 'true':'false'})" class="btn-glow" style="padding: 0 0.6rem; background: rgba(239,68,68,0.2); border-color: rgba(239,68,68,0.5);">🗑️</button>
                </div>
            </div>
        `);
    }
    container.innerHTML = rows.join('');
}

function newStandardFieldRow() {
    const container = document.getElementById('standard-fields-list');
    if (!container) return;
    const id = `sf-new-${Date.now()}`;
    const roleOptions = ['DIMENSION','METRIC','DATE','PK','FK']
        .map(r => `<option value="${r}">${r}</option>`).join('');
    const rowHtml = `
        <div style="display: grid; grid-template-columns: 180px 180px 1fr 140px 80px 100px; gap: 0.6rem; padding: 0.6rem 1rem; border-bottom: 1px solid rgba(255,255,255,0.05); align-items:center;">
            <input id="${id}-name" type="text" placeholder="Nombre original (columna MSSQL)" style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
            <input id="${id}-business" type="text" placeholder="Nombre de negocio sugerido" style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
            <textarea id="${id}-desc" rows="2" placeholder="Descripción semántica por defecto" style="background: rgba(0,0,0,0.3); border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem; resize: vertical;"></textarea>
            <select id="${id}-role" style="background: #09090b; border: 1px solid #3f3f46; border-radius: 6px; color: #fff; padding: 0.4rem;">
                ${roleOptions}
            </select>
            <input id="${id}-iskey" type="checkbox" style="accent-color: var(--accent);">
            <div style="display:flex; gap:0.5rem; align-items:center;">
                <button onclick="saveStandardField('${id}', false)" class="btn-glow" style="padding: 0 0.6rem;">💾</button>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('afterbegin', rowHtml);
}

async function saveStandardField(id, isSystem) {
    const name = document.getElementById(`${id}-name`)?.value?.trim();
    const business = document.getElementById(`${id}-business`)?.value?.trim();
    const desc = document.getElementById(`${id}-desc`)?.value?.trim();
    const role = document.getElementById(`${id}-role`)?.value;
    const iskey = document.getElementById(`${id}-iskey`)?.checked || false;
    if (!name) {
        if (typeof showToast === 'function') showToast('⚠️ El nombre es obligatorio');
        return;
    }
    const payload = { name, business_name: business || name, description: desc, semantic_role: role || 'DIMENSION', is_key: !!iskey };
    if (isSystem) payload.force = true;
    try {
        const res = await fetch('/api/semantic/standard-fields/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'ok') {
            if (typeof showToast === 'function') showToast('✅ Guardado');
            loadStandardFields();
        } else {
            if (typeof showToast === 'function') showToast('❌ ' + (data.message || 'Error al guardar'));
        }
    } catch (e) {
        console.error('Error guardando StandardField', e);
        if (typeof showToast === 'function') showToast('❌ Error de conexión');
    }
}

async function deleteStandardField(id, isSystem) {
    const name = document.getElementById(`${id}-name`)?.value?.trim();
    if (!name) return;
    try {
        if (isSystem) {
            openSfConfirmModal(`Vas a eliminar un campo de sistema: "${name}". Esta acción es irreversible.`, async () => {
                const res = await fetch('/api/semantic/standard-fields/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, force: true })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    if (typeof showToast === 'function') showToast('🗑️ Eliminado');
                    loadStandardFields();
                } else {
                    if (typeof showToast === 'function') showToast('❌ ' + (data.message || 'Error al eliminar'));
                }
            });
        } else {
            const res = await fetch('/api/semantic/standard-fields/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            const data = await res.json();
            if (data.status === 'ok') {
                if (typeof showToast === 'function') showToast('🗑️ Eliminado');
                loadStandardFields();
            } else {
                if (typeof showToast === 'function') showToast('❌ ' + (data.message || 'Error al eliminar'));
            }
        }
    } catch (e) {
        console.error('Error eliminando StandardField', e);
        if (typeof showToast === 'function') showToast('❌ Error de conexión');
    }
}

function htmlEscape(str) {
    return String(str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function openSfConfirmModal(msg, onConfirm) {
    const overlay = document.getElementById('sf-confirm-modal');
    const txt = document.getElementById('sf-confirm-msg');
    if (txt) txt.innerText = msg || '';
    window.sfModalConfirmAction = onConfirm;
    if (overlay) overlay.style.display = 'flex';
}

function closeSfConfirmModal() {
    const overlay = document.getElementById('sf-confirm-modal');
    if (overlay) overlay.style.display = 'none';
    window.sfModalConfirmAction = null;
}

function sfExecuteModalConfirm() {
    const fn = window.sfModalConfirmAction;
    if (typeof fn === 'function') {
        Promise.resolve(fn()).finally(() => {
            closeSfConfirmModal();
        });
    } else {
        closeSfConfirmModal();
    }
}
