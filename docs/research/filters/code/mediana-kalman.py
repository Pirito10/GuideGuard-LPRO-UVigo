import asyncio
import json
import sys
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

# --- CONFIGURACIÓN PIPELINE ---
VENTANA_MEDIANA = 5  # Limpiador de picos
Q_KALMAN = 0.02      # Estabilidad de movimiento (menor = más estable)
R_KALMAN = 10.0      # Confianza en la lectura (mayor = filtra más ruido)

class KalmanFilter:
    def __init__(self, q, r):
        self.q, self.r = q, r
        self.x, self.p = None, 1.0
    def update(self, measurement):
        if self.x is None: self.x = measurement; return measurement
        self.p = self.p + self.q
        k = self.p / (self.p + self.r)
        self.x = self.x + k * (measurement - self.x)
        self.p = (1 - k) * self.p
        return self.x

# Diccionarios de estado por dispositivo
historial_mediana = {} 
filtros_kalman = {}

# --- MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except: pass

def filtrar_pipeline(uuid, rssi_raw):
    # PASO 1: Mediana para limpiar picos brutos
    if uuid not in historial_mediana: historial_mediana[uuid] = []
    historial_mediana[uuid].append(rssi_raw)
    if len(historial_mediana[uuid]) > VENTANA_MEDIANA: historial_mediana[uuid].pop(0)
    rssi_pre_limpio = statistics.median(historial_mediana[uuid])

    # PASO 2: Kalman para suavizar la trayectoria
    if uuid not in filtros_kalman: filtros_kalman[uuid] = KalmanFilter(Q_KALMAN, R_KALMAN)
    return filtros_kalman[uuid].update(rssi_pre_limpio)

async def main():
    print(f"Monitor GuideGuard - Pipeline: MEDIANA + KALMAN")
    print("-" * 80)

    def callback(device, adv):
        if adv.service_uuids:
            uuid = next((u.lower() for u in adv.service_uuids if u.lower().startswith(TARGET_PREFIX.lower())), None)
            if uuid:
                # Aplicar Pipeline
                rssi_filt = filtrar_pipeline(uuid, adv.rssi)
                dist = 10**((RSSI_A_UN_METRO - rssi_filt) / (10 * N_AMBIENTAL))
                
                # Lógica de estado simplificada
                estado = "saliendo" if dist < 1.5 else "cerca_salida" if dist < 4.0 else "seguro"

                # Enviar y Mostrar
                payload = {"id": uuid[-12:].upper(), "rssi": round(rssi_filt, 1), "dist": round(dist, 2), "status": estado}
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                sys.stdout.write(f"\rID: {payload['id']} | RAW: {adv.rssi:3} | FILT: {rssi_filt:5.1f} | DIST: {dist:5.2f}m | {estado.upper():12}")
                sys.stdout.flush()

    scanner = BleakScanner(callback, scanning_mode="active")
    await scanner.start()
    while True: await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())