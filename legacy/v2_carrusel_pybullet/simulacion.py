"""
simulacion.py - Sistema logístico de monedas en PyBullet (v2: carrusel + remolque).

    python generar_urdf.py                     # una vez (o cuando cambies config.py)
    python simulacion.py                       # ventana 3D, modo interactivo (espera al chatbot)
    python simulacion.py --monedas 15           # cuántas monedas simular antes de esperar orden
    python simulacion.py --auto-despachar 500_actual   # despacha solo, sin esperar al chatbot (pruebas)
    python simulacion.py --sin-gui --rapido --auto-despachar 1000_actual   # prueba automática rápida

Proceso:
    1. Entra una moneda a la banda (recta).
    2. Sensor de presencia + cámara la identifican (denominación).
    3. El carrusel gira para alinear el cubículo de esa denominación con el final de la banda.
    4. La moneda entra al cubículo. Se repite para cada moneda.
    5. El CHATBOT ordena despachar un cubículo -> el carrusel lo lleva al lado del carro ->
       el carro se engancha como remolque -> recorre la pista (curvas + 3 obstáculos) hasta la meta.

Cada 0.25 s escribe estado.json. Para pedir un despacho desde otro proceso (el chatbot),
escribe comando.json con {"accion": "despachar", "tipo": "<id de TIPOS>"}; simulacion.py
lo recoge, lo ejecuta y borra el pendiente.
"""
import argparse
import json
import math
import os
import random
import sys
import time

import pybullet as p
import pybullet_data

from config import *

AQUI = os.path.dirname(os.path.abspath(__file__))
URDF = os.path.join(AQUI, "urdf")
ESTADO_PATH = os.path.join(AQUI, "estado.json")
COMANDO_PATH = os.path.join(AQUI, "comando.json")


def u(nombre):
    return os.path.join(URDF, nombre)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def envolver(a):
    while a > math.pi:
        a -= 2 * math.pi
    while a < -math.pi:
        a += 2 * math.pi
    return a


