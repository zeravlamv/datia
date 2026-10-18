"""Índice local de clientes, artículos y cuentas. La cifra no sale de este módulo."""

import logging
import os

import numpy as np
import requests
from django.db import connections, transaction

logger = logging.getLogger(__name__)
_INDICE = {}

UMBRAL = 0.66
HUECO = 0.03
MAX_OPCIONES = 5
LOTE_VECTORES = 64

CATALOGOS = (
    {
        'clase': 'cliente',
        'origen': 'datia_cliente',
        'sql': 'SELECT cliente, nombre, COALESCE(nombre_fiscal, \'\') FROM datia_cliente WHERE empresa = %s',
    },
    {
        'clase': 'articulo',
        'origen': 'datia_articulos',
        'sql': 'SELECT articulo, COALESCE(descripcion, \'\'), \'\' FROM datia_articulos WHERE empresa = %s',
    },
    {
        'clase': 'cuenta',
        'origen': 'datiadb_plancuentas',
        'sql': 'SELECT codigo_cuenta, COALESCE(nombre_cuenta, \'\'), \'\' FROM datiadb_plancuentas WHERE empresa = %s',
    },
)


def coseno(izquierda, derecha):
    """None si la longitud no coincide. No se rellena con ceros."""
    if not isinstance(izquierda, list) or not isinstance(derecha, list):
        return None
    if not izquierda or len(izquierda) != len(derecha):
        return None
    producto = 0.0
    norma_izq = 0.0
    norma_der = 0.0
    for uno, otro in zip(izquierda, derecha):
        producto += float(uno) * float(otro)
        norma_izq += float(uno) * float(uno)
        norma_der += float(otro) * float(otro)
    if norma_izq == 0.0 or norma_der == 0.0:
        return None
    return producto / ((norma_izq ** 0.5) * (norma_der ** 0.5))


def comparable(fila, modelo, longitud):
    """No se compara un vector con otro de distinto modelo o distinta longitud."""
    if getattr(fila, 'modelo', None) != modelo:
        return False
    vector = getattr(fila, 'vector', None)
    if not isinstance(vector, list) or len(vector) != longitud:
        return False
    return True


def olvidar_indice():
    _INDICE.clear()


def decidir(candidatos, hueco=HUECO):
    if not candidatos:
        return {'status': 'ninguna'}
    candidatos = sorted(candidatos, key=lambda item: item[0], reverse=True)
    clase = candidatos[0][1].clase
    misma = [item for item in candidatos if item[1].clase == clase]
    if len(misma) >= 2 and (misma[0][0] - misma[1][0]) < hueco:
        return {'status': 'ambiguo', 'opciones': [item[1] for item in misma[:MAX_OPCIONES]]}
    return {'status': 'encontrada', 'entidad': misma[0][1]}


def puntuar(vector, filas, modelo, umbral=UMBRAL, hueco=HUECO):
    """Elige una entidad o hasta cinco de la misma clase si están demasiado próximas."""
    if not isinstance(vector, list) or not vector:
        return {'status': 'preparando'}
    candidatos = []
    for fila in filas:
        if not comparable(fila, modelo, len(vector)):
            continue
        score = coseno(vector, fila.vector)
        if score is None or score < umbral:
            continue
        candidatos.append((score, fila))
    return decidir(candidatos, hueco)


