from ninja import Router, Query
from typing import Dict, Any
import threading
import time
import uuid
from django.http import JsonResponse, HttpResponse
from datia.services.etl_service import ETLService
from datia.models.semantic import DataSource
from django.conf import settings
import json
from django.db import connections
from django.contrib.auth.models import User

router = Router()

# In-memory job store (Global)
ETL_JOBS: Dict[str, Dict[str, Any]] = {}

def _job_store_path():
    import os
    return os.path.join(settings.BASE_DIR, 'datia', 'runtime', 'etl_jobs.json')

def _read_jobs():
    import json, os
    p = _job_store_path()
    try:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def _write_jobs(jobs):
    import json, os
    p = _job_store_path()
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(jobs, f, ensure_ascii=False)
    except:
        pass

def _active_sync_job():
    now = time.time()
    for job in ETL_JOBS.values():
        status = str(job.get('status') or '')
        if status not in ('pending', 'running', 'starting'):
            continue
        updated = float(job.get('updated_at') or job.get('created_at') or now)
        if now - updated < 6 * 3600:
            return job
    return None

_PG_TABLE = __import__('re').compile(r'^[a-z][a-z0-9_]*$')
_DOMAIN_PG = {
    'ventas_cabecera': 'datiadb_cabeceraalbarancliente',
    'ventas_lineas': 'datiadb_lineasalbarancliente',
    'compras_cabecera': 'datiadb_cabeceraalbaranproveedor',
    'compras_lineas': 'datiadb_lineasalbaranproveedor',
}

def _pg_row_count(table, empresa_id=None, year=None):
    if not table or not _PG_TABLE.match(str(table)):
        return None
    try:
        with connections['analytics'].cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s)", [f'public.{table}'])
            if not cursor.fetchone()[0]:
                return 0
            cursor.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                [table],
            )
            cols = {str(row[0]).lower() for row in cursor.fetchall()}
            where = []
            params = []
            emp_col = next((name for name in ('codigoempresa', 'empresa', 'empresacodigo') if name in cols), None)
            year_col = next((name for name in ('ejercicio', 'anio', 'year') if name in cols), None)
            if empresa_id is not None and emp_col:
                where.append(f'"{emp_col}"::text = %s')
                params.append(str(empresa_id))
            if year is not None and year_col:
                where.append(f'"{year_col}"::text = %s')
                params.append(str(year))
            sql = f'SELECT COUNT(*) FROM "{table}"'
            if where:
                sql += ' WHERE ' + ' AND '.join(where)
            cursor.execute(sql, params)
            return int(cursor.fetchone()[0] or 0)
    except Exception:
        return None

import os
import datetime
import logging
PERF_PATH = os.path.join(settings.BASE_DIR, 'datia', 'config', 'system_perf.json')
try:
    with open(PERF_PATH, 'r', encoding='utf-8') as f:
        perf_cfg = json.load(f)
    LOG_PROGRESS = bool(perf_cfg.get('log_etl_progress', False))
except:
    LOG_PROGRESS = False
logger = logging.getLogger('datia.etl')
LOG_ETL_ENABLED = os.environ.get('DATIA_LOG_ETL', '').lower() in ('1', 'true', 'yes')
def log_api(msg):
    try:
        if LOG_PROGRESS or LOG_ETL_ENABLED:
            logger.info(msg)
    except Exception:
        pass

