"""Uso:
    uv run python main.py ["mensaje del cliente"] [--escenario E] [--contexto RUTA]   caso nuevo
    uv run python main.py --historial THREAD_ID                                       historial de un caso
    uv run python main.py --retomar THREAD_ID [--contexto RUTA]                       retomar un caso que falló
    uv run python main.py --pendientes                                                bandeja del supervisor
    uv run python main.py --resolver THREAD_ID --accion A --revisor R [--instruccion T] [--contexto RUTA]

Demostraciones:
- Recuperación: abrir un caso con --contexto taller/datos/tenant_sin_pastillas.json (el Presupuestador
  falla) y retomarlo con el catálogo por defecto.
- Revisión humana: abrir un caso con --escenario maximo_reintentos (queda pendiente) y resolverlo.
  Con --contexto taller/datos/tenant_ejemplo_v2.json al resolver se ve el aviso de cambio de versión.
"""

import argparse
import json
import sys
from pathlib import Path
from pprint import pprint

from langgraph.checkpoint.sqlite import SqliteSaver

from taller import config
from taller.casos import (
    ErrorDeCaso,
    Ejecucion,
    casos_pendientes,
    historial_caso,
    iniciar_caso,
    metadatos_caso,
    nuevo_thread_id,
    pendientes_caso,
    resolver_revision,
    retomar_caso,
    situacion_caso,
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
    modo.add_argument("--resolver", metavar="THREAD_ID", help="resuelve la revisión humana de un caso")
    modo.add_argument("--pendientes", action="store_true", help="lista los casos pendientes de revisión")
    # Sin choices a propósito: la validación de la decisión es de la capa de casos (DecisionSupervisor).
    parser.add_argument("--accion", help="con --resolver: aprobar, corregir o cancelar")
    parser.add_argument("--instruccion", help="con --resolver --accion corregir: qué debe corregir el Presupuestador")
    parser.add_argument("--revisor", help="con --resolver: quién decide")
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
    if ejecucion.aviso_version_contexto:
        print(f"AVISO: {ejecucion.aviso_version_contexto}")
    if ejecucion.pendiente:
        print(f"Caso pendiente de revisión humana (causa: {ejecucion.paquete['causa_escalada']}). Paquete:")
        print(json.dumps(ejecucion.paquete, indent=2, ensure_ascii=False))
        print(
            "Resuélvelo con:\n"
            f"    uv run python main.py --resolver {ejecucion.thread_id} --accion aprobar --revisor NOMBRE\n"
            f'    uv run python main.py --resolver {ejecucion.thread_id} --accion corregir --instruccion "..." '
            "--revisor NOMBRE"
        )
        return
    pprint(ejecucion.estado, sort_dicts=False)


def imprimir_historial(saver, thread_id: str) -> None:
    grafo = construir_grafo(checkpointer=saver)
    metadatos = metadatos_caso(grafo, thread_id)
    print(f"Caso {thread_id} (escenario: {metadatos.get('escenario', '?')}, contexto: {metadatos.get('version_contexto', '?')})")
    print(
        f"{'paso':>4}  {'origen':6}  {'ejecutado':17}  {'siguiente':17}  {'intentos':>8}  "
        f"{'causa':18}  {'resultado':10}  motivos"
    )
    for paso in historial_caso(grafo, thread_id):
        motivos = [r["motivo"] for r in paso.retroalimentaciones]
        pausa = "  <- en pausa: pendiente de revisión" if paso.en_pausa else ""
        print(
            f"{paso.paso:>4}  {paso.origen:6}  {', '.join(paso.ejecutado) or '-':17}  "
            f"{', '.join(paso.siguiente) or '-':17}  {paso.intentos:>8}  {paso.causa_escalada or '-':18}  "
            f"{paso.resultado_final or '-':10}  {motivos}{pausa}"
        )


def imprimir_pendientes(saver) -> None:
    grafo = construir_grafo(checkpointer=saver)
    pendientes = casos_pendientes(grafo)
    print(f"Casos pendientes de revisión: {len(pendientes)}")
    for thread_id, paquete in pendientes:
        print(f"  {thread_id}  causa: {paquete['causa_escalada']:18}  síntoma: {paquete['sintoma']}")


def grafo_del_caso(saver, thread_id: str, escenario_pedido: str | None):
    """La decisión del Evaluador es código, no estado: se reconstruye con el escenario guardado en el caso."""
    escenario = metadatos_caso(construir_grafo(checkpointer=saver), thread_id)["escenario"]
    if escenario_pedido and escenario_pedido != escenario:
        sys.exit(f"Error: el caso {thread_id} se abrió con --escenario {escenario}, no {escenario_pedido}.")
    return construir_grafo(ESCENARIOS[escenario], checkpointer=saver), escenario


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
            run_name=f"taller-lg-005-{escenario}",
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
    grafo, escenario = grafo_del_caso(saver, thread_id, argumentos.escenario)
    if situacion_caso(grafo, thread_id) == "fallado":
        print(f"Retomando caso {thread_id} desde: {', '.join(pendientes_caso(grafo, thread_id))}")
    ejecucion = retomar_caso(
        grafo, thread_id, cargar_contexto(argumentos.contexto), run_name=f"taller-lg-005-{escenario}-retomado"
    )
    imprimir_ejecucion(ejecucion, escenario)


def resolver(saver, argumentos: argparse.Namespace) -> None:
    thread_id = argumentos.resolver
    grafo, escenario = grafo_del_caso(saver, thread_id, argumentos.escenario)
    decision = {
        clave: valor
        for clave, valor in (
            ("accion", argumentos.accion),
            ("instruccion", argumentos.instruccion),
            ("revisor", argumentos.revisor),
        )
        if valor is not None
    }
    print(f"Resolviendo revisión del caso {thread_id}: {decision}")
    ejecucion = resolver_revision(
        grafo, thread_id, decision, cargar_contexto(argumentos.contexto), run_name=f"taller-lg-005-{escenario}-revision"
    )
    imprimir_ejecucion(ejecucion, escenario)


def main() -> None:
    # La consola de Windows usa cp1252 por defecto; stderr también, porque sys.exit(mensaje) escribe ahí.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    argumentos = leer_argumentos()
    if not (argumentos.historial or argumentos.pendientes or argumentos.resolver):
        exigir_api_key()

    with SqliteSaver.from_conn_string(config.RUTA_BASE_CASOS) as saver:
        try:
            if argumentos.historial:
                imprimir_historial(saver, argumentos.historial)
            elif argumentos.pendientes:
                imprimir_pendientes(saver)
            elif argumentos.retomar:
                retomar(saver, argumentos)
            elif argumentos.resolver:
                resolver(saver, argumentos)
            else:
                abrir_caso(saver, argumentos)
        except ErrorDeCaso as error:
            sys.exit(f"Error: {error}")


if __name__ == "__main__":
    main()
