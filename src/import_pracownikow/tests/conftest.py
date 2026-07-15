import asyncio
import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tests._helpers import unikalna_nazwa

__all__ = ["unikalna_nazwa"]


@pytest.fixture(autouse=True)
def _bez_wycieklej_petli_zdarzen():
    """Izoluje test od wyciekłej „bieżącej pętli zdarzeń" w wątku workera.

    Testy Playwright (sync-API na greenletach) potrafią zostawić w wątku
    ustawiony ``asyncio`` running-loop marker, który już się nie czyści. Gdy
    taki test wypadnie na tym samym workerze xdist PRZED testem
    ``import_pracownikow``, każde wywołanie ``asgiref.sync.async_to_sync``
    w analizie (eager-runner liveops → ``WebProgress._push`` →
    ``channel_layer.group_send``) wywala się na „You cannot use AsyncToSync in
    the same thread as an async event loop"; wyjątek jest połknięty przez
    runner, a stan importu utyka na ``zmapowany`` zamiast przejść dalej. Efekt:
    flake zależny od kolejności shardowania (zielono w izolacji, czerwono po
    teście Playwright na tym samym workerze).

    Zerujemy marker NA CZAS testu (nasze testy są synchroniczne — nie potrzebują
    działającej pętli), a po teście PRZYWRACAMY go w niezmienionej postaci, żeby
    ewentualny kolejny test Playwright na tym workerze zastał swój współdzielony
    stan pętli nietknięty. Prywatne ``asyncio.events._{get,set}_running_loop``
    to jedyny sposób na ten marker — dopuszczalne w kodzie wyłącznie testowym.
    """
    zapisany = asyncio.events._get_running_loop()
    if zapisany is not None:
        asyncio.events._set_running_loop(None)
    try:
        yield
    finally:
        asyncio.events._set_running_loop(zapisany)


def xls_path_factory(suffix=""):
    return os.path.join(os.path.dirname(__file__), "", f"testdata{suffix}.xlsx")


def import_pracownikow_factory(user, path):
    i = ImportPracownikow(owner=user)
    with open(path, "rb") as f:
        i.plik_xls = SimpleUploadedFile(
            "import_dyscyplin_zrodel_przyklad.xlsx", f.read()
        )
    i.save()
    return i


@pytest.fixture
def testdata_xlsx_path():
    return xls_path_factory()


@pytest.fixture
def testdata_brak_naglowka_xlsx_path():
    return xls_path_factory("_brak_naglowka")


@pytest.fixture
def autor_z_pliku():
    return baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pk=50)


@pytest.fixture
def jednostka_z_pliku():
    return baker.make(
        Jednostka,
        nazwa="Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej",
        skrot="Kat. i Klin. Derm., Wen. i Derm. Dz.",
    )


@pytest.fixture
def baza_importu_pracownikow(autor_z_pliku, jednostka_z_pliku):
    pass


@pytest.fixture
def autor_spoza_pliku():
    return baker.make(Autor, nazwisko="Nowak", imiona="Marian", pk=100)


@pytest.fixture
def jednostka_spoza_pliku() -> Jednostka:
    return baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Jednostka Spozaplikowa"),
        skrot=unikalna_nazwa("Jedn. Spoz."),
        zarzadzaj_automatycznie=True,
    )


@pytest.fixture
def import_pracownikow(admin_user, baza_importu_pracownikow, testdata_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_xlsx_path)


@pytest.fixture
def import_pracownikow_performed(import_pracownikow) -> ImportPracownikow:
    """Pełny przebieg dry-run (analiza) + commit (integracja), odpowiednik
    starego ``.perform()`` (który robił obie fazy naraz) w nowym modelu
    dyspozytora ``run(self, p)`` + polu ``stan`` (Faza 0 T1/T7)."""
    import_pracownikow.stan = import_pracownikow.STAN_ZMAPOWANY
    import_pracownikow.run(MockProgress(import_pracownikow))
    import_pracownikow.stan = import_pracownikow.STAN_ZATWIERDZONY
    import_pracownikow.run(MockProgress(import_pracownikow))
    import_pracownikow.refresh_from_db()
    return import_pracownikow


@pytest.fixture
def import_pracownikow_brak_naglowka(admin_user, testdata_brak_naglowka_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_brak_naglowka_xlsx_path)


@pytest.fixture
def dwaj_autorzy_z_jednostki():
    """(Autor, Jednostka) matchowalne przez ``matchuj_autora``/``matchuj_jednostke``.

    Nazwa fixture nawiązuje do docelowego scenariusza analizy dwóch wierszy
    pliku (jeden autor już powiązany z jednostką) — na Task 3 wystarczy
    pojedyncza para, na której testy dry-run weryfikują brak zapisu do
    domeny. ``Autor_Jednostka`` i ``aktualna_jednostka`` są ustawione z
    góry, tak jak w prawdziwych danych kadrowych (autor już zatrudniony).
    """
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Testowa"),
        skrot=unikalna_nazwa("Kat. Test."),
    )
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    return autor, jednostka


@pytest.fixture
def autor_bez_autor_jednostka():
    """(Autor, Jednostka) matchowalne przez ``matchuj_autora`` po imieniu i
    nazwisku, ale BEZ powiązania ``Autor_Jednostka`` do tej jednostki.

    W przeciwieństwie do ``dwaj_autorzy_z_jednostki`` (gdzie AJ istnieje z
    góry), tu celowo NIE tworzymy ani ``Autor_Jednostka``, ani nie
    ustawiamy ``aktualna_jednostka`` — ``matchuj_autora`` i tak znajdzie
    autora po dokładnym dopasowaniu imienia+nazwiska (jednostka jest tylko
    tie-breakerem przy niejednoznaczności, nie wymogiem). Fixture pozwala
    zweryfikować gałąź ``aj is None`` w ``analyze._przetworz_wiersz``:
    autor się matchuje, ale AJ nie istnieje i dry-run go nie tworzy.
    """
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Bez Powiazania"),
        skrot=unikalna_nazwa("Kat. Bez Pow."),
    )
    autor = baker.make(Autor, nazwisko="Nowicki", imiona="Piotr")
    return autor, jednostka


@pytest.fixture
def autor_jednostka_fixture():
    """(Autor, Jednostka) do testów fazy integracji (Task 4).

    Bez powiązania ``Autor_Jednostka`` z góry — to właśnie materializacja
    ``diff_do_utworzenia["autor_jednostka"]`` w ``integrate.py`` ma je
    utworzyć. Nazwa i kształt fixture odpowiadają temu, czego oczekuje
    brief Task 4 (``test_integrate.py``); logicznie to ten sam wzorzec co
    ``autor_bez_autor_jednostka``, ale z dedykowaną nazwą dla czytelności
    testów fazy integracji.
    """
    jednostka = baker.make(
        Jednostka,
        nazwa=unikalna_nazwa("Katedra Integracji Testowej"),
        skrot=unikalna_nazwa("Kat. Integr. Test."),
    )
    autor = baker.make(Autor, nazwisko="Wisniewski", imiona="Adam")
    return autor, jednostka
