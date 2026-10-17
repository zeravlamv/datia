from ninja import Router, Schema
from typing import List, Optional
from django.shortcuts import get_object_or_404
from datia.models.mobile import MobileConfig
from datia.models.totales import MetricsTotalesEmpresaEjercicio

router = Router(tags=["Mobile"])

class MobileConfigSchema(Schema):
    mode: str = 'standard'
    layout: List[str] = []

@router.get("/config", response=MobileConfigSchema)
def get_mobile_config(request, empresa: int):
    """
    Get mobile configuration for a specific company.
    """
    # Try to find existing config, or return default
    config = MobileConfig.objects.filter(empresa_id=empresa).first()
    
    if config:
        return {
            "mode": config.mode,
            "layout": config.layout
        }
    
    # Default
    return {
        "mode": "standard",
        "layout": []
    }

@router.post("/config", response={200: dict})
def save_mobile_config(request, empresa: int, data: MobileConfigSchema):
    """
    Save or update mobile configuration.
    """
    config, created = MobileConfig.objects.update_or_create(
        empresa_id=empresa,
        defaults={
            'mode': data.mode,
            'layout': data.layout
        }
    )
    
    return {"status": "success", "mode": config.mode}

@router.get("/ejercicios", response=List[int])
def list_ejercicios(request, empresa: int):
    """
    Return all available ejercicios for a given empresa (from pre-aggregated metrics).
    """
    qs = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa).values_list('ejercicio', flat=True).distinct()
    arr = sorted(set(int(x or 0) for x in qs))
    if not arr:
        arr = []
    return arr