INITIAL_LOAD_LOG = os.path.join(settings.BASE_DIR, 'carga_inicial.log')
def log_initial_load(level, message, extra=None):
    try:
        payload = {
            "ts": datetime.datetime.now().isoformat(),
            "level": str(level),
            "message": str(message),
        }
        if isinstance(extra, dict):
            payload.update(extra)
        os.makedirs(os.path.dirname(INITIAL_LOAD_LOG), exist_ok=True)
        with open(INITIAL_LOAD_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
def audit_event(job_id, table, operation, rows, state, message, duration=None):
    try:
        with connections['analytics'].cursor() as c:
            c.execute("SELECT datia_audit.log_event(%s,%s,%s,%s,%s,%s,%s,'public')",
                      [f"workflow:{job_id}", table, operation, int(rows or 0), state, message, duration if duration is not None else None])
    except Exception:
        pass
def heartbeat_job(job_id):
    try:
        while True:
            job = ETL_JOBS.get(job_id)
            if not job:
                break
            st = job.get('status')
            if st in ['completed', 'error']:
                break
            ETL_JOBS[job_id]['updated_at'] = time.time()
            jobs = _read_jobs()
            if job_id in jobs:
                jobs[job_id]['updated_at'] = time.time()
                _write_jobs(jobs)
            if LOG_PROGRESS:
                log_api(f"Heartbeat: Job {job_id} at {ETL_JOBS[job_id].get('progress', 0)}% - {ETL_JOBS[job_id].get('message', '')}")
            time.sleep(5)
    except:
        pass

def _get_db_size(conn_alias="analytics"):
    try:
        with connections[conn_alias].cursor() as c:
            c.execute("SELECT pg_database_size(current_database())")
            sz = int(c.fetchone()[0] or 0)
        return sz
    except:
        return None
def full_sync_worker(job_id, empresa_id=None, table_name=None, sync_type="all", table_ids=None, sync_data=True, target_year=None, fast_bulk=True, years_count=None, standard_tables=None, force_reset=False, mssql_database=None, delete_users=False, reload_companies=False, empresas_filter=None, skip_cleanup=False):
    log_api(f"Worker START: Job={job_id}, Emp={empresa_id}, Table={table_name}, SyncType={sync_type}, TableIDs={table_ids}, SyncData={sync_data}, TargetYear={target_year}, YearsCount={years_count}, StandardTables={standard_tables}, ForceReset={force_reset}, DeleteUsers={delete_users}, ReloadCompanies={reload_companies}, SkipCleanup={skip_cleanup}")
    """
    Background worker that executes the ETL sync.
    If empresa_id is provided, it syncs only that company (Per-Tenant Isolation).
    If force_reset is True, it performs a DESTRUCTIVE reset but scoped to the empresa_id if provided.
    Global reset is only allowed if empresa_id is None (Admin only).
    """
    global json
    def progress_callback(msg, percent):
        if job_id in ETL_JOBS:
            ETL_JOBS[job_id]['status'] = 'running'
            ETL_JOBS[job_id]['message'] = msg
            ETL_JOBS[job_id]['progress'] = percent
            ETL_JOBS[job_id]['updated_at'] = time.time()
        jobs = _read_jobs()
        jobs[job_id] = {
            "id": job_id,
            "status": ETL_JOBS.get(job_id, {}).get('status', 'running'),
            "progress": percent,
            "message": msg,
            "updated_at": time.time()
        }
        _write_jobs(jobs)

    def maybe_pause():
        while True:
            j = ETL_JOBS.get(job_id) or _read_jobs().get(job_id)
            if j and j.get('pause'):
                try:
                    ETL_JOBS[job_id]['status'] = 'paused'
                except Exception:
                    pass
                time.sleep(1)
            else:
                break

    try:
        if job_id in ETL_JOBS:
            ETL_JOBS[job_id]['status'] = 'starting'
        threading.Thread(target=heartbeat_job, args=(job_id,), daemon=True).start()
        
        # Initialize Service
        svc = ETLService(mssql_db=mssql_database)
        
        # --- PHASE 1: CLEANUP / RESET ---
        # Logic: If empresa_id is present, we clean ONLY that empresa.
        # If force_reset is True and empresa_id is None, we clean EVERYTHING (Dangerous).
        
        emp_val = None
        if empresa_id:
            try:
                emp_val = int(str(empresa_id).strip())
            except Exception:
                emp_val = None

        if emp_val and not skip_cleanup:
            # PER-TENANT CLEANUP (The "Initial Migration" mode)
            try:
                ETL_JOBS[job_id]['stage'] = 'cleanup'
                ETL_JOBS[job_id]['stage_progress'] = 0
                progress_callback(f"Limpiando datos anteriores de empresa {emp_val}...", 5)
            except Exception:
                pass

            wipe_full = bool((ETL_JOBS.get(job_id, {}) or {}).get('wipe'))
            if wipe_full:
                try:
                    progress_callback("Limpieza rápida (modo Factory Reset)", 1)
                except Exception:
                    pass
                conn = connections['analytics']
                def _terminate_metrics_blockers(table_name: str):
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    try:
                        with conn.cursor() as c2:
                            c2.execute(
                                """
                                SELECT a.pid,
                                       left(regexp_replace(a.query,'\\s+',' ','g'), 240) AS query
                                FROM pg_locks l
                                JOIN pg_class t ON t.oid = l.relation
                                JOIN pg_stat_activity a ON a.pid = l.pid
                                WHERE t.relname = %s
                                  AND l.granted
                                  AND a.pid <> pg_backend_pid()
                                """,
                                [table_name],
                            )
                            holders = c2.fetchall()
                        for pid, q in holders:
                            ql = (q or "").lower()
                            if ql.startswith("insert into metrics_") or "metrics_totales_" in ql or ql.startswith("truncate table"):
                                try:
                                    with conn.cursor() as c3:
                                        c3.execute("SELECT pg_terminate_backend(%s)", [int(pid)])
                                except Exception:
                                    pass
                    except Exception:
                        pass
                protected = set([
                    'datia_globalconfig',
                    'datia_userpreference',
                    'datia_mobile_config',
                    'datia_sync_checkpoints',
                    'datia_widgetconfig',
                    'datia_widgetstate',
                ])
                tables = []
                with conn.cursor() as c:
                    try:
                        c.execute("SELECT set_config('lock_timeout','5s', false)")
                        c.execute("SELECT set_config('statement_timeout','900000', false)")
                    except Exception:
                        pass
                    try:
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                        tables.extend([r[0] for r in c.fetchall()])
                    except Exception:
                        pass
                    try:
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                        tables.extend([r[0] for r in c.fetchall()])
                    except Exception:
                        pass
                    try:
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_financial_%'")
                        tables.extend([r[0] for r in c.fetchall()])
                    except Exception:
                        pass
                    try:
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_%' AND table_name NOT ILIKE 'datia_financial_%'")
                        tables.extend([r[0] for r in c.fetchall()])
                    except Exception:
                        pass
                seen = set()
                ordered = []
                for t in tables:
                    if not t or t in seen:
                        continue
                    seen.add(t)
                    if t in protected:
                        continue
                    ordered.append(t)
                total = len(ordered)
                done = 0
                cleanup_tables = []
                with conn.cursor() as c:
                    for t in ordered:
                        done += 1
                        try:
                            progress_callback(f"Limpieza: truncando {t}", 2 + int((done / max(1, total)) * 18))
                        except Exception:
                            pass
                        status = "OK"
                        try:
                            c.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                        except Exception as e_tr:
                            msg = str(e_tr).lower()
                            try:
                                conn.rollback()
                            except Exception:
                                pass
                            if "lock timeout" in msg or "canceling statement due to lock timeout" in msg:
                                try:
                                    _terminate_metrics_blockers(t)
                                    with conn.cursor() as c_retry:
                                        c_retry.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                                except Exception:
                                    try:
                                        conn.rollback()
                                    except Exception:
                                        pass
                                    if t.startswith("metrics_") or t.startswith("datiadb_") or t.startswith("datia_financial_") or t.startswith("datia_"):
                                        try:
                                            with conn.cursor() as c_del:
                                                c_del.execute(f'DELETE FROM "{t}"')
                                            status = "OK (DELETE)"
                                        except Exception:
                                            try:
                                                conn.rollback()
                                            except Exception:
                                                pass
                                            status = "SKIPPED (LOCK)"
                                    else:
                                        status = "SKIPPED (LOCK)"
                            else:
                                status = "SKIPPED"
                        cleanup_tables.append({"table": t, "action": "truncate", "status": status})
                try:
                    size_after = _get_db_size('analytics')
                except Exception:
                    size_after = None
                ETL_JOBS[job_id]['cleanup'] = {"size_before": None, "size_after": size_after, "tables": cleanup_tables}
                try:
                    progress_callback("Limpieza completada", 20)
                except Exception:
                    pass
            if not wipe_full:
                size_before = _get_db_size('analytics')
                cleanup_tables = []
                
                # 1. Identify tables to clean for this tenant
                targets = []
                try:
                    with connections['analytics'].cursor() as c:
                        # Metrics tables
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                        targets += [(r[0], 'empresa', 'delete') for r in c.fetchall()]
                        # DatiaDB tables (The core of migration), excluyendo datiadb_ai*
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                        targets += [(r[0], 'empresa', 'delete') for r in c.fetchall()]
                        # Financial tables
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_financial_%'")
                        targets += [(r[0], 'empresa', 'delete') for r in c.fetchall()]
                        # Other datia tables (masters, stocks, etc), excluding configs and core
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_%' AND table_name NOT ILIKE 'datia_financial_%' AND table_name NOT IN ('datia_empresa', 'datia_globalconfig', 'datia_userpreference', 'datia_mobile_config', 'datia_sync_checkpoints')")
                        targets += [(r[0], 'empresa', 'delete') for r in c.fetchall()]
                except Exception:
                    pass
                
                # Note: Respetamos tablas históricas no operativas según instrucciones del usuario.

                total_targets = len(targets)
                processed = 0
                
                with connections['analytics'].cursor() as c:
                    for t, col_hint, action in targets:
                        maybe_pause()
                        processed += 1
                        
                        # Determine the 'empresa' column dynamically
                        emp_col = None
                        try:
                            c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                            cols = [str(r[0]).lower() for r in c.fetchall()]
                            for cand in ['codigoempresa', 'empresa', 'empresacodigo', 'company', 'companyid']:
                                if cand in cols:
                                    emp_col = cand
                                    break
                        except Exception:
                            pass
                        
                        status = "SKIPPED"
                        deleted = 0
                        before = 0
                        after = 0
                        
                        if emp_col:
                            try:
                                # Count before
                                c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{emp_col}" = %s', [emp_val])
                                before = int(c.fetchone()[0] or 0)
                                
                                if before > 0:
                                    # Delete
                                    c.execute(f'DELETE FROM "{t}" WHERE "{emp_col}" = %s', [emp_val])
                                    deleted = before # Assuming successful delete of all matches
                                    status = "OK"
                                    
                                    # Verify
                                    c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{emp_col}" = %s', [emp_val])
                                    after = int(c.fetchone()[0] or 0)
                                else:
                                    status = "OK (Empty)"
                            except Exception as e:
                                status = f"ERROR: {str(e)}"
                        else:
                            status = "SKIPPED (No company col)"

                        cleanup_tables.append({"table": t, "action": "delete_rows", "before": before, "deleted": deleted, "after": after, "status": status})
                        
                        # Update progress every 5 tables
                        if processed % 5 == 0:
                             pct = int((processed / max(1, total_targets)) * 20) # Cleanup is 20% of total
                             progress_callback(f"Limpiando tablas... ({processed}/{total_targets})", pct)

                size_after = _get_db_size('analytics')
                ETL_JOBS[job_id]['cleanup'] = {"size_before": size_before, "size_after": size_after, "tables": cleanup_tables}
            
        elif force_reset and not emp_val and not skip_cleanup:
            # GLOBAL RESET (Admin only - Deprecated but kept for safety if requested without empresa)
            # User instruction: "revisa de 0 a 100... factory reset".
            # We must make this SAFE. No more TRUNCATE datia_raw.
            progress_callback("Factory Reset Global (Modo Seguro)...", 0)
            with connections['analytics'].cursor() as cursor:
                 # Clean metrics globally
                 cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                 for r in cursor.fetchall():
                     cursor.execute(f'TRUNCATE TABLE "{r[0]}" RESTART IDENTITY')
                 
                 # Clean datiadb globally (excluyendo datiadb_ai*)
                 cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                 for r in cursor.fetchall():
                     cursor.execute(f'TRUNCATE TABLE "{r[0]}" RESTART IDENTITY')
                 
                 # Clean datia_financial globally
                 cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_financial_%'")
                 for r in cursor.fetchall():
                     cursor.execute(f'TRUNCATE TABLE "{r[0]}" RESTART IDENTITY')

                 # Clean other datia_ tables globally
                 cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_%' AND table_name NOT ILIKE 'datia_financial_%' AND table_name NOT IN ('datia_globalconfig', 'datia_userpreference', 'datia_mobile_config', 'datia_sync_checkpoints')")
                 for r in cursor.fetchall():
                     cursor.execute(f'TRUNCATE TABLE "{r[0]}" RESTART IDENTITY')
            
            # Borrado de usuarios opcional
            if delete_users:
                progress_callback("Eliminando usuarios (excepto admin)...", 10)
                try:
                    User.objects.exclude(username='admin').delete()
                except Exception as e:
                    progress_callback(f"Error borrando usuarios: {e}", 10)

            # Recarga de empresas opcional
            if reload_companies and mssql_database:
                progress_callback("Recargando empresas desde MSSQL...", 15)
                try:
                    svc = ETLService(mssql_db=mssql_database)
                    svc.sync_empresas(allow_db_switch=True)
                except Exception as e:
                    progress_callback(f"Error recargando empresas: {e}", 15)
            
        # --- PHASE 2: MIGRATION (SYNC) ---
        parsed_standard_tables = None
        if standard_tables is not None:
            try:
                raw = standard_tables if isinstance(standard_tables, list) else str(standard_tables).split(',')
                parsed_standard_tables = [str(x).strip() for x in raw if str(x).strip() in ['ventas','compras','financiera','existencias']]
            except:
                parsed_standard_tables = []
                if LOG_ETL_ENABLED:
                    logger.warning("Error parsing standard_tables: %s", standard_tables)
        try:
            from datia.models import MetricsTotalesEmpresaEjercicio as _MTEE, Empresa as _EmpCheck
            first_run = (_MTEE.objects.count() == 0)
        except Exception:
            first_run = False
        if first_run and sync_type in ['all', 'standard'] and (not parsed_standard_tables or len(parsed_standard_tables) == 0):
            parsed_standard_tables = ['ventas','compras','financiera','existencias']
        if not first_run and sync_type == 'standard' and (not parsed_standard_tables or len(parsed_standard_tables) == 0):
            progress_callback("Debe seleccionar al menos una tabla estándar.", 0)
            if job_id in ETL_JOBS:
                ETL_JOBS[job_id]['status'] = 'error'
                ETL_JOBS[job_id]['progress'] = 0
                ETL_JOBS[job_id]['message'] = "Debe seleccionar al menos una tabla estándar."
            jobs = _read_jobs()
            jobs[job_id] = {
                "id": job_id,
                "status": "error",
                "progress": 0,
                "message": "Debe seleccionar al menos una tabla estándar.",
                "updated_at": time.time()
            }
            _write_jobs(jobs)
            return
        parsed_table_ids = None
        if table_ids:
            try:
                if isinstance(table_ids, str):
                    parsed_table_ids = [int(x) for x in table_ids.split(',') if x.strip().isdigit()]
                elif isinstance(table_ids, list):
                    parsed_table_ids = [int(x) for x in table_ids]
            except:
                pass
        
        if empresa_id:
            # Specific Company Sync with optional Table Granularity and Sync Type
            import json
            # Pass parsed_table_ids to generator
            for step_data in svc.sync_all_years_for_empresa_generator(empresa_id, filter_table=table_name, sync_type=sync_type, table_ids=parsed_table_ids, sync_data=sync_data, target_year=target_year, fast_bulk=fast_bulk, years_count=years_count, standard_tables=parsed_standard_tables):
                maybe_pause()
                # Parse the "data: {...}\n\n" format emitted by generators
                if step_data.startswith("data: "):
                    try:
                        clean_json = step_data.replace("data: ", "").replace("\\n", "").strip()
                        if LOG_PROGRESS:
                            log_api(f"Progress Update: {clean_json}")
                        data = json.loads(clean_json)
                        progress_callback(data.get('message', ''), data.get('percent', 0))
                        try:
                            step_name = str(data.get('step', '') or '')
                            if step_name in ('Setup', 'Syncing', 'DynamicSync'):
                                ETL_JOBS[job_id]['stage'] = 'sync'
                            elif step_name == 'Metrics':
                                ETL_JOBS[job_id]['stage'] = 'metrics'
                            msg = str(data.get('message', '') or '')
                            if 'TABLE:' in msg:
                                idx = msg.rfind('TABLE:')
                                if idx >= 0:
                                    nm = msg[idx + 6:].strip()
                                    ETL_JOBS[job_id]['current_table'] = nm
                            jobs = _read_jobs()
                            jobs[job_id] = ETL_JOBS[job_id]
                            _write_jobs(jobs)
                        except Exception:
                            pass
                    except Exception as e:
                        log_api(f"JSON Parse Error: {e} | Data: {step_data}")
            else:
                # If it's a direct dictionary (some generators might yield dicts)
                if isinstance(step_data, dict):
                    progress_callback(step_data.get('message', ''), step_data.get('percent', 0))
        else:
            # Full Global Sync (Does not support table granularity yet, creates complexity)
            # ... existing global sync logic ...
            progress_callback("Sincronizando estructura de empresas...", 5)
            svc.sync_structure(empresas_filter=empresas_filter, allow_db_switch=bool(force_reset))
            from datia.models import Empresa
            empresas = Empresa.objects.all()
            if empresas_filter:
                try:
                    codes = [int(x) for x in str(empresas_filter).split(',') if x.strip().isdigit()]
                    if codes:
                        empresas = empresas.filter(codigo__in=codes)
                except Exception:
                    pass
            if len(empresas) == 0:
                try:
                    # Respetar flag MSSQL
                    disable_mssql = os.environ.get('DATIA_DISABLE_MSSQL_SYNC', '').lower() in ('1', 'true', 'yes')
                except Exception:
                    disable_mssql = False
                if disable_mssql:
                    progress_callback("Primera migración requiere MSSQL: activa la conexión o usa Factory Reset con 'Recargar empresas'.", 0)
                    if job_id in ETL_JOBS:
                        ETL_JOBS[job_id]['status'] = 'error'
                        ETL_JOBS[job_id]['progress'] = 0
                        ETL_JOBS[job_id]['message'] = "Primera migración requiere recargar empresas desde MSSQL."
                    jobs = _read_jobs()
                    jobs[job_id] = {
                        "id": job_id,
                        "status": "error",
                        "progress": 0,
                        "message": "Primera migración requiere recargar empresas desde MSSQL.",
                        "updated_at": time.time()
                    }
                    _write_jobs(jobs)
                    return
                try:
                    svc.sync_empresas()
                except Exception as e:
                    log_api(f"Error recargando empresas en primera migración: {e}")
                empresas = Empresa.objects.all()
                if len(empresas) == 0:
                    progress_callback("No hay empresas disponibles tras intentar recarga.", 0)
                    if job_id in ETL_JOBS:
                        ETL_JOBS[job_id]['status'] = 'error'
                        ETL_JOBS[job_id]['progress'] = 0
                        ETL_JOBS[job_id]['message'] = "No hay empresas disponibles."
                    jobs = _read_jobs()
                    jobs[job_id] = {
                        "id": job_id,
                        "status": "error",
                        "progress": 0,
                        "message": "No hay empresas disponibles.",
                        "updated_at": time.time()
                    }
                    _write_jobs(jobs)
                    return
            total_empresas = len(empresas)
            
            current_emp = 0
            if total_empresas > 0:
                try:
                    eff_years_count = int(years_count) if years_count is not None else 10
                except Exception:
                    eff_years_count = 10
                for emp in empresas:
                    current_emp += 1
                    base_progress = 10 + int((current_emp / total_empresas) * 80)
                    
                    progress_callback(f"Procesando {emp.nombre}...", base_progress)
                    
                    # Use the generator that supports sync_type logic
                    for step_data in svc.sync_all_years_for_empresa_generator(emp.codigo, sync_type=sync_type, table_ids=parsed_table_ids, sync_data=sync_data, fast_bulk=fast_bulk, years_count=eff_years_count, standard_tables=parsed_standard_tables):
                        maybe_pause()
                        if step_data.startswith("data: "):
                            try:
                                clean_json = step_data.replace("data: ", "").replace("\\n", "").strip()
                                if LOG_PROGRESS:
                                    log_api(f"Progress Update: {clean_json}")
                                data = json.loads(clean_json)
                                progress_callback(data.get('message', ''), data.get('percent', 0))
                            except Exception as e:
                                log_api(f"Global JSON Parse Error: {e} | Data: {step_data}")
            else:
                progress_callback("No hay empresas para sincronizar.", 100)
        
        try:
            if empresa_id and target_year:
                with connections['analytics'].cursor() as c:
                    table_names = ['datiadb_cabeceraalbarancliente', 'datiadb_cabecerapedidocliente', 'datiadb_cabeceraalbaranproveedor']
                    existing = []
                    for t in table_names:
                        c.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = %s", [t])
                        if c.fetchone()[0]:
                            existing.append(t)
                    cab = 0
                    for t in existing:
                        c.execute(
                            f"SELECT COUNT(*) FROM {t} WHERE (codigoempresa = %s OR empresa = %s OR empresacodigo = %s) AND (ejercicioalbaran = %s OR ejercicio = %s OR year = %s)",
                            [int(empresa_id), int(empresa_id), int(empresa_id), int(target_year), int(target_year), int(target_year)],
                        )
                        cab += int(c.fetchone()[0] or 0)
                progress_callback(f"Verificación {empresa_id}/{target_year}: registros={cab}", 98)
            else:
                progress_callback("Verificación básica completada", 98)
        except Exception:
            progress_callback("Verificación no disponible", 98)
        try:
            doms = None
            if standard_tables:
                try:
                    doms = [str(x).strip() for x in standard_tables if str(x).strip() in ['ventas', 'compras']]
                except Exception:
                    doms = None
            pairs = []
            try:
                pairs_set = set()
                with connections['analytics'].cursor() as c:
                    candidates = [
                        'datiadb_cabeceraalbarancliente',
                        'datiadb_cabecerapedidocliente',
                        'datiadb_cabeceraalbaranproveedor',
                    ]
                    for table in candidates:
                        try:
                            c.execute(
                                """
                                SELECT column_name
                                FROM information_schema.columns
                                WHERE table_schema='public' AND table_name=%s
                                """,
                                [table],
                            )
                            cols = {r[0].lower() for r in c.fetchall()}
                            def pick(cands):
                                for name in cands:
                                    if name in cols:
                                        return name
                                return None
                            emp_col = pick(['empresa', 'codigoempresa', 'empresacodigo'])
                            year_col = pick(['ejercicio', 'ejercicioalbaran', 'ejerciciopedido', 'year'])
                            if not emp_col or not year_col:
                                continue
                            sql = f'SELECT "{emp_col}", "{year_col}" FROM "{table}" GROUP BY "{emp_col}", "{year_col}"'
                            if empresa_id:
                                sql = f'SELECT "{emp_col}", "{year_col}" FROM "{table}" WHERE "{emp_col}" = {int(str(empresa_id).strip())} GROUP BY "{emp_col}", "{year_col}"'
                            c.execute(sql)
                            for emp, eje in c.fetchall():
                                if emp is not None and eje is not None:
                                    pairs_set.add((int(emp), int(eje)))
                        except Exception:
                            continue
                pairs = sorted(list(pairs_set), key=lambda x: (x[0], x[1]))
            except Exception:
                pairs = []
            verification = {"ok": True, "pairs": [], "problems": [], "generated_at": time.time()}
            with connections['analytics'].cursor() as c:
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                metrics_tables = {r[0] for r in c.fetchall()}
                def _has_col(table_name: str, candidates):
                    try:
                        c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [table_name])
                        cols = {str(r[0]).lower() for r in c.fetchall()}
                        for cand in candidates:
                            if str(cand).lower() in cols:
                                return True
                    except Exception:
                        return False
                    return False
                sales_art_enabled = _has_col('datiadb_lineasalbarancliente', ['codigoarticulo', 'articulo'])
                purchases_art_enabled = _has_col('datiadb_lineasalbaranproveedor', ['codigoarticulo', 'articulo'])
                for emp, year in pairs:
                    pair_item = {"empresa": int(emp), "ejercicio": int(year), "metrics": []}
                    cod_postal_nonempty = 0
                    try:
                        c.execute(
                            "SELECT COUNT(*) FROM datia_cliente WHERE empresa=%s AND cod_postal IS NOT NULL AND BTRIM(cod_postal) <> ''",
                            [int(emp)],
                        )
                        cod_postal_nonempty = int(c.fetchone()[0] or 0)
                    except Exception:
                        cod_postal_nonempty = 0
                    expected = []
                    if (not doms) or ('ventas' in doms):
                        expected.extend([
                            "metrics_totales_empresa_ejercicio",
                            "metrics_totales_empresa_ejercicio_mes",
                            "metrics_totales_empresa_ejercicio_cliente",
                            "metrics_totales_empresa_ejercicio_cliente_mes",
                        ])
                        if sales_art_enabled:
                            expected.append("metrics_totales_empresa_ejercicio_articulo")
                        if cod_postal_nonempty > 0:
                            expected.append("metrics_totales_empresa_ejercicio_cod_postal")
                    if (not doms) or ('compras' in doms):
                        expected.extend([
                            "metrics_totales_empresa_ejercicio_compra",
                            "metrics_totales_empresa_ejercicio_compra_mes",
                            "metrics_totales_empresa_ejercicio_proveedor",
                            "metrics_totales_empresa_ejercicio_proveedor_mes",
                        ])
                        if purchases_art_enabled:
                            expected.append("metrics_totales_empresa_ejercicio_articulo_compra")
                    for t in expected:
                        item = {"table": t, "rows": 0, "status": "OK"}
                        if t not in metrics_tables:
                            item["status"] = "MISSING"
                            verification["ok"] = False
                            verification["problems"].append({"empresa": int(emp), "ejercicio": int(year), "table": t, "status": "MISSING"})
                            pair_item["metrics"].append(item)
                            continue
                        if t == "metrics_totales_empresa_ejercicio_cod_postal" and cod_postal_nonempty <= 0:
                            item["status"] = "NA"
                            item["rows"] = 0
                            pair_item["metrics"].append(item)
                            continue
                        try:
                            c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE empresa=%s AND ejercicio=%s', [int(emp), int(year)])
                            n = int(c.fetchone()[0] or 0)
                        except Exception:
                            n = 0
                        item["rows"] = n
                        if n <= 0:
                            item["status"] = "ZERO"
                            verification["ok"] = False
                            verification["problems"].append({"empresa": int(emp), "ejercicio": int(year), "table": t, "status": "ZERO"})
                        pair_item["metrics"].append(item)
                    verification["pairs"].append(pair_item)
            if job_id in ETL_JOBS:
                ETL_JOBS[job_id]['verification'] = verification
            progress_callback("Verificación 100% completada", 99)
        except Exception:
            try:
                progress_callback("Verificación 100% no disponible", 99)
            except Exception:
                pass

        progress_callback("Finalizado correctamente", 100)
        if job_id in ETL_JOBS:
            ETL_JOBS[job_id]['status'] = 'completed'
        jobs = _read_jobs()
        jobs[job_id] = {
            "id": job_id,
            "status": "completed",
            "progress": 100,
            "message": "Finalizado correctamente",
            "updated_at": time.time(),
            "verification": (ETL_JOBS.get(job_id, {}) or {}).get("verification"),
        }
        _write_jobs(jobs)
        
    except Exception as e:
        logger.error("ETL Job Failed: %s", e)
        log_api(f"WORKER ERROR (Job={job_id}): {str(e)}")
        try:
            emp_val_rollback = None
            try:
                if empresa_id:
                    emp_val_rollback = int(str(empresa_id).strip())
            except Exception:
                emp_val_rollback = None
            with connections['analytics'].cursor() as cursor:
                if emp_val_rollback is not None:
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                    mt = [r[0] for r in cursor.fetchall()]
                    for t in mt:
                        try:
                            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                            cols = [str(r[0]).lower() for r in cursor.fetchall()]
                            if 'empresa' in cols:
                                cursor.execute(f'DELETE FROM "{t}" WHERE "empresa" = %s', [emp_val_rollback])
                        except Exception:
                            pass
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_financial_%'")
                    ft = [r[0] for r in cursor.fetchall()]
                    for t in ft:
                        try:
                            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                            cols = [str(r[0]).lower() for r in cursor.fetchall()]
                            emp_col = 'empresa' if 'empresa' in cols else None
                            if emp_col:
                                cursor.execute(f'DELETE FROM "{t}" WHERE "{emp_col}" = %s', [emp_val_rollback])
                        except Exception:
                            pass
                    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                    dt = [r[0] for r in cursor.fetchall()]
                    for t in dt:
                        try:
                            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                            cols = [str(r[0]).lower() for r in cursor.fetchall()]
                            emp_col = None
                            for cand in ['codigoempresa', 'empresa', 'empresacodigo', 'company', 'companyid']:
                                if cand in cols:
                                    emp_col = cand
                                    break
                            if emp_col:
                                cursor.execute(f'DELETE FROM "{t}" WHERE "{emp_col}" = %s', [emp_val_rollback])
                        except Exception:
                            pass
                else:
                    pass
        except Exception:
            pass
        if job_id in ETL_JOBS:
            ETL_JOBS[job_id]['status'] = 'error'
            ETL_JOBS[job_id]['error'] = str(e)
            ETL_JOBS[job_id]['progress'] = 0
            ETL_JOBS[job_id]['message'] = f"Error: {str(e)}"
            ETL_JOBS[job_id]['rollback'] = True
        jobs = _read_jobs()
        jobs[job_id] = {
            "id": job_id,
            "status": "error",
            "progress": 0,
            "message": f"Error: {str(e)}",
            "updated_at": time.time()
        }
        _write_jobs(jobs)

