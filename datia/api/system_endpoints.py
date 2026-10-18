from ninja import Router, Schema
from typing import Dict, Any
from datia.services.system_monitor import SystemMonitorService
from django.conf import settings
from django.http import JsonResponse
from datia.models.master import Empresa, GlobalConfig
from django.db.models import Count
import json
import os
from datia.services.dev.mobile_server_manager import start as mobile_start, stop as mobile_stop, status as mobile_status
from datia.services.dev.ngrok_tunnel import current_url as ngrok_current_url, open_tunnel as ngrok_open_tunnel

router = Router(tags=["System"])

class SystemConfigSchema(Schema):
    preset: str

# In-memory config storage (or could be DB/File)
CONFIG_FILE = os.path.join(settings.BASE_DIR, 'datia', 'config', 'system_perf.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                    print(f"DEBUG: Loaded Config: {data}")
                return data
        except Exception as e:
            if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                print(f"DEBUG: Load Config Error: {e}")
            pass
    else:
        if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
            print(f"DEBUG: Config file not found at {CONFIG_FILE}")
    return {"preset": "auto"}

def save_config(data):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f)
        if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
            print(f"DEBUG: Saved Config: {data} to {CONFIG_FILE}")
    except Exception as e:
        if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
            print(f"DEBUG: Save Config Error: {e}")

@router.get("/metrics")
def get_system_metrics(request):
    metrics = SystemMonitorService.get_system_metrics()
    user_config = load_config()
    preset = user_config.get("preset", "auto")
    adaptive = SystemMonitorService.get_adaptive_config(metrics, preset)
    schema_status = SystemMonitorService.get_database_schema_status()
    response = JsonResponse(
        {
            "metrics": metrics,
            "config": adaptive,
            "preset": preset,
            "schema": schema_status,
        }
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@router.get("/schema", response=Dict[str, Any])
def get_schema_status(request):
    return SystemMonitorService.get_database_schema_status()

@router.post("/config")
def update_system_config(request, payload: SystemConfigSchema):
    """
    Updates the performance preset (auto, eco, turbo).
    """
    preset = payload.preset
    save_config({"preset": preset})
    return {"status": "success", "preset": preset}

@router.post("/mobile_server/start")
def api_mobile_server_start(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {"status": "error", "message": "forbidden"}
    return mobile_start()

@router.post("/mobile_server/stop")
def api_mobile_server_stop(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return {"status": "error", "message": "forbidden"}
    return mobile_stop()

@router.get("/mobile_server/status")
def api_mobile_server_status(request):
    if not request.user.is_authenticated:
        return {"running": False}
    return mobile_status()

def _staff_only(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)

@router.get("/ngrok/url")
def api_ngrok_url(request):
    if not _staff_only(request):
        return {"status": "error", "message": "Solo un administrador puede ver el acceso móvil."}
    url = ngrok_current_url()
    return {"status": "ok", "url": url}

@router.post("/ngrok/open")
def api_ngrok_open(request):
    if not _staff_only(request):
        return {"status": "error", "message": "Solo un administrador puede abrir el acceso móvil."}
    return ngrok_open_tunnel()

@router.get("/initial_setup/status")
def initial_setup_status(request):
    """
    Estado del asistente de inicialización.
    Indica si existen empresas y si el asistente ya fue completado.
    """
    config = GlobalConfig.load()
    settings_map: Dict[str, Any] = config.implanter_settings or {}
    completed = bool(settings_map.get('initial_setup_completed', False))
    schema = SystemMonitorService.get_database_schema_status()
    if not schema.get("ok", True):
        return {
            "has_companies": False,
            "initial_setup_completed": completed,
            "schema": schema,
        }
    try:
        has_companies = Empresa.objects.exists()
    except Exception:
        has_companies = False
    return {
        "has_companies": bool(has_companies),
        "initial_setup_completed": completed,
    }

@router.get("/initial_setup/verify")
def initial_setup_verify(request):
    """
    Verifica integridad básica tras la importación inicial de empresas.
    """
    try:
        count = Empresa.objects.count()
        errors = []
        if count == 0:
            errors.append({
                "code": "NO_COMPANIES",
                "message": "No se ha encontrado ninguna empresa en la base de datos."
            })
        dup = (
            Empresa.objects.values('codigo')
            .annotate(c=Count('id'))
            .filter(c__gt=1)
        )
        if dup.exists():
            errors.append({
                "code": "DUPLICATE_CODES",
                "message": "Se han detectado códigos de empresa duplicados. Revisa los datos en origen."
            })
        status = "ok" if not errors else "error"
        return {
            "status": status,
            "count": count,
            "errors": errors
        }
    except Exception as e:
        return {
            "status": "error",
            "count": 0,
            "errors": [{
                "code": "EXCEPTION",
                "message": str(e)
            }]
        }, 500

@router.post("/initial_setup/complete")
def initial_setup_complete(request):
    """
    Marca el asistente de inicialización como completado.
    Solo disponible para superusuarios o implantadores.
    """
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return {"status": "error", "message": "Autenticación requerida"}, 401
    if not (getattr(user, 'is_superuser', False) or user.groups.filter(name__iexact='Implantador').exists()):
        return {"status": "error", "message": "Permisos insuficientes"}, 403
    config = GlobalConfig.load()
    settings_map: Dict[str, Any] = config.implanter_settings or {}
    settings_map['initial_setup_completed'] = True
    config.implanter_settings = settings_map
    config.save()
    return {"status": "ok"}
