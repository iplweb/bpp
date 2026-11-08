"""Wypisuje przypiete wersje (z hashami) wybranych pakietow z uv.lock.

Uzywane przez etap `lock-pins` w docker/bpp_base/Dockerfile. Etapy
`test-browser-builder` i `test-assets-builder` potrzebuja tylko kilku
pakietow z calego zamka (Playwright do pobrania przegladarek, paczki
z plikami JS dla esbuilda). Zamiast zalezec od calego `uv.lock` (kazda zmiana
dowolnej zaleznosci przebudowywala przegladarki i Grunta), kopiuja wynik tego
skryptu: plik o tej samej tresci daje cache-hit BuildKita nawet wtedy, gdy
`uv.lock` zmienil sie w innych miejscach.

Wyjscie to plik requirements w formacie `pip`/`uv pip` z `--hash` dla
wszystkich artefaktow pakietu w zamku; instalowac z `--no-deps`.

Uzycie: python lock-pins.py UV_LOCK NAZWA [NAZWA ...] > requirements.txt
"""

import sys

import tomllib


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    with open(argv[1], "rb") as f:
        lock = tomllib.load(f)
    packages = {p["name"]: p for p in lock["package"]}
    for name in argv[2:]:
        pkg = packages.get(name)
        if pkg is None:
            sys.exit(f"lock-pins: brak pakietu {name!r} w {argv[1]}")
        if "registry" not in pkg.get("source", {}):
            sys.exit(f"lock-pins: {name!r} nie pochodzi z indeksu pakietow")
        artifacts = list(pkg.get("wheels", []))
        if "sdist" in pkg:
            artifacts.append(pkg["sdist"])
        hashes = sorted({a["hash"] for a in artifacts})
        if not hashes:
            sys.exit(f"lock-pins: {name!r} nie ma hashy w zamku")
        lines = [f"{name}=={pkg['version']}"]
        lines += [f"    --hash={h}" for h in hashes]
        print(" \\\n".join(lines))


if __name__ == "__main__":
    main(sys.argv)
