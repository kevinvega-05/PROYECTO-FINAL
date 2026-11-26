"""
dashboard.py - Tablero Streamlit del sistema de monedas.

    streamlit run monedas/dashboard.py

Lee datos/estado.json (lo publica `python -m monedas`) y escribe datos/comando.json para despachar un vaso.
Si el sistema no esta corriendo, muestra un aviso en lugar de fallar.
"""
import json
import os
import sys
import time

import streamlit as st

# `streamlit run monedas/dashboard.py` solo agrega la carpeta del script al path: agregamos la raiz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monedas import config as cfg
from monedas.chatbot import enviar_despacho

st.set_page_config(page_title="Monedas inteligentes", page_icon="🪙", layout="wide")
st.title("🪙 Sistema logístico de monedas inteligentes")
st.caption("UMNG · Ingeniería Mecatrónica — banda, visión por computador, canaleta con servo, 5 vasos y carro remolcador")


def leer_estado():
    try:
        with open(cfg.ESTADO_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def pesos(v):
    return "$" + f"{v:,}".replace(",", ".")


def leer_registro(n=200):
    import csv
    try:
        with open(cfg.REGISTRO_PATH, encoding="utf-8") as fh:
            filas = list(csv.DictReader(fh))
    except OSError:
        return []
    return filas[-n:][::-1]


@st.fragment(run_every=1.0)
def panel():
    est = leer_estado()
    if est is None:
        st.warning("Sin datos todavía. Arranca el sistema con `python -m monedas` (o `python -m monedas --demo`).")
        return
    if time.time() - os.path.getmtime(cfg.ESTADO_PATH) > 5:
        st.error("El sistema dejó de publicar: datos/estado.json no se actualiza hace más de 5 s.")

    tab_res, tab_carro, tab_reg = st.tabs(["Resumen", "Carro y conexiones", "Registro"])

    with tab_res:
        c = st.columns(4)
        c[0].metric("Monedas en los vasos", est["cantidad_total"])
        c[1].metric("Valor total", pesos(est["valor"]))
        c[2].metric("Peso", f"{est['peso_g']} g")
        c[3].metric("Sin reconocer", est.get("rechazo", {}).get("cantidad", 0))
        st.caption(f"Etapa: **{est['etapa']}**  ·  Último evento: {est['ultimo_evento']}")

        st.subheader("Vasos")
        cols = st.columns(len(cfg.CUBICULO_DE_VALOR))
        vasos = est.get("vasos", {})
        for col, (valor, k) in zip(cols, cfg.CUBICULO_DE_VALOR.items()):
            v = vasos.get(str(valor), {"cantidad": 0, "despachado": False})
            col.metric(f"Vaso {k} · {pesos(valor)}", v["cantidad"], "despachado" if v["despachado"] else None)
            if col.button("Despachar", key=f"d_{valor}", disabled=v["cantidad"] == 0):
                enviar_despacho(valor)
                st.toast(f"Orden enviada: vaso de {pesos(valor)}")

    with tab_carro:
        car = est["carro"]
        k = st.columns(4)
        k[0].metric("Estado", car["estado"])
        k[1].metric("Enganchado", "sí" if car["enganchado"] else "no")
        k[2].metric("Obstáculos tocados", car["obstaculos_tocados"])
        d = est.get("distancia_cm")
        k[3].metric("Distancia al frente", f"{d} cm" if d is not None else "—")
        con = est.get("conexiones", {})
        st.write(f"Estación (ESP32): {'✅' if con.get('estacion') else '—'}   ·   "
                 f"Carro (Bluetooth): {'✅' if con.get('carro') else '—'}   ·   "
                 f"Sensor de presencia: {'● hay moneda' if con.get('presencia') else '○'}")
        b = est.get("banda", {})
        st.write(f"Banda: {'encendida al %d %%' % b.get('pct', 0) if b.get('activa') else 'apagada'}   ·   "
                 f"Canaleta apuntando al vaso: {est.get('canaleta', {}).get('cubiculo')}   ·   "
                 f"Monedas en camino: {est.get('en_camino', 0)}")

    with tab_reg:
        filas = leer_registro()
        if filas:
            st.dataframe(filas, use_container_width=True, hide_index=True)
        else:
            st.info("Aún no hay eventos en datos/registro_monedas.csv.")


panel()
