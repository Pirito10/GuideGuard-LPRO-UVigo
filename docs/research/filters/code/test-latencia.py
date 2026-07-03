import math
import statistics

# --- CONFIGURACIÓN DEL ESCENARIO ---
FREQ = 10  # 10Hz (100ms por muestra)
INICIO = -50
FIN = -80
# Damos 200 muestras tras el salto para que hasta el Kalman más lento llegue
SAMPLES_POST = 200 

class KalmanFilter:
    def __init__(self, q, r):
        self.q, self.r = q, r
        self.x, self.p = INICIO, 1.0
    def filter(self, z):
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= (1 - k)
        return self.x

class OneEuroFilter:
    def __init__(self, freq=10.0, min_cutoff=1.0, beta=0.007):
        self.freq, self.min_cutoff, self.beta = freq, min_cutoff, beta
        self.x_prev, self.dx_prev = INICIO, 0
    def filter(self, x):
        te = 1.0 / self.freq
        a_d = 1.0 / (1.0 + (1.0 / (2 * math.pi * 1.0)) / te)
        dx = (x - self.x_prev) / te
        edx = a_d * dx + (1 - a_d) * self.dx_prev
        cutoff = self.min_cutoff + self.beta * abs(edx)
        a = 1.0 / (1.0 + (1.0 / (2 * math.pi * cutoff)) / te)
        x_hat = a * x + (1 - a) * self.x_prev
        self.x_prev, self.dx_prev = x_hat, edx
        return x_hat

def ejecutar_benchmark():
    # Generar señal: 10 muestras estables y luego el salto
    datos = [INICIO] * 10 + [FIN] * SAMPLES_POST
    umbral_90 = INICIO + (FIN - INICIO) * 0.9 # -77dBm
    
    # Inicializar filtros
    filtros = {
        "SMA (Media Móvil n=10)": {"buffer": [INICIO]*10, "type": "sma"},
        "Mediana (n=7)": {"buffer": [INICIO]*7, "type": "mediana"},
        "EMA (alpha=0.2)": {"val": INICIO, "type": "ema", "a": 0.2},
        "Kalman (Q=0.02, R=10)": {"obj": KalmanFilter(0.02, 10), "type": "obj"},
        "One Euro (Estándar)": {"obj": OneEuroFilter(), "type": "obj"},
        "Híbrido (Mediana+Kalman)": {"med": [INICIO]*5, "kal": KalmanFilter(0.02, 10), "type": "hib"}
    }

    resultados = {}

    for nombre, f in filtros.items():
        retraso_muestras = None
        
        for i, z in enumerate(datos):
            # Procesamiento
            if f["type"] == "sma":
                f["buffer"].append(z); f["buffer"].pop(0)
                val = sum(f["buffer"]) / len(f["buffer"])
            elif f["type"] == "mediana":
                f["buffer"].append(z); f["buffer"].pop(0)
                val = statistics.median(f["buffer"])
            elif f["type"] == "ema":
                f["val"] = f["a"] * z + (1 - f["a"]) * f["val"]
                val = f["val"]
            elif f["type"] == "obj":
                val = f["obj"].filter(z)
            elif f["type"] == "hib":
                f["med"].append(z); f["med"].pop(0)
                val_med = statistics.median(f["med"])
                val = f["kal"].filter(val_med)

            # Medir retraso tras el salto (índice 10)
            if i >= 10 and retraso_muestras is None:
                if val <= umbral_90: # Detectamos cuando cruza el 90% del salto
                    retraso_muestras = i - 10

        resultados[nombre] = retraso_muestras

    # Imprimir Tabla
    print(f"\n{'MÉTODO DE FILTRADO':<25} | {'LAG (MUESTRAS)':<15} | {'RETARDO (ms)':<15}")
    print("-" * 60)
    for nombre, lag in resultados.items():
        ms = lag * (1000/FREQ) if lag is not None else "Fuera de rango"
        print(f"{nombre:<25} | {str(lag):<15} | {ms:<15.0f}")

if __name__ == "__main__":
    ejecutar_benchmark()