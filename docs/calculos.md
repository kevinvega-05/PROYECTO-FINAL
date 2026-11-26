# Cálculos de ingeniería

Todo se recalcula con `python -m monedas.calculos` (acepta tus mediciones: `--bateria-mah 2600 --motor-ma 300 ...`).
Los **supuestos** están en la clase `Supuestos` de `monedas/calculos.py`; los que no se han medido se marcan **(supuesto)**
y deben cambiarse por lo que mida con el multímetro. Valores "típicos" = hojas de datos genéricas.

## Supuestos principales

| Dato | Valor por defecto | Origen |
|---|---|---|
| Batería del carro | 2 × 18650 «UltraFire» en serie, 7,4 V, **1500 mAh reales** | Las celdas se ven en la foto del carro y dicen «6800 mAh»: esa cifra es imposible para una 18650 (las mejores rondan 3000–3500 mAh), así que se usa **1500 mAh (supuesto)** |
| Fracción utilizable de la batería | 80 % | típico |
| Corriente por motor TT con carga | 250 mA (atascado > 700) | típico |
| Lógica del carro (UNO + JDY-16 + sensor) | 70 mA | típico |
| Espera entre dos despachos | 60 s | **(supuesto)** |
| Fuente de la estación | cargador 5 V, 2 A | el cargador es de 5 V; los 2 A son **(supuesto)** |
| SG90 | 250 mA moviéndose, 650 mA bloqueado | típico |
| Motor de la banda | 300 mA (800 mA atascado) | típico |
| Espesor de moneda | 2,0 mm | **(supuesto)**: mide con pie de rey |
| Cámara | campo de 200 mm, 1280 px de ancho, 25 fps | **(supuesto)** |

## 1. Cuánto tiempo puede estar encendido el carro

Corriente en movimiento: `I = 2·I_motor + I_lógica = 2·250 + 70 = 570 mA`. Capacidad útil: `1500 · 0,8 = 1200 mAh`.

| Resultado | Fórmula | Valor |
|---|---|---|
| Tiempo **moviéndose sin parar** | 1200 / 570 | **≈ 2,1 h** |
| Tiempo **en reposo** (solo lógica) | 1200 / 70 | ≈ 17 h |
| Duración de un viaje (ruta + enganche) | 17,8 s + 0,8 s | 18,6 s |
| Consumo por viaje | 570 mA · 18,6 s / 3600 | ≈ 2,9 mAh (≈ 0,022 Wh) |
| **Viajes por carga** (con 60 s de espera entre viajes) | 1200 / (2,9 + 1,2) | **≈ 290 viajes** |
| Horas de uso con ese ciclo | 292 · 78,6 s | ≈ 6,4 h |

Sensibilidad (misma corriente de motores salvo que se indique):

| Batería | Moviéndose | Viajes por carga | Horas con ciclo |
|---|---|---|---|
| Lo que dice la etiqueta: «6800 mAh» (**no es real**) | 9,5 h | 1324 | 28,9 h |
| 2×18650 de calidad, ~3000 mAh | 4,2 h | 584 | 12,8 h |
| **2×UltraFire reales, ~1500 mAh (por defecto)** | **2,1 h** | **292** | **6,4 h** |
| 2×UltraFire envejecidas, ~1000 mAh | 1,4 h | 195 | 4,3 h |
| 2×UltraFire 1500 mAh, motores a 350 mA (más fricción) | 1,6 h | 234 | 5,1 h |
| 4×AA alcalinas (~1800 mAh a 0,5 A) | 2,5 h | 351 | 7,7 h |

**Conclusión:** para una demostración (decenas de viajes) sobra autonomía incluso con celdas envejecidas. El factor que más
cambia el resultado es la capacidad real de las celdas (la etiqueta miente) y la corriente de los motores. Dos formas de
medirlo: (a) multímetro **en serie** con la batería mientras el carro avanza remolcando un vaso; (b) **prueba de campo**:
carga completa, repite la ruta cada 60 s y anota cuántos viajes hace antes de que baje la velocidad.
El puente H cae ≈ 1,4 V **(típico)**, así que con 7,4 V cada motor recibe ≈ 6 V; con 4×AA (6 V) recibiría ≈ 4,6 V y el carro
iría más lento: `V_AVANCE` cambia con la carga de la batería, hay que recalibrarlo.

## 2. Cinemática y calibración del carro

| Dato | Cálculo | Valor |
|---|---|---|
| Camino de la ruta | suma de la trayectoria simulada | ≈ 3,53 m |
| Velocidad media | 3,53 m / 17,8 s | ≈ 199 mm/s (con pausas de giro) |
| RPM de la rueda | 250 mm/s / (π · 65 mm) · 60 | ≈ 73,5 rpm |
| Giro de 90° en el sitio (teórico) | `t = (π/2) / (2·v / ancho) = (π/2)/(2·250/170)` | 534 ms |
| `T_GIRO90` provisional | — | 450 ms (≈ 200 °/s) |
| Corrección `L40` | 90° · 40/450 | **8° por cada segundo de avance** |
| Desajuste de ruedas que `L40` compensa | `Δv/v = ω·ancho/v`, ω = 8°/s | **≈ 9,5 %** |

