import asyncio
import json
import sys
import paho.mqtt.client as mqtt
from bleak import BleakScanner

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC = "museo/audioguias"

# --- AJUSTES DE CALIBRACIÓN ---
RSSI_A_UN_METRO = -60 
N_AMBIENTAL = 2.4     

# --- CONFIGURACIÓN FILTRO DE KALMAN ---
# Q: Ruido de proceso (qué tan rápido cambia el valor real). 
# R: Ruido de medición (qué tan "mala" es la lectura del sensor).
# Si el valor baila mucho, aumenta R o disminuye Q.
Q_PROCESO = 0.05
R_MEDICION = 5.0

class KalmanFilter:
    def __init__(self, q, r):
        self.q = q  # Process noise covariance
        self.r = r  # Measurement noise covariance
        self.x = None  # Valor estimado
        self.p = 1.0   # Error de estimación

    def update(self, measurement):
        if self.x is None:
            self.x = measurement
            return measurement
        
        # Predicción
        self.p = self.p + self.q
        
        # Ganancia de Kalman
        k = self.p / (self.p + self.r)
        
        # Actualización
        self.x = self.x + k * (measurement - self.x)
        self.p = (1 - k) * self.p
        
        return self.x

filtros_kalman = {} # {uuid: objeto KalmanFilter}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def mostrar_linea_unica(rssi_raw, rssi_filtered, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | KALMAN: {rssi_filtered:5.1f} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():12}")
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    print(f"Monitor activo - FILTRO DE KALMAN (Q={Q_PROCESO}, R={R_MEDICION})")
    print(f"Calibración a 1m: {RSSI_A_UN_METRO} dBm")
    print("-" * 75)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                # 1. Aplicar Filtro de Kalman
                if uuid_encontrado not in filtros_kalman:
                    filtros_kalman[uuid_encontrado] = KalmanFilter(Q_PROCESO, R_MEDICION)
                
                rssi_crudo = adv.rssi
                rssi_kalman = filtros_kalman[uuid_encontrado].update(rssi_crudo)
                
                # 2. Calcular Distancia
                dist = 10**((RSSI_A_UN_METRO - rssi_kalman) / (10 * N_AMBIENTAL))
                
                # 3. Lógica de estado
                if dist < 1.5: estado = "saliendo"
                elif dist < 4.0: estado = "cerca_salida"
                else: estado = "seguro"

                # 4. MQTT
                payload = {
                    "id": uuid_encontrado[-12:].upper(),
                    "rssi": round(rssi_kalman, 1), 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # 5. UI
                mostrar_linea_unica(rssi_crudo, rssi_kalman, dist, estado, uuid_encontrado)

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