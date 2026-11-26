"""
generar_urdf.py - Genera los URDF del sistema logístico de monedas (v2: carrusel + remolque).

    python generar_urdf.py

Crea en ./urdf:
    banda.urdf            tramo recto de banda (fijo)
    entrada.urdf          pequeña tolva/chute donde entra la moneda (visual)
    sensor.urdf           poste con el sensor de presencia + soporte del celular (visual)
    disco_base.urdf       pedestal fijo del carrusel
    disco.urdf            plato giratorio del carrusel (une por joint revolute a disco_base)
    cubiculo.urdf         cubículo (uno de los 9, se colorea distinto por tipo al cargarlo)
    carro.urdf            carro diferencial con punto de enganche (remolque) en la parte trasera
"""
import math
import os
from config import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "urdf")

MATERIALES = {
    "azul": (0.05, 0.15, 0.35, 1),
    "negro": (0.06, 0.06, 0.06, 1),
    "blanco": (0.95, 0.95, 0.98, 1),
    "gris": (0.35, 0.35, 0.38, 1),
    "rojo": (0.80, 0.20, 0.20, 1),
    "claro": (0.90, 0.90, 0.90, 1),
    "carro": (0.10, 0.35, 0.75, 1),
    "verde": (0.15, 0.70, 0.30, 1),
    "cubiculo": (0.55, 0.55, 0.60, 1),
}


# ------------------------------------------------------------------ helpers
def f(v):
    return f"{v:.5f}"


def xyz(t):
    return " ".join(f(x) for x in t)


def caja(size):
    return f'<box size="{xyz(size)}"/>'


def cil(r, l):
    return f'<cylinder radius="{f(r)}" length="{f(l)}"/>'


def esfera(r):
    return f'<sphere radius="{f(r)}"/>'


def parte(geom, origen=(0, 0, 0), rpy=(0, 0, 0), mat=None, col=True, vis=True):
    o = f'<origin xyz="{xyz(origen)}" rpy="{xyz(rpy)}"/>'
    s = ""
    if vis:
        s += f"    <visual>\n      {o}\n      <geometry>{geom}</geometry>\n"
        if mat:
            s += f'      <material name="{mat}"/>\n'
        s += "    </visual>\n"
    if col:
        s += f"    <collision>\n      {o}\n      <geometry>{geom}</geometry>\n    </collision>\n"
    return s


def i_caja(m, x, y, z):
    return (m / 12 * (y * y + z * z), m / 12 * (x * x + z * z), m / 12 * (x * x + y * y))


def i_cil(m, r, l):
    return (m * (3 * r * r + l * l) / 12, m * (3 * r * r + l * l) / 12, m * r * r / 2)


def link(nombre, partes, masa, inercia, com=(0, 0, 0)):
    ixx, iyy, izz = inercia
    s = f'  <link name="{nombre}">\n'
    s += "".join(partes)
    s += "    <inertial>\n"
    s += f'      <origin xyz="{xyz(com)}" rpy="0 0 0"/>\n'
    s += f'      <mass value="{f(masa)}"/>\n'
    s += (f'      <inertia ixx="{ixx:.7f}" ixy="0" ixz="0" iyy="{iyy:.7f}" iyz="0" izz="{izz:.7f}"/>\n')
    s += "    </inertial>\n  </link>\n"
    return s


def joint(nombre, tipo, padre, hijo, origen=(0, 0, 0), rpy=(0, 0, 0), eje=None, lim=None):
    s = f'  <joint name="{nombre}" type="{tipo}">\n'
    s += f'    <parent link="{padre}"/>\n    <child link="{hijo}"/>\n'
    s += f'    <origin xyz="{xyz(origen)}" rpy="{xyz(rpy)}"/>\n'
    if eje:
        s += f'    <axis xyz="{xyz(eje)}"/>\n'
    if lim:
        lo, hi, ef, vel = lim
        s += (f'    <limit lower="{f(lo)}" upper="{f(hi)}" effort="{f(ef)}" velocity="{f(vel)}"/>\n')
    elif tipo == "continuous":
        s += '    <limit effort="10" velocity="10"/>\n'
    s += "  </joint>\n"
    return s


