"""
generar_cad.py - Genera TODAS las piezas 3D del proyecto (STL), los modelos de referencia y la escena GLB.

    python cad/generar_cad.py            # escribe cad/stl/, cad/referencia/, cad/escena.glb y cad/PIEZAS.md
    python cad/generar_cad.py --check    # ademas valida (hermeticidad, cama 220, choques, pendiente)

Todas las medidas salen de cad/parametros.py. Piezas imprimibles -> cad/stl/ ; modelos de referencia
(carro, banda, termo, pista) -> cad/referencia/ (no se imprimen, sirven para ver el conjunto).
"""
import argparse
import math
import os
import sys

import numpy as np
import trimesh
from shapely.geometry import Polygon, box as sbox
from trimesh.creation import extrude_polygon

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, ".."))
import parametros as P  # noqa: E402

SEG = 96
MAN = "manifold"


# ------------------------------------------------------------------ primitivas
def cil(r, h, x=0.0, y=0.0, z=0.0, seg=SEG):
    m = trimesh.creation.cylinder(radius=r, height=h, sections=seg)
    m.apply_translation([x, y, z + h / 2])
    return m


def caja(x0, x1, y0, y1, z0, z1):
    x0, x1, y0, y1, z0, z1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
    m = trimesh.creation.box(extents=[x1 - x0, y1 - y0, z1 - z0])
    m.apply_translation([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
    return m


def resta(a, *bs):
    for b in bs:
        a = a.difference(b, engine=MAN)
    return a


def une(*ms):
    r = ms[0]
    for m in ms[1:]:
        r = r.union(m, engine=MAN)
    return r


def inter(a, b):
    return a.intersection(b, engine=MAN)


def rotz(m, grados, centro=(0, 0, 0)):
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(grados), [0, 0, 1], centro))
    return m


def roty(m, grados, centro=(0, 0, 0)):
    m = m.copy()
    m.apply_transform(trimesh.transformations.rotation_matrix(math.radians(grados), [0, 1, 0], centro))
    return m


def color(m, rgba):
    m = m.copy()
    m.visual.face_colors = np.tile(np.array(rgba, dtype=np.uint8), (len(m.faces), 1))
    return m


def sector_poligono(r_in, r_out, a0, a1, pasos=48):
    """Sector anular 2D entre radios r_in..r_out y angulos a0..a1 (grados), centro en el origen."""
    ang = np.radians(np.linspace(a0, a1, pasos))
    ext = [(r_out * math.cos(a), r_out * math.sin(a)) for a in ang]
    inn = [(r_in * math.cos(a), r_in * math.sin(a)) for a in ang[::-1]]
    return Polygon(ext + inn)


# ------------------------------------------------------------------ PIEZAS IMPRIMIBLES
def vaso():
    """Vaso con base y oreja de enganche (el carro lo remolca por la oreja)."""
    r_e, r_i = P.VASO_DE / 2, P.VASO_DI / 2
    cuerpo = resta(cil(r_e, P.VASO_ALTO), cil(r_i, P.VASO_ALTO, z=P.VASO_FONDO))
    oreja = _oreja()
    return une(cuerpo, oreja)


def _cil_horiz(r, largo, x, z):
    """Cilindro con eje en Y centrado en (x, 0, z)."""
    m = trimesh.creation.cylinder(radius=r, height=largo, sections=48)
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    m.apply_translation([x, 0, z])
    return m


def _oreja():
    """Oreja plana vertical (plano XZ, espesor en Y) con agujero horizontal... el pasador del carro es VERTICAL,
    asi que la oreja va ACOSTADA: placa horizontal con agujero vertical, a la altura OREJA_Z."""
    r_e = P.VASO_DE / 2
    w = P.OREJA_ANCHO
    placa = caja(r_e - 2, r_e + P.OREJA_L - w / 2, -w / 2, w / 2, P.OREJA_Z - P.OREJA_ESP / 2, P.OREJA_Z + P.OREJA_ESP / 2)
    punta = cil(w / 2, P.OREJA_ESP, x=r_e + P.OREJA_L - w / 2, z=P.OREJA_Z - P.OREJA_ESP / 2, seg=48)
    # costilla de refuerzo bajo la oreja hacia la pared del vaso
    costilla = caja(r_e - 2, r_e + 8, -1.5, 1.5, P.OREJA_Z - P.OREJA_ESP / 2 - 8, P.OREJA_Z - P.OREJA_ESP / 2)
    pieza = une(placa, punta, costilla)
    hueco = cil(P.OREJA_HUECO / 2, P.OREJA_ESP + 20, x=r_e + P.OREJA_L - w / 2, z=P.OREJA_Z - 10, seg=48)
    return resta(pieza, hueco)


