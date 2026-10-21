import os
import subprocess
import sys
from pathlib import Path

import pytest

from taller.config import MARCADOR_ANTHROPIC_API_KEY, anthropic_api_key_configurada

RAIZ = Path(__file__).parent.parent


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("", False), ("   ", False), (MARCADOR_ANTHROPIC_API_KEY, False), ("sk-ant-api03-abc", True)],
    ids=["vacia", "espacios", "marcador", "real"],
)
def test_anthropic_api_key_configurada(monkeypatch, valor, esperado):
    monkeypatch.setenv("ANTHROPIC_API_KEY", valor)

    assert anthropic_api_key_configurada() is esperado


@pytest.mark.parametrize("valor", ["", MARCADOR_ANTHROPIC_API_KEY], ids=["falta", "marcador"])
def test_main_falla_al_arrancar_sin_key_real(valor):
    # La variable de entorno gana sobre .env (load_dotenv no sobrescribe), así no depende del .env local.
    entorno = {**os.environ, "ANTHROPIC_API_KEY": valor, "LANGSMITH_TRACING": "false"}

    proceso = subprocess.run(
        [sys.executable, "main.py"], cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding="utf-8"
    )

    assert proceso.returncode == 1
    assert "ANTHROPIC_API_KEY falta o es el marcador" in proceso.stderr
    assert "sintoma" not in proceso.stdout  # no llegó a invocar el grafo
