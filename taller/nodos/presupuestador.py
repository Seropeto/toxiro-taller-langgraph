from langgraph.runtime import Runtime

from ..contexto import TenantContext
from ..estado import EstadoTaller

TASA_IVA = 0.16
# Ítems para la hipótesis principal (pastillas desgastadas). Simulado: fijo, precios del catálogo.
CODIGOS_PRESUPUESTO = ("FRE-PAS-DEL", "MO-FRENOS")


def presupuestador(estado: EstadoTaller, runtime: Runtime[TenantContext]) -> EstadoTaller:
    """Arma el presupuesto con el catálogo y los márgenes del taller (runtime.context)."""
    contexto = runtime.context
    if contexto is None:
        raise ValueError("El presupuestador necesita un TenantContext: invoca el grafo con context=")

    items = []
    for codigo in CODIGOS_PRESUPUESTO:
        item = contexto.item(codigo)
        precio = contexto.precio_cliente(item)
        items.append(
            {"descripcion": item.descripcion, "cantidad": 1, "precio_unitario": precio, "subtotal": precio}
        )
    subtotal = sum(item["subtotal"] for item in items)
    iva = round(subtotal * TASA_IVA, 2)
    return {
        "presupuesto": {
            "taller": contexto.nombre_taller,
            "items": items,
            "subtotal": subtotal,
            "iva": iva,
            "total": subtotal + iva,
        }
    }
