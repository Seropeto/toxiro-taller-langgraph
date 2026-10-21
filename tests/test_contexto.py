import pytest
from langgraph.runtime import Runtime

from taller.contexto import RUTA_EJEMPLO_V2, ItemCatalogo, TenantContext, aviso_cambio_de_version, cargar_contexto
from taller.nodos import presupuestador

CONTEXTO_PRUEBA = TenantContext(
    nombre_taller="Taller de Prueba",
    version="prueba-1",
    catalogo=(
        ItemCatalogo("FRE-PAS-DEL", "Pastillas marca Prueba", "repuestos", 1000.0),
        ItemCatalogo("MO-FRENOS", "Mano de obra Prueba", "mano_de_obra", 300.0),
    ),
    margenes={"repuestos": 0.5, "mano_de_obra": 0.0},
)
RETROALIMENTACION = {"motivo": "item_omitido", "detalle": "Falta la mano de obra."}


def test_presupuestador_lee_el_catalogo_de_runtime_context():
    presupuesto = presupuestador({"sintoma": "x"}, Runtime(context=CONTEXTO_PRUEBA))["presupuesto"]

    assert presupuesto["taller"] == "Taller de Prueba"
    (pastillas,) = presupuesto["items"]  # primera pasada: sin mano de obra
    assert pastillas["descripcion"] == "Pastillas marca Prueba"
    assert pastillas["categoria"] == "repuestos"
    assert pastillas["precio_unitario"] == 1500.0  # 1000 + 50 % de margen de repuestos
    assert presupuesto["correcciones_aplicadas"] == 0


def test_presupuestador_agrega_mano_de_obra_si_hay_retroalimentacion():
    estado = {"sintoma": "x", "retroalimentaciones": [RETROALIMENTACION]}

    presupuesto = presupuestador(estado, Runtime(context=CONTEXTO_PRUEBA))["presupuesto"]

    assert [item["categoria"] for item in presupuesto["items"]] == ["repuestos", "mano_de_obra"]
    assert presupuesto["subtotal"] == 1800.0
    assert presupuesto["correcciones_aplicadas"] == 1


def test_presupuestador_cuenta_todas_las_retroalimentaciones():
    estado = {"sintoma": "x", "retroalimentaciones": [RETROALIMENTACION, RETROALIMENTACION]}

    presupuesto = presupuestador(estado, Runtime(context=CONTEXTO_PRUEBA))["presupuesto"]

    assert presupuesto["correcciones_aplicadas"] == 2


def test_presupuestador_sin_contexto_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="context="):
        presupuestador({"sintoma": "x"}, Runtime(context=None))


def test_contexto_de_ejemplo_carga_catalogo(contexto):
    assert contexto.nombre_taller
    assert contexto.version == "2026.10.1"
    assert 3 <= len(contexto.catalogo) <= 5
    assert {item.categoria for item in contexto.catalogo} <= set(contexto.margenes)


def test_contexto_v2_es_el_mismo_taller_con_otra_version(contexto):
    v2 = cargar_contexto(RUTA_EJEMPLO_V2)

    assert v2.nombre_taller == contexto.nombre_taller
    assert v2.version != contexto.version


def test_aviso_cambio_de_version():
    assert aviso_cambio_de_version("2026.10.1", "2026.10.1") is None
    assert aviso_cambio_de_version(None, "2026.10.1") is None  # caso sin versión registrada: no se avisa
    aviso = aviso_cambio_de_version("2026.10.1", "2026.11.0")
    assert "2026.10.1 -> 2026.11.0" in aviso
