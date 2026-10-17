/* --- tab_auto_training.js --- */
/* Mass SQL Training Logic */

let trainingEventSource = null;
let trainingTimerInterval = null;
let isTrainingActive = false;
let trainingAbortController = null;

async function startMassTraining() {
    console.log("🚀 Iniciando startMassTraining...");
    const statusDiv = document.getElementById('mass-training-status');
    const progressBar = document.getElementById('mt-progress-bar');
    const progressText = document.getElementById('mt-progress-text');
    const statusText = document.getElementById('mt-status-text');
    const timerEl = document.getElementById('training-timer');

    const countSelect = document.getElementById('sel-training-count');
    const queriesPerTable = countSelect ? parseInt(countSelect.value) : 500;
    const forceCheckbox = document.getElementById('chk-force-train');
    const force = forceCheckbox ? forceCheckbox.checked : false;

    const tablesGrid = document.getElementById('tables-progress');
    const startBtn = document.getElementById('btn-start-training');

    if (statusDiv) statusDiv.style.display = 'block';
    if (startBtn) startBtn.disabled = true;
    if (tablesGrid) tablesGrid.innerHTML = '';
    if (progressBar) progressBar.style.width = '0%';
    if (statusText) statusText.textContent = 'Obteniendo lista de tablas...';
    if (progressText) progressText.textContent = '0/0';

    if (typeof trainingTimerInterval !== 'undefined' && trainingTimerInterval) clearInterval(trainingTimerInterval);
    trainingTimerInterval = null;

    let startTime = Date.now();
    if (timerEl) timerEl.innerText = "00:00";

    trainingTimerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const s = (elapsed % 60).toString().padStart(2, '0');
        if (timerEl) timerEl.innerText = `${m}:${s}`;
    }, 1000);

    isTrainingActive = true;

    try {
        const res = await fetch('/api/semantic/active-tables');
        const data = await res.json();

        if (data.status !== 'ok' || data.tables.length === 0) {
            if (statusText) statusText.innerHTML = '<span style="color: #ef4444;">❌ No se encontraron tablas activas</span>';
            if (startBtn) startBtn.disabled = false;
            return;
        }

        const tables = data.tables;
        let pendingTables = tables.filter(t => !t.is_trained);

        if (force) {
            console.log("⚠️ Force mode active: Retraining ALL tables.");
            pendingTables = tables;
        }

        if (pendingTables.length === 0) {
            console.log("⚠️ Pre-check: No hay tablas pendientes.");
            showNoDataModal(
                "No hay datos nuevos para entrenar",
                "Los conjuntos de datos ya han sido procesados anteriormente.",
                "Marca 'Forzar re-entrenamiento' si deseas sobreescribir el conocimiento existente."
            );

            if (statusText) statusText.innerHTML = '<span style="color: #fbbf24;">⚠️ Sin cambios pendientes</span>';
            if (startBtn) startBtn.disabled = false;
            isTrainingActive = false;
            if (typeof trainingTimerInterval !== 'undefined' && trainingTimerInterval) clearInterval(trainingTimerInterval);
            return;
        }

        const progressContainer = document.getElementById('training-progress');
        if (progressContainer) progressContainer.style.display = 'block';

        const massStatus = document.getElementById('mass-training-status');
        if (massStatus) massStatus.style.display = 'block';

        if (statusText) statusText.textContent = `Preparado para entrenar ${pendingTables.length} tablas (de ${tables.length})...`;

        tables.forEach(t => {
            const isVirtual = !t.physical_name;
            const card = document.createElement('div');
            card.className = 'table-training-card';
            card.id = `table-card-${t.id}`;

            if (t.is_trained) {
                card.style.opacity = '0.8';
                card.style.borderColor = '#22c55e';
            } else {
                card.style.opacity = '0.5';
            }

            if (isVirtual) {
                card.style.background = 'rgba(59, 130, 246, 0.05)';
                if (!t.is_trained) card.style.border = '1px dashed rgba(59, 130, 246, 0.4)';
            }

            const initialStatus = t.is_trained
                ? '<span style="color: #22c55e;">✅ Ya entrenada</span>'
                : 'Pendiente...';

            const initialProgress = t.is_trained ? '100%' : '0%';

            card.innerHTML = `
                    <div class="table-name">
                        <span style="color: #fff;">
                            ${isVirtual ? '📡' : ''} ${t.name}
                        </span>
                        <div style="font-size: 0.75rem; color: ${isVirtual ? '#60a5fa' : '#34d399'}; font-family: monospace; margin-top: 2px;">
                                ${isVirtual ? 'Virtual (Direct MSSQL)' : `target: ${t.physical_name}`}
                        </div>
                    </div>
                    <div class="table-status">${initialStatus}</div>
                    <div class="progress-bar-container" style="height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; margin-top: 8px;">
                        <div class="progress-bar" style="height: 100%; background: #a855f7; border-radius: 3px; width: ${initialProgress}; transition: width 0.3s;"></div>
                    </div>
                    <div class="terminal-logs" style="
                        margin-top: 12px;
                        background: #0f0f12; 
                        color: #10b981; 
                        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                        font-size: 0.8rem;
                        padding: 12px;
                        border: 1px solid #3f3f46;
                        border-radius: 6px;
                        height: 200px; 
                        overflow-y: auto;
                        display: none; 
                        line-height: 1.4;
                        box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
                    "></div>
                `;
            tablesGrid.appendChild(card);
        });

        let tablesProcessed = 0;
        let tablesFailed = 0;
        const pendingTotal = Math.max(1, pendingTables.length);

        for (const table of tables) {
            if (!isTrainingActive) break;

            if (table.is_trained && !force) {
                continue;
            }

            const card = document.getElementById(`table-card-${table.id}`);
            if (card) {
                card.style.opacity = '1';
                card.style.borderColor = '#a855f7';
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });

                const terminal = card.querySelector('.terminal-logs');
                if (terminal) terminal.style.display = 'block';

                if (statusText) statusText.innerHTML = `Entrenando: <strong style="color:#a855f7">${table.name}</strong> (${tablesProcessed + 1}/${pendingTables.length})`;

                const trainedOk = await trainSingleTable(table, queriesPerTable, card, terminal, force);
                if (!trainedOk) tablesFailed++;
            }
            tablesProcessed++;
            if (progressText) progressText.textContent = `${tablesProcessed}/${pendingTables.length}`;
            if (progressBar) progressBar.style.width = `${Math.min(100, Math.round((tablesProcessed / pendingTotal) * 100))}%`;
        }

        if (isTrainingActive) {
            if (tablesFailed > 0) {
                if (statusText) statusText.innerHTML = `<strong style="color: #fbbf24;">Entrenamiento terminado con ${tablesFailed} tablas sin completar</strong>`;
            } else if (statusText) statusText.innerHTML = `<strong style="color: #22c55e;">🎉 Entrenamiento Completado</strong>`;
            const cq = document.getElementById('current-query');
            if (cq) cq.textContent = 'Todas las tablas han sido procesadas.';
            if (typeof showToast === 'function') {
                showToast(tablesFailed > 0 ? 'Entrenamiento terminado con tablas pendientes.' : 'Entrenamiento finalizado con éxito.');
            }
        } else {
            if (statusText) statusText.textContent = 'Proceso detenido.';
        }

    } catch (e) {
        console.error(e);
        if (statusText) statusText.textContent = 'Error: ' + e.message;
    } finally {
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.innerHTML = '⚡ Iniciar Entrenamiento';
        }
        isTrainingActive = false;
        if (typeof trainingTimerInterval !== 'undefined' && trainingTimerInterval) clearInterval(trainingTimerInterval);
    }
}

