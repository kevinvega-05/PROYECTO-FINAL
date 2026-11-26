"""dibujos.py - Planos 2D (planta y corte) del selector, dibujados con los MISMOS parametros del CAD.

    python cad/dibujos.py      # escribe docs/img/cad_planta.png y docs/img/cad_corte.png
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Arc, Circle, Rectangle  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, ".."))
import parametros as P  # noqa: E402

OUT = os.path.join(AQUI, "..", "docs", "img")
FONDO, TXT, LINEA, ACENTO, VASO, CANAL = "#0e1116", "#e8ecf2", "#5b6577", "#f5c542", "#4fc3f7", "#ff7043"


def _ax(figsize):
    fig, ax = plt.subplots(figsize=figsize, dpi=150, facecolor=FONDO)
    ax.set_facecolor(FONDO)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def planta():
    fig, ax = _ax((9, 7))
    px = P.PIVOTE_X
    # banda
    ax.add_patch(Rectangle((-150, -P.BANDA_ANCHO / 2), 150, P.BANDA_ANCHO, fc="#2a1414", ec="#c0392b", lw=1.5))
    ax.text(-75, 0, "BANDA\n160 mm", color="#e57373", ha="center", va="center", fontsize=10)
    # arco R_VASOS
    ax.add_patch(Arc((px, 0), 2 * P.R_VASOS, 2 * P.R_VASOS, theta1=-70, theta2=70, color=LINEA, ls="--", lw=1))
    ax.add_patch(Circle((px, 0), P.TOLVA_D / 2, fc="none", ec=ACENTO, lw=1.5))
    ax.plot([px], [0], "o", color=ACENTO, ms=5)
    ax.annotate("pivote del servo\n(16 mm tras la banda)", (px, 0), (px - 70, 95), color=ACENTO, fontsize=8,
                arrowprops=dict(arrowstyle="->", color=ACENTO), ha="center")
    for k, ang in enumerate(P.ANGULOS_SERVO):
        cx, cy = P.dir_servo(ang)
        ax.plot([px, px + (P.PUNTA_R) * cx], [0, P.PUNTA_R * cy], color=CANAL, lw=1.2, alpha=.8)
        vx, vy = P.pos_vaso(k)
        ax.add_patch(Circle((vx, vy), P.VASO_DE / 2, fc="#16384a", ec=VASO, lw=1.5))
        nombre = ["$50", "$100", "$200", "$500", "$1000"][k]
        ax.text(vx + 38 * cx, vy + 38 * cy, f"{nombre}\n{ang}°", color=TXT, ha="center", va="center", fontsize=9)
    ax.add_patch(Arc((px, 0), 70, 70, theta1=0, theta2=0, color=TXT))
    ax.annotate("", (px + P.R_VASOS, 0), (px, 0), arrowprops=dict(arrowstyle="<->", color=TXT, lw=.8))
    ax.text(px + P.R_VASOS / 2, -9, f"R = {P.R_VASOS:.0f} mm", color=TXT, ha="center", fontsize=8)
    ax.text(px + P.PUNTA_R - 30, 12, "punta canaleta", color=CANAL, fontsize=7, ha="center")
    ax.set_xlim(-160, 215)
    ax.set_ylim(-150, 150)
    ax.set_title("Planta del selector: 5 vasos sobre un arco, la canaleta apunta con el servo",
                 color=TXT, fontsize=11, pad=10)
    fig.savefig(os.path.join(OUT, "cad_planta.png"), facecolor=FONDO, bbox_inches="tight")
    plt.close(fig)


def corte():
    fig, ax = _ax((9, 5))
    px = P.PIVOTE_X
    zb = P.BANDA_ALTO
    # mesa y banda
    ax.add_patch(Rectangle((-160, 0), 160, zb - 14, fc="#222", ec=LINEA))
    ax.add_patch(Rectangle((-160, zb - 14), 160, 14, fc="#5a1f1f", ec="#c0392b"))
    ax.text(-80, zb - 7, "banda", color="#e57373", ha="center", va="center", fontsize=8)
    # torre del servo
    ax.add_patch(Rectangle((px - 22, 0), 44, P.TORRE_ALTO, fc="#3a4a3a", ec="#8bc34a"))
    ax.text(px, P.TORRE_ALTO / 2, "torre\nservo", color="#c5e1a5", ha="center", va="center", fontsize=8)
    # placa + vaso
    xv = px + P.R_VASOS
    ax.add_patch(Rectangle((xv - 30, 0), 60, P.PLACA_ESP, fc="#8d6e63", ec=TXT))
    ax.add_patch(Rectangle((xv - P.VASO_DE / 2, P.PLACA_ESP), P.VASO_DE, P.VASO_ALTO, fc="#16384a", ec=VASO))
    ax.text(xv, P.PLACA_ESP + P.VASO_ALTO / 2, "vaso", color=TXT, ha="center", va="center", fontsize=8)
    # canaleta (pendiente)
    ax.plot([px, px + P.PUNTA_R], [P.PIVOTE_Z, P.PUNTA_Z], color=CANAL, lw=4, solid_capstyle="round")
    ax.plot([px, px + P.PUNTA_R], [P.PIVOTE_Z, P.PIVOTE_Z], color=LINEA, ls=":", lw=1)
    ax.add_patch(Arc((px, P.PIVOTE_Z), 80, 80, theta1=-P.PENDIENTE_GRADOS, theta2=0, color=ACENTO))
    ax.text(px + 44, P.PIVOTE_Z - 7, f"{P.PENDIENTE_GRADOS:.1f}°", color=ACENTO, fontsize=10)
    # cotas
    def cota(x, z0, z1, texto, dx=10):
        ax.annotate("", (x, z1), (x, z0), arrowprops=dict(arrowstyle="<->", color=TXT, lw=.8))
        ax.text(x + dx, (z0 + z1) / 2, texto, color=TXT, fontsize=8, va="center")
    cota(xv + 38, 0, P.PIVOTE_Z, f"pivote {P.PIVOTE_Z:.0f}", 6)
    cota(xv + 80, 0, P.PUNTA_Z, f"punta {P.PUNTA_Z:.0f}", 6)
    cota(xv - 40, 0, P.BORDE_VASO_Z, f"borde {P.BORDE_VASO_Z:.0f}", -4)
    ax.texts[-1].set_ha("right")
    ax.set_xlim(-165, xv + 140)
    ax.set_ylim(-8, P.PIVOTE_Z + 25)
    ax.set_title("Corte lateral: la moneda baja por gravedad, sin motor extra",
                 color=TXT, fontsize=11, pad=10)
    fig.savefig(os.path.join(OUT, "cad_corte.png"), facecolor=FONDO, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    planta()
    corte()
    print("ok -> docs/img/cad_planta.png, cad_corte.png")
