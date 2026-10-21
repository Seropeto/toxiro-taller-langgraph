"""Contexto de ejecución por taller (tenant). Se pasa con context=, nunca va en el estado."""

import json
from dataclasses import dataclass
from pathlib import Path

RUTA_EJEMPLO = Path(__file__).parent / "datos" / "tenant_ejemplo.json"


@dataclass(frozen=True)
class ItemCatalogo:
    codigo: str
    descripcion: str
    categoria: str
    precio: float


@dataclass(frozen=True)
class TenantContext:
    nombre_taller: str
    catalogo: tuple[ItemCatalogo, ...]
    # Margen sobre el precio de catálogo, por categoría (0.30 = 30 %).
    margenes: dict[str, float]

    def item(self, codigo: str) -> ItemCatalogo:
        for item in self.catalogo:
            if item.codigo == codigo:
                return item
        raise KeyError(f"El catálogo de {self.nombre_taller} no tiene el ítem {codigo}")

    def precio_cliente(self, item: ItemCatalogo) -> float:
        return round(item.precio * (1 + self.margenes.get(item.categoria, 0.0)), 2)


def cargar_contexto(ruta: Path = RUTA_EJEMPLO) -> TenantContext:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return TenantContext(
        nombre_taller=datos["nombre_taller"],
        catalogo=tuple(ItemCatalogo(**item) for item in datos["catalogo"]),
        margenes=datos["margenes"],
    )
