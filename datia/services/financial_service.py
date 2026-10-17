from typing import Dict, List, Any
from django.db.models import Sum, Q
from django.db.utils import ProgrammingError
from datia.models.financial import DatiaAcumuladosConta, DatiaPlanCuentas, DatiaGrupos, DatiaCarteraEfectos
from datia.services.cache_service import CacheService, compute_mssql_fingerprint
from datia.services.analysis_service import AnalysisService
from datia.models.totales import MetricsTotalesEmpresaEjercicioMes

class FinancialService:
    """
    Business Logic for Financial Reporting.
    Calculates Ratios, P&L, and Balance Sheet.
    """

    def __init__(self):
        self.cache = CacheService()

    def get_snapshot(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        """
        Returns high-level financial KPIs for the dashboard.
        """
        fp = compute_mssql_fingerprint()
        cache_key = f"{fp}:fin_snapshot_{empresa}_{ejercicio}_v6"
        cached = self.cache.get(cache_key) 
        if cached:
            print(f"🔥 [CACHE HIT] Financial Snapshot found for {empresa}/{ejercicio}")
            return cached

        # Calculate Actuals (separar ventas 70 del resto del grupo 7)
        ventas = self._get_saldo_grupo(empresa, ejercicio, '70')
        otros7 = sum(self._get_saldo_grupo(empresa, ejercicio, p) for p in ['72','73','74','75','76','77','78','79'])
        compras = self._get_saldo_grupo(empresa, ejercicio, '60')
        otros_gastos = sum(self._get_saldo_grupo(empresa, ejercicio, p) for p in ['62','63','64','65','66','67','68','69'])
        depam = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='68', periodo__lte=12
        ).aggregate(t=Sum('saldo'))['t'] or 0.0
        
        # Correction:
        # Grupo 6 (Gastos): Saldo > 0 (Deudor)
        # Grupo 7 (Ingresos): Saldo < 0 (Acreedor)
        
        ingresos_val = float(abs(ventas) if ventas < 0 else -ventas)
        otros_ingresos_val = float(abs(otros7) if otros7 < 0 else -otros7)
        gastos_val = float(compras)
        otros_gastos_val = float(otros_gastos)
        # EBITDA según especificación del usuario:
        # 70 + (resto grupo 7) + variación existencias - compras(60) - otros gastos(62–69)
        ebitda = ingresos_val + otros_ingresos_val - gastos_val - otros_gastos_val
        
        # Variación de existencias independiente (61 y 71, magnitud positiva)
        var_61 = self._get_saldo_grupo(empresa, ejercicio, '61')
        var_71 = self._get_saldo_grupo(empresa, ejercicio, '71')
        variacion_val = float(abs(var_71)) + float(var_61)
        # Incorporar variación a EBITDA final (según fórmula)
        ebitda = ebitda + variacion_val
        
        # Calculate Budgets (optional: if table or data is missing, fallback to zeros)
        bud_ing_val = 0.0
        bud_gas_val = 0.0
        bud_ebitda = 0.0
        try:
            from datia.models.financial import DatiaPresupuestos
            
            qs_ing = DatiaPresupuestos.objects.filter(empresa=empresa, ejercicio=ejercicio, cuenta__startswith='7')
            qs_gas = DatiaPresupuestos.objects.filter(empresa=empresa, ejercicio=ejercicio, cuenta__startswith='6')
            
            bud_ing = qs_ing.aggregate(t=Sum('importe'))['t'] or 0.0
            bud_gas = qs_gas.aggregate(t=Sum('importe'))['t'] or 0.0
            
            # Budget logic matches Acumulados logic (Signed)
            bud_ing_val = abs(bud_ing) if bud_ing < 0 else -bud_ing
            bud_gas_val = bud_gas
            bud_ebitda = bud_ing_val - bud_gas_val
        except Exception:
            bud_ing_val = 0.0
            bud_gas_val = 0.0
            bud_ebitda = 0.0
        
        # Ratios
        # Activo Corriente: Grupo 3 + 43 + 57... (Simplified: Grupo 3, 4, 5 with Saldo > 0)
        # Pasivo Corriente: Grupo 4, 5 with Saldo < 0
        
        activo_corriente = self._get_saldo_pattern(empresa, ejercicio, ['3%', '43%', '57%'])
        pasivo_corriente = abs(self._get_saldo_pattern(empresa, ejercicio, ['40%', '41%', '52%'])) # Approx
        
        liquidez = (activo_corriente / pasivo_corriente) if pasivo_corriente else 0
        
        # New Ratios
        # Solvencia = Activo Total / Pasivo Total
        # Activo Total (Approx): Grupos 2, 3, 4 (Deudor), 5 (Deudor)
        # Pasivo Total (Approx): Grupos 1 (Ajeno), 4 (Acreedor), 5 (Acreedor)
        # Patrimonio Neto: Grupos 10, 11, 12
        
        activo_total = self._get_saldo_pattern(empresa, ejercicio, ['2%', '3%', '43%', '57%'])
        pasivo_total = abs(self._get_saldo_pattern(empresa, ejercicio, ['13%', '14%', '15%', '16%', '17%', '40%', '41%', '52%']))
        patrimonio_neto = abs(self._get_saldo_pattern(empresa, ejercicio, ['10%', '11%', '12%']))

        solvencia = (activo_total / pasivo_total) if pasivo_total else 0
        endeudamiento = ((pasivo_total / patrimonio_neto) * 100) if patrimonio_neto else 0

        prev_year = ejercicio - 1
        ventas_py = self._get_saldo_grupo(empresa, prev_year, '70')
        otros7_py = sum(self._get_saldo_grupo(empresa, prev_year, p) for p in ['72','73','74','75','76','77','78','79'])
        compras_py = self._get_saldo_grupo(empresa, prev_year, '60')
        otros_gastos_py = sum(self._get_saldo_grupo(empresa, prev_year, p) for p in ['62','63','64','65','66','67','68','69'])
        var_61_py = self._get_saldo_grupo(empresa, prev_year, '61')
        var_71_py = self._get_saldo_grupo(empresa, prev_year, '71')
        ingresos_py = float(abs(ventas_py) if ventas_py < 0 else -ventas_py)
        otros_ingresos_py = float(abs(otros7_py) if otros7_py < 0 else -otros7_py)
        variacion_py = float(abs(var_71_py)) + float(var_61_py)
        gastos_py = float(compras_py)
        otros_gastos_py_val = float(otros_gastos_py)

        # Fallback: si el ejercicio anterior no tiene ingresos contables pero sí hay métricas de ventas,
        # usamos MetricsTotalesEmpresaEjercicio como aproximación para la comparación de ingresos.
        try:
            if prev_year > 0 and abs(ingresos_py) < 0.01:
                from datia.models.totales import MetricsTotalesEmpresaEjercicio
                m_prev = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa, ejercicio=prev_year).first()
                if m_prev and m_prev.importe_neto_total:
                    ingresos_py = float(m_prev.importe_neto_total or 0.0)
        except Exception:
            pass

        # Fallback análogo para gastos: si no hay compras contables pero sí métricas de compras,
        # usamos MetricsTotalesEmpresaEjercicioCompra como proxy de gastos operativos.
        try:
            if prev_year > 0 and abs(gastos_py) < 0.01:
                from datia.models.totales import MetricsTotalesEmpresaEjercicioCompra
                m_prev_comp = MetricsTotalesEmpresaEjercicioCompra.objects.filter(empresa=empresa, ejercicio=prev_year).first()
                if m_prev_comp and m_prev_comp.importe_neto_total:
                    gastos_py = float(m_prev_comp.importe_neto_total or 0.0)
        except Exception:
            pass

        ebitda_py = ingresos_py + otros_ingresos_py + variacion_py - gastos_py - otros_gastos_py_val
        
        def _var(cy, py):
            d = float(cy) - float(py)
            pct = (d / float(py) * 100) if float(py) != 0 else 0.0
            return {'abs': round(d, 2), 'pct': round(pct, 2)}
        
        data = {
            'ingresos': round(float(ingresos_val), 2),
            'otros_ingresos': round(float(otros_ingresos_val), 2),
            'gastos': round(float(gastos_val), 2),
            'otros_gastos': round(float(otros_gastos_val), 2),
            'resultado': round(float(ebitda), 2),
            'variacion': round(float(variacion_val), 2),
            'py': {
                'ingresos': round(float(ingresos_py), 2),
                'otros_ingresos': round(float(otros_ingresos_py), 2),
                'gastos': round(float(gastos_py), 2),
                'otros_gastos': round(float(otros_gastos_py_val), 2),
                'resultado': round(float(ebitda_py), 2),
                'variacion': round(float(variacion_py), 2),
                'ejercicio': prev_year
            },
            'var': {
                'ingresos': _var(ingresos_val, ingresos_py),
                'otros_ingresos': _var(otros_ingresos_val, otros_ingresos_py),
                'gastos': _var(gastos_val, gastos_py),
                'otros_gastos': _var(otros_gastos_val, otros_gastos_py_val),
                'resultado': _var(ebitda, ebitda_py),
                'variacion': _var(variacion_val, variacion_py)
            },
            'budget': {
                'ingresos': round(float(bud_ing_val), 2),
                'gastos': round(float(bud_gas_val), 2),
                'ebitda': round(float(bud_ebitda), 2)
            },
            'ratios': {
                'liquidez': round(float(liquidez), 2),
                'margen': round(float((ebitda / (ingresos_val + otros_ingresos_val + variacion_val) * 100) if (ingresos_val + otros_ingresos_val + variacion_val) > 0 else 0), 2),
                'solvencia': round(float(solvencia), 2),
                'endeudamiento': round(float(endeudamiento), 2)
            },
            'ranges': {
                'liquidez': {'min': 0, 'max': 3, 'low': 1.0, 'high': 1.5, 'optimal': 1.8},
                'margen': {'min': 0, 'max': 50, 'low': 5.0, 'high': 15.0, 'optimal': 25.0},
                'solvencia': {'min': 0, 'max': 5, 'low': 1.1, 'high': 1.8, 'optimal': 2.5},
                'endeudamiento': {'min': 0, 'max': 200, 'low': 40.0, 'high': 80.0, 'optimal': 50.0, 'inverse': True}
            }
        }

        self.cache.set(cache_key, data, ttl=3600)
        return data

    def get_ratios_extended(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        fp = compute_mssql_fingerprint()
        cache_key = f"{fp}:fin_ratios_{empresa}_{ejercicio}_v1"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        snapshot = self.get_snapshot(empresa, ejercicio)

        ingresos_val = float(snapshot.get('ingresos', 0.0))
        otros_ingresos_val = float(snapshot.get('otros_ingresos', 0.0))
        gastos_val = float(snapshot.get('gastos', 0.0))
        otros_gastos_val = float(snapshot.get('otros_gastos', 0.0))
        ebitda_val = float(snapshot.get('resultado', 0.0))
        variacion_val = float(snapshot.get('variacion', 0.0))

        activo_corriente = float(self._get_saldo_pattern(empresa, ejercicio, ['3%', '43%', '57%']))
        pasivo_corriente_raw = float(self._get_saldo_pattern(empresa, ejercicio, ['40%', '41%', '52%']))
        pasivo_corriente = abs(pasivo_corriente_raw)
        existencias = float(self._get_saldo_pattern(empresa, ejercicio, ['30%', '31%', '32%', '33%', '34%', '35%', '36%', '37%', '38%', '39%']))
        efectivo = float(self._get_saldo_pattern(empresa, ejercicio, ['57%']))

        activo_total = float(self._get_saldo_pattern(empresa, ejercicio, ['2%', '3%', '43%', '57%']))
        pasivo_total = abs(float(self._get_saldo_pattern(empresa, ejercicio, ['13%', '14%', '15%', '16%', '17%', '40%', '41%', '52%'])))
        patrimonio_neto = abs(float(self._get_saldo_pattern(empresa, ejercicio, ['10%', '11%', '12%'])))

        clientes = float(self._get_saldo_pattern(empresa, ejercicio, ['43%']))
        proveedores = abs(float(self._get_saldo_pattern(empresa, ejercicio, ['40%', '41%'])))

        try:
            depam_val = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, ejercicio=ejercicio, cuenta__startswith='68', periodo__lte=12
            ).aggregate(t=Sum('saldo'))['t'] or 0.0
        except ProgrammingError:
            depam_val = 0.0
        depam_abs = abs(float(depam_val))

        gastos_financieros = float(self._get_saldo_pattern(empresa, ejercicio, ['66%', '67%']))
        gastos_financieros_pos = abs(gastos_financieros)

        ventas_totales = ingresos_val + otros_ingresos_val
        coste_ventas = gastos_val + otros_gastos_val - variacion_val
        existencias_media = abs(existencias)

        def safe_div(num: float, den: float) -> float:
            d = float(den)
            if d == 0.0:
                return 0.0
            return float(num) / d

        liquidez_corriente = safe_div(activo_corriente, pasivo_corriente)
        test_acido = safe_div(activo_corriente - existencias, pasivo_corriente)
        disponibilidad = safe_div(efectivo, pasivo_corriente)
        fondo_maniobra = activo_corriente - pasivo_corriente

        endeudamiento_pct = 0.0
        base_capital = patrimonio_neto + pasivo_total
        if base_capital != 0.0:
            endeudamiento_pct = safe_div(pasivo_total, base_capital) * 100.0

        autonomia = safe_div(patrimonio_neto, pasivo_total)
        garantia = safe_div(activo_total, pasivo_total)
        calidad_deuda = safe_div(pasivo_corriente, pasivo_total)

        rot_activos = safe_div(ventas_totales, abs(activo_total))
        rot_stock = safe_div(coste_ventas, existencias_media)
        periodo_cobro = safe_div(abs(clientes), ventas_totales) * 365.0 if ventas_totales > 0 else 0.0
        base_compras = gastos_val if gastos_val > 0 else coste_ventas
        periodo_pago = safe_div(abs(proveedores), base_compras) * 365.0 if base_compras > 0 else 0.0

        margen_bruto_pct = safe_div(ventas_totales - coste_ventas, ventas_totales) * 100.0 if ventas_totales > 0 else 0.0

        ebit = ebitda_val - depam_abs
        beneficio_neto = ebit - gastos_financieros_pos
        margen_neto_pct = safe_div(beneficio_neto, ventas_totales) * 100.0 if ventas_totales > 0 else 0.0

        roa_pct = safe_div(ebit, abs(activo_total)) * 100.0 if activo_total != 0 else 0.0
        roe_pct = safe_div(beneficio_neto, patrimonio_neto) * 100.0 if patrimonio_neto != 0 else 0.0

        cobertura_interes = safe_div(ebit, gastos_financieros_pos) if gastos_financieros_pos > 0 else 0.0
        cobertura_deuda = 0.0

        margen_ebitda_pct = safe_div(ebitda_val, ventas_totales) * 100.0 if ventas_totales > 0 else 0.0

        base_values = {
            'activo_corriente': round(activo_corriente, 2),
            'pasivo_corriente': round(pasivo_corriente, 2),
            'existencias': round(existencias, 2),
            'efectivo': round(efectivo, 2),
            'activo_total': round(activo_total, 2),
            'pasivo_total': round(pasivo_total, 2),
            'patrimonio_neto': round(patrimonio_neto, 2),
            'clientes': round(clientes, 2),
            'proveedores': round(proveedores, 2),
            'ventas_totales': round(ventas_totales, 2),
            'coste_ventas': round(coste_ventas, 2),
            'ebitda': round(ebitda_val, 2),
            'ebit': round(ebit, 2),
            'beneficio_neto': round(beneficio_neto, 2),
            'gastos_financieros': round(gastos_financieros_pos, 2),
            'variacion_existencias': round(variacion_val, 2),
        }

        ranges_snapshot = snapshot.get('ranges', {})

        def _classify(val: float, cfg: Dict[str, Any], inverse: bool = False) -> Dict[str, Any]:
            if not cfg:
                return {}
            low = float(cfg.get('low') or 0.0)
            high = float(cfg.get('high') or 0.0)
            status = 'target'
            label = 'Zona objetivo'
            if not inverse:
                if val < low:
                    status = 'low'
                    label = 'Por debajo de objetivo'
                elif val > high:
                    status = 'high'
                    label = 'Por encima de objetivo'
            else:
                if val > high:
                    status = 'high'
                    label = 'Por encima de objetivo'
                elif val < low:
                    status = 'low'
                    label = 'Por debajo de objetivo'
            return {'status': status, 'zone_label': label}

        cfg_liq = ranges_snapshot.get('liquidez') or {}
        cfg_margen = ranges_snapshot.get('margen') or {}
        cfg_end = ranges_snapshot.get('endeudamiento') or {}

        ratios = {
            'liquidez_corriente': {
                'value': round(liquidez_corriente, 2),
                'unit': '',
                'category': 'liquidez',
                'available': pasivo_corriente > 0,
                **_classify(liquidez_corriente, cfg_liq, inverse=False),
            },
            'test_acido': {'value': round(test_acido, 2), 'unit': '', 'category': 'liquidez', 'available': pasivo_corriente > 0},
            'disponibilidad': {'value': round(disponibilidad, 2), 'unit': '', 'category': 'liquidez', 'available': pasivo_corriente > 0},
            'fondo_maniobra': {'value': round(fondo_maniobra, 2), 'unit': 'eur', 'category': 'liquidez', 'available': True},
            'endeudamiento': {
                'value': round(endeudamiento_pct, 2),
                'unit': 'percent',
                'category': 'solvencia',
                'available': base_capital != 0.0,
                **_classify(endeudamiento_pct, cfg_end, inverse=bool(cfg_end.get('inverse'))),
            },
            'autonomia': {'value': round(autonomia, 2), 'unit': '', 'category': 'solvencia', 'available': pasivo_total > 0},
            'garantia': {'value': round(garantia, 2), 'unit': '', 'category': 'solvencia', 'available': pasivo_total > 0},
            'calidad_deuda': {'value': round(calidad_deuda * 100.0, 2), 'unit': 'percent', 'category': 'solvencia', 'available': pasivo_total > 0},
            'rotacion_activos': {'value': round(rot_activos, 2), 'unit': '', 'category': 'gestion', 'available': activo_total != 0},
            'rotacion_stock': {'value': round(rot_stock, 2), 'unit': '', 'category': 'gestion', 'available': existencias_media > 0},
            'periodo_cobro': {'value': round(periodo_cobro, 1), 'unit': 'days', 'category': 'gestion', 'available': ventas_totales > 0},
            'periodo_pago': {'value': round(periodo_pago, 1), 'unit': 'days', 'category': 'gestion', 'available': base_compras > 0},
            'margen_bruto': {'value': round(margen_bruto_pct, 2), 'unit': 'percent', 'category': 'rentabilidad', 'available': ventas_totales > 0},
            'margen_neto': {
                'value': round(margen_neto_pct, 2),
                'unit': 'percent',
                'category': 'rentabilidad',
                'available': ventas_totales > 0,
            },
            'roa': {'value': round(roa_pct, 2), 'unit': 'percent', 'category': 'rentabilidad', 'available': activo_total != 0},
            'roe': {'value': round(roe_pct, 2), 'unit': 'percent', 'category': 'rentabilidad', 'available': patrimonio_neto != 0},
            'cobertura_interes': {'value': round(cobertura_interes, 2), 'unit': 'times', 'category': 'cobertura', 'available': gastos_financieros_pos > 0},
            'cobertura_deuda': {'value': round(cobertura_deuda, 2), 'unit': 'times', 'category': 'cobertura', 'available': False},
            'margen_ebitda': {
                'value': round(margen_ebitda_pct, 2),
                'unit': 'percent',
                'category': 'cobertura',
                'available': ventas_totales > 0,
                **_classify(margen_ebitda_pct, cfg_margen, inverse=False),
            },
        }

        result = {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'base': base_values,
            'ratios': ratios,
        }

        self.cache.set(cache_key, result, ttl=3600)
        return result

    def get_pl_detail(self, empresa: int, ejercicio: int, month: int = 0, level: int = 3) -> Dict[str, Any]:
        """
        Returns detailed P&L comparing current month vs SAME month of PREVIOUS year.
        Returns: { 'data': [...], 'meta': { 'period_name': '...', 'year': ..., 'prev_year': ... } }
        """
        from django.db.models import Sum, Q
        
        # Auto-detect last month with data if month is 0
        if not month or month == 0:
            # Find periods with significant P&L activity (more than 10 records in Group 6 or 7)
            # This avoids selecting "partial" periods like Period 11 which only has 6 records.
            qs = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, ejercicio=ejercicio, periodo__lte=12, periodo__gt=0
            )
            
            # Get period counts for P&L accounts
            from django.db.models import Count
            candidates = qs.filter(Q(cuenta__startswith='6') | Q(cuenta__startswith='7')) \
                           .values('periodo') \
                           .annotate(count=Count('id')) \
                           .filter(count__gt=10) \
                           .order_by('-periodo')
            
            last_entry = candidates.first()
            if last_entry:
                month = last_entry['periodo']
            else:
                # Fallback: Just take the max period with ANY data if no "full" period found
                last_any = qs.order_by('-periodo').first()
                month = last_any.periodo if last_any else 1

        # YoY Comparison: Same month, previous year
        prev_year = ejercicio - 1
        
        # Helper to get data grouped by truncated account
        def get_period_data(year, p_idx):
            if p_idx == 0: return {}
            
            qs = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, ejercicio=year, periodo=p_idx
            ).filter(Q(cuenta__startswith='6') | Q(cuenta__startswith='7'))
            
            data = {}
            for row in qs:
                # Truncate account to level
                acc_code = row.cuenta[:level]
                if len(acc_code) < level: continue 

                if acc_code not in data:
                    data[acc_code] = 0.0
                
                # Sign correction for display
                # Group 7 (Income) is usually negative (Haber), make positive
                # Group 6 (Expense) is usually positive (Debe), keep positive
                # Actually in Acumulados: Debe is +, Haber is -. 
                # Sales (700) are usually Credit (-). Display as positive.
                # Expenses (600) are usually Debit (+). Display as positive.
                if row.cuenta.startswith('7'):
                    data[acc_code] += float(row.saldo) * -1
                else:
                    data[acc_code] += float(row.saldo)
            return data

        current_data = get_period_data(ejercicio, month)
        prev_data = get_period_data(prev_year, month) # YoY Comparison
        # Combine keys
        all_keys = set(current_data.keys()) | set(prev_data.keys())
        
        result = []
        for code in sorted(all_keys):
            curr_val = current_data.get(code, 0.0)
            prev_val = prev_data.get(code, 0.0)
            
            # Skip if both zero
            if abs(curr_val) < 0.01 and abs(prev_val) < 0.01:
                continue
                
            desc = self._get_account_desc(empresa, ejercicio, code)
            
            # Variacion
            if prev_val != 0:
                var_pct = ((curr_val - prev_val) / abs(prev_val)) * 100
            else:
                var_pct = 100.0 if curr_val > 0 else 0.0
                
            is_ingreso = code.startswith('7')
            
            result.append({
                'cuenta': code,
                'descripcion': desc,
                'mes_actual': round(curr_val, 2),
                'mes_anterior': round(prev_val, 2),
                'variacion': round(var_pct, 2),
                'is_ingreso': is_ingreso
            })
            
        # Metadata
        month_names = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        period_name = month_names[month] if 1 <= month <= 12 else str(month)
        
        return {
            'data': result,
            'meta': {
                'period_name': period_name,
                'month_index': month,
                'year_current': ejercicio,
                'year_prev': prev_year
            }
        }

    def get_pl_report(self, empresa: int, ejercicio: int, level: int = 3) -> Dict[str, Any]:
        """
        Generates Profit & Loss Report (Cuenta de Resultados) grouped by Analytic Masses.
        Includes Budget Comparison.
        """
        rows_6 = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='6', periodo__gte=1, periodo__lte=12
        ).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))
        
        rows_7 = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='7', periodo__gte=1, periodo__lte=12
        ).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))

        try:
            from datia.models.financial import DatiaPresupuestos
            budgets_6 = list(
                DatiaPresupuestos.objects.filter(
                    empresa=empresa, ejercicio=ejercicio, cuenta__startswith='6'
                ).values('cuenta').annotate(total=Sum('importe'))
            )
            budgets_7 = list(
                DatiaPresupuestos.objects.filter(
                    empresa=empresa, ejercicio=ejercicio, cuenta__startswith='7'
                ).values('cuenta').annotate(total=Sum('importe'))
            )
        except ProgrammingError:
            budgets_6 = []
            budgets_7 = []

        # 2. Helpers
        def prefix_for(code: str, lvl: int) -> str:
            target = 2 if lvl == 2 else (3 if lvl == 3 else 4)
            return code[:target] if code else code

        def get_net_value(row):
            # Calculate Net (Debe - Haber)
            # Group 6 (Debit balance +) -> result is (+).
            # Group 7 (Credit balance -) -> result is (-).
            # We want to normalize to "Positive Magnitude" for display?
            # Or keep Sign?
            # User wants "Ventas", "Consumo".
            # Usually Ventas are displayed Positive. Consumo is displayed Positive (as cost).
            # The Result is Ventas - Consumo.
            # So we will store "Magnitude".
            
            debe = float(row.get('d') or 0.0)
            haber = float(row.get('h') or 0.0)
            net = debe - haber
            
            # If it's a budget row
            if 'total' in row:
                net = float(row['total'] or 0.0)
                
            code = row['cuenta']
            # If Group 7 (Income) -> It is usually Credit (-). We flip to show as Positive Revenue.
            if code.startswith('7'):
                return -net
            # If Group 6 (Expense) -> It is usually Debit (+). We keep as Positive Expense.
            return net

        # 3. Aggregate Data into Dicts
        agg_actual = {}
        agg_budget = {}

        # Merge all into one raw dict first?
        # Better: Accumulate by target level key
        
        # Process Actuals
        total_ingresos = 0.0
        total_gastos = 0.0
        
        for r in list(rows_6) + list(rows_7):
            val = get_net_value(r)
            key = prefix_for(r['cuenta'], level)
            agg_actual[key] = agg_actual.get(key, 0.0) + val
            
            # Global Totals check
            if r['cuenta'].startswith('7'):
                total_ingresos += val
            else:
                total_gastos += val
                
        # Process Budgets
        total_ing_bud = 0.0
        total_gas_bud = 0.0
        
        for r in list(budgets_6) + list(budgets_7):
            val = get_net_value(r)
            key = prefix_for(r['cuenta'], level)
            agg_budget[key] = agg_budget.get(key, 0.0) + val
            
            if r['cuenta'].startswith('7'):
                total_ing_bud += val
            else:
                total_gas_bud += val

        # 4. Define Standard Masses
        # To match user request: "Ventas, Consumo materia primas, Gastos de personal"
        
        PL_MASSES = [
            {'label': 'VENTAS', 'prefixes': ['70']},
            {'label': 'OTROS INGRESOS', 'prefixes': ['72', '73', '74', '75', '76', '77', '78', '79']},
            {'label': 'Variación de existencias', 'prefixes': ['61', '71']},
            {'label': 'COMPRAS Y APROVISIONAMIENTOS', 'prefixes': ['60']},
            {'label': 'GASTOS DE PERSONAL', 'prefixes': ['64']},
            {'label': 'OTROS GASTOS DE EXPLOTACIÓN', 'prefixes': ['62', '63', '65', '69']},
            {'label': 'AMORTIZACIONES Y DETERIOROS', 'prefixes': ['68']},
            {'label': 'RESULTADO FINANCIERO', 'prefixes': ['66', '67']},
        ]

        final_rows = []
        processed_codes = set()

        for mass in PL_MASSES:
            m_label = mass['label']
            m_prefixes = mass['prefixes']
            
            # Find matching codes in our aggregated keys
            # We must be careful not to double count if shallow prefixes overlap (e.g. '7' vs '70')
            # The list order matters. Once a code is processed, we skip it.
            
            match_codes = []
            all_keys = set(agg_actual.keys()) | set(agg_budget.keys())
            
            for code in sorted(all_keys):
                if code in processed_codes:
                    continue
                
                # Check prefix match
                is_match = False
                for p in m_prefixes:
                    if code.startswith(p):
                        is_match = True
                        break
                
                if is_match:
                    match_codes.append(code)
            
            if not match_codes and m_label != 'VENTAS E INGRESOS': 
                # Skip empty masses (except maybe Sales if we want to show it always? No, skip empty)
                continue

            if not match_codes:
                continue

            # Calculate Mass Total
            mass_act = sum(agg_actual.get(c, 0.0) for c in match_codes)
            mass_bud = sum(agg_budget.get(c, 0.0) for c in match_codes)
            
            # Skip Mass if 0 (Optional, but cleaner)
            if abs(mass_act) < 0.01 and abs(mass_bud) < 0.01:
                # Mark as processed nonetheless? Yes
                processed_codes.update(match_codes)
                continue

            # Add Header
            final_rows.append({
                'cuenta': '', # No code for header
                'descripcion': m_label,
                'valor': round(mass_act, 2),
                'presupuesto': round(mass_bud, 2),
                'desviacion': round(mass_act - mass_bud, 2),
                'level': 1,
                'is_header': True,
                'isIngreso': (m_label in ('VENTAS', 'OTROS INGRESOS'))
            })
            
            # Add Children
            for code in match_codes:
                processed_codes.add(code)
                desc = self._get_account_desc(empresa, ejercicio, code)
                act = agg_actual.get(code, 0.0)
                bud = agg_budget.get(code, 0.0)
                
                # Determine display level: Shifted (1 -> 2, 2 -> 3)
                # If code len is 1, it's a Group -> Level 2
                # If code len is 3, Account -> Level 3 or 4
                lvl = (1 if len(code) == 1 else (2 if len(code) == 2 else (3 if len(code) == 3 else 4))) + 1
                
                final_rows.append({
                    'cuenta': code,
                    'descripcion': desc,
                    'valor': round(act, 2),
                    'presupuesto': round(bud, 2),
                    'desviacion': round(act - bud, 2),
                    'level': lvl,
                    'is_header': False,
                    'isIngreso': code.startswith('7')
                })

        # 4. Resultados
        resultado = round(float(total_ingresos - total_gastos), 2)
        resultado_bud = round(float(total_ing_bud - total_gas_bud), 2)

        return {
            'rows': final_rows,
            'total_ingresos': round(float(total_ingresos), 2),
            'total_gastos': round(float(total_gastos), 2),
            'total_ingresos_budget': round(float(total_ing_bud), 2),
            'total_gastos_budget': round(float(total_gas_bud), 2),
            'resultado_explotacion': resultado,
            'resultado_explotacion_budget': resultado_bud,
            'meta': {
                'level': int(level)
            }
        }

    def get_advanced_analysis(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        """
        Generates advanced strategic analysis (Trends, Anomalies, Recommendations).
        """
        # 1. Get Monthly Income Series (Group 7)
        rows_7 = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='7', periodo__lte=12
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        
        monthly_income = [0.0] * 12
        for r in rows_7:
            idx = r['periodo'] - 1
            if 0 <= idx < 12:
                monthly_income[idx] = float(abs(r['total'])) # Force positive for analysis

        # 2. Get Snapshot for KPIs (Margin, Growth)
        # We need Growth PCT, so we might need prev year. 
        # For simplicity, we calculate growth from trend or check prev year if available.
        snapshot = self.get_snapshot(empresa, ejercicio)
        
        # 3. Run Analysis
        anomalies = AnalysisService.detect_anomalies(monthly_income)
        trend = AnalysisService.calculate_trend(monthly_income)
        
        # 4. Generate Recommendations
        # Estimate growth from trend slope relative to mean
        mean_income = sum(monthly_income) / 12 if sum(monthly_income) > 0 else 1
        growth_est = (trend['slope'] * 12) / mean_income * 100
        
        recs = AnalysisService.generate_recommendations({
            'margin': snapshot['ratios']['margen'],
            'growth_pct': growth_est
        }, {'sales_trend': trend})
        
        return {
            'anomalies': anomalies,
            'trend': trend,
            'recommendations': recs,
            'monthly_series': monthly_income
        }

    def get_monthly_kpis(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        rows_inc = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='7', periodo__lte=12
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        rows_exp = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='6', periodo__lte=12
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        rows_dep = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith='68', periodo__lte=12
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        ingresos = [0.0] * 12
        gastos = [0.0] * 12
        depam = [0.0] * 12
        for r in rows_inc:
            idx = r['periodo'] - 1
            if 0 <= idx < 12:
                ingresos[idx] = float(abs(r['total'] or 0))
        for r in rows_exp:
            idx = r['periodo'] - 1
            if 0 <= idx < 12:
                gastos[idx] = float(r['total'] or 0)
        for r in rows_dep:
            idx = r['periodo'] - 1
            if 0 <= idx < 12:
                depam[idx] = float(abs(r['total'] or 0))
        ebitda = [ingresos[i] - gastos[i] + depam[i] for i in range(12)]
        margen_pct = [(ebitda[i] / ingresos[i] * 100) if ingresos[i] > 0 else 0.0 for i in range(12)]
        ingresos = [round(v, 2) for v in ingresos]
        gastos = [round(v, 2) for v in gastos]
        ebitda = [round(v, 2) for v in ebitda]
        margen_pct = [round(v, 2) for v in margen_pct]
        labels = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
        return {
            'labels': labels,
            'ingresos': ingresos,
            'gastos': gastos,
            'ebitda': ebitda,
            'margen_pct': margen_pct
        }

    def list_departments(self) -> List[Dict[str, Any]]:
        """
        Returns available PGC-based areas for filtering (acts as 'departamentos' financieros).
        """
        return [
            {'key': 'todos', 'label': 'Todos'},
            {'key': 'aprovisionamientos', 'label': 'Aprovisionamientos (60-61)'},
            {'key': 'personal', 'label': 'Gastos de Personal (64)'},
            {'key': 'otros_gastos', 'label': 'Otros Gastos de Explotación (62-63-65-69)'},
            {'key': 'ingresos', 'label': 'Ingresos Operativos (7)'}
        ]

    def get_quarterly_report(self, empresa: int, ejercicio: int, departamento: str = None) -> Dict[str, Any]:
        """
        Aggregates financials by quarter (Q1..Q4) for current year and compares with previous year.
        - Ingresos: cuentas grupo 7 (positivo por magnitud)
        - Gastos: cuentas grupo 6 (filtrables por área PGC)
        - Beneficio neto: ingresos - gastos
        - Margen operativo: (beneficio / ingresos) * 100
        - Métricas negocio: ticket medio, operaciones, margen % a partir de MetricsTotalesEmpresaEjercicioMes
        """
        def pgc_filter(area: str):
            if not area or area == 'todos':
                return ['6']
            if area == 'aprovisionamientos':
                return ['60', '61']
            if area == 'personal':
                return ['64']
            if area == 'otros_gastos':
                return ['62', '63', '65', '69']
            if area == 'ingresos':
                return ['7']  # Especial: si se pide 'ingresos', tratamos gastos=0 y sólo ingresos
            return ['6']

        ranges = {
            'Q1': (1, 3),
            'Q2': (4, 6),
            'Q3': (7, 9),
            'Q4': (10, 12)
        }
        prev_year = ejercicio - 1

        def sum_grupo_periodo(year: int, prefixes: List[str], p_from: int, p_to: int, invert_sign_for_7: bool = False) -> float:
            q = Q()
            for pref in prefixes:
                q |= Q(cuenta__startswith=pref)
            val = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, ejercicio=year, periodo__gte=p_from, periodo__lte=p_to
            ).filter(q).aggregate(t=Sum('saldo'))['t'] or 0
            # Grupo 7 suele ser negativo: invertimos a positivo si procede
            if invert_sign_for_7:
                return float(abs(val))
            return float(val)

        def negocio_metrics(year: int, p_from: int, p_to: int) -> Dict[str, Any]:
            rows = MetricsTotalesEmpresaEjercicioMes.objects.filter(
                empresa=empresa, ejercicio=year, mes__gte=p_from, mes__lte=p_to
            ).values('mes').aggregate(
                neto=Sum('importe_neto_total'),
                coste=Sum('importe_coste_total'),
                ops=Sum('albaranes_count')
            )
            neto = float(rows.get('neto') or 0)
            coste = float(rows.get('coste') or 0)
            ops = int(rows.get('ops') or 0)
            ticket = (neto / ops) if ops > 0 else 0.0
            margen_pct = ((neto - coste) / neto * 100) if neto > 0 else 0.0
            return {
                'ticket_medio': round(ticket, 2),
                'operaciones': ops,
                'margen_pct': round(margen_pct, 2)
            }

        area_prefixes = pgc_filter(departamento)
        quarters = []
        comparison = {'prev_year': prev_year, 'quarters': {}, 'prev_values': {'quarters': {}}}

        for q_key, (pf, pt) in ranges.items():
            # Ingresos CY
            ingresos_cy = sum_grupo_periodo(ejercicio, ['7'], pf, pt, invert_sign_for_7=True)
            # Gastos CY (posibles áreas)
            if departamento == 'ingresos':
                gastos_cy = 0.0
            else:
                gastos_cy = sum_grupo_periodo(ejercicio, area_prefixes, pf, pt, invert_sign_for_7=False)
            beneficio_cy = ingresos_cy - gastos_cy
            margen_op_cy = (beneficio_cy / ingresos_cy * 100) if ingresos_cy > 0 else 0.0
            metrics_cy = negocio_metrics(ejercicio, pf, pt)

            # Prev Year
            ingresos_py = sum_grupo_periodo(prev_year, ['7'], pf, pt, invert_sign_for_7=True)
            gastos_py = 0.0 if departamento == 'ingresos' else sum_grupo_periodo(prev_year, area_prefixes, pf, pt, invert_sign_for_7=False)
            beneficio_py = ingresos_py - gastos_py
            margen_op_py = (beneficio_py / ingresos_py * 100) if ingresos_py > 0 else 0.0
            metrics_py = negocio_metrics(prev_year, pf, pt)

            def var_pct(curr, prev):
                if prev and abs(prev) > 0:
                    return ((curr - prev) / abs(prev)) * 100
                return 100.0 if curr != 0 and prev == 0 else 0.0

            quarters.append({
                'quarter': q_key,
                'ingresos': round(ingresos_cy, 2),
                'gastos': round(gastos_cy, 2),
                'beneficio_neto': round(beneficio_cy, 2),
                'margen_operativo': round(margen_op_cy, 2),
                'metrics': metrics_cy
            })
            comparison['quarters'][q_key] = {
                'ingresos_var_pct': round(var_pct(ingresos_cy, ingresos_py), 2),
                'gastos_var_pct': round(var_pct(gastos_cy, gastos_py), 2),
                'beneficio_var_pct': round(var_pct(beneficio_cy, beneficio_py), 2),
                'margen_operativo_diff_pts': round((margen_op_cy - margen_op_py), 2),
                'metrics': {
                    'ticket_medio_diff': round(metrics_cy['ticket_medio'] - metrics_py['ticket_medio'], 2),
                    'operaciones_diff': metrics_cy['operaciones'] - metrics_py['operaciones'],
                    'margen_pct_diff_pts': round(metrics_cy['margen_pct'] - metrics_py['margen_pct'], 2)
                }
            }
            comparison['prev_values']['quarters'][q_key] = {
                'ingresos': round(ingresos_py, 2),
                'gastos': round(gastos_py, 2),
                'beneficio_neto': round(beneficio_py, 2),
                'margen_operativo': round(margen_op_py, 2),
                'metrics': metrics_py
            }

        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'departamento': departamento or 'todos',
            'quarters': quarters,
            'comparison': comparison
        }

    def _get_balance_prefixes(self, root: str) -> List[str]:
        """
        Devuelve la lista unificada de prefijos de cuentas para cada masa patrimonial.
        Asegura coherencia entre Resumen y Detalle.
        """
        if root == 'activo':
            # Activo No Corriente (2) + Activo Corriente (3, 43, 44, 57...) + H.P. Deudora (470-474) + Anticipos (407) + Socios (551) + Fianzas (560) + Inv.Fin.CP (53)
            return ['2%', '3%', '43%', '44%', '45%', '57%', '54%', '55%', '56%', '53%', '460%', '48%', '470%', '471%', '472%', '473%', '474%', '407%']
        elif root == 'pasivo':
            # Pasivo No Corriente + Pasivo Corriente + H.P. Acreedora (475-479) + Anticipos Cli (438) + Remuneraciones (465)
            # Remove 55/56 from here if assigned to Activo (Metodo Neto) OR split by specific codes if deemed necessary.
            # For simplicity in "Netting" approach: If 55 is in Activo, Credit will reduce Activo. 
            # To be strict: 40, 41, 50, 51, 52. 
            # We keep 13 in Pasivo ref? User note said 13 in PN.
            # Updated List:
            return ['14%', '15%', '16%', '17%', '40%', '41%', '50%', '51%', '52%', '465%', '466%', '475%', '476%', '477%', '479%', '49%', '438%']
        elif root == 'patrimonio':
            # Patrimonio Neto (10, 11, 12) + Subvenciones (13 strictly speaking PN in PGC)
            return ['10%', '11%', '12%', '13%', '18%', '19%'] 
        elif root == 'activo_corriente':
             return ['3%', '43%', '44%', '45%', '57%', '54%', '55%', '56%', '53%', '460%', '48%', '470%', '471%', '472%', '473%', '407%']
        elif root == 'activo_no_corriente':
             return ['2%', '474%']
        elif root == 'pasivo_corriente':
             return ['40%', '41%', '50%', '51%', '52%', '465%', '466%', '475%', '476%', '477%', '479%', '49%', '438%']
        elif root == 'pasivo_no_corriente':
             return ['14%', '15%', '16%', '17%']
             
        return []

    def get_balance_summary(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        has_acumulados = DatiaAcumuladosConta.objects.filter(empresa=empresa, ejercicio=ejercicio, periodo__lte=12).exists()
        
        # Use Shared Definitions
        p_ac = self._get_balance_prefixes('activo_corriente')
        p_anc = self._get_balance_prefixes('activo_no_corriente')
        p_pc = self._get_balance_prefixes('pasivo_corriente')
        p_pnc = self._get_balance_prefixes('pasivo_no_corriente')
        p_pn = self._get_balance_prefixes('patrimonio')
        
        # --- CÁLCULOS ---
        
        # 1. Saldos Patrimoniales
        activo_corriente = self._get_saldo_pattern(empresa, ejercicio, p_ac)
        activo_no_corriente = self._get_saldo_pattern(empresa, ejercicio, p_anc)
        
        pasivo_corriente_raw = self._get_saldo_pattern(empresa, ejercicio, p_pc)
        pasivo_no_corriente_raw = self._get_saldo_pattern(empresa, ejercicio, p_pnc)
        patrimonio_raw = self._get_saldo_pattern(empresa, ejercicio, p_pn)
        
        # Invertir Signos (Pasivo y Patrimonio suelen venir en negativo/Haber)
        pasivo_corriente = abs(pasivo_corriente_raw)
        pasivo_no_corriente = abs(pasivo_no_corriente_raw)
        patrimonio_base = abs(patrimonio_raw) # Fondos propios acumulados y subvenciones
        
        # 2. Resultado del Ejercicio (Activo - Pasivo dinámico de la cuenta 6 y 7)
        # Suma de Grupo 6 (Gastos, Debe +) y Grupo 7 (Ingresos, Haber -).
        # El saldo neto (6+7) es el Resultado. 
        # Si Gastos > Ingresos (100 - 150 = -50) -> Ganancia (Haber neto). Ojo al signo.
        # Check _get_pl_report logic.
        # Ingresos (7) -> suelen ser Saldo Acreedor (Negativo en DB o Positivo en haber).
        # Gastos (6) -> Saldo Deudor (Positivo en DB).
        # Saldo Cuenta Explotación = Sum(6) + Sum(7).
        # Ejemplo: Ventas -1000, Compras 800. Saldo = -200 (Acreedor -> Beneficio).
        # Ejemplo: Ventas -1000, Compras 1200. Saldo = +200 (Deudor -> Pérdida).
        
        # REGLA PGC: El Resultado se suma al Patrimonio.
        # Si hay Beneficio (-200), incrementa el Patrimonio (que es Acreedor -). 
        # -10000 (Capital) + (-200) Result = -10200. ABS -> 10200.
        # Si hay Pérdida (+200), decrementa.
        # -10000 (Capital) + 200 Result = -9800. ABS -> 9800.
        
        # Por tanto, simplemente sumamos al acumulador de patrimonio con su signo original.
        # PERO `patrimonio_base` ya lo hemos hecho ABS.
        # Vamos a trabajar con SIGNOS ORIGINALES para la ecuación, luego ABS para display.
        
        raw_ac = activo_corriente
        raw_anc = activo_no_corriente
        raw_pc = pasivo_corriente_raw # Negative likely
        raw_pnc = pasivo_no_corriente_raw # Negative likely
        raw_pn_base = patrimonio_raw # Negative likely
        
        raw_result = self._get_saldo_pattern(empresa, ejercicio, ['6%', '7%'])
        
        # Total Equity with Result
        # Check if 129 is already in raw_pn_base? Usually 129 is booked at close.
        # If open year, 129 is 0.
        # Safe to add raw_result.
        
        raw_total_pn = raw_pn_base + raw_result
        
        # Display Values (Magnitudes)
        # Assets are Debit (+)
        activo_total = float(raw_ac) + float(raw_anc)
        
        # Liabilities/Equity are Credit (-) -> Convert to abs for UI
        # But wait, if result is Loss (+200), Equity reduces (-10000 + 200 = -9800). Abs is 9800. Correct.
        
        final_pn = float(abs(raw_total_pn))
        final_pc = float(abs(raw_pc))
        final_pnc = float(abs(raw_pnc))
        
        pasivo_total = final_pc + final_pnc
        
        # Ratios
        liquidez = (float(raw_ac) / final_pc) if final_pc else 0.0
        solvencia = (float(activo_total) / pasivo_total) if pasivo_total else 0.0
        # Endeudamiento: Pasivo / PN
        endeudamiento = ((pasivo_total / final_pn) * 100.0) if final_pn else 0.0
        
        # Ecuación Fundamental: A = P + N
        # Diff = Activo - (Pasivo + Neto)
        balance_eq_diff = float(activo_total - (pasivo_total + final_pn))
        
        # [Manual Fix requested by User]: Invert sign of result diff
        balance_eq_diff = -balance_eq_diff
        
        # Tolerancia visual (centimos)
        if abs(balance_eq_diff) < 1.0:
            balance_eq_diff = 0.0

        # Resultado de explotación según snapshot oficial (para alinear con Cuenta de Resultados)
        try:
            snap = self.get_snapshot(empresa, ejercicio)
            resultado_explotacion = float(snap.get('resultado', 0.0))
        except Exception:
            resultado_explotacion = 0.0

        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'status': ('ok' if has_acumulados else 'no_data'),
            'reason': ('' if has_acumulados else 'Sin datos contables'),
            'totales': {
                'activo': round(activo_total, 2),
                'pasivo': round(pasivo_total, 2),
                'patrimonio': round(float(final_pn), 2)
            },
            'resultado_explotacion': round(float(resultado_explotacion), 2),
            'desglose': {
                'activo': {
                    'corriente': round(float(raw_ac), 2),
                    'no_corriente': round(float(raw_anc), 2)
                },
                'pasivo': {
                    'corriente': round(float(final_pc), 2),
                    'no_corriente': round(float(final_pnc), 2)
                }
            },
            'ratios': {
                'liquidez': round(float(liquidez), 2),
                'solvencia': round(float(solvencia), 2),
                'endeudamiento': round(float(endeudamiento), 2)
            },
            'balance_eq_diff': round(balance_eq_diff, 2)
        }

    def get_balance_tree(self, empresa: int, ejercicio: int, root: str = 'activo', start_level: int = 3, end_level: int = 6) -> Dict[str, Any]:
        from django.db.models import Q
        if root == 'activo':
            prefixes = ['2', '3', '43', '57']
            invert_for = []
        elif root == 'pasivo':
            prefixes = ['13', '14', '15', '16', '17', '40', '41', '52']
            invert_for = prefixes
        else:
            prefixes = ['10', '11', '12']
            invert_for = prefixes
        q = Q()
        for p in prefixes:
            q |= Q(cuenta__startswith=p)
        rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12
        ).filter(q).values('cuenta').annotate(total=Sum('saldo'))
        amounts = {}
        for r in rows:
            code = r['cuenta']
            val = float(r['total'] or 0)
            if any(code.startswith(k) for k in invert_for):
                val = abs(val)
            else:
                val = abs(val)
            amounts[code] = amounts.get(code, 0.0) + val
        q_plan = Q()
        for p in prefixes:
            q_plan |= Q(codigo__startswith=p)
        plan = DatiaPlanCuentas.objects.filter(
            q_plan, empresa=empresa, ejercicio=ejercicio, nivel__gte=start_level, nivel__lte=end_level
        ).values('codigo', 'descripcion', 'nivel').order_by('nivel', 'codigo')
        plan_map = {p['codigo']: {'code': p['codigo'], 'name': p['descripcion'], 'level': p['nivel']} for p in plan}
        def sum_for_prefix(prefix: str) -> float:
            s = 0.0
            for c, v in amounts.items():
                if c.startswith(prefix):
                    s += v
            return s
        nodes = {}
        for code, meta in plan_map.items():
            amt = sum_for_prefix(code)
            nodes[code] = {
                'code': code,
                'name': meta['name'],
                'level': meta['level'],
                'amount': amt,
                'parent_code': None,
                'children': []
            }
        codes_sorted = sorted(nodes.keys(), key=lambda x: (nodes[x]['level'], len(x)))
        for code in codes_sorted:
            level = nodes[code]['level']
            if level > start_level:
                parent = None
                for i in range(len(code) - 1, 0, -1):
                    pref = code[:i]
                    if pref in nodes and nodes[pref]['level'] < level:
                        parent = pref
                        break
                if parent:
                    nodes[code]['parent_code'] = parent
                    nodes[parent]['children'].append(code)
        roots = [n for n in nodes.values() if n['level'] == start_level]
        tree = []
        def build_subtree(code: str) -> Dict[str, Any]:
            n = nodes[code]
            return {
                'code': n['code'],
                'name': n['name'],
                'level': n['level'],
                'amount': n['amount'],
                'parent_code': n['parent_code'],
                'children': [build_subtree(ch) for ch in n['children']]
            }
        for r in roots:
            tree.append(build_subtree(r['code']))
        total = sum(n['amount'] for n in roots)
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'root': root,
            'start_level': start_level,
            'end_level': end_level,
            'total': total,
            'nodes': tree,
            'status': ('ok' if (len(tree) > 0 and total > 0) else 'no_data'),
            'reason': ('' if (len(tree) > 0 and total > 0) else 'Plan de cuentas vacío o importes cero')
        }

    def get_balance_table(self, empresa: int, ejercicio: int, root: str = 'activo', start_level: int = 3, end_level: int = 6, order: str = 'amount_desc') -> Dict[str, Any]:
        """
        Returns a flat list of balance items with hierarchy.
        Ensures parent groups (Level 1, 2...) are included if children have data, even if missing from Plan.
        """
        from django.db.models import Q, Sum
        
        # 1. Define Prefixes using Shared Logic
        # Root here comes as 'activo', 'pasivo', 'patrimonio'.
        if root == 'activo':
            prefixes = self._get_balance_prefixes('activo_corriente') + self._get_balance_prefixes('activo_no_corriente')
        elif root == 'pasivo':
            prefixes = self._get_balance_prefixes('pasivo_corriente') + self._get_balance_prefixes('pasivo_no_corriente')
        else:
            prefixes = self._get_balance_prefixes('patrimonio')
            
        prefixes = list(set(prefixes))
        
        invert_val = False
        if root in ['pasivo', 'patrimonio']:
            invert_val = True

        # 2. Get Raw Balances (Acumulados)
        q = Q()
        for p in prefixes:
            clean_p = p.replace('%', '')
            q |= Q(cuenta__startswith=clean_p)
            
        rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12
        ).filter(q).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))
        
        # Map: Account Code -> Amount
        amounts = {}
        for r in rows:
            code = r['cuenta']
            val = float((r['d'] or 0) - (r['h'] or 0))
            if invert_val:
                val = -val # Convert Credit balance (-) to Positive UI Magnitude
            amounts[code] = amounts.get(code, 0.0) + val

        # Prev Year
        prev_year = ejercicio - 1
        rows_prev = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=prev_year, periodo__lte=12
        ).filter(q).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))
        
        amounts_prev = {}
        for r in rows_prev:
            code = r['cuenta']
            val = float((r['d'] or 0) - (r['h'] or 0))
            if invert_val:
                val = -val
            amounts_prev[code] = amounts_prev.get(code, 0.0) + val

        # 3. Identify all necessary codes to display (Accounts + Parents)
        relevant_codes = set()
        
        # Add all actual accounts with balance
        # Filter by start_level/end_level is applied at output, but we need parents.
        for code in set(amounts.keys()) | set(amounts_prev.keys()):
            # Logic: If we have account 5720001 (Level 7), we need headers for:
            # 5 (L1), 57 (L2), 572 (L3), 5720 (L4)... down to end_level
            # We iterate length.
            length = len(code)
            
            # Add parents up to specific levels
            for i in range(1, length + 1):
                sub = code[:i]
                # Only include if within valid PGC ranges (roughly) and within requested levels
                if i >= start_level and i <= end_level:
                    relevant_codes.add(sub)

        # 4. Fetch Descriptions (Plan and Groups)
        # We fetch all relevant codes from Plan first
        plan_map = {}
        if relevant_codes:
            plans = DatiaPlanCuentas.objects.filter(
                empresa=empresa, ejercicio=ejercicio, codigo__in=list(relevant_codes)
            ).values('codigo', 'descripcion')
            for p in plans:
                plan_map[p['codigo']] = p['descripcion']
                
            # For missing descriptions (especially Groups), check DatiaGrupos
            missing = [c for c in relevant_codes if c not in plan_map]
            if missing:
                # First check company specific groups
                grps = DatiaGrupos.objects.filter(
                    empresa=empresa, ejercicio=ejercicio, codigo__in=missing
                ).values('codigo', 'descripcion')
                for g in grps:
                    plan_map[g['codigo']] = g['descripcion']
                
                # Still missing? Check generic/historical DatiaGrupos
                still_missing = [c for c in missing if c not in plan_map]
                if still_missing:
                     grps_generic = DatiaGrupos.objects.filter(
                        codigo__in=still_missing
                     ).order_by('codigo', '-ejercicio').distinct('codigo').values('codigo', 'descripcion')
                     # Django distinct('codigo') only works on Postgres. 
                     # Fallback simple filter and loop
                     grps_generic = DatiaGrupos.objects.filter(codigo__in=still_missing).values('codigo', 'descripcion')
                     for g in grps_generic:
                         if g['codigo'] not in plan_map: # Take first found
                             plan_map[g['codigo']] = g['descripcion']
            
            # [FIX] Enforce Standard PGC Descriptions for Level 1 to avoid "101 BAR" kind of errors
            PGC_STD_MAP = {
                '1': 'Financiación Básica',
                '2': 'Inmovilizado', # Fixed from user report ("101 BAR") to "Inmovilizado" or "Activo No Corriente" depending on context, but Group 2 is usually Inmovilizado in Plan
                '3': 'Existencias',
                '4': 'Acreedores y Deudores por Operaciones Comerciales',
                '5': 'Cuentas Financieras',
                '6': 'Compras y Gastos',
                '7': 'Ventas e Ingresos',
                '8': 'Gastos imputados al patrimonio neto',
                '9': 'Ingresos imputados al patrimonio neto'
            }
            for code, desc in PGC_STD_MAP.items():
                if code in relevant_codes:
                     plan_map[code] = desc

        # 5. Build Final List with Groups (Masses)
        final_rows = []
        
        # Define Masses structure based on Root
        masses = []
        if root == 'activo':
            masses = [
                {'label': 'ACTIVO NO CORRIENTE', 'key': 'activo_no_corriente'},
                {'label': 'ACTIVO CORRIENTE', 'key': 'activo_corriente'}
            ]
        elif root == 'pasivo':
            # Usually Pasivo + PN if just "Pasivo" requested
            masses = [
                {'label': 'PATRIMONIO NETO', 'key': 'patrimonio'},
                {'label': 'PASIVO NO CORRIENTE', 'key': 'pasivo_no_corriente'},
                {'label': 'PASIVO CORRIENTE', 'key': 'pasivo_corriente'}
            ]
        elif root == 'patrimonio':
            masses = [
                {'label': 'PATRIMONIO NETO', 'key': 'patrimonio'}
            ]
        
        # Helper to check if code belongs to mass
        def match_mass(c, prefixes):
            for p in prefixes:
                clean = p.replace('%', '')
                if c.startswith(clean):
                    return True
            return False
            
        def get_var_pct(curr, prev):
            if prev == 0:
                return 100.0 if curr > 0 else 0.0
            return ((curr - prev) / abs(prev)) * 100.0

        # Helpers for sums (Restored)
        def get_recursive_amount(prefix, source_dict):
            total = 0.0
            for c, v in source_dict.items():
                if c.startswith(prefix):
                    total += v
            return total

        # Build Rows per Mass
        for m in masses:
            m_key = m['key']
            m_label = m['label']
            m_prefixes = self._get_balance_prefixes(m_key)
            
            # Filter codes for this mass
            mass_codes = [c for c in relevant_codes if match_mass(c, m_prefixes)]
            
            # Use recursive sum for mass headers too (safer than Pattern sometimes, or consistent)
            # Actually pattern should be consistent. Let's keep Pattern for Mass Header.
            m_curr = self._get_saldo_pattern(empresa, ejercicio, m_prefixes)
            m_prev = self._get_saldo_pattern(empresa, ejercicio - 1, m_prefixes)
            
            if invert_val:
                m_curr = abs(m_curr)
                m_prev = abs(m_prev)
            
            # Condition to show Mass: if it has value OR has children codes
            has_value = abs(m_curr) > 0.01 or abs(m_prev) > 0.01
            if not has_value and not mass_codes:
                continue
                
            # Add Mass Header (Level 1)
            final_rows.append({
                'code': '', # Empty code to avoid Repetition in UI (User Req)
                'description': m_label,
                'amount': float(m_curr),
                'prev_amount': float(m_prev),
                'var_pct': round(get_var_pct(m_curr, m_prev), 2),
                'level': 1, # Top Level
                'is_header': True
            })
            
            # Process Children
            sorted_codes = sorted(mass_codes)
            
            for code in sorted_codes:
                # Level Shift: 1 -> 2
                display_level = (len(code) if len(code) > 1 else 1) + 1
                
                # Fetch Calculated Amount (Recursive)
                curr = get_recursive_amount(code, amounts)
                prev = get_recursive_amount(code, amounts_prev)
                
                # Filter empty rows (Parents with no children value)
                if abs(curr) <= 0.01 and abs(prev) <= 0.01:
                    continue
                
                desc = plan_map.get(code, f"Grupo {code}" if len(code) < 4 else "Sin Descripción")
                if desc == "Sin Descripción" and len(code) <= 2:
                     PGC_STD_MAP = {
                         '1': 'FINANCIACIÓN BÁSICA', '2': 'INMOVILIZADO', '3': 'EXISTENCIAS', 
                         '4': 'ACREEDORES Y DEUDORES', '5': 'CUENTAS FINANCIERAS',
                         '6': 'COMPRAS Y GASTOS', '7': 'VENTAS E INGRESOS',
                         '10': 'CAPITAL', '11': 'RESERVAS', '12': 'RESULTADOS PENDIENTES',
                         '57': 'TESORERÍA', '43': 'CLIENTES', '40': 'PROVEEDORES', '41': 'ACREEDORES VARIOS',
                         '20': 'INMOVILIZADO INTANGIBLE', '21': 'INMOVILIZADO MATERIAL'
                     }
                     if code in PGC_STD_MAP:
                         desc = PGC_STD_MAP[code]
                
                final_rows.append({
                    'code': code,
                    'description': desc.upper() if len(code) <= 2 else desc, # Styling tweak
                    'amount': float(curr),
                    'prev_amount': float(prev),
                    'var_pct': round(get_var_pct(curr, prev), 2),
                    'level': display_level,
                    'is_header': False
                })

        # Calculate Totals for Response Metadata
        total_curr = sum(r['amount'] for r in final_rows if r.get('level') == 1)
        total_prev = sum(r['prev_amount'] for r in final_rows if r.get('level') == 1)

        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'root': root,
            'start_level': start_level,
            'end_level': end_level,
            'total': float(total_curr),
            'total_prev': float(total_prev),
            'rows': final_rows,
            'status': ('ok' if final_rows else 'no_data'),
            'reason': ('' if final_rows else 'Sin datos')
        }

    # --- BUDGET MANAGEMENT ---

    def save_budget_row(self, empresa: int, ejercicio: int, cuenta: str, month: int, value: float):
        """
        Saves a single budget cell.
        """
        from datia.models.financial import DatiaPresupuestos
        DatiaPresupuestos.objects.update_or_create(
            empresa=empresa,
            ejercicio=ejercicio,
            cuenta=cuenta,
            periodo=month,
            defaults={'importe': value}
        )

    def generate_initial_budget(self, empresa: int, ejercicio: int, base_year: int, increment_pct: float):
        """
        Generates a draft budget based on previous year actuals + increment %.
        """
        from datia.models.financial import DatiaPresupuestos
        
        # 1. Fetch Actuals from Base Year
        actuals = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=base_year, periodo__lte=12
        ).filter(Q(cuenta__startswith='6') | Q(cuenta__startswith='7'))
        
        factor = 1.0 + (increment_pct / 100.0)
        
        count = 0
        for item in actuals:
            # Calculate Target
            # Acumulados stores 'saldo'. 
            # Income (7) is usually Negative (Haber). Expense (6) Positive.
            # We want to store Magnitude in Budget? Or Signed?
            # Keeping Signed makes math easier (comparison).
            # But UI usually usually wants positive numbers for "Sales Budget".
            # Decision: Store as POSITIVE MAGNITUDE for 7s if we want user to input "1000" instead of "-1000".
            # BUT consistency with Acumulados is safer.
            # Let's check Reporting Logic. It handles signs.
            # IMPT: `Actualidad Financiera` UI expects POSITIVE values for everything usually (Ingresos, Gastos).
            # The API converts signs.
            # Let's store SIGNED in DB (System of Record) matching Acumulados logic.
            # WAIT. If user types "1,000" in grid for Sales, they mean 1,000 Revenue.
            # If we store it as 1,000, and Acumulados has -1,000... variance will be 2,000!
            # We must be careful.
            # "Ingresos" accounts (7) in Acumulados are CREDIT (-). 
            # In Budget UI, user sees positive. 
            # We should probably Invert logical sign for 7s when reading/writing from UI service.
            # Let's assume THIS Service handles the "Business Logic".
            # So: UI sends Positive. Service converts to DB Sign.
            # For Generation: Base is Signed. Factor applies to Signed. 
            # e.g. -1000 * 1.05 = -1050. Correct.
            
            new_val = float(item.saldo) * factor
            
            DatiaPresupuestos.objects.update_or_create(
                empresa=empresa,
                ejercicio=ejercicio,
                cuenta=item.cuenta,
                periodo=item.periodo,
                defaults={'importe': new_val}
            )
            count += 1
            
        return count



    def get_accounts_tree(self, empresa: int, ejercicio: int, root: str = 'ingresos', start_level: int = 3, end_level: int = 6) -> Dict[str, Any]:
        root_prefix = '7' if root == 'ingresos' else '6'
        rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith=root_prefix
        ).values('cuenta').annotate(total=Sum('saldo'))
        amounts = {}
        for r in rows:
            code = r['cuenta']
            val = float(r['total'] or 0)
            if code.startswith('7'):
                val = abs(val)
            amounts[code] = amounts.get(code, 0.0) + val
        plan = DatiaPlanCuentas.objects.filter(
            empresa=empresa, ejercicio=ejercicio, codigo__startswith=root_prefix, nivel__gte=start_level, nivel__lte=end_level
        ).values('codigo', 'descripcion', 'nivel').order_by('nivel', 'codigo')
        plan_map = {p['codigo']: {'code': p['codigo'], 'name': p['descripcion'], 'level': p['nivel']} for p in plan}
        prefix_len = int(start_level)
        group_candidates = set()
        for c in amounts.keys():
            if c.startswith(root_prefix) and len(c) >= prefix_len:
                group_candidates.add(c[:prefix_len])
        grp_map = {}
        grps = DatiaGrupos.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo__in=list(group_candidates)).values('codigo', 'descripcion')
        for g in grps:
            grp_map[g['codigo']] = g['descripcion']
        missing_grp = [code for code in group_candidates if code not in grp_map]
        if missing_grp:
            grps2 = DatiaGrupos.objects.filter(empresa=empresa, codigo__in=missing_grp).values('codigo', 'descripcion')
            for g in grps2:
                if g['codigo'] not in grp_map:
                    grp_map[g['codigo']] = g['descripcion']
        for code, meta in plan_map.items():
            if int(meta['level']) == int(start_level) and code in grp_map:
                meta['name'] = grp_map.get(code, meta['name'])
        for gc in group_candidates:
            if gc not in plan_map:
                plan_map[gc] = {'code': gc, 'name': grp_map.get(gc, gc), 'level': int(start_level)}
        def sum_for_prefix(prefix: str) -> float:
            s = 0.0
            for c, v in amounts.items():
                if c.startswith(prefix):
                    s += v
            return s
        nodes = {}
        for code, meta in plan_map.items():
            amt = sum_for_prefix(code)
            nodes[code] = {
                'code': code,
                'name': meta['name'],
                'level': meta['level'],
                'amount': amt,
                'parent_code': None,
                'children': []
            }
        codes_sorted = sorted(nodes.keys(), key=lambda x: (nodes[x]['level'], len(x)))
        for code in codes_sorted:
            level = nodes[code]['level']
            if level > start_level:
                parent = None
                for i in range(len(code) - 1, 0, -1):
                    pref = code[:i]
                    if pref in nodes and nodes[pref]['level'] < level:
                        parent = pref
                        break
                if parent:
                    nodes[code]['parent_code'] = parent
                    nodes[parent]['children'].append(code)
        roots = [n for n in nodes.values() if n['level'] == start_level]
        tree = []
        def build_subtree(code: str) -> Dict[str, Any]:
            n = nodes[code]
            return {
                'code': n['code'],
                'name': n['name'],
                'level': n['level'],
                'amount': n['amount'],
                'parent_code': n['parent_code'],
                'children': [build_subtree(ch) for ch in n['children']]
            }
        for r in roots:
            tree.append(build_subtree(r['code']))
        total = sum(n['amount'] for n in roots)
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'root': root,
            'start_level': start_level,
            'end_level': end_level,
            'total': total,
            'nodes': tree
        }

    def get_account_detail(self, empresa: int, ejercicio: int, code: str) -> Dict[str, Any]:
        plan = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo=code).first()
        name = plan.descripcion if plan else code
        vals = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith=code
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        monthly = [0.0] * 12
        for r in vals:
            idx = r['periodo'] - 1
            val = float(r['total'] or 0)
            if code.startswith('7'):
                val = abs(val)
            if 0 <= idx < 12:
                monthly[idx] = val
        total = sum(monthly)
        return {
            'code': code,
            'name': name,
            'monthly': monthly,
            'total': total
        }

    def get_account_breakdown(self, empresa: int, ejercicio: int, code: str) -> Dict[str, Any]:
        """
        Returns deepest-level breakdown (max granularity) under a given account prefix.
        Aggregates saldo across periodos 1..12 and lists child accounts with their description.
        """
        from django.db.models import Sum
        prefix = ''.join(ch for ch in str(code) if ch.isdigit())
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith=prefix
        ).values('cuenta').annotate(total=Sum('saldo')).order_by('cuenta')
        rows = []
        base_len = len(prefix)
        for r in qs:
            c = str(r['cuenta'])
            if len(c) <= base_len:
                continue
            val = float(r['total'] or 0)
            # Show magnitudes as positive for readability
            val = abs(val)
            desc = self._get_account_desc(empresa, ejercicio, c)
            rows.append({'cuenta': c, 'descripcion': desc, 'valor': round(val, 2)})
        rows.sort(key=lambda x: x['cuenta'])
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'code': prefix,
            'name': self._get_account_desc(empresa, ejercicio, prefix),
            'rows': rows
        }

    def _get_saldo_grupo(self, empresa, ejercicio, grupo_prefix):
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa,
            ejercicio=ejercicio,
            cuenta__startswith=grupo_prefix,
            periodo__gte=1,
            periodo__lte=12
        )
        val = qs.aggregate(t=Sum('saldo'))['t']
        return val or 0

    def _get_saldo_pattern(self, empresa, ejercicio, patterns):
        # Calculation: Sum(Debe) - Sum(Haber)
        total = 0
        from django.db.models import Q, Sum
        q = Q()
        for p in patterns:
            clean_p = p.replace('%', '')
            q |= Q(cuenta__startswith=clean_p)
            
        qs = DatiaAcumuladosConta.objects.filter(
            q, empresa=empresa, ejercicio=ejercicio, periodo__lte=12
        )
        res = qs.aggregate(d=Sum('debe'), h=Sum('haber'))
        debe = res['d'] or 0
        haber = res['h'] or 0
        return float(debe - haber)

    def _get_account_desc(self, empresa, ejercicio, cuenta):
        try:
            obj = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo=cuenta).first()
            if obj:
                return obj.descripcion
            if len(cuenta) <= 4:
                grp = DatiaGrupos.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo=cuenta).first()
                if not grp:
                     grp = DatiaGrupos.objects.filter(empresa=empresa, codigo=cuenta).order_by('-ejercicio').first()
                if grp:
                    return grp.descripcion
            for i in range(len(cuenta) - 1, 0, -1):
                parent_code = cuenta[:i]
                obj = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo=parent_code).first()
                if obj:
                    return f"{obj.descripcion} (Genérica)"
            obj = DatiaPlanCuentas.objects.filter(empresa=empresa, codigo=cuenta).first()
            if obj:
                return obj.descripcion
            for i in range(len(cuenta) - 1, 0, -1):
                parent_code = cuenta[:i]
                obj = DatiaPlanCuentas.objects.filter(empresa=empresa, codigo=parent_code).first()
                if obj:
                    return f"{obj.descripcion} (Genérica)"
            from datia.services.etl_service import ETLService
            if len(cuenta) > 3:
                key = f"acct_desc_mssql_{empresa}_{cuenta}"
                cached = self.cache.get(key)
                if cached:
                    return cached
                etl = ETLService()
                conn = etl.get_connection()
                cursor = conn.cursor()
                cands = etl.get_table_candidates(cursor, 'plan_cuentas')
                tab, colmap = etl.pick_best_table(cursor, cands, etl.COLUMN_MAP_PLAN_CUENTAS, ['codigo', 'descripcion'])
                if tab and ('codigo' in colmap):
                    def gen_candidates(code: str):
                        s = ''.join(ch for ch in str(code) if ch.isdigit())
                        yield s
                        yield s.rstrip('0')
                        for L in range(len(s), 3, -1):
                            yield s[:L]
                    found = None
                    tried = set()
                    for cand in gen_candidates(cuenta):
                        if not cand or cand in tried:
                            continue
                        tried.add(cand)
                        if 'descripcion' in colmap:
                            sql = f"SELECT TOP 1 T.{colmap['descripcion']} FROM {tab} T WHERE T.{colmap['codigo']} = ?"
                            params = [cand]
                            if 'empresa' in colmap and empresa:
                                try:
                                    sql_emp = sql + f" AND T.{colmap['empresa']} = ?"
                                    cursor.execute(sql_emp, tuple(params + [empresa]))
                                    row = cursor.fetchone()
                                    if row and row[0]:
                                        found = str(row[0]).strip()
                                        break
                                except:
                                    pass
                            try:
                                cursor.execute(sql, tuple(params))
                                row = cursor.fetchone()
                                if row and row[0]:
                                    found = str(row[0]).strip()
                                    break
                            except:
                                pass
                            sql_like = f"SELECT TOP 1 T.{colmap['descripcion']} FROM {tab} T WHERE T.{colmap['codigo']} LIKE ?"
                            like_param = cand + '%'
                            try:
                                if 'empresa' in colmap and empresa:
                                    sql_emp_like = sql_like + f" AND T.{colmap['empresa']} = ?"
                                    cursor.execute(sql_emp_like, (like_param, empresa))
                                    row = cursor.fetchone()
                                    if row and row[0]:
                                        found = str(row[0]).strip()
                                        break
                                cursor.execute(sql_like, (like_param,))
                                row = cursor.fetchone()
                                if row and row[0]:
                                    found = str(row[0]).strip()
                                    break
                            except:
                                pass
                        else:
                            sql2 = f"SELECT TOP 1 T.{colmap['codigo']} FROM {tab} T WHERE T.{colmap['codigo']} = ?"
                            params2 = [cand]
                            if 'empresa' in colmap and empresa:
                                try:
                                    sql2_emp = sql2 + f" AND T.{colmap['empresa']} = ?"
                                    cursor.execute(sql2_emp, tuple(params2 + [empresa]))
                                    row = cursor.fetchone()
                                    if row and row[0]:
                                        val = str(row[0]).strip()
                                        if any(ch.isalpha() for ch in val):
                                            found = val
                                            break
                                except:
                                    pass
                            try:
                                cursor.execute(sql2, tuple(params2))
                                row = cursor.fetchone()
                                if row and row[0]:
                                    val = str(row[0]).strip()
                                    if any(ch.isalpha() for ch in val):
                                        found = val
                                        break
                            except:
                                pass
                            sql2_like = f"SELECT TOP 1 T.{colmap['codigo']} FROM {tab} T WHERE T.{colmap['codigo']} LIKE ?"
                            like_param2 = cand + '%'
                            try:
                                if 'empresa' in colmap and empresa:
                                    sql2_emp_like = sql2_like + f" AND T.{colmap['empresa']} = ?"
                                    cursor.execute(sql2_emp_like, (like_param2, empresa))
                                    row = cursor.fetchone()
                                    if row and row[0]:
                                        val = str(row[0]).strip()
                                        if any(ch.isalpha() for ch in val):
                                            found = val
                                            break
                                cursor.execute(sql2_like, (like_param2,))
                                row = cursor.fetchone()
                                if row and row[0]:
                                    val = str(row[0]).strip()
                                    if any(ch.isalpha() for ch in val):
                                        found = val
                                        break
                            except:
                                pass
                    if found:
                        self.cache.set(key, found, ttl=3600)
                        conn.close()
                        return found
                conn.close()
            if len(cuenta) <= 3:
                return f"Grupo {cuenta}"
            return "Sin Descripción"
        except:
            return "Error"

    def generate_initial_budget_generator(self, empresa: int, ejercicio: int, base_year: int, increment_pct: float):
        from datia.models.financial import DatiaPresupuestos, DatiaAcumuladosConta
        from django.db.models import Sum
        try:
            q_del = DatiaPresupuestos.objects.filter(empresa=empresa, ejercicio=ejercicio, cuenta__regex=r'^[67]')
            deleted = q_del.delete()[0]
            yield {'step': 'clean', 'deleted': int(deleted)}
            actuals = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, ejercicio=base_year, periodo__lte=12, cuenta__regex=r'^[67]'
            ).values('cuenta', 'periodo').annotate(total=Sum('saldo'))
            total = actuals.count()
            yield {'step': 'prepare', 'total': int(total)}
            multiplier = 1.0 + (increment_pct / 100.0)
            processed = 0
            batch = []
            for row in actuals:
                code = row['cuenta']
                amount = float(row['total'] or 0) * multiplier
                if abs(amount) < 0.001:
                    continue
                batch.append(DatiaPresupuestos(
                    empresa=empresa,
                    ejercicio=ejercicio,
                    cuenta=code,
                    periodo=row['periodo'],
                    importe=amount
                ))
                if len(batch) >= 5000:
                    DatiaPresupuestos.objects.bulk_create(batch, batch_size=5000)
                    processed += len(batch)
                    batch = []
                    pct = int((processed / max(1, total)) * 100)
                    yield {'step': 'progress', 'processed': int(processed), 'total': int(total), 'percent': pct}
            if batch:
                DatiaPresupuestos.objects.bulk_create(batch, batch_size=5000)
                processed += len(batch)
                pct = int((processed / max(1, total)) * 100)
                yield {'step': 'progress', 'processed': int(processed), 'total': int(total), 'percent': pct}
            yield {'step': 'done', 'generated_records': int(processed)}
        except Exception as e:
            yield {'status': 'error', 'message': str(e)}

    def get_treasury_snapshot(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        """
        Snapshot of Treasury: Cash, Receivables, Payables, Aging.
        Includes Top Clients/Suppliers/Banks for Dashboard.
        """
        from datetime import date, timedelta
        from django.db.models import Sum

        # 1. Cash (Group 57)
        cash_balance = self._get_saldo_pattern(empresa, ejercicio, ['57%'])

        # 2. Receivables & Payables Total (Accounting)
        # Receivables: 43 (Clientes)
        # Payables: 40 (Proveedores), 41 (Acreedores)
        receivables_total = self._get_saldo_pattern(empresa, ejercicio, ['43%'])
        payables_total = abs(self._get_saldo_pattern(empresa, ejercicio, ['40%', '41%']))

        # 3. Aging Analysis & Top Lists
        today = date.today()
        
        cartera_qs = DatiaCarteraEfectos.objects.filter(
            empresa=empresa, ejercicio=ejercicio
        ).exclude(estado__in=['COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO'])
        
        # Buckets and Top Lists
        aging_receivables = {'overdue': 0.0, '0-30': 0.0, '30-60': 0.0, '60-90': 0.0, '>90': 0.0}
        aging_receivables_overdue = {'0-30': 0.0, '30-60': 0.0, '60-90': 0.0, '>90': 0.0}
        aging_receivables_cartera = {'0-30': 0.0, '30-60': 0.0, '60-90': 0.0, '>90': 0.0}
        aging_payables = {'overdue': 0.0, '0-30': 0.0, '30-60': 0.0, '60-90': 0.0, '>90': 0.0}
        
        clients_debt = {} # Code -> Amount
        suppliers_debt = {} # Code -> Amount

        rows = cartera_qs.values('fecha_vencimiento', 'importe', 'importe_cobrado', 'tipo_efecto', 'codigo_titular')
        
        has_cartera = False
        for r in rows:
            has_cartera = True
            imp = float(r['importe'] or 0) - float(r['importe_cobrado'] or 0)
            if imp <= 0.01: continue
            
            # Aging
            vto = r['fecha_vencimiento']
            if not vto: 
                bucket = '>90'
                late_bucket = '>90'
            else:
                delta = (vto - today).days
                if delta < 0:
                    late = abs(delta)
                    bucket = 'overdue'
                    if late <= 30: late_bucket = '0-30'
                    elif late <= 60: late_bucket = '30-60'
                    elif late <= 90: late_bucket = '60-90'
                    else: late_bucket = '>90'
                elif delta <= 30:
                    bucket = '0-30'
                    late_bucket = None
                elif delta <= 60:
                    bucket = '30-60'
                    late_bucket = None
                elif delta <= 90:
                    bucket = '60-90'
                    late_bucket = None
                else:
                    bucket = '>90'
                    late_bucket = None
            
            titular = r['codigo_titular']
            
            if r['tipo_efecto'] == 'C': 
                aging_receivables[bucket] += imp
                if late_bucket:
                    aging_receivables_overdue[late_bucket] += imp
                imp_gross = float(r['importe'] or 0.0)
                if not vto:
                    abs_bucket = '>90'
                else:
                    ad = abs((vto - today).days)
                    if ad <= 30: abs_bucket = '0-30'
                    elif ad <= 60: abs_bucket = '30-60'
                    elif ad <= 90: abs_bucket = '60-90'
                    else: abs_bucket = '>90'
                aging_receivables_cartera[abs_bucket] += imp_gross
                # Top Clients
                if titular:
                    clients_debt[titular] = clients_debt.get(titular, 0.0) + imp
            else: 
                aging_payables[bucket] += imp
                # Top Suppliers
                if titular:
                    suppliers_debt[titular] = suppliers_debt.get(titular, 0.0) + imp
        
        # Importes agregados (suma de campo Importe) para cards
        try:
            total_importe = float(cartera_qs.aggregate(total=Sum('importe')).get('total') or 0.0)
        except Exception:
            total_importe = 0.0
        try:
            importe_cobros = float(cartera_qs.filter(tipo_efecto='C').aggregate(total=Sum('importe')).get('total') or 0.0)
        except Exception:
            importe_cobros = 0.0
        try:
            importe_pagos = float(cartera_qs.filter(tipo_efecto='P').aggregate(total=Sum('importe')).get('total') or 0.0)
        except Exception:
            importe_pagos = 0.0
        try:
            overdue_cut = today - timedelta(days=90)
            importe_overdue_90 = float(
                cartera_qs.filter(tipo_efecto='C', fecha_vencimiento__lt=overdue_cut).aggregate(total=Sum('importe')).get('total') or 0.0
            )
        except Exception:
            importe_overdue_90 = 0.0

        # Helper for Top N Names
        def get_top_n(debt_dict, n=10):
            sorted_items = sorted(debt_dict.items(), key=lambda x: x[1], reverse=True)[:n]
            # Fetch names
            codes = [x[0] for x in sorted_items]
            names = {}
            if codes:
                plans = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo__in=codes)
                for p in plans:
                    names[p.codigo] = p.descripcion
            
            result = []
            for code, amt in sorted_items:
                result.append({'name': names.get(code, code), 'value': round(amt, 2), 'code': code})
            return result

        top_clients = get_top_n(clients_debt)
        top_suppliers = get_top_n(suppliers_debt)

        # 4. Working Capital & Ratios
        # Need Sales (Ingresos) and Purchases (Gastos) for DSO/DPO
        # Basic Snapshot for Totals
        
        # Get Sales/Purchases from Acumulados directly to avoid recursion or overhead
        ingresos_anuales = float(abs(self._get_saldo_grupo(empresa, ejercicio, '7')))
        gastos_anuales = float(self._get_saldo_grupo(empresa, ejercicio, '6'))
        
        # DSO = (Receivables / Annual Sales) * 365
        dso = (receivables_total / ingresos_anuales * 365) if ingresos_anuales > 0 else 0.0
        
        # DPO = (Payables / Annual Purchases) * 365 
        dpo = (payables_total / gastos_anuales * 365) if gastos_anuales > 0 else 0.0
 
        ac = self._get_saldo_pattern(empresa, ejercicio, ['3%', '43%', '57%'])
        pc = abs(self._get_saldo_pattern(empresa, ejercicio, ['40%', '41%', '52%']))
        working_capital = ac - pc
        
        banks_rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith='572'
        ).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))
        
        banks_items = []
        codes = []
        for b in banks_rows:
            code_b = str(b['cuenta'] or '')
            bal = float(b['d'] or 0) - float(b['h'] or 0)
            if abs(bal) > 1.0:
                banks_items.append((code_b, bal))
                codes.append(code_b)
        names = {}
        if codes:
            plans = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo__in=codes)
            for p in plans:
                names[p.codigo] = p.descripcion
        top_banks = [{'name': names.get(code, code), 'value': round(val, 2), 'code': code} for code, val in banks_items]
        top_banks.sort(key=lambda x: abs(x['value']), reverse=True)

        return {
            'kpis': {
                'cash': float(cash_balance),
                'working_capital': float(working_capital),
                'receivables': float(receivables_total),
                'payables': float(payables_total),
                'unpaid_receivables': float(aging_receivables['overdue']),
                'dso': round(float(dso), 2),
                'dpo': round(float(dpo), 2),
                'cartera_importe_total': round(float(total_importe), 2),
                'cartera_importe_cobros': round(float(importe_cobros), 2),
                'cartera_importe_pagos': round(float(importe_pagos), 2),
                'cartera_importe_overdue_90': round(float(importe_overdue_90), 2)
            },
            'aging': {
                'receivables': aging_receivables,
                'receivables_overdue': aging_receivables_overdue,
                'receivables_cartera': aging_receivables_cartera,
                'payables': aging_payables
            },
            'charts': {
                'top_clients': top_clients,
                'top_suppliers': top_suppliers,
                'banks': top_banks
            },
            'cash': float(cash_balance),
            'working_capital': float(working_capital),
            'receivables': {
                'total': float(receivables_total),
                'aging': aging_receivables
            },
            'payables': {
                'total': float(payables_total),
                'aging': aging_payables
            },
            'meta': {'data_available': True}
        }

    def get_receivables_breakdown(self, empresa: int, ejercicio: int, level: int = 3) -> Dict[str, Any]:
        from django.db.models import Sum
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith='43'
        ).values('cuenta').annotate(total=Sum('saldo'))
        data = {}
        for row in qs:
            code = str(row['cuenta'] or '')
            if not code:
                continue
            key = code[:max(1, level)]
            data[key] = data.get(key, 0.0) + float(row['total'] or 0.0)
        rows = []
        for code, val in data.items():
            desc = self._get_account_desc(empresa, ejercicio, code)
            rows.append({'cuenta': code, 'descripcion': desc, 'saldo': round(float(val), 2)})
        rows.sort(key=lambda x: abs(x['saldo']), reverse=True)
        return {'rows': rows, 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'level': int(level)}}

    def get_receivables_breakdown_detail(self, empresa: int, ejercicio: int, parent: str, level: int = 6) -> Dict[str, Any]:
        from django.db.models import Sum
        parent = str(parent or '').strip()
        try:
            int(parent)
        except Exception:
            return {'rows': [], 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'parent': parent, 'level': int(level)}}
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith=parent
        ).values('cuenta').annotate(total=Sum('saldo'))
        data = {}
        for row in qs:
            code = str(row['cuenta'] or '')
            if not code:
                continue
            key = code[:max(1, level)]
            data[key] = data.get(key, 0.0) + float(row['total'] or 0.0)
        rows = []
        for code, val in data.items():
            desc = self._get_account_desc(empresa, ejercicio, code)
            rows.append({'cuenta': code, 'descripcion': desc, 'saldo': round(float(val), 2)})
        rows.sort(key=lambda x: abs(x['saldo']), reverse=True)
        return {'rows': rows, 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'parent': parent, 'level': int(level)}}

    def get_receivables_breakdown_flat(self, empresa: int, ejercicio: int, parent: str) -> Dict[str, Any]:
        from django.db.models import Sum
        parent = str(parent or '').strip()
        try:
            int(parent)
        except Exception:
            return {'rows': [], 'validation': {'parent_total': 0.0, 'children_sum': 0.0, 'matched': True}, 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'parent': parent}}
        qs = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=12, cuenta__startswith=parent
        ).values('cuenta').annotate(total=Sum('saldo'))
        rows = []
        total_sum = 0.0
        for r in qs:
            code = str(r['cuenta'] or '')
            val = float(r['total'] or 0.0)
            total_sum += val
            desc = self._get_account_desc(empresa, ejercicio, code)
            rows.append({'cuenta': code, 'descripcion': desc, 'saldo': round(val, 2)})
        rows.sort(key=lambda x: abs(x['saldo']), reverse=True)
        parent_total = float(self._get_saldo_pattern(empresa, ejercicio, [f"{parent}%"]))
        matched = abs(parent_total - total_sum) < 0.01
        return {
            'rows': rows,
            'validation': {'parent_total': round(parent_total, 2), 'children_sum': round(total_sum, 2), 'matched': matched},
            'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'parent': parent}
        }

    def get_cartera_clients_bucket(self, empresa: int, ejercicio: int, bucket: str) -> Dict[str, Any]:
        """
        Returns list of clients and gross 'importe' for a given absolute bucket:
        bucket in {'0-30','30-60','60-90','>90'}
        """
        from datetime import date
        bucket = str(bucket or '').strip()
        valid = {'0-30', '30-60', '60-90', '>90'}
        if bucket not in valid:
            return {'rows': [], 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'bucket': bucket}, 'total': 0.0}
        qs = DatiaCarteraEfectos.objects.filter(
            empresa=empresa, ejercicio=ejercicio, tipo_efecto='C'
        ).exclude(estado__in=['COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO'])
        rows = qs.values('fecha_vencimiento', 'importe', 'codigo_titular')
        today = date.today()
        agg = {}
        total = 0.0
        for r in rows:
            vto = r['fecha_vencimiento']
            if not vto:
                b = '>90'
            else:
                ad = abs((vto - today).days)
                if ad <= 30:
                    b = '0-30'
                elif ad <= 60:
                    b = '30-60'
                elif ad <= 90:
                    b = '60-90'
                else:
                    b = '>90'
            if b != bucket:
                continue
            code = str(r['codigo_titular'] or '').strip()
            if not code:
                continue
            val = float(r['importe'] or 0.0)
            total += val
            agg[code] = agg.get(code, 0.0) + val
        # Resolve names
        names = {}
        if agg:
            codes = list(agg.keys())
            plans = DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo__in=codes)
            for p in plans:
                names[p.codigo] = p.descripcion
        out = [{'code': c, 'name': names.get(c, c), 'value': round(v, 2)} for c, v in agg.items()]
        out.sort(key=lambda x: x['value'], reverse=True)
        return {'rows': out, 'meta': {'empresa': empresa, 'ejercicio': ejercicio, 'bucket': bucket}, 'total': round(total, 2)}

    def get_cartera_importe_codes(self, empresa: int, ejercicio: int, codes: List[str]) -> Dict[str, Any]:
        """
        Returns a map {code: total_importe} for requested account codes/prefixes.
        If a code is a prefix (e.g., '430'), sums all cartera registros whose codigo_titular startswith that prefix.
        Only considers tipo_efecto='C' and estados pendientes.
        """
        from django.db.models import F
        codes = [str(c or '').strip() for c in (codes or []) if str(c or '').strip()]
        if not codes:
            return {'map': {}, 'meta': {'empresa': empresa, 'ejercicio': ejercicio}}
        qs = DatiaCarteraEfectos.objects.filter(
            empresa=empresa, ejercicio=ejercicio, tipo_efecto='C'
        ).exclude(estado__in=['COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO']).values('codigo_titular', 'importe')
        agg_exact = {}
        for r in qs:
            code = str(r['codigo_titular'] or '').strip()
            if not code:
                continue
            val = float(r['importe'] or 0.0)
            agg_exact[code] = agg_exact.get(code, 0.0) + val
        result = {}
        keys = list(agg_exact.keys())
        for wanted in codes:
            s = 0.0
            for k in keys:
                if k.startswith(wanted):
                    s += agg_exact[k]
            result[wanted] = round(s, 2)
        return {'map': result, 'meta': {'empresa': empresa, 'ejercicio': ejercicio}}

    def get_treasury_forecast(self, empresa: int, ejercicio: int, months: int = 6, cobro_anticipado_pct: float = 0.0, diferir_pagos_pct: float = 0.0, prob_default_pct: float = 0.0, umbral_liquidez: float = 1.5) -> Dict[str, Any]:
        """
        Projects future cash flow based on CarteraEfectos due dates.
        Returns monthly buckets with Inflows, Outflows, Projected Balance and Liquidity Ratio.
        """
        from datetime import date, timedelta
        import itertools
        
        # 1. Starting Position (Current Cash)
        current_cash = float(self._get_saldo_pattern(empresa, ejercicio, ['57%']))
        # Base Liquidity components from Balance Summary
        try:
            bs = self.get_balance_summary(empresa, ejercicio)
            ac_base = float(bs.get('desglose', {}).get('activo', {}).get('corriente', 0.0))
            pc_base = float(bs.get('desglose', {}).get('pasivo', {}).get('corriente', 1.0)) or 1.0
        except Exception:
            ac_base, pc_base = 0.0, 1.0
        
        # 2. Fetch Future Items
        today = date.today()
        cutoff = today + timedelta(days=30 * months)
        
        qs = DatiaCarteraEfectos.objects.filter(
            empresa=empresa, 
            fecha_vencimiento__gte=today,
            fecha_vencimiento__lte=cutoff
        ).exclude(estado__in=['COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO'])
        
        rows = qs.values('fecha_vencimiento', 'importe', 'importe_cobrado', 'tipo_efecto')
        
        # 3. Bucket by Month
        buckets = {} # "YYYY-MM" -> {in: 0, out: 0}
        
        # Initialize buckets for the next N months to ensure continuity
        for i in range(months):
            d = today + timedelta(days=30 * i)
            key = d.strftime("%Y-%m")
            buckets[key] = {'in': 0.0, 'out': 0.0}
            
        for r in rows:
            vto = r['fecha_vencimiento']
            if not vto: continue
            
            key = vto.strftime("%Y-%m")
            if key not in buckets: continue # Should be covered if within cutoff
            
            imp = float(r['importe'] or 0) - float(r['importe_cobrado'] or 0)
            if imp <= 0.01: continue
            
            if r['tipo_efecto'] == 'C':
                buckets[key]['in'] += imp
            else:
                buckets[key]['out'] += imp
                
        # 4. Scenario adjustments and Calculate Projection
        # Clamp parameters to safe ranges
        try:
            cobro_anticipado_pct = max(0.0, min(50.0, float(cobro_anticipado_pct or 0.0)))
        except Exception:
            cobro_anticipado_pct = 0.0
        try:
            diferir_pagos_pct = max(0.0, min(50.0, float(diferir_pagos_pct or 0.0)))
        except Exception:
            diferir_pagos_pct = 0.0
        try:
            prob_default_pct = max(0.0, min(10.0, float(prob_default_pct or 0.0)))
        except Exception:
            prob_default_pct = 0.0
        try:
            umbral_liquidez = max(0.1, float(umbral_liquidez or 1.5))
        except Exception:
            umbral_liquidez = 1.5
        
        sorted_keys = sorted(buckets.keys())
        series = []
        running_cash = current_cash
        cum_inflow = 0.0
        cum_outflow = 0.0
        alerts = []
        
        for key in sorted_keys:
            base_in = buckets[key]['in']
            base_out = buckets[key]['out']
            # Adjustments: early collections increase inflow; default risk reduces inflow; payment deferral reduces outflow
            inflow = base_in * (1.0 + cobro_anticipado_pct / 100.0) * (1.0 - prob_default_pct / 100.0)
            outflow = base_out * (1.0 - diferir_pagos_pct / 100.0)
            net_change = inflow - outflow
            running_cash += net_change
            cum_inflow += inflow
            cum_outflow += outflow
            denom = pc_base if pc_base > 1e-6 else 1.0
            ratio = (ac_base + cum_inflow - cum_outflow) / denom
            # Alerts
            if running_cash < 0:
                alerts.append({'period': key, 'type': 'caja', 'threshold': 0.0, 'value': running_cash})
            if ratio < umbral_liquidez:
                alerts.append({'period': key, 'type': 'liquidez', 'threshold': umbral_liquidez, 'value': ratio})
            
            series.append({
                'period': key, # YYYY-MM
                'inflow': inflow,
                'outflow': outflow,
                'balance': running_cash,
                'ratio': ratio
            })
            
        return {
            'start_cash': current_cash,
            'forecast': series,
            'alerts': alerts,
            'validation': {
                'sum_inflow': sum(x['inflow'] for x in series),
                'sum_outflow': sum(x['outflow'] for x in series),
                'min_balance': min((x['balance'] for x in series), default=current_cash),
                'min_ratio': min((x.get('ratio', 0.0) for x in series), default=0.0)
            },
            'meta': {
                'months': months,
                'umbral_liquidez': umbral_liquidez
            }
        }

    def _get_budget_desc_map(self, empresa: int, codes: List[str]) -> Dict[str, str]:
        codes = [str(c) for c in codes if c]
        uniq_codes = []
        for c in codes:
            if c not in uniq_codes:
                uniq_codes.append(c)
        desc_map: Dict[str, str] = {}
        if not uniq_codes:
            return desc_map
        conn = None
        try:
            from datia.services.etl_service import ETLService
            etl = ETLService()
            conn = etl.get_connection()
            cursor = conn.cursor()
            cands = etl.get_table_candidates(cursor, 'plan_cuentas')
            tab, colmap = etl.pick_best_table(cursor, cands, etl.COLUMN_MAP_PLAN_CUENTAS, ['codigo', 'descripcion'])

            def normalize_empresa_candidates(val):
                s = str(val).strip()
                seq = [s]
                if s.isdigit():
                    seq.append(s.zfill(2))
                    seq.append(s.zfill(3))
                    try:
                        seq.append(str(int(s)))
                    except Exception:
                        pass
                else:
                    try:
                        seq.append(str(int(s)))
                    except Exception:
                        pass
                res = []
                for x in seq:
                    if x not in res:
                        res.append(x)
                return res

            if tab and ('codigo' in colmap):
                chunk_size = 900
                emp_candidates = normalize_empresa_candidates(empresa) if 'empresa' in colmap else []
                for i in range(0, len(uniq_codes), chunk_size):
                    chunk = uniq_codes[i:i + chunk_size]
                    ph_codes = ','.join(['?'] * len(chunk))
                    if 'descripcion' in colmap:
                        if emp_candidates:
                            ph_emp = ','.join(['?'] * len(emp_candidates))
                            sql = f"SELECT T.{colmap['codigo']}, T.{colmap['descripcion']} FROM {tab} T WHERE T.{colmap['codigo']} IN ({ph_codes}) AND T.{colmap['empresa']} IN ({ph_emp})"
                            params = tuple(chunk + emp_candidates)
                        else:
                            sql = f"SELECT T.{colmap['codigo']}, T.{colmap['descripcion']} FROM {tab} T WHERE T.{colmap['codigo']} IN ({ph_codes})"
                            params = tuple(chunk)
                        cursor.execute(sql, params)
                        for row in cursor.fetchall():
                            code_val = str(row[0]).strip() if row[0] is not None else None
                            desc_val = str(row[1]).strip() if row[1] is not None else None
                            if code_val and desc_val and code_val not in desc_map:
                                desc_map[code_val] = desc_val
                    else:
                        if emp_candidates:
                            ph_emp = ','.join(['?'] * len(emp_candidates))
                            sql2 = f"SELECT T.{colmap['codigo']} FROM {tab} T WHERE T.{colmap['codigo']} IN ({ph_codes}) AND T.{colmap['empresa']} IN ({ph_emp})"
                            params2 = tuple(chunk + emp_candidates)
                        else:
                            sql2 = f"SELECT T.{colmap['codigo']} FROM {tab} T WHERE T.{colmap['codigo']} IN ({ph_codes})"
                            params2 = tuple(chunk)
                        cursor.execute(sql2, params2)
                        for row in cursor.fetchall():
                            code_val = str(row[0]).strip() if row[0] is not None else None
                            if code_val and any(ch.isalpha() for ch in code_val) and code_val not in desc_map:
                                desc_map[code_val] = code_val
        except Exception:
            return desc_map
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        return desc_map

    def get_budget_grid(self, empresa: int, ejercicio: int, group_filter: str = 'PL', base_year: int = None) -> Dict[str, Any]:
        """
        Returns the budget grid rows with two lines per account:
        Base (prev year) non-editable and Presupuesto (current target year) editable.
        """
        from datia.models.financial import DatiaPresupuestos, DatiaAcumuladosConta
        from django.db.models import Q, Sum
        
        # 1. Determine accounts to fetch
        prefixes = []
        if group_filter == 'PL': prefixes = ['6', '7']
        elif group_filter == '6': prefixes = ['6']
        elif group_filter == '7': prefixes = ['7']
        else: prefixes = ['6', '7']

        q_bud = Q()
        for p in prefixes:
            q_bud |= Q(cuenta__startswith=p)
        budget_map = {}
        controls_map = {}
        try:
            budgets = list(DatiaPresupuestos.objects.filter(q_bud, empresa=empresa, ejercicio=ejercicio))
        except Exception:
            budgets = []
        for b in budgets:
            if b.cuenta not in budget_map:
                budget_map[b.cuenta] = [0.0] * 13
            if 1 <= b.periodo <= 12:
                budget_map[b.cuenta][b.periodo] = float(b.importe)
            if b.cuenta not in controls_map:
                controls_map[b.cuenta] = {
                    'agosto_full': bool(getattr(b, 'agosto_full', False)),
                    'line_pct': float(getattr(b, 'line_pct', 0) or 0)
                }

        base_year = int(base_year) if base_year is not None else (int(ejercicio) - 1)
        q_prev = Q(empresa=empresa, ejercicio=base_year, periodo__lte=12)
        q_prev_groups = Q()
        for p in prefixes:
            q_prev_groups |= Q(cuenta__startswith=p)
        prev_rows = DatiaAcumuladosConta.objects.filter(q_prev & q_prev_groups).values('cuenta', 'periodo').annotate(total=Sum('saldo'))
        base_map = {}
        for r in prev_rows:
            code = str(r['cuenta'])
            period = int(r['periodo'] or 0)
            val = float(r['total'] or 0.0)
            if code.startswith('7'):
                val = abs(val)
            if code not in base_map:
                base_map[code] = [0.0] * 13
            if 1 <= period <= 12:
                base_map[code][period] = val

        included_codes = sorted(set(list(budget_map.keys())) | set(list(base_map.keys())))
        desc_map = self._get_budget_desc_map(empresa, included_codes)
        
        # 5. Fetch Notes for included codes
        notes_map = {}
        try:
            from datia.models.financial import DatiaPresupuestoNotas
            if included_codes:
                qs_notes = DatiaPresupuestoNotas.objects.filter(
                    empresa=empresa, ejercicio=ejercicio, cuenta__in=included_codes
                ).values('cuenta', 'periodo', 'nota')
                for n in qs_notes:
                    c = str(n['cuenta'])
                    p = int(n['periodo'] or 0)
                    t = n['nota'] or ''
                    if c not in notes_map:
                        notes_map[c] = {}
                    notes_map[c][p] = t
        except Exception:
            notes_map = {}
        
        # 6. Build rows
        rows = []
        for code in included_codes:
            bmonths = budget_map.get(code, [0.0] * 13)[1:]
            btotal = sum(bmonths)
            amonths = base_map.get(code, [0.0] * 13)[1:]
            atotal = sum(amonths)
            rows.append({
                'cuenta': code,
                'descripcion': desc_map.get(code, code),
                'base': {
                    'year': base_year,
                    'months': amonths,
                    'total': atotal
                },
                'presupuesto': {
                    'year': int(ejercicio),
                    'months': bmonths,
                    'total': btotal,
                    'config': controls_map.get(code, {'agosto_full': False, 'line_pct': 0.0}),
                    'notes': notes_map.get(code, {})
                }
            })
        rows.sort(key=lambda x: x['cuenta'])
        
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'meta': {
                'base_year': base_year,
                'budget_year': int(ejercicio)
            },
            'rows': rows
        }
        
    def save_budget_row(self, empresa, ejercicio, cuenta, period, value):
        from datia.models.financial import DatiaPresupuestos
        obj, created = DatiaPresupuestos.objects.update_or_create(
            empresa=empresa,
            ejercicio=ejercicio,
            cuenta=cuenta,
            periodo=period,
            defaults={'importe': value}
        )
        return obj

    def save_budget_controls(self, empresa, ejercicio, cuenta, agosto_full, line_pct):
        from datia.models.financial import DatiaPresupuestos
        try:
            lpct = float(line_pct or 0.0)
        except Exception:
            lpct = 0.0
        if lpct < -100.0 or lpct > 100.0:
            raise ValueError('line_pct out of range')
        DatiaPresupuestos.objects.filter(
            empresa=empresa,
            ejercicio=ejercicio,
            cuenta=cuenta
        ).update(agosto_full=bool(agosto_full), line_pct=lpct)
        return True

    def save_budget_note(self, empresa: int, ejercicio: int, cuenta: str, periodo: int, nota: str):
        from datia.models.financial import DatiaPresupuestoNotas
        obj, created = DatiaPresupuestoNotas.objects.update_or_create(
            empresa=empresa,
            ejercicio=ejercicio,
            cuenta=cuenta,
            periodo=periodo,
            defaults={'nota': nota or ''}
        )
        return obj

    def generate_initial_budget(self, empresa: int, ejercicio: int, base_year: int, increment_pct: float) -> int:
        from datia.models.financial import DatiaPresupuestos, DatiaAcumuladosConta
        from django.db.models import Sum
        
        try:
            # 1. Fetch Base Actuals (Optimized)
            # Groups 6 and 7 only
            actuals = DatiaAcumuladosConta.objects.filter(
                empresa=empresa, 
                ejercicio=base_year,
                periodo__lte=12,
                cuenta__regex=r'^[67]' 
            ).values('cuenta', 'periodo').annotate(total=Sum('saldo'))
            
            if not actuals:
                return 0
                
            created_count = 0
            # Normalize percentage: None or blank -> 0
            try:
                pct = float(increment_pct or 0.0)
            except Exception:
                pct = 0.0
            multiplier = 1.0 + (pct / 100.0)
            
            # 2. Upsert only missing months; respect existing manual entries
            for row in actuals:
                code = row['cuenta']
                amount_base = float(row['total'] or 0)
                amount = amount_base * multiplier
                
                # Skip zero amounts to save space? User might want to see them.
                # Let's keep them if significant
                if abs(amount) < 0.001: 
                    continue

                # Respect existing budget entries: create if missing, do not overwrite
                obj, created = DatiaPresupuestos.objects.get_or_create(
                    empresa=empresa,
                    ejercicio=ejercicio,
                    cuenta=code,
                    periodo=row['periodo'],
                    defaults={'importe': amount}
                )
                if created:
                    created_count += 1
                
            return created_count
            
        except Exception as e:
            print(f"Error generating budget: {e}")
            raise e

    def get_ratio_drilldown(self, empresa: int, ejercicio: int, ratio: str) -> Dict[str, Any]:
        """
        Returns detailed drilldown for a specific ratio:
        - Lists of accounts for Numerator and Denominator
        - Senior Analysis Text (Expert Logic)
        """
        
        # 1. Define Components based on Ratio
        num_prefixes = []
        den_prefixes = []
        ratio_label = ""
        
        if ratio == 'liquidez':
            ratio_label = "Liquidez General"
            num_prefixes = self._get_balance_prefixes('activo_corriente')
            den_prefixes = self._get_balance_prefixes('pasivo_corriente')
        elif ratio == 'solvencia':
            ratio_label = "Solvencia a Corto Plazo" 
            num_prefixes = self._get_balance_prefixes('activo')
            den_prefixes = self._get_balance_prefixes('pasivo')
        elif ratio == 'endeudamiento':
            ratio_label = "Endeudamiento"
            num_prefixes = self._get_balance_prefixes('pasivo')
            den_prefixes = self._get_balance_prefixes('patrimonio')
        else:
            return {'status': 'error', 'message': 'Ratio desconocido'}

        # 2. Fetch Account Details helper
        def fetch_details(prefixes):
            from django.db.models import Q
            q_obj = Q()
            for p in prefixes:
                clean_p = p.replace('%', '')
                q_obj |= Q(cuenta__startswith=clean_p)
            
            rows = DatiaAcumuladosConta.objects.filter(
                q_obj,
                empresa=empresa,
                ejercicio=ejercicio,
                periodo__lte=12
            ).values('cuenta').annotate(d=Sum('debe'), h=Sum('haber'))
            
            details = []
            total = 0.0
            
            for r in rows:
                code = r['cuenta']
                debe = float(r.get('d') or 0.0)
                haber = float(r.get('h') or 0.0)
                
                val = 0.0
                if code.startswith(('1', '40', '41', '50', '51', '52', '475', '476', '477', '49')): # Pasivo/PN
                     val = haber - debe
                else: # Activo
                     val = debe - haber
                
                if abs(val) > 0.01:
                    desc = self._get_account_desc(empresa, ejercicio, code)
                    details.append({
                        'code': code,
                        'name': desc,
                        'value': round(val, 2)
                    })
                    total += val
            
            details.sort(key=lambda x: abs(x['value']), reverse=True)
            return details, total

        num_details, num_total = fetch_details(num_prefixes)
        den_details, den_total = fetch_details(den_prefixes)

        # 3. Calculate Ratio
        ratio_val = 0.0
        if den_total != 0:
            if ratio == 'endeudamiento':
                ratio_val = (num_total / den_total) * 100.0
            else:
                ratio_val = num_total / den_total

        # 4. Generate "Senior Analysis" Text
        analysis_text = ""
        
        if ratio == 'liquidez':
            if ratio_val < 1.0:
                analysis_text = (
                    f"CRÍTICO: El ratio de {ratio_val:.2f} indica un Fondo de Maniobra negativo. "
                    "La empresa financia activos inmovilizados con deuda a corto plazo, lo que genera un riesgo inminente de suspensión de pagos. "
                    "Se recomidena reestructurar deuda a largo plazo o ampliar capital urgentemente."
                )
            elif 1.0 <= ratio_val < 1.5:
                analysis_text = (
                    f"PRECAUCIÓN: Con un ratio de {ratio_val:.2f}, la empresa cubre sus obligaciones a corto pero con poco margen. "
                    "Cualquier retraso en cobros podría generar tensiones de tesorería. Se sugiere optimizar el ciclo de conversión de efectivo."
                )
            elif 1.5 <= ratio_val < 2.5:
                analysis_text = (
                    f"ÓPTIMO: Posición sólida ({ratio_val:.2f}). Existe un equilibrio correcto entre activos líquidos y obligaciones exigibles. "
                    "La empresa demuestra capacidad de pago sin incurrir en recursos ociosos excesivos."
                )
            else:
                analysis_text = (
                    f"EXCESO: Un ratio de {ratio_val:.2f} sugiere activos corrientes improductivos (exceso de caja o stock obsoleto). "
                    "Aunque la solvencia a corto está garantizada, se está sacrificando rentabilidad."
                )
                
        elif ratio == 'solvencia':
            if ratio_val < 1.0:
                 analysis_text = (
                    f"QUIEBRA TÉCNICA: El valor {ratio_val:.2f} revela que los pasivos superan a los activos totales. "
                    "El Patrimonio Neto es negativo, indicando que los socios han perdido su inversión y la empresa se sostiene con deuda."
                )
            elif 1.0 <= ratio_val < 1.5:
                 analysis_text = (
                    f"DEBILIDAD: Ratio de {ratio_val:.2f}. Los activos cubren las deudas pero con un margen estrecho. "
                    "La autonomía financiera es limitada y existe alta dependencia de los acreedores."
                )
            else:
                 analysis_text = (
                    f"ROBUSTEZ: Un ratio de {ratio_val:.2f} indica una fuerte protección para los acreedores. "
                    "La empresa dispone de activos reales suficientes para respaldar su financiación ajena con holgura."
                )

        elif ratio == 'endeudamiento':
            if ratio_val > 150:
                 analysis_text = (
                    f"ALARMA: Endeudamiento muy elevado ({ratio_val:.1f}%). Por cada euro propio, hay 1.5 ajenos. "
                    "Riesgo financiero alto ante variaciones de tipos de interés, o sensibilidad a caídas en el EBITDA."
                )
            elif 80 <= ratio_val <= 150:
                 analysis_text = (
                    f"ELEVADO: Endeudamiento del {ratio_val:.1f}%. Apalancamiento agresivo que puede potenciar la rentabilidad (ROE) "
                    "si el coste de la deuda es bajo, pero aumenta la vulnerabilidad financiera."
                )
            elif 40 <= ratio_val < 80:
                 analysis_text = (
                    f"EQUILIBRADO: Nivel ({ratio_val:.1f}%) saludable. Existe un mix razonable entre financiación propia y ajena, "
                    "aprovechando el escudo fiscal de la deuda sin comprometer la estabilidad."
                )
            else:
                 analysis_text = (
                    f"CONSERVADOR: Bajo endeudamiento ({ratio_val:.1f}%). Gran autonomía financiera, aunque podría indicarse "
                    "una política excesivamente prudente que no maximiza el retorno para el accionista."
                )

        return {
            'ratio': ratio,
            'value': ratio_val,
            'label': ratio_label,
            'analysis': analysis_text,
            'numerator': {
                'total': num_total,
                'details': num_details
            },
            'denominator': {
                'total': den_total,
                'details': den_details
            }
        }

    def get_budget_comparison_data(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        """
        Calculates comparison between Actual (DatiaAcumuladosConta) and Budget (DatiaPresupuestos).
        Returns table data and charts data.
        """
        from datia.models.financial import DatiaAcumuladosConta, DatiaPresupuestos
        from django.db.models import Sum, Q
        from django.db.utils import ProgrammingError, OperationalError

        # 1. Fetch Real Data (Acumulados) - Groups 6 and 7
        try:
            rows_acum = list(
                DatiaAcumuladosConta.objects.filter(
                    empresa=empresa, ejercicio=ejercicio, periodo__lte=12
                )
                .filter(Q(cuenta__startswith='6') | Q(cuenta__startswith='7'))
                .values('cuenta', 'periodo')
                .annotate(total=Sum('saldo'))
            )
        except (ProgrammingError, OperationalError):
            rows_acum = []

        # 2. Fetch Budget Data
        try:
            rows_budget = list(
                DatiaPresupuestos.objects.filter(
                    empresa=empresa, ejercicio=ejercicio
                )
                .filter(Q(cuenta__startswith='6') | Q(cuenta__startswith='7'))
                .values('cuenta', 'periodo')
                .annotate(total=Sum('importe'))
            )
        except (ProgrammingError, OperationalError):
            rows_budget = []

        # Build Lookups
        real_map = {}
        for r in rows_acum:
            key = (r['cuenta'], r['periodo'])
            val = float(r['total'] or 0.0)
            if r['cuenta'].startswith('6'):
                real_map[key] = val
            elif r['cuenta'].startswith('7'):
                real_map[key] = abs(val) # Invert to positive
        
        bud_map = {}
        for r in rows_budget:
            key = (r['cuenta'], r['periodo'])
            val = float(r['total'] or 0.0)
            bud_map[key] = abs(val)

        # 3. Aggregate by Account (Year Total) for Table
        all_accounts = set([str(c) for c, p in real_map.keys()] + [str(c) for c, p in bud_map.keys()])
        desc_map = {}
        try:
            from datia.models.financial import DatiaPlanCuentas
            desc_map = {
                str(r.get('codigo') or ''): (r.get('descripcion') or '')
                for r in DatiaPlanCuentas.objects.filter(empresa=empresa, ejercicio=ejercicio, codigo__in=list(all_accounts)).values('codigo', 'descripcion')
            }
        except Exception:
            desc_map = {}
        table_data = []
        
        for acc in all_accounts:
            real_sum = sum(real_map.get((acc, p), 0.0) for p in range(1, 13))
            bud_sum = sum(bud_map.get((acc, p), 0.0) for p in range(1, 13))
            
            if real_sum == 0 and bud_sum == 0:
                continue

            desc = desc_map.get(acc) or 'Sin Descripción'
            diff = real_sum - bud_sum
            # Deviation %: (Diff / Budget) * 100
            pct = (diff / bud_sum * 100.0) if bud_sum != 0 else (100.0 if real_sum != 0 else 0.0)
            
            table_data.append({
                'cuenta': acc,
                'descripcion': desc,
                'real': round(real_sum, 2),
                'presupuesto': round(bud_sum, 2),
                'desviacion': round(diff, 2),
                'desviacion_pct': round(pct, 2),
                'is_ingreso': acc.startswith('7')
            })

        table_data.sort(key=lambda x: x['cuenta'])

        # 4. Aggregate by Month for Charts (Income vs Expense)
        # Series for: Real Income, Budget Income, Real Expense, Budget Expense
        real_inc = [0.0]*12
        bud_inc = [0.0]*12
        real_exp = [0.0]*12
        bud_exp = [0.0]*12

        # Optimized Chart Aggregation
        for (acc, p), val in real_map.items():
            if 1 <= p <= 12:
                if acc.startswith('7'):
                    real_inc[p-1] += val
                else:
                    real_exp[p-1] += val
        
        for (acc, p), val in bud_map.items():
            if 1 <= p <= 12:
                if acc.startswith('7'):
                    bud_inc[p-1] += val
                else:
                    bud_exp[p-1] += val

        # 5. Cumulative Logic
        def accum(arr):
            out = []
            run = 0.0
            for x in arr:
                run += x
                out.append(round(run, 2))
            return out

        return {
            'table': table_data,
            'charts': {
                'monthly': {
                    'real_income': [round(x, 2) for x in real_inc],
                    'budget_income': [round(x, 2) for x in bud_inc],
                    'real_expense': [round(x, 2) for x in real_exp],
                    'budget_expense': [round(x, 2) for x in bud_exp]
                },
                'cumulative': {
                    'real_income': accum(real_inc),
                    'budget_income': accum(bud_inc),
                    'real_expense': accum(real_exp),
                    'budget_expense': accum(bud_exp)
                }
            }
        }

    def validate_pl_balance(self, empresa: int, ejercicio: int, tolerance: float = 0.01) -> Dict[str, Any]:
        ventas70 = float(self._get_saldo_grupo(empresa, ejercicio, '70') or 0.0)
        otros7 = float(sum(self._get_saldo_grupo(empresa, ejercicio, p) for p in ['72','73','74','75','76','77','78','79']) or 0.0)
        var71 = float(self._get_saldo_grupo(empresa, ejercicio, '71') or 0.0)
        ingresos_total = float(abs(self._get_saldo_grupo(empresa, ejercicio, '7') or 0.0))
        ingresos_split = float(abs(ventas70)) + float(abs(otros7)) + float(abs(var71))
        cost60 = float(self._get_saldo_grupo(empresa, ejercicio, '60') or 0.0)
        var61 = float(self._get_saldo_grupo(empresa, ejercicio, '61') or 0.0)
        ga = float(sum(self._get_saldo_grupo(empresa, ejercicio, p) for p in ['62','65','69']) or 0.0)
        impuestos = float(self._get_saldo_grupo(empresa, ejercicio, '63') or 0.0)
        personal = float(self._get_saldo_grupo(empresa, ejercicio, '64') or 0.0)
        amort = float(self._get_saldo_grupo(empresa, ejercicio, '68') or 0.0)
        financiero = float(self._get_saldo_grupo(empresa, ejercicio, '66') or 0.0) + float(self._get_saldo_grupo(empresa, ejercicio, '67') or 0.0)
        gastos_total = float(self._get_saldo_grupo(empresa, ejercicio, '6') or 0.0)
        ogde_full = float(ga + impuestos + personal + amort + financiero)
        gastos_split = float(cost60 + var61 + ogde_full)
        util_from_totals = float(ingresos_total - gastos_total)
        util_from_split = float(ingresos_split - gastos_split)
        pl = self.get_pl_report(empresa, ejercicio, 2)
        pl_res = float(pl.get('resultado_explotacion') or 0.0)
        diff_resultado = float(util_from_totals - pl_res)
        diff_split_vs_totals = float(util_from_totals - util_from_split)
        pref_list = ['60','61','62','63','64','65','66','67','68','69']
        sum_by_prefix = {p: float(self._get_saldo_grupo(empresa, ejercicio, p) or 0.0) for p in pref_list}
        sum_prefix_total = float(sum(sum_by_prefix.values()))
        alerts = []
        if abs(diff_resultado) > tolerance:
            alerts.append({'type': 'resultado_mismatch', 'diff': round(diff_resultado, 2)})
        if abs(diff_split_vs_totals) > tolerance:
            alerts.append({'type': 'split_vs_totals_mismatch', 'diff': round(diff_split_vs_totals, 2)})
        if abs(sum_prefix_total - gastos_total) > tolerance:
            alerts.append({'type': 'prefix_coverage_mismatch', 'diff': round(sum_prefix_total - gastos_total, 2)})
        return {
            'ok': len(alerts) == 0,
            'tolerance': float(tolerance),
            'computed': {
                'ingresos_total': round(ingresos_total, 2),
                'ingresos_split': round(ingresos_split, 2),
                'coste_ventas': round(cost60, 2),
                'variacion_existencias_61': round(var61, 2),
                'variacion_existencias_71': round(abs(var71), 2),
                'gastos_admin': round(ga, 2),
                'impuestos': round(impuestos, 2),
                'personal': round(personal, 2),
                'amort': round(amort, 2),
                'financiero': round(financiero, 2),
                'ogde_full': round(ogde_full, 2),
                'gastos_total': round(gastos_total, 2),
                'utilidad_totales': round(util_from_totals, 2),
                'utilidad_split': round(util_from_split, 2)
            },
            'pl_resultado_explotacion': round(pl_res, 2),
            'diff_resultado': round(diff_resultado, 2),
            'equivalencias': {
                'ogde_calc': round(ogde_full, 2),
                'ogde_split_sum': round(ogde_full, 2),
                'diff_ogde': 0.0
            },
            'prefix_coverage': {
                'sum_by_prefix': {k: round(v, 2) for k, v in sum_by_prefix.items()},
                'total_group6': round(gastos_total, 2),
                'diff': round(sum_prefix_total - gastos_total, 2)
            },
            'alerts': alerts
        }

    def get_per100(self, empresa: int, ejercicio: int, eq_mode: bool = True) -> Dict[str, Any]:
        base = float(abs(self._get_saldo_grupo(empresa, ejercicio, '7') or 0.0))
        if base <= 0.0:
            return {'empresa': empresa, 'ejercicio': ejercicio, 'eq_mode': bool(eq_mode), 'status': 'no_data', 'cy': {}, 'py': {}, 'validation': {}}
        cost60 = float(self._get_saldo_grupo(empresa, ejercicio, '60') or 0.0)
        ga = float(sum(self._get_saldo_grupo(empresa, ejercicio, p) for p in ['62','65','69']) or 0.0)
        impuestos = float(self._get_saldo_grupo(empresa, ejercicio, '63') or 0.0)
        personal = float(self._get_saldo_grupo(empresa, ejercicio, '64') or 0.0)
        amort = float(self._get_saldo_grupo(empresa, ejercicio, '68') or 0.0)
        financiero = float(self._get_saldo_grupo(empresa, ejercicio, '66') or 0.0) + float(self._get_saldo_grupo(empresa, ejercicio, '67') or 0.0)
        ogde = float(ga + impuestos + personal + amort + financiero)
        if eq_mode:
            parts_cy = [
                {'key': 'costo_ventas', 'amount': round(cost60, 2), 'pct': round((cost60 / base * 100.0), 2)},
                {'key': 'otros_gastos_exp', 'amount': round(ogde, 2), 'pct': round((ogde / base * 100.0), 2)},
            ]
            util_amount = float(base - cost60 - ogde)
            parts_cy.append({'key': 'utilidad_neta', 'amount': round(util_amount, 2), 'pct': round((util_amount / base * 100.0), 2)})
        else:
            parts_cy = [
                {'key': 'costo_ventas', 'amount': round(cost60, 2), 'pct': round((cost60 / base * 100.0), 2)},
                {'key': 'gastos_admin', 'amount': round(ga, 2), 'pct': round((ga / base * 100.0), 2)},
                {'key': 'impuestos', 'amount': round(impuestos, 2), 'pct': round((impuestos / base * 100.0), 2)},
                {'key': 'personal', 'amount': round(personal, 2), 'pct': round((personal / base * 100.0), 2)},
                {'key': 'amort', 'amount': round(amort, 2), 'pct': round((amort / base * 100.0), 2)},
                {'key': 'financiero', 'amount': round(financiero, 2), 'pct': round((financiero / base * 100.0), 2)},
            ]
            used = float(sum(p['amount'] for p in parts_cy))
            util_amount = float(base - used)
            parts_cy.append({'key': 'utilidad_neta', 'amount': round(util_amount, 2), 'pct': round((util_amount / base * 100.0), 2)})
        sum_pct_cy = float(sum(p['pct'] for p in parts_cy))
        py_base = float(abs(self._get_saldo_grupo(empresa, ejercicio - 1, '7') or 0.0))
        if py_base > 0.0:
            py_cost60 = float(self._get_saldo_grupo(empresa, ejercicio - 1, '60') or 0.0)
            py_ga = float(sum(self._get_saldo_grupo(empresa, ejercicio - 1, p) for p in ['62','65','69']) or 0.0)
            py_imp = float(self._get_saldo_grupo(empresa, ejercicio - 1, '63') or 0.0)
            py_per = float(self._get_saldo_grupo(empresa, ejercicio - 1, '64') or 0.0)
            py_amo = float(self._get_saldo_grupo(empresa, ejercicio - 1, '68') or 0.0)
            py_fin = float(self._get_saldo_grupo(empresa, ejercicio - 1, '66') or 0.0) + float(self._get_saldo_grupo(empresa, ejercicio - 1, '67') or 0.0)
            py_ogde = float(py_ga + py_imp + py_per + py_amo + py_fin)
            if eq_mode:
                parts_py = [
                    {'key': 'costo_ventas', 'amount': round(py_cost60, 2), 'pct': round((py_cost60 / py_base * 100.0), 2)},
                    {'key': 'otros_gastos_exp', 'amount': round(py_ogde, 2), 'pct': round((py_ogde / py_base * 100.0), 2)},
                ]
                py_util_amount = float(py_base - py_cost60 - py_ogde)
                parts_py.append({'key': 'utilidad_neta', 'amount': round(py_util_amount, 2), 'pct': round((py_util_amount / py_base * 100.0), 2)})
            else:
                parts_py = [
                    {'key': 'costo_ventas', 'amount': round(py_cost60, 2), 'pct': round((py_cost60 / py_base * 100.0), 2)},
                    {'key': 'gastos_admin', 'amount': round(py_ga, 2), 'pct': round((py_ga / py_base * 100.0), 2)},
                    {'key': 'impuestos', 'amount': round(py_imp, 2), 'pct': round((py_imp / py_base * 100.0), 2)},
                    {'key': 'personal', 'amount': round(py_per, 2), 'pct': round((py_per / py_base * 100.0), 2)},
                    {'key': 'amort', 'amount': round(py_amo, 2), 'pct': round((py_amo / py_base * 100.0), 2)},
                    {'key': 'financiero', 'amount': round(py_fin, 2), 'pct': round((py_fin / py_base * 100.0), 2)},
                ]
                py_used = float(sum(p['amount'] for p in parts_py))
                py_util_amount = float(py_base - py_used)
                parts_py.append({'key': 'utilidad_neta', 'amount': round(py_util_amount, 2), 'pct': round((py_util_amount / py_base * 100.0), 2)})
            sum_pct_py = float(sum(p['pct'] for p in parts_py))
        else:
            parts_py = []
            sum_pct_py = 0.0
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'eq_mode': bool(eq_mode),
            'status': 'ok',
            'base_cy': round(base, 2),
            'base_py': round(py_base, 2),
            'cy': {'parts': parts_cy},
            'py': {'parts': parts_py},
            'validation': {
                'sum_pct_cy': round(sum_pct_cy, 2),
                'close_diff_cy': round(100.0 - sum_pct_cy, 2),
                'sum_pct_py': round(sum_pct_py, 2),
                'close_diff_py': round(100.0 - sum_pct_py, 2)
            }
        }

    def get_uninvoiced_lines(self, empresa: int, ejercicio: int) -> Dict[str, Any]:
        from datia.services.etl_service import ETLService
        svc = ETLService()
        conn = svc.get_connection()
        cursor = conn.cursor()
        try:
            tab_cab = 'CabeceraAlbaranCliente' if svc.table_exists(cursor, 'CabeceraAlbaranCliente') else None
            tab_lin = 'LineasAlbaranCliente' if svc.table_exists(cursor, 'LineasAlbaranCliente') else None
            if not tab_cab or not tab_lin:
                return {'status': 'not_supported', 'empresa': empresa, 'ejercicio': ejercicio}
            map_cab = svc.get_column_mapping(cursor, tab_cab, svc.COLUMN_MAP_CABECERA)
            map_lin = svc.get_column_mapping(cursor, tab_lin, svc.COLUMN_MAP_LINEAS)
            req_cab = ['empresa', 'ejercicio', 'serie', 'numero', 'facturado']
            req_lin = ['empresa', 'ejercicio', 'serie', 'numero', 'neto']
            if not all(k in map_cab for k in req_cab) or not all(k in map_lin for k in req_lin):
                return {'status': 'not_supported', 'empresa': empresa, 'ejercicio': ejercicio}
            emp_candidates = svc._empresa_candidates(empresa)
            placeholders_emp = ",".join("?" for _ in emp_candidates)
            fact_cond = f"(C.{map_cab['facturado']} IS NULL OR C.{map_cab['facturado']} <> -1)"
            sql_lines = f"""
                SELECT COUNT(*) as cnt, SUM(L.{map_lin['neto']}) as total
                FROM {tab_lin} L
                JOIN {tab_cab} C
                  ON L.{map_lin['empresa']} = C.{map_cab['empresa']}
                 AND L.{map_lin['ejercicio']} = C.{map_cab['ejercicio']}
                 AND L.{map_lin['serie']} = C.{map_cab['serie']}
                 AND L.{map_lin['numero']} = C.{map_cab['numero']}
                WHERE C.{map_cab['empresa']} IN ({placeholders_emp})
                  AND C.{map_cab['ejercicio']} = ?
                  AND {fact_cond}
            """
            params = tuple(emp_candidates + [ejercicio])
            cursor.execute(sql_lines, params)
            row = cursor.fetchone()
            lineas_count = int(row[0] or 0) if row else 0
            total_val = row[1] if row else 0
            try:
                import decimal
                if isinstance(total_val, decimal.Decimal):
                    total_val = float(total_val)
            except:
                pass
            total_val = float(total_val or 0.0)
            sql_headers = f"""
                SELECT COUNT(*) as cnt
                FROM {tab_cab} C
                WHERE C.{map_cab['empresa']} IN ({placeholders_emp})
                  AND C.{map_cab['ejercicio']} = ?
                  AND {fact_cond}
            """
            cursor.execute(sql_headers, params)
            cab_row = cursor.fetchone()
            albaranes_count = int(cab_row[0] or 0) if cab_row else 0
            return {
                'status': 'ok',
                'empresa': empresa,
                'ejercicio': ejercicio,
                'albaranes_count': albaranes_count,
                'lineas_count': lineas_count,
                'importe_bruto_total': round(total_val, 2)
            }
        finally:
            try:
                cursor.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
