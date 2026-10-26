// datia/static/js/dashboard/ia.js

// [UX] Auto-Focus on Load
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('ai-input');
    if (input) {
        // Short delay to ensure animations/transitions are done
        setTimeout(() => input.focus(), 300);
    }
    cargarConversaciones();
});

// Also listen for Tab activation (if handled via custom events or visibility change)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        const input = document.getElementById('ai-input');
        if (input) input.focus();
    }
});

// === TABS REPORT MODAL ===
function switchReportTab(tab) {
    const logTab = document.getElementById('reporte-tab-log');
    const resTab = document.getElementById('reporte-tab-resumen');
    const btnLog = document.getElementById('btn-tab-reporte-log');
    const btnRes = document.getElementById('btn-tab-reporte-resumen');

    if(tab === 'log') {
        if(logTab) logTab.style.display = 'flex';
        if(resTab) resTab.style.display = 'none';
        if(btnLog) { btnLog.style.background = '#27272a'; btnLog.style.color = 'white'; }
        if(btnRes) { btnRes.style.background = 'transparent'; btnRes.style.color = '#a1a1aa'; }
    } else {
        if(logTab) logTab.style.display = 'none';
        if(resTab) resTab.style.display = 'flex';
        if(btnLog) { btnLog.style.background = 'transparent'; btnLog.style.color = '#a1a1aa'; }
        if(btnRes) { btnRes.style.background = '#27272a'; btnRes.style.color = 'white'; btnRes.style.display = 'block'; }
    }
}

async function fetchFinalSummary(empresaIds) {
    try {
        const body = document.getElementById('reset-resumen-body');
        if (body) body.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px;">Generando resumen final...</td></tr>';
        
        switchReportTab('resumen');
        const btnResumen = document.getElementById('btn-tab-reporte-resumen');
        if(btnResumen) btnResumen.style.display = 'block';

        const res = await fetch(`/api/etl/verify_migration?empresa_id=${empresaIds.join(',')}`);
        const data = await res.json();
        
        if (body) body.innerHTML = '';
        if (data.status === 'ok' && data.summary && data.summary.length > 0) {
            data.summary.forEach(item => {
                const tr = document.createElement('tr');
                tr.style.borderBottom = '1px solid #27272a';
                
                // Calculando maestros
                const tMaestros = (item.clientes||0) + (item.proveedores||0) + (item.articulos||0) + (item.almacenes||0) + (item.familias||0) + (item.comisionistas||0);
                
                tr.innerHTML = `
                    <td style="padding:8px 10px; text-align:left; color:#e4e4e7; font-weight:500; position: sticky; left: 0; background: #18181b;">${item.empresa}</td>
                    <td style="padding:8px 10px; color:#10b981;">${tMaestros.toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#3b82f6;">${(item.cab_ped_cli||0).toLocaleString()} / ${(item.lin_ped_cli||0).toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#3b82f6;">${(item.cab_alb_cli||0).toLocaleString()} / ${(item.lin_alb_cli||0).toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#a855f7;">${(item.acum_stocks||0).toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#f59e0b;">${(item.fin_acumulados||0).toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#f59e0b;">${(item.fin_cartera||0).toLocaleString()}</td>
                    <td style="padding:8px 10px; color:#e4e4e7;">${(item.metrics_emp_eje||0).toLocaleString()}</td>
                `;
                if(body) body.appendChild(tr);
            });
        } else {
            if(body) body.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px;">No se encontraron datos.</td></tr>';
        }
    } catch (e) {
        console.error("Error fetching summary:", e);
    }
}

function toggleCard(header) {
    const card = header.parentElement;
    card.classList.toggle('collapsed');
}

async function askAI(queryString, forceTraining = false) {
    const input = document.getElementById('ai-input');
    const stream = document.getElementById('ia-results-stream');

    // Support retry or input
    const q = (typeof queryString === 'string') ? queryString : input.value.trim();

    if (!q) return;

    // --- COMMAND: CLEAR/RESET ---
    const cleanKeywords = ['limpiar', 'borrar', 'reset', 'clear', 'nueva busqueda', 'inicio'];
    const normalizedQ = q.toLowerCase().replace(/[áéíóú]/g, (m) => ({ 'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u' }[m])).replace(/[.,!]/g, '').trim();

    // Check if query exactly matches OR starts with a keyword
    if (cleanKeywords.some(k => normalizedQ === k || normalizedQ.startsWith(k + ' '))) {
        nuevaConsulta();
        return;
    }

    input.value = "";

    // Transition from centered to sticky top prompt
    const centeredPrompt = document.getElementById('ia-prompt-centered');
    const stickyPrompt = document.getElementById('ia-prompt-sticky');
    const streamContainer = document.getElementById('ia-results-stream');

    if (centeredPrompt && centeredPrompt.style.display !== 'none') {
        centeredPrompt.style.opacity = '0';
        centeredPrompt.style.transform = 'translate(-50%, -60%)';
        setTimeout(() => {
            centeredPrompt.style.display = 'none';
            if (stickyPrompt) {
                stickyPrompt.style.display = 'flex';
                stickyPrompt.style.opacity = '0';
                // stickyPrompt.style.transform = 'translateY(-20px)'; // Come from top? No, fade in place is better
                setTimeout(() => {
                    stickyPrompt.style.opacity = '1';
                    // stickyPrompt.style.transform = 'translateY(0)';

                    // [FOCUS FIX] Ensure cursor is in the sticky input
                    const stickyInput = document.getElementById('ai-input-sticky');
                    if (stickyInput) stickyInput.focus();

                }, 50);
            }
            // Add padding to stream
            if (streamContainer) streamContainer.classList.add('has-sticky-prompt');
        }, 400);
    }

    document.querySelectorAll('.ia-turno.latest, .ia-card.latest').forEach(c => c.classList.remove('latest'));

    const card = document.createElement('div');
    card.className = "ia-turno ia-card latest";

    const burbuja = document.createElement('div');
    burbuja.className = "ia-burbuja-usuario";
    burbuja.textContent = q;
    card.appendChild(burbuja);

    const body = document.createElement('div');
    body.className = "ia-respuesta card-body";
    body.id = 'ai-res-' + Date.now();

    // --- BRAIN EXPERIENCE LOADER ---
    const isTraining = forceTraining; // ONLY show visual training loader if MANUALLY triggered

    let steps = [
        gettext("📡 Conectando con Nodos Datia..."),
        gettext("✨ Explorando Memoria Vectorial..."),
        gettext("🛡️ Validando Esquema Seguro..."),
        gettext("✨ Materializando Respuesta...")
    ];

    if (isTraining) {
        steps = [
            gettext("✨ Entrenamiento Manual Solicitado..."),
            gettext("🎓 IA asimilando del experto..."),
            gettext("💾 Guardando nuevo conocimiento..."),
            gettext("✨ Generando respuesta maestra...")
        ];
    }


    let stepIdx = 0;
    const brainId = 'brain-' + Date.now();

    // [NEW] Language Command Detection
    const langPattern = /(?:cambiar|poner|traducir|speak|switch).*(?:idioma|a|in|to)?\s+(ingl[ée]s|english|franc[ée]s|french|alem[áa]n|german|catal[áa]n|catala|portugu[ée]s|portuguese|italiano|italian|vasco|euskera|gallego|galician|español|spanish|castellano)/i;
    const isLangCommand = langPattern.test(q);

    let loaderInterval;

    if (isLangCommand) {
        body.innerHTML = `
            <div style="text-align:center; padding:50px; color:#34d399;">
                <div style="font-size: 3rem;">🌍</div>
                <div style="margin-top:20px; font-weight:bold; font-size:1.2rem;">${gettext("Procesando cambio de idioma...")}</div>
            </div>
        `;
    } else {
        body.innerHTML = `
            <div id="${brainId}" style="font-size:0.95rem; color:#a1a1aa; min-height:1.5em;">${steps[0]}</div>
        `;

        loaderInterval = setInterval(() => {
            stepIdx = (stepIdx + 1) % steps.length;
            const txt = document.getElementById(brainId);
            if (txt) {
                txt.style.opacity = '0';
                setTimeout(() => {
                    txt.innerText = steps[stepIdx];
                    txt.style.opacity = '1';
                }, 300);
            }
        }, 1800);
    }

    card.appendChild(body);
    stream.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'end' });

    // API Call
    try {
        // [FIX] Force update of global exercise if query mentions a year
        // This ensures the backend context (currEjercicio) matches the user intent
        let activeEjercicio = currEjercicio;
        const yearMatch = q.match(/\b(202\d)\b/);
        if (yearMatch) {
            activeEjercicio = yearMatch[1];
        }

        if (window._empresaDeLaMemoria && String(window._empresaDeLaMemoria) !== String(currEmpresa)) {
            conversacionActual = null;
        }
        window._empresaDeLaMemoria = currEmpresa;
        const emp = encodeURIComponent(currEmpresa);
        const eje = encodeURIComponent(activeEjercicio);
        const conversacionId = Number(conversacionActual) || 0;

        const isSettingOn = localStorage.getItem('datia-training-mode') === 'true';
        const trainingMode = forceTraining === true || isSettingOn;
        const aiModel = localStorage.getItem('datia-ai-model') || localStorage.getItem('datia-sql-training-model') || '';

        // [HOTFIX] Use AbortController for Timeout (Reduced to 90s to prevent long hangs)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000); // 90 seconds (1.5 min)

        const res = await fetch(`${API}/qa?question=${encodeURIComponent(q)}&empresa=${emp}&ejercicio=${eje}&training_enabled=${trainingMode}&model=${encodeURIComponent(aiModel)}&conversacion_id=${conversacionId}`, {
            method: 'POST',
            signal: controller.signal
        });
        clearTimeout(timeoutId); // Clear timeout if successful

        const data = await res.json();

        // Stop Loader Animation
        clearInterval(loaderInterval);


        if (data.error === 'PASSIVE_MODE') {
            const btnId = `btn-gen-ai-${Date.now()}`;
            const btnDslId = `btn-dsl-${Date.now()}`;

            body.innerHTML = `
                <div style="text-align:center; padding:20px; color:#a1a1aa;">
                    <div style="margin-bottom:15px; font-size: 0.95rem; color: #fff;">${gettext("No encuentro esta consulta en mi memoria verificada.")}</div>
                    
                    <button id="${btnId}" 
                        class="btn-primary-glow"
                        style="
                            background: var(--accent); 
                            color: #fff; 
                            border: none; 
                            padding: 12px 24px; 
                            border-radius: 8px; 
                            cursor: pointer; 
                            font-weight: 600; 
                            font-size: 0.95rem;
                            display: inline-flex; 
                            align-items: center; 
                            gap: 10px;
                            box-shadow: 0 4px 12px rgba(168, 85, 247, 0.4);
                            transition: transform 0.2s;
                        "
                        onmouseover="this.style.transform='translateY(-2px)'"
                        onmouseout="this.style.transform='translateY(0)'"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>
                        ${gettext("Generar con IA (vZULU)")}
                    </button>
                    
                    <button id="${btnDslId}" class="btn-primary-blue" style="margin-left:10px;">
                        <i class="bi bi-code-slash"></i> ${gettext("Generar Consulta DSL")}
                    </button>
                    
                    <div style="font-size:0.8rem; margin-top:15px; color:#71717a;">${gettext("Esto analizará tu pregunta y generará una respuesta nueva.")}</div>
                </div>
            `;

            // DIRECT CLOSURE BINDING - SIMPLEST & SAFEST
            const btn = document.getElementById(btnId);
            const btnDsl = document.getElementById(btnDslId);
            if (btn) {
                // [FIX] Ensure we only use the current query, not accumulating previous ones
                const currentQuery = String(q).trim();
                btn.onclick = function () {
                    if (!currentQuery) {
                        if (window.showToast) window.showToast(gettext("Error ZULU: Consulta vacía"), true);
                        return;
                    }
                    // Ejecutar consulta IA vía DSL y mostrar overlay
                    try {
                        if (window.AIReportManager && typeof window.AIReportManager.executeQuery === 'function') {
                            window.AIReportManager.executeQuery(currentQuery);
                        } else {
                            // Fallback al flujo original si el overlay no está disponible
                            askAI(currentQuery, true);
                        }
                    } catch (e) {
                        askAI(currentQuery, true);
                    }
                };
            }
            if (btnDsl) {
                const currentQuery = String(q).trim();
                btnDsl.onclick = function () {
                    if (!currentQuery) {
                        if (window.showToast) window.showToast(gettext("Consulta vacía"), true);
                        return;
                    }
                    try {
                        if (window.AIReportManager && typeof window.AIReportManager.executeQuery === 'function') {
                            window.AIReportManager.executeQuery(currentQuery);
                        } else {
                            if (window.showToast) window.showToast(gettext("Overlay no disponible"), true);
                        }
                    } catch (e) {
                        if (window.showToast) window.showToast(gettext("Error al abrir overlay"), true);
                    }
                };
            }

        } else if (data.error) {
            body.innerHTML = `<div style="color: #ef4444;">Error: ${data.error}</div>`;
        } else if (data.type === 'training_completed') {
            // ... existing logic ...
            body.innerHTML = `...`;
        } else if (data.action === 'RELOAD') {
            // [NEW] Language Change Handling
            body.innerHTML = `
                <div style="text-align:center; padding:20px; color:#34d399;">
                    <div style="font-size: 2rem;">🌍</div>
                    <div style="margin-top:10px; font-weight:bold;">${data.answer}</div>
                </div>
            `;
            // Toast if available
            if (window.showToast) window.showToast(gettext("Idioma actualizado"), false);

            // Reload after short delay
            setTimeout(() => {
                window.location.reload();
            }, 1500);

        } else {
            const copiaRespuesta = copiarRespuestaGuardable(data);
            renderAiResponse(data, body, { query: q });
            nodoConversacionActual = null;
            await guardarConversacionActual(q, copiaRespuesta);
            try { if (window.VOA && typeof window.VOA.notify === 'function') window.VOA.notify('AI_QA_COMPLETED', { query: q }); } catch (_) {}
        }
    } catch (e) {
        clearInterval(loaderInterval);
        console.error(e);

        // [FIX] Detect AbortError explicitly
        if (e.name === 'AbortError') {
            body.innerHTML = `<div style="color: #ef4444; font-weight: bold;">${gettext("Tiempo de espera agotado (Timeout)")}</div>
             <div style="color: #a1a1aa; font-size: 0.9rem; margin-top: 5px;">${gettext("La consulta ha tardado más de 90 segundos y ha sido cancelada por el navegador.")}</div>`;
        } else {
            body.innerHTML = `<div style="color: #ef4444;">${gettext("Error de sistema:")} ${e.message}</div>`;
        }
    }
}

function startTrainingFlow(query) {
    // Deprecated but kept to prevent reference errors if old HTML lingers
    if (!query) {
        if (window.showToast) window.showToast(`Error Legacy: ${typeof query}`, true);
        return;
    }
    askAI(query, true);
}
// Expose to Global Scope
window.startTrainingFlow = startTrainingFlow;

// Handle Enter key from centered prompt
function handleAiKey(e) {
    if (e.key === 'Enter') askAI();
}

// Handle Enter key from sticky prompt
function handleAiKeySticky(e) {
    if (e.key === 'Enter') askAIFromSticky();
}

// Ask AI from sticky prompt
async function askAIFromSticky() {
    const stickyInput = document.getElementById('ai-input-sticky');
    const topInput = document.getElementById('ai-input');

    // [FIX] Ensure we are not appending to existing value in topInput if it wasn't cleared properly
    const newQuery = stickyInput.value.trim();

    // Copy value to top input and trigger askAI
    topInput.value = newQuery;
    stickyInput.value = '';

    // [FOCUS FIX] Keep focus on input after submit to allow rapid typing
    stickyInput.focus();

    await askAI(newQuery);

    // [FOCUS FIX] Ensure focus returns even after async operation
    stickyInput.focus();
}

async function triggerDeepDive(query, containerId, lang) {
    const container = document.getElementById(containerId);
    if (!container) return;

    // 1. Disable button and track that deep dive was triggered
    const btn = document.getElementById(`btn-deep-dive-${containerId}`);
    if (btn) {
        btn.disabled = true;
        btn.style.pointerEvents = 'none'; // Ensure no clicks
        btn.style.opacity = '0.5';
        btn.style.cursor = 'wait';
        btn.innerHTML = '⏳ ' + gettext("Analizando...");
    }

    const effectiveQuery = String(query || '').replace(/\s*\(Deep Dive:.*\)\s*$/i, '').trim();

    // 4. Inline Loading
    const loadingDiv = document.createElement("div");
    loadingDiv.id = "loading-" + containerId;
    loadingDiv.className = "pulse";
    loadingDiv.style.marginTop = "10px";
    loadingDiv.style.color = "#a1a1aa";
    loadingDiv.innerText = gettext("Buscando el detalle de esta respuesta...");
    container.appendChild(loadingDiv);
    loadingDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    try {
        const emp = encodeURIComponent(currEmpresa);
        const eje = encodeURIComponent(currEjercicio);

        // Deep Dive uses Manual Mode (False) by default to avoid auto-training on deep dive? 
        // Or should it use whatever mode? 
        // Deep Dive is "Generative" by definition. But we want to avoid "Training" (Saving).
        // Let's pass False. The Backend handles Deep Dive via GenerativeHandler anyway? 
        // Wait, if we force False, Router might block it.
        // But Deep Dive queries are usually "Long Text". Router sends Long Text to GenerativeHandler automatically?
        // Let's check Router heuristic.
        // It's irrelevant for now. Sending false is safer.
        const trainingMode = false;
        const aiModel = localStorage.getItem('datia-ai-model') || '';

        const res = await fetch(`${API}/qa?question=${encodeURIComponent(effectiveQuery)}&empresa=${emp}&ejercicio=${eje}&training_enabled=${trainingMode}&model=${encodeURIComponent(aiModel)}&profundizar=1`, {
            method: 'POST'
        });
        const data = await res.json();

        loadingDiv.remove();

        if (data.error) {
            const errDiv = document.createElement("div");
            errDiv.style.color = "#ef4444";
            errDiv.innerText = "Error: " + data.error;
            container.appendChild(errDiv);

            // Re-enable button on error
            if (btn) {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.innerHTML = '✨ ' + gettext("Analizar más");
            }
        } else {
            // Clean up ANY existing deep dive content to prevent duplication/stacking
            const existingSep = container.querySelector('.deep-dive-separator');
            if (existingSep) existingSep.remove();

            const existingContent = container.querySelector('.deep-dive-content');
            if (existingContent) existingContent.remove();

            // 5. Visual Separator
            const separator = document.createElement("div");
            separator.className = "deep-dive-separator"; // Add class for cleanup
            separator.style.cssText = 'border-top: 2px solid #a855f7; margin: 30px 0 20px 0; position: relative;';
            separator.innerHTML = `
                <span style="background: #18181b; padding: 4px 16px; color: #a855f7; font-size: 0.75rem; font-weight: 700; position: absolute; top: -12px; left: 20px; border: 1px solid #a855f7; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.5px;">
                    ✨ ${gettext("Análisis Detallado")}
                </span>
            `;
            container.appendChild(separator);

            // 6. Render deep dive content
            const extensionDiv = document.createElement("div");
            extensionDiv.className = "deep-dive-content"; // Add class for cleanup
            extensionDiv.style.marginTop = '10px';
            container.appendChild(extensionDiv);

            renderAiResponse(data, extensionDiv, { isDeepDive: false, query: query });

            // Hide the button completely after successful deep dive
            if (btn) {
                btn.style.display = 'none';
            }
        }

    } catch (e) {
        if (loadingDiv) loadingDiv.remove();
        console.error(e);

        // Re-enable button on error
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.innerHTML = '✨ ' + gettext("Analizar más");
        }
    }
}

