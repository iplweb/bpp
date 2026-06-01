"""Manifest demo data: PK obiektow stworzonych przez create_demo_data."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

CLEANUP_ORDER = (
    # Najpierw M2M-through:
    "bpp.Wydawnictwo_Ciagle_Autor",
    "bpp.Wydawnictwo_Zwarte_Autor",
    # Potem rekordy. UWAGA: Wydawnictwo_Zwarte zawiera mieszane PK
    # (nadrzedne + rozdzialy). Cleanup musi usuwac w odwrotnej
    # kolejnosci PK (najpierw najwyzsze, tj. rozdzialy stworzone po
    # nadrzednych), aby zachowac FK wydawnictwo_nadrzedne. Cleanup
    # command (T14) implementuje to przez `sorted(pks, reverse=True)`.
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte",
    # Powiazania autorow:
    "bpp.Autor_Dyscyplina",
    "bpp.Autor_Jednostka",
    # Encje bazowe:
    "bpp.Autor",
    "bpp.Jednostka",
    "bpp.Wydzial",
    # Slowniki "Demo —":
    "bpp.Zrodlo",
    "bpp.Wydawca",
    # Singleton tylko jesli stworzony przez nas:
    "bpp.Uczelnia",
)


class Manifest:
    """Zapis i odczyt manifestu PK obiektow demo data.

    Append-on-batch + atomic write (`.tmp` → `os.replace`).
    """

    def __init__(
        self,
        path: Path,
        database: str,
        command_args: dict,
        *,
        created_at: str | None = None,
        objects: dict | None = None,
    ):
        self.path = Path(path)
        self.database = database
        self.command_args = dict(command_args)
        self.created_at = (
            created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        self.objects: dict[str, dict] = dict(objects or {})

    def append(self, model_label: str, pks: list[int], extra: dict | None = None):
        entry = self.objects.setdefault(model_label, {"pks": []})
        entry["pks"].extend(pks)
        if extra:
            for k, v in extra.items():
                entry[k] = v

    def objects_for(self, model_label: str) -> list[int]:
        return list(self.objects.get(model_label, {}).get("pks", []))

    def extra_for(self, model_label: str) -> dict:
        entry = self.objects.get(model_label, {})
        return {k: v for k, v in entry.items() if k != "pks"}

    def objects_in_cleanup_order(self):
        """Yielduje (model_label, pks) w kolejnosci bezpiecznego usuwania.

        Pomija bpp.Uczelnia jesli nie ma flagi `created_by_demo: True`.
        """
        for label in CLEANUP_ORDER:
            entry = self.objects.get(label)
            if not entry or not entry.get("pks"):
                continue
            if label == "bpp.Uczelnia" and not entry.get("created_by_demo"):
                continue
            yield label, list(entry["pks"])

    def save(self):
        payload = {
            "created_at": self.created_at,
            "command_args": self.command_args,
            "database": self.database,
            "objects": self.objects,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        os.replace(tmp, self.path)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = json.loads(Path(path).read_text())
        return cls(
            path=path,
            database=data["database"],
            command_args=data.get("command_args", {}),
            created_at=data.get("created_at"),
            objects=data.get("objects", {}),
        )
