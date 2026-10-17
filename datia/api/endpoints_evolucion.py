from ninja import Router, Schema
from typing import List, Dict, Any, Optional
from django.http import HttpRequest
from django.db.models import Sum
from django.db.models import Q
from datia.models.financial import DatiaAcumuladosConta

router = Router()

class EvolutionDataPoint(Schema):
    periodo: str
    anio: int
    mes: int
    ingresos: float
    gastos: float
    resultado: float

class EvolutionResponse(Schema):
    status: str
    data: List[EvolutionDataPoint]
    meta: Dict[str, Any]

@router.get("/evolution", response=EvolutionResponse)
def get_financial_evolution(request: HttpRequest, empresa: Optional[int] = None, start_year: Optional[int] = None, end_year: Optional[int] = None, group_by: str = "month"):
    """
    Evolución financiera desde Postgres (datia_financial_acumulados).
    Filtro por empresa y rango de años. group_by: 'month' o 'year'.
    """
    emp = int(empresa or 1)
    base_q = DatiaAcumuladosConta.objects.filter(empresa=emp, periodo__gt=0, periodo__lte=12)
    if start_year:
        base_q = base_q.filter(ejercicio__gte=int(start_year))
    if end_year:
        base_q = base_q.filter(ejercicio__lte=int(end_year))

    data: List[EvolutionDataPoint] = []
    try:
        if group_by == 'year':
            inc_rows = base_q.filter(cuenta__startswith='7').values('ejercicio').annotate(total=Sum('saldo')).order_by('-ejercicio')
            gas_rows = base_q.filter(cuenta__startswith='6').values('ejercicio').annotate(total=Sum('saldo'))
            inc_map = {int(r['ejercicio']): float(abs(r['total'] or 0)) for r in inc_rows}
            gas_map = {int(r['ejercicio']): float(r['total'] or 0) for r in gas_rows}
            years = sorted(set(inc_map.keys()) | set(gas_map.keys()), reverse=True)
            for y in years:
                ingreso = round(inc_map.get(y, 0.0), 2)
                gasto = round(gas_map.get(y, 0.0), 2)
                resultado = round(ingreso - gasto, 2)
                data.append(EvolutionDataPoint(
                    periodo=str(y),
                    anio=y,
                    mes=0,
                    ingresos=ingreso,
                    gastos=gasto,
                    resultado=resultado
                ))
        else:
            inc_rows = base_q.filter(cuenta__startswith='7').values('ejercicio', 'periodo').annotate(total=Sum('saldo')).order_by('ejercicio', 'periodo')
            gas_rows = base_q.filter(cuenta__startswith='6').values('ejercicio', 'periodo').annotate(total=Sum('saldo'))
            inc_map = {(int(r['ejercicio']), int(r['periodo'])): float(abs(r['total'] or 0)) for r in inc_rows}
            gas_map = {(int(r['ejercicio']), int(r['periodo'])): float(r['total'] or 0) for r in gas_rows}
            keys = sorted(set(list(inc_map.keys()) + list(gas_map.keys())))
            for (anio, mes) in keys:
                ingreso = round(inc_map.get((anio, mes), 0.0), 2)
                gasto = round(gas_map.get((anio, mes), 0.0), 2)
                resultado = round(ingreso - gasto, 2)
                label = f"{anio}-{mes:02d}"
                data.append(EvolutionDataPoint(
                    periodo=label,
                    anio=anio,
                    mes=mes,
                    ingresos=ingreso,
                    gastos=gasto,
                    resultado=resultado
                ))

        return EvolutionResponse(
            status="ok",
            data=data,
            meta={
                "empresa": emp,
                "start_year": start_year,
                "end_year": end_year,
                "group_by": group_by,
                "count": len(data),
                "source": "postgres"
            }
        )
    except Exception as e:
        return EvolutionResponse(
            status="error",
            data=[],
            meta={"error": str(e)}
        )