@router.post("/sync")
def trigger_sync(
    request,
    empresa_id: str = Query(None),
    table_name: str = Query(None),
    filter_table: str = Query(None),
    sync_type: str = Query("all"),
    table_ids: str = Query(None),
    sync_data: str = Query("true"),
    year: str = Query(None),
    fast_bulk: bool = Query(False),
    years_count: int = Query(10),
    standard_tables: str = Query(None),
    force_reset: bool = Query(False),
    mssql_database: str = Query(None),
    delete_users: bool = Query(False),
    reload_companies: bool = Query(False),
):
    log_api(
        f"trigger_sync CALLED. emp={empresa_id}, table={table_name}, type={sync_type}, "
        f"table_ids={table_ids}, sync_data={sync_data}, year={year}, years_count={years_count}, "
        f"standard_tables={standard_tables}, force_reset={force_reset}, "
        f"delete_users={delete_users}, reload_companies={reload_companies}"
    )
    """
    Triggers an ETL Sync (Structure + Data + Aggregations) in background.
    Optional empresa_id filter for specific sync.
    Optional table_name for granular table sync.
    Optional sync_type: 'all' (default), 'trained' (only DatiaDB_*), 'standard' (only metrics_*)
    Optional table_ids: Comma-separated list of IDs to force sync (e.g. "1,2,3")
    Optional sync_data: "true"/"false" (default: "true"). If false, skips row sync.
    Optional year: "2024" (default: None). If set, limits sync history to 7 years from this year.
    """
    active = _active_sync_job()
    if active:
        return ({
            "status": "busy",
            "message": active.get("message") or "Ya hay una copia en marcha.",
            "job_id": active.get("id"),
        }, 409)

    # Parse boolean
    is_sync_data = sync_data.lower() == 'true'
    if not table_name and filter_table:
        table_name = filter_table

    # Respetar flag de entorno para evitar cualquier conexión a MSSQL al sincronizar estándar
    try:
        import os
        disable_mssql = os.environ.get('DATIA_DISABLE_MSSQL_SYNC', '').lower() in ('1', 'true', 'yes')
    except Exception:
        disable_mssql = False
    if disable_mssql and sync_type in ['standard', 'all']:
        return ({"status": "error", "message": "Sincronización estándar desactivada por DATIA_DISABLE_MSSQL_SYNC"}, 400)

    # DEBUG: Log received parameters
    if LOG_ETL_ENABLED:
        logger.info(
            "trigger_sync params emp=%s table=%s type=%s table_ids=%s sync_data=%s "
            "year=%s fast_bulk=%s years_count=%s standard_tables=%s "
            "force_reset=%s delete_users=%s reload_companies=%s",
            empresa_id,
            table_name,
            sync_type,
            table_ids,
            is_sync_data,
            year,
            fast_bulk,
            years_count,
            standard_tables,
            force_reset,
            delete_users,
            reload_companies,
        )
    
    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "force_reset": bool(force_reset),
        "delete_users": bool(delete_users),
        "reload_companies": bool(reload_companies),
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)
    
    thread = threading.Thread(
        target=full_sync_worker,
        kwargs={
            "job_id": job_id,
            "empresa_id": empresa_id,
            "table_name": table_name,
            "sync_type": sync_type,
            "table_ids": table_ids,
            "sync_data": is_sync_data,
            "target_year": year,
            "fast_bulk": fast_bulk,
            "years_count": years_count,
            "standard_tables": standard_tables,
            "force_reset": force_reset,
            "mssql_database": mssql_database,
            "delete_users": delete_users,
            "reload_companies": reload_companies,
            "empresas_filter": None,
            "skip_cleanup": False,
        },
    )
    thread.daemon = True
    thread.start()
    
    return {"status": "started", "job_id": job_id}


@router.post("/initial_load")
def trigger_initial_load(
    request,
    empresa_id: str = Query(...),
    empresa_label: str = Query(None),
    sync_type: str = Query("all"),
    sync_data: str = Query("true"),
    year: str = Query(None),
    fast_bulk: bool = Query(True),
    years_count: int = Query(10),
    standard_tables: str = Query(None),
    mssql_database: str = Query(None),
    wipe: bool = Query(True),
):
    """
    Proceso 1 - Carga inicial unificada para una empresa.
    Reutiliza full_sync_worker pero permite controlar el borrado previo (wipe).
    """
    is_sync_data = sync_data.lower() == "true"

    # Respetar bandera global para evitar conexiones MSSQL estándar
    try:
        disable_mssql = os.environ.get("DATIA_DISABLE_MSSQL_SYNC", "").lower() in ("1", "true", "yes")
    except Exception:
        disable_mssql = False
    if disable_mssql and sync_type in ["standard", "all"]:
        return ({"status": "error", "message": "Sincronización estándar desactivada por DATIA_DISABLE_MSSQL_SYNC"}, 400)

    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando carga inicial...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "mode": "initial_load",
        "empresa_id": empresa_id,
        "empresa_name": empresa_label or str(empresa_id),
        "wipe": bool(wipe),
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)

    thread = threading.Thread(
        target=full_sync_worker,
        kwargs={
            "job_id": job_id,
            "empresa_id": empresa_id,
            "table_name": None,
            "sync_type": sync_type,
            "table_ids": None,
            "sync_data": is_sync_data,
            "target_year": year,
            "fast_bulk": fast_bulk,
            "years_count": years_count,
            "standard_tables": standard_tables,
            "force_reset": False,
            "mssql_database": mssql_database,
            "delete_users": False,
            "reload_companies": False,
            "empresas_filter": None,
            # wipe=True  -> skip_cleanup=False (borrado previo)
            # wipe=False -> skip_cleanup=True  (sin borrar datos existentes)
            "skip_cleanup": not bool(wipe),
        },
    )
    thread.daemon = True
    thread.start()

    return {"status": "started", "job_id": job_id}


@router.post("/factory_reset")
def trigger_factory_reset(
    request,
    mssql_database: str = Query(None),
    reload_companies: bool = Query(False),
    delete_users: bool = Query(False),
):
    """
    Proceso 2 - Factory reset controlado (modo global analytics).
    Usa full_sync_worker con force_reset=True y sin empresa_id.
    """
    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando Factory Reset...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "mode": "factory_reset",
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)

    thread = threading.Thread(
        target=full_sync_worker,
        kwargs={
            "job_id": job_id,
            "empresa_id": None,
            "table_name": None,
            "sync_type": "all",
            "table_ids": None,
            "sync_data": True,
            "target_year": None,
            "fast_bulk": True,
            "years_count": None,
            "standard_tables": None,
            "force_reset": True,
            "mssql_database": mssql_database,
            "delete_users": bool(delete_users),
            "reload_companies": bool(reload_companies),
            "empresas_filter": None,
            "skip_cleanup": False,
        },
    )
    thread.daemon = True
    thread.start()

    return {"status": "started", "job_id": job_id}


@router.post("/maintenance")
def trigger_maintenance(
    request,
    empresa_id: str = Query(...),
    empresa_label: str = Query(None),
    actions: str = Query("metrics,financial,trained_ai"),
    year: str = Query(None),
    fast_bulk: bool = Query(True),
    years_count: int = Query(3),
    mssql_database: str = Query(None),
):
    """
    Proceso 2 - Mantenimiento sin limpieza destructiva.
    'actions' controla qué sincronizar: metrics, financial, trained_ai.
    """
    acts = {a.strip() for a in str(actions or "").split(",") if a.strip()}
    if not acts:
        acts = {"metrics", "financial"}

    # Determinar sync_type y tablas estándar en función de actions
    sync_type = "all"
    standard_tables = None
    if "trained_ai" in acts and ("metrics" not in acts and "financial" not in acts):
        sync_type = "trained"
    elif "trained_ai" not in acts and ("metrics" in acts or "financial" in acts):
        sync_type = "standard"
    else:
        sync_type = "all"

    std = []
    if "metrics" in acts:
        std.extend(["ventas", "compras", "existencias"])
    if "financial" in acts:
        std.append("financiera")
    if std:
        # quitar duplicados
        seen = set()
        std_clean = []
        for x in std:
            if x not in seen:
                std_clean.append(x)
                seen.add(x)
        standard_tables = ",".join(std_clean)

    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando mantenimiento...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "mode": "maintenance",
        "empresa_id": empresa_id,
        "empresa_name": empresa_label or str(empresa_id),
        "actions": list(acts),
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)

    thread = threading.Thread(
        target=full_sync_worker,
        kwargs={
            "job_id": job_id,
            "empresa_id": empresa_id,
            "table_name": None,
            "sync_type": sync_type,
            "table_ids": None,
            "sync_data": True,
            "target_year": year,
            "fast_bulk": fast_bulk,
            "years_count": years_count,
            "standard_tables": standard_tables,
            "force_reset": False,
            "mssql_database": mssql_database,
            "delete_users": False,
            "reload_companies": False,
            "empresas_filter": None,
            # Mantenimiento → nunca limpiamos datos existentes
            "skip_cleanup": True,
        },
    )
    thread.daemon = True
    thread.start()

    return {"status": "started", "job_id": job_id}

def initial_load_all_worker(job_id, mssql_database=None, years_count: int = 10, fast_bulk: bool = True, standard_tables: str = None):
    try:
        ETL_JOBS[job_id]['status'] = 'starting'
        ETL_JOBS[job_id]['mode'] = 'initial_load_all'
        ETL_JOBS[job_id]['source_db'] = mssql_database
        ETL_JOBS[job_id]['children'] = []
        _write_jobs({**_read_jobs(), job_id: ETL_JOBS[job_id]})
        svc = ETLService(mssql_db=mssql_database)
        conn = svc.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT CodigoEmpresa, Empresa FROM Empresas ORDER BY TRY_CONVERT(int, CodigoEmpresa)")
        rows = cur.fetchall()
        empresas = []
        for r in rows:
            try:
                code = int(str(getattr(r, 'CodigoEmpresa', r[0])).strip())
                name = getattr(r, 'Empresa', r[1]) or f"Empresa {code}"
                empresas.append((code, name))
            except Exception:
                continue
        total = len(empresas)
        idx = 0
        for code, name in empresas:
            idx += 1
            try:
                from datia.models import Empresa as _Empresa
                _Empresa.objects.update_or_create(codigo=int(code), defaults={"nombre": name or f"Empresa {code}"})
            except Exception:
                pass
            child_id = str(uuid.uuid4())
            ETL_JOBS[child_id] = {
                "id": child_id,
                "status": "pending",
                "progress": 0,
                "message": "Iniciando...",
                "created_at": time.time(),
                "source_db": mssql_database,
                "mode": "initial_load",
                "empresa_id": code,
                "empresa_name": name,
                "wipe": True,
            }
            parent = ETL_JOBS.get(job_id, {})
            parent['empresa_id'] = code
            parent['empresa_name'] = name
            parent['progress'] = int((idx - 1) / max(1, total) * 100)
            parent['message'] = f"Migrando {name} ({idx}/{total})"
            ETL_JOBS[job_id] = parent
            jobs_all = _read_jobs()
            jobs_all[job_id] = ETL_JOBS[job_id]
            jobs_all[child_id] = ETL_JOBS[child_id]
            _write_jobs(jobs_all)
            full_sync_worker(
                job_id=child_id,
                empresa_id=str(code),
                table_name=None,
                sync_type="all",
                table_ids=None,
                sync_data=True,
                target_year=None,
                fast_bulk=fast_bulk,
                years_count=years_count,
                standard_tables=standard_tables,
                force_reset=False,
                mssql_database=mssql_database,
                delete_users=False,
                reload_companies=False,
                empresas_filter=None,
                skip_cleanup=False,
            )
            child = ETL_JOBS.get(child_id) or _read_jobs().get(child_id) or {}
            ETL_JOBS[job_id]['children'].append({
                "job_id": child_id,
                "empresa_id": code,
                "empresa_name": name,
                "status": child.get("status"),
                "progress": child.get("progress"),
                "message": child.get("message"),
            })
            ETL_JOBS[job_id]['progress'] = int((idx / max(1, total)) * 100)
            ETL_JOBS[job_id]['message'] = f"Migración {name} finalizada ({idx}/{total})"
            _write_jobs({**_read_jobs(), job_id: ETL_JOBS[job_id]})
        ETL_JOBS[job_id]['status'] = 'completed'
        ETL_JOBS[job_id]['progress'] = 100
        ETL_JOBS[job_id]['message'] = "Carga inicial multiempresa completada"
        _write_jobs({**_read_jobs(), job_id: ETL_JOBS[job_id]})
    except Exception as e:
        ETL_JOBS[job_id]['status'] = 'error'
        ETL_JOBS[job_id]['message'] = str(e)
        _write_jobs({**_read_jobs(), job_id: ETL_JOBS[job_id]})

