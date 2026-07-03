import asyncio
import json
import sys
import time
import math
import paho.mqtt.client as mqtt
from bleak import BleakScanner

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC = "museo/audioguias"

# --- AJUSTES DE CALIBRACIÓN ---
RSSI_A_UN_METRO = -60 
N_AMBIENTAL = 2.4     

# --- CLASE FILTRO ONE EURO ---
class OneEuroFilter:
    def __init__(self, freq, min_cutoff=1.0, beta=0.007, d_cutoff=1.0):
        self.freq = freq           # Frecuencia estimada (Hz) de los beacons
        self.min_cutoff = min_cutoff # A menor valor, más estable en reposo
        self.beta = beta           # A mayor valor, menos lag en movimiento
        self.d_cutoff = d_cutoff   # Corte para la derivada (estándar 1.0)
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
        
        # Calcular velocidad de cambio (derivada)
        dx = (x - self.x_prev) * self.freq
        edx = (self._alpha(self.d_cutoff) * dx) + ((1 - self._alpha(self.d_cutoff)) * self.dx_prev)
        
        # Calcular cutoff dinámico
        cutoff = self.min_cutoff + self.beta * abs(edx)
        
        # Aplicar filtro de paso bajo adaptativo
        a = self._alpha(cutoff)
        x_hat = (a * x) + ((1 - a) * self.x_prev)
        
        # Guardar estados
        self.x_prev, self.dx_prev = x_hat, edx
        return x_hat

# Diccionario para gestionar un objeto filtro por cada dispositivo detectado
filtros_one_euro = {}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def mostrar_linea_unica(rssi_raw, rssi_filtered, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | 1 EURO: {rssi_filtered:5.1f} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():12}")
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    # Asumimos que emites a 10 Hz (Low Latency)
    print(f"Monitor activo - FILTRO ONE EURO (Dinámico)")
    print(f"Config: min_cutoff=1.0, beta=0.007 | Calibración 1m: {RSSI_A_UN_METRO} dBm")
    print("-" * 80)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                # 1. Crear el filtro para este dispositivo si no existe
                if uuid_encontrado not in filtros_one_euro:
                    # freq=10.0 porque estamos usando Low Latency (100ms)
                    filtros_one_euro[uuid_encontrado] = OneEuroFilter(freq=10.0)
                
                # 2. Aplicar Filtro One Euro
                rssi_crudo = adv.rssi
                rssi_filtrado = filtros_one_euro[uuid_encontrado].filter(rssi_crudo)
                
                # 3. Calcular Distancia
                dist = 10**((RSSI_A_UN_METRO - rssi_filtrado) / (10 * N_AMBIENTAL))
                
                # 4. Lógica de estado
                if dist < 1.5: estado = "saliendo"
                elif dist < 4.0: estado = "cerca_salida"
                else: estado = "seguro"

                # 5. Envío MQTT
                payload = {
                    "id": uuid_encontrado[-12:].upper(),
                    "rssi": round(rssi_filtrado, 1), 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # 6. UI
                mostrar_linea_unica(rssi_crudo, rssi_filtrado, dist, estado, uuid_encontrado)

    scanner = BleakScanner(callback, scanning_mode="active")
    
    try:
        await scanner.start()
        while True:
            await asyncio.sleep(1)
          
    except KeyboardInterrupt:
        await scanner.stop()
        print("\n\nMonitor finalizado.")

if __name__ == "__main__":
    asyncio.run(main())