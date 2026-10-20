"""Banco de mil preguntas de negocio y su resultado contra el chat, sin modelo ni entreno."""
import json
import logging
from pathlib import Path

ANOS = (2023, 2024, 2025, 2026)
MESES = ('enero', 'marzo', 'junio', 'septiembre', 'diciembre')
TOPS = (5, 10, 20, 50)
PREFIJOS = ('', 'dime ', 'necesito ', 'quiero ', 'muestra ')

FRASES_RECHAZO = (
    'puedo responder sobre',
    'no he podido',
    'formula la pregunta',
    'no he entendido',
    'elige la empresa',
    'nombra el dato',
)

_FAMILIAS = (
    {
        'familia': 'ventas', 'espera': 'respuesta', 'pista': 'importe', 'cupo': 120,
        'frases': (
            'ventas de {ano}', 'ventas netas de {ano}', 'importe de ventas en {ano}',
            'cuanto se ha vendido en {ano}', 'facturacion de {ano}', 'total de ventas en {ano}',
            'ventas del ejercicio {ano}', 'ventas mensuales de {ano}', 'evolucion de ventas en {ano}',
            'resumen de ventas {ano}', 'ventas de {mes} de {ano}', 'venta neta de {mes} de {ano}',
        ),
    },
    {
        'familia': 'compras', 'espera': 'respuesta', 'pista': 'compras', 'cupo': 100,
        'frases': (
            'compras de {ano}', 'importe de compras en {ano}', 'cuanto se ha comprado en {ano}',
            'total de compras en {ano}', 'compras del ejercicio {ano}', 'compras mensuales de {ano}',
            'evolucion de compras en {ano}', 'resumen de compras {ano}', 'compras de {mes} de {ano}',
            'compra neta de {mes} de {ano}',
        ),
    },
    {
        'familia': 'precio_medio', 'espera': 'respuesta', 'pista': 'precio_medio', 'cupo': 80,
        'frases': (
            'precio medio de venta en {ano}', 'cual es el precio medio de venta en {ano}',
            'ticket medio en {ano}', 'importe medio de albaran en {ano}',
            'precio medio de venta de {mes} de {ano}', 'ticket medio de {mes} de {ano}',
        ),
    },
    {
        'familia': 'margen', 'espera': 'respuesta', 'pista': 'margen', 'cupo': 100,
        'frases': (
            'margen de {ano}', 'cual es el margen de {ano}', 'margen del ejercicio {ano}',
            'margen por cliente en {ano}', 'margen por articulo en {ano}',
            'clientes con margen negativo en {ano}', 'articulos con margen negativo en {ano}',
            'margen de {mes} de {ano}',
        ),
    },
    {
        'familia': 'coste', 'espera': 'respuesta', 'pista': 'coste', 'cupo': 60,
        'frases': (
            'coste de {ano}', 'coste de ventas en {ano}', 'cual es el coste de {ano}',
            'coste del ejercicio {ano}', 'coste de {mes} de {ano}',
        ),
    },
    {
        'familia': 'ranking', 'espera': 'respuesta', 'pista': 'ranking', 'cupo': 140,
        'frases': (
            'top {n} clientes de {ano}', 'mejores {n} clientes de {ano}', 'peores {n} clientes de {ano}',
            'top {n} productos de {ano}', 'mejores articulos de {ano}', 'peores productos de {ano}',
            'top {n} proveedores de {ano}', 'peores proveedores de {ano}',
            'proveedor al que mas le compro en {ano}', 'a quien mas le compro en {ano}',
        ),
    },
    {
        'familia': 'conteo', 'espera': 'respuesta', 'pista': 'conteo', 'cupo': 80,
        'frases': (
            'cuantos clientes en {ano}', 'cuantos articulos en {ano}', 'cuantos proveedores en {ano}',
            'cuantos albaranes en {ano}', 'numero de clientes en {ano}', 'numero de articulos en {ano}',
        ),
    },
    {
        'familia': 'deuda', 'espera': 'respuesta', 'pista': 'deuda', 'cupo': 80,
        'frases': (
            'cuanto deben los clientes en {ano}', 'pendiente de cobro en {ano}',
            'cuanto debemos a los proveedores en {ano}', 'pendiente de pago en {ano}',
            'deuda de clientes en {ano}', 'deuda con proveedores en {ano}',
        ),
    },
    {
        'familia': 'kilos', 'espera': 'respuesta', 'pista': 'kilos', 'cupo': 60,
        'frases': (
            'cuantos kilos se han vendido en {ano}', 'kilos de cafe vendidos en {ano}',
            'kilos por cliente en {ano}', 'unidades vendidas en {ano}',
            'kilos vendidos en {mes} de {ano}',
        ),
    },
    {
        'familia': 'stock', 'espera': 'respuesta', 'pista': 'stock', 'cupo': 40,
        'frases': (
            'stock del 10045 en {ano}', 'stock de cafe en {ano}', 'existencias de cafe en {ano}',
            'inventario del 10045 en {ano}',
        ),
    },
    {
        'familia': 'lineas', 'espera': 'respuesta', 'pista': 'lineas', 'cupo': 40,
        'frases': (
            'detalle de lineas de albaran en {ano}', 'lineas de albaran de {ano}',
            'detalle de lineas de compra en {ano}', 'lineas de albaran de {mes} de {ano}',
        ),
    },
    {
        'familia': 'ventas_y_compras', 'espera': 'respuesta', 'pista': 'ambos', 'cupo': 40,
        'frases': (
            'ventas y compras de {ano}', 'ventas y compras de {mes} de {ano}',
            'comparar ventas y compras en {ano}',
        ),
    },
    {
        'familia': 'fuera', 'espera': 'rechazo', 'pista': '', 'cupo': 60,
        'frases': (
            'que tiempo hace manana', 'quien gano el mundial', 'cuentame un chiste',
            'cual es la capital de francia', 'pon una cancion', 'receta de tortilla',
            'a que hora sale el tren', 'cuantos habitantes tiene roma',
            'como se ata un nudo', 'que pelicula veo hoy', 'a que huele la lluvia',
            'cuanto mide el everest',
        ),
    },
)


