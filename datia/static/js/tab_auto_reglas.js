let reglaEsNueva = false;
let reglaAbierta = '';

function marcarReglaAbierta() {
    document.querySelectorAll('#reglas-lista button').forEach(boton => {
        const activa = boton.dataset.nombre === reglaAbierta;
        boton.style.background = activa ? 'rgba(147, 51, 234, 0.35)' : 'rgba(0,0,0,0.25)';
        boton.style.borderColor = activa ? '#a855f7' : '#3f3f46';
    });
}

async function cargarReglas() {
    const lista = document.getElementById('reglas-lista');
    if (!lista) return;
    const res = await fetch('/api/auto-training/reglas', { credentials: 'same-origin' });
    const data = await res.json();
    lista.innerHTML = '';
    (data.ficheros || []).forEach(fichero => {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.dataset.nombre = fichero.nombre;
        boton.textContent = fichero.nombre;
        boton.style.cssText = 'text-align:left; color:#fff; background:rgba(0,0,0,0.25); border:1px solid #3f3f46; border-radius:8px; padding:0.65rem 0.8rem; cursor:pointer;';
        boton.onclick = () => abrirRegla(fichero.nombre);
        lista.appendChild(boton);
    });
    marcarReglaAbierta();
    if (!reglaAbierta && data.ficheros && data.ficheros.length) abrirRegla(data.ficheros[0].nombre);
}

async function abrirRegla(nombre) {
    const res = await fetch('/api/auto-training/reglas/' + encodeURIComponent(nombre), { credentials: 'same-origin' });
    const data = await res.json();
    const estado = document.getElementById('reglas-estado');
    if (!res.ok) {
        if (estado) estado.textContent = data.message || 'No se pudo abrir';
        return;
    }
    reglaEsNueva = false;
    reglaAbierta = data.nombre;
    const campo = document.getElementById('reglas-nombre');
    campo.value = data.nombre.replace(/\.md$/i, '');
    campo.readOnly = true;
    document.getElementById('reglas-texto').value = data.texto || '';
    if (estado) estado.textContent = '';
    marcarReglaAbierta();
}

function nuevaRegla() {
    reglaEsNueva = true;
    reglaAbierta = '';
    const campo = document.getElementById('reglas-nombre');
    campo.readOnly = false;
    campo.value = '';
    document.getElementById('reglas-texto').value = [
        '# Reglas',
        '',
        ':::regla',
        'id: nueva-regla',
        'motor: mapeo',
        'cuando: ',
        'nota: ',
        ':::',
        '',
    ].join('\n');
    const estado = document.getElementById('reglas-estado');
    if (estado) estado.textContent = 'Fichero nuevo. El nombre no lleva espacios.';
    marcarReglaAbierta();
    campo.focus();
}

async function guardarRegla() {
    const estado = document.getElementById('reglas-estado');
    const nombre = document.getElementById('reglas-nombre').value.trim();
    const texto = document.getElementById('reglas-texto').value;
    const fichero = nombre.toLowerCase().endsWith('.md') ? nombre : nombre + '.md';
    const url = reglaEsNueva
        ? '/api/auto-training/reglas'
        : '/api/auto-training/reglas/' + encodeURIComponent(fichero);
    const res = await fetch(url, {
        method: reglaEsNueva ? 'POST' : 'PUT',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre: nombre, texto: texto }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        if (estado) estado.textContent = data.message || 'No se pudo guardar';
        return;
    }
    reglaEsNueva = false;
    reglaAbierta = data.nombre;
    document.getElementById('reglas-nombre').value = data.nombre.replace(/\.md$/i, '');
    document.getElementById('reglas-nombre').readOnly = true;
    if (estado) estado.textContent = 'Guardado';
    await cargarReglas();
}

window.cargarReglas = cargarReglas;
window.abrirRegla = abrirRegla;
window.nuevaRegla = nuevaRegla;
window.guardarRegla = guardarRegla;
