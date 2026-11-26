from monedas import clases as mc
from monedas import config as cfg
from monedas import vision as vm
from monedas.tipos import DENOMINACIONES, N_TIPOS, TIPOS


def test_hay_9_clases_y_5_vasos():
    assert N_TIPOS == 9
    assert sorted(cfg.CUBICULO_DE_VALOR) == list(DENOMINACIONES)
    assert sorted(cfg.CUBICULO_DE_VALOR.values()) == [0, 1, 2, 3, 4]


def test_cada_clase_tiene_vaso():
    for t in TIPOS:
        assert t["valor"] in cfg.CUBICULO_DE_VALOR
        assert t["id"] in cfg.IDS_DE_VALOR[t["valor"]]
        assert cfg.VALOR_DE_TIPO_ID[t["id"]] == t["valor"]


def test_actual_y_antigua_van_al_mismo_vaso():
    for valor, ids in cfg.IDS_DE_VALOR.items():
        assert len(set(cfg.cubiculo_de_valor(cfg.VALOR_DE_TIPO_ID[i]) for i in ids)) == 1


def test_moneda_no_reconocida_no_tiene_vaso():
    assert cfg.cubiculo_de_valor(None) is None
    assert cfg.cubiculo_de_valor(777) is None


def test_claves_ida_y_vuelta():
    for valor in DENOMINACIONES:
        for antigua in (False, True):
            c = mc.clave(valor, antigua)
            assert mc.valor_de(c) == valor
            assert mc.es_antigua(c) == antigua
            assert mc.tipo_id(c) == f"{valor}_{'antigua' if antigua else 'actual'}"
    assert mc.valor_de(None) is None


def test_instalar_deja_9_clases_en_vision():
    mc.instalar()
    mc.instalar()                                   # idempotente
    assert len(vm.MONEDAS) == 9
    assert vm.pesos(mc.clave(500, True)) == "$500 ant"
    assert vm.pesos(1000) == "$1.000"
    assert vm.pesos(10_000_000 - 1) == "$9.999.999"  # totales grandes no se confunden con una clave


def test_pares_confundibles_documentados():
    mc.instalar()
    pares = {(vm.pesos(a), vm.pesos(b)) for a, b, _, _ in mc.pares_confundibles()}
    assert ("$100 ant", "$500 ant") in pares or ("$500 ant", "$100 ant") in pares


def test_variables_de_entorno_sobreescriben(monkeypatch):
    import importlib
    monkeypatch.setenv("MONEDAS_BANDA_PCT", "55")
    monkeypatch.setenv("MONEDAS_SERVO_INMEDIATO", "false")
    importlib.reload(cfg)
    try:
        assert cfg.BANDA_PCT == 55 and cfg.SERVO_INMEDIATO is False
    finally:
        monkeypatch.delenv("MONEDAS_BANDA_PCT")
        monkeypatch.delenv("MONEDAS_SERVO_INMEDIATO")
        importlib.reload(cfg)
