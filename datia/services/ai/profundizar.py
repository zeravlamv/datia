"""Detalle de una respuesta ya mostrada. No repite la misma tabla."""
import logging
import re
from datetime import date, datetime

from django.db import connections

from datia.services.ai.open_question import OpenQuestion, _fold

logger = logging.getLogger('query_builder')

_MESES = (
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
)
_TOPE_DETALLE = 40


class Profundizar:
    @staticmethod
    def responder(question, empresa, ejercicio):
        try:
            emp = int(empresa)
            year = int(ejercicio)
        except (TypeError, ValueError):
            return Profundizar._texto('No puedo detallar esta consulta sin empresa y ejercicio.')
        years = re.findall(r'\b(20\d{2})\b', question or '')
        if years:
            year = int(years[0])
        folded = _fold(question)
        sentido = OpenQuestion.clasificar_deuda(folded)
        if sentido:
            return Profundizar._deuda(emp, year, sentido)
        if re.search(r'\b(kilo|kilos|litro|litros|unidad|unidades|stock|existencia|inventario)\b', folded):
            return Profundizar._texto(
                'No hay un desglose más fino guardado para cantidades o stock. '
                'La respuesta de arriba es el dato disponible.'
            )
        if re.search(r'\b(compra|compras|proveedor|proveedores)\b', folded) and not re.search(
            r'\b(venta|ventas|cliente|clientes)\b', folded
        ):
            return Profundizar._meses(emp, year, compra=True)
        if re.search(
            r'\b(venta|ventas|cliente|clientes|margen|producto|productos|articulo|articulos|'
            r'ranking|mejor|mejores|top|vendid)\b',
            folded,
        ):
            return Profundizar._meses(emp, year, compra=False)
        return Profundizar._comparar_ejercicio(emp, year)

    @staticmethod
    def _deuda(empresa, year, sentido):
        tipo = 'P' if sentido == 'P' else 'C'
        titulo = 'pago' if tipo == 'P' else 'cobro'
        sujeto = 'proveedores' if tipo == 'P' else 'clientes'
        try:
            filas = Profundizar._leer_vencido(empresa, year, tipo)
        except Exception:
            logger.exception('Profundizar: no se pudo detallar la cartera')
            return Profundizar._texto(f'No he podido detallar la cartera de {year}.')
        if not filas:
            return Profundizar._texto(f'En {year} no hay efectos pendientes de {titulo} que detallar.')
        vencido = sum(fila['vencido'] for fila in filas)
        por_vencer = sum(fila['por_vencer'] for fila in filas)
        visibles = filas[:_TOPE_DETALLE]
        texto = (
            f"A fecha de hoy, de lo que los {sujeto} tienen pendiente en {year}, "
            f"{Profundizar._eur(vencido)} está vencido y {Profundizar._eur(por_vencer)} está por vencer. "
            f"Se listan {len(visibles)} de {len(filas)} cuentas, con el vencimiento más antiguo de cada una."
        )
        return {
            'type': 'report',
            'key': 'detalle_deuda_proveedores' if tipo == 'P' else 'detalle_deuda_clientes',
            'text': texto,
            'answer': texto,
            'profundizado': True,
            'source': 'cartera',
            'kpis': [
                {'label': 'Vencido', 'value': round(vencido, 2), 'suffix': '€', 'color': '#f87171'},
                {'label': 'Por vencer', 'value': round(por_vencer, 2), 'suffix': '€', 'color': '#fbbf24'},
            ],
            'table': {
                'title': f'Detalle de {titulo} por cuenta',
                'columns': ['Cuenta', 'Vencido (€)', 'Por vencer (€)', 'Efectos', 'Vencimiento'],
                'rows': [
                    [
                        fila['nombre'],
                        round(fila['vencido'], 2),
                        round(fila['por_vencer'], 2),
                        fila['efectos'],
                        fila['vencimiento'],
                    ]
                    for fila in visibles
                ],
            },
        }

    @staticmethod
    def _leer_vencido(empresa, year, tipo):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sql = """
            SELECT COALESCE(NULLIF(BTRIM(MAX(p.descripcion)), ''), c.codigo_titular) AS nombre,
                   SUM(CASE
                         WHEN c.fecha_vencimiento IS NOT NULL AND c.fecha_vencimiento < CURRENT_DATE
                         THEN c.importe - c.importe_cobrado ELSE 0
                       END) AS vencido,
                   SUM(CASE
                         WHEN c.fecha_vencimiento IS NULL OR c.fecha_vencimiento >= CURRENT_DATE
                         THEN c.importe - c.importe_cobrado ELSE 0
                       END) AS por_vencer,
                   MIN(c.fecha_vencimiento) AS vencimiento,
                   COUNT(*) AS efectos
            FROM datia_financial_cartera c
            LEFT JOIN datia_financial_plan p
              ON p.empresa = c.empresa
             AND p.ejercicio = c.ejercicio
             AND p.codigo = c.codigo_titular
            WHERE c.empresa = %s
              AND c.ejercicio = %s
              AND c.tipo_efecto = %s
              AND COALESCE(c.estado, '') NOT IN ('COBRADO', 'PAGADO', 'LIQUIDADO', 'ANULADO')
              AND (c.importe - c.importe_cobrado) > 0.01
            GROUP BY c.codigo_titular
            ORDER BY (SUM(c.importe - c.importe_cobrado)) DESC
        """
        with connections[alias].cursor() as cur:
            cur.execute(sql, [int(empresa), int(year), tipo])
            rows = cur.fetchall()
        salida = []
        for nombre, vencido, por_vencer, vencimiento, efectos in rows:
            salida.append({
                'nombre': str(nombre or 'Sin nombre'),
                'vencido': float(vencido or 0),
                'por_vencer': float(por_vencer or 0),
                'vencimiento': Profundizar._fecha(vencimiento),
                'efectos': int(efectos or 0),
            })
        return salida

    @staticmethod
    def _meses(empresa, year, compra):
        tabla = (
            'metrics_totales_empresa_ejercicio_compra_mes'
            if compra else 'metrics_totales_empresa_ejercicio_mes'
        )
        etiqueta = 'Compras' if compra else 'Ventas'
        try:
            filas = Profundizar._leer_meses(empresa, year, tabla)
        except Exception:
            logger.exception('Profundizar: no se pudo leer el mes')
            return Profundizar._texto(f'No he podido bajar {etiqueta.lower()} de {year} a meses.')
        if not filas:
            return Profundizar._texto(f'No hay meses con {etiqueta.lower()} en {year}.')
        neto = sum(fila['neto'] for fila in filas)
        coste = sum(fila['coste'] for fila in filas)
        texto = (
            f"{etiqueta} de {year} mes a mes. "
            f"El margen de cada mes es el importe neto menos el coste."
        )
        return {
            'type': 'report',
            'key': 'detalle_meses_compra' if compra else 'detalle_meses_venta',
            'text': texto,
            'answer': texto,
            'profundizado': True,
            'source': 'metrics',
            'kpis': [
                {'label': etiqueta, 'value': round(neto, 2), 'suffix': '€', 'color': '#34d399'},
                {'label': 'Margen', 'value': round(neto - coste, 2), 'suffix': '€', 'color': '#fbbf24'},
            ],
            'table': {
                'title': f'{etiqueta} por mes',
                'columns': ['Mes', f'{etiqueta} (€)', 'Coste (€)', 'Margen (€)', 'Operaciones'],
                'rows': [
                    [
                        fila['mes'],
                        round(fila['neto'], 2),
                        round(fila['coste'], 2),
                        round(fila['neto'] - fila['coste'], 2),
                        fila['ops'],
                    ]
                    for fila in filas
                ],
            },
        }

    @staticmethod
    def _leer_meses(empresa, year, tabla):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sql = f"""
            SELECT mes, importe_neto_total, importe_coste_total, albaranes_count
            FROM {tabla}
            WHERE empresa = %s AND ejercicio = %s
            ORDER BY mes
        """
        with connections[alias].cursor() as cur:
            cur.execute(sql, [int(empresa), int(year)])
            rows = cur.fetchall()
        salida = []
        for mes, neto, coste, ops in rows:
            numero = int(mes or 0)
            salida.append({
                'mes': _MESES[numero] if 1 <= numero <= 12 else str(mes),
                'neto': float(neto or 0),
                'coste': float(coste or 0),
                'ops': int(ops or 0),
            })
        return salida

    @staticmethod
    def _comparar_ejercicio(empresa, year):
        try:
            actual = Profundizar._leer_ejercicio(empresa, year)
            anterior = Profundizar._leer_ejercicio(empresa, year - 1)
        except Exception:
            logger.exception('Profundizar: no se pudo comparar el ejercicio')
            return Profundizar._texto(f'No he podido comparar {year} con el año anterior.')
        if not actual and not anterior:
            return Profundizar._texto(
                f'No hay un detalle más fino para esta consulta en {year}.'
            )
        columnas = ['Concepto', str(year)]
        if anterior:
            columnas += [str(year - 1), 'Variación (%)']
        conceptos = (
            ('Ventas (€)', 'neto'),
            ('Coste (€)', 'coste'),
            ('Margen (€)', 'margen'),
            ('Operaciones', 'ops'),
        )
        filas = []
        for etiqueta, clave in conceptos:
            ahora = actual.get(clave, 0) if actual else 0
            fila = [etiqueta, round(float(ahora), 2)]
            if anterior:
                antes = float(anterior.get(clave, 0))
                fila.append(round(antes, 2))
                fila.append(Profundizar._variacion(float(ahora), antes))
            filas.append(fila)
        texto = (
            f"Comparación del ejercicio {year} con {year - 1}. "
            f"El margen es la venta neta menos el coste."
            if anterior else
            f"Solo hay métricas de {year}. No existe la del año anterior para comparar."
        )
        neto = float((actual or anterior).get('neto', 0))
        return {
            'type': 'report',
            'key': 'detalle_comparativa',
            'text': texto,
            'answer': texto,
            'profundizado': True,
            'source': 'metrics',
            'kpis': [{
                'label': f'Ventas {year if actual else year - 1}',
                'value': round(neto, 2),
                'suffix': '€',
                'color': '#34d399',
            }],
            'table': {'title': 'Ejercicio contra el anterior', 'columns': columnas, 'rows': filas},
        }

    @staticmethod
    def _leer_ejercicio(empresa, year):
        alias = 'analytics' if 'analytics' in connections.databases else 'default'
        sql = """
            SELECT importe_neto_total, importe_coste_total, albaranes_count
            FROM metrics_totales_empresa_ejercicio
            WHERE empresa = %s AND ejercicio = %s
        """
        with connections[alias].cursor() as cur:
            cur.execute(sql, [int(empresa), int(year)])
            row = cur.fetchone()
        if not row:
            return None
        neto = float(row[0] or 0)
        coste = float(row[1] or 0)
        return {'neto': neto, 'coste': coste, 'margen': neto - coste, 'ops': int(row[2] or 0)}

    @staticmethod
    def _variacion(actual, anterior):
        if not anterior:
            return 0.0
        return round((actual - anterior) / abs(anterior) * 100, 1)

    @staticmethod
    def _fecha(valor):
        if isinstance(valor, datetime):
            valor = valor.date()
        if isinstance(valor, date):
            return valor.strftime('%d/%m/%Y')
        return '' if valor is None else str(valor)

    @staticmethod
    def _eur(valor):
        return f"{float(valor):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') + ' €'

    @staticmethod
    def _texto(mensaje):
        return {
            'type': 'text',
            'key': 'detalle_vacio',
            'text': mensaje,
            'answer': mensaje,
            'profundizado': True,
            'source': 'detalle',
        }
