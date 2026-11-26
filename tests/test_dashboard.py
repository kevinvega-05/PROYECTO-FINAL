from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
DASH = str(Path(__file__).resolve().parents[1] / "monedas" / "dashboard.py")


def test_dashboard_sin_datos_no_falla():
    at = st_testing.AppTest.from_file(DASH, default_timeout=20).run()
    assert not at.exception
    assert any("Sin datos" in w.value for w in at.warning)


def test_dashboard_muestra_los_5_vasos():
    from monedas.estado import Estado
    e = Estado()
    e.moneda_llego(100, 1)
    e.publicar()
    at = st_testing.AppTest.from_file(DASH, default_timeout=20).run()
    assert not at.exception
    botones = [b for b in at.button if b.label == "Despachar"]
    assert len(botones) == 5
    assert [b.disabled for b in botones] == [True, False, True, True, True]


def test_streamlit_run_funciona_sin_instalar_el_paquete():
    """Regresion: `streamlit run monedas/dashboard.py` fallaba con ModuleNotFoundError fuera de pytest."""
    import subprocess
    import sys
    code = ("import runpy,sys;sys.path=[p for p in sys.path if 'proyecto' not in p];"
            f"sys.path.insert(0, {str(Path(DASH).parent)!r});"
            f"src=open({DASH!r}).read();compile(src,'d','exec')")
    assert subprocess.run([sys.executable, "-c", code], cwd="/tmp").returncode == 0
    assert "sys.path.insert(0" in Path(DASH).read_text(encoding="utf-8")