def _poligono_placa(k0, k1):
    """Region 2D (en el marco del pivote) de la placa para los vasos k0..k1 (cortes a +-CORTE_PLACA_GRADOS)."""
    ang = [90 - a for a in P.ANGULOS_SERVO]          # phi de cada vaso (grados)
    cortes = [(ang[i] + ang[i + 1]) / 2 for i in range(len(ang) - 1)]
    hi = (ang[k0] + 12.0) if k0 == 0 else cortes[k0 - 1]       # angulo mayor (vaso 0 es phi=70)
    lo = (ang[k1] - 12.0) if k1 == len(ang) - 1 else cortes[k1]
    return lo, hi


def placa_portavasos(k0, k1):
    """Tramo de la placa que sostiene los vasos k0..k1: sector anular con alojamientos abiertos hacia afuera."""
    lo, hi = _poligono_placa(k0, k1)
    r_in, r_out = P.R_VASOS - P.VASO_DE / 2 - P.PLACA_BORDE, P.R_VASOS + P.VASO_DE / 2 + P.PLACA_BORDE
    pol = sector_poligono(r_in, r_out, lo, hi)
    m = extrude_polygon(pol, P.PLACA_ESP)
    r_loc = P.VASO_DE / 2 + P.HOLGURA_VASO
    for k in range(k0, k1 + 1):
        phi = math.radians(90 - P.ANGULOS_SERVO[k])
        cx, cy = P.R_VASOS * math.cos(phi), P.R_VASOS * math.sin(phi)
        aloj = une(cil(r_loc, 1.6, x=cx, y=cy, z=P.PLACA_ESP - 1.5),
                   rotz(caja(P.R_VASOS, P.R_VASOS + 60, -r_loc, r_loc, P.PLACA_ESP - 1.5, P.PLACA_ESP + 1), 90 - P.ANGULOS_SERVO[k]))
        m = resta(m, aloj)
    # 3 tornillos de fijacion a la tabla
    for fr in (0.25, 0.75):
        a = math.radians(lo + (hi - lo) * fr)
        r = P.R_VASOS - P.VASO_DE / 2 - P.PLACA_BORDE / 2 - 1
        m = resta(m, cil(1.7, 10, x=r * math.cos(a), y=r * math.sin(a), z=-1, seg=24))
    # pasadores de union en los cortes interiores (radiales)
    for lado, a in (("hi", hi), ("lo", lo)):
        interior = (lado == "hi" and k0 > 0) or (lado == "lo" and k1 < len(P.ANGULOS_SERVO) - 1)
        if interior:
            for r in (P.R_VASOS - 12, P.R_VASOS + 12):
                m = resta(m, _perno(r, a))
    # la placa vive en el marco del pivote -> pasa al marco de la escena
    m.apply_translation([P.PIVOTE_X, 0, 0])
    return m


def _perno(r, a_deg):
    """Agujero radial (en el plano del corte) para pasador de 4 mm."""
    a = math.radians(a_deg)
    h = trimesh.creation.cylinder(radius=P.PERNO_D / 2 + 0.15, height=16, sections=24)
    # eje tangencial al corte: lo dejamos en direccion del arco, centrado en el corte
    h.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))   # eje Y
    h = rotz(h, a_deg)
    h.apply_translation([r * math.cos(a), r * math.sin(a), P.PLACA_ESP / 2])
    return h


