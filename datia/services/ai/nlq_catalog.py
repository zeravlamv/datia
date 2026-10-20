import re
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple


@dataclass(frozen=True)
class CatalogIntent:
    intent_id: str
    patterns: Tuple[re.Pattern, ...]


def _p(expr: str) -> re.Pattern:
    return re.compile(expr, re.IGNORECASE)


CATALOG: List[CatalogIntent] = [
    CatalogIntent(
        intent_id="financiera.ratios",
        patterns=(
            _p(r"^\s*ratios?\b.*\b(20\d{2})\b"),
            _p(r"\b(ratios?\s+financieros?|ratio\s+financiero)\b"),
            _p(r"\b(liquidez|test\s+[aá]cido|solvencia|endeudamiento|roe|roa|margen\s+neto|margen\s+ebitda|cobertura\s+de\s+inter[eé]s|fondo\s+de\s+maniobra)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="presupuestos.comparativa",
        patterns=(
            _p(r"\bpresupuestos?\b"),
            _p(r"\bbudget\b"),
            _p(r"\b(desviaci[oó]n|comparativa)\b.*\bpresupuest"),
            _p(r"\bpresupuest\b.*\b(vs|contra|comparativa)\b.*\b(real|actual)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="tesoreria.resumen",
        patterns=(
            _p(r"\b(resumen|informe|an[aá]lisis)\b.*\b(tesorer[ií]a|caja|saldos?|cartera|vencimientos|cobros?|pagos?)\b"),
            _p(r"\b(tesorer[ií]a|caja|saldos?|cartera|vencimientos|cobros?|pagos?)\b.*\b(resumen|informe|an[aá]lisis)\b"),
            _p(r"^\s*tesorer[ií]a\s*(20\d{2})?\s*$"),
        ),
    ),
    CatalogIntent(
        intent_id="tesoreria.forecast",
        patterns=(
            _p(r"\b(previsi[oó]n|forecast|proyecci[oó]n)\b.*\b(tesorer[ií]a|caja)\b"),
            _p(r"\b(tesorer[ií]a|caja)\b.*\b(previsi[oó]n|forecast|proyecci[oó]n)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="tesoreria.pool_bancario",
        patterns=(
            _p(r"\b(pool|bancario|lineas?\s+de\s+credito|poliza|confirming|factoring)\b"),
            _p(r"\b(instrumentos|vencimientos)\b.*\b(pool|bancario)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="tesoreria.caja_mensual",
        patterns=(
            _p(r"\b(caja|tesorer[ií]a)\b.*\b(mensual|mensuales|por mes|mes a mes|evoluci[oó]n)\b"),
            _p(r"\b(saldos?|saldo)\b.*\b(mensual|mensuales|por mes|mes a mes)\b.*\b(caja|tesorer[ií]a)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.resumen_ejercicio",
        patterns=(
            _p(r"\bventas\b.*\bresumen\b"),
            _p(r"\bresumen\b.*\bventas\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.top_clientes",
        patterns=(
            _p(r"\b(top|mejores|ranking|peores|peor|menores)\b.*\bclientes?\b"),
            _p(r"\bclientes?\b.*\b(peores|peor|menores)\b"),
            _p(r"\bmejores?\b.*\bclientes?\b.*\b(año|ano|ejercicio)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.top_productos",
        patterns=(
            _p(r"\b(top|mejores|ranking|peores|peor|menores)\b.*\b(productos?|art[ií]culos?)\b"),
            _p(r"\b(productos?|art[ií]culos?)\b.*\b(peores|peor|menores)\b"),
            _p(r"\bmejores?\b.*\b(productos?|art[ií]culos?)\b.*\b(año|ano|ejercicio)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.ventas_mensual",
        patterns=(
            _p(r"\bventas?\b.*\b(mensual|por mes|mes a mes)\b"),
            _p(r"\bevoluci[oó]n\b.*\bventas?\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.margen_mensual",
        patterns=(
            _p(r"\bmargen\b.*\b(mensual|por mes|mes a mes)\b"),
            _p(r"\bevoluci[oó]n\b.*\bmargen\b"),
        ),
    ),
    CatalogIntent(
        intent_id="finanzas.resumen_ejercicio",
        patterns=(
            _p(r"\bresumen\b.*\b(finanzas?|financiero|financiera)\b"),
            _p(r"\b(informe|an[aá]lisis)\b.*\b(finanzas?|financiero|financiera)\b"),
            _p(r"^\s*resumen\s*(20\d{2})?\s*$"),
        ),
    ),
    CatalogIntent(
        intent_id="finanzas.per100",
        patterns=(
            _p(r"\b(coste|costes)\b.*\b(cada\s*100|por\s*100)\b"),
            _p(r"\bper\s*100\b"),
            _p(r"\bestructura\b.*\bcostes?\b"),
        ),
    ),
    CatalogIntent(
        intent_id="ventas.rango_periodos",
        patterns=(
            _p(r"\bventas?\b.*\b(periodo|per[íi]odo)\b.*\b(\d{1,2})\b"),
            _p(r"\bventas?\b.*\bde\b.*\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b.*\ba\b.*\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="compras.top_proveedores",
        patterns=(
            _p(r"\b(top|mejores|ranking|peores|peor|menores)\b.*\bproveedores?\b"),
            _p(r"\bproveedores?\b.*\b(peores|peor|menores)\b"),
            _p(r"\bmejores?\b.*\bproveedores?\b.*\b(año|ano|ejercicio)\b"),
        ),
    ),
    CatalogIntent(
        intent_id="compras.resumen_ejercicio",
        patterns=(
            _p(r"\bresumen\b.*\bcompras?\b"),
            _p(r"\bcompras?\b.*\bresumen\b"),
        ),
    ),
    CatalogIntent(
        intent_id="compras.compras_mensual",
        patterns=(
            _p(r"\bcompras?\b.*\b(mensual|por mes|mes a mes)\b"),
            _p(r"\bevoluci[oó]n\b.*\bcompras?\b"),
        ),
    ),
]


def match_intent(question: str) -> Optional[Dict[str, Any]]:
    q = (question or "").strip()
    if not q:
        return None
    for it in CATALOG:
        for pat in it.patterns:
            if pat.search(q):
                return {"intent_id": it.intent_id}
    return None


def cubre_la_pregunta(question: str, intent_id: str) -> bool:
    """Una frase con dos cortes (clientes y productos, ventas y compras) no cabe en un solo informe."""
    q = (question or "").lower()

    def has(*words: str) -> bool:
        return any(re.search(rf"\b{re.escape(word)}\b", q) for word in words)

    entidades = sum([
        has("cliente", "clientes"),
        has("producto", "productos", "articulo", "articulos", "artículo", "artículos"),
        has("proveedor", "proveedores"),
    ])
    if entidades >= 2:
        return False
    if has("venta", "ventas") and has("compra", "compras"):
        if str(intent_id or "").startswith(("ventas.", "compras.")):
            return False
    return True
