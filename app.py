# app_optimizado.py
import os
#from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine
import streamlit as st
import plotly.express as px
import st_aggrid as ag

# ==== Cargar variables de entorno ====
#load_dotenv()
#DB_NAME = os.getenv("DB_NAME")
#DB_USER = os.getenv("DB_USER")
#DB_PASSWORD = os.getenv("DB_PASSWORD")
#DB_HOST = os.getenv("DB_HOST")
#DB_PORT = os.getenv("DB_PORT")

import streamlit as st
# =========================================================
# ================== STREAMLIT UI =========================
# =========================================================
st.set_page_config(layout="wide", page_title="Dashboard Chat_BIAE")
st.title("Dashboard Chat_BIAE - Retroalimentaciones Optimizado")

DB_NAME = st.secrets["DB_NAME"]
DB_USER = st.secrets["DB_USER"]
DB_PASSWORD = st.secrets["DB_PASSWORD"]
DB_HOST = st.secrets["DB_HOST"]
DB_PORT = st.secrets["DB_PORT"]

# ==== Conexión a PostgreSQL ====
DB_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

# =========================================================
# ==== Traer resultados (últimos 45 días) =================
# =========================================================
@st.cache_data(ttl=60)
def get_resultados():
    query = """
        SELECT *
        FROM ia_retroalimentaciones_tareas
        WHERE estado IN (0,1,3)
        ORDER BY fecha DESC
    """
    df = pd.read_sql(query, engine)

    df["fecha"] = pd.to_datetime(df["fecha"])
    fecha_limite = pd.Timestamp.now() - pd.Timedelta(days=45)
    df = df[df["fecha"] >= fecha_limite]

    df["username"] = df["user_id"].astype(str)
    df["firstname"] = ""
    df["lastname"] = ""

    return df

df_resultados = get_resultados()

# =========================================================
# ==== Cargar Excel de mapeo (SIN MOODLE) =================
# =========================================================
df_mapeo = pd.read_excel("mapeo_cursos_actividades.xlsx")

df_mapeo = df_mapeo.rename(columns={
    "curid": "course_id",
    "cmid": "cmid"
})

df_resultados = df_resultados.merge(
    df_mapeo,
    on=["course_id", "cmid"],
    how="left"
)

df_resultados["nombre_curso"] = df_resultados["nombre_curso"].fillna(
    df_resultados["course_id"].astype(str)
)

df_resultados["nombre_actividad"] = df_resultados["nombre_actividad"].fillna(
    df_resultados["cmid"].astype(str)
)



# ================== SIDEBAR ==============================
# ================== SIDEBAR ==============================
st.sidebar.header("Filtros")

usuarios_disponibles = sorted(
    df_resultados["username"].dropna().astype(str).unique().tolist()
)

cursos_disponibles = sorted(
    df_resultados["nombre_curso"].dropna().astype(str).unique().tolist()
)

modelos_disponibles = sorted(
    df_resultados["modelo"].dropna().astype(str).unique().tolist()
)

estados_disponibles = {
    0: "Validación",
    1: "Retroalimentado",
    3: "Validación_Previa"
}

estado_labels = list(estados_disponibles.values())

# 🔹 Filtros múltiples
usuario_sel = st.sidebar.multiselect(
    "Usuario",
    usuarios_disponibles,
    default=[]
)

curso_sel = st.sidebar.multiselect(
    "Curso",
    cursos_disponibles,
    default=[]
)

modelo_sel = st.sidebar.multiselect(
    "Modelo",
    modelos_disponibles,
    default=[]
)

estado_sel = st.sidebar.multiselect(
    "Estado",
    estado_labels,
    default=[]
)
# ================== FILTROS ==============================
df_display = df_resultados.copy()

if usuario_sel:
    df_display = df_display[df_display["username"].isin(usuario_sel)]

if curso_sel:
    df_display = df_display[df_display["nombre_curso"].isin(curso_sel)]

if modelo_sel:
    df_display = df_display[df_display["modelo"].isin(modelo_sel)]

if estado_sel:
    df_display = df_display[
        df_display["estado"].map(estados_disponibles).isin(estado_sel)
    ]

# ================== TABS =================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Tabla General",
    "Tokens por Modelo",
    "Costo por Curso",
    "Envíos por Curso",
    "Evolución por Estado",
    "Estados vs Usuarios"
])

# =========================================================
# ================= TAB 1 =================================
# =========================================================
with tab1:
    st.subheader("Tabla de resultados")

    df_tabla = df_display[[ 
        "id","username","nombre_curso","nombre_actividad",
        "modelo","total_tokens","costo_total_usd","fecha","estado"
    ]].head(2000)   # 🔥 límite
    
    ag.AgGrid(
        df_tabla,
        height=600,
        fit_columns_on_grid_load=True,
        enable_enterprise_modules=False
    )