function escaparHtmlTabla(valor) {
    return String(valor ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function columnaEsNumerica(columnas, filas, indice) {
    const titulo = String(columnas[indice] || '');
    if (/[€%]/.test(titulo) || /var/i.test(titulo)) return true;
    let vistos = 0;
    let numeros = 0;
    filas.forEach(function (fila) {
        const celda = fila && fila[indice];
        if (celda === null || celda === undefined || celda === '') return;
        vistos += 1;
        if (typeof celda === 'number' && !Number.isNaN(celda)) numeros += 1;
    });
    return vistos > 0 && numeros === vistos;
}

function htmlTablaAlineada(columnas, filas, maxFilas) {
    const cols = Array.isArray(columnas) ? columnas : [];
    const rows = (Array.isArray(filas) ? filas : []).slice(0, maxFilas);
    const ancho = Math.max(cols.length, (rows[0] || []).length);
    const numerica = [];
    for (let i = 0; i < ancho; i += 1) numerica.push(columnaEsNumerica(cols, rows, i));
    const fmt = function (n, decimales) {
        return new Intl.NumberFormat('es-ES', {
            minimumFractionDigits: decimales,
            maximumFractionDigits: decimales
        }).format(n);
    };
    let html = '<table style="width:max-content; border-collapse:collapse; font-size:0.9rem; font-variant-numeric:tabular-nums;">';
    if (cols.length > 0) {
        html += '<thead><tr style="border-bottom:1px solid #3f3f46; color:#a1a1aa;">';
        cols.forEach(function (titulo, idx) {
            const align = numerica[idx] ? 'right' : 'left';
            html += '<th style="padding:8px 8px; text-align:' + align + '; font-weight:600; vertical-align:bottom;">' + escaparHtmlTabla(titulo) + '</th>';
        });
        html += '</tr></thead>';
    }
    html += '<tbody>';
    rows.forEach(function (fila) {
        html += '<tr style="border-bottom:1px solid rgba(63,63,70,0.4);">';
        (fila || []).forEach(function (celda, idx) {
            const align = numerica[idx] ? 'right' : 'left';
            const titulo = String(cols[idx] || '');
            let texto;
            if (typeof celda === 'number' && !Number.isNaN(celda)) {
                if (titulo.includes('%') || /var/i.test(titulo)) texto = fmt(celda, 1);
                else if (titulo.includes('€')) texto = fmt(celda, 2);
                else texto = fmt(celda, Number.isInteger(celda) ? 0 : 2);
            } else {
                texto = escaparHtmlTabla(celda);
            }
            const nowrap = ' white-space:nowrap;';
            html += '<td style="padding:8px 8px; text-align:' + align + '; color:#e4e4e7; vertical-align:baseline;' + nowrap + '">' + texto + '</td>';
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    return html;
}

function anadirGrafico(fila, titulo, config) {
    if (!config) return;
    const bloque = document.createElement('div');
    bloque.className = 'ai-report-grafico';
    if (titulo) {
        const title = document.createElement('div');
        title.className = 'ai-report-seccion';
        title.textContent = titulo;
        bloque.appendChild(title);
    }
    const chartDiv = document.createElement('div');
    chartDiv.className = 'ai-report-lienzo';
    bloque.appendChild(chartDiv);
    fila.appendChild(bloque);
    renderAiChart(chartDiv, config);
}

function anadirTablaInforme(container, table, maxFilas) {
    if (!table || !Array.isArray(table.rows) || table.rows.length === 0) return;
    const title = document.createElement('div');
    title.className = 'ai-report-seccion';
    title.style.marginTop = '18px';
    title.textContent = table.title || gettext('Detalle');
    container.appendChild(title);
    const wrapper = document.createElement('div');
    wrapper.className = 'ai-report-tabla';
    const cols = Array.isArray(table.columns) ? table.columns : [];
    wrapper.innerHTML = htmlTablaAlineada(cols, table.rows, maxFilas);
    container.appendChild(wrapper);
}

function renderAiReport(container, data, isDeepDive = false) {
    if (!data || !data.kpis) return;

    const fmtNumber = (n, decimals) => {
        try {
            return new Intl.NumberFormat('es-ES', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n);
        } catch (e) {
            return String(n);
        }
    };
    const fmtMoney = (n) => fmtNumber(n, 2);
    const fmtPercent = (n) => fmtNumber(n, 1);
    const fmtKpiValue = (k) => {
        const v = k && k.value;
        const suffix = (k && k.suffix) ? String(k.suffix) : '';
        if (typeof v !== 'number') return (v === 0 ? '0' : (v || '--'));
        if (suffix === '€') return `${fmtMoney(v)} €`;
        if (suffix === '%') return `${fmtPercent(v)} %`;
        if (suffix === 'uds') return `${fmtNumber(v, 0)} ${suffix}`;
        if (suffix) return `${fmtNumber(v, 2)} ${suffix}`;
        return fmtMoney(v);
    };

    // 1. KPI Grid - Skip in Deep Dive (Redundant information)
    if (!isDeepDive) {
        const isRatios = String(data.key || '') === 'financiera_ratios';
        const groupOrder = ['liquidez', 'solvencia', 'gestion', 'rentabilidad', 'cobertura'];
        const groupLabels = { liquidez: gettext('Liquidez'), solvencia: gettext('Solvencia'), gestion: gettext('Gestión'), rentabilidad: gettext('Rentabilidad'), cobertura: gettext('Cobertura') };

        const section = document.createElement('div');
        section.className = 'ai-report-kpi-section';

        const renderCard = (k) => {
            const card = document.createElement('div');
            card.className = 'ai-report-kpi-card';
            const label = (k && k.label) ? k.label : gettext('Sin etiqueta');
            const changeText = (typeof k.change === 'number') ? (fmtPercent(k.change) + ' %') : (k.change || '');
            card.innerHTML = `
                <div class="ai-report-kpi-label">${label}</div>
                <div class="ai-report-kpi-value" style="color:${k.color || '#fff'}">${fmtKpiValue(k)}</div>
                <div class="ai-report-kpi-sub">${String(changeText).replace(/\\b(vs\\s+\\d{4}:)/i, '<strong>$1</strong>')}</div>
            `;
            return card;
        };

        if (isRatios) {
            const byGroup = {};
            (data.kpis || []).forEach(k => {
                const g = String(k && k.group || 'otros');
                if (!byGroup[g]) byGroup[g] = [];
                byGroup[g].push(k);
            });
            const groupsEl = document.createElement('div');
            groupsEl.className = 'ai-report-kpi-groups';

            groupOrder
                .filter(g => (byGroup[g] || []).length)
                .forEach(g => {
                    const gWrap = document.createElement('div');
                    gWrap.className = 'ai-report-kpi-group';
                    const gTitle = document.createElement('div');
                    gTitle.className = 'ai-report-kpi-group-title';
                    gTitle.textContent = groupLabels[g] || g;
                    const grid = document.createElement('div');
                    grid.className = 'ai-report-kpi-grid';
                    (byGroup[g] || []).forEach(k => grid.appendChild(renderCard(k)));
                    gWrap.appendChild(gTitle);
                    gWrap.appendChild(grid);
                    groupsEl.appendChild(gWrap);
                });

            section.appendChild(groupsEl);
        } else {
            const grid = document.createElement('div');
            grid.className = 'ai-report-kpi-grid';
            (data.kpis || []).forEach(k => grid.appendChild(renderCard(k)));
            section.appendChild(grid);
        }

        container.appendChild(section);
    }

    // 2. Charts
    // Initial View: Show Summary (Main Trend)
    if (!isDeepDive) {
        const fila = document.createElement('div');
        fila.className = 'ai-report-graficos';
        anadirGrafico(fila, '', data.chart_config);
        if (data.chart_pareto_clients) {
            anadirGrafico(fila, gettext("Distribución de Ventas por Cliente (Top)"), data.chart_pareto_clients);
        } else if (data.chart_pareto_products) {
            anadirGrafico(fila, gettext("Distribución de Ventas por Artículo (Top)"), data.chart_pareto_products);
        } else if (data.chart_pareto) {
            anadirGrafico(fila, gettext("Distribución (Top)"), data.chart_pareto);
        }
        if (fila.children.length) container.appendChild(fila);
        const topeInforme = (data.completo && data.table && Array.isArray(data.table.rows))
            ? data.table.rows.length
            : 30;
        anadirTablaInforme(container, data.table, topeInforme);
        if (data.chart_pareto || data.chart_pareto_clients || data.chart_pareto_products) {
            const hint = document.createElement('div');
            hint.className = 'ai-report-nota';
            hint.textContent = gettext("Dale a 'Analizar más' para ver desgloses y distribuciones.");
            container.appendChild(hint);
        }
    } else {
        // Deep Dive View: Show Details (Paretos, Concentration, etc.)
        let detailedRendered = false;
        const fila = document.createElement('div');
        fila.className = 'ai-report-graficos';
        if (data.chart_pareto_clients) {
            anadirGrafico(fila, gettext("Distribución de Ventas por Cliente (Pareto)"), data.chart_pareto_clients);
            detailedRendered = true;
        } else if (data.chart_pareto) {
            anadirGrafico(fila, gettext("Distribución de Ventas (Pareto Top 20)"), data.chart_pareto);
            detailedRendered = true;
        }
        if (data.chart_pareto_products) {
            anadirGrafico(fila, gettext("Distribución de Ventas por Artículo (Pareto)"), data.chart_pareto_products);
            detailedRendered = true;
        }
        if (data.chart_concentration) {
            const slice = (data.chart_concentration.data && Array.isArray(data.chart_concentration.data.labels))
                ? data.chart_concentration.data.labels.length
                : 5;
            anadirGrafico(fila, `${gettext("Concentración de Clientes")} (Top ${slice})`, data.chart_concentration);
            detailedRendered = true;
        }
        if (fila.children.length) container.appendChild(fila);
        if (data.table && Array.isArray(data.table.rows) && data.table.rows.length > 0) {
            const topeDetalle = data.completo ? data.table.rows.length : 50;
            anadirTablaInforme(container, data.table, topeDetalle);
            detailedRendered = true;
        }

        if (!detailedRendered) {
            const fallback = document.createElement('div');
            fallback.style.padding = "20px";
            fallback.style.textAlign = "center";
            fallback.style.color = "#71717a";
            fallback.style.fontStyle = "italic";
            // Check if we have standard chart config but NO special deep dive charts
            if (data.chart_config) {
                fallback.innerText = gettext("Este informe no contiene desgloses adicionales (Pareto), pero observa el gráfico principal arriba.");
            } else {
                fallback.innerText = gettext("No hay gráficos de desglose adicionales disponibles en este informe.");
            }
            container.appendChild(fallback);
        }
    }
}

function renderAiTable(container, rows, chartConfig, isDeepDive = false, metric = 'sales') {
    if (!rows || !Array.isArray(rows) || rows.length === 0) {
        container.innerText = "Error: " + gettext("Formato de tabla incorrecto o sin datos.");
        return;
    }

    const firstRow = rows[0];
    // [NEW] Helper for Month Mapping using Intl for automatic localization
    const getLocalizedMonth = (monthNum) => {
        const n = parseInt(monthNum);
        if (isNaN(n) || n < 1 || n > 12) return monthNum;

        // Use the language set in the HTML lang attribute or fallback to Spanish
        const lang = document.documentElement.lang || 'es';
        const date = new Date(2024, n - 1, 1);
        const monthName = new Intl.DateTimeFormat(lang, { month: 'short' }).format(date);
        // Capitalize and remove trailing dot if any (common in some locales)
        return (monthName.charAt(0).toUpperCase() + monthName.slice(1)).replace(/\.$/, '');
    };

    let html = `<div class="ai-report-tabla"><table style="width:100%; border-collapse: collapse; font-size: 0.9rem; font-variant-numeric: tabular-nums;">`;
    html += `<thead><tr style="border-bottom: 1px solid #3f3f46; color: #a1a1aa;">`;
    html += `<th style="padding: 8px 12px; text-align: left; white-space: nowrap; vertical-align: bottom;">${gettext('Mes')}</th>`;

    // Determine columns dynamically but enforce specific order if possible
    // Order: Ventas, Costos, Imp. Margen, Margen %, Precio Medio, Pedidos
    const preferredOrder = ['val', 'coste', 'imp_margin', 'margin', 'ticket', 'ops'];

    // Get all available keys from first row to detect what we have
    const allKeys = Object.keys(firstRow);
    // [FIX] Robust Case-Insensitive Ignore List
    const ignoreKeys = ['label', 'extra', 'row_id', 'item', 'value'];

    const metricKeys = allKeys.filter(k => {
        const lowerK = k.toLowerCase().trim();
        // Ignore if in ignoreKeys OR if it is one of the preferred keys (which are handled separately)
        return !ignoreKeys.includes(lowerK) && !preferredOrder.includes(k);
    });

    // Merge preferred with any extra keys found
    let displayKeys = preferredOrder.filter(k =>
        k === 'val' || k === 'coste' || k === 'imp_margin' || k === 'margin' || k === 'ticket' || k === 'ops' || metricKeys.includes(k)
    );

    // [FIX] Hide irrelevant columns for Purchase/Cost mode
    if (metric === 'purchase_amount' || metric === 'purchase' || metric === 'purchase_order') {
        // Purchases don't have "Cost", "Margin", "Margin %" usually (unless we have Sales Price which we don't)
        // So hide 'coste', 'imp_margin', 'margin'
        const hide = ['coste', 'imp_margin', 'margin'];
        displayKeys = displayKeys.filter(k => !hide.includes(k));
    }

    // Totals Accumulators
    let totalVal = 0;
    let totalCoste = 0;
    let totalOps = 0;
    let totalImpMargin = 0;

    displayKeys.forEach(k => {
        let title = k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, ' ');
        if (k === 'val') {
            if (metric === 'purchase_amount' || metric === 'purchase') title = gettext('Compras');
            else if (metric === 'purchase_order') title = gettext('Importe Pedidos');
            else if (metric === 'cost') title = gettext('Coste Total');
            else title = gettext('Ventas');
        }
        if (k === 'coste') title = gettext('Costos');
        if (k === 'imp_margin') title = gettext('Imp. Margen');
        if (k === 'ops') {
            if (metric === 'purchase_amount' || metric === 'purchase') title = gettext('Albaranes');
            else title = gettext('Pedidos');
        }
        if (k === 'ticket') title = gettext('Precio Medio');
        if (k === 'margin') title = gettext('Margen %');

        const align = 'right';
        html += `<th style="padding: 8px 12px; text-align: ${align}; white-space: nowrap; vertical-align: bottom; width: 1%;">${title}</th>`;
    });
    html += `</tr></thead><tbody>`;

    rows.forEach(r => {
        // Calculate derived metrics if missing
        const val = r.val || 0;
        const coste = r.coste || 0;
        const ops = r.ops || 0;
        const impMargin = val - coste;

        // Accumulate totals
        totalVal += val;
        totalCoste += coste;
        totalOps += ops;
        totalImpMargin += impMargin;

        const margin = val !== 0 ? (impMargin / val) * 100 : 0;
        const ticket = ops !== 0 ? val / ops : 0;

        // Inject derived into row object for rendering
        r.imp_margin = impMargin;
        r.margin = margin;
        r.ticket = ticket;
        // Ensure ops and coste are present for loop
        r.ops = ops;
        r.coste = coste;

        html += `<tr style="border-bottom: 1px solid #27272a; color: #e4e4e7;">`;

        // Label Mapping
        let label = r.label || r.Item || 'N/D';
        label = getLocalizedMonth(label);

        html += `<td style="padding: 8px 12px; text-align: left;">${label}</td>`;

        displayKeys.forEach(k => {
            let valToRender = r[k];

            // Format numbers
            if (typeof valToRender === 'number') {
                if (k === 'margin') {
                    const marginVal = valToRender.toFixed(1) + '%';
                    // Colorize Margin
                    const color = valToRender > 0 ? '#4ade80' : (valToRender < 0 ? '#ef4444' : '#e4e4e7');
                    valToRender = `<span style="color:${color}">${marginVal}</span>`;
                } else if (k === 'ops') {
                    valToRender = Math.round(valToRender).toLocaleString('es-ES');
                } else {
                    valToRender = valToRender.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
                    if (k === 'imp_margin') {
                        const color = r[k] > 0 ? '#4ade80' : (r[k] < 0 ? '#ef4444' : '#e4e4e7');
                        valToRender = `<span style="color:${color}">${valToRender}</span>`;
                    }
                }
            } else if (valToRender === undefined) {
                valToRender = '-';
            }

            html += `<td style="padding: 8px 12px; text-align: right; white-space: nowrap; width: 1%;">${valToRender}</td>`;
        });
        html += `</tr>`;
    });

    // --- GRAND TOTALS ROW ---
    const totalMargin = totalVal !== 0 ? (totalImpMargin / totalVal) * 100 : 0;
    const totalTicket = totalOps !== 0 ? totalVal / totalOps : 0;

    html += `<tr style="border-top: 2px solid #52525b; font-weight: bold; background: rgba(255,255,255,0.02);">`;
    html += `<td style="padding: 8px 12px; text-align: left;">TOTAL</td>`;

    displayKeys.forEach(k => {
        let valToRender = 0;
        if (k === 'val') valToRender = totalVal;
        else if (k === 'coste') valToRender = totalCoste;
        else if (k === 'imp_margin') valToRender = totalImpMargin;
        else if (k === 'ops') valToRender = totalOps;
        else if (k === 'margin') valToRender = totalMargin;
        else if (k === 'ticket') valToRender = totalTicket;

        if (typeof valToRender === 'number') {
            if (k === 'margin') {
                valToRender = valToRender.toFixed(1) + '%';
            } else if (k === 'ops') {
                valToRender = Math.round(valToRender).toLocaleString('es-ES');
            } else {
                valToRender = valToRender.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' €';
            }
        }

        html += `<td style="padding: 8px 12px; text-align: right; white-space: nowrap; width: 1%;">${valToRender}</td>`;
    });

    // [FIX] Add Total for 'Value' column if present
    // The previous implementation was missing the accumulator for the 'value' column in the total row.
    // However, looking at the code, 'val' IS the 'Value' column (Ventas).
    // The user screenshot showed a separate 'Value' column with 0,00 €.
    // This suggests 'Value' might be coming from 'extra' or a misinterpretation of keys.
    // Let's ensure 'val' is treated as 'Ventas' and we don't have a duplicate 'Value' column.

    // Wait, the screenshot shows: Mes, Ventas, Costos, Precio Medio, Margen, Pedidos, Value.
    // 'Value' is likely 'val' appearing twice because 'val' was not filtered out from 'metricKeys' correctly in some cases?
    // In line 615: const metricKeys = allKeys.filter(k => !ignoreKeys.includes(k) && k !== 'val' && k !== 'coste' && k !== 'ops');
    // If the backend returns 'Value' as a key, it would be in metricKeys.
    // But our Python code returns 'val' alias.
    // Let's look at the screenshot again. The last column is "Value".
    // This usually happens if there is a 'value' key in the row object that is NOT 'val'.
    // Or if ApexCharts or some library injected it?
    // Ah, 'val' is used for the chart. Maybe the backend sends 'value'?
    // Let's filter out 'value' explicitly if it's redundant.

    html += `</tr>`;

    html += `</tbody></table></div>`;

    // Set table HTML
    container.innerHTML = html;

    // [NEW] Render Chart if Config Exists
    if (chartConfig) {
        if (!isDeepDive) {
            // Standard View: Table + Chart
            const chartDiv = document.createElement('div');
            chartDiv.style.marginTop = "1rem";
            chartDiv.style.minHeight = "250px"; // Ensure visibility
            container.appendChild(chartDiv);
            renderAiChart(chartDiv, chartConfig);
        }
        // If DeepDive, usually we just show table or chart separately, but let's keep it simple
    }
}

// --- Training Mode Toggle ---
// --- Settings Tabs Logic ---
// --- Settings Tabs Logic ---
function switchSettingsTab(tabName) {
    const tabs = ['user', 'dev', 'impl'];

    tabs.forEach(t => {
        const tabEl = document.getElementById(`settings-tab-${t}`);
        const btnEl = document.getElementById(`btn-tab-${t}`);

        if (t === tabName) {
            if (tabEl) tabEl.style.display = 'block';
            if (btnEl) {
                btnEl.classList.add('active');
                btnEl.style.borderBottom = '2px solid #a855f7';
                btnEl.style.color = '#fff';
            }
        } else {
            if (tabEl) tabEl.style.display = 'none';
            if (btnEl) {
                btnEl.classList.remove('active');
                btnEl.style.borderBottom = 'none';
                btnEl.style.color = '#a1a1aa';
            }
        }
    });
}

// --- Factory Reset Logic ---
// --- Factory Reset Logic (Custom Modal) ---
function requestFactoryReset() {
    const modal = document.getElementById('reset-auth-modal');
    if (!modal) {
        if (window.showToast) window.showToast("No se encontró el modal de reset", true);
        return;
    }
    modal.style.display = 'flex';
    const settingsOverlay = document.getElementById('settings-modal-overlay');
    if (settingsOverlay) {
        try {
            settingsOverlay.dataset.prevPointer = settingsOverlay.style.pointerEvents || '';
            settingsOverlay.style.pointerEvents = 'none';
        } catch (e) {}
    }
    document.body.classList.add('modal-open');
    setTimeout(() => {
        const pwdInput = document.getElementById('reset-auth-password');
        if (pwdInput) {
            pwdInput.value = '';
            pwdInput.focus();
        }
    }, 100);
}

function closeAuthModal() {
    const modal = document.getElementById('reset-auth-modal');
    if (modal) modal.style.display = 'none';
    const settingsOverlay = document.getElementById('settings-modal-overlay');
    if (settingsOverlay) {
        try {
            const prev = settingsOverlay.dataset.prevPointer || '';
            settingsOverlay.style.pointerEvents = prev;
            delete settingsOverlay.dataset.prevPointer;
        } catch (e) {}
    }
    document.body.classList.remove('modal-open');
}

function closeResetPreviewModal() {
    const modal = document.getElementById('reset-preview-modal');
    if (modal) modal.style.display = 'none';
}

function openPgTablesPreview() {
    const modal = document.getElementById('reset-preview-modal');
    const t = document.getElementById('preview-tables');
    const u = document.getElementById('preview-users');
    const prefSel = document.getElementById('preview-filter-prefix');
    if (modal) modal.style.display = 'flex';
    if (t) t.style.display = 'block';
    if (u) u.style.display = 'none';
    if (prefSel) {
        prefSel.value = "";
    }
    reloadPgTables();
}

function openUsersPreview() {
    const modal = document.getElementById('reset-preview-modal');
    const t = document.getElementById('preview-tables');
    const u = document.getElementById('preview-users');
    if (modal) modal.style.display = 'flex';
    if (t) t.style.display = 'none';
    if (u) u.style.display = 'block';
    reloadUsersPreview();
}

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B','KB','MB','GB','TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    const v = parseFloat((bytes / Math.pow(k, i)).toFixed(2));
    return `${v} ${sizes[i]}`;
}

function openWorkflowProgress(jobId, sourceDb) {
    const overlay = document.getElementById('reset-report-modal');
    const tbody = document.getElementById('reset-report-body');
    const sub = document.getElementById('reset-report-subtitle');
    const src = document.getElementById('reset-sync-source');
    const vis = document.getElementById('reset-sync-visual');
    if (tbody) tbody.innerHTML = '';
    if (sub) sub.innerText = `Migración en curso`;
    if (src) src.innerText = sourceDb ? `Origen MSSQL: ${sourceDb}` : '';
    if (vis) vis.style.display = 'block';
    if (overlay) overlay.style.display = 'flex';
    startSyncPolling(jobId);
}

async function reloadPgTables() {
    const body = document.getElementById('reset-preview-tables-body');
    if (body) body.innerHTML = '';
    const prefSel = document.getElementById('preview-filter-prefix');
    const sortSel = document.getElementById('preview-sort');
    const ordSel = document.getElementById('preview-order');
    const prefix = prefSel ? (prefSel.value || '') : '';
    let sort = 'size';
    if (sortSel) {
        const v = sortSel.value;
        sort = v === 'rows' ? 'rows' : (v === 'name' ? 'name' : 'size');
    }
    const order = ordSel ? (ordSel.value || 'desc') : 'desc';
    const q = new URLSearchParams();
    if (prefix) q.set('prefix', prefix);
    if (sort) q.set('sort', sort);
    if (order) q.set('order', order);
    const url = `/api/etl/analytics/tables?${q.toString()}`;
    try {
        const res = await fetch(url);
        const data = await res.json();
        const rows = (data && Array.isArray(data.tables)) ? data.tables : [];
        if (body) {
            rows.forEach(r => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="padding:4px 6px; color:#e4e4e7;">${r.table}</td>
                    <td style="padding:4px 6px; color:#a1a1aa;">${r.category}</td>
                    <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${r.approx_rows}</td>
                    <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${formatBytes(r.total_bytes)}</td>
                `;
                body.appendChild(tr);
            });
        }
    } catch (e) {
        if (window.showToast) window.showToast("No se pudieron cargar tablas", true);
    }
}

async function reloadUsersPreview() {
    const body = document.getElementById('reset-preview-users-body');
    if (body) body.innerHTML = '';
    try {
        const res = await fetch(`/api/etl/analytics/users/preview_deletion`);
        const data = await res.json();
        const users = (data && Array.isArray(data.users)) ? data.users : [];
        if (body) {
            users.forEach(u => {
                const tr = document.createElement('tr');
                const su = u.is_superuser ? 'Sí' : 'No';
                const st = u.is_staff ? 'Sí' : 'No';
                const dj = u.date_joined ? new Date(u.date_joined).toLocaleString() : '';
                tr.innerHTML = `
                    <td style="padding:4px 6px; color:#e4e4e7;">${u.username}</td>
                    <td style="padding:4px 6px; color:#a1a1aa;">${u.email || ''}</td>
                    <td style="padding:4px 6px; color:#a1a1aa;">${su}</td>
                    <td style="padding:4px 6px; color:#a1a1aa;">${st}</td>
                    <td style="padding:4px 6px; color:#a1a1aa;">${dj}</td>
                `;
                body.appendChild(tr);
            });
        }
    } catch (e) {
        if (window.showToast) window.showToast("No se pudieron cargar usuarios", true);
    }
}
async function dropNonTplAuthTables() {
    try {
        if (window.showToast) window.showToast("Ejecutando borrado masivo de tablas (excepto tpl_ y auth_)...", false);
        const res = await fetch('/api/etl/analytics/drop_non_tpl_auth', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
            const n = data.count || 0;
            if (window.showToast) window.showToast(`✅ Borradas ${n} tablas.`, false);
            reloadPgTables();
        } else {
            if (window.showToast) window.showToast(`❌ Error: ${data.message || 'no disponible'}`, true);
        }
    } catch (e) {
        if (window.showToast) window.showToast("❌ Error al borrar tablas.", true);
    }
}
async function confirmWorkflowAction() {
    try {
        const dbSel = document.getElementById('reset-mssql-db-select');
        const dbInp = document.getElementById('reset-mssql-db');
        const empresas = getSelectedEmpresas();
        const db = (dbSel && dbSel.value) ? dbSel.value : (dbInp ? dbInp.value : '');
        if (!db || db.trim() === '') {
            if (window.showToast) window.showToast("Selecciona una base de datos MSSQL", true);
            return;
        }
        if (!empresas || empresas.length === 0) {
            if (window.showToast) window.showToast("Selecciona al menos una empresa", true);
            return;
        }
        const q = [...empresas];
        const total = q.length;
        const subtitle = document.getElementById('reset-report-subtitle');
        const migratedEmpresas = [];
        
        // MOSTRAR MODAL Y PREPARAR UI
        const reportModal = document.getElementById('reset-report-modal');
        if(reportModal) {
            reportModal.style.display = 'flex';
            switchReportTab('log');
            const btnResumen = document.getElementById('btn-tab-reporte-resumen');
            if(btnResumen) btnResumen.style.display = 'none';
            const tbody = document.getElementById('reset-report-body');
            if(tbody) tbody.innerHTML = '';
            const sv = document.getElementById('reset-sync-visual');
            if(sv) sv.style.display = 'none';
        }
        
        async function runNext() {
            if (q.length === 0) {
                if (window.showToast) window.showToast("Migración inicial completada", false);
                window._onResetJobDone = null;
                
                const pb = document.getElementById('reset-sync-progress');
                if(pb) { pb.style.width = '100%'; pb.style.background = '#10b981'; }
                const sm = document.getElementById('reset-sync-message');
                if(sm) sm.innerText = "Proceso finalizado";
                if (subtitle) subtitle.innerText = "Todas las migraciones completadas.";
                
                if(migratedEmpresas.length > 0) {
                    fetchFinalSummary(migratedEmpresas);
                }
                return;
            }
            const current = q.shift();
            try {
                const currentLabel = getEmpresaLabelById(current);
                const params = new URLSearchParams();
                params.set('empresa_id', current);
                if (currentLabel) params.set('empresa_label', currentLabel);
                params.set('sync_type', 'all');
                params.set('years_count', '10');
                params.set('fast_bulk', 'true');
                params.set('mssql_database', db);
                params.set('wipe', 'true');
                const res = await fetch(`/api/etl/initial_load?${params.toString()}`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': (window.getCookie ? window.getCookie('csrftoken') : (document.cookie||'')) }
                });
                const data = await res.json();
                if (res.ok && data && data.job_id) {
                    migratedEmpresas.push(current);
                    const labelText = currentLabel || current;
                    if (subtitle) subtitle.innerText = `Migración en curso · ${labelText} (${total - q.length}/${total})`;
                    window._onResetJobDone = function (info) {
                        if (!info || !info.jobId) return;
                        // Encadenar siguiente trabajo tras completar o error
                        setTimeout(runNext, 400);
                    };
                    openWorkflowProgress(data.job_id, db);
                } else {
                    const msg = (data && (data.error || data.message)) ? (data.error || data.message) : 'No se pudo iniciar la migración';
                    if (window.showToast) window.showToast(`Error: ${msg}`, true);
                    // Intentar siguiente
                    setTimeout(runNext, 400);
                }
            } catch (e) {
                if (window.showToast) window.showToast("Error de conexión al iniciar migración", true);
                setTimeout(runNext, 400);
            }
        }
        runNext();
    } catch (e) {
        if (window.showToast) window.showToast("Error al preparar la migración", true);
    }
}
function closeResetReportModal() {
    const modal = document.getElementById('reset-report-modal');
    if (modal) modal.style.display = 'none';
}

function showResetReport(report) {
    const overlay = document.getElementById('reset-report-modal');
    const tbody = document.getElementById('reset-report-body');
    const empresaDiv = document.getElementById('reset-report-empresa');
    const sub = document.getElementById('reset-report-subtitle');
    const riDiv = document.getElementById('reset-report-ri');
    const src = document.getElementById('reset-sync-source');
    if (!overlay || !tbody) return;
    tbody.innerHTML = '';
    const ts = report && report.timestamp ? new Date(report.timestamp * 1000) : new Date();
    if (sub) sub.innerText = `Generado: ${ts.toLocaleString()}`;
    if (empresaDiv) {
        const ok = report && report.empresa_empty === true;
        const before = report && typeof report.empresa_before === 'number' ? report.empresa_before : 0;
        const afterDel = report && typeof report.empresa_after_delete === 'number' ? report.empresa_after_delete : 0;
        const afterRel = report && typeof report.empresa_after_reload === 'number' ? report.empresa_after_reload : 0;
        const badge = ok ? '✅' : '❌';
        empresaDiv.innerHTML = `${badge} Empresas tras limpieza: ${afterDel}. Antes: ${before}. Tras recarga: ${afterRel}.`;
        empresaDiv.style.color = ok ? '#34d399' : '#f87171';
    }
    const rows = (report && Array.isArray(report.tables)) ? report.tables : [];
    rows.forEach(r => {
        const tr = document.createElement('tr');
        const st = (r.after === 0) ? 'OK' : 'ERROR';
        const stColor = (r.after === 0) ? '#34d399' : '#f87171';
        tr.innerHTML = `
            <td style="padding:4px 6px; color:#e4e4e7;">${r.table}</td>
            <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${r.before}</td>
            <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${r.deleted}</td>
            <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${r.after}</td>
            <td style="padding:4px 6px; font-weight:600; color:${stColor};">${st}</td>
        `;
        tbody.appendChild(tr);
    });
    if (riDiv) {
        const total = report && typeof report.fk_total === 'number' ? report.fk_total : 0;
        const notValid = report && typeof report.fk_not_valid === 'number' ? report.fk_not_valid : 0;
        const ok = notValid === 0;
        const badge = ok ? '✅' : '❌';
        riDiv.innerText = `${badge} Integridad referencial: FKs=${total}, no validadas=${notValid}`;
        riDiv.style.color = ok ? '#34d399' : '#f87171';
    }
    if (src) {
        src.innerText = '';
    }
    overlay.style.display = 'flex';
}

async function confirmFactoryResetAction() {
    try {
        const dbSel = document.getElementById('reset-mssql-db-select');
        const dbInp = document.getElementById('reset-mssql-db');
        const reloadChk = document.getElementById('reset-reload-companies');
        // Asumimos que si hay un checkbox de usuarios, lo usaríamos. Si no, por defecto false.
        // Pero para Factory Reset completo, borrar usuarios suele ser deseado.
        // Vamos a asumir false por seguridad salvo que exista UI.
        const deleteUsers = false; // TODO: Agregar checkbox en UI si se requiere

        const db = (dbSel && dbSel.value) ? dbSel.value : (dbInp ? dbInp.value : '');
        const doReload = reloadChk ? reloadChk.checked : false;

        if (!confirm("⚠️ ADVERTENCIA: Esta acción BORRARÁ TODOS LOS DATOS (metrics_*, datiadb_*) de la base de datos de análisis.\n\n¿Estás seguro de continuar con el Factory Reset Global?")) {
            return;
        }

        const params = new URLSearchParams();
        params.set('force_reset', 'true');
        params.set('sync_type', 'all'); // Reset completo
        params.set('delete_users', deleteUsers ? 'true' : 'false');
        params.set('reload_companies', doReload ? 'true' : 'false');
        if (db) params.set('mssql_database', db);

        const res = await fetch(`/api/etl/sync`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': (window.getCookie ? window.getCookie('csrftoken') : (document.cookie||'')) 
            },
            body: params
        });

        const data = await res.json();
        if (res.ok && data && data.job_id) {
            closeAuthModal();
            if (window.showToast) window.showToast("Factory Reset iniciado", false);
            openWorkflowProgress(data.job_id, db);
        } else {
            const msg = (data && (data.error || data.message)) ? (data.error || data.message) : 'No se pudo iniciar el Factory Reset';
            if (window.showToast) window.showToast(`Error: ${msg}`, true);
        }
    } catch (e) {
        if (window.showToast) window.showToast("Error de conexión al iniciar reset", true);
    }
}

async function detectMSSQLDatabases() {
    try {
        const res = await fetch(`/api/etl/mssql/databases`);
        const data = await res.json();
        const list = Array.isArray(data.databases) ? data.databases : [];
        const dl = document.getElementById('mssql-db-list');
        const sel = document.getElementById('reset-mssql-db-select');
        const inp = document.getElementById('reset-mssql-db');
        if (dl) {
            dl.innerHTML = list.map(n => `<option value="${n}">`).join('');
        }
        if (sel) {
            let html = '';
            if (list.length > 0) {
                html = ['<option value="">Selecciona una base detectada…</option>'].concat(
                    list.map(n => `<option value="${n}">${n}</option>`)
                ).join('');
            } else {
                html = '<option value="">Sin resultados (introduce manualmente)</option>';
            }
            sel.innerHTML = html;
            sel.style.display = 'block';
            sel.onchange = function () {
                const val = sel.value || '';
                if (inp) inp.value = val;
                if (val) detectMSSQLEmpresas(val);
            };
            // Autoselección y precarga si no hay valor manual
            if (!inp || !inp.value) {
                const first = list[0];
                if (first) {
                    sel.value = first;
                    if (inp) inp.value = first;
                    detectMSSQLEmpresas(first);
                }
            }
        }
        // Vincular eventos para carga manual
        if (inp && !inp.dataset.empHandler) {
            inp.addEventListener('change', () => {
                const v = (inp.value || '').trim();
                if (v) detectMSSQLEmpresas(v);
            });
            inp.addEventListener('blur', () => {
                const v = (inp.value || '').trim();
                if (v) detectMSSQLEmpresas(v);
            });
            inp.dataset.empHandler = '1';
        }
        if (list.length === 0 && window.showToast) window.showToast("No se pudieron detectar bases. Introduce el nombre manualmente.", true);
    } catch (e) {
        const sel = document.getElementById('reset-mssql-db-select');
        if (sel) {
            sel.innerHTML = '<option value="">Sin resultados (introduce manualmente)</option>';
            sel.style.display = 'block';
        }
        if (window.showToast) window.showToast("No se pudieron detectar bases. Introduce el nombre manualmente.", true);
    }
}

async function detectMSSQLEmpresas(dbName) {
    try {
        const block = document.getElementById('reset-empresa-block');
        const sel = document.getElementById('reset-empresa-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">Cargando…</option>';
        if (block) block.style.display = 'block';
        const res = await fetch(`/api/etl/mssql/empresas?db=${encodeURIComponent(dbName)}`);
        const data = await res.json();
        const items = Array.isArray(data.items) ? data.items : [];
        let html = '<option value="">Selecciona una empresa…</option>';
        for (const it of items) {
            const val = typeof it.empresa !== 'undefined' ? String(it.empresa) : '';
            const text = (it.nombre || val);
            html += `<option value="${val}">${text}</option>`;
        }
        sel.innerHTML = html;
        // Ajustar altura para visualizar todas las empresas sin scroll (con un tope por viewport)
        const rows = Math.max(6, (items.length + 1));
        sel.size = rows;
        try {
            const rowPx = 26; // aproximación de alto por fila
            const maxPx = Math.floor(window.innerHeight * 0.7);
            sel.style.height = Math.min(maxPx, rows * rowPx) + 'px';
            sel.style.overflowY = 'auto';
        } catch (_) {}
        updateEmpresaSelectionCounter();
        if (!sel.dataset.multHandler) {
            sel.addEventListener('change', updateEmpresaSelectionCounter);
            sel.dataset.multHandler = '1';
        }
    } catch (e) {
        const sel = document.getElementById('reset-empresa-select');
        if (sel) sel.innerHTML = '<option value="">No se pudieron cargar empresas</option>';
        if (window.showToast) window.showToast("No se pudieron cargar empresas", true);
    }
}

function getSelectedEmpresas() {
    const sel = document.getElementById('reset-empresa-select');
    if (!sel) return [];
    const arr = [];
    for (const opt of sel.options) {
        if (opt.selected && opt.value) arr.push(opt.value);
    }
    return arr;
}

function getEmpresaLabelById(val) {
    const sel = document.getElementById('reset-empresa-select');
    if (!sel) return '';
    for (const opt of sel.options) {
        if (opt.value === val) return opt.text || val;
    }
    return val;
}

function updateEmpresaSelectionCounter() {
    const cnt = document.getElementById('reset-empresa-count');
    if (!cnt) return;
    const arr = getSelectedEmpresas();
    cnt.innerText = arr.length > 0 ? `${arr.length} seleccionadas` : '';
}

function startSyncPolling(jobId) {
    const msgEl = document.getElementById('reset-sync-message');
    const bar = document.getElementById('reset-sync-progress');
    const tbody = document.getElementById('reset-report-body');
    const overlay = document.getElementById('reset-report-modal');
    let toolbar = document.getElementById('reset-monitor-toolbar');
    if (!toolbar && overlay) {
        toolbar = document.createElement('div');
        toolbar.id = 'reset-monitor-toolbar';
        toolbar.style.display = 'flex';
        toolbar.style.alignItems = 'center';
        toolbar.style.justifyContent = 'space-between';
        toolbar.style.gap = '8px';
        toolbar.style.padding = '6px 0';
        const left = document.createElement('div');
        left.style.display = 'flex';
        left.style.gap = '12px';
        const right = document.createElement('div');
        right.style.display = 'flex';
        right.style.gap = '8px';
        const conn = document.createElement('span');
        conn.id = 'reset-conn';
        conn.style.fontWeight = '600';
        conn.style.color = '#34d399';
        conn.innerText = 'Online';
        const timer = document.createElement('span');
        timer.id = 'reset-timer';
        timer.style.color = '#a1a1aa';
        timer.innerText = '00:00';
        const stage = document.createElement('span');
        stage.id = 'reset-stage';
        stage.style.color = '#e4e4e7';
        stage.innerText = '';
        const curTable = document.createElement('span');
        curTable.id = 'reset-table';
        curTable.style.color = '#a1a1aa';
        curTable.innerText = '';
        const eta = document.createElement('span');
        eta.id = 'reset-eta';
        eta.style.color = '#a1a1aa';
        eta.innerText = '';
        const rps = document.createElement('span');
        rps.id = 'reset-rps';
        rps.style.color = '#a1a1aa';
        rps.innerText = '';
        const pauseBtn = document.createElement('button');
        pauseBtn.id = 'reset-pause-btn';
        pauseBtn.innerText = 'Pausar';
        pauseBtn.style.padding = '6px 10px';
        pauseBtn.style.borderRadius = '6px';
        pauseBtn.style.border = '1px solid #3f3f46';
        pauseBtn.style.background = '#18181b';
        pauseBtn.style.color = '#e4e4e7';
        const exportJson = document.createElement('button');
        exportJson.id = 'reset-export-json';
        exportJson.innerText = 'Export JSON';
        exportJson.style.padding = '6px 10px';
        exportJson.style.borderRadius = '6px';
        exportJson.style.border = '1px solid #3f3f46';
        exportJson.style.background = '#18181b';
        exportJson.style.color = '#e4e4e7';
        const exportCsv = document.createElement('button');
        exportCsv.id = 'reset-export-csv';
        exportCsv.innerText = 'Export CSV';
        exportCsv.style.padding = '6px 10px';
        exportCsv.style.borderRadius = '6px';
        exportCsv.style.border = '1px solid #3f3f46';
        exportCsv.style.background = '#18181b';
        exportCsv.style.color = '#e4e4e7';
        left.appendChild(conn);
        left.appendChild(timer);
        left.appendChild(stage);
        left.appendChild(curTable);
        left.appendChild(rps);
        left.appendChild(eta);
        right.appendChild(pauseBtn);
        right.appendChild(exportJson);
        right.appendChild(exportCsv);
        toolbar.appendChild(left);
        toolbar.appendChild(right);
        const containerToolbar = overlay.querySelector('.modal-card') || overlay;
        containerToolbar.insertBefore(toolbar, containerToolbar.firstChild);
        const logBox = document.getElementById('reset-sync-log') || document.createElement('div');
        if (!logBox.id) logBox.id = 'reset-sync-log';
        logBox.style.marginTop = '8px';
        logBox.style.maxHeight = '160px';
        logBox.style.overflow = 'auto';
        logBox.style.fontSize = '12px';
        logBox.style.border = '1px solid #27272a';
        logBox.style.borderRadius = '6px';
        logBox.style.padding = '6px';
        const containerLog = overlay.querySelector('.modal-card') || overlay;
        containerLog.appendChild(logBox);
        // Stage progress bar
        let stageWrap = document.getElementById('reset-stagebar-wrap');
        if (!stageWrap) {
            stageWrap = document.createElement('div');
            stageWrap.id = 'reset-stagebar-wrap';
            stageWrap.style.margin = '8px 0 6px 0';
            stageWrap.style.height = '8px';
            stageWrap.style.background = '#1f2937';
            stageWrap.style.border = '1px solid #27272a';
            stageWrap.style.borderRadius = '6px';
            const inner = document.createElement('div');
            inner.id = 'reset-stagebar';
            inner.style.height = '100%';
            inner.style.width = '0%';
            inner.style.transition = 'width 250ms linear';
            inner.style.background = 'linear-gradient(90deg, #3b82f6, #22c55e)';
            inner.style.borderRadius = '6px';
            stageWrap.appendChild(inner);
            const containerStage = overlay.querySelector('.modal-card') || overlay;
            containerStage.insertBefore(stageWrap, logBox);
            let stageMeta = document.getElementById('reset-stagebar-meta');
            if (!stageMeta) {
                stageMeta = document.createElement('div');
                stageMeta.id = 'reset-stagebar-meta';
                stageMeta.style.display = 'flex';
                stageMeta.style.justifyContent = 'flex-end';
                stageMeta.style.gap = '8px';
                stageMeta.style.fontSize = '12px';
                stageMeta.style.color = '#a1a1aa';
                const cnt = document.createElement('span');
                cnt.id = 'reset-stagebar-count';
                cnt.innerText = '';
                stageMeta.appendChild(cnt);
                containerStage.insertBefore(stageMeta, logBox);
            }
        }
    }
    try {
        const sumBox = document.getElementById('reset-summary');
        if (sumBox && sumBox.parentNode) sumBox.parentNode.removeChild(sumBox);
    } catch (_) {}
    let lastPct = 0;
    let lastTs = Date.now();
    let lastServerOk = true;
    let lastLogTs = '';
    let stopped = false;
    const tableTimers = {};
    const tableLastStatus = {};
    let activeTable = '';
    function fmt(ms) {
        const s = Math.max(0, Math.floor(ms / 1000));
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const ss = s % 60;
        if (h > 0) return `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${ss.toString().padStart(2,'0')}`;
        return `${m.toString().padStart(2,'0')}:${ss.toString().padStart(2,'0')}`;
    }
    async function post(url) {
        try {
            const res = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': (window.getCookie ? window.getCookie('csrftoken') : (document.cookie||'')) } });
            return await res.json();
        } catch (e) { return null; }
    }
    const tick = async () => {
        if (stopped) return;
        try {
            const ctrl = new AbortController();
            const to = setTimeout(() => ctrl.abort(), 5000);
            const res = await fetch(`/api/etl/status/${jobId}`, { signal: ctrl.signal });
            clearTimeout(to);
            const job = await res.json();
            const pct = job && typeof job.progress === 'number' ? job.progress : 0;
            const message = job && job.message ? job.message : '';
            const st = job && job.status ? job.status : 'pending';
            const activeId = (job && job.child_id) ? job.child_id : jobId;
            const tel = (job && job.telemetry) ? job.telemetry : {};
            const elapsed = tel.elapsed_ms || 0;
            const etaMs = tel.eta_ms || null;
            const stagePct = typeof job.stage_progress === 'number' ? job.stage_progress : null;
            const stageName = job && job.stage ? job.stage : '';
            const now = Date.now();
            const dt = Math.max(1, (now - lastTs)) / 1000;
            const dp = Math.max(0, pct - lastPct);
            const pps = dp / dt;
            lastPct = pct;
            lastTs = now;
            if (bar) bar.style.width = `${pct}%`;
            if (msgEl) msgEl.innerText = `${pct}% ${message}`;
            const connEl = document.getElementById('reset-conn');
            if (connEl) {
                connEl.innerText = 'Online';
                connEl.style.color = '#34d399';
            }
            lastServerOk = true;
            const timerEl = document.getElementById('reset-timer');
            if (timerEl) timerEl.innerText = fmt(elapsed);
            const stageEl = document.getElementById('reset-stage');
            const empresaInfo = document.getElementById('reset-report-empresa');
            let stageLabel = '';
            if (stageName === 'cleanup') stageLabel = 'Fase 1 – Eliminación de datos';
            else if (stageName === 'sync') stageLabel = 'Fase 2 – Migración datiadb';
            else if (stageName === 'metrics') stageLabel = 'Fase 3 – Generación de métricas';
            if (stageEl) {
                stageEl.innerText = stageLabel ? `${stageLabel} ${stagePct !== null ? `(${stagePct}%)` : ''}` : '';
                stageEl.style.color = (job && job.last_error) ? '#f87171' : '#e4e4e7';
            }
            if (empresaInfo) {
                const empName = job && job.empresa_name ? job.empresa_name : '';
                const empId = job && job.empresa_id ? job.empresa_id : '';
                const year = job && job.target_year ? job.target_year : '';
                const empText = empName ? empName : (empId ? `Empresa ${empId}` : '');
                const yearText = year ? `Ejercicio ${year}` : 'Ejercicios: todos';
                const parts = [];
                if (empText) parts.push(empText);
                if (yearText) parts.push(yearText);
                if (stageLabel) parts.push(stageLabel);
                empresaInfo.innerText = parts.join(' · ');
                empresaInfo.style.color = '#e4e4e7';
            }
            const stageBar = document.getElementById('reset-stagebar');
            if (stageBar) {
                const sp = (typeof stagePct === 'number' && stagePct >= 0) ? stagePct : 0;
                stageBar.style.width = `${sp}%`;
                if (stageName === 'cleanup') {
                    stageBar.style.background = 'linear-gradient(90deg, #3b82f6, #60a5fa)';
                } else if (stageName === 'sync') {
                    stageBar.style.background = 'linear-gradient(90deg, #22c55e, #16a34a)';
                } else if (stageName === 'metrics') {
                    stageBar.style.background = 'linear-gradient(90deg, #a855f7, #7c3aed)';
                } else {
                    stageBar.style.background = 'linear-gradient(90deg, #3b82f6, #22c55e)';
                }
            }
            const stageCnt = document.getElementById('reset-stagebar-count');
            if (stageCnt) {
                if (stageName === 'cleanup' && job && job.cleanup && Array.isArray(job.cleanup.tables)) {
                    const act = job.cleanup.tables.filter(t => (t.action || '').toLowerCase() !== 'skip');
                    const ok = act.filter(t => String(t.status || '').toUpperCase() === 'OK').length;
                    stageCnt.innerText = `${ok}/${act.length}`;
                } else {
                    stageCnt.innerText = '';
                }
            }
            const tableEl = document.getElementById('reset-table');
            if (tableEl) {
                const ct = job && job.current_table ? job.current_table : '';
                if (ct) {
                    if (!activeTable) activeTable = ct;
                    if (activeTable !== ct) {
                        if (tableTimers[activeTable] && !tableTimers[activeTable].end) tableTimers[activeTable].end = now;
                        activeTable = ct;
                    }
                    if (!tableTimers[ct]) tableTimers[ct] = { start: now, end: null };
                    const t = tableTimers[ct];
                    const ms = (t && t.start) ? (now - t.start) : 0;
                    tableEl.innerText = `Tabla actual: ${ct} · ${fmt(ms)}`;
                } else {
                    tableEl.innerText = '';
                }
            }
            const etaEl = document.getElementById('reset-eta');
            if (etaEl) {
                const eta = etaMs !== null ? etaMs : (pps > 0 ? ((100 - pct) / pps) * 1000 : null);
                etaEl.innerText = eta ? `ETA ${fmt(eta)}` : '';
            }
            const rpsEl = document.getElementById('reset-rps');
            if (rpsEl) {
                const val = (job && typeof job.rps === 'number') ? job.rps : null;
                rpsEl.innerText = (val !== null) ? `${val} filas/s` : '';
            }
            const logBox = document.getElementById('reset-sync-log');
            if (logBox && job && Array.isArray(job.log_tail)) {
                const newItems = job.log_tail.filter(x => !lastLogTs || (x.ts && x.ts > lastLogTs));
                if (newItems.length > 0) {
                    lastLogTs = newItems[newItems.length - 1].ts || lastLogTs;
                    const html = newItems.map(x => {
                        const color = x.state === 'error' ? '#f87171' : (x.state === 'completed' ? '#34d399' : '#a1a1aa');
                        const t = x.ts ? new Date(x.ts).toLocaleTimeString() : '';
                        const tbl = x.table || '';
                        const op = x.operation || '';
                        const msg = x.message || '';
                        const rw = typeof x.rows === 'number' ? ` ${x.rows}` : '';
                        return `<div style="color:${color}">[${t}] ${op}${rw} ${tbl} ${msg}</div>`;
                    }).join('');
                    logBox.insertAdjacentHTML('beforeend', html);
                    logBox.scrollTop = logBox.scrollHeight;
                }
            }
            const pb = document.getElementById('reset-pause-btn');
            if (pb && !pb.dataset.bound) {
                pb.dataset.bound = '1';
                pb.addEventListener('click', async () => {
                    const paused = pb.innerText === 'Reanudar' ? false : true;
                    if (paused) {
                        const r = await post(`/api/etl/job/${activeId}/pause`);
                        if (r && r.status === 'ok') pb.innerText = 'Reanudar';
                    } else {
                        const r = await post(`/api/etl/job/${activeId}/resume`);
                        if (r && r.status === 'ok') pb.innerText = 'Pausar';
                    }
                });
            }
            const ej = document.getElementById('reset-export-json');
            if (ej && !ej.dataset.bound) {
                ej.dataset.bound = '1';
                ej.addEventListener('click', () => {
                    window.open(`/api/etl/logs/${jobId}?fmt=json`, '_blank');
                });
            }
            const ec = document.getElementById('reset-export-csv');
            if (ec && !ec.dataset.bound) {
                ec.dataset.bound = '1';
                ec.addEventListener('click', () => {
                    window.open(`/api/etl/logs/${jobId}?fmt=csv`, '_blank');
                });
            }
            if (tbody) {
                try {
                    const cl = job && job.cleanup && Array.isArray(job.cleanup.tables) ? job.cleanup.tables : [];
                    if (cl && cl.length > 0) {
                        cl.forEach(r => {
                            const name = r.table || '';
                            if (!name) return;
                            const st = String(r.status || '');
                            const prevSt = tableLastStatus[name] || '';
                            tableLastStatus[name] = st;
                            if (!tableTimers[name]) {
                                if (st === 'PENDING' || name === activeTable) tableTimers[name] = { start: now, end: null };
                            }
                            if (tableTimers[name] && !tableTimers[name].end) {
                                if ((prevSt === 'PENDING' && st !== 'PENDING') || (st === 'OK') || (st && st !== 'PENDING' && st !== '')) {
                                    if (!tableTimers[name].start) tableTimers[name].start = now;
                                    tableTimers[name].end = now;
                                }
                            }
                        });
                        const rowsHtml = cl.map(r => {
                            const name = r.table || '';
                            const rows = typeof r.after === 'number' ? r.after : '';
                            const t = name && tableTimers[name] ? tableTimers[name] : null;
                            const ms = t ? ((t.end ? t.end : now) - (t.start ? t.start : now)) : 0;
                            const elapsedTxt = t ? fmt(ms) : '';
                            const status = r.status || '';
                            let stColor = '#a1a1aa';
                            if (status === 'OK') stColor = '#34d399';
                            else if (status === 'PENDING') stColor = '#f59e0b';
                            else if (status && status !== 'SKIPPED') stColor = '#f87171';
                            return `
                                <tr>
                                    <td style="padding:4px 6px; color:#e4e4e7;">${name}</td>
                                    <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${rows}</td>
                                    <td style="padding:4px 6px; text-align:right; color:#a1a1aa;">${elapsedTxt}</td>
                                    <td style="padding:4px 6px; font-weight:600; color:${stColor};">${status}</td>
                                </tr>
                            `;
                        }).join('');
                        tbody.innerHTML = rowsHtml;
                    }
                } catch (_) {}
            }
            if (st === 'completed') {
                stopped = true;
                if (msgEl) msgEl.innerText = "Completado";
                if (window.showToast) window.showToast("Sincronización global completada", false);
                const etaEl = document.getElementById('reset-eta');
                if (etaEl) etaEl.innerText = `Tiempo total ${fmt((job && job.telemetry && job.telemetry.elapsed_ms) ? job.telemetry.elapsed_ms : 0)}`;
                try {
                    if (typeof window._onResetJobDone === 'function') {
                        window._onResetJobDone({ jobId, status: 'completed' });
                    }
                } catch (_) {}
                return;
            }
            if (st === 'error') {
                stopped = true;
                if (msgEl) msgEl.innerText = "Error en sincronización";
                if (window.showToast) window.showToast("Error en la sincronización global", true);
                try {
                    if (typeof window._onResetJobDone === 'function') {
                        window._onResetJobDone({ jobId, status: 'error' });
                    }
                } catch (_) {}
                return;
            }
        } catch (e) {
            const connEl = document.getElementById('reset-conn');
            if (connEl) {
                connEl.innerText = 'Offline';
                connEl.style.color = '#f87171';
            }
            if (lastServerOk) {
                lastServerOk = false;
                if (window.showToast) window.showToast("Conexión con el servidor perdida", true);
            }
        }
        setTimeout(tick, 2000);
    };
    tick();
}

// --- Template Manager Handlers ---

try {
    window.requestFactoryReset = requestFactoryReset;
    window.closeAuthModal = closeAuthModal;
    window.openPgTablesPreview = openPgTablesPreview;
    window.openUsersPreview = openUsersPreview;
    window.confirmWorkflowAction = confirmWorkflowAction;
    window.detectMSSQLDatabases = detectMSSQLDatabases;
} catch (e) {}

async function requestExportPack() {
    const nameInput = document.getElementById('tpl-export-name');
    const packName = nameInput.value.trim();

    if (!packName) {
        alert("Por favor, introduce un nombre para el Pack.");
        return;
    }

    try {
        const btn = document.querySelector('button[onclick="requestExportPack()"]');
        const originalText = btn.innerText;
        btn.disabled = true;
        btn.innerText = "⏳...";

        const res = await fetch('/api/template/export', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ pack_name: packName })
        });

        if (res.ok) {
            // Trigger Download
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${packName}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();

            if (window.showToast) window.showToast("✅ Pack exportado y descargado");
        } else {
            const err = await res.json();
            alert("❌ Error al exportar: " + (err.error || err.message || "Unknown error"));
        }

        btn.disabled = false;
        btn.innerText = originalText;

    } catch (e) {
        alert("❌ Error de conexión: " + e);
        const btn = document.querySelector('button[onclick="requestExportPack()"]');
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Exportar";
        }
    }
}

async function requestImportPack() {
    const fileInput = document.getElementById('tpl-import-file');
    const wipeCheck = document.getElementById('tpl-import-wipe');

    if (fileInput.files.length === 0) {
        alert("Selecciona un archivo JSON válido.");
        return;
    }

    const file = fileInput.files[0];
    const wipe = wipeCheck.checked;

    if (wipe) {
        const confirmWipe = prompt("⚠️ PRECAUCIÓN: Has seleccionado borrar la configuración actual.\nEsto eliminará mapeos y memoria local.\n\nEscribe 'CONFIRMAR' para proceder:");
        if (confirmWipe !== 'CONFIRMAR') return;
    }

    try {
        const btn = document.querySelector('button[onclick="requestImportPack()"]');
        const originalText = btn.innerText;
        btn.disabled = true;
        btn.innerText = "⏳ Importando...";

        const formData = new FormData();
        formData.append('file', file);
        formData.append('wipe', wipe); // Ninja might need this as query param ? No, passing as Form field, need to adjust backend if expecting query param

        // My backend implementation used query param for wipe?
        // Let's check: def import_template(request, file: UploadedFile = File(...), wipe: str = "false"):
        // This signature in Django Ninja usually expects query params unless Form(...) is used for non-files.
        // But since we are using Multipart upload, let's better pass wipe as Query Param to be safe/standard with previous Ninja usage

        const res = await fetch(`/api/template/import?wipe=${wipe}`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        });

        const data = await res.json();

        if (res.ok) {
            alert("✅ Pack importado exitosamente.\n" + (data.message || ""));
            window.location.reload();
        } else {
            alert("❌ Error: " + (data.error || data.message));
            btn.disabled = false;
            btn.innerText = originalText;
        }

    } catch (e) {
        alert("❌ Error de importación: " + e);
        const btn = document.querySelector('button[onclick="requestImportPack()"]');
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Importar";
        }
    }
}

// Helper for CSRF if not globally available
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// --- Auto-Load Toggle ---
function toggleAutoLoad(input) {
    const isEnabled = input.checked;
    localStorage.setItem('datia-auto-load', isEnabled);
}

// --- Training Mode Toggle ---
function toggleTrainingMode(input) {
    const isEnabled = input.checked;
    localStorage.setItem('datia-training-mode', isEnabled);

    // Update visual indicator immediately if it exists
    updateTrainingIndicator();
}

function updateTrainingIndicator() {
    const isModeActive = localStorage.getItem('datia-training-mode') === 'true';
    const badge = document.getElementById('training-mode-badge'); // Assuming this exists or we create it
    if (badge) {
        if (isModeActive) {
            badge.style.display = 'flex';
            badge.innerText = "MODO ENTRENAMIENTO: ON";
            badge.style.background = "rgba(168, 85, 247, 0.2)";
            badge.style.border = "1px solid #a855f7";
            badge.style.color = "#a855f7";
        } else {
            badge.style.display = 'none';
        }
    }
}

// --- SQL Toggle Logic ---
function toggleShowSql(input) {
    const isEnabled = input.checked;
    localStorage.setItem('datia-show-sql', isEnabled);
}

function toggleFastBulk(input) {
    const isEnabled = input.checked;
    localStorage.setItem('datia-fast-bulk', isEnabled);
}

// Initialize Settings State (Run on load)
document.addEventListener('DOMContentLoaded', () => {
    const sqlToggle = document.getElementById('settings-show-sql');
    if (sqlToggle) {
        sqlToggle.checked = localStorage.getItem('datia-show-sql') === 'true';
    }

    // Settings Toggle for Training Mode
    const trainToggle = document.getElementById('settings-training-mode');
    if (trainToggle) {
        trainToggle.checked = localStorage.getItem('datia-training-mode') === 'true';
        trainToggle.disabled = false;
        trainToggle.parentElement.title = "Activar para permitir entrenamiento manual";
    }

    // Settings Toggle for Auto Load
    const autoLoadToggle = document.getElementById('settings-auto-load');
    if (autoLoadToggle) {
        const stored = localStorage.getItem('datia-auto-load');
        // Default to TRUE if missing
        autoLoadToggle.checked = (stored === null) ? true : (stored === 'true');
    }

    const fastBulkToggle = document.getElementById('settings-fast-bulk');
    if (fastBulkToggle) {
        fastBulkToggle.checked = localStorage.getItem('datia-fast-bulk') === 'true';
    }

    updateTrainingIndicator();

    // Default Tab
    switchSettingsTab('user');

    // Update Company Name in Prompt
    const interval = setInterval(() => {
        const companySpan = document.getElementById('ia-prompt-company');
        const companySelect = document.getElementById('sel-empresa');

        if (companySelect && companySelect.options.length > 0 && companySelect.selectedIndex >= 0) {
            const text = companySelect.options[companySelect.selectedIndex].text;
            if (text && text !== "Sin Empresas" && text !== "Cargando..." && !text.startsWith("Error")) {
                if (companySpan) companySpan.innerText = text;
                clearInterval(interval);
            }
        }
    }, 200);

    setTimeout(() => clearInterval(interval), 5000);
});

// --- UI Customization ---
function setAccentColor(hex) {
    const root = document.documentElement;
    root.style.setProperty('--accent', hex);
    root.style.setProperty('--gradient-start', hex);
    root.style.setProperty('--accent-border', hex);
    try {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        root.style.setProperty('--accent-soft', `rgba(${r}, ${g}, ${b}, 0.35)`);
    } catch (e) { }

    // Calculate Glow (Hex -> RGBA)
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    root.style.setProperty('--accent-glow', `rgba(${r}, ${g}, ${b}, 0.5)`);

    // Save
    localStorage.setItem('datia-accent-color', hex);
    try {
        document.cookie = 'datia-accent-color=' + encodeURIComponent(hex) + '; path=/; max-age=31536000; SameSite=Lax';
    } catch (e) { }
    try {
        const csrf = (typeof getCookie === 'function' ? getCookie('csrftoken') : (window.CSRF_TOKEN || ''));
        fetch('/api/financial/preferences/ui', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrf
            },
            body: JSON.stringify({ accent_color: hex })
        }).catch(() => { });
    } catch (e) { }

    // Update Picker UI if triggered by Preset
    const picker = document.getElementById('custom-color-picker');
    if (picker && picker.value !== hex) {
        picker.value = hex;
    }
}

// Initialize Color (Run immediately to avoid flash if possible, but DOMContentLoaded is safe)
const savedAccent = localStorage.getItem('datia-accent-color');
if (savedAccent) {
    setAccentColor(savedAccent);
}

function escaparHtmlTexto(texto) {
    return String(texto)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function marcarDatosTexto(escapado) {
    let s = String(escapado);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/(\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:,\d{3})+\.\d{2}|\d+,\d{2}|\d+\.\d{2})\s*€/g, '<strong>$&</strong>');
    s = s.replace(/(\d{1,3}(?:\.\d{3})*,\d{1,2}|\d{1,3}(?:,\d{3})*\.\d{1,2}|\d+)\s*%/g, '<strong>$&</strong>');
    s = s.replace(/\b(20\d{2})\b/g, '<strong>$1</strong>');
    s = s.replace(/\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ0-9]{2,})+)\b/g, '<strong>$1</strong>');
    return s;
}

function textoSinHtml(texto) {
    return String(texto)
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/(p|div|h[1-6]|li|tr)>/gi, '\n')
        .replace(/<h[1-6][^>]*>/gi, '\n# ')
        .replace(/<li[^>]*>/gi, '\n- ')
        .replace(/<\/?(strong|b)>/gi, '**')
        .replace(/<[^>]+>/g, '')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"');
}

function sanearHtmlRespuesta(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = String(html);
    tmp.querySelectorAll('script, iframe, object, embed, link, meta').forEach(nodo => nodo.remove());
    tmp.querySelectorAll('*').forEach(el => {
        [...el.attributes].forEach(attr => {
            const nombre = attr.name.toLowerCase();
            const valor = attr.value || '';
            if (nombre.startsWith('on') || nombre === 'srcdoc' || /^javascript:/i.test(valor)) {
                el.removeAttribute(attr.name);
            }
        });
    });
    return tmp.innerHTML;
}

function partirFrasesTexto(texto) {
    const limpio = String(texto).replace(/\s+/g, ' ').trim();
    const partes = [];
    let actual = '';
    for (let i = 0; i < limpio.length; i++) {
        const caracter = limpio[i];
        actual += caracter;
        if (caracter !== '.' && caracter !== '!' && caracter !== '?') continue;
        const anterior = actual[actual.length - 2] || '';
        const siguiente = limpio[i + 1] || '';
        const trasEspacio = limpio[i + 2] || '';
        if (caracter === '.' && /\d/.test(anterior) && /\d/.test(siguiente)) continue;
        if (!siguiente) {
            partes.push(actual.trim());
            actual = '';
            continue;
        }
        if (siguiente === ' ' && /[A-ZÁÉÍÓÚÑ«0-9]/.test(trasEspacio)) {
            partes.push(actual.trim());
            actual = '';
            i += 1;
        }
    }
    if (actual.trim()) partes.push(actual.trim());
    return partes.filter(Boolean);
}

function fraseEsAviso(frase) {
    return /coste agregado supera|supera la venta|no tienen métrica|es un hueco|variación no es|se muestra como|Revisa esas líneas|Ese coste suma/i.test(frase);
}

function htmlDesdeMarcas(lineas) {
    let html = '';
    let avisos = [];
    let lista = [];
    const cerrarLista = () => {
        if (!lista.length) return;
        html += '<ul class="ai-texto-lista">' + lista.map(item => `<li>${marcarDatosTexto(escaparHtmlTexto(item))}</li>`).join('') + '</ul>';
        lista = [];
    };
    const cerrarAvisos = () => {
        if (!avisos.length) return;
        html += '<div class="ai-texto-avisos"><div class="ai-texto-avisos-titulo">Avisos</div>' +
            avisos.map(aviso => `<p>${marcarDatosTexto(escaparHtmlTexto(aviso))}</p>`).join('') + '</div>';
        avisos = [];
    };
    lineas.forEach(linea => {
        if (linea.startsWith('# ')) {
            cerrarLista();
            cerrarAvisos();
            html += `<h3 class="ai-texto-titulo">${marcarDatosTexto(escaparHtmlTexto(linea.slice(2)))}</h3>`;
        } else if (linea.startsWith('## ')) {
            cerrarLista();
            cerrarAvisos();
            html += `<h4 class="ai-texto-seccion">${marcarDatosTexto(escaparHtmlTexto(linea.slice(3)))}</h4>`;
        } else if (linea.startsWith('> ')) {
            cerrarLista();
            avisos.push(linea.slice(2));
        } else if (linea.startsWith('- ')) {
            cerrarAvisos();
            lista.push(linea.slice(2));
        } else {
            cerrarLista();
            cerrarAvisos();
            html += `<p class="ai-texto-parrafo">${marcarDatosTexto(escaparHtmlTexto(linea))}</p>`;
        }
    });
    cerrarLista();
    cerrarAvisos();
    return html;
}

function presentarRespuesta(raw) {
    let texto = String(raw || '').trim();
    if (!texto) return '';
    if (/<(div|table)\b/i.test(texto)) return sanearHtmlRespuesta(texto);
    if (/<[a-z][\s\S]*>/i.test(texto)) texto = textoSinHtml(texto);
    const lineas = texto.split(/\n+/).map(linea => linea.trim()).filter(Boolean);
    const usaMarca = lineas.some(linea => /^(#{1,2}\s|>\s|-\s)/.test(linea) || /\*\*/.test(linea));
    if (usaMarca) return htmlDesdeMarcas(lineas);

    const frases = partirFrasesTexto(texto);
    if (!frases.length) return '';
    let titulo = '';
    let cuerpo = frases.slice();
    const corte = frases[0].indexOf(': ');
    if (corte > 0 && corte <= 60 && !frases[0].slice(0, corte).includes('€')) {
        titulo = frases[0].slice(0, corte);
        const resto = frases[0].slice(corte + 2).trim();
        cuerpo = resto ? [resto.charAt(0).toUpperCase() + resto.slice(1)].concat(frases.slice(1)) : frases.slice(1);
    }
    const parrafos = [];
    const avisos = [];
    cuerpo.forEach(frase => {
        if (fraseEsAviso(frase) || (avisos.length && /^(Ese |Revisa |La variación|Si viene)/.test(frase))) avisos.push(frase);
        else parrafos.push(frase);
    });
    let html = '';
    if (titulo) html += `<h3 class="ai-texto-titulo">${marcarDatosTexto(escaparHtmlTexto(titulo))}</h3>`;
    parrafos.forEach(parrafo => {
        html += `<p class="ai-texto-parrafo">${marcarDatosTexto(escaparHtmlTexto(parrafo))}</p>`;
    });
    if (avisos.length) {
        html += '<div class="ai-texto-avisos"><div class="ai-texto-avisos-titulo">Avisos</div>' +
            avisos.map(aviso => `<p>${marcarDatosTexto(escaparHtmlTexto(aviso))}</p>`).join('') + '</div>';
    }
    return html;
}

function anadirOrigen(container, origen) {
    if (!origen || !container) return;
    const detalles = document.createElement('details');
    detalles.className = 'ai-origen';
    detalles.style.cssText = 'margin-top:16px; border:1px solid rgba(96,165,250,0.35); border-radius:10px; padding:12px 14px; background:rgba(96,165,250,0.06);';
    const resumen = document.createElement('summary');
    resumen.textContent = 'Origen del dato';
    resumen.style.cssText = 'cursor:pointer; color:#93c5fd; font-size:0.9rem; font-weight:600; width:max-content;';
    detalles.appendChild(resumen);
    const cuerpo = document.createElement('div');
    cuerpo.style.cssText = 'margin-top:10px; color:#d4d4d8; font-size:0.85rem; line-height:1.45;';

    const linea = (titulo, valor) => {
        if (!valor) return;
        const bloque = document.createElement('p');
        bloque.style.margin = '0 0 8px';
        const etiqueta = document.createElement('strong');
        etiqueta.textContent = titulo + ' ';
        etiqueta.style.color = '#a1a1aa';
        bloque.appendChild(etiqueta);
        bloque.appendChild(document.createTextNode(String(valor)));
        cuerpo.appendChild(bloque);
    };

    if (origen.falta) {
        const aviso = document.createElement('p');
        aviso.textContent = String(origen.falta);
        aviso.style.margin = '0 0 8px';
        cuerpo.appendChild(aviso);
    }
    linea('Tabla', origen.tabla);
    linea('Fórmula', origen.formula);
    const filtros = Array.isArray(origen.filtros) ? origen.filtros.filter(Boolean).join(' · ') : '';
    linea('Filtros', filtros);
    if (origen.consulta) {
        const titulo = document.createElement('div');
        titulo.textContent = 'Consulta';
        titulo.style.cssText = 'color:#a1a1aa; font-weight:600; margin-bottom:4px;';
        const pre = document.createElement('pre');
        pre.textContent = String(origen.consulta);
        pre.style.cssText = 'white-space:pre-wrap; background:#18181b; border:1px solid #3f3f46; border-radius:8px; padding:10px; color:#93c5fd; font-size:0.75rem; overflow-x:auto;';
        cuerpo.appendChild(titulo);
        cuerpo.appendChild(pre);
    }
    detalles.appendChild(cuerpo);
    container.appendChild(detalles);
}

function renderAiResponse(data, container, options = {}) {
    container.innerHTML = "";
    container.style.position = "relative";

    if (data.source === 'ai') {
        const badge = document.createElement("div");
        badge.style.position = "absolute";
        badge.style.top = "-10px";
        badge.style.left = "0";
        badge.style.fontSize = "0.7rem";
        badge.style.background = "#38bdf8";
        badge.style.color = "#000";
        badge.style.padding = "2px 6px";
        badge.style.borderRadius = "4px";
        badge.style.fontWeight = "bold";
        badge.innerText = "AI";
        container.appendChild(badge);
    }

    const effectiveQuery = options.query || data.query || data.question || '';


    const contentWrapper = document.createElement("div");
    contentWrapper.style.marginTop = "10px";
    container.appendChild(contentWrapper);

    // --- SQL DEBUG BLOCK ---
    const showSql = localStorage.getItem('datia-show-sql') === 'true';
    if (showSql && data.sql) {
        const sqlBlock = document.createElement("div");
        sqlBlock.style.background = "#18181b"; // Darker bg
        sqlBlock.style.border = "1px solid #3f3f46";
        sqlBlock.style.borderRadius = "6px";
        sqlBlock.style.padding = "10px";
        sqlBlock.style.marginBottom = "10px";
        sqlBlock.style.fontFamily = "monospace";
        sqlBlock.style.fontSize = "0.75rem";
        sqlBlock.style.overflowX = "auto";
        sqlBlock.style.color = "#a1a1aa";

        sqlBlock.innerHTML = `
            <div style="font-weight:bold; color:#71717a; margin-bottom:4px; font-size:0.7rem;">DEBUG: GENERATED SQL</div>
            <code style="color: #60a5fa;">${data.sql}</code>
        `;
        contentWrapper.appendChild(sqlBlock);
    }

    const shouldSkipText = options.skipText;

    if (data.answer && !shouldSkipText) {
        const titleDiv = document.createElement("div");
        titleDiv.className = "ai-report-texto";
        titleDiv.innerHTML = presentarRespuesta(data.answer);
        contentWrapper.appendChild(titleDiv);
    }

    // Content based on Type
    let customRendered = false;
    const vizContainer = document.createElement("div");
    vizContainer.id = "ai-viz-" + (container.id || Date.now());
    vizContainer.style.marginTop = "1rem";

    if (data.type === 'report') {
        contentWrapper.appendChild(vizContainer);
        renderAiReport(vizContainer, data, options.isDeepDive || false);
        customRendered = true;
    } else if (data.type === 'table') {
        contentWrapper.appendChild(vizContainer);
        if (Array.isArray(data.kpis) && data.kpis.length) {
            const kpiBox = document.createElement('div');
            contentWrapper.appendChild(kpiBox);
            renderAiReport(kpiBox, { kpis: data.kpis }, false);
        }
        // Pass metric from data (check intent_meta for Fast Path)
        const activeMetric = data.metric || (data.intent_meta ? data.intent_meta.metric : 'sales');
        renderAiTable(vizContainer, data.data, data.chart_config, options.isDeepDive || false, activeMetric);
        customRendered = true;

        // ... existing ... 
    } else if (data.type === 'resumen') {
        (data.partes || []).forEach(function (parte) {
            const bloque = document.createElement('div');
            bloque.style.marginTop = '28px';
            if (parte.text) {
                const resumen = document.createElement('div');
                resumen.innerHTML = parte.text;
                bloque.appendChild(resumen);
            }
            if (Array.isArray(parte.data) && parte.data.length) {
                const tabla = document.createElement('div');
                bloque.appendChild(tabla);
                renderAiTable(tabla, parte.data, parte.chart_config, false, parte.metric || 'sales');
            }
            contentWrapper.appendChild(bloque);
        });
        customRendered = true;
    } else if (data.type === 'deep_dive_v2') {
        contentWrapper.appendChild(vizContainer);
        renderDeepDiveV2(vizContainer, data);
        customRendered = true;
    } else if (data.type === 'no_data_option') {
        // [NEW] Render "No Data" message + Force Generation Button
        const glassCard = document.createElement('div');
        glassCard.style.cssText = `
            background: rgba(239, 68, 68, 0.05); 
            border: 1px solid rgba(239, 68, 68, 0.2); 
            border-radius: 12px; 
            padding: 20px; 
            margin-top: 20px; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            text-align: center;
        `;

        const msg = presentarRespuesta(data.answer || "No hay datos.");
        // Escape quotes for the onclick handler
        const questionText = effectiveQuery.replace(/'/g, "\\'");

        glassCard.innerHTML = `
            <div style="font-size: 1rem; color: #fca5a5; margin-bottom: 15px; font-weight: 500;">
                ${msg}
            </div>

            <button onclick="startTrainingFlow('${questionText}')" 
                class="btn-force-gen"
                style="
                    background: var(--accent);
                    color: #fff;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 8px;
                    font-size: 0.9rem;
                    font-weight: 500;
                    cursor: pointer;
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                    transition: transform 0.2s;
                    box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);
                "
                onmouseover="this.style.transform='translateY(-2px)'"
                onmouseout="this.style.transform='translateY(0)'"
            >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>
                Generar con IA
            </button>
            
            <div style="font-size: 0.75rem; color: #71717a; margin-top: 12px;">
                Esto ignorará la memoria y generará una nueva consulta SQL.
            </div>
        `;
        contentWrapper.appendChild(glassCard);
        customRendered = true;
    } else if (data.type === 'ambiguity_alert') {
        const glassCard = document.createElement('div');
        glassCard.style.cssText = `
            background: rgba(234, 179, 8, 0.06);
            border: 1px solid rgba(234, 179, 8, 0.25);
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
        `;
        const msg = presentarRespuesta(data.answer || "Consulta ambigua.");
        const items = Array.isArray(data.suggestions) ? data.suggestions : [];
        const inputId = 'amb-free-text-' + (container.id || Date.now());
        let shtml = '';
        if (items.length > 0) {
            shtml = `<div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:10px;">` + items.map(it => {
                const lbl = (it.label || 'Opción').replace(/"/g,'&quot;');
                const q = (it.query || '').replace(/'/g, "\\'");
                return `<button onclick="askAI('${q}')" style="background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);">${lbl}</button>`;
            }).join('') + `</div>`;
        }
        glassCard.innerHTML = `
            <div style="font-size: 1rem; color: #facc15; margin-bottom: 8px;">
                ${msg}
            </div>
            ${shtml}
            <div style="margin-top: 12px;">
                <input id="${inputId}" type="text" placeholder="Especificar..." style="width: 70%; padding: 8px; border-radius: 6px; border: 1px solid #3f3f46; background:#0b0b0f; color:#e4e4e7;">
                <button onclick="(function(){ const v=document.getElementById('${inputId}').value || ''; if(v){ askAI(v);} })()" style="margin-left:8px; background: #3b82f6; color: #fff; border: none; padding: 8px 14px; border-radius: 8px; font-size: 0.85rem; cursor: pointer;">Aclarar</button>
            </div>
        `;
        contentWrapper.appendChild(glassCard);
        customRendered = true;
    } else if (data.type === 'training_ask') {
        const glassCard = document.createElement('div');
        glassCard.style.cssText = `
            background: rgba(168, 85, 247, 0.05); 
            border: 1px solid rgba(168, 85, 247, 0.2); 
            border-radius: 12px; 
            padding: 30px; 
            margin-top: 20px; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            text-align: center;
        `;

        const questionText = effectiveQuery.replace(/'/g, "\\'");

        if (data.details === 'pedido_or_albaran') {
            glassCard.innerHTML = `
                <div style="font-size: 1rem; color: #a1a1aa; margin-bottom: 20px; font-family: 'Inter', sans-serif;">
                    ¿Quieres ver por Pedido o por Albarán?
                </div>
                <div style="display:flex; gap:12px;">
                    <button onclick="askAI('${questionText} pedido')" 
                        style="background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);">
                        Pedido
                    </button>
                    <button onclick="askAI('${questionText} albaranes')" 
                        style="background: var(--accent); color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-size: 0.9rem; cursor: pointer; box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);">
                        Albaranes
                    </button>
                </div>
            `;
        } else {
            glassCard.innerHTML = `
                <div style="font-size: 1rem; color: #a1a1aa; margin-bottom: 20px; font-family: 'Inter', sans-serif;">
                    No encuentro esta consulta en mi memoria verificada.
                </div>
    
                <button onclick="startTrainingFlow('${questionText}')" 
                    style="
                        background: var(--accent);
                        color: #fff;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-size: 0.95rem;
                        font-weight: 500;
                        cursor: pointer;
                        display: inline-flex;
                        align-items: center;
                        gap: 10px;
                        transition: transform 0.2s;
                        box-shadow: 0 4px 12px rgba(168, 85, 247, 0.3);
                    "
                    onmouseover="this.style.transform='translateY(-2px)'"
                    onmouseout="this.style.transform='translateY(0)'"
                >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>
                    Generar con IA
                </button>
                
                <div style="font-size: 0.8rem; color: #71717a; margin-top: 15px;">
                    Esto analizará tu pregunta y generará una respuesta nueva.
                </div>
            `;
        }
        contentWrapper.appendChild(glassCard);
        customRendered = true;
    }

    anadirOrigen(contentWrapper, data.origen);

    // Feedback logic (restored from previous)
    const feedbackDiv = document.createElement("div");
    // [FIX] Ensure feedback div has clear separation and spacing
    feedbackDiv.style.cssText = "display: flex; gap: 10px; margin-top: 2rem; align-items: center; font-size: 0.8rem; color: #71717a; border-top: 1px solid rgba(255,255,255,0.1); padding-top: 15px; width: 100%; justify-content: flex-start;";

    const containerId = container.id || ("ai-res-" + Date.now());
    container.id = containerId;
    try {
        window.__datia_ai_payloads = window.__datia_ai_payloads || {};
        window.__datia_ai_payloads[containerId] = { payload: data, query: effectiveQuery };
    } catch (_) { }
    const feedbackKey = data.key || 'general';
    let deepDiveBtn = '';
    const contentLang = data.lang || 'es';
    const safeQuery = effectiveQuery.replace(/'/g, "\\'").replace(/"/g, '&quot;');
    const proBtn = `
        <div class="vr mx-2 bg-secondary" style="height: 16px; margin: 0 15px;"></div>
        <button class="btn btn-sm btn-outline-light"
            onclick="openProReportFromChat('${containerId}')"
            title="Convertir esta respuesta en un informe profesional"
            style="cursor:pointer; z-index:100;">
            🧾 Informe Pro
        </button>
    `;

    const isDetailed = effectiveQuery && (effectiveQuery.toLowerCase().includes("detallado") || effectiveQuery.toLowerCase().includes("detailed"));

    if (!isDetailed && !data.profundizado) {
        deepDiveBtn = `
            <div class="vr mx-2 bg-secondary" style="height: 16px; margin: 0 15px;"></div>
            <button id="btn-deep-dive-${containerId}" class="btn btn-sm btn-outline-info" onclick="triggerDeepDive('${safeQuery}', '${containerId}', '${contentLang}')" style="cursor:pointer; z-index:100;">
                ✨ Analizar más
            </button>
            `;
    }

    feedbackDiv.className = "d-flex align-items-center gap-2 mt-3";

    if (data.source === 'ai_gen') {
        const sqlEncoded = data.sql ? encodeURIComponent(data.sql) : '';
        const analysisEncoded = '';
        const typeEncoded = data.type || 'table';

        // [FIX] Use Thumbs Up/Down for consistency as requested
        // [DEBUG] Added console.log and explicit z-index/cursor to debug click issues
        feedbackDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px; position: relative; z-index: 50; pointer-events: auto;">
                <span class="small text-muted" style="margin-right:8px;">¿Respuesta correcta?</span>
                <button class="btn btn-sm btn-outline-success" 
                    onclick="validateAndSave('${safeQuery}', decodeURIComponent('${sqlEncoded}'), '', '${typeEncoded}')"
                    title="Guardar en Memoria (Aprender)"
                    style="cursor: pointer; position: relative; z-index: 51; padding: 4px 12px;">
                    👍 Sí
                </button>
                <button class="btn btn-sm btn-outline-danger" 
                    onclick="this.closest('.card-body').remove()" 
                    title="Descartar"
                    style="cursor: pointer; position: relative; z-index: 51; padding: 4px 12px;">
                    👎 No
                </button>
            </div>
            ${proBtn}
            ${deepDiveBtn}
        `;
    } else {
        feedbackDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 10px; position: relative; z-index: 50; pointer-events: auto;">
                <span class="small text-muted" style="margin-right:8px;">¿Es útil?</span>
                <button class="btn btn-sm btn-outline-success" 
                    onclick="sendFeedback('${safeQuery}', '${feedbackKey}', 1, '${containerId}')"
                    style="cursor: pointer; position: relative; z-index: 51; padding: 4px 12px;">
                    👍 Sí
                </button>
                <button class="btn btn-sm btn-outline-danger" 
                    onclick="sendFeedback('${safeQuery}', '${feedbackKey}', -1, '${containerId}')"
                    style="cursor: pointer; position: relative; z-index: 51; padding: 4px 12px;">
                    👎 No
                </button>
            </div>
            ${proBtn}
            ${deepDiveBtn}
        `;
    }

    // [FIX] Create a wrapper to push content up and ensure feedback is visible at bottom
    const bottomSpacer = document.createElement("div");
    bottomSpacer.style.height = "20px";
    if (!data.profundizado) {
        contentWrapper.appendChild(bottomSpacer);
        contentWrapper.appendChild(feedbackDiv);
    }

    if (!customRendered) {
        if (!data || (!data.kpis && !data.chart_config)) return;
        renderAiReport(vizContainer, data, options.isDeepDive || false);
    }
}

window.openProReportFromChat = function (containerId) {
    try {
        const store = window.__datia_ai_payloads || {};
        const item = store[containerId] || {};
        const payload = item.payload || null;
        const query = item.query || '';
        if (!payload) {
            if (typeof showToast === 'function') showToast('No se pudo generar el informe (respuesta no disponible)');
            return;
        }
        if (typeof AIReportManager === 'undefined' || typeof AIReportManager.showProFromAnswer !== 'function') {
            if (typeof showToast === 'function') showToast('No se pudo generar el informe (motor no disponible)');
            return;
        }
        AIReportManager.showProFromAnswer(payload, query);
    } catch (e) {
        try { console.error(e); } catch (_) { }
        if (typeof showToast === 'function') showToast('No se pudo generar el informe');
    }
};

async function sendFeedback(query, key, vote, containerId) {
    const container = containerId ? document.getElementById(containerId) : document.getElementById('ai-chat-container');
    const feedbackDiv = container.querySelector('[style*="display: flex"][style*="gap: 10px"]');

    if (vote === 1) {
        try {
            const url = `${API}/ai/feedback`;
            const payload = {
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                query: query,
                key: key,
                vote: vote,
                answer: container ? (container.innerText || '').slice(0, 800) : ''
            };

            // Use JSON body
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });
            const json = await res.json();

            if (json.status === 'saved' || json.status === 'already_saved') {
                if (feedbackDiv) {
                    feedbackDiv.innerHTML = `
                        <span style="color: #34d399; font-weight: 600; font-size: 0.85rem;">
                            ✓ Guardado en historial
                        </span>
                    `;
                    feedbackDiv.style.animation = 'feedbackSuccess 0.5s ease-out';
                }

                const notification = document.createElement('div');
                notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #34d399; color: #000; padding: 12px 20px; border-radius: 8px; font-weight: 600; z-index: 10000; animation: slideIn 0.3s ease-out;';
                notification.innerText = json.status === 'saved' ? '✓ Consulta guardada en historial' : '✓ Ya estaba en tu historial';
                document.body.appendChild(notification);

                setTimeout(() => {
                    notification.style.animation = 'slideOut 0.3s ease-out';
                    setTimeout(() => notification.remove(), 300);
                }, 2000);

                loadHistory();
            } else {
                const msg = (json && json.message) ? json.message : 'No se pudo guardar en historial';
                if (feedbackDiv) {
                    feedbackDiv.innerHTML = `<span style="color: #ef4444; font-size: 0.85rem;">✗ ${msg}</span>`;
                }
                if (typeof showToast === 'function') showToast("❌ " + msg);
            }
        } catch (e) {
            console.error('Error saving query:', e);
            if (feedbackDiv) {
                feedbackDiv.innerHTML = `<span style="color: #ef4444; font-size: 0.85rem;">✗ Error al guardar: ${e.message}</span>`;
            }
        }
        return;
    }

    if (vote === -1) {
        try {
            await fetch(`${API}/ai/feedback`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    empresa: currEmpresa,
                    ejercicio: currEjercicio,
                    query: query,
                    key: key,
                    vote: -1,
                    answer: container ? (container.innerText || '').slice(0, 800) : ''
                })
            });
        } catch (e) {
            console.error('Error registrando el voto negativo:', e);
        }
        if (feedbackDiv) {
            feedbackDiv.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:8px; align-items:flex-start;">
                    <div style="color: #ef4444; font-weight: 600; font-size: 0.85rem;">
                         Gracias por el feedback 👎
                    </div>
                    <button class="btn btn-sm" 
                            style="background:rgba(234, 179, 8, 0.15); color:#ca8a04; border:1px solid #ca8a04; font-size:0.8rem; padding: 4px 10px; border-radius:6px; display:flex; align-items:center; gap:6px;"
                            onclick="startTrainingFlow('${query.replace(/'/g, "\\'")}')">
                       <span>🎓</span> Enseñar respuesta correcta
                    </button>
                    <small style="color:#71717a; font-size:0.75rem;">Esto abrirá el modo supervisor.</small>
                </div>
            `;
        }
        const deepDiveBtn = document.getElementById(`btn-deep-dive-${containerId}`);
        if (deepDiveBtn) deepDiveBtn.remove();
        return;
    }
}

async function loadHistory(excludeId = null) {
    try {
        const emp = encodeURIComponent(currEmpresa);
        const eje = encodeURIComponent(currEjercicio);
        const res = await fetch(`${API}/ai/history?empresa=${emp}&ejercicio=${eje}&_t=${Date.now()}`);
        const data = await res.json();

        const container = document.getElementById('ia-history-container');
        const refreshAllBtn = document.getElementById('refresh-all-btn');

        if (!container) return;

        let historyItems = data.history || [];

        if (excludeId) {
            historyItems = historyItems.filter(h => h.id != excludeId);
        }

        if (historyItems.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #71717a; padding: 2rem; font-style: italic;">No hay consultas guardadas aún. Dale 👍 a una respuesta para guardarla.</div>';
            if (refreshAllBtn) refreshAllBtn.style.display = 'none';
            return;
        }

        container.innerHTML = '';
        if (refreshAllBtn) refreshAllBtn.style.display = 'block';

        historyItems.forEach(item => {
            renderHistoryCard(item, container);
        });
    } catch (e) {
        console.error('Error loading history:', e);
    }
}

function renderHistoryCard(item, container) {
    const card = document.createElement('div');
    card.className = "history-card";

    let typeIcon = "📊";
    if (item.type === 'report') typeIcon = "📑";
    else if (item.type === 'card') typeIcon = "🏷️";

    card.innerHTML = `
        <div class="history-header">
            <div class="history-query" title="${item.query}">
                <span class="history-icon">${typeIcon}</span>
                ${item.query}
            </div>
            <div class="history-meta">
               <span class="history-ts">${new Date(item.ts).toLocaleDateString()}</span>
               <button class="btn-delete" title="Borrar" onclick="deleteHistoryItem(${item.id}, this)">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"></path>
                  </svg>
               </button>
            </div>
        </div>
        <div class="history-preview">${item.label || 'Sin descripción'}</div>
    `;

    card.onclick = (e) => {
        if (!e.target.closest('.btn-delete')) {
            askAI(item.query);
        }
    };
    container.appendChild(card);
}

async function deleteHistoryItem(id, btnElement) {
    if (!confirm("¿Borrar esta consulta del historial?")) return;

    const card = btnElement.closest('.history-card');
    if (card) {
        card.style.opacity = '0.5';
        card.style.pointerEvents = 'none';
    }

    try {
        const emp = encodeURIComponent(currEmpresa);
        const url = `${API}/ai/history/${id}?empresa=${emp}`;
        const res = await fetch(url, { method: 'DELETE' });
        const json = await res.json();

        if (json.status === 'deleted') {
            if (card) {
                card.style.transform = 'translateX(20px)';
                card.style.opacity = '0';
                setTimeout(() => card.remove(), 300);
            }
        }
    } catch (e) {
        alert("Error al borrar: " + e.message);
        if (card) card.style.opacity = '1';
    }
}

function openSqlEditor(btn) {
    const sql = btn.getAttribute('data-sql');
    navigator.clipboard.writeText(sql).then(() => {
        alert("SQL copiado al portapapeles.\n\n(El editor visual integrado estará disponible próximamente en las Opciones de Desarrollador).");
    });
}

async function validateAndSave(question, sql, analysis, type) {
    if (!confirm("¿Confirmas que esta respuesta es correcta y quieres que la aprenda para el futuro?")) return;

    const target = event.target;
    const container = target.closest('div[style*="border-top"]');

    target.disabled = true;
    target.innerHTML = "⏳ Guardando...";

    try {
        const payload = {
            empresa: currEmpresa,
            ejercicio: currEjercicio,
            question: question,
            sql: sql,
            analysis: analysis,
            type: type
        };

        const res = await fetch(`${API}/ai/learn`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
            },
            credentials: 'same-origin',
            body: JSON.stringify(payload)
        });

        const json = await res.json();

        if (json.status === 'learned') {
            if (container) {
                container.innerHTML = `
                        <div style="color: #34d399; font-weight: bold; text-align: center; padding: 10px;">
                            <span style="font-size: 1.5rem;">🎉</span><br>
                            ¡Conocimiento Guardado!<br>
                            <span style="font-size: 0.8rem; font-weight: normal; color: #a1a1aa;">La IA recordará esto la próxima vez.</span>
                        </div>
                     `;
                setTimeout(() => {
                    container.style.opacity = '0';
                    setTimeout(() => container.remove(), 500);
                }, 3000);
            }
        } else {
            if (typeof showToast === 'function') showToast("❌ Error al guardar: " + json.message);
            target.disabled = false;
            target.innerHTML = "💾 Guardar y Aprender";
        }

    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') showToast("❌ Error de red: " + e.message);
        target.disabled = false;
        target.innerHTML = "💾 Guardar y Aprender";
    }
}


function renderDeepDiveV2(container, data) {

    if (!data) return;

    // --- REPORT MODE (NF-026) ---
    // If data comes from ReportHandler, it has specific structure: kpis, evolution, rankings
    if (data.kpis && data.evolution) {

        // 1. Header
        const header = document.createElement('div');
        header.style.marginBottom = "20px";
        header.style.borderBottom = "1px solid rgba(255,255,255,0.1)";
        header.style.paddingBottom = "10px";
        header.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h3 style="margin:0; font-size:1.2rem; color:#fff;">Dossier Ejecutivo ${data.ejercicio}</h3>
                    <div style="font-size:0.8rem; color:#a1a1aa;">Generado automáticamente por Datia AI • ${new Date().toLocaleDateString()}</div>
                </div>
                <button onclick="window.print()" class="btn btn-sm btn-outline-secondary" style="border:1px solid #3f3f46; color:#a1a1aa;">
                    🖨️ Imprimir
                </button>
            </div>
        `;
        container.appendChild(header);

        // 2. KPI Grid
        const grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(200px, 1fr))';
        grid.style.gap = '15px';
        grid.style.marginBottom = '25px';

        data.kpis.forEach(card => {
            const el = document.createElement('div');
            el.className = "stat-card";
            el.style.background = "rgba(255,255,255,0.03)";
            el.style.border = "1px solid rgba(255,255,255,0.1)";
            el.style.padding = "20px";
            el.style.borderRadius = "12px";
            el.style.position = "relative";
            el.style.overflow = "hidden";

            let color = "#fff";
            let glow = "rgba(255,255,255,0.05)";
            if (card.color === 'blue') { color = "#60a5fa"; glow = "rgba(96, 165, 250, 0.1)"; }
            if (card.color === 'green') { color = "#4ade80"; glow = "rgba(74, 222, 128, 0.1)"; }

            const trendIcon = card.trend === 'up' ? '↗' : '↘';
            const trendColor = card.trend === 'up' ? '#4ade80' : '#f87171';

            el.innerHTML = `
                <div style="position:absolute; top:-20px; right:-20px; width:100px; height:100px; background:${glow}; filter:blur(40px); border-radius:50%;"></div>
                <div style="font-size:0.85rem; color:#a1a1aa; margin-bottom:5px;">${card.label}</div>
                <div style="font-size:1.8rem; font-weight:700; color:${color};">${card.value}</div>
                <div style="font-size:0.8rem; color:${trendColor}; margin-top:5px; display:flex; align-items:center; gap:5px;">
                    <span>${trendIcon}</span> ${card.sub}
                </div>
            `;
            grid.appendChild(el);
        });
        container.appendChild(grid);

        // 3. Main Chart (Evolution)
        const chartBox = document.createElement('div');
        chartBox.style.background = "rgba(24, 24, 27, 0.5)";
        chartBox.style.border = "1px solid #3f3f46";
        chartBox.style.borderRadius = "12px";
        chartBox.style.padding = "20px";
        chartBox.style.marginBottom = "25px";

        const chartTitle = document.createElement('div');
        chartTitle.innerText = "Evolución Anual (Comparativa)";
        chartTitle.style.fontWeight = "600";
        chartTitle.style.marginBottom = "15px";
        chartTitle.style.color = "#e4e4e7";
        chartBox.appendChild(chartTitle);

        const chartCanvas = document.createElement('div');
        chartCanvas.style.height = "300px";
        chartBox.appendChild(chartCanvas);
        container.appendChild(chartBox);

        if (window.renderAiChart) renderAiChart(chartCanvas, data.evolution);

        // 4. Rankings (Split View)
        if (data.rankings && data.rankings.clients) {
            const splitGrid = document.createElement('div');
            splitGrid.style.display = 'grid';
            splitGrid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(300px, 1fr))';
            splitGrid.style.gap = '20px';

            // Top Clients Table
            const clientBox = document.createElement('div');
            clientBox.innerHTML = `<h4 style="font-size:0.95rem; color:#a1a1aa; margin-bottom:15px;">Top Clientes</h4>`;

            let tableHtml = `<table style="width:100%; border-collapse:collapse; font-size:0.9rem; font-variant-numeric:tabular-nums;">`;
            tableHtml += `<thead><tr style="border-bottom:1px solid #3f3f46; color:#a1a1aa;">
                <th style="padding:8px 12px; text-align:left;">#</th>
                <th style="padding:8px 12px; text-align:left;">Cliente</th>
                <th style="padding:8px 12px; text-align:right; white-space:nowrap;">Importe</th>
            </tr></thead><tbody>`;
            data.rankings.clients.forEach((c, idx) => {
                const importe = typeof c.value === 'number'
                    ? c.value.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : escaparHtmlTabla(c.value);
                tableHtml += `
                    <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                        <td style="padding:8px 12px; color:#71717a; text-align:left;">${idx + 1}</td>
                        <td style="padding:8px 12px; color:#e4e4e7; text-align:left;">${escaparHtmlTabla(c.name)}</td>
                        <td style="padding:8px 12px; text-align:right; white-space:nowrap; font-weight:600; color:#fff;">${importe} €</td>
                    </tr>
                `;
            });
            tableHtml += `</tbody></table>`;
            clientBox.innerHTML += tableHtml;

            splitGrid.appendChild(clientBox);

            // Operations Status
            if (data.operations && data.operations.pending_orders) {
                const opsBox = document.createElement('div');
                opsBox.innerHTML = `<h4 style="font-size:0.95rem; color:#a1a1aa; margin-bottom:15px;">Operaciones en Curso</h4>`;

                const ops = data.operations.pending_orders;
                opsBox.innerHTML += `
                    <div style="background:rgba(255,255,255,0.03); border-radius:10px; padding:20px; display:flex; align-items:center; gap:20px;">
                        <div style="background:rgba(234, 179, 8, 0.1); width:50px; height:50px; border-radius:50%; display:flex; align-items:center; justify-content:center; color:#fbbf24; font-size:1.5rem;">📦</div>
                        <div>
                            <div style="font-size:1.5rem; font-weight:700; color:#fff;">${ops.count}</div>
                            <div style="font-size:0.85rem; color:#a1a1aa;">Pedidos Pendientes</div>
                        </div>
                        <div style="margin-left:auto; text-align:right;">
                            <div style="font-size:1.1rem; font-weight:600; color:#e4e4e7;">${ops.amount ? ops.amount.toLocaleString() : '0'} €</div>
                            <div style="font-size:0.75rem; color:#71717a;">Volumen en curso</div>
                        </div>
                    </div>
                `;
                splitGrid.appendChild(opsBox);
            }

            container.appendChild(splitGrid);
        }

        return;
    }

    // --- END REPORT MODE ---

    // 1. Financial Cards Grid
    if (data.financial_cards) {
        const grid = document.createElement('div');
        grid.style.display = 'grid';
        grid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(150px, 1fr))';
        grid.style.gap = '15px';
        grid.style.marginBottom = '20px';

        data.financial_cards.forEach(card => {
            const el = document.createElement('div');
            el.className = "stat-card";
            el.style.background = "rgba(255,255,255,0.03)";
            el.style.border = "1px solid rgba(255,255,255,0.1)";
            el.style.padding = "15px";
            el.style.borderRadius = "12px";
            el.style.position = "relative";
            el.style.overflow = "hidden";

            // Glow effect based on color name
            let glow = "rgba(255,255,255,0.05)";
            let textColor = "#fff";
            if (card.color === 'blue') { glow = "rgba(56, 189, 248, 0.15)"; textColor = "#38bdf8"; }
            if (card.color === 'green') { glow = "rgba(16, 185, 129, 0.15)"; textColor = "#34d399"; }
            if (card.color === 'yellow') { glow = "rgba(251, 191, 36, 0.15)"; textColor = "#fbbf24"; }
            if (card.color === 'purple') { glow = "rgba(168, 85, 247, 0.15)"; textColor = "#c084fc"; }

            // Trend Icon
            let trendIcon = "";
            let trendColor = "#71717a";
            if (card.trend === 'up') { trendIcon = "↗"; trendColor = "#34d399"; }
            if (card.trend === 'down') { trendIcon = "↘"; trendColor = "#ef4444"; }

            el.innerHTML = `
                <div style="position:absolute; top:0; right:0; width:60px; height:60px; background:${glow}; filter:blur(30px); border-radius:50%;"></div>
                <div style="font-size: 0.85rem; color: #a1a1aa; font-weight: 500;">${card.label}</div>
                <div style="font-size: 1.6rem; font-weight: 700; color: #fff; margin: 5px 0;">${card.value}</div>
                <div style="font-size: 0.75rem; color: ${trendColor}; display:flex; align-items:center; gap:4px;">
                    <span style="font-size:1rem;">${trendIcon}</span> ${card.sub}
                </div>
            `;
            grid.appendChild(el);
        });
        container.appendChild(grid);
    }

    // 2. Main Evolution Chart (Multi-Series)
    if (data.chart_main) {
        const chartBox = document.createElement('div');
        chartBox.style.background = "rgba(24, 24, 27, 0.5)";
        chartBox.style.border = "1px solid #3f3f46";
        chartBox.style.borderRadius = "10px";
        chartBox.style.padding = "15px";
        chartBox.style.marginBottom = "20px";
        chartBox.style.minHeight = "300px";

        const title = document.createElement('div');
        title.innerText = "Evolución Comparativa";
        title.style.fontSize = "0.9rem";
        title.style.fontWeight = "600";
        title.style.marginBottom = "10px";
        title.style.color = "#e4e4e7";
        chartBox.appendChild(title);

        const canvasDiv = document.createElement('div');
        chartBox.appendChild(canvasDiv);
        container.appendChild(chartBox);

        // Use global renderAiChart (wraps Chart.js)
        if (window.renderAiChart) {
            renderAiChart(canvasDiv, data.chart_main);
        } else {
            canvasDiv.innerText = "Error: renderAiChart not found.";
        }
    }

    // 3. Side Charts (Grid 2 cols)
    if (data.chart_clients || data.chart_products) {
        const sideGrid = document.createElement('div');
        sideGrid.style.display = 'grid';
        sideGrid.style.gridTemplateColumns = 'repeat(auto-fit, minmax(300px, 1fr))';
        sideGrid.style.gap = '20px';
        sideGrid.style.marginBottom = '20px';

        [data.chart_clients, data.chart_products].forEach((chk, idx) => {
            if (!chk) return;
            const box = document.createElement('div');
            box.style.border = "1px solid rgba(255,255,255,0.1)";
            box.style.borderRadius = "10px";
            box.style.padding = "10px";

            const head = document.createElement('div');
            head.innerText = idx === 0 ? "Top Clientes (Pareto)" : "Top Productos (Pareto)";
            head.style.fontSize = "0.85rem";
            head.style.color = "#a1a1aa";
            head.style.marginBottom = "10px";
            box.appendChild(head);

            const cDiv = document.createElement('div');
            cDiv.style.minHeight = "200px";
            box.appendChild(cDiv);
            sideGrid.appendChild(box);

            if (window.renderAiChart) renderAiChart(cDiv, chk);
        });
        container.appendChild(sideGrid);
    }
}

