"""Contexto de ejecución por taller (tenant). Se pasa con context=, nunca va en el estado."""

import json
from dataclasses import dataclass
from pathlib import Path

RUTA_EJEMPLO = Path(__file__).parent / "datos" / "tenant_ejemplo.json"
# Catálogo sin FRE-PAS-DEL: hace fallar al Presupuestador para demostrar el retome de un caso (LG-004).
RUTA_SIN_PASTILLAS = Path(__file__).parent / "datos" / "tenant_sin_pastillas.json"
# Mismo taller con otra versión del catálogo: demuestra el aviso de cambio de versión (LG-005).
RUTA_EJEMPLO_V2 = Path(__file__).parent / "datos" / "tenant_ejemplo_v2.json"


@dataclass(frozen=True)
class ItemCatalogo:
    codigo: str
    descripcion: str
    categoria: str
    precio: float


@dataclass(frozen=True)
class TenantContext:
    nombre_taller: str
    # Versión del catálogo y los márgenes. Se guarda en los metadatos del caso al iniciarlo.
    version: str
    catalogo: tuple[ItemCatalogo, ...]
    # Margen sobre el precio de catálogo, por categoría (0.30 = 30 %).
    margenes: dict[str, float]

    def item(self, codigo: str) -> ItemCatalogo:
        """Busca un ítem por código.

        Comportamiento simulado: un ítem faltante lanza KeyError y corta la ejecución (el caso queda
        guardado y se puede retomar). Según las reglas del negocio, un ítem faltante en el catálogo
        debería escalarse a revisión en lugar de fallar.
        """
        for item in self.catalogo:
            if item.codigo == codigo:
                return item
        raise KeyError(f"El catálogo de {self.nombre_taller} no tiene el ítem {codigo}")

    def precio_cliente(self, item: ItemCatalogo) -> float:
        return round(item.precio * (1 + self.margenes.get(item.categoria, 0.0)), 2)


def aviso_cambio_de_version(version_inicial: str | None, version_actual: str) -> str | None:
    """Función pura: el aviso si la versión del contexto cambió desde que se inició el caso; si no, None.

    No bloquea el caso: quien la usa decide dónde mostrar o registrar el aviso.
    """
    if version_inicial is None or version_inicial == version_actual:
        return None
    return (
        f"La versión del contexto cambió desde el inicio del caso: {version_inicial} -> {version_actual}. "
        "El presupuesto puede no reflejar el catálogo actual."
    )


def cargar_contexto(ruta: Path = RUTA_EJEMPLO) -> TenantContext:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return TenantContext(
        nombre_taller=datos["nombre_taller"],
        version=datos["version"],
        catalogo=tuple(ItemCatalogo(**item) for item in datos["catalogo"]),
        margenes=datos["margenes"],
    )