def torre_servo():
    """Torre hueca (se imprime boca abajo) con placa superior donde cuelga el SG90 por las orejas."""
    x_eje = P.PIVOTE_X
    x0 = x_eje - P.SERVO_EJE_DESDE_EXTREMO - 8.3          # pared izquierda
    x1 = x_eje + (P.SERVO_L - P.SERVO_EJE_DESDE_EXTREMO) + 8.3
    y = (P.SERVO_A / 2 + 5.0)
    z1 = P.TORRE_ALTO
    exterior = caja(x0, x1, -y, y, 0, z1)
    interior = caja(x0 + P.TORRE_PARED, x1 - P.TORRE_PARED, -y + P.TORRE_PARED, y - P.TORRE_PARED, -1, z1 - P.TORRE_PLACA)
    t = resta(exterior, interior)
    # ventana del cuerpo del servo
    bx0 = x_eje - P.SERVO_EJE_DESDE_EXTREMO
    t = resta(t, caja(bx0, bx0 + P.SERVO_L, -P.SERVO_A / 2, P.SERVO_A / 2, z1 - P.TORRE_PLACA - 1, z1 + 1))
    # tornillos de las orejas
    for dx in P.SERVO_OREJA_X:
        t = resta(t, cil(1.0, 10, x=x_eje + dx, z=z1 - 7, seg=20))
    # salida del cable (ranura baja en la pared trasera) y ventilacion
    t = resta(t, caja(x0 - 1, x0 + P.TORRE_PARED + 1, -4, 4, 0, 9))
    # brida de fijacion a la mesa con 4 agujeros M3 (solo hacia +X y a los lados: no choca con la banda)
    brida = caja(max(0.5, x0), x1 + 12, -y - 12, y + 12, 0, 4)
    t = une(t, brida)
    for sx in (max(0.5, x0) + 5, x1 + 7):
        for sy in (-y - 6, y + 6):
            t = resta(t, cil(1.7, 8, x=sx, y=sy, z=-1, seg=24))
    # el hueco interior sigue libre bajo la brida
    t = resta(t, caja(x0 + P.TORRE_PARED, x1 - P.TORRE_PARED, -y + P.TORRE_PARED, y - P.TORRE_PARED, -1, z1 - P.TORRE_PLACA))
    t = resta(t, caja(bx0, bx0 + P.SERVO_L, -P.SERVO_A / 2, P.SERVO_A / 2, z1 - P.TORRE_PLACA - 1, z1 + 1))
    return t


def canaleta():
    """Tolva giratoria + canal. Origen = centro del fondo de la tolva; el canal sale hacia +X y baja P.PENDIENTE.
    Ya viene girada/inclinada y puesta en la escena con angulo de servo 90."""
    rt = P.TOLVA_D / 2
    L = P.PUNTA_R
    ancho_ext = P.CANAL_ANCHO + 2 * P.CANAL_PARED
    # tolva: vaso bajo con apertura hacia +X
    tolva = resta(cil(rt, P.CANAL_ALTO + P.CANAL_PISO), cil(rt - P.CANAL_PARED, P.CANAL_ALTO + 1, z=P.CANAL_PISO))
    canal = caja(0, L, -ancho_ext / 2, ancho_ext / 2, 0, P.CANAL_ALTO + P.CANAL_PISO)
    canal = resta(canal, caja(-1, L + 1, -P.CANAL_ANCHO / 2, P.CANAL_ANCHO / 2, P.CANAL_PISO, P.CANAL_ALTO + P.CANAL_PISO + 1))
    c = une(tolva, canal)
    # abre la pared de la tolva hacia el canal
    c = resta(c, caja(rt - P.CANAL_PARED - 1, rt + 1, -P.CANAL_ANCHO / 2, P.CANAL_ANCHO / 2, P.CANAL_PISO, P.CANAL_ALTO + P.CANAL_PISO + 1))
    # el interior de la tolva queda libre para que la moneda llegue desde atras
    c = resta(c, cil(rt - P.CANAL_PARED, P.CANAL_ALTO + 1, z=P.CANAL_PISO))
    # cubo para el horn del SG90: boquete cilindrico en la cara inferior
    c = une(c, cil(7.0, 5.0, z=-5.0, seg=48))
    c = resta(c, cil(4.0, 3.6, z=-5.1, seg=36), cil(1.1, 12, z=-6, seg=20))
    return c


def canaleta_en_escena(angulo=90):
    m = roty(canaleta(), P.PENDIENTE_GRADOS)         # +X baja
    m = rotz(m, 90 - angulo)
    m.apply_translation([P.PIVOTE_X, 0, P.PIVOTE_Z])
    return m


