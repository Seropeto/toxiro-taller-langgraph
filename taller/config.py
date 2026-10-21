"""Configuración cargada desde variables de entorno (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()

MAX_REINTENTOS: int = int(os.getenv("MAX_REINTENTOS", "2"))

# Versión fija (no alias) para comparar con producción y tener tests de integración reproducibles.
MODELO_ROUTER: str = os.getenv("MODELO_ROUTER", "claude-haiku-4-5-20251001")

# Valor de ejemplo de .env.example; no es una key real.
MARCADOR_ANTHROPIC_API_KEY = "sk-ant-..."


def anthropic_api_key_configurada() -> bool:
    """True si ANTHROPIC_API_KEY existe y no es el marcador de .env.example."""
    valor = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return bool(valor) and valor != MARCADOR_ANTHROPIC_API_KEY
