"""Test świeżości commitowanych artefaktów schematu DjangoQL.

``src/bpp/data/{rekord,autor,autorzy}_djangoql_schema.compact.txt`` to opisy
przestrzeni wyszukiwania wystawiane KONSUMENTOM (asystenci LLM, integratorzy
``/api/v1/zapytanie/``). Są generowane komendą
``opisz_schemat_djangoql_dla_llm``, ale do tej pory NIC nie pilnowało, żeby
nadążały za modelami — i faktycznie rozjechały się cicho: po fazie 01
soft-delete nie wymieniały ``deleted_at`` w ogóle. Ta klasa zaniedbania wraca
przy każdej zmianie modeli w allow-liście (faza 02 doda ``deleted_at`` pięciu
modelom publikacji).

Ten test porównuje artefakt z repo z artefaktem wygenerowanym z AKTUALNYCH
modeli. Porównanie NIE jest bajt-w-bajt — patrz :func:`_normalizuj`.

Gdy test padnie
===============

To znaczy, że schemat DjangoQL zmienił się razem z modelami. Zregeneruj::

    uv run python src/manage.py opisz_schemat_djangoql_dla_llm \\
        --wszystkie-korzenie

i zacommituj trzy pliki z ``src/bpp/data/``. Regeneruj przeciw bazie
zbudowanej z ``baseline-sql/baseline.sql`` (np. ``uv run run-site run`` bez
dumpa) — wtedy do repo open-source nie trafiają dane Twojej instytucji.
"""

import re

import pytest
from django.core.management import call_command

from bpp.management.commands.opisz_schemat_djangoql_dla_llm import (
    DATA_DIR,
    KORZENIE,
)

#: Nagłówek sekcji ze słownikami — wszystko od niej w dół to WARTOŚCI wierszy
#: pobrane z bazy, nie opis modeli.
SEKCJA_SLOWNIKOW = "dictionaries (shared relation values, referenced above):"

#: Marker „po czym dopasować obiekt tej relacji" (``match nazwa``). djangoql
#: emituje go tylko wtedy, gdy w bazie SĄ jakieś wartości do dopasowania —
#: czyli jest funkcją zawartości bazy, nie modeli.
RE_MARKER_MATCH = re.compile(r"  match [a-z_]+(?= |$)")


def _normalizuj(tekst: str) -> str:
    """Zostaw z artefaktu to, co jest funkcją MODELI, wytnij resztę.

    Świadomie pomijane (i dlaczego):

    1. **Linia ``# BPP <wersja>``** — stempel wersji zmienia się przy KAŻDYM
       wydaniu (``promote.yml`` podmienia ``version.py``), a schemat nie.
       Bez tego wyjątku test świeciłby się na czerwono po każdym release,
       zamiast na realnym rozjeździe modeli.
    2. **Sekcja ``dictionaries``** oraz **markery ``match <pole>``** —
       to WARTOŚCI wierszy słowników odczytane z bazy, na której puszczono
       generator. Baza testowa (baseline) ma inny zestaw niż instalacja
       konkretnej uczelni, więc porównywanie ich zamieniłoby test świeżości
       modeli w test zawartości bazy (i uzależniło CI od danych).

    Wszystko inne — komplet modeli, komplet pól, typy, nullowalność, choices,
    verbose_name/help_text, nagłówek z kontraktem soft-delete — porównujemy
    dosłownie. To wystarczy, żeby zniknięcie albo pojawienie się pola
    (``deleted_at``!) zapaliło czerwone światło.
    """
    linie = []
    for linia in tekst.splitlines():
        if linia.startswith("# BPP "):
            continue
        if linia.startswith(SEKCJA_SLOWNIKOW):
            break
        if "->" in linia:
            linia = RE_MARKER_MATCH.sub("", linia)
        linie.append(linia)
    return "\n".join(linie).rstrip("\n") + "\n"


@pytest.mark.django_db
@pytest.mark.parametrize(("etykieta_modelu", "nazwa_pliku"), sorted(KORZENIE.items()))
def test_artefakt_djangoql_nadaza_za_modelami(etykieta_modelu, nazwa_pliku, tmp_path):
    """Artefakt w repo == artefakt wygenerowany z aktualnych modeli."""
    swiezy = tmp_path / nazwa_pliku
    call_command(
        "opisz_schemat_djangoql_dla_llm",
        "--model",
        etykieta_modelu,
        "--output",
        str(swiezy),
    )

    zacommitowany = DATA_DIR / nazwa_pliku
    assert zacommitowany.exists(), f"brak artefaktu {zacommitowany}"

    assert _normalizuj(zacommitowany.read_text(encoding="utf-8")) == _normalizuj(
        swiezy.read_text(encoding="utf-8")
    ), (
        f"Artefakt {nazwa_pliku} rozjechał się z modelami. Zregeneruj:\n"
        f"  uv run python src/manage.py opisz_schemat_djangoql_dla_llm "
        f"--wszystkie-korzenie\n"
        f"Szczegóły — docstring src/bpp/tests/test_djangoql_schema_swiezosc.py"
    )


def test_normalizacja_widzi_roznice_pol():
    """Meta-test: normalizacja NIE zjada tego, czego ma pilnować.

    Bez niego „zielony test świeżości" nie niósłby informacji — dokładnie ten
    sam powód, dla którego kanarki ORM/katalogowy mają swoje meta-testy.
    """
    bazowy = "bpp.wydawnictwo_ciagle_autor:\n  afiliuje  bool\n"
    z_polem = (
        "bpp.wydawnictwo_ciagle_autor:\n  afiliuje  bool\n  deleted_at  datetime?\n"
    )

    assert _normalizuj(bazowy) != _normalizuj(z_polem)


def test_normalizacja_ignoruje_wersje_slowniki_i_markery():
    """…a jednocześnie milczy na tym, co świadomie pomijamy."""
    wspolne = 'bpp.rekord:\n  jezyk  -> bpp.jezyk  match nazwa  "Język"\n'

    a = (
        "# BPP 202601.1\n"
        + wspolne
        + SEKCJA_SLOWNIKOW
        + '\n  bpp.jezyk\n    nazwa: "pol."\n'
    )
    b = (
        "# BPP 202699.9\n"
        + wspolne.replace("  match nazwa", "")
        + SEKCJA_SLOWNIKOW
        + '\n  bpp.jezyk\n    nazwa: "ang.", "pol."\n'
    )

    assert _normalizuj(a) == _normalizuj(b)
