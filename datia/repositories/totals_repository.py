from .base import BaseRepository
from datia.models import MetricsTotalesEmpresaEjercicio

class TotalsRepository(BaseRepository[MetricsTotalesEmpresaEjercicio]):
    def __init__(self):
        super().__init__(MetricsTotalesEmpresaEjercicio)

    def get_by_empresa_ejercicio(self, empresa: int, ejercicio: int):
        return self.model.objects.filter(empresa=empresa, ejercicio=ejercicio).first()
