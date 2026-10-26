import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from datia.api.guards import login_required_json
from datia.services.ai.reglas_negocio import guardar_fichero, leer_fichero, listar_ficheros


def _cuerpo(request):
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


@csrf_exempt
@login_required_json
def reglas_lista_api(request):
    if request.method == 'GET':
        return JsonResponse({'status': 'ok', 'ficheros': listar_ficheros()})
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    data = _cuerpo(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'El cuerpo no es JSON.'}, status=400)
    try:
        nombre = guardar_fichero(data.get('nombre'), data.get('texto') or '', crear=True)
    except FileExistsError:
        return JsonResponse({'status': 'error', 'message': 'Ese fichero ya existe.'}, status=409)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    return JsonResponse({'status': 'ok', 'nombre': nombre})


@csrf_exempt
@login_required_json
def reglas_detalle_api(request, nombre):
    if request.method == 'GET':
        try:
            texto = leer_fichero(nombre)
        except FileNotFoundError:
            return JsonResponse({'status': 'error', 'message': 'No está ese fichero.'}, status=404)
        except ValueError as exc:
            return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
        return JsonResponse({'status': 'ok', 'nombre': nombre if nombre.lower().endswith('.md') else f'{nombre}.md', 'texto': texto})
    if request.method != 'PUT':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    data = _cuerpo(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'El cuerpo no es JSON.'}, status=400)
    try:
        guardado = guardar_fichero(nombre, data.get('texto') or '', crear=False)
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': 'No está ese fichero.'}, status=404)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    return JsonResponse({'status': 'ok', 'nombre': guardado})