let conversacionActual = null;
let nodoConversacionActual = null;
let recalcularConversacionId = 0;
let recalculoEnCurso = false;
const arbolesAbiertos = {};
let cargaConversacionesToken = 0;

function escaparTexto(valor) {
    return String(valor || '').replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
}

function resetPantallaChat() {
    const stream = document.getElementById('ia-results-stream');
    const input = document.getElementById('ai-input');
    const stickyInput = document.getElementById('ai-input-sticky');
    const centeredPrompt = document.getElementById('ia-prompt-centered');
    const stickyPrompt = document.getElementById('ia-prompt-sticky');
    if (stream) stream.innerHTML = '';
    if (input) input.value = '';
    if (stickyInput) stickyInput.value = '';
    if (centeredPrompt && stickyPrompt) {
        stickyPrompt.style.opacity = '0';
        if (stream) stream.classList.remove('has-sticky-prompt');
        setTimeout(() => {
            stickyPrompt.style.display = 'none';
            centeredPrompt.style.removeProperty('display');
            centeredPrompt.style.opacity = '0';
            centeredPrompt.style.removeProperty('transform');
            requestAnimationFrame(() => {
                setTimeout(() => { centeredPrompt.style.opacity = '1'; }, 50);
            });
            if (input) input.focus();
        }, 200);
    }
}

