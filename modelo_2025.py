# -*- coding: utf-8 -*-
"""
Leslie's Store - Red de distribución con la producción real de 2025 (sin proyección de demanda)
Requiere: pip install pulp==2.9.0 pandas
Ejecutar: python modelo_2025.py

Idea: el volumen de cada mes es la producción de 2025 (dato real). Se compara
  - As-Is: el taller despacha directo a cada zona.
  - To-Be "todo el año": un almacén que se paga los 12 meses.
  - To-Be "por temporada": el almacén se usa (y se paga) solo en los meses en que conviene.
Etapas: 1 datos, 2 demanda por zona, 3 As-Is, 4 To-Be, 5 comparación, 6 indicadores,
        7 punto de equilibrio por almacén, 8 sensibilidad.
Los archivos graficos_2025.py y dashboard_2025.py importan este.
"""
import copy
import os
import pulp
import pandas as pd

# ====================== 1. DATOS DE ENTRADA ======================
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
PRODUCCION_2025 = [1500, 1200, 1600, 1200, 1800, 1600, 2000, 1400, 1400, 2200, 1900, 3200]  # REAL (2025)

PARAMS_BASE = {
    # REALES (de la empresa)
    "cap": 4160,            # capacidad del taller (unid/mes)
    "precio": 30,           # precio unitario (S/); penalidad por unidad no atendida
    # SIMULADOS (supuestos del equipo)
    "f_trans": 1.0,         # multiplicador de transporte (1.0 = base)
    "f_fijo": 1.0,          # multiplicador de costos fijos de almacén (1.0 = base)
    "zonas": {"Lima Norte": 0.30, "Lima Centro": 0.30, "Lima Este": 0.25, "Lima Sur": 0.15},
    "alm": {"A1 Los Olivos": (2500, 1200),   # (capacidad unid/mes, costo fijo S/mes)
            "A2 Gamarra": (3000, 2500),
            "A3 SJL": (2000, 1500)},
    "c_pa": {"A1 Los Olivos": 0.3, "A2 Gamarra": 0.8, "A3 SJL": 1.0},   # taller -> almacén (S/unid)
    "c_az": {"A1 Los Olivos": {"Lima Norte": 0.4, "Lima Centro": 1.0, "Lima Este": 1.6, "Lima Sur": 2.2},
             "A2 Gamarra":    {"Lima Norte": 1.0, "Lima Centro": 0.4, "Lima Este": 1.0, "Lima Sur": 1.4},
             "A3 SJL":        {"Lima Norte": 1.5, "Lima Centro": 0.9, "Lima Este": 0.5, "Lima Sur": 1.3}},
    "c_dir": {"Lima Norte": 0.9, "Lima Centro": 2.0, "Lima Este": 2.8, "Lima Sur": 3.6},  # taller -> zona
}
ALT = {"asis": "As-Is", "anual": "To-Be todo el año", "estacional": "To-Be por temporada"}


# ====================== 2. DEMANDA POR ZONA ======================
def demanda_zonas(p, volumen):
    return {z: round(volumen * pct) for z, pct in p["zonas"].items()}


# ====================== MODELO ======================
def _val(v):
    x = v.value()
    return round(x, 6) if x is not None else 0.0


