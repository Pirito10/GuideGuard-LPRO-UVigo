"""
GuideGuard — Análisis de resultados de pruebas de antenas (con orientación)
Uso: python analisis_orientacion.py resultados_YYYYMMDD_HHMMSS.json
     python analisis_orientacion.py resultados_A.json resultados_B.json ...

Diferencia respecto a analisis.py:
  - La antena 5dBi se desglosa por orientación (vertical_arriba,
    horizontal_hacia_dispositivo, horizontal_perpendicular) en lugar de
    promediarlas juntas.
  - Se añade una sección y gráfica específica de comparación por orientación.
Genera: informe.txt  +  gráficas PNG en analisis_orientacion_TIMESTAMP/
"""

import json
import sys
import statistics
from pathlib import Path
from datetime import datetime
from itertools import groupby

# matplotlib es opcional — si no está, solo genera el informe de texto
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    MATPLOTLIB = True
except ImportError:
    MATPLOTLIB = False
    print("[aviso] matplotlib no encontrado — solo se generará el informe de texto.")

# ── Antena que tiene orientaciones múltiples ──────────────────────────────────
ANTENA_CON_ORIENTACION = "avanzada"

# Etiquetas cortas para las orientaciones en gráficas
ETIQ_ORIENTACION = {
    "vertical"           : "vertical",
    "horizontal"         : "horizontal",
    "dirigida": "dirigida",
    "no_aplica"          : "",
}

# ── Paleta de colores ─────────────────────────────────────────────────────────
COLORES = {
    "integrada"              : "#1B4EA8",   # azul oscuro
    "simple"                 : "#e07820",   # naranja
    "avanzada · vertical"    : "#2ebfbf",   # teal
    "avanzada · horizontal"  : "#c0392b",   # rojo
    "avanzada · dirigida"    : "#8e44ad",   # morado
}
MARCADORES = {
    "integrada"            : "o",
    "simple"               : "s",
    "avanzada · vertical"  : "^",
    "avanzada · horizontal": "D",
    "avanzada · dirigida"  : "v",
}

# ── Carga de datos ────────────────────────────────────────────────────────────
def cargar_sesiones(archivos):
    mediciones = []
    for archivo in archivos:
        p = Path(archivo)
        if not p.exists():
            print(f"[error] No encuentro el archivo: {archivo}")
            sys.exit(1)
        with open(p, encoding="utf-8") as f:
            sesion = json.load(f)
        antena = sesion.get("antena")
        for m in sesion.get("mediciones", []):
            m["antena"] = antena
            mediciones.append(m)
    return mediciones

def agrupar(mediciones, clave):
    datos = {}
    for m in mediciones:
        k = m.get(clave)
        datos.setdefault(k, []).append(m)
    return datos

def clave_variante(m):
    """
    Devuelve la clave de variante de una medición.
    Para la antena con orientación, combina antena + orientación corta.
    Para el resto, devuelve solo el nombre de la antena.
    """
    antena = m.get("antena", "")
    if antena == ANTENA_CON_ORIENTACION:
        ori   = m.get("orientacion", "no_aplica")
        etiq  = ETIQ_ORIENTACION.get(ori, ori)
        return f"{antena} · {etiq}" if etiq else antena
    return antena

# ── Resumen estadístico ───────────────────────────────────────────────────────
def resumen_por_variante_distancia(mediciones):
    """
    Devuelve dict:
      variante → distancia → {"media", "stdev", "mediana", "n", "rep"}

    Para integrada y simple, variante == antena.
    Para 5dBi, variante == "5dBi · <orientacion_corta>".
    """
    por_variante = {}
    for m in mediciones:
        k = clave_variante(m)
        por_variante.setdefault(k, []).append(m)

    resultado = {}
    for variante, meds in por_variante.items():
        resultado[variante] = {}
        por_dist = agrupar(meds, "distancia_m")
        for dist, mlist in sorted(por_dist.items()):
            medias = [m["rssi_media"] for m in mlist]
            stdevs = [m["rssi_stdev"] for m in mlist]
            resultado[variante][dist] = {
                "media"  : round(statistics.mean(medias), 2),
                "stdev"  : round(statistics.mean(stdevs), 2),
                "mediana": round(statistics.mean([m["rssi_median"] for m in mlist]), 2),
                "n"      : sum(m["n_muestras"] for m in mlist),
                "rep"    : len(mlist),
            }
    return resultado

