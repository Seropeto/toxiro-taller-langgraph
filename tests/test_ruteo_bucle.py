"""Regla de ruteo del ciclo, paso por paso, sin ejecutar el grafo."""

import pytest

from taller import config
from taller.grafo import construir_grafo
from taller.nodos import escalar
from taller.ruteo import Decision, decidir_ruta, rutear_por_veredicto


def estado(veredicto, motivos=(), intentos=None, motivo_actual=None):
    """Estado tal como lo deja el Evaluador: si rechazó, el rechazo actual ya está al final de la lista."""
    retroalimentaciones = [{"motivo": m, "detalle": f"Rechazo por {m}."} for m in motivos]
    return {
        "sintoma": "x",
        "evaluacion": {"veredicto": veredicto, "motivo": motivo_actual, "detalle": "d"},
        "retroalimentaciones": retroalimentaciones,
        "intentos": len(retroalimentaciones) if intentos is None else intentos,
    }


def test_paso_1_aprobado_termina():
    assert decidir_ruta(estado("aprobado", ["item_omitido"])) == Decision("fin")


def test_paso_2_escalar_por_decision_del_evaluador():
    assert decidir_ruta(estado("escalar")) == Decision("escalar", "decision_evaluador")


def test_paso_3_mismo_motivo_que_el_rechazo_anterior_escala():
    assert decidir_ruta(estado("rechazado", ["item_omitido", "item_omitido"])) == Decision(
        "escalar", "motivo_repetido"
    )


def test_paso_4_superar_el_maximo_de_reintentos_escala():
    motivos = ["item_omitido", "margen_incorrecto", "item_duplicado"]  # intentos = 3 > MAX_REINTENTOS = 2

    assert decidir_ruta(estado("rechazado", motivos)) == Decision("escalar", "maximo_reintentos")


def test_paso_5_otro_rechazo_vuelve_al_presupuestador():
    assert decidir_ruta(estado("rechazado", ["item_omitido"])) == Decision("presupuestador")


def test_paso_3_gana_sobre_paso_4_si_se_cumplen_ambos():
    motivos = ["item_omitido", "margen_incorrecto", "margen_incorrecto"]  # repetido y además intentos = 3

    assert decidir_ruta(estado("rechazado", motivos)).causa == "motivo_repetido"


def test_motivo_repetido_no_consecutivo_no_cuenta_como_repetido():
    motivos = ["item_omitido", "margen_incorrecto", "item_omitido"]

    assert decidir_ruta(estado("rechazado", motivos)).causa == "maximo_reintentos"


def test_intentos_igual_al_maximo_todavia_reintenta():
    motivos = ["item_omitido", "margen_incorrecto"]  # intentos = 2 = MAX_REINTENTOS: no es mayor

    assert decidir_ruta(estado("rechazado", motivos)) == Decision("presupuestador")


def test_el_maximo_sale_de_config(monkeypatch):
    monkeypatch.setattr(config, "MAX_REINTENTOS", 0)

    assert decidir_ruta(estado("rechazado", ["item_omitido"])).causa == "maximo_reintentos"


def test_rutear_por_veredicto_devuelve_el_destino_de_la_regla():
    assert rutear_por_veredicto(estado("aprobado")) == "fin"
    assert rutear_por_veredicto(estado("escalar")) == "escalar"
    assert rutear_por_veredicto(estado("rechazado", ["item_omitido"])) == "presupuestador"


def test_cada_destino_lleva_a_su_nodo():
    aristas = construir_grafo().get_graph().edges
    ramas = {(a.data or a.target): a.target for a in aristas if a.source == "evaluador" and a.conditional}

    assert ramas == {"fin": "__end__", "escalar": "escalar", "presupuestador": "presupuestador"}


@pytest.mark.parametrize(
    ("estado_al_escalar", "causa"),
    [
        (estado("escalar"), "decision_evaluador"),
        (estado("rechazado", ["item_omitido", "item_omitido"]), "motivo_repetido"),
        (estado("rechazado", ["item_omitido", "margen_incorrecto", "item_duplicado"]), "maximo_reintentos"),
    ],
    ids=["decision_evaluador", "motivo_repetido", "maximo_reintentos"],
)
def test_escalar_registra_la_causa_de_la_regla(estado_al_escalar, causa):
    assert escalar(estado_al_escalar) == {"resultado_final": "escalado", "causa_escalada": causa}
