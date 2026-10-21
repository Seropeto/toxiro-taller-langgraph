"""Router con Haiku real. No corre por defecto.

Para correrlo a mano (requiere ANTHROPIC_API_KEY en .env):
    uv run pytest -m integracion -v
"""

import pytest

from taller import config
from taller.nodos import router

pytestmark = [
    pytest.mark.integracion,
    pytest.mark.skipif(
        not config.anthropic_api_key_configurada(),
        reason="Falta ANTHROPIC_API_KEY real en el entorno o en .env",
    ),
]


@pytest.mark.parametrize(
    ("mensaje", "intencion"),
    [
        ("Rechinido metálico al frenar en el eje delantero", "diagnostico"),
        ("El motor se apaga solo cuando paro en un semáforo", "diagnostico"),
        ("¿A qué hora cierran el sábado?", "fuera_de_alcance"),
    ],
)
def test_router_clasifica_con_haiku(mensaje, intencion):
    resultado = router({"sintoma": mensaje})

    assert resultado == {"intencion": intencion, "origen_intencion": "llm"}