def tolva_entrada():
    """Guia de entrada: embudo en V que centra la moneda y un puente que deja pasar UNA moneda por vez."""
    w = P.BANDA_ANCHO
    neck = 36.0
    h = 14.0
    esp = 3.0
    largo = 130.0
    alto_pas = 4.0                               # luz bajo el puente (la moneda mas gruesa mide ~2.5)
    # paredes en V
    def pared(signo):
        pol = Polygon([(0, signo * w / 2), (largo, signo * neck / 2), (largo, signo * (neck / 2 + esp)), (0, signo * (w / 2 + esp))])
        return extrude_polygon(pol, h)
    t = une(pared(1), pared(-1))
    puente = caja(largo - 45, largo - 25, -neck / 2 - esp, neck / 2 + esp, alto_pas, alto_pas + esp)
    t = une(t, puente)
    # orejas de fijacion al bastidor con tornillo M4
    for s in (1, -1):
        oreja = caja(10, 40, s * (w / 2 + esp), s * (w / 2 + esp + 14), 0, 4)
        t = une(t, oreja)
        t = resta(t, cil(2.1, 10, x=25, y=s * (w / 2 + esp + 8), z=-1, seg=24))
    return t


def soporte_sensor_ir():
    """Pilar con brazo que deja el modulo IR sobre el centro de la banda, mirando hacia abajo.
    Eje X local = hacia el centro de la banda. El pilar queda fuera del bastidor."""
    H = P.BANDA_ALTO + 38.0                           # el brazo queda 38 mm sobre la banda
    alcance = P.BANDA_ANCHO / 2 + 14.0                # del pilar al centro de la banda
    base = caja(-12, 30, -16, 16, 0, 5)
    pilar = caja(-8, 0, -8, 8, 0, H)
    brazo = caja(-8, alcance + 9, -6, 6, H - 6, H)
    t = une(base, pilar, brazo)
    t = une(t, caja(alcance - 9, alcance + 9, -9, 9, H - 12, H - 6))            # asiento del modulo
    t = resta(t, cil(1.6, 14, x=alcance, z=H - 17, seg=24))                      # tornillo M3 del modulo
    t = resta(t, caja(alcance - 6, alcance + 6, -4, 4, H - 13, H - 5))            # ventana de los LED
    for sx in (-2, 22):
        t = resta(t, cil(2.1, 8, x=sx, y=0, z=-1, seg=24))                      # fijacion a la mesa
    return t


def base_poste_celular():
    """Base cuadrada con enchufe para el poste del celular + 4 nervios + 4 agujeros de fijacion."""
    s = 130.0
    base = caja(-s / 2, s / 2, -s / 2, s / 2, 0, 6)
    enchufe = resta(cil(P.POSTE_D / 2 + 6, 40, seg=64), cil(P.POSTE_D / 2 + 0.2, 41, z=1.5, seg=64))
    t = une(base, enchufe)
    for a in (0, 90, 180, 270):
        n = caja(P.POSTE_D / 2 + 5, P.POSTE_D / 2 + 38, -2, 2, 0, 28)
        t = une(t, rotz(n, a))
    for sx in (-1, 1):
        for sy in (-1, 1):
            t = resta(t, cil(2.6, 9, x=sx * (s / 2 - 12), y=sy * (s / 2 - 12), z=-1, seg=24))
    return t


def soporte_celular():
    """Bandeja donde el celular queda acostado, con la lente hacia abajo (ventana de camara), y un collar al poste."""
    w, l, e = P.CELULAR
    bw, bl = w + 18, l + 14
    base = caja(0, bw, 0, bl, 0, 3)
    base = resta(base, caja(10, 10 + 36, 16, 52, -1, 4))                 # ventana de la lente (esquina del lado abierto) [?]
    rieles = []
    for x0 in (0, bw - 4):
        rieles.append(caja(x0, x0 + 4, 0, bl, 0, e + 5))
        rieles.append(caja(x0 if x0 == 0 else x0 - 3, x0 + 4 if x0 == 0 else x0 + 4, 0, bl, e + 2, e + 5))   # labio
    tope = caja(0, bw, bl - 4, bl, 0, e + 5)
    tope = une(tope, caja(0, bw, 0, 3, 0, 4))                                  # labio bajo del lado abierto
    t = une(base, *rieles, tope)
    # (la bandeja queda abierta por el lado y=0 para deslizar el celular)
    # collar al poste
    cx, cy = bw / 2, bl + 20
    collar = resta(cil(P.POSTE_D / 2 + 7, 40, x=cx, y=cy, seg=64), cil(P.POSTE_D / 2 + 0.3, 41, x=cx, y=cy, z=-0.5, seg=64))
    t = une(t, collar, caja(cx - 14, cx + 14, bl - 4, cy, 0, 12))
    # tornillo de presion M4
    prensa = trimesh.creation.cylinder(radius=2.1, height=20, sections=24)
    prensa.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
    prensa.apply_translation([cx, cy + 12, 20])
    return resta(t, prensa)


