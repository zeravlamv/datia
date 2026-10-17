import re
from typing import Dict, Any, List, Optional, Tuple


def _months_es() -> List[str]:
    return ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']


def _parse_month(token: str) -> Optional[int]:
    if not token:
        return None
    t = str(token).strip().lower()
    months = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    if t in months:
        return months[t]
    try:
        n = int(t)
        if 1 <= n <= 12:
            return n
    except Exception:
        return None
    return None


def _extract_range(question: str) -> Optional[Tuple[int, int]]:
    q = (question or '').lower()
    m = re.search(r"(?:periodo|per[íi]odo)\s*(\d{1,2})\s*(?:a|hasta|y|-)\s*(\d{1,2})", q)
    if m:
        a = _parse_month(m.group(1))
        b = _parse_month(m.group(2))
        if a and b:
            return (min(a, b), max(a, b))
    m2 = re.search(r"\bde\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+a\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", q)
    if m2:
        a = _parse_month(m2.group(1))
        b = _parse_month(m2.group(2))
        if a and b:
            return (min(a, b), max(a, b))
    return None


def build_compras_mensual_chart(handler, empresa: int, year: int, prev: int, title: str) -> Dict[str, Any]:
    labels = _months_es()
    curr = [0.0] * 12
    prev_vals = [0.0] * 12
    for r in handler.Models.MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa, ejercicio=year):
        m = int(getattr(r, 'mes', 0) or 0)
        if 1 <= m <= 12:
            curr[m - 1] = handler.to_float(getattr(r, 'importe_neto_total', 0))
    for r in handler.Models.MetricsTotalesEmpresaEjercicioCompraMes.objects.filter(empresa=empresa, ejercicio=prev):
        m = int(getattr(r, 'mes', 0) or 0)
        if 1 <= m <= 12:
            prev_vals[m - 1] = handler.to_float(getattr(r, 'importe_neto_total', 0))
    return handler.line_dual(labels, curr, prev_vals, title, str(year), str(prev))


def build_compras_top_proveedores(handler, empresa: int, year: int, prev: int, limit: int, worst: bool = False) -> Dict[str, Any]:
    qs = handler.Models.MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=year)
    if worst:
        qs = qs.filter(importe_neto_total__gt=0)
    rows = list(qs.order_by('importe_neto_total' if worst else '-importe_neto_total')[:limit])
    data = []
    for r in rows:
        name = (getattr(r, 'nombre', None) or getattr(r, 'proveedor', None) or handler.t('unknown')).strip()
        val = handler.to_float(getattr(r, 'importe_neto_total', 0))
        data.append({'name': name, 'value': val})
    labels = [(d['name'][:15] + '...') if len(d['name']) > 15 else d['name'] for d in data]
    values = [d['value'] for d in data]
    keys = [getattr(r, 'proveedor', None) for r in rows if getattr(r, 'proveedor', None) is not None]
    prev_rows = list(
        handler.Models.MetricsTotalesEmpresaEjercicioProveedor.objects.filter(empresa=empresa, ejercicio=prev, proveedor__in=keys)
    ) if keys else []
    prev_map = {getattr(r, 'proveedor', None): r for r in prev_rows}

    table_rows = []
    for d, r in zip(data, rows):
        key = getattr(r, 'proveedor', None)
        pr = prev_map.get(key)
        cy_sales = float(d.get('value') or 0.0)
        py_sales = handler.to_float(getattr(pr, 'importe_neto_total', 0)) if pr else 0.0
        cy_cost = handler.to_float(getattr(r, 'importe_coste_total', 0))
        py_cost = handler.to_float(getattr(pr, 'importe_coste_total', 0)) if pr else 0.0
        cy_ops = int(getattr(r, 'albaranes_count', 0) or 0)
        py_ops = int(getattr(pr, 'albaranes_count', 0) or 0) if pr else 0
        cy_margin = cy_sales - cy_cost
        py_margin = py_sales - py_cost
        cy_margin_pct = (cy_margin / cy_sales * 100.0) if cy_sales else 0.0
        py_margin_pct = (py_margin / py_sales * 100.0) if py_sales else 0.0
        sales_var_pct = ((cy_sales - py_sales) / py_sales * 100.0) if py_sales else 0.0
        price_cy = (cy_sales / cy_ops) if cy_ops else 0.0
        price_py = (py_sales / py_ops) if py_ops else 0.0
        table_rows.append([
            d['name'],
            round(cy_sales, 2), round(py_sales, 2), round(sales_var_pct, 1),
            round(cy_cost, 2), round(py_cost, 2),
            round(cy_margin, 2), round(py_margin, 2),
            round(cy_margin_pct, 1), round(py_margin_pct, 1),
            cy_ops, py_ops,
            round(price_cy, 2), round(price_py, 2)
        ])
    cy_total = handler.compras_totales(empresa, year)
    py_total = handler.compras_totales(empresa, prev)
    top_for_pie = [(labels[i], values[i]) for i in range(min(5, len(values)))]
    top1_name = data[0]['name'] if data else ''
    top1_val = values[0] if values else 0.0
    return {
        'type': 'report',
        'key': 'compras_top_proveedores',
        'kpis': [{'label': f"Top 1: {top1_name}", 'value': round(top1_val, 2), 'suffix': '€', 'color': '#3b82f6'}] if data else [],
        'answer': f"{'Proveedores con menores compras' if worst else 'Mejores proveedores'} del ejercicio {year}.",
        'chart_config': handler.yoy_total_chart(year, prev, cy_total, py_total, f"Compras {year} vs {prev}"),
        'chart_pareto': handler.bar_h(labels, values, "Proveedores con menores compras" if worst else "Mejores proveedores", "Compras (€)"),
        'chart_concentration': handler.concentration_pie(top_for_pie, sum(values), 'Concentración de compras'),
        'table': {'title': 'Detalle', 'columns': ['Proveedor', f'Compras {year} (€)', f'Compras {prev} (€)', 'Var %', f'Coste {year} (€)', f'Coste {prev} (€)', f'Margen {year} (€)', f'Margen {prev} (€)', f'Margen {year} %', f'Margen {prev} %', f'Ops {year}', f'Ops {prev}', f'Precio medio {year} (€)', f'Precio medio {prev} (€)'], 'rows': table_rows},
    }


