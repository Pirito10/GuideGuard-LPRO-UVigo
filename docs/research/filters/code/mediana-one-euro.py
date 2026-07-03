import asyncio
import json
import sys
import math
import statistics
import paho.mqtt.client as mqtt
from bleak import BleakScanner

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC = "museo/audioguias"

# --- CALIBRACIÓN ---
RSSI_A_UN_METRO = -60 
N_AMBIENTAL = 2.4     

# --- CONFIGURACIÓN PIPELINE HÍBRIDO ---
# 1. Mediana
VENTANA_MEDIANA = 5 

# 2. One Euro (Ajustes recomendados)
FREQ_BEACONS = 10.0   # 10Hz (Low Latency 100ms)
MIN_CUTOFF = 0.5      # Bajar para más estabilidad en reposo (ej. 0.1)
BETA = 0.05           # Subir para menos lag en movimiento (ej. 0.1)

# --- CLASE FILTRO ONE EURO ---
class OneEuroFilter:
    def __init__(self, freq, min_cutoff=1.0, beta=0.0, d_cutoff=1.0):
        self.freq = freq
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev = None
        self.dx_prev = 0

    def _alpha(self, cutoff):
        tau = 1.0 / (2 * math.pi * cutoff)
        te = 1.0 / self.freq
        return 1.0 / (1.0 + tau / te)

    def filter(self, x):
        if self.x_prev is None:
            self.x_prev = x
            return x
        dx = (x - self.x_prev) * self.freq
        edx = (self._alpha(self.d_cutoff) * dx) + ((1 - self._alpha(self.d_cutoff)) * self.dx_prev)
        cutoff = self.min_cutoff + self.beta * abs(edx)
        a = self._alpha(cutoff)
        x_hat = (a * x) + ((1 - a) * self.x_prev)
        self.x_prev, self.dx_prev = x_hat, edx
        return x_hat

# Diccionarios de estado por dispositivo
historial_mediana = {} 
filtros_one_euro = {}

# --- MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except: pass

def filtrar_pipeline_hibrido(uuid, rssi_raw):
    # PASO 1: Filtro de Mediana (Limpieza de picos)
    if uuid not in historial_mediana: historial_mediana[uuid] = []
    historial_mediana[uuid].append(rssi_raw)
    if len(historial_mediana[uuid]) > VENTANA_MEDIANA: historial_mediana[uuid].pop(0)
    rssi_limpio = statistics.median(historial_mediana[uuid])

    # PASO 2: Filtro One Euro (Suavizado adaptativo)
    if uuid not in filtros_one_euro:
        filtros_one_euro[uuid] = OneEuroFilter(freq=FREQ_BEACONS, min_cutoff=MIN_CUTOFF, beta=BETA)
    
    return filtros_one_euro[uuid].filter(rssi_limpio)

async def main():
    print(f"Monitor GuideGuard - Pipeline: MEDIANA + ONE EURO")
    print(f"Config: Mediana({VENTANA_MEDIANA}) + 1€(Beta={BETA}, MinCut={MIN_CUTOFF})")
    print("-" * 85)

    def callback(device, adv):
        if adv.service_uuids:
            uuid = next((u.lower() for u in adv.service_uuids if u.lower().startswith(TARGET_PREFIX.lower())), None)
            if uuid:
                # Aplicar Pipeline Híbrido
                rssi_filt = filtrar_pipeline_hibrido(uuid, adv.rssi)
                
                # Calcular Distancia
                dist = 10**((RSSI_A_UN_METRO - rssi_filt) / (10 * N_AMBIENTAL))
                
                # Lógica de estado
                estado = "saliendo" if dist < 1.5 else "cerca_salida" if dist < 4.0 else "seguro"

                # Enviar MQTT
                payload = {
                    "id": uuid[-12:].upper(), 
                    "rssi": round(rssi_filt, 1), 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # UI en una sola línea
                sys.stdout.write(f"\rID: {payload['id']} | RAW: {adv.rssi:3} | 1€: {rssi_filt:5.1f} | DIST: {dist:5.2f}m | {estado.upper():12}")
                sys.stdout.flush()

    scanner = BleakScanner(callback, scanning_mode="active")
    await scanner.start()
    while True: await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())