def resolver_anio(p, produccion, modo="estacional", abiertos_fijos=None):
    """
    modo 'asis'       : sin almacenes.
    modo 'anual'      : cada almacén se abre los 12 meses o ninguno (decisión única).
    modo 'estacional' : cada mes decide qué almacenes abrir.
    abiertos_fijos    : lista de almacenes obligados a estar abiertos todos los meses (los demás cerrados).
    """
    zonas, alm = p["zonas"], p["alm"]
    ft, ff, precio = p["f_trans"], p["f_fijo"], p["precio"]
    n = len(produccion)
    dems = [demanda_zonas(p, v) for v in produccion]
    m = pulp.LpProblem("red_2025", pulp.LpMinimize)
    ab = {(a, t): pulp.LpVariable(f"ab_{i}_{t}", cat=pulp.LpBinary) for i, a in enumerate(alm) for t in range(n)}
    anual = {a: pulp.LpVariable(f"an_{i}", cat=pulp.LpBinary) for i, a in enumerate(alm)}
    x = {(a, t): pulp.LpVariable(f"x_{i}_{t}", lowBound=0) for i, a in enumerate(alm) for t in range(n)}
    y = {(a, z, t): pulp.LpVariable(f"y_{i}_{j}_{t}", lowBound=0)
         for i, a in enumerate(alm) for j, z in enumerate(zonas) for t in range(n)}
    d = {(z, t): pulp.LpVariable(f"d_{j}_{t}", lowBound=0) for j, z in enumerate(zonas) for t in range(n)}
    f = {(z, t): pulp.LpVariable(f"f_{j}_{t}", lowBound=0) for j, z in enumerate(zonas) for t in range(n)}

    obj = []
    for t in range(n):
        obj.append(pulp.lpSum(alm[a][1] * ff * ab[(a, t)] for a in alm)
                   + pulp.lpSum(p["c_pa"][a] * ft * x[(a, t)] for a in alm)
                   + pulp.lpSum(p["c_az"][a][z] * ft * y[(a, z, t)] for a in alm for z in zonas)
                   + pulp.lpSum(p["c_dir"][z] * ft * d[(z, t)] for z in zonas)
                   + pulp.lpSum(precio * f[(z, t)] for z in zonas))
        m += pulp.lpSum(x[(a, t)] for a in alm) + pulp.lpSum(d[(z, t)] for z in zonas) <= p["cap"]
        for a in alm:
            m += pulp.lpSum(y[(a, z, t)] for z in zonas) == x[(a, t)]
            m += x[(a, t)] <= alm[a][0] * ab[(a, t)]
            if modo == "asis":
                m += ab[(a, t)] == 0
            elif modo == "anual":
                m += ab[(a, t)] == anual[a]
            if abiertos_fijos is not None:
                m += ab[(a, t)] == (1 if a in abiertos_fijos else 0)
        for z in zonas:
            m += pulp.lpSum(y[(a, z, t)] for a in alm) + d[(z, t)] + f[(z, t)] == dems[t][z]
    m += pulp.lpSum(obj)
    m.solve(pulp.PULP_CBC_CMD(msg=0))

    meses = []
    for t in range(n):
        xr = {a: _val(x[(a, t)]) for a in alm}
        yr = {(a, z): _val(y[(a, z, t)]) for a in alm for z in zonas}
        dr = {z: _val(d[(z, t)]) for z in zonas}
        fr = {z: _val(f[(z, t)]) for z in zonas}
        abiertos = [a for a in alm if ab[(a, t)].value() > 0.5]
        c = {"fijo": sum(alm[a][1] * ff for a in abiertos),
             "trans_pa": sum(p["c_pa"][a] * ft * xr[a] for a in alm),
             "trans_az": sum(p["c_az"][a][z] * ft * yr[(a, z)] for a in alm for z in zonas),
             "trans_dir": sum(p["c_dir"][z] * ft * dr[z] for z in zonas),
             "pen": precio * sum(fr.values())}
        meses.append({"t": t, "dem": dems[t], "volumen": sum(dems[t].values()), "abiertos": abiertos,
                      "x": xr, "y": yr, "d": dr, "f": fr, "costos": c})
    return meses


def totales(meses):
    tot = {k: sum(mm["costos"][k] for mm in meses) for k in ("fijo", "trans_pa", "trans_az", "trans_dir", "pen")}
    tot["trans"] = tot["trans_pa"] + tot["trans_az"] + tot["trans_dir"]
    tot["log"] = tot["fijo"] + tot["trans"]
    tot["total"] = tot["log"] + tot["pen"]
    return tot


# ====================== 6. INDICADORES ======================
def indicadores(p, meses):
    tot = totales(meses)
    atendidas = sum(mm["volumen"] - sum(mm["f"].values()) for mm in meses)
    ventas = atendidas * p["precio"]
    return {"log": tot["log"], "atendidas": atendidas, "ventas": ventas,
            "costo_unit": tot["log"] / atendidas if atendidas else 0.0,       # Indicador 1 (S/ por unidad atendida)
            "pct_ventas": 100 * tot["log"] / ventas if ventas else 0.0}       # Indicador 2 (% de ventas atendidas)


def _var(a, b):
    return round((b - a) / a * 100, 1) if a else float("nan")


