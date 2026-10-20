from ..estado import EstadoTaller


def diagnostico(estado: EstadoTaller) -> EstadoTaller:
    """Genera hipótesis de causa a partir del síntoma. Simulado con datos fijos."""
    return {
        "hipotesis": [
            {"causa": "Pastillas de freno desgastadas", "probabilidad": 0.7, "urgencia": "alta"},
            {"causa": "Disco de freno rayado", "probabilidad": 0.2, "urgencia": "media"},
            {"causa": "Calibrador agarrotado", "probabilidad": 0.1, "urgencia": "media"},
        ]
    }
