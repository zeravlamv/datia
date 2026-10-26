"""Aplica los .md de datia/reglas. La primera regla que encaja decide el motor."""
import logging
import re
from pathlib import Path

from datia.services.ai.compilador_mapeo import _plegar

logger = logging.getLogger('query_builder')

_CARPETA = Path(__file__).resolve().parents[2] / 'reglas'
_CACHE = {'clave': None, 'reglas': []}
_NOMBRE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$')
_TOPE = 200_000


def carpeta_reglas():
    return _CARPETA


def _raiz(raiz=None):
    return Path(raiz) if raiz else _CARPETA


def _firma(base):
    if not base.is_dir():
        return None
    return tuple(
        (path.name, path.stat().st_mtime_ns)
        for path in sorted(base.glob('*.md'), key=lambda item: item.name.lower())
        if path.is_file()
    )


def _bloques(texto):
    reglas = []
    for bloque in re.findall(r':::regla\n(.*?):::', texto or '', re.S):
        regla = {}
        for linea in bloque.splitlines():
            if ':' not in linea:
                continue
            clave, valor = linea.split(':', 1)
            regla[clave.strip().lower()] = valor.strip()
        if regla.get('id') and regla.get('motor'):
            reglas.append(regla)
    return reglas


def cargar(raiz=None):
    base = _raiz(raiz)
    firma = _firma(base)
    clave = (str(base.resolve()) if base.exists() else str(base), firma)
    if _CACHE.get('clave') == clave:
        return _CACHE['reglas']
    if firma is None:
        logger.warning('Reglas: no está la carpeta %s', base)
        _CACHE['clave'] = clave
        _CACHE['reglas'] = []
        return []
    reglas = []
    for nombre, _mtime in firma:
        reglas.extend(_bloques((base / nombre).read_text(encoding='utf-8')))
    _CACHE['clave'] = clave
    _CACHE['reglas'] = reglas
    return reglas


def _fichero(nombre, raiz=None):
    base = _raiz(raiz).resolve()
    limpio = (nombre or '').strip().replace('\\', '/')
    if '/' in limpio or limpio in ('.', '..'):
        raise ValueError('El nombre solo admite letras, números, guion y guion bajo.')
    if limpio.lower().endswith('.md'):
        limpio = limpio[:-3]
    if not _NOMBRE.fullmatch(limpio):
        raise ValueError('El nombre solo admite letras, números, guion y guion bajo.')
    destino = (base / f'{limpio}.md').resolve()
    if destino.parent != base:
        raise ValueError('El fichero tiene que quedar en la carpeta de reglas.')
    return destino


def listar_ficheros(raiz=None):
    base = _raiz(raiz)
    firma = _firma(base) or ()
    return [{'nombre': nombre, 'bytes': (base / nombre).stat().st_size} for nombre, _mtime in firma]


def leer_fichero(nombre, raiz=None):
    path = _fichero(nombre, raiz)
    if not path.is_file():
        raise FileNotFoundError(path.name)
    return path.read_text(encoding='utf-8')


def guardar_fichero(nombre, texto, raiz=None, crear=False):
    path = _fichero(nombre, raiz)
    cuerpo = (texto or '').replace('\r\n', '\n').replace('\r', '\n')
    if len(cuerpo) > _TOPE:
        raise ValueError('El fichero pasa de 200.000 caracteres.')
    if crear and path.exists():
        raise FileExistsError(path.name)
    if not crear and not path.is_file():
        raise FileNotFoundError(path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cuerpo, encoding='utf-8', newline='\n')
    _CACHE['clave'] = None
    return path.name


def _trozos(valor):
    return [trozo.strip() for trozo in (valor or '').split('|') if trozo.strip()]


def _pasos(valor):
    return [paso.strip() for paso in re.split(r'[,|]', valor or '') if paso.strip()]


def _encaja(folded, token):
    token = _plegar(token)
    if not token:
        return False
    if token.endswith('*'):
        raiz = re.escape(token[:-1])
        return re.search(r'\b' + raiz + r'\w*\b', folded) is not None
    palabras = token.split()
    patron = r'\b' + r'\s+'.join(re.escape(palabra) for palabra in palabras) + r'\b'
    return re.search(patron, folded) is not None


def _alguna(folded, valor):
    return any(_encaja(folded, token) for token in _trozos(valor))


def _anio_de(pregunta, lectura, ejercicio, regla):
    from datia.services.ai.interprete_mapeo import _anio_del_hilo, _periodos
    for paso in _pasos(regla.get('anio') or 'frase, hilo, ejercicio'):
        if paso == 'frase':
            anios = _periodos(pregunta)
            if anios:
                return int(anios[-1])
        elif paso == 'hilo':
            anio = _anio_del_hilo(lectura)
            if anio:
                return int(anio)
        elif paso == 'ejercicio':
            try:
                return int(ejercicio)
            except (TypeError, ValueError):
                return None
    return None


def _lado_de(pregunta, lectura, lado_forzado, regla):
    if lado_forzado in ('cliente', 'proveedor'):
        return lado_forzado
    folded = _plegar(pregunta)
    venta = _alguna(folded, regla.get('venta'))
    compra = _alguna(folded, regla.get('compra'))
    if venta and not compra:
        return 'cliente'
    if compra and not venta:
        return 'proveedor'
    from datia.services.ai.interprete_mapeo import _lado_unico
    return _lado_unico(lectura, ['cliente', 'proveedor']) or 'cliente'


def decidir(pregunta, lectura=None, ejercicio=None, lado_forzado=''):
    folded = _plegar(pregunta)
    if not folded:
        return None
    for regla in cargar():
        motor = regla.get('motor')
        if motor in ('mapeo', 'cobertura'):
            continue
        if motor == 'informe' and _alguna(folded, regla.get('contiene')):
            return {
                'id': regla['id'],
                'motor': 'informe',
                'informe': regla.get('informe'),
                'anio': _anio_de(pregunta, lectura, ejercicio, regla),
            }
        if motor == 'kilos' and _alguna(folded, regla.get('señal')) and _alguna(folded, regla.get('corte')):
            return {
                'id': regla['id'],
                'motor': 'kilos',
                'anio': _anio_de(pregunta, lectura, ejercicio, regla),
                'lado': _lado_de(pregunta, lectura, lado_forzado, regla),
            }
    return None


def respuesta_informe(pregunta, context):
    """Informe con nombre propio. None si la frase sigue en el mapeo."""
    decision = decidir(pregunta, (context or {}).get('lectura'), (context or {}).get('ejercicio'))
    if not decision or decision.get('motor') != 'informe':
        return None
    if decision.get('anio'):
        context['ejercicio'] = decision['anio']
    from datia.services.ai.handlers.catalog_report_handler import CatalogReportHandler
    payload = CatalogReportHandler(None).handle(
        {'intent_id': decision['informe'], 'query': pregunta, 'regla': decision['id']},
        context,
    )
    if isinstance(payload, dict):
        payload['regla'] = decision['id']
        payload['source'] = 'reglas'
    return {'reply': payload, 'regla': decision['id']}
