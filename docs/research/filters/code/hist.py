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

# --- CONFIGURACIÓN DE HISTÉRESIS (Márgenes de seguridad) ---
# Definimos un umbral de activación y uno de desactivación (el "buffer")
UMBRAL_SALIDA_ENTRAR = 1.3  # Se activa la alerta al bajar de 1.3m
UMBRAL_SALIDA_SALIR  = 1.6  # No se quita la alerta hasta subir de 1.6m

UMBRAL_CERCA_ENTRAR  = 3.8  # Entra en aviso al bajar de 3.8m
UMBRAL_CERCA_SALIR   = 4.3  # No vuelve a "seguro" hasta subir de 4.3m

# Diccionario para recordar el estado anterior de cada dispositivo
estados_anteriores = {} # {uuid: "seguro" | "cerca_salida" | "saliendo"}

# --- CLIENTE MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
try:
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()
except:
    pass

def aplicar_histeresis(uuid, dist_actual):
    """Lógica de decisión con zona muerta para evitar parpadeos"""
    # Si es un dispositivo nuevo, empezamos en seguro
    estado_anterior = estados_anteriores.get(uuid, "seguro")
    nuevo_estado = estado_anterior

    # Lógica para estado SALIENDO (Máxima prioridad)
    if dist_actual < UMBRAL_SALIDA_ENTRAR:
        nuevo_estado = "saliendo"
    elif estado_anterior == "saliendo" and dist_actual > UMBRAL_SALIDA_SALIR:
        # Solo bajamos de nivel si cruzamos el margen de seguridad superior
        nuevo_estado = "cerca_salida"

    # Lógica para estado CERCA_SALIDA
    if nuevo_estado != "saliendo":
        if dist_actual < UMBRAL_CERCA_ENTRAR:
            nuevo_estado = "cerca_salida"
        elif estado_anterior == "cerca_salida" and dist_actual > UMBRAL_CERCA_SALIR:
            nuevo_estado = "seguro"
    
    estados_anteriores[uuid] = nuevo_estado
    return nuevo_estado

def mostrar_linea_unica(rssi_raw, dist, estado, uuid):
    sufijo = uuid[-12:].upper()
    output = (f"\rID: {sufijo} | RAW: {rssi_raw:3} | "
              f"DIST: {dist:5.2f}m | ESTADO: {estado.upper():15}")
    sys.stdout.write(output)
    sys.stdout.flush()

async def main():
    print(f"Monitor activo - FILTRO DE HISTÉRESIS (Buffer: 30cm)")
    print(f"Calibración 1m: {RSSI_A_UN_METRO} dBm")
    print("-" * 75)

    def callback(device, adv):
        if adv.service_uuids:
            uuid_encontrado = next((u.lower() for u in adv.service_uuids 
                                   if u.lower().startswith(TARGET_PREFIX.lower())), None)
            
            if uuid_encontrado:
                rssi_crudo = adv.rssi
                
                # 1. Calculamos distancia (usamos el crudo para ver el efecto del filtro de estado)
                dist = 10**((RSSI_A_UN_METRO - rssi_crudo) / (10 * N_AMBIENTAL))
                
                # 2. Aplicamos Histéresis sobre la decisión
                estado = aplicar_histeresis(uuid_encontrado, dist)

                # 3. Envío MQTT
                payload = {
                    "id": uuid_encontrado[-12:].upper(),
                    "rssi": rssi_crudo, 
                    "dist": round(dist, 2), 
                    "status": estado
                }
                client.publish(MQTT_TOPIC, json.dumps(payload))
                
                # 4. UI
                mostrar_linea_unica(rssi_crudo, dist, estado, uuid_encontrado)

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