**Qué significa:** la ruta corrige 8° hacia la izquierda cada segundo, que equivale a compensar que una rueda va ≈ 9,5 %
más rápida. Si después de ajustar `K` el carro ya casi no se desvía, **esa corrección será excesiva y el carro se irá a la
izquierda**. Regla: `CORRECCION_IZQ_MS ≈ 450 · (desvío en grados por segundo) / 90`. Mide cuántos grados se desvía el
carro en 1 s de `F1000` (con `K` ya ajustado) y calcula el valor; vuelve a correr `python -m monedas.pista`.
La diferencia entre 534 ms (teórico) y 450 ms (provisional) es normal: mide `T_GIRO90` real con `RR400`, `RR450`…

**Transmisión de la ruta:** 346 caracteres a 9600 baudios = 346 · 10 bits / 9600 ≈ 0,36 s por el cable; por BLE en trozos de
20 bytes son ≈ 18 paquetes: del orden de 1 s con pausas entre paquetes **(supuesto)**. Es despreciable frente a los 18 s
del viaje.

## 3. Estación: presupuesto de corriente de la fuente de 5 V

| Escenario | Suma | Corriente | Potencia |
|---|---|---|---|
| Típico (banda + servo moviéndose) | 80 + 36 + 300 + 250 | **≈ 0,67 A** | 3,3 W |
| Pico de servo (servo bloqueado) | 80 + 36 + 300 + 650 | ≈ 1,07 A | 5,3 W |
| Peor caso (banda y servo atascados) | 80 + 36 + 800 + 650 | ≈ 1,57 A | 7,8 W |

Con un cargador de 2 A el margen en el peor caso es ≈ 22 %; con uno de 1 A **no alcanza** en el peor caso (el ESP32 se
reinicia por caída de tensión). Mide la corriente del cargador real y pon un condensador de 470–1000 µF junto al servo.

## 4. Banda y caudal

| Dato | Cálculo | Valor |
|---|---|---|
| Recorrido completo | 660 mm / 20 mm/s | 33 s |
| Línea de lectura → borde | 300 mm / 20 mm/s | 15 s |
| Separación mínima entre monedas | 26 mm + 14 mm | 40 mm |
| **Caudal máximo** | 20 mm/s / 40 mm | **0,5 moneda/s ≈ 1800 monedas/h** |
| Cuadros por moneda | (200 mm / 20 mm/s) · 25 fps | ≈ 250 |
| Velocidad máxima de banda (≥ 10 cuadros) | 200 mm · 25 fps / 10 | ≈ 500 mm/s |

La banda está muy lejos del límite de la cámara: 20 mm/s deja 250 cuadros por moneda. El límite real es el servo y la
fiabilidad de la caída, no la visión.

## 5. Servo y canaleta

* Peor salto: 20° → 160° = 140°; a 0,1 s/60° **(típico)** ≈ 0,23 s. El planificador espera además `TIEMPO_SERVO_S = 0,7 s`:
  total ≈ 0,93 s, menor que los 2 s entre monedas (a 0,5 moneda/s).
* Torque del SG90 ≈ 1,8 kg·cm = 0,177 N·m **(típico)**; la canaleta (~18 g, giro horizontal) necesita una fracción.
* Pendiente de la canaleta: `atan((78 − 54) / 96) = 14°` (ver [cad.md](cad.md)): limitada por la altura de la banda.

## 6. Capacidad de los vasos

Volumen interior: π · 18² · 42 = 42,8 cm³. Con 60 % de aprovechamiento y espesor 2 mm:

| Moneda | Monedas por vaso (aprox.) | Masa |
|---|---|---|
| $50 | 56 | 3,0 g |
| $100 | 38 | 5,0 g |
| $200 | 32 | 6,0 g |
| $500 actual / antigua | 29 / 37 | 7,3 / 4,5 g |
| $1000 | 24 | 7,6 g |

Un vaso se llena en 24–56 monedas del mismo valor (a 0,5 moneda/s, de 48 s a 2 min). Masa máxima de monedas ≈ 212 g. Como
cada vaso recibe actual + antigua, la capacidad real es la de la moneda más grande de su valor. Si pones el sensor de
peso o el conteo cerca del límite, el despacho debe avisar «vaso lleno» (**pendiente de implementar**).

## 7. Visión: ¿se distinguen las monedas parecidas?

Campo de 200 mm en 1280 px → 0,156 mm/px. El par crítico ($500 antigua 21,0 mm vs $100 antigua 20,5 mm) difiere 0,5 mm = 3,2 px.
Con incertidumbre de ±0,5 px (0,078 mm) la separación es **6,4 σ**: se distinguen **si** la medida de diámetro es estable.
Para separar con 4σ hace falta como mínimo 800 px a lo ancho del campo; por debajo (cámara a 640 px) el par se confunde.
Los diámetros de referencia son aproximados: **mide tus monedas con pie de rey** y corrige `tipos.py`.

## 8. Fuerza de remolque

Masa remolcada: vaso (≈ 20 g) + monedas (≈ 212 g) ≈ 0,23 kg; con μ ≈ 0,4 sobre la pista: `F = μ·m·g ≈ 0,9 N`. Los motores TT
dan varios newtons en la rueda, así que no es limitante; el problema real es el agarre de las ruedas sobre la pista.

## 9. Qué medir para cerrar estos cálculos

1. Corriente del carro en marcha (multímetro en serie con la batería) y tensión de la batería cargada y a mitad de carga.
2. Capacidad real de la batería (la impresa en la celda) y tipo (18650, AA, LiPo).
3. Corriente del servo y de la banda en la estación; corriente máxima del cargador.
4. `V_AVANCE`, `T_GIRO90` y el desvío en grados por segundo del carro.
5. Espesor y diámetro de cada moneda (pie de rey) y píxeles por mm de tu cámara real.
