from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from datia.api.guards import login_required_json
import json
from datia.services.etl_service import ETLService
from datia.models.semantic import DataSource, DataField, BusinessContext
from django.db import connections
from django.conf import settings
import os

@csrf_exempt
@login_required_json
def get_tables_api(request):
    """
    GET /api/semantic/tables
    Lists all available tables from MSSQL source.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        service = ETLService()
        conn = service.get_connection()
        cursor = conn.cursor()
        
        # Query MSSQL for all base tables
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
        tables = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        return JsonResponse({'status': 'ok', 'tables': tables})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def get_columns_api(request, table_name):
    """
    GET /api/semantic/columns/<table_name>
    Lists columns for a specific table from MSSQL.
    Also merges with existing DataField definitions if available.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        service = ETLService()
        conn = service.get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch Columns from MSSQL
        # We also fetch Data Type to help the UI
        query = "SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?"
        cursor.execute(query, (table_name,))
        rows = cursor.fetchall()
        
        conn.close()
        
        if not rows:
             return JsonResponse({'status': 'error', 'message': f'Table {table_name} not found or has no columns'}, status=404)
        
        # El mapeo es único para toda la base.
        source = DataSource.objects.filter(source_table__iexact=table_name).order_by('id').first()
        
        existing_fields = {}
        table_metadata = {}
        is_virtual_source = False
        
        if source:
            fields_qs = DataField.objects.filter(source=source)
            existing_fields = {f.field_name: f for f in fields_qs}
            table_metadata = {
                'business_name': source.name,
                'description': source.description
            }
            is_virtual_source = bool(source.is_virtual)
        
        # [NEW] Check which columns actually exist in PostgreSQL materialized table
        postgres_columns = set()
        try:
            import psycopg2
            from django.conf import settings
            
            pg_config = settings.DATABASES.get('default', {})
            if pg_config and not is_virtual_source:
                pg_conn = psycopg2.connect(
                    dbname=pg_config['NAME'],
                    user=pg_config['USER'],
                    password=pg_config['PASSWORD'],
                    host=pg_config['HOST'],
                    port=pg_config['PORT']
                )
                pg_cursor = pg_conn.cursor()
                
                # Check if table exists and get its columns
                datia_table = None
                if source and not is_virtual_source:
                    datia_table = source.get_local_table_name()
                if not datia_table:
                    datia_table = f"datiadb_{table_name.lower()}"
                pg_cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND LOWER(table_name) = LOWER(%s)
                """, (datia_table,))
                
                postgres_columns = {row[0].lower() for row in pg_cursor.fetchall()}
                pg_conn.close()
        except Exception as pg_err:
            # If we can't connect to Postgres, assume nothing is migrated
            if getattr(settings, 'DEBUG', False) or os.environ.get('DATIA_DEBUG') == '1':
                print(f"Warning: Could not check PostgreSQL for migrated columns: {pg_err}")
        
        columns = []
        for r in rows:
            col_name = r[0]
            data_type = r[1]
            
            field = existing_fields.get(col_name)
            
            col_data = {
                'name': col_name,
                'type': data_type,
                # Defaults
                'business_name': '',
                'description': '',
                'usage': 'data', 
                'metadata': 'General',
                'is_active': False # Default unchecked
            }
            
            if field:
                col_data['business_name'] = field.business_name
                col_data['description'] = field.description
                col_data['usage'] = field.usage_type
                col_data['metadata'] = field.metadata_tag
                col_data['is_active'] = field.is_active
                col_data['is_key'] = field.is_key # [NEW]
                
                # Sanear auto-detectados en tablas virtuales: mostrar como candidatos (no activos)
                if is_virtual_source and field.auto_discovered and not field.is_key:
                    col_data['usage'] = 'data'
                    col_data['is_active'] = False
            else:
                # [NF-011] Global Repository Enrichment
                # If no specific mapping exists, try to find a Standard Match
                from datia.models.semantic import StandardField
                std = StandardField.objects.filter(name__iexact=col_name).first()
                if std:
                    col_data['business_name'] = std.business_name
                    col_data['description'] = std.description
                    # Map semantic_role to usage_type
                    # usage_type choices: dimension, metric, filter, none
                    role_map = {
                        'DIMENSION': 'dimension',
                        'PK': 'dimension', # PKs are dimensions usually
                        'FK': 'dimension',
                        'METRIC': 'metric',
                        'DATE': 'date'
                    }
                    # En tablas virtuales no activar rol por defecto; solo sugerir
                    col_data['usage'] = role_map.get(std.semantic_role, 'dimension') if not is_virtual_source else 'data'
                    col_data['metadata'] = 'Standard' # Tag as Standard
                    col_data['is_key'] = std.is_key
                    col_data['is_auto_detected'] = True # Signal for UI
                    if not is_virtual_source:
                        col_data['is_active'] = True
                else:
                    base_names = [
                        'Ejercicio','Fecha','Numero','Serie','Cliente','Proveedor',
                        'Articulo','Empresa','Cuenta','Familia','SubFamilia','Albaran',
                        'Linea','Posicion'
                    ]
                    lowered = col_name.lower()
                    matched = None
                    for bn in base_names:
                        if bn.lower() in lowered:
                            matched = StandardField.objects.filter(name__iexact=bn).first()
                            if matched:
                                break
                    if matched:
                        col_data['business_name'] = matched.business_name
                        col_data['description'] = matched.description
                        role_map = {
                            'DIMENSION': 'dimension',
                            'PK': 'dimension',
                            'FK': 'dimension',
                            'METRIC': 'metric',
                            'DATE': 'date'
                        }
                        col_data['usage'] = role_map.get(matched.semantic_role, 'dimension') if not is_virtual_source else 'data'
                        col_data['metadata'] = 'Standard'
                        col_data['is_key'] = matched.is_key
                        col_data['is_auto_detected'] = True
                        if not is_virtual_source:
                            col_data['is_active'] = True
            
            # [FIXED] is_mapped ONLY if column exists in materialized PostgreSQL table
            # IMPORTANT: Always use the ORIGINAL column name (col_name), not business_name
            # because ETL syncs columns using their original names from MSSQL
            target_col_name = col_name.lower().replace(' ', '_')
            
            is_mapped = (not is_virtual_source) and (target_col_name in postgres_columns)
            col_data['is_mapped'] = is_mapped
            
            # [FIXED] Do NOT clear description for non-migrated columns. 
            # We want to preserve semantic work even if the table is not yet synced.
            # if not is_mapped:
            #    col_data['description'] = ''
            
            columns.append(col_data)
            
        return JsonResponse({
            'status': 'ok', 
            'columns': columns,
            'table_metadata': table_metadata,
            'is_virtual': source.is_virtual if source else False  # NF-016
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def save_mapping_api(request):
    """
    POST /api/semantic/mapping
    Saves the semantic mapping (DataSource + DataFields).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        
        empresa_id = data.get('empresa_id')
        if empresa_id is None or not str(empresa_id).strip().isdigit():
            return JsonResponse({'status': 'error', 'message': 'empresa_id numérico requerido'}, status=400)
        empresa_id = int(str(empresa_id).strip())
        table_name = data.get('table_name')
        business_name = data.get('business_name')
        table_desc = data.get('table_description')
        # [FIX] Fallback to description if context is missing (Frontend legacy behavior)
        table_ctx = data.get('table_context') or table_desc or ''
        fields = data.get('fields', [])
        
        if not table_name:
             return JsonResponse({'status': 'error', 'message': 'Missing table name'}, status=400)
             
        # 1. Save Source
        is_virtual = data.get('is_virtual', False)  # NF-016
        sync_mode = data.get('sync_mode', 'full') # Fix ISS-029
        
        source, created = DataSource.resolver(
            empresa_id,
            table_name,
            defaults={
                'name': business_name or table_name,
                'description': table_desc,
                'table_context': table_ctx,
                'is_active': False,
                'is_virtual': is_virtual,
                'sync_mode': sync_mode
            },
            actualizar=True,
        )
        
        # If updating existing source, also mark as pending
        if not created:
            source.is_active = False
            source.save(update_fields=['is_active'])
        
        # 2. Save Fields
        # RESET STEP: Mark all fields as inactive first.
        # Only the ones sent in 'fields' (checked in UI) will be reactivated.
        import re
        def _norm(s):
            x = str(s or '').strip().lower()
            x = re.sub(r'\s+', '_', x).replace('.', '_')
            x = re.sub(r'[^a-z0-9_]', '', x)
            if x == 'id':
                x = 'source_id'
            if x in ('"order"', 'order'):
                x = 'order'
            return x
        seen = set()
        dups = set()
        for f in fields:
            bn = f.get('business_name') or f.get('name') or ''
            n = _norm(bn)
            if n in seen:
                dups.add(n)
            else:
                seen.add(n)
        if dups:
            return JsonResponse({'status': 'error', 'message': 'business_name duplicado: ' + ', '.join(sorted(list(dups)))}, status=400)
        DataField.objects.filter(source=source).update(is_active=False)
        
        for f in fields:
            fname = f.get('name')
            usage = f.get('usage', 'dimension')
            
            # Skip invalid entries
            if not fname:
                continue
            
            DataField.objects.update_or_create(
                source=source,
                field_name=fname,
                defaults={
                    'business_name': f.get('business_name') or fname,
                    'description': f.get('description', ''),
                    'data_type': f.get('type', 'text'),
                    'usage_type': f.get('usage', 'dimension'),
                    'metadata_tag': f.get('metadata', 'General'),
                    'is_key': f.get('is_key', False), # [NEW]
                    'is_active': True
                }
            )
            
        # No deletion step: non-sent fields remain inactive
            
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def _empresa_solicitada(request):
    raw = (request.GET.get('empresa') or request.GET.get('empresa_id') or '').strip()
    if raw.isdigit():
        return int(raw)
    return None


