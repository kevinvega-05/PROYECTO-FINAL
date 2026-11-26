/*
  CARRO DE MONEDAS - Arduino UNO + shield LAFVIN 2WD V2.2 + Bluetooth JDY-16
  ---------------------------------------------------------------------------
  Es el codigo carro_guia_arduino8 ampliado para el proyecto "Sistema logistico de monedas":
  el carro retrocede hasta enganchar el vaso (pinza en la parte trasera), lo remolca por la
  pista (2 curvas, 3 obstaculos) y se detiene. Se mantiene TODO lo anterior (ordenes M, S, P, T,
  V, K, reporte D, aviso O, parada por obstaculo, compensacion de ruedas en EEPROM) y se agrega
  el modo RUTA: una secuencia de tramos que el carro recorre solo.

  ORDENES QUE RECIBE (texto, una por linea, terminada en '\n'):
    M<izq>,<der>   velocidad de cada rueda, de -255 a 255   ej: M150,120   (cancela una ruta)
    S              parar (cancela una ruta)
    P              "sigo aqui"
    T              prueba de ruedas (diagnostico)
    V1 / V0        eco de ordenes
    K<izq>,<der>   compensacion de ruedas en % (se guarda en EEPROM) / K? la muestra

  NUEVAS (modo ruta):
    R<tramos>      recorre una secuencia. Cada tramo = letra + milisegundos, separados por coma:
                     F adelante   B reversa   L giro izquierda en su sitio   R giro derecha   S pausa
                   ej: RB800,F1500,L400,F1200,R400,F1500
    R              (sola) recorre la RUTA_DEFECTO que esta mas abajo en este archivo
    Rutas largas (hasta 120 tramos). Una linea admite ~75 caracteres, asi que se manda en pedazos:
                     C          borra la ruta cargada
                     A<tramos>  agrega tramos SIN ejecutar (repite A las veces que haga falta)
                     E          ejecuta la ruta cargada
    X              cancela la ruta y para
    U<n>           velocidad de avance en ruta   (0-255, defecto 200)   ej: U140
    W<n>           velocidad de reversa en ruta  (defecto 170)         ej: W100
    G<n>           velocidad de giro en ruta     (defecto 180)         ej: G110
    N<cm>          distancia de freno en RUTA (defecto 8; 0 = sin freno). En manual sigue en 25 cm.
                   Se usa baja para que el carro NO se detenga ante un obstaculo que va a esquivar.
    Q              estado: Q<en ruta 0/1>,<tramo>,<distancia cm>

  LO QUE RESPONDE:
    D<cm>          distancia al frente cada 200 ms
    O              se detuvo por un obstaculo (si iba en ruta, la ruta se cancela)
    Z              la ruta termino completa
    X              la ruta fue cancelada
    R<n>           ruta aceptada con n tramos  /  R?  ruta invalida
    U<n> W<n> G<n> velocidad aceptada
    E<izq>,<der>   eco (solo con V1)

  SEGURIDAD:
    - En modo manual (M), si no llega ninguna orden en 800 ms el carro se detiene.
    - Una ruta NO depende del celular: se ejecuta por tiempos aunque se pierda el Bluetooth.
    - Hacia adelante no avanza con algo a menos de 25 cm (girar y retroceder si se puede).
      El enganche se hace RETROCEDIENDO, y el sensor mira al frente, asi que no lo frena.

  CONEXIONES (igual que antes):
    Motores -> "Motor Interface" (izquierdo en canal A, derecho en canal B)
    Ultrasonico HC-SR04 -> TRIG D12, ECHO D13
    Servo -> D10 (sensor mirando al frente)
    JDY-16 -> conector Bluetooth.  Baterias 2x18650 -> conector BAT, boton ON.

  IMPORTANTE: quita el JDY-16 antes de subir el codigo (usa los mismos pines que el USB).
  El JDY-16 (BLE) manda en paquetes de 20 bytes: la linea se arma sola hasta el '\n', pero si tu
  app corta los mensajes, manda las rutas largas en varias lineas pequenas.
*/

#include <Servo.h>
#include <EEPROM.h>