function mostrarChatActivo() {
    const centeredPrompt = document.getElementById('ia-prompt-centered');
    const stickyPrompt = document.getElementById('ia-prompt-sticky');
    const stream = document.getElementById('ia-results-stream');
    if (centeredPrompt) centeredPrompt.style.display = 'none';
    if (stickyPrompt) {
        stickyPrompt.style.display = 'flex';
        stickyPrompt.style.opacity = '1';
    }
    if (stream) stream.classList.add('has-sticky-prompt');
}

function pintarMensajeGuardado(mensaje, indice, abierta) {
    const stream = document.getElementById('ia-results-stream');
    if (!stream || !mensaje) return;
    const card = document.createElement('div');
    card.className = 'ia-turno ia-card' + (abierta ? ' latest' : '');
    card.dataset.indice = String(indice);
    const burbuja = document.createElement('div');
    burbuja.className = 'ia-burbuja-usuario';
    burbuja.textContent = mensaje.pregunta || '';
    const body = document.createElement('div');
    body.className = 'ia-respuesta card-body';
    body.id = 'ai-res-saved-' + indice + '-' + (conversacionActual || 'x');
    card.appendChild(burbuja);
    card.appendChild(body);
    stream.appendChild(card);
    renderAiResponse(mensaje.respuesta || {}, body, { query: mensaje.pregunta || '' });
}

