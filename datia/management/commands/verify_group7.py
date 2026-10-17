from django.core.management.base import BaseCommand
from django.db import connections
from django.db.models import Sum
from datia.models.financial import DatiaAcumuladosConta
from datia.services.etl_service import ETLService
from decimal import Decimal

class Command(BaseCommand):
    help = "Verifica el total del Grupo 7 (1–12) comparando MSSQL AcumuladosConta y Postgres."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, default=None)
        parser.add_argument('--ejercicio', type=int, default=None)

    def handle(self, *args, **options):
        empresa_opt = options.get('empresa')
        ejercicio_opt = options.get('ejercicio')
        empresa, ejercicio = self._resolve_context(empresa_opt, ejercicio_opt)
        pg_total = self._pg_sum(empresa, ejercicio)
        mssql_total = self._mssql_sum(empresa, ejercicio)
        diff = float(pg_total) - float(mssql_total)
        self.stdout.write(f"Empresa: {empresa}  Ejercicio: {ejercicio}")
        self.stdout.write(f"Postgres Grupo7 (1–12): {pg_total:,.2f}")
        self.stdout.write(f"MSSQL    Grupo7 (1–12): {mssql_total:,.2f}")
        self.stdout.write(f"Diferencia (PG - MSSQL): {diff:,.2f}")

    def _resolve_context(self, empresa_opt, ejercicio_opt):
        if empresa_opt and ejercicio_opt:
            return empresa_opt, int(ejercicio_opt)
        qs = DatiaAcumuladosConta.objects.all()
        if empresa_opt:
            qs = qs.filter(empresa=empresa_opt)
        if ejercicio_opt:
            qs = qs.filter(ejercicio=int(ejercicio_opt))
        row = qs.order_by('-ejercicio').values('empresa', 'ejercicio').first()
        if not row:
            raise RuntimeError("No hay datos en datia_financial_acumulados para resolver empresa/ejercicio.")
        return str(row['empresa']), int(row['ejercicio'])

    def _pg_sum(self, empresa, ejercicio):
        t = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio,
            periodo__gte=1, periodo__lte=12,
            cuenta__startswith='7'
        ).aggregate(t=Sum('saldo'))['t'] or 0
        return float(t)

    def _mssql_sum(self, empresa, ejercicio):
        etl = ETLService()
        conn = etl.get_connection()
        cur = conn.cursor()
        try:
            cands = etl.get_table_candidates(cur, 'acumulados')
            tab, colmap = etl.pick_best_table(cur, cands, etl.COLUMN_MAP_ACUMULADOS, ['empresa', 'ejercicio', 'cuenta', 'periodo'])
            if not tab:
                return 0.0
            emp_candidates = self._normalize_empresa_candidates(empresa)
            ph_emp = ','.join(['?'] * len(emp_candidates))
            sql = f"""
                SELECT T.{colmap['cuenta']}, T.{colmap['periodo']}, T.{colmap['debe']}, T.{colmap['haber']}
                FROM {tab} T
                WHERE T.{colmap['empresa']} IN ({ph_emp})
                  AND T.{colmap['ejercicio']} = ?
                  AND T.{colmap['periodo']} BETWEEN 1 AND 12
            """
            params = tuple(emp_candidates) + (ejercicio,)
            cur.execute(sql, params)
            total = Decimal('0')
            for r in cur.fetchall():
                acct = str(r[0]).strip() if r[0] is not None else ''
                if not acct.startswith('7'):
                    continue
                debe = Decimal(str(r[2] or 0))
                haber = Decimal(str(r[3] or 0))
                total += (debe - haber)
            return float(total)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _normalize_empresa_candidates(self, val):
        s = str(val).strip()
        arr = [s]
        if s.isdigit():
            arr.append(s.zfill(2))
            arr.append(s.zfill(3))
            arr.append(str(int(s)))
        else:
            try:
                arr.append(str(int(s)))
            except Exception:
                pass
        uniq = []
        for x in arr:
            if x not in uniq:
                uniq.append(x)
        return uniq