def _completar(grupo, vistas):
    conseguidas = []
    for prefijo in PREFIJOS:
        for ano in ANOS:
            for mes in MESES:
                for n in TOPS:
                    for plantilla in grupo['frases']:
                        texto = prefijo + plantilla.format(ano=ano, mes=mes, n=n)
                        if texto in vistas:
                            continue
                        vistas.add(texto)
                        conseguidas.append(texto)
                        if len(conseguidas) >= grupo['cupo']:
                            return conseguidas
    return conseguidas


def construir_banco():
    """Mil preguntas unicas, cada una con familia y resultado esperado."""
    banco = []
    vistas = set()
    for grupo in _FAMILIAS:
        for texto in _completar(grupo, vistas):
            banco.append({
                'texto': texto,
                'familia': grupo['familia'],
                'espera': grupo['espera'],
                'pista': grupo['pista'],
            })
    if len(banco) != 1000:
        raise RuntimeError(f'El banco tiene {len(banco)} preguntas, no 1000')
    for numero, pregunta in enumerate(banco, start=1):
        pregunta['id'] = numero
    return banco


def clasificar(pregunta, resultado):
    from datia.services.ai_service import _respuesta_tiene_valor

    texto = f"{(resultado or {}).get('text') or ''} {(resultado or {}).get('answer') or ''}"
    folded = texto.casefold()
    tiene = _respuesta_tiene_valor(resultado or {})
    es_rechazo = any(frase in folded for frase in FRASES_RECHAZO)
    tipo = (resultado or {}).get('type')
    sql = str((resultado or {}).get('sql') or '').casefold()
    plan = (resultado or {}).get('plan') or {}
    metrica = str(plan.get('metrica') or '')
    if tipo == 'error' or 'error al procesar' in folded:
        clase = 'error'
    elif pregunta['espera'] == 'rechazo':
        clase = 'acierto' if es_rechazo or not tiene else 'aceptada_sin_ser_negocio'
    elif tipo == 'ambiguity_alert':
        clase = 'aclaracion'
    elif not tiene or es_rechazo:
        clase = 'sin_respuesta'
    else:
        clase = 'acierto'
        pista = pregunta.get('pista') or ''
        if pista == 'precio_medio' and 'medio' not in folded and 'nullif(albaranes_count' not in sql and metrica != 'precio_medio':
            clase = 'metrica_incorrecta'
        elif pista == 'deuda' and resultado.get('source') != 'cartera' and not any(
            palabra in folded for palabra in ('pendiente', 'cobro', 'pago', 'deuda')
        ):
            clase = 'metrica_incorrecta'
        elif pista == 'kilos' and metrica != 'kilos' and 'importeneto' not in sql and not any(
            palabra in folded for palabra in ('kilo', 'unidad', 'unidades')
        ):
            clase = 'metrica_incorrecta'
        elif pista == 'stock' and 'unidadsaldo' not in sql and not any(
            palabra in folded for palabra in ('stock', 'existenc', 'inventario')
        ):
            clase = 'metrica_incorrecta'
    return {
        'id': pregunta['id'],
        'texto': pregunta['texto'],
        'familia': pregunta['familia'],
        'espera': pregunta['espera'],
        'pista': pregunta.get('pista') or '',
        'clase': clase,
        'tipo': tipo,
        'origen': 'ya_sabida',
        'extracto': ' '.join(texto.split())[:240],
    }


def _callar_gemini():
    """El informe de catálogo no debe salir a Gemini. El autoentreno sigue en Ollama."""
    from unittest.mock import patch
    from datia.services.gemini_service import GeminiService

    def texto_vacio(*_args, **_kwargs):
        return ''

    def politica_vacia(*_args, **_kwargs):
        return {'status': 'skip', 'text': ''}

    return [
        patch.object(GeminiService, 'generate_text', texto_vacio),
        patch.object(GeminiService, 'generate_text_with_policy', politica_vacia),
    ]