function pintarListaConversaciones(filas) {
    const lista = document.getElementById('ia-conversaciones-lista');
    if (!lista) return;
    if (!filas.length) {
        lista.innerHTML = '<div class="ia-conversaciones-vacio">Todavía no hay consultas guardadas.</div>';
        return;
    }
    lista.innerHTML = filas.map(function (fila) {
        const preguntas = Array.isArray(fila.preguntas) && fila.preguntas.length
            ? fila.preguntas
            : [{ indice: 0, texto: fila.titulo }];
        const esEsta = Number(fila.id) === Number(conversacionActual);
        const nodo = esEsta
            ? (nodoConversacionActual === null ? preguntas[preguntas.length - 1].indice : nodoConversacionActual)
            : null;
        const ramas = preguntas.map(function (pregunta, orden) {
            const esPrincipal = orden === 0;
            const activa = esEsta && Number(nodo) >= 0 && Number(pregunta.indice) === Number(nodo) ? ' activa' : '';
            const conHijos = esPrincipal && preguntas.length > 1;
            const tono = conHijos ? ' con-hijos' : ' sin-niveles';
            const nivel = esPrincipal ? 0 : 1;
            const rama = esPrincipal ? '' : '<span class="ia-conversacion-rama" aria-hidden="true"></span>';
            const plegar = conHijos
                ? `<button type="button" class="ia-conversacion-plegar" title="Abrir" onclick="plegarNivel(event, ${fila.id}, ${Number(pregunta.indice) || 0})">▸</button>`
                : '';
            const borrar = `<button type="button" class="ia-conversacion-borrar" title="Borrar" onclick="borrarNivel(event, ${fila.id}, ${Number(pregunta.indice) || 0})">×</button>`;
            return `
                <div class="ia-conversacion-item${activa}${tono}" data-id="${fila.id}" data-indice="${pregunta.indice}" style="--nivel:${nivel}">
                    ${rama}
                    ${plegar}
                    <button type="button" class="ia-conversacion-titulo" onclick="abrirConversacion(${fila.id}, ${Number(pregunta.indice) || 0})">
                        ${escaparTexto(pregunta.texto)}
                    </button>
                    ${borrar}
                </div>
            `;
        }).join('');
        return `<div class="ia-conversacion-arbol" data-id="${fila.id}">${ramas}</div>`;
    }).join('');
    prepararVistaPregunta(lista);
    abrirCaminoDeLaUltima(filas);
    aplicarPliegue();
}