@router.post("/initial_load_all")
def trigger_initial_load_all(
    request,
    mssql_database: str = Query(...),
    years_count: int = Query(10),
    fast_bulk: bool = Query(True),
    standard_tables: str = Query(None),
):
    try:
        disable_mssql = os.environ.get("DATIA_DISABLE_MSSQL_SYNC", "").lower() in ("1", "true", "yes")
    except Exception:
        disable_mssql = False
    if disable_mssql:
        return ({"status": "error", "message": "Carga inicial desactivada por DATIA_DISABLE_MSSQL_SYNC"}, 400)
    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando carga inicial multiempresa...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "mode": "initial_load_all",
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)
    thread = threading.Thread(
        target=initial_load_all_worker,
        kwargs={
            "job_id": job_id,
            "mssql_database": mssql_database,
            "years_count": years_count,
            "fast_bulk": fast_bulk,
            "standard_tables": standard_tables,
        },
    )
    thread.daemon = True
    thread.start()
    return {"status": "started", "job_id": job_id}

@router.get("/verify_migration")
def verify_migration(request, empresas: str = Query(...)):
    try:
        ids = []
        for x in str(empresas).split(','):
            s = x.strip()
            if s.isdigit():
                ids.append(int(s))
        if not ids:
            return {"status": "error", "message": "Lista de empresas inválida"}, 400
        res = []
        with connections['analytics'].cursor() as c:
            for emp in ids:
                item = {"empresa": emp}
                # Empresa en modelo
                try:
                    from datia.models import Empresa
                    item["empresa_model"] = bool(Empresa.objects.filter(codigo=emp).exists())
                except Exception:
                    item["empresa_model"] = False
                # Helper: contar con columna dinámica
                def count_rows(table_name, emp_val, prefer_cols=('empresa','codigoempresa','empresacodigo','company','companyid'), year_cols=('ejercicio','ejercicioalbaran','ejerciciopedido','year'), year_val=None):
                    try:
                        c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [table_name])
                        cols = {r[0].lower() for r in c.fetchall()}
                        emp_col = None
                        for cand in prefer_cols:
                            if cand in cols:
                                emp_col = cand
                                break
                        if not emp_col:
                            return None
                        if year_val is not None:
                            y_col = None
                            for yc in year_cols:
                                if yc in cols:
                                    y_col = yc
                                    break
                            if y_col:
                                c.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{emp_col}" = %s AND "{y_col}" = %s', [emp_val, year_val])
                                return int(c.fetchone()[0] or 0)
                        c.execute(f'SELECT COUNT(*) FROM "{table_name}" WHERE "{emp_col}" = %s', [emp_val])
                        return int(c.fetchone()[0] or 0)
                    except Exception:
                        return None
                # datiadb cabeceras y líneas (cliente)
                item["cab_alb_cli"] = count_rows("datiadb_cabeceraalbarancliente", emp)
                item["lin_alb_cli"] = count_rows("datiadb_lineasalbarancliente", emp)
                item["cab_ped_cli"] = count_rows("datiadb_cabecerapedidocliente", emp)
                item["lin_ped_cli"] = count_rows("datiadb_lineaspedidocliente", emp)
                # datiadb cabeceras proveedor (si existen)
                item["cab_alb_prov"] = count_rows("datiadb_cabeceraalbaranproveedor", emp)
                item["lin_alb_prov"] = count_rows("datiadb_lineasalbaranproveedor", emp)
                item["cab_ped_prov"] = count_rows("datiadb_cabecerapedidoproveedor", emp)
                item["lin_ped_prov"] = count_rows("datiadb_lineaspedidoproveedor", emp)
                
                # Otras tablas operativas según mapping
                item["acum_stocks"] = count_rows("datia_acumulados_stocks", emp)
                item["fin_acumulados"] = count_rows("datia_financial_acumulados", emp)
                item["fin_presupuestos"] = count_rows("datia_financial_presupuestos", emp)
                item["fin_cartera"] = count_rows("datia_financial_cartera", emp)
                item["fin_groups"] = count_rows("datia_financial_groups", emp)
                item["fin_plan"] = count_rows("datia_financial_plan", emp)
                item["bancos"] = count_rows("datia_banking_bank", emp)
                
                # Maestros
                item["almacenes"] = count_rows("datia_almacenes", emp)
                item["articulos"] = count_rows("datia_articulos", emp)
                item["clientes"] = count_rows("datia_cliente", emp)
                item["proveedores"] = count_rows("datia_proveedores", emp)
                item["familias"] = count_rows("datia_familias", emp)
                item["comisionistas"] = count_rows("datia_comisionistas", emp)
                # metrics totales por empresa/ejercicio
                try:
                    c.execute('SELECT COUNT(*) FROM "metrics_totales_empresa_ejercicio" WHERE "empresa" = %s', [emp])
                    item["metrics_emp_eje"] = int(c.fetchone()[0] or 0)
                except Exception:
                    item["metrics_emp_eje"] = None
                # acumulados financieros
                try:
                    c.execute('SELECT COUNT(*) FROM "datia_financial_acumulados" WHERE "empresa" = %s', [emp])
                    item["financial_acum"] = int(c.fetchone()[0] or 0)
                except Exception:
                    item["financial_acum"] = None
                res.append(item)
        return {"status": "ok", "summary": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@router.post("/drop_physical")
def drop_physical_tables(request, table_ids: str = Query(None)):
    # Seguridad: solo usuarios autenticados con rol Administrators o superuser
    try:
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return {"status": "error", "message": "Autenticación requerida"}, 401
        is_admin = getattr(user, 'is_superuser', False)
        try:
            if not is_admin:
                is_admin = user.groups.filter(name='Administrators').exists()
        except Exception:
            pass
        if not is_admin:
            return {"status": "error", "message": "Acceso denegado. Requiere Administrador."}, 403
    except Exception:
        # En caso de no poder verificar, denegar por defecto
        return {"status": "error", "message": "No se pudo verificar permisos"}, 403
    if not table_ids:
        return {"status": "error", "message": "table_ids requerido"}, 400
    try:
        ids = []
        try:
            ids = [int(x) for x in str(table_ids).split(',') if x.strip().isdigit()]
        except:
            ids = []
        if not ids:
            return {"status": "error", "message": "table_ids inválido"}, 400
        dropped = []
        pg_conn = None
        try:
            from django.db import connections
            pg_conn = connections['analytics']
        except Exception as e:
            return {"status": "error", "message": f"Conexión analytics no disponible: {e}"}, 500
        sources = list(DataSource.objects.filter(id__in=ids))
        if not sources:
            return {"status": "error", "message": "No se encontraron fuentes"}, 404
        with pg_conn.cursor() as cursor:
            for ds in sources:
                table_name = ds.get_local_table_name()
                if table_name:
                    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
                    dropped.append(table_name)
        try:
            logger.info(f"drop_physical by user={getattr(request.user, 'id', None)} tables={dropped}")
        except Exception:
            pass
        return {"status": "ok", "dropped": dropped}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@router.get("/sync/readiness")
def sync_readiness(request, empresa_id: int = Query(...), year: int = Query(None)):
    from datia.models.totales import MetricsTotalesEmpresaEjercicio
    qs = MetricsTotalesEmpresaEjercicio.objects.filter(empresa=empresa_id)
    years = list(qs.order_by('-ejercicio').values_list('ejercicio', flat=True)[:12])
    year_rows = qs.filter(ejercicio=year).count() if year else 0
    job = _active_sync_job()
    return {
        "status": "ok",
        "has_metrics": qs.exists(),
        "metrics_rows": qs.count(),
        "years": years,
        "year_rows": year_rows,
        "chat_ready": bool(year_rows) if year else qs.exists(),
        "suggested_years": 1 if qs.exists() else 7,
        "job_running": bool(job),
        "job_message": (job or {}).get("message") or "",
    }

@router.get("/preview_sources")
def preview_sources(request, empresa_id: str = Query(...), year: int = Query(None), sync_type: str = Query("all"), standard_tables: str = Query(None), table_ids: str = Query(None)):
    try:
        import os
        if os.environ.get('DATIA_DISABLE_MSSQL_SYNC', '').lower() in ('1', 'true', 'yes'):
            return JsonResponse({"status": "error", "message": "Vista previa desactivada por DATIA_DISABLE_MSSQL_SYNC"}, status=400)
    except Exception:
        pass
    try:
        svc = ETLService()
        conn = svc.get_connection()
        if not conn:
            return JsonResponse({"status": "error", "message": "No se pudo conectar a MSSQL"}, status=500)
        cur = conn.cursor()
        res = []
        def norm_emp(val):
            s = str(val).strip()
            arr = [s]
            try:
                i = int(s)
                arr += [str(i), str(i).zfill(2), str(i).zfill(3)]
            except:
                try:
                    arr.append(str(int(s)))
                except:
                    pass
            out = []
            for x in arr:
                if x not in out:
                    out.append(x)
            return out
        emp_vals = norm_emp(empresa_id)
        sel_std = None
        if standard_tables:
            try:
                sel_std = [x.strip() for x in standard_tables.split(',') if x.strip() in ['ventas','compras','financiera','existencias']]
            except:
                sel_std = None
        do_std = sync_type in ['all', 'standard']
        if do_std:
            if not sel_std:
                sel_std = ['ventas','compras','financiera','existencias']
            if 'ventas' in sel_std:
                cands_cab = svc.get_table_candidates(cur, 'cabecera')
                tab_cab, map_cab = svc.pick_best_table(cur, cands_cab, svc.COLUMN_MAP_CABECERA, ['empresa','ejercicio','serie','numero','fecha','cliente'])
                if tab_cab:
                    where = []
                    params = []
                    if 'empresa' in map_cab:
                        where.append(f"T.{map_cab['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                        params += emp_vals
                    if year is not None and 'ejercicio' in map_cab:
                        where.append(f"T.{map_cab['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_cab} T"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"ventas_cabecera","table":tab_cab,"count":int(cnt)})
                cands_lin = svc.get_table_candidates(cur, 'lineas')
                tab_lin, map_lin = svc.pick_best_table(cur, cands_lin, svc.COLUMN_MAP_LINEAS, ['empresa','ejercicio','serie','numero','articulo','cantidad','neto'])
                if tab_lin:
                    where = []
                    params = []
                    if 'empresa' in map_lin:
                        where.append(f"T.{map_lin['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                        params += emp_vals
                    if year is not None and 'ejercicio' in map_lin:
                        where.append(f"T.{map_lin['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_lin} T"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"ventas_lineas","table":tab_lin,"count":int(cnt)})
            if 'compras' in sel_std:
                cands_cab = svc.get_table_candidates(cur, 'cabecera_compra')
                tab_cab, map_cab = svc.pick_best_table(cur, cands_cab, svc.COLUMN_MAP_CABECERA_COMPRA, ['empresa','ejercicio','serie','numero','fecha','proveedor'])
                if tab_cab:
                    where = []
                    params = []
                    if 'empresa' in map_cab:
                        where.append(f"T.{map_cab['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                        params += emp_vals
                    if year is not None and 'ejercicio' in map_cab:
                        where.append(f"T.{map_cab['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_cab} T"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"compras_cabecera","table":tab_cab,"count":int(cnt)})
                cands_lin = svc.get_table_candidates(cur, 'lineas_compra')
                tab_lin, map_lin = svc.pick_best_table(cur, cands_lin, svc.COLUMN_MAP_LINEAS_COMPRA, ['empresa','ejercicio','serie','numero','articulo','cantidad','neto'])
                if tab_lin:
                    where = []
                    params = []
                    if 'empresa' in map_lin:
                        where.append(f"T.{map_lin['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                        params += emp_vals
                    if year is not None and 'ejercicio' in map_lin:
                        where.append(f"T.{map_lin['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_lin} T"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"compras_lineas","table":tab_lin,"count":int(cnt)})
            if 'financiera' in sel_std:
                cands_plan = svc.get_table_candidates(cur, 'plan_cuentas')
                cands_acum = svc.get_table_candidates(cur, 'acumulados')
                tab_plan, map_plan = svc.pick_best_table(cur, cands_plan, svc.COLUMN_MAP_PLAN_CUENTAS, ['empresa','codigo'])
                if tab_plan and 'empresa' in map_plan:
                    where = f"T.{map_plan['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")"
                    sql = f"SELECT COUNT(*) FROM {tab_plan} T WHERE {where}"
                    cur.execute(sql, tuple(emp_vals))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"financiera_plan","table":tab_plan,"count":int(cnt)})
                tab_acum, map_acum = svc.pick_best_table(cur, cands_acum, svc.COLUMN_MAP_ACUMULADOS, ['empresa','ejercicio','cuenta','periodo'])
                if tab_acum and 'empresa' in map_acum:
                    where = []
                    params = []
                    where.append(f"T.{map_acum['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                    params += emp_vals
                    if year is not None and 'ejercicio' in map_acum:
                        where.append(f"T.{map_acum['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_acum} T WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"financiera_acumulados","table":tab_acum,"count":int(cnt)})
                try:
                    cur.execute("SELECT COUNT(*) FROM CarteraEfectos WHERE CodigoEmpresa=? AND Ejercicio=?", (empresa_id, year if year is not None else 0))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"cartera_efectos","table":"CarteraEfectos","count":int(cnt)})
                except:
                    pass
            if 'existencias' in sel_std:
                cands_stk = svc.get_table_candidates(cur, 'stocks')
                tab_stk, map_stk = svc.pick_best_table(cur, cands_stk, svc.COLUMN_MAP_STOCKS, ['empresa','ejercicio','periodo','articulo','importe_saldo'])
                if tab_stk:
                    where = []
                    params = []
                    if 'empresa' in map_stk:
                        where.append(f"T.{map_stk['empresa']} IN (" + ",".join("?" for _ in emp_vals) + ")")
                        params += emp_vals
                    if year is not None and 'ejercicio' in map_stk:
                        where.append(f"T.{map_stk['ejercicio']} = ?")
                        params.append(year)
                    sql = f"SELECT COUNT(*) FROM {tab_stk} T"
                    if where:
                        sql += " WHERE " + " AND ".join(where)
                    cur.execute(sql, tuple(params))
                    cnt = cur.fetchone()[0] or 0
                    res.append({"domain":"existencias","table":tab_stk,"count":int(cnt)})
        do_trained = sync_type in ['all', 'trained']
        if do_trained:
            try:
                ids = None
                if table_ids:
                    try:
                        ids = [int(x) for x in str(table_ids).split(',') if str(x).strip().isdigit()]
                    except Exception:
                        ids = None
                try:
                    emp_int = int(empresa_id)
                except Exception:
                    emp_int = None
                qs = DataSource.objects.all()
                if emp_int is not None:
                    qs = qs.filter(empresa_id=emp_int)
                if ids:
                    qs = qs.filter(id__in=ids)
                sources = list(qs)
                EMP_CANDS = {'empresa','codigoempresa','codempresa','idempresa','empresaid','company','companyid'}
                EJER_CANDS = {'ejercicio','anio','ano','year','ejerciciofiscal','fiscalyear'}
                def san(x):
                    import re
                    return re.sub(r'[^a-z0-9]', '', str(x).lower())
                for src in sources:
                    table = src.source_table
                    col_emp = None
                    col_ej = None
                    try:
                        cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (table,))
                        cols = [r[0] for r in cur.fetchall()]
                        for c in cols:
                            sc = san(c)
                            if not col_emp and sc in EMP_CANDS:
                                col_emp = c
                            if not col_ej and sc in EJER_CANDS:
                                col_ej = c
                            if col_emp and col_ej:
                                break
                    except Exception:
                        pass
                    try:
                        where = []
                        params = []
                        if col_emp:
                            where.append(f"T.[{col_emp}] IN (" + ",".join("?" for _ in emp_vals) + ")")
                            params += emp_vals
                        if (year is not None) and col_ej:
                            where.append(f"T.[{col_ej}] = ?")
                            params.append(year)
                        sql = f"SELECT COUNT(*) FROM {table} T"
                        if where:
                            sql += " WHERE " + " AND ".join(where)
                        cur.execute(sql, tuple(params))
                        cnt = cur.fetchone()[0] or 0
                    except Exception:
                        try:
                            cur.execute(f"SELECT COUNT(*) FROM {table}")
                            cnt = cur.fetchone()[0] or 0
                        except Exception:
                            cnt = 0
                    pg_name = src.get_local_table_name()
                    res.append({
                        "domain": f"entrenada: {src.name}",
                        "table": table,
                        "count": int(cnt),
                        "postgres_table": pg_name,
                        "postgres_count": _pg_row_count(pg_name, empresa_id, year),
                    })
            except Exception:
                pass
        for item in res:
            dest = _DOMAIN_PG.get(item.get("domain"))
            if dest and "postgres_count" not in item:
                item["postgres_table"] = dest
                item["postgres_count"] = _pg_row_count(dest, empresa_id, year)
        return JsonResponse({"status": "ok", "entries": res})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@router.post("/incremental/sales")
