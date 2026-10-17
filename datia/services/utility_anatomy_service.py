from typing import Dict, Any, List, Tuple
from django.db.models import Sum, Q
from django.conf import settings
from datia.models.financial import DatiaAcumuladosConta
import math
import os

class UtilityAnatomyService:
    def _quarters(self) -> Dict[int, List[int]]:
        return {1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9], 4: [10, 11, 12]}

    def _fetch_series(self, empresa: int, year: int) -> Dict[str, List[float]]:
        qs = DatiaAcumuladosConta.objects.filter(empresa=empresa, ejercicio=year, periodo__gte=1, periodo__lte=12)
        data = {k: [0.0] * 12 for k in ["ingresos", "costo_ventas", "gastos_admin", "impuestos"]}
        # Extras para alinear utilidad con P&L: personal (64), amort (68), financiero (66-67)
        extras = {"personal": [0.0] * 12, "amort": [0.0] * 12, "financiero": [0.0] * 12}
        def q_prefixes(prefixes: List[str]) -> Q:
            q = Q()
            for pref in prefixes:
                q |= Q(cuenta__startswith=pref)
            return q

        q_ventas70 = q_prefixes(["70"])
        q_otros7279 = q_prefixes(["72", "73", "74", "75", "76", "77", "78", "79"])
        q_compras60 = q_prefixes(["60"])
        q_var61 = q_prefixes(["61"])
        q_var71 = q_prefixes(["71"])
        q_gastos_admin = q_prefixes(["62", "65", "69"])
        q_impuestos = q_prefixes(["63"])
        q_personal = q_prefixes(["64"])
        q_amort = q_prefixes(["68"])
        q_financiero = q_prefixes(["66", "67"])

        rows = list(
            qs.values("periodo")
            .annotate(
                ventas70_d=Sum("debe", filter=q_ventas70),
                ventas70_h=Sum("haber", filter=q_ventas70),
                otros7279_d=Sum("debe", filter=q_otros7279),
                otros7279_h=Sum("haber", filter=q_otros7279),
                compras60_d=Sum("debe", filter=q_compras60),
                compras60_h=Sum("haber", filter=q_compras60),
                var61_d=Sum("debe", filter=q_var61),
                var61_h=Sum("haber", filter=q_var61),
                var71_d=Sum("debe", filter=q_var71),
                var71_h=Sum("haber", filter=q_var71),
                gastos_admin_d=Sum("debe", filter=q_gastos_admin),
                gastos_admin_h=Sum("haber", filter=q_gastos_admin),
                impuestos_d=Sum("debe", filter=q_impuestos),
                impuestos_h=Sum("haber", filter=q_impuestos),
                personal_d=Sum("debe", filter=q_personal),
                personal_h=Sum("haber", filter=q_personal),
                amort_d=Sum("debe", filter=q_amort),
                amort_h=Sum("haber", filter=q_amort),
                financiero_d=Sum("debe", filter=q_financiero),
                financiero_h=Sum("haber", filter=q_financiero),
            )
            .order_by("periodo")
        )

        extras["variacion"] = [0.0] * 12

        for row in rows:
            p = int(row.get("periodo") or 0)
            if p < 1 or p > 12:
                continue
            i = p - 1

            ventas_70 = float(row.get("ventas70_d") or 0.0) - float(row.get("ventas70_h") or 0.0)
            otros_72_79 = float(row.get("otros7279_d") or 0.0) - float(row.get("otros7279_h") or 0.0)
            ingresos = -(ventas_70 + otros_72_79)

            compras = float(row.get("compras60_d") or 0.0) - float(row.get("compras60_h") or 0.0)
            var_61 = float(row.get("var61_d") or 0.0) - float(row.get("var61_h") or 0.0)
            var_71 = float(row.get("var71_d") or 0.0) - float(row.get("var71_h") or 0.0)
            variacion = var_61 + (-var_71)

            gastos_admin = float(row.get("gastos_admin_d") or 0.0) - float(row.get("gastos_admin_h") or 0.0)
            impuestos = float(row.get("impuestos_d") or 0.0) - float(row.get("impuestos_h") or 0.0)
            personal = float(row.get("personal_d") or 0.0) - float(row.get("personal_h") or 0.0)
            amort = float(row.get("amort_d") or 0.0) - float(row.get("amort_h") or 0.0)
            financiero = float(row.get("financiero_d") or 0.0) - float(row.get("financiero_h") or 0.0)

            data["ingresos"][i] = float(abs(ingresos))
            data["costo_ventas"][i] = float(abs(compras or 0.0))
            data["gastos_admin"][i] = float(abs(gastos_admin))
            data["impuestos"][i] = float(abs(impuestos))

            extras["personal"][i] = float(abs(personal))
            extras["amort"][i] = float(abs(amort))
            extras["financiero"][i] = float(abs(financiero))
            extras["variacion"][i] = float(abs(variacion))
        data.update(extras)
        return data

    def _impute_ma3(self, values: List[float]) -> List[float]:
        out = values[:]
        for i, v in enumerate(out):
            if v is None or math.isnan(v):
                a = out[i - 1] if i - 1 >= 0 else 0.0
                b = out[i - 2] if i - 2 >= 0 else 0.0
                c = out[i - 3] if i - 3 >= 0 else 0.0
                out[i] = (a + b + c) / 3.0 if (i - 1 >= 0) else 0.0
        return [float(x) for x in out]

    def _quarter_aggregate(self, series: List[float]) -> List[float]:
        qmap = self._quarters()
        agg = []
        for q in range(1, 5):
            months = qmap[q]
            s = sum(series[m - 1] for m in months)
            agg.append(float(s))
        return agg

    def _common_size(self, ingresos_q: List[float], parts: Dict[str, List[float]]) -> Dict[str, List[float]]:
        res = {}
        for k, vals in parts.items():
            pct = []
            for i in range(4):
                base = ingresos_q[i]
                pct.append(float((vals[i] / base * 100.0) if base else 0.0))
            res[k] = pct
        return res

    def _yoy(self, curr: List[float], prev: List[float], infl: List[float]) -> List[float]:
        out = []
        for i in range(4):
            p = prev[i]
            adj = p * (1.0 + (infl[i] / 100.0))
            c = curr[i]
            v = ((c - adj) / adj * 100.0) if adj else 0.0
            out.append(float(v))
        return out

    def _sigma_outliers(self, vals: List[float]) -> List[bool]:
        if not vals:
            return []
        m = sum(vals) / len(vals)
        s = (sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5
        return [abs(x - m) > 3 * s for x in vals]

    def _inflation_quarter(self, start_year: int, end_year: int) -> Dict[int, List[float]]:
        infl = {}
        for y in range(start_year, end_year + 1):
            infl[y] = [0.0, 0.0, 0.0, 0.0]
        return infl

    def get_anatomy(self, empresa: int, start_year: int, end_year: int, moneda: str = "EUR", region: str = "global") -> Dict[str, Any]:
        years = []
        series_by_year = {}
        for y in range(start_year, end_year + 1):
            raw = self._fetch_series(empresa, y)
            raw["ingresos"] = self._impute_ma3(raw["ingresos"])
            raw["costo_ventas"] = self._impute_ma3(raw["costo_ventas"])
            raw["gastos_admin"] = self._impute_ma3(raw["gastos_admin"])
            raw["impuestos"] = self._impute_ma3(raw["impuestos"])
            # Extras imputación
            raw["personal"] = self._impute_ma3(raw.get("personal", [0.0] * 12))
            raw["amort"] = self._impute_ma3(raw.get("amort", [0.0] * 12))
            raw["financiero"] = self._impute_ma3(raw.get("financiero", [0.0] * 12))
            iq = self._quarter_aggregate(raw["ingresos"])
            cq = self._quarter_aggregate(raw["costo_ventas"])
            gq = self._quarter_aggregate(raw["gastos_admin"])
            tq = self._quarter_aggregate(raw["impuestos"])
            pq = self._quarter_aggregate(raw["personal"])
            aq = self._quarter_aggregate(raw["amort"])
            fq = self._quarter_aggregate(raw["financiero"])
            vq = self._quarter_aggregate(raw.get("variacion", [0.0] * 12))
            ogde = [float(gq[i] + tq[i] + pq[i] + aq[i] + fq[i]) for i in range(4)]
            utilidad = [float(iq[i] + vq[i] - cq[i] - gq[i] - tq[i] - pq[i] - aq[i] - fq[i]) for i in range(4)]
            cs = self._common_size(iq, {"costo_ventas": cq, "gastos_admin": gq, "impuestos": tq, "otros_gastos_exp": ogde, "utilidad_neta": utilidad})
            series_by_year[y] = {"ingresos": iq, "costo_ventas": cq, "gastos_admin": gq, "impuestos": tq, "otros_gastos_exp": ogde, "utilidad_neta": utilidad, "variacion": vq, "personal": pq, "amort": aq, "financiero": fq, "common_size": cs}
            years.append(y)
        infl = self._inflation_quarter(start_year, end_year)
        yoy = {}
        for y in years:
            py = y - 1
            if py in series_by_year:
                curr = series_by_year[y]
                prev = series_by_year[py]
                yoy[y] = {
                    "ingresos": self._yoy(curr["ingresos"], prev["ingresos"], infl[y]),
                    "costo_ventas": self._yoy(curr["costo_ventas"], prev["costo_ventas"], infl[y]),
                    "gastos_admin": self._yoy(curr["gastos_admin"], prev["gastos_admin"], infl[y]),
                    "impuestos": self._yoy(curr["impuestos"], prev["impuestos"], infl[y]),
                    "utilidad_neta": self._yoy(curr["utilidad_neta"], prev["utilidad_neta"], infl[y]),
                }
        bench = {}
        for k in ["ingresos", "costo_ventas", "gastos_admin", "impuestos", "utilidad_neta"]:
            vals = []
            for y in years:
                vals += series_by_year[y][k]
            avg = sum(vals) / len(vals) if vals else 0.0
            bench[k] = avg
        outliers = {}
        for y in years:
            outliers[y] = {}
            for k in ["ingresos", "costo_ventas", "gastos_admin", "impuestos", "utilidad_neta"]:
                outliers[y][k] = self._sigma_outliers(series_by_year[y][k])
        return {"years": years, "data": series_by_year, "yoy": yoy, "benchmarks": bench, "outliers": outliers, "moneda": moneda, "region": region}

    def get_forecast(self, empresa: int, start_year: int, end_year: int) -> Dict[str, Any]:
        months_ds = []
        months_vals = []
        util_quarters: Dict[int, List[float]] = {}
        s_year = int(start_year)
        e_year = int(end_year)
        for y in range(s_year, e_year + 1):
            s = self._fetch_series(empresa, y)
            util_y = [float(s["ingresos"][i] + s.get("variacion",[0.0]*12)[i] - s["costo_ventas"][i] - s["gastos_admin"][i] - s["impuestos"][i] - s.get("personal",[0.0]*12)[i] - s.get("amort",[0.0]*12)[i] - s.get("financiero",[0.0]*12)[i]) for i in range(12)]
            months_vals.extend(util_y)
            months_ds.extend([(y, m + 1) for m in range(12)])
            iq = self._quarter_aggregate(s["ingresos"])
            cq = self._quarter_aggregate(s["costo_ventas"])
            gq = self._quarter_aggregate(s["gastos_admin"])
            tq = self._quarter_aggregate(s["impuestos"])
            pq = self._quarter_aggregate(s.get("personal",[0.0]*12))
            aq = self._quarter_aggregate(s.get("amort",[0.0]*12))
            fq = self._quarter_aggregate(s.get("financiero",[0.0]*12))
            vq = self._quarter_aggregate(s.get("variacion",[0.0]*12))
            util_q = [float(iq[i] + vq[i] - cq[i] - gq[i] - tq[i] - pq[i] - aq[i] - fq[i]) for i in range(4)]
            util_quarters[y] = util_q
        try:
            import pandas as pd
            try:
                from prophet import Prophet
            except Exception:
                from fbprophet import Prophet
            ds_vals = [pd.Timestamp(year=ym[0], month=ym[1], day=1) for ym in months_ds]
            df = pd.DataFrame({"ds": ds_vals, "y": months_vals, "inflacion": [0.0] * len(months_vals)})
            m = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False, interval_width=0.95)
            m.add_regressor("inflacion")
            m.fit(df)
            fut_ds = [pd.Timestamp(year=e_year + 1, month=i + 1, day=1) for i in range(12)]
            fut = pd.DataFrame({"ds": fut_ds, "inflacion": [0.0] * 12})
            fcst = m.predict(fut)
            qmap = {1: [0, 1, 2], 2: [3, 4, 5], 3: [6, 7, 8], 4: [9, 10, 11]}
            fc = []
            for q, idxs in qmap.items():
                y = sum(float(fcst["yhat"].iloc[i]) for i in idxs)
                low = sum(float(fcst["yhat_lower"].iloc[i]) for i in idxs)
                high = sum(float(fcst["yhat_upper"].iloc[i]) for i in idxs)
                fc.append({"quarter": q, "utilidad_neta": y, "low": low, "high": high})
            mae = 0.0
            rmse = 0.0
            return {"year": e_year + 1, "forecast": fc, "metrics": {"mae": mae, "rmse": rmse}}
        except Exception:
            # Fallback sin Prophet: proyección por crecimiento medio YoY por trimestre
            util_e = util_quarters.get(e_year)
            if not util_e:
                s_last = self._fetch_series(empresa, e_year)
                iq = self._quarter_aggregate(s_last["ingresos"])
                cq = self._quarter_aggregate(s_last["costo_ventas"])
                gq = self._quarter_aggregate(s_last["gastos_admin"])
                tq = self._quarter_aggregate(s_last["impuestos"])
                pq = self._quarter_aggregate(s_last.get("personal",[0.0]*12))
                aq = self._quarter_aggregate(s_last.get("amort",[0.0]*12))
                fq = self._quarter_aggregate(s_last.get("financiero",[0.0]*12))
                vq = self._quarter_aggregate(s_last.get("variacion",[0.0]*12))
                util_e = [float(iq[i] + vq[i] - cq[i] - gq[i] - tq[i] - pq[i] - aq[i] - fq[i]) for i in range(4)]
            fc = []
            import statistics
            for i in range(4):
                # Crecimientos YoY por trimestre i
                growths = []
                for y in range(s_year + 1, e_year + 1):
                    prev = util_quarters.get(y - 1, [0.0, 0.0, 0.0, 0.0])[i]
                    curr = util_quarters.get(y, [0.0, 0.0, 0.0, 0.0])[i]
                    denom = abs(prev) if abs(prev) > 1e-6 else 1.0
                    growths.append((curr - prev) / denom)
                avg_g = statistics.mean(growths) if growths else 0.0
                base = util_e[i]
                proj = base * (1.0 + avg_g)
                # Banda basada en desviación estándar del histórico del trimestre
                hist_vals = [util_quarters.get(y, [0.0, 0.0, 0.0, 0.0])[i] for y in range(s_year, e_year + 1)]
                sigma = statistics.pstdev(hist_vals) if len(hist_vals) > 1 else abs(proj) * 0.1
                low = proj - sigma
                high = proj + sigma
                fc.append({"quarter": i + 1, "utilidad_neta": proj, "low": low, "high": high})
            return {"year": e_year + 1, "forecast": fc, "metrics": {"mae": 0.0, "rmse": 0.0}}
