"""
test_cubiculos_reales.py - Prueba en PyBullet (sin ventana) de que CADA moneda cae en SU cubículo.

Usa las piezas reales (cad/vaso.stl y cad/disco_portavasos.stl) con las medidas de config_fisico.py:
la moneda sale por el extremo de la banda (80 mm de altura), cae 12 mm y debe quedar dentro del vaso
que le corresponde según su tipo (índice en config.TIPOS). Se varía la velocidad de la banda y el
desvío lateral de la moneda.

    python tests/test_cubiculos_reales.py
"""
import math
import os
import sys
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, ".."))
sys.path.insert(0, RAIZ)
import pybullet as p
import config_fisico as F
from config import TIPOS

MM = 0.001
VELOCIDADES = (100.0, 150.0, 250.0)      # mm/s
DESVIOS = (-6.0, 0.0, 6.0)               # mm, desvío lateral permitido por las guías


def malla_estatica(archivo, pos, yaw=0.0):
    col = p.createCollisionShape(p.GEOM_MESH, fileName=archivo, meshScale=[MM] * 3,
                                 flags=p.GEOM_FORCE_CONCAVE_TRIMESH)
    return p.createMultiBody(0, col, basePosition=pos, baseOrientation=p.getQuaternionFromEuler([0, 0, yaw]))


def construir(k_llenado):
    p.resetSimulation()
    p.setGravity(0, 0, -9.81)
    p.setTimeStep(1 / 480)
    # banda: cinta recta, fricción ~0 para que la moneda conserve la velocidad de la cinta
    L = 0.30
    b = p.createCollisionShape(p.GEOM_BOX, halfExtents=[L / 2, F.BANDA_ANCHO * MM / 2, 0.0025])
    banda = p.createMultiBody(0, b, basePosition=[-L / 2, 0, F.BANDA_Z * MM - 0.0025])
    p.changeDynamics(banda, -1, lateralFriction=0.0, restitution=0.0)
    # disco y vasos, con el vaso k_llenado en la estación de llenado
    yaw = F.yaw_disco_para_llenar(k_llenado)
    disco = malla_estatica(os.path.join(RAIZ, "cad", "disco_portavasos.stl"),
                           [F.EJE_X * MM, F.EJE_Y * MM, F.DISCO_BASE_Z * MM], yaw)
    p.changeDynamics(disco, -1, restitution=0.1, lateralFriction=0.5)
    vasos = []
    for k in range(F.N_TIPOS):
        x, y = F.pos_vaso(k, yaw)
        v = malla_estatica(os.path.join(RAIZ, "cad", "vaso.stl"),
                           [x * MM, y * MM, (F.VASO_TOPE_Z - F.VASO_H) * MM], 0.0)
        p.changeDynamics(v, -1, restitution=0.1, lateralFriction=0.5)
        vasos.append((x, y))
    return vasos


def lanzar(k, vel, desvio):
    t = TIPOS[k]
    r = t["diam_mm"] * MM / 2
    esp = 0.0025
    col = p.createCollisionShape(p.GEOM_CYLINDER, radius=r, height=esp)
    m = p.createMultiBody(t["masa_g"] / 1000.0, col,
                          basePosition=[-r - 0.001, desvio * MM, F.BANDA_Z * MM + esp / 2 + 0.0005])
    p.changeDynamics(m, -1, restitution=0.1, lateralFriction=0.4, linearDamping=0.0, angularDamping=0.02)
    p.resetBaseVelocity(m, [vel * MM, 0, 0])
    return m


def dentro_de_vaso(pos, vasos):
    """Índice del vaso que contiene la posición (mm), o None."""
    x, y, z = pos[0] / MM, pos[1] / MM, pos[2] / MM
    for i, (vx, vy) in enumerate(vasos):
        if math.hypot(x - vx, y - vy) < F.VASO_DI / 2 and (F.VASO_TOPE_Z - F.VASO_H) <= z <= F.VASO_TOPE_Z:
            return i
    return None


def main():
    p.connect(p.DIRECT)
    fallos, total = [], 0
    for k in range(F.N_TIPOS):
        vasos = construir(k)
        for vel in VELOCIDADES:
            for des in DESVIOS:
                m = lanzar(k, vel, des)
                for _ in range(int(2.0 * 480)):
                    p.stepSimulation()
                pos, _ = p.getBasePositionAndOrientation(m)
                dst = dentro_de_vaso(pos, vasos)
                total += 1
                # el vaso en la estación de llenado es el que tiene el tipo k (misma ranura k del disco)
                ok = dst == k
                if not ok:
                    fallos.append((TIPOS[k]["id"], vel, des, dst, [round(c / MM, 1) for c in pos]))
                p.removeBody(m)
    p.disconnect()
    print(f"{total - len(fallos)}/{total} lanzamientos terminaron en su cubículo "
          f"({F.N_TIPOS} tipos x {len(VELOCIDADES)} velocidades x {len(DESVIOS)} desvíos)")
    for f in fallos:
        print("  FALLO:", f)
    assert not fallos, "hay monedas que no caen en su cubículo"
    print("test_cubiculos_reales: OK")


if __name__ == "__main__":
    main()
