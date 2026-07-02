"""
GuideGuard — Script de captura de RSSI para pruebas de antenas
Uso: python captura.py
Guarda los resultados en resultados/ANTENA_YYYYMMDD_HHMMSS.json
"""

import json
import time
import sys
import signal
import statistics
from datetime import datetime
from pathlib import Path
import paho.mqtt.client as mqtt

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MQTT_BROKER   = "127.0.0.1"
MQTT_PORT     = 1883
MQTT_TOPIC    = "museo/audioguias/raw"

ANTENAS_VALIDAS  = ["integrada", "simple", "avanzada"]
DURACION_CAPTURA = 30   # segundos por medición
MIN_PAQUETES     = 20   # mínimo para considerar la medición válida

# --- CONTROL DE TERMINAL ---
ESC = {
    "LIMPIAR" : "\033[H\033[J",
    "HOME"    : "\033[H",
    "HIDE"    : "\033[?25l",
    "SHOW"    : "\033[?25h",
    "BOLD"    : "\033[1m",
    "RESET"   : "\033[0m",
    "CIAN"    : "\033[96m",
    "VERDE"   : "\033[92m",
    "AMARILLO": "\033[93m",
    "ROJO"    : "\033[91m",
    "GRIS"    : "\033[90m",
}

def c(codigo, texto):
    return f"{ESC[codigo]}{texto}{ESC['RESET']}"

# ── Estado global de captura ──────────────────────────────────────────────────
estado = {
    "capturando"  : False,
    "muestras"    : [],
    "inicio"      : 0.0,
    "uuid_visto"  : None,
}

sesion = {
    "antena"     : None,
    "mediciones" : [],   # lista de dicts con los resultados
    "inicio"     : datetime.now().isoformat(),
}

# ── MQTT callbacks ────────────────────────────────────────────────────────────
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    if not estado["capturando"]:
        return
    try:
        payload = json.loads(msg.payload.decode())
        uuid    = payload.get("uuid", "").lower()
        rssi    = payload.get("rssi", None)
        if not uuid.startswith(TARGET_PREFIX) or rssi is None:
            return
        estado["muestras"].append(rssi)
        estado["uuid_visto"] = uuid
    except Exception:
        pass

# ── Helpers de UI ─────────────────────────────────────────────────────────────
def limpiar():
    sys.stdout.write(ESC["LIMPIAR"])
    sys.stdout.flush()

def cabecera():
    print(c("CIAN", c("BOLD", "╔══════════════════════════════════════════╗")))
    print(c("CIAN", c("BOLD", "║   GUIDEGUARD — CAPTURA DE PRUEBAS RSSI   ║")))
    print(c("CIAN", c("BOLD", "╚══════════════════════════════════════════╝")))
    print()

def pedir_opcion(pregunta, opciones):
    """Muestra un menú numerado y devuelve el valor elegido."""
    print(c("BOLD", pregunta))
    for i, op in enumerate(opciones, 1):
        print(f"  {c('CIAN', str(i))}) {op}")
    while True:
        try:
            idx = int(input(c("AMARILLO", "  Opción: "))) - 1
            if 0 <= idx < len(opciones):
                return opciones[idx]
            print(c("ROJO", "  Opción no válida."))
        except (ValueError, EOFError):
            print(c("ROJO", "  Introduce un número."))

def pedir_distancia():
    while True:
        try:
            txt = input(c("AMARILLO", "  Distancia en metros: ")).strip()
            d   = float(txt)
            if d > 0:
                return d
            print(c("ROJO", "  La distancia debe ser mayor que 0."))
        except (ValueError, EOFError):
            print(c("ROJO", "  Introduce un número válido (ej: 1.5)."))

def esperar_señal(client):
    """Bloquea hasta recibir al menos 3 paquetes del dispositivo objetivo."""
    print()
    print(c("AMARILLO", "  Esperando señal del dispositivo..."), end="", flush=True)
    recibidos = []

    def _on_msg(cl, ud, msg):
        try:
            p    = json.loads(msg.payload.decode())
            uuid = p.get("uuid", "").lower()
            rssi = p.get("rssi", None)
            if uuid.startswith(TARGET_PREFIX) and rssi is not None:
                recibidos.append(rssi)
        except Exception:
            pass

    client.on_message = _on_msg
    while len(recibidos) < 3:
        time.sleep(0.2)
        print(".", end="", flush=True)

    client.on_message = on_message
    print(c("VERDE", f" OK ({recibidos[-1]} dBm)"))

def barra_progreso(transcurrido, total, n_muestras):
    ancho  = 30
    hecho  = int(ancho * transcurrido / total)
    barra  = "█" * hecho + "░" * (ancho - hecho)
    pct    = int(100 * transcurrido / total)
    resto  = max(0, total - transcurrido)
    return (f"  [{c('VERDE', barra)}] {pct:3d}%  "
            f"{c('GRIS', f'{n_muestras} paquetes  {resto:.0f}s restantes')}")

