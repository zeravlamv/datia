from ninja import Router
from typing import Dict, Any
from django.http import HttpRequest
from datia.services.predictive_service import PredictiveService

router = Router()

@router.get("/eda", response=Dict[str, Any])
def get_eda(request: HttpRequest, empresa: int, start_year: int, end_year: int):
    service = PredictiveService()
    return service.get_eda(empresa, start_year, end_year)

@router.get("/forecast", response=Dict[str, Any])
def get_forecast(request: HttpRequest, empresa: int, start_year: int, end_year: int, horizon: int = 4, scenario: str = 'base'):
    service = PredictiveService()
    return service.get_forecast(empresa, start_year, end_year, horizon, scenario)