def build_compras_resumen(handler, empresa: int, year: int, prev: int) -> Dict[str, Any]:
    cy = handler.compras_totales(empresa, year)
    py = handler.compras_totales(empresa, prev)
    yoy = ((cy - py) / py * 100.0) if py > 0 else 0.0
    kpis = [{'label': 'Compras', 'value': round(cy, 2), 'suffix': '€', 'color': '#3b82f6', 'change': round(yoy, 1)}]
    chart = build_compras_mensual_chart(handler, empresa, year, prev, "Compras por mes")
    return {'type': 'report', 'key': 'compras_resumen', 'kpis': kpis, 'answer': f"Resumen de compras del ejercicio {year}.", 'chart_config': chart}


def build_compras_mensual(handler, empresa: int, year: int, prev: int) -> Dict[str, Any]:
    chart = build_compras_mensual_chart(handler, empresa, year, prev, "Compras por mes")
    return {'type': 'report', 'key': 'compras_mensual', 'kpis': [], 'answer': f"Evolución mensual de compras ({year} vs {prev}).", 'chart_config': chart}


def build_ventas_rango_periodos(handler, query: str, empresa: int, year: int, prev: int) -> Dict[str, Any]:
    rng = _extract_range(query or '')
    if not rng:
        rng = (1, 12)
    a, b = rng

    def rows_for(y: int):
        return handler.Models.MetricsTotalesEmpresaEjercicioMes.objects.filter(
            empresa=empresa, ejercicio=y, mes__gte=a, mes__lte=b
        )

    cy = sum(handler.to_float(getattr(r, 'importe_neto_total', 0)) for r in rows_for(year))
    py = sum(handler.to_float(getattr(r, 'importe_neto_total', 0)) for r in rows_for(prev))

    labels = _months_es()[a - 1:b]
    cur = [0.0] * (b - a + 1)
    prv = [0.0] * (b - a + 1)
    for r in rows_for(year):
        m = int(getattr(r, 'mes', 0) or 0)
        if a <= m <= b:
            cur[m - a] = handler.to_float(getattr(r, 'importe_neto_total', 0))
    for r in rows_for(prev):
        m = int(getattr(r, 'mes', 0) or 0)
        if a <= m <= b:
            prv[m - a] = handler.to_float(getattr(r, 'importe_neto_total', 0))

    chart = handler.line_dual(labels, cur, prv, f"Ventas {labels[0]}–{labels[-1]}", str(year), str(prev))
    return {
        'type': 'report',
        'key': 'ventas_rango_periodos',
        'kpis': [{'label': 'Ventas', 'value': round(cy, 2), 'suffix': '€', 'color': '#3b82f6', 'change': round(((cy - py) / py * 100.0) if py > 0 else 0.0, 1)}],
        'answer': f"Ventas de {labels[0]} a {labels[-1]} ({year} vs {prev}).",
        'chart_config': chart,
    }