def _fuentes():
    """Catálogo único. Una fila por nombre de tabla, sin partir por empresa."""
    vistas = []
    seen = set()
    rows = DataSource.objects.all().order_by('source_table', 'id')
    for source in rows:
        key = (source.source_table or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        vistas.append(source)
    return vistas


@csrf_exempt
@login_required_json
def get_mapped_sources_api(request):
    """
    GET /api/semantic/mapped-sources?empresa=
    Tablas mapeadas de una sola empresa. Sin empresa no se mezclan el resto de sociedades.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
        
    try:
        data = []
        for source in _fuentes():
            data.append({
                'id': source.id,
                'name': source.name,
                'table': source.source_table,
                'desc': source.description,
                'last_sync': source.last_sync_at,
                'is_virtual': source.is_virtual,
                'is_active': source.is_active,
            })
        
        return JsonResponse({'status': 'ok', 'sources': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@login_required_json
def examen_preguntas_api(request):
    """Lanza el examen de preguntas de la empresa y el ejercicio activos."""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    try:
        empresa = int(request.GET.get('empresa') or 0)
        ejercicio = int(request.GET.get('ejercicio') or 0)
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Empresa o ejercicio no válidos.'}, status=400)
    if empresa <= 0 or ejercicio <= 0:
        return JsonResponse({'status': 'error', 'message': 'Elige la empresa y el ejercicio antes del examen.'}, status=400)
    from datia.services.ai.examen_preguntas import listar, responder_una
    fase = (request.GET.get('fase') or 'lista').strip()
    try:
        if fase == 'una':
            indice = int(request.GET.get('indice') or 0)
            resultado = responder_una(empresa, ejercicio, indice)
        else:
            resultado = listar(empresa, ejercicio)
    except (TypeError, ValueError, IndexError) as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=500)
    return JsonResponse({'status': 'ok', **resultado})


@csrf_exempt
@login_required_json
def generate_sql_training_batch(request):
    return JsonResponse({
        'status': 'retired',
        'message': 'El entrenamiento masivo ya no guarda consultas de ejemplo. El examen de preguntas ocupa su lugar.',
    }, status=410)


@csrf_exempt
@login_required_json
def get_active_tables_api(request):
    """
    GET /api/semantic/active-tables
    Lists all tables configured in DataSource (Postgres/Mapped tables)
    Used for driving the Mass Training UI table-by-table.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        from datia.models.ai import MetricsEmbeddings
        
        data = []
        for ds in _fuentes():
            # Check training status
            is_trained = MetricsEmbeddings.objects.filter(
                kind='qa', 
                metadata__source_table=ds.name
            ).exists()
            
            data.append({
                'id': ds.id,
                'name': ds.name, # User friendly
                'physical_name': ds.get_local_table_name(), # DatiaDB_...
                'is_trained': is_trained,  # New field
                'is_active': ds.is_active # Pass active status to UI if needed
            })
            
        return JsonResponse({'status': 'ok', 'tables': data})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def reset_source_api(request, source_id):
    """
    POST /api/semantic/source/<id>/reset
    Resets a DataSource:
    1. Drops physical table in Postgres.
    2. Deletes all DataField configurations.
    3. Sets is_active=False.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        source = get_object_or_404(DataSource, pk=source_id)
        
        # 1. Drop Physical Table
        local_table = source.get_local_table_name()
        service = ETLService()
        pg_conn = connections['analytics']
        with pg_conn.cursor() as cursor:
            print(f"Dropping table {local_table}...")
            cursor.execute(f'DROP TABLE IF EXISTS "{local_table}"')
            
        # 2. Delete DataFields (Configuration)
        DataField.objects.filter(source=source).delete()
        
        # 3. Reset Source State
        source.is_active = False
        source.last_sync_at = None
        source.save()
        
        return JsonResponse({'status': 'ok', 'message': f'Tabla {source.source_table} reiniciada correctamente.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def factory_reset_api(request):
    return JsonResponse({'status': 'error', 'message': 'Endpoint deshabilitado'}, status=410)
    """
    POST /api/semantic/factory-reset
    SECURITY: Requires Admin Password.
    Destructive "Factory Reset" for Implementers.
    Actions:
    1. Verify Password.
    2. Check Admin/Superuser.
    3. Update DataSources (Reset Sync Status, KEEP Context).
    4. Delete DataFields (Mapping) - Preserved by default now.
    5. Delete MetricsEmbeddings (AI Knowledge).
    6. Delete ALL Application Data (Transactional, Financial, Metrics).
    7. DROP all `datiaDB_` tables in Postgres.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        body = json.loads(request.body)
        password = body.get('password')
        preserve_config = body.get('preserve_config', True)
        reload_companies = body.get('reload_companies', True)
        dry_run = body.get('dry_run', False)
        auto_sync = body.get('auto_sync', True)
        mssql_database = body.get('mssql_database')
        
        if not password:
            return JsonResponse({'status': 'error', 'message': 'Password required'}, status=400)
            
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': 'Authentication required'}, status=401)
            
        # 1. Verify Password
        if not user.check_password(password):
            return JsonResponse({'status': 'error', 'message': 'Contraseña incorrecta'}, status=403)
            
        # 2. Check Permissions (Superuser or Administrators Group)
        is_admin = user.is_superuser or user.groups.filter(name='Administrators').exists()
        if not is_admin:
             return JsonResponse({'status': 'error', 'message': 'Acceso denegado. Se requiere nivel Administrador.'}, status=403)
             
        # --- PRE-VALIDATION FOR MSSQL OVERRIDE ---
        if auto_sync:
            try:
                import pyodbc
                from datia.services.runtime_config import mssql_connection_string, mssql_params
                conn_str = mssql_connection_string(mssql_database or mssql_params()['name'])
                try:
                    pyodbc.pooling = False
                except Exception:
                    pass
                _conn = pyodbc.connect(conn_str)
                _cur = _conn.cursor()
                _cur.execute("SELECT 1")
                try:
                    _conn.close()
                except Exception:
                    pass
            except Exception as _e:
                return JsonResponse({'status': 'error', 'message': f'Conexión MSSQL inválida: {str(_e)}'}, status=400)

        # --- DESTRUCTIVE ACTIONS ---
        from datia.models.ai import MetricsEmbeddings, MetricsLLMConsultas, MetricsFeedback, MetricsSavedQuery
        from datia.models.financial import DatiaPlanCuentas, DatiaAcumuladosConta, DatiaGrupos, DatiaCarteraEfectos, DatiaPresupuestoNotas
        from datia.models.mobile import MobileConfig
        from datia.models.permissions import UserEmpresaPermission
        from datia.models.master import Empresa
        from django.db import connections
        from django.db.models import Model
        import inspect
        import datia.models.totales as totales_models
        from django.conf import settings
        import time, os, json as _json
        
        # 3. Reset DataSources (Keep Context/Description, Reset Sync)
        # [MODIFIED] Preserve Mappings (User Request) - Do NOT delete sources
        DataSource.objects.all().update(
            is_active=False,
            last_sync_at=None,
            record_count=0,
            auto_discovered_fields=0
        )
        count_sources = 0 # Preserved
        
        # 4. Delete DataFields (Mappings)
        # [MODIFIED] Preserve Mappings (User Request) - Do NOT delete fields
        count_fields = 0 # Preserved
        
        # 5. SUPER FACTORY RESET: preparar plan y ejecutar
        pg_conn = connections['analytics']
        count_embeddings = 0
        truncated_tables = []
        tables_report = []
        empresa_before = 0
        empresa_after_delete = 0
        empresa_after_reload = 0
        dropped_tables = []
        vacuumed_tables = []

        # Construir plan (si dry_run no se ejecuta la limpieza)
        with pg_conn.cursor() as cursor:
            # métricas núcleo
            metric_core = ["metrics_llm_consultas", "metrics_feedback", "metrics_saved_queries", "tpl_ai_embeddings"]
            # datos estándar
            datia_core = [
                "datia_financial_plan",
                "datia_financial_acumulados",
                "datia_financial_groups",
                "datia_financial_cartera",
                "datia_financial_presupuestos",
                "datia_acumulados_stocks",
                "datia_sync_checkpoints",
            ]
            # opcionales de configuración
            datia_cfg = ["datia_financial_presupuesto_notas", "datia_mobile_config", "datia_user_empresa_permission"]
            # banca
            datia_banking = ["datia_banking_bank", "datia_banking_account", "datia_banking_instr_map", "datia_banking_instrument", "datia_banking_amort"]
            # totales (por introspección)
            total_tables = []
            for name, obj in inspect.getmembers(totales_models):
                if inspect.isclass(obj) and issubclass(obj, Model) and not obj._meta.abstract:
                    try:
                        total_tables.append(obj._meta.db_table)
                    except Exception:
                        pass
            # datiadb_ físicas
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%'")
            datiadb_tables = [row[0] for row in cursor.fetchall()]

        if dry_run:
            plan = {
                "truncate": metric_core
                + datia_core
                + total_tables
                + ([] if preserve_config else datia_cfg)
                + datia_banking,
                "drop": datiadb_tables,
                "vacuum": [
                    "datia_financial_plan",
                    "datia_financial_acumulados",
                    "datia_financial_groups",
                    "datia_financial_cartera",
                    "datia_financial_presupuestos",
                ],
            }
            return JsonResponse({'status': 'ok', 'message': 'Factory Reset (dry_run)', 'plan': plan})

        try:
            empresa_before = Empresa.objects.count()
        except Exception:
            empresa_before = 0
        Empresa.objects.all().delete()
        try:
            empresa_after_delete = Empresa.objects.count()
        except Exception:
            empresa_after_delete = 0

        with pg_conn.cursor() as cursor:
            for t in metric_core:
                before = 0
                after = 0
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    before = int(cursor.fetchone()[0] or 0)
                except Exception:
                    before = 0
                try:
                    cursor.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                    truncated_tables.append(t)
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    after = int(cursor.fetchone()[0] or 0)
                except Exception:
                    after = 0
                tables_report.append({"table": t, "before": before, "after": after, "deleted": before, "status": "ok" if after == 0 else "error"})
            for t in datia_core:
                before = 0
                after = 0
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    before = int(cursor.fetchone()[0] or 0)
                except Exception:
                    before = 0
                try:
                    cursor.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                    truncated_tables.append(t)
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    after = int(cursor.fetchone()[0] or 0)
                except Exception:
                    after = 0
                tables_report.append({"table": t, "before": before, "after": after, "deleted": before, "status": "ok" if after == 0 else "error"})
            for t in datia_banking:
                before = 0
                after = 0
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    before = int(cursor.fetchone()[0] or 0)
                except Exception:
                    before = 0
                try:
                    cursor.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                    truncated_tables.append(t)
                    cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                    after = int(cursor.fetchone()[0] or 0)
                except Exception:
                    after = 0
                tables_report.append({"table": t, "before": before, "after": after, "deleted": before, "status": "ok" if after == 0 else "error"})
            if not preserve_config:
                for t in datia_cfg:
                    before = 0
                    after = 0
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                        before = int(cursor.fetchone()[0] or 0)
                    except Exception:
                        before = 0
                    try:
                        cursor.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                        truncated_tables.append(t)
                        cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
                        after = int(cursor.fetchone()[0] or 0)
                    except Exception:
                        after = 0
                    tables_report.append({"table": t, "before": before, "after": after, "deleted": before, "status": "ok" if after == 0 else "error"})

        metrics_deleted = 0
        with pg_conn.cursor() as cursor:
            for name, obj in inspect.getmembers(totales_models):
                if inspect.isclass(obj) and issubclass(obj, Model) and not obj._meta.abstract:
                    try:
                        table = obj._meta.db_table
                        before = 0
                        after = 0
                        try:
                            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                            before = int(cursor.fetchone()[0] or 0)
                        except Exception:
                            before = 0
                        cursor.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY')
                        truncated_tables.append(table)
                        try:
                            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                            after = int(cursor.fetchone()[0] or 0)
                        except Exception:
                            after = 0
                        tables_report.append({"table": table, "before": before, "after": after, "deleted": before, "status": "ok" if after == 0 else "error"})
                    except Exception as e:
                        pass

        # 6. Drop Physical Tables (Deep Clean)
        with pg_conn.cursor() as cursor:
            # Tables starting with 'datiadb_' (lowercase convention)
            # We use ILIKE to be safe against case variants
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                cursor.execute(f'DROP TABLE "{table}" CASCADE')
                dropped_tables.append(table)
        
        with pg_conn.cursor() as cursor:
            for t in [
                "datia_financial_plan",
                "datia_financial_acumulados",
                "datia_financial_groups",
                "datia_financial_cartera",
                "datia_financial_presupuestos",
            ]:
                cursor.execute(f'VACUUM FULL ANALYZE "{t}"')
                vacuumed_tables.append(t)

        reloaded_empresas = 0
        if reload_companies:
            try:
                service = ETLService()
                reloaded_empresas = service.sync_empresas()
            except Exception:
                reloaded_empresas = 0
        try:
            empresa_after_reload = Empresa.objects.count()
        except Exception:
            empresa_after_reload = 0

        fk_total = 0
        fk_not_valid = 0
        with pg_conn.cursor() as cursor:
            try:
                cursor.execute("SELECT COUNT(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=%s AND c.contype='f'", ['public'])
                fk_total = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=%s AND c.contype='f' AND NOT c.convalidated", ['public'])
                fk_not_valid = int(cursor.fetchone()[0] or 0)
            except Exception:
                fk_total = 0
                fk_not_valid = 0

        report = {
            "timestamp": int(time.time()),
            "empresa_before": empresa_before,
            "empresa_after_delete": empresa_after_delete,
            "empresa_after_reload": empresa_after_reload,
            "empresa_empty": empresa_after_delete == 0,
            "tables": tables_report,
            "dropped_tables": dropped_tables,
            "fk_total": fk_total,
            "fk_not_valid": fk_not_valid,
            "ri_ok": fk_not_valid == 0
        }
        try:
            audit_dir = os.path.join(settings.BASE_DIR, 'datia', 'runtime')
            os.makedirs(audit_dir, exist_ok=True)
            audit_path = os.path.join(audit_dir, f"reset_audit_{report['timestamp']}.json")
            with open(audit_path, 'w', encoding='utf-8') as f:
                _json.dump(report, f, ensure_ascii=False)
        except Exception:
            pass
                
        # --- OPTIONAL AUTO SYNC ---
        sync_job_id = None
        if auto_sync:
            try:
                import uuid, threading, time
                from datia.api.etl_endpoints import full_sync_worker, ETL_JOBS, _read_jobs, _write_jobs
                sync_job_id = str(uuid.uuid4())
                ETL_JOBS[sync_job_id] = {
                    "id": sync_job_id,
                    "status": "pending",
                    "progress": 0,
                    "message": "Iniciando sincronización global...",
                    "created_at": time.time(),
                    "source_db": mssql_database
                }
                jobs = _read_jobs()
                jobs[sync_job_id] = ETL_JOBS[sync_job_id]
                _write_jobs(jobs)
                t = threading.Thread(target=full_sync_worker, args=(sync_job_id, None, None, "all", None, True, None, True, 7, None, False, mssql_database))
                t.daemon = True
                t.start()
            except Exception:
                sync_job_id = None

        return JsonResponse({
            'status': 'ok',
            'message': 'Super Factory Reset Completo',
            'details': {
                'fields_deleted': count_fields,
                'embeddings_deleted': count_embeddings,
                'tables_dropped': len(dropped_tables),
                'sources_deleted': count_sources,
                'metrics_records_deleted': metrics_deleted,
                'companies_reloaded': reloaded_empresas,
                'tables_truncated': len(truncated_tables),
                'vacuumed_tables': vacuumed_tables
            },
            'report': report,
            'sync_job_id': sync_job_id,
            'source_db': mssql_database
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
@login_required_json
def reindex_datasource_api(request, source_id):
    """
    POST /api/datasource/<id>/reindex
    Re-generates AI training data for a specific table (Synchronous).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        source = DataSource.objects.get(pk=source_id)

        local_table = source.get_local_table_name()
        if local_table and not source.is_virtual:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
                    [local_table],
                )
                if cursor.fetchone() is None:
                    return JsonResponse({
                        'status': 'error',
                        'error': f'{source.name} todavía no está copiada en la base local. Sincronízala antes de reentrenar.',
                    })
        
        from datia.models.ai import MetricsEmbeddings
        del_count = MetricsEmbeddings.objects.filter(kind='qa', metadata__source_table=source.name).delete()[0]
        return JsonResponse({
            'status': 'ok',
            'generated': 0,
            'purged': del_count,
            'message': 'Las consultas de ejemplo de esta tabla se han borrado. El examen de preguntas ocupa su lugar.',
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
