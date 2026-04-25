"""Raw dataset loaders — read only, no cleaning applied."""

import pandas as pd
import geopandas as gpd

from src.utils import detect_encoding


def load_distritos(path: str = "data/raw/distritos/DISTRITOS.shp") -> gpd.GeoDataFrame:
    """Load the district boundaries shapefile.

    Returns a GeoDataFrame with one row per district (1,873 expected),
    CRS as stored in the file (EPSG:4326).
    """
    return gpd.read_file(path)


def load_ipress(path: str = "data/raw/ipress/ipress.csv") -> pd.DataFrame:
    """Load the MINSA-IPRESS health facilities catalogue.

    Uses chardet to detect encoding. Separator is comma.
    Returns a DataFrame with 20,819 rows and 33 columns as published.
    """
    enc = detect_encoding(path)
    return pd.read_csv(path, sep=",", encoding=enc)


def load_emergencias(
    path: str = "data/raw/emergencias/emergencias_2025.csv",
) -> pd.DataFrame:
    """Load the SUSALUD emergency-care production dataset (2025).

    Uses chardet to detect encoding. Separator is semicolon.
    Returns a DataFrame with 342,753 rows and 14 columns as published.
    """
    enc = detect_encoding(path)
    return pd.read_csv(path, sep=";", encoding=enc)


def load_ccpp(
    path: str = "data/raw/centros_poblados/CCPP_IGN100K.shp",
) -> gpd.GeoDataFrame:
    """Load the IGN populated-centers shapefile.

    Returns a GeoDataFrame with 136,587 Point features,
    CRS as stored in the file (EPSG:4326).
    """
    return gpd.read_file(path)
