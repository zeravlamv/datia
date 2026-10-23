"""Celdas de comparación interanual y avisos cuando el coste o el año anterior no cuadran."""


def celda(hay_anterior, valor):
    if not hay_anterior:
        return 'sin datos'
    return valor


def aviso_coste_y_hueco(filas, ejercicio_anterior):
    """filas: dicts con ventas, coste y hay_anterior."""
    sobre = 0
    huecos = 0
    for fila in filas:
        if not fila.get('hay_anterior'):
            huecos += 1
        try:
            ventas = float(fila.get('ventas') if fila.get('ventas') is not None else fila.get('value') or 0)
            coste = float(fila.get('coste') if fila.get('coste') is not None else fila.get('cost') or 0)
        except (TypeError, ValueError):
            continue
        if ventas > 0 and coste > ventas:
            sobre += 1
    partes = []
    if sobre:
        partes.append(
            f"En {sobre} filas el coste agregado supera la venta. "
            "Ese coste suma ImporteCoste de cada línea de albarán; si viene a cero, usa PrecioCoste por unidades "
            "y, en último lugar, el precio de compra del artículo por las unidades. "
            "Revisa esas líneas antes de leer el margen negativo como una pérdida confirmada."
        )
    if huecos:
        partes.append(
            f"{huecos} filas no tienen métrica de {ejercicio_anterior}. "
            "La variación no es 0 %: es un hueco y se muestra como «sin datos»."
        )
    texto = "\n".join(f"> {parte}" for parte in partes)
    return texto, bool(texto)
