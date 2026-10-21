"""Uso:
    uv run python main.py ["mensaje del cliente"] [--escenario E] [--contexto RUTA]   caso nuevo
    uv run python main.py --historial THREAD_ID                                       historial de un caso
    uv run python main.py --retomar THREAD_ID [--contexto RUTA]                       retomar un caso que falló

Demostración de recuperación: abrir un caso con --contexto taller/datos/tenant_sin_pastillas.json
(el Presupuestador falla) y retomarlo con el catálogo por defecto.
"""

import argparse
import sys
from pathlib import Path
from pprint import pprint

from langgraph.checkpoint.sqlite import SqliteSaver

from taller import config
from taller.casos import (
    ErrorDeCaso,
    Ejecucion,
    historial_caso,
    iniciar_caso,
    metadatos_caso,
    nuevo_thread_id,
    pendientes_caso,
    retomar_caso,
)
from taller.contexto import RUTA_EJEMPLO, cargar_contexto
from taller.escenarios import ESCENARIOS
from taller.grafo import construir_grafo

SINTOMA_POR_DEFECTO = "Rechinido metálico al frenar en el eje delantero"


def leer_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta y consulta casos del taller.")
    parser.add_argument("sintoma", nargs="?", default=SINTOMA_POR_DEFECTO, help="mensaje del cliente")
    parser.add_argument(
        "--escenario",
        choices=ESCENARIOS,
        help="guion del Evaluador para un caso nuevo (por defecto: normal, la regla simulada)",
    )
    parser.add_argument(
        "--contexto", type=Path, default=RUTA_EJEMPLO, help="archivo JSON del taller (TenantContext)"
    )
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--historial", metavar="THREAD_ID", help="muestra el historial de un caso")
    modo.add_argument("--retomar", metavar="THREAD_ID", help="retoma un caso que falló")
    return parser.parse_args()


def exigir_api_key() -> None:
    if not config.anthropic_api_key_configurada():
        sys.exit(
            "Error: ANTHROPIC_API_KEY falta o es el marcador de .env.example. "
            "Pon tu key real en .env antes de ejecutar."
        )


def imprimir_ejecucion(ejecucion: Ejecucion, escenario: str) -> None:
    print(f"Escenario: {escenario}")
    print("Recorrido:", " -> ".join(ejecucion.nodos))
    pprint(ejecucion.estado, sort_dicts=False)


def imprimir_historial(saver, thread_id: str) -> None:
    grafo = construir_grafo(checkpointer=saver)
    escenario = metadatos_caso(grafo, thread_id).get("escenario", "?")
    print(f"Caso {thread_id} (escenario: {escenario})")
    print(f"{'paso':>4}  {'origen':6}  {'ejecutado':17}  {'siguiente':17}  {'intentos':>8}  {'resultado':10}  motivos")
    for paso in historial_caso(grafo, thread_id):
        motivos = [r["motivo"] for r in paso.retroalimentaciones]
        print(
            f"{paso.paso:>4}  {paso.origen:6}  {', '.join(paso.ejecutado) or '-':17}  "
            f"{', '.join(paso.siguiente) or '-':17}  {paso.intentos:>8}  {paso.resultado_final or '-':10}  {motivos}"
        )


def abrir_caso(saver, argumentos: argparse.Namespace) -> None:
    escenario = argumentos.escenario or "normal"
    grafo = construir_grafo(ESCENARIOS[escenario], checkpointer=saver)
    thread_id = nuevo_thread_id()
    print(f"Caso: {thread_id}")
    entrada = {"sintoma": argumentos.sintoma, "retroalimentaciones": [], "intentos": 0, "decision_humana": None}
    try:
        ejecucion = iniciar_caso(
            grafo,
            entrada,
            cargar_contexto(argumentos.contexto),
            thread_id=thread_id,
            metadatos={"escenario": escenario},
            run_name=f"taller-lg-004-{escenario}",
        )
    except ErrorDeCaso:
        raise
    except Exception as error:  # la falla de un nodo: el caso queda guardado hasta el paso anterior
        pendientes = ", ".join(pendientes_caso(grafo, thread_id))
        sys.exit(
            f"El caso falló en {pendientes}: {type(error).__name__}: {error}\n"
            f"Quedó guardado hasta el paso anterior. Retómalo con:\n"
            f"    uv run python main.py --retomar {thread_id}"
        )
    imprimir_ejecucion(ejecucion, escenario)


def retomar(saver, argumentos: argparse.Namespace) -> None:
    thread_id = argumentos.retomar
    # La decisión del Evaluador es código, no estado: se reconstruye con el escenario guardado en el caso.
    escenario = metadatos_caso(construir_grafo(checkpointer=saver), thread_id)["escenario"]
    if argumentos.escenario and argumentos.escenario != escenario:
        sys.exit(f"Error: el caso {thread_id} se abrió con --escenario {escenario}, no {argumentos.escenario}.")
    grafo = construir_grafo(ESCENARIOS[escenario], checkpointer=saver)
    if pendientes := pendientes_caso(grafo, thread_id):
        print(f"Retomando caso {thread_id} desde: {', '.join(pendientes)}")
    ejecucion = retomar_caso(
        grafo, thread_id, cargar_contexto(argumentos.contexto), run_name=f"taller-lg-004-{escenario}-retomado"
    )
    imprimir_ejecucion(ejecucion, escenario)


def main() -> None:
    # La consola de Windows usa cp1252 por defecto; stderr también, porque sys.exit(mensaje) escribe ahí.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    argumentos = leer_argumentos()
    if not argumentos.historial:
        exigir_api_key()

    with SqliteSaver.from_conn_string(config.RUTA_BASE_CASOS) as saver:
        try:
            if argumentos.historial:
                imprimir_historial(saver, argumentos.historial)
            elif argumentos.retomar:
                retomar(saver, argumentos)
            else:
                abrir_caso(saver, argumentos)
        except ErrorDeCaso as error:
            sys.exit(f"Error: {error}")


if __name__ == "__main__":
    main()
