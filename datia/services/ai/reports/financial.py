# datia/services/ai/reports/financial.py

import json
import logging
from datia.services.ai.prompts.financial_stability import FINANCIAL_STABILITY_PROMPT
from datia.factories import ServiceFactory

logger = logging.getLogger(__name__)

class FinancialReportGenerator:
    """
    Generador especializado para Informes Financieros de Estabilidad.
    Implementa la lógica de 'Deep Dive' solicitada.
    """

    def generate(self, context: dict, ejercicio: int, model: str = None, force_fallback: bool = False, role: str = None, req_id: str = None) -> dict:
        """
        Genera el informe HTML utilizando el contexto financiero.
        Retorna un diccionario con {html, model_used, status}.
        """
        # 1. Preparar Datos para el Prompt
        # Serializamos el contexto a JSON String, limitando longitud si es necesario
        try:
            summary_json = self._summarize_context_for_llm(context, ejercicio)
            json_str = json.dumps(summary_json, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error construyendo resumen: {e}")
            optimized_context = self._optimize_context_for_llm(context)
            json_str = json.dumps(optimized_context, ensure_ascii=False, indent=2)

        # 2. Construir Prompt
        prompt = FINANCIAL_STABILITY_PROMPT.format(json_data=json_str[:6000])
        if role:
            prompt = f"Rol: {role}.\n" + prompt
        try:
            derived_sections = self._render_derived_sections(json.loads(json_str))
        except Exception:
            derived_sections = ""

        # 3. Selección de Modelo
        selected_model = model
        llm = ServiceFactory.get_report_llm_service(kind="financiera")
        
        if not selected_model and not force_fallback:
            try:
                if hasattr(llm, "list_models") and hasattr(llm.__class__, "select_preferred_model"):
                    available = llm.list_models()
                    selected_model = llm.__class__.select_preferred_model('financiera', available)
                if not selected_model and model:
                    selected_model = model
            except:
                selected_model = getattr(llm, "model", None) or model or 'qwen2.5:14b-instruct-q4_k_m'

        # 4. Inferencia
        if not force_fallback:
            try:
                logger.info(f"Generando Informe Financiero con modelo: {selected_model}")
                deadline_val = 480
                try:
                    if selected_model and 'qwen3' in selected_model:
                        deadline_val = 1200
                    elif selected_model and 'qwen2.5:14b' in selected_model:
                        deadline_val = 900
                    elif selected_model and 'qwen2.5:7b' in selected_model:
                        deadline_val = 600
                except Exception:
                    pass
                res = llm.generate_text_with_policy(
                    prompt=prompt,
                    kind='financiera',
                    requested_model=selected_model,
                    deadline=deadline_val,
                    req_id=req_id,
                    prefer_no_stream=True,
                    allow_degrade=True
                )
                
                if res.get("status") == "ok":
                    html_out = self._ensure_sections(res.get("text", ""), derived_sections)
                    return {
                        "html": html_out,
                        "model_used": res.get("model"),
                        "selected_model": selected_model,
                        "status": "success",
                        "reason": None
                    }
            except Exception as e:
                logger.error(f"Error en inferencia LLM: {e}")
                # Fallthrough to fallback

        # 5. Fallback (Reglas deterministas)
        logger.warning("Usando Fallback Determinista para Informe Financiero")
        fallback_html = self._build_deterministic_report(context, ejercicio)
        try:
            fallback_html = self._ensure_sections(fallback_html, derived_sections)
        except Exception:
            pass
        return {
            "html": fallback_html,
            "model_used": "fallback_algorithm",
            "selected_model": selected_model,
            "status": "success",
            "reason": (locals().get('res', {}) or {}).get("reason") or "fallback"
        }

    def _optimize_context_for_llm(self, context: dict) -> dict:
        """Limpia el contexto para que el LLM se centre en lo importante."""
        # Clonamos superficialmente
        c = context.copy()
        # Mantenemos kpis_globales, balance_situacion, tesoreria summary
        # Si 'series_mensuales' es muy grande, quizás resumir?
        # De momento pasamos todo, el contexto financiero suele ser pequeño (<50KB)
        return c

    def _summarize_context_for_llm(self, context: dict, ejercicio: int) -> dict:
        emb = None
        try:
            emb = ServiceFactory.get_embedding_service()
        except Exception:
            emb = None
        meta = (context.get("meta") or {})
        empresa_id = meta.get("empresa_id") or ""
        def as_dict(x):
            if isinstance(x, dict): return x
            if isinstance(x, list):
                for it in x:
                    if isinstance(it, dict): return it
                return {}
            return {}
        kpis = as_dict(context.get("kpis_globales"))
        pl = as_dict(context.get("pl_analisis"))
        tes = as_dict(context.get("tesoreria"))
        bal = as_dict(context.get("balance_situacion"))
        ratios = as_dict(bal.get("ratios"))
        sen = context.get('tendencias_anomalias') or context.get('alertas_sistema') or {}
        if not isinstance(sen, dict):
            if isinstance(sen, list): sen = {"items": sen[:5]}
            else: sen = {}
        def num(x):
            try:
                if x is None: return None
                return float(str(x).replace(',', '.'))
            except Exception:
                return None
        def add(a, b):
            return (a + b) if (a is not None and b is not None) else None
        def sub(a, b):
            return (a - b) if (a is not None and b is not None) else None
        def div(a, b):
            try:
                if a is None or b is None: return None
                if isinstance(b, (int, float)) and b == 0: return None
                return a / b
            except Exception:
                return None
        def fmtn(x, nd=2):
            try:
                if x is None: return "—"
                return f"{float(x):,.{nd}f}"
            except Exception:
                return "—"
        ventas = num(kpis.get('ventas'))
        ebitda = num(kpis.get('ebitda'))
        margen_pct = num(kpis.get('margen_op_pct'))
        liquidez = num(ratios.get('liquidez') or tes.get('liquidez') or tes.get('ratio_liquidez'))
        solvencia = num(ratios.get('solvencia') or bal.get('solvencia') or bal.get('ratio_solvencia'))
        activo_corr = num(bal.get('activo_corriente'))
        activo_no_corr = num(bal.get('activo_no_corriente'))
        pasivo_corr = num(bal.get('pasivo_corriente'))
        pasivo_no_corr = num(bal.get('pasivo_no_corriente'))
        pn = num(bal.get('patrimonio_neto'))
        activo_total = add(activo_corr, activo_no_corr)
        if activo_total is None:
            activo_total = num(bal.get('activo_total'))
        deuda_total = num(tes.get('deuda_total') or bal.get('deuda_total'))
        endeudamiento = div(deuda_total, activo_total)
        fondo_maniobra = sub(activo_corr, pasivo_corr)
        rot_activos = div(ventas, activo_total)
        gastos_int = num(pl.get('gastos_intereses') or pl.get('intereses'))
        cob_int = div(ebitda, gastos_int)
        dso = None
        dio = None
        dpo = None
        clientes = num(bal.get('clientes') or bal.get('cuentas_por_cobrar') or bal.get('deudores'))
        existencias = num(bal.get('existencias') or bal.get('inventarios'))
        proveedores = num(bal.get('proveedores') or bal.get('cuentas_por_pagar') or bal.get('acreedores'))
        ventas_diarias = div(ventas, 365.0)
        coste_total = num(pl.get('costes'))
        coste_diario = div(coste_total, 365.0)
        compras_diarias = coste_diario
        if clientes is not None and ventas_diarias and ventas_diarias != 0:
            dso = div(clientes, ventas_diarias)
        if existencias is not None and coste_diario and coste_diario != 0:
            dio = div(existencias, coste_diario)
        if proveedores is not None and compras_diarias and compras_diarias != 0:
            dpo = div(proveedores, compras_diarias)
        if dso is None:
            dso = num(tes.get('periodo_medio_cobro_dias') or tes.get('dso'))
        if dpo is None:
            dpo = num(tes.get('periodo_medio_pago_dias') or tes.get('dpo'))
        trimestres = {}
        sm = as_dict(context.get('series_mensuales') or context.get('mensual') or context.get('series'))
        def _to12(vals):
            if isinstance(vals, list) and len(vals) >= 12:
                return [num(v) for v in vals[:12]]
            if isinstance(vals, dict):
                arr = []
                for i in range(1,13):
                    v = vals.get(str(i)) or vals.get(i) or vals.get(f"m{i}") or 0
                    arr.append(num(v))
                return arr
            return None
        ventas_m = _to12(sm.get('ventas') or sm.get('ingresos') or sm.get('ventas_mensuales') or sm.get('ventas_por_mes') or [])
        margen_m = _to12(sm.get('margen') or sm.get('margen_pct') or sm.get('margen_mensual') or [])
        ebitda_m = _to12(sm.get('ebitda') or sm.get('ebitda_mensual') or [])
        def _qsum(arr, qi):
            if not arr: return None
            idx = (qi-1)*3
            slice_vals = [v for v in arr[idx:idx+3] if v is not None]
            if not slice_vals:
                return None
            return sum(slice_vals)
        def _qavg(arr, qi):
            if not arr: return None
            idx = (qi-1)*3
            slice_vals = [v for v in arr[idx:idx+3] if v is not None]
            if not slice_vals:
                return None
            return (sum(slice_vals) / float(len(slice_vals)))
        if ventas_m:
            trimestres['ventas'] = {"Q1": _qsum(ventas_m,1), "Q2": _qsum(ventas_m,2), "Q3": _qsum(ventas_m,3), "Q4": _qsum(ventas_m,4)}
            est_list_q = context.get('estacionalidad')
            y12_q = None
            if isinstance(est_list_q, list) and est_list_q:
                y_arr_q = []
                for i in range(12):
                    if i < len(est_list_q) and isinstance(est_list_q[i], dict):
                        y_arr_q.append(num(est_list_q[i].get('yoy_pct')))
                    else:
                        y_arr_q.append(None)
                y12_q = y_arr_q
            if y12_q:
                def _qs_y(v):
                    def _avg_safe(xs):
                        vals = [x for x in xs if x is not None]
                        return (sum(vals) / float(len(vals))) if vals else None
                    return [_avg_safe(v[0:3]), _avg_safe(v[3:6]), _avg_safe(v[6:9]), _avg_safe(v[9:12])]
                yqs_q = _qs_y(y12_q)
                trimestres['ventas_yoy_pct'] = {
                    "Q1": yqs_q[0],
                    "Q2": yqs_q[1],
                    "Q3": yqs_q[2],
                    "Q4": yqs_q[3]
                }
        if margen_m:
            trimestres['margen'] = {"Q1": _qavg(margen_m,1), "Q2": _qavg(margen_m,2), "Q3": _qavg(margen_m,3), "Q4": _qavg(margen_m,4)}
        if ebitda_m:
            trimestres['ebitda'] = {"Q1": _qsum(ebitda_m,1), "Q2": _qsum(ebitda_m,2), "Q3": _qsum(ebitda_m,3), "Q4": _qsum(ebitda_m,4)}
        if not trimestres.get('ventas'):
            est_list = context.get('estacionalidad')
            s12 = None
            y12 = None
            if isinstance(est_list, list) and est_list:
                s_arr = []
                y_arr = []
                for i in range(12):
                    if i < len(est_list) and isinstance(est_list[i], dict):
                        s_arr.append(num(est_list[i].get('share_pct')))
                        y_arr.append(num(est_list[i].get('yoy_pct')))
                    else:
                        s_arr.append(None)
                        y_arr.append(None)
                s12 = s_arr
                y12 = y_arr
            if s12:
                def _qs(v):
                    def _sum_safe(xs):
                        vals = [x for x in xs if x is not None]
                        return sum(vals) if vals else None
                    return [_sum_safe(v[0:3]), _sum_safe(v[3:6]), _sum_safe(v[6:9]), _sum_safe(v[9:12])]
                qs = _qs(s12)
                if ventas is not None:
                    trimestres['ventas'] = {
                        "Q1": (ventas*(qs[0]/100.0) if qs[0] is not None else None),
                        "Q2": (ventas*(qs[1]/100.0) if qs[1] is not None else None),
                        "Q3": (ventas*(qs[2]/100.0) if qs[2] is not None else None),
                        "Q4": (ventas*(qs[3]/100.0) if qs[3] is not None else None)
                    }
                if y12:
                    yqs = _qs(y12)
                    trimestres['ventas_yoy_pct'] = {
                        "Q1": (yqs[0]/3.0 if yqs[0] is not None else None),
                        "Q2": (yqs[1]/3.0 if yqs[1] is not None else None),
                        "Q3": (yqs[2]/3.0 if yqs[2] is not None else None),
                        "Q4": (yqs[3]/3.0 if yqs[3] is not None else None)
                    }
        if fondo_maniobra is None:
            fm_direct = num(tes.get('fondo_maniobra') or bal.get('fondo_maniobra'))
            fondo_maniobra = fm_direct
        blocks = []
        blocks.append(("kpis", f"Ejercicio {ejercicio}. Ventas {fmtn(ventas)} EUR. EBITDA {fmtn(ebitda)} EUR. Margen Operativo {fmtn(margen_pct)}%"))
        blocks.append(("ratios", f"Liquidez {fmtn(liquidez)}. Solvencia {fmtn(solvencia)}."))
        blocks.append(("ratios_ext", f"Endeudamiento {fmtn(endeudamiento,3)}. Fondo de maniobra {fmtn(fondo_maniobra)} EUR. Rotación de activos {fmtn(rot_activos,3)}. Cobertura de intereses {fmtn(cob_int,3)}. DSO {fmtn(dso,1)} días, DIO {fmtn(dio,1)} días, DPO {fmtn(dpo,1)} días."))
        if pl:
            blocks.append(("pl", f"Ingresos {fmtn(num(pl.get('ingresos')))} EUR. Costes {fmtn(num(pl.get('costes')))} EUR. Resultado {fmtn(num(pl.get('resultado')))} EUR."))
        if tes:
            blocks.append(("tesoreria", f"Deuda total {fmtn(num(tes.get('deuda_total')))} EUR. Caja {fmtn(num(tes.get('caja')))} EUR."))
        if trimestres.get('ventas'):
            vq = trimestres['ventas']
            blocks.append(("trimestres", f"Ventas trimestrales Q1 {fmtn(vq.get('Q1'))}, Q2 {fmtn(vq.get('Q2'))}, Q3 {fmtn(vq.get('Q3'))}, Q4 {fmtn(vq.get('Q4'))}."))
        if isinstance(sen.get("items"), list) and sen["items"]:
            first = sen["items"][0]
            blocks.append(("señales", f"Primera señal: {str(first)[:200]}"))
        scored = []
        import numpy as np
        q_text = "diagnóstico CFO rentabilidad liquidez solvencia EBITDA margen riesgo"
        q_vec = emb.embed_text(q_text) if emb else None
        guides = []
        if emb:
            try:
                emb.ensure_cfo_guide_indexed()
                guides = emb.get_cfo_guides()
            except Exception:
                guides = []
        for name, text in blocks:
            score = 0.0
            if ebitda is not None and ebitda < 0: score += 0.4
            if margen_pct is not None and margen_pct < 5: score += 0.3
            if liquidez is not None and liquidez < 1.2: score += 0.2
            if solvencia is not None and solvencia < 1.5: score += 0.2
            if emb:
                try:
                    v = np.array(emb.embed_text(text))
                    q = np.array(q_vec) if q_vec is not None else v
                    nv = np.linalg.norm(v) or 1.0
                    nq = np.linalg.norm(q) or 1.0
                    sim = float((np.dot(v, q)) / (nv * nq))
                    score += max(0.0, sim * 0.3)
                    # CFO guide boost: max similarity against guide vectors
                    if guides:
                        try:
                            max_guide_sim = 0.0
                            for g in guides:
                                gv = np.array(g['vector'])
                                ng = np.linalg.norm(gv) or 1.0
                                simg = float((np.dot(v, gv)) / (nv * ng))
                                if simg > max_guide_sim:
                                    max_guide_sim = simg
                            score += max(0.0, max_guide_sim * 0.25)
                        except Exception:
                            pass
                    emb.add_embedding(
                        text=text,
                        sql="CONTEXT",
                        metadata={"scope": "datiadb", "label": f"financial_{name}", "empresa": empresa_id, "ejercicio": ejercicio},
                        kind="context",
                        key=f"financial_{name}_{empresa_id}_{ejercicio}"
                    )
                except Exception:
                    pass
            scored.append((score, name, text))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:6]
        summary_text = " | ".join([t for _, _, t in top])
        return {
            "empresa_id": empresa_id,
            "ejercicio": ejercicio,
            "resumen": summary_text,
            "kpis": {"ventas": ventas, "ebitda": ebitda, "margen_op_pct": margen_pct},
            "ratios": {"liquidez": liquidez, "solvencia": solvencia},
            "ratios_ampliados": {
                "endeudamiento": endeudamiento,
                "fondo_maniobra": fondo_maniobra,
                "rotacion_activos": rot_activos,
                "cobertura_intereses": cob_int,
                "DSO": dso, "DIO": dio, "DPO": dpo
            },
            "balance": {
                "activo_corriente": activo_corr,
                "activo_no_corriente": activo_no_corr,
                "pasivo_corriente": pasivo_corr,
                "pasivo_no_corriente": pasivo_no_corr,
                "patrimonio_neto": pn,
                "activo_total": activo_total,
                "deuda_total": deuda_total
            },
            "trimestres": trimestres
        }

    def _build_deterministic_report(self, data_context: dict, ejercicio: int) -> str:
        """
        Generación basada en reglas (sin IA) cuando el LLM falla.
        Se produce un bloque HTML con clases 'story-*' para que use el estilo editorial.
        """
        kpis = data_context.get("kpis_globales") or {}
        ventas = float(kpis.get("ventas", 0) or 0)
        ebitda = float(kpis.get("ebitda", 0) or 0)
        margen = float(kpis.get("margen_op_pct", 0) or 0)
        yoy = float(kpis.get("yoy_pct_global", 0) or 0)
        balance = data_context.get("balance_situacion", {}) or {}
        ratios = balance.get("ratios", {}) or {}
        liquidez = float(ratios.get("liquidez", 0) or 0)
        solvencia = float(ratios.get("solvencia", 0) or 0)
        patrimonio = float((balance.get("totales") or {}).get("patrimonio", 0) or balance.get("patrimonio_neto", 0) or 0)
        est = data_context.get("estacionalidad") or []
        pl_rows = data_context.get("pl_analisis") or []

        def fmt_eur(x):
            try:
                return f"{float(x):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return "—"
        def fmt_pct(x):
            try:
                return f"{float(x):.2f} %".replace(".", ",")
            except Exception:
                return "—"

        # Chips resumen ejecutivo
        chip_yoy = f"<span class='chip'>YoY {fmt_pct(yoy)}</span>" if yoy else ""
        chip_liq = f"<span class='chip{' warn' if liquidez < 1.0 else ''}'>Liquidez {'Riesgo' if liquidez < 1.0 else 'OK'}</span>"
        chip_solv = f"<span class='chip'>Solvencia {fmt_pct(solvencia)}</span>"

        # KPIs
        kpi_html = f"""
        <div class="story-kpi-cards">
          <div class="story-kpi" aria-label="Ventas Totales"><div class="val">{fmt_eur(ventas)}</div><div class="label">Ventas Totales</div></div>
          <div class="story-kpi" aria-label="EBITDA"><div class="val">{fmt_eur(ebitda)}</div><div class="label">EBITDA</div></div>
          <div class="story-kpi" aria-label="Margen Operativo"><div class="val">{fmt_pct(margen)}</div><div class="label">Margen Operativo</div></div>
        </div>
        <div class="story-hint">Crecimiento y rentabilidad operativa en foco</div>
        """

        circ = int(2*3.14159*36)
        dash_liq = int(max(0,min(1,(liquidez or 0)/1.2))*circ)
        dash_solv = int(max(0,min(1,(solvencia or 0)/1.5))*circ)
        gauge_html = f"""
        <section class="gauge-grid" aria-label="Indicadores ejecutivos">
            <div class="gauge">
                <svg viewBox="0 0 100 100" aria-label="Liquidez">
                    <circle class="track" cx="50" cy="50" r="36"></circle>
                    <circle class="progress" cx="50" cy="50" r="36" style="stroke-dasharray:{dash_liq} {circ};"></circle>
                </svg>
                <div>
                    <div class="g-val">{liquidez:.2f}</div>
                    <div class="g-label">Liquidez objetivo 1,20</div>
                </div>
            </div>
            <div class="gauge">
                <svg viewBox="0 0 100 100" aria-label="Solvencia">
                    <circle class="track" cx="50" cy="50" r="36"></circle>
                    <circle class="progress" cx="50" cy="50" r="36" style="stroke-dasharray:{dash_solv} {circ};"></circle>
                </svg>
                <div>
                    <div class="g-val">{solvencia:.2f}</div>
                    <div class="g-label">Solvencia objetivo 1,50</div>
                </div>
            </div>
        </section>
        """

        # Balance
        bal_html = f"""
        <section class="story-balance" aria-label="Solidez del balance y ratios">
          <div class="story-columns">
            <div class="story-column" aria-label="Solvencia"><h3 class="big">{solvencia:.2f}</h3><p class="small">Solvencia</p></div>
            <div class="story-column" aria-label="Liquidez"><h3 class="big">{liquidez:.2f}</h3><p class="small">Liquidez</p></div>
            <div class="story-column" aria-label="Patrimonio Neto"><h3 class="big">{fmt_eur(patrimonio)}</h3><p class="small">Patrimonio Neto</p></div>
          </div>
          <div class="story-chips"><span class="story-chip">Estado editorial</span>{''}</div>
        </section>
        """

        # Estacionalidad (meses clave)
        meses = ["Enero","Abril","Julio","Octubre","Diciembre"]
        idxs = [0,3,6,9,11]
        cards = []
        for i, mi in enumerate(idxs):
            if mi < len(est) and isinstance(est[mi], dict):
                s = est[mi].get("share_pct")
                y = est[mi].get("yoy_pct")
                cards.append(f"<div class='story-season-card'><div class='month'>{meses[i]}</div><div class='kpis'>Cuota {fmt_pct(s)} • YoY {fmt_pct(y)}</div></div>")
        season_html = f"""
        <section class="story-season" aria-label="Estacionalidad y alertas estratégicas">
          <div class="story-season-grid">{''.join(cards)}</div>
        </section>
        """

        # P&L Tabla
        pl_html = ""
        if isinstance(pl_rows, list) and pl_rows:
            def cell(v, pct=False):
                if pct: return fmt_pct(v)
                return fmt_eur(v)
            rows = []
            for r in pl_rows[:10]:
                rows.append(f"<div class='row'><div class='cell'>{r.get('concepto','')}</div><div class='cell right'>{cell(r.get('real'))}</div><div class='cell right'>{cell(r.get('objetivo'))}</div><div class='cell right'>{cell(r.get('desviacion_importe'))}</div><div class='cell right'>{cell(r.get('desviacion_pct'), pct=True)}</div></div>")
            head = "<div class='row head'><div class='cell'>Concepto</div><div class='cell right'>Real</div><div class='cell right'>Objetivo</div><div class='cell right'>Desviación</div><div class='cell right'>Desv. %</div></div>"
            pl_html = f"<section class='story-pl' aria-label='Cuenta de resultados'><div class='story-pl-table'>{head}{''.join(rows)}</div></section>"

        # Gobierno del desempeño y Storytelling
        tes = data_context.get("tesoreria") or {}
        try:
            dso = float(tes.get('periodo_medio_cobro_dias') or tes.get('dso') or 0)
        except Exception:
            dso = 0.0
        try:
            dio = float(tes.get('periodo_medio_almacenamiento_dias') or tes.get('dio') or 0)
        except Exception:
            dio = 0.0
        try:
            dpo = float(tes.get('periodo_medio_pago_dias') or tes.get('dpo') or 0)
        except Exception:
            dpo = 0.0
        ccc = dso + dio - dpo
        gov_html = f"""
        <section class='story-govern' aria-label='Gobierno del desempeño'>
            <div class='gov-grid'>
                <div class='gov-card'>
                    <div class='gov-title'>Caja (CCC)</div>
                    <div class='gov-desc'>Ciclo de conversión de efectivo</div>
                    <div class='gov-kpi'>DSO {dso:.1f} • DIO {dio:.1f} • DPO {dpo:.1f} • CCC {ccc:.1f} días</div>
                    <span class='gov-chip {"warn" if ccc>45 else ""}'>Objetivo CCC ≤ 45 días</span>
                </div>
                <div class='gov-card'>
                    <div class='gov-title'>Rentabilidad</div>
                    <div class='gov-desc'>EBITDA y Margen Operativo</div>
                    <div class='gov-kpi'>EBITDA {fmt_eur(ebitda)} • Margen {fmt_pct(margen)}</div>
                    <span class='gov-chip {"warn" if ebitda<0 else ""}'>Objetivo EBITDA ≥ 0</span>
                </div>
                <div class='gov-card'>
                    <div class='gov-title'>Solidez</div>
                    <div class='gov-desc'>Liquidez y Solvencia</div>
                    <div class='gov-kpi'>Liquidez {liquidez:.2f} • Solvencia {solvencia:.2f}</div>
                    <span class='gov-chip {"warn" if (liquidez<1.2 or solvencia<1.5) else ""}'>Objetivo L≥1,20 • S≥1,50</span>
                </div>
            </div>
        </section>
        """
        acts_html = f"""
        <section class="story-acts" aria-label="Storytelling financiero">
            <div class="story-act">
                <div class="story-act-title">Contexto</div>
                <div class="story-act-text">El ejercicio {ejercicio} cierra con ventas de {fmt_eur(ventas)} y un margen operativo de {fmt_pct(margen)}. El EBITDA asciende a {fmt_eur(ebitda)}.</div>
                <div class="story-act-chips">
                    <span class="story-act-chip">Patrimonio Neto {fmt_eur(patrimonio)}</span>
                    <span class="story-act-chip">Liquidez {liquidez:.2f}</span>
                    <span class="story-act-chip">Solvencia {solvencia:.2f}</span>
                </div>
            </div>
            <div class="story-act">
                <div class="story-act-title">Conflicto</div>
                <div class="story-act-text">Se identifican factores que presionan la cuenta: {'caída interanual' if yoy<0 else 'crecimiento moderado'} de {fmt_pct(yoy)}, {'tensión de liquidez' if liquidez<1.2 else 'liquidez adecuada'} y focos de riesgo comercial.</div>
                <div class="story-act-chips">
                    <span class="story-act-chip {'warn' if dso>45 else ''}">DSO {dso:.1f} días</span>
                </div>
            </div>
            <div class="story-act">
                <div class="story-act-title">Decisión</div>
                <div class="story-act-text">Priorizar liquidez si {liquidez:.2f} < 1,20; diversificar cartera si concentración > 60%; revisar estructura de costes si el EBITDA es negativo; activar plan de cobro si DSO elevado.</div>
                <div class="story-cta"><button class="story-btn">Plan de acción CFO</button></div>
            </div>
            <div class="story-act">
                <div class="story-act-title">Seguimiento</div>
                <div class="story-act-text">Validar el impacto de las medidas con tres indicadores clave de control.</div>
                <div class="story-act-chips">
                    <span class="story-act-chip {"warn" if ccc>45 else ""}">CCC {ccc:.1f} ≤ 45</span>
                    <span class="story-act-chip {"warn" if ebitda<0 else ""}">EBITDA {fmt_eur(ebitda)} ≥ 0</span>
                    <span class="story-act-chip {"warn" if (liquidez<1.2 or solvencia<1.5) else ""}">L {liquidez:.2f} / S {solvencia:.2f}</span>
                </div>
            </div>
        </section>
        """
        series = (data_context.get("series_mensuales") or {})
        def mini_spark(arr, neg=False):
            try:
                vals = [float(x or 0) for x in (arr or [])]
                if not vals: return "<div class='mini-spark'></div>"
                m = max([abs(v) for v in vals] + [1.0])
                bars = []
                for v in vals[:12]:
                    h = max(3, int((abs(float(v))/m)*28))
                    cls = "mini-bar neg" if (neg and float(v) < 0) else "mini-bar"
                    bars.append(f"<div class='{cls}' style='height:{h}px'></div>")
                return f"<div class='mini-spark'>{''.join(bars)}</div>"
            except Exception:
                return "<div class='mini-spark'></div>"
        monthly_html = f"""
        <section class='story-monthly' aria-label='Series mensuales'>
            <div class='story-monthly-grid'>
                <div class='monthly-card'><div class='monthly-title'>Ingresos</div>{mini_spark(series.get('ingresos') or series.get('ventas'))}</div>
                <div class='monthly-card'><div class='monthly-title'>EBITDA</div>{mini_spark(series.get('ebitda'), True)}</div>
                <div class='monthly-card'><div class='monthly-title'>Margen %</div>{mini_spark(series.get('margen_pct'), True)}</div>
            </div>
        </section>
        """
        bal_raw = (data_context.get("balance_situacion") or {})
        desg = (bal_raw.get("desglose") or {})
        act = (desg.get("activo") or {})
        pas = (desg.get("pasivo") or {})
        def numf(x):
            try:
                return float(x or 0)
            except Exception:
                return 0.0
        ac = numf(act.get("corriente"))
        anc = numf(act.get("no_corriente"))
        pc = numf(pas.get("corriente"))
        pnc = numf(pas.get("no_corriente"))
        bal_desg_html = ""
        if any([ac, anc, pc, pnc]):
            bal_desg_html = f"<section class='story-ops' aria-label='Desglose Balance'><div class='story-chips'><span class='story-chip'>Activo Corr. {fmt_eur(ac)}</span><span class='story-chip'>Activo No Corr. {fmt_eur(anc)}</span><span class='story-chip'>Pasivo Corr. {fmt_eur(pc)}</span><span class='story-chip'>Pasivo No Corr. {fmt_eur(pnc)}</span></div></section>"
        alerts = data_context.get("alertas_sistema") or data_context.get("tendencias_anomalias") or []
        alerts_html = ""
        if isinstance(alerts, list) and alerts:
            def atext(a):
                if isinstance(a, str): return a
                if isinstance(a, dict): return a.get("title") or a.get("msg") or "Alerta"
                return "Alerta"
            alerts_html = "<section class='story-alerts' aria-label='Alertas del sistema'>" + "".join([f"<div class='story-alert'>{atext(a)}</div>" for a in alerts[:3]]) + "</section>"
        banner_html = f"<section class='story-banner'><div class='story-banner-chips'>{chip_yoy}{chip_liq}{chip_solv}</div></section>"
        html = banner_html + gauge_html + kpi_html + bal_html + season_html + pl_html + gov_html + monthly_html + bal_desg_html + alerts_html + acts_html
        return html

    def _render_derived_sections(self, summary: dict) -> str:
        def fmt_num_es(x, nd=2):
            try:
                s = f"{float(x):,.{nd}f}"
                return s.replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return "—"
        def fmt_eur_es(x):
            try:
                return fmt_num_es(x, 2) + " €"
            except Exception:
                return "—"
        def fmt_pct_es(x):
            try:
                return fmt_num_es(x, 2) + " %"
            except Exception:
                return "—"
        r = (summary.get("ratios_ampliados") or {})
        t = (summary.get("trimestres") or {})
        endeud = r.get("endeudamiento")
        fm = r.get("fondo_maniobra")
        rot = r.get("rotacion_activos")
        cob = r.get("cobertura_intereses")
        dso = r.get("DSO")
        dio = r.get("DIO")
        dpo = r.get("DPO")
        vq = (t.get("ventas") or {})
        mq = (t.get("margen") or {})
        eq = (t.get("ebitda") or {})
        yoy = t.get("ventas_yoy_pct") or {}
        chips = []
        chips.append(f"<span class='story-chip'>Endeudamiento {fmt_num_es(endeud,3)}</span>")
        chips.append(f"<span class='story-chip'>Fondo Maniobra {fmt_eur_es(fm)}</span>")
        chips.append(f"<span class='story-chip'>Rotación Activos {fmt_num_es(rot,3)}</span>")
        chips.append(f"<span class='story-chip'>Cobertura Intereses {fmt_num_es(cob,3)}</span>")
        chips.append(f"<span class='story-chip'>DSO/DIO/DPO {fmt_num_es(dso,1)} / {fmt_num_es(dio,1)} / {fmt_num_es(dpo,1)} días</span>")
        ratios_html = f"<section class='story-ops' aria-label='Ratios ampliados'><div class='story-chips'>{''.join(chips)}</div></section>"
        def fnum(x):
            try:
                return float(x)
            except Exception:
                return 0.0
        qs = ["Q1","Q2","Q3","Q4"]
        max_v = max([abs(fnum(vq.get(q))) for q in qs] + [1.0])
        max_e = max([abs(fnum(eq.get(q))) for q in qs] + [1.0])
        max_m = max([abs(fnum(mq.get(q))) for q in qs] + [1.0])
        cards = []
        for q in qs:
            v = fnum(vq.get(q))
            ebi = fnum(eq.get(q))
            m = fnum(mq.get(q))
            yy = fnum(yoy.get(q))
            pv = max(3, int((abs(v)/max_v)*100))
            pe = max(3, int((abs(ebi)/max_e)*100))
            pm = max(3, int((abs(m)/max_m)*100))
            cards.append(
                f"<div class='story-quarter-card'>"
                f"<div class='q-title'>{q}</div>"
                f"<div class='q-line'>Ventas: {fmt_eur_es(v)}</div>"
                f"<div class='spark'><div class='spark-bar pos' style='width:{pv}%;'></div></div>"
                f"<div class='q-line'>Margen: {fmt_pct_es(m)}</div>"
                f"<div class='spark'><div class='spark-bar {'neg' if m < 0 else 'pos'}' style='width:{pm}%;'></div></div>"
                f"<div class='q-line'>EBITDA: {fmt_eur_es(ebi)}</div>"
                f"<div class='spark'><div class='spark-bar {'neg' if ebi < 0 else 'pos'}' style='width:{pe}%;'></div></div>"
                f"<div class='q-line'>YoY: {fmt_pct_es(yy)}</div>"
                f"</div>"
            )
        trimes_html = f"<section class='story-quarter' aria-label='Resultados Trimestrales'><div class='story-quarter-grid'>{''.join(cards)}</div></section>"
        return ratios_html + "\n" + trimes_html

    def _ensure_sections(self, html: str, derived_sections: str) -> str:
        try:
            has_ratios = ("Ratios ampliados" in (html or ""))
            has_trim = ("Resultados Trimestrales" in (html or ""))
            if has_ratios and has_trim:
                return html
            marker = "</div>"
            if html and ("financial-report" in html):
                idx = html.rfind(marker)
                if idx != -1:
                    return html[:idx] + derived_sections + html[idx:]
            return (html or "") + derived_sections
        except Exception:
            return (html or "") + derived_sections
