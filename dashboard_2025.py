# -*- coding: utf-8 -*-
"""
Dashboard interactivo con la producción 2025 (sin proyección) - Leslie's Store
Requiere: pip install pulp==2.9.0 pandas plotly streamlit
Ejecutar (en la misma carpeta que modelo_2025.py):
    python -m streamlit run dashboard_2025.py
"""
import copy
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from modelo_2025 import PARAMS_BASE, PRODUCCION_2025, MESES, analizar, sensibilidad

AZUL, AZUL2, CELESTE, NARANJA, GRIS, ROJO, VERDE = "#1F3864", "#2E75B6", "#9DC3E6", "#ED7D31", "#A6A6A6", "#C00000", "#548235"

st.set_page_config(page_title="Leslie's Store - Producción 2025", layout="wide")
st.title("Leslie's Store - Red de distribución con la producción 2025")
st.caption("Reales: producción 2025 por mes, capacidad del taller y precio. Simulados: reparto por zona, almacenes y costos de transporte.")

# ---------------- Parámetros ----------------
st.sidebar.header("Parámetros")
p = copy.deepcopy(PARAMS_BASE)
p["cap"] = st.sidebar.slider("Capacidad del taller (unid/mes)", 1000, 9000, PARAMS_BASE["cap"], 40)
p["precio"] = st.sidebar.slider("Precio / penalidad por unidad no atendida (S/)", 5, 60, PARAMS_BASE["precio"])
p["f_trans"] = st.sidebar.slider("Costos de transporte (% del base)", 50, 200, 100) / 100
p["f_fijo"] = st.sidebar.slider("Costos fijos de almacenes (% del base)", 50, 300, 100) / 100
st.sidebar.caption("Los valores por defecto son los del trabajo. Para cambiar la producción de algún mes, usa la pestaña 'Producción 2025'.")

# Producción editable (por defecto, la real de 2025)
if "prod_df" not in st.session_state:
    st.session_state["prod_df"] = pd.DataFrame({"Mes": MESES, "Producción": PRODUCCION_2025})


@st.cache_data
def calcular(p, prod):
    return analizar(p, list(prod))


@st.cache_data
def calcular_sens(p, prod):
    return sensibilidad(p, list(prod))


tabs = st.tabs(["Resumen", "Producción 2025", "As-Is", "To-Be", "Comparación e indicadores", "Punto de equilibrio", "Sensibilidad"])

# ---------------- Producción 2025 (editable) ----------------
with tabs[1]:
    st.subheader("Producción 2025 por mes")
    st.caption("Puedes editar los valores para probar otros volúmenes. Para volver a los reales, recarga la página.")
    editado = st.data_editor(st.session_state["prod_df"], hide_index=True, disabled=["Mes"], key="editor")
prod = tuple(int(v) for v in editado["Producción"])

R = calcular(p, prod)
A, TA, TE = R["A"], R["TA"], R["TE"]
iA, iTA, iTE, tA, tTE = R["iA"], R["iTA"], R["iTE"], R["tA"], R["tTE"]
zonas, alm = list(p["zonas"]), list(p["alm"])
meses_alm = sum(1 for m in TE if m["abiertos"])

with tabs[1]:
    st.dataframe(R["t_produccion"], hide_index=True)
    fig = go.Figure()
    fig.add_bar(x=MESES, y=R["prod"], marker_color=AZUL2, name="Producción")
    fig.add_scatter(x=MESES, y=[100 * v / p["cap"] for v in R["prod"]], name="% utilización", yaxis="y2", line=dict(color=ROJO))
    fig.update_layout(title="Producción y utilización de capacidad", height=380,
                      yaxis2=dict(overlaying="y", side="right", range=[0, 110], title="% utilización"))
    st.plotly_chart(fig)

