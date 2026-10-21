"""Configuración cargada desde variables de entorno (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()

# Reintentos del ciclo Evaluador -> Presupuestador: el Presupuestador corre como máximo MAX_REINTENTOS + 1 veces.
MAX_REINTENTOS: int = int(os.getenv("MAX_REINTENTOS", "2"))

# Supersteps del peor caso (escalada por máximo de reintentos): la entrada cuenta como un paso,
# luego router y diagnostico, presupuestador + evaluador en cada pasada, y escalar.
PASOS_PEOR_CASO: int = 1 + 2 + 2 * (MAX_REINTENTOS + 1) + 1
# El valor por defecto de langgraph 1.2.16 es 10007: un error en el ruteo daría miles de vueltas.
LIMITE_RECURSION: int = PASOS_PEOR_CASO + 5

# Versión fija (no alias) para comparar con producción y tener tests de integración reproducibles.
MODELO_ROUTER: str = os.getenv("MODELO_ROUTER", "claude-haiku-4-5-20251001")

# Valor de ejemplo de .env.example; no es una key real.
MARCADOR_ANTHROPIC_API_KEY = "sk-ant-..."


def anthropic_api_key_configurada() -> bool:
    """True si ANTHROPIC_API_KEY existe y no es el marcador de .env.example."""
    valor = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return bool(valor) and valor != MARCADOR_ANTHROPIC_API_KEY
