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