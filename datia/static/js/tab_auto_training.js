/* Examen de preguntas: una pregunta cada vez, con el paso visible. */

const EXAMEN_COLORES = {
    espera: { borde: '#3f3f46', fondo: 'rgba(0,0,0,0.2)', texto: '#a1a1aa', etiqueta: 'En espera' },
    ahora: { borde: '#a855f7', fondo: 'rgba(147, 51, 234, 0.18)', texto: '#d8b4fe', etiqueta: 'Preguntando al chat' },
    cifra_tabla: { borde: '#22c55e', fondo: 'rgba(34, 197, 94, 0.12)', texto: '#86efac', etiqueta: 'Cifra de la tabla' },
    otra_cifra: { borde: '#f59e0b', fondo: 'rgba(245, 158, 11, 0.12)', texto: '#fcd34d', etiqueta: 'Otra cifra' },
    sin_respuesta: { borde: '#71717a', fondo: 'rgba(113, 113, 122, 0.15)', texto: '#d4d4d8', etiqueta: 'Sin respuesta' },
    error: { borde: '#ef4444', fondo: 'rgba(239, 68, 68, 0.12)', texto: '#fca5a5', etiqueta: 'No se pudo preguntar' },
};

let examenEnCurso = false;
let examenListaCargada = '';
let examenPeticion = 0;

function cargarListaExamen() {
    if (examenEnCurso) return;
    const empresa = (typeof currEmpresa !== 'undefined' && currEmpresa) ? currEmpresa : '';
    const ejercicio = (typeof currEjercicio !== 'undefined' && currEjercicio) ? currEjercicio : '';
    const estado = document.getElementById('examen-estado');
    if (!empresa || !ejercicio) {
        if (estado) estado.textContent = 'Elige la empresa y el ejercicio para ver las preguntas.';
        return;
    }
    const clave = `${empresa}|${ejercicio}`;
    if (examenListaCargada === clave) return;
    const marca = ++examenPeticion;
    if (estado) estado.textContent = 'Preparando las preguntas del examen.';
    const base = `/api/auto-training/examen?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(ejercicio)}`;
    fetch(`${base}&fase=lista`)
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
            if (examenEnCurso || marca !== examenPeticion) return;
            if (!ok || data.status !== 'ok' || !Array.isArray(data.preguntas) || !data.preguntas.length) {
                if (estado) estado.textContent = (data && (data.message || data.error)) || 'No he podido preparar las preguntas.';
                return;
            }
            examenListaCargada = clave;
            pintarListaExamen(data.preguntas);
            const aviso = data.aviso ? `${data.aviso} ` : '';
            if (estado) {
                estado.textContent = `${aviso}${data.preguntas.length} preguntas preparadas. Pulsa Hacer el examen para lanzarlas.`;
            }
        })
        .catch(() => {
            if (examenEnCurso || marca !== examenPeticion) return;
            if (estado) estado.textContent = 'No he podido conectar con el examen.';
        });
}

function startExamen() {
    if (examenEnCurso) return;
    examenPeticion += 1;
    const empresa = (typeof currEmpresa !== 'undefined' && currEmpresa) ? currEmpresa : '';
    const ejercicio = (typeof currEjercicio !== 'undefined' && currEjercicio) ? currEjercicio : '';
    const estado = document.getElementById('examen-estado');
    if (!empresa || !ejercicio) {
        if (estado) estado.textContent = 'Elige la empresa y el ejercicio antes del examen.';
        return;
    }
    examenEnCurso = true;
    const boton = document.getElementById('btn-start-examen');
    if (boton) {
        boton.disabled = true;
        boton.textContent = 'Examen en curso';
    }
    if (estado) estado.textContent = 'Leyendo las preguntas del examen.';
    pintarResumenExamen({ cifra_tabla: 0, otra_cifra: 0, sin_respuesta: 0 });
    const lista = document.getElementById('examen-resultado');
    if (lista) lista.innerHTML = '';

    const base = `/api/auto-training/examen?empresa=${encodeURIComponent(empresa)}&ejercicio=${encodeURIComponent(ejercicio)}`;
    fetch(`${base}&fase=lista`)
        .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
        .then(async ({ ok, data }) => {
            if (!ok || data.status !== 'ok' || !Array.isArray(data.preguntas) || !data.preguntas.length) {
                if (estado) estado.textContent = (data && (data.message || data.error)) || 'No he podido preparar las preguntas.';
                return;
            }
            pintarListaExamen(data.preguntas);
            const cuentas = { cifra_tabla: 0, otra_cifra: 0, sin_respuesta: 0 };
            for (let i = 0; i < data.preguntas.length; i += 1) {
                marcarPreguntaExamen(i, 'ahora');
                mostrarPasoExamen(i + 1, data.preguntas.length, data.preguntas[i].pregunta);
                if (estado) estado.textContent = `El chat está contestando la pregunta ${i + 1} de ${data.preguntas.length}.`;
                let fila;
                try {
                    const respuesta = await fetch(`${base}&fase=una&indice=${i}`);
                    const cuerpo = await respuesta.json();
                    if (!respuesta.ok || cuerpo.status !== 'ok') {
                        throw new Error((cuerpo && (cuerpo.message || cuerpo.error)) || 'Sin respuesta del examen');
                    }
                    fila = cuerpo;
                } catch (error) {
                    fila = {
                        indice: i,
                        veredicto: 'error',
                        etiqueta: 'No se pudo preguntar',
                        esperado: data.preguntas[i].esperado,
                        obtenido: error.message || 'La pregunta no ha llegado a responderse.',
                    };
                }
                if (cuentas[fila.veredicto] !== undefined) cuentas[fila.veredicto] += 1;
                pintarResumenExamen(cuentas);
                marcarPreguntaExamen(i, fila.veredicto, fila);
            }
            ocultarPasoExamen();
            if (estado) estado.textContent = 'Examen terminado.';
        })
        .catch(() => {
            if (estado) estado.textContent = 'No he podido conectar con el examen.';
        })
        .finally(() => {
            examenEnCurso = false;
            if (boton) {
                boton.disabled = false;
                boton.textContent = 'Repetir el examen';
            }
        });
}

