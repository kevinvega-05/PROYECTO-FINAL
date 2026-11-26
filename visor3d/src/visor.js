// Visor 3D del Sistema logistico de monedas inteligentes.
// Los datos (escena GLB, poses del carro y angulos del servo) los inyecta construir.py en window.DATOS.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);       // la escena de CAD es Z hacia arriba
const D = window.DATOS;
const $ = (id) => document.getElementById(id);
const VALORES = [50, 100, 200, 500, 1000];

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
$("lienzo").appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1116);
scene.fog = new THREE.Fog(0x0e1116, 2600, 6000);
const camera = new THREE.PerspectiveCamera(40, 1, 5, 12000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x2a3a2a, 1.05));
const sol = new THREE.DirectionalLight(0xffffff, 2.2);
sol.position.set(500, -700, 1400);
sol.castShadow = true;
sol.shadow.mapSize.set(2048, 2048);
Object.assign(sol.shadow.camera, { left: -900, right: 1900, top: 500, bottom: -1300, near: 100, far: 4000 });
sol.target.position.set(500, -300, 0);
scene.add(sol, sol.target);

const VISTAS = {
  general: { pos: [-1000, -1750, 1350], mira: [380, -260, 40] },
  estacion: { pos: [-260, -380, 330], mira: [60, 0, 55] },
  pista: { pos: [700, -320, 2300], mira: [700, -320, 0], up: [1, 0, 0] },
  carro: { seguir: true },
};
function vista(nombre) {
  const v = VISTAS[nombre];
  seguir = !!v.seguir;
  if (v.seguir) return;
  camera.up.set(...(v.up || [0, 0, 1]));
  camera.position.set(...v.pos);
  controls.target.set(...v.mira);
  controls.update();
}

let seguir = false, carro, canaleta, grupoCanaleta, pivote;
const vasos = [];
let termos = [];
const vasoPos = [];
let vasoRemolque = null;
let t = 0, corriendo = false, velocidad = 2, elegido = 3;
const poses = D.poses;                 // [t, x_pista, y_pista, rumbo_grados]
const T_TOTAL = poses[poses.length - 1][0];

function aEscena(xp, yp) { return [D.pista_x0 + yp, -xp]; }
function pose(tt) {
  let lo = 0, hi = poses.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; (poses[m][0] <= tt) ? lo = m : hi = m; }
  const a = poses[lo], b = poses[hi];
  const f = b[0] > a[0] ? Math.min(1, Math.max(0, (tt - a[0]) / (b[0] - a[0]))) : 0;
  const L = (i) => a[i] + (b[i] - a[i]) * f;
  const [X, Y] = aEscena(L(1), L(2));
  return { X, Y, yaw: -L(3) * Math.PI / 180 };
}

new GLTFLoader().parse(Uint8Array.from(atob(D.glb), c => c.charCodeAt(0)).buffer, "", (gltf) => {
  const raiz = gltf.scene;
  raiz.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.material.side = THREE.DoubleSide; } });
  scene.add(raiz);
  const por = (n) => raiz.getObjectByName(n);
  carro = por("carro");
  canaleta = por("canaleta");
  for (let k = 0; k < 5; k++) { const v = por("vaso_" + k); vasos.push(v); vasoPos.push(v.position.clone()); }
  termos = [1, 2, 3].map((i) => por("termo_" + i));
  // la canaleta gira alrededor del pivote del servo
  pivote = new THREE.Vector3(D.pivote_x, 0, D.pivote_z);
  grupoCanaleta = new THREE.Group();
  grupoCanaleta.position.copy(pivote);
  scene.add(grupoCanaleta);
  grupoCanaleta.add(canaleta);
  canaleta.position.set(-pivote.x, 0, -pivote.z);
  carro.position.set(0, 0, 0);
  elegirVaso(3);
  reiniciar();
  vista("general");
  $("cargando").remove();
  requestAnimationFrame(bucle);
});

function elegirVaso(k) {
  elegido = k;
  vasos.forEach((v, i) => { v.visible = true; v.position.copy(vasoPos[i]); v.rotation.set(0, 0, 0); });
  document.querySelectorAll("[data-vaso]").forEach((b) => b.classList.toggle("on", +b.dataset.vaso === k));
  apuntarCanaleta(k);
  reiniciar();
}
function anguloCanaleta(k) { return (90 - D.angulos[k]) * Math.PI / 180; }   // 0 = hacia +X
let objetivoCanal = 0;
function apuntarCanaleta(k) { objetivoCanal = anguloCanaleta(k) - (90 - 90) * 0; }

function ponerCarro(tt) {
  const p = pose(tt);
  carro.position.set(p.X, p.Y, 0);
  carro.rotation.set(0, 0, p.yaw);
  // el vaso despachado va enganchado detras del carro (su oreja apunta hacia el carro)
  const v = vasos[elegido];
  const atras = D.atras;
  const cx = p.X - Math.cos(p.yaw) * atras, cy = p.Y - Math.sin(p.yaw) * atras;
  const base = vasoPos[elegido];
  v.rotation.z = p.yaw - (0);              // gira con el carro
  v.position.set(cx, cy, base.z);
  // al inicio el vaso esta en su sitio del arco y el carro llega a recogerlo (primeros 2 s)
}