window.startMassTraining = startMassTraining;

async function trainSingleTable(table, count, card, terminal, force = false) {
    const configuredModel = localStorage.getItem('datia-sql-training-model');
    let url = `/api/auto-training/generate-sql-batch?queries_per_table=${count}&table_ids=${table.id}`;
    if (configuredModel) {
        url += `&model=${encodeURIComponent(configuredModel)}`;
    }
    if (force) {
        url += `&force=true`;
    }

    const statusEl = card.querySelector('.table-status');
    const progressBar = card.querySelector('.progress-bar');

    const log = (msg, color = '#0f0') => {
        const line = document.createElement('div');
        line.style.color = color;
        line.textContent = `> ${msg}`;
        terminal.appendChild(line);
        terminal.scrollTop = terminal.scrollHeight;
    };

    statusEl.innerHTML = '<span style="color: #fbbf24;">Iniciando...</span>';
    log("Conectando vía Fetch Stream...");
    let outcome = 'empty';

    try {
        trainingAbortController = new AbortController();
        const response = await fetch(url, { signal: trainingAbortController.signal });
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (line.startsWith("event: ")) {
                    const parts = line.split("\n");
                    const eventType = parts[0].replace("event: ", "").trim();
                    const dataLine = parts.find(p => p.startsWith("data: "));

                    if (dataLine) {
                        try {
                            const jsonStr = dataLine.replace("data: ", "");
                            const data = JSON.parse(jsonStr);

                            if (eventType === 'log') {
                                log(data.message, '#a855f7');
                            } else if (eventType === 'prompt_data') {
                                log("PROMPT GENERATED:", '#fbbf24');
                                const l = document.createElement('div');
                                l.style.color = '#ccc';
                                l.style.fontSize = '0.7rem';
                                l.textContent = data.prompt ? data.prompt.substring(0, 300) + '...' : 'Prompt data';
                                terminal.appendChild(l);
                            } else if (eventType === 'query_generated') {
                                statusEl.textContent = `${data.query_index} / ${data.total_queries} queries`;
                                if (data.total_queries > 0) {
                                    progressBar.style.width = `${(data.query_index / data.total_queries) * 100}%`;
                                }
                                log(`Query ${data.query_index} OK`, '#34d399');
                                const cq = document.getElementById('current-query');
                                if (cq) cq.textContent = data.description;
                            } else if (eventType === 'table_complete') {
                                statusEl.innerHTML = `<span style="color: #22c55e;">✅ ${data.saved} guardadas</span>`;
                                card.style.borderColor = '#22c55e';
                                log(`COMPLETADO: ${data.saved} queries.`, '#22c55e');
                                if (outcome !== 'error') outcome = (data.saved > 0) ? 'ok' : 'skipped';
                            } else if (eventType === 'error') {
                                log(`ERROR: ${data.message}`, '#ef4444');
                                statusEl.innerHTML = `<span style="color: #ef4444;">Error</span>`;
                                outcome = 'error';
                            } else if (eventType === 'complete') {
                                log("Stream Finished.", '#34d399');
                            } else if (eventType === 'no_data_alert') {
                                stopTraining();
                                showNoDataModal(data.title, data.message, data.suggestion);
                                const statusText = document.getElementById('mt-status-text');
                                if (statusText) statusText.innerHTML = `<span style="color: #fbbf24;">⚠️ ${data.title}</span>`;
                            }

                        } catch (parseErr) {
                            console.warn("Error parsing SSE JSON", parseErr);
                        }
                    }
                }
            }
        }
        if (outcome === 'empty') {
            statusEl.innerHTML = '<span style="color: #fbbf24;">Sin consultas nuevas</span>';
        }
        return outcome === 'ok' || outcome === 'skipped';
    } catch (err) {
        console.error(err);
        log(`Fetch Error: ${err.message}`, '#ef4444');
        statusEl.innerHTML = '<span style="color: #ef4444;">Fallo Conexión</span>';
        return false;
    }
}