function mostrarPasoExamen(actual, total, frase) {
    const caja = document.getElementById('examen-ahora');
    const paso = document.getElementById('examen-paso');
    const texto = document.getElementById('examen-frase');
    const barra = document.getElementById('examen-barra');
    if (caja) caja.style.display = 'block';
    if (paso) paso.textContent = `Pregunta ${actual} de ${total}`;
    if (texto) texto.textContent = frase;
    if (barra) barra.style.width = `${Math.round(((actual - 1) / total) * 100)}%`;
}

function ocultarPasoExamen() {
    const caja = document.getElementById('examen-ahora');
    const barra = document.getElementById('examen-barra');
    if (barra) barra.style.width = '100%';
    if (caja) caja.style.display = 'none';
}

function pintarListaExamen(preguntas) {
    const lista = document.getElementById('examen-resultado');
    if (!lista) return;
    lista.innerHTML = preguntas.map((fila, i) => (
        `<article id="examen-pregunta-${i}" style="padding: 1rem 1.2rem; border-radius: 12px; border: 1px solid #3f3f46; background: rgba(0,0,0,0.2);">
            <div style="display: flex; justify-content: space-between; gap: 1rem; align-items: baseline;">
                <strong style="color: #fff;">${i + 1}. ${escaparExamen(fila.pregunta)}</strong>
                <span class="examen-etiqueta" style="color: #a1a1aa; font-size: 0.85rem; white-space: nowrap;">En espera</span>
            </div>
            <p class="examen-esperado" style="color: #d4d4d8; margin: 0.6rem 0 0.3rem;">Esperado: ${escaparExamen(fila.esperado)}</p>
            <p class="examen-obtenido" style="color: #a1a1aa; margin: 0;"></p>
        </article>`
    )).join('');
}

function marcarPreguntaExamen(indice, veredicto, fila) {
    const card = document.getElementById(`examen-pregunta-${indice}`);
    if (!card) return;
    const color = EXAMEN_COLORES[veredicto] || EXAMEN_COLORES.espera;
    card.style.borderColor = color.borde;
    card.style.background = color.fondo;
    const etiqueta = card.querySelector('.examen-etiqueta');
    if (etiqueta) {
        etiqueta.textContent = (fila && fila.etiqueta) || color.etiqueta;
        etiqueta.style.color = color.texto;
    }
    const obtenido = card.querySelector('.examen-obtenido');
    if (obtenido && fila) {
        obtenido.textContent = fila.obtenido ? `Respuesta: ${fila.obtenido}` : '';
    }
    card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function pintarResumenExamen(cuentas) {
    const resumen = document.getElementById('examen-resumen');
    if (!resumen) return;
    resumen.style.display = 'grid';
    resumen.innerHTML = [
        ['Cifra de la tabla', cuentas.cifra_tabla || 0, EXAMEN_COLORES.cifra_tabla],
        ['Otra cifra', cuentas.otra_cifra || 0, EXAMEN_COLORES.otra_cifra],
        ['Sin respuesta', cuentas.sin_respuesta || 0, EXAMEN_COLORES.sin_respuesta],
    ].map(([titulo, valor, color]) => (
        `<div style="padding: 1rem 1.2rem; border-radius: 12px; border: 1px solid ${color.borde}; background: ${color.fondo};">
            <div style="color: ${color.texto}; font-size: 0.8rem;">${titulo}</div>
            <div style="color: #fff; font-size: 1.8rem; font-weight: 700;">${valor}</div>
        </div>`
    )).join('');
}

function escaparExamen(valor) {
    return String(valor || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

window.startExamen = startExamen;
window.cargarListaExamen = cargarListaExamen;