function reiniciar() {
  t = 0; corriendo = false; $("play").textContent = "▶ Iniciar recorrido";
  ponerCarro(0);
  vasos[elegido].position.copy(vasoPos[elegido]); vasos[elegido].rotation.set(0, 0, 0);
  actualizarHUD();
}

// ---- moneda cayendo por la banda y la canaleta
let moneda = null, monedaT = 0;
function soltarMoneda() {
  if (moneda) scene.remove(moneda);
  const m = new THREE.Mesh(new THREE.CylinderGeometry(11.8, 11.8, 2.4, 32), new THREE.MeshStandardMaterial({ color: 0xe8c14a, metalness: 0.8, roughness: 0.3 }));
  m.rotation.x = Math.PI / 2; moneda = new THREE.Group(); moneda.add(m); moneda.castShadow = true;
  scene.add(moneda); monedaT = 0;
  apuntarCanaleta(elegido);
}
function moverMoneda(dt) {
  if (!moneda) return;
  monedaT += dt;
  const phi = anguloCanaleta(elegido), cx = Math.cos(phi), cy = Math.sin(phi);
  const pend = D.pendiente * Math.PI / 180;
  const zBanda = D.banda_alto + 1.5;
  let x, y, z;
  const T1 = 2.4, T2 = 1.6, T3 = 0.5;      // banda, canaleta, caida
  if (monedaT < T1) { x = -200 * (1 - monedaT / T1); y = 0; z = zBanda; }
  else if (monedaT < T1 + T2) {
    const f = (monedaT - T1) / T2, r = D.punta_r * f * f * 0.7 + D.punta_r * f * 0.3;
    x = D.pivote_x + r * cx; y = r * cy; z = D.pivote_z + 4 - r * Math.tan(pend);
  } else {
    const f = Math.min(1, (monedaT - T1 - T2) / T3);
    const [vx, vy] = [vasoPos[elegido].x, vasoPos[elegido].y];
    const r = D.punta_r;
    x = D.pivote_x + r * cx + (vx - (D.pivote_x + r * cx)) * f; y = r * cy + (vy - r * cy) * f;
    const z0 = D.pivote_z + 4 - r * Math.tan(pend), z1 = D.placa + D.vaso_fondo + 2;
    z = z0 + (z1 - z0) * f * f;
    if (f >= 1) { scene.remove(moneda); moneda = null; return; }
  }
  moneda.position.set(x, y, z);
}

// ---- interfaz
function actualizarHUD() {
  $("hud-t").textContent = t.toFixed(1) + " s / " + T_TOTAL.toFixed(1) + " s";
  $("barra").style.width = (100 * t / T_TOTAL) + "%";
  $("hud-vaso").textContent = "$" + VALORES[elegido];
}
$("play").onclick = () => {
  if (t >= T_TOTAL) reiniciar();
  corriendo = !corriendo;
  $("play").textContent = corriendo ? "⏸ Pausa" : "▶ Continuar";
};
$("reset").onclick = reiniciar;
$("moneda").onclick = soltarMoneda;
$("vel").oninput = (e) => { velocidad = +e.target.value; $("vel-n").textContent = "×" + velocidad; };
document.querySelectorAll("[data-vaso]").forEach((b) => b.onclick = () => elegirVaso(+b.dataset.vaso));
document.querySelectorAll("[data-vista]").forEach((b) => b.onclick = () => vista(b.dataset.vista));
$("termos").onchange = (e) => termos.forEach((o) => o.visible = e.target.checked);

function ajustar() {
  const w = $("lienzo").clientWidth, h = $("lienzo").clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
addEventListener("resize", ajustar); ajustar();

let ultimo = performance.now(), canalAng = 0;
function bucle(ahora) {
  const dt = Math.min(0.05, (ahora - ultimo) / 1000); ultimo = ahora;
  if (corriendo) { t = Math.min(T_TOTAL, t + dt * velocidad); ponerCarro(t); actualizarHUD(); if (t >= T_TOTAL) { corriendo = false; $("play").textContent = "↺ Repetir"; } }
  canalAng += (objetivoCanal - canalAng) * Math.min(1, dt * 6);
  grupoCanaleta.rotation.z = canalAng;
  moverMoneda(dt);
  if (seguir) { const p = carro.position; controls.target.lerp(new THREE.Vector3(p.x, p.y, 40), 0.15); camera.position.lerp(new THREE.Vector3(p.x - 330, p.y - 330, 330), 0.08); }
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(bucle);
}
window.__visor = { vista, elegirVaso, soltarMoneda, ponerT: (x) => { t = x; ponerCarro(t); actualizarHUD(); }, escena: () => scene, camera, controls, render: () => renderer.render(scene, camera) };
