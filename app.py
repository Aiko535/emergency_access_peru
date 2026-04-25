"""Streamlit app — Emergency Healthcare Access in Peru
4 tabs: Data & Methodology | Static Analysis | GeoSpatial Results | Interactive Exploration
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
from pathlib import Path
import streamlit.components.v1 as components

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Acceso a Emergencias — Perú",
    page_icon="🏥",
    layout="wide",
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent
DATA       = ROOT / "data" / "processed"
FIGS       = ROOT / "output" / "figures"

# ── Data loaders (cached) ─────────────────────────────────────────────────────
@st.cache_data
def load_baseline():
    return pd.read_parquet(DATA / "district_index_baseline.parquet")

@st.cache_data
def load_alternative():
    return pd.read_parquet(DATA / "district_index_alternative.parquet")

@st.cache_data
def load_comparison():
    return pd.read_parquet(DATA / "district_index_comparison.parquet")

@st.cache_data
def load_spatial_summary():
    return pd.read_parquet(DATA / "district_spatial_summary.parquet")

@st.cache_data
def load_distritos():
    gdf = gpd.read_file(DATA / "distritos.gpkg")
    return gdf[["UBIGEO", "DISTRITO", "PROVINCIA", "DEPARTAMEN", "geometry"]]

# ── Load data ─────────────────────────────────────────────────────────────────
baseline    = load_baseline()
alternative = load_alternative()
comparison  = load_comparison()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Data & Metodología",
    "📊 Análisis Estático",
    "🗺️ Resultados Geoespaciales",
    "🌐 Exploración Interactiva",
])

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Data & Methodology
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.title("🏥 Acceso a Emergencias en Perú — Análisis Distrital")

    st.markdown("""
    ## ¿Qué hace este proyecto?
    Este proyecto construye un **índice distrital de acceso a atención de emergencias** en Perú,
    combinando cuatro fuentes de datos públicos para identificar qué distritos están mejor o peor
    servidos en términos de disponibilidad de IPRESS, actividad asistencial y proximidad geográfica
    de los centros poblados a los establecimientos de salud.

    ## Objetivo analítico principal
    > **¿Qué distritos del Perú aparecen relativamente mejor o peor servidos en acceso a
    > emergencias sanitarias, y qué evidencia lo respalda?**
    """)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ## 📂 Fuentes de datos

        | Dataset | Fuente |
        |---|---|
        | Centros Poblados | datos.gob.pe |
        | Límites distritales (DISTRITOS.shp) | d2cml-ai / GitHub |
        | Producción asistencial en emergencia por IPRESS | susalud.gob.pe |
        | IPRESS — establecimientos de salud | datosabiertos.gob.pe |

        ## 🧹 Limpieza y preprocesamiento

        - Se eliminaron registros con coordenadas fuera del territorio peruano (lat/lon inválidas).
        - Se estandarizaron nombres de columnas a snake_case.
        - Se filtraron IPRESS sin geometría válida.
        - Los centros poblados y las IPRESS fueron asignados a distritos mediante spatial join (EPSG:4326).
        - Distritos sin centros poblados asignados fueron excluidos del índice (aparecen como "Sin datos").
        - Los datos de producción asistencial fueron agrupados por IPRESS y luego por distrito.
        """)

    with col2:
        st.markdown("""
        ## 📐 Construcción del índice

        El índice combina **tres componentes** normalizados al rango [0, 1]:

        | Componente | Variable | Descripción |
        |---|---|---|
        | **A — Disponibilidad** | `n_ipress_emergencia` / `n_ccpp` | IPRESS de emergencia por centro poblado en el distrito |
        | **B — Actividad** | `total_atenciones` / `n_ccpp` | Atenciones de emergencia registradas por centro poblado |
        | **C — Acceso espacial** | `1 − mean_dist_km` (norm.) | Inverso de la distancia media del CCPP al IPRESS más cercano |

        ### Especificación baseline
        Índice = (1/3)·A + (1/3)·B + (1/3)·C
        ### Especificación alternativa
        Índice = (0.25)·A + (0.25)·B + (0.50)·C
        La alternativa pondera el doble el componente espacial, priorizando la accesibilidad
        geográfica sobre la oferta y la actividad registrada.

        ## ⚠️ Limitaciones principales

        - La distancia es euclídea (en grados), no caminata ni tiempo de viaje real.
        - Los datos de producción asistencial pueden tener subregistro en zonas rurales.
        - Distritos sin ningún CCPP asignado (geometría muy pequeña) son excluidos.
        - El índice es relativo (ranking), no una medida absoluta de cobertura.
        """)

    st.divider()
    st.markdown("## 📊 Resumen estadístico — Índice baseline")

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Distritos analizados", f"{len(baseline):,}")
    col_b.metric("Media del índice", f"{baseline['index'].mean():.3f}")
    col_c.metric("Índice máximo", f"{baseline['index'].max():.3f}")
    col_d.metric("Índice mínimo", f"{baseline['index'].min():.3f}")

    st.dataframe(
        baseline[["UBIGEO", "n_ccpp", "n_ipress_emergencia",
                  "A_norm", "B_norm", "C_norm_inverted", "index", "rank"]]
        .sort_values("rank")
        .rename(columns={
            "n_ccpp": "N° CCPP",
            "n_ipress_emergencia": "N° IPRESS emerg.",
            "A_norm": "Comp. A",
            "B_norm": "Comp. B",
            "C_norm_inverted": "Comp. C",
            "index": "Índice",
            "rank": "Ranking",
        }),
        use_container_width=True,
        height=350,
    )

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Static Analysis
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.title("📊 Análisis Estático")

    # fig01
    st.markdown("### Fig. 1 — Distribución del índice: baseline vs alternativa")
    st.image(str(FIGS / "fig01_index_distribution.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Permite ver si ambas especificaciones producen distribuciones similares
    o si el cambio de pesos desplaza sistemáticamente los valores.
    **¿Por qué KDE?** Muestra la forma completa de la distribución (asimetría, modas) mejor que
    un histograma con bins arbitrarios. Una distribución muy sesgada a la izquierda evidencia que
    la mayoría de distritos tiene acceso bajo.
    **Hallazgo:** La alternativa desplaza la media de 0.31 a 0.46, reflejando que al ponderar más
    el componente C (acceso espacial), los distritos con cercanía a IPRESS suben notoriamente.
    """)

    st.divider()

    # fig02
    st.markdown("### Fig. 2 — Top 15 y Bottom 15 distritos (baseline)")
    st.image(str(FIGS / "fig02_top_bottom_districts.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Identifica los distritos con mayor y menor acceso (Pregunta 3).
    **¿Por qué barras horizontales?** Los nombres de distritos son largos; las barras horizontales
    evitan rotación de etiquetas y facilitan la lectura comparativa. Un boxplot no identificaría
    unidades individuales.
    **Hallazgo:** Yanahuara (Arequipa) y Chiclayo lideran. Los 15 peores son casi todos de Loreto,
    evidenciando la brecha amazónica.
    """)

    st.divider()

    # fig03
    st.markdown("### Fig. 3 — Distancia media al IPRESS más cercano por departamento")
    st.image(str(FIGS / "fig03_distance_by_department.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Responde la Pregunta 2: qué distritos tienen centros poblados con menor
    acceso espacial a servicios de emergencia.
    **¿Por qué boxplot?** Muestra la dispersión intra-departamental, no solo la media. Loreto
    tiene una distribución amplísima, indicando heterogeneidad interna severa. Un gráfico de barras
    con solo la media ocultaría esa variabilidad.
    **Hallazgo:** Loreto tiene distritos con distancias superiores a 300 km al IPRESS más cercano.
    """)

    st.divider()

    # fig04
    st.markdown("### Fig. 4 — Oferta de IPRESS vs actividad registrada")
    st.image(str(FIGS / "fig04_supply_vs_activity.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Responde la Pregunta 1: relación entre disponibilidad de IPRESS y actividad
    asistencial (componentes A y B).
    **¿Por qué bubble chart?** Tres dimensiones en un solo gráfico: N° IPRESS (eje X), atenciones
    (eje Y), N° CCPP (tamaño burbuja) y el índice (color). Un scatter simple perdería la dimensión
    del tamaño poblacional del distrito.
    **Hallazgo:** No siempre más IPRESS implica más atenciones; hay distritos con 1 IPRESS y
    volúmenes muy altos, y otros con varios IPRESS y poca actividad registrada.
    """)

    st.divider()

    # fig05
    st.markdown("### Fig. 5 — Cambio de rango entre especificaciones")
    st.image(str(FIGS / "fig05_rank_changes.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Responde la Pregunta 4 (sensibilidad metodológica): qué distritos cambian
    más de posición al cambiar los pesos.
    **¿Por qué scatter rank-rank?** La diagonal de 45° es la referencia de "sin cambio". Los puntos
    alejados de ella son los más sensibles. Un gráfico de barras del cambio absoluto no mostraría
    la dirección (mejoran o empeoran).
    **Hallazgo:** Los Top 20 mayores cambios (naranja) son distritos que mejoran notoriamente con
    la alternativa, es decir, tienen buena proximidad espacial pero poca oferta o actividad.
    """)

    st.divider()

    # fig06
    st.markdown("### Fig. 6 — Heatmap de componentes por grupo de distritos")
    st.image(str(FIGS / "fig06_component_heatmap.png"), use_container_width=True)
    st.markdown("""
    **¿Qué responde?** Permite entender qué componente explica el buen o mal desempeño de cada
    grupo (Top 30, Top 20 cambiantes, Bottom 30).
    **¿Por qué heatmap?** Permite comparar patrones de componentes entre muchos distritos
    simultáneamente. Un gráfico de barras agrupado con 80 distritos sería ilegible.
    **Hallazgo:** El Bottom 30 falla principalmente en componentes A y B (poca oferta y actividad),
    no necesariamente en C, lo que sugiere que el problema es de oferta, no solo de distancia.
    """)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — GeoSpatial Results
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.title("🗺️ Resultados Geoespaciales")

    st.markdown("### Mapa 1 — Índice de acceso nacional (baseline, quintiles)")
    st.image(str(FIGS / "map01_choropleth_national.png"), use_container_width=True)
    st.markdown("""
    Choropleth nacional clasificado en quintiles. Los distritos más oscuros (rojo intenso)
    concentran el mejor acceso: costa norte y algunas capitales de provincia. La Amazonía
    (Loreto, Ucayali) domina los quintiles inferiores.
    """)

    st.divider()

    st.markdown("### Mapa 2 — Comparación baseline vs alternativa")
    st.image(str(FIGS / "map02_choropleth_comparison.png"), use_container_width=True)
    st.markdown("""
    Al dar mayor peso al acceso espacial (alternativa), los distritos costeros con IPRESS
    cercanos mejoran su posición relativa, mientras que distritos amazónicos con algo de oferta
    pero muy lejanos descienden. La escala de color es compartida entre ambos paneles para
    permitir comparación directa.
    """)

    st.divider()

    st.markdown("### Mapa 3 — Lima Metropolitana con IPRESS de emergencia")
    st.image(str(FIGS / "map03_lima_ipress.png"), use_container_width=True)
    st.markdown("""
    Zoom sobre Lima Metropolitana. Los puntos azules son IPRESS con servicio de emergencia.
    Se aprecia concentración de IPRESS en el centro histórico y distritos centrales, mientras
    que distritos periféricos tienen menor índice pese a tener algunos establecimientos.
    """)

    st.divider()

    st.markdown("### Tabla — Top 20 distritos mejor y peor servidos")

    col_left, col_right = st.columns(2)

    top20 = (baseline.nsmallest(20, "rank")
             [["UBIGEO", "rank", "index", "n_ipress_emergencia", "mean_dist_km"]]
             .rename(columns={"rank": "Ranking", "index": "Índice",
                               "n_ipress_emergencia": "IPRESS emerg.",
                               "mean_dist_km": "Dist. media (km)"}))

    bot20 = (baseline.nlargest(20, "rank")
             [["UBIGEO", "rank", "index", "n_ipress_emergencia", "mean_dist_km"]]
             .rename(columns={"rank": "Ranking", "index": "Índice",
                               "n_ipress_emergencia": "IPRESS emerg.",
                               "mean_dist_km": "Dist. media (km)"}))

    with col_left:
        st.markdown("**🟢 Top 20 — Mayor acceso**")
        st.dataframe(top20, use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("**🔴 Bottom 20 — Menor acceso**")
        st.dataframe(bot20, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Interactive Exploration
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.title("🌐 Exploración Interactiva")

    st.markdown("### Mapa 4 — Índice nacional interactivo (baseline)")
    st.markdown("Haz clic en cualquier distrito para ver su nombre, índice y ranking. "
                "Los marcadores agrupados representan IPRESS con servicio de emergencia.")

    map04_path = FIGS / "map04_interactive_national.html"
    if map04_path.exists():
        with open(map04_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=600, scrolling=False)
    else:
        st.warning("map04_interactive_national.html no encontrado. Corre run_mapping.py primero.")

    st.divider()

    st.markdown("### Mapa 5 — Cambio de ranking baseline vs alternativa")
    st.markdown("Los círculos rojos marcan los **Top 20 distritos con mayor cambio de ranking** "
                "entre especificaciones. El choropleth muestra la magnitud del cambio absoluto "
                "en quintiles.")

    map05_path = FIGS / "map05_interactive_comparison.html"
    if map05_path.exists():
        with open(map05_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=600, scrolling=False)
    else:
        st.warning("map05_interactive_comparison.html no encontrado. Corre run_mapping.py primero.")

    st.divider()

    st.markdown("### 🔍 Busca un distrito")
    search = st.text_input("Ingresa UBIGEO o parte del nombre (usa la tabla de Tab 3):")

    if search:
        mask = baseline["UBIGEO"].astype(str).str.contains(search, case=False)
        result = baseline[mask][["UBIGEO", "index", "rank",
                                  "n_ipress_emergencia", "mean_dist_km",
                                  "A_norm", "B_norm", "C_norm_inverted"]]
        if result.empty:
            st.info("No se encontraron resultados.")
        else:
            st.dataframe(
                result.rename(columns={
                    "index": "Índice", "rank": "Ranking",
                    "n_ipress_emergencia": "IPRESS emerg.",
                    "mean_dist_km": "Dist. media (km)",
                    "A_norm": "Comp. A", "B_norm": "Comp. B",
                    "C_norm_inverted": "Comp. C",
                }),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.markdown("### 📊 Comparación baseline vs alternativa por UBIGEO")
    if comparison is not None and not comparison.empty:
        st.dataframe(
            comparison.sort_values("rank_change_abs", ascending=False)
            .head(50)
            .rename(columns={
                "index_baseline": "Índice baseline",
                "index_alt": "Índice alt.",
                "rank_baseline": "Rank baseline",
                "rank_alt": "Rank alt.",
                "rank_change_abs": "Δ Rank (abs)",
            }),
            use_container_width=True,
            hide_index=True,
        )