def incremental_sales(request, empresa_id: str, year: int, days: int = 7):
    etl = ETLService()
    if not etl.has_baseline(int(empresa_id), int(year), 'ventas'):
        return ({"status": "error", "message": "La migración incremental requiere baseline previo. Ejecute sincronización completa primero."}, 400)
    msgs = []
    for update in etl.sync_mssql_sales_incremental_generator(empresa_id, int(year), days_back=int(days)):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}
@router.post("/incremental/purchases")
def incremental_purchases(request, empresa_id: str, year: int, days: int = 7):
    etl = ETLService()
    if not etl.has_baseline(int(empresa_id), int(year), 'compras'):
        return ({"status": "error", "message": "La migración incremental requiere baseline previo. Ejecute sincronización completa primero."}, 400)
    msgs = []
    for update in etl.sync_mssql_purchases_incremental_generator(empresa_id, int(year), days_back=int(days)):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}
@router.post("/incremental/financial")
def incremental_financial(request, empresa_id: str, year: int):
    etl = ETLService()
    if not etl.has_baseline(int(empresa_id), int(year), 'financiera'):
        return ({"status": "error", "message": "La migración incremental requiere baseline previo. Ejecute sincronización completa primero."}, 400)
    msgs = []
    for update in etl.sync_mssql_financial_incremental_generator(empresa_id, int(year)):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}
@router.post("/incremental/cartera")
def incremental_cartera(request, empresa_id: str, year: int, days: int = Query(7)):
    etl = ETLService()
    if not etl.has_baseline(int(empresa_id), int(year), 'cartera'):
        return ({"status": "error", "message": "La migración incremental requiere baseline previo. Ejecute sincronización completa primero."}, 400)
    msgs = []
    for update in etl.sync_mssql_cartera_incremental_generator(empresa_id, int(year), days_back=int(days)):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}
@router.post("/incremental/stocks")
def incremental_stocks(request, empresa_id: str, year: int, periods: int = Query(2)):
    etl = ETLService()
    if not etl.has_baseline(int(empresa_id), int(year), 'existencias'):
        return ({"status": "error", "message": "La migración incremental requiere baseline previo. Ejecute sincronización completa primero."}, 400)
    msgs = []
    for update in etl.sync_mssql_stocks_incremental_generator(empresa_id, int(year), periods_back=int(periods)):
        msgs.append(str(update))
    return {"status": "ok", "logs": len(msgs)}
@router.get("/status/{job_id}")
def check_sync_status(request, job_id: str):
    job = ETL_JOBS.get(job_id)
    if not job:
        jobs = _read_jobs()
        job = jobs.get(job_id)
        if not job:
            return {"status": "not_found"}
    try:
        created = job.get('created_at') or time.time()
        updated = job.get('updated_at') or time.time()
        elapsed_ms = int((updated - created) * 1000)
        p = float(job.get('progress') or 0.0)
        eta_ms = None
        if p > 0 and p < 100:
            rate = p / max((updated - created), 0.001)
            eta_ms = int(((100 - p) / rate) * 1000)
        logs_tail = []
        try:
            with connections['analytics'].cursor() as c:
                c.execute("""
                    SELECT ts, process_name, table_name, operation, rows_count, state, message
                    FROM datia_audit.oplog
                    WHERE process_name=%s
                    ORDER BY ts DESC
                    LIMIT 20
                """, [f"workflow:{job_id}"])
                for r in c.fetchall():
                    logs_tail.append({
                        "ts": r[0].isoformat() if r[0] else None,
                        "process": r[1],
                        "table": r[2],
                        "operation": r[3],
                        "rows": int(r[4] or 0),
                        "state": r[5],
                        "message": r[6]
                    })
        except Exception:
            logs_tail = []
        stage = job.get('stage')
        stage_progress = None
        current_table = None
        rps = None
        last_error = None
        try:
            if stage == 'cleanup':
                cl = job.get('cleanup', {}).get('tables', []) or []
                if cl:
                    actives = [x for x in cl if str(x.get('action','')).lower() != 'skip']
                    total = len(actives)
                    ok = len([x for x in actives if str(x.get('status','')).upper() == 'OK'])
                    stage_progress = int((ok / max(1, total)) * 100)
                    pending = next((x for x in actives if str(x.get('status','')).upper() != 'OK'), None)
                    if pending:
                        current_table = pending.get('table')
            elif stage == 'sync':
                child_id = job.get('child_id')
                if child_id:
                    cj = ETL_JOBS.get(child_id) or _read_jobs().get(child_id) or {}
                    try:
                        stage_progress = int(cj.get('progress') or 0)
                    except Exception:
                        stage_progress = None
                # 1) Intentar deducir por DML reciente
                with connections['analytics'].cursor() as c:
                    c.execute("""
                        SELECT table_name, max(ts) FROM datia_audit.oplog
                        WHERE operation IN ('INSERT','UPDATE','DELETE')
                          AND table_name IS NOT NULL
                          AND ts >= now() - interval '30 seconds'
                        GROUP BY table_name
                        ORDER BY max(ts) DESC
                        LIMIT 1
                    """)
                    row = c.fetchone()
                    if row:
                        current_table = row[0]
                    c.execute("""
                        SELECT COALESCE(sum(rows_count),0)
                        FROM datia_audit.oplog
                        WHERE operation IN ('INSERT','UPDATE','DELETE')
                          AND ts >= now() - interval '10 seconds'
                    """)
                    total_rows = int(c.fetchone()[0] or 0)
                    rps = round(total_rows / 10.0, 2)
                # 2) Fallback: extraer tabla del mensaje del job hijo si no hay DML reciente
                if not current_table:
                    try:
                        import re
                        msg_src = (cj.get('message') if child_id else None) or job.get('message') or ''
                        m = re.search(r'(datiadb_[a-z0-9_]+|datia_financial_[a-z0-9_]+)', str(msg_src), flags=re.IGNORECASE)
                        if m:
                            current_table = m.group(1)
                    except Exception:
                        pass
            elif stage == 'metrics':
                try:
                    base = 82.0
                    span = 15.0
                    stage_progress = int(max(0.0, min(100.0, ((p - base) / span) * 100.0)))
                except Exception:
                    stage_progress = None
            with connections['analytics'].cursor() as c:
                c.execute("""
                    SELECT ts, message FROM datia_audit.oplog
                    WHERE state='error'
                      AND process_name=%s
                      AND ts >= now() - interval '10 minutes'
                    ORDER BY ts DESC
                    LIMIT 1
                """, [f"workflow:{job_id}"])
                e = c.fetchone()
                if e:
                    last_error = {"ts": e[0].isoformat() if e[0] else None, "message": e[1]}
        except Exception:
            pass
        # Corrección de valores obsoletos: si no estamos en 'sync', limpiar la tabla actual
        try:
            if stage != 'sync' and 'current_table' in job:
                del job['current_table']
        except Exception:
            pass
        # Normalizar estados PENDING para tablas banking en cualquier etapa
        try:
            cl_fix = job.get('cleanup', {}).get('tables', []) or []
            changed = False
            for i, item in enumerate(cl_fix):
                tn = str(item.get('table') or '')
                if item.get('status') == 'PENDING' and tn.startswith('datia_banking_'):
                    cl_fix[i]['status'] = 'SKIPPED'
                    changed = True
            if changed:
                job['cleanup']['tables'] = cl_fix
                try:
                    ETL_JOBS[job_id]['cleanup']['tables'] = cl_fix
                    jobs = _read_jobs()
                    jobs[job_id] = ETL_JOBS[job_id]
                    _write_jobs(jobs)
                except Exception:
                    pass
        except Exception:
            pass
        job['telemetry'] = {
            "elapsed_ms": elapsed_ms,
            "eta_ms": eta_ms,
            "server_time": int(time.time()*1000)
        }
        job['log_tail'] = list(reversed(logs_tail))
        if stage_progress is not None:
            job['stage_progress'] = int(stage_progress)
        if current_table:
            job['current_table'] = current_table
        if rps is not None:
            job['rps'] = rps
        if last_error:
            job['last_error'] = last_error
    except Exception:
        pass
    return job

@router.get("/logs/{job_id}")
def get_job_logs(request, job_id: str, fmt: str = Query("json"), limit: int = Query(1000)):
    try:
        rows = []
        with connections['analytics'].cursor() as c:
            c.execute("""
                SELECT ts, process_name, table_name, operation, rows_count, state, message
                FROM datia_audit.oplog
                WHERE process_name=%s
                ORDER BY ts ASC
                LIMIT %s
            """, [f"workflow:{job_id}", int(max(1, min(limit, 5000)))])
            for r in c.fetchall():
                rows.append({
                    "ts": r[0].isoformat() if r[0] else None,
                    "process": r[1],
                    "table": r[2],
                    "operation": r[3],
                    "rows": int(r[4] or 0),
                    "state": r[5],
                    "message": r[6]
                })
        if (fmt or '').lower() == 'csv':
            data = "ts,process,table,operation,rows,state,message\n"
            for x in rows:
                m = (x['message'] or '').replace('"','""').replace('\n',' ').replace('\r',' ')
                t = (x['table'] or '')
                data += f"{x['ts']},{x['process']},{t},{x['operation']},{x['rows']},{x['state']},\"{m}\"\n"
            resp = HttpResponse(data, content_type="text/csv; charset=utf-8")
            resp['Content-Disposition'] = f'attachment; filename="workflow_{job_id}_logs.csv"'
            return resp
        return {"status": "ok", "job_id": job_id, "logs": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@router.post("/job/{job_id}/pause")
def pause_job(request, job_id: str):
    job = ETL_JOBS.get(job_id) or _read_jobs().get(job_id)
    if not job:
        return {"status": "not_found"}, 404
    ETL_JOBS[job_id] = dict(job, pause=True, status="paused")
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)
    return {"status": "ok", "job_id": job_id, "pause": True}

@router.post("/job/{job_id}/resume")
def resume_job(request, job_id: str):
    job = ETL_JOBS.get(job_id) or _read_jobs().get(job_id)
    if not job:
        return {"status": "not_found"}, 404
    ETL_JOBS[job_id] = dict(job, pause=False)
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)
    return {"status": "ok", "job_id": job_id, "pause": False}

@router.get("/check/raw_sales_presence")
def check_raw_sales_presence(request, empresa: int, ejercicio: int):
    from django.db import connections
    alias = 'analytics' if 'analytics' in connections.databases else 'default'
    cab = 0
    lin = 0
    try:
        with connections[alias].cursor() as c:
            try:
                c.execute(
                    'SELECT COUNT(*) FROM datiadb_cabeceraalbarancliente WHERE "codigoempresa" = %s AND "ejercicio" = %s',
                    [empresa, ejercicio]
                )
                cab = int(c.fetchone()[0] or 0)
            except Exception:
                cab = 0
            try:
                c.execute(
                    'SELECT COUNT(*) FROM datiadb_lineasalbarancliente WHERE "codigoempresa" = %s AND "ejercicio" = %s',
                    [empresa, ejercicio]
                )
                lin = int(c.fetchone()[0] or 0)
            except Exception:
                lin = 0
    except Exception:
        cab = 0
        lin = 0
    status = "ok" if (cab > 0 and lin > 0) else "empty"
    return {"empresa": empresa, "ejercicio": ejercicio, "cabecera": cab, "lineas": lin, "status": status}

@router.get("/mssql/databases")
def list_mssql_databases(request):
    try:
        import pyodbc
        from datia.services.runtime_config import mssql_connection_string
        conn_str = mssql_connection_string('master')
        try:
            pyodbc.pooling = False
        except Exception:
            pass
        conn = pyodbc.connect(conn_str)
        cur = conn.cursor()
        names = []
        try:
            cur.execute("SELECT name FROM sys.databases WHERE HAS_DBACCESS(name)=1 AND name NOT IN ('master','tempdb','model','msdb') ORDER BY name")
            rows = cur.fetchall()
            names = [str(r[0]) for r in rows]
        except Exception:
            try:
                cur.execute("EXEC sp_databases")
                rows = cur.fetchall()
                tmp = []
                for r in rows:
                    val = None
                    try:
                        val = getattr(r, 'DATABASE_NAME', None)
                    except Exception:
                        val = None
                    if not val:
                        try:
                            val = getattr(r, 'DB_NAME', None)
                        except Exception:
                            val = None
                    if not val:
                        try:
                            val = r[0]
                        except Exception:
                            val = None
                    if val:
                        s = str(val)
                        if s.lower() not in ('master','tempdb','model','msdb'):
                            tmp.append(s)
                names = tmp
            except Exception:
                names = []
        seen = set()
        uniq = []
        for n in names:
            s = str(n)
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "ok", "databases": uniq}
    except Exception as e:
        return {"status": "ok", "databases": []}

@router.get("/mssql/empresas")
def list_mssql_empresas(request, db: str = Query(...)):
    try:
        svc = ETLService(mssql_db=db)
        conn = svc.get_connection()
        cur = conn.cursor()
        fields = {}
        try:
            fields = svc.static_mapping.get('Empresas', {})
        except Exception:
            fields = {}
        col_emp = fields.get('empresa') or fields.get('empresa_id') or 'CodigoEmpresa'
        col_nom = fields.get('nombre') or 'Empresa'
        # Intento 1: columnas completas (si existen en esta instancia)
        rows = None
        try:
            col_cif = fields.get('cif')
            col_fc = fields.get('fecha_creacion')
            cols = [f"{col_emp} as empresa", f"{col_nom} as nombre"]
            if col_cif:
                cols.append(f"{col_cif} as cif")
            if col_fc:
                cols.append(f"{col_fc} as fecha_creacion")
            sql = f"SELECT {', '.join(cols)} FROM Empresas ORDER BY {col_emp}"
            cur.execute(sql)
            rows = cur.fetchall()
        except Exception:
            # Fallback mínimo: solo empresa y nombre, evitando depender de mapping secundario
            try:
                cur.execute(f"SELECT {col_emp} as empresa, {col_nom} as nombre FROM Empresas ORDER BY {col_emp}")
                rows = cur.fetchall()
            except Exception:
                # Último fallback: nombres fijos más comunes
                cur.execute("SELECT CodigoEmpresa as empresa, Empresa as nombre FROM Empresas ORDER BY CodigoEmpresa")
                rows = cur.fetchall()
        items = []
        for r in rows:
            emp_val = None
            nom_val = None
            try:
                emp_val = getattr(r, 'empresa', None)
            except Exception:
                pass
            try:
                nom_val = getattr(r, 'nombre', None)
            except Exception:
                pass
            # Compatibilidad por índice si el driver no expone atributos
            if emp_val is None or nom_val is None:
                try:
                    emp_val = emp_val if emp_val is not None else r[0]
                    nom_val = nom_val if nom_val is not None else r[1]
                except Exception:
                    pass
            d = {"empresa": int(str(emp_val).strip() or "0") if emp_val is not None else 0,
                 "nombre": str(nom_val or "").strip()}
            try:
                d["cif"] = str(getattr(r, 'cif', '')).strip()
            except Exception:
                pass
            try:
                v = getattr(r, 'fecha_creacion', None)
                d["fecha_creacion"] = v.isoformat() if v else None
            except Exception:
                d["fecha_creacion"] = None
            items.append(d)
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "ok", "items": items}
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "error", "message": str(e)}, 500