// ----------------- PINES DEL SHIELD -----------------
// motor IZQUIERDO -> conector A1 o A2 (canal A: DIRA D2, PWMA D5)
// motor DERECHO   -> conector B1 o B2 (canal B: DIRB D4, PWMB D6)
const int IZQ_DIR = 2;
const int IZQ_PWM = 5;
const int DER_DIR = 4;
const int DER_PWM = 6;
const int TRIG = 12;
const int ECHO = 13;
const int SERVO_PIN = 10;

// ----------------- AJUSTES (los mismos valores que ya tenias en el carrito) -----------------
// Verifica con la orden T. Si una rueda gira al reves, cambia solo esa.
const int IZQ_ADELANTE = HIGH;
const int DER_ADELANTE = HIGH;
const bool INTERCAMBIAR_LADOS = false;
const int FACTOR_IZQ_INICIAL = 100;
const int FACTOR_DER_INICIAL = 100;
const int PWM_MINIMO = 60;
const int SERVO_CENTRO = 90;
const int DIST_PARADA = 25;                   // cm
const unsigned long TIEMPO_SIN_ORDEN = 800;   // ms (solo modo manual)
const unsigned long PERIODO_MEDICION = 100;   // ms
const unsigned long PERIODO_REPORTE = 200;    // ms
const long BAUDIOS_BT = 9600;

// Ruta que se ejecuta con la orden "R" sin argumentos. VALORES DE PARTIDA: calibralos en tu pista.
//   B800 = retrocede 0,8 s para que la pinza agarre el vaso; luego F/L/R recorren las curvas.
const char RUTA_DEFECTO[] = "B800,F1500,L400,F1200,R400,F1500";

// ----------------- ESTADO -----------------
Servo servo;
int velIzq = 0, velDer = 0;
long distancia = 400;
bool frenadoPorObstaculo = false;
unsigned long ultimaOrden = 0, ultimaMedicion = 0, ultimoReporte = 0;
int factorIzq = FACTOR_IZQ_INICIAL, factorDer = FACTOR_DER_INICIAL;
const byte EE_FIRMA = 0x5A;
bool eco = false;
char buf[80];
byte largo = 0;

// ----------------- ESTADO DEL MODO RUTA -----------------
const byte MAX_TRAMOS = 120;
struct Tramo { char c; unsigned int ms; };
Tramo ruta[MAX_TRAMOS];
byte nTramos = 0, idxTramo = 0;
bool enRuta = false;
unsigned long finTramo = 0;
int velAdelante = 200, velReversa = 170, velGiro = 180;   // altas: la compensacion K (ej. 50 %) las reduce a la mitad en una rueda
int distParadaRuta = 8;      // cm: en modo ruta solo frena si algo esta MAS cerca que esto (0 = sin freno). Orden N<cm>

// ============ MOTORES ============
void motor(int pinDir, int pinPwm, int v, int factor, int nivelAdelante) {
  v = constrain(v, -255, 255);
  int pwm = (long)abs(v) * factor / 100;
  if (v != 0 && pwm < PWM_MINIMO) pwm = PWM_MINIMO;
  digitalWrite(pinDir, v >= 0 ? nivelAdelante : !nivelAdelante);
  analogWrite(pinPwm, constrain(pwm, 0, 255));
}

void aplicar(int izq, int der) {
  if (INTERCAMBIAR_LADOS) { int t = izq; izq = der; der = t; }
  motor(IZQ_DIR, IZQ_PWM, izq, factorIzq, IZQ_ADELANTE);
  motor(DER_DIR, DER_PWM, der, factorDer, DER_ADELANTE);
}

// ============ COMPENSACION GUARDADA ============
void cargarFactores() {
  if (EEPROM.read(0) == EE_FIRMA) {
    factorIzq = constrain(EEPROM.read(1), 10, 100);
    factorDer = constrain(EEPROM.read(2), 10, 100);
  }
}

void guardarFactores() {
  EEPROM.update(0, EE_FIRMA);
  EEPROM.update(1, factorIzq);
  EEPROM.update(2, factorDer);
}

void reportarFactores() {
  Serial.print("K"); Serial.print(factorIzq); Serial.print(","); Serial.println(factorDer);
}

int umbralParada() { return enRuta ? distParadaRuta : DIST_PARADA; }

bool avanza(int izq, int der) {
  if ((long)izq * der < 0) return false;   // giro en su sitio
  return izq + der > 0;
}

