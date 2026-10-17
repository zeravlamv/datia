from ninja import NinjaAPI
from datia.api.endpoints import router as datia_router
from datia.api.etl_endpoints import router as etl_router
from datia.api.patterns import router as patterns_router
from datia.api.issues import router as issues_router
from datia.api.features import router as features_router
from datia.api.template_endpoints import router as template_router
from datia.api.system_endpoints import router as system_router
from datia.api.mobile_endpoints import router as mobile_router
from datia.api.financial_endpoints import router as financial_router
from datia.api.predictive_endpoints import router as predictive_router
from datia.api.config_endpoints import router as config_router
from datia.api.endpoints_evolucion import router as evolution_router
from datia.api.inventory_endpoints import router as inventory_router
from datia.api.ai_endpoints import router as ai_report_router
from datia.api.dashboard_stats import router as dashboard_router

api = NinjaAPI(title="Datia API", version="2.0.0")

api.add_router("/datia", datia_router)
api.add_router("/etl", etl_router)
api.add_router("/patterns", patterns_router)
api.add_router("/issues", issues_router)
api.add_router("/features", features_router)
api.add_router("/template", template_router)
api.add_router("/system", system_router)
api.add_router("/mobile", mobile_router)
api.add_router("/financial", financial_router)
api.add_router("/financial/predict", predictive_router)
api.add_router("/financial/evolution", evolution_router)
api.add_router("/config", config_router)
api.add_router("/inventory", inventory_router)
api.add_router("/ai", ai_report_router)
api.add_router("/auto-training", dashboard_router)