@router.get("/analytics/tables")
def list_pg_tables(request, prefix: str = Query(None), sort: str = Query("size"), order: str = Query("desc")):
    try:
        rows = []
        with connections['analytics'].cursor() as c:
            c.execute("""
                SELECT n.nspname AS schema, c.relname AS table, c.reltuples::BIGINT AS approx_rows, pg_total_relation_size(c.oid) AS total_bytes
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname='public' AND c.relkind='r'
            """)
            for r in c.fetchall():
                schema, table, approx_rows, total_bytes = r
                name = str(table)
                cat = 'other'
                if name.startswith('datiadb_'):
                    cat = 'datiadb'
                elif name.startswith('datia_'):
                    cat = 'datia'
                elif name.startswith('metrics_'):
                    cat = 'metrics'
                rows.append({
                    "schema": schema,
                    "table": name,
                    "category": cat,
                    "approx_rows": int(approx_rows or 0),
                    "total_bytes": int(total_bytes or 0)
                })
        if prefix:
            p = prefix.lower()
            rows = [x for x in rows if x['table'].lower().startswith(p)]
        key = 'total_bytes' if sort in ['size','total_bytes'] else ('approx_rows' if sort in ['rows','approx_rows'] else 'table')
        rev = (order.lower() != 'asc')
        rows.sort(key=lambda x: x[key], reverse=rev)
        return {"status": "ok", "tables": rows}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@router.post("/analytics/drop_non_tpl_auth")