# ---------------- Resumen ----------------
with tabs[0]:
    k = st.columns(5)
    k[0].metric("Costo logístico As-Is (año)", f"S/ {tA['log']:,.0f}")
    k[1].metric("Costo logístico To-Be (temporada)", f"S/ {tTE['log']:,.0f}", f"{tTE['log'] - tA['log']:,.0f}", delta_color="inverse")
    k[2].metric("Indicador 1: costo por unidad", f"S/ {iTE['costo_unit']:.3f}", f"{iTE['costo_unit'] - iA['costo_unit']:.3f}", delta_color="inverse")
    k[3].metric("Indicador 2: % de ventas", f"{iTE['pct_ventas']:.2f}%", f"{iTE['pct_ventas'] - iA['pct_ventas']:.2f} pts", delta_color="inverse")
    k[4].metric("Meses con almacén", f"{meses_alm} de 12")
    dem_no = sum(sum(m["f"].values()) for m in TE)
    st.write(f"**Producción 2025:** {sum(R['prod']):,} unid · **Utilización anual:** {100 * sum(R['prod']) / (12 * p['cap']):.2f}% · "
             f"**Demanda no atendida:** {dem_no:,.0f} unid")
    if meses_alm == 0:
        st.info("Con estos parámetros el modelo no abre ningún almacén: el ahorro de transporte no cubre el costo fijo en ningún mes.")
    else:
        st.write("**Meses con almacén abierto:** " + ", ".join(MESES[m["t"]] for m in TE if m["abiertos"]))
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        for et, kk, col in [("Costo fijo almacenes", "fijo", AZUL), ("Taller -> almacén", "trans_pa", AZUL2),
                            ("Almacén -> zona", "trans_az", CELESTE), ("Directo taller -> zona", "trans_dir", NARANJA)]:
            fig.add_bar(name=et, x=["As-Is", "To-Be todo el año", "To-Be por temporada"], y=[tA[kk], R["tTA"][kk], tTE[kk]], marker_color=col)
        fig.update_layout(barmode="stack", title="Costo logístico anual por componente (S/)", height=380)
        st.plotly_chart(fig)
    with c2:
        tm = R["t_meses"]
        fig = go.Figure()
        fig.add_bar(name="As-Is", x=MESES, y=tm["Costo logístico As-Is (S/)"], marker_color=GRIS)
        fig.add_bar(name="To-Be por temporada", x=MESES, y=tm["Costo logístico To-Be (S/)"], marker_color=AZUL)
        fig.update_layout(barmode="group", title="Costo logístico mensual (S/)", height=380)
        st.plotly_chart(fig)

# ---------------- As-Is ----------------
with tabs[2]:
    st.subheader("As-Is: el taller despacha directo a cada zona")
    st.write("**Demanda mensual por zona**")
    st.dataframe(R["t_demanda"], hide_index=True)
    st.write("**Costo por zona en el año**")
    st.dataframe(R["t_asis_zonas"], hide_index=True)

# ---------------- To-Be ----------------
with tabs[3]:
    st.subheader("To-Be: almacén por temporada")
    st.caption("El almacén se usa y se paga solo en los meses en que el ahorro de transporte supera su costo fijo.")
    st.dataframe(R["t_meses"], hide_index=True)
    st.write("**Flujos del año**")
    st.dataframe(R["t_flujos_tobe"], hide_index=True)
    nodos = ["Taller"] + alm + zonas + ["No atendida"]
    idx = {n: i for i, n in enumerate(nodos)}
    src, dst, val = [], [], []
    acum = {}
    for m in TE:
        for a in alm:
            acum[("Taller", a)] = acum.get(("Taller", a), 0) + m["x"][a]
            for z in zonas:
                acum[(a, z)] = acum.get((a, z), 0) + m["y"][(a, z)]
        for z in zonas:
            acum[("Taller", z)] = acum.get(("Taller", z), 0) + m["d"][z]
            acum[(z, "No atendida")] = acum.get((z, "No atendida"), 0) + m["f"][z]
    for (o, d_), v in acum.items():
        if v > 0.5:
            src.append(idx[o]); dst.append(idx[d_]); val.append(v)
    fig = go.Figure(go.Sankey(node=dict(label=nodos, pad=18, thickness=18), link=dict(source=src, target=dst, value=val)))
    fig.update_layout(title="Red To-Be por temporada: unidades del año", height=420)
    st.plotly_chart(fig)