function stopTraining() {
    isTrainingActive = false;
    if (trainingAbortController) {
        trainingAbortController.abort();
        trainingAbortController = null;
    }
    const startBtn = document.getElementById('btn-start-training');
    if (startBtn) startBtn.disabled = false;
}

function showNoDataModal(title, message, suggestion) {
    document.getElementById('nd-title').innerText = title;
    document.getElementById('nd-message').innerText = message;
    document.getElementById('nd-suggestion').innerText = suggestion;
    document.getElementById('no-data-modal').style.display = 'flex';

    const btn = document.getElementById('btn-start-training');
    if (btn) btn.disabled = false;
}

function closeNoDataModal() {
    document.getElementById('no-data-modal').style.display = 'none';
}

// [NF] Custom Training Count Logic
function initTrainingCountSelector() {
    const selector = document.getElementById('sel-training-count');
    if (!selector) return;

    // 1. Restaurar último valor personalizado
    const lastVal = localStorage.getItem('datia_last_training_count');
    if (lastVal) {
        // Verificar si ya existe en las opciones estáticas
        let exists = false;
        for (let i = 0; i < selector.options.length; i++) {
            if (selector.options[i].value == lastVal) {
                exists = true;
                // Actualizar texto si es necesario? No, dejar el estático
                break;
            }
        }

        if (!exists) {
            const opt = document.createElement('option');
            opt.value = lastVal;
            opt.text = `${lastVal} (último entreno)`;
            // Insertar al principio para visibilidad
            selector.add(opt, selector.options[0]);
        }
        selector.value = lastVal;
    }

    // 2. Añadir opción manual si no existe
    let hasCustom = false;
    for (let i = 0; i < selector.options.length; i++) {
        if (selector.options[i].value === 'custom') {
            hasCustom = true;
            break;
        }
    }

    if (!hasCustom) {
        const customOpt = document.createElement('option');
        customOpt.value = 'custom';
        customOpt.text = '✏️ Manual...';
        selector.add(customOpt);
    }

    // 3. Listener para cambios
    // Usamos una propiedad en el elemento para evitar múltiples listeners si se reinicializa
    if (!selector._hasCustomListener) {
        selector._hasCustomListener = true;
        selector.addEventListener('change', async function () {
            if (this.value === 'custom') {
                let val = null;

                // Intentar usar SweetAlert2 si está disponible (común en este proyecto)
                if (typeof Swal !== 'undefined') {
                    const result = await Swal.fire({
                        title: 'Consultas por Tabla',
                        text: 'Indica el número de consultas a generar:',
                        input: 'number',
                        inputValue: 250,
                        showCancelButton: true,
                        confirmButtonColor: '#a855f7',
                        cancelButtonColor: '#3f3f46',
                        confirmButtonText: 'Establecer',
                        cancelButtonText: 'Cancelar',
                        background: '#18181b',
                        color: '#fff',
                        inputValidator: (value) => {
                            if (!value || value <= 0) {
                                return 'Debes escribir un número mayor a 0'
                            }
                        }
                    });
                    if (result.isConfirmed) {
                        val = result.value;
                    }
                } else {
                    // Fallback nativo
                    val = prompt("Indica el número de consultas por tabla:", "250");
                }

                if (val && !isNaN(val) && val > 0) {
                    // Guardar persistencia
                    localStorage.setItem('datia_last_training_count', val);

                    // Comprobar si ya existe como opción (para no duplicar visualmente)
                    let exists = false;
                    for (let i = 0; i < this.options.length; i++) {
                        if (this.options[i].value == val) {
                            exists = true;
                            this.value = val;
                            break;
                        }
                    }

                    if (!exists) {
                        const newOpt = document.createElement('option');
                        newOpt.value = val;
                        newOpt.text = `${val} (último entreno)`;
                        newOpt.selected = true;

                        // Insertar antes de la opción 'custom' (que es la última)
                        const customIndex = this.options.length - 1;
                        this.add(newOpt, this.options[customIndex]);
                        this.value = val;
                    }
                } else {
                    // Si cancela o inválido, volver al valor por defecto o anterior
                    // Intentamos volver a 200 o al primero
                    this.value = "200";
                }
            } else {
                // Guardar también si elige una opción estándar
                localStorage.setItem('datia_last_training_count', this.value);
            }
        });
    }
}
