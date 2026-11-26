import json

from monedas import clases as mc
from monedas import config as cfg
from monedas.estado import Estado


def test_moneda_llego_cuenta_por_vaso_y_tipo():
    e = Estado()
    e.en_camino = 3
    e.moneda_llego(500, 3)
    e.moneda_llego(mc.clave(500, True), 3)            # antigua: mismo vaso
    e.moneda_llego(1000, 4)
    assert e.cantidad_vaso(500) == 2 and e.cantidad_vaso(1000) == 1
    assert e.total == 3 and e.valor == 2000
    assert e.cubiculos["500_antigua"]["cantidad"] == 1 and e.cubiculos["500_actual"]["cantidad"] == 1
    assert e.en_camino == 0


def test_moneda_no_reconocida_va_al_rechazo():
    e = Estado()
    e.moneda_llego(None, None)
    assert e.rechazadas == 1 and e.total == 0


def test_publicar_escribe_el_contrato():
    e = Estado()
    e.moneda_llego(100, 1)
    est = e.publicar()
    with open(cfg.ESTADO_PATH, encoding="utf-8") as fh:
        disco = json.load(fh)
    assert disco["cantidad_total"] == est["cantidad_total"] == 1
    for k in ("t", "etapa", "ultimo_evento", "monedas", "valor", "peso_g", "cubiculos", "vasos", "carro",
              "rechazo", "banda", "canaleta", "conexiones"):
        assert k in disco
    assert set(disco["vasos"]) == {"50", "100", "200", "500", "1000"}
    assert disco["carro"]["estado"] == "en reposo"


def test_vaso_vacio_no_aparece_despachado():
    e = Estado()
    e.moneda_llego(100, 1)
    e.marcar_despachado(100)
    v = e.instantanea()["vasos"]
    assert v["100"]["despachado"] is True
    assert v["50"]["despachado"] is False and v["50"]["cantidad"] == 0
    e.moneda_llego(100, 1)                            # llegan monedas nuevas: vuelve a estar disponible
    assert e.instantanea()["vasos"]["100"]["despachado"] is False


def test_reiniciar_conteo():
    e = Estado()
    e.moneda_llego(100, 1)
    e.reiniciar_conteo()
    assert e.total == 0 and e.cantidad_vaso(100) == 0