def robot(nombre, cuerpo, mats):
    s = f'<?xml version="1.0"?>\n<robot name="{nombre}">\n'
    for m in mats:
        r, g, b, a = MATERIALES[m]
        s += f'  <material name="{m}"><color rgba="{r} {g} {b} {a}"/></material>\n'
    s += cuerpo + "</robot>\n"
    with open(os.path.join(OUT, nombre + ".urdf"), "w") as fh:
        fh.write(s)
    print("  ->", nombre + ".urdf")


# ------------------------------------------------------------------ BANDA (recta)
def banda():
    largo = BANDA_LARGO
    grosor = 0.02
    partes = [
        parte(caja((largo, BANDA_ANCHO, grosor)), (largo / 2, 0, BANDA_H - grosor / 2), mat="negro"),
        parte(caja((largo, 0.012, 0.03)), (largo / 2, BANDA_ANCHO / 2 + 0.006, BANDA_H - 0.015), mat="azul", col=False),
        parte(caja((largo, 0.012, 0.03)), (largo / 2, -BANDA_ANCHO / 2 - 0.006, BANDA_H - 0.015), mat="azul", col=False),
        parte(cil(0.014, BANDA_ANCHO + 0.02), (largo, 0, BANDA_H - 0.012), (math.pi / 2, 0, 0), "gris", col=False),
        parte(cil(0.014, BANDA_ANCHO + 0.02), (0, 0, BANDA_H - 0.012), (math.pi / 2, 0, 0), "gris", col=False),
    ]
    pata_h = BANDA_H - grosor
    for sx in (0.05, largo - 0.05):
        for sy in (-1, 1):
            partes.append(parte(caja((0.03, 0.03, pata_h)),
                                (sx, sy * (BANDA_ANCHO / 2 + 0.01), pata_h / 2), mat="gris"))
    c = link("banda", partes, 5.0, i_caja(5.0, largo, BANDA_ANCHO, BANDA_H), (largo / 2, 0, BANDA_H / 2))
    robot("banda", c, ["negro", "azul", "gris"])


def entrada():
    partes = [
        parte(caja((0.10, BANDA_ANCHO + 0.06, 0.10)), (0, 0, BANDA_H + 0.10), mat="blanco"),
        parte(caja((0.06, 0.06, 0.06)), (0, 0, BANDA_H + 0.03), mat="gris", col=False),
    ]
    c = link("entrada", partes, 4.0, i_caja(4.0, 0.10, BANDA_ANCHO + 0.06, 0.10), (0, 0, BANDA_H + 0.05))
    robot("entrada", c, ["blanco", "gris"])


def sensor():
    partes = [
        parte(cil(0.012, BANDA_H + 0.20), (0, BANDA_ANCHO / 2 + 0.02, (BANDA_H + 0.20) / 2), mat="gris", col=False),
        parte(caja((0.05, 0.02, 0.09)), (0, BANDA_ANCHO / 2 + 0.02, BANDA_H + 0.20), (0, math.radians(20), 0), mat="negro", col=False),
        parte(cil(0.006, 0.01), (0, BANDA_ANCHO / 2 + 0.055, BANDA_H + 0.235), (math.pi / 2, 0, 0), "verde", col=False),
    ]
    c = link("sensor", partes, 2.0, i_cil(2.0, 0.02, BANDA_H + 0.20), (0, 0, (BANDA_H + 0.20) / 2))
    robot("sensor", c, ["gris", "negro", "verde"])


# ------------------------------------------------------------------ CARRUSEL
def disco_base():
    partes = [parte(cil(0.05, DISCO_PEDESTAL_H), (0, 0, DISCO_PEDESTAL_H / 2), mat="gris")]
    c = link("disco_base", partes, 6.0, i_cil(6.0, 0.05, DISCO_PEDESTAL_H), (0, 0, DISCO_PEDESTAL_H / 2))
    robot("disco_base", c, ["gris"])


