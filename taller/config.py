"""Configuración cargada desde variables de entorno (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()

MAX_REINTENTOS: int = int(os.getenv("MAX_REINTENTOS", "2"))
