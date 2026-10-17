from typing import Dict, Any, List
from django.db.models import Sum
from datia.models.financial import DatiaAcumuladosConta
from datia.services.analysis_service import AnalysisService
from datia.services.financial_service import FinancialService

class PredictiveService:
    def _monthly_series(self, empresa: int, ejercicio: int, prefix: str) -> List[float]:
        rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith=prefix, periodo__gt=0, periodo__lte=12
        ).values('periodo').annotate(total=Sum('saldo')).order_by('periodo')
        series = [0.0] * 12
        for r in rows:
            idx = r['periodo'] - 1
            val = float(r['total'] or 0.0)
            if prefix == '7':
                val = abs(val)
            series[idx] = val if 0 <= idx < 12 else 0.0
        return series

    def _annual_total(self, empresa: int, ejercicio: int, prefix: str) -> float:
        total = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, cuenta__startswith=prefix, periodo__gt=0, periodo__lte=12
        ).aggregate(t=Sum('saldo'))['t'] or 0.0
        if prefix == '7':
            return float(abs(total))
        return float(total)

    def _calc_cagr(self, start_val: float, end_val: float, n_years: int) -> float:
        if start_val <= 0 or n_years <= 0:
            return 0.0
        try:
            return (end_val / start_val) ** (1.0 / n_years) - 1.0
        except Exception:
            return 0.0

    def get_eda(self, empresa: int, start_year: int, end_year: int) -> Dict[str, Any]:
        n_years = max(0, int(end_year) - int(start_year))
        inc_start = self._annual_total(empresa, start_year, '7')
        inc_end = self._annual_total(empresa, end_year, '7')
        gas_start = self._annual_total(empresa, start_year, '6')
        gas_end = self._annual_total(empresa, end_year, '6')
        cagr_inc = self._calc_cagr(inc_start, inc_end, n_years)
        cagr_gas = self._calc_cagr(gas_start, gas_end, n_years)
        monthly_inc = self._monthly_series(empresa, end_year, '7')
        monthly_gas = self._monthly_series(empresa, end_year, '6')
        anomalies = AnalysisService.detect_anomalies(monthly_inc, method='zscore', threshold=2.0)
        return {
            "status": "ok",
            "years": {"start": int(start_year), "end": int(end_year), "n": n_years},
            "cagr": {"ingresos": cagr_inc, "gastos": cagr_gas},
            "monthly": {"ingresos": monthly_inc, "gastos": monthly_gas},
            "anomalies": anomalies,
        }

    def _cmgr(self, arr: List[float]) -> float:
        if not arr or len(arr) < 2:
            return 0.0
        first = arr[0]
        last = arr[-1]
        if first <= 0:
            return 0.0
        n = len(arr) - 1
        try:
            return (last / first) ** (1.0 / n) - 1.0
        except Exception:
            return 0.0

    def _weighted_mean(self, arr: List[float]) -> float:
        if not arr:
            return 0.0
        w = 0.0
        s = 0.0
        for i, v in enumerate(arr):
            weight = i + 1
            w += weight
            s += v * weight
        return s / w if w else 0.0

    def _build_projection(self, base_inc: float, base_gas: float, h: int, cmgr_inc: float, cmgr_gas: float, scenario: str) -> List[Dict[str, Any]]:
        out = []
        for i in range(1, h + 1):
            inc = base_inc * ((1.0 + (cmgr_inc or 0.0)) ** i)
            if scenario == 'pesimista':
                inc = inc * 0.9
                gas = base_gas
            else:
                gas = base_gas * ((1.0 + (cmgr_gas or 0.0)) ** i)
            res = inc - gas
            out.append({"mes": i, "ingresos": float(inc), "gastos": float(gas), "resultado": float(res)})
        return out

    def _compute_liquidez(self, balances: List[Dict[str, Any]], cash_start: float, ac_base: float, pc_base: float) -> List[Dict[str, Any]]:
        out = []
        for i, x in enumerate(balances):
            delta = float(x.get('balance', cash_start)) - cash_start
            ratio = (ac_base + delta) / (pc_base or 1.0)
            out.append({"mes": i + 1, "ratio": float(ratio)})
        return out

    def get_forecast(self, empresa: int, start_year: int, end_year: int, horizon: int = 4, scenario: str = 'base') -> Dict[str, Any]:
        end_year = int(end_year)
        last_months_inc = self._monthly_series(empresa, end_year, '7')[-6:]
        last_months_gas = self._monthly_series(empresa, end_year, '6')[-6:]
        cmgr_inc = self._cmgr(last_months_inc)
        cmgr_gas = self._cmgr(last_months_gas)
        base_inc = self._weighted_mean(last_months_inc)
        base_gas = self._weighted_mean(last_months_gas)
        projection = self._build_projection(base_inc, base_gas, int(horizon), cmgr_inc, cmgr_gas, scenario)
        fin = FinancialService()
        bs = fin.get_balance_summary(empresa, end_year)
        ac_base = float(bs.get('desglose', {}).get('activo', {}).get('corriente', 0.0))
        pc_base = float(bs.get('desglose', {}).get('pasivo', {}).get('corriente', 1.0)) or 1.0
        snap = fin.get_snapshot(empresa, end_year)
        cash_start = float(snap.get('ingresos', 0.0)) - float(snap.get('gastos', 0.0))
        tre = fin.get_treasury_forecast(empresa, end_year)
        balances = []
        if tre and isinstance(tre.get('forecast'), list):
            for x in tre['forecast'][:int(horizon)]:
                balances.append({"balance": float(x.get('balance', cash_start))})
        else:
            for _ in range(int(horizon)):
                balances.append({"balance": cash_start})
        liquidez = self._compute_liquidez(balances, cash_start, ac_base, pc_base)
        risk_month = None
        for item in liquidez:
            if item['ratio'] < 1.5 and risk_month is None:
                risk_month = item['mes']
        def _trend_dir(arr: List[float]) -> str:
            if not arr or len(arr) < 2:
                return 'flat'
            n = len(arr)
            x_sum = 0.0
            y_sum = 0.0
            xy_sum = 0.0
            xx_sum = 0.0
            for i in range(n):
                x = float(i)
                y = float(arr[i] or 0.0)
                x_sum += x
                y_sum += y
                xy_sum += x * y
                xx_sum += x * x
            denom = (n * xx_sum) - (x_sum * x_sum)
            slope = 0.0
            if denom != 0.0:
                slope = ((n * xy_sum) - (x_sum * y_sum)) / denom
            mean = y_sum / n if n else 0.0
            thr = abs(mean) * 0.05
            if slope > thr:
                return 'up'
            if slope < -thr:
                return 'down'
            return 'flat'
        inc_dir = _trend_dir(last_months_inc)
        gas_dir = _trend_dir(last_months_gas)
        margin_status = 'estable'
        eps = 0.002
        if (cmgr_gas or 0.0) > (cmgr_inc or 0.0) + eps:
            margin_status = 'en erosión'
        elif (cmgr_inc or 0.0) > (cmgr_gas or 0.0) + eps:
            margin_status = 'en mejora'
        burns = []
        if tre and isinstance(tre.get('forecast'), list):
            for i, x in enumerate(tre['forecast'][:int(horizon)]):
                inflow = float(x.get('inflow', 0.0))
                outflow = float(x.get('outflow', 0.0))
                if inflow > 0.0 or outflow > 0.0:
                    burns.append(max(0.0, outflow - inflow))
                else:
                    res = projection[i]['resultado'] if i < len(projection) else 0.0
                    burns.append(abs(res) if res < 0.0 else 0.0)
        else:
            for i in range(int(horizon)):
                res = projection[i]['resultado'] if i < len(projection) else 0.0
                burns.append(abs(res) if res < 0.0 else 0.0)
        burn_rate = sum(burns) / len(burns) if burns else 0.0
        runway = int(cash_start / burn_rate) if burn_rate > 0.0 else None
        text = f"Ingresos CMGR {round((cmgr_inc or 0.0) * 100, 2)}% y Gastos CMGR {round((cmgr_gas or 0.0) * 100, 2)}%."
        if risk_month:
            text += f" Liquidez proyectada bajo 1,5 en Mes {risk_month}."
        else:
            text += " Liquidez proyectada estable ≥1,5."
        dir_map = {'up': '↑', 'down': '↓', 'flat': '→'}
        text += f" Tendencia: Ingresos {dir_map.get(inc_dir, '→')} / Gastos {dir_map.get(gas_dir, '→')}."
        text += f" Margen: {margin_status}."
        if burn_rate > 0.0:
            text += f" Burn Rate {round(burn_rate, 2)} €/mes"
        if runway is not None:
            text += f" · Runway {runway} meses"
        return {
            "status": "ok",
            "horizon": int(horizon),
            "scenario": scenario,
            "projection": projection,
            "liquidez": liquidez,
            "alerts": {"risk_month": risk_month},
            "summary": text,
            "trend": {"ingresos": inc_dir, "gastos": gas_dir},
            "margin_status": margin_status,
            "burn_rate": burn_rate,
            "runway_months": runway,
        }
