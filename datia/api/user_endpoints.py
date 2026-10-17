from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import update_session_auth_hash
import json

@login_required
@require_POST
def change_password_api(request):
    """
    API Endpoint to change user password.
    Expects JSON: { "old_password": "...", "new_password": "..." }
    """
    try:
        data = json.loads(request.body)
        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not old_password or not new_password:
            return JsonResponse({'status': 'error', 'message': 'Faltan datos obligatorios.'}, status=400)

        # Verify old password
        if not request.user.check_password(old_password):
            return JsonResponse({'status': 'error', 'message': 'La contraseña actual es incorrecta.'}, status=400)

        # Set new password
        request.user.set_password(new_password)
        request.user.save()
        
        # Keep user logged in after password change
        update_session_auth_hash(request, request.user)

        return JsonResponse({'status': 'success', 'message': 'Contraseña actualizada correctamente.'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
