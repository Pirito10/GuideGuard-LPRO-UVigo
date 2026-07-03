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

# --- AJUSTES DE CALIBRACIÓN ---
RSSI_A_UN_METRO = -60  # Ajusta este valor pegando el móvil a 1 metro del PC
N_AMBIENTAL = 2.4      # Factor de propagación (entre 2.0 y 3.0)

# --- CONFIGURACIÓN DEL FILTRO DE MEDIANA ---
VENTANA_MEDIANA = 7    # Tamaño de la muestra (Se recomienda un número impar como 5, 7 o 9)
historico_rssi = {}    # {uuid: [lista_de_lecturas]}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def aplicar_filtro_mediana(uuid, rssi_crudo):
    """Calcula la mediana de las últimas lecturas para ignorar picos de ruido"""
    if uuid not in historico_rssi:
        historico_rssi[uuid] = []
    
    historico_rssi[uuid].append(rssi_crudo)
    
    if len(historico_rssi[uuid]) > VENTANA_MEDIANA:
        historico_rssi[uuid].pop(0)
    
    # statistics.median ordena la lista y devuelve el valor central
    return statistics.median(historico_rssi[uuid])

def mostrar_linea_unica(rssi_raw, rssi_filtered, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | MEDIANA: {rssi_filtered:3} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():12}")
    
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    print(f"Monitor activo - FILTRO DE MEDIANA (Ventana: {VENTANA_MEDIANA})")
    print(f"Calibración a 1m: {RSSI_A_UN_METRO} dBm")
    print("-" * 75)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                # 1. Aplicar Filtro de Mediana
                rssi_crudo = adv.rssi
                rssi_mediana = aplicar_filtro_mediana(uuid_encontrado, rssi_crudo)
                
                # 2. Calcular Distancia con calibración
                dist = 10**((RSSI_A_UN_METRO - rssi_mediana) / (10 * N_AMBIENTAL))
                
                # 3. Lógica de estado
                if dist < 1.5: estado = "saliendo"
                elif dist < 4.0: estado = "cerca_salida"
                else: estado = "seguro"

                # 4. Envío MQTT
                payload = {
                    "id": uuid_encontrado[-12:].upper(),
                    "rssi": int(rssi_mediana), 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # 5. Actualizar pantalla
                mostrar_linea_unica(rssi_crudo, rssi_mediana, dist, estado, uuid_encontrado)

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