# =====================================================================
#  Carro autónomo con remolque (agente reactivo: pure-pursuit + mapa local de obstáculos)
# =====================================================================
class Carro:
    ANGULOS = [math.radians(a) for a in range(-90, 91, 10)]   # 19 rayos
    ALCANCE = 0.60
    HOLGURA = 0.20
    VENTANA = 10

    def __init__(self, mundo):
        self.m = mundo
        self.id = p.loadURDF(u("carro.urdf"),
                             [CARRO_POS[0], CARRO_POS[1], CARRO_Z],
                             p.getQuaternionFromEuler([0, 0, CARRO_YAW]))
        idx = {p.getJointInfo(self.id, j)[1].decode(): j for j in range(p.getNumJoints(self.id))}
        self.jl, self.jr = idx["j_rueda_izq"], idx["j_rueda_der"]
        for j in (self.jl, self.jr):
            p.changeDynamics(self.id, j, lateralFriction=1.5)
        for n in ("j_caster_del", "j_caster_tras"):
            p.changeDynamics(self.id, idx[n], lateralFriction=0.0)
        p.changeDynamics(self.id, -1, lateralFriction=0.6)
        self.estado = "esperando orden"
        self.v_cmd = 0.0
        self.obstaculos_vistos = set()
        self.choques = set()
        self.mapa = {}
        self.idx_path = 0
        self.enganchado = None

    def pose(self):
        pos, orn = p.getBasePositionAndOrientation(self.id)
        return pos, p.getEulerFromQuaternion(orn)[2]

    def enganchar(self, cubiculo_id):
        """Engancha el cubículo como remolque: constraint rígido que congela la pose
        relativa actual entre el carro y el cubículo (mismo patrón que Mundo.unir)."""
        self.m.unir(self.id, cubiculo_id, max_fuerza=400)
        self.enganchado = cubiculo_id

    def comandar(self, v, w):
        wl = (v - w * VIA / 2) / RUEDA_R
        wr = (v + w * VIA / 2) / RUEDA_R
        p.setJointMotorControl2(self.id, self.jl, p.VELOCITY_CONTROL, targetVelocity=wl, force=2.0)
        p.setJointMotorControl2(self.id, self.jr, p.VELOCITY_CONTROL, targetVelocity=wr, force=2.0)

    def parar(self):
        self.v_cmd = 0
        self.comandar(0, 0)

    def lidar(self):
        pos, yaw = self.pose()
        ox = pos[0] + (CARRO_L / 2 + 0.01) * math.cos(yaw)
        oy = pos[1] + (CARRO_L / 2 + 0.01) * math.sin(yaw)
        z = 0.07
        orig, fin = [], []
        for a in self.ANGULOS:
            orig.append([ox, oy, z])
            fin.append([ox + self.ALCANCE * math.cos(yaw + a), oy + self.ALCANCE * math.sin(yaw + a), z])
        res = p.rayTestBatch(orig, fin)
        d = []
        for r in res:
            if r[0] in self.m.obst_ids:
                d.append(r[2] * self.ALCANCE)
                self.obstaculos_vistos.add(r[0])
                hx, hy = r[3][0], r[3][1]
                self.mapa[(round(hx / 0.03), round(hy / 0.03))] = (hx, hy)
            else:
                d.append(self.ALCANCE)
        return d

    def _clusters(self):
        cl = []
        for qx, qy in self.mapa.values():
            for c in cl:
                if math.hypot(qx - c[0] / c[2], qy - c[1] / c[2]) < 0.15:
                    c[0] += qx
                    c[1] += qy
                    c[2] += 1
                    break
            else:
                cl.append([qx, qy, 1])
        return [(c[0] / c[2], c[1] / c[2]) for c in cl]

    def pista_desviada(self):
        path = self.m.pista
        n = len(path)
        normales = self.m.pista_normales
        off = [0.0] * n
        for cx, cy in self._clusters():
            i_o = min(range(n), key=lambda i: (path[i][0] - cx) ** 2 + (path[i][1] - cy) ** 2)
            nx, ny = normales[i_o]
            lat_o = (cx - path[i_o][0]) * nx + (cy - path[i_o][1]) * ny
            if abs(lat_o) > 0.30:
                continue
            lado = 1.0 if lat_o >= 0 else -1.0
            pico = lat_o - lado * self.HOLGURA
            for i in range(max(0, i_o - 3 - self.VENTANA), min(n, i_o + 4 + self.VENTANA)):
                d = abs(i - i_o)
                w = 1.0 if d <= 3 else math.cos(math.pi / 2 * (d - 3) / self.VENTANA) ** 2
                if abs(pico * w) > abs(off[i]):
                    off[i] = pico * w
        ref = [(path[i][0] + normales[i][0] * off[i], path[i][1] + normales[i][1] * off[i]) for i in range(n)]
        return ref, max(abs(o) for o in off)

    def conducir(self, timeout=180.0):
        m = self.m
        meta = m.pista[-1]
        t0 = m.t
        LOOK = 0.22
        ref_pos, ref_t = self.pose()[0], m.t
        while m.t - t0 < timeout:
            pos, yaw = self.pose()
            self.lidar()
            path, desv = self.pista_desviada()
            c, sn = math.cos(yaw), math.sin(yaw)

            mejor, dm = self.idx_path, 1e9
            for i in range(self.idx_path, min(self.idx_path + 40, len(path))):
                d = math.hypot(path[i][0] - pos[0], path[i][1] - pos[1])
                if d < dm:
                    mejor, dm = i, d
            self.idx_path = mejor
            j = mejor
            while j < len(path) - 1 and math.hypot(path[j][0] - pos[0], path[j][1] - pos[1]) < LOOK:
                j += 1
            tx, ty = path[j]

            if math.hypot(meta[0] - pos[0], meta[1] - pos[1]) < 0.12:
                self.parar()
                self.estado = "meta"
                m.etapa = "meta alcanzada"
                m.avanzar(0.5)
                return True

            err = envolver(math.atan2(ty - pos[1], tx - pos[0]) - yaw)
            frente = 1.0
            for qx, qy in self.mapa.values():
                rx, ry = qx - pos[0], qy - pos[1]
                xf = rx * c + ry * sn
                yl = -rx * sn + ry * c
                if 0.0 < xf < 0.6 and abs(yl) < 0.14:
                    frente = min(frente, xf)
            self.estado = "esquivando obstaculo" if desv > 0.04 else "siguiendo pista con remolque"

            if int(m.t / DT) % 12 == 0:
                for o in m.obst_ids:
                    if p.getContactPoints(self.id, o):
                        self.choques.add(o)

            v_des = V_CARRO * (1 - 0.65 * min(1.0, abs(err) / 0.9))
            v_des *= clamp((frente - 0.14) / 0.4, 0.4, 1.0)
            v_des = max(v_des, 0.05)
            w_cmd = clamp(2.0 * err, -2.0, 2.0)

            if m.t - ref_t > 3.0:
                avance = math.hypot(pos[0] - ref_pos[0], pos[1] - ref_pos[1])
                ref_pos, ref_t = pos, m.t
                if avance < 0.03:
                    self.estado = "recuperandose"
                    self.comandar(-0.18 if frente < 0.25 else 0.15, 0.0)
                    m.avanzar(1.0)
                    self.v_cmd = 0.0
                    ref_pos, ref_t = self.pose()[0], m.t
                    continue
            self.v_cmd += clamp(v_des - self.v_cmd, -0.6 * DT * 4, 0.5 * DT)
            self.comandar(self.v_cmd, w_cmd)
            m.paso()
        self.parar()
        return False


