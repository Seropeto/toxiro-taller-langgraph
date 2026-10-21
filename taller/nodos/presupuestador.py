from langgraph.runtime import Runtime

from ..contexto import TenantContext
from ..estado import EstadoTaller

TASA_IVA = 0.16
# Ítems para la hipótesis principal (pastillas desgastadas). Simulado: fijo, precios del catálogo.
CODIGO_REPUESTO = "FRE-PAS-DEL"
CODIGO_MANO_DE_OBRA = "MO-FRENOS"


def presupuestador(estado: EstadoTaller, runtime: Runtime[TenantContext]) -> EstadoTaller:
    """Arma el presupuesto con el catálogo y los márgenes del taller (runtime.context).

    Simulado: la primera pasada omite la mano de obra a propósito, para ejercitar el ciclo con el
    Evaluador; si hay retroalimentaciones, la agrega.
    """
    contexto = runtime.context
    if contexto is None:
        raise ValueError("El presupuestador necesita un TenantContext: invoca el grafo con context=")

    retroalimentaciones = estado.get("retroalimentaciones", [])
    codigos = [CODIGO_REPUESTO] + ([CODIGO_MANO_DE_OBRA] if retroalimentaciones else [])
    items = []
    for codigo in codigos:
        item = contexto.item(codigo)
        precio = contexto.precio_cliente(item)
        items.append(
            {
                "descripcion": item.descripcion,
                "categoria": item.categoria,
                "cantidad": 1,
                "precio_unitario": precio,
                "subtotal": precio,
            }
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
            "correcciones_aplicadas": len(retroalimentaciones),
        }
    }