# =========================================================
# ================= TAB 2 =================================
# =========================================================
with tab2:

    # 🔹 1) Tokens por Modelo (General)
    st.subheader("Tokens por Modelo - General")

    df_tokens_modelo = df_display.groupby("modelo")["total_tokens"].sum().reset_index()

    fig_tokens_general = px.bar(
        df_tokens_modelo,
        x="modelo",
        y="total_tokens",
        color="modelo",
        text="total_tokens",
        title="Total de Tokens por Modelo"
    )

    fig_tokens_general.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig_tokens_general.update_yaxes(tickformat=",d")

    st.plotly_chart(fig_tokens_general, use_container_width=True)

    # 🔹 2) Tokens por Modelo segmentado por Curso
    st.subheader("Tokens por Modelo y Curso")

    df_tokens_curso = df_display.groupby(
        ["nombre_curso", "modelo"]
    )["total_tokens"].sum().reset_index()

    fig_tokens_curso = px.bar(
        df_tokens_curso,
        x="modelo",
        y="total_tokens",
        color="nombre_curso",
        barmode="group",   # cambia a "stack" si lo quieres apilado
        text="total_tokens",
        title="Tokens por Modelo segmentado por Curso"
    )

    fig_tokens_curso.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
    fig_tokens_curso.update_yaxes(tickformat=",d")
    fig_tokens_curso.update_layout(legend_title="Curso")

    st.plotly_chart(fig_tokens_curso, use_container_width=True)
# =========================================================
# ================= TAB 3 =================================
# =========================================================
with tab3:
    df_cost = df_display.groupby("nombre_curso")["costo_total_usd"].sum().reset_index()

    fig_cost = px.bar(
        df_cost,
        x="nombre_curso",
        y="costo_total_usd",
        text="costo_total_usd",
        title="Costo total por Curso"
    )

    fig_cost.update_traces(texttemplate="%{text:,.2f}", textposition="outside")
    fig_cost.update_yaxes(tickformat=",.2f")

    st.plotly_chart(fig_cost, use_container_width=True)

# =========================================================
# ================= TAB 4 =================================
# =========================================================
# =========================================================
# ================= TAB 4 =================================
# =========================================================
with tab4:

    # 🔹 Filtrar solo estado 0 y 1
    df_envios = df_display[df_display["estado"].isin([0,1])].copy()

    df_envios["estado_label"] = df_envios["estado"].map({
        0: "Validación",
        1: "Retroalimentado"
    })

    # =====================================================
    # 🔹 1) ENVÍOS POR CURSO (SIN ESTADO 3)
    # =====================================================
    st.subheader("Cantidad de Envíos por Curso")

    df_envios_curso = df_envios.groupby(
        ["nombre_curso", "estado_label"]
    ).size().reset_index(name="envios")

    fig_curso = px.bar(
        df_envios_curso,
        x="nombre_curso",
        y="envios",
        color="estado_label",
        barmode="group",
        text="envios",
        title="Envíos por Curso (Validación vs Retroalimentado)"
    )

    fig_curso.update_traces(textposition="outside")
    fig_curso.update_yaxes(tickformat=",d")
    fig_curso.update_layout(legend_title="Estado")

    st.plotly_chart(fig_curso, use_container_width=True)

    # =====================================================
    # 🔹 2) ENVÍOS POR ACTIVIDAD (SIN ESTADO 3)
    # =====================================================
    st.subheader("Cantidad de Envíos por Actividad")

    df_envios_act = df_envios.groupby(
        ["nombre_actividad", "estado_label"]
    ).size().reset_index(name="envios")

    fig_act = px.bar(
        df_envios_act,
        x="nombre_actividad",
        y="envios",
        color="estado_label",
        barmode="group",
        text="envios",
        title="Envíos por Actividad (Validación vs Retroalimentado)"
    )

    fig_act.update_traces(textposition="outside")
    fig_act.update_yaxes(tickformat=",d")
    fig_act.update_layout(legend_title="Estado")

    st.plotly_chart(fig_act, use_container_width=True)

# =========================================================
# ================= TAB 5 =================================
# =========================================================
with tab5:

    df_line = df_resultados.copy()
    df_line["estado_label"] = df_line["estado"].map(estados_disponibles)
    df_line["fecha_dia"] = df_line["fecha"].dt.date

    df_line_grouped = df_line.groupby(
        ["fecha_dia","estado_label"]
    ).size().reset_index(name="count")

    fig_line = px.line(
        df_line_grouped,
        x="fecha_dia",
        y="count",
        color="estado_label",
        markers=True,
        text="count",
        title="Evolución de Envíos por Estado - Últimos 45 días"
    )

    fig_line.update_traces(textposition="top center", line=dict(width=3))
    fig_line.update_yaxes(tickformat=",d")

    st.plotly_chart(fig_line, use_container_width=True)

# =========================================================
# ================= TAB 6 =================================
# =========================================================
with tab6:

    df_line = df_resultados.copy()
    df_line["fecha_dia"] = df_line["fecha"].dt.date

    for estado_val in [0, 1]:

        st.subheader(f"Estado = {estado_val}")

        df_estado = df_line[df_line["estado"] == estado_val]

        df_group = df_estado.groupby("fecha_dia").agg(
            retroalimentaciones=("id", "count"),
            usuarios_distintos=("user_id", "nunique")
        ).reset_index()

        fig = px.line(
            df_group,
            x="fecha_dia",
            y=["retroalimentaciones", "usuarios_distintos"],
            markers=True,
            title=f"Evolución Estado {estado_val}: Retroalimentaciones vs Usuarios Distintos"
        )

        fig.update_yaxes(tickformat=",d")
        fig.update_layout(legend_title="Métrica")

        st.plotly_chart(fig, use_container_width=True)

# =========================================================
# ================= FOOTER =================================
# =========================================================
st.write("Última actualización: ", pd.Timestamp.now())
