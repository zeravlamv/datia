import re
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

def log_debug(msg):
    return

from django.conf import settings
from django.db import connections, transaction, connection
from django.utils import timezone
import decimal
import pyodbc
import json
from datia.models import MetricsTotalesEmpresaEjercicio, Empresa
from datia.models.financial import DatiaAcumuladosConta, DatiaGrupos, DatiaCarteraEfectos

class ETLService:
    """
    Core ETL Engine for Datia.
    Handles dynamic MSSQL table detection and normalization.
    Strictly follows variants from DATIA_prompt.md.
    """
    

    # "Tipado fuerte y saneado" implies we treat these map lists as priority queues
    COLUMN_MAP_CABECERA = {
        'empresa': ['CodigoEmpresa', 'Empresa', 'EmpresaCodigo'],
        'ejercicio': ['EjercicioAlbaran', 'Ejercicio', 'Year'],
        'serie': ['SerieAlbaran', 'Serie'],
        'numero': ['NumeroAlbaran', 'Numero'],
        'fecha': ['FechaAlbaran', 'Fecha'],
        'cliente': ['CodigoCliente', 'ClienteCodigo', 'Cliente'],
        'neto': ['ImporteNeto', 'TotalNeto', 'BaseImponible', 'ImporteBruto'],
        'con_iva': ['ImporteFactura', 'TotalConIva', 'TotalFactura'],
        'coste': ['CosteTotal', 'ImporteCoste', 'Coste'], 
        # Optional fields from prompt
        'nombre_cliente': ['Nombre', 'RazonSocial', 'NombreCliente', 'Razon'],
        'base_iva': ['BaseIVA', 'CuotaIVA'],
        'facturado': ['Facturado', 'EstadoFactura'], 
        'cod_postal': ['CodPostal', 'CodigoPostal', 'CP', 'CodPostalEnvio', 'CPostal'],
    }
    
    COLUMN_MAP_LINEAS = {
        'empresa': ['CodigoEmpresa', 'Empresa', 'EmpresaCodigo'],
        'ejercicio': ['EjercicioAlbaran', 'Ejercicio', 'Year'],
        'serie': ['SerieAlbaran', 'Serie', 'SerieAlbaran'],
        'numero': ['NumeroAlbaran', 'Numero', 'NumeroAlbaran'],
        'fecha': ['FechaLinea', 'Fecha'], # Prompt specific
        'cliente': ['CodigoCliente', 'ClienteCodigo', 'Cliente'],
        'articulo': ['CodigoArticulo', 'ArticuloCodigo', 'Articulo'],
        'descripcion': ['DescripcionArticulo', 'Descripcion'],
        'cantidad': ['Cantidad', 'Unidades'],
        'neto': ['ImporteBruto', 'ImporteNeto', 'TotalLinea', 'Precio'], # User: ImporteBruto is (Sin IVA)
        'con_iva': ['ImporteFactura', 'TotalConIva', 'TotalLinea'], # User: ImporteFactura is (Con IVA)
        'coste': ['ImporteCoste', 'Coste', 'CosteTotal'], 
        # Optional specifics
        'precio_unitario': ['PrecioUnitario'],
        'coste_unitario': ['CosteUnitario'],
        'descuento_pct': ['DescuentoPct'],
    }

    # [NEW] Purchase Mappings
    COLUMN_MAP_CABECERA_COMPRA = {
        'empresa': ['CodigoEmpresa', 'Empresa', 'EmpresaCodigo'],
        'ejercicio': ['EjercicioAlbaran', 'EjercicioPedido', 'Ejercicio', 'Year'],
        'serie': ['SerieAlbaran', 'SeriePedido', 'Serie'],
        'numero': ['NumeroAlbaran', 'NumeroPedido', 'Numero'],
        'fecha': ['FechaAlbaran', 'FechaPedido', 'Fecha'], # Priorizar FechaAlbaran
        'proveedor': ['CodigoProveedor', 'ProveedorCodigo', 'Proveedor'],
        'nombre_proveedor': ['Nombre', 'RazonSocial', 'NombreProveedor', 'Razon'],
        'neto': ['ImporteLiquido', 'TotalNeto', 'BaseImponible', 'ImporteBruto'], # Purchases often use ImporteLiquido
        'con_iva': ['ImporteTotal', 'TotalConIva', 'TotalFactura'],
        'coste': ['ImporteBruto', 'CosteTotal'], # Fallback
        'cod_postal': ['CodPostal', 'CodigoPostal', 'CP'],
    }

    COLUMN_MAP_LINEAS_COMPRA = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'ejercicio': ['EjercicioAlbaran', 'Ejercicio'],
        'serie': ['SerieAlbaran', 'Serie'],
        'numero': ['NumeroAlbaran', 'Numero'],
        'fecha': ['FechaLinea', 'Fecha'],
        'proveedor': ['CodigoProveedor', 'Proveedor'],
        'articulo': ['CodigoArticulo', 'Articulo'],
        'descripcion': ['DescripcionArticulo', 'Descripcion'],
        'cantidad': ['Cantidad', 'Unidades'],
        'neto': ['ImporteBruto', 'ImporteNeto', 'TotalLinea', 'Precio'],
        'con_iva': ['ImporteTotal', 'TotalConIva', 'TotalLinea'],
        'coste': ['ImporteCoste', 'Coste'], 
    }

    COLUMN_MAP_CLIENTES = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'cliente': ['CodigoCliente', 'Cliente'],
        'nombre': ['RazonSocial', 'Nombre', 'NombreCliente'],
        'cod_postal': ['CodPostal', 'CodigoPostal', 'CP', 'CPostal']
    }

    COLUMN_MAP_PROVEEDORES = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'proveedor': ['CodigoProveedor', 'Proveedor'],
        'nombre': ['RazonSocial', 'Nombre', 'NombreProveedor'],
        'cod_postal': ['CodPostal', 'CodigoPostal', 'CP', 'CPostal']
    }

    COLUMN_MAP_ARTICULOS = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'articulo': ['CodigoArticulo', 'Articulo'],
        'descripcion': ['Descripcion', 'DescripcionArticulo'],
        'familia': ['Familia', 'CodigoFamilia'],
        'marca': ['Marca', 'CodigoMarca'],
        'precio_compra': ['PrecioCompra', 'PCosto', 'CosteUnitario', 'PrecioCoste']
    }

    COLUMN_MAP_PLAN_CUENTAS = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'codigo': ['CodigoCuenta', 'IdCuenta', 'CuentaContable', 'Codigo', 'CodCuenta'],
        'descripcion': ['DescripcionCuenta', 'NombreCuenta', 'Descripcion', 'Nombre', 'NomCuenta', 'DescCuenta', 'Cuenta'],
        'nivel': ['Nivel', 'NivelCuenta'],
        'grupo': ['Grupo', 'CodigoGrupo']
    }

    COLUMN_MAP_ACUMULADOS = {
        'empresa': ['CodigoEmpresa', 'Empresa', 'EmpresaCodigo'],
        'ejercicio': ['Ejercicio', 'Year', 'Anyo'],
        'cuenta': ['CodigoCuenta', 'Cuenta', 'CuentaContable', 'Codigo'],
        'periodo': ['NumeroPeriodo', 'Periodo', 'Mes'],
        'debe': ['DebeAcum', 'Debe', 'ImporteDebe'],
        'haber': ['HaberAcum', 'Haber', 'ImporteHaber'],
        'saldo': ['Saldo', 'ImporteSaldo']
    }
    
    COLUMN_MAP_ALMACENES = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'codigo': ['CodigoAlmacen', 'Almacen', 'Codigo'],
        'nombre': ['Almacen', 'Nombre', 'Descripcion']
    }

    COLUMN_MAP_GRUPOS = {
        'empresa': ['CodigoEmpresa', 'Empresa'],
        'codigo': ['CodigoGrupo', 'Grupo', 'Codigo'],
        'descripcion': ['DescripcionGrupo', 'Descripcion', 'NombreGrupo']
    }
    COLUMN_MAP_STOCKS = {
        'empresa': ['CodigoEmpresa', 'Empresa', 'EmpresaCodigo'],
        'ejercicio': ['Ejercicio', 'EjercicioStock', 'Year'],
        'periodo': ['Periodo', 'Mes'],
        'articulo': ['Articulo', 'CodigoArticulo', 'Codigo'],
        'almacen': ['Almacen', 'CodigoAlmacen'],
        'ubicacion': ['Ubicacion', 'UbicacionAlmacen', 'Ubic'],
        'tipologia': ['Tipologia', 'Tipo', 'Familia', 'Categoria'],
        'importe_saldo': ['ImporteSaldo', 'SaldoImporte', 'Importe', 'SaldoValor', 'ValorSaldo'],
        'unidad_saldo': ['UnidadSaldo', 'SaldoUnidades', 'CantidadSaldo', 'UnidadesSaldo', 'Unidades'],
        'precio_medio': ['PrecioMedio', 'CosteMedio', 'PrecioPonderado'],
        'precio_ultima': ['PrecioUltimaEntrada', 'UltimoPrecio', 'PrecioUltimo'],
        'precio_compra': ['PrecioCompra', 'PCosto', 'CosteUnitario', 'PrecioCoste']
    }
    
    def __init__(self, mssql_db=None):
        self.copy_chunk_rows = 10000
        self.progress_emit_rows = 5000
        self.mssql_db_override = mssql_db
        try:
            p = os.path.join(settings.BASE_DIR, 'datia', 'config', 'system_perf.json')
            with open(p, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            self.copy_chunk_rows = int(cfg.get('etl_copy_chunk_rows', self.copy_chunk_rows))
            self.progress_emit_rows = int(cfg.get('etl_progress_emit_rows', self.progress_emit_rows))
        except:
            pass
        self.static_mapping = {}
        try:
            mp = os.path.join(settings.BASE_DIR, 'datia', 'config', 'mssql_mapping.json')
            if os.path.exists(mp):
                with open(mp, 'r', encoding='utf-8') as mf:
                    raw = json.load(mf)
                by_table = {}
                mm = raw.get('mappings', {})
                if isinstance(mm, dict):
                    for _, entry in mm.items():
                        if isinstance(entry, dict):
                            st = entry.get('source_table')
                            fields = entry.get('fields') or {}
                            if st and isinstance(fields, dict) and fields:
                                by_table[st] = fields
                self.static_mapping = by_table
        except:
            self.static_mapping = {}

    def get_connection(self):
        from datia.services.runtime_config import mssql_connection_string, mssql_params
        params = mssql_params()
        db_name = self.mssql_db_override or params['name']
        conn_str = mssql_connection_string(db_name)
        try:
            pyodbc.pooling = False
        except Exception:
            pass
        try:
            conn = pyodbc.connect(conn_str, timeout=60)
        except Exception as e:
            accessible = []
            try:
                master_str = mssql_connection_string('master')
                c2 = pyodbc.connect(master_str, timeout=10)
                cur2 = c2.cursor()
                try:
                    cur2.execute("SELECT TOP 25 [name] FROM sys.databases WHERE HAS_DBACCESS([name])=1 ORDER BY [name]")
                    accessible = [str(r[0]) for r in cur2.fetchall()]
                except Exception:
                    accessible = []
                try:
                    c2.close()
                except Exception:
                    pass
            except Exception:
                accessible = []
            msg = f"Conexión MSSQL fallida abriendo la base de datos '{db_name}'."
            if accessible:
                msg += f" Bases accesibles con este login: {', '.join(accessible[:25])}."
            raise RuntimeError(msg) from e
        try:
            conn.timeout = 60
            cur = conn.cursor()
            try:
                cur.execute("SET LOCK_TIMEOUT 5000")
            except Exception:
                pass
            try:
                cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
            except Exception:
                pass
            try:
                cur.timeout = 60
            except Exception:
                pass
        except Exception:
            pass
        return conn

    def _empresa_candidates(self, val):
        s = str(val).strip()
        arr = [s]
        if s.isdigit():
            arr.append(s.zfill(2))
            arr.append(s.zfill(3))
            try:
                arr.append(int(s))
            except:
                pass
        else:
            try:
                arr.append(int(s))
            except:
                pass
        uniq = []
        for x in arr:
            if x not in uniq:
                uniq.append(x)
        return uniq
    def table_exists(self, cursor, name: str) -> bool:
        cursor.execute("SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE' AND TABLE_NAME = ?", (name,))
        return cursor.fetchone() is not None

    def get_table_candidates(self, cursor, kind: str) -> List[str]:
        # Modo exclusivo: si existe mapeo exacto para este kind, devolver solo esa tabla (si existe)
        kind_to_key = {
            'cabecera': 'ventas_cabecera',
            'lineas': 'ventas_lineas',
            'cabecera_compra': 'compras_cabecera',
            'lineas_compra': 'compras_lineas',
            'articulos': 'articulos',
            'clientes': 'clientes',
            'proveedores': 'proveedores',
            'familias': 'familias',
            'plan_cuentas': 'plan_cuentas',
            'acumulados': 'acumulados',
            'grupos': 'grupos',
            'stocks': 'stocks',
            'almacenes': 'almacenes'
        }
        if kind in kind_to_key:
            exact = self.get_exact_table(cursor, kind_to_key[kind])
            return [exact] if exact else []
        return []

    def get_column_mapping(self, cursor, table_name: str, mapping_def: Dict) -> Dict[str, str]:
        try:
            if not self.static_mapping or table_name not in self.static_mapping:
                return {}
            raw_map = self.static_mapping.get(table_name, {}) or {}
            mapping = dict(raw_map)
            if table_name == 'PlanCuentas':
                if 'codigo' not in mapping and 'codigo_cuenta' in mapping:
                    mapping['codigo'] = mapping['codigo_cuenta']
                if 'descripcion' not in mapping:
                    mapping['descripcion'] = 'Cuenta'
            elif table_name == 'AcumuladosConta':
                if 'cuenta' not in mapping and 'codigo_cuenta' in mapping:
                    mapping['cuenta'] = mapping['codigo_cuenta']
                if 'periodo' not in mapping and 'numero_periodo' in mapping:
                    mapping['periodo'] = mapping['numero_periodo']
            elif table_name == 'Grupos':
                if 'codigo' not in mapping and 'codigo_grupo' in mapping:
                    mapping['codigo'] = mapping['codigo_grupo']
                if 'descripcion' not in mapping and 'descripcion_grupo' in mapping:
                    mapping['descripcion'] = mapping['descripcion_grupo']
            if not mapping:
                return {}
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
                    (table_name,)
                )
                cols = {str(r[0]) for r in cursor.fetchall() if r and r[0]}
            except Exception:
                return mapping
            filtered = {k: v for k, v in mapping.items() if v in cols}
            return filtered
        except Exception:
            return {}

    def pick_best_table(self, cursor, candidates: List[str], mapping_def: Dict, required_keys: List[str]) -> Tuple[Optional[str], Dict]:
        best_table = None
        best_map = {}
        best_score = -1
        
        for table in candidates:
            mapping = self.get_column_mapping(cursor, table, mapping_def)
            score = sum(1 for k in required_keys if k in mapping)
            
            if score > best_score:
                best_score = score
                best_table = table
                best_map = mapping
                
        return best_table, best_map

    EXACT_MSSQL_TABLES = {
        'ventas_cabecera': 'CabeceraAlbaranCliente',
        'ventas_lineas': 'LineasAlbaranCliente',
        'compras_cabecera': 'CabeceraAlbaranProveedor',
        'compras_lineas': 'LineasAlbaranProveedor',
        'articulos': 'Articulos',
        'clientes': 'Clientes',
        'proveedores': 'Proveedores',
        'familias': 'Familias',
        'plan_cuentas': 'PlanCuentas',
        'acumulados': 'AcumuladosConta',
        'grupos': 'Grupos',
        'stocks': 'AcumuladoStock',
        'almacenes': 'Almacenes'
    }

    def get_exact_table(self, cursor, key: str) -> Optional[str]:
        name = self.EXACT_MSSQL_TABLES.get(key)
        if not name:
            return None
        return name if self.table_exists(cursor, name) else None

    def _list_tables_columns(self, cursor) -> Dict[str, set]:
        tables: Dict[str, set] = {}
        cursor.execute("SELECT TABLE_NAME, COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS")
        for t, c in cursor.fetchall():
            if not t:
                continue
            ts = str(t)
            cs = str(c) if c else ''
            if ts not in tables:
                tables[ts] = set()
            if cs:
                tables[ts].add(cs)
        return tables

    def pick_table_by_signature(self, cursor, mapping_def: Dict, required_keys: List[str]) -> Tuple[Optional[str], Dict]:
        tables_cols = self._list_tables_columns(cursor)
        best_table = None
        best_map: Dict[str, str] = {}
        best_score = -1
        req_len = len(required_keys)
        mapping_lower = {k: [s.lower() for s in v] for k, v in mapping_def.items()}
        for table_name, cols in tables_cols.items():
            cols_lower = {c.lower() for c in cols}
            tmp_map: Dict[str, str] = {}
            matched_req = 0
            for k in required_keys:
                found = None
                for cand in mapping_lower.get(k, []):
                    if cand in cols_lower:
                        for original in cols:
                            if original.lower() == cand:
                                found = original
                                break
                        break
                if found:
                    tmp_map[k] = found
                    matched_req += 1
                else:
                    matched_req = -999
                    break
            if matched_req != req_len:
                continue
            opt_score = 0
            for k, cand_list in mapping_lower.items():
                if k in tmp_map:
                    continue
                for cand in cand_list:
                    if cand in cols_lower:
                        for original in cols:
                            if original.lower() == cand:
                                tmp_map[k] = original
                                break
                        opt_score += 1
                        break
            total_score = matched_req * 100 + opt_score
            if total_score > best_score:
                best_score = total_score
                best_table = table_name
                best_map = tmp_map
        return best_table, best_map

    def _copy_csv(self, psy_cursor, sql, buf):
        import io, csv, re
        data = buf.getvalue()
        try:
            if hasattr(psy_cursor, "copy"):
                with psy_cursor.copy(sql) as copy:
                    copy.write(data)
                return
            if hasattr(psy_cursor, "copy_expert"):
                sio = io.StringIO(data)
                psy_cursor.copy_expert(sql, sio)
                return
        except Exception as e:
            try:
                log_debug(f"COPY fallback triggered: {e}")
            except:
                pass
        # Fallback: parse COPY and perform bulk INSERT
        try:
            m = re.search(r'COPY\s+"?([^\s(]+)"?\s*\(([^)]*)\)\s+FROM', sql, re.IGNORECASE)
            if not m:
                raise ValueError("Unable to parse COPY statement for fallback")
            table = m.group(1)
            cols_raw = m.group(2)
            cols = [c.strip().strip('"') for c in cols_raw.split(',') if c.strip()]
            cols_quoted = ", ".join(['"' + c + '"' for c in cols])
            reader = csv.reader(io.StringIO(data))
            rows = [tuple(r) for r in reader]
            if not rows:
                return
            base_sql = f'INSERT INTO "{table}" ({cols_quoted}) VALUES %s'
            template = "(" + ",".join(["%s"] * len(cols)) + ")"
            # Use existing bulk helper
            self._execute_values_bulk(psy_cursor, base_sql, rows, template, page_size=5000)
        except Exception as e2:
            raise e2

    def _ensure_datiadb_perf(self, table_name: str):
        import re
        from django.db import connections
        try:
            conn = connections['analytics']
        except Exception:
            return
        try:
            with conn.cursor() as c:
                c.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",
                    [table_name],
                )
                raw_cols = [r[0] for r in c.fetchall()]
            cols = {str(x).lower(): str(x) for x in raw_cols}
        except Exception:
            cols = {}

        def pick(cands):
            for cand in cands:
                k = str(cand).lower()
                if k in cols:
                    return cols[k]
            return None

        emp_col = pick(['codigoempresa', 'empresa', 'empresacodigo'])
        year_col = pick(['ejercicioalbaran', 'ejercicio', 'ejerciciopedido', 'year'])
        date_col = pick(['fechaalbaran', 'fechapedido', 'fecha', 'fecharegistro'])
        doc_col = pick(['numeroalbaran', 'numeropedido', 'numero', 'numalbaran'])
        partner_col = pick(['codigocliente', 'cliente', 'codigoproveedor', 'proveedor'])
        art_col = pick(['codigoarticulo', 'articulo'])

        if not emp_col or not year_col:
            try:
                with conn.cursor() as c:
                    c.execute(f'ANALYZE "{table_name}"')
            except Exception:
                pass
            return

        base = re.sub(r'[^a-z0-9_]+', '_', str(table_name).lower())
        specs = []
        tl = str(table_name).lower()
        if 'cabecera' in tl:
            if date_col:
                specs.append(('eyd', [emp_col, year_col, date_col]))
            if partner_col:
                specs.append(('eyp', [emp_col, year_col, partner_col]))
        else:
            if doc_col:
                specs.append(('eyn', [emp_col, year_col, doc_col]))
            if art_col:
                specs.append(('eya', [emp_col, year_col, art_col]))

        try:
            with conn.cursor() as c:
                for suffix, cols_list in specs:
                    idx_name = f"idx_{base}_{suffix}"
                    if len(idx_name) > 60:
                        idx_name = idx_name[:60]
                    cols_sql = ", ".join([f'\"{x}\"' for x in cols_list])
                    c.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON \"{table_name}\" ({cols_sql})')
                c.execute(f'ANALYZE \"{table_name}\"')
        except Exception:
            try:
                with conn.cursor() as c:
                    c.execute(f'ANALYZE \"{table_name}\"')
            except Exception:
                pass

    def _execute_values_bulk(self, cursor, base_sql: str, rows: List[Tuple], template: str, page_size: int):
        idx = 0
        total = len(rows)
        while idx < total:
            chunk = rows[idx:idx + page_size]
            if not chunk:
                break
            placeholders = ",".join([template] * len(chunk))
            sql = base_sql.replace("VALUES %s", f"VALUES {placeholders}")
            params = []
            for item in chunk:
                params.extend(list(item))
            cursor.execute(sql, params)
            idx += len(chunk)

    def sync_mssql_sales_generator(self, empresa: int, ejercicio: int, fast_bulk: bool = False):
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        yield send_progress("Info", 10, "Ventas se calculan exclusivamente desde datiadb_*. ETL estándar no agrega métricas directas.")
        yield send_progress("Done", 100, "Sincronización Ventas estándar finalizada (sin tocar metrics_).")

    def ensure_checkpoints_table(self):
        cursor_local = connections['analytics'].cursor()
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_sync_checkpoints (
                empresa TEXT NOT NULL,
                ejercicio INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                last_fecha TIMESTAMP NULL,
                last_serie TEXT NULL,
                last_numero TEXT NULL,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (empresa, ejercicio, tipo)
            )
        """)

    def ensure_financial_core_tables(self):
        cursor_local = connections['analytics'].cursor()
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_financial_plan (
                id BIGSERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                ejercicio INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                codigo VARCHAR(20) NOT NULL,
                descripcion VARCHAR(255) NOT NULL,
                nivel INTEGER NOT NULL DEFAULT 0,
                es_ultimo_nivel BOOLEAN NOT NULL DEFAULT FALSE,
                grupo VARCHAR(10),
                subgrupo VARCHAR(10),
                tipo_balance VARCHAR(20)
            )
        """)
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_financial_acumulados (
                id BIGSERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                ejercicio INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                cuenta VARCHAR(20) NOT NULL,
                periodo INTEGER NOT NULL,
                debe NUMERIC(18,4) NOT NULL DEFAULT 0,
                haber NUMERIC(18,4) NOT NULL DEFAULT 0,
                saldo NUMERIC(18,4) NOT NULL DEFAULT 0,
                debe_presupuesto NUMERIC(18,4) NOT NULL DEFAULT 0,
                haber_presupuesto NUMERIC(18,4) NOT NULL DEFAULT 0
            )
        """)
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_financial_groups (
                id BIGSERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                ejercicio INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                codigo VARCHAR(20) NOT NULL,
                descripcion VARCHAR(255) NOT NULL
            )
        """)
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_financial_cartera (
                id BIGSERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                ejercicio INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                codigo_titular VARCHAR(50),
                fecha_vencimiento DATE,
                fecha_emision DATE,
                importe NUMERIC(19,4) NOT NULL DEFAULT 0,
                importe_cobrado NUMERIC(19,4) NOT NULL DEFAULT 0,
                estado VARCHAR(50),
                tipo_efecto VARCHAR(1) NOT NULL DEFAULT 'C'
            )
        """)

    def ensure_stocks_table(self):
        cursor_local = connections['analytics'].cursor()
        cursor_local.execute("""
            CREATE TABLE IF NOT EXISTS datia_acumulados_stocks (
                id BIGSERIAL PRIMARY KEY,
                empresa INTEGER NOT NULL,
                ejercicio INTEGER NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                periodo INTEGER NOT NULL,
                articulo VARCHAR(64) NOT NULL,
                almacen VARCHAR(64),
                almacen_name VARCHAR(128),
                ubicacion VARCHAR(64),
                tipologia VARCHAR(64),
                importesaldo NUMERIC(18,2) NOT NULL DEFAULT 0,
                unidadsaldo NUMERIC(18,4) NOT NULL DEFAULT 0,
                preciomedio NUMERIC(18,4) NOT NULL DEFAULT 0,
                precioultimaentrada NUMERIC(18,4) NOT NULL DEFAULT 0,
                preciocompra NUMERIC(18,4) NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

    def ensure_master_tables(self):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        with connections[alias].cursor() as cur:
            cur.execute("""
                ALTER TABLE datia_empresa
                ADD COLUMN IF NOT EXISTS empresa INTEGER,
                ADD COLUMN IF NOT EXISTS cif VARCHAR(32),
                ADD COLUMN IF NOT EXISTS fecha_creacion TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS activa BOOLEAN NOT NULL DEFAULT TRUE
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_cliente (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    cliente VARCHAR(64) NOT NULL,
                    nombre VARCHAR(255) NOT NULL,
                    nombre_fiscal VARCHAR(255),
                    cif_nif VARCHAR(32),
                    fecha_alta TIMESTAMPTZ,
                    activo BOOLEAN NOT NULL DEFAULT TRUE,
                    cod_postal VARCHAR(16),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_proveedores (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    proveedor VARCHAR(64) NOT NULL,
                    nombre VARCHAR(255) NOT NULL,
                    nombre_fiscal VARCHAR(255),
                    cif_nif VARCHAR(32),
                    fecha_alta TIMESTAMPTZ,
                    activo BOOLEAN NOT NULL DEFAULT TRUE,
                    cod_postal VARCHAR(16),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_familias (
                    id BIGSERIAL PRIMARY KEY,
                    codigo_familia VARCHAR(64) NOT NULL,
                    descripcion VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_articulos (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    articulo VARCHAR(64) NOT NULL,
                    descripcion VARCHAR(255),
                    familia VARCHAR(64),
                    unidad_medida VARCHAR(16),
                    activo BOOLEAN NOT NULL DEFAULT TRUE,
                    fecha_alta TIMESTAMPTZ,
                    precio_compra NUMERIC(18,4),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_almacenes (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    codigo_almacen VARCHAR(64) NOT NULL,
                    descripcion VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS datia_comisionistas (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    codigo_comisionista VARCHAR(64) NOT NULL,
                    nombre VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)

    def ensure_ai_tables(self):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        with connections[alias].cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics_feedback (
                    id BIGSERIAL PRIMARY KEY,
                    query TEXT NOT NULL,
                    rejected_key VARCHAR(128),
                    is_positive BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS metrics_feedback_query_idx
                ON metrics_feedback (query)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics_saved_queries (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    ejercicio INTEGER NOT NULL,
                    query TEXT NOT NULL,
                    last_answer JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS metrics_saved_queries_emp_ej_query_uq
                ON metrics_saved_queries (empresa, ejercicio, query)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS metrics_saved_queries_emp_ej_idx
                ON metrics_saved_queries (empresa, ejercicio)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics_llm_consultas (
                    id BIGSERIAL PRIMARY KEY,
                    empresa INTEGER NOT NULL,
                    ejercicio INTEGER NOT NULL,
                    pregunta TEXT NOT NULL,
                    respuesta TEXT NOT NULL,
                    sql_generado TEXT,
                    creado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS metrics_llm_consultas_emp_ej_idx
                ON metrics_llm_consultas (empresa, ejercicio)
            """)

    def sync_mssql_masters(self):
        import io
        import csv
        from django.utils import timezone
        from django.db import transaction
        conn = self.get_connection()
        cursor = conn.cursor()
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        cursor_local = connections[alias].cursor()

        def _sync_table(source_table: str, target_table: str, int_empresa: bool = True):
            mapping = self.static_mapping.get(source_table, {})
            if not mapping:
                return
            try:
                cursor.execute(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?",
                    (source_table,)
                )
                src_lookup = {
                    str(r[0]).upper(): str(r[0]) for r in cursor.fetchall() if r and r[0]
                }
            except Exception:
                src_lookup = {}
            filtered_mapping = {}
            for dest, src in mapping.items():
                key = str(src).upper()
                real = src_lookup.get(key)
                if real:
                    filtered_mapping[dest] = real
            mapping = filtered_mapping
            if not mapping:
                return
            cursor_local.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                [target_table]
            )
            target_cols = {str(r[0]) for r in cursor_local.fetchall() if r and r[0]}
            cols = [c for c in mapping.keys() if c in target_cols]
            if not cols:
                return
            select_cols = ", ".join(f"{mapping[c]} AS {c}" for c in cols)
            cursor.execute(f"SELECT {select_cols} FROM {source_table}")
            desc = cursor.description or []
            idx_map = {str(col[0]): i for i, col in enumerate(desc) if col and col[0] is not None}
            cursor_local.execute(f'DELETE FROM {target_table}')
            chunk = self.copy_chunk_rows
            with transaction.atomic(using=alias):
                psy = connections[alias].connection.cursor()
                psy.execute("SET LOCAL synchronous_commit = OFF")
                while True:
                    rows = cursor.fetchmany(chunk)
                    if not rows:
                        break
                    buf = io.StringIO()
                    w = csv.writer(buf)
                    for r in rows:
                        vals = {}
                        for c in cols:
                            idx = idx_map.get(c)
                            v = r[idx] if idx is not None and idx < len(r) else None
                            if c == 'empresa' and v is not None and int_empresa:
                                s = str(v).strip()
                                if s.isdigit():
                                    v = int(s)
                                else:
                                    try:
                                        v = int(s)
                                    except Exception:
                                        v = None
                            vals[c] = v
                        # Skip rows without identificador de tercero para evitar violar NOT NULL
                        if ('cliente' in vals and (vals.get('cliente') is None or str(vals.get('cliente')).strip() == '')) or (
                            'proveedor' in vals and (vals.get('proveedor') is None or str(vals.get('proveedor')).strip() == '')
                        ):
                            continue
                        if 'nombre' in vals and (vals.get('nombre') is None or str(vals.get('nombre')).strip() == ''):
                            code = vals.get('cliente') or vals.get('proveedor') or ''
                            vals['nombre'] = str(code) or 'SIN_NOMBRE'
                        if 'nombre_fiscal' in vals and (vals.get('nombre_fiscal') is None or str(vals.get('nombre_fiscal')).strip() == ''):
                            vals['nombre_fiscal'] = vals.get('nombre') or 'SIN_NOMBRE'
                        out = []
                        for c in cols:
                            v = vals.get(c)
                            out.append(v if v is not None else '')
                        w.writerow(out)
                    buf.seek(0)
                    cols_csv = ", ".join(cols)
                    self._copy_csv(
                        psy,
                        f'COPY {target_table} ({cols_csv}) FROM STDIN WITH (FORMAT CSV)',
                        buf
                    )

        # Empresas ya se sincroniza mediante sync_empresas/Modelo Empresa; evitamos duplicar en tabla separada
        try:
            _sync_table('Clientes', 'datia_cliente')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Clientes → datia_cliente: {e}")
        try:
            _sync_table('Proveedores', 'datia_proveedores')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Proveedores → datia_proveedores: {e}")
        try:
            _sync_table('Familias', 'datia_familias', int_empresa=False)
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Familias → datia_familias: {e}")
        try:
            _sync_table('Articulos', 'datia_articulos')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Articulos → datia_articulos: {e}")
        try:
            _sync_table('Almacenes', 'datia_almacenes')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Almacenes → datia_almacenes: {e}")
        try:
            _sync_table('Comisionistas', 'datia_comisionistas')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Comisionistas → datia_comisionistas: {e}")
        try:
            _sync_table('Bancos', 'datia_banking_bank')
        except Exception as e:
            print(f"[ETL Masters] Error sincronizando Bancos → datia_banking_bank: {e}")
        try:
            conn.close()
        except Exception:
            pass

    def get_checkpoint(self, empresa: int, ejercicio: int, tipo: str):
        cursor_local = connections['analytics'].cursor()
        cursor_local.execute(
            "SELECT last_fecha, last_serie, last_numero FROM datia_sync_checkpoints WHERE empresa=%s AND ejercicio=%s AND tipo=%s",
            [str(empresa), ejercicio, tipo]
        )
        row = cursor_local.fetchone()
        if row:
            return {'last_fecha': row[0], 'last_serie': row[1], 'last_numero': row[2]}
        return None

    def set_checkpoint(self, empresa: int, ejercicio: int, tipo: str, last_fecha, last_serie=None, last_numero=None):
        cursor_local = connections['analytics'].cursor()
        cursor_local.execute("""
            INSERT INTO datia_sync_checkpoints (empresa, ejercicio, tipo, last_fecha, last_serie, last_numero, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,NOW())
            ON CONFLICT (empresa, ejercicio, tipo) DO UPDATE SET
                last_fecha=EXCLUDED.last_fecha,
                last_serie=EXCLUDED.last_serie,
                last_numero=EXCLUDED.last_numero,
                updated_at=NOW()
        """, [str(empresa), ejercicio, tipo, last_fecha, last_serie, last_numero])

    def sync_mssql_sales_incremental_generator(self, empresa: int, ejercicio: int, days_back: int = 7):
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        try:
            self.ensure_checkpoints_table()
            yield send_progress("Setup", 5, "Incremental Ventas → recálculo directo | DOMAIN: ventas")
            for msg in self.sync_mssql_sales_generator(empresa, ejercicio, fast_bulk=False):
                yield msg
            try:
                from datia.services.totals_service import TotalsService
                TotalsService().aggregate_from_datiadb_sales(int(empresa), int(ejercicio))
                yield send_progress("Metrics", 95, f"Recalculando métricas Ventas {empresa}/{ejercicio}...")
            except Exception as e:
                yield send_progress("Metrics", 95, f"Recalculando métricas Ventas {empresa}/{ejercicio}... (error: {str(e)})")
        except Exception as e:
            yield send_progress("Error", 0, f"Error Incremental Ventas: {str(e)}")
    
    def sync_mssql_purchases_incremental_generator(self, empresa: int, ejercicio: int, days_back: int = 7):
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        try:
            self.ensure_checkpoints_table()
            yield send_progress("Setup", 5, "Incremental Compras → recálculo directo | DOMAIN: compras")
            for msg in self.sync_mssql_purchases_generator(empresa, ejercicio, fast_bulk=False):
                yield msg
            try:
                from datia.services.totals_service import TotalsService
                TotalsService().aggregate_from_datiadb_purchases(int(empresa), int(ejercicio))
                yield send_progress("Metrics", 95, f"Recalculando métricas Compras {empresa}/{ejercicio}...")
            except Exception as e:
                yield send_progress("Metrics", 95, f"Recalculando métricas Compras {empresa}/{ejercicio}... (error: {str(e)})")
        except Exception as e:
            yield send_progress("Error", 0, f"Error Incremental Compras: {str(e)}")
    
    def sync_mssql_financial_incremental_generator(self, empresa: int, ejercicio: int):
        import decimal
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        def normalize_empresa_candidates(val):
            s = str(val).strip()
            arr = [s]
            if s.isdigit():
                arr.append(s.zfill(2))
                arr.append(s.zfill(3))
                arr.append(str(int(s)))
            else:
                try:
                    arr.append(str(int(s)))
                except:
                    pass
            uniq = []
            for x in arr:
                if x not in uniq:
                    uniq.append(x)
            return uniq
        def infer_level(code):
            c = ''.join(ch for ch in str(code) if ch.isdigit())
            n = len(c)
            if n <= 1:
                return 1
            if n == 2:
                return 2
            if n == 3:
                return 3
            if n == 4:
                return 4
            if n <= 6:
                return 5
            return 6
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield send_progress("Setup", 5, "Sincronización Incremental Financiera...")
            cands_plan = self.get_table_candidates(cursor, 'plan_cuentas')
            cands_acum = self.get_table_candidates(cursor, 'acumulados')
            tab_plan, map_plan = self.pick_best_table(cursor, cands_plan, self.COLUMN_MAP_PLAN_CUENTAS, ['empresa','codigo'])
            tab_acum, map_acum = self.pick_best_table(cursor, cands_acum, self.COLUMN_MAP_ACUMULADOS, ['empresa','ejercicio','cuenta','periodo'])
            if not tab_plan and not tab_acum:
                yield send_progress("Error", 0, "Tablas financieras no encontradas.")
                return
            cursor_local = connections['analytics'].cursor()
            emp_candidates = normalize_empresa_candidates(empresa)
            placeholders = ','.join('?' for _ in emp_candidates)
            if tab_plan:
                yield send_progress("Importing", 20, "Actualizando Plan de Cuentas...")
                sel_plan = f"""
                    SELECT 
                        T.{map_plan['codigo']} as codigo,
                        {f"T.{map_plan['descripcion']}" if 'descripcion' in map_plan else "'Sin Descripción'"} as descripcion,
                        {f"T.{map_plan['nivel']}" if 'nivel' in map_plan else "0"} as nivel,
                        {f"T.{map_plan['grupo']}" if 'grupo' in map_plan else "LEFT(T."+map_plan['codigo']+", 1)"} as grupo
                    FROM {tab_plan} T
                    WHERE T.{map_plan['empresa']} IN ({placeholders})
                """
                cursor.execute(sel_plan, tuple(emp_candidates))
                rows_plan = []
                for r in cursor.fetchall():
                    code_s = str(r.codigo).strip()
                    desc_s = str(r.descripcion).strip() if r.descripcion is not None else ''
                    lvl = int(r.nivel) if r.nivel else 0
                    if lvl < 1:
                        lvl = infer_level(code_s)
                    grp = str(r.grupo).strip()[:10] if r.grupo else (code_s[:1] if code_s else '')
                    rows_plan.append((
                        empresa, ejercicio,
                        code_s,
                        (desc_s if desc_s else 'Sin Descripción'),
                        lvl,
                        grp
                    ))
                insert_upsert_plan = """
                    INSERT INTO datia_financial_plan 
                    (empresa, ejercicio, codigo, descripcion, nivel, grupo, es_ultimo_nivel, created_at)
                    VALUES %s
                    ON CONFLICT (empresa, ejercicio, codigo) DO UPDATE SET
                        descripcion=EXCLUDED.descripcion,
                        nivel=EXCLUDED.nivel,
                        grupo=EXCLUDED.grupo,
                        created_at=NOW()
                """
                template_plan = "(%s,%s,%s,%s,%s,%s,false,NOW())"
                if rows_plan:
                    with transaction.atomic(using='analytics'):
                        cursor_local = connections['analytics'].cursor()
                        cursor_local.execute("SET LOCAL synchronous_commit = OFF")
                        self._execute_values_bulk(cursor_local, insert_upsert_plan, rows_plan, template_plan, 5000)
            if tab_acum:
                yield send_progress("Importing", 60, "Actualizando Acumulados...")
                sel_acum = f"""
                    SELECT 
                        T.{map_acum['cuenta']} as cuenta,
                        T.{map_acum['periodo']} as periodo,
                        {f"T.{map_acum['debe']}" if 'debe' in map_acum else "0"} as debe,
                        {f"T.{map_acum['haber']}" if 'haber' in map_acum else "0"} as haber
                    FROM {tab_acum} T
                    WHERE T.{map_acum['empresa']} IN ({placeholders}) AND T.{map_acum['ejercicio']} = ? AND T.{map_acum['periodo']} BETWEEN 0 AND 12
                """
                cursor.execute(sel_acum, tuple(emp_candidates) + (ejercicio,))
                rows_acum = []
                for r in cursor.fetchall():
                    debe = decimal.Decimal(r.debe or 0)
                    haber = decimal.Decimal(r.haber or 0)
                    saldo = debe - haber
                    acct = str(r.cuenta).strip() if r.cuenta is not None else ''
                    if not acct:
                        continue
                    rows_acum.append((
                        empresa, ejercicio,
                        acct,
                        int(r.periodo),
                        str(debe),
                        str(haber),
                        str(saldo)
                    ))
                insert_upsert_acum = """
                    INSERT INTO datia_financial_acumulados 
                    (empresa, ejercicio, cuenta, periodo, debe, haber, saldo, debe_presupuesto, haber_presupuesto, created_at)
                    VALUES %s
                    ON CONFLICT (empresa, ejercicio, cuenta, periodo) DO UPDATE SET
                        debe=EXCLUDED.debe,
                        haber=EXCLUDED.haber,
                        saldo=EXCLUDED.saldo,
                        created_at=NOW()
                """
                template_acum = "(%s,%s,%s,%s,%s,%s,%s,0,0,NOW())"
                if rows_acum:
                    with transaction.atomic(using='analytics'):
                        cursor_local = connections['analytics'].cursor()
                        cursor_local.execute("SET LOCAL synchronous_commit = OFF")
                        self._execute_values_bulk(cursor_local, insert_upsert_acum, rows_acum, template_acum, 5000)
            yield send_progress("Done", 100, "Incremental Financiera Completado")
        except Exception as e:
            yield send_progress("Error", 0, f"Error Incremental Financiera: {str(e)}")
        finally:
            conn.close()

    def sync_mssql_sales(self, empresa: int, ejercicio: int, progress_callback=None):
        for x in self.sync_mssql_sales_generator(empresa, ejercicio):
            if progress_callback:
                progress_callback(x)
            else:
                print(x) 

    def sync_mssql_purchases_generator(self, empresa, ejercicio, fast_bulk: bool = False):
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        yield send_progress("Info", 10, "Compras se calculan exclusivamente desde datiadb_*. ETL estándar no agrega métricas directas.")
        yield send_progress("Done", 100, "Sincronización Compras estándar finalizada (sin tocar metrics_).")

    def sync_empresas(self, empresas_filter=None, allow_db_switch: bool = False):
        """
        Synchronizes the list of companies (Empresas) from MSSQL to Django.
        """
        try:
            from datia.models.master import GlobalConfig
            current_db = self.mssql_db_override or settings.MSSQL_NAME
            cfg = GlobalConfig.load()
            m = cfg.implanter_settings or {}
            stored = m.get('mssql_source_db')
            if stored and str(stored).strip() != str(current_db).strip():
                if not allow_db_switch:
                    raise RuntimeError(f"Origen MSSQL cambiado ({stored} → {current_db}). Debes ejecutar una limpieza global antes de sincronizar empresas.")
                Empresa.objects.all().delete()
                m['mssql_source_db'] = str(current_db).strip()
                cfg.implanter_settings = m
                cfg.save()
            elif not stored:
                m['mssql_source_db'] = str(current_db).strip()
                cfg.implanter_settings = m
                cfg.save()
        except RuntimeError:
            raise
        except Exception:
            pass
        with connection.cursor() as pg_cursor:
            pg_cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS datia_empresa (
                    id BIGSERIAL PRIMARY KEY,
                    codigo INTEGER UNIQUE NOT NULL,
                    nombre VARCHAR(255) NOT NULL,
                    empresa INTEGER,
                    cif VARCHAR(32),
                    fecha_creacion TIMESTAMPTZ,
                    activa BOOLEAN NOT NULL DEFAULT TRUE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            codes = None
            if empresas_filter:
                try:
                    codes = [int(str(c).strip()) for c in empresas_filter if str(c).strip() != ""]
                    if not codes:
                        codes = None
                except Exception:
                    codes = None
            if codes:
                placeholders = ",".join("?" for _ in codes)
                sql = f"SELECT CodigoEmpresa, Empresa FROM Empresas WHERE TRY_CONVERT(int, CodigoEmpresa) IN ({placeholders})"
                cursor.execute(sql, tuple(codes))
            else:
                cursor.execute("SELECT CodigoEmpresa, Empresa FROM Empresas")
            rows = cursor.fetchall()
            count = 0
            valid_codes = []
            for row in rows:
                code = int(str(row.CodigoEmpresa).strip())
                name = row.Empresa or f"Empresa {code}"
                Empresa.objects.update_or_create(
                    codigo=code,
                    defaults={'nombre': name}
                )
                valid_codes.append(code)
                count += 1
            if not codes:
                Empresa.objects.exclude(codigo__in=valid_codes).delete()
            return count
        finally:
            conn.close()

    def get_available_exercises(self, empresa_code: str) -> List[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            years_set = set()
            tab_cab = self.get_exact_table(cursor, 'ventas_cabecera')
            if tab_cab:
                map_cab = self.get_column_mapping(cursor, tab_cab, self.COLUMN_MAP_CABECERA)
                if 'ejercicio' in map_cab and 'empresa' in map_cab:
                    col_ejercicio = map_cab['ejercicio']
                    col_empresa = map_cab['empresa']
                    query = f"SELECT DISTINCT {col_ejercicio} FROM {tab_cab} WHERE TRY_CONVERT(int, {col_empresa}) = ? ORDER BY {col_ejercicio} DESC"
                    cursor.execute(query, (int(str(empresa_code).strip()),))
                    for row in cursor.fetchall():
                        if row[0] is not None:
                            years_set.add(int(row[0]))
            tab_acum = self.get_exact_table(cursor, 'acumulados')
            if tab_acum:
                map_acum = self.get_column_mapping(cursor, tab_acum, self.COLUMN_MAP_ACUMULADOS)
                if 'ejercicio' in map_acum and 'empresa' in map_acum:
                    emp_candidates2 = self._empresa_candidates(empresa_code)
                    placeholders2 = ",".join("?" for _ in emp_candidates2)
                    q2 = f"SELECT DISTINCT T.{map_acum['ejercicio']} FROM {tab_acum} T WHERE T.{map_acum['empresa']} IN ({placeholders2}) ORDER BY T.{map_acum['ejercicio']} DESC"
                    cursor.execute(q2, tuple(emp_candidates2))
                    for row in cursor.fetchall():
                        if row[0] is not None:
                            years_set.add(int(row[0]))
            years = sorted(list(years_set), reverse=True)
            return years
        except Exception as e:
            print(f"Error getting exercises for {empresa_code}: {e}")
            return []
        finally:
            conn.close()


    def sync_structure(self, empresas_filter=None, allow_db_switch: bool = False):
        import os
        from django.db import connections
        from datia.services.runtime_config import mssql_sync_disabled
        disabled = mssql_sync_disabled()
        if not disabled:
            self.sync_empresas(empresas_filter=empresas_filter, allow_db_switch=allow_db_switch)
            self.ensure_master_tables()
            try:
                self.ensure_ai_tables()
            except Exception:
                pass
            try:
                self.sync_mssql_masters()
            except Exception:
                pass
        if disabled:
            return
        try:
            alias = 'analytics' if 'analytics' in connections.databases else 'default'
            with connections[alias].cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                try:
                    cur.execute(
                        """
                        ALTER TABLE metrics_totales_empresa_ejercicio
                        ALTER COLUMN empresa TYPE INTEGER USING empresa::integer
                        """
                    )
                except Exception:
                    pass
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_empresa_unique_empresa_ejercicio
                    ON metrics_totales_empresa_ejercicio (empresa, ejercicio)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_mes (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        mes INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_mes
                    ON metrics_totales_empresa_ejercicio_mes (empresa, ejercicio, mes)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_cliente (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        cliente VARCHAR(64) NOT NULL,
                        nombre VARCHAR(255),
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_cliente
                    ON metrics_totales_empresa_ejercicio_cliente (empresa, ejercicio, cliente)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_articulo (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        articulo VARCHAR(64) NOT NULL,
                        descripcion VARCHAR(255),
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_articulo
                    ON metrics_totales_empresa_ejercicio_articulo (empresa, ejercicio, articulo)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_cod_postal (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        cod_postal VARCHAR(12) NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_cod_postal
                    ON metrics_totales_empresa_ejercicio_cod_postal (empresa, ejercicio, cod_postal)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_cliente_mes (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        cliente VARCHAR(64) NOT NULL,
                        mes INTEGER NOT NULL,
                        nombre VARCHAR(255),
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_cli_mes
                    ON metrics_totales_empresa_ejercicio_cliente_mes (empresa, ejercicio, cliente, mes)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_compra (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_compra
                    ON metrics_totales_empresa_ejercicio_compra (empresa, ejercicio)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_compra_mes (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        mes INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_mes_compra
                    ON metrics_totales_empresa_ejercicio_compra_mes (empresa, ejercicio, mes)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_proveedor (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        proveedor VARCHAR(64) NOT NULL,
                        nombre VARCHAR(255)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_prov
                    ON metrics_totales_empresa_ejercicio_proveedor (empresa, ejercicio, proveedor)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_articulo_compra (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        articulo VARCHAR(64) NOT NULL,
                        descripcion VARCHAR(255)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_art_compra
                    ON metrics_totales_empresa_ejercicio_articulo_compra (empresa, ejercicio, articulo)
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS metrics_totales_empresa_ejercicio_proveedor_mes (
                        id BIGSERIAL PRIMARY KEY,
                        empresa INTEGER NOT NULL,
                        ejercicio INTEGER NOT NULL,
                        importe_neto_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_con_iva_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        importe_coste_total NUMERIC(18,2) NOT NULL DEFAULT 0,
                        albaranes_count INTEGER NOT NULL DEFAULT 0,
                        calculado_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        proveedor VARCHAR(64) NOT NULL,
                        mes INTEGER NOT NULL,
                        nombre VARCHAR(255)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS metrics_tot_emp_ej_prov_mes
                    ON metrics_totales_empresa_ejercicio_proveedor_mes (empresa, ejercicio, proveedor, mes)
                    """
                )
        except Exception:
            pass
        empresas = Empresa.objects.all()
        count = 0
        for emp in empresas:
            years = self.get_available_exercises(emp.codigo)
            for year in years:
                obj, created = MetricsTotalesEmpresaEjercicio.objects.get_or_create(
                    empresa=emp.codigo,
                    ejercicio=year,
                    defaults={
                        'importe_neto_total': 0,
                        'importe_coste_total': 0,
                        'albaranes_count': 0
                    }
                )
                if created:
                    count += 1

    def ensure_raw_sales_tables(self):
        return

    def introspect_and_update_datasource(self, datasource, cursor_mssql):
        from datia.models.semantic import DataSource, DataField
        from django.utils import timezone
        
        summary = {'new_fields': 0, 'updated_fields': 0, 'record_count': 0}
        
        try:
            # 1. Get Record Count
            cursor_mssql.execute(f"SELECT COUNT(*) FROM {datasource.source_table}")
            summary['record_count'] = cursor_mssql.fetchone()[0]
            
            # 2. Get Columns
            cursor_mssql.execute(f"SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (datasource.source_table,))
            columns = cursor_mssql.fetchall()
            
            # 3. Sync DataFields
            for col_name, data_type in columns:
                django_type = 'str'
                if data_type in ['int', 'smallint', 'tinyint', 'bigint']:
                    django_type = 'int'
                elif data_type in ['decimal', 'numeric', 'money', 'float', 'real']:
                    django_type = 'decimal'
                elif data_type in ['date', 'datetime', 'datetime2', 'smalldatetime']:
                    django_type = 'date'
                elif data_type in ['bit']:
                    django_type = 'bool'
                
                field, created = DataField.objects.get_or_create(
                    source=datasource,
                    field_name=col_name,
                    defaults={
                        'business_name': col_name.replace('_', ' ').title(),
                        'data_type': django_type,
                        'auto_discovered': True,
                        'description': f"Campo {col_name} detectado automáticamente.",
                        'usage_type': 'data',
                        'is_active': False
                    }
                )
                
                if not created:
                    if field.data_type != django_type:
                        field.data_type = django_type
                        field.save(update_fields=['data_type', 'updated_at'])
                        summary['updated_fields'] += 1
                else:
                    summary['new_fields'] += 1
            
            datasource.last_sync_at = timezone.now()
            datasource.record_count = summary['record_count']
            datasource.auto_discovered_fields = DataField.objects.filter(
                source=datasource,
                auto_discovered=True
            ).count()
            datasource.save(update_fields=['last_sync_at', 'record_count', 'auto_discovered_fields', 'updated_at'])
            
        except Exception as e:
            print(f"Error in introspection for {datasource.name}: {e}")
            import traceback
            traceback.print_exc()
        
        return summary
    
    def sync_dynamic_tables_generator(self, empresa_id: str, sync_data: bool = True, table_ids: list = None, fast_bulk: bool = False, year_from: int = None, year_to: int = None):
        import json
        from datia.models.semantic import DataSource, DataField
        from django.db import connection, connections
        from django.utils import timezone
        from django.db.models import Q
        
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"

        log_debug(f"START sync_dynamic_tables_generator. Company={empresa_id}, TableIDs={table_ids}, SyncData={sync_data}")
        yield send_progress("DynamicSync", 0, "Iniciando sincronización de tablas personalizadas...")
        
        # Bootstrap default semantic sources (Cabeceras y Líneas estándar) si no existen
        try:
            emp_int = int(empresa_id)
        except Exception:
            emp_int = None
        if emp_int is not None:
            default_sources = [
                ("Ventas - Cabecera Albarán Cliente", "CabeceraAlbaranCliente"),
                ("Ventas - Cabecera Pedido Cliente", "CabeceraPedidoCliente"),
                ("Ventas - Líneas Albarán Cliente", "LineasAlbaranCliente"),
                ("Ventas - Líneas Pedido Cliente", "LineasPedidoCliente"),
                ("Compras - Cabecera Albarán Proveedor", "CabeceraAlbaranProveedor"),
                ("Compras - Cabecera Pedido Proveedor", "CabeceraPedidoProveedor"),
                ("Compras - Líneas Albarán Proveedor", "LineasAlbaranProveedor"),
                ("Compras - Líneas Pedido Proveedor", "LineasPedidoProveedor"),
            ]
            for name, src in default_sources:
                try:
                    DataSource.resolver(
                        emp_int,
                        src,
                        defaults={
                            'name': name,
                            'description': '',
                            'is_virtual': False,
                        },
                    )
                except Exception:
                    # Si falla la creación de una fuente, no bloqueamos el resto del ETL
                    continue
        
        if table_ids:
            log_debug(f"Using explicit table_ids: {table_ids}")
            yield send_progress("DynamicSync", 5, f"Sincronizando {len(table_ids)} tablas seleccionadas...")
            sources = DataSource.objects.filter(id__in=table_ids)
        else:
            log_debug(f"Auto-selecting tables for empresa_id={empresa_id}")
            # Migrar todas las fuentes definidas para la empresa, aunque todavía no tengan campos
            sources = DataSource.objects.all().order_by('id')
        
        total_sources = sources.count()
        if total_sources == 0:
            yield send_progress("DynamicSync", 100, "No hay tablas que necesiten sincronización.")
            return

        conn_mssql = self.get_connection()
        cursor_mssql = conn_mssql.cursor()
        try:
            cursor_mssql.timeout = 60
        except Exception:
            pass
        
        try:
            for idx, source in enumerate(sources):
                progress_base = int((idx / total_sources) * 100)
                local_table = source.get_local_table_name()
                yield send_progress("DynamicSync", progress_base, f"Procesando {source.name} ({source.source_table}) | TABLE: {local_table}")
                
                if source.is_virtual:
                    yield send_progress("DynamicSync", progress_base, f"📡 {source.name}: Tabla virtual (No migrada). Actualizando estado... | TABLE: {local_table}")
                    source.is_active = True
                    source.last_sync_at = timezone.now()
                    source.save(update_fields=['is_active', 'last_sync_at'])
                    continue
                
                yield send_progress("DynamicSync", progress_base, f"{source.name}: Introspectando esquema MSSQL... | TABLE: {local_table}")
                introspect_summary = self.introspect_and_update_datasource(source, cursor_mssql)
                
                # [FIX] Actually Materialize the table (Create + Copy Data)
                if sync_data:
                    try:
                        for step in self.materialize_dynamic_table_generator(
                            source,
                            cursor_mssql,
                            empresa_id,
                            base=progress_base,
                            span=8,
                            fast_bulk=fast_bulk,
                            year_from=year_from,
                            year_to=year_to,
                        ):
                            yield step
                    except Exception as mat_err:
                        print(f"Error materializing {source.name}: {mat_err}")
                        yield send_progress("DynamicSync", progress_base, f"{source.name}: ⚠️ Error al copiar datos: {mat_err}")
                
                 # Update Active Status correctly
                source.is_active = True
                source.last_sync_at = timezone.now()
                source.save(update_fields=['is_active', 'last_sync_at'])
                
                if introspect_summary['new_fields'] > 0 or introspect_summary['updated_fields'] > 0:
                    yield send_progress("DynamicSync", progress_base, f"{source.name}: {introspect_summary['new_fields']} campos nuevos, {introspect_summary['updated_fields']} actualizados, {introspect_summary['record_count']} registros en MSSQL | TABLE: {local_table}")
                
                yield send_progress("DynamicSync", progress_base, f"{source.name}: ✅ Completado ({source.record_count} registros) | TABLE: {local_table}")
            
            yield send_progress("DynamicSync", 100, "Sincronización dinámica finalizada.")


        except Exception as e:
            import traceback
            error_msg = f"Error en sincronización dinámica: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            yield send_progress("Error", 0, error_msg)
        finally:
            conn_mssql.close()

    def materialize_dynamic_table(self, source, cursor_mssql):
        """
        Creates physical table datiaDB_{OriginalName} in Postgres and copies data.
        """
        postgres_table = source.get_local_table_name()
        
        # 1. Fetch Columns to build CREATE TABLE
        # We use the DataFields we just managed/introspected
        from django.db.models import Q
        try:
            from datia.models.semantic import StandardField as _StdField
            std_names = list(_StdField.objects.values_list('name', flat=True))
        except Exception:
            std_names = []
        fields = source.fields.filter(usage_type__in=['dimension', 'metric', 'date', 'data']).filter(
            Q(is_active=True) | Q(field_name__in=std_names)
        )
        if not fields.exists():
            fields = source.fields.filter(usage_type__in=['dimension', 'metric', 'date', 'data'])
        if not fields.exists():
            print(f"Skipping materialization for {source.name}: No fields available.")
            return 0

        # Build Headers
        col_defs = []
        sel_cols = []
        pg_cols = []
        for f in fields:
            pg_type = 'TEXT' # Default
            if f.data_type == 'int': pg_type = 'BIGINT'
            elif f.data_type == 'decimal': pg_type = 'NUMERIC(18,4)'
            elif f.data_type == 'date': pg_type = 'TIMESTAMP'
            elif f.data_type == 'bool': pg_type = 'BOOLEAN'
            
            # Sanitize column name
            safe_col = f.field_name.lower().replace(' ', '_').replace('.', '_')
            if safe_col == 'id': safe_col = 'source_id' # Avoid PK conflict
            if safe_col == 'order': safe_col = '"order"' # Reserved keyword
            
            col_defs.append(f'"{safe_col}" {pg_type}')
            pg_cols.append(safe_col if safe_col != '"order"' else 'order')
            sel_cols.append(f"[{f.field_name}]") # MSSQL quoting
            
        create_sql = f'CREATE TABLE "{postgres_table}" ({", ".join(col_defs)});'
        
        from django.db import connections
        pg_conn = connections['analytics']
        
        total_copied = 0
        
        with pg_conn.cursor() as pg_cursor:
            pg_cursor.execute(f'DROP TABLE IF EXISTS "{postgres_table}"')
            pg_cursor.execute(create_sql)
            BATCH_SIZE = 5000
            cursor_mssql.execute(f"SELECT {','.join(sel_cols)} FROM {source.source_table} WITH (NOLOCK)")
            with transaction.atomic(using='analytics'):
                import io, csv
                psy_cursor = connections['analytics'].connection.cursor()
                psy_cursor.execute("SET LOCAL synchronous_commit = OFF")
                while True:
                    rows = cursor_mssql.fetchmany(BATCH_SIZE)
                    if not rows: break
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for row in rows:
                        out = []
                        for val in row:
                            out.append(str(val) if val is not None else '')
                        writer.writerow(out)
                    buf.seek(0)
                    cols_quoted = ", ".join([f'"{c}"' for c in pg_cols])
                    self._copy_csv(
                        psy_cursor,
                        f'COPY "{postgres_table}" ({cols_quoted}) FROM STDIN WITH (FORMAT CSV)',
                        buf
                    )
                    total_copied += len(rows)
            try:
                self._ensure_datiadb_perf(postgres_table)
            except Exception:
                pass
                
        return total_copied
    
    def materialize_dynamic_table_generator(self, source, cursor_mssql, empresa_id=None, base=0, span=8, fast_bulk: bool = False, year_from: int = None, year_to: int = None):
        import json
        from django.db import connections
        import re
        from types import SimpleNamespace

        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"

        postgres_table = source.get_local_table_name()
        from django.db.models import Q
        # 1) Resolver Campos Estándar globales
        std_by_name = {}
        std_names = []
        try:
            from datia.models.semantic import StandardField as _StdField
            std_list = list(_StdField.objects.all())
            std_by_name = {str(s.name): s for s in std_list}
            std_names = [str(s.name) for s in std_list]
        except Exception:
            std_by_name = {}
            std_names = []

        # 2) Campos definidos en el DataSource (solo activos o StandardField)
        fields_qs = source.fields.filter(usage_type__in=['dimension', 'metric', 'date', 'data']).filter(
            Q(is_active=True) | Q(field_name__in=std_names)
        )
        if not fields_qs.exists():
            # Fallback: materializar aunque los campos todavía no estén marcados como activos
            fields_qs = source.fields.filter(usage_type__in=['dimension', 'metric', 'date', 'data'])

        # 3) Detectar columnas reales en MSSQL para enriquecer con StandardField
        try:
            cursor_mssql.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?", (source.source_table,))
            available_cols = [str(r[0]) for r in cursor_mssql.fetchall()]
        except Exception:
            available_cols = []

        # 4) Asegurar que todas las columnas estándar presentes en MSSQL están en la lista de campos
        existing_field_names = {str(f.field_name) for f in fields_qs}
        extra_fields = []
        for col in available_cols:
            if col in existing_field_names:
                continue
            std = std_by_name.get(col)
            if not std:
                continue
            dt = 'text'
            role = (std.semantic_role or '').upper()
            if role in ('METRIC',) or col.lower() in ('importe', 'importeneto', 'importecoste', 'cantidad', 'unidades', 'precio', 'precio_unitario', 'coste'):
                dt = 'decimal'
            elif role in ('DATE',) or col.lower().startswith('fecha'):
                dt = 'date'
            elif role in ('PK', 'FK'):
                dt = 'int'
            extra_fields.append(
                SimpleNamespace(
                    field_name=col,
                    source_table_name=source.source_table,
                    business_name=std.business_name or col,
                    synonyms=[],
                    description=std.description or "",
                    metadata_tag="",
                    data_type=dt,
                )
            )

        fields = list(fields_qs) + extra_fields
        if not fields:
            yield send_progress("DynamicSync", base, f"{source.name}: Sin campos disponibles")
            return

        yield send_progress("DynamicSync", base, f"{source.name}: Origen→Destino: {source.source_table} → {postgres_table} | TABLE: {postgres_table}")
        # Detectar columnas reales en MSSQL para mapear field_name/sinónimos
        def _norm(s: str) -> str:
            return re.sub(r'[^a-z0-9]', '', str(s or '').lower())
        norm_map = {_norm(c): c for c in available_cols}
        col_defs = []
        sel_cols = []
        pg_cols = []
        pg_cols_types = []
        empresa_src_col = None
        empresa_pg_col = None
        ejercicio_src_col = None
        used_cols = set()
        for f in fields:
            pg_type = 'TEXT'
            if f.data_type == 'int':
                pg_type = 'BIGINT'
            elif f.data_type == 'decimal':
                pg_type = 'NUMERIC(18,4)'
            elif f.data_type == 'date':
                pg_type = 'TIMESTAMP'
            elif f.data_type == 'bool':
                pg_type = 'BOOLEAN'
            preferred_name = f.business_name if f.business_name else f.field_name
            safe_col = preferred_name.strip().lower()
            safe_col = re.sub(r'\s+', '_', safe_col)
            safe_col = safe_col.replace('.', '_')
            safe_col = re.sub(r'[^a-z0-9_]', '', safe_col)
            if safe_col == 'id':
                safe_col = 'source_id'
            # Reserve exact "order" keyword; duplicates will become "order_2", "order_3", ...
            is_order_reserved = (safe_col == 'order')
            # Ensure uniqueness
            base_name = safe_col
            counter = 2
            while base_name in used_cols or (is_order_reserved and base_name == 'order' and 'order' in used_cols):
                base_name = f"{safe_col}_{counter}"
                is_order_reserved = False
                counter += 1
            safe_col = base_name
            used_cols.add(safe_col)
            # Apply reserved quoting only for exact "order"
            col_name_sql = '"order"' if is_order_reserved and safe_col == 'order' else f'"{safe_col}"'
            # Resolver columna real en MSSQL: field_name + synonyms
            candidates = [f.field_name]
            try:
                if isinstance(f.synonyms, list):
                    candidates.extend([str(x) for x in f.synonyms if x])
                elif f.synonyms:
                    candidates.extend([s.strip() for s in str(f.synonyms).split(',') if s.strip()])
            except Exception:
                pass
            # Añadir algunas variantes simples
            variants = []
            for cand in candidates:
                variants.append(cand)
                variants.append(cand.replace(' ', ''))
                variants.append(cand.replace(' ', '_'))
                variants.append(cand.replace('_', ''))
            candidates = variants
            picked = None
            for cand in candidates:
                n = _norm(cand)
                if n in norm_map:
                    picked = norm_map[n]
                    break
            if not picked:
                # Si no hay correspondencia, saltar la columna para evitar errores 42S22
                continue
            col_defs.append(f'{col_name_sql} {pg_type}')
            eff_col = 'order' if is_order_reserved and safe_col == 'order' else safe_col
            pg_cols.append(eff_col)
            pg_cols_types.append((eff_col, pg_type))
            sel_cols.append(f"[{picked}]")
            try:
                bn = (f.business_name or '').strip().lower()
            except Exception:
                bn = ''
            if not empresa_src_col and (bn == 'codigoempresa' or eff_col in ('codigoempresa', 'empresa', 'empresacodigo')):
                empresa_src_col = picked
                empresa_pg_col = eff_col
            if not ejercicio_src_col and bn == 'ejercicio':
                ejercicio_src_col = picked
        
        # Fallback: Detectar columna de empresa si no se encontró por metadata
        if not empresa_pg_col:
            for c_pg, c_src in zip(pg_cols, sel_cols):
                # c_src es "[NombreOriginal]"
                raw_src = c_src.replace('[', '').replace(']', '').lower()
                if raw_src in ('codigoempresa', 'empresa', 'empresacodigo'):
                    empresa_pg_col = c_pg
                    empresa_src_col = raw_src # Aproximado, ya que sel_cols tiene quoting
                    break
        if not ejercicio_src_col:
            try:
                mapping = self.static_mapping.get(source.source_table, {})
                if isinstance(mapping, dict):
                    ej_col = mapping.get('ejercicio')
                    if ej_col:
                        ejercicio_src_col = ej_col
            except Exception:
                ejercicio_src_col = None
        if not ejercicio_src_col:
            for c in available_cols:
                n = _norm(c)
                if n in ('ejercicio', 'ejercicioalbaran', 'ejerciciopedido'):
                    ejercicio_src_col = c
                    break
        
        if not col_defs:
            try:
                from datia.models.semantic import DataField as _DF
                fb_fields = list(_DF.objects.filter(source=source, auto_discovered=True))
            except Exception:
                fb_fields = []
            for f in fb_fields:
                pg_type = 'TEXT'
                dt = getattr(f, 'data_type', 'str')
                if dt == 'int':
                    pg_type = 'BIGINT'
                elif dt == 'decimal':
                    pg_type = 'NUMERIC(18,4)'
                elif dt == 'date':
                    pg_type = 'TIMESTAMP'
                elif dt == 'bool':
                    pg_type = 'BOOLEAN'
                name_src = str(getattr(f, 'field_name', '') or '')
                if not name_src:
                    continue
                safe_col = name_src.strip().lower()
                safe_col = re.sub(r'\s+', '_', safe_col)
                safe_col = safe_col.replace('.', '_')
                safe_col = re.sub(r'[^a-z0-9_]', '', safe_col)
                if safe_col == 'id':
                    safe_col = 'source_id'
                is_order_reserved = (safe_col == 'order')
                base_name = safe_col
                counter = 2
                while base_name in used_cols or (is_order_reserved and base_name == 'order' and 'order' in used_cols):
                    base_name = f"{safe_col}_{counter}"
                    is_order_reserved = False
                    counter += 1
                safe_col = base_name
                used_cols.add(safe_col)
                col_name_sql = '"order"' if is_order_reserved and safe_col == 'order' else f'"{safe_col}"'
                col_defs.append(f'{col_name_sql} {pg_type}')
                eff_col = 'order' if is_order_reserved and safe_col == 'order' else safe_col
                pg_cols.append(eff_col)
                pg_cols_types.append((eff_col, pg_type))
                sel_cols.append(f"[{name_src}]")
                if not empresa_src_col:
                    n = _norm(name_src)
                    if 'empresa' in n:
                        empresa_src_col = name_src
                        empresa_pg_col = eff_col
        if not col_defs:
            yield send_progress("DynamicSync", base, f"{source.name}: Sin columnas válidas tras mapeo (revise sinónimos/activos)")
            return
        create_sql = f'CREATE TABLE "{postgres_table}" ({", ".join(col_defs)});'
        pg_conn = connections['analytics']
        total = int(source.record_count or 0)
        copied = 0
        batch_idx = 0
        with pg_conn.cursor() as pg_cursor:
            exists = False
            try:
                pg_cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name = %s", [postgres_table])
                exists = bool(pg_cursor.fetchone()[0])
            except Exception:
                exists = False
            if exists:
                pg_cursor.execute(
                    "SELECT table_type FROM information_schema.tables WHERE table_schema='public' AND table_name = %s",
                    [postgres_table],
                )
                kind_row = pg_cursor.fetchone()
                if kind_row and str(kind_row[0]).upper() == 'VIEW':
                    pg_cursor.execute(f'DROP VIEW IF EXISTS "{postgres_table}"')
                    exists = False
            if not exists:
                pg_cursor.execute(create_sql)
            else:
                try:
                    pg_cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [postgres_table])
                    existing_cols = [r[0] for r in pg_cursor.fetchall()]
                except Exception:
                    existing_cols = []
                for name, typ in pg_cols_types:
                    if name not in existing_cols:
                        try:
                            pg_cursor.execute(f'ALTER TABLE "{postgres_table}" ADD COLUMN "{name}" {typ}')
                        except Exception:
                            try:
                                pg_cursor.execute(f'ALTER TABLE "{postgres_table}" ADD COLUMN IF NOT EXISTS "{name}" {typ}')
                            except Exception:
                                pass
            # Borrado por empresa (solo filas de la empresa)
            if empresa_pg_col and empresa_id is not None:
                try:
                    emp_val = int(str(empresa_id).strip())
                    pg_cursor.execute(f'DELETE FROM "{postgres_table}" WHERE "{empresa_pg_col}" = %s', [emp_val])
                except Exception:
                    pass
            BATCH_SIZE = 5000
            expected_batches = max(1, (total + BATCH_SIZE - 1) // BATCH_SIZE)
            if not sel_cols:
                yield send_progress("DynamicSync", base, f"{source.name}: Sin columnas mapeadas disponibles en MSSQL")
                return
            where_clauses = []
            params = []
            if empresa_src_col and empresa_id is not None:
                s = str(empresa_id).strip()
                emp_params = [s]
                if s.isdigit():
                    try:
                        emp_params.append(str(int(s)))
                    except Exception:
                        pass
                    emp_params.append(s.zfill(2))
                    emp_params.append(s.zfill(3))
                ph = ",".join("?" for _ in emp_params)
                where_clauses.append(f"[{empresa_src_col}] IN ({ph})")
                params.extend(emp_params)
            if ejercicio_src_col and year_from is not None:
                where_clauses.append(f"[{ejercicio_src_col}] >= ?")
                params.append(int(year_from))
            if ejercicio_src_col and year_to is not None:
                where_clauses.append(f"[{ejercicio_src_col}] <= ?")
                params.append(int(year_to))
            where_sql = ""
            if where_clauses:
                where_sql = " WHERE " + " AND ".join(where_clauses)
            src_from = f"{source.source_table} WITH (NOLOCK)"
            try:
                if where_sql:
                    cursor_mssql.execute(f"SELECT COUNT(*) FROM {src_from}{where_sql}", tuple(params))
                    total = int(cursor_mssql.fetchone()[0] or 0)
            except Exception:
                pass
            if params:
                cursor_mssql.execute(f"SELECT {','.join(sel_cols)} FROM {src_from}{where_sql}", tuple(params))
            else:
                cursor_mssql.execute(f"SELECT {','.join(sel_cols)} FROM {src_from}")
            if not fast_bulk:
                import io, csv
                with transaction.atomic(using='analytics'):
                    psy_cursor = connections['analytics'].connection.cursor()
                    psy_cursor.execute("SET LOCAL synchronous_commit = OFF")
                    while True:
                        rows = cursor_mssql.fetchmany(BATCH_SIZE)
                        if not rows:
                            break
                        buf = io.StringIO()
                        writer = csv.writer(buf)
                        for row in rows:
                            out = []
                            for val in row:
                                out.append(str(val) if val is not None else '')
                            writer.writerow(out)
                        buf.seek(0)
                        cols_quoted = ", ".join([f'"{c}"' for c in pg_cols])
                        self._copy_csv(
                            psy_cursor,
                            f'COPY "{postgres_table}" ({cols_quoted}) FROM STDIN WITH (FORMAT CSV)',
                            buf
                        )
                        copied += len(rows)
                        batch_idx += 1
                        pct = base + min(span, batch_idx)
                        if pct > base + span:
                            pct = base + span
                        yield send_progress("DynamicSync", pct, f"{source.name}: Materializando datos ({copied}/{total})... | TABLE: {postgres_table}")
            else:
                import io, csv
                with transaction.atomic(using='analytics'):
                    psy_cursor = connections['analytics'].connection.cursor()
                    psy_cursor.execute("SET LOCAL synchronous_commit = OFF")
                    while True:
                        rows = cursor_mssql.fetchmany(BATCH_SIZE)
                        if not rows:
                            break
                        buf = io.StringIO()
                        writer = csv.writer(buf)
                        for row in rows:
                            out = []
                            for val in row:
                                out.append(str(val) if val is not None else '')
                            writer.writerow(out)
                        buf.seek(0)
                        cols_quoted = ", ".join([f'"{c}"' for c in pg_cols])
                        self._copy_csv(
                            psy_cursor,
                            f'COPY "{postgres_table}" ({cols_quoted}) FROM STDIN WITH (FORMAT CSV)',
                            buf
                        )
                        copied += len(rows)
                        batch_idx += 1
                        pct = base + min(span, batch_idx)
                        if pct > base + span:
                            pct = base + span
                        yield send_progress("DynamicSync", pct, f"{source.name}: Materializando datos ({copied}/{total})... | TABLE: {postgres_table}")
        try:
            self._ensure_datiadb_perf(postgres_table)
        except Exception:
            pass
        yield send_progress("DynamicSync", base + span, f"{source.name}: ✅ Datos copiados ({copied} filas). | TABLE: {postgres_table}")

    def sync_all_years_for_empresa_generator(self, empresa_id, filter_table=None, sync_type='all', table_ids=None, sync_data=True, target_year=None, fast_bulk=False, years_count=None, standard_tables=None):
        import json
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        
        should_sync_standard = sync_type in ['all', 'standard']
        should_sync_trained = sync_type in ['all', 'trained']
        if should_sync_standard:
            yield send_progress("Setup", 5, "Sincronizando estructura base...")
            try:
                emp_code = int(str(empresa_id).strip())
                self.sync_structure(empresas_filter=[emp_code])
            except Exception:
                self.sync_structure()
        else:
            yield send_progress("Setup", 5, "Preparando sincronización entrenada...")
        try:
            from datia.services.runtime_config import mssql_sync_disabled
            disable_mssql = mssql_sync_disabled()
        except Exception:
            disable_mssql = False
        if disable_mssql and should_sync_standard:
            should_sync_standard = False
            yield send_progress("Setup", 8, "Sincronización estándar desactivada: se mantienen solo las tablas entrenadas.")
        selected_std = None
        if standard_tables is not None:
            try:
                selected_std = [str(x).strip() for x in standard_tables if str(x).strip() in ['ventas','compras','financiera','existencias']]
            except Exception:
                selected_std = []
        if selected_std is not None and len(selected_std) == 0 and sync_type == 'all':
            should_sync_standard = False

        def domain_on(name):
            return selected_std is None or name in selected_std
        
        if sync_type == 'standard':
            if not standard_tables or not selected_std:
                yield send_progress("Error", 0, "Debe seleccionar al menos una tabla estándar.")
                return
        
        if (filter_table or table_ids) and sync_type == 'trained':
            should_sync_standard = False
            yield send_progress("Syncing", 10, "Saltando tablas estándar (Modo Entrenadas Granular)...")
        
        year_from = None
        year_to = None
        try:
            yc = int(years_count) if years_count is not None else 10
            if yc > 0:
                cy = int(target_year) if target_year is not None else datetime.now().year
                year_to = cy
                year_from = cy - yc + 1
        except Exception:
            year_from = None
            year_to = None
        
        if should_sync_standard:
            years = self.get_available_exercises(empresa_id)
            processed_years = []
            if years:
                try:
                    yc = int(years_count) if years_count is not None else 10
                    cy = int(target_year) if target_year is not None else datetime.now().year
                    filtered = [y for y in years if y <= cy]
                    filtered.sort(reverse=True)
                    original_count = len(filtered)
                    years = filtered[:yc]
                    print(f"📉 Optimization: Filtered years from {original_count} to {len(years)} (Top {yc} up to {cy})")
                    yield send_progress("Syncing", 10, f"Optimización: {yc} ejercicios desde {cy} hacia atrás")
                except Exception as e:
                    print(f"Error filtering years_count: {e}")

            if not years:
                raise RuntimeError(f"No se encontraron ejercicios disponibles en MSSQL para la empresa {empresa_id}.")

            if years:
                total_years = len(years)
                for idx, year in enumerate(years):
                    base_p = 10 + int((idx / total_years) * 60)
                    # Helper para anotar la tabla destino en el mensaje si no aparece
                    def _annotate(update: str):
                        try:
                            if isinstance(update, str) and update.startswith("data: "):
                                payload = update.replace("data: ", "").strip()
                                obj = json.loads(payload)
                                msg = str(obj.get('message', ''))
                                if "TABLE:" not in msg:
                                    low = msg.lower()
                                    tbl = None
                                    if ("cabeceras compras" in low) or ("cabeceras compra" in low):
                                        tbl = "datiadb_cabeceraalbaranproveedor"
                                    elif (
                                        ("líneas compras" in low)
                                        or ("lineas compras" in low)
                                        or ("líneas compra" in low)
                                        or ("lineas compra" in low)
                                    ):
                                        tbl = "datiadb_lineasalbaranproveedor"
                                    elif "cabeceras" in low:
                                        tbl = "datiadb_cabeceraalbarancliente"
                                    elif ("líneas" in low) or ("lineas" in low):
                                        tbl = "datiadb_lineasalbarancliente"
                                    if tbl:
                                        obj["message"] = f"{msg} | TABLE: {tbl}"
                                        return f"data: {json.dumps(obj)}\\n\\n"
                        except Exception:
                            return update
                        return update
                    if domain_on('ventas'):
                        if not self.has_baseline(empresa_id, year, 'ventas'):
                            yield send_progress("Syncing", base_p, f"Sincronizando Ventas (Inicial) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_sales_generator(empresa_id, year, fast_bulk=fast_bulk):
                                yield _annotate(progress_update)
                        else:
                            yield send_progress("Syncing", base_p, f"Sincronizando Ventas (Incremental) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_sales_incremental_generator(empresa_id, year, days_back=7):
                                yield _annotate(progress_update)
                    if domain_on('compras'):
                        if not self.has_baseline(empresa_id, year, 'compras'):
                            yield send_progress("Syncing", base_p + 5, f"Sincronizando Compras (Inicial) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_purchases_generator(empresa_id, year, fast_bulk=fast_bulk):
                                yield _annotate(progress_update)
                        else:
                            yield send_progress("Syncing", base_p + 5, f"Sincronizando Compras (Incremental) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_purchases_incremental_generator(empresa_id, year, days_back=7):
                                yield _annotate(progress_update)
                    if domain_on('financiera'):
                        if not self.has_baseline(empresa_id, year, 'financiera'):
                            yield send_progress("Syncing", base_p + 10, f"Sincronizando Financiera (Inicial) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_financial_generator(empresa_id, year, fast_bulk=fast_bulk):
                                yield progress_update
                            yield send_progress("Syncing", base_p + 12, f"Sincronizando CarteraEfectos (Inicial) - Ejercicio {year}...")
                            for update in self.sync_mssql_cartera_generator(empresa_id, year):
                                if isinstance(update, str):
                                    yield update
                                else:
                                    pct_local = base_p + 12 + int((int(update.get('percentage', 0)) / 100.0) * 5)
                                    yield f"data: {json.dumps({'step': 'Cartera', 'percent': pct_local, 'message': update.get('message','')})}\\n\\n"
                        else:
                            yield send_progress("Syncing", base_p + 10, f"Sincronizando Financiera (Incremental) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_financial_incremental_generator(empresa_id, year):
                                yield progress_update
                            yield send_progress("Syncing", base_p + 12, f"Sincronizando CarteraEfectos (Incremental) - Ejercicio {year}...")
                            for update in self.sync_mssql_cartera_incremental_generator(empresa_id, year, days_back=90):
                                try:
                                    if isinstance(update, str):
                                        yield update
                                    else:
                                        pct_local = base_p + 12 + int((int(update.get('percentage', 0)) / 100.0) * 5)
                                        yield f"data: {json.dumps({'step': 'Cartera', 'percent': pct_local, 'message': update.get('message','')})}\\n\\n"
                                except:
                                    yield send_progress("Syncing", base_p + 12, "CarteraEfectos en proceso...")
                    if domain_on('existencias'):
                        if not self.has_baseline(empresa_id, year, 'existencias'):
                            yield send_progress("Syncing", base_p + 15, f"Sincronizando Existencias (Inicial) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_stocks_generator(empresa_id, year, fast_bulk=fast_bulk):
                                yield progress_update
                        else:
                            yield send_progress("Syncing", base_p + 15, f"Sincronizando Existencias (Incremental) - Ejercicio {year}...")
                            for progress_update in self.sync_mssql_stocks_incremental_generator(empresa_id, year, periods_back=2):
                                yield progress_update
                    processed_years.append(year)

        else:
            yield send_progress("Syncing", 70, "Omitiendo tablas estándar (solo entrenadas)...")

        if should_sync_trained:
            yield send_progress("DynamicSync", 75, "Iniciando sincronización de tablas entrenadas...")
            for dy_progress in self.sync_dynamic_tables_generator(
                empresa_id,
                sync_data=sync_data,
                table_ids=table_ids,
                fast_bulk=fast_bulk,
                year_from=year_from,
                year_to=year_to,
            ):
                yield dy_progress
        else:
            yield send_progress("DynamicSync", 95, "Omitiendo tablas entrenadas (solo estándar)...")

        # Recalcular siempre metrics_* desde datiadb_* cuando existan cabeceras,
        # independientemente de sync_type (all, standard, trained)
        from django.db import connections
        try:
            with connections['analytics'].cursor() as cur:
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('datiadb_cabeceraalbarancliente','datiadb_cabecerapedidocliente','datiadb_cabeceraalbaranproveedor')")
                exists = [r[0] for r in cur.fetchall()]
                years_set = set()
                def pick(cols, candidates):
                    s = set([c.lower() for c in cols])
                    for c in candidates:
                        if c in s:
                            return c
                    return None
                for t in exists:
                    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", [t])
                    cols = [r[0] for r in cur.fetchall()]
                    emp_col = pick(cols, ['codigoempresa','empresa','empresacodigo'])
                    year_col = pick(cols, ['ejercicioalbaran','ejercicio','year'])
                    date_col = pick(cols, ['fechaalbaran','fecha','fechapedido'])
                    if not emp_col:
                        continue
                    year_expr = year_col if year_col else (f"CAST(EXTRACT(YEAR FROM {date_col}) AS INTEGER)" if date_col else None)
                    if not year_expr:
                        continue
                    cur.execute(f"SELECT DISTINCT {year_expr} FROM {t} WHERE {emp_col} = %s ORDER BY 1 DESC", [int(empresa_id)])
                    for r in cur.fetchall():
                        if r[0] is not None:
                            try:
                                years_set.add(int(r[0]))
                            except:
                                pass
                years = sorted(list(years_set), reverse=True)
        except Exception:
            years = []
        try:
            from datia.services.totals_service import TotalsService
            ts = TotalsService()
            for y in (years or []):
                yield send_progress("Metrics", 96, f"Recalculando métricas Ventas {empresa_id}/{y} desde datiadb_...")
                try:
                    ts.aggregate_from_datiadb_sales(int(empresa_id), int(y))
                except Exception:
                    pass
                yield send_progress("Metrics", 97, f"Recalculando métricas Compras {empresa_id}/{y} desde datiadb_...")
                try:
                    ts.aggregate_from_datiadb_purchases(int(empresa_id), int(y))
                except Exception:
                    pass
        except Exception:
            pass

        try:
            msg_done = f"Sincronización de {empresa_id} completada."
            if should_sync_standard:
                if 'processed_years' in locals() and processed_years:
                    msg_done = f"{msg_done} Ejercicios: {','.join([str(y) for y in processed_years])}"
            yield send_progress("Done", 100, msg_done)
            if should_sync_standard and 'processed_years' in locals():
                log_debug(f"Validation Report empresa={empresa_id} years={processed_years}")
        except:
            yield send_progress("Done", 100, f"Sincronización de {empresa_id} completada.")

    def has_baseline(self, empresa: int, ejercicio: int, dominio: str) -> bool:
        from django.db import connections
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        if dominio == 'cartera' and 'default' in connections.databases:
            alias = 'default'
        table = None
        if dominio == 'ventas':
            table = 'metrics_totales_empresa_ejercicio'
        elif dominio == 'compras':
            table = 'metrics_totales_empresa_ejercicio_compra'
        elif dominio == 'financiera':
            table = 'datia_financial_acumulados'
        elif dominio == 'existencias':
            table = 'datia_acumulados_stocks'
        elif dominio == 'cartera':
            try:
                from datia.models.financial import DatiaCarteraEfectos
                table = DatiaCarteraEfectos._meta.db_table
            except:
                table = None
        if not table:
            return False
        try:
            with connections[alias].cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
                cnt = cur.fetchone()[0] or 0
                return cnt > 0
        except:
            return False

    def sync_all(self):
        self.sync_structure()
        
        empresas = Empresa.objects.all()
        for emp in empresas:
            print(f"--- Processing {emp.nombre} ({emp.codigo}) ---")
            years = self.get_available_exercises(emp.codigo)
            print(f"Found exercises: {years}")
            
            for year in years:
                try:
                    print(f"Syncing {emp.codigo} / {year}...")
                    self.sync_mssql_sales(emp.codigo, year)
                except Exception as e:
                    print(f"Failed to sync {emp.codigo}/{year}: {e}")

    def sync_mssql_stocks_generator(self, empresa: int, ejercicio: int, fast_bulk: bool = False):
        import json
        import decimal
        import io
        import csv
        from datia.services.cache_service import compute_mssql_fingerprint
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        self.ensure_stocks_table()
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield send_progress("Setup", 0, "Iniciando Sincronización de Existencias...")
            candidates = self.get_table_candidates(cursor, 'stocks')
            tab_stk, map_stk = self.pick_best_table(cursor, candidates, self.COLUMN_MAP_STOCKS, ['empresa', 'ejercicio', 'periodo', 'articulo', 'importe_saldo'])
            if not tab_stk:
                yield send_progress("Skipped", 100, "No se encontró tabla de existencias.")
                return
            yield send_progress("Setup", 5, f"Tabla seleccionada: {tab_stk}")
            cursor_local = connections['analytics'].cursor()
            cursor_local.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'datia_acumulados_stocks'")
            existing_cols = [r[0] for r in cursor_local.fetchall()]
            if 'unidadsaldo' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS unidadsaldo NUMERIC(18,4) DEFAULT 0")
            if 'preciomedio' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS preciomedio NUMERIC(18,4) DEFAULT 0")
            if 'precioultimaentrada' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS precioultimaentrada NUMERIC(18,4) DEFAULT 0")
            if 'preciocompra' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS preciocompra NUMERIC(18,4) DEFAULT 0")
            if 'almacen_name' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS almacen_name VARCHAR(128)")
            if 'articulo_desc' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS articulo_desc VARCHAR(256)")
            if 'source_fp' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS source_fp VARCHAR(16)")
            cursor_local.execute("DELETE FROM datia_acumulados_stocks WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            emp_candidates = self._empresa_candidates(empresa)
            placeholders_emp = ",".join("?" for _ in emp_candidates)
            count_sql = f"SELECT COUNT(*) FROM {tab_stk} T WHERE T.{map_stk['empresa']} IN ({placeholders_emp}) AND T.{map_stk['ejercicio']} = ?"
            cursor.execute(count_sql, tuple(emp_candidates + [ejercicio]))
            total_rows = cursor.fetchone()[0] or 1
            yield send_progress("Importing", 10, f"Importando Existencias (0 / {total_rows})...")
            units_expr = f"T.{map_stk['unidad_saldo']}" if 'unidad_saldo' in map_stk else "NULL"
            medio_expr = f"T.{map_stk['precio_medio']}" if 'precio_medio' in map_stk else "NULL"
            ultima_expr = f"T.{map_stk['precio_ultima']}" if 'precio_ultima' in map_stk else "NULL"
            compra_expr = None
            join_sql = ""
            wh_name_expr = "NULL"
            # Join a tabla Almacenes para nombre descriptivo
            if 'almacen' in map_stk:
                cands_wh = self.get_table_candidates(cursor, 'almacenes')
                tab_wh, map_wh = self.pick_best_table(cursor, cands_wh, self.COLUMN_MAP_ALMACENES, ['codigo'])
                if tab_wh and map_wh.get('nombre'):
                    join_sql += f" LEFT JOIN {tab_wh} W ON W.{map_wh['codigo']} = T.{map_stk['almacen']}"
                    if map_wh.get('empresa') and map_stk.get('empresa'):
                        join_sql += f" AND W.{map_wh['empresa']} = T.{map_stk['empresa']}"
                    wh_name_expr = f"W.{map_wh['nombre']}"
            cands_art = self.get_table_candidates(cursor, 'articulos')
            tab_art, map_art = self.pick_best_table(cursor, cands_art, self.COLUMN_MAP_ARTICULOS, ['articulo'])
            art_desc_expr = "NULL"
            if tab_art and 'articulo' in map_stk:
                join_sql += f" LEFT JOIN {tab_art} A ON A.{map_art['articulo']} = T.{map_stk['articulo']}"
                if map_art.get('empresa') and map_stk.get('empresa'):
                    join_sql += f" AND A.{map_art['empresa']} = T.{map_stk['empresa']}"
                if map_art.get('descripcion'):
                    art_desc_expr = f"A.{map_art['descripcion']}"
            if 'precio_compra' in map_stk:
                compra_expr = f"T.{map_stk['precio_compra']}"
            elif tab_art and map_art.get('precio_compra'):
                compra_expr = f"A.{map_art['precio_compra']}"
            else:
                compra_expr = "NULL"
            sel_sql = f"""
                SELECT 
                    T.{map_stk['periodo']} as periodo,
                    T.{map_stk['articulo']} as articulo,
                    {art_desc_expr} as articulo_desc,
                    {('T.' + map_stk['almacen']) if 'almacen' in map_stk else "''"} as almacen,
                    {wh_name_expr} as almacen_name,
                    {('T.' + map_stk['ubicacion']) if 'ubicacion' in map_stk else "''"} as ubicacion,
                    {('T.' + map_stk['tipologia']) if 'tipologia' in map_stk else "''"} as tipologia,
                    T.{map_stk['importe_saldo']} as importesaldo,
                    {units_expr} as unidadsaldo,
                    {medio_expr} as preciomedio,
                    {ultima_expr} as precioultimaentrada,
                    {compra_expr} as preciocompra
                FROM {tab_stk} T{join_sql}
                WHERE T.{map_stk['empresa']} IN ({placeholders_emp}) AND T.{map_stk['ejercicio']} = ?
            """
            cursor.execute(sel_sql, tuple(emp_candidates + [ejercicio]))
            CHUNK = self.copy_chunk_rows
            count_c = 0
            fp = compute_mssql_fingerprint()
            with transaction.atomic(using='analytics'):
                psy_cursor = connections['analytics'].connection.cursor()
                psy_cursor.execute("SET LOCAL synchronous_commit = OFF")
                while True:
                    rows = cursor.fetchmany(CHUNK)
                    if not rows:
                        break
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for r in rows:
                        periodo = int(r.periodo or 0)
                        articulo = str(r.articulo).strip() if r.articulo is not None else ''
                        articulo_desc = str(getattr(r, 'articulo_desc', '')).strip() if getattr(r, 'articulo_desc', None) is not None else ''
                        almacen = str(r.almacen).strip() if r.almacen is not None else ''
                        almacen_name = str(getattr(r, 'almacen_name', '')).strip() if getattr(r, 'almacen_name', None) is not None else ''
                        ubicacion = str(r.ubicacion).strip() if r.ubicacion is not None else ''
                        tipologia = str(r.tipologia).strip() if r.tipologia is not None else ''
                        importe = decimal.Decimal(r.importesaldo or 0)
                        unidadsaldo = decimal.Decimal(getattr(r, 'unidadsaldo', 0) or 0)
                        preciomedio = decimal.Decimal(getattr(r, 'preciomedio', 0) or 0)
                        precioultimaentrada = decimal.Decimal(getattr(r, 'precioultimaentrada', 0) or 0)
                        preciocompra = decimal.Decimal(getattr(r, 'preciocompra', 0) or 0)
                        writer.writerow([
                            empresa, ejercicio, periodo, articulo, articulo_desc, almacen, almacen_name, ubicacion, tipologia, str(importe),
                            str(unidadsaldo), str(preciomedio), str(precioultimaentrada), str(preciocompra), fp,
                            timezone.now().strftime("%Y-%m-%d %H:%M:%S"), timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])
                    buf.seek(0)
                    cols = "empresa, ejercicio, periodo, articulo, articulo_desc, almacen, almacen_name, ubicacion, tipologia, importesaldo, unidadsaldo, preciomedio, precioultimaentrada, preciocompra, source_fp, created_at, updated_at"
                    self._copy_csv(psy_cursor, f"COPY datia_acumulados_stocks ({cols}) FROM STDIN WITH (FORMAT CSV)", buf)
                    count_c += len(rows)
                    pct = 10 + int((count_c / total_rows) * 85)
                    yield send_progress("Importing", pct, f"Existencias: {count_c} / {total_rows}")
            yield send_progress("Done", 100, "Existencias sincronizadas")
        except Exception as e:
            yield send_progress("Error", 0, str(e))

    def sync_mssql_financial_generator(self, empresa: int, ejercicio: int, fast_bulk: bool = False):
        import decimal
        import traceback
        import json
        from datia.models.financial import DatiaPlanCuentas, DatiaAcumuladosConta, DatiaGrupos
        
        self.ensure_financial_core_tables()

        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        def normalize_empresa_candidates(val):
            s = str(val).strip()
            arr = [s]
            if s.isdigit():
                arr.append(s.zfill(2))
                arr.append(s.zfill(3))
                arr.append(str(int(s)))
            else:
                try:
                    arr.append(str(int(s)))
                except:
                    pass
            uniq = []
            for x in arr:
                if x not in uniq:
                    uniq.append(x)
            return uniq
        def infer_level(code):
            c = ''.join(ch for ch in str(code) if ch.isdigit())
            n = len(c)
            if n <= 1:
                return 1
            if n == 2:
                return 2
            if n == 3:
                return 3
            if n == 4:
                return 4
            if n <= 6:
                return 5
            return 6

        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            yield send_progress("Setup", 0, "Iniciando Sincronización Financiera...")

            cands_plan = self.get_table_candidates(cursor, 'plan_cuentas')
            cands_acum = self.get_table_candidates(cursor, 'acumulados')

            tab_plan, map_plan = self.pick_best_table(cursor, cands_plan, self.COLUMN_MAP_PLAN_CUENTAS, ['empresa', 'codigo'])
            tab_acum, map_acum = self.pick_best_table(cursor, cands_acum, self.COLUMN_MAP_ACUMULADOS, ['empresa', 'ejercicio', 'cuenta', 'periodo'])

            if not tab_plan or not tab_acum:
                yield send_progress("Skipped", 100, "No se encontraron tablas contables.")
                return

            yield send_progress("Setup", 10, f"Tablas Financieras: {tab_plan} y {tab_acum}")

            yield send_progress("Cleaning", 15, "Limpiando Plan de Cuentas...")
            
            cursor_local = connections['analytics'].cursor()
            
            cursor_local.execute("DELETE FROM datia_financial_plan WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])
            cursor_local.execute("DELETE FROM datia_financial_acumulados WHERE empresa = %s AND ejercicio = %s", [empresa, ejercicio])

            col_plan_code = f"T.{map_plan['codigo']}"
            col_plan_desc = f"T.{map_plan['descripcion']}" if 'descripcion' in map_plan else "'Sin Descripción'"
            col_plan_level = f"T.{map_plan['nivel']}" if 'nivel' in map_plan else "0"
            col_plan_group = f"T.{map_plan['grupo']}" if 'grupo' in map_plan else "LEFT(T." + map_plan['codigo'] + ", 1)"

            sel_plan = f'''
                SELECT 
                    {col_plan_code} as codigo,
                    {col_plan_desc} as descripcion,
                    {col_plan_level} as nivel,
                    {col_plan_group} as grupo
                FROM {tab_plan} T
                WHERE T.{map_plan['empresa']} = ?
            '''
            
            emp_candidates = normalize_empresa_candidates(empresa)
            placeholders = ','.join('?' for _ in emp_candidates)
            cursor.execute(f"SELECT COUNT(*) FROM {tab_plan} T WHERE T.{map_plan['empresa']} IN ({placeholders})", tuple(emp_candidates))
            total_plan = cursor.fetchone()[0] or 1

            yield send_progress("Importing", 20, f"Importando Plan Contable (0 / {total_plan})...")
            cursor.execute(sel_plan.replace(f"T.{map_plan['empresa']} = ?", f"T.{map_plan['empresa']} IN ({placeholders})"), tuple(emp_candidates))
            
            BATCH_SIZE = 5000
            plan_batch = []
            count_p = 0
            insert_base_plan = """
                INSERT INTO datia_financial_plan 
                (empresa, ejercicio, codigo, descripcion, nivel, grupo, es_ultimo_nivel, created_at)
                VALUES %s
            """
            template_plan = "(%s,%s,%s,%s,%s,%s,false,NOW())"

            from django.utils import timezone
            CHUNK = 50000
            with transaction.atomic(using='analytics'):
                pg_cur = connections['analytics'].cursor()
                try:
                    pg_cur.execute("SET LOCAL synchronous_commit = OFF")
                except Exception:
                    pass
                while True:
                    rows = cursor.fetchmany(CHUNK)
                    if not rows:
                        break
                    batch = []
                    for r in rows:
                        code_s = str(r.codigo).strip() if r.codigo is not None else ''
                        if not code_s:
                            continue
                        desc_s = str(r.descripcion).strip() if r.descripcion is not None else ''
                        lvl = int(r.nivel) if r.nivel else 0
                        if lvl < 1:
                            lvl = infer_level(code_s)
                        grp = str(r.grupo).strip()[:10] if r.grupo else (code_s[:1] if code_s else '')
                        batch.append((
                            int(empresa),
                            int(ejercicio),
                            code_s,
                            (desc_s if desc_s else 'Sin Descripción'),
                            int(lvl),
                            grp,
                        ))
                    if batch:
                        self._execute_values_bulk(pg_cur, insert_base_plan, batch, template_plan, page_size=2000)
                        count_p += len(batch)
                        pct_build = 20 + int((count_p / total_plan) * 20)
                        yield send_progress("Importing", pct_build, f"Plan Contable: {count_p} / {total_plan}")
            pct = 20 + int((count_p / total_plan) * 20)
            yield send_progress("Importing", pct, f"Plan Contable: {count_p} / {total_plan}")

            # TRY ACUMULADOS
            try:
                col_acum_cta = f"T.{map_acum['cuenta']}"
                col_acum_per = f"T.{map_acum['periodo']}"
                col_acum_debe = f"T.{map_acum['debe']}" if 'debe' in map_acum else "0"
                col_acum_haber = f"T.{map_acum['haber']}" if 'haber' in map_acum else "0"
            
                sel_acum = f'''
                    SELECT 
                        {col_acum_cta} as cuenta,
                        {col_acum_per} as periodo,
                        {col_acum_debe} as debe,
                        {col_acum_haber} as haber
                    FROM {tab_acum} T
                    WHERE T.{map_acum['empresa']} = ? AND T.{map_acum['ejercicio']} = ?
                      AND T.{map_acum['periodo']} BETWEEN 0 AND 12
                '''
                
                placeholders_ac = ','.join('?' for _ in emp_candidates)
                cursor.execute(f"SELECT COUNT(*) FROM {tab_acum} T WHERE T.{map_acum['empresa']} IN ({placeholders_ac}) AND T.{map_acum['ejercicio']} = ?", tuple(emp_candidates) + (ejercicio,))
                total_acum = cursor.fetchone()[0] or 1

                yield send_progress("Importing", 40, f"Importando Saldos (0 / {total_acum})...")
                cursor.execute(sel_acum.replace(f"T.{map_acum['empresa']} = ?", f"T.{map_acum['empresa']} IN ({placeholders_ac})"), tuple(emp_candidates) + (ejercicio,))
                
                acum_batch = []
                count_a = 0
                insert_base_acum = """
                    INSERT INTO datia_financial_acumulados 
                    (empresa, ejercicio, cuenta, periodo, debe, haber, saldo, debe_presupuesto, haber_presupuesto, created_at)
                    VALUES %s
                """
                template_acum = "(%s,%s,%s,%s,%s,%s,%s,0,0,NOW())"

                CHUNK2 = self.copy_chunk_rows
                with transaction.atomic(using='analytics'):
                    pg_cur2 = connections['analytics'].cursor()
                    try:
                        pg_cur2.execute("SET LOCAL synchronous_commit = OFF")
                    except Exception:
                        pass
                    while True:
                        rows = cursor.fetchmany(CHUNK2)
                        if not rows:
                            break
                        batch2 = []
                        built = 0
                        for r in rows:
                            acct = str(r.cuenta).strip() if r.cuenta is not None else ''
                            if not acct:
                                continue
                            debe = decimal.Decimal(r.debe or 0)
                            haber = decimal.Decimal(r.haber or 0)
                            saldo = debe - haber
                            batch2.append((
                                int(empresa),
                                int(ejercicio),
                                acct,
                                int(r.periodo or 0),
                                debe,
                                haber,
                                saldo,
                            ))
                            built += 1
                            if built % max(1, self.progress_emit_rows) == 0:
                                pct_build = 40 + int(((count_a + built) / total_acum) * 50)
                                yield send_progress("Importing", pct_build, f"Saldos: {count_a + built} / {total_acum}")
                        if batch2:
                            self._execute_values_bulk(pg_cur2, insert_base_acum, batch2, template_acum, page_size=2000)
                            count_a += len(batch2)
                            pct = 40 + int((count_a / total_acum) * 50)
                            yield send_progress("Importing", pct, f"Saldos: {count_a} / {total_acum}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Continue implementation...
                yield send_progress("Error", 0, f"Error en Acumulados: {e}")


            # --- SYNC GRUPOS (Optional) ---
            cands_grupos = self.get_table_candidates(cursor, 'grupos')
            tab_grupos, map_grupos = self.pick_best_table(cursor, cands_grupos, self.COLUMN_MAP_GRUPOS, ['empresa', 'codigo'])

            if tab_grupos:
                yield send_progress("Importing", 95, f"Importando Grupos desde {tab_grupos}... | TABLE: datia_financial_groups")
                col_grp_code = f"T.{map_grupos['codigo']}"
                col_grp_desc = f"T.{map_grupos['descripcion']}" if 'descripcion' in map_grupos else "NULL"
                emp_candidates_g = normalize_empresa_candidates(empresa)
                placeholders_g = ",".join("?" for _ in emp_candidates_g)
                cnt_grp = f'''
                    SELECT COUNT(*)
                    FROM {tab_grupos} T
                    WHERE T.{map_grupos['empresa']} IN ({placeholders_g})
                '''
                cursor.execute(cnt_grp, tuple(emp_candidates_g))
                total_g = int(cursor.fetchone()[0] or 0)
                sel_grp = f'''
                    SELECT {col_grp_code}, {col_grp_desc}
                    FROM {tab_grupos} T
                    WHERE T.{map_grupos['empresa']} IN ({placeholders_g})
                '''
                cursor.execute(sel_grp, tuple(emp_candidates_g))
                CH = 5000
                count_g = 0
                while True:
                    rows_grp = cursor.fetchmany(CH)
                    if not rows_grp:
                        break
                    for r in rows_grp:
                        code = str(r[0]).strip() if r[0] is not None else ''
                        desc = str(r[1]).strip() if len(r) > 1 and r[1] is not None else ''
                        DatiaGrupos.objects.update_or_create(
                            empresa=empresa,
                            codigo=code,
                            defaults={
                                'descripcion': desc,
                                'ejercicio': ejercicio
                            }
                        )
                        count_g += 1
                    pct_g = 95 + int((count_g / max(1, total_g)) * 3)
                    if pct_g > 98:
                        pct_g = 98
                    yield send_progress("Importing", pct_g, f"Grupos: {count_g} / {total_g} | TABLE: datia_financial_groups")
                yield send_progress("Importing", 98, f"Grupos Actualizados: {count_g} | TABLE: datia_financial_groups")

            yield send_progress("Done", 100, "Sincronización Financiera Completada")

        except Exception as e:
            traceback.print_exc()
            yield send_progress("Error", 0, f"Error Financiero: {str(e)}")
        finally:
            conn.close()

    def sync_mssql_cartera_generator(self, empresa, ejercicio):
        """
        Syncs CarteraEfectos (Bills) from MSSQL to DatiaCarteraEfectos.
        Strategy: Delete all for (empresa, ejercicio) and re-insert.
        """
        from datia.models.financial import DatiaCarteraEfectos
        from django.db import connection, transaction
        import decimal
        
        cursor_local = connection.cursor()
        
        def send_progress(status, pct, msg):
            return {'status': status, 'percentage': pct, 'message': msg}
        
        yield send_progress("Start", 0, "Conectando a MSSQL (Cartera)...")
        
        conn_mssql = self.get_connection()
        if not conn_mssql:
            yield send_progress("Error", 0, "No se pudo conectar a MSSQL")
            return

        try:
            cursor = conn_mssql.cursor()
            
            # Check if table exists (simple check)
            try:
                cursor.execute("SELECT TOP 1 * FROM CarteraEfectos")
            except:
                yield send_progress("Error", 0, "Tabla CarteraEfectos no encontrada en MSSQL")
                return

            # 1. Delete existing for this period
            yield send_progress("Cleaning", 10, "Limpiando datos antiguos...")
            DatiaCarteraEfectos.objects.filter(empresa=empresa, ejercicio=ejercicio).delete()

            # 2. Count Total
            cursor.execute("SELECT COUNT(*) FROM CarteraEfectos WHERE CodigoEmpresa=? AND Ejercicio=?", (empresa, ejercicio))
            total_recs = cursor.fetchone()[0] or 0
            if total_recs == 0:
                    yield send_progress("Info", 100, "No hay efectos para este ejercicio.")
                    return

            # 3. Select Data
            query = """
                SELECT 
                    CodigoClienteProveedor, FechaVencimiento, FechaFactura, 
                    ImporteEfecto, ImporteCobrado, 
                    ImportePendiente, Prevision,
                    StatusBorrado, StatusRemesado
                FROM CarteraEfectos
                WHERE CodigoEmpresa=? AND Ejercicio=?
            """
            cursor.execute(query, (empresa, ejercicio))
            
            batch = []
            count = 0
            BATCH_SIZE = 1000
            
            sql_insert = """
                INSERT INTO datia_financial_cartera
                (empresa, ejercicio, codigo_titular, fecha_vencimiento, fecha_emision, importe, importe_cobrado, estado, tipo_efecto, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """
            
            while True:
                rows = cursor.fetchmany(BATCH_SIZE)
                if not rows: break
                
                for r in rows:
                    pending = decimal.Decimal(r.ImportePendiente or 0)
                    if r.StatusBorrado == -1:
                        continue
                    if r.StatusRemesado == -1:
                        status = 'COBRADO'
                    elif pending > 0.01:
                        status = 'PENDIENTE'
                    else:
                        status = 'COBRADO'
                    
                    batch.append((
                        empresa, ejercicio,
                        str(r.CodigoClienteProveedor or '').strip(),
                        r.FechaVencimiento, 
                        r.FechaFactura,
                        decimal.Decimal(r.ImporteEfecto or 0),
                        decimal.Decimal(r.ImporteCobrado or 0),
                        status,
                        str(r.Prevision or 'C')[:1] 
                    ))
                
                cursor_local.executemany(sql_insert, batch)
                count += len(batch)
                batch = []
                
                pct = 10 + int((count / total_recs) * 90)
                yield send_progress("Importing", pct, f"Cartera: {count} / {total_recs}")

            yield send_progress("Done", 100, "Sincronización de Cartera finalizada.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield send_progress("Error", 0, f"Error Cartera: {e}")
        finally:
            conn_mssql.close()

    def sync_mssql_cartera_incremental_generator(self, empresa, ejercicio, days_back: int = 7):
        """
        Incremental sync for CarteraEfectos:
        - Uses checkpoint last_fecha for tipo='cartera'
        - Pulls changed rows where FechaVencimiento or FechaFactura >= cutoff
        - Delete+Insert per key tuple (empresa, ejercicio, codigo_titular, fecha_emision, fecha_vencimiento, importe)
        """
        import decimal, json
        from datetime import datetime, timedelta
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        try:
            self.ensure_checkpoints_table()
        except:
            pass
        cp = self.get_checkpoint(empresa, ejercicio, "cartera")
        cutoff = None
        if cp and cp.get('last_fecha'):
            cutoff = cp['last_fecha']
        else:
            cutoff = datetime.now() - timedelta(days=max(1, int(days_back)))
        conn_mssql = self.get_connection()
        if not conn_mssql:
            yield send_progress("Error", 0, "No se pudo conectar a MSSQL")
            return
        try:
            cur = conn_mssql.cursor()
            try:
                cur.execute("SELECT TOP 1 * FROM CarteraEfectos")
            except:
                yield send_progress("Error", 0, "Tabla CarteraEfectos no encontrada en MSSQL")
                return
            q = """
                SELECT 
                    CodigoClienteProveedor, FechaVencimiento, FechaFactura, 
                    ImporteEfecto, ImporteCobrado, 
                    ImportePendiente, Prevision,
                    StatusBorrado, StatusRemesado
                FROM CarteraEfectos
                WHERE CodigoEmpresa=? AND Ejercicio=? AND (FechaVencimiento >= ? OR FechaFactura >= ?)
            """
            cur.execute(q, (empresa, ejercicio, cutoff, cutoff))
            rows = cur.fetchall()
            total = len(rows) or 0
            yield send_progress("Importing", 10, f"Cambios Cartera: {total}")
            if total == 0:
                yield send_progress("Done", 100, "Incremental Cartera sin cambios.")
                return
            cursor_local = connections['analytics'].cursor()
            processed = 0
            max_fecha = cutoff
            for r in rows:
                codigo = str(r.CodigoClienteProveedor or '').strip()
                fv = r.FechaVencimiento
                ff = r.FechaFactura
                importe = decimal.Decimal(r.ImporteEfecto or 0)
                cobrado = decimal.Decimal(r.ImporteCobrado or 0)
                pending = decimal.Decimal(r.ImportePendiente or 0)
                if r.StatusBorrado == -1:
                    cursor_local.execute("""
                        DELETE FROM datia_financial_cartera 
                        WHERE empresa=%s AND ejercicio=%s AND codigo_titular=%s AND fecha_emision=%s AND fecha_vencimiento=%s AND importe=%s
                    """, [empresa, ejercicio, codigo, ff, fv, importe])
                    processed += 1
                    pct = 10 + int((processed / max(1, total)) * 80)
                    yield send_progress("Importing", pct, f"Cartera: {processed} / {total}")
                    continue
                if r.StatusRemesado == -1:
                    status = 'COBRADO'
                elif pending > 0.01:
                    status = 'PENDIENTE'
                else:
                    status = 'COBRADO'
                # Delete existing key tuple
                cursor_local.execute("""
                    DELETE FROM datia_financial_cartera 
                    WHERE empresa=%s AND ejercicio=%s AND codigo_titular=%s AND fecha_emision=%s AND fecha_vencimiento=%s AND importe=%s
                """, [empresa, ejercicio, codigo, ff, fv, importe])
                # Insert updated row
                cursor_local.execute("""
                    INSERT INTO datia_financial_cartera
                    (empresa, ejercicio, codigo_titular, fecha_vencimiento, fecha_emision, importe, importe_cobrado, estado, tipo_efecto, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                """, [empresa, ejercicio, codigo, fv, ff, importe, cobrado, status, str(r.Prevision or 'C')[:1]])
                processed += 1
                dt = ff if (ff and (not fv or ff >= fv)) else fv
                if dt and (not max_fecha or dt > max_fecha):
                    max_fecha = dt
                pct = 10 + int((processed / max(1, total)) * 80)
                yield send_progress("Importing", pct, f"Cartera: {processed} / {total}")
            # Update checkpoint
            if max_fecha:
                self.set_checkpoint(empresa, ejercicio, "cartera", max_fecha)
            yield send_progress("Done", 100, "Incremental Cartera Completado")
        except Exception as e:
            yield send_progress("Error", 0, f"Error Incremental Cartera: {e}")
        finally:
            conn_mssql.close()

    def sync_mssql_stocks_incremental_generator(self, empresa: int, ejercicio: int, periods_back: int = 2):
        """
        Incremental sync for Stocks:
        - Refresh only last N periodos (default 2) for given ejercicio
        - Delete+reinsert for those periodos
        """
        import json, decimal, io, csv
        from datia.services.cache_service import compute_mssql_fingerprint
        def send_progress(step, percent, msg=""):
            return f"data: {json.dumps({'step': step, 'percent': percent, 'message': msg})}\\n\\n"
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield send_progress("Setup", 0, "Iniciando Sincronización Incremental de Existencias...")
            candidates = self.get_table_candidates(cursor, 'stocks')
            tab_stk, map_stk = self.pick_best_table(cursor, candidates, self.COLUMN_MAP_STOCKS, ['empresa', 'ejercicio', 'periodo', 'articulo', 'importe_saldo'])
            if not tab_stk:
                yield send_progress("Skipped", 100, "No se encontró tabla de existencias.")
                return
            yield send_progress("Setup", 5, f"Tabla seleccionada: {tab_stk}")
            # Compute periods to refresh: last N periods within 1..12
            try:
                pb = max(1, int(periods_back))
            except:
                pb = 2
            start_p = max(1, 12 - pb + 1)
            target_periods = list(range(start_p, 13))
            placeholders_periods = ",".join(str(p) for p in target_periods)
            # Prepare local table and delete only target periods
            cursor_local = connections['analytics'].cursor()
            # Ensure source_fp column exists for fingerprinting
            cursor_local.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'datia_acumulados_stocks'")
            existing_cols = [r[0] for r in cursor_local.fetchall()]
            if 'source_fp' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS source_fp VARCHAR(16)")
            if 'articulo_desc' not in existing_cols:
                cursor_local.execute("ALTER TABLE datia_acumulados_stocks ADD COLUMN IF NOT EXISTS articulo_desc VARCHAR(256)")
            cursor_local.execute("""
                DELETE FROM datia_acumulados_stocks
                WHERE empresa = %s AND ejercicio = %s AND periodo IN (%s)
            """ % ("%s", "%s", placeholders_periods), [empresa, ejercicio])
            yield send_progress("Cleaning", 10, f"Eliminados periodos {start_p}..12")
            # Build joins and select limited periods
            units_expr = f"T.{map_stk['unidad_saldo']}" if 'unidad_saldo' in map_stk else "NULL"
            medio_expr = f"T.{map_stk['precio_medio']}" if 'precio_medio' in map_stk else "NULL"
            ultima_expr = f"T.{map_stk['precio_ultima']}" if 'precio_ultima' in map_stk else "NULL"
            compra_expr = None
            join_sql = ""
            wh_name_expr = "NULL"
            if 'almacen' in map_stk:
                cands_wh = self.get_table_candidates(cursor, 'almacenes')
                tab_wh, map_wh = self.pick_best_table(cursor, cands_wh, self.COLUMN_MAP_ALMACENES, ['codigo'])
                if tab_wh and map_wh.get('nombre'):
                    join_sql += f" LEFT JOIN {tab_wh} W ON W.{map_wh['codigo']} = T.{map_stk['almacen']}"
                    if map_wh.get('empresa') and map_stk.get('empresa'):
                        join_sql += f" AND W.{map_wh['empresa']} = T.{map_stk['empresa']}"
                    wh_name_expr = f"W.{map_wh['nombre']}"
            cands_art = self.get_table_candidates(cursor, 'articulos')
            tab_art, map_art = self.pick_best_table(cursor, cands_art, self.COLUMN_MAP_ARTICULOS, ['articulo'])
            if 'precio_compra' in map_stk:
                compra_expr = f"T.{map_stk['precio_compra']}"
            elif tab_art and map_art.get('precio_compra') and 'articulo' in map_stk:
                join_sql += f" LEFT JOIN {tab_art} A ON A.{map_art['articulo']} = T.{map_stk['articulo']}"
                if map_art.get('empresa') and map_stk.get('empresa'):
                    join_sql += f" AND A.{map_art['empresa']} = T.{map_stk['empresa']}"
                compra_expr = f"A.{map_art['precio_compra']}"
            else:
                compra_expr = "NULL"
            emp_candidates = self._empresa_candidates(empresa)
            placeholders_emp = ",".join("?" for _ in emp_candidates)
            art_desc_expr = "NULL"
            if tab_art and map_art.get('descripcion'):
                art_desc_expr = f"A.{map_art['descripcion']}"
            sel_sql = f"""
                SELECT 
                    T.{map_stk['periodo']} as periodo,
                    T.{map_stk['articulo']} as articulo,
                    {art_desc_expr} as articulo_desc,
                    {('T.' + map_stk['almacen']) if 'almacen' in map_stk else "''"} as almacen,
                    {wh_name_expr} as almacen_name,
                    {('T.' + map_stk['ubicacion']) if 'ubicacion' in map_stk else "''"} as ubicacion,
                    {('T.' + map_stk['tipologia']) if 'tipologia' in map_stk else "''"} as tipologia,
                    T.{map_stk['importe_saldo']} as importesaldo,
                    {units_expr} as unidadsaldo,
                    {medio_expr} as preciomedio,
                    {ultima_expr} as precioultimaentrada,
                    {compra_expr} as preciocompra
                FROM {tab_stk} T{join_sql}
                WHERE T.{map_stk['empresa']} IN ({placeholders_emp}) AND T.{map_stk['ejercicio']} = ? AND T.{map_stk['periodo']} IN ({placeholders_periods})
            """
            cursor.execute(sel_sql, tuple(emp_candidates + [ejercicio]))
            CHUNK = self.copy_chunk_rows
            count_c = 0
            fp = compute_mssql_fingerprint()
            with transaction.atomic(using='analytics'):
                psy_cursor = connections['analytics'].connection.cursor()
                psy_cursor.execute("SET LOCAL synchronous_commit = OFF")
                while True:
                    rows = cursor.fetchmany(CHUNK)
                    if not rows:
                        break
                    buf = io.StringIO()
                    writer = csv.writer(buf)
                    for r in rows:
                        periodo = int(r.periodo or 0)
                        articulo = str(r.articulo).strip() if r.articulo is not None else ''
                        articulo_desc = str(getattr(r, 'articulo_desc', '')).strip() if getattr(r, 'articulo_desc', None) is not None else ''
                        almacen = str(r.almacen).strip() if r.almacen is not None else ''
                        almacen_name = str(getattr(r, 'almacen_name', '')).strip() if getattr(r, 'almacen_name', None) is not None else ''
                        ubicacion = str(r.ubicacion).strip() if r.ubicacion is not None else ''
                        tipologia = str(r.tipologia).strip() if r.tipologia is not None else ''
                        importe = decimal.Decimal(r.importesaldo or 0)
                        unidadsaldo = decimal.Decimal(getattr(r, 'unidadsaldo', 0) or 0)
                        preciomedio = decimal.Decimal(getattr(r, 'preciomedio', 0) or 0)
                        precioultimaentrada = decimal.Decimal(getattr(r, 'precioultimaentrada', 0) or 0)
                        preciocompra = decimal.Decimal(getattr(r, 'preciocompra', 0) or 0)
                        writer.writerow([
                            empresa, ejercicio, periodo, articulo, articulo_desc, almacen, almacen_name, ubicacion, tipologia, str(importe),
                            str(unidadsaldo), str(preciomedio), str(precioultimaentrada), str(preciocompra), fp,
                            timezone.now().strftime("%Y-%m-%d %H:%M:%S"), timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                        ])
                    buf.seek(0)
                    cols = "empresa, ejercicio, periodo, articulo, articulo_desc, almacen, almacen_name, ubicacion, tipologia, importesaldo, unidadsaldo, preciomedio, precioultimaentrada, preciocompra, source_fp, created_at, updated_at"
                    self._copy_csv(psy_cursor, f"COPY datia_acumulados_stocks ({cols}) FROM STDIN WITH (FORMAT CSV)", buf)
                    count_c += len(rows)
                    pct = 20 + int((count_c / max(1, len(target_periods))) * 75)
                    yield send_progress("Importing", pct, f"Existencias (periodos {start_p}..12): {count_c}")
            yield send_progress("Done", 100, "Incremental Existencias Completado")
        except Exception as e:
            yield send_progress("Error", 0, str(e))
        finally:
            conn.close()
    def verify_acumulados_mssql(self, empresa: int, ejercicio: int) -> dict:
        import json
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cands = self.get_table_candidates(cursor, 'acumulados')
            tab_acum, map_acum = self.pick_best_table(cursor, cands, self.COLUMN_MAP_ACUMULADOS, ['empresa', 'ejercicio', 'cuenta', 'periodo'])
            if not tab_acum:
                return {'status': 'error', 'message': 'No se encontró tabla Acumulados'}
            def normalize_empresa_candidates(val):
                s = str(val).strip()
                arr = [s]
                if s.isdigit():
                    arr.append(s.zfill(2)); arr.append(s.zfill(3)); arr.append(str(int(s)))
                else:
                    try: arr.append(str(int(s)))
                    except: pass
                uniq = []
                for x in arr:
                    if x not in uniq: uniq.append(x)
                return uniq
            emp_candidates = normalize_empresa_candidates(empresa)
            placeholders = ','.join('?' for _ in emp_candidates)
            q_dist = f"""
                SELECT T.{map_acum['periodo']} as periodo, COUNT(*) as cnt
                FROM {tab_acum} T
                WHERE T.{map_acum['empresa']} IN ({placeholders})
                  AND T.{map_acum['ejercicio']} = ?
                  AND T.{map_acum['periodo']} BETWEEN 0 AND 12
                GROUP BY T.{map_acum['periodo']}
                ORDER BY T.{map_acum['periodo']}
            """
            cursor.execute(q_dist, tuple(emp_candidates) + (ejercicio,))
            dist = [{'periodo': int(r[0] or 0), 'count': int(r[1] or 0)} for r in cursor.fetchall()]
            q_nulls = f"""
                SELECT COUNT(*)
                FROM {tab_acum} T
                WHERE (T.{map_acum['empresa']} IS NULL OR T.{map_acum['ejercicio']} IS NULL
                       OR T.{map_acum['cuenta']} IS NULL OR T.{map_acum['periodo']} IS NULL)
                  AND T.{map_acum['empresa']} IN ({placeholders}) AND T.{map_acum['ejercicio']} = ?
            """
            cursor.execute(q_nulls, tuple(emp_candidates) + (ejercicio,))
            nulls = int(cursor.fetchone()[0] or 0)
            q_dups = f"""
                SELECT COUNT(*) FROM (
                    SELECT T.{map_acum['empresa']}, T.{map_acum['ejercicio']}, T.{map_acum['cuenta']}, T.{map_acum['periodo']}, COUNT(*) AS c
                    FROM {tab_acum} T
                    WHERE T.{map_acum['empresa']} IN ({placeholders}) AND T.{map_acum['ejercicio']} = ?
                    GROUP BY T.{map_acum['empresa']}, T.{map_acum['ejercicio']}, T.{map_acum['cuenta']}, T.{map_acum['periodo']}
                    HAVING COUNT(*) > 1
                ) X
            """
            cursor.execute(q_dups, tuple(emp_candidates) + (ejercicio,))
            dups = int(cursor.fetchone()[0] or 0)
            saldo_col = map_acum.get('saldo')
            incoher = 0
            if saldo_col:
                q_inco = f"""
                    SELECT COUNT(*)
                    FROM {tab_acum} T
                    WHERE T.{map_acum['empresa']} IN ({placeholders}) AND T.{map_acum['ejercicio']} = ?
                      AND T.{map_acum['periodo']} BETWEEN 0 AND 12
                      AND ABS((COALESCE(T.{map_acum.get('debe','0')},0) - COALESCE(T.{map_acum.get('haber','0')},0)) - COALESCE(T.{saldo_col},0)) > 0.01
                """
                cursor.execute(q_inco, tuple(emp_candidates) + (ejercicio,))
                incoher = int(cursor.fetchone()[0] or 0)
            return {'status': 'ok', 'distribution': dist, 'null_keys': nulls, 'duplicates': dups, 'saldo_incoherence': incoher, 'table': tab_acum}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
        finally:
            conn.close()

    def clear_financial_acumulados(self) -> dict:
        from django.db import connections
        try:
            cursor_local = connections['analytics'].cursor()
            cursor_local.execute("TRUNCATE TABLE datia_financial_acumulados RESTART IDENTITY CASCADE;")
            return {'status': 'ok'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def add_period_check_constraint(self) -> dict:
        from django.db import connections
        try:
            cursor_local = connections['analytics'].cursor()
            cursor_local.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints
                        WHERE constraint_name = 'chk_periodo_0_12'
                          AND table_name = 'datia_financial_acumulados'
                    ) THEN
                        ALTER TABLE datia_financial_acumulados
                        ADD CONSTRAINT chk_periodo_0_12 CHECK (periodo >= 0 AND periodo <= 12);
                    END IF;
                END $$;
            """)
            return {'status': 'ok'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def regenerate_financial_acumulados(self, empresa: int, ejercicio: int) -> dict:
        try:
            for _ in self.sync_mssql_financial_generator(empresa, ejercicio):
                pass
            return {'status': 'ok'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def rebuild_financial_acumulados(self, empresa: int, ejercicio: int) -> dict:
        res_clear = self.clear_financial_acumulados()
        if res_clear.get('status') != 'ok':
            return res_clear
        res_chk = self.add_period_check_constraint()
        if res_chk.get('status') != 'ok':
            return res_chk
        return self.regenerate_financial_acumulados(empresa, ejercicio)
