"""Bramka regresyjna na N+1 w changelistach admina (Django 6.1).

``test_fetch_peers.py`` obok pilnuje tylko tego, że tryb ``FETCH_PEERS``
JEST USTAWIONY i przeżywa klonowanie querysetu. To za mało: dowodzi, że
mechanizm jest podpięty, ale nie dowodzi, że changelisty faktycznie
przestały robić N+1 — ani nie zatrzyma powrotu N+1, gdy ktoś dołoży
kolumnę do ``list_display`` albo relację do ``__str__``.

Tutaj przybijamy KSZTAŁT ZAPYTAŃ, trzema uzupełniającymi się bramkami.

1. ``FETCH_RAISE`` (``test_changelist_*_bez_dociagania_relacji``) —
   renderujemy prawdziwą changelistę przez klienta HTTP, podmieniając
   tryb pobierania na ``FETCH_RAISE``. Wtedy KAŻDE leniwe dotknięcie
   relacji (albo pola odroczonego) rzuca ``FieldFetchBlocked`` z nazwą
   pola, zamiast po cichu dołożyć SELECT-a. Test przechodzi tylko wtedy,
   gdy wszystko, czego dotyka szablon i ``list_display``, zostało
   pobrane HURTEM — czyli zadeklarowane w ``list_select_related``.

2. Liczba zapytań niezależna od liczby wierszy
   (``test_liczba_zapytan_*``) — renderujemy tę samą changelistę raz
   z dwoma, raz z ośmioma wierszami i wymagamy TAKIEJ SAMEJ liczby
   zapytań. To bezpośrednia definicja braku N+1 i, w odróżnieniu od
   przybicia konkretnej liczby, nie wymaga aktualizacji przy każdej
   niewinnej zmianie (np. dołożeniu filtra).

3. Deklaracja ``list_select_related`` naprawdę trafia do zapytania
   (``test_deklaracja_list_select_related_*``) — Django aplikuje ją
   WARUNKOWO, więc sama jej obecność w kodzie nic nie gwarantuje.
   Szczegóły przy teście.

Jak dokładnie działa ``FETCH_RAISE`` (wg kodu Django 6.1):
``QuerySet.fetch_mode(tryb)`` zapisuje tryb w ``_fetch_mode``; przy
materializacji wierszy ``ModelIterable`` przekazuje go do
``Model.from_db(..., fetch_mode=...)``, skąd ląduje w
``instance._state.fetch_mode`` (i jest dziedziczony przez obiekty
z ``select_related`` oraz ``prefetch_related``). Trzy deskryptory —
``DeferredAttribute`` (pole odroczone), ``ForwardManyToOneDescriptor``
(FK/O2O w przód) i ``ReverseOneToOneDescriptor`` — zamiast dociągać
dane wołają ``instance._state.fetch_mode.fetch(...)``. ``FetchRaise``
rzuca w tym miejscu ``FieldFetchBlocked`` (podklasa ``FieldError``)
z komunikatem ``"Fetching of <Model>.<pole> blocked."``.

CZEGO ``FETCH_RAISE`` NIE ŁAPIE: menedżerów relacji odwrotnych
(``obj.cos_set.all()``) i M2M — one tylko DZIEDZICZĄ tryb do swojego
querysetu, nie są przez niego blokowane. Dlatego bramka nr 2 (liczba
zapytań) jest tu niezbędna, a nie ozdobna.

Co się stanie, gdy ktoś doda kolumnę do ``list_display``: jeśli kolumna
sięga po relację (``obj.cokolwiek.pole``), bramka nr 1 wywali się
natychmiast komunikatem ``Fetching of Model.cokolwiek blocked.``.
Naprawa: dopisać relację do ``list_select_related`` (w BPP zwykle do
dialektu słownikowego ``{"nazwa_kolumny": ["relacja"]}``, obsługiwanego
przez ``django-dynamic-admin-columns`` — join płaci tylko wtedy, gdy
kolumna jest widoczna).

Uwaga o zakresie: ``FETCH_RAISE`` jest tu WYŁĄCZNIE narzędziem
testowym, podmienianym przez ``monkeypatch`` na czas jednego testu.
Kod produkcyjny dalej używa ``FETCH_PEERS``, a globalny
``DEFAULT_FETCH_MODE`` pozostaje nietknięty.
"""

