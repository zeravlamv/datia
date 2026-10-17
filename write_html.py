
import os

fin_html = """{% load static i18n %}
<div id="tab-actualidad-financiera" class="financial-theme">
    <div class="dashboard-v2-container">
        <!-- Toolbar: Status & Customize -->
        <div class="fin-toolbar">
            <div class="fin-toolbar-left">
                <button id="btn-save-layout" class="btn-fin-action" onclick="saveLayout()" style="display:none;">
                    <i class="fas fa-save"></i> {% trans "Guardar Orden" %}
                </button>
                <button id="btn-reset-layout" class="btn-fin-action" onclick="resetLayout()" style="display:none;">
                    <i class="fas fa-undo"></i> {% trans "Reset" %}
                </button>
            </div>
            <div class="fin-toolbar-right">
                <span id="fin-pending-badge" class="fin-badge-warning" style="display:none;">
                    <i class="fas fa-exclamation-triangle"></i> {% trans "Actualización Pendiente" %}
                </span>
                <button id="btn-local-ai-analysis"
                        class="btn-fin-action btn-local-ai"
                        title="{% trans 'Generar análisis financiero mediante inteligencia artificial' %}"
                        aria-label="{% trans 'Análisis IA local' %}"
                        aria-disabled="true"
                        disabled
                        style="margin-left: 10px;">
                    <i class="fas fa-brain" aria-hidden="true"></i>
                    {% trans "Análisis IA local" %}
                </button>
            </div>
        </div>

        <!-- Draggable Container -->
        <div id="fin-dashboard-grid" class="fin-grid-container">
            <!-- SECTION: EXECUTIVE SUMMARY -->
            <div id="fin-section-exec" class="fin-grid-item" draggable="true" data-id="exec">
                <div class="fin-card-simple">
                    <div class="fin-card-header">
                        <span class="fin-card-title">{% trans "Resumen Ejecutivo" %}</span>
                        <i class="fas fa-grip-lines fin-drag-handle"></i>
                    </div>
                    
                    <div class="fin-grid-container" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                        <div class="fin-kpi-card fin-bg-blue">
                            <div class="fin-kpi-title">{% trans "Ingresos Totales" %}</div>
                            <div class="fin-kpi-val" id="fin-val-ingresos">--</div>
                            <div class="fin-kpi-desc" id="fin-comp-ingresos">--</div>
                        </div>
                        <div class="fin-kpi-card fin-bg-red">
                            <div class="fin-kpi-title">{% trans "Gastos Totales" %}</div>
                            <div class="fin-kpi-val" id="fin-val-gastos">--</div>
                            <div class="fin-kpi-desc" id="fin-comp-gastos">--</div>
                        </div>
                        <div class="fin-kpi-card fin-bg-green">
                            <div class="fin-kpi-title">{% trans "Resultado de Explotación" %}</div>
                            <div class="fin-kpi-val" id="fin-val-resultado">--</div>
                            <div class="fin-kpi-desc" id="fin-comp-resultado">--</div>
                        </div>
                    </div>
                    
                    <div class="fin-chart-container" id="fin-exec-chart" style="height:300px;"></div>
                </div>
            </div>

            <!-- SECTION: AI ANALYSIS -->
            <div id="fin-section-analysis" class="fin-grid-item" draggable="true" data-id="analysis">
                <div class="fin-card-simple">
                    <div class="fin-card-header">
                        <span class="fin-card-title">{% trans "Análisis Estratégico (IA)" %}</span>
                        <i class="fas fa-grip-lines fin-drag-handle"></i>
                    </div>
                    <div id="fin-analysis-container" role="status" aria-live="polite">
                        <div class="fin-skeleton" style="padding:12px;">
                            <div class="fin-skeleton-line"></div>
                            <div class="fin-skeleton-line short"></div>
                            <div class="fin-skeleton-line"></div>
                        </div>
                        <div class="fin-skeleton-text text-center">{% trans "Analizando..." %}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

with open("datia/templates/datia/components/tab_actualidad_financiera.html", "w", encoding="utf-8") as f:
    f.write(fin_html)

print("Done")

