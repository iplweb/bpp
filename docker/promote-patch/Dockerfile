# Patch-layer nakładany przez .github/workflows/promote.yml podczas promocji
# RC → :latest. Bierze NIEZMIENIONY (przetestowany) obraz RC jako bazę i
# nadpisuje WYŁĄCZNIE to, co odróżnia wydanie od kandydata:
#
#   1. src/django_bpp/version.py — finalna wersja (bez sufiksu rcN). Aplikacja
#      czyta ją przez PYTHONPATH=/app/src (projekt instalowany z
#      `uv sync --no-install-project`, NIE do site-packages), więc podmiana
#      tego jednego pliku wystarcza — stopka, panel admina i Rollbar
#      (ROLLBAR["code_version"]) od razu widzą finalną wersję.
#
#   2. usunięcie skompilowanego bytecode'u version.pyc. `collectstatic` w
#      builder stage importuje django_bpp.settings → `from django_bpp.version
#      import VERSION`, więc do /app/src/django_bpp/__pycache__/ trafia .pyc
#      zapieczony z wersją rc i jest kopiowany do runtime. Bez rm Python mógłby
#      uznać stary .pyc za ważny i serwować wersję rc. rm wymusza rekompilację
#      z podmienionego .py przy pierwszym imporcie (runtime działa jako root —
#      brak USER w stage `runtime` — więc rm i rekompilacja mają uprawnienia).
#
#   3. BPP_BUILD_FLAVOR=release — obrazy RC są STAGING-flavored (stopka na
#      deploymencie :staging pokazuje rcN + git SHA). Patch przełącza je w
#      release, więc prod chowa "atrakcje" (SHA/branch/tag) i pokazuje samą
#      czystą wersję.
#
# Wszystkie warstwy poniżej pozostają bit-w-bit tymi z przetestowanego RC
# (współdzielone w rejestrze — push dokłada tylko te 2 malutkie warstwy).
# Kontekst build-u = korzeń repo; drzewo robocze promote.yml ma już
# sfinalizowany version.py (krok "Finalizuj wersję" via bumpver).
ARG RC_IMAGE
FROM ${RC_IMAGE}

COPY src/django_bpp/version.py /app/src/django_bpp/version.py
RUN rm -f /app/src/django_bpp/__pycache__/version.*.pyc

ENV BPP_BUILD_FLAVOR=release
