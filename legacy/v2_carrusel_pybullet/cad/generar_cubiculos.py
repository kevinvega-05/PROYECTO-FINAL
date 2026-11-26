"""
generar_cubiculos.py - Genera las piezas y planos de los cubículos de clasificación.

    python cad/generar_cubiculos.py

Salidas (en cad/):
    vaso.stl               vaso cilíndrico (x9, uno por tipo de moneda)
    disco_portavasos.stl   disco con 9 alojamientos y cubo para el eje del motor
    cubiculos.dxf          planos 2D acotados (vista superior y corte), mm
y docs/cubiculos_plano.png con el mismo plano para el README.
Todas las medidas salen de config_fisico.py.
"""
import math
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import trimesh
import config_fisico as F
from config import TIPOS

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..")
SEG = 96


def cil(r, h, z0=0.0, x=0.0, y=0.0):
    m = trimesh.creation.cylinder(radius=r, height=h, sections=SEG)
    m.apply_translation([x, y, z0 + h / 2])
    return m


def vaso():
    ext = cil(F.VASO_DE / 2, F.VASO_H)
    hueco = cil(F.VASO_DI / 2, F.VASO_H, z0=F.VASO_FONDO)
    return ext.difference(hueco, engine="manifold")


def disco():
    d = cil(F.DISCO_RADIO, F.DISCO_ESP)
    d = d.union(cil(F.CUBO_R, F.DISCO_ESP + F.CUBO_H), engine="manifold")
    for k in range(F.N_TIPOS):
        a = F.angulo_vaso_local(k)
        x, y = F.RADIO_VASOS * math.cos(a), F.RADIO_VASOS * math.sin(a)
        d = d.difference(cil(F.SOCKET_D / 2, F.SOCKET_PROF + 0.1,
                             z0=F.DISCO_ESP - F.SOCKET_PROF, x=x, y=y), engine="manifold")
    d = d.difference(cil(F.EJE_D / 2, F.DISCO_ESP + F.CUBO_H + 1, z0=-0.5), engine="manifold")
    # tornillo de fijación M3 radial en el cubo
    tor = trimesh.creation.cylinder(radius=1.6, height=F.CUBO_R + 1, sections=24)
    tor.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
    tor.apply_translation([(F.CUBO_R + 1) / 2, 0, F.DISCO_ESP + F.CUBO_H / 2])
    return d.difference(tor, engine="manifold")


def guardar_stl():
    v, d = vaso(), disco()
    v.export(os.path.join(AQUI, "vaso.stl"))
    d.export(os.path.join(AQUI, "disco_portavasos.stl"))
    return v, d


# ------------------------------------------------------------------ DXF
def guardar_dxf():
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = 4
    for n, c in (("DISCO", 7), ("VASOS", 3), ("EJE", 1), ("BANDA", 8), ("COTAS", 1)):
        doc.layers.add(n, color=c)
    m = doc.modelspace()
    # ---- vista superior (origen = eje del carrusel)
    m.add_circle((0, 0), F.DISCO_RADIO, dxfattribs={"layer": "DISCO"})
    m.add_circle((0, 0), F.CUBO_R, dxfattribs={"layer": "DISCO"})
    m.add_circle((0, 0), F.EJE_D / 2, dxfattribs={"layer": "EJE"})
    for k in range(F.N_TIPOS):
        a = F.angulo_vaso_local(k)
        x, y = F.RADIO_VASOS * math.cos(a), F.RADIO_VASOS * math.sin(a)
        m.add_circle((x, y), F.SOCKET_D / 2, dxfattribs={"layer": "DISCO"})
        m.add_circle((x, y), F.VASO_DE / 2, dxfattribs={"layer": "VASOS"})
        m.add_circle((x, y), F.VASO_DI / 2, dxfattribs={"layer": "VASOS"})
        m.add_text(f"{k}: {TIPOS[k]['id']}", height=3.2,
                   dxfattribs={"layer": "COTAS", "insert": (x - 14, y - 1.5)})
    # borde de la banda (a la izquierda, x negativa = hacia la banda)
    bx = -F.EJE_X
    m.add_line((bx, -F.BANDA_ANCHO / 2), (bx, F.BANDA_ANCHO / 2), dxfattribs={"layer": "BANDA"})
    m.add_line((bx - 60, -F.BANDA_ANCHO / 2), (bx, -F.BANDA_ANCHO / 2), dxfattribs={"layer": "BANDA"})
    m.add_line((bx - 60, F.BANDA_ANCHO / 2), (bx, F.BANDA_ANCHO / 2), dxfattribs={"layer": "BANDA"})
    m.add_text("BANDA", height=5, dxfattribs={"layer": "BANDA", "insert": (bx - 45, 0)})
    m.add_text("VISTA SUPERIOR (mm)", height=6, dxfattribs={"insert": (-F.DISCO_RADIO, F.DISCO_RADIO + 15)})
    # ---- corte del vaso (a la derecha)
    ox = F.DISCO_RADIO + 60
    for sx in (-1, 1):
        xi, xe = sx * F.VASO_DI / 2, sx * F.VASO_DE / 2
        m.add_lwpolyline([(ox + xi, F.VASO_FONDO), (ox + xe, F.VASO_FONDO),
                          (ox + xe, F.VASO_H), (ox + xi, F.VASO_H)], dxfattribs={"layer": "VASOS"})
    m.add_line((ox - F.VASO_DE / 2, 0), (ox + F.VASO_DE / 2, 0), dxfattribs={"layer": "VASOS"})
    m.add_line((ox - F.VASO_DE / 2, 0), (ox - F.VASO_DE / 2, F.VASO_H), dxfattribs={"layer": "VASOS"})
    m.add_line((ox + F.VASO_DE / 2, 0), (ox + F.VASO_DE / 2, F.VASO_H), dxfattribs={"layer": "VASOS"})
    m.add_text("CORTE DEL VASO", height=6, dxfattribs={"insert": (ox - 25, F.VASO_H + 15)})
    m.add_linear_dim(base=(ox, -12), p1=(ox - F.VASO_DE / 2, 0), p2=(ox + F.VASO_DE / 2, 0),
                     dimstyle="EZDXF").render()
    m.add_linear_dim(base=(ox + F.VASO_DE / 2 + 12, 0), p1=(ox + F.VASO_DE / 2, 0),
                     p2=(ox + F.VASO_DE / 2, F.VASO_H), angle=90, dimstyle="EZDXF").render()
    m.add_diameter_dim(center=(0, 0), radius=F.DISCO_RADIO, angle=35, dimstyle="EZDXF").render()
    doc.saveas(os.path.join(AQUI, "cubiculos.dxf"))