class SignificadoService:
    @staticmethod
    def modelo_activo():
        try:
            from django.conf import settings
            configurado = getattr(settings, 'OLLAMA_EMBED_MODEL', None)
        except Exception:
            configurado = None
        import os
        return os.environ.get('OLLAMA_EMBED_MODEL') or configurado or 'nomic-embed-text'

    @staticmethod
    def vector_de(texto):
        from datia.services.embedding_service import EmbeddingService
        return EmbeddingService()._embed_with_ollama(texto)

    @staticmethod
    def _alias():
        return 'analytics' if 'analytics' in connections.databases else 'default'

    @staticmethod
    def cargar_catalogo(empresa):
        filas = []
        with connections[SignificadoService._alias()].cursor() as cur:
            for catalogo in CATALOGOS:
                cur.execute(catalogo['sql'], [empresa])
                for identificador, visible, alternativo in cur.fetchall():
                    codigo = str(identificador or '').strip()
                    texto = str(visible or '').strip() or str(alternativo or '').strip()
                    if not codigo or not texto:
                        continue
                    filas.append({
                        'clase': catalogo['clase'],
                        'origen': catalogo['origen'],
                        'identificador': codigo,
                        'texto': texto,
                    })
        return filas

    @staticmethod
    def vectores_de(textos):
        """Varios textos en una sola llamada local. None si Ollama no responde."""
        if not textos:
            return []
        base = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        modelo = SignificadoService.modelo_activo()
        try:
            res = requests.post(
                f'{base}/api/embed',
                json={'model': modelo, 'input': list(textos)},
                timeout=(5, 180),
            )
        except Exception:
            logger.exception('Significado: Ollama no respondió el lote')
            return None
        if res.status_code != 200:
            return None
        crudos = (res.json() or {}).get('embeddings')
        if not isinstance(crudos, list) or len(crudos) != len(textos):
            return None
        vectores = []
        for vector in crudos:
            if not isinstance(vector, list) or not vector:
                return None
            vectores.append([float(numero) for numero in vector])
        return vectores

    @staticmethod
    def reindex(empresa, on_progress=None):
        from datia.models.significado import SignificadoEntidad, SignificadoLote

        modelo = SignificadoService.modelo_activo()
        sonda = SignificadoService.vector_de('datia')
        if not sonda:
            return {
                'ok': False,
                'message': 'Falta el modelo nomic-embed-text en Ollama. El índice no queda listo.',
            }
        empresa_id = int(empresa)
        olvidar_indice()
        lote, _created = SignificadoLote.objects.update_or_create(
            empresa=empresa_id,
            modelo=modelo,
            defaults={'estado': 'construyendo'},
        )
        try:
            catalogo = SignificadoService.cargar_catalogo(empresa_id)
        except Exception:
            logger.exception('Significado: no se pudo leer el catálogo')
            return {
                'ok': False,
                'message': 'No se pudo leer el catálogo de la empresa. El índice no queda listo.',
            }
        unicos = {}
        for fila in catalogo:
            unicos[(fila['clase'], fila['identificador'])] = fila
        catalogo = list(unicos.values())
        SignificadoEntidad.objects.filter(empresa=empresa_id, modelo=modelo).delete()
        hechos = 0
        total = len(catalogo)
        for inicio in range(0, total, LOTE_VECTORES):
            trozo = catalogo[inicio:inicio + LOTE_VECTORES]
            vectores = SignificadoService.vectores_de([fila['texto'] for fila in trozo])
            if not vectores:
                return {
                    'ok': False,
                    'message': 'Ollama no devolvió el vector completo. El índice no queda listo.',
                }
            objetos = []
            for fila, vector in zip(trozo, vectores):
                if len(vector) != len(sonda):
                    return {
                        'ok': False,
                        'message': 'Ollama no devolvió el vector completo. El índice no queda listo.',
                    }
                objetos.append(SignificadoEntidad(
                    empresa=empresa_id,
                    clase=fila['clase'],
                    identificador=fila['identificador'],
                    texto_indexado=fila['texto'],
                    origen=fila['origen'],
                    modelo=modelo,
                    vector=vector,
                ))
            SignificadoEntidad.objects.bulk_create(objetos, batch_size=500)
            hechos += len(objetos)
            if on_progress:
                on_progress(hechos, total)
        with transaction.atomic():
            SignificadoEntidad.objects.filter(empresa=empresa_id).exclude(modelo=modelo).delete()
            SignificadoLote.objects.filter(empresa=empresa_id).exclude(modelo=modelo).delete()
            lote.estado = 'listo'
            lote.save(update_fields=['estado'])
        olvidar_indice()
        return {'ok': True, 'message': f'Índice listo para la empresa {empresa} con {modelo}. {total} textos.'}

    @staticmethod
    def buscar(texto, empresa, clase=None):
        from datia.models.significado import SignificadoEntidad, SignificadoLote

        try:
            empresa_id = int(empresa)
        except (TypeError, ValueError):
            return {'status': 'sin_empresa'}
        modelo = SignificadoService.modelo_activo()
        lote = SignificadoLote.objects.filter(empresa=empresa_id, modelo=modelo).first()
        if not lote or lote.estado != 'listo':
            return {'status': 'preparando'}
        vector = SignificadoService.vector_de(texto)
        if not vector:
            return {'status': 'preparando'}
        return SignificadoService._buscar_en_memoria(empresa_id, modelo, clase, vector)

    @staticmethod
    def _buscar_en_memoria(empresa_id, modelo, clase, vector):
        from datia.models.significado import SignificadoEntidad

        clave = (empresa_id, modelo, clase or '')
        if clave not in _INDICE:
            consulta = SignificadoEntidad.objects.filter(empresa=empresa_id, modelo=modelo)
            if clase:
                consulta = consulta.filter(clase=clase)
            filas = []
            columnas = []
            for fila in consulta.iterator(chunk_size=1000):
                if not comparable(fila, modelo, len(vector)):
                    continue
                filas.append(fila)
                columnas.append(fila.vector)
            if columnas:
                matriz = np.asarray(columnas, dtype=np.float32)
                normas = np.linalg.norm(matriz, axis=1)
                normas[normas == 0] = 1.0
                matriz = matriz / normas[:, None]
            else:
                matriz = None
            _INDICE[clave] = (matriz, filas)
        matriz, filas = _INDICE[clave]
        if matriz is None or not len(filas):
            return {'status': 'ninguna'}
        if matriz.shape[1] != len(vector):
            return {'status': 'ninguna'}
        consulta = np.asarray(vector, dtype=np.float32)
        norma = float(np.linalg.norm(consulta))
        if norma == 0.0:
            return {'status': 'ninguna'}
        consulta = consulta / norma
        puntuaciones = matriz @ consulta
        candidatos = []
        for posicion in np.argsort(-puntuaciones):
            score = float(puntuaciones[int(posicion)])
            if score < UMBRAL:
                break
            candidatos.append((score, filas[int(posicion)]))
        return decidir(candidatos)
