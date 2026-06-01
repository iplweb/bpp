# WeasyPrint na macOS (Apple Silicon) — problem i obejście

## TL;DR

BPP używa `django-weasyprint` do generowania PDF-ów. WeasyPrint przez
`cffi` / `ctypes.util.find_library` woła `dlopen()` na bibliotekach
natywnych (`libgobject-2.0`, `libpango-1.0`, `libharfbuzz`,
`libfontconfig.1`, `libpangoft2-1.0`). Na Apple Silicon te biblioteki
instaluje Homebrew do `/opt/homebrew/lib`, którego `dyld` **nie**
konsultuje domyślnie.

Obejście: `make prepare-developer-machine-macos` tworzy `sudo`-symlinki
w `/usr/local/lib` wskazujące na pliki w `/opt/homebrew/lib`. `dyld`
konsultuje `/usr/local/lib` z automatu (część hardcoded default search
path), więc po tym `dlopen()` znajduje libki w każdym kontekście —
niezależnie od stanu zmiennych `DYLD_*`.

## Dlaczego nie `DYLD_FALLBACK_LIBRARY_PATH`?

Krótko: SIP (System Integrity Protection) na macOS strippuje wszystkie
zmienne środowiskowe o nazwach `DYLD_*` w momencie wywołania **chronionej
binarki** — czyli wszystkiego w `/usr/bin/`, `/bin/`, `/sbin/`,
`/System/`, oraz binarek z `restrict` flagą w nagłówku Mach-O.

W praktyce każdy łańcuch wywołań typu:

```
make → /bin/sh → uv → python → pytest
```

ma ryzyko zgubienia zmiennej po drodze — wystarczy że jeden z procesów
pośrednich uruchomi się przez `/usr/bin/env` albo `/bin/sh`. Efekt jest
niedeterministyczny: czasem działa, czasem nie, zależnie od tego jak
shell rozwiązał ścieżkę do `uv` / `pytest` / `python`.

Próbowaliśmy tego podejścia w commicie `3531fd2d4`
(*fix(devsetup): macOS — DYLD_FALLBACK_LIBRARY_PATH zamiast symlinkow*).
W praktyce zmienna „nie docierała" do procesów z `pytest`, mimo że była
ustawiona w `~/.zprofile` i widoczna w shellu. Wróciliśmy do symlinków.

## Co dokładnie robi recipe `prepare-developer-machine-macos`

1. Sprawdza, czy `brew` jest zainstalowany. Jeśli nie — wypisuje
   instrukcję instalacji i wychodzi z kodem `1`.
2. `brew install cairo pango gdk-pixbuf libffi gobject-introspection
   gtk+3 node yarn` — instaluje wszystkie natywne libki + Node/Yarn.
3. `npm install -g grunt-cli` — globalny `grunt`.
4. `uv sync --frozen --no-install-project --all-extras` — synchronizuje
   środowisko Pythona.
5. **Idempotentnie tworzy symlinki** w `/usr/local/lib`:

   | Symlink (cel)                       | Źródło (Homebrew)                                       |
   | ----------------------------------- | ------------------------------------------------------- |
   | `/usr/local/lib/gobject-2.0`        | `/opt/homebrew/opt/glib/lib/libgobject-2.0.0.dylib`     |
   | `/usr/local/lib/pango-1.0`          | `/opt/homebrew/opt/pango/lib/libpango-1.0.dylib`        |
   | `/usr/local/lib/harfbuzz`           | `/opt/homebrew/opt/harfbuzz/lib/libharfbuzz.dylib`      |
   | `/usr/local/lib/fontconfig-1`       | `/opt/homebrew/opt/fontconfig/lib/libfontconfig.1.dylib`|
   | `/usr/local/lib/pangoft2-1.0`       | `/opt/homebrew/opt/pango/lib/libpangoft2-1.0.dylib`     |

   Nazwy docelowe są bez prefiksu `lib` / suffiksu `.dylib` — taką
   formę woła `weasyprint` przez `ctypes.util.find_library('gobject-2.0')`
   itd. Recipe nie nadpisuje symlinka, który już istnieje i wskazuje na
   ten sam cel (loguje „pomijam").
6. Jeśli `/usr/local/lib` nie istnieje, recipe go tworzy (`sudo mkdir -p`).
   Na świeżym Apple Silicon ten katalog często go nie ma (Homebrew Intel
   to `/usr/local`, Apple Silicon to `/opt/homebrew`).
7. **Czyści stary wpis** `DYLD_FALLBACK_LIBRARY_PATH` z `~/.zprofile`
   (jeśli wcześniej był dopisany przez poprzednią wersję recipe).
   Backup zachowywany w `~/.zprofile.bpp-bak`.
8. `make playwright-install` — instaluje przeglądarki Playwright.

`sudo` jest wymagane **raz, przy pierwszym setupie**. Kolejne uruchomienia
recipe są no-op (symlinki istnieją, wpis z zprofile już skasowany).

## Cofnięcie obejścia

Jeśli z jakiegoś powodu chcesz usunąć symlinki ręcznie:

```bash
sudo rm -f /usr/local/lib/gobject-2.0 \
           /usr/local/lib/pango-1.0 \
           /usr/local/lib/harfbuzz \
           /usr/local/lib/fontconfig-1 \
           /usr/local/lib/pangoft2-1.0
```

`brew uninstall cairo pango ...` usunie *źródła* — symlinki staną się
dangling, ale `dyld` po prostu je przeskoczy (`find_library` zwróci
`None`). WeasyPrint wtedy padnie z `OSError: cannot load library
'libgobject-2.0-0'`.

## Co z błędami build-time?

Symlinki w `/usr/local/lib` rozwiązują tylko problem **runtime'owy**
(`dlopen` po zainstalowaniu wheela). Jeśli pip/uv próbuje **zbudować
wheela ze źródła** (np. `cairocffi`, `pycairo`), kompilator szuka
nagłówków `.h` i bibliotek `.dylib` *w czasie linkowania*, na zupełnie
innych ścieżkach. Wtedy potrzeba:

```bash
export PKG_CONFIG_PATH=/opt/homebrew/lib/pkgconfig
export LDFLAGS="-L/opt/homebrew/lib"
export CPPFLAGS="-I/opt/homebrew/include"
```

W BPP używamy gotowych wheeli, więc build-time error rzadko się zdarza.
Jeśli się zdarzy — dopisz powyższe do shella i ponów `uv sync`.

## Co z Linuksem?

Na Linuksie nie ma tego problemu: `apt` instaluje libki do `/usr/lib`
albo `/usr/lib/x86_64-linux-gnu`, czyli na default search path
loadera (`ld.so`). Recipe `prepare-developer-machine-linux` instaluje
`libcairo2-dev`, `libpango1.0-dev` etc. i kończy temat — żadnych
symlinków nie potrzeba.

## Co z Dockerem?

Obrazy `iplweb/bpp_appserver` budują się na bazie Debiana — analogicznie
jak Linux deweloperski. Symlinki to wyłącznie problem stacji deweloperskiej
na Apple Silicon Macu.

## Linki

- Commit `3531fd2d4` — pierwotna (nieudana) próba z DYLD_FALLBACK
- WeasyPrint docs: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#macos
- macOS dyld(1) man page: `man dyld`
- SIP runtime restrictions: https://developer.apple.com/library/archive/documentation/Security/Conceptual/System_Integrity_Protection_Guide/RuntimeProtections/RuntimeProtections.html
