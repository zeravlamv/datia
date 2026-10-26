
from typing import Dict, List, Any, Optional
from datia.services.ai.language import LanguageService
from datia.services.ai.prediction_service import PredictionService

class ResponseFormatter:
    """
    Transforms Raw DB Rows into UI Payload (Text, Chart, Table).
    Decouples presentation logic from business logic.
    """
    
    MONTHS = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    @staticmethod
    def format_response(match_meta: Dict, rows: List[Dict], ejercicio: int, limit: int = 20, lang: str = 'es') -> Dict:
        lectura = match_meta.get('lectura') if isinstance(match_meta, dict) else None
        periodo = lectura.get('periodo') if isinstance(lectura, dict) else None
        if isinstance(periodo, list) and periodo:
            try:
                ejercicio = int(periodo[-1])
            except (TypeError, ValueError):
                pass
        response_type = match_meta.get('type', 'text')
        label = match_meta.get('label', 'Resultados')
        
        if not rows and response_type == 'listado':
            return {
                'text': 'No hay registros.',
                'answer': 'No hay registros.',
                'type': 'report',
                'sql': match_meta.get('sql'),
                'source': match_meta.get('source'),
                'completo': bool(match_meta.get('completo')),
                'kpis': [{'label': 'Registros', 'value': 0, 'suffix': 'uds'}],
                'table': {
                    'title': label,
                    'columns': match_meta.get('titulos') or [],
                    'rows': [],
                },
            }

        if not rows:
            # [FIX] Improve UX for "Auto-Training" generic labels
            display_label = label
            if "Aprendizaje Automático" in label or "Auto-Training" in label:
                display_label = "esta consulta"
            
            msg = LanguageService.get_text('no_data', lang, label=display_label, ejercicio=ejercicio)
            
            # [NEW] Return special type to allow frontend to offer "Force Generation"
            return {
                "text": msg,
                "answer": msg, # [FIX] Map text to answer for frontend compatibility
                "sql": match_meta['sql'], 
                "source": match_meta.get('source'),
                "type": "no_data_option" 
            }

        count_only = ResponseFormatter._count_only_answer(rows, match_meta)
        if count_only:
            return count_only

        if response_type == 'listado':
            return ResponseFormatter._format_listado(label, rows, match_meta)

        if response_type == 'cantidad':
            return ResponseFormatter._format_cantidad(rows, match_meta, ejercicio)

        # A) CARD / RESUMEN
        if response_type == 'card':
            return ResponseFormatter._format_card(label, rows[0] if rows else {}, match_meta['sql'], lang, match_meta)

        # B) CHART (Line/Bar)
        elif response_type == 'chart':
            if match_meta.get('chart_type') == 'line':
                return ResponseFormatter._format_line_chart(label, ejercicio, rows, match_meta['sql'], lang, match_meta)
            elif match_meta.get('chart_type') == 'bar':
                 # Use table formatter which generates Bar Chart config
                 res = ResponseFormatter._format_table(label, ejercicio, rows, match_meta, limit, lang)
                 # Keep type='table' because ia.js supports it and renders both Table+Chart.
                 # type='chart' is not implemented in ia.js and breaks rendering.
                 res['type'] = 'table' 
                 return res

        # C) TABLE
        elif response_type == 'table':
            return ResponseFormatter._format_table(label, ejercicio, rows, match_meta, limit, lang)

        elif response_type == 'ambiguity_alert':
            return {
                "type": "ambiguity_alert",
                "answer": match_meta.get('text') or label,
                "details": match_meta.get('details'),
                "suggestions": match_meta.get('suggestions') or [],
                "sql": None,
                "source": "ambiguity"
            }

        msg = LanguageService.get_text('unknown_format', lang)
        return {"text": msg, "answer": msg, "sql": match_meta['sql']}

    @staticmethod
    def _format_listado(label: str, rows: List[Dict], match_meta: Dict) -> Dict:
        columnas = match_meta.get('columnas') or list(rows[0].keys())
        titulos = match_meta.get('titulos') or columnas
        if len(titulos) != len(columnas):
            titulos = columnas
        completo = bool(match_meta.get('completo'))
        total = len(rows)
        visibles = rows[:10000] if completo and total > 10000 else rows
        tabla = []
        for fila in visibles:
            tabla.append([fila.get(columna) for columna in columnas])
        texto = label
        if completo and total > 10000:
            texto = f'La lista está incompleta. Hay {total} registros y se muestran 10.000. {label}'
        return {
            'text': texto,
            'answer': texto,
            'type': 'report',
            'sql': match_meta.get('sql'),
            'source': match_meta.get('source'),
            'completo': completo,
            'kpis': [{
                'label': 'Registros',
                'value': total,
                'suffix': 'uds',
            }],
            'table': {
                'title': label,
                'columns': titulos,
                'rows': tabla,
            },
            'origen': match_meta.get('origen'),
        }

    @staticmethod
    def _count_only_answer(rows: List[Dict], match_meta: Dict) -> Optional[Dict]:
        amount_keys = {
            'val', 'neto', 'importe', 'importe_neto', 'importe_neto_total',
            'ventas', 'amount', 'sales', 'coste', 'costo',
        }
        for row in rows:
            for key, value in row.items():
                if str(key).lower() in amount_keys and value is not None:
                    return None
        count = None
        for row in rows:
            for key, value in row.items():
                if str(key).lower() in ('registros', 'count', 'conteo') and value is not None:
                    count = value
                    break
        if count is None:
            return None
        try:
            shown = f"{int(count):,}".replace(',', '.')
        except (TypeError, ValueError):
            shown = str(count)
        if match_meta.get('key') == 'conteo':
            msg = f"{match_meta.get('label') or 'Conteo'}: {shown}."
        else:
            msg = f"El resultado es un conteo de {shown} registros. No es el importe del ejercicio."
        salida = {
            "text": msg,
            "answer": msg,
            "sql": match_meta.get('sql'),
            "type": "text",
            "source": match_meta.get('source'),
            "data": rows,
        }
        if isinstance(match_meta.get('origen'), dict):
            salida['origen'] = match_meta['origen']
        return salida

    @staticmethod
    def _format_cantidad(rows: List[Dict], match_meta: Dict, ejercicio: int) -> Dict:
        meta = match_meta.get('intent_meta') or {}
        unidad = meta.get('unidad') or 'unidades'
        producto = meta.get('producto') or ''
        year = meta.get('ejercicio') or ejercicio
        verbo = 'comprado' if meta.get('compras') else 'vendido'
        raw = 0
        if rows:
            lower = {str(clave).lower(): valor for clave, valor in rows[0].items()}
            raw = lower.get('cantidad') or 0
        try:
            numero = f"{float(raw):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        except (TypeError, ValueError):
            numero = str(raw)
        if producto:
            msg = f"En {year} se han {verbo} {numero} {unidad} de {producto}."
        else:
            msg = f"En {year} se han {verbo} {numero} {unidad}."
        return {
            "text": msg,
            "answer": msg,
            "sql": match_meta.get('sql'),
            "type": "text",
            "source": match_meta.get('source'),
        }

    @staticmethod
    def _format_card(label: str, data: Dict, sql: str, lang: str, match_meta: Dict = None) -> Dict:
        # Improved Extraction Logic: Support dynamic keys from LLM (e.g. VentasTotal, Total, Amount)
        
        # 1. Neto/Sales (First Priority). Un cero explícito se conserva.
        neto = None
        keys_neto = ['neto', 'importe', 'val', 'value', 'total', 'ventas', 'ventastotal', 'amount', 'sales', 'sum']
        
        # Case insensitive search
        data_lower = {k.lower(): v for k, v in data.items()}
        
        for k in keys_neto:
            if k in data_lower and data_lower[k] is not None:
                try:
                    neto = float(data_lower[k])
                    break
                except: continue
        
        if neto is None:
            neto = 0.0
            for v in data.values():
                 if isinstance(v, (int, float, str)):
                     try:
                         val = float(v)
                         if val != 0:
                             neto = val
                             break
                     except: continue

        # 2. Coste (Specific)
        coste = 0.0
        keys_coste = ['coste', 'cost', 'costo', 'compra', 'expense']
        for k in keys_coste:
            if k in data_lower and data_lower[k] is not None:
                try:
                    coste = float(data_lower[k])
                    break
                except: continue

        # 3. Ops/Count
        ops = 0
        keys_ops = ['ops', 'operaciones', 'count', 'cantidad', 'pedidos', 'facturas', 'num']
        for k in keys_ops:
            if k in data_lower and data_lower[k] is not None:
                try:
                    ops = int(data_lower[k])
                    break
                except: continue
        
        if ops > 0:
            if ops == 0: ticket = 0
            else: ticket = (neto / ops)
        else:
             ticket = 0

        # Quality Control: Ticket
        ticket_warning = ""
        if neto > 100 and ticket == 0 and ops > 0:
             ticket_warning = f"<br>⚠️ <small>{LanguageService.get_text('generative_error', lang, error='Ticket medio = 0 (Quality Check)')}</small>"
        
        margen_pct = ((neto - coste) / neto * 100) if neto != 0 else 0
        
        # Format text answer using LanguageService
        text_answer = LanguageService.get_text('card_sales', lang, label=label, neto=f"{neto:,.2f}€")
        text_answer += LanguageService.get_text('card_margin', lang, pct=f"{margen_pct:.2f}", val=f"{neto-coste:,.2f}€")
        text_answer += LanguageService.get_text('card_ticket', lang, val=f"{ticket:.2f}€", ops=ops)
        text_answer += ticket_warning
        
        # Methodology Footer
        methodology = f"""
        <div style="margin-top: 15px; font-size: 0.75rem; color: #71717a; border-top: 1px solid #3f3f46; padding-top: 5px;">
            <b>Methodology:</b><br>
            • Margin = (Net Sales - Cost) / Net Sales<br>
            • Ticket = Net Sales / Operations<br>
            • Source: {match_meta.get('source', 'AI Generated')}
        </div>
        """

        html = f'''
         <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
            <div>
                <div style="font-size: 0.8rem; color: #a1a1aa;">Ventas</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #34d399;">{neto:,.2f}€</div>
            </div>
             <div>
                <div style="font-size: 0.8rem; color: #a1a1aa;">Margen %</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #fbbf24;">{margen_pct:.2f}%</div>
            </div>
            <div>
                <div style="font-size: 0.8rem; color: #a1a1aa;">Ticket Medio</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #38bdf8;">{ticket:,.2f}€</div>
            </div>
            <div>
                <div style="font-size: 0.8rem; color: #a1a1aa;">Operaciones</div>
                <div style="font-size: 1.1rem; font-weight: bold; color: #fff;">{ops}</div>
            </div>
         </div>
         {methodology}
        '''
        salida = {
            "text": text_answer + html,
            "answer": text_answer + html, # [FIX] Frontend expects 'answer'
            "sql": sql,
            "type": "text", 
            "data": data,
            "key": match_meta.get('key') if match_meta else None,
            "source": match_meta.get('source') if match_meta else None
        }
        if match_meta and isinstance(match_meta.get('origen'), dict):
            salida['origen'] = match_meta['origen']
        return salida

    @staticmethod
    def _format_line_chart(label: str, ejercicio: int, rows: List[Dict], sql: str, lang: str, match_meta: Dict = None) -> Dict:
        # Check for Multi-Series (Comparison)
        is_comparison = len(rows) > 0 and 'serie' in rows[0]
        
        if is_comparison:
            # --- PIVOT LOGIC ---
            pivoted_data = {}
            series_years = set()
            labels_map = {} # label_key -> label_name
            
            for r in rows:
                lbl_key = r.get('label')
                # Try to resolve month name
                lbl_name = str(lbl_key)
                try:
                    m_idx = int(float(lbl_key))
                    if 1 <= m_idx <= 12:
                         lbl_name = list(ResponseFormatter.MONTHS.keys())[m_idx-1][:3].capitalize()
                except: pass
                
                if lbl_key not in pivoted_data:
                    pivoted_data[lbl_key] = {'label': lbl_name, 'raw_label': lbl_key}
                
                serie_key = str(int(float(r.get('serie')))) # Year
                val = float(r.get('val', 0) or 0)
                ops = int(r.get('ops', 0) or 0)
                
                pivoted_data[lbl_key][serie_key] = val
                pivoted_data[lbl_key][f"{serie_key}_ops"] = ops
                series_years.add(serie_key)
            
            # Sort Years
            sorted_years = sorted(list(series_years))
            if not sorted_years: return {"text": "Error formatting comparison.", "sql": sql}
            
            # Prepare Lists
            final_rows = []
            labels = []
            datasets = []
            
            # Colors for years (Fade Effect)
            colors = ["#94a3b8", "#38bdf8", "#818cf8", "#c084fc"] # Gray -> Blue -> Indigo -> Purple
            
            # Build Datasets structure
            dataset_map = {year: [] for year in sorted_years}
            
            # Sort by Label (Assumes 1-12 or string sort)
            # Try integer sort if possible
            try:
                sorted_keys = sorted(pivoted_data.keys(), key=lambda x: int(float(x)))
            except:
                sorted_keys = sorted(pivoted_data.keys())
                
            for k in sorted_keys:
                item = pivoted_data[k]
                labels.append(item['label'])
                
                # Table Row
                row_obj = {'label': item['label']}
                
                for i, year in enumerate(sorted_years):
                    val = item.get(year, 0.0)
                    dataset_map[year].append(val)
                    row_obj[year] = val # For Table Column
                    row_obj[f"{year}_ops"] = item.get(f"{year}_ops", 0)
                    
                    # Calculate Variance for Table (vs previous year in list)
                    if i > 0:
                        prev_year = sorted_years[i-1]
                        prev_val = item.get(prev_year, 0.0)
                        diff = val - prev_val
                        pct = (diff / prev_val * 100) if prev_val != 0 else 0
                        row_obj['var_pct'] = f"{pct:+.1f}%"
                        row_obj['var_val'] = diff
                
                # Add extra metrics for Table
                # We put the LAST year's val as main 'val' for strict compatibility with standard renderers
                last_year = sorted_years[-1]
                row_obj['val'] = item.get(last_year, 0) 
                row_obj['ops'] = item.get(f"{last_year}_ops", 0)
                
                final_rows.append(row_obj)

            # Construct Chart Datasets
            for i, year in enumerate(sorted_years):
                # Specific Colors request: 2024 Blue, 2025 Green
                color = "#94a3b8" # Default Gray
                s_str = str(year)
                if "2024" in s_str: color = "#38bdf8" # Blue
                elif "2025" in s_str: color = "#34d399" # Green
                elif "2023" in s_str: color = "#9ca3af" # Gray
                else:
                    # Fallback palette
                    palette = ["#38bdf8", "#fbbf24", "#34d399", "#f472b6", "#a855f7"]
                    color = palette[i % len(palette)]

                # Highlight last year logic (thicker border)
                border_width = 3 if i == len(sorted_years) - 1 else 2
                
                # [FIX] Clean Label to avoid "Comparativa Ventas 2024 vs 2025 2024"
                clean_label = label
                if "Comparativa" in label:
                    clean_label = label.split("Comparativa")[0].strip() # Fallback to generic if complex
                    if not clean_label: clean_label = "Ventas" # Default
                elif "vs" in label:
                    clean_label = label.split("vs")[0].replace("2024", "").replace("2025", "").strip()
                
                # If label is still too long or contains the year, just use "Ventas" or "Serie"
                if str(year) in clean_label:
                    clean_label = clean_label.replace(str(year), "").strip()
                    
                datasets.append({
                    "label": f"{clean_label} {year}",
                    "data": dataset_map[year],
                    "borderColor": color,
                    "backgroundColor": color, # For legend consistency
                    "tension": 0.3,
                    "borderWidth": border_width
                })

            # Summary
            summary_html = ResponseFormatter._generate_comparison_summary(final_rows, sorted_years, label, lang)
            
            # [FIX] Clean Title: Remove year duplication
            # If label already has "vs", don't append exercise
            title_text = label
            if "vs" not in label and "Comparativa" not in label:
                 title_text = f"{label} ({sorted_years[0]} vs {sorted_years[-1]})"
            
            # We construct title manually instead of using LanguageService to avoid double suffix
            title = f'<div style="text-align: center; margin-top: 20px; color: #a1a1aa; font-size: 0.9rem; font-family: \'Inter\', sans-serif;">{title_text}</div>'
            
            return {
                "text": summary_html + title,
                "answer": summary_html + title, # [FIX] Frontend expects 'answer'
                "type": "table", # Force Table to render rows + chart
                "chart_config": {
                    "type": "line",
                    "data": {"labels": labels, "datasets": datasets}
                },
                "data": final_rows,
                "sql": sql,
                "key": match_meta.get('key')
            }

        else:
             # --- STANDARD SINGLE SERIES LOGIC ---
             labels = []
             data_vals = []
             data_vals_prev = []
             has_prev = False
     
             for r in rows:
                 # Map month number to name
                 m_idx = int(r.get('mes') or 0)
                 m_name = list(ResponseFormatter.MONTHS.keys())[m_idx-1][:3].capitalize() if 1 <= m_idx <= 12 else str(r.get('label', ''))
                 labels.append(m_name)
                 data_vals.append(float(r.get('val', 0) or 0))
                 
                 # Comparison Data Logic (Legacy columns)
                 if 'val_prev' in r or 'neto_prev' in r:
                     has_prev = True
                     data_vals_prev.append(float(r.get('val_prev') or r.get('neto_prev') or 0))
             
             datasets = [{
                 "label": f"{label} {ejercicio}",
                 "data": data_vals,
                 "borderColor": "#00d2ff",
                 "tension": 0.3
             }]
     
             if has_prev:
                 datasets.append({
                     "label": f"{label} {int(ejercicio)-1}",
                     "data": data_vals_prev,
                     "borderColor": "#71717a", 
                     "borderDash": [5, 5],
                     "tension": 0.3
                 })
     
             # [NEW] Prediction Injection
             if match_meta and match_meta.get('prediction'):
                 target_year = match_meta.get('target_year')
                 forecast_rows = PredictionService.forecast(rows, target_year)
                 pred_data = []
                 for i in range(len(labels)):
                     if i < len(forecast_rows):
                         pred_data.append(forecast_rows[i]['val'])
                     else:
                         pred_data.append(None)
                 
                 datasets.append({
                     "label": f"🔮 Proyección {target_year}",
                     "data": pred_data,
                     "borderColor": "#a855f7",
                     "borderDash": [2, 2],
                     "pointStyle": 'star',
                     "tension": 0.4
                 })
                 label = f"{label} (con Proyección {target_year})"
     
             title = LanguageService.get_text('chart_title', lang, label=label, ejercicio=ejercicio)
             summary_html = ResponseFormatter._generate_consultant_summary(rows, ejercicio, label, lang)
             text = summary_html + title
     
             return {
                 "text": text,
                 "type": "table", # Force Table
                 "chart_config": {
                     "type": "line",
                     "data": {
                         "labels": labels,
                         "datasets": datasets
                     }
                 },
                 "data": rows,
                 "sql": sql,
                 "key": match_meta.get('key') if match_meta else None
             }

    @staticmethod
    def _generate_consultant_summary(rows: List[Dict], ejercicio: int, label: str, lang: str, metric_mode: str = 'sales') -> str:
        """
        Generates a consultant-style text summary based on the data rows.
        Enhanced for 'Senior Consultant' analysis: Trends, Margins, Seasonality.
        """
        if not rows:
            return ""

        # Terminology Logic
        term_volumen = "Volumen de Negocio"
        term_facturacion = "facturación"
        
        if metric_mode == 'purchase_amount' or metric_mode == 'purchase':
            term_volumen = "Volumen de Compras"
            term_facturacion = "inversión"
        elif metric_mode == 'purchase_order':
            term_volumen = "Volumen de Pedidos"
            term_facturacion = "cartera de pedidos"
        elif metric_mode == 'cost':
            term_volumen = "Volumen de Costes"
            term_facturacion = "gasto"
        
        total_val = 0.0
        total_cost = 0.0
        total_ops = 0
        
        max_val = -1.0
        max_label = ""
        min_val = float('inf')
        min_label = ""
        
        best_margin_pct = -100.0
        best_margin_label = ""
        worst_margin_pct = 100.0
        worst_margin_label = ""

        # Analyze Data
        for r in rows:
            val = float(r.get('val') or r.get('neto') or r.get('importe') or 0)
            cost = float(r.get('coste') or 0)
            ops = int(r.get('ops') or 0)
            
            margin = val - cost
            margin_pct = (margin / val * 100) if val != 0 else 0
            
            total_val += val
            total_cost += cost
            total_ops += ops
            
            # Label resolution (Month Name if possible)
            lbl = r.get('label') or r.get('mes') or 'N/D'
            # Try to convert to month name if it's a number 1-12
            try:
                m_num = int(float(lbl))
                if 1 <= m_num <= 12:
                    # Get key by index
                    lbl = list(ResponseFormatter.MONTHS.keys())[m_num-1].capitalize()
            except:
                pass
            
            if val > max_val:
                max_val = val
                max_label = lbl
                
            if val < min_val and val > 0:
                min_val = val
                min_label = lbl
                
            if margin_pct > best_margin_pct and val > 0:
                best_margin_pct = margin_pct
                best_margin_label = lbl
                
            if margin_pct < worst_margin_pct and val > 0:
                worst_margin_pct = margin_pct
                worst_margin_label = lbl

        # Global Metrics
        total_margin = total_val - total_cost
        global_margin_pct = (total_margin / total_val * 100) if total_val != 0 else 0
        avg_ticket = (total_val / total_ops) if total_ops > 0 else 0
        
        # Formatting
        total_str = f"{total_val:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")
        margin_str = f"{total_margin:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")
        ticket_str = f"{avg_ticket:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")
        
        # Trend Analysis (First vs Second Half if enough rows)
        trend_text = ""
        is_ranking_mode = False
        
        # Check if Time Series (Labels are months 1-12) or Ranking
        try:
            is_time_series = all(str(r.get('label','')).isdigit() and 1 <= int(float(r.get('label',''))) <= 12 for r in rows if r.get('label'))
        except:
            is_time_series = False
            
        if is_time_series and len(rows) >= 6:
            mid = len(rows) // 2
            first_half = sum([float(r.get('val') or 0) for r in rows[:mid]])
            second_half = sum([float(r.get('val') or 0) for r in rows[mid:]])
            
            if second_half > first_half * 1.05:
                trend_text = "El año muestra una <b>tendencia positiva</b>, con un segundo semestre más fuerte."
            elif first_half > second_half * 1.05:
                trend_text = "Se observa una <b>desaceleración</b> en la segunda mitad del periodo."
            else:
                trend_text = "El rendimiento se ha mantenido <b>estable</b> a lo largo del periodo."
        else:
            is_ranking_mode = True

        # [NEW] PARETO / CONCENTRATION ANALYSIS
        concentration_text = ""
        if is_ranking_mode and total_val > 0:
            # Sort by val desc
            sorted_rows = sorted(rows, key=lambda x: float(x.get('val') or 0), reverse=True)
            accum = 0
            count_80 = 0
            
            for i, r in enumerate(sorted_rows):
                accum += float(r.get('val') or 0)
                if accum / total_val <= 0.80:
                    count_80 += 1
                else:
                    if count_80 == 0: count_80 = 1 # At least 1
                    break
            
            pct_items_80 = (count_80 / len(rows) * 100)
            
            if pct_items_80 < 20:
                concentration_text = f"⚠️ <b>Alta Concentración de Riesgo:</b> El {pct_items_80:.0f}% de los elementos genera el 80% del volumen."
            elif pct_items_80 < 40:
                concentration_text = f"<b>Concentración Moderada:</b> El {pct_items_80:.0f}% de los elementos genera el 80% del volumen (Pareto Standard)."
            else:
                concentration_text = "<b>Cartera Diversificada:</b> El volumen está distribuido equitativamente, reduciendo la dependencia de elementos clave."

        # Construct Text - Minimalist Executive Style
        intro_text = ""
        if is_time_series:
             intro_text = f"""
                El ejercicio se caracteriza por una <b style="color:#fff; font-weight: 600;">{ "tendencia positiva" if "positiva" in trend_text else ("desaceleración" if "desaceleración" in trend_text else "estabilidad") }</b> en el volumen de actividad. 
                El pico máximo de {term_facturacion} se alcanzó en <b style="color:#fff; font-weight: 600;">{max_label}</b>, consolidándose como el periodo clave del año.
             """
        else:
             intro_text = f"""
                El análisis de ranking muestra un volumen total de <b>{total_str}</b> distribuido entre {len(rows)} elementos activos.
                {concentration_text}
             """

        summary = f"""
        <div style="background: rgba(24, 24, 27, 0.4); border: 1px solid #3f3f46; padding: 32px; margin-bottom: 40px; border-radius: 16px; font-family: 'Inter', sans-serif;">
            
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 32px; border-bottom: 1px solid #3f3f46; padding-bottom: 20px;">
                <span style="font-size: 1.5rem; font-weight: 600; color: #fff; letter-spacing: -0.5px;">Resumen Ejecutivo {ejercicio}</span>
                <span style="font-size: 0.85rem; color: #71717a; text-transform: uppercase; letter-spacing: 1px;">Informe IA</span>
            </div>

            <!-- KPI GRID -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; margin-bottom: 32px;">
                
                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">{term_volumen}</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: #fff; letter-spacing: -1px; margin-bottom: 4px;">{total_str}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">{total_ops} Operaciones</div>
                </div>

                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Margen Bruto</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: #fbbf24; letter-spacing: -1px; margin-bottom: 4px;">{global_margin_pct:.1f}%</div>
                    <div style="font-size: 0.9rem; color: #71717a;">{margin_str}</div>
                </div>

                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Ticket Medio</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: #38bdf8; letter-spacing: -1px; margin-bottom: 4px;">{ticket_str}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">Eficiencia Comercial</div>
                </div>

            </div>
            
            <!-- NARRATIVE ANALYSIS -->
            <div style="font-size: 1.05rem; color: #d4d4d8; line-height: 1.8; font-weight: 400; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.05);">
                <p style="margin-bottom: 16px;">
                    {intro_text}
                </p>
                <p style="margin-bottom: 0;">
                    En términos de rentabilidad, <b style="color:#fff; font-weight: 600;">{best_margin_label}</b> destaca por su eficiencia ({best_margin_pct:.1f}%), 
                    mientras que se observa una contracción del margen en <b style="color:#fff; font-weight: 600;">{worst_margin_label}</b> ({worst_margin_pct:.1f}%), 
                    punto que requiere atención operativa.
                </p>
            </div>
            
            <!-- FOOTER ACTION -->
            <div style="margin-top: 32px; padding-top: 20px; border-top: 1px solid #3f3f46; display: flex; align-items: center; justify-content: space-between;">
                <div style="font-size: 0.9rem; color: #a1a1aa;">
                    <span style="color: #34d399; font-weight: 600;">Recomendación:</span> { "Vigilar la caída de margen detectada." if worst_margin_pct < global_margin_pct - 5 else "Mantener la estrategia actual." }
                </div>
            </div>

        </div>
        """
        return summary

    @staticmethod
    def _generate_comparison_summary(rows: List[Dict], years: List[str], label: str, lang: str, extras: Dict = None) -> str:
        """
        Generates a Pivot Comparison Summary (Variance Analysis) with Senior Consultant Insights.
        """
        if len(years) < 2: return ""
        
        curr_year = years[-1]
        prev_year = years[-2]
        
        # --- DATA PREPARATION ---
        # Helper to safely extract float
        def get_val(r, y): return float(r.get(y, 0) or 0)
        
        # Totals
        total_curr = sum([get_val(r, curr_year) for r in rows])
        total_prev = sum([get_val(r, prev_year) for r in rows])
        
        ops_curr = sum([int(r.get(f"{curr_year}_ops", 0) or 0) for r in rows])
        ops_prev = sum([int(r.get(f"{prev_year}_ops", 0) or 0) for r in rows])

        # Variances
        diff = total_curr - total_prev
        var_pct = (diff / total_prev * 100) if total_prev != 0 else 0
        
        # Ticket
        ticket_curr = (total_curr / ops_curr) if ops_curr > 0 else 0
        ticket_prev = (total_prev / ops_prev) if ops_prev > 0 else 0
        ticket_diff = ticket_curr - ticket_prev
        ticket_var_pct = (ticket_diff / ticket_prev * 100) if ticket_prev != 0 else 0
        
        # Operations
        ops_diff = ops_curr - ops_prev
        ops_var_pct = (ops_diff / ops_prev * 100) if ops_prev != 0 else 0

        # --- QUARTERLY ANALYSIS ---
        # Map labels to quarters (Assuming labels are month names or numbers)
        # We need to map row index to quarter roughly if order is chronological
        # Or rely on label parsing
        
        q_data = {
            'Q1': {'curr': 0, 'prev': 0},
            'Q2': {'curr': 0, 'prev': 0},
            'Q3': {'curr': 0, 'prev': 0},
            'Q4': {'curr': 0, 'prev': 0}
        }
        
        month_to_q = {
            'ene': 'Q1', 'feb': 'Q1', 'mar': 'Q1', '1': 'Q1', '01': 'Q1',
            'abr': 'Q2', 'may': 'Q2', 'jun': 'Q2', '2': 'Q2', '02': 'Q2',
            'jul': 'Q3', 'ago': 'Q3', 'sep': 'Q3', '3': 'Q3', '03': 'Q3',
            'oct': 'Q4', 'nov': 'Q4', 'dic': 'Q4', '4': 'Q4', '04': 'Q4'
        }
        
        for r in rows:
            lbl = str(r.get('label', '')).lower()[:3]
            # Try to match numeric string "1.0" -> "1"
            if lbl.replace('.0','').isdigit():
                lbl = lbl.replace('.0','')
                
            quarter = 'Q?'
            # Direct mapping
            if lbl in month_to_q: quarter = month_to_q[lbl]
            # Name mapping
            else:
                for k, v in month_to_q.items():
                    if k in lbl: 
                        quarter = v
                        break
            
            if quarter in q_data:
                q_data[quarter]['curr'] += get_val(r, curr_year)
                q_data[quarter]['prev'] += get_val(r, prev_year)

        # Identify Best Quarter
        best_q = max(q_data, key=lambda k: q_data[k]['curr'])
        best_q_val = q_data[best_q]['curr']
        
        # Identify Best Growth Quarter
        best_growth_q = None
        best_growth_pct = -9999
        
        for q, vals in q_data.items():
            if vals['prev'] > 0:
                growth = (vals['curr'] - vals['prev']) / vals['prev'] * 100
                if growth > best_growth_pct:
                    best_growth_pct = growth
                    best_growth_q = q

        # --- MONTHLY INSIGHTS ---
        best_month_lbl = ""
        best_month_diff = -float('inf')
        worst_month_lbl = ""
        worst_month_diff = float('inf')

        for r in rows:
            v_curr = get_val(r, curr_year)
            v_prev = get_val(r, prev_year)
            d = v_curr - v_prev
            
            if d > best_month_diff:
                best_month_diff = d
                best_month_lbl = r.get('label', '')
            
            if d < worst_month_diff:
                worst_month_diff = d
                worst_month_lbl = r.get('label', '')

        # --- NARRATIVE CONSTRUCTION ---
        import locale
        fmt = lambda x: f"{x:,.2f}€".replace(",", "X").replace(".", ",").replace("X", ".")
        fmt_pct = lambda x: f"{x:+.1f}%"
        
        color_var = "#ef4444" if diff < 0 else "#34d399"
        icon_var = "📉" if diff < 0 else "📈"
        color_ticket = "#ef4444" if ticket_diff < 0 else "#38bdf8"
        color_ops = "#ef4444" if ops_diff < 0 else "#fbbf24"
        
        # Tone Logic
        tone = "positivo" if var_pct > 0 else "negativo"
        magnitude = "significativo" if abs(var_pct) > 10 else "moderado"
        
        narrative_intro = f"El ejercicio {curr_year} cierra con un comportamiento <b>{tone}</b> ({fmt_pct(var_pct)}), "
        if diff > 0:
            narrative_intro += f"generando un <b>valor incremental de {fmt(diff)}</b> respecto al año anterior."
        else:
            narrative_intro += f"lo que supone una <b>contracción de {fmt(abs(diff))}</b> en el volumen de negocio."

        # Quarter Analysis Text
        q_text = ""
        if best_growth_q and best_growth_pct > 0:
            q_text = f"El dinamismo se concentró en el <b>{best_growth_q}</b>, que lideró el crecimiento relativo ({fmt_pct(best_growth_pct)}). "
        
        # Ticket vs Volume Logic
        driver_text = ""
        if ticket_var_pct > 0 and ops_var_pct > 0:
            driver_text = "El crecimiento es <b>orgánico y saludable</b>, impulsado tanto por captación de operaciones como por mejora del ticket medio."
        elif ticket_var_pct > 0 and ops_var_pct < 0:
            driver_text = "La estrategia de <b>valor sobre volumen</b> ha compensado la caída en operaciones con un mayor ticket medio."
        elif ticket_var_pct < 0 and ops_var_pct > 0:
            driver_text = "Se observa una estrategia de <b>rotación</b>, sacrificando ticket medio para ganar cuota de mercado (operaciones)."
        elif ticket_var_pct < 0 and ops_var_pct < 0:
            driver_text = "Se detecta un <b>deterioro generalizado</b> en los fundamentales del negocio (tráfico y valor)."

        # --- EXTRAS (Top Clients / Products) ---
        extras_html = ""
        if extras:
            top_clients = extras.get('top_clients', [])
            top_products = extras.get('top_products', [])
            
            if top_clients or top_products:
                extras_html = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; margin-top: 32px; padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.05);">'
                
                # Clients
                if top_clients:
                    rows_html = "".join([
                        f"""
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.02); padding-bottom: 4px;">
                            <span style="color: #d4d4d8; font-size: 0.9rem;">{str(c.get('label','N/D'))[:25]}</span>
                            <span style="color: #fff; font-weight: 600;">{fmt(c.get('val',0))}</span>
                        </div>
                        """ for c in top_clients
                    ])
                    extras_html += f"""
                    <div style="background: rgba(255,255,255,0.02); padding: 20px; border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 16px; letter-spacing: 0.5px; font-weight: 600;">🏆 Top Clientes {curr_year}</div>
                        {rows_html}
                    </div>
                    """
                
                # Products
                if top_products:
                    rows_html = "".join([
                        f"""
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.02); padding-bottom: 4px;">
                            <span style="color: #d4d4d8; font-size: 0.9rem;">{str(p.get('label','N/D'))[:25]}</span>
                            <span style="color: #fff; font-weight: 600;">{fmt(p.get('val',0))}</span>
                        </div>
                        """ for p in top_products
                    ])
                    extras_html += f"""
                    <div style="background: rgba(255,255,255,0.02); padding: 20px; border-radius: 12px;">
                        <div style="font-size: 0.85rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 16px; letter-spacing: 0.5px; font-weight: 600;">📦 Top Artículos {curr_year}</div>
                        {rows_html}
                    </div>
                    """
                
                extras_html += "</div>"

        summary = f"""
        <div style="background: rgba(24, 24, 27, 0.6); border: 1px solid #3f3f46; padding: 32px; margin-bottom: 40px; border-radius: 16px; font-family: 'Inter', sans-serif; box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);">
            
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 32px; border-bottom: 1px solid #3f3f46; padding-bottom: 20px;">
                <span style="font-size: 1.5rem; font-weight: 600; color: #fff; letter-spacing: -0.5px;">Comparativa {prev_year} vs {curr_year}</span>
                <span style="font-size: 0.85rem; color: #71717a; text-transform: uppercase; letter-spacing: 1px;">Informe IA</span>
            </div>

            <!-- KPI GRID -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; margin-bottom: 32px;">
                
                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border-left: 4px solid {color_var}; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Variación Ventas</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: {color_var}; letter-spacing: -1px; margin-bottom: 4px;">{icon_var} {fmt_pct(var_pct)}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">Gap: {fmt(diff)}</div>
                </div>

                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Total {curr_year}</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: #fff; letter-spacing: -1px; margin-bottom: 4px;">{fmt(total_curr)}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">vs {fmt(total_prev)}</div>
                </div>

                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Ticket Medio</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: {color_ticket}; letter-spacing: -1px; margin-bottom: 4px;">{fmt_pct(ticket_var_pct)}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">{fmt(ticket_curr)}</div>
                </div>
                
                <div style="background: rgba(255,255,255,0.03); padding: 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.05);">
                    <div style="font-size: 0.8rem; color: #a1a1aa; text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.5px;">Operaciones</div>
                    <div style="font-size: 1.75rem; font-weight: 700; color: {color_ops}; letter-spacing: -1px; margin-bottom: 4px;">{fmt_pct(ops_var_pct)}</div>
                    <div style="font-size: 0.9rem; color: #71717a;">{ops_curr} Ops</div>
                </div>

            </div>
            
            <!-- NARRATIVE ANALYSIS -->
            <div style="font-size: 1.05rem; color: #d4d4d8; line-height: 1.8; font-weight: 400; padding-top: 24px; border-top: 1px solid rgba(255,255,255,0.05);">
                <p style="margin-bottom: 16px;">
                    {narrative_intro} {driver_text}
                </p>
                <p style="margin-bottom: 16px;">
                    {q_text} A nivel mensual, <b>{best_month_lbl}</b> destaca como el mes de mayor contribución relativa (+{fmt(best_month_diff)}), 
                    compensando la corrección observada en <b>{worst_month_lbl}</b> ({fmt(worst_month_diff)}).
                </p>
                <p style="margin-bottom: 0; font-size: 0.9rem; color: #a1a1aa; font-style: italic;">
                    Nota: Para un desglose por clientes o productos, utiliza el botón "Analizar más" a continuación.
                </p>
            </div>

            <!-- EXTRAS -->
            {extras_html}

        </div>
        """
        return summary

    @staticmethod
    def _format_table(label: str, ejercicio: int, rows: List[Dict], match_meta: Dict, limit: int, lang: str) -> Dict:
        formatted_rows = []
        labels = []
        vals = []
        has_coste = len(rows) > 0 and 'coste' in rows[0]
        
        # [NEW] Detect Metric Intent
        intent_meta = match_meta.get('intent_meta', {})
        metric_mode = intent_meta.get('metric', 'sales') # sales, cost, margin
        
        for r in rows:
            # Dynamic Label Logic: Try 'label', then 'nombre', then 'fecha', then first key
            l = r.get('label') or r.get('nombre') or r.get('fecha') or 'N/D'
            
            # Value Logic: Try 'val', then 'neto', then 'importe'
            # [FIX] 'val' is NOW ALWAYS SALES (ImporteLiquido) from the SQL Guardrail.
            # We don't need to reconstruct anything.
            sales_val = float(r.get('val') or r.get('neto') or r.get('importe') or 0)
            cost_val = float(r.get('coste') or 0)
            
            # Calculate Margin explicitly
            margin_val = sales_val - cost_val
            
            # Determine what to plot in the CHART based on metric_mode
            chart_val = sales_val
            if metric_mode == 'margin':
                chart_val = margin_val
            elif metric_mode == 'cost':
                chart_val = cost_val
            
            # Table Logic
            m_pct = 0
            if sales_val != 0:
                m_pct = (margin_val / sales_val) * 100
            
            m_str = f"{m_pct:.2f}%"

            # Allow 'extra' from SQL (e.g. Doc Ref or Client Code) to be combined with colored margin
            sql_extra = r.get('extra')
            
            # Format Margin with HTML Color
            final_extra = ""
            if m_str:
                color = "#ef4444" if "-" in m_str else "#34d399"
                final_extra = f"<span style='color: {color}'>{m_str}</span>"
            
            if sql_extra:
                 if final_extra:
                     final_extra = f"{sql_extra}  ({final_extra})"
                 else:
                     final_extra = sql_extra
            elif not final_extra:
                 final_extra = "" # Ensure not None
            
            # Copy all original keys to support dynamic frontend
            new_row = r.copy()
            new_row['label'] = str(l)
            
            # Ensure Table Columns are Correct
            new_row['val'] = sales_val # Ventas Column
            new_row['coste'] = cost_val # Costos Column
            # Frontend calculates Imp. Margen = val - coste. 
            # So if val=Sales and coste=Cost, Imp. Margen will be correct.
            
            if 'importe' not in new_row and 'neto' not in new_row:
                 new_row['value'] = sales_val
            new_row['extra'] = final_extra
            
            formatted_rows.append(new_row)
            labels.append(str(l))
            
            # Chart Data
            vals.append(chart_val) 

        # [NEW] Multi-Series Chart Logic (Comparison)
        is_comparison = intent_meta.get('is_comparison', False) or (len(rows) > 0 and 'serie' in rows[0])
        
        # [NEW] Pareto Logic for Rankings (Top N)
        # We assume it's a ranking if:
        # 1. Not a comparison
        # 2. Not a time series (labels are not months)
        # 3. Has more than 1 row
        is_ranking = False
        if not is_comparison and len(rows) > 1:
             # Check if labels are months
             try:
                 if not all(str(r.get('label','')).isdigit() for r in rows):
                      is_ranking = True
             except: is_ranking = True
             
             if is_ranking:
                 # Check keywords "Top" or "Ranking" in label or sql
                 if 'top' not in label.lower() and 'ranking' not in label.lower():
                     # Maybe generic list, check if sorted descending by value
                     pass

        if is_comparison:
            # Pivot Data
            series_map = {} # { '2024': [val, val, ...], '2025': ... }
            labels_set = sorted(list(set(labels)))
            
            # Re-build labels to ensure order (months)
            # If labels are months (1..12), sort numerically
            try:
                if all(str(l).isdigit() for l in labels_set):
                    labels_set.sort(key=int)
            except:
                pass # lexical sort
                
            # Initialize series
            unique_series = sorted(list(set(r.get('serie') for r in rows if r.get('serie'))))
            for s in unique_series:
                series_map[str(s)] = [0] * len(labels_set)
            
            # [FIX] PIVOT TABLE ROWS FOR FRONTEND
            # We must return PIVOTED rows so the table shows columns: Label | 2024 | 2025 | Var%
            pivoted_rows_map = {} # label -> row_obj
            
            # Fill Data
            for r in rows:
                s = str(r.get('serie'))
                l = str(r.get('label'))
                v = float(r.get('val') or 0)
                if metric_mode == 'margin': v = float(r.get('val') or 0) - float(r.get('coste') or 0)
                elif metric_mode == 'cost': v = float(r.get('coste') or 0)
                
                if l not in pivoted_rows_map:
                    pivoted_rows_map[l] = {'label': l, 'extra': r.get('extra', '')}

                # Add value for this series
                pivoted_rows_map[l][s] = v
                pivoted_rows_map[l][f"{s}_ops"] = int(r.get('ops') or 0)
                
                if l in labels_set:
                    idx = labels_set.index(l)
                    if s in series_map:
                        series_map[s][idx] = v
            
            # Calculate Variances and Finalize Rows
            formatted_rows = []
            for l in labels_set:
                if l in pivoted_rows_map:
                    row = pivoted_rows_map[l]
                    
                    # Calculate Var (Last vs Prev)
                    if len(unique_series) >= 2:
                        curr = str(unique_series[-1])
                        prev = str(unique_series[-2])
                        v_curr = row.get(curr, 0)
                        v_prev = row.get(prev, 0)
                        diff = v_curr - v_prev
                        pct = (diff / v_prev * 100) if v_prev != 0 else 0
                        
                        color = "#34d399" if diff >= 0 else "#ef4444"
                        row['var_pct'] = f"<span style='color:{color}'>{pct:+.1f}%</span>"
                        row['var_val'] = diff
                    
                    # Set main 'val' to the latest year for sorting/compatibility
                    row['val'] = row.get(str(unique_series[-1]), 0)
                    
                    formatted_rows.append(row)

            # Build Datasets with Fixed Colors
            chart_datasets = []
            for i, s in enumerate(unique_series):
                s_str = str(s)
                # Specific Colors request: 2024 Blue, 2025 Green
                color = "#94a3b8" # Default Gray
                if "2024" in s_str: color = "#38bdf8" # Blue
                elif "2025" in s_str: color = "#34d399" # Green
                elif "2023" in s_str: color = "#9ca3af" # Gray
                else:
                    # Fallback palette
                    palette = ["#38bdf8", "#fbbf24", "#34d399", "#f472b6", "#a855f7"]
                    color = palette[i % len(palette)]
                
                chart_datasets.append({
                    "label": s_str,
                    "data": series_map[s_str],
                    "backgroundColor": color,
                    "borderColor": color,
                    "borderWidth": 2,
                    # If comparison, prefer line? User asked for comparison. 
                    # Lines are better for trends.
                    "type": "line" if len(labels_set) > 1 else "bar"
                })
            
            # Override flat labels with pivoted labels
            labels = labels_set
            
        else:
            # Single Series (Legacy)
            chart_label = "Ventas"
            chart_color = "#38bdf8" # Blue
            
            if metric_mode == 'margin':
                chart_label = "Margen"
                chart_color = "#fbbf24" # Gold
            elif metric_mode == 'cost':
                chart_label = "Costes"
                chart_color = "#ef4444" # Red
            elif metric_mode == 'purchase_amount' or metric_mode == 'purchase':
                chart_label = "Compras"
                chart_color = "#a855f7" # Purple for purchases
            elif metric_mode == 'purchase_order':
                chart_label = "Pedidos Proveedor"
                chart_color = "#d946ef" # Magenta for orders
                
            chart_datasets = [{"label": chart_label, "data": vals, "backgroundColor": chart_color}]
            
            # [NEW] PARETO ANALYSIS for Rankings
            if is_ranking:
                 # Sort by val descending just in case
                 formatted_rows.sort(key=lambda x: float(x.get('val', 0)), reverse=True)
                 
                 total_sum = sum(float(r.get('val', 0)) for r in formatted_rows)
                 accum = 0.0
                 
                 for i, r in enumerate(formatted_rows):
                     val = float(r.get('val', 0))
                     accum += val
                     pct_accum = (accum / total_sum * 100) if total_sum > 0 else 0
                     pct_single = (val / total_sum * 100) if total_sum > 0 else 0
                     
                     # ABC Classification
                     abc = 'A'
                     if pct_accum > 80: abc = 'B'
                     if pct_accum > 95: abc = 'C'
                     
                     # Add to Row
                     r['pct_total'] = f"{pct_single:.1f}%"
                     r['pct_accum'] = f"{pct_accum:.1f}%"
                     r['abc'] = abc
                     
                     # Visual Bar for Cumulative
                     color_abc = "#34d399" # A - Green
                     if abc == 'B': color_abc = "#fbbf24" # B - Yellow
                     if abc == 'C': color_abc = "#ef4444" # C - Red
                     
                     r['abc_badge'] = f"<span style='background: {color_abc}20; color: {color_abc}; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; font-weight: bold;'>{abc}</span>"
        
        # Determine Title
        is_dynamic = "dynamic" in match_meta.get('key', '')
        if str(match_meta.get('key') or '').startswith('named_') or match_meta.get('key') == 'year_analysis':
             text = label
        elif is_dynamic:
             text = LanguageService.get_text('list_title', lang, label=label, ejercicio=ejercicio)
        else:
             tope_titulo = len(rows) if match_meta.get('completo') else limit
             text = LanguageService.get_text('ranking_title', lang, label=label, ejercicio=ejercicio, limit=tope_titulo)

        # [NEW] Append Consultant Summary
        summary_html = ""
        if is_comparison and locals().get('unique_series') and len(unique_series) >= 2:
             # Need to construct pivoted rows for the summary
             pivoted_summary_rows = []
             p_map = {}
             
             for r in formatted_rows:
                 lbl = r.get('label')
                 serie = str(r.get('serie'))
                 if lbl not in p_map: 
                     p_map[lbl] = {'label': lbl}
                     pivoted_summary_rows.append(p_map[lbl])
                 
                 p_map[lbl][serie] = float(r.get('val') or 0)
                 p_map[lbl][f"{serie}_ops"] = int(r.get('ops') or 0)

             summary_html = ResponseFormatter._generate_comparison_summary(pivoted_summary_rows, [str(s) for s in unique_series], label, lang)
        else:
             summary_html = ResponseFormatter._generate_consultant_summary(rows, ejercicio, label, lang, metric_mode=metric_mode)
        
        text = summary_html + text

        result = {
            "text": text,
            "type": "table",
            "metric": metric_mode, # Add metric to allow frontend customization
            "data": formatted_rows,
            "sql": match_meta['sql'],
            "key": match_meta.get('key'),
            "query": match_meta.get('query_orig'), # If we had it, but API sets it.
            "source": match_meta.get('source'),
            "limit": limit,
            "completo": bool(match_meta.get('completo')),
        }

        # Only add chart if it's a numeric ranking, not a document list
        # We assume Top N is numeric ranking. "Dynamic" might be list.
        is_doc_list = match_meta.get('key', '').startswith('dynamic_') or match_meta.get('key') == 'doc_list'
        
        if not is_doc_list:
            # [FIX] Smart Orientation
            # If labels look like months, use vertical bars (indexAxis: 'x')
            is_time_series = False
            if len(labels) > 0:
                l = str(labels[0]).lower()
                # Check 1..12 or month names
                if l.isdigit() and 1 <= int(l) <= 12:
                    is_time_series = True
                elif l in ResponseFormatter.MONTHS or l[:3] in [m[:3] for m in ResponseFormatter.MONTHS]:
                    is_time_series = True
            
            result["chart_config"] = {
                "type": "bar",
                "indexAxis": 'x' if is_time_series else 'y',
                "data": {
                    "labels": labels,
                    "datasets": chart_datasets
                }
            }

        if str(match_meta.get('key') or '').startswith('ranking_') and formatted_rows:
            primero = formatted_rows[0]
            result['kpis'] = [{
                'label': str(primero.get('label') or 'Primero')[:80],
                'value': round(float(primero.get('val') or 0), 2),
                'suffix': '€',
                'color': '#60a5fa',
            }]
        if isinstance(match_meta.get('origen'), dict):
            result['origen'] = match_meta['origen']
        
        return result
