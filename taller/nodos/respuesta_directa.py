from ..estado import EstadoTaller, OrigenIntencion

MENSAJE_FUERA_DE_ALCANCE = (
    "Solo podemos ayudarte con fallas o síntomas de tu vehículo. "
    "Para otras consultas, comunícate con la recepción del taller."
)
MENSAJE_REFORMULAR = (
    "No pudimos entender tu consulta. ¿Puedes describir de nuevo el problema de tu vehículo?"
)
MENSAJE_SERVICIO_NO_DISPONIBLE = (
    "Nuestro asistente no está disponible en este momento. Intenta de nuevo en unos minutos."
)

MENSAJES: dict[OrigenIntencion, str] = {
    "llm": MENSAJE_FUERA_DE_ALCANCE,
    "respaldo_contenido": MENSAJE_REFORMULAR,
    "respaldo_servicio": MENSAJE_SERVICIO_NO_DISPONIBLE,
}


def respuesta_directa(estado: EstadoTaller) -> EstadoTaller:
    """Responde sin diagnosticar. Simulado: el mensaje depende de quién fijó la intención."""
    return {
        "mensaje_respuesta": MENSAJES[estado.get("origen_intencion", "llm")],
        "resultado_final": "fuera_de_alcance",
    }