def enganche_carro():
    """Pasador vertical que entra en la oreja del vaso (se atornilla en la parte trasera del carro)."""
    base = caja(-22, 22, -16, 16, 0, 4)
    pas = cil(P.PASADOR_D / 2, 16, z=4, seg=48)
    cabeza = trimesh.creation.cone(radius=P.PASADOR_D / 2, height=3.0, sections=48)
    cabeza.apply_translation([0, 0, 20])
    t = une(base, pas, cabeza)
    for sx in (-14, 14):
        t = resta(t, cil(1.7, 8, x=sx, z=-1, seg=24))
    return t


# ------------------------------------------------------------------ MODELOS DE REFERENCIA (no se imprimen)
def ref_carro():
    A, L = P.CARRO_ANCHO, P.CARRO_LARGO
    rr, rw = P.RUEDA_D / 2, P.RUEDA_ANCHO
    chasis = caja(-L / 2 + 20, L / 2 - 30, -(A - 2 * rw) / 2 + 4, (A - 2 * rw) / 2 - 4, rr - 12, rr + 6)
    piezas = [color(chasis, (40, 90, 200, 255))]
    for s in (1, -1):
        r = trimesh.creation.cylinder(radius=rr, height=rw, sections=48)
        r.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [1, 0, 0]))
        r.apply_translation([-20, s * (A / 2 - rw / 2), rr])
        piezas.append(color(r, (25, 25, 25, 255)))
    rueda_loca = trimesh.creation.icosphere(radius=10)
    rueda_loca.apply_translation([L / 2 - 36, 0, 10])
    piezas.append(color(rueda_loca, (180, 180, 180, 255)))
    piezas.append(color(caja(-L / 2 + 30, L / 2 - 60, -32, 32, rr + 6, rr + 22), (20, 130, 80, 255)))      # Arduino + shield
    piezas.append(color(caja(L / 2 - 30, L / 2 - 16, -22, 22, rr - 6, rr + 8), (200, 200, 60, 255)))      # sensor de distancia
    piezas.append(color(caja(-L / 2 - 4, -L / 2 + 22, -10, 10, rr - 8, rr + 2), (255, 140, 0, 255)))        # pinza trasera
    return trimesh.util.concatenate(piezas)


def ref_banda():
    W, Lg, Z = P.BANDA_ANCHO, P.BANDA_LARGO, P.BANDA_ALTO
    pz = [color(caja(-Lg, 0, -W / 2, W / 2, Z - 12, Z - 2), (30, 30, 30, 255))]
    for s in (1, -1):
        pz.append(color(caja(-Lg, 0, s * W / 2 - (3 if s > 0 else -3) - 3, s * W / 2 - (3 if s > 0 else -3) + 3, 0, Z), (170, 170, 175, 255)))
    for x in (-Lg + 20, -20):
        for s in (1, -1):
            pz.append(color(caja(x - 15, x + 15, s * (W / 2 - 6) - 3, s * (W / 2 - 6) + 3, 0, Z - 12), (150, 150, 155, 255)))
    return trimesh.util.concatenate(pz)


def ref_termo():
    r = P.TERMO_D / 2
    cuerpo = color(cil(r, P.TERMO_ALTO - 25), (20, 110, 120, 255))
    tapa = color(cil(r - 4, 25, z=P.TERMO_ALTO - 25), (230, 230, 230, 255))
    return trimesh.util.concatenate([cuerpo, tapa])


