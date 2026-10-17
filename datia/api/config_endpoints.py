from ninja import Router, Schema
from typing import Dict, Any, List
from django.shortcuts import get_object_or_404
from datia.models.master import GlobalConfig
from datia.models.preferences import UserPreference
import json

router = Router(tags=["Configuration"])

class GlobalConfigSchema(Schema):
    settings: Dict[str, Any]

class UserConfigSchema(Schema):
    visible_tabs: Dict[str, bool]

@router.get("/runtime")
def get_runtime_config(request):
    """Configuración de plataforma sin secretos, para aplicar al arrancar la app."""
    if not getattr(request.user, 'is_authenticated', False):
        return {"error": "Unauthorized"}
    from datia.services.runtime_config import public_runtime
    return public_runtime()


@router.get("/global")
def get_global_config(request):
    """
    Returns the current Global Configuration.
    """
    config = GlobalConfig.load()
    return config.implanter_settings

@router.post("/global")
def update_global_config(request, payload: GlobalConfigSchema):
    """
    Updates the Global Configuration.
    Requires staff permission.
    """
    if not (request.user.is_superuser or request.user.groups.filter(name__iexact='Implantador').exists()):
        return {"error": "Unauthorized", "status": 403}
    
    config = GlobalConfig.load()
    config.implanter_settings = payload.settings
    config.save()
    return {"status": "ok"}

@router.get("/user")
def get_user_config(request):
    """
    Returns the effective configuration for the current user.
    Merges GlobalConfig with UserPreference.
    """
    global_conf = GlobalConfig.load().implanter_settings or {}
    
    # Ensure UserPreference exists
    if not hasattr(request.user, 'preferences'):
        UserPreference.objects.create(user=request.user)
        
    user_vis = request.user.preferences.visible_tabs or {}
    
    effective_config = {}
    
    # Merge keys
    all_keys = set(global_conf.keys()) | set(user_vis.keys())
    
    for key in all_keys:
        global_val = global_conf.get(key, True) 
        if not global_val:
            effective_config[key] = False
        else:
            effective_config[key] = user_vis.get(key, True)
            
    return effective_config

@router.post("/user")
def update_user_config(request, payload: UserConfigSchema):
    """
    Updates the user's preferences (specifically visible_tabs).
    """
    if not hasattr(request.user, 'preferences'):
        UserPreference.objects.create(user=request.user)
    
    prefs = request.user.preferences
    prefs.visible_tabs = payload.visible_tabs
    prefs.save()
    
    return {"status": "ok"}
