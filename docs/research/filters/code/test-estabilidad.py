import asyncio
import statistics
import time
import sys
import math
from bleak import BleakScanner

# --- CONFIGURACIÓN ---
TARGET_PREFIX = "550e8400-e29b-41d4-a716-"
MAX_SAMPLES = 100
RSSI_A_UN_METRO = -43 
N_AMBIENTAL = 2.4

# --- CLASES DE FILTRADO ---
class KalmanFilter:
    def __init__(self, q=0.2, r=10.0):
        self.q, self.r, self.x, self.p = q, r, None, 1.0
    def filter(self, z):
        if self.x is None: self.x = z
        else:
            self.p += self.q
            k = self.p / (self.p + self.r)
            self.x += k * (z - self.x)
            self.p = (1 - k) * self.p
        return self.x

class OneEuroFilter:
    def __init__(self, freq=10.0, min_cutoff=1.0, beta=0.007):
        self.freq, self.min_cutoff, self.beta = freq, min_cutoff, beta
        self.x_prev, self.dx_prev = None, 0
    def filter(self, x):
        if self.x_prev is None: self.x_prev = x; return x
        te = 1.0 / self.freq
        a_d = 1.0 / (1.0 + (1.0 / (2 * math.pi * 1.0)) / te)
        dx = (x - self.x_prev) / te
        edx = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * abs(edx)
        a = 1.0 / (1.0 + (1.0 / (2 * math.pi * cutoff)) / te)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev = x_hat, edx
        return x_hat

# --- INICIALIZACIÓN DE MOTORES DE FILTRADO ---
filters = {
    "RAW (Sin filtro)": lambda x: x,
    "Media Móvil (n=10)": None, # Se gestiona con buffer
    "Mediana (n=7)": None,      # Se gestiona con buffer
    "EMA (alpha=0.2)": {"val": None, "alpha": 0.2},
    "Kalman (Q=0.02, R=10)": KalmanFilter(),
    "One Euro (Adaptativo)": OneEuroFilter(),
    "Híbrido (Mediana+Kalman)": {"med": [], "kal": KalmanFilter()}
}

buffers = {"Media Móvil (n=10)": [], "Mediana (n=7)": [], "Híbrido": []}
resultados = {name: [] for name in filters.keys()}

async def main():
    print(f"🧪 LABORATORIO GUIDEGUARD: Capturando {MAX_SAMPLES} muestras reales...")
    print("Coloca el móvil a una distancia fija y no lo muevas durante el test.")
    
    samples_count = 0

    def callback(device, adv):
        nonlocal samples_count
        uuid = next((u.lower() for u in adv.service_uuids if u.lower().startswith(TARGET_PREFIX.lower())), None)
        
        if uuid and samples_count < MAX_SAMPLES:
            rssi = adv.rssi
            samples_count += 1
            
            # 1. RAW
            resultados["RAW (Sin filtro)"].append(rssi)

            # 2. SMA
            b_sma = buffers["Media Móvil (n=10)"]
            b_sma.append(rssi)
            if len(b_sma) > 10: b_sma.pop(0)
            resultados["Media Móvil (n=10)"].append(sum(b_sma)/len(b_sma))

            # 3. Mediana
            b_med = buffers["Mediana (n=7)"]
            b_med.append(rssi)
            if len(b_med) > 7: b_med.pop(0)
            resultados["Mediana (n=7)"].append(statistics.median(b_med))

            # 4. EMA
            f_ema = filters["EMA (alpha=0.2)"]
            if f_ema["val"] is None: f_ema["val"] = rssi
            else: f_ema["val"] = f_ema["alpha"] * rssi + (1 - f_ema["alpha"]) * f_ema["val"]
            resultados["EMA (alpha=0.2)"].append(f_ema["val"])

            # 5. Kalman
            resultados["Kalman (Q=0.02, R=10)"].append(filters["Kalman (Q=0.02, R=10)"].filter(rssi))

            # 6. One Euro
            resultados["One Euro (Adaptativo)"].append(filters["One Euro (Adaptativo)"].filter(rssi))

            # 7. Híbrido (Mediana + Kalman)
            f_hib = filters["Híbrido (Mediana+Kalman)"]
            f_hib["med"].append(rssi)
            if len(f_hib["med"]) > 5: f_hib["med"].pop(0)
            val_med = statistics.median(f_hib["med"])
            resultados["Híbrido (Mediana+Kalman)"].append(f_hib["kal"].filter(val_med))

            sys.stdout.write(f"\rProgreso: [{'#'*(samples_count//5)}{'.'*(20-samples_count//5)}] {samples_count}%")
            sys.stdout.flush()

    scanner = BleakScanner(callback, scanning_mode="active")
    await scanner.start()
    while samples_count < MAX_SAMPLES: await asyncio.sleep(0.1)
    await scanner.stop()
    
    imprimir_tabla_comparativa()

def imprimir_tabla_comparativa():
    print("\n\n" + "═"*95)
    print(f"{'MÉTODO DE FILTRADO':<25} | {'DESV. TÍPICA':<15} | {'RANGO (MAX-MIN)':<15} | {'ESTABILIDAD':<15}")
    print("─"*95)
    
    raw_stdev = statistics.stdev(resultados["RAW (Sin filtro)"])

    for metodo, datos in resultados.items():
        if len(datos) < 2: continue
        stdev = statistics.stdev(datos)
        rango = max(datos) - min(datos)
        
        # Estabilidad: comparación porcentual de mejora de ruido respecto al raw
        mejora = (1 - (stdev / raw_stdev)) * 100 if raw_stdev > 0 else 0
        
        print(f"{metodo:<25} | {stdev:14.3f} | {rango:15.1f} | {mejora:13.1f}%")
    
    print("═"*95)
    print("CONSEJO: El método con mayor % de ESTABILIDAD y menor DESV. TÍPICA es el ideal para el radar.")

if __name__ == "__main__":
    asyncio.run(main())