# -*- coding: utf-8 -*-
"""
Gráficos PNG con la producción 2025 (sin proyección).
Requiere: pip install pulp==2.9.0 pandas matplotlib
Ejecutar (en la misma carpeta que modelo_2025.py):  python graficos_2025.py
Crea la carpeta 'graficos_2025' con 7 imágenes.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from modelo_2025 import PARAMS_BASE, MESES, analizar, sensibilidad

AZUL, AZUL2, CELESTE, NARANJA, GRIS, ROJO, VERDE = "#1F3864", "#2E75B6", "#9DC3E6", "#ED7D31", "#A6A6A6", "#C00000", "#548235"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
SALIDA = "graficos_2025"
os.makedirs(SALIDA, exist_ok=True)

p = PARAMS_BASE
R = analizar(p)
A, TA, TE = R["A"], R["TA"], R["TE"]
iA, iTA, iTE = R["iA"], R["iTA"], R["iTE"]
tA, tTA, tTE = R["tA"], R["tTA"], R["tTE"]
zonas, alm = list(p["zonas"]), list(p["alm"])
abrev = [m[:3] for m in MESES]


def limpiar(ax):
    ax.spines[["top", "right"]].set_visible(False)


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(os.path.join(SALIDA, nombre), dpi=160, bbox_inches="tight")
    plt.close(fig)


# 1) Producción 2025 y utilización de capacidad
fig, ax = plt.subplots(figsize=(9, 4.8))
prod = R["prod"]
ax.bar(abrev, prod, color=AZUL2)
for i, v in enumerate(prod):
    ax.text(i, v + 40, f"{v:,}", ha="center", fontsize=8.5)
ax.set_ylabel("Unidades producidas"); ax.set_ylim(0, p["cap"] * 1.05); limpiar(ax)
ax.axhline(p["cap"], color=NARANJA, ls="--"); ax.text(11.4, p["cap"] + 40, f"Capacidad {p['cap']:,}", ha="right", color=NARANJA, fontsize=9)
ax2 = ax.twinx()
ut = [100 * v / p["cap"] for v in prod]
ax2.plot(abrev, ut, color=ROJO, marker="o", lw=1.5); ax2.set_ylim(0, 105); ax2.set_ylabel("% de utilización", color=ROJO)
ax2.spines[["top"]].set_visible(False)
ax.set_title(f"Producción 2025 y utilización de capacidad (total {sum(prod):,} unid, {100 * sum(prod) / (12 * p['cap']):.2f}% de utilización anual)", fontsize=10)
guardar(fig, "1_produccion_utilizacion.png")

# 2) Costo logístico mensual As-Is vs To-Be por temporada
fig, ax = plt.subplots(figsize=(10, 4.8))
t_m = R["t_meses"]
xs = range(12)
ax.bar([i - 0.2 for i in xs], t_m["Costo logístico As-Is (S/)"], 0.4, color=GRIS, label="As-Is")
ax.bar([i + 0.2 for i in xs], t_m["Costo logístico To-Be (S/)"], 0.4, color=AZUL, label="To-Be por temporada")
for i in xs:
    if t_m["Almacén abierto"][i] != "-":
        ax.text(i + 0.2, t_m["Costo logístico To-Be (S/)"][i] + 80, f"{t_m['Almacén abierto'][i]}\n-S/{t_m['Ahorro del mes (S/)'][i]:,.0f}",
                ha="center", fontsize=8, color=VERDE, fontweight="bold")
ax.set_xticks(list(xs)); ax.set_xticklabels(abrev); ax.set_ylabel("S/ por mes"); ax.set_ylim(0, max(t_m["Costo logístico As-Is (S/)"]) * 1.2)
ax.set_title("Costo logístico mensual (en verde: meses con almacén abierto y ahorro del mes)"); ax.legend(loc="upper left"); limpiar(ax)
guardar(fig, "2_costo_mensual.png")

# 3) Costo anual por componente (3 alternativas)
fig, ax = plt.subplots(figsize=(8.5, 5.2))
comp = [("Costo fijo almacenes", "fijo", AZUL), ("Taller -> almacén", "trans_pa", AZUL2),
        ("Almacén -> zona", "trans_az", CELESTE), ("Directo taller -> zona", "trans_dir", NARANJA)]
for xpos, (nombre, t_) in enumerate([("As-Is", tA), ("To-Be\ntodo el año", tTA), ("To-Be\npor temporada", tTE)]):
    base = 0
    for et, k, col in comp:
        v = t_[k]
        ax.bar(nombre, v, bottom=base, color=col, width=0.5, label=et if xpos == 0 else None)
        if v > 2500:
            ax.text(xpos, base + v / 2, f"S/ {v:,.0f}", ha="center", va="center", fontsize=8.5, color="black" if col == CELESTE else "white")
        base += v
    ax.text(xpos, base + 600, f"Total S/ {base:,.0f}", ha="center", fontweight="bold")
ax.set_ylabel("S/ por año"); ax.set_ylim(0, tA["log"] * 1.15)
ax.set_title("Costo logístico anual por componente"); ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8); limpiar(ax)
guardar(fig, "3_costo_anual_componentes.png")

# 4) Indicadores 1 y 2
fig, axs = plt.subplots(1, 2, figsize=(10, 4.8))
nombres = ["As-Is", "To-Be\ntodo el año", "To-Be\npor temporada"]
for ax, k, tit, fmt in [(axs[0], "costo_unit", "Indicador 1\nCosto logístico por unidad atendida (S/)", "S/ {:.3f}"),
                        (axs[1], "pct_ventas", "Indicador 2\nCosto logístico como % de ventas atendidas", "{:.2f}%")]:
    vals = [iA[k], iTA[k], iTE[k]]
    b = ax.bar(nombres, vals, color=[GRIS, AZUL2, AZUL], width=0.55)
    for rect, v in zip(b, vals):
        ax.text(rect.get_x() + rect.get_width() / 2, v * 1.01, fmt.format(v), ha="center", fontweight="bold", fontsize=9)
    var = (vals[2] - vals[0]) / vals[0] * 100
    ax.set_title(tit + f"\nTemporada vs As-Is: {var:.1f}%", fontsize=10)
    ax.set_ylim(0, max(vals) * 1.2); limpiar(ax)
guardar(fig, "4_indicadores.png")

# 5) Punto de equilibrio del almacén A1 mes a mes
fig, ax = plt.subplots(figsize=(9.5, 4.8))
a1 = alm[0]
fijo = p["alm"][a1][1] * p["f_fijo"]
br = R["ahorro_mes"][a1]
cols = [VERDE if b > fijo else GRIS for b in br]
ax.bar(abrev, br, color=cols)
ax.axhline(fijo, color=ROJO, ls="--", label=f"Costo fijo mensual de A1: S/ {fijo:,.0f}")
for i, (b, v) in enumerate(zip(br, prod)):
    ax.text(i, b + 25, f"{b:,.0f}", ha="center", fontsize=8.5)
    ax.text(i, 40, f"{v:,}", ha="center", fontsize=8, color="white")
ax.set_ylabel("Ahorro bruto de transporte (S/)"); ax.set_ylim(0, max(br) * 1.15); ax.legend(loc="upper left")
ax.set_title(f"¿Cuándo conviene abrir {a1}? Verde: el ahorro supera al costo fijo (número blanco = unidades del mes)", fontsize=10); limpiar(ax)
guardar(fig, "5_equilibrio_A1.png")

# 6) Red To-Be en el mes pico
tp = max(range(12), key=lambda t: TE[t]["volumen"])
mes = TE[tp]
fig, ax = plt.subplots(figsize=(9.5, 5.8)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 8)
abiertos = mes["abiertos"]
pos_t = (1.2, 4)
pos_a = {a: (5, 6.3 - i * 2.4) for i, a in enumerate(abiertos)}
pos_z = {z: (8.8, 7 - i * 2) for i, z in enumerate(zonas)}


def nodo(xy, txt, col):
    ax.add_patch(FancyBboxPatch((xy[0] - 0.9, xy[1] - 0.35), 1.8, 0.7, boxstyle="round,pad=0.05", fc=col, ec="none"))
    ax.text(xy[0], xy[1], txt, ha="center", va="center", color="white", fontsize=9, fontweight="bold")


def flecha(a, b, v, col, t):
    if v < 1:
        return
    ax.annotate("", xy=(b[0] - 0.95, b[1]), xytext=(a[0] + 0.95, a[1]),
                arrowprops=dict(arrowstyle="-|>", lw=max(0.8, min(v / 220, 5)), color=col, alpha=0.75, shrinkA=0, shrinkB=0, mutation_scale=14))
    ax.text(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t + 0.1, f"{v:,.0f}", ha="center", fontsize=8.5, color=col,
            fontweight="bold", bbox=dict(fc="white", ec="none", pad=0.8))


nodo(pos_t, "Taller\nLos Olivos", "#595959")
for a, xy in pos_a.items():
    nodo(xy, a, AZUL)
for z in zonas:
    nodo(pos_z[z], z, AZUL2)
for a, xy in pos_a.items():
    flecha(pos_t, xy, mes["x"][a], AZUL, 0.5)
    for z in zonas:
        flecha(xy, pos_z[z], mes["y"][(a, z)], AZUL, 0.62)
for z in zonas:
    flecha(pos_t, pos_z[z], mes["d"][z], NARANJA, 0.42)
ax.set_title(f"Red To-Be en {MESES[tp]} (mes pico, {mes['volumen']:,} unid): azul = vía almacén, naranja = directo", fontsize=10.5)
guardar(fig, "6_red_mes_pico.png")

# 7) Sensibilidad
sens = sensibilidad(p)
fts = sorted(sens["Transporte (x base)"].unique()); ffs = sorted(sens["Costo fijo (x base)"].unique())


def celda(a, b, col):
    return sens[(sens["Transporte (x base)"] == a) & (sens["Costo fijo (x base)"] == b)][col].iloc[0]


mat = [[celda(a, b, "Ahorro temporada %") for b in ffs] for a in fts]
fig, ax = plt.subplots(figsize=(8, 5))
im = ax.imshow(mat, cmap="Blues", aspect="auto", vmin=0)
ax.set_xticks(range(len(ffs))); ax.set_xticklabels([f"x{v}" for v in ffs])
ax.set_yticks(range(len(fts))); ax.set_yticklabels([f"x{v}" for v in fts])
for i, a in enumerate(fts):
    for j, b in enumerate(ffs):
        ax.text(j, i, f"{mat[i][j]:.1f}%\n{int(celda(a, b, 'Meses con almacén (temporada)'))} meses", ha="center", va="center",
                color="white" if mat[i][j] > 11 else "black", fontsize=8.5)
ax.set_xlabel("Costo fijo de almacenes (veces el valor base)"); ax.set_ylabel("Costo de transporte (veces el valor base)")
ax.set_title("Sensibilidad: ahorro logístico anual del To-Be por temporada\n(y meses al año con almacén abierto)")
fig.colorbar(im, label="Ahorro %")
guardar(fig, "7_sensibilidad.png")
print(f"Gráficos guardados en la carpeta '{SALIDA}'")