def ref_pista():
    """Pista: base verde, asfalto negro y bordes blancos, en el marco de la escena."""
    xi, xc, xd, y_sup, y_inf, y_meta = pista.geometria()
    W = pista.ANCHO_CARRIL
    R1, R2 = pista.SEPARACION_IZQ_CEN / 2, pista.SEPARACION_CEN_DER / 2
    def a_escena_poly(pol):
        pts = [P.pista_a_escena(x, y) for x, y in pol.exterior.coords]
        return Polygon(pts)
    negro = sbox(xi - W / 2, -pista.MARGEN_ATRAS, xi + W / 2, y_sup).union(
        sbox(xc - W / 2, y_inf, xc + W / 2, y_sup)).union(sbox(xd - W / 2, y_inf, xd + W / 2, y_meta))
    def semianillo(cx, cy, r_c, arriba):
        n = 60
        a = np.linspace(0, math.pi, n) if arriba else np.linspace(math.pi, 2 * math.pi, n)
        ext = [(cx + (r_c + W / 2) * math.cos(t), cy + (r_c + W / 2) * math.sin(t)) for t in a]
        inn = [(cx + (r_c - W / 2) * math.cos(t), cy + (r_c - W / 2) * math.sin(t)) for t in a[::-1]]
        return Polygon(ext + inn)
    negro = negro.union(semianillo(xi + R1, y_sup, R1, True)).union(semianillo(xc + R2, y_inf, R2, False)).buffer(0)
    pol_m = negro if negro.geom_type == "Polygon" else max(negro.geoms, key=lambda g: g.area)
    pol = a_escena_poly(pol_m)
    asfalto = color(extrude_polygon(pol, 1.0), (45, 45, 48, 255))
    borde = pol.buffer(2.0).difference(pol.buffer(-4.0))
    raya = color(extrude_polygon(borde, 1.3), (240, 240, 240, 255)) if not borde.is_empty else None
    minx, miny, maxx, maxy = pol.bounds
    suelo = color(caja(minx - 120, maxx + 120, miny - 120, maxy + 120, -6, -0.01), (62, 130, 70, 255))
    return trimesh.util.concatenate([m for m in (suelo, asfalto, raya) if m is not None])


# ------------------------------------------------------------------ escena
from monedas import pista  # noqa: E402  (se importa al final para que parametros pueda usarlo)

IMPRIMIBLES = {
    "vaso":              (vaso, 5, "Vaso con oreja de enganche (x5, uno por denominacion)"),
    "placa_portavasos_A": (lambda: placa_portavasos(0, 1), 1, "Placa del arco: vasos $50 y $100"),
    "placa_portavasos_B": (lambda: placa_portavasos(2, 2), 1, "Placa del arco: vaso $200"),
    "placa_portavasos_C": (lambda: placa_portavasos(3, 4), 1, "Placa del arco: vasos $500 y $1000"),
    "torre_servo":       (torre_servo, 1, "Torre hueca del servo SG90 (imprimir boca abajo)"),
    "canaleta":          (canaleta, 1, "Tolva giratoria + canal (va en el horn del servo)"),
    "tolva_entrada":     (tolva_entrada, 1, "Embudo de entrada de una moneda por vez"),
    "soporte_sensor_ir": (soporte_sensor_ir, 1, "Soporte del sensor IR de presencia"),
    "base_poste_celular": (base_poste_celular, 1, "Base del poste del celular"),
    "soporte_celular":   (soporte_celular, 1, "Bandeja del celular con collar al poste"),
    "enganche_carro":    (enganche_carro, 1, "Pasador de remolque para la parte trasera del carro"),
}
REFERENCIAS = {"carro": ref_carro, "banda": ref_banda, "termo": ref_termo, "pista": ref_pista}


def construir_todo():
    imp = {n: f() for n, (f, _, _) in IMPRIMIBLES.items()}
    ref = {n: f() for n, f in REFERENCIAS.items()}
    return imp, ref