# =====================================================================
#  Mundo
# =====================================================================
class Mundo:
    def __init__(self, gui=True, tiempo_real=True):
        self.gui = gui
        self.tiempo_real = tiempo_real and gui
        p.connect(p.GUI if gui else p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath())
        p.setGravity(0, 0, -9.81)
        p.setTimeStep(DT)
        p.setPhysicsEngineParameter(numSolverIterations=80, contactBreakingThreshold=0.001)
        if gui:
            p.resetDebugVisualizerCamera(2.6, 55, -55, [1.2, -0.6, 0.0])
        p.loadURDF("plane.urdf")

        self.t = 0.0
        self._t_estado = -1.0
        self.etapa = "inicio"
        self.cont = {tp["id"]: 0 for tp in TIPOS}
        self.peso_g = 0.0
        self.valor = 0
        self.total_monedas = 0
        self.obst_ids = set()
        self.monedas_por_cubiculo = {k: [] for k in range(N_TIPOS)}
        self.despachado = {k: False for k in range(N_TIPOS)}
        self.disco_yaw = YAW_LLENADO[0]
        self.ultimo_evento = "inicio"

        self._construir_fabrica()
        self.pista = self._construir_pista()
        self._construir_obstaculos()
        self.carro = Carro(self)
        self._construir_carrusel()
        self.avanzar(0.3)

    # ---------------- construcción
    def _construir_fabrica(self):
        p.loadURDF(u("entrada.urdf"), [S_ENTRADA - 0.05, 0, 0], useFixedBase=True)
        p.loadURDF(u("banda.urdf"), [0, 0, 0], useFixedBase=True)
        p.loadURDF(u("sensor.urdf"), [S_SENSOR, 0, 0], useFixedBase=True)
        p.loadURDF(u("disco_base.urdf"), [DISCO_CENTRO[0], DISCO_CENTRO[1], 0], useFixedBase=True)

    def _construir_carrusel(self):
        self.disco_id = p.loadURDF(u("disco.urdf"),
                                   [DISCO_CENTRO[0], DISCO_CENTRO[1], DISCO_PEDESTAL_H + DISCO_H / 2],
                                   p.getQuaternionFromEuler([0, 0, self.disco_yaw]))
        p.changeDynamics(self.disco_id, -1, mass=0)   # el disco es puramente cinemático (lo giramos nosotros)
        self.cubiculo_ids = []
        z_centro = DISCO_PEDESTAL_H + DISCO_H + CUBICULO_H / 2   # ver nota de alturas en generar_urdf/config
        for k, tp in enumerate(TIPOS):
            x, y = self._pos_slot(k, self.disco_yaw)
            cid = p.loadURDF(u("cubiculo.urdf"), [x, y, z_centro])
            p.changeVisualShape(cid, -1, rgbaColor=tp["color"])
            p.changeDynamics(cid, -1, lateralFriction=0.8)
            self.cubiculo_ids.append(cid)

    def _pos_slot(self, k, yaw):
        ang = angulo_local(k) + yaw
        return (DISCO_CENTRO[0] + CARRUSEL_RADIO * math.cos(ang),
                DISCO_CENTRO[1] + CARRUSEL_RADIO * math.sin(ang))

    def piso_cubiculo(self, cubiculo_id):
        cp, _ = p.getBasePositionAndOrientation(cubiculo_id)
        return cp[2] - CUBICULO_H / 2 + CUBICULO_PISO

    def _construir_pista(self):
        pts = PISTA_PUNTOS
        ext = [pts[0]] + list(pts) + [pts[-1]]
        denso = []
        for i in range(1, len(ext) - 2):
            p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
            for k in range(20):
                t = k / 20
                t2, t3 = t * t, t * t * t
                x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                           + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
                y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                           + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
                denso.append((x, y))
        denso.append(pts[-1])
        path = [denso[0]]
        acum = 0.0
        for a, b in zip(denso[:-1], denso[1:]):
            acum += math.hypot(b[0] - a[0], b[1] - a[1])
            if acum >= 0.04:
                path.append(b)
                acum = 0.0
        path.append(denso[-1])

        self.pista_normales = []
        for i in range(len(path)):
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            self.pista_normales.append((-math.sin(ang), math.cos(ang)))
        self.pista_long = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path[:-1], path[1:]))

        gris = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.03, PISTA_ANCHO / 2, 0.0015], rgbaColor=[0.12, 0.12, 0.13, 1])
        raya = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.012, 0.006, 0.0018], rgbaColor=[0.95, 0.95, 0.95, 1])
        for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
            yaw = math.atan2(b[1] - a[1], b[0] - a[0])
            cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            q = p.getQuaternionFromEuler([0, 0, yaw])
            p.createMultiBody(0, -1, gris, [cx, cy, 0.0015], q)
            if i % 3 == 0:
                p.createMultiBody(0, -1, raya, [cx, cy, 0.0035], q)
        mx, my = path[-1]
        p.createMultiBody(0, -1, p.createVisualShape(p.GEOM_CYLINDER, radius=0.008, length=0.30,
                                                     rgbaColor=[0.8, 0.8, 0.8, 1]), [mx + 0.15, my, 0.15])
        blanco = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.006, 0.025, 0.025], rgbaColor=[1, 1, 1, 1])
        negro = p.createVisualShape(p.GEOM_BOX, halfExtents=[0.006, 0.025, 0.025], rgbaColor=[0.05, 0.05, 0.05, 1])
        for i in range(3):
            for j in range(2):
                p.createMultiBody(0, -1, blanco if (i + j) % 2 == 0 else negro,
                                  [mx + 0.15, my + (j - 0.5) * 0.05 + 0.03, 0.27 - i * 0.05])
        p.createMultiBody(0, -1, p.createVisualShape(p.GEOM_BOX, halfExtents=[0.015, PISTA_ANCHO / 2, 0.002],
                                                     rgbaColor=[1, 1, 1, 1]), [mx, my, 0.004])
        return path

    def _construir_obstaculos(self):
        path = self.pista
        s = [0.0]
        for a, b in zip(path[:-1], path[1:]):
            s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        for k, fr in enumerate(OBSTACULOS_FRAC):
            objetivo = fr * s[-1]
            i = min(range(len(s)), key=lambda n: abs(s[n] - objetivo))
            a = path[max(0, i - 1)]
            b = path[min(len(path) - 1, i + 1)]
            yaw = math.atan2(b[1] - a[1], b[0] - a[0])
            nx, ny = -math.sin(yaw), math.cos(yaw)
            lado = 1 if k % 2 == 0 else -1
            x = path[i][0] + nx * OBSTACULO_DESFASE * lado
            y = path[i][1] + ny * OBSTACULO_DESFASE * lado
            he = [OBSTACULO_TAM[0] / 2, OBSTACULO_TAM[1] / 2, OBSTACULO_TAM[2] / 2]
            col = p.createCollisionShape(p.GEOM_BOX, halfExtents=he)
            vis = p.createVisualShape(p.GEOM_BOX, halfExtents=he, rgbaColor=[0.65, 0.25, 0.18, 1])
            oid = p.createMultiBody(0, col, vis, [x, y, he[2]], p.getQuaternionFromEuler([0, 0, yaw]))
            self.obst_ids.add(oid)

    # ---------------- simulación
    def paso(self, antes=None):
        if antes is not None:
            antes()
        p.stepSimulation()
        self.t += DT
        if self.tiempo_real:
            time.sleep(DT)
        if self.t - self._t_estado >= 0.25:
            self._t_estado = self.t
            self.publicar()

    def avanzar(self, seg):
        for _ in range(int(seg / DT)):
            self.paso()

    def unir(self, cuerpo_a, cuerpo_b, max_fuerza=None):
        pa, oa = p.getBasePositionAndOrientation(cuerpo_a)
        pb, ob = p.getBasePositionAndOrientation(cuerpo_b)
        ip, io = p.invertTransform(pa, oa)
        rp, ro = p.multiplyTransforms(ip, io, pb, ob)
        cid = p.createConstraint(cuerpo_a, -1, cuerpo_b, -1, p.JOINT_FIXED, [0, 0, 0], rp, [0, 0, 0], ro, [0, 0, 0, 1])
        if max_fuerza is not None:
            p.changeConstraint(cid, maxForce=max_fuerza)
        return cid

    # ---------------- carrusel (rotación cinemática, arrastra cubículos y sus monedas)
    def rotar_disco(self, yaw_objetivo):
        yaw_objetivo = envolver(yaw_objetivo)
        while abs(envolver(yaw_objetivo - self.disco_yaw)) > 0.01:
            paso_ang = clamp(envolver(yaw_objetivo - self.disco_yaw), -ANGULO_VEL * DT, ANGULO_VEL * DT)
            nuevo_yaw = self.disco_yaw + paso_ang

            def antes(nuevo_yaw=nuevo_yaw):
                p.resetBasePositionAndOrientation(
                    self.disco_id, [DISCO_CENTRO[0], DISCO_CENTRO[1], DISCO_PEDESTAL_H + DISCO_H / 2],
                    p.getQuaternionFromEuler([0, 0, nuevo_yaw]))
                for k in range(N_TIPOS):
                    if self.despachado[k]:
                        continue
                    x, y = self._pos_slot(k, nuevo_yaw)
                    cid = self.cubiculo_ids[k]
                    cp, co = p.getBasePositionAndOrientation(cid)
                    dx, dy = x - cp[0], y - cp[1]
                    p.resetBasePositionAndOrientation(cid, (x, y, cp[2]), co)
                    p.resetBaseVelocity(cid, [0, 0, 0], [0, 0, 0])
                    for mo in self.monedas_por_cubiculo[k]:
                        mp, mo_orn = p.getBasePositionAndOrientation(mo)
                        p.resetBasePositionAndOrientation(mo, (mp[0] + dx, mp[1] + dy, mp[2]), mo_orn)
                        p.resetBaseVelocity(mo, [0, 0, 0], [0, 0, 0])

            self.paso(antes)
            self.disco_yaw = nuevo_yaw
        self.disco_yaw = yaw_objetivo

    # ---------------- banda recta (transporte cinemático de UNA moneda)
    def _mover_moneda(self, mid, s_ini, s_fin, z_ini, z_fin):
        dist = s_fin - s_ini
        if dist <= 0:
            return
        s = s_ini
        while s_fin - s > 0.0008:
            resto = s_fin - s
            v = min(V_BANDA, 0.02 + 2.0 * resto)
            s = min(s_fin, s + v * DT)
            frac = (s - s_ini) / dist
            z = z_ini + (z_fin - z_ini) * frac

            def antes(s=s, z=z):
                p.resetBasePositionAndOrientation(mid, (s, 0.0, z), p.getQuaternionFromEuler([0, 0, 0]))
                p.resetBaseVelocity(mid, [0, 0, 0], [0, 0, 0])

            self.paso(antes)

    def procesar_moneda(self, tipo_real_idx):
        """Una moneda entra a la banda, pasa el sensor+cámara, y el carrusel se alinea
        con el cubículo que le corresponde antes de que la moneda llegue al final."""
        tp = TIPOS[tipo_real_idx]
        r = coin_radius(tipo_real_idx)
        col = p.createCollisionShape(p.GEOM_CYLINDER, radius=r, height=MONEDA_ESPESOR)
        vis = p.createVisualShape(p.GEOM_CYLINDER, radius=r, length=MONEDA_ESPESOR, rgbaColor=tp["color"])
        z_banda = BANDA_H + MONEDA_ESPESOR / 2 + 0.0015
        mid = p.createMultiBody(coin_mass(tipo_real_idx), col, vis, [S_ENTRADA, 0.0, z_banda],
                                p.getQuaternionFromEuler([0, 0, 0]))
        p.changeDynamics(mid, -1, lateralFriction=0.5, restitution=0.0)

        self.etapa = f"banda: moneda hacia el sensor ({tp['id']})"
        self._mover_moneda(mid, S_ENTRADA, S_SENSOR, z_banda, z_banda)

        # --- sensor de presencia + cámara ---
        self.ultimo_evento = f"sensor: objeto detectado -> cámara identifica {tp['id']}"
        if random.random() < CAMARA_PRECISION:
            tipo_identificado = tipo_real_idx
        else:
            tipo_identificado = random.choice([i for i in range(N_TIPOS) if i != tipo_real_idx])
        k = tipo_identificado
        self.etapa = f"carrusel: alineando cubículo {TIPOS[k]['id']}"
        if not math.isclose(envolver(self.disco_yaw - YAW_LLENADO[k]), 0.0, abs_tol=0.02):
            self.rotar_disco(YAW_LLENADO[k])

        z_piso = self.piso_cubiculo(self.cubiculo_ids[k]) + len(self.monedas_por_cubiculo[k]) * (MONEDA_ESPESOR * 1.4) + 0.006
        self.etapa = f"banda: moneda entrando al cubículo {TIPOS[k]['id']}"
        self._mover_moneda(mid, S_SENSOR, BANDA_LARGO, z_banda, z_piso)

        self.monedas_por_cubiculo[k].append(mid)
        self.cont[TIPOS[k]["id"]] += 1
        self.peso_g += TIPOS[k]["masa_g"]
        self.valor += TIPOS[k]["valor"]
        self.total_monedas += 1
        self.avanzar(0.15)

    # ---------------- despacho (orden del chatbot)
    def despachar(self, tipo_id):
        if tipo_id not in TIPO_INDEX:
            return False, f"tipo desconocido: {tipo_id}"
        k = TIPO_INDEX[tipo_id]
        if self.despachado[k]:
            return False, f"el cubículo de {tipo_id} ya fue despachado"
        if not self.monedas_por_cubiculo[k]:
            return False, f"el cubículo de {tipo_id} está vacío, no se despacha"

        self.etapa = f"carrusel: llevando cubículo {tipo_id} al carro"
        self.rotar_disco(YAW_DESPACHO[k])

        cid = self.cubiculo_ids[k]
        self.etapa = f"carro: enganchando cubículo {tipo_id}"
        for mo in self.monedas_por_cubiculo[k]:
            self.unir(cid, mo)          # las monedas quedan solidarias al cubículo
        self.carro.enganchar(cid)       # el cubículo queda solidario al carro (remolque)
        self.despachado[k] = True
        self.avanzar(0.5)

        self.etapa = f"carro: recorriendo la pista con el cubículo de {tipo_id}"
        ok = self.carro.conducir()
        return ok, "meta alcanzada" if ok else "tiempo agotado antes de la meta"

    # ---------------- puente de comandos (chatbot.py escribe aquí)
    def leer_comando(self):
        if not os.path.exists(COMANDO_PATH):
            return None
        try:
            with open(COMANDO_PATH) as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None
        if data.get("accion") == "despachar" and not data.get("atendido"):
            data["atendido"] = True
            with open(COMANDO_PATH, "w") as fh:
                json.dump(data, fh)
            return data.get("tipo")
        return None

    # ---------------- estado para el chatbot / dashboard
    def publicar(self):
        pos, yaw = self.carro.pose()
        est = {
            "t": round(self.t, 2),
            "etapa": self.etapa,
            "ultimo_evento": self.ultimo_evento,
            "monedas": self.cont,
            "cantidad_total": self.total_monedas,
            "peso_g": round(self.peso_g, 1),
            "valor": self.valor,
            "cubiculos": {
                TIPOS[k]["id"]: {
                    "cantidad": len(self.monedas_por_cubiculo[k]),
                    "despachado": self.despachado[k],
                } for k in range(N_TIPOS)
            },
            "carro": {
                "x": round(pos[0], 3), "y": round(pos[1], 3), "yaw": round(yaw, 3),
                "estado": self.carro.estado,
                "enganchado": self.carro.enganchado is not None,
                "obstaculos_detectados": len(self.carro.obstaculos_vistos),
                "obstaculos_tocados": len(self.carro.choques),
            },
        }
        tmp = ESTADO_PATH + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(est, fh, ensure_ascii=False)
        os.replace(tmp, ESTADO_PATH)
        return est


# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-gui", action="store_true")
    ap.add_argument("--rapido", action="store_true", help="no esperar tiempo real")
    ap.add_argument("--monedas", type=int, default=12)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--auto-despachar", type=str, default=None,
                    help="id de TIPOS a despachar automáticamente (sin esperar al chatbot), p.ej. 500_actual")
    ap.add_argument("--espera-max", type=float, default=600.0,
                    help="segundos (simulados) que espera una orden del chatbot antes de salir")
    a = ap.parse_args()
    random.seed(a.semilla)

    if not os.path.exists(u("carro.urdf")):
        sys.exit("Falta la carpeta urdf/. Corre primero:  python generar_urdf.py")
    if os.path.exists(COMANDO_PATH):
        os.remove(COMANDO_PATH)

    m = Mundo(gui=not a.sin_gui, tiempo_real=not a.rapido)

    for _ in range(a.monedas):
        tipo_idx = random.randrange(N_TIPOS)
        m.procesar_moneda(tipo_idx)

    print("Cubículos tras el llenado:")
    for i, tp in enumerate(TIPOS):
        print(f"  {tp['id']:>14}: {len(m.monedas_por_cubiculo[i])} moneda(s)")

    despachado_id = None
    if a.auto_despachar:
        despachado_id = a.auto_despachar
        ok, msg = m.despachar(a.auto_despachar)
        print(msg)
    else:
        m.etapa = "esperando orden del chatbot (comando.json)"
        print("Esperando orden de despacho del chatbot (comando.json)...")
        t0 = m.t
        tipo_pedido = None
        while m.t - t0 < a.espera_max:
            tipo_pedido = m.leer_comando()
            if tipo_pedido:
                break
            m.avanzar(0.2)
        if tipo_pedido:
            despachado_id = tipo_pedido
            ok, msg = m.despachar(tipo_pedido)
            print(msg)
        else:
            print("No llegó ninguna orden a tiempo.")
            ok = False

    est = m.publicar()
    print(json.dumps(est, indent=2, ensure_ascii=False))

    total_dentro, total_monedas = 0, 0
    for k in range(N_TIPOS):
        cid = m.cubiculo_ids[k]
        cp, _ = p.getBasePositionAndOrientation(cid)
        dentro = 0
        for mo in m.monedas_por_cubiculo[k]:
            mp, _ = p.getBasePositionAndOrientation(mo)
            if math.hypot(mp[0] - cp[0], mp[1] - cp[1]) < 0.06 and abs(mp[2] - cp[2]) < CUBICULO_H:
                dentro += 1
        total_dentro += dentro
        total_monedas += len(m.monedas_por_cubiculo[k])
        if len(m.monedas_por_cubiculo[k]):
            marca = " (despachado)" if m.despachado[k] else ""
            print(f"  {TIPOS[k]['id']:>14}: {dentro}/{len(m.monedas_por_cubiculo[k])} dentro{marca}")
    print(f"Monedas dentro de su cubículo (los 9): {total_dentro}/{total_monedas}")
    if despachado_id:
        k = TIPO_INDEX[despachado_id]
        print(f"Cubículo despachado enganchado al carro: {m.carro.enganchado == m.cubiculo_ids[k]}")
        print(f"Obstáculos tocados: {len(m.carro.choques)} (detectados: {len(m.carro.obstaculos_vistos)})")
    print(f"Tiempo simulado: {m.t:.1f} s")

    if m.gui:
        print("Cierra la ventana o Ctrl+C para salir.")
        try:
            while p.isConnected():
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
