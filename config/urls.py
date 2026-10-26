from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from datia.api.api import api
from datia.api.user_endpoints import change_password_api
from datia.views import dashboard, login_view, logout_view, project_context_view, mobile_dashboard_view, tab_visibility_view, download_whitepaper_pdf, landing_cliente_view, landing_cliente_img

from datia.api.semantic_endpoints import business_context_api, generate_metadata_api
from datia.api.semantic_endpoints import (
    standard_fields_list_api, standard_fields_save_api, standard_fields_delete_api
)
from datia.api.introspection_endpoints import (
    get_tables_api, get_columns_api, save_mapping_api, get_mapped_sources_api, 
    generate_sql_training_batch, examen_preguntas_api, get_active_tables_api, reset_source_api,
    factory_reset_api, reindex_datasource_api
)

from datia.api.relationship_endpoints import relationships_api, relationship_detail_api
from datia.api.reglas_endpoints import reglas_detalle_api, reglas_lista_api
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path('api/', api.urls),
    path('admin/tab-visibility/', tab_visibility_view, name='tab_visibility'),
    path('admin/usuarios/visibilidad/', tab_visibility_view, name='user_tab_visibility'),
    path('admin/', admin.site.urls),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    # Semantic Layer Endpoints
    path('api/semantic/context/<str:empresa>', business_context_api, name='semantic_context'),
    path('api/semantic/generate-metadata', generate_metadata_api, name='semantic_generate'),
    path('api/semantic/standard-fields', standard_fields_list_api, name='standard_fields_list'),
    path('api/semantic/standard-fields/save', standard_fields_save_api, name='standard_fields_save'),
    path('api/semantic/standard-fields/delete', standard_fields_delete_api, name='standard_fields_delete'),
    
    # Introspection / Mapping Endpoints
    path('api/semantic/tables', get_tables_api, name='semantic_tables'),
    path('api/semantic/mapped-sources', get_mapped_sources_api, name='semantic_mapped_sources'),
    path('api/semantic/columns/<str:table_name>', get_columns_api, name='semantic_columns'),
    path('api/semantic/mapping', save_mapping_api, name='semantic_mapping'),
    path('api/semantic/source/<int:source_id>/reset', reset_source_api, name='reset_source'),
    path('api/datasource/<int:source_id>/reindex', reindex_datasource_api, name='reindex_source'),
    path('api/semantic/factory-reset', factory_reset_api, name='factory_reset'),
    
    # [NEW] Configuration Endpoints
    
    # Auto Training / SQL Generation
    path('api/auto-training/examen', examen_preguntas_api, name='examen_preguntas'),
    path('api/auto-training/reglas', reglas_lista_api, name='reglas_lista'),
    path('api/auto-training/reglas/<str:nombre>', reglas_detalle_api, name='reglas_detalle'),
    path('api/auto-training/generate-sql-batch', generate_sql_training_batch, name='generate_sql_batch'),
    path('api/semantic/active-tables', get_active_tables_api, name='get_active_tables'),
    
    # Relationships
    path('api/relationships', relationships_api, name='relationships_api'),
    path('api/relationships/<int:relation_id>', relationship_detail_api, name='relationship_detail'),
    
    # System Catalog (Developer Tool)
    path('catalog/', lambda request: render(request, 'datia/catalog.html'), name='catalog'),
    
    # White Paper (Investor Document)
    path('whitepaper/', lambda request: render(request, 'datia/whitepaper.html'), name='whitepaper'),
    path('whitepaper/pdf/', download_whitepaper_pdf, name='whitepaper_pdf'),
    
    # Landing Resumen Comercial
    path('resumen/comercial/', lambda request: render(request, 'datia/resumen_comercial.html'), name='resumen_comercial'),
    path('comercial/', lambda request: render(request, 'datia/comercial.html'), name='comercial'),
    
    # Project Context (Technical Landing)
    path('project-context/', project_context_view, name='project_context'),
    # Landing Comercial Cliente
    path('landing/cliente/', landing_cliente_view, name='landing_cliente'),
    path('landing/cliente/img/<str:name>', landing_cliente_img, name='landing_cliente_img'),
    # Catalog Guide IA
    path('catalog/guia-ia/', lambda request: render(request, 'datia/guide_ia.html'), name='catalog_guide_ia'),
    path('infografia/story/', lambda request: render(request, 'datia/infografia_story.html'), name='infografia_story'),
    
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('', dashboard, name='dashboard'),

    path('mobile/', mobile_dashboard_view, name='mobile'),
    
    # User Management Endpoints
    path('api/user/change-password', change_password_api, name='user_change_password'),
]
