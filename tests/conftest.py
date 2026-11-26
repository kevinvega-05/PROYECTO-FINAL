"""Aisla los archivos de trabajo (estado.json, comando.json, calibracion...) en una carpeta temporal."""
import os
import sys
import tempfile

_DATOS = tempfile.mkdtemp(prefix="monedas_tests_")
os.environ["MONEDAS_DATOS"] = _DATOS
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def datos_limpios():
    """Cada prueba empieza sin estado.json / comando.json / registro."""
    for nombre in os.listdir(_DATOS):
        try:
            os.remove(os.path.join(_DATOS, nombre))
        except OSError:
            pass
    yield _DATOS
