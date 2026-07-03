import json
import time
import sys
import paho.mqtt.client as mqtt
from collections import deque
import threading

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
RSSI_1M = -47
N_PROPAGACION = 2.7
UMBRAL_ALARMA = 1.2 
TIEMPO_RESET = 3.0 

ESP_INTERIOR = "ESP32-00:70:07:B0:B0:F8"
ESP_PUERTA   = "ESP32-00:70:07:2E:A2:7C"

MQTT_BROKER = "127.0.0.1"
TOPIC_RAW = "museo/audioguias/raw"
TOPIC_DASHBOARD = "museo/audioguias"

ESC = {
    "HOME": "\033[H", "CLEAR": "\033[H\033[J", "BOLD": "\033[1m", "RESET": "\033[0m",
    "CIAN": "\033[96m", "BG_ROJO": "\033[41m", "BG_VERDE": "\033[42m", "AMARILLO": "\033[93m"
}

# --- FILTRO KALMAN 1D ---
class KalmanFilter:
    def __init__(self, q=0.1, r=1.0):
        self.q = q  # Ruido de proceso
        self.r = r  # Ruido de medición
        self.x = None # Estado estimado (RSSI)
        self.p = 1.0  # Error de estimación

    def update(self, z):
        if self.x is None:
            self.x = z
            return self.x
        self.p = self.p + self.q
        k = self.p / (self.p + self.r)
        self.x = self.x + k * (z - self.x)
        self.p = (1 - k) * self.p
        return self.x

# --- TRACKER CON FILTRO Y ESTADOS ---
class Tracker:
    def __init__(self, uuid):
        self.uuid = uuid
        self.filtros = {
            ESP_INTERIOR: KalmanFilter(q=0.1, r=1.2),
            ESP_PUERTA: KalmanFilter(q=0.1, r=1.2)
        }
        self.distancias = {ESP_INTERIOR: 10.0, ESP_PUERTA: 10.0}
        self.rssis_filtrados = {ESP_INTERIOR: -100.0, ESP_PUERTA: -100.0}
        
        self.confirmado_interior = False 
        self.last_seen = time.time()
        self.historia_pue = deque(maxlen=6)
        self.status = "seguro"
        self.alarma = False

    def registrar_lectura(self, esp_id, rssi_raw):
        self.last_seen = time.time()
        rssi_f = self.filtros[esp_id].update(rssi_raw)
        self.rssis_filtrados[esp_id] = rssi_f
        dist = 10 ** ((RSSI_1M - rssi_f) / (10 * N_PROPAGACION))
        self.distancias[esp_id] = dist
        if esp_id == ESP_PUERTA:
            self.historia_pue.append(dist)

    def reset_validation(self):
        if self.confirmado_interior:
            self.confirmado_interior = False
            self.historia_pue.clear()
            for f in self.filtros.values(): f.x = None
            return True
        return False

    def procesar(self):
        d_pue = self.distancias[ESP_PUERTA]
        d_int = self.distancias[ESP_INTERIOR]
        esta_saliendo = False
        if len(self.historia_pue) >= 3:
            if d_pue < (sum(list(self.historia_pue)[:-1]) / (len(self.historia_pue)-1)):
                esta_saliendo = True
        if d_int < 1.5:
            self.confirmado_interior = True
        self.alarma = False
        if self.confirmado_interior and esta_saliendo and d_pue < UMBRAL_ALARMA:
            self.alarma = True
        if self.alarma: self.status = "saliendo"
        elif self.distancias[ESP_PUERTA] < self.distancias[ESP_INTERIOR]: self.status = "cerca_salida"
        else: self.status = "seguro"

# --- LÓGICA DE CONTROL MQTT Y HILOS ---
tracker_dict = {}
lock = threading.Lock()

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        uuid = data["uuid"].lower()
        if not uuid.startswith(TARGET_PREFIX): return

        with lock:
            if uuid not in tracker_dict:
                tracker_dict[uuid] = Tracker(uuid)
            
            tr = tracker_dict[uuid]
            tr.registrar_lectura(data["esp"], float(data["rssi"]))
            tr.procesar()
            
            # 🔥 ENVIANDO TODOS LOS DATOS AL DASHBOARD SIN ELIMINAR LÓGICA
            client.publish(TOPIC_DASHBOARD, json.dumps({
                "uuid": uuid, 
                "alarma": tr.alarma, 
                "status": tr.status,
                "validado": tr.confirmado_interior,
                "rssi": round(tr.rssis_filtrados[ESP_PUERTA], 2),     # RSSI Puerta (principal)
                "dist": round(tr.distancias[ESP_PUERTA], 2),         # Distancia Puerta
                "rssi_int": round(tr.rssis_filtrados[ESP_INTERIOR], 2), # RSSI Interior
                "dist_int": round(tr.distancias[ESP_INTERIOR], 2)      # Distancia Interior
            }))
    except: pass

def main():
    sys.stdout.write(ESC["CLEAR"])
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(TOPIC_RAW)
    client.loop_start()

    try:
        while True:
            now = time.time()
            sys.stdout.write(ESC["HOME"])
            print(f"{ESC['CIAN']}{ESC['BOLD']} GUIDEGUARD v10.0 - KALMAN & REAL-TIME MONITOR {ESC['RESET']}")
            print(f" {time.strftime('%H:%M:%S')} | Watchdog: {TIEMPO_RESET}s | Activos: {len(tracker_dict)}")
            print(" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

            with lock:
                for uuid, tr in list(tracker_dict.items()):
                    silencio = now - tr.last_seen
                    if silencio > TIEMPO_RESET:
                        tr.reset_validation()
                        estado_label = f"{ESC['BG_ROJO']}¡DESCONECTADO!{ESC['RESET']}"
                    else:
                        estado_label = f"{ESC['BG_VERDE']}   EN LÍNEA   {ESC['RESET']}"

                    bg_alarma = ESC["BG_ROJO"] if tr.alarma else ""
                    print(f" ID: {uuid[-12:].upper()} | {estado_label} | {bg_alarma} ALARMA: {'SÍ' if tr.alarma else 'NO'} {ESC['RESET']}")
                    print(f"   ANTENA    | RSSI (K) |  DISTANCIA ")
                    print(f"   ──────────┼──────────┼────────────")
                    print(f"   PUERTA    | {tr.rssis_filtrados[ESP_PUERTA]:>6.1f} dBm| {tr.distancias[ESP_PUERTA]:>7.2f} m")
                    print(f"   INTERIOR  | {tr.rssis_filtrados[ESP_INTERIOR]:>6.1f} dBm| {tr.distancias[ESP_INTERIOR]:>7.2f} m")
                    val_color = ESC["BG_VERDE"] if tr.confirmado_interior else ESC["AMARILLO"]
                    print(f"\n   VALIDACIÓN: {val_color} {'SÍ' if tr.confirmado_interior else 'NO'} {ESC['RESET']} | SILENCIO: {silencio:.1f}s")
                    print(f"   STATUS: {ESC['BOLD']}{tr.status.upper()}{ESC['RESET']}")
                    print(" ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            time.sleep(0.1)
    except KeyboardInterrupt:
        client.loop_stop()

if __name__ == "__main__": main()