# ── Lógica de captura ─────────────────────────────────────────────────────────
def capturar(client, antena, distancia, orientacion):
    """Captura RSSI durante DURACION_CAPTURA segundos y devuelve el dict de resultado."""
    estado["capturando"] = True
    estado["muestras"]   = []
    estado["inicio"]     = time.time()

    print()
    print(c("BOLD", f"  Capturando {DURACION_CAPTURA}s  |  antena={antena}  dist={distancia}m"))
    print()

    while True:
        transcurrido = time.time() - estado["inicio"]
        if transcurrido >= DURACION_CAPTURA:
            print(f"\r{barra_progreso(DURACION_CAPTURA, DURACION_CAPTURA, len(estado['muestras']))}",
                  end="", flush=True)
            break
        print(f"\r{barra_progreso(transcurrido, DURACION_CAPTURA, len(estado['muestras']))}",
              end="", flush=True)
        time.sleep(0.25)

    estado["capturando"] = False
    print()

    muestras = estado["muestras"]
    if len(muestras) < MIN_PAQUETES:
        print(c("ROJO",
                f"\n  ⚠ Solo {len(muestras)} paquetes recibidos (mínimo {MIN_PAQUETES}). "
                f"Medición descartada."))
        return None

    resultado = {
        "timestamp"  : datetime.now().isoformat(),
        "distancia_m": distancia,
        "orientacion": orientacion,
        "n_muestras" : len(muestras),
        "hz_medio"   : round(len(muestras) / DURACION_CAPTURA, 2),
        "rssi_media" : round(statistics.mean(muestras), 2),
        "rssi_median": round(statistics.median(muestras), 2),
        "rssi_min"   : min(muestras),
        "rssi_max"   : max(muestras),
        "rssi_stdev" : round(statistics.stdev(muestras) if len(muestras) > 1 else 0.0, 2),
        "muestras_raw": muestras,
    }

    print()
    print(c("VERDE", "  ✓ Medición completada:"))
    print(f"    Media:  {resultado['rssi_media']:6.2f} dBm")
    print(f"    Mediana:{resultado['rssi_median']:6.2f} dBm")
    print(f"    Stdev:  {resultado['rssi_stdev']:6.2f} dB")
    print(f"    Rango:  [{resultado['rssi_min']} , {resultado['rssi_max']}] dBm")
    print(f"    Tasa:   {resultado['hz_medio']:.1f} Hz")
    return resultado

# ── Guardado ──────────────────────────────────────────────────────────────────
def guardar(sesion, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sesion, f, indent=2, ensure_ascii=False)
    print(c("VERDE", f"\n  Resultados guardados en: {filepath}"))

# ── Bucle principal ───────────────────────────────────────────────────────────
def main():
    # Conectar MQTT
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    limpiar()
    cabecera()
    print(c("AMARILLO", "  Conectando al broker MQTT..."), end="", flush=True)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except Exception as e:
        print(c("ROJO", f"\n  Error de conexión: {e}"))
        sys.exit(1)
    client.loop_start()
    print(c("VERDE", " OK"))

    # Selección de antena (una vez por sesión, antes de crear el archivo)
    limpiar()
    cabecera()
    sesion["antena"] = pedir_opcion("¿Qué antena estás usando?", ANTENAS_VALIDAS)

    # Archivo de salida — nombre ANTENA_TIMESTAMP dentro de resultados/
    directorio = Path("resultados")
    directorio.mkdir(exist_ok=True)
    ts       = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filepath = directorio / f"{sesion['antena']}_{ts}.json"

    # Gestión de Ctrl+C: guarda lo que haya
    def salir(sig, frame):
        estado["capturando"] = False
        client.loop_stop()
        if sesion["mediciones"]:
            guardar(sesion, filepath)
        print(ESC["SHOW"] + c("AMARILLO", "\n\n  Sesión finalizada.\n"))
        sys.exit(0)
    signal.signal(signal.SIGINT, salir)

    continuar = True
    while continuar:
        limpiar()
        cabecera()
        print(c("BOLD", f"  Antena activa: {c('CIAN', sesion['antena'])}"))
        print(c("GRIS",  f"  Mediciones realizadas: {len(sesion['mediciones'])}"))
        print()

        # Parámetros de la medición
        distancia = pedir_distancia()
        print()
        if sesion["antena"] == "integrada":
            orientacion = "no_aplica"
        else:
            orientacion = pedir_opcion("Orientación de la antena:",
                                       ["vertical",
                                        "horizontal",
                                        "dirigida"])

        # Esperar señal antes de capturar
        esperar_señal(client)

        input(c("AMARILLO", "\n  Pulsa Enter para iniciar la captura..."))

        resultado = capturar(client, sesion["antena"], distancia, orientacion)
        if resultado:
            sesion["mediciones"].append(resultado)
            guardar(sesion, filepath)   # guardado incremental

        print()
        resp = input(c("BOLD", "  ¿Hacer otra medición? [S/n]: ")).strip().lower()
        continuar = resp not in ("n", "no")

    client.loop_stop()
    limpiar()
    cabecera()
    print(c("VERDE", f"  Sesión completada. {len(sesion['mediciones'])} mediciones guardadas."))
    print(c("GRIS",  f"  Archivo: {filepath}\n"))

if __name__ == "__main__":
    sys.stdout.write(ESC["HIDE"])
    main()
    sys.stdout.write(ESC["SHOW"])