# ====================== 7. PUNTO DE EQUILIBRIO ======================
def volumen_minimo(p, almacen):
    """Menor volumen mensual (unid) a partir del cual el modelo abre ese almacén. None si nunca (hasta la capacidad)."""
    def abre(v):
        return almacen in resolver_anio(p, [v], "estacional")[0]["abiertos"]
    lo, hi = 1, int(p["cap"])
    if not abre(hi):
        return None
    while lo < hi:
        mid = (lo + hi) // 2
        if abre(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo


# ====================== ANÁLISIS COMPLETO ======================
def analizar(p, produccion=None):
    produccion = list(produccion or PRODUCCION_2025)
    zonas, alm = p["zonas"], p["alm"]
    ft = p["f_trans"]
    R = {"p": p, "prod": produccion}
    A = resolver_anio(p, produccion, "asis")
    TA = resolver_anio(p, produccion, "anual")
    TE = resolver_anio(p, produccion, "estacional")
    R.update(A=A, TA=TA, TE=TE)
    iA, iTA, iTE = indicadores(p, A), indicadores(p, TA), indicadores(p, TE)
    tA, tTA, tTE = totales(A), totales(TA), totales(TE)
    R.update(iA=iA, iTA=iTA, iTE=iTE, tA=tA, tTA=tTA, tTE=tTE)

    # Producción y utilización (reproduce el cuadro del Excel de 2025)
    filas = [{"Mes": MESES[t], "Producción": produccion[t], "Capacidad": p["cap"],
              "Utilización %": round(100 * produccion[t] / p["cap"], 2)} for t in range(12)]
    filas.append({"Mes": "Total año", "Producción": sum(produccion), "Capacidad": p["cap"] * 12,
                  "Utilización %": round(100 * sum(produccion) / (p["cap"] * 12), 2)})
    R["t_produccion"] = pd.DataFrame(filas)

    # Datos de entrada simulados
    R["t_almacenes"] = pd.DataFrame([{"Almacén": a, "Capacidad (unid/mes)": c, "Costo fijo (S/mes)": round(fj * p["f_fijo"], 2),
                                      "Taller -> almacén (S/unid)": round(p["c_pa"][a] * ft, 2)} for a, (c, fj) in alm.items()])
    R["t_costos_unit"] = pd.DataFrame(
        [{"Zona": z, "% de la demanda": round(pct * 100), "Directo taller -> zona (S/unid)": round(p["c_dir"][z] * ft, 2),
          **{f"Vía {a.split()[0]} (S/unid)": round((p["c_pa"][a] + p["c_az"][a][z]) * ft, 2) for a in alm}}
         for z, pct in zonas.items()])

    # Demanda por zona y mes
    R["t_demanda"] = pd.DataFrame(
        [{"Mes": MESES[t], **{z: A[t]["dem"][z] for z in zonas}, "Total": A[t]["volumen"]} for t in range(12)]
        + [{"Mes": "Total año", **{z: sum(A[t]["dem"][z] for t in range(12)) for z in zonas},
            "Total": sum(A[t]["volumen"] for t in range(12))}])

    # As-Is por zona (anual)
    R["t_asis_zonas"] = pd.DataFrame([{
        "Zona": z, "Unidades año": sum(A[t]["d"][z] for t in range(12)),
        "Costo directo (S/unid)": round(p["c_dir"][z] * ft, 2),
        "Costo transporte año (S/)": round(sum(p["c_dir"][z] * ft * A[t]["d"][z] for t in range(12)), 2)} for z in zonas])

    # Resumen mensual As-Is vs To-Be por temporada
    filas = []
    for t in range(12):
        la = A[t]["costos"]["fijo"] + A[t]["costos"]["trans_dir"] + A[t]["costos"]["trans_pa"] + A[t]["costos"]["trans_az"]
        c = TE[t]["costos"]
        lt = c["fijo"] + c["trans_pa"] + c["trans_az"] + c["trans_dir"]
        via = sum(TE[t]["x"].values())
        vol = TE[t]["volumen"]
        filas.append({"Mes": MESES[t], "Producción": vol,
                      "Utilización %": round(100 * vol / p["cap"], 1),
                      "Almacén abierto": ", ".join(a.split()[0] for a in TE[t]["abiertos"]) or "-",
                      "Vía almacén": via, "Directo": vol - via,
                      "Costo logístico As-Is (S/)": round(la, 2), "Costo logístico To-Be (S/)": round(lt, 2),
                      "Ahorro del mes (S/)": round(la - lt, 2),
                      "Costo/unid As-Is": round(la / vol, 3) if vol else 0.0,
                      "Costo/unid To-Be": round(lt / vol, 3) if vol else 0.0})
    R["t_meses"] = pd.DataFrame(filas)

    # Flujos anuales To-Be por temporada
    filas = []
    for a in alm:
        u = sum(TE[t]["x"][a] for t in range(12))
        if u > 0.5:
            filas.append({"Tramo": "Taller -> almacén", "Origen": "Taller", "Destino": a, "Unidades año": u,
                          "Costo (S/)": round(sum(p["c_pa"][a] * ft * TE[t]["x"][a] for t in range(12)), 2)})
        for z in zonas:
            u = sum(TE[t]["y"][(a, z)] for t in range(12))
            if u > 0.5:
                filas.append({"Tramo": "Almacén -> zona", "Origen": a, "Destino": z, "Unidades año": u,
                              "Costo (S/)": round(sum(p["c_az"][a][z] * ft * TE[t]["y"][(a, z)] for t in range(12)), 2)})
    for z in zonas:
        u = sum(TE[t]["d"][z] for t in range(12))
        if u > 0.5:
            filas.append({"Tramo": "Taller -> zona (directo)", "Origen": "Taller", "Destino": z, "Unidades año": u,
                          "Costo (S/)": round(sum(p["c_dir"][z] * ft * TE[t]["d"][z] for t in range(12)), 2)})
    R["t_flujos_tobe"] = pd.DataFrame(filas)

    # Comparación anual de las tres alternativas
    def col(t_):
        return t_
    conceptos = [("Costo fijo de almacenes (S/)", "fijo"), ("Transporte (S/)", "trans"),
                 ("COSTO LOGÍSTICO (S/)", "log"), ("Penalidad por demanda no atendida (S/)", "pen"), ("COSTO TOTAL (S/)", "total")]
    filas = []
    for n_, k in conceptos:
        filas.append({"Concepto": n_, "As-Is": round(tA[k], 2), "To-Be todo el año": round(tTA[k], 2),
                      "To-Be por temporada": round(tTE[k], 2),
                      "Dif. temporada vs As-Is": round(tTE[k] - tA[k], 2), "Variación %": _var(tA[k], tTE[k])})
    filas.append({"Concepto": "Meses con almacén abierto", "As-Is": 0,
                  "To-Be todo el año": sum(1 for mm in TA if mm["abiertos"]),
                  "To-Be por temporada": sum(1 for mm in TE if mm["abiertos"]),
                  "Dif. temporada vs As-Is": sum(1 for mm in TE if mm["abiertos"]), "Variación %": float("nan")})
    R["t_comparacion"] = pd.DataFrame(filas)

    # Indicadores
    def fila(n_, k, dec=2):
        return {"Indicador": n_, "As-Is": round(iA[k], dec), "To-Be todo el año": round(iTA[k], dec),
                "To-Be por temporada": round(iTE[k], dec), "Variación temporada %": _var(iA[k], iTE[k])}
    R["t_indicadores"] = pd.DataFrame([
        fila("Costo logístico anual (S/)", "log"), fila("Unidades atendidas", "atendidas", 0),
        fila("Ventas atendidas (S/)", "ventas"),
        fila("INDICADOR 1: Costo logístico por unidad atendida (S/unid)", "costo_unit", 3),
        fila("INDICADOR 2: Costo logístico como % de ventas atendidas", "pct_ventas", 2)])

    # Punto de equilibrio por almacén (cada uno abierto todo el año, solo él)
    filas, ahorro_mes = [], {}
    for a in alm:
        S = resolver_anio(p, produccion, "estacional", abiertos_fijos=[a])
        brutos = []
        for t in range(12):
            ct = S[t]["costos"]
            trans_s = ct["trans_pa"] + ct["trans_az"] + ct["trans_dir"]
            ca_ = A[t]["costos"]
            brutos.append((ca_["trans_dir"] + ca_["trans_pa"] + ca_["trans_az"]) - trans_s)
        fijo_m = alm[a][1] * p["f_fijo"]
        ahorro_mes[a] = brutos
        vmin = volumen_minimo(p, a)
        filas.append({"Almacén": a, "Costo fijo mensual (S/)": round(fijo_m, 2),
                      "Ahorro bruto de transporte en el año (S/)": round(sum(brutos), 2),
                      "Costo fijo de 12 meses (S/)": round(fijo_m * 12, 2),
                      "Resultado neto abierto todo el año (S/)": round(sum(brutos) - fijo_m * 12, 2),
                      "Meses en que, solo, cubre su costo fijo": sum(1 for b in brutos if b > fijo_m),
                      "Volumen mensual mínimo para abrir (unid)": f"{vmin:,}" if vmin is not None else "No se abre"})
    R["t_equilibrio"] = pd.DataFrame(filas)
    R["ahorro_mes"] = ahorro_mes
    a1 = list(alm)[0]
    fijo1 = alm[a1][1] * p["f_fijo"]
    R["t_ahorro_a1"] = pd.DataFrame([{
        "Mes": MESES[t], "Producción": A[t]["volumen"], "Ahorro bruto de transporte con A1 (S/)": round(ahorro_mes[a1][t], 2),
        "Costo fijo A1 (S/)": round(fijo1, 2), "Resultado neto (S/)": round(ahorro_mes[a1][t] - fijo1, 2),
        "¿Conviene abrir?": "Sí" if ahorro_mes[a1][t] > fijo1 else "No"} for t in range(12)])
    return R


# ====================== 8. SENSIBILIDAD ======================
def sensibilidad(p_base, produccion=None, f_trans_lista=(0.8, 1.0, 1.2, 1.5), f_fijo_lista=(0.5, 0.75, 1.0, 1.5)):
    produccion = list(produccion or PRODUCCION_2025)
    filas = []
    for ft in f_trans_lista:
        for ff in f_fijo_lista:
            p = copy.deepcopy(p_base)
            p["f_trans"], p["f_fijo"] = ft, ff
            A = totales(resolver_anio(p, produccion, "asis"))
            TA = totales(resolver_anio(p, produccion, "anual"))
            TE_m = resolver_anio(p, produccion, "estacional")
            TE = totales(TE_m)
            filas.append({"Transporte (x base)": ft, "Costo fijo (x base)": ff,
                          "Meses con almacén (temporada)": sum(1 for mm in TE_m if mm["abiertos"]),
                          "Costo logístico As-Is": round(A["log"], 2), "Costo logístico To-Be temporada": round(TE["log"], 2),
                          "Ahorro temporada (S/)": round(A["log"] - TE["log"], 2),
                          "Ahorro temporada %": round(100 * (A["log"] - TE["log"]) / A["log"], 1) if A["log"] else 0.0,
                          "Ahorro almacén todo el año (S/)": round(A["log"] - TA["log"], 2)})
    return pd.DataFrame(filas)


# ====================== EXPORTAR ======================
def guardar_csv(tablas, carpeta="resultados_2025"):
    os.makedirs(carpeta, exist_ok=True)
    for nombre, df in tablas.items():
        df.to_csv(os.path.join(carpeta, nombre + ".csv"), index=False, encoding="utf-8-sig")


def _titulo(t):
    print("\n" + "=" * 80 + "\n" + t + "\n" + "=" * 80)


def _tabla(df):
    print(df.to_string(index=False))


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    R = analizar(PARAMS_BASE)
    p = PARAMS_BASE
    _titulo("1. DATOS DE ENTRADA")
    print("Reales: producción 2025 por mes, capacidad del taller (4,160/mes) y precio (S/ 30).")
    print("Simulados: reparto por zona, almacenes candidatos y costos de transporte.\n")
    _tabla(R["t_produccion"])
    print()
    _tabla(R["t_almacenes"])
    print()
    _tabla(R["t_costos_unit"])
    _titulo("2. DEMANDA MENSUAL POR ZONA (producción 2025 repartida según el % de cada zona)")
    _tabla(R["t_demanda"])
    _titulo("3. SITUACIÓN AS-IS: el taller despacha directo a cada zona")
    _tabla(R["t_asis_zonas"])
    _titulo("4. SITUACIÓN TO-BE: almacén por temporada (se usa solo en los meses en que conviene)")
    _tabla(R["t_meses"])
    print()
    _tabla(R["t_flujos_tobe"])
    _titulo("5. COMPARACIÓN ANUAL DE LAS TRES ALTERNATIVAS")
    _tabla(R["t_comparacion"])
    _titulo("6. INDICADORES")
    _tabla(R["t_indicadores"])
    iA, iTE = R["iA"], R["iTE"]
    print(f"\nLectura: el costo logístico por unidad atendida pasa de S/ {iA['costo_unit']:.3f} a S/ {iTE['costo_unit']:.3f} "
          f"({_var(iA['costo_unit'], iTE['costo_unit'])}%) y de {iA['pct_ventas']:.2f}% a {iTE['pct_ventas']:.2f}% de las ventas atendidas.")
    _titulo("7. PUNTO DE EQUILIBRIO POR ALMACÉN")
    _tabla(R["t_equilibrio"])
    print("\nNota: A3 no se abre porque A1 ahorra más en los mismos meses; A2 nunca cubre su costo fijo.")
    print("\nDetalle del almacén A1 mes a mes:")
    _tabla(R["t_ahorro_a1"])
    sens = sensibilidad(p)
    _titulo("8. ANÁLISIS DE SENSIBILIDAD")
    _tabla(sens)
    guardar_csv({"produccion": R["t_produccion"], "demanda_zonas": R["t_demanda"], "meses": R["t_meses"],
                 "flujos_tobe": R["t_flujos_tobe"], "comparacion": R["t_comparacion"],
                 "indicadores": R["t_indicadores"], "equilibrio": R["t_equilibrio"],
                 "ahorro_a1": R["t_ahorro_a1"], "sensibilidad": sens})
    print("\nTablas guardadas como CSV en la carpeta 'resultados_2025' (se abren con Excel).")
