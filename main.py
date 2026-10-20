import sys
from pprint import pprint

from taller import config  # noqa: F401  (carga .env antes de construir el grafo)
from taller.grafo import construir_grafo


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252 por defecto
    grafo = construir_grafo()
    estado_final = grafo.invoke(
        {
            "sintoma": "Rechinido metálico al frenar en el eje delantero",
            "retroalimentaciones": [],
            "intentos": 0,
            "decision_humana": None,
        },
        config={"run_name": "taller-lg-001"},
    )
    pprint(estado_final, sort_dicts=False)


if __name__ == "__main__":
    main()
