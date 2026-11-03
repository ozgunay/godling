"""Godling's own files, written whole: a copy taken while one is being written (the backups, ADR-018) or a crash in
the middle never finds it half written. The new text goes to a file beside it, which then takes its place."""
import os
from pathlib import Path


def write_atomic(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)