import pytest
from django.contrib import admin as dj_admin
from django.core.exceptions import FieldFetchBlocked
from django.db import connection
from django.db.models import FETCH_RAISE
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from bpp.admin import core
from bpp.admin.jednostka import JednostkaAdmin
from bpp.models import Charakter_Formalny, Jednostka, RodzajJednostki, Typ_KBN

#: Ile wierszy renderujemy w bramce „liczba zapytań nie zależy od liczby
#: wierszy". Obie liczby muszą mieścić się na jednej stronie changelisty
#: (``list_per_page``), żeby paginacja nie mieszała w pomiarze.
MALO_WIERSZY = 2
DUZO_WIERSZY = 8


@pytest.fixture(autouse=True)
def swiezy_uklad_kolumn():
    """Wyzeruj cache układu kolumn ``django-dynamic-admin-columns``.

    ``DynamicColumnsMixin._modeladmin_enabled`` to ``cached_property``
    trzymana na OBIEKCIE admina, a adminy są singletonami rejestru —
    cache przeżywa rollback bazy między testami, choć wiersze modelu
    ``ModelAdmin`` (układ kolumn) znikają razem z transakcją. Skutek:
    kolejny test dostaje z ``get_list_display`` układ inny, niż sądzi
    (w praktyce uboższy), więc bramka renderuje mniej kolumn i CICHO SIĘ
    ROZBRAJA. Czyścimy przed każdym testem, żeby każdy startował od
    domyślnego układu odtworzonego z kodu.
    """
    for model_admin in dj_admin.site._registry.values():
        model_admin.__dict__.pop("_modeladmin_enabled", None)


@pytest.fixture
def fetch_raise_w_adminie(monkeypatch):
    """Podmień tryb pobierania adminów z ``FETCH_PEERS`` na ``FETCH_RAISE``.

    ``BaseBppAdminMixin.get_queryset`` woła ``.fetch_mode(FETCH_PEERS)``,
    czytając ``FETCH_PEERS`` jako globalną nazwę modułu ``bpp.admin.core``
    — podmiana tej nazwy przestawia tryb dla WSZYSTKICH adminów BPP naraz,
    bez dotykania kodu produkcyjnego i bez kopiowania logiki
    ``get_queryset`` do testu.
    """
    monkeypatch.setattr(core, "FETCH_PEERS", FETCH_RAISE)


def _url(nazwa_modelu):
    return reverse(f"admin:bpp_{nazwa_modelu}_changelist")


# ---------------------------------------------------------------------------
# Budowniczowie danych. Każdy tworzy wiersze changelisty z WYPEŁNIONYMI
# FK-ami widocznych kolumn — ``FETCH_RAISE`` odpala się tylko dla relacji
# o niepustym kluczu (``ForwardManyToOneDescriptor`` sprawdza ``has_value``),
# więc rekordy z samymi NULL-ami przepuściłyby bramkę na pusto.
# ---------------------------------------------------------------------------


