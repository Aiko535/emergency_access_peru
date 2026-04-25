# Acceso a Emergencias en Perú — Análisis Distrital

Proyecto de análisis geoespacial que construye un **índice distrital de acceso a atención de emergencias** en Perú, integrando cuatro fuentes de datos públicos para identificar qué distritos están mejor o peor servidos en términos de disponibilidad de IPRESS, actividad asistencial y proximidad geográfica.

## ¿Qué hace este proyecto?

Combina datos de establecimientos de salud (IPRESS), producción asistencial de emergencias, centros poblados y límites distritales para responder cuatro preguntas:

1. **¿Cómo se relaciona la oferta de IPRESS con la actividad asistencial registrada?** (componentes A y B)
2. **¿Qué distritos tienen menor acceso espacial a servicios de emergencia?** (componente C)
3. **¿Qué distritos del Perú aparecen mejor o peor servidos?** (índice compuesto)
4. **¿Qué tan sensibles son los rankings al cambio de pesos?** (análisis de sensibilidad)

## Datasets utilizados

| Dataset | Fuente | Descripción |
|---|---|---|
| Límites distritales | [d2cml-ai/Data-Science-Python](https://github.com/d2cml-ai/Data-Science-Python) | Shapefile de los 1,873 distritos del Perú (EPSG:4326) |
| IPRESS | [datosabiertos.gob.pe](https://datosabiertos.gob.pe) | 20,819 establecimientos de salud con coordenadas y categoría |
| Emergencias 2025 | [datos.susalud.gob.pe](https://datos.susalud.gob.pe) | 342,753 registros de producción asistencial en emergencia |
| Centros Poblados | IGN — Instituto Geográfico Nacional | 136,587 centros poblados (proxy de distribución poblacional) |

## Limpieza y preprocesamiento (Tarea 1)

| Dataset | Crudo | Limpio | Decisiones clave |
|---|---|---|---|
| DISTRITOS | 1,873 | 1,873 | Renombrar `IDDIST → UBIGEO`; cast `int`; verificar EPSG:4326 |
| IPRESS | 20,819 | 20,793 | Drop duplicados por `Código Único`; filtrar coordenadas válidas dentro del bounding box de Perú (long: -81.5 a -68.5; lat: -18.5 a 0.5) |
| EMERGENCIAS | 342,753 | 307,703 | Drop duplicados exactos; reemplazar placeholder `NE_0001` por NaN; agrupar por (UBIGEO, IPRESS, año, mes, sexo, edad) |
| CCPP | 136,587 | 74,767 | Filtrar `FUENTE='INEI'`; excluir códigos de 9 dígitos (artefactos IGN); usar solo geometría (la columna Y tiene errores en 45% de filas) |

**Por qué 2025 y no 2024**: El archivo de 2024 estaba truncado a exactamente 250,000 registros. El de 2025 tenía mayor cobertura de IPRESS y menor tasa de placeholders.

## Construcción del índice (Tarea 3)

El índice distrital combina **tres componentes normalizados al rango [0, 1]**:

| Componente | Variable | Descripción |
|---|---|---|
| **A — Disponibilidad** | `n_ipress_emergencia / n_ccpp` | IPRESS con servicio de emergencia por centro poblado |
| **B — Actividad** | `total_atenciones / n_ccpp` | Atenciones de emergencia registradas por centro poblado |
| **C — Acceso espacial** | `1 - mean_dist_km` (normalizado) | Inverso de la distancia media del CCPP al IPRESS de emergencia más cercano |

Se usa `n_ccpp` como **proxy poblacional** dado que no se incorporó censo. Los 61 distritos con `n_ccpp = 0` se excluyen del ranking.

### Flag de "IPRESS con emergencia"

Pre-filtro: `Estado='ACTIVADO' AND Condicion='EN FUNCIONAMIENTO'`.

- **Baseline (conservador)**: Horario contiene `"EMER"` OR (Horario = `"24 HORAS"` exacto AND Tipo contiene `"CON INTERNAMIENTO"`)
- **Alternativa (permisivo)**: lo anterior OR Horario = `"24 HORAS"` solo OR Clasificación contiene `"HOSPITAL"`

### Especificaciones del índice

| Spec | Pesos (A, B, C) | Flag emergencia | Distritos válidos |
|---|---|---|---|
| Baseline | (1/3, 1/3, 1/3) | Conservador | 329 con ≥1 IPRESS emergencia |
| Alternativa | (0.25, 0.25, 0.50) | Permisivo | 467 con ≥1 IPRESS emergencia |

## Manejo de CRS (sistemas de coordenadas)

Siguiendo la convención del notebook de referencia (`docs/references/Geopandas1.ipynb`):

- **EPSG:4326 (WGS84)** — para visualización, Folium y datos crudos.
- **EPSG:32718 (UTM 18S)** — para cálculos de distancia y área en metros.
- Reproyección local en cada función (`to_metric()` y `to_wgs84()` en `src/geospatial.py`).

## Estructura del proyecto
emergency_access_peru/
├── data/
│   ├── raw/         # Datasets crudos (gitignored)
│   └── processed/   # Outputs procesados (gitignored)
├── docs/
│   └── methodology.md
├── output/
│   ├── figures/     # 11 visualizaciones (PNG + HTML)
│   └── tables/      # 3 CSVs de ranking
├── src/
│   ├── utils.py
│   ├── data_loader.py
│   ├── cleaning.py        # Tarea 1
│   ├── geospatial.py      # Tarea 2
│   ├── metrics.py         # Tarea 3
│   ├── visualization.py   # Tarea 4
│   └── mapping.py         # Tarea 5
├── run_cleaning.py
├── run_geospatial.py
├── run_metrics.py
├── run_visualization.py
├── run_mapping.py
├── app.py            # Streamlit (Tarea 6)
├── requirements.txt
└── README.md
## Instalación

```bash
git clone https://github.com/Aiko535/emergency_access_peru.git
cd emergency_access_peru
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows
pip install -r requirements.txt
```

## Reproducir el pipeline

Descargar los datos crudos en `data/raw/` (ver sección Datasets) y ejecutar **en orden**:

```bash
python run_cleaning.py       # Tarea 1: limpieza y carga
python run_geospatial.py     # Tarea 2: spatial joins
python run_metrics.py        # Tarea 3: índice + sensibilidad
python run_visualization.py  # Tarea 4: gráficos estáticos
python run_mapping.py        # Tarea 5: mapas estáticos + Folium
```

## Correr la app de Streamlit

```bash
streamlit run app.py
```

Abrir `http://localhost:8501`. La app contiene 4 pestañas: Data & Metodología, Análisis Estático, Resultados Geoespaciales y Exploración Interactiva.

## Visualizaciones generadas (Tarea 4)

Cada figura responde a una pregunta específica con justificación metodológica:

| Figura | Pregunta | Tipo y por qué | Hallazgo clave |
|---|---|---|---|
| fig01_index_distribution | P4 | KDE (no histograma — evita sesgo por bin-width) | Alternativa desplaza la media de 0.31 a 0.46 |
| fig02_top_bottom_districts | P3 | Barras horizontales (nombres largos; boxplot ocultaría unidades) | Yanahuara (Arequipa) y Chiclayo lideran; bottom dominado por Loreto |
| fig03_distance_by_department | P2 | Boxplot ordenado por mediana (revela heterogeneidad intra-departamental) | Loreto/Ucayali con dispersiones extremas (>300 km) |
| fig04_supply_vs_activity | P1 | Bubble chart con eje Y capeado al p95 + outliers como triángulos | Más IPRESS no implica más atenciones |
| fig05_rank_changes | P4 | Scatter rank-rank con diagonal (muestra dirección, no solo magnitud) | Top 20 cambiantes tienen alta proximidad pero baja oferta |
| fig06_component_heatmap | P3+P4 | Heatmap de 3 grupos × 3 componentes (compara perfiles simultáneamente) | Bottom 30 falla en A y B, no en C: el problema es de oferta, no distancia |

## Mapas (Tarea 5)

| Mapa | Descripción |
|---|---|
| map01_choropleth_baseline.png | Choropleth nacional del índice baseline (escala viridis); distritos excluidos en gris |
| map02_choropleth_comparison.png | Panel izquierdo: baseline. Panel derecho: cambio firmado de ranking (RdBu — azul mejora, rojo empeora) |
| map03_lima_ipress.png | Choropleth de Lima Metropolitana con 475 IPRESS de emergencia sobrepuestas |
| map04_interactive_national.html | Folium con choropleth + capa IPRESS clickable + LayerControl |
| map05_interactive_comparison.html | Folium con magnitud de cambio + Top 20 markers con popups |

## Hallazgos principales

1. **Los 5 distritos con menor acceso son todos de Loreto** (Yaguas, Yavari, Ramón Castilla, Teniente Manuel Clavero, Torres Causana), confirmando una brecha amazónica severa.
2. **Más IPRESS no garantiza más atenciones**: distritos con 1 IPRESS pueden tener volúmenes muy altos, mientras otros con varias IPRESS reportan poca actividad.
3. **El cambio de pesos afecta drásticamente el ranking**: 1,807 de 1,812 distritos cambian de posición, y un distrito puede moverse hasta 1,638 puestos según la especificación. Esto indica que las recomendaciones de política deben acompañarse de análisis de sensibilidad.
4. **Los rank-changers tienen un perfil específico**: alta proximidad a IPRESS (componente C) pero baja oferta y actividad — son distritos que se benefician artificialmente de pesar más la distancia.
5. **El Bottom 30 falla principalmente en disponibilidad y actividad**, no en distancia. Esto sugiere que el problema no es solo geográfico sino estructural — falta de IPRESS instaladas y operativas.

## Limitaciones

- **Distancia euclídea, no caminata real ni tiempo de viaje**: en zonas amazónicas con ríos y selva, la distancia recta subestima severamente el tiempo de acceso.
- **Subregistro probable** en zonas rurales del componente B (atenciones registradas).
- **Centros poblados como proxy poblacional**: un CCPP en Lima no equivale a uno en Loreto en términos de población.
- **Distritos sin CCPP asignado** (61 distritos) son excluidos del ranking.
- **El índice es relativo (ranking)**, no una medida absoluta de cobertura.
- **No incorpora capacidad instalada** (camas, médicos, equipamiento) — solo presencia y actividad registrada.

## Documentación adicional

Ver `docs/methodology.md` para el log completo de decisiones metodológicas por tarea.