# Piezas 3D

Todo sale de `cad/parametros.py` (única fuente de medidas) con `python cad/generar_cad.py`:
`cad/stl/` (imprimibles), `cad/referencia/` (carro, banda, termo y pista, no se imprimen), `cad/escena.glb` (conjunto) y
`cad/PIEZAS.md` (tabla con medidas y volúmenes). `--check` valida: mallas herméticas, que quepan en la cama de 220 mm,
vasos sin tocarse, canaleta sin chocar con vasos ni torre a ningún ángulo del servo, y punta sobre cada vaso.

## Decisiones
* **5 vasos** (uno por denominación) en un arco de R = 110 mm alrededor del pivote del servo, en los ángulos del
  firmware (20/45/90/135/160°). Los alojamientos de la placa están abiertos hacia afuera para que el carro saque el vaso.
* **Enganche:** cada vaso tiene una oreja con agujero Ø6; el carro lleva un pasador Ø5,4 (`enganche_carro`).
* **Placa en 3 tramos** con agujeros para pasadores de filamento (Ø4) y tornillos de fijación.
* **Torre del servo hueca**: se imprime boca abajo; el SG90 cuelga por las orejas.

## Límite importante: la pendiente
La canaleta baja de 78 mm (banda) a ~54 mm (borde de los vasos + 6 mm): **14°**. Una moneda sobre plástico necesita ~17–22°
para deslizar desde reposo; aquí cuenta con el impulso de la banda. Mejoras: canal liso (PETG pulido o cinta transparente),
vasos más bajos (`VASO_ALTO`), subir la banda o bajar la mesa de los vasos. El validador lo avisa.

## Antes de imprimir (medidas `[?]`)
Largo real de la banda · dimensiones del SG90 (cuerpo, orejas, posición del eje) · módulo IR · celular y posición de su lente
(ventana de la bandeja) · diámetro del poste. Cambia `parametros.py` y regenera; ningún STL se edita a mano.
Impresión: PLA/PETG, 0,2 mm, 20 % de relleno; la torre del servo boca abajo y el vaso de pie.