def rango_dinamico(tabla_antena):
    """dBm entre la distancia mínima y máxima medidas."""
    distancias = sorted(tabla_antena.keys())
    if len(distancias) < 2:
        return None
    return round(tabla_antena[distancias[0]]["media"]
                 - tabla_antena[distancias[-1]]["media"], 2)

# ── Informe de texto ──────────────────────────────────────────────────────────
SEP = "─" * 62

def generar_informe(mediciones, resumen, filepath):
    lineas = []
    lineas.append("GUIDEGUARD — INFORME DE PRUEBAS DE ANTENAS")
    lineas.append(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lineas.append(f"Total de mediciones: {len(mediciones)}")

    variantes = sorted(resumen.keys())

    # Tabla RSSI medio
    lineas.append("\n[1] RSSI MEDIO (dBm) POR VARIANTE Y DISTANCIA\n")
    distancias_todas = sorted({d for v in resumen.values() for d in v})
    ancho_v   = max(len(v) for v in variantes) + 2
    encabezado = f"{'Dist (m)':<10}" + "".join(f"{v:>{ancho_v}}" for v in variantes)
    SEP_DIN   = "─" * len(encabezado)
    lineas.append(SEP_DIN)
    lineas.append(encabezado)
    lineas.append(SEP_DIN)
    hay_ausentes = False
    for dist in distancias_todas:
        fila = f"{dist:<10.1f}"
        for v in variantes:
            val = resumen[v].get(dist, {}).get("media", None)
            if val is None:
                hay_ausentes = True
            fila += f"{val:>{ancho_v}.2f}" if val is not None else f"{'—':>{ancho_v}}"
        lineas.append(fila)
    if hay_ausentes:
        lineas.append("  — Sin medición registrada para esa combinación de variante y distancia.")

    # Tabla desviación típica
    lineas.append("\n[2] DESVIACIÓN TÍPICA (dB) — INDICADOR DE ESTABILIDAD\n")
    lineas.append(SEP_DIN)
    lineas.append(encabezado)
    lineas.append(SEP_DIN)
    for dist in distancias_todas:
        fila = f"{dist:<10.1f}"
        for v in variantes:
            val = resumen[v].get(dist, {}).get("stdev", None)
            fila += f"{val:>{ancho_v}.2f}" if val is not None else f"{'—':>{ancho_v}}"
        lineas.append(fila)

    # Rango dinámico
    sep_rd = "─" * 46
    lineas.append("\n[3] RANGO DINÁMICO (dB entre distancia mín y máx)\n")
    lineas.append(sep_rd)
    lineas.append(f"{'Variante':<28} {'Rango dinámico':>16}")
    lineas.append(sep_rd)
    for v in variantes:
        rd = rango_dinamico(resumen[v])
        lineas.append(f"{v:<28} {str(rd) + ' dB':>16}" if rd else
                      f"{v:<28} {'— (datos insuficientes)':>16}")

    # Mejor orientación por distancia (solo para la antena avanzada)
    variantes_avanzada = [v for v in variantes if v.startswith(ANTENA_CON_ORIENTACION)]
    if len(variantes_avanzada) > 1:
        lineas.append(f"\n[4] MEJOR ORIENTACIÓN POR DISTANCIA — ANTENA {ANTENA_CON_ORIENTACION}\n")
        for dist in distancias_todas:
            vals = {v: resumen[v].get(dist, {}).get("media") for v in variantes_avanzada}
            vals = {v: m for v, m in vals.items() if m is not None}
            if vals:
                mejor = max(vals, key=vals.get)
                lineas.append(f"    {dist:.1f} m  →  {mejor} ({vals[mejor]:.2f} dBm)")

    # Resumen comparativo
    lineas.append(f"\n{SEP_DIN}")
    lineas.append("[5] RESUMEN COMPARATIVO\n")
    rd_vals = {v: rango_dinamico(resumen[v]) for v in variantes if rango_dinamico(resumen[v])}
    if rd_vals:
        mejor_rd = max(rd_vals, key=rd_vals.get)
        lineas.append(f"  Mayor rango dinámico : {mejor_rd} ({rd_vals[mejor_rd]} dB)")
    stdev_media = {}
    for v in variantes:
        vals = [x["stdev"] for x in resumen[v].values() if x.get("stdev") is not None]
        if vals:
            stdev_media[v] = round(statistics.mean(vals), 2)
    if stdev_media:
        mas_estable = min(stdev_media, key=stdev_media.get)
        lineas.append(f"  Señal más estable    : {mas_estable} (stdev media {stdev_media[mas_estable]} dB)")

    lineas.append(f"\n{SEP_DIN}\n")

    texto = "\n".join(lineas)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(texto)
    print(f"[ok] Informe guardado en: {filepath}")
    return texto

# ── Gráficas ──────────────────────────────────────────────────────────────────
def grafica_stdev_por_distancia(resumen, carpeta):
    fig, ax = plt.subplots(figsize=(11, 5))

    for variante, tabla in sorted(resumen.items()):
        distancias = sorted(tabla.keys())
        stdevs     = [tabla[d]["stdev"] for d in distancias]
        color      = COLORES.get(variante, "#888")
        marcador   = MARCADORES.get(variante, "o")

        ax.plot(distancias, stdevs,
                label=variante,
                color=color, marker=marcador, linestyle="-",
                linewidth=2, markersize=7)

    ax.set_xlabel("Distancia (m)", fontsize=12)
    ax.set_ylabel("Desviación típica RSSI (dB)", fontsize=12)
    ax.set_title("Estabilidad de señal", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.text(0.5, -0.01,
             "A menor desviación típica, más estable es la señal recibida — valores bajos indican menor variabilidad del RSSI.",
             ha="center", fontsize=8, color="#666", style="italic")
    fig.tight_layout()

    out = carpeta / "estabilidad.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Gráfica guardada: {out}")

def grafica_orientaciones_5dbi(resumen, carpeta):
    """Gráfica dedicada solo a las tres orientaciones de la antena 5dBi."""
    variantes_5dbi = {v: t for v, t in resumen.items()
                      if v.startswith(ANTENA_CON_ORIENTACION)}
    if len(variantes_5dbi) < 2:
        return  # no hay nada que comparar

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    for variante, tabla in sorted(variantes_5dbi.items()):
        distancias = sorted(tabla.keys())
        medias     = [tabla[d]["media"] for d in distancias]
        stdevs     = [tabla[d]["stdev"] for d in distancias]
        color      = COLORES.get(variante, "#888")
        marcador   = MARCADORES.get(variante, "o")

        ax1.plot(distancias, medias,
                 label=variante, color=color, marker=marcador,
                 linewidth=2, markersize=7)
        ax2.plot(distancias, stdevs,
                 label=variante, color=color, marker=marcador,
                 linewidth=2, markersize=7)

    ax1.set_xlabel("Distancia (m)", fontsize=11)
    ax1.set_ylabel("RSSI medio (dBm)", fontsize=11)
    ax1.set_title("RSSI por distancia", fontsize=12, fontweight="bold")
    ax1.legend(fontsize=10)
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.invert_yaxis()

    ax2.set_xlabel("Distancia (m)", fontsize=11)
    ax2.set_ylabel("Desviación típica (dB)", fontsize=11)
    ax2.set_title("Estabilidad de señal", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=10)
    ax2.grid(True, linestyle="--", alpha=0.5)

    fig.suptitle("Comparativa de orientaciones",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.text(0.5, -0.01,
             "Izquierda: RSSI medio por orientación — valores menos negativos indican mayor potencia recibida.  "
             "Derecha: desviación típica del RSSI — menor valor indica señal más estable.",
             ha="center", fontsize=8, color="#666", style="italic")
    fig.tight_layout()

    out = carpeta / "orientaciones.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Gráfica guardada: {out}")

def grafica_boxplot_por_antena(mediciones, carpeta):
    """Boxplot por variante — máximo 3 paneles por fila."""
    por_variante = {}
    for m in mediciones:
        k = clave_variante(m)
        por_variante.setdefault(k, []).append(m)

    variantes  = sorted(por_variante.keys())
    n          = len(variantes)
    cols       = min(n, 3)
    rows       = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols,
                             figsize=(5 * cols, 5 * rows),
                             sharey=True, squeeze=False)

    for idx, variante in enumerate(variantes):
        fila = idx // cols
        col  = idx % cols
        ax   = axes[fila][col]

        meds_sorted = sorted(por_variante[variante], key=lambda m: m["distancia_m"])
        grupos      = groupby(meds_sorted, key=lambda m: m["distancia_m"])
        datos_bp    = []
        etiquetas   = []
        for dist, grupo in grupos:
            raw = []
            for m in grupo:
                raw.extend(m.get("muestras_raw", []))
            if raw:
                datos_bp.append(raw)
                etiquetas.append(f"{dist}m")

        bp = ax.boxplot(datos_bp, tick_labels=etiquetas, patch_artist=True,
                        medianprops={"color": "white", "linewidth": 2})
        color = COLORES.get(variante, "#888")
        for patch in bp["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_title(variante, fontsize=10, fontweight="bold")
        ax.set_xlabel("Distancia (m)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.4, axis="y")
        if col == 0:
            ax.set_ylabel("RSSI (dBm)", fontsize=11)

    # Ocultar ejes sobrantes si el número de variantes no llena la última fila
    for idx in range(n, rows * cols):
        axes[idx // cols][idx % cols].set_visible(False)

    fig.suptitle("RSSI por distancia",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.text(0.5, -0.01,
             "Cada caja muestra la distribución del RSSI a una distancia dada — línea blanca: mediana  ·  ○ puntos aislados: outliers (valores a más de 1.5×IQR del borde de la caja).",
             ha="center", fontsize=8, color="#666", style="italic")
    fig.tight_layout()

    out = carpeta / "distribucion.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Gráfica guardada: {out}")

def grafica_rango_dinamico(resumen, carpeta):
    variantes = sorted(resumen.keys())
    rangos    = [rango_dinamico(resumen[v]) or 0 for v in variantes]
    colores   = [COLORES.get(v, "#888") for v in variantes]

    fig, ax = plt.subplots(figsize=(max(7, 2 * len(variantes)), 4))
    bars = ax.bar(variantes, rangos, color=colores, edgecolor="white", linewidth=1.2)
    for bar, val in zip(bars, rangos):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val:.1f} dB", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax.set_ylabel("Rango dinámico (dB)", fontsize=12)
    ax.set_title("Rango dinámico", fontsize=12, fontweight="bold")
    ax.set_ylim(0, max(rangos) * 1.25 if rangos else 10)
    ax.tick_params(axis="x", labelsize=9)
    plt.xticks(rotation=15, ha="center")
    ax.grid(True, linestyle="--", alpha=0.4, axis="y")
    fig.text(0.5, -0.04,
             "Diferencia de RSSI medio entre la distancia mínima y máxima medidas — mayor rango indica mejor capacidad de discriminar la proximidad al arco.",
             ha="center", fontsize=8, color="#666", style="italic")
    fig.tight_layout()

    out = carpeta / "rango_dinamico.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] Gráfica guardada: {out}")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        directorio = Path("resultados")
        if not directorio.exists() or not list(directorio.glob("*.json")):
            print("Uso: python analisis.py resultados/*.json")
            print("     (o ejecuta sin argumentos con un directorio resultados/ poblado)")
            sys.exit(1)
        archivos = sorted(directorio.glob("*.json"))
        print(f"\n  Sin argumentos — cargando {len(archivos)} archivo(s) de resultados/\n")
    else:
        archivos = sys.argv[1:]

    mediciones = cargar_sesiones(archivos)

    if not mediciones:
        print("[error] No hay mediciones en los archivos proporcionados.")
        sys.exit(1)

    print(f"\n  Cargadas {len(mediciones)} mediciones de {len(archivos)} archivo(s).\n")

    ts      = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    carpeta = Path(f"analisis_{ts}")
    carpeta.mkdir(exist_ok=True)
    carpeta_graficas = carpeta / "graficas"
    carpeta_graficas.mkdir(exist_ok=True)

    resumen = resumen_por_variante_distancia(mediciones)

    # Informe de texto
    generar_informe(mediciones, resumen, carpeta / "informe.txt")

    # Gráficas
    if MATPLOTLIB:
        plt.rcParams.update({
            "figure.facecolor" : "white",
            "axes.facecolor"   : "#f8f9fb",
            "axes.spines.top"  : False,
            "axes.spines.right": False,
            "font.family"      : "sans-serif",
        })
        grafica_stdev_por_distancia(resumen, carpeta_graficas)
        grafica_orientaciones_5dbi(resumen, carpeta_graficas)
        grafica_boxplot_por_antena(mediciones, carpeta_graficas)
        grafica_rango_dinamico(resumen, carpeta_graficas)
        print(f"\n[ok] Todo guardado en la carpeta: {carpeta}/\n")
    else:
        print("\n[aviso] Instala matplotlib para generar gráficas: pip install matplotlib\n")

if __name__ == "__main__":
    main()