def escena(imp, ref):
    """Escena armada. El carro y los vasos van como nodos separados para animarlos en el visor."""
    sc = trimesh.Scene()
    paleta = {
        "placa_portavasos_A": (235, 235, 235), "placa_portavasos_B": (235, 235, 235), "placa_portavasos_C": (235, 235, 235),
        "torre_servo": (240, 140, 30), "tolva_entrada": (90, 160, 230), "soporte_sensor_ir": (230, 70, 70),
        "base_poste_celular": (120, 120, 130), "soporte_celular": (120, 120, 130),
    }
    for n in ("placa_portavasos_A", "placa_portavasos_B", "placa_portavasos_C", "torre_servo"):
        sc.add_geometry(color(imp[n], paleta[n] + (255,)), node_name=n, geom_name=n)
    W = P.BANDA_ANCHO
    tol = imp["tolva_entrada"].copy(); tol.apply_translation([-P.BANDA_LARGO, 0, P.BANDA_ALTO])
    sc.add_geometry(color(tol, (90, 160, 230, 255)), node_name="tolva_entrada", geom_name="tolva_entrada_e")
    sen = rotz(imp["soporte_sensor_ir"], 90)                       # el brazo apunta hacia +Y (centro de la banda)
    sen.apply_translation([-P.BANDA_LARGO + 150, -(W / 2 + 14), 0])
    sc.add_geometry(color(sen, (230, 70, 70, 255)), node_name="sensor_ir", geom_name="sensor_ir_e")
    # camara: poste + base + bandeja del celular, 138 mm al lado de la banda
    py = W / 2 + 58
    px = -P.BANDA_LARGO + 150
    bp = imp["base_poste_celular"].copy(); bp.apply_translation([px, py, 0])
    sc.add_geometry(color(bp, (120, 120, 130, 255)), node_name="base_poste", geom_name="base_poste_e")
    z_t = P.BANDA_ALTO + P.CAMARA_ALTURA
    poste = cil(P.POSTE_D / 2, z_t + 40 - 6, x=px, y=py, z=6)
    sc.add_geometry(color(poste, (200, 200, 205, 255)), node_name="poste", geom_name="poste_e")
    w, l, e = P.CELULAR
    bw, bl = w + 18, l + 14
    cel = imp["soporte_celular"].copy()
    cel.apply_translation([px - bw / 2, py - (bl + 20), z_t])
    sc.add_geometry(color(cel, (120, 120, 130, 255)), node_name="soporte_celular", geom_name="soporte_celular_e")
    sc.add_geometry(color(canaleta_en_escena(90), (255, 215, 0, 255)), node_name="canaleta", geom_name="canaleta")
    # vasos: uno por denominacion, color por valor
    cols = [(210, 210, 215), (235, 190, 60), (190, 190, 200), (230, 170, 40), (245, 210, 60)]
    v = imp["vaso"]
    for k in range(5):
        x, y = P.pos_vaso(k)
        phi = 90 - P.ANGULOS_SERVO[k]
        vv = rotz(v, phi)
        vv.apply_translation([x, y, P.PLACA_ESP])
        sc.add_geometry(color(vv, cols[k] + (255,)), node_name=f"vaso_{k}", geom_name=f"vaso_{k}")
    sc.add_geometry(ref["banda"], node_name="banda", geom_name="banda")
    sc.add_geometry(ref["pista"], node_name="pista", geom_name="pista")
    sc.add_geometry(ref["carro"], node_name="carro", geom_name="carro")
    for i, pos in enumerate(posiciones_termos(), 1):
        t = ref["termo"].copy()
        t.apply_translation([pos[0], pos[1], 0])
        sc.add_geometry(t, node_name=f"termo_{i}", geom_name=f"termo_{i}")
    return sc


def posiciones_termos():
    """Centros (X, Y) de la escena de los 3 termos, igual que pista.dibujar()."""
    xi, xc, xd, y_sup, y_inf, y_meta = pista.geometria()
    W = pista.ANCHO_CARRIL
    out = []
    for t, d, lado in pista.OBSTACULOS:
        x0 = (xi, xc, xd)[t - 1]
        y0 = (0.0, y_sup, y_inf)[t - 1]
        sentido = 1 if t in (1, 3) else -1
        lado_x = (1 if lado == "der" else -1) * sentido
        cx = x0 + lado_x * (W / 2 + pista.OBSTACULO_DIAM / 2 - pista.INTRUSION)
        out.append(P.pista_a_escena(cx, y0 + d * sentido))
    return out


