"""Uso: uv run python main.py ["mensaje del cliente"]"""

import sys
from pprint import pprint

from taller import config
from taller.contexto import cargar_contexto
from taller.grafo import construir_grafo

SINTOMA_POR_DEFECTO = "Rechinido metálico al frenar en el eje delantero"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252 por defecto
    if not config.anthropic_api_key_configurada():
        sys.exit(
            "Error: ANTHROPIC_API_KEY falta o es el marcador de .env.example. "
            "Pon tu key real en .env antes de ejecutar."
        )
    sintoma = sys.argv[1] if len(sys.argv) > 1 else SINTOMA_POR_DEFECTO
    grafo = construir_grafo()
    estado_final = grafo.invoke(
        {
            "sintoma": sintoma,
            "retroalimentaciones": [],
            "intentos": 0,
            "decision_humana": None,
        },
        context=cargar_contexto(),
        config={"run_name": "taller-lg-002"},
    )
    pprint(estado_final, sort_dicts=False)


if __name__ == "__main__":
    main()