# ---------------- Comparación e indicadores ----------------
with tabs[4]:
    st.subheader("Comparación anual de las tres alternativas")
    st.dataframe(R["t_comparacion"], hide_index=True)
    st.subheader("Indicadores")
    st.dataframe(R["t_indicadores"], hide_index=True)
    c1, c2 = st.columns(2)
    nombres = ["As-Is", "To-Be todo el año", "To-Be por temporada"]
    for col, kk, tit, fmt in [(c1, "costo_unit", "Indicador 1: costo logístico por unidad atendida (S/)", "S/ %.3f"),
                              (c2, "pct_ventas", "Indicador 2: costo logístico como % de ventas atendidas", "%.2f%%")]:
        with col:
            vals = [iA[kk], iTA[kk], iTE[kk]]
            fig = go.Figure(go.Bar(x=nombres, y=vals, marker_color=[GRIS, AZUL2, AZUL], text=[fmt % v for v in vals], textposition="outside"))
            fig.update_layout(title=tit, height=360, yaxis_range=[0, max(vals) * 1.25 if max(vals) else 1])
            st.plotly_chart(fig)
    st.caption("Indicador 1 = costo logístico (fijo + transporte) ÷ unidades atendidas. Indicador 2 = costo logístico ÷ (unidades atendidas × precio).")

# ---------------- Punto de equilibrio ----------------
with tabs[5]:
    st.subheader("¿Cuándo conviene abrir un almacén?")
    st.dataframe(R["t_equilibrio"], hide_index=True)
    st.caption("A3 no se abre aunque cubra su costo fijo en algún mes, porque A1 ahorra más en esos mismos meses. "
               "Volumen mínimo = menor producción mensual a partir de la cual el modelo abre ese almacén.")
    a1 = alm[0]
    fijo = p["alm"][a1][1] * p["f_fijo"]
    br = R["ahorro_mes"][a1]
    fig = go.Figure(go.Bar(x=MESES, y=br, marker_color=[VERDE if b > fijo else GRIS for b in br],
                           text=[f"{b:,.0f}" for b in br], textposition="outside", name="Ahorro bruto de transporte"))
    fig.add_hline(y=fijo, line_dash="dash", line_color=ROJO, annotation_text=f"Costo fijo mensual de {a1}: S/ {fijo:,.0f}")
    fig.update_layout(title=f"Ahorro bruto de transporte con {a1} abierto (verde = supera el costo fijo)", height=420)
    st.plotly_chart(fig)
    st.dataframe(R["t_ahorro_a1"], hide_index=True)

# ---------------- Sensibilidad ----------------
with tabs[6]:
    st.subheader("Sensibilidad: transporte y costo fijo respecto al valor base")
    sens = calcular_sens(p, prod)
    st.dataframe(sens, hide_index=True)
    fts = sorted(sens["Transporte (x base)"].unique()); ffs = sorted(sens["Costo fijo (x base)"].unique())

    def celda(a, b, c):
        return sens[(sens["Transporte (x base)"] == a) & (sens["Costo fijo (x base)"] == b)][c].iloc[0]

    z = [[celda(a, b, "Ahorro temporada %") for b in ffs] for a in fts]
    txt = [[f"{z[i][j]:.1f}%<br>{int(celda(a, b, 'Meses con almacén (temporada)'))} meses" for j, b in enumerate(ffs)] for i, a in enumerate(fts)]
    fig = go.Figure(go.Heatmap(z=z, x=[f"x{v}" for v in ffs], y=[f"x{v}" for v in fts], text=txt, texttemplate="%{text}",
                               colorscale="Blues", colorbar=dict(title="Ahorro %")))
    fig.update_layout(title="Ahorro logístico anual del To-Be por temporada (y meses con almacén)", height=420,
                      xaxis_title="Costo fijo de almacenes (veces el base)", yaxis_title="Transporte (veces el base)")
    st.plotly_chart(fig)
