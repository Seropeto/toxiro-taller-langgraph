"""Revisión humana: preparar_revision arma el paquete; revision_humana pausa con interrupt y aplica la decisión."""

from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, model_validator

from ..contexto import TenantContext, aviso_cambio_de_version
from ..estado import AccionSupervisor, EstadoTaller
from ..ruteo import decidir_ruta


class DecisionSupervisor(BaseModel):
    # Un campo desconocido (p. ej. "instrucion") se rechaza en vez de ignorarse en silencio.
    model_config = ConfigDict(extra="forbid")

    accion: AccionSupervisor
    # Obligatoria y no vacía si la acción es corregir; prohibida en los otros casos.
    instruccion: str | None = None
    revisor: str

    @model_validator(mode="after")
    def _coherente_con_la_accion(self) -> "DecisionSupervisor":
        if not self.revisor.strip():
            raise ValueError("revisor es obligatorio")
        if self.accion == "corregir" and (self.instruccion is None or not self.instruccion.strip()):
            raise ValueError("instruccion es obligatoria y no puede venir vacía cuando la acción es corregir")
        if self.accion != "corregir" and self.instruccion is not None:
            raise ValueError(f"instruccion debe ser None cuando la acción es {self.accion}")
        return self


def version_inicial_del_caso(config: RunnableConfig) -> str | None:
    """Versión del TenantContext guardada en los metadatos del hilo al iniciar el caso."""
    return (config.get("metadata") or {}).get("version_contexto")


def preparar_revision(estado: EstadoTaller, runtime: Runtime[TenantContext], config: RunnableConfig) -> EstadoTaller:
    """Escribe la causa de la escalada y arma el paquete para el supervisor.

    La causa sale de la misma regla que eligió el borde: el estado no cambia entre el borde y este nodo.
    """
    causa = decidir_ruta(estado).causa
    paquete = {
        "sintoma": estado["sintoma"],
        "hipotesis": estado["hipotesis"],
        "presupuesto": estado["presupuesto"],
        "evaluacion": estado["evaluacion"],
        "retroalimentaciones": estado.get("retroalimentaciones", []),
        "causa_escalada": causa,
        "aviso_version_contexto": aviso_cambio_de_version(
            version_inicial_del_caso(config), runtime.context.version
        ),
    }
    return {"causa_escalada": causa, "paquete_revision": paquete}


def revision_humana(estado: EstadoTaller, runtime: Runtime[TenantContext], config: RunnableConfig) -> EstadoTaller:
    """Pausa el caso hasta la decisión del supervisor y la aplica.

    Al reanudar, LangGraph ejecuta este nodo desde el principio: antes del interrupt solo se lee el
    paquete ya guardado, así que repetirlo no tiene efecto. Sin try/except alrededor del interrupt:
    internamente es una excepción y atraparla rompería la pausa.
    """
    valor = interrupt(estado["paquete_revision"])

    # La capa de casos ya validó la decisión; se vuelve a validar por si alguien reanuda sin pasar por ella.
    decision = DecisionSupervisor.model_validate(valor)
    actualizacion: EstadoTaller = {
        "decision_humana": decision.model_dump(),
        "aviso_version_contexto": aviso_cambio_de_version(version_inicial_del_caso(config), runtime.context.version),
    }
    if decision.accion == "aprobar":
        actualizacion["resultado_final"] = "aprobado"
    elif decision.accion == "cancelar":
        actualizacion["resultado_final"] = "cancelado"
    else:
        # No reinicia intentos: si el Evaluador vuelve a rechazar con el máximo agotado, se escala otra vez.
        actualizacion["retroalimentaciones"] = [{"motivo": "instruccion_supervisor", "detalle": decision.instruccion}]
    return actualizacion