def drop_non_tpl_auth_tables(request):
    try:
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return {"status": "error", "message": "Autenticación requerida"}, 401
        if not getattr(user, 'is_superuser', False):
            return {"status": "error", "message": "Acceso denegado. Requiere Admin."}, 403
        dropped = []
        skipped = []
        with connections['analytics'].cursor() as c:
            c.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='public' AND table_type='BASE TABLE'
            """)
            rows = [r[0] for r in c.fetchall()]
            protected_prefixes = ('tpl_', 'auth_')
            protected_exact = set([
                # Tablas core de Django
                'django_migrations',
                'django_content_type',
                'django_admin_log',
                'django_session',
                'django_site',
                # Tablas core de configuración Datia (no deben borrarse)
                'datia_globalconfig',
                'datia_userpreference',
                'datia_mobile_config',
                'datia_sync_checkpoints',
                'datia_widgetconfig',
                'datia_widgetstate'
            ])
            for name in rows:
                tn = str(name)
                low = tn.lower()
                if low.startswith(protected_prefixes) or low in protected_exact:
                    skipped.append(tn)
                    continue
                try:
                    c.execute(f'DROP TABLE IF EXISTS \"{tn}\" CASCADE')
                    dropped.append(tn)
                except Exception:
                    skipped.append(tn)
        return {"status": "ok", "dropped": dropped, "skipped": skipped, "count": len(dropped)}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@router.get("/analytics/users/preview_deletion")
def preview_users_to_delete(request):
    try:
        qs = User.objects.exclude(username='admin').values('username','email','is_superuser','is_staff','date_joined')
        users = []
        for u in qs:
            users.append({
                "username": u.get('username'),
                "email": u.get('email'),
                "is_superuser": bool(u.get('is_superuser')),
                "is_staff": bool(u.get('is_staff')),
                "date_joined": u.get('date_joined').isoformat() if u.get('date_joined') else None
            })
        return {"status": "ok", "count": len(users), "users": users}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

def workflow_worker(job_id, mssql_database=None, years_count: int = None, include_domains: str = None, verify_samples_year: int = None, delete_users_except_admin: bool = True, dry_run: bool = False, empresa_id: str = None, empresas_filter: str = None):
    def update(msg, pct, st='running'):
        if job_id in ETL_JOBS:
            ETL_JOBS[job_id]['status'] = st
            ETL_JOBS[job_id]['message'] = msg
            ETL_JOBS[job_id]['progress'] = pct
            ETL_JOBS[job_id]['updated_at'] = time.time()
        jobs = _read_jobs()
        jobs[job_id] = {
            "id": job_id,
            "status": st,
            "progress": pct,
            "message": msg,
            "updated_at": time.time()
        }
        _write_jobs(jobs)
    def audit(process, table, operation, rows, state, message, duration=None):
        try:
            with connections['analytics'].cursor() as c:
                c.execute("SELECT datia_audit.log_event(%s,%s,%s,%s,%s,%s,%s,'public')",
                          [process, table, operation, int(rows or 0), state, message, duration if duration is not None else None])
        except Exception:
            pass
    try:
        log_initial_load("info", "workflow_start", {"job_id": job_id, "db": mssql_database, "years_count": years_count, "empresa_id": empresa_id, "empresas_filter": empresas_filter})
        threading.Thread(target=heartbeat_job, args=(job_id,), daemon=True).start()
        ETL_JOBS[job_id]['status'] = 'running'
        ETL_JOBS[job_id]['stage'] = 'cleanup'
        audit(f"workflow:{job_id}", None, "STATUS", 0, "started", "Inicio workflow")
        update("Preparando limpieza", 2)
        size_before = _get_db_size('analytics')
        
        # Determine scope: Global vs Per-Empresa
        emp_val = None
        if empresa_id:
            try:
                emp_val = int(str(empresa_id).strip())
            except:
                pass
        
        cleanup_tables = []
        to_truncate = []
        to_drop = []
        
        if emp_val:
            # --- PER-EMPRESA SCOPED CLEANUP ---
            update(f"Limpieza selectiva para empresa {emp_val}", 3)
            # We will DELETE rows from metrics_ and datiadb_ tables where empresa matches
            # We will NOT touch datia_* config tables or users
            
            targets = []
            with connections['analytics'].cursor() as c:
                # Metrics tables
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                targets += [r[0] for r in c.fetchall()]
                # DatiaDB tables (excluyendo datiadb_ai*)
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                targets += [r[0] for r in c.fetchall()]
                # Financial tables
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_financial_%'")
                targets += [r[0] for r in c.fetchall()]

            active_total = len(targets)
            done_count = 0
            
            with connections['analytics'].cursor() as c:
                for t in targets:
                    try:
                        # Determine empresa column
                        emp_col = None
                        c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                        cols = [str(r[0]).lower() for r in c.fetchall()]
                        for cand in ['codigoempresa', 'empresa', 'empresacodigo', 'company', 'companyid']:
                            if cand in cols:
                                emp_col = cand
                                break
                        
                        if emp_col:
                            # Count before
                            c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE "{emp_col}" = %s', [emp_val])
                            before = int(c.fetchone()[0] or 0)
                            
                            if before > 0:
                                update(f"Limpiando {t} (Empresa {emp_val})", 3 + int((done_count / max(1, active_total)) * 20))
                                c.execute(f'DELETE FROM "{t}" WHERE "{emp_col}" = %s', [emp_val])
                                audit(f"workflow:{job_id}", t, "DELETE", before, "completed", f"Removed {before} rows for empresa {emp_val}")
                                cleanup_tables.append({
                                    "table": t,
                                    "action": "delete_rows",
                                    "before": before,
                                    "deleted": before,
                                    "after": 0,
                                    "status": "OK"
                                })
                            else:
                                cleanup_tables.append({
                                    "table": t,
                                    "action": "delete_rows",
                                    "before": 0,
                                    "deleted": 0,
                                    "after": 0,
                                    "status": "OK (Empty)"
                                })
                        else:
                            cleanup_tables.append({
                                "table": t,
                                "action": "skip",
                                "before": 0,
                                "deleted": 0,
                                "after": 0,
                                "status": "SKIPPED (No company col)"
                            })
                    except Exception as e:
                        cleanup_tables.append({
                            "table": t,
                            "action": "error",
                            "status": f"ERROR: {str(e)}"
                        })
                    finally:
                        done_count += 1
            
            # Skip user deletion in per-empresa mode
            delete_users_except_admin = False
            
        else:
            # --- GLOBAL CLEANUP (Legacy behavior with safeguards) ---
            to_truncate = []
            to_drop = []
            with connections['analytics'].cursor() as c:
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datia_%'")
                to_truncate += [r[0] for r in c.fetchall()]
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                to_truncate += [r[0] for r in c.fetchall()]
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                to_drop = [r[0] for r in c.fetchall()]
            
            # Excluir tablas de configuración, checkpoints y datia_raw (obsoletas) del reseteo
            excluded_cfg = {
                "datia_globalconfig",
                "datia_widgetconfig",
                "datia_widgetstate",
                "datia_sync_checkpoints"
            }
            # Excluir también tablas operativas del módulo Banking
            banking_prefix = "datia_banking_"
            banking_skip = [t for t in to_truncate if isinstance(t, str) and t.startswith(banking_prefix)]
            excluded_cfg = excluded_cfg.union(set(banking_skip))
            
            skipped = [t for t in to_truncate if t in excluded_cfg]
            to_truncate = [t for t in to_truncate if t not in excluded_cfg]
            
            # ... (Reuse existing logic for Global cleanup) ...
            try:
                with connections['analytics'].cursor() as c:
                    # Añadir entradas SKIPPED para las tablas excluidas
                    for t in skipped:
                        try:
                            c.execute("""
                                SELECT c.reltuples::BIGINT
                                FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE n.nspname='public' AND c.relname=%s
                            """, [t])
                            approx = int(c.fetchone()[0] or 0)
                        except Exception:
                            approx = 0
                        cleanup_tables.append({
                            "table": t,
                            "action": "skip",
                            "before": approx,
                            "deleted": 0,
                            "after": approx,
                            "status": "SKIPPED"
                        })
                        try:
                            audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "SKIPPED (config)")
                        except Exception:
                            pass
                    for t in to_truncate:
                        try:
                            c.execute("""
                                SELECT c.reltuples::BIGINT
                                FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE n.nspname='public' AND c.relname=%s
                            """, [t])
                            approx = int(c.fetchone()[0] or 0)
                        except Exception:
                            approx = 0
                        cleanup_tables.append({
                            "table": t,
                            "action": "truncate",
                            "before": approx,
                            "deleted": approx,
                            "after": 0,
                            "status": "PENDING"
                        })
                    for t in to_drop:
                        try:
                            c.execute("""
                                SELECT c.reltuples::BIGINT
                                FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE n.nspname='public' AND c.relname=%s
                            """, [t])
                            approx = int(c.fetchone()[0] or 0)
                        except Exception:
                            approx = 0
                        cleanup_tables.append({
                            "table": t,
                            "action": "drop",
                            "before": approx,
                            "deleted": approx,
                            "after": 0,
                            "status": "PENDING"
                        })
            except Exception:
                pass
            
            try:
                cleanup_tables = sorted(cleanup_tables, key=lambda x: {'drop':0,'truncate':1,'skip':2}.get(str(x.get('action','')).lower(), 1))
            except Exception:
                pass
            
            ETL_JOBS[job_id]['cleanup'] = {"size_before": size_before, "size_after": None, "freed": None, "truncated": to_truncate, "dropped": to_drop, "tables": cleanup_tables}
            jobs = _read_jobs()
            jobs[job_id] = ETL_JOBS[job_id]
            _write_jobs(jobs)
            
            if dry_run:
                ETL_JOBS[job_id]['plan'] = {"truncate": to_truncate, "drop": to_drop}
                update("Plan generado", 5, 'pending')
                return
                
            with connections['analytics'].cursor() as c:
                conn = connections['analytics']
                def _terminate_metrics_blockers(table_name: str):
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    try:
                        with conn.cursor() as c2:
                            c2.execute(
                                """
                                SELECT a.pid,
                                       now() - a.query_start AS age,
                                       left(regexp_replace(a.query,'\\s+',' ','g'), 240) AS query
                                FROM pg_locks l
                                JOIN pg_class t ON t.oid = l.relation
                                JOIN pg_stat_activity a ON a.pid = l.pid
                                WHERE t.relname = %s
                                  AND l.granted
                                  AND a.pid <> pg_backend_pid()
                                ORDER BY a.query_start NULLS LAST
                                """,
                                [table_name],
                            )
                            holders = c2.fetchall()
                        for pid, age, q in holders:
                            ql = (q or "").lower()
                            if ql.startswith("insert into metrics_") or "metrics_totales_" in ql or ql.startswith("truncate table"):
                                try:
                                    with conn.cursor() as c3:
                                        c3.execute("SELECT pg_terminate_backend(%s)", [int(pid)])
                                except Exception:
                                    pass
                    except Exception:
                        pass
                try:
                    c.execute("SELECT set_config('lock_timeout','5s', false)")
                    c.execute("SELECT set_config('statement_timeout','900000', false)")
                except Exception:
                    pass
                # Progreso granular de limpieza
                active_total = len([x for x in cleanup_tables if str(x.get('action','')).lower() != 'skip'])
                done_count = 0
                
                # TRUNCATE por tabla con actualización inmediata del estado
                for t in to_truncate:
                    try:
                        update(f'Limpieza: truncando {t}', 2 + int(((done_count) / max(1, active_total)) * 28))
                        c.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                        # Marcar como OK la tabla correspondiente
                        for idx, item in enumerate(cleanup_tables):
                            if item.get("action") == "truncate" and item.get("table") == t:
                                cleanup_tables[idx]["status"] = "OK"
                                break
                        try:
                            cleanup_tables = sorted(cleanup_tables, key=lambda x: {'drop':0,'truncate':1,'skip':2}.get(str(x.get('action','')).lower(), 1))
                        except Exception:
                            pass
                        ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                        jobs = _read_jobs()
                        jobs[job_id] = ETL_JOBS[job_id]
                        _write_jobs(jobs)
                        try:
                            audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "TRUNCATE OK")
                        except Exception:
                            pass
                    except Exception as e_tr:
                        msg = str(e_tr).lower()
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        if "lock timeout" in msg or "canceling statement due to lock timeout" in msg:
                            try:
                                _terminate_metrics_blockers(t)
                                with conn.cursor() as c_retry:
                                    c_retry.execute(f'TRUNCATE TABLE "{t}" RESTART IDENTITY')
                                for idx, item in enumerate(cleanup_tables):
                                    if item.get("action") == "truncate" and item.get("table") == t:
                                        cleanup_tables[idx]["status"] = "OK"
                                        break
                                ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                                jobs = _read_jobs()
                                jobs[job_id] = ETL_JOBS[job_id]
                                _write_jobs(jobs)
                                try:
                                    audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "TRUNCATE OK (after kill)")
                                except Exception:
                                    pass
                                continue
                            except Exception:
                                try:
                                    conn.rollback()
                                except Exception:
                                    pass
                                if t.startswith("metrics_") or t.startswith("datiadb_"):
                                    try:
                                        with conn.cursor() as c_del:
                                            c_del.execute(f'DELETE FROM "{t}"')
                                        for idx, item in enumerate(cleanup_tables):
                                            if item.get("action") == "truncate" and item.get("table") == t:
                                                cleanup_tables[idx]["status"] = "OK"
                                                break
                                        ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                                        jobs = _read_jobs()
                                        jobs[job_id] = ETL_JOBS[job_id]
                                        _write_jobs(jobs)
                                        try:
                                            audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "DELETE OK (lock timeout)")
                                        except Exception:
                                            pass
                                        continue
                                    except Exception:
                                        try:
                                            conn.rollback()
                                        except Exception:
                                            pass
                        try:
                            if t.startswith("datia_financial_") or t == "datia_acumulados_stocks":
                                try:
                                    c.execute(f'DELETE FROM "{t}"')
                                    for idx, item in enumerate(cleanup_tables):
                                        if item.get("action") == "truncate" and item.get("table") == t:
                                            cleanup_tables[idx]["status"] = "OK"
                                            break
                                    ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                                    jobs = _read_jobs()
                                    jobs[job_id] = ETL_JOBS[job_id]
                                    _write_jobs(jobs)
                                    try:
                                        audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "DELETE OK")
                                    except Exception:
                                        pass
                                except Exception:
                                    for idx, item in enumerate(cleanup_tables):
                                        if item.get("action") == "truncate" and item.get("table") == t:
                                            cleanup_tables[idx]["status"] = "SKIPPED"
                                            break
                                    ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                                    jobs = _read_jobs()
                                    jobs[job_id] = ETL_JOBS[job_id]
                                    _write_jobs(jobs)
                                    try:
                                        audit(f"workflow:{job_id}", t, "STATUS", 0, "error", "TRUNCATE/DELETE SKIPPED")
                                    except Exception:
                                        pass
                            else:
                                for idx, item in enumerate(cleanup_tables):
                                    if item.get("action") == "truncate" and item.get("table") == t:
                                        cleanup_tables[idx]["status"] = "SKIPPED"
                                        break
                                ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                                jobs = _read_jobs()
                                jobs[job_id] = ETL_JOBS[job_id]
                                _write_jobs(jobs)
                                try:
                                    audit(f"workflow:{job_id}", t, "STATUS", 0, "error", "TRUNCATE SKIPPED")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    finally:
                        done_count += 1
                        update(f'Limpieza: {done_count}/{active_total}', 2 + int(((done_count) / max(1, active_total)) * 28))
                
                # DROP por tabla con actualización inmediata del estado
                for t in to_drop:
                    try:
                        update(f'Limpieza: eliminando {t}', 2 + int(((done_count) / max(1, active_total)) * 28))
                        c.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
                        for idx, item in enumerate(cleanup_tables):
                            if item.get("action") == "drop" and item.get("table") == t:
                                cleanup_tables[idx]["status"] = "OK"
                                break
                        ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                        jobs = _read_jobs()
                        jobs[job_id] = ETL_JOBS[job_id]
                        _write_jobs(jobs)
                        try:
                            audit(f"workflow:{job_id}", t, "STATUS", 0, "completed", "DROP OK")
                        except Exception:
                            pass
                    except Exception:
                        try:
                            for idx, item in enumerate(cleanup_tables):
                                if item.get("action") == "drop" and item.get("table") == t:
                                    cleanup_tables[idx]["status"] = "SKIPPED"
                                    break
                            ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
                            jobs = _read_jobs()
                            jobs[job_id] = ETL_JOBS[job_id]
                            _write_jobs(jobs)
                            try:
                                audit(f"workflow:{job_id}", t, "STATUS", 0, "error", "DROP SKIPPED")
                            except Exception:
                                pass
                        except Exception:
                            pass
                    finally:
                        done_count += 1
                        update(f'Limpieza: {done_count}/{active_total}', 2 + int(((done_count) / max(1, active_total)) * 28))
        try:
            for idx, item in enumerate(cleanup_tables):
                if item.get("action") == "drop":
                    cleanup_tables[idx]["status"] = "OK"
            try:
                cleanup_tables = sorted(cleanup_tables, key=lambda x: {'drop':0,'truncate':1,'skip':2}.get(str(x.get('action','')).lower(), 1))
            except Exception:
                pass
            ETL_JOBS[job_id]['cleanup']['tables'] = cleanup_tables
            jobs = _read_jobs()
            jobs[job_id] = ETL_JOBS[job_id]
            _write_jobs(jobs)
        except Exception:
            pass
        heavy = [
            "datia_financial_plan",
            "datia_financial_acumulados",
            "datia_financial_groups",
            "datia_financial_cartera",
            "datia_financial_presupuestos",
        ]
        with connections['analytics'].cursor() as c:
            for t in heavy:
                try:
                    c.execute(f'ANALYZE "{t}"')
                except Exception:
                    pass
        if delete_users_except_admin:
            try:
                User.objects.exclude(username='admin').delete()
            except Exception:
                pass
        size_after = _get_db_size('analytics')
        ETL_JOBS[job_id]['cleanup'] = {"size_before": size_before, "size_after": size_after, "freed": (size_before - size_after) if (isinstance(size_before,int) and isinstance(size_after,int)) else None, "truncated": to_truncate, "dropped": to_drop, "tables": cleanup_tables}
        # Asegurar que cualquier tabla aún marcada PENDING pero excluida por configuración quede en SKIPPED
        try:
            cl_fix = ETL_JOBS[job_id]['cleanup']['tables']
            changed = False
            for i, item in enumerate(cl_fix):
                tn = str(item.get('table') or '')
                if item.get('status') == 'PENDING' and (tn in excluded_cfg or tn.startswith(banking_prefix)):
                    cl_fix[i]['status'] = 'SKIPPED'
                    changed = True
            if changed:
                jobs = _read_jobs()
                jobs[job_id]['cleanup']['tables'] = cl_fix
                _write_jobs(jobs)
        except Exception:
            pass
        update("Limpieza completada", 30)
        audit(f"workflow:{job_id}", None, "STATUS", 0, "completed", "Limpieza completada")
        ETL_JOBS[job_id]['stage'] = 'sync'
        update("Validando conexión MSSQL", 32)
        if mssql_database:
            try:
                svc = ETLService(mssql_db=mssql_database)
                conn = svc.get_connection()
                conn.close()
            except Exception as e:
                ETL_JOBS[job_id]['rollback'] = True
                update(f"Conexión MSSQL inválida: {e}", 0, 'error')
                audit(f"workflow:{job_id}", None, "STATUS", 0, "error", f"Conexión MSSQL inválida: {e}")
                return
        try:
            svc_emp = ETLService(mssql_db=mssql_database)
            codes = None
            if empresas_filter:
                try:
                    codes = [int(x) for x in str(empresas_filter).split(',') if x.strip().isdigit()]
                except Exception:
                    codes = None
            if emp_val:
                codes = [int(emp_val)]
            svc_emp.sync_empresas(empresas_filter=codes, allow_db_switch=(emp_val is None))
        except Exception as e:
            ETL_JOBS[job_id]['rollback'] = True
            update(f"Error sincronizando empresas: {e}", 0, 'error')
            try:
                audit(f"workflow:{job_id}", "datia_empresa", "IMPORT", 0, "error", str(e))
            except Exception:
                pass
            return
        try:
            from django.conf import settings
            if getattr(settings, 'DATIA_DISABLE_MSSQL_SYNC', False):
                update("Importación de bancos omitida por DATIA_DISABLE_MSSQL_SYNC", 33)
            else:
                from datia.services.banking_import_service import BankingImportService
                from datia.services.etl_service import ETLService as _EmpSyncService
                from datia.models import Empresa
                empresas = []
                if emp_val:
                    empresas = [emp_val]
                else:
                    try:
                        empresas = list(Empresa.objects.values_list('codigo', flat=True))
                    except Exception as e_emp:
                        msg_e = str(e_emp) or ""
                        if "datia_empresa" in msg_e and ("does not exist" in msg_e or "no existe la relación" in msg_e):
                            try:
                                svc_emp = _EmpSyncService(mssql_db=mssql_database)
                                codes = None
                                if empresas_filter:
                                    try:
                                        codes = [int(x) for x in str(empresas_filter).split(',') if x.strip().isdigit()]
                                    except Exception:
                                        codes = None
                                svc_emp.sync_empresas(empresas_filter=codes)
                                empresas_qs = Empresa.objects.all()
                                if codes:
                                    empresas_qs = empresas_qs.filter(codigo__in=codes)
                                empresas = list(empresas_qs.values_list('codigo', flat=True))
                            except Exception as e_sync:
                                ETL_JOBS[job_id]['rollback'] = True
                                update(f"Error creando tabla de empresas: {e_sync}", 0, "error")
                                try:
                                    audit(f"workflow:{job_id}", "datia_empresa", "IMPORT", 0, "error", str(e_sync))
                                except Exception:
                                    pass
                                return
                        else:
                            raise
                if empresas:
                    svc_banking = BankingImportService(mssql_db=mssql_database)
                    total_emp = len(empresas)
                    for idx, emp in enumerate(empresas, start=1):
                        try:
                            rep = svc_banking.import_empresa(int(emp))
                            created = int(rep.get("banks_created", 0)) + int(rep.get("accounts_created", 0))
                            updated = int(rep.get("accounts_updated", 0))
                            rows_count = created + updated
                            pct = 33 + int((idx / max(1, total_emp)) * 5)
                            msg = f"Importando bancos empresa {emp}"
                            update(msg, pct)
                            try:
                                audit(f"workflow:{job_id}", "datia_banking_bank", "IMPORT", rows_count, "completed", f"Empresa {emp}")
                            except Exception:
                                pass
                        except Exception as e:
                            ETL_JOBS[job_id]['rollback'] = True
                            update(f"Error importando bancos empresa {emp}: {e}", 0, "error")
                            try:
                                audit(f"workflow:{job_id}", "datia_banking_bank", "IMPORT", 0, "error", f"Empresa {emp}: {e}")
                            except Exception:
                                pass
                            return
                    try:
                        from django.core.management import call_command
                        for emp in empresas:
                            try:
                                update(f"Sembrando semántica de ventas empresa {emp}", 38)
                                call_command("seed_sales_semantics", empresa=int(emp))
                                try:
                                    audit(f"workflow:{job_id}", "seed_sales_semantics", "STATUS", 0, "completed", f"Semántica ventas empresa {emp}")
                                except Exception:
                                    pass
                            except Exception as e_seed:
                                try:
                                    audit(f"workflow:{job_id}", "seed_sales_semantics", "STATUS", 0, "error", f"Empresa {emp}: {e_seed}")
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception as e:
            ETL_JOBS[job_id]['rollback'] = True
            update(f"Error en importación de bancos: {e}", 0, "error")
            try:
                audit(f"workflow:{job_id}", "datia_banking_bank", "IMPORT", 0, "error", str(e))
            except Exception:
                pass
            return
        try:
            with connections['analytics'].cursor() as c:
                c.execute("SELECT pg_try_advisory_lock(92345002)")
                locked_sync = bool(c.fetchone()[0])
            if not locked_sync:
                ETL_JOBS[job_id]['rollback'] = True
                update("Sincronización ocupada por otro proceso", 0, 'error')
                audit(f"workflow:{job_id}", None, "STATUS", 0, "error", "Sync lock no disponible")
                return
        except Exception:
            pass
        child_id = str(uuid.uuid4())
        ETL_JOBS[child_id] = {"id": child_id, "status": "pending", "progress": 0, "message": "Iniciando...", "created_at": time.time(), "source_db": mssql_database}
        jobs = _read_jobs()
        jobs[child_id] = ETL_JOBS[child_id]
        _write_jobs(jobs)
        try:
            ETL_JOBS[job_id]['child_id'] = child_id
            jobs = _read_jobs()
            jobs[job_id] = ETL_JOBS[job_id]
            _write_jobs(jobs)
        except Exception:
            pass
        th = threading.Thread(
            target=full_sync_worker,
            args=(
                child_id,
                None,
                None,
                "all",
                None,
                True,
                None,
                True,
                years_count if years_count is not None else 10,
                None,
                False,
                mssql_database,
                False,
                False,
                empresas_filter,
            ),
        )
        th.daemon = True
        th.start()
        last_log_pct = -5
        last_after_scan = 0.0
        after_rr = 0
        stall_watch_pct = None
        stall_watch_ts = time.time()
        STALL_LIMIT_SEC = 900
        while True:
            cj = ETL_JOBS.get(child_id) or _read_jobs().get(child_id)
            if not cj:
                update("Sincronización no encontrada", 0, 'error')
                audit(f"workflow:{job_id}", None, "STATUS", 0, "error", "Sincronización no encontrada")
                return
            cur_pct = int((cj.get('progress',0) or 0))
            cur_msg = cj.get('message','')
            update(f"Sincronización: {cur_msg}", 30 + int(cur_pct * 0.4))
            try:
                if cur_pct >= last_log_pct + 5:
                    last_log_pct = cur_pct
                    audit(f"workflow:{job_id}", None, "STATUS", 0, "running", f"{cur_msg} ({cur_pct}%)")
                # watchdog de estancamiento
                if stall_watch_pct is None or cur_pct != stall_watch_pct:
                    stall_watch_pct = cur_pct
                    stall_watch_ts = time.time()
                else:
                    if time.time() - stall_watch_ts > STALL_LIMIT_SEC:
                        ETL_JOBS[child_id]['status'] = 'error'
                        ETL_JOBS[child_id]['message'] = f"Sin progreso durante {int(STALL_LIMIT_SEC/60)} minutos"
                        jobs = _read_jobs()
                        jobs[child_id] = ETL_JOBS[child_id]
                        _write_jobs(jobs)
                        try:
                            audit(f"workflow:{job_id}", None, "STATUS", 0, "error", ETL_JOBS[child_id]['message'])
                        except Exception:
                            pass
                        break
            except Exception:
                pass
            try:
                now = time.time()
                if now - last_after_scan >= 5:
                    last_after_scan = now
                    # Determinar tabla actual por token TABLE: en el mensaje
                    import re
                    ct = None
                    try:
                        m = re.search(r'TABLE:\s*([a-zA-Z0-9_]+)', str(cur_msg))
                        if m:
                            ct = m.group(1)
                    except Exception:
                        ct = None
                    base_list = []
                    cl = ETL_JOBS.get(job_id, {}).get('cleanup', {}).get('tables', []) or []
                    all_names = []
                    if ct:
                        all_names.append(ct)
                    all_names.extend(base_list)
                    try:
                        db_names = [x.get('table') for x in cl if str(x.get('action','')).lower() != 'skip' and isinstance(x.get('table'), str)]
                        # Solo considerar tablas datiadb_* durante la fase DynamicSync
                        if stage == 'sync':
                            db_names = [n for n in db_names if n and (n.startswith('datiadb_') or n.startswith('datia_financial_'))]
                        else:
                            db_names = [n for n in db_names if n and n.startswith('datiadb_')]
                        db_names = list(dict.fromkeys(db_names))
                    except Exception:
                        db_names = []
                    if db_names:
                        # selección por lotes para evitar consultas pesadas
                        batch = []
                        for i in range(len(db_names)):
                            idx = (after_rr + i) % len(db_names)
                            batch.append(db_names[idx])
                            if len(batch) >= 4:
                                break
                        after_rr = (after_rr + 4) % max(1, len(db_names))
                        all_names.extend(batch)
                    tracked = list(dict.fromkeys(all_names))
                    with connections['analytics'].cursor() as c:
                        counts = {}
                        for t in tracked[:5]:
                            try:
                                # Estimación rápida para todas las tablas (n_live_tup con fallback a reltuples)
                                c.execute("""
                                    SELECT COALESCE(s.n_live_tup::bigint, c.reltuples::bigint)
                                    FROM pg_class c
                                    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                                    WHERE c.relname = %s
                                """, [t])
                                v = c.fetchone()
                                approx = int(v[0]) if v and v[0] is not None else None
                                counts[t] = approx
                            except Exception:
                                counts[t] = None
                    changed = False
                    for idx, item in enumerate(cl):
                        tn = item.get('table')
                        if tn in counts and counts[tn] is not None:
                            if item.get('after') != counts[tn]:
                                cl[idx]['after'] = counts[tn]
                                changed = True
                    if changed:
                        ETL_JOBS[job_id]['cleanup']['tables'] = cl
                        jobs = _read_jobs()
                        jobs[job_id] = ETL_JOBS[job_id]
                        _write_jobs(jobs)
            except Exception:
                pass
            if cj.get('status') in ['completed','error']:
                break
            time.sleep(2)
        if cj.get('status') != 'completed':
            try:
                with connections['analytics'].cursor() as c:
                    try:
                        c.execute("SELECT pg_advisory_unlock(92345002)")
                    except Exception:
                        pass
                    emp_val_fail = None
                    try:
                        emp_raw = ETL_JOBS.get(job_id, {}).get('empresa_id')
                        if emp_raw is not None:
                            emp_val_fail = int(str(emp_raw).strip())
                    except Exception:
                        emp_val_fail = None
                    for t in ["datia_financial_plan", "datia_financial_acumulados", "datia_financial_groups", "datia_financial_cartera", "datia_financial_presupuestos","datia_acumulados_stocks"]:
                        try:
                            if emp_val_fail is not None:
                                c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                                cols = [str(r[0]).lower() for r in c.fetchall()]
                                if 'empresa' in cols:
                                    c.execute(f'DELETE FROM "{t}" WHERE "empresa" = %s', [emp_val_fail])
                                else:
                                    pass
                            else:
                                pass
                        except Exception:
                            pass
                    try:
                        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'datiadb_%' AND table_name NOT ILIKE 'datiadb_ai%'")
                        rows = [r[0] for r in c.fetchall()]
                    except Exception:
                        rows = []
                    for tn in rows:
                        try:
                            if emp_val_fail is not None:
                                c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [tn])
                                cols = [str(r[0]).lower() for r in c.fetchall()]
                                emp_col = None
                                for cand in ['codigoempresa', 'empresa', 'empresacodigo', 'company', 'companyid']:
                                    if cand in cols:
                                        emp_col = cand
                                        break
                                if emp_col:
                                    c.execute(f'DELETE FROM "{tn}" WHERE "{emp_col}" = %s', [emp_val_fail])
                            else:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass
            ETL_JOBS[job_id]['rollback'] = True
            update("Fallo en sincronización", 0, 'error')
            audit(f"workflow:{job_id}", None, "STATUS", 0, "error", f"Fallo en sincronización: {cj.get('message','') if cj else ''}")
            return
        try:
            cl = ETL_JOBS.get(job_id, {}).get('cleanup', {}).get('tables', []) or []
            existing = {str(x.get('table')) for x in cl}
            added = False
            with connections['analytics'].cursor() as c:
                c.execute("""
                    SELECT c.relname, COALESCE(s.n_live_tup::bigint, c.reltuples::bigint) AS approx
                    FROM pg_class c
                    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname='public' AND c.relname ILIKE 'datiadb_%' AND c.relname NOT ILIKE 'datiadb_ai%'
                """)
                for name, approx in c.fetchall():
                    if name not in existing:
                        cl.append({
                            "table": name,
                            "action": "trained",
                            "before": -1,
                            "deleted": 0,
                            "after": int(approx or 0),
                            "status": "OK"
                        })
                        added = True
            if added:
                try:
                    cl = sorted(cl, key=lambda x: {'drop':0,'truncate':1,'skip':2,'trained':3}.get(str(x.get('action','')).lower(), 4))
                except Exception:
                    pass
                ETL_JOBS[job_id]['cleanup']['tables'] = cl
                jobs = _read_jobs()
                jobs[job_id] = ETL_JOBS[job_id]
                _write_jobs(jobs)
            summary_tables = []
            summary_metrics = []
            for item in cl:
                tn = str(item.get('table') or '')
                rows = item.get('after')
                if rows is None:
                    continue
                try:
                    rows_int = int(rows)
                except Exception:
                    continue
                if tn.startswith('metrics_'):
                    summary_metrics.append({"table": tn, "rows": rows_int})
                elif tn.startswith('datiadb_') or tn.startswith('datia_financial_'):
                    summary_tables.append({"table": tn, "rows": rows_int})
            ETL_JOBS[job_id]['summary'] = {
                "tables": summary_tables,
                "metrics": summary_metrics,
            }
            jobs = _read_jobs()
            jobs[job_id] = ETL_JOBS[job_id]
            _write_jobs(jobs)
        except Exception:
            pass
        try:
            with connections['analytics'].cursor() as c:
                try:
                    c.execute("SELECT pg_advisory_unlock(92345002)")
                except Exception:
                    pass
        except Exception:
            pass
        ETL_JOBS[job_id]['stage'] = 'metrics'
        update("Recalculando métricas", 82)
        doms = None
        if include_domains:
            try:
                doms = [x.strip() for x in str(include_domains).split(',') if x.strip() in ['ventas','compras']]
            except Exception:
                doms = None
        try:
            pairs_set = set()
            with connections['analytics'].cursor() as c:
                candidates = [
                    'datiadb_cabeceraalbarancliente',
                    'datiadb_cabecerapedidocliente',
                    'datiadb_cabeceraalbaranproveedor',
                ]
                for table in candidates:
                    try:
                        c.execute(
                            """
                            SELECT column_name
                            FROM information_schema.columns
                            WHERE table_schema='public' AND table_name=%s
                            """,
                            [table],
                        )
                        cols = {r[0].lower() for r in c.fetchall()}
                        def pick(cands):
                            for name in cands:
                                if name in cols:
                                    return name
                            return None
                        emp_col = pick(['empresa', 'codigoempresa', 'empresacodigo'])
                        year_col = pick(['ejercicio', 'ejercicioalbaran', 'ejerciciopedido', 'year'])
                        if not emp_col or not year_col:
                            continue
                        sql = f'SELECT "{emp_col}", "{year_col}" FROM "{table}" GROUP BY "{emp_col}", "{year_col}"'
                        c.execute(sql)
                        for emp, eje in c.fetchall():
                            if emp is not None and eje is not None:
                                pairs_set.add((int(emp), int(eje)))
                    except Exception:
                        continue
            pairs = sorted(list(pairs_set), key=lambda x: (x[0], x[1]))
        except Exception:
            pairs = []
        try:
            from datia.services.totals_service import TotalsService
            ts = TotalsService()
            total = len(pairs)
            done = 0
            for emp, year in pairs:
                done += 1
                update(f"Métricas {emp}/{year}", 82 + int((done / total) * 15) if total else 95)
                if not doms or 'ventas' in doms:
                    try:
                        ts.aggregate_from_datiadb_sales(emp, year)
                    except Exception:
                        pass
                if not doms or 'compras' in doms:
                    try:
                        ts.aggregate_from_datiadb_purchases(emp, year)
                    except Exception:
                        pass
        except Exception as e:
            try:
                with connections['analytics'].cursor() as c:
                    emp_val_metrics = None
                    try:
                        emp_raw = ETL_JOBS.get(job_id, {}).get('empresa_id')
                        if emp_raw is not None:
                            emp_val_metrics = int(str(emp_raw).strip())
                    except Exception:
                        emp_val_metrics = None
                    c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                    mt = [r[0] for r in c.fetchall()]
                    for t in mt:
                        try:
                            if emp_val_metrics is not None:
                                c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [t])
                                cols = [str(r[0]).lower() for r in c.fetchall()]
                                if 'empresa' in cols:
                                    c.execute(f'DELETE FROM "{t}" WHERE "empresa" = %s', [emp_val_metrics])
                            else:
                                pass
                        except Exception:
                            pass
            except Exception:
                pass
            ETL_JOBS[job_id]['rollback'] = True
            update(f"Fallo recalculando métricas: {e}", 0, 'error')
            audit(f"workflow:{job_id}", None, "STATUS", 0, "error", f"Fallo recalculando métricas: {e}")
            return
        summary_tables = []
        summary_metrics = []
        try:
            with connections['analytics'].cursor() as c:
                c.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema='public'
                      AND (
                        (table_name ILIKE 'datiadb_%%' AND table_name NOT ILIKE 'datiadb_ai%%')
                        OR table_name ILIKE 'datia_financial_%%'
                        OR table_name IN (
                          'datia_acumulados_stocks',
                          'datia_empresa',
                          'datia_cliente',
                          'datia_proveedores',
                          'datia_familias',
                          'datia_articulos'
                        )
                      )
                """)
                tbls = [r[0] for r in c.fetchall()]
                for t in sorted(tbls):
                    try:
                        c.execute(f'SELECT COUNT(*) FROM "{t}"')
                        cnt = int(c.fetchone()[0] or 0)
                        summary_tables.append({"table": t, "rows": cnt})
                    except Exception:
                        continue
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                mt = [r[0] for r in c.fetchall()]
                for t in sorted(mt):
                    try:
                        c.execute(f'SELECT COUNT(*) FROM "{t}"')
                        cnt = int(c.fetchone()[0] or 0)
                        summary_metrics.append({"table": t, "rows": cnt})
                    except Exception:
                        continue
        except Exception:
            pass
        try:
            ETL_JOBS[job_id]['summary'] = {"tables": summary_tables, "metrics": summary_metrics}
            jobs = _read_jobs()
            job_rec = jobs.get(job_id, {})
            job_rec['summary'] = ETL_JOBS[job_id]['summary']
            jobs[job_id] = job_rec
            _write_jobs(jobs)
        except Exception:
            pass
        try:
            verification = {"ok": True, "pairs": [], "problems": [], "generated_at": time.time()}
            with connections['analytics'].cursor() as c:
                c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE 'metrics_%'")
                metrics_tables = {r[0] for r in c.fetchall()}
                def _has_col(table_name: str, candidates):
                    try:
                        c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", [table_name])
                        cols = {str(r[0]).lower() for r in c.fetchall()}
                        for cand in candidates:
                            if str(cand).lower() in cols:
                                return True
                    except Exception:
                        return False
                    return False
                sales_art_enabled = _has_col('datiadb_lineasalbarancliente', ['codigoarticulo', 'articulo'])
                purchases_art_enabled = _has_col('datiadb_lineasalbaranproveedor', ['codigoarticulo', 'articulo'])
                for emp, year in pairs:
                    pair_item = {"empresa": int(emp), "ejercicio": int(year), "metrics": []}
                    cod_postal_nonempty = 0
                    try:
                        c.execute(
                            "SELECT COUNT(*) FROM datia_cliente WHERE empresa=%s AND cod_postal IS NOT NULL AND BTRIM(cod_postal) <> ''",
                            [int(emp)],
                        )
                        cod_postal_nonempty = int(c.fetchone()[0] or 0)
                    except Exception:
                        cod_postal_nonempty = 0
                    expected = []
                    if (not doms) or ('ventas' in doms):
                        expected.extend([
                            "metrics_totales_empresa_ejercicio",
                            "metrics_totales_empresa_ejercicio_mes",
                            "metrics_totales_empresa_ejercicio_cliente",
                            "metrics_totales_empresa_ejercicio_cliente_mes",
                        ])
                        if sales_art_enabled:
                            expected.append("metrics_totales_empresa_ejercicio_articulo")
                        if cod_postal_nonempty > 0:
                            expected.append("metrics_totales_empresa_ejercicio_cod_postal")
                    if (not doms) or ('compras' in doms):
                        expected.extend([
                            "metrics_totales_empresa_ejercicio_compra",
                            "metrics_totales_empresa_ejercicio_compra_mes",
                            "metrics_totales_empresa_ejercicio_proveedor",
                            "metrics_totales_empresa_ejercicio_proveedor_mes",
                        ])
                        if purchases_art_enabled:
                            expected.append("metrics_totales_empresa_ejercicio_articulo_compra")
                    for t in expected:
                        item = {"table": t, "rows": 0, "status": "OK"}
                        if t not in metrics_tables:
                            item["status"] = "MISSING"
                            verification["ok"] = False
                            verification["problems"].append({"empresa": int(emp), "ejercicio": int(year), "table": t, "status": "MISSING"})
                            pair_item["metrics"].append(item)
                            continue
                        if t == "metrics_totales_empresa_ejercicio_cod_postal" and cod_postal_nonempty <= 0:
                            item["status"] = "NA"
                            item["rows"] = 0
                            pair_item["metrics"].append(item)
                            continue
                        try:
                            c.execute(f'SELECT COUNT(*) FROM "{t}" WHERE empresa=%s AND ejercicio=%s', [int(emp), int(year)])
                            n = int(c.fetchone()[0] or 0)
                        except Exception:
                            n = 0
                        item["rows"] = n
                        if n <= 0:
                            item["status"] = "ZERO"
                            verification["ok"] = False
                            verification["problems"].append({"empresa": int(emp), "ejercicio": int(year), "table": t, "status": "ZERO"})
                        pair_item["metrics"].append(item)
                    verification["pairs"].append(pair_item)
            ETL_JOBS[job_id]['verification'] = verification
            jobs = _read_jobs()
            job_rec = jobs.get(job_id, {})
            job_rec['verification'] = ETL_JOBS[job_id]['verification']
            jobs[job_id] = job_rec
            _write_jobs(jobs)
        except Exception:
            pass
        update("Workflow completado", 100, 'completed')
        audit(f"workflow:{job_id}", None, "STATUS", 0, "completed", "Workflow completado")
        log_initial_load("info", "workflow_completed", {"job_id": job_id})
        ETL_JOBS[job_id]['status'] = 'completed'
        jobs = _read_jobs()
        jobs[job_id] = ETL_JOBS[job_id]
        _write_jobs(jobs)
    except Exception as e:
        ETL_JOBS[job_id]['status'] = 'error'
        ETL_JOBS[job_id]['message'] = str(e)
        ETL_JOBS[job_id]['progress'] = 0
        log_initial_load("error", "workflow_exception", {"job_id": job_id, "error": str(e)})
        try:
            audit(f"workflow:{job_id}", None, "STATUS", 0, "error", str(e))
        except Exception:
            pass
        jobs = _read_jobs()
        jobs[job_id] = ETL_JOBS[job_id]
        _write_jobs(jobs)

