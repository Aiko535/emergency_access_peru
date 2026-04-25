"""Utility helpers shared across the pipeline."""

import os
import chardet


def detect_encoding(path: str) -> str:
    """Detect the character encoding of a file using chardet.

    Reads the full file in binary mode and returns the encoding string
    (e.g. 'latin-1', 'utf-8') detected by chardet.
    """
    with open(path, "rb") as f:
        raw = f.read()
    return chardet.detect(raw)["encoding"]


def ensure_dir(path: str) -> None:
    """Create *path* (and any missing parents) if it does not exist."""
    os.makedirs(path, exist_ok=True)