@pytest.fixture
def buduj_wydawnictwa_ciagle(
    db, jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    from fixtures.conftest_publications import _wydawnictwo_ciagle_maker

    typ_kbn = Typ_KBN.objects.first()
    charakter_formalny = Charakter_Formalny.objects.first()
    licznik = 0

    def buduj(ile):
        nonlocal licznik
        for _ in range(ile):
            licznik += 1
            _wydawnictwo_ciagle_maker(
                tytul_oryginalny=f"Ciągłe {licznik}",
                typ_kbn=typ_kbn,
                charakter_formalny=charakter_formalny,
            )

    return buduj


@pytest.fixture
def buduj_wydawnictwa_zwarte(
    db,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
    wydawca,
):
    from fixtures.conftest_publications import _zwarte_maker

    typ_kbn = Typ_KBN.objects.first()
    charakter_formalny = Charakter_Formalny.objects.first()
    # Kolumna ``wydawnictwo_nadrzedne_col`` jest domyślnie widoczna, więc
    # rekordy MUSZĄ mieć wypełnione ``wydawnictwo_nadrzedne`` — inaczej
    # bramka nie sprawdzi tej relacji.
    nadrzedne = _zwarte_maker(tytul_oryginalny="Zwarte nadrzędne")
    licznik = 0

    def buduj(ile):
        nonlocal licznik
        for _ in range(ile):
            licznik += 1
            _zwarte_maker(
                tytul_oryginalny=f"Zwarte {licznik}",
                typ_kbn=typ_kbn,
                charakter_formalny=charakter_formalny,
                wydawnictwo_nadrzedne=nadrzedne,
                wydawca=wydawca,
            )

    return buduj


@pytest.fixture
def buduj_autorow(db, tytuly):
    from fixtures.conftest_models import _autor_maker

    licznik = 0

    def buduj(ile):
        nonlocal licznik
        for _ in range(ile):
            licznik += 1
            # ``Autor.__str__`` dokleja ``self.tytul.skrot`` — bez tytułu
            # bramka przepuściłaby brak JOIN-a na ``tytul``.
            _autor_maker(imiona=f"Jan{licznik}", nazwisko=f"Nowak{licznik}")

    return buduj


@pytest.fixture
def buduj_jednostki(db, uczelnia, wydzial):
    from fixtures.conftest_models import _jednostka_maker

    rodzaj = RodzajJednostki.objects.get_or_create(nazwa="Katedra")[0]
    licznik = 0

    def buduj(ile):
        nonlocal licznik
        for _ in range(ile):
            licznik += 1
            _jednostka_maker(
                nazwa=f"Jednostka {licznik}",
                skrot=f"J{licznik}",
                wydzial=wydzial,
                rodzaj=rodzaj,
            )

    return buduj


#: (nazwa modelu w URL-u adminowym, nazwa fixture'a budującego dane).
#: Cztery najgorętsze changelisty BPP: dwa główne typy publikacji (setki
#: tysięcy rekordów, najczęściej otwierana lista w systemie) oraz autorzy
#: i jednostki — słowniki, po których redakcja nawiguje bez przerwy i
#: których ``__str__`` sięga po FK (``Autor.tytul``, ``Jednostka.uczelnia``).
CHANGELISTY = [
    ("wydawnictwo_ciagle", "buduj_wydawnictwa_ciagle"),
    ("wydawnictwo_zwarte", "buduj_wydawnictwa_zwarte"),
    ("autor", "buduj_autorow"),
    ("jednostka", "buduj_jednostki"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("model,budowniczy", CHANGELISTY)
def test_changelist_nie_dociaga_relacji_spoza_deklaracji(
    model, budowniczy, request, admin_client, uczelnia, fetch_raise_w_adminie
):
    """Changelista renderuje się BEZ ani jednego leniwego dociągnięcia relacji.

    Przed czym chroni: ktoś dokłada kolumnę do ``list_display`` (albo
    ``list_display_default``), która sięga po FK — np. ``obj.wydawca.nazwa``
    — i zapomina dopisać relację do ``list_select_related``. Bez tej bramki
    zmiana przechodzi na zielono, a na produkcji każdy wiersz listy
    (do 50 na stronę) dokłada jeden SELECT.

    Z ``FETCH_RAISE`` taka zmiana wywala test natychmiast, komunikatem
    ``Fetching of <Model>.<pole> blocked.`` — od razu wiadomo, CO dopisać
    i GDZIE.
    """
    request.getfixturevalue(budowniczy)(DUZO_WIERSZY)

    res = admin_client.get(_url(model))

    assert res.status_code == 200


@pytest.mark.django_db
def test_bramka_fetch_raise_faktycznie_gryzie(
    admin_client, uczelnia, buduj_wydawnictwa_ciagle, monkeypatch
):
    """Meta-test: sprawdź, że bramka wyżej NIE jest pusta.

    Test z ``FETCH_RAISE`` jest wart tyle, ile mechanizm podmiany trybu.
    Gdyby ``BaseBppAdminMixin.get_queryset`` przestało czytać
    ``FETCH_PEERS`` z modułu (albo ktoś nadpisał ``get_queryset``
    w podklasie bez ``super()``), fixture ``fetch_raise_w_adminie``
    stałby się no-opem i wszystkie bramki zrobiłyby się ZIELONE NA PUSTO.

    Tutaj świadomie kasujemy deklarację ``list_select_related``
    changelisty wydawnictw ciągłych. Kolumna ``zrodlo_col`` czyta
    ``obj.zrodlo.nazwa``, więc przy działającej bramce MUSI polecieć
    ``FieldFetchBlocked``.
    """
    from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin

    buduj_wydawnictwa_ciagle(MALO_WIERSZY)
    monkeypatch.setattr(core, "FETCH_PEERS", FETCH_RAISE)
    monkeypatch.setattr(Wydawnictwo_CiagleAdmin, "list_select_related", {})

    with pytest.raises(FieldFetchBlocked) as wyjatek:
        admin_client.get(_url("wydawnictwo_ciagle"))

    assert "Wydawnictwo_Ciagle." in str(wyjatek.value)


@pytest.mark.django_db
@pytest.mark.parametrize("model,budowniczy", CHANGELISTY)
def test_liczba_zapytan_nie_zalezy_od_liczby_wierszy(
    model, budowniczy, request, admin_client, uczelnia
):
    """Ta sama changelista, 2 i 8 wierszy — dokładnie tyle samo zapytań.

    To jest operacyjna definicja „nie ma N+1": koszt zapytań ma zależeć
    od liczby zadeklarowanych relacji, a nie od liczby wierszy na stronie.
    W odróżnieniu od przybicia konkretnej liczby (``assert n == 17``) ta
    bramka nie wymaga aktualizacji przy niewinnych zmianach — reaguje
    dopiero na regresję, która naprawdę boli.

    Łapie też przypadki, których ``FETCH_RAISE`` NIE widzi: dociąganie
    przez menedżery relacji odwrotnych (``obj.cos_set.all()``) i M2M —
    one tryb tylko dziedziczą, nie są przez niego blokowane.

    Przed każdym pomiarem robimy rozgrzewkę, bo pierwszy request na
    changelistę zapełnia cache'e niezależne od liczby wierszy (układ
    kolumn ``django-dynamic-admin-columns``, content-typy, uprawnienia).
    """
    buduj = request.getfixturevalue(budowniczy)
    url = _url(model)

    buduj(MALO_WIERSZY)
    admin_client.get(url)  # rozgrzewka cache'ów
    with CaptureQueriesContext(connection) as malo:
        admin_client.get(url)

    buduj(DUZO_WIERSZY - MALO_WIERSZY)
    admin_client.get(url)  # rozgrzewka po zmianie danych
    with CaptureQueriesContext(connection) as duzo:
        admin_client.get(url)

    assert len(duzo) == len(malo), (
        f"Changelista {model}: {MALO_WIERSZY} wierszy → {len(malo)} zapytań, "
        f"{DUZO_WIERSZY} wierszy → {len(duzo)}. Liczba zapytań rośnie razem "
        f"z liczbą wierszy, czyli wróciło N+1. Nadmiarowe zapytania:\n"
        + "\n".join(q["sql"][:200] for q in duzo.captured_queries[len(malo) :])
    )


def _sciezka_w_select_related(select_related, sciezka):
    """Czy ``sciezka`` (dialekt ``a__b``) jest w drzewie ``select_related``?

    ``Query.select_related`` to zagnieżdżony słownik (``{"autor":
    {"tytul": {}}}``) albo ``True``/``False`` — schodzimy nim segment po
    segmencie.
    """
    if select_related is True:
        return True
    if not isinstance(select_related, dict):
        return False
    poziom = select_related
    for segment in sciezka.split("__"):
        if segment not in poziom:
            return False
        poziom = poziom[segment]
    return True


@pytest.mark.django_db
def test_deklaracja_list_select_related_trafia_do_zapytania(rf, admin_user, uczelnia):
    """``list_select_related`` bywa przez Django CICHO POMIJANE — pilnuj tego.

    ``ChangeList.get_queryset`` aplikuje deklarację warunkowo::

        if not qs.query.select_related:
            qs = self.apply_select_related(qs)

    czyli tylko wtedy, gdy queryset bazowy admina nie ma JESZCZE żadnego
    ``select_related``. Wystarczy więc, że manager modelu dokłada własny
    (``JednostkaManager.get_queryset()`` robi
    ``.select_related("wydzial")``), by CAŁA deklaracja z admina przepadła
    — bez ostrzeżenia, bez błędu, po prostu N+1 na produkcji.

    Test przechodzi po wszystkich zarejestrowanych adminach BPP i szuka
    DOKŁADNIE tej pułapki: admin, którego queryset bazowy ma już jakiś
    ``select_related`` (więc Django deklaracji nie doda), a zadeklarowanych
    ścieżek w tym querysecie brakuje. Adminów bez własnego
    ``select_related`` nie ruszamy — tam ``apply_select_related`` zadziała
    normalnie.
    """
    request = rf.get("/admin/")
    request.user = admin_user

    problemy = []
    for model, model_admin in dj_admin.site._registry.items():
        if model._meta.app_label != "bpp":
            continue
        deklaracja = model_admin.get_list_select_related(request)
        if isinstance(deklaracja, bool) or not deklaracja:
            continue
        select_related = model_admin.get_queryset(request).query.select_related
        if not select_related:
            # ChangeList sam zaaplikuje deklarację — nie ma pułapki.
            continue
        brakujace = [
            sciezka
            for sciezka in deklaracja
            if not _sciezka_w_select_related(select_related, sciezka)
        ]
        if brakujace:
            problemy.append(f"{model_admin.__class__.__name__}: {sorted(brakujace)}")

    assert not problemy, (
        "Adminy deklarują ``list_select_related``, którego Django do "
        "zapytania NIE wstawi (bo queryset bazowy ma już własny "
        "``select_related``, więc ``ChangeList`` pomija "
        "``apply_select_related``). Dołóż brakujące relacje w "
        "``get_queryset`` admina:\n" + "\n".join(problemy)
    )


@pytest.mark.django_db
def test_jednostka_laczy_wszystkie_zadeklarowane_relacje(rf, admin_user, uczelnia):
    """Regresja wprost: changelista jednostek gubiła 3 z 4 JOIN-ów.

    ``JednostkaManager`` dokłada ``select_related("wydzial")``, przez co
    ``ChangeList`` pomijał ``apply_select_related`` i do zapytania szedł
    SAM ``wydzial``. ``rodzaj`` (kolumna ``list_display``), ``uczelnia``
    (czytana przez ``Jednostka.__str__`` przy sprawdzaniu
    ``uzywaj_wydzialow``) i ``parent`` (kolumna ``parent_nazwa``) leciały
    leniwie, jedno zapytanie na wiersz.

    Ten test celuje w konkretny model, żeby po ewentualnym przepisaniu
    ogólnego testu wyżej regresja nie mogła wrócić bokiem.
    """
    request = rf.get("/admin/")
    request.user = admin_user
    model_admin = JednostkaAdmin(Jednostka, dj_admin.site)

    select_related = model_admin.get_queryset(request).query.select_related

    assert sorted(select_related) == ["parent", "rodzaj", "uczelnia", "wydzial"]