@router.post("/workflow/reset_sync_recalc")
def start_workflow(request, mssql_database: str = Query(None), years_count: int = Query(10), include_domains: str = Query(None), verify_samples_year: int = Query(None), delete_users_except_admin: bool = Query(True), dry_run: bool = Query(False), admin_password: str = Query(None), empresas: str = Query(None)):
    from django.http import JsonResponse
    from datia.models import Empresa
    try:
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return JsonResponse({"status": "error", "message": "Autenticación requerida"}, status=401)
        try:
            has_companies = Empresa.objects.exists()
        except Exception:
            has_companies = True
        username = (getattr(user, 'username', '') or '').strip().lower()
        if has_companies and username != 'admin':
            if not admin_password:
                return JsonResponse({"status": "error", "message": "Se requiere contraseña de administrador para Factory Reset."}, status=403)
            try:
                if not user.check_password(admin_password):
                    return JsonResponse({"status": "error", "message": "Contraseña de administrador no válida."}, status=403)
            except Exception:
                return JsonResponse({"status": "error", "message": "No se pudo validar la contraseña de administrador"}, status=403)
    except Exception:
        return JsonResponse({"status": "error", "message": "No se pudo verificar permisos"}, status=403)
    job_id = str(uuid.uuid4())
    ETL_JOBS[job_id] = {
        "id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Iniciando workflow...",
        "created_at": time.time(),
        "source_db": mssql_database,
        "kind": "workflow",
        "empresas_filter": empresas,
    }
    jobs = _read_jobs()
    jobs[job_id] = ETL_JOBS[job_id]
    _write_jobs(jobs)
    th = threading.Thread(target=workflow_worker, args=(job_id, mssql_database, years_count, include_domains, verify_samples_year, delete_users_except_admin, dry_run, None, empresas))
    th.daemon = True
    th.start()
    return JsonResponse({"status": "started", "job_id": job_id}, status=200)
