import pytest
from pydantic import ValidationError

from taller.nodos.evaluador import SalidaEvaluador, crear_evaluador, evaluar_mano_de_obra


def presupuesto_con(*categorias):
    return {"presupuesto": {"items": [{"categoria": c} for c in categorias]}}


@pytest.mark.parametrize(
    "datos",
    [
        {"veredicto": "aprobado", "detalle": "ok"},
        {"veredicto": "aprobado", "detalle": ""},  # al aprobar, el detalle puede venir vacío
        {"veredicto": "rechazado", "motivo": "item_omitido", "detalle": "Falta mano de obra."},
        {"veredicto": "escalar", "detalle": "Caso ambiguo."},
    ],
    ids=["aprobado", "aprobado_sin_detalle", "rechazado", "escalar"],
)
def test_salidas_validas(datos):
    SalidaEvaluador(**datos)


@pytest.mark.parametrize(
    ("datos", "error"),
    [
        ({"veredicto": "rechazado", "detalle": "Falta algo."}, "motivo es obligatorio"),
        ({"veredicto": "aprobado", "motivo": "item_omitido", "detalle": "ok"}, "motivo debe ser None"),
        ({"veredicto": "escalar", "motivo": "item_omitido", "detalle": "x"}, "motivo debe ser None"),
        ({"veredicto": "rechazado", "motivo": "item_omitido", "detalle": "  "}, "detalle no puede venir vacío"),
        ({"veredicto": "escalar", "detalle": ""}, "detalle no puede venir vacío"),
        ({"veredicto": "rechazado", "motivo": "precio_alto", "detalle": "x"}, "motivo"),
        ({"veredicto": "rechazado", "motivo": "instruccion_supervisor", "detalle": "x"}, "motivo"),
        ({"veredicto": "pendiente", "detalle": "x"}, "veredicto"),
    ],
    ids=[
        "rechazado_sin_motivo",
        "aprobado_con_motivo",
        "escalar_con_motivo",
        "rechazado_detalle_vacio",
        "escalar_detalle_vacio",
        "motivo_fuera_del_conjunto",
        "motivo_del_supervisor",
        "veredicto_fuera_del_conjunto",
    ],
)
def test_salidas_invalidas(datos, error):
    with pytest.raises(ValidationError, match=error):
        SalidaEvaluador(**datos)


def test_regla_simulada_rechaza_sin_mano_de_obra():
    salida = evaluar_mano_de_obra(presupuesto_con("repuestos"))

    assert (salida.veredicto, salida.motivo) == ("rechazado", "item_omitido")


def test_regla_simulada_aprueba_con_mano_de_obra():
    assert evaluar_mano_de_obra(presupuesto_con("repuestos", "mano_de_obra")).veredicto == "aprobado"


def evaluador_que_responde(salida):
    return crear_evaluador(lambda _estado: salida)


def test_rechazo_incrementa_intentos_y_agrega_retroalimentacion():
    salida = SalidaEvaluador(veredicto="rechazado", motivo="item_duplicado", detalle="Pastillas dos veces.")

    actualizacion = evaluador_que_responde(salida)({"sintoma": "x", "intentos": 1})

    assert actualizacion["intentos"] == 2
    assert actualizacion["retroalimentaciones"] == [{"motivo": "item_duplicado", "detalle": "Pastillas dos veces."}]
    assert actualizacion["evaluacion"] == {
        "veredicto": "rechazado",
        "motivo": "item_duplicado",
        "detalle": "Pastillas dos veces.",
    }
    assert "resultado_final" not in actualizacion


def test_aprobado_marca_resultado_sin_tocar_intentos_ni_retroalimentaciones():
    actualizacion = evaluador_que_responde(SalidaEvaluador(veredicto="aprobado", detalle="ok"))({"sintoma": "x"})

    assert actualizacion["resultado_final"] == "aprobado"
    assert "intentos" not in actualizacion
    assert "retroalimentaciones" not in actualizacion


def test_escalar_no_toca_intentos_ni_retroalimentaciones_ni_resultado():
    salida = SalidaEvaluador(veredicto="escalar", detalle="Caso ambiguo.")

    actualizacion = evaluador_que_responde(salida)({"sintoma": "x", "intentos": 1})

    assert set(actualizacion) == {"evaluacion", "evaluaciones"}  # la causa la escribe preparar_revision


@pytest.mark.parametrize(
    "salida",
    [
        SalidaEvaluador(veredicto="aprobado", detalle="ok"),
        SalidaEvaluador(veredicto="rechazado", motivo="item_omitido", detalle="x"),
        SalidaEvaluador(veredicto="escalar", detalle="x"),
    ],
    ids=["aprobado", "rechazado", "escalar"],
)
def test_cada_evaluacion_incrementa_evaluaciones(salida):
    assert evaluador_que_responde(salida)({"sintoma": "x", "evaluaciones": 2})["evaluaciones"] == 3