function abrirCaminoDeLaUltima(filas) {
    if (nodoConversacionActual !== null || !conversacionActual) return;
    const fila = (filas || []).find(function (item) {
        return Number(item.id) === Number(conversacionActual);
    });
    if (!fila) return;
    const preguntas = Array.isArray(fila.preguntas) && fila.preguntas.length
        ? fila.preguntas
        : [{ indice: 0, texto: fila.titulo }];
    if (preguntas.length > 1) {
        arbolesAbiertos[claveArbol(fila.id, preguntas[0].indice)] = true;
    }
}

function claveArbol(id, indice) {
    return String(id) + ':' + String(indice);
}

function plegarNivel(evento, id, indice) {
    if (evento) {
        evento.preventDefault();
        evento.stopPropagation();
    }
    const clave = claveArbol(id, indice);
    arbolesAbiertos[clave] = !arbolesAbiertos[clave];
    aplicarPliegue();
}

function aplicarPliegue() {
    document.querySelectorAll('.ia-conversacion-arbol').forEach(function (arbol) {
        const id = arbol.dataset.id;
        const items = [].slice.call(arbol.querySelectorAll('.ia-conversacion-item'));
        items.forEach(function (item, orden) {
            const principal = items[0];
            const abierto = !!(principal && arbolesAbiertos[claveArbol(id, principal.dataset.indice)]);
            item.hidden = orden > 0 && !abierto;
            const boton = item.querySelector('.ia-conversacion-plegar');
            if (boton) {
                boton.textContent = abierto ? '▾' : '▸';
                boton.title = abierto ? 'Plegar' : 'Abrir';
            }
        });
    });
}

