"""Uso: uv run python main.py ["mensaje del cliente"] [--escenario {normal,aprobado,motivo_repetido,...}]"""

import argparse
import sys
from pprint import pprint

from taller import config
from taller.contexto import cargar_contexto
from taller.escenarios import ESCENARIOS
from taller.grafo import construir_grafo

SINTOMA_POR_DEFECTO = "Rechinido metálico al frenar en el eje delantero"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows usa cp1252 por defecto
    parser = argparse.ArgumentParser(description="Ejecuta el grafo del taller.")
    parser.add_argument("sintoma", nargs="?", default=SINTOMA_POR_DEFECTO, help="mensaje del cliente")
    parser.add_argument(
        "--escenario",
        choices=ESCENARIOS,
        default="normal",
        help="guion del Evaluador para mostrar un recorrido del ciclo (por defecto: regla simulada)",
    )
    argumentos = parser.parse_args()
    if not config.anthropic_api_key_configurada():
        sys.exit(
            "Error: ANTHROPIC_API_KEY falta o es el marcador de .env.example. "
            "Pon tu key real en .env antes de ejecutar."
        )

    grafo = construir_grafo(decidir_evaluacion=ESCENARIOS[argumentos.escenario])
    recorrido, estado_final = [], {}
    for modo, datos in grafo.stream(
        {
            "sintoma": argumentos.sintoma,
            "retroalimentaciones": [],
            "intentos": 0,
            "decision_humana": None,
        },
        context=cargar_contexto(),
        config={"run_name": f"taller-lg-003-{argumentos.escenario}"},
        stream_mode=["updates", "values"],
    ):
        if modo == "updates":
            recorrido.extend(datos)
        else:
            estado_final = datos

    print(f"Escenario: {argumentos.escenario}")
    print("Recorrido:", " -> ".join(recorrido))
    pprint(estado_final, sort_dicts=False)


if __name__ == "__main__":
    main()
