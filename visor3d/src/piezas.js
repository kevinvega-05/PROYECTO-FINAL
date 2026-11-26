// Catalogo 3D de las piezas imprimibles. Los datos los inyecta construir.py en window.DATOS.
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

THREE.Object3D.DEFAULT_UP.set(0, 0, 1);
const D = window.DATOS;
const $ = (id) => document.getElementById(id);
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
$("lienzo").appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1116);
const camera = new THREE.PerspectiveCamera(35, 1, 1, 5000);
camera.up.set(0, 0, 1);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
scene.add(new THREE.HemisphereLight(0xdfe9ff, 0x3a3a46, 1.2));
const sol = new THREE.DirectionalLight(0xffffff, 2.4);
sol.position.set(200, -300, 500); sol.castShadow = true;
Object.assign(sol.shadow.camera, { left: -200, right: 200, top: 200, bottom: -200, near: 10, far: 1500 });
scene.add(sol);
const suelo = new THREE.Mesh(new THREE.CircleGeometry(400, 64), new THREE.MeshStandardMaterial({ color: 0x1a1f28, roughness: 1 }));
suelo.receiveShadow = true; scene.add(suelo);
scene.add(new THREE.GridHelper(400, 20, 0x2a313c, 0x1f252e).rotateX(Math.PI / 2));

const nodos = {};
let actual = null, girar = true;

new GLTFLoader().parse(Uint8Array.from(atob(D.glb), (c) => c.charCodeAt(0)).buffer, "", (g) => {
  g.scene.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; o.material.side = THREE.DoubleSide; } });
  scene.add(g.scene);
  D.piezas.forEach((p) => { nodos[p.id] = g.scene.getObjectByName(p.id); nodos[p.id].visible = false; });
  armarLista();
  mostrar(location.hash ? location.hash.slice(1) : D.piezas[0].id);
  requestAnimationFrame(bucle);
});

function armarLista() {
  const ul = $("lista");
  D.piezas.forEach((p) => {
    const b = document.createElement("button");
    b.dataset.id = p.id;
    b.innerHTML = `<span class="pt" style="background:rgb(${D.colores[p.id].join(",")})"></span>${p.id.replace(/_/g, " ")}<small>×${p.cant}</small>`;
    b.onclick = () => mostrar(p.id);
    ul.appendChild(b);
  });
}

function mostrar(id) {
  if (!nodos[id]) id = D.piezas[0].id;
  if (actual) nodos[actual].visible = false;
  actual = id; nodos[id].visible = true;
  document.querySelectorAll("#lista button").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
  const p = D.piezas.find((x) => x.id === id);
  $("nombre").textContent = id.replace(/_/g, " ");
  $("desc").textContent = p.desc;
  $("dims").textContent = p.dims.join(" × ") + " mm";
  $("vol").textContent = p.vol + " cm³";
  $("cant").textContent = "×" + p.cant;
  const box = new THREE.Box3().setFromObject(nodos[id]);
  const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.5;
  const d = r / Math.tan((camera.fov * Math.PI) / 360) * 0.95;
  controls.target.copy(c);
  camera.position.set(c.x + d * 0.62, c.y - d * 0.62, c.z + d * 0.55);
  controls.update();
  history.replaceState(null, "", "#" + id);
}
$("girar").onchange = (e) => (girar = e.target.checked);
function ajustar() {
  const w = $("lienzo").clientWidth, h = $("lienzo").clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
addEventListener("resize", ajustar); ajustar();
let t0 = performance.now();
function bucle(t) {
  const dt = (t - t0) / 1000; t0 = t;
  if (girar && actual) {
    const c = controls.target, v = camera.position.clone().sub(c);
    v.applyAxisAngle(new THREE.Vector3(0, 0, 1), dt * 0.35); camera.position.copy(c).add(v);
  }
  controls.update(); renderer.render(scene, camera); requestAnimationFrame(bucle);
}
window.__piezas = { mostrar, parar: () => { girar = false; $("girar").checked = false; }, render: () => renderer.render(scene, camera) };
