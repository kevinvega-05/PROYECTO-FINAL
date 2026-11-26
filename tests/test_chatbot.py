import json

import pytest

from monedas import chatbot as cb
from monedas import config as cfg
from monedas.estado import Estado


@pytest.mark.parametrize("texto,esperado", [
    ("despacha el de 500", 500), ("manda el vaso de mil", 1000), ("despacha $200", 200),
    ("cincuenta", 50), ("lleva el de cien", 100), ("despacha el de 1000", 1000), ("despacha el de 1.000", 1000),
    ("quinientos", 500), ("doscientos por favor", 200), ("hola", None), ("despacha algo", None),
    ("despacha el 5000", None),
])
def test_interpretar_orden(texto, esperado):
    assert cb.interpretar_orden(texto) == esperado


def test_enviar_despacho_escribe_el_contrato():
    cb.enviar_despacho(500)
    with open(cfg.COMANDO_PATH, encoding="utf-8") as fh:
        c = json.load(fh)
    assert c["accion"] == "despachar" and c["atendido"] is False
    assert cfg.VALOR_DE_TIPO_ID[c["tipo"]] == 500


def test_responder_despacha_si_el_vaso_tiene_monedas():
    e = Estado()
    e.moneda_llego(500, 3)
    e.publicar()
    assert cb.responder("despacha el de 500", voz=False, esperar=False)
    with open(cfg.COMANDO_PATH, encoding="utf-8") as fh:
        assert json.load(fh)["atendido"] is False


def test_responder_no_despacha_vaso_vacio(capsys):
    Estado().publicar()
    cb.responder("despacha el de 200", voz=False, esperar=False)
    import os
    assert not os.path.exists(cfg.COMANDO_PATH)
    assert "vacio" in capsys.readouterr().out


def test_responder_no_despacha_si_el_carro_esta_ocupado():
    e = Estado()
    e.moneda_llego(100, 1)
    e.carro["estado"] = "recorriendo"
    e.publicar()
    import os
    cb.responder("despacha el de 100", voz=False, esperar=False)
    assert not os.path.exists(cfg.COMANDO_PATH)


def test_estado_y_vasos(capsys):
    e = Estado()
    e.moneda_llego(50, 0)
    e.publicar()
    cb.responder("estado", voz=False)
    cb.responder("vasos", voz=False)
    out = capsys.readouterr().out
    assert "1 moneda" in out and "vaso 0 ($50): 1" in out


def test_salir():
    assert cb.responder("salir", voz=False) is False