# ------------------------------------------------------------------ PNG para el README
def guardar_png():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Rectangle
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6.4), gridspec_kw={"width_ratios": [1.25, 1]})
    # vista superior, en marco de la banda (x hacia el carrusel)
    a1.set_aspect("equal")
    a1.add_patch(Rectangle((-80, -F.BANDA_ANCHO / 2), 80, F.BANDA_ANCHO, fc="#ecf0f1", ec="#333"))
    a1.text(-40, 24, "BANDA", ha="center", va="center", color="#555", fontsize=11)
    a1.annotate("", xy=(-4, 0), xytext=(-60, 0), arrowprops=dict(arrowstyle="->", color="#2c3e50", lw=2))
    a1.add_patch(Circle((F.EJE_X, 0), F.DISCO_RADIO, fc="#f4f6f6", ec="#333", lw=1.5))
    a1.add_patch(Circle((F.EJE_X, 0), F.CUBO_R, fc="#bdc3c7", ec="#333"))
    for k in range(F.N_TIPOS):
        a = F.angulo_vaso_local(k) + F.yaw_disco_para_llenar(0)
        x, y = F.EJE_X + F.RADIO_VASOS * math.cos(a), F.RADIO_VASOS * math.sin(a)
        col = "#e67e22" if k == 0 else "#27ae60"
        a1.add_patch(Circle((x, y), F.VASO_DE / 2, fc="#d5f5e3", ec=col, lw=1.5))
        a1.add_patch(Circle((x, y), F.VASO_DI / 2, fc="white", ec=col, lw=1))
        a1.text(x, y + 2.5, str(k), ha="center", va="center", fontsize=11, fontweight="bold")
        a1.text(x, y - 5.5, TIPOS[k]["id"].replace("_", "\n"), ha="center", va="center", fontsize=6.2)
    a1.annotate("", xy=(F.EJE_X + F.DISCO_RADIO, F.DISCO_RADIO + 14), xytext=(F.EJE_X, F.DISCO_RADIO + 14),
                arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    a1.text(F.EJE_X + F.DISCO_RADIO / 2, F.DISCO_RADIO + 17, f"R disco = {F.DISCO_RADIO:.1f}",
            ha="center", color="#c0392b", fontsize=9, fontweight="bold")
    a1.text(F.EJE_X, -F.DISCO_RADIO - 16,
            f"9 vasos a R = {F.RADIO_VASOS:.1f} mm, cada {F.PASO_GRADOS:.0f}°  ·  vaso en la estación de llenado en naranja",
            ha="center", fontsize=9, color="#444")
    a1.set_xlim(-85, F.EJE_X + F.DISCO_RADIO + 15)
    a1.set_ylim(-F.DISCO_RADIO - 28, F.DISCO_RADIO + 30)
    a1.set_title("A. Vista superior (mm)", loc="left", fontweight="bold")
    a1.axis("off")
    # corte lateral en el eje y=0 del vaso de llenado + banda
    a2.set_aspect("equal")
    z0 = 0
    a2.add_patch(Rectangle((-80, F.BANDA_Z - 5), 80, 5, fc="#7f8c8d", ec="#333"))
    a2.add_patch(Rectangle((-80, F.BANDA_Z - 50), 80, 45, fc="#f4f6f6", ec="#333"))
    a2.plot([-90, F.EJE_X + 55], [0, 0], color="#333", lw=2)
    cx = F.DIST_BORDE_A_VASO
    a2.add_patch(Rectangle((F.EJE_X - F.DISCO_RADIO, F.DISCO_BASE_Z), 2 * F.DISCO_RADIO, F.DISCO_ESP,
                           fc="#d7dbdd", ec="#333"))
    a2.add_patch(Rectangle((F.EJE_X - F.CUBO_R, F.DISCO_TOPE_Z), 2 * F.CUBO_R, F.CUBO_H, fc="#bdc3c7", ec="#333"))
    vz = F.VASO_TOPE_Z - F.VASO_H
    a2.add_patch(Rectangle((cx - F.VASO_DE / 2, vz), F.VASO_DE, F.VASO_H, fc="#d5f5e3", ec="#27ae60", lw=1.5))
    a2.add_patch(Rectangle((cx - F.VASO_DI / 2, vz + F.VASO_FONDO), F.VASO_DI, F.VASO_H - F.VASO_FONDO, fc="white", ec="#27ae60"))
    a2.annotate("", xy=(cx, F.BANDA_Z + 12), xytext=(cx, F.VASO_TOPE_Z + 1),
                arrowprops=dict(arrowstyle="<-", color="#e67e22", lw=2))
    a2.text(cx + 4, F.BANDA_Z + 8, "moneda", color="#e67e22", fontsize=9)
    a2.text(-40, F.BANDA_Z - 28, "banda", ha="center", fontsize=9, color="#555")
    a2.annotate("", xy=(-96, 0), xytext=(-96, F.BANDA_Z), arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    a2.text(-100, F.BANDA_Z / 2, f"{F.BANDA_Z:.0f}", color="#c0392b", ha="right", fontsize=9, fontweight="bold")
    a2.annotate("", xy=(cx + 36, F.VASO_TOPE_Z), xytext=(cx + 36, F.BANDA_Z), arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    a2.text(cx + 40, (F.VASO_TOPE_Z + F.BANDA_Z) / 2 - 2, f"caída {F.CAIDA:.0f}", color="#c0392b", fontsize=9, fontweight="bold")
    a2.annotate("", xy=(cx + F.VASO_DE / 2 + 16, vz), xytext=(cx + F.VASO_DE / 2 + 16, F.VASO_TOPE_Z),
                arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    a2.text(cx + F.VASO_DE / 2 + 20, vz + F.VASO_H / 2, f"vaso {F.VASO_H:.0f}", color="#c0392b",
            ha="left", fontsize=9, fontweight="bold")
    a2.annotate("", xy=(cx - F.VASO_DI / 2, vz - 8), xytext=(cx + F.VASO_DI / 2, vz - 8),
                arrowprops=dict(arrowstyle="<->", color="#c0392b"))
    a2.text(cx + 20, vz - 20, f"Ø int {F.VASO_DI:.0f} / Ø ext {F.VASO_DE:.0f}", color="#c0392b", ha="center",
            fontsize=9, fontweight="bold")
    a2.set_xlim(-110, F.EJE_X + 60)
    a2.set_ylim(-32, F.BANDA_Z + 25)
    a2.set_title("B. Corte lateral en la estación de llenado (mm)", loc="left", fontweight="bold")
    a2.axis("off")
    fig.text(0.01, 0.01, "Plano a escala (1:1 entre ejes). Banda: medidas reales; cubículos: diseño. Monedas: valores de referencia.",
             fontsize=8, color="#555")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(os.path.join(RAIZ, "docs", "cubiculos_plano.png"), dpi=130)


if __name__ == "__main__":
    os.makedirs(os.path.join(RAIZ, "docs"), exist_ok=True)
    v, d = guardar_stl()
    print("vaso.stl         watertight:", v.is_watertight, "vol mm3:", round(v.volume))
    print("disco_portavasos watertight:", d.is_watertight, "vol mm3:", round(d.volume))
    guardar_dxf()
    guardar_png()
    print("OK: cad/vaso.stl, cad/disco_portavasos.stl, cad/cubiculos.dxf, docs/cubiculos_plano.png")