def _aprendio(resultado):
    if not isinstance(resultado, dict):
        return False
    from datia.services.ai_service import _respuesta_tiene_valor
    if not _respuesta_tiene_valor(resultado):
        return False
    return bool(resultado.get('sql') or resultado.get('plan') or resultado.get('reentrenado'))


def ejecutar(empresa=1, ejercicio=2025, banco=None, informe_path=None):
    """Lo ya resuelto se queda. Lo demás lo escribe el modelo local y, si hay filas, se aprende."""
    from datia.services.ai_service import IAService

    banco = banco or construir_banco()
    logging.getLogger('datia').setLevel(logging.ERROR)
    logging.getLogger('query_builder').setLevel(logging.ERROR)
    logging.getLogger('gemini_service').setLevel(logging.CRITICAL)
    servicio = IAService()
    filas = []
    parches = _callar_gemini()
    for parche in parches:
        parche.start()
    try:
        for pregunta in banco:
            try:
                primero = servicio._responder(pregunta['texto'], {
                    'empresa': empresa,
                    'ejercicio': ejercicio,
                    'limit': 10,
                    'threshold': 0.60,
                    'lang': 'es',
                    'training_enabled': False,
                    'model': None,
                    'request': None,
                }, 'es', False)
            except Exception as exc:
                primero = {'type': 'error', 'text': str(exc), 'answer': str(exc)}
            fila = clasificar(pregunta, primero if isinstance(primero, dict) else {})
            if fila['clase'] != 'acierto':
                print(f"entreno {pregunta['id']}: {pregunta['texto']}", flush=True)
                try:
                    segundo = servicio._consulta_del_modelo(pregunta['texto'], {
                        'empresa': empresa,
                        'ejercicio': ejercicio,
                        'limit': 10,
                    }, 'es')
                except Exception as exc:
                    segundo = {'type': 'error', 'text': str(exc), 'answer': str(exc)}
                if isinstance(segundo, dict):
                    fila = clasificar(pregunta, segundo)
                    fila['origen'] = 'aprendida' if _aprendio(segundo) else 'sin_resultado'
                else:
                    fila['origen'] = 'sin_resultado'
            filas.append(fila)
            if len(filas) % 100 == 0:
                print(f'banco {len(filas)}/1000', flush=True)
    finally:
        for parche in reversed(parches):
            parche.stop()
    informe = _informe(filas)
    destino = Path(informe_path) if informe_path else Path(__file__).resolve().parents[1] / 'runtime' / 'banco_preguntas_resultado.json'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding='utf-8')
    informe['ruta'] = str(destino)
    return informe


def _informe(filas):
    clases = {}
    origenes = {}
    familias = {}
    ejemplos = {}
    for fila in filas:
        clases[fila['clase']] = clases.get(fila['clase'], 0) + 1
        origen = fila.get('origen') or 'ya_sabida'
        origenes[origen] = origenes.get(origen, 0) + 1
        familia = familias.setdefault(fila['familia'], {'total': 0, 'acierto': 0, 'aprendida': 0})
        familia['total'] += 1
        if fila['clase'] == 'acierto':
            familia['acierto'] += 1
        if origen == 'aprendida':
            familia['aprendida'] += 1
        if fila['clase'] != 'acierto':
            grupo = ejemplos.setdefault(fila['clase'], [])
            if len(grupo) < 12:
                grupo.append({
                    'familia': fila['familia'],
                    'origen': fila.get('origen'),
                    'texto': fila['texto'],
                    'extracto': fila['extracto'],
                })
    por_familia = []
    for nombre, datos in familias.items():
        por_familia.append({
            'familia': nombre,
            'total': datos['total'],
            'acierto': datos['acierto'],
            'aprendida': datos['aprendida'],
            'tasa': round(datos['acierto'] / datos['total'], 3) if datos['total'] else 0,
        })
    return {
        'preguntas': len(filas),
        'origen': origenes,
        'clases': clases,
        'familias': por_familia,
        'ejemplos': ejemplos,
    }


def resumen_texto(informe):
    lineas = [f"Preguntas: {informe['preguntas']}"]
    lineas.append('Autoentreno:')
    for origen, cuenta in sorted((informe.get('origen') or {}).items(), key=lambda item: -item[1]):
        lineas.append(f"  {origen}: {cuenta}")
    for clase, cuenta in sorted(informe['clases'].items(), key=lambda item: -item[1]):
        lineas.append(f"  {clase}: {cuenta}")
    lineas.append('Por familia:')
    for fila in informe['familias']:
        lineas.append(f"  {fila['familia']}: {fila['acierto']}/{fila['total']} ({fila['tasa']:.0%})")
    return '\n'.join(lineas)


if __name__ == '__main__':
    import os
    import sys

    import django

    raiz = Path(__file__).resolve().parents[2]
    if str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    print(resumen_texto(ejecutar()))