void actualizarMotores() {
  if (avanza(velIzq, velDer) && distancia < umbralParada()) {
    aplicar(0, 0);
    if (!frenadoPorObstaculo) { Serial.println("O"); frenadoPorObstaculo = true; }
  } else {
    aplicar(velIzq, velDer);
    if (distancia >= umbralParada()) frenadoPorObstaculo = false;
  }
}

// ============ SENSOR ============
long medirDistancia() {
  digitalWrite(TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long t = pulseIn(ECHO, HIGH, 20000UL);
  if (t == 0) return 400;
  return t / 58;
}

// ============ PRUEBA DE RUEDAS ============
void pasoPrueba(const char *texto, int izq, int der) {
  Serial.println(texto);
  aplicar(izq, der);
  delay(1000);
  aplicar(0, 0);
  delay(700);
}

void pruebaRuedas() {
  Serial.println("T inicio");
  pasoPrueba("T1 solo IZQUIERDA adelante: debe girar a la DERECHA", 150, 0);
  pasoPrueba("T2 solo DERECHA adelante: debe girar a la IZQUIERDA", 0, 150);
  pasoPrueba("T3 las dos adelante: debe ir DERECHO", 150, 150);
  Serial.println("T fin");
  velIzq = 0; velDer = 0;
  ultimaOrden = millis();
}

// ============ MODO RUTA ============
// Lee "F1500,L400,..." y la guarda en ruta[]. Devuelve false si hay una letra invalida o esta vacia.
bool cargarRuta(const char *s, bool agregar) {
  if (!agregar) nTramos = 0;
  while (*s && nTramos < MAX_TRAMOS) {
    while (*s == ' ' || *s == ',') s++;
    if (!*s) break;
    char c = *s++;
    if (c >= 'a' && c <= 'z') c -= 32;                       // acepta minusculas
    if (c != 'F' && c != 'B' && c != 'L' && c != 'R' && c != 'S') return false;
    unsigned long ms = 0;
    while (*s >= '0' && *s <= '9') { ms = ms * 10 + (*s - '0'); s++; }
    if (ms > 60000UL) ms = 60000UL;
    ruta[nTramos].c = c;
    ruta[nTramos].ms = (unsigned int)ms;
    nTramos++;
  }
  while (*s == ' ' || *s == ',') s++;
  if (*s) return false;                                      // sobraron tramos: no caben (maximo 120)
  return nTramos > 0;
}

void aplicarTramo(byte i) {
  switch (ruta[i].c) {
    case 'F': velIzq = velAdelante;  velDer = velAdelante;  break;
    case 'B': velIzq = -velReversa;  velDer = -velReversa;  break;
    case 'L': velIzq = -velGiro;     velDer = velGiro;      break;   // gira a la izquierda
    case 'R': velIzq = velGiro;      velDer = -velGiro;     break;   // gira a la derecha
    default:  velIzq = 0;            velDer = 0;
  }
  finTramo = millis() + ruta[i].ms;
}

void iniciarRuta() {
  idxTramo = 0;
  enRuta = true;
  aplicarTramo(0);
  ultimaOrden = millis();
}

// motivo: 'Z' completa, 'O' obstaculo, 'X' cancelada
void terminarRuta(char motivo) {
  enRuta = false;
  velIzq = 0; velDer = 0;
  Serial.println(motivo);
}

void avanzarRuta() {
  if (!enRuta) return;
  ultimaOrden = millis();                                    // la ruta no depende del celular
  if (avanza(velIzq, velDer) && distancia < umbralParada()) {   // obstaculo al frente
    terminarRuta('O');
    return;
  }
  if ((long)(millis() - finTramo) >= 0) {
    idxTramo++;
    if (idxTramo >= nTramos) terminarRuta('Z');
    else aplicarTramo(idxTramo);
  }
}

// ============ ORDENES ============
void procesar(char *s) {
  if (s[0] == 'M') {
    char *coma = strchr(s, ',');
    if (!coma) return;
    *coma = '\0';
    enRuta = false;                                          // una orden manual cancela la ruta
    velIzq = constrain(atoi(s + 1), -255, 255);
    velDer = constrain(atoi(coma + 1), -255, 255);
    ultimaOrden = millis();
    if (eco) { Serial.print("E"); Serial.print(velIzq); Serial.print(","); Serial.println(velDer); }
  } else if (s[0] == 'S') {
    enRuta = false;
    velIzq = 0; velDer = 0;
    ultimaOrden = millis();
  } else if (s[0] == 'P') {
    ultimaOrden = millis();
  } else if (s[0] == 'T') {
    enRuta = false;
    pruebaRuedas();
  } else if (s[0] == 'V') {
    eco = (s[1] == '1');
  } else if (s[0] == 'K') {
    char *coma = strchr(s, ',');
    if (s[1] != '?' && coma) {
      *coma = '\0';
      factorIzq = constrain(atoi(s + 1), 10, 100);
      factorDer = constrain(atoi(coma + 1), 10, 100);
      guardarFactores();
    }
    reportarFactores();
  } else if (s[0] == 'R') {
    const char *txt = s + 1;
    if (*txt == '\0') txt = RUTA_DEFECTO;
    if (cargarRuta(txt, false)) { iniciarRuta(); Serial.print("R"); Serial.println(nTramos); }
    else Serial.println("R?");
  } else if (s[0] == 'A') {                                  // agrega tramos sin ejecutar
    if (!enRuta && cargarRuta(s + 1, true)) { Serial.print("A"); Serial.println(nTramos); }
    else Serial.println("A?");
  } else if (s[0] == 'C') {                                  // borra la ruta cargada
    if (!enRuta) { nTramos = 0; Serial.println("C"); }
  } else if (s[0] == 'E') {                                  // ejecuta la ruta cargada con R/A
    if (nTramos > 0 && !enRuta) { iniciarRuta(); Serial.print("R"); Serial.println(nTramos); }
    else Serial.println("R?");
  } else if (s[0] == 'X') {
    if (enRuta) terminarRuta('X');
    else { velIzq = 0; velDer = 0; Serial.println("X"); }
  } else if (s[0] == 'U') {
    velAdelante = constrain(atoi(s + 1), PWM_MINIMO, 255);
    Serial.print("U"); Serial.println(velAdelante);
  } else if (s[0] == 'W') {
    velReversa = constrain(atoi(s + 1), PWM_MINIMO, 255);
    Serial.print("W"); Serial.println(velReversa);
  } else if (s[0] == 'G') {
    velGiro = constrain(atoi(s + 1), PWM_MINIMO, 255);
    Serial.print("G"); Serial.println(velGiro);
  } else if (s[0] == 'N') {
    distParadaRuta = constrain(atoi(s + 1), 0, 100);
    Serial.print("N"); Serial.println(distParadaRuta);
  } else if (s[0] == 'Q') {
    Serial.print("Q"); Serial.print(enRuta ? 1 : 0); Serial.print(",");
    Serial.print(idxTramo); Serial.print(","); Serial.println(distancia);
  }
}

void leerSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (largo > 0) { buf[largo] = '\0'; procesar(buf); largo = 0; }
    } else if (largo < sizeof(buf) - 1) {
      buf[largo++] = c;
    } else {
      largo = 0;   // linea demasiado larga: se descarta
    }
  }
}

// ============ SETUP / LOOP ============
void setup() {
  Serial.begin(BAUDIOS_BT);
  pinMode(IZQ_DIR, OUTPUT); pinMode(IZQ_PWM, OUTPUT);
  pinMode(DER_DIR, OUTPUT); pinMode(DER_PWM, OUTPUT);
  pinMode(TRIG, OUTPUT); pinMode(ECHO, INPUT);
  cargarFactores();
  servo.attach(SERVO_PIN);
  servo.write(SERVO_CENTRO);
  aplicar(0, 0);
}

void loop() {
  leerSerial();

  // Seguridad en modo manual: sin ordenes recientes, el carro se detiene (la ruta tiene su propio tiempo)
  if (!enRuta && millis() - ultimaOrden > TIEMPO_SIN_ORDEN) { velIzq = 0; velDer = 0; }

  if (millis() - ultimaMedicion >= PERIODO_MEDICION) {
    ultimaMedicion = millis();
    distancia = medirDistancia();
  }

  avanzarRuta();
  actualizarMotores();

  if (millis() - ultimoReporte >= PERIODO_REPORTE) {
    ultimoReporte = millis();
    Serial.print("D");
    Serial.println(distancia);
  }
}
