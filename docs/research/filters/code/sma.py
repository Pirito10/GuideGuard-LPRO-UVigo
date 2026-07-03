import asyncio
import json
import sys
import paho.mqtt.client as mqtt
from bleak import BleakScanner

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MQTT_BROKER = "127.0.0.1"
MQTT_TOPIC = "museo/audioguias"

# --- AJUSTES DE CALIBRACIÓN (IMPORTANTE) ---
RSSI_A_UN_METRO = -60  # Ajusta este valor según tus pruebas a 1 metro
N_AMBIENTAL = 2.4      # Factor de propagación (2.0 espacio abierto, 2.4-3.0 interiores)

# --- CONFIGURACIÓN DEL FILTRO ---
VENTANA_MEDIA = 5
historico_rssi = {}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def aplicar_filtro_media(uuid, rssi_crudo):
    if uuid not in historico_rssi:
        historico_rssi[uuid] = []
    historico_rssi[uuid].append(rssi_crudo)
    if len(historico_rssi[uuid]) > VENTANA_MEDIA:
        historico_rssi[uuid].pop(0)
    return sum(historico_rssi[uuid]) / len(historico_rssi[uuid])

def mostrar_linea_unica(rssi_raw, rssi_filtered, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    # \r vuelve al inicio de la línea, end="" evita el salto de línea
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | FILT: {rssi_filtered:5.1f} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():12}")
    
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    print(f"Monitor activo (Calibrado a 1m: {RSSI_A_UN_METRO} dBm)")
    print("ID DISPOSITIVO | RSSI RAW | RSSI FILT | DISTANCIA | ESTADO")
    print("-" * 75)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                # 1. Aplicar Filtro
                rssi_crudo = adv.rssi
                rssi_filtrado = aplicar_filtro_media(uuid_encontrado, rssi_crudo)
                
                # 2. Calcular Distancia con calibración
                # Formula: d = 10 ^ ((Measured_Power - RSSI) / (10 * N))
                dist = 10**((RSSI_A_UN_METRO - rssi_filtrado) / (10 * N_AMBIENTAL))
                
                # 3. Lógica de estado
                if dist < 1.5: estado = "saliendo"
                elif dist < 4.0: estado = "cerca_salida"
                else: estado = "seguro"

                # 4. MQTT
                payload = {
                    "id": uuid_encontrado[-12:].upper(),
                    "rssi": round(rssi_filtrado, 1), 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # 5. Actualizar pantalla
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