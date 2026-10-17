from typing import Dict, Any, List
from django.db.models import Sum, Q
from django.db.utils import ProgrammingError, OperationalError
from datetime import date, timedelta

from datia.models.financial import DatiaAcumuladosConta
from datia.models.banking import (
    BankingBank, BankingAccount, BankingInstrument, BankingInstrumentAccountMap,
    BankingAmortization
)


class BankingService:
    """
    Reglas de negocio para el Pool Bancario:
    - Agregación de límite/dispuesto/disponible por instrumento, banco y tipo.
    - Medición de concentración por banco y por producto.
    - Cronograma de vencimientos a partir de plan de amortización.
    """

    def _dispuesto_por_prefixes(self, empresa: int, ejercicio: int, prefixes: List[str], until_month: int | None = None) -> float:
        if not prefixes:
            return 0.0
        q = Q()
        for p in prefixes:
            p = (p or '').strip()
            if not p:
                continue
            q |= Q(cuenta__startswith=p)
        if not q:
            return 0.0
        max_month = 12
        if isinstance(until_month, int) and 1 <= until_month <= 12:
            max_month = until_month
        rows = DatiaAcumuladosConta.objects.filter(
            empresa=empresa, ejercicio=ejercicio, periodo__lte=max_month
        ).filter(q).aggregate(total=Sum('saldo'))
        total = float(rows.get('total') or 0.0)
        return abs(total)

    def _instrument_dispuesto(self, empresa: int, ejercicio: int, instrument_id: int, until_month: int | None = None) -> float:
        maps = list(BankingInstrumentAccountMap.objects.filter(
            empresa=empresa, instrument_id=instrument_id
        ).values_list('cuenta_prefix', flat=True))
        return self._dispuesto_por_prefixes(empresa, ejercicio, maps, until_month)

    def get_summary(self, empresa: int, ejercicio: int, until_month: int | None = None) -> Dict[str, Any]:
        try:
            instruments = list(BankingInstrument.objects.filter(empresa=empresa, estado__in=['activo', 'pausado']))
        except (ProgrammingError, OperationalError):
            return {
                'empresa': empresa,
                'ejercicio': ejercicio,
                'items': [],
                'por_banco': [],
                'por_tipo': [],
                'totales': {
                    'limite': 0.0,
                    'dispuesto': 0.0,
                    'disponible': 0.0,
                    'utilizacion_pct': 0.0
                },
                'status': 'no_data'
            }
        banks = {}
        tipos = {}
        items = []
        total_limite = 0.0
        total_dispuesto = 0.0

        for inst in instruments:
            limite = float(inst.limite or 0.0)
            dispuesto = self._instrument_dispuesto(empresa, ejercicio, inst.id, until_month)
            disponible = max(limite - dispuesto, 0.0)
            total_limite += limite
            total_dispuesto += dispuesto

            items.append({
                'instrument_id': inst.id,
                'bank_id': inst.bank_id,
                'bank': inst.bank.nombre if inst.bank_id else '',
                'tipo': inst.tipo,
                'producto': inst.producto or '',
                'limite': round(limite, 2),
                'dispuesto': round(dispuesto, 2),
                'disponible': round(disponible, 2),
                'estado': inst.estado,
            })

            bkey = inst.bank_id
            tkey = inst.tipo
            if bkey not in banks:
                banks[bkey] = {'bank_id': bkey, 'bank': inst.bank.nombre if inst.bank_id else '', 'limite': 0.0, 'dispuesto': 0.0}
            if tkey not in tipos:
                tipos[tkey] = {'tipo': tkey, 'limite': 0.0, 'dispuesto': 0.0}
            banks[bkey]['limite'] += limite
            banks[bkey]['dispuesto'] += dispuesto
            tipos[tkey]['limite'] += limite
            tipos[tkey]['dispuesto'] += dispuesto

        total_disponible = max(total_limite - total_dispuesto, 0.0)
        for b in banks.values():
            b['disponible'] = max(b['limite'] - b['dispuesto'], 0.0)
            b['utilizacion_pct'] = round((b['dispuesto'] / b['limite'] * 100.0), 2) if b['limite'] > 0 else 0.0
        for t in tipos.values():
            t['disponible'] = max(t['limite'] - t['dispuesto'], 0.0)
            t['utilizacion_pct'] = round((t['dispuesto'] / t['limite'] * 100.0), 2) if t['limite'] > 0 else 0.0

        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'items': items,
            'por_banco': list(banks.values()),
            'por_tipo': list(tipos.values()),
            'totales': {
                'limite': round(total_limite, 2),
                'dispuesto': round(total_dispuesto, 2),
                'disponible': round(total_disponible, 2),
                'utilizacion_pct': round((total_dispuesto / total_limite * 100.0), 2) if total_limite > 0 else 0.0
            }
        }

    def get_concentration(self, empresa: int, ejercicio: int, until_month: int | None = None) -> Dict[str, Any]:
        s = self.get_summary(empresa, ejercicio, until_month)
        banks = sorted(s.get('por_banco', []), key=lambda x: x.get('limite', 0.0), reverse=True)
        top1 = banks[0]['limite'] if banks else 0.0
        top3 = sum(b['limite'] for b in banks[:3]) if banks else 0.0
        total = s.get('totales', {}).get('limite', 0.0)
        return {
            'empresa': empresa,
            'ejercicio': ejercicio,
            'banks': banks,
            'concentration': {
                'top1_pct': round((top1 / total * 100.0), 2) if total > 0 else 0.0,
                'top3_pct': round((top3 / total * 100.0), 2) if total > 0 else 0.0,
            }
        }

    def get_maturities(self, empresa: int, horizon: int = 12) -> Dict[str, Any]:
        today = date.today()
        last_date = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
        # Horizon in months
        horizon_end = last_date
        for _ in range(max(0, horizon - 1)):
            # move one month forward
            horizon_end = (horizon_end.replace(day=28) + timedelta(days=4)).replace(day=1)

        try:
            qs_values = list(BankingAmortization.objects.filter(
                empresa=empresa, fecha_cuota__gte=today, fecha_cuota__lt=horizon_end
            ).values('fecha_cuota', 'principal', 'interes', 'cuota', 'instrument_id'))
        except (ProgrammingError, OperationalError):
            return {
                'empresa': empresa,
                'series': [],
                'detalles': [],
                'status': 'no_data'
            }
        buckets: Dict[str, Dict[str, float]] = {}
        details: List[Dict[str, Any]] = []
        for row in qs_values:
            ym = row['fecha_cuota'].strftime('%Y-%m')
            if ym not in buckets:
                buckets[ym] = {'principal': 0.0, 'interes': 0.0, 'cuota': 0.0}
            buckets[ym]['principal'] += float(row.get('principal') or 0.0)
            buckets[ym]['interes'] += float(row.get('interes') or 0.0)
            buckets[ym]['cuota'] += float(row.get('cuota') or 0.0)
            details.append({
                'fecha': row['fecha_cuota'].isoformat(),
                'instrument_id': row['instrument_id'],
                'principal': float(row.get('principal') or 0.0),
                'interes': float(row.get('interes') or 0.0),
                'cuota': float(row.get('cuota') or 0.0),
            })
        series = [{'periodo': k, **{kk: round(vv, 2) for kk, vv in v.items()}} for k, v in sorted(buckets.items())]
        return {
            'empresa': empresa,
            'series': series,
            'detalles': details,
        }

    # --- CRUD helpers ---
    def create_bank(self, empresa: int, data: Dict[str, Any]) -> BankingBank:
        return BankingBank.objects.create(
            empresa=empresa,
            nombre=data.get('nombre', '').strip(),
            swift=data.get('swift'),
            rating=data.get('rating'),
            contacto=data.get('contacto') or {},
            activo=bool(data.get('activo', True)),
        )

    def update_bank(self, bank_id: int, data: Dict[str, Any]) -> BankingBank:
        bank = BankingBank.objects.get(id=bank_id)
        for f in ['nombre', 'swift', 'rating', 'contacto', 'activo']:
            if f in data:
                setattr(bank, f, data[f])
        bank.save()
        return bank

    def delete_bank(self, bank_id: int) -> None:
        BankingBank.objects.filter(id=bank_id).delete()
