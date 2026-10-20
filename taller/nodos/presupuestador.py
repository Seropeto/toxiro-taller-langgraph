from ..estado import EstadoTaller

TASA_IVA = 0.16


def presupuestador(estado: EstadoTaller) -> EstadoTaller:
    """Arma el presupuesto para la hipótesis principal. Simulado con datos fijos."""
    items = [
        {"descripcion": "Juego de pastillas delanteras", "cantidad": 1, "precio_unitario": 850.0},
        {"descripcion": "Mano de obra cambio de pastillas", "cantidad": 1, "precio_unitario": 400.0},
    ]
    for item in items:
        item["subtotal"] = item["cantidad"] * item["precio_unitario"]
    subtotal = sum(item["subtotal"] for item in items)
    iva = round(subtotal * TASA_IVA, 2)
    return {
        "presupuesto": {
            "items": items,
            "subtotal": subtotal,
            "iva": iva,
            "total": subtotal + iva,
        }
    }
