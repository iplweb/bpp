"""Top-level orkiestracja create_demo_data — sklada generatory razem."""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from pathlib import Path

from django.db import connection

from bpp.demo_data.confirm import ConfirmAborted, double_confirm
from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.dyscypliny import create_autor_dyscypliny
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.wydawnictwa_ciagle import create_wc
from bpp.demo_data.generators.wydawnictwa_zwarte import create_wz
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.preflight import check_required


@dataclass
class CreateOptions:
    wydzialow: int
    jednostek_na_wydzial: int
    autorow: int
    ile_ciaglych: int
    ile_zwartych: int
    od_roku: int
    do_roku: int
    procent_z_dyscyplina: int
    procent_z_subdyscyplina: int
    procent_zmiana_dyscypliny: int
    zrodel: int
    wydawcow: int
    seed: int | None
    manifest_out: Path
    batch_size: int
    yes_i_am_sure: bool
    confirm_db: str | None
    disable_progress: bool = False


def run_create(opts: CreateOptions, *, stdin=None, stdout=None):
    """Main orchestration entrypoint.

    1. Preflight check (BEFORE confirm) — slowniki musza istniec.
    2. Double-confirm (po preflight, zeby nie pytac usera o cos
       co i tak sie nie wykona).
    3. Manifest + RNG init.
    4. Generatory w sztywnej kolejnosci dependency: uczelnia → wydzialy →
       jednostki → autorzy → dyscypliny → zrodla → wydawcy → WC → WZ.
    5. Manifest save + summary do stdout.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    db_name = connection.settings_dict["NAME"]

    # 1. Preflight (PRZED promptami):
    missing = check_required()
    if missing:
        stdout.write("[BLAD] Brakuje wymaganych slownikow:\n")
        for label, hint in missing:
            stdout.write(f"  - {label}: {hint}\n")
        stdout.write("\nUruchom najpierw odpowiednie loaddata / seed.\n")
        raise SystemExit(1)

    # 2. Confirm:
    plan_text = (
        f"Stworzy: {opts.wydzialow} wydz., "
        f"{opts.wydzialow * opts.jednostek_na_wydzial} jedn., "
        f"{opts.autorow} aut., {opts.ile_ciaglych} prac ciaglych, "
        f"{opts.ile_zwartych} prac zwartych w bazie '{db_name}'."
    )
    try:
        double_confirm(
            stdin=stdin,
            stdout=stdout,
            database=db_name,
            plan_text=plan_text,
            yes_flag=opts.yes_i_am_sure,
            confirm_db_flag=opts.confirm_db,
        )
    except ConfirmAborted as e:
        stdout.write(f"[ABORT] {e}\n")
        raise SystemExit(1) from None

    # 3. Manifest + RNG:
    rng = random.Random(opts.seed)
    # Serialize manifest_out (Path) jako str — JSON nie potrafi PosixPath.
    command_args = {
        k: (str(v) if isinstance(v, Path) else v) for k, v in vars(opts).items()
    }
    manifest = Manifest(
        path=opts.manifest_out,
        database=db_name,
        command_args=command_args,
    )

    # 4. Generatory (kolejnosc zalozenia: uczelnia → wydzialy → jednostki →
    # autorzy → dyscypliny → zrodla → wydawcy → WC → WZ):
    uczelnia = ensure_uczelnia(manifest)
    wydzialy = create_wydzialy(
        n=opts.wydzialow,
        uczelnia=uczelnia,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    jednostki = create_jednostki(
        per_wydzial=opts.jednostek_na_wydzial,
        wydzialy=wydzialy,
        uczelnia=uczelnia,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    autorzy = create_autorzy(
        n=opts.autorow,
        jednostki=jednostki,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(opts.od_roku, opts.do_roku + 1),
        procent_z_dyscyplina=opts.procent_z_dyscyplina,
        procent_z_subdyscyplina=opts.procent_z_subdyscyplina,
        procent_zmiana_dyscypliny=opts.procent_zmiana_dyscypliny,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    zrodla = create_zrodla(
        n=opts.zrodel,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    wydawcy = create_wydawcy(
        n=opts.wydawcow,
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_wc(
        n=opts.ile_ciaglych,
        autorzy=autorzy,
        zrodla=zrodla,
        lata=range(opts.od_roku, opts.do_roku + 1),
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_wz(
        n=opts.ile_zwartych,
        autorzy=autorzy,
        wydawcy=wydawcy,
        lata=range(opts.od_roku, opts.do_roku + 1),
        manifest=manifest,
        rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )

    manifest.save()
    stdout.write(
        f"\n[OK] Manifest zapisany: {opts.manifest_out}\n"
        f"     Cleanup: uv run python src/manage.py cleanup_demo_data"
        f" --manifest {opts.manifest_out} --yes-i-am-sure"
        f" --confirm-db {db_name}\n"
    )