function lecturaGuardada(mensaje) {
    const respuesta = mensaje && mensaje.respuesta;
    if (!respuesta || typeof respuesta !== 'object') return null;
    if (respuesta.vinculo === 'rechazo' || respuesta.vinculo === 'aviso') return null;
    if (respuesta.lectura && typeof respuesta.lectura === 'object') return respuesta.lectura;
    if (respuesta.lectura_aceptada && typeof respuesta.lectura_aceptada === 'object') return respuesta.lectura_aceptada;
    return null;
}

function lecturaAnterior(mensajes, indice) {
    for (let posicion = indice - 1; posicion >= 0; posicion -= 1) {
        const lectura = lecturaGuardada(mensajes[posicion]);
        if (lectura) return lectura;
    }
    return null;
}

function capaPreguntaCompleta() {
    let capa = document.getElementById('ia-pregunta-completa');
    if (capa) return capa;
    capa = document.createElement('div');
    capa.id = 'ia-pregunta-completa';
    capa.className = 'ia-pregunta-completa';
    capa.hidden = true;
    document.body.appendChild(capa);
    return capa;
}

function mostrarPreguntaCompleta(boton) {
    const texto = (boton.textContent || '').trim();
    const capa = capaPreguntaCompleta();
    if (!texto) return;
    capa.textContent = texto;
    capa.hidden = false;
    const rect = boton.getBoundingClientRect();
    const margen = 12;
    let izquierda = rect.right + margen;
    let arriba = rect.top;
    capa.style.left = izquierda + 'px';
    capa.style.top = arriba + 'px';
    const caja = capa.getBoundingClientRect();
    if (izquierda + caja.width > window.innerWidth - 8) {
        izquierda = Math.max(8, rect.left - caja.width - margen);
        capa.style.left = izquierda + 'px';
    }
    if (arriba + caja.height > window.innerHeight - 8) {
        capa.style.top = Math.max(8, window.innerHeight - caja.height - 8) + 'px';
    }
}