def disco():
    partes = [
        parte(cil(DISCO_RADIO, DISCO_H), (0, 0, 0), mat="azul"),
        parte(cil(0.03, DISCO_H + 0.02), (0, 0, 0.01), mat="negro", col=False),
    ]
    # marcas radiales (solo visuales) para ver los 9 puestos
    for k in range(N_TIPOS):
        ang = angulo_local(k)
        partes.append(parte(caja((DISCO_RADIO - 0.02, 0.004, 0.004)),
                            ((DISCO_RADIO - 0.02) / 2 * math.cos(ang), (DISCO_RADIO - 0.02) / 2 * math.sin(ang), DISCO_H),
                            (0, 0, ang), mat="negro", col=False))
    c = link("disco", partes, 4.0, i_cil(4.0, DISCO_RADIO, DISCO_H), (0, 0, 0))
    robot("disco", c, ["azul", "negro"])


def cubiculo():
    A = CUBICULO_LADO / 2
    t = CUBICULO_PARED
    partes = [parte(caja((CUBICULO_LADO, CUBICULO_LADO, CUBICULO_PISO)), (0, 0, CUBICULO_PISO / 2), mat="cubiculo")]
    for sx, sy, dim in ((1, 0, (t, CUBICULO_LADO, CUBICULO_H)), (-1, 0, (t, CUBICULO_LADO, CUBICULO_H)),
                       (0, 1, (CUBICULO_LADO, t, CUBICULO_H)), (0, -1, (CUBICULO_LADO, t, CUBICULO_H))):
        partes.append(parte(caja(dim), (sx * (A - t / 2) if sx else 0, sy * (A - t / 2) if sy else 0, CUBICULO_H / 2), mat="cubiculo"))
    m = CUBICULO_MASA
    c = link("cubiculo", partes, m, i_caja(m, CUBICULO_LADO, CUBICULO_LADO, CUBICULO_H), (0, 0, CUBICULO_H / 2))
    robot("cubiculo", c, ["cubiculo"])


# ------------------------------------------------------------------ CARRO (remolque)
def carro():
    s = ""
    cz = CARRO_CHASIS_H / 2
    partes = [
        parte(caja((CARRO_L, CARRO_W, CARRO_CHASIS_H)), (0, 0, 0), mat="carro"),
        parte(cil(0.02, 0.03), (CARRO_L / 2 - 0.02, 0, cz), mat="negro", col=False),
        parte(esfera(0.018), (CARRO_L / 2 - 0.02, 0, cz + 0.03), mat="claro", col=False),
        # barra de enganche, apuntando hacia atrás
        parte(caja((0.04, 0.015, 0.015)), (-CARRO_L / 2 - 0.02, 0, 0.02), mat="negro", col=False),
        parte(cil(0.01, 0.01), (-CARRO_L / 2 - 0.035, 0, 0.02), (math.pi / 2, 0, 0), "rojo", col=False),
    ]
    m = 0.8
    s += link("chasis", partes, m, i_caja(m, CARRO_L, CARRO_W, 0.06))

    wz = RUEDA_R - CARRO_Z
    for nombre, lado in (("izq", 1), ("der", -1)):
        s += joint(f"j_rueda_{nombre}", "continuous", "chasis", f"rueda_{nombre}",
                   (0, lado * VIA / 2, wz), eje=(0, 1, 0))
        mr = 0.05
        ixx, iyy, izz = i_cil(mr, RUEDA_R, RUEDA_ANCHO)
        s += link(f"rueda_{nombre}",
                  [parte(cil(RUEDA_R, RUEDA_ANCHO), (0, 0, 0), (math.pi / 2, 0, 0), "negro")],
                  mr, (ixx, izz, ixx))

    rc = 0.02
    for nombre, sx in (("del", 1), ("tras", -1)):
        s += joint(f"j_caster_{nombre}", "fixed", "chasis", f"caster_{nombre}",
                   (sx * (CARRO_L / 2 - 0.03), 0, rc - CARRO_Z))
        s += link(f"caster_{nombre}", [parte(esfera(rc), mat="gris")], 0.03,
                  (2 / 5 * 0.03 * rc * rc,) * 3)
    robot("carro", s, ["carro", "negro", "claro", "gris", "rojo"])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    print("Generando URDF en", OUT)
    banda()
    entrada()
    sensor()
    disco_base()
    disco()
    cubiculo()
    carro()
    print("Listo.")