# ------------------------------------------------------------------ validaciones
def validar(imp, ref):
    """Devuelve (lista_de_problemas, lista_de_avisos)."""
    err, avisos = [], []
    for n, m in imp.items():
        if not m.is_watertight:
            err.append(f"{n}: la malla no es hermetica (no imprimible)")
        if m.volume <= 0:
            err.append(f"{n}: volumen no positivo")
        dx, dy, dz = m.extents
        if min(max(dx, dy), P.LIMITE_CAMA) < max(dx, dy) and max(dx, dy) > P.LIMITE_CAMA and n != "tolva_entrada":
            err.append(f"{n}: {max(dx, dy):.0f} mm no cabe en la cama de {P.LIMITE_CAMA:.0f} mm")
    # vasos: separacion entre vecinos
    for k in range(4):
        (x0, y0), (x1, y1) = P.pos_vaso(k), P.pos_vaso(k + 1)
        d = math.hypot(x1 - x0, y1 - y0)
        if d < P.VASO_DE + 2.5:
            err.append(f"vasos {k} y {k+1} a {d:.1f} mm entre centros: se tocan (minimo {P.VASO_DE + 2.5:.1f})")
    # canaleta barriendo el arco: no puede chocar con ningun vaso ni con la torre
    sc_vasos = []
    for k in range(5):
        x, y = P.pos_vaso(k)
        vv = rotz(imp["vaso"], 90 - P.ANGULOS_SERVO[k])
        vv.apply_translation([x, y, P.PLACA_ESP])
        sc_vasos.append(vv)
    peor = 0.0
    for ang in range(P.ANGULOS_SERVO[0], P.ANGULOS_SERVO[-1] + 1, 5):
        c = canaleta_en_escena(ang)
        for vv in sc_vasos:
            vol = inter(c, vv).volume if c.bounds[1][0] > vv.bounds[0][0] else 0.0
            peor = max(peor, abs(vol))
        if abs(inter(c, imp["torre_servo"]).volume) > 1e-6:
            err.append(f"la canaleta a {ang} grados choca con la torre del servo")
    if peor > 1e-6:
        err.append(f"la canaleta choca con un vaso al girar (volumen {peor:.1f} mm3)")
    # la punta debe quedar sobre el vaso al angulo de cada vaso
    for k, a in enumerate(P.ANGULOS_SERVO):
        x, y = P.pos_vaso(k)
        cx, cy = P.dir_servo(a)
        px, py = P.PIVOTE_X + P.PUNTA_R * cx, P.PUNTA_R * cy
        if math.hypot(px - x, py - y) > P.VASO_DI / 2:
            err.append(f"vaso {k}: la punta cae a {math.hypot(px - x, py - y):.0f} mm del centro del vaso")
    # pendiente
    if P.PENDIENTE_GRADOS < 8:
        err.append(f"pendiente de la canaleta {P.PENDIENTE_GRADOS:.1f} grados: demasiado plana")
    elif P.PENDIENTE_GRADOS < 18:
        avisos.append(f"pendiente de la canaleta {P.PENDIENTE_GRADOS:.1f} grados (<18): la moneda necesita el empuje de la banda; "
                      "usa PETG/PLA liso o cinta transparente en el canal")
    # el sensor debe caer sobre el centro de la banda
    return err, avisos


# ------------------------------------------------------------------ salida
def guardar(imp, ref, sc):
    os.makedirs(os.path.join(AQUI, "stl"), exist_ok=True)
    os.makedirs(os.path.join(AQUI, "referencia"), exist_ok=True)
    for n, m in imp.items():
        m.export(os.path.join(AQUI, "stl", f"{n}.stl"))
    for n, m in ref.items():
        m.export(os.path.join(AQUI, "referencia", f"{n}.stl"))
    sc.export(os.path.join(AQUI, "escena.glb"))


def tabla_piezas(imp):
    filas = ["| Pieza | Cant. | Medidas XxYxZ (mm) | Volumen (cm³) | Descripción |", "|---|---|---|---|---|"]
    for n, (_, cant, desc) in IMPRIMIBLES.items():
        m = imp[n]
        e = m.extents
        filas.append(f"| `stl/{n}.stl` | {cant} | {e[0]:.0f} × {e[1]:.0f} × {e[2]:.0f} | {m.volume / 1000:.1f} | {desc} |")
    return "\n".join(filas)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    imp, ref = construir_todo()
    sc = escena(imp, ref)
    guardar(imp, ref, sc)
    with open(os.path.join(AQUI, "PIEZAS.md"), "w", encoding="utf-8") as fh:
        fh.write("# Piezas imprimibles (generado por `cad/generar_cad.py`)\n\n" + tabla_piezas(imp) +
                 f"\n\nPendiente de la canaleta: {P.PENDIENTE_GRADOS:.1f}°.\n")
    print(tabla_piezas(imp))
    print(f"\nPendiente de la canaleta: {P.PENDIENTE_GRADOS:.1f} grados")
    if a.check:
        err, avisos = validar(imp, ref)
        for e in err:
            print("ERROR:", e)
        for v in avisos:
            print("AVISO:", v)
        print("VALIDACION:", "FALLA" if err else "OK")
        return 1 if err else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
