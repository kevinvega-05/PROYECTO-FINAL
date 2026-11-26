"""
parametros.py - UNICA fuente de verdad de las medidas (mm) de todas las piezas 3D.

Origen del sistema de coordenadas de la escena:
    X = hacia donde sale la moneda de la banda (extremo de salida de la banda = X 0)
    Y = lateral,  Z = hacia arriba desde la mesa.

MEDIDO en el montaje físico: banda (160 de ancho, 80 de alto), pista (ver monedas/pista.py), termo Ø90.
SUPUESTO (verificar con pie de rey ANTES de imprimir): todo lo marcado con [?].
"""
import math
from monedas import pista

# ------------------------------------------------------------------ banda (medida)
BANDA_ANCHO = 160.0
BANDA_ALTO = 80.0                 # superficie de la banda sobre la mesa
BANDA_LARGO = 660.0               # [?] 3 modulos de 220

# ------------------------------------------------------------------ vasos (5, uno por denominacion)
VASO_DI = 36.0                    # la moneda mayor ($1000, 26 mm) cabe con holgura
VASO_PARED = 3.0
VASO_DE = VASO_DI + 2 * VASO_PARED
VASO_ALTO = 45.0                  # ~20 monedas apiladas; mas bajo = pendiente de la canaleta mas pronunciada
VASO_FONDO = 3.0
OREJA_L = 12.0                    # oreja de enganche: sobresale de la pared
OREJA_ANCHO = 16.0
OREJA_ESP = 4.0
OREJA_HUECO = 6.0                 # agujero que entra en el pasador del carro (pasador = 5.4)
OREJA_Z = 14.0                    # altura del centro del agujero

# ------------------------------------------------------------------ placa portavasos (arco)
PLACA_ESP = 3.0
R_VASOS = 110.0                   # radio del arco de vasos medido desde el pivote de la canaleta
HOLGURA_VASO = 0.6                # radial: el vaso entra suelto y el carro lo arrastra hacia afuera
PLACA_BORDE = 14.0                # borde de la placa alrededor de cada vaso
CORTE_PLACA_GRADOS = 22.5         # los cortes radiales entre vasos (3 piezas, cada una cabe en 220 mm)
PERNO_D = 4.0                     # agujeros para pasadores de filamento 3 mm... (se pega)

# angulos del servo (los mismos que ANGULOS[] del firmware). 90 = recto hacia adelante.
ANGULOS_SERVO = (20, 45, 90, 135, 160)

# ------------------------------------------------------------------ canaleta giratoria + torre del servo SG90
PIVOTE_X = 16.0                   # el pivote del servo queda 16 mm despues del borde de la banda
PIVOTE_Z = BANDA_ALTO - 2.0       # fondo de la tolva (2 mm bajo la banda)
TOLVA_D = 46.0                    # tolva giratoria que recibe la moneda
CANAL_ANCHO = 30.0                # interior del canal (moneda mayor 26)
CANAL_PARED = 2.5
CANAL_PISO = 2.0
CANAL_ALTO = 8.0
PUNTA_SOBRE_BORDE = 6.0           # la punta de la canaleta queda 6 mm por encima del borde de los vasos
PUNTA_R = R_VASOS - 14.0          # distancia pivote -> punta (la moneda sale hacia el vaso)
SERVO_L, SERVO_A = 22.8, 12.6     # cuerpo del SG90 (+ holgura)
SERVO_ALTO_ABAJO_OREJAS = 16.5    # desde el fondo del servo hasta la cara inferior de las orejas
SERVO_SOBRE_OREJAS = 10.0         # de las orejas hasta la punta del horn (eje + palanca)
SERVO_EJE_DESDE_EXTREMO = 6.2     # [?] el eje esta a 6.2 mm del extremo del cuerpo
SERVO_OREJA_X = (-5.0, 17.0)      # tornillos de las orejas respecto al eje (+ x hacia el canal)
TORRE_ALTO = PIVOTE_Z - SERVO_SOBRE_OREJAS    # cara superior de la torre
TORRE_PARED = 3.0
TORRE_PLACA = 4.0

# ------------------------------------------------------------------ sensor, entrada, celular, carro
SENSOR_PCB = (32.0, 14.0)         # modulo IR LM393 (FC-51) [?]
CELULAR = (78.0, 164.0, 9.5)      # ancho x largo x espesor [?]
CAMARA_ALTURA = 280.0             # de la banda a la lente
POSTE_D = 22.0                    # tubo PVC de 3/4" (~ 26) o varilla [?]
PASADOR_D = 5.4

# ------------------------------------------------------------------ carro (referencia, no se imprime)
CARRO_ANCHO = pista.CARRO_ANCHO
CARRO_LARGO = pista.CARRO_LARGO
RUEDA_D, RUEDA_ANCHO = 65.0, 26.0
TERMO_D, TERMO_ALTO = pista.OBSTACULO_DIAM, 270.0

# ------------------------------------------------------------------ pista en la escena
# pista (xp adelante... ver pista.py): el carro arranca en (X0, 0) mirando a +X; la derecha del carro es -Y.
PISTA_X0 = 440.0
LIMITE_CAMA = 220.0               # cama de impresion (Ender 3 / similar)


def pista_a_escena(xp, yp):
    """(x lateral derecha, y adelante) de pista.py -> (X, Y) de la escena."""
    return PISTA_X0 + yp, -xp


# ------------------------------------------------------------------ derivados
def dir_servo(angulo):
    """Direccion horizontal (cx, cy) de la canaleta para un angulo de servo (90 = +X)."""
    phi = math.radians(90 - angulo)
    return math.cos(phi), math.sin(phi)


def pos_vaso(k):
    cx, cy = dir_servo(ANGULOS_SERVO[k])
    return PIVOTE_X + R_VASOS * cx, R_VASOS * cy


BORDE_VASO_Z = PLACA_ESP + VASO_ALTO
PUNTA_Z = BORDE_VASO_Z + PUNTA_SOBRE_BORDE
PENDIENTE_GRADOS = math.degrees(math.atan2(PIVOTE_Z - PUNTA_Z, PUNTA_R))
