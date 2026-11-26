/*
  DIAGNOSTICO DEL CARRO - Arduino UNO + shield LAFVIN + JDY-16
  ------------------------------------------------------------
  Separa los dos problemas posibles: (A) los motores y (B) el Bluetooth.

  PASO A - MOTORES (no usa Bluetooth):
     Al encender el carro (con el boton ON y las baterias), espera 3 s y mueve SOLO:
       1) rueda izquierda adelante 1 s   2) rueda derecha adelante 1 s
       3) las dos adelante 1 s           4) las dos atras 1 s
     Si esto NO se mueve: el problema es de alimentacion, del boton ON o de los cables de motor.

  PASO B - BLUETOOTH:
     Despues de la prueba, todo lo que le mandes desde el celular te lo devuelve:
         RX 'a' (97)
         LINEA: hola
     Si NO devuelve nada: el JDY-16 no esta conectado/alimentado, esta mal enchufado,
     o la velocidad (BAUDIOS) no es la de tu modulo. Prueba cambiando BAUDIOS a 115200 y vuelve a subir.
     Si devuelve simbolos raros: la velocidad esta mal.
     Ademas, estas letras mueven el carro 0,8 s a PWM 200:  f adelante, b atras, l izquierda, r derecha.

  IMPORTANTE: quita el JDY-16 para SUBIR el codigo y vuelve a ponerlo despues.
*/

const long BAUDIOS = 9600;        // prueba 115200 si no devuelve nada o devuelve simbolos raros
const int IZQ_DIR = 2, IZQ_PWM = 5, DER_DIR = 4, DER_PWM = 6;
const int IZQ_ADELANTE = HIGH, DER_ADELANTE = HIGH;   // igual que en carro_monedas.ino
const int PWM_PRUEBA = 200;

void rueda(int pinDir, int pinPwm, int v, int nivelAdelante) {   // v: -255..255
  digitalWrite(pinDir, v >= 0 ? nivelAdelante : !nivelAdelante);
  analogWrite(pinPwm, abs(v));
}
void mover(int izq, int der) {
  rueda(IZQ_DIR, IZQ_PWM, izq, IZQ_ADELANTE);
  rueda(DER_DIR, DER_PWM, der, DER_ADELANTE);
}
void paso(const char *texto, int izq, int der, unsigned long ms) {
  Serial.println(texto);
  mover(izq, der);
  delay(ms);
  mover(0, 0);
  delay(500);
}

void setup() {
  Serial.begin(BAUDIOS);
  pinMode(IZQ_DIR, OUTPUT); pinMode(IZQ_PWM, OUTPUT);
  pinMode(DER_DIR, OUTPUT); pinMode(DER_PWM, OUTPUT);
  mover(0, 0);
  delay(3000);
  Serial.println("DIAG paso A: motores");
  paso("A1 rueda IZQUIERDA adelante", PWM_PRUEBA, 0, 1000);
  paso("A2 rueda DERECHA adelante", 0, PWM_PRUEBA, 1000);
  paso("A3 las dos adelante", PWM_PRUEBA, PWM_PRUEBA, 1000);
  paso("A4 las dos atras", -PWM_PRUEBA, -PWM_PRUEBA, 1000);
  Serial.println("DIAG paso B: mandame texto y te lo devuelvo (f b l r mueven el carro)");
}

char linea[40];
byte n = 0;

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    Serial.print("RX '");
    if (c >= 32) Serial.print(c); else Serial.print('.');
    Serial.print("' (");
    Serial.print((int)c);
    Serial.println(")");

    if (c == 'f') paso("-> adelante", PWM_PRUEBA, PWM_PRUEBA, 800);
    else if (c == 'b') paso("-> atras", -PWM_PRUEBA, -PWM_PRUEBA, 800);
    else if (c == 'l') paso("-> izquierda", -PWM_PRUEBA, PWM_PRUEBA, 800);
    else if (c == 'r') paso("-> derecha", PWM_PRUEBA, -PWM_PRUEBA, 800);

    if (c == '\n' || c == '\r') {
      if (n > 0) { linea[n] = 0; Serial.print("LINEA: "); Serial.println(linea); n = 0; }
    } else if (n < sizeof(linea) - 1) {
      linea[n++] = c;
    }
  }
}
