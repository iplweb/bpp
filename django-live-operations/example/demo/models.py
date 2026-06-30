"""
DemoImport — a concrete LiveOperation that simulates a 5-stage file import.

Each stage does a short time.sleep loop so the browser demo shows live progress.
"""
import time

from live_operations.models import LiveOperation

_STAGE_ITEMS = {
    "Wczytanie": 20,
    "Walidacja": 30,
    "Dopasowanie": 25,
    "Zapis": 40,
    "Raport": 5,
}


class DemoImport(LiveOperation):
    stages = ["Wczytanie", "Walidacja", "Dopasowanie", "Zapis", "Raport"]

    class Meta:
        app_label = "demo"

    def run(self, p):
        total_items = sum(_STAGE_ITEMS.values())
        ok = 0
        skipped = 0
        errors = 0

        for stage_name in self.stages:
            count = _STAGE_ITEMS[stage_name]
            with p.stage(stage_name):
                p.status(f"Etap: {stage_name}", level="info")
                for i in p.track(range(count), total=count, label=stage_name):
                    time.sleep(0.05)
                    if i % 7 == 0:
                        skipped += 1
                        p.log(f"[{stage_name}] pominięto rekord {i}")
                    elif i % 11 == 0:
                        errors += 1
                        p.log(f"[{stage_name}] błąd rekordu {i}")
                    else:
                        ok += 1

        p.result(
            {
                "total": total_items,
                "ok": ok,
                "skipped": skipped,
                "errors": errors,
            }
        )
