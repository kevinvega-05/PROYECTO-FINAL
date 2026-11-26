"""
estado.py - Estado compartido del sistema, publicado en datos/estado.json.

El formato es el CONTRATO con el chatbot y el dashboard (no lo cambies sin actualizarlos):
    t, etapa, ultimo_evento, monedas{id: n}, cantidad_total, peso_g, valor,
    cubiculos{id_de_tipo: {cantidad, despachado}}         # 9 clases (actual/antigua)
    vasos{"50": {cantidad, despachado}, ...}               # 5 vasos fisicos
    carro{x, y, yaw, estado, enganchado, obstaculos_detectados, obstaculos_tocados}
    rechazo{cantidad}, en_camino, banda{activa, pct}, canaleta{cubiculo}, distancia_cm, conexiones{...}
"""
import csv
import json
import os
import threading
import time
from collections import Counter

from monedas import clases as mc
from monedas import config as cfg
from monedas.tipos import TIPO_POR_ID, TIPOS


class Estado:
    def __init__(self):
        self.lock = threading.RLock()
        self.t0 = time.time()
        self.etapa = "iniciando"
        self.ultimo_evento = ""
        self.cont = Counter()                       # por id de tipo: monedas que YA cayeron
        self.cubiculos = {t["id"]: {"cantidad": 0, "despachado": False} for t in TIPOS}
        self.vaso_despachado = {v: False for v in cfg.IDS_DE_VALOR}   # por denominacion
        self.rechazadas = 0
        self.total = 0
        self.valor = 0
        self.peso_g = 0.0
        self.en_camino = 0                          # contadas por la camara, aun no han caido
        self.carro = {"estado": "en reposo", "enganchado": False,
                      "obstaculos_detectados": 0, "obstaculos_tocados": 0}
        self.banda_pct = 0
        self.cubiculo_actual = None
        self.dist_cm = None
        self.estacion_ok = False
        self.carro_ok = False
        self.presencia = False
        self._cabecera_registro()

    # ------------------------------------------------------------ eventos y registro CSV
    def evento(self, txt):
        with self.lock:
            self.ultimo_evento = txt
        print(f"[{time.strftime('%H:%M:%S')}] {txt}", flush=True)

    @staticmethod
    def _cabecera_registro():
        if not os.path.exists(cfg.REGISTRO_PATH):
            with open(cfg.REGISTRO_PATH, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(["fecha", "evento", "valor", "cubiculo", "detalle"])

    def registrar(self, evento, valor="", cubiculo="", detalle=""):
        try:
            with open(cfg.REGISTRO_PATH, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([time.strftime("%Y-%m-%d %H:%M:%S"), evento, valor, cubiculo, detalle])
        except OSError:
            pass

    # ------------------------------------------------------------ conteo
    def moneda_llego(self, clave, k):
        """Una moneda cayo en su vaso. clave = clase reconocida (ver clases.py) o None; k = vaso 0-4 o None."""
        with self.lock:
            self.en_camino = max(0, self.en_camino - 1)
            if clave is None or k is None:
                self.rechazadas += 1
                self.registrar("moneda", "", "", "no reconocida -> rechazo")
                return
            valor = mc.valor_de(clave)
            tid = mc.tipo_id(clave)
            self.cubiculos[tid]["cantidad"] += 1
            self.vaso_despachado[valor] = False          # el vaso volvio a recibir monedas
            self.cont[tid] += 1
            self.total += 1
            self.valor += valor
            self.peso_g += TIPO_POR_ID[tid]["masa_g"]
            self.registrar("moneda", valor, k, tid)

    def cantidad_vaso(self, valor):
        with self.lock:
            return sum(self.cubiculos[i]["cantidad"] for i in cfg.IDS_DE_VALOR[valor])

    def marcar_despachado(self, valor):
        with self.lock:
            self.vaso_despachado[valor] = True
            for i in cfg.IDS_DE_VALOR[valor]:
                self.cubiculos[i]["despachado"] = True

    def reiniciar_conteo(self):
        with self.lock:
            self.cont = Counter()
            for c in self.cubiculos.values():
                c["cantidad"] = 0
                c["despachado"] = False
            self.vaso_despachado = {v: False for v in cfg.IDS_DE_VALOR}
            self.rechazadas = 0
            self.total = self.valor = 0
            self.peso_g = 0.0
            self.en_camino = 0

    # ------------------------------------------------------------ publicacion
    def instantanea(self):
        with self.lock:
            return {
                "t": round(time.time() - self.t0, 2),
                "etapa": self.etapa,
                "ultimo_evento": self.ultimo_evento,
                "monedas": dict(self.cont),
                "cantidad_total": self.total,
                "peso_g": round(self.peso_g, 1),
                "valor": self.valor,
                "cubiculos": {tid: dict(v) for tid, v in self.cubiculos.items()},
                "vasos": {str(v): {"cantidad": sum(self.cubiculos[i]["cantidad"] for i in ids),
                                   "despachado": self.vaso_despachado[v]}
                          for v, ids in cfg.IDS_DE_VALOR.items()},
                "carro": {"x": 0.0, "y": 0.0, "yaw": 0.0, **self.carro},
                "rechazo": {"cantidad": self.rechazadas},
                "en_camino": self.en_camino,
                "banda": {"activa": self.banda_pct > 0, "pct": self.banda_pct},
                "canaleta": {"cubiculo": self.cubiculo_actual},
                "distancia_cm": self.dist_cm,
                "conexiones": {"estacion": self.estacion_ok, "carro": self.carro_ok,
                               "presencia": self.presencia},
            }

    def publicar(self):
        est = self.instantanea()
        tmp = cfg.ESTADO_PATH + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(est, fh, ensure_ascii=False)
            os.replace(tmp, cfg.ESTADO_PATH)
        except OSError:
            pass          # en Windows puede fallar un instante si otro proceso lo esta leyendo
        return est
