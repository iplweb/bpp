"""Faza integracji (commit) importu pracowników.

``integruj`` materializuje odroczone create'y zapisane w
``ImportPracownikowRow.diff_do_utworzenia`` przez fazę analizy
(``import_pracownikow.pipeline.analyze``) — tworzy brakujące
Funkcja_Autora/Grupa_Pracownicza/Wymiar_Etatu oraz ``Autor_Jednostka``
przez ``get_or_create`` (idempotentne przy duplikacie osoby w pliku),
ustawia FK na wierszu, po czym robi świeży ``check_if_integration_needed()``
— baza mogła się zmienić od czasu analizy (dry-run), więc wiersz uznany
za "potrzebujący zmian" w analizie może już być nieaktualny.

Uwaga: ``get_or_create`` w ``_materializuj_diff`` OD RAZU ustawia docelowe
wartości (np. ``Autor_Jednostka.funkcja``), więc świeży
``check_if_integration_needed()`` po materializacji zwykle wraca ``False``
— to NIE znaczy, że wiersz jest nieaktualny, tylko że materializacja już
wykonała pracę. ``pominiety_bo_nieaktualny`` jest więc ustawiane tylko gdy
wiersz nie miał odroczonych create'ów (prawdziwy drift bazy między analizą
a commitem); w przeciwnym razie wołane jest istniejące
``ImportPracownikowRow.integrate()`` albo — gdy recheck faktycznie nie
wykrył driftu, a materializacja coś utworzyła — ślad utworzenia jest
dopisywany ręcznie do ``log_zmian``, żeby audyt i licznik ``zintegrowano``
widziały, że wiersz wykonał realną pracę.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Wymiar_Etatu,
)
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_wymiar_etatu,
)
from import_pracownikow.models import (
    ImportPracownikow,
    wiersz_kwalifikuje_do_przepiecia,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_WIELU,
    odtworz_autor_jednostka,
)
from przemapuj_prace_autora import service as przemapuj_service


def _materializuj_diff(row):
    """Tworzy (get_or_create) obiekty odłożone przez analizę i podpina FK.

    Wartości w ``diff`` są już znormalizowane przez fazę analizy
    (``import_pracownikow.pipeline.analyze``) — ponowne wołanie
    ``normalize_*`` tutaj jest więc no-opem (normalizery są idempotentne),
    zostawione dla czytelności/obrony w głąb.
    """
    diff = row.diff_do_utworzenia or {}
    if "funkcja_autora" in diff:
        nazwa = normalize_funkcja_autora(diff["funkcja_autora"])
        row.funkcja_autora, _ = Funkcja_Autora.objects.get_or_create(
            nazwa=nazwa, defaults={"skrot": nazwa}
        )
    if "grupa_pracownicza" in diff:
        nazwa = normalize_grupa_pracownicza(diff["grupa_pracownicza"])
        row.grupa_pracownicza, _ = Grupa_Pracownicza.objects.get_or_create(nazwa=nazwa)
    if "wymiar_etatu" in diff:
        nazwa = normalize_wymiar_etatu(diff["wymiar_etatu"])
        row.wymiar_etatu, _ = Wymiar_Etatu.objects.get_or_create(nazwa=nazwa)
    if "autor_jednostka" in diff:
        # Dług Fazy 0: `get_or_create` tutaj pomija `rozpoczal_prace`, mimo
        # że `unique_together` na Autor_Jednostka to
        # (autor, jednostka, rozpoczal_prace). Dla autora z wieloma AJ w tej
        # samej jednostce (multi-etat / historia zatrudnienia) ten lookup
        # (autor, jednostka) może trafić na >1 wiersz — Django łapie tylko
        # `DoesNotExist`, więc `get_or_create` rzuci nieobsłużony
        # `MultipleObjectsReturned`. Akceptowany dług, do naprawy gdy
        # multi-etat trafi do zakresu importu.
        row.autor_jednostka, _ = Autor_Jednostka.objects.get_or_create(
            autor_id=diff["autor_jednostka"]["autor"],
            jednostka_id=diff["autor_jednostka"]["jednostka"],
            defaults={"funkcja": row.funkcja_autora},
        )


def _opisz_utworzone(diff):
    """Krótkie opisy obiektów utworzonych z ``diff_do_utworzenia`` — do
    ``log_zmian["utworzono"]``, żeby audyt widział realną pracę wykonaną
    przez materializację nawet gdy świeży recheck nie wykrył driftu."""
    opisy = []
    if "nowy_autor" in diff:
        opisy.append(f"nowy autor: {diff['nowy_autor']}")
    if "funkcja_autora" in diff:
        opisy.append(f"funkcja: {diff['funkcja_autora']}")
    if "grupa_pracownicza" in diff:
        opisy.append(f"grupa pracownicza: {diff['grupa_pracownicza']}")
    if "wymiar_etatu" in diff:
        opisy.append(f"wymiar etatu: {diff['wymiar_etatu']}")
    if "autor_jednostka" in diff:
        opisy.append("powiązanie autor-jednostka")
    return opisy


def _integruj_wiersz(row):
    with transaction.atomic():
        # Sprawdzone PRZED materializacją — po niej `diff_do_utworzenia`
        # nadal jest niepuste (nic go nie czyści), więc to jest jedyny
        # moment, w którym rozróżnienie "miał odroczone create'y" ma sens
        # jako flaga, nie tylko jako odczyt pola.
        materializowano = bool(row.diff_do_utworzenia)
        _materializuj_diff(row)
        row.save(
            update_fields=[
                "funkcja_autora",
                "grupa_pracownicza",
                "wymiar_etatu",
                "autor_jednostka",
            ]
        )
        # Świeży re-check — baza mogła się zmienić od preview (dry-run).
        if row.check_if_integration_needed():
            row.integrate()
            if materializowano:
                # `integrate()` nadpisuje `log_zmian` na starcie — ślad
                # utworzenia dopisujemy DOPIERO PO nim, do klucza
                # "utworzono", zamiast go nadpisać.
                row.log_zmian["utworzono"] = _opisz_utworzone(row.diff_do_utworzenia)
                row.save(update_fields=["log_zmian"])
            return
        if materializowano:
            # Recheck nie widzi driftu (get_or_create już ustawił docelowe
            # wartości), ale wiersz FAKTYCZNIE wykonał pracę: utworzył nowe
            # obiekty (Funkcja_Autora/Grupa_Pracownicza/Wymiar_Etatu/
            # Autor_Jednostka). To NIE jest "nieaktualny" wiersz — nie
            # oznaczamy go `pominiety_bo_nieaktualny`, tylko zapisujemy
            # ślad w `log_zmian`, żeby audyt i licznik `zintegrowano` go
            # widziały.
            row.log_zmian = {
                "autor": [],
                "autor_jednostka": [],
                "utworzono": _opisz_utworzone(row.diff_do_utworzenia),
            }
            row.save(update_fields=["log_zmian"])
            return
        # Prawdziwy drift: diff był pusty (nic nie materializowano) i
        # recheck nie widzi potrzeby zmian — baza zmieniła się od analizy.
        row.pominiety_bo_nieaktualny = True
        row.save(update_fields=["pominiety_bo_nieaktualny"])


def _wykonaj_odpiecia(parent):
    """Kończy zatrudnienie dla zaznaczonych, jeszcze niewykonanych odpięć (§9).

    Świeży re-check ma DWA warunki pomijające (oba: NIE wykonuj, NIE licz,
    ``wykonane`` zostaje False):

    1. **Para stała się parą Z PLIKU (G1).** Odpięcia materializują się w
       analizie, gdy wiersze ``wielu``/``brak`` mają ``autor=None`` — więc AJ
       PRAWDZIWEGO autora z pliku trafia na listę „spoza pliku". Gdy user potem
       rozstrzygnie wiersz (``WybierzKandydataView``/``EdytujWierszView`` ustawia
       ``row.autor``), zmaterializowane odpięcie ZOSTAJE. Gdyby je wykonać,
       zakończylibyśmy zatrudnienie pracownika, który JEST w pliku (korupcja).
       Dlatego przed wykonaniem sprawdzamy, czy para ``(autor_id, jednostka_id)``
       AJ jest teraz obecna w wierszach importu — jeśli tak, POMIJAMY (spójne z
       definicją „spoza pliku" §9 i duchem świeżego re-checku).
    2. **AJ zakończone ręcznie od czasu podglądu (drift bazy).** ``zakonczyl_prace
       is not None and <= today`` → pomijamy (NIE nadpisujemy daty).

    Wykonane: ``zakonczyl_prace = wczoraj``, ``podstawowe_miejsce_pracy =
    False``, ``wykonane = True``. Zwraca liczbę faktycznie odpiętych."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    odpieto = 0
    for odp in parent.odpiecia.filter(zaznaczone=True, wykonane=False):
        with transaction.atomic():
            aj = odp.autor_jednostka
            aj.refresh_from_db()
            # G1: para AJ trafiła do pliku po rozstrzygnięciu wiersza — to już
            # pracownik Z PLIKU, NIE odpinamy (wykonane zostaje False).
            if parent.importpracownikowrow_set.filter(
                autor_id=aj.autor_id, jednostka_id=aj.jednostka_id
            ).exists():
                continue
            if aj.zakonczyl_prace is not None and aj.zakonczyl_prace <= today:
                # zakończone ręcznie — pomijamy, nie nadpisujemy daty.
                continue
            aj.zakonczyl_prace = yesterday
            aj.podstawowe_miejsce_pracy = False
            aj.save()
            odp.wykonane = True
            odp.save(update_fields=["wykonane"])
            odpieto += 1
    return odpieto


def _wykonaj_przepiecia(parent, stare_jednostki, user, p):
    """Przepina prace dla wierszy ``przepnij_prace=True`` (§10 D6/D7).

    ``stare_jednostki`` = ``{row.pk: aktualna_jednostka_id sprzed importu}``
    zebrane PRZED pętlą integracji (trigger DB przestawia ``aktualna_jednostka``
    na jednostkę z pliku). Kwalifikacja wiersza przez wspólny
    ``wiersz_kwalifikuje_do_przepiecia`` (F1/F2/F3 — identyczny warunek co w
    UI): autor+jednostki ustawione i różne, a stara jednostka NIE jest
    potwierdzona jako etat w innym wierszu pliku (guard „para z pliku”, F1).

    F4: filtr wyklucza wiersze ``pominiety_bo_nieaktualny=True`` (drift bazy —
    integracja się NIE wykonała, więc nie przepinamy na podstawie nieaktualnego
    podglądu) oraz ``jednostka__isnull=False`` (F2). F5: gdy stara == docelowa
    (możliwy restart po częściowej integracji) zostawiamy ślad przez ``p.log``.
    F3: dla duplikatu autora z tą samą starą jednostką (dwa wiersze, różne nowe
    jednostki) przepięcie wykonujemy RAZ (pierwszy po ``pk`` — iterujemy z
    ``order_by("pk")``), kolejnym wpisujemy ślad ``przepiecie_pominiete`` bez
    pustego rekordu. Zwraca ``(przepieto_wierszy, przepieto_prac)``.
    """
    przepieto_wierszy = 0
    przepieto_prac = 0
    pary_z_pliku = parent.pary_z_pliku()
    juz_przepiete = set()
    for row in (
        parent.importpracownikowrow_set.filter(
            przepnij_prace=True,
            autor__isnull=False,
            jednostka__isnull=False,
            pominiety_bo_nieaktualny=False,
        )
        .select_related("autor")
        .order_by("pk")
    ):
        stara_id = stare_jednostki.get(row.pk)
        # F5: snapshot czyta bieżący stan — po restarcie stara może już być
        # docelową; zostawiamy ślad, nie przepinamy.
        if stara_id is not None and stara_id == row.jednostka_id:
            p.log(
                f"Wiersz {row.pk}: pominięto przepięcie — jednostka źródłowa "
                "== docelowa (brak zmiany do przepięcia)"
            )
            continue
        if not wiersz_kwalifikuje_do_przepiecia(
            row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
        ):
            continue
        # F3: duplikat autora z tą samą starą jednostką — przepinamy raz.
        if (row.autor_id, stara_id) in juz_przepiete:
            if row.log_zmian is None:
                row.log_zmian = {"autor": [], "autor_jednostka": []}
            row.log_zmian["przepiecie_pominiete"] = (
                "pominięto — prace tego autora ze starej jednostki już "
                "przepięte w innym wierszu tego importu"
            )
            row.save(update_fields=["log_zmian"])
            continue
        # G3: jednostka źródłowa (ze snapshotu) lub docelowa mogła zostać
        # usunięta między snapshotem a przepięciem — pomiń wiersz przez
        # `filter().first()` zamiast `get()`, żeby nieobsłużony `DoesNotExist`
        # nie wywrócił CAŁEGO taska integracji (okno = cała pętla, minuty).
        jednostka_z = Jednostka.objects.filter(pk=stara_id).first()
        jednostka_do = Jednostka.objects.filter(pk=row.jednostka_id).first()
        if jednostka_z is None or jednostka_do is None:
            p.log(
                f"Wiersz {row.pk}: pominięto przepięcie — jednostka źródłowa "
                "lub docelowa usunięta"
            )
            continue
        with transaction.atomic():
            prz = przemapuj_service.przemapuj(
                row.autor,
                jednostka_z,
                jednostka_do,
                user,
                zrodlowy_import=parent,
            )
            if row.log_zmian is None:
                row.log_zmian = {"autor": [], "autor_jednostka": []}
            row.log_zmian["przepiecie"] = {
                "pk": prz.pk,
                "prace_ciagle": prz.liczba_prac_ciaglych,
                "prace_zwarte": prz.liczba_prac_zwartych,
                "z": jednostka_z.skrot,
                "do": jednostka_do.skrot,
            }
            row.save(update_fields=["log_zmian"])
            juz_przepiete.add((row.autor_id, stara_id))
            przepieto_wierszy += 1
            przepieto_prac += prz.liczba_prac_ciaglych + prz.liczba_prac_zwartych
    return przepieto_wierszy, przepieto_prac


def _przygotuj_nowego_autora(row, cache):
    """D2: dla wiersza ``brak`` z ``utworz_nowego=True`` tworzy (albo REUŻYWA —
    G4) ``bpp.Autor`` (nazwisko/imiona z ``dane_znormalizowane``, tytuł z FK
    ``row.tytul`` z analizy), podpina go do wiersza i odtwarza powiązanie
    ``Autor_Jednostka`` (wspólny ``odtworz_autor_jednostka`` — odkłada AJ do
    ``diff_do_utworzenia`` i ustawia ``zmiany_potrzebne=True``). NIE integruje:
    właściwą integrację (materializacja AJ + ``integrate()``) robi główna pętla
    ``zmiany_potrzebne_set`` w ``integruj`` (bez podwójnego przetwarzania). Ślad
    utworzenia autora idzie w ``diff_do_utworzenia['nowy_autor']`` → trafia do
    ``log_zmian['utworzono']`` przez ``_opisz_utworzone``. ``imię`` to klucz
    ``AutorForm`` mapowany na ``Autor.imiona``.

    G4 (dedup multi-etat): ``cache`` to słownik ``{(nazwisko, imiona, tytul_id):
    Autor}`` współdzielony w obrębie JEDNEGO ``integruj``. Dwa wiersze tej samej
    osoby (identyczna trójka) w RÓŻNYCH jednostkach — oba ``utworz_nowego=True``
    — dają JEDEN ``Autor`` i DWA ``Autor_Jednostka`` (multi-etat), zamiast dwóch
    autorów-duplikatów. Pierwszy wiersz trójki tworzy autora (wpis do cache),
    kolejne REUŻYWAJĄ go i wołają ``odtworz_autor_jednostka`` dla swojej
    jednostki (osobne AJ). Marker ``nowy_autor`` (i inkrement licznika w
    ``integruj``) tylko przy realnym create.

    F5: ``EdytujWierszView`` waliduje TYLKO ``nazwisko`` (nie ``imię``), więc
    korekta na samo nazwisko może zejść do ``brak`` z pustym ``imię``. Autora
    bez imienia NIE tworzymy (``AutorForm`` wymaga obu) — wiersz zostaje
    ``autor=None`` i wpada w istniejący licznik ``pominieto_niedopasowane``.

    F4: create autora + ``odtworz_autor_jednostka`` + ``row.save`` w JEDNEJ
    ``transaction.atomic`` (per-wiersz). Bez tego, gdy ``row.save`` padnie, autor
    już istnieje a ``row.autor`` zostaje NULL → restart integracji (stan
    zatwierdzony + RestartView) znów trafi w ``autor__isnull=True`` i utworzy
    DRUGIEGO autora. Atomic cofa też ``Autor.create`` przy rollbacku.

    Zwraca ``True`` TYLKO gdy autor faktycznie POWSTAŁ (→ inkrement licznika).
    ``False`` gdy: (a) puste ``imię`` — pominięto, ``autor=None``; albo (b) autor
    zREUŻYTY z cache — wiersz dostaje ``autor`` i zintegruje się (nowe AJ), ale
    NIE liczy się jako nowy autor.
    """
    dane = row.dane_znormalizowane or {}
    nazwisko = (dane.get("nazwisko") or "").strip()
    imiona = (dane.get("imię") or "").strip()
    if not imiona:
        return False
    klucz = (nazwisko, imiona, row.tytul_id)
    with transaction.atomic():
        autor = cache.get(klucz)
        utworzono = autor is None
        if utworzono:
            autor = Autor.objects.create(
                nazwisko=nazwisko,
                imiona=imiona,
                tytul=row.tytul,
            )
            cache[klucz] = autor
        row.autor = autor
        odtworz_autor_jednostka(row, autor)
        if utworzono:
            row.diff_do_utworzenia["nowy_autor"] = str(autor)
        row.save(
            update_fields=[
                "autor",
                "autor_jednostka",
                "diff_do_utworzenia",
                "zmiany_potrzebne",
            ]
        )
    return utworzono


def integruj(parent, p):
    # Snapshot starych jednostek PRZED integracją: trigger DB
    # `bpp_autor_ustaw_jednostka_aktualna` przestawi `aktualna_jednostka` na
    # jednostkę z pliku, więc to jedyny moment, gdy widać stan sprzed importu.
    # Snapshot jest SZERSZY niż finalny filtr w `_wykonaj_przepiecia` (F4): na
    # tym etapie nie wiemy jeszcze, które wiersze zostaną `pominiety_bo_
    # nieaktualny`; kwalifikację (w tym `pominiety_bo_nieaktualny=False`)
    # rozstrzyga dopiero pętla w `_wykonaj_przepiecia`.
    stare_jednostki = {}
    for row in parent.importpracownikowrow_set.filter(
        przepnij_prace=True, autor__isnull=False, jednostka__isnull=False
    ).select_related("autor"):
        stare_jednostki[row.pk] = row.autor.aktualna_jednostka_id

    utworzono_nowych = 0
    # G4: cache dedupujący nowych autorów po (nazwisko, imiona, tytul_id) w
    # obrębie tego commitu — multi-etat (ta sama osoba, wiele jednostek) daje
    # jednego Autora + wiele Autor_Jednostka.
    nowi_autorzy_cache = {}
    for row in list(
        parent.importpracownikowrow_set.filter(
            confidence=STATUS_BRAK, utworz_nowego=True, autor__isnull=True
        )
    ):
        if _przygotuj_nowego_autora(row, nowi_autorzy_cache):
            utworzono_nowych += 1

    qs = parent.zmiany_potrzebne_set.all()
    for row in p.track(list(qs), total=qs.count(), label="Integracja"):
        _integruj_wiersz(row)

    odpieto = _wykonaj_odpiecia(parent)
    przepieto_wierszy, przepieto_prac = _wykonaj_przepiecia(
        parent, stare_jednostki, parent.owner, p
    )

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])

    pominieto_nieaktualne = parent.importpracownikowrow_set.filter(
        pominiety_bo_nieaktualny=True
    ).count()
    # `zintegrowano` to wiersze faktycznie przetworzone (integrate() albo
    # materializacja create-only) — czyli wszystkie ze `zmiany_potrzebne_set`
    # poza tymi prawdziwie pominiętymi jako nieaktualne. Liczenie przez
    # `log_zmian__isnull=False` było błędne: create-only wiersz, dla
    # którego `_materializuj_diff` ustawia od razu docelowe wartości, nie
    # wchodzi w `row.integrate()` (recheck nie widzi driftu), a mimo to
    # wykonał realną pracę.
    zintegrowano = parent.zmiany_potrzebne_set.count() - pominieto_nieaktualne

    # Wiersze brak/wielu bez rozstrzygnięcia usera (autor None) — świadomie
    # pominięte w tej fazie (Faza 4 doda „utwórz nowego"). Raportujemy licznik
    # + flagę „wymaga uwagi", żeby podsumowanie nie udawało pełnego sukcesu.
    pominieto_niedopasowane = parent.importpracownikowrow_set.filter(
        confidence__in=[STATUS_BRAK, STATUS_WIELU], autor__isnull=True
    ).count()
    p.result(
        {
            "zintegrowano": zintegrowano,
            "pominieto_nieaktualne": pominieto_nieaktualne,
            "pominieto_niedopasowane": pominieto_niedopasowane,
            "wymaga_uwagi": pominieto_niedopasowane > 0,
            "odpieto": odpieto,
            "przepieto_wierszy": przepieto_wierszy,
            "przepieto_prac": przepieto_prac,
            "utworzono_nowych_autorow": utworzono_nowych,
            "stan": parent.stan,
        }
    )
