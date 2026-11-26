"""
config.py - Parametros de TODO el sistema real (estacion + carro + camara).
Todos los modulos leen de aqui. Los valores marcados MIDE / CALIBRA son de partida: ajustalos con tu montaje.
Cada parametro se puede sobreescribir con una variable de entorno MONEDAS_<NOMBRE> (ver _env abajo).

Flujo:   banda -> la CAMARA clasifica la moneda al cruzar la linea de conteo -> el PC calcula cuando llegara
         al borde de la banda -> el servo SG90 gira la canaleta hacia el cubiculo de esa denominacion
         -> la moneda cae -> el chatbot/dashboard pide "despachar" un cubiculo -> el carro lo engancha y
         lo lleva por la pista.
"""
import os

from monedas.tipos import TIPOS as _TIPOS

# Carpeta donde se escriben los archivos de trabajo (estado.json, comando.json, calibracion.json, registros).
# Por defecto ./datos junto a donde ejecutas el programa; cambiala con la variable MONEDAS_DATOS.
DATOS = os.path.abspath(os.environ.get("MONEDAS_DATOS", os.path.join(os.getcwd(), "datos")))
os.makedirs(DATOS, exist_ok=True)
AQUI = DATOS            # (compatibilidad)

# ------------------------------------------------------------------ comunicacion
ESTACION_PUERTO = "auto"        # ESP32 de la estacion (banda+servo): "COM5", "/dev/ttyUSB0" o "auto"
ESTACION_BAUDIOS = 115200
CARRO_NOMBRE = "JDY"            # el carro (JDY-16, Bluetooth BLE) se busca por un nombre que EMPIECE asi
CARRO_DIRECCION = None          # o la direccion exacta, ej. "AA:BB:CC:DD:EE:FF" (en Mac es un UUID)
UUID_CARRO = "0000ffe1-0000-1000-8000-00805f9b34fb"   # caracteristica del JDY-16 (si no esta, usa la primera que sirva)
CARRO_PEDAZO_MAX = 60           # caracteres por linea Bluetooth

# ------------------------------------------------------------------ cubiculos (5 vasos fijos en arco de 180 grados)
# 5 vasos, uno por denominacion. Cada vaso recibe la moneda ACTUAL y la ANTIGUA de ese valor.
CUBICULO_DE_VALOR = {50: 0, 100: 1, 200: 2, 500: 3, 1000: 4}
# No hay vaso de rechazo: una moneda que la camara no reconoce lleva la canaleta a este angulo (0-180),
# FUERA del arco de los vasos, y cae a una bandeja/suelo para recogerla a mano. Ajustalo a tu montaje.
ANGULO_RECHAZO = 0
# Ids de config.py (los que usa el chatbot) de cada denominacion, p. ej. 500 -> ['500_antigua', '500_actual']
IDS_DE_VALOR = {}
for _t in _TIPOS:
    IDS_DE_VALOR.setdefault(_t["valor"], []).append(_t["id"])
VALOR_DE_TIPO_ID = {_t["id"]: _t["valor"] for _t in _TIPOS}

# ------------------------------------------------------------------ tiempos de la banda  (MIDE)
V_BANDA_MM_S = 20.0             # velocidad real de la banda: marca un punto y cronometra 100 mm
DIST_LINEA_A_BORDE_MM = 300.0   # de la linea roja de conteo (video) al borde donde cae la moneda
SERVO_INMEDIATO = True           # True: el servo se mueve EN CUANTO la camara identifica la moneda (pruebas sin banda).
                                # False: espera a que la moneda llegue al borde (usa V_BANDA_MM_S y DIST_LINEA_A_BORDE_MM)
BANDA_PCT = 100                 # % de potencia de la banda al encenderla (tecla B)
TIEMPO_SERVO_S = 0.7            # lo que tarda la canaleta en llegar de un vaso a otro (la peor distancia)
TIEMPO_CAIDA_S = 0.7            # lo que se queda la canaleta quieta para que la moneda termine de caer

# ------------------------------------------------------------------ rutas del carro (CALIBRA con panel_carro.html / pista.py)
# Tramos: letra + milisegundos (F adelante, B reversa, L/R giro, S pausa). Una ruta por cubiculo para engancharlo.
RUTA_ENGANCHE = {k: "B800" for k in range(5)}       # PLACEHOLDER: retroceder hasta que la pinza agarre el vaso
def ruta_pista():
    """Ruta completa de la pista (2 retornos en U y 3 termos) como texto 'F1000,L40,...' (la genera pista.py)."""
    from monedas import pista
    return pista.a_texto(pista.construir_ruta())
CARRO_TIMEOUT_RUTA_S = 120
DESPACHAR_VACIOS = False        # False: no despacha un cubiculo sin monedas

# ------------------------------------------------------------------ modo demo (sin hardware)
DEMO_V_BANDA_MM_S = 100.0       # banda simulada mas rapida para ver todo en poco tiempo
DEMO_ACELERACION_CARRO = 10.0   # el carro simulado recorre la ruta N veces mas rapido

# ------------------------------------------------------------------ archivos
ESTADO_PATH = os.path.join(DATOS, "estado.json")        # lo lee el chatbot y el dashboard
COMANDO_PATH = os.path.join(DATOS, "comando.json")      # lo escribe el chatbot y el dashboard
REGISTRO_PATH = os.path.join(DATOS, "registro_monedas.csv")


def cubiculo_de_valor(valor):
    """Vaso (0-4) al que va una moneda de ese valor en pesos; None si no se reconocio (va al rechazo)."""
    return CUBICULO_DE_VALOR.get(valor) if valor is not None else None


def tiempo_hasta_borde_s(v_banda_mm_s=None):
    v = v_banda_mm_s or V_BANDA_MM_S
    return DIST_LINEA_A_BORDE_MM / v


def _aplicar_entorno():
    """MONEDAS_<NOMBRE>=valor sobreescribe el parametro <NOMBRE> (solo numeros, textos y booleanos)."""
    g = globals()
    for nombre in [n for n in g if n.isupper() and not n.startswith("_")]:
        crudo = os.environ.get("MONEDAS_" + nombre)
        actual = g[nombre]
        if crudo is None or not (actual is None or isinstance(actual, (bool, int, float, str))):
            continue
        if isinstance(actual, bool):
            g[nombre] = crudo.strip().lower() in ("1", "true", "si", "sí", "yes")
        elif isinstance(actual, int):
            g[nombre] = int(float(crudo))
        elif isinstance(actual, float):
            g[nombre] = float(crudo)
        else:
            g[nombre] = crudo


_aplicar_entorno()
