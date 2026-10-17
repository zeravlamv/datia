import re

with open('c:\\Users\\miguel vergara\\Desktop\\datia\\datia\\templates\\datia\\dashboard.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_html = """    <!-- Factory Reset / Migración Report Modal -->
    <div class="modal-overlay" id="reset-report-modal" style="display:none; z-index:10000;">
        <div class="modal-card" style="max-width: 900px; width: 90vw; max-height: 90vh; text-align:left; display:flex; flex-direction:column;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div>
                    <h3 style="margin:0; font-size:1.05rem; color:#e4e4e7;">Informe de limpieza</h3>
                    <div id="reset-report-subtitle" style="font-size:0.8rem; color:#a1a1aa; margin-top:4px;"></div>
                </div>
                <button onclick="closeResetReportModal()" style="background:none; border:none; color:#71717a; font-size:1.2rem; cursor:pointer;">&times;</button>
            </div>
            <div id="reset-report-empresa" style="margin-bottom:10px; font-size:0.9rem;"></div>
            <div id="reset-sync-source" style="margin-bottom:6px; font-size:0.85rem; color:#a1a1aa;"></div>
            <div style="flex:1 1 auto; max-height:65vh; overflow:auto; border:1px solid #27272a; border-radius:6px; padding:8px;">
                <table style="width:100%; border-collapse:collapse; font-size:0.8rem;">
                    <thead>
                        <tr style="color:#a1a1aa; text-align:left;">
                            <th style="padding:4px 6px;">Tabla</th>
                            <th style="padding:4px 6px; text-align:right;">Filas</th>
                            <th style="padding:4px 6px;">Estado</th>
                        </tr>
                    </thead>
                    <tbody id="reset-report-body"></tbody>
                </table>
            </div>
            <div id="reset-report-ri" style="margin-top:10px; font-size:0.8rem; color:#a1a1aa;"></div>
            <div id="reset-sync-visual" style="margin-top:12px; display:none;">
                <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                    <div style="color:#e4e4e7; font-size:0.9rem;">Sincronización Global</div>
                    <div id="reset-sync-message" style="color:#a1a1aa; font-size:0.8rem;"></div>
                </div>
                <div style="height:10px; width:100%; background:#27272a; border-radius:6px; overflow:hidden;">
                    <div id="reset-sync-progress" style="height:100%; width:0%; background:#10b981; transition:width 0.2s;"></div>
                </div>
            </div>
            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:14px;">
                <button class="btn-secondary" onclick="closeResetReportModal()">Cerrar</button>
            </div>
        </div>
    </div>"""

new_html = """    <!-- Factory Reset / Migración Report Modal -->
    <div class="modal-overlay" id="reset-report-modal" style="display:none; z-index:10000;">
        <div class="modal-card" style="max-width: 900px; width: 90vw; max-height: 90vh; text-align:left; display:flex; flex-direction:column; background: #18181b; border: 1px solid #3f3f46;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <div>
                    <h3 style="margin:0; font-size:1.15rem; color:#e4e4e7; display:flex; align-items:center; gap:8px;">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                        Progreso de Migración
                    </h3>
                    <div id="reset-report-subtitle" style="font-size:0.85rem; color:#a1a1aa; margin-top:4px;"></div>
                </div>
                <button onclick="closeResetReportModal()" style="background:none; border:none; color:#71717a; font-size:1.5rem; cursor:pointer; transition: color 0.2s;" onmouseover="this.style.color='#e4e4e7'" onmouseout="this.style.color='#71717a'">&times;</button>
            </div>

            <!-- Pestañas de Navegación del Modal -->
            <div style="display: flex; gap: 10px; margin-bottom: 12px; border-bottom: 1px solid #27272a; padding-bottom: 8px;">
                <button id="btn-tab-reporte-log" onclick="switchReportTab('log')" class="btn-secondary" style="background: #27272a; border-color: #3f3f46; color: white;">Log de Ejecución</button>
                <button id="btn-tab-reporte-resumen" onclick="switchReportTab('resumen')" class="btn-secondary" style="display:none;">Resumen de Tablas (Final)</button>
            </div>

            <!-- Contenido: Log de Ejecución -->
            <div id="reporte-tab-log" style="flex:1 1 auto; display:flex; flex-direction:column; overflow:hidden;">
                <div id="reset-report-empresa" style="margin-bottom:10px; font-size:0.9rem;"></div>
                <div id="reset-sync-source" style="margin-bottom:6px; font-size:0.85rem; color:#a1a1aa;"></div>
                
                <div style="flex:1 1 auto; max-height:55vh; overflow:auto; border:1px solid #27272a; border-radius:6px; background: #09090b;">
                    <table style="width:100%; border-collapse:collapse; font-size:0.8rem;">
                        <thead style="position: sticky; top: 0; background: #18181b; border-bottom: 1px solid #27272a;">
                            <tr style="color:#a1a1aa; text-align:left;">
                                <th style="padding:8px 10px;">Tabla / Tarea</th>
                                <th style="padding:8px 10px; text-align:right;">Filas</th>
                                <th style="padding:8px 10px;">Estado</th>
                            </tr>
                        </thead>
                        <tbody id="reset-report-body"></tbody>
                    </table>
                </div>
                <div id="reset-report-ri" style="margin-top:10px; font-size:0.8rem; color:#a1a1aa;"></div>
                
                <div id="reset-sync-visual" style="margin-top:12px; display:none; background: #27272a; padding: 12px; border-radius: 8px;">
                    <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                        <div style="color:#e4e4e7; font-size:0.9rem; font-weight:500;">Sincronización en curso</div>
                        <div id="reset-sync-message" style="color:#10b981; font-size:0.85rem; font-family: monospace;"></div>
                    </div>
                    <div style="height:12px; width:100%; background:#18181b; border-radius:6px; overflow:hidden; border: 1px solid #3f3f46;">
                        <div id="reset-sync-progress" style="height:100%; width:0%; background:linear-gradient(90deg, #059669, #10b981); transition:width 0.3s ease-in-out;"></div>
                    </div>
                </div>
            </div>

            <!-- Contenido: Resumen Final Matriz -->
            <div id="reporte-tab-resumen" style="flex:1 1 auto; display:none; flex-direction:column; overflow:hidden;">
                <div style="margin-bottom: 10px; font-size: 0.9rem; color: #a1a1aa;">
                    Validación final de registros insertados en Postgres por cada empresa migrada.
                </div>
                <div style="flex:1 1 auto; max-height:60vh; overflow:auto; border:1px solid #27272a; border-radius:6px; background: #09090b;">
                    <table style="width:100%; border-collapse:collapse; font-size:0.8rem; text-align: right;">
                        <thead style="position: sticky; top: 0; background: #18181b; border-bottom: 1px solid #27272a; z-index: 2;">
                            <tr style="color:#a1a1aa;">
                                <th style="padding:8px 10px; text-align:left; position: sticky; left: 0; background: #18181b; z-index: 3;">Empresa</th>
                                <th style="padding:8px 10px;" title="datia_cliente, datia_proveedores, datia_articulos...">Maestros</th>
                                <th style="padding:8px 10px;" title="datiadb_cabecerapedidocliente, datiadb_lineas...">Pedidos (C/L)</th>
                                <th style="padding:8px 10px;" title="datiadb_cabeceraalbarancliente, datiadb_lineas...">Albaranes (C/L)</th>
                                <th style="padding:8px 10px;" title="datia_acumulados_stocks">Stocks</th>
                                <th style="padding:8px 10px;" title="datia_financial_acumulados, datia_financial_plan">Contabilidad</th>
                                <th style="padding:8px 10px;" title="datia_financial_cartera">Cartera</th>
                                <th style="padding:8px 10px;" title="metrics_totales_empresa_ejercicio">Métricas base</th>
                            </tr>
                        </thead>
                        <tbody id="reset-resumen-body">
                            <!-- Filas dinámicas -->
                        </tbody>
                    </table>
                </div>
            </div>

            <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:16px;">
                <button class="btn-secondary" onclick="closeResetReportModal()" style="padding: 8px 20px;">Cerrar</button>
            </div>
        </div>
    </div>"""

if old_html in content:
    content = content.replace(old_html, new_html)
    with open('c:\\Users\\miguel vergara\\Desktop\\datia\\datia\\templates\\datia\\dashboard.html', 'w', encoding='utf-8') as f:
        f.write(content)
    print("REPLACED")
else:
    print("NOT FOUND")
