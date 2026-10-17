from django.core.management.base import BaseCommand
from datia.services.financial_service import FinancialService
from datia.models.financial import DatiaAcumuladosConta

class Command(BaseCommand):
    help = "Verifica la clasificación del P&L por masas (prefijos) para empresa/ejercicio/level."

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=str, default=None)
        parser.add_argument('--ejercicio', type=int, default=None)
        parser.add_argument('--level', type=int, default=2)

    def handle(self, *args, **options):
        empresa = options.get('empresa')
        ejercicio = options.get('ejercicio')
        level = int(options.get('level') or 2)
        if not empresa or not ejercicio:
            row = DatiaAcumuladosConta.objects.order_by('-ejercicio').values('empresa', 'ejercicio').first()
            if not empresa and row:
                empresa = str(row['empresa'])
            if not ejercicio and row:
                ejercicio = int(row['ejercicio'])
        if not empresa or not ejercicio:
            self.stdout.write(self.style.ERROR("No hay datos para resolver empresa/ejercicio"))
            return
        service = FinancialService()
        data = service.get_pl_report(empresa=empresa, ejercicio=ejercicio, level=level)
        rows = data.get('rows') or []
        headers = [r for r in rows if r.get('is_header')]
        lines = [r for r in rows if not r.get('is_header')]
        self.stdout.write(f"Empresa: {empresa}  Ejercicio: {ejercicio}  Level: {level}")
        for h in headers:
            self.stdout.write(f"[{h['descripcion']}] valor={h['valor']:.2f} presupuesto={h['presupuesto']:.2f} ingreso={h['isIngreso']}")
            # Print children codes under this header (approx by level proximity)
            # Not perfect: children appear immediately after header in list
            # We'll list subsequent non-header rows until next header
            idx = rows.index(h)
            j = idx + 1
            while j < len(rows) and not rows[j].get('is_header'):
                r = rows[j]
                self.stdout.write(f"  - {r['cuenta']} {r['descripcion']} val={r['valor']:.2f} bud={r['presupuesto']:.2f}")
                j += 1
        self.stdout.write("Totales:")
        self.stdout.write(f"  Ingresos: {data.get('total_ingresos'):.2f}  Gastos: {data.get('total_gastos'):.2f}  Resultado: {data.get('resultado_explotacion'):.2f}")
