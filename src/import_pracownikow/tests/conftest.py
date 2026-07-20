import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tests._helpers import unikalna_nazwa

__all__ = ["unikalna_nazwa"]


# USUNIĘTY fixture ``_bez_wycieklej_petli_zdarzen``.
#
# Zerował marker running-loop na czas testu i PRZYWRACAŁ go w ``finally``,
# żeby obejść wyciek markera z sync-API Playwrighta (flake „You cannot use
# AsyncToSync in the same thread as an async event loop" w eager-runnerze
# liveops).
#
# Okazał się przyczyną GORSZEGO problemu: Django trzyma połączenia w
# ``asgiref.local.Local(thread_critical=True)``, którego magazyn zależy od
# ``asyncio.get_running_loop()``. Przestawianie markera przy żywych
# połączeniach przerzucało zapisy testu na INNE połączenie — bez atomic bloku,
# w autocommit — więc dane commitowały się mimo ``django_db`` i wyciekały do
# kolejnych testów na tym workerze. Na CI: 79 wykryć, wszystkie w tym appie,
# bo ten autouse obejmował WSZYSTKIE jego testy.
#
# Marker jest teraz kasowany U ŹRÓDŁA — po KAŻDYM teście, w
# ``_sprzatnij_marker_petli`` (``src/conftest.py``), zanim wstanie ``db``
# następnego testu. To usuwa oba problemy naraz: nieświeży marker nie dożywa
# kolejnego testu, więc ani ``AsyncToSync`` nie ma się o co wywrócić, ani
# magazyn połączeń nie przełącza się w trakcie testu.


@pytest.fixture(autouse=True)
def _biezaca_uczelnia_importu(request, settings):
    """Zapewnia bieżącą uczelnię dla testów WIDOKÓW importu (tych z klientem).

    Bramka ``WymagajUczelniZRequestuMixin`` redirectuje na home, gdy
    ``get_for_request`` nie ustali uczelni (0 uczelni → None). Większość testów
    widoków tworzy import bez tworzenia uczelni — bez rozstrzygalnej uczelni
    każdy widok dawał 302 zamiast 200. Tworzymy JEDNĄ uczelnię zmapowaną na host
    klienta (``testserver``), więc ``get_for_request`` ją rozstrzyga (dopasowanie
    domeny), a importy bez własnej uczelni (``uczelnia=None``) przechodzą
    ``sprawdz_uczelnie`` przez single-tenant fallback ``uczelnia_do_integracji``.

    Uruchamiane TYLKO gdy test używa klienta HTTP (``admin_client``/``client``)
    — testy modelowe/pipelinowe (bez klienta, często wrażliwe na liczbę uczelni)
    są nietknięte. Testy multi-hosted zarządzają uczelniami jawnie
    (``ustaw_biezaca_uczelnie`` zwalnia host od tej autouse-uczelni; test
    „brak uczelni" kasuje uczelnie na starcie)."""
    uzywa_klienta = any(
        f in request.fixturenames
        for f in ("client", "admin_client", "client_class", "async_client")
    )
    if not uzywa_klienta:
        return None

    from import_pracownikow.tests._helpers import ustaw_biezaca_uczelnie

    request.getfixturevalue("db")
    # Gdy test sam żąda fixture'a ``uczelnia`` (bezpośrednio lub tranzytywnie) —
    # użyj JEJ jako bieżącej, nie twórz drugiej (``bpp_uczelnia_site_id_key``
    # dopuszcza jedną Uczelnię na Site → druga = IntegrityError).
    if "uczelnia" in request.fixturenames:
        u = request.getfixturevalue("uczelnia")
    else:
        from bpp.models import Uczelnia

        u = baker.make(Uczelnia)
    ustaw_biezaca_uczelnie(u, settings)
    return u


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
