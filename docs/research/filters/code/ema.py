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
RSSI_A_UN_METRO = -60  # Valor de RSSI a 1 metro de distancia
N_AMBIENTAL = 2.4      # Factor de propagación (2.0 a 3.0)

# --- CONFIGURACIÓN DEL FILTRO EMA ---
# ALPHA (α): Entre 0.0 y 1.0. 
# Cerca de 0: Mucha estabilidad, pero mucho retraso (lag).
# Cerca de 1: Reacción instantánea, pero mucha vibración (ruido).
ALPHA = 0.7
ultimos_rssi = {}      # {uuid: ultimo_rssi_filtrado}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def aplicar_filtro_ema(uuid, rssi_crudo):
    """Calcula el EMA: (ALPHA * actual) + ((1 - ALPHA) * anterior)"""
    if uuid not in ultimos_rssi:
        # Inicializamos con el primer valor recibido
        ultimos_rssi[uuid] = rssi_crudo
        return rssi_crudo
    
    # Aplicamos la fórmula del filtro
    rssi_filtrado = (ALPHA * rssi_crudo) + ((1 - ALPHA) * ultimos_rssi[uuid])
    
    # Guardamos el resultado para la siguiente iteración
    ultimos_rssi[uuid] = rssi_filtrado
    return rssi_filtrado

def mostrar_linea_unica(rssi_raw, rssi_filtered, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | EMA: {rssi_filtered:5.1f} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():12}")
    
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    print(f"Monitor activo - FILTRO EMA (Alpha: {ALPHA})")
    print(f"Calibración a 1m: {RSSI_A_UN_METRO} dBm")
    print("-" * 75)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                # 1. Aplicar Filtro EMA
                rssi_crudo = adv.rssi
                rssi_filtrado = aplicar_filtro_ema(uuid_encontrado, rssi_crudo)
                
                # 2. Calcular Distancia con calibración
                dist = 10**((RSSI_A_UN_METRO - rssi_filtrado) / (10 * N_AMBIENTAL))
                
                # 3. Lógica de estado
                if dist < 1.5: estado = "saliendo"
                elif dist < 4.0: estado = "cerca_salida"
                else: estado = "seguro"

                # 4. Envío MQTT
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