function ocultarPreguntaCompleta() {
    const capa = document.getElementById('ia-pregunta-completa');
    if (capa) capa.hidden = true;
}

function prepararVistaPregunta(lista) {
    if (lista.dataset.vistaPregunta) return;
    lista.dataset.vistaPregunta = '1';
    lista.addEventListener('mouseover', function (evento) {
        const boton = evento.target.closest('.ia-conversacion-titulo');
        if (!boton || !lista.contains(boton)) return;
        mostrarPreguntaCompleta(boton);
    });
    lista.addEventListener('mouseout', function (evento) {
        const boton = evento.target.closest('.ia-conversacion-titulo');
        if (!boton) return;
        if (evento.relatedTarget && boton.contains(evento.relatedTarget)) return;
        ocultarPreguntaCompleta();
    });
    lista.addEventListener('scroll', ocultarPreguntaCompleta);
    lista.addEventListener('focusin', function (evento) {
        const boton = evento.target.closest('.ia-conversacion-titulo');
        if (boton) mostrarPreguntaCompleta(boton);
    });
    lista.addEventListener('focusout', function (evento) {
        const boton = evento.target.closest('.ia-conversacion-titulo');
        if (!boton) return;
        if (evento.relatedTarget && boton.contains(evento.relatedTarget)) return;
        ocultarPreguntaCompleta();
    });
}

async function cargarConversaciones() {
    const lista = document.getElementById('ia-conversaciones-lista');
    const empresa = parseInt(currEmpresa, 10);
    if (!lista || !empresa) return;
    const token = ++cargaConversacionesToken;
    try {
        const res = await fetch(`${API}/ai/conversaciones?empresa=${empresa}`, { credentials: 'same-origin' });
        const data = await res.json();
        if (token !== cargaConversacionesToken) return;
        pintarListaConversaciones(data.conversaciones || []);
    } catch (e) {
        if (token !== cargaConversacionesToken) return;
        lista.innerHTML = '<div class="ia-conversaciones-vacio">No se pudo cargar la lista.</div>';
    }
}

function copiarRespuestaGuardable(data) {
    try {
        return JSON.parse(JSON.stringify(data));
    } catch (e) {
        return {
            answer: data && data.answer ? String(data.answer) : '',
            type: data && data.type ? data.type : 'text',
            query: data && data.query ? data.query : ''
        };
    }
}

async function guardarConversacionActual(pregunta, respuesta) {
    if (!pregunta || !respuesta || respuesta.error) return;
    const reemplazarId = Number(recalcularConversacionId) || 0;
    recalcularConversacionId = 0;
    try {
        const res = await fetch(`${API}/ai/conversaciones`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
            },
            body: JSON.stringify({
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                pregunta: pregunta,
                respuesta: respuesta,
                conversacion_id: Number(conversacionActual) || reemplazarId || 0,
                reemplazar: reemplazarId > 0,
                lectura_aceptada: (respuesta && respuesta.lectura_aceptada) || null
            })
        });
        const json = await res.json();
        if (json && json.id) {
            conversacionActual = json.id;
            const stream = document.getElementById('ia-results-stream');
            const card = stream && stream.querySelector('.ia-turno.latest');
            if (card && json.indice !== undefined && json.indice !== null) {
                card.dataset.indice = String(json.indice);
            }
            cargarConversaciones();
        }
    } catch (e) {
        console.error('No se pudo guardar la consulta', e);
    }
}

function nuevaConsulta() {
    conversacionActual = null;
    nodoConversacionActual = null;
    resetPantallaChat();
    cargarConversaciones();
}

function tarjetaRecalculo(pregunta, indice) {
    const stream = document.getElementById('ia-results-stream');
    const card = document.createElement('div');
    card.className = 'ia-turno ia-card';
    card.dataset.indice = String(indice);
    const burbuja = document.createElement('div');
    burbuja.className = 'ia-burbuja-usuario';
    burbuja.textContent = pregunta || '';
    const body = document.createElement('div');
    body.className = 'ia-respuesta card-body';
    body.id = 'ai-res-recalc-' + indice + '-' + (conversacionActual || 'x');
    body.textContent = 'Recalculando…';
    card.appendChild(burbuja);
    card.appendChild(body);
    if (stream) stream.appendChild(card);
    return body;
}

async function recalcularPregunta(id, indice, lectura) {
    const controller = new AbortController();
    const timeoutId = setTimeout(function () { controller.abort(); }, 90000);
    try {
        const res = await fetch(`${API}/ai/conversaciones/${id}/recalcular`, {
            method: 'POST',
            credentials: 'same-origin',
            signal: controller.signal,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
            },
            body: JSON.stringify({
                empresa: currEmpresa,
                ejercicio: currEjercicio,
                indice: indice,
                lectura: lectura || null
            })
        });
        return await res.json();
    } finally {
        clearTimeout(timeoutId);
    }
}

async function abrirConversacion(id, indice) {
    if (recalculoEnCurso) return;
    recalculoEnCurso = true;
    try {
        const empresa = parseInt(currEmpresa, 10);
        const res = await fetch(`${API}/ai/conversaciones/${id}?empresa=${empresa}`, { credentials: 'same-origin' });
        const data = await res.json();
        const mensajes = data && Array.isArray(data.mensajes) ? data.mensajes : [];
        if (!data || data.status === 'error' || !mensajes.length) {
            if (window.showToast) window.showToast('No se pudo abrir la consulta');
            return;
        }
        const pedido = Number(indice);
        const elegido = Number.isInteger(pedido) && mensajes[pedido] ? pedido : 0;
        const todoElHilo = elegido === 0;
        conversacionActual = data.id;
        nodoConversacionActual = elegido;
        const stream = document.getElementById('ia-results-stream');
        if (stream) stream.innerHTML = '';
        mostrarChatActivo();
        const posiciones = todoElHilo
            ? mensajes.map(function (_mensaje, posicion) { return posicion; })
            : [elegido];
        let lectura = todoElHilo ? null : lecturaAnterior(mensajes, elegido);
        for (let paso = 0; paso < posiciones.length; paso += 1) {
            const posicion = posiciones[paso];
            const pregunta = (mensajes[posicion] && mensajes[posicion].pregunta) || '';
            const cuerpo = tarjetaRecalculo(pregunta, posicion);
            if (cuerpo) cuerpo.scrollIntoView({ block: 'start' });
            const json = await recalcularPregunta(data.id, posicion, lectura);
            if (!json || json.status === 'error') {
                if (cuerpo) cuerpo.textContent = (json && json.message) || 'No se pudo recalcular la consulta';
                break;
            }
            lectura = json.lectura_siguiente || lectura;
            if (mensajes[posicion]) {
                mensajes[posicion].respuesta = json.respuesta || {};
            }
            if (cuerpo) {
                cuerpo.textContent = '';
                renderAiResponse(json.respuesta || {}, cuerpo, { query: json.pregunta || pregunta });
            }
        }
        cargarConversaciones();
    } catch (e) {
        if (window.showToast) window.showToast('No se pudo abrir la consulta');
    } finally {
        recalculoEnCurso = false;
    }
}

function quitarTarjeta(indice) {
    const stream = document.getElementById('ia-results-stream');
    if (!stream) return false;
    const tarjeta = stream.querySelector('.ia-turno[data-indice="' + indice + '"]');
    if (tarjeta) tarjeta.remove();
    stream.querySelectorAll('.ia-turno').forEach(function (card) {
        const actual = Number(card.dataset.indice);
        if (!Number.isNaN(actual) && actual > indice) card.dataset.indice = String(actual - 1);
    });
    return !!stream.querySelector('.ia-turno');
}

async function borrarNivel(evento, id, indice) {
    if (evento) {
        evento.preventDefault();
        evento.stopPropagation();
    }
    if (!confirm('¿Borrar esta pregunta?')) return;
    try {
        const empresa = parseInt(currEmpresa, 10);
        const res = await fetch(`${API}/ai/conversaciones/${id}?empresa=${empresa}&indice=${indice}`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: {
                'X-CSRFToken': (typeof CSRF_TOKEN !== 'undefined' ? CSRF_TOKEN : '')
            }
        });
        const json = await res.json();
        if (!json || json.status === 'error') {
            alert((json && json.message) || 'No se pudo borrar la pregunta');
            return;
        }
        if (json.status === 'deleted') {
            if (Number(conversacionActual) === Number(id)) nuevaConsulta();
            else cargarConversaciones();
            return;
        }
        if (Number(conversacionActual) === Number(id)) {
            const quedan = quitarTarjeta(indice);
            if (!quedan) nodoConversacionActual = -1;
            else if (nodoConversacionActual > indice) nodoConversacionActual -= 1;
        }
        cargarConversaciones();
    } catch (e) {
        alert('No se pudo borrar la pregunta');
    }
}

window.nuevaConsulta = nuevaConsulta;
window.abrirConversacion = abrirConversacion;
window.borrarNivel = borrarNivel;
window.plegarNivel = plegarNivel;

