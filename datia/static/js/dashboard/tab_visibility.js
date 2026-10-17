function getCsrfToken() {
    // Try input first (most reliable when {% csrf_token %} is present)
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) return input.value;

    // Fallback to cookie
    const name = 'csrftoken';
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
}

function saveVisibility() {
    console.log('Attempting to save visibility...');
    const form = document.getElementById('visibility-form');
    if (!form) {
        console.error('Form not found!');
        alert('Error: Formulario no encontrado');
        return;
    }

    const checkboxes = form.querySelectorAll('input[name="visible_tabs"]');
    const visibleTabs = {};
    checkboxes.forEach(cb => {
        visibleTabs[cb.value] = cb.checked;
    });

    const userSelect = document.getElementById('user');
    const userId = userSelect ? userSelect.value : null;

    if (!userId) {
        alert('Error: Usuario no seleccionado');
        return;
    }

    const csrfToken = getCsrfToken();
    console.log('User:', userId, 'CSRF found:', !!csrfToken);

    fetch(window.location.href, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            visible_tabs: visibleTabs,
            target_user_id: userId
        })
    })
        .then(r => {
            if (!r.ok) throw new Error('Network response was not ok');
            return r.json();
        })
        .then(data => {
            console.log('Response:', data);
            if (data.status === 'ok') {
                alert('Preferencias guardadas correctamente');
            } else {
                alert('Error al guardar: ' + (data.msg || 'Desconocido'));
            }
        })
        .catch(err => {
            console.error('Error en la petición', err);
            alert('Error de conexión o servidor: ' + err.message);
        });
}
