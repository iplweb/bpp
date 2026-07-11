"""Generyczny czytnik tabeli ``records`` z bazy ppm_harvester.

Niezależny od typu rekordu — filtruje po kolumnie ``type``. Konkretne
mapowanie ``parsed`` → model BPP robią handlery (``handlers/``).
"""

import json
import sqlite3
import warnings
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class RawRecord:
    source_id: str
    source_url: str
    parsed: dict


def iter_records(sqlite_path: str, typ: str) -> Iterator[RawRecord]:
    """Iteruj rekordy danego ``typ`` z tabeli ``records``.

    Rekordy z pustym/niepoprawnym ``parsed_json`` są pomijane z ostrzeżeniem
    (nie przerywają importu). Kolejność: jak w bazie (bez ORDER BY).
    """
    con = sqlite3.connect(sqlite_path)
    try:
        cur = con.execute(
            "SELECT source_id, source_url, parsed_json FROM records WHERE type = ?",
            (typ,),
        )
        for source_id, source_url, parsed_json in cur:
            if not parsed_json:
                warnings.warn(f"Pusty parsed_json dla {source_id}", stacklevel=2)
                continue
            try:
                parsed = json.loads(parsed_json)
            except json.JSONDecodeError:
                warnings.warn(f"Niepoprawny parsed_json dla {source_id}", stacklevel=2)
                continue
            yield RawRecord(source_id or "", source_url or "", parsed)
    finally:
        con.close()
