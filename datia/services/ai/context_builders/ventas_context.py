from datia.factories import RepositoryFactory
from datia.models import (
    MetricsTotalesEmpresaEjercicioMes,
    MetricsTotalesEmpresaEjercicioCliente,
    MetricsTotalesEmpresaEjercicioArticulo,
    MetricsTotalesEmpresaEjercicioCodigoPostal,
    MetricsTotalesEmpresaEjercicioClienteMes,
)
from django.db.models import Sum
from datia.services.cache_service import compute_mssql_fingerprint

class VentasContextBuilder:
    """
    Agrega datos financieros (Ventas) para el informe de IA.
    Replica la lógica de los widgets del Dashboard.
    """
    def build_context(self, empresa: int, ejercicio: int) -> dict:
        context = {
            "empresa": empresa,
            "ejercicio": ejercicio,
            "moneda": "EUR"
        }
        context["meta"] = {
            "empresa_id": empresa,
            "ejercicio": ejercicio,
            "fingerprint": compute_mssql_fingerprint()
        }
        
        # 1. Resumen Global (KPIs Principales)
        repo = RepositoryFactory.get_totals_repository()
        total_obj = repo.get_by_empresa_ejercicio(empresa, ejercicio)
        
        neto = float(total_obj.importe_neto_total) if total_obj else 0
        coste = float(total_obj.importe_coste_total) if total_obj else 0
        margen_pct = ((neto - coste) / neto * 100) if neto > 0 else 0
        albaranes = total_obj.albaranes_count if total_obj else 0
        
        # Comparativa Año Anterior
        prev_obj = repo.get_by_empresa_ejercicio(empresa, ejercicio - 1)
        prev_neto = float(prev_obj.importe_neto_total) if prev_obj else 0
        
        var_neto = ((neto - prev_neto) / prev_neto * 100) if prev_neto > 0 else 0
        diff_neto = neto - prev_neto

        context['kpis'] = {
            "ventas_totales": neto,
            "margen_beneficio_pct": round(margen_pct, 2),
            "crecimiento_anual_pct": round(var_neto, 2),
            "diferencia_absoluta_anual": diff_neto,
            "total_operaciones": albaranes
        }
        
        # 2. Top Clientes (Pareto A - 80/20 implícito en top 5 por volumen)
        top_clients = MetricsTotalesEmpresaEjercicioCliente.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).order_by('-importe_neto_total')[:5]
        
        context['top_clientes'] = [
            {
                "nombre": c.nombre or f"Cliente {c.cliente}", 
                "volumen_compras": float(c.importe_neto_total)
            }
            for c in top_clients
        ]
        
        clientes_riesgo = []
        for c in top_clients:
            curr = float(c.importe_neto_total or 0)
            prev_row = MetricsTotalesEmpresaEjercicioCliente.objects.filter(
                empresa=empresa, ejercicio=ejercicio - 1, cliente=c.cliente
            ).first()
            prev = float(prev_row.importe_neto_total or 0) if prev_row else 0.0
            yoy = ((curr - prev) / prev * 100) if prev > 0 else 0.0
            weight = (curr / neto * 100) if neto > 0 else 0.0
            if yoy < -15 and weight >= 5:
                clientes_riesgo.append({
                    "cliente": c.cliente,
                    "nombre": c.nombre or f"Cliente {c.cliente}",
                    "yoy_pct": round(yoy, 2),
                    "peso_pct": round(weight, 2)
                })
        
        # 3. Top Productos
        top_arts = MetricsTotalesEmpresaEjercicioArticulo.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).order_by('-importe_neto_total')[:5]
        
        context['top_productos'] = [
            {
                "nombre": c.descripcion or f"Art {c.articulo}", 
                "ingresos_generados": float(c.importe_neto_total)
            }
            for c in top_arts
        ]
        
        all_arts = list(MetricsTotalesEmpresaEjercicioArticulo.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).order_by('-importe_neto_total')[:200])
        productos_negativos = []
        ranking_top_margen = []
        margen_total = 0.0
        for a in all_arts:
            neto_a = float(a.importe_neto_total or 0)
            coste_a = float(a.importe_coste_total or 0)
            margen_a = neto_a - coste_a
            margen_total += max(margen_a, 0)
            if margen_a < 0 or (neto_a > 0 and ((margen_a / neto_a) * 100) < 5):
                productos_negativos.append({
                    "articulo": a.articulo,
                    "nombre": a.descripcion or f"Art {a.articulo}",
                    "margen": margen_a
                })
            ranking_top_margen.append({
                "articulo": a.articulo,
                "nombre": a.descripcion or f"Art {a.articulo}",
                "margen": margen_a
            })
        ranking_top_margen = sorted(ranking_top_margen, key=lambda x: x["margen"], reverse=True)[:5]
        margen_por_producto_pct = [
            {
                "articulo": x["articulo"],
                "nombre": x["nombre"],
                "share_pct": round(((x["margen"] / margen_total) * 100), 2) if margen_total > 0 else 0.0
            } for x in ranking_top_margen
        ]
        
        # 4. Tendencia Mensual (Para detectar estacionalidad)
        months = MetricsTotalesEmpresaEjercicioMes.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).order_by('mes')
        
        context['evolucion_mensual'] = [
            {"mes": m.mes, "ventas": float(m.importe_neto_total), "margen": float(m.importe_neto_total - m.importe_coste_total)}
            for m in months
        ]
        
        # 5. Ticket Medio Mensual
        context['ticket_mensual'] = [
            {
                "mes": m.mes,
                "ticket": float(m.importe_neto_total) / m.albaranes_count if m.albaranes_count > 0 else 0.0
            }
            for m in months
        ]

        # 6. Clientes/Mes para Top Clientes
        clientes_mes = []
        for c in top_clients:
            serie = MetricsTotalesEmpresaEjercicioClienteMes.objects.filter(
                empresa=empresa, ejercicio=ejercicio, cliente=c.cliente
            ).order_by('mes')
            clientes_mes.append({
                "cliente": c.cliente,
                "nombre": c.nombre or f"Cliente {c.cliente}",
                "series": [{"mes": s.mes, "ventas": float(s.importe_neto_total)} for s in serie]
            })
        context['clientes_mes'] = clientes_mes

        # 7. Geografía por Código Postal
        cp_qs = MetricsTotalesEmpresaEjercicioCodigoPostal.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).order_by('-importe_neto_total')[:5]
        context['geografia'] = [
            {"cod_postal": x.cod_postal, "ventas": float(x.importe_neto_total)}
            for x in cp_qs
        ]

        # 8. Pareto 80/20
        total_clients_sum = MetricsTotalesEmpresaEjercicioCliente.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).aggregate(Sum('importe_neto_total'))['importe_neto_total__sum'] or 0
        top_clients_sum = sum(float(c.importe_neto_total) for c in top_clients)
        top_share_pct = (top_clients_sum / float(total_clients_sum) * 100) if total_clients_sum else 0.0
        context['pareto'] = {
            "top_share_pct": round(top_share_pct, 2),
            "top_n": len(top_clients)
        }

        # 9. Estacionalidad y YoY por mes
        prev_months = MetricsTotalesEmpresaEjercicioMes.objects.filter(
            empresa=empresa, ejercicio=ejercicio - 1
        ).order_by('mes')
        prev_map = {pm.mes: float(pm.importe_neto_total) for pm in prev_months}
        estacionalidad = []
        for m in months:
            ventas = float(m.importe_neto_total)
            share_pct = (ventas / neto * 100) if neto > 0 else 0.0
            prev_val = prev_map.get(m.mes, 0.0)
            yoy_pct = ((ventas - prev_val) / prev_val * 100) if prev_val > 0 else 0.0
            estacionalidad.append({"mes": m.mes, "share_pct": round(share_pct, 2), "yoy_pct": round(yoy_pct, 2)})
        context['estacionalidad'] = estacionalidad
        meses_yoy_caida = sum(1 for e in estacionalidad if e.get("yoy_pct", 0) < -15)

        # 10. Alertas Ejecutivas
        alertas = []
        if margen_pct < 20:
            alertas.append("Margen por debajo del 20%")
        if context['pareto']['top_share_pct'] > 60:
            alertas.append("Concentración elevada de ventas en pocos clientes")
        if any(item.get("yoy_pct", 0) < -15 for item in estacionalidad):
            alertas.append("Caída interanual relevante en algún mes (>15%)")
        context['alertas'] = alertas
        context['señales'] = {
            "margen_pct": round(margen_pct, 2),
            "meses_yoy_caida": meses_yoy_caida,
            "clientes_riesgo_count": len(clientes_riesgo),
            "productos_negativos_count": len(productos_negativos),
            "concentracion_pct": round(context['pareto']['top_share_pct'], 2)
        }
        context['productos_negativos'] = productos_negativos[:10]
        context['clientes_riesgo'] = clientes_riesgo
        context['ranking_top_margen'] = ranking_top_margen
        context['margen_por_producto_pct'] = margen_por_producto_pct

        return context
