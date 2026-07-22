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

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    StanowiskoDydaktyczne,
    StopienSluzbowy,
    Tytul,
    Wymiar_Etatu,
)
from import_common.core.jednostka import unikalny_skrot, zaproponuj_skrot
from import_common.core.stanowisko import zaproponuj_skrot_stanowiska
from import_common.core.stopien import zaproponuj_skrot_stopnia
from import_common.core.tytul import zaproponuj_skrot_tytulu
from import_common.exceptions import BPPDatabaseError
from import_common.normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_wymiar_etatu,
)
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
    ImportPracownikowTytul,
    wiersz_kwalifikuje_do_przepiecia,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_WIELU,
    odtworz_autor_jednostka,
)
from przemapuj_prace_autora import service as przemapuj_service


def _materializuj_diff(row):
    """Tworzy obiekty odłożone przez analizę i podpina FK. Zwraca ``created``
    (bool) dla ``Autor_Jednostka`` — zasila licznik nowych okresów zatrudnienia.

    Wartości w ``diff`` są już znormalizowane przez fazę analizy
    (``import_pracownikow.pipeline.analyze``) — ponowne wołanie
    ``normalize_*`` tutaj jest więc no-opem (normalizery są idempotentne),
    zostawione dla czytelności/obrony w głąb.

    ``Autor_Jednostka`` tworzymy po PEŁNYM kluczu ``unique_together`` (autor,
    jednostka, ``rozpoczal_prace``): lookup ``order_by("pk").first()`` + jawny
    ``create`` (nie ``get_or_create``) jest deterministyczny i nie rzuca
    ``MultipleObjectsReturned`` przy duplikatach ``(A, J, NULL)`` z admina/legacy.
    Nowy AJ z pustym „plik_od" dostaje fallback ``data zmian → dziś`` (P1) TU, przy
    materializacji — świeży AJ ma więc od razu ``rozpoczal_prace`` (nie ``NULL``),
    a ``_integruj_daty_aj`` już go nie stempluje."""
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
    created = False
    if "autor_jednostka" in diff:
        d = diff["autor_jednostka"]
        rozpoczal = (
            date.fromisoformat(d["rozpoczal_prace"])
            if d.get("rozpoczal_prace")
            else None
        )
        if rozpoczal is None:
            # Nowy AJ, pusty plik_od → fallback (P1): data zmian → dziś. Odtąd
            # tworzony rekord ma konkretną datę (brak NULL w kluczu unikalności).
            rozpoczal = row.parent.data_zmian_personalnych or timezone.localdate()
        aj = (
            Autor_Jednostka.objects.filter(
                autor_id=d["autor"],
                jednostka_id=d["jednostka"],
                rozpoczal_prace=rozpoczal,
            )
            .order_by("pk")
            .first()
        )
        created = aj is None
        if created:
            aj = Autor_Jednostka.objects.create(
                autor_id=d["autor"],
                jednostka_id=d["jednostka"],
                rozpoczal_prace=rozpoczal,
                funkcja=row.funkcja_autora,
                stanowisko=row.stanowisko_dydaktyczne,
            )
        row.autor_jednostka = aj
    return created


def _opisz_utworzone(diff, aj_created=True):
    """Krótkie opisy obiektów utworzonych z ``diff_do_utworzenia`` — do
    ``log_zmian["utworzono"]``, żeby audyt widział realną pracę wykonaną
    przez materializację nawet gdy świeży recheck nie wykrył driftu.

    ``aj_created`` (zwrot ``_materializuj_diff``): gdy AJ NIE powstał (drugi
    wiersz z tym samym ``(A, J, data)`` trafił lookupem w istniejący) — NIE
    opisujemy „nowy okres" (N6), żeby audyt nie kłamał."""
    opisy = []
    if "nowy_autor" in diff:
        opisy.append(f"nowy autor: {diff['nowy_autor']}")
    if "funkcja_autora" in diff:
        opisy.append(f"funkcja: {diff['funkcja_autora']}")
    if "grupa_pracownicza" in diff:
        opisy.append(f"grupa pracownicza: {diff['grupa_pracownicza']}")
    if "wymiar_etatu" in diff:
        opisy.append(f"wymiar etatu: {diff['wymiar_etatu']}")
    if "autor_jednostka" in diff and aj_created:
        aj_diff = diff["autor_jednostka"]
        if aj_diff.get("nowy_okres"):
            rozpoczal = aj_diff.get("rozpoczal_prace")
            opisy.append(
                f"nowy okres zatrudnienia od {rozpoczal}"
                if rozpoczal
                else "nowy okres zatrudnienia"
            )
        else:
            opisy.append("powiązanie autor-jednostka")
    return opisy


def _oznacz_wiersz_bledny(row, powod):
    """Oznacz wiersz, którego integracja naruszyła niezmiennik bazy (np.
    odwrócony zakres dat) — jego transakcja per-wiersz jest już wycofana
    (savepoint w ``_integruj_wiersz``). Zapisujemy powód do ``log_zmian["blad"]``
    (widoczny w audycie), żeby błąd JEDNEGO wiersza nie wywalał całego commitu
    (audyt #2). ``log_zmian`` niepuste działa też jak marker „już przetworzony"
    — restart integracji go nie powtórzy."""
    row.log_zmian = {"autor": [], "autor_jednostka": [], "blad": [powod]}
    row.save(update_fields=["log_zmian"])


def _integruj_wiersz(row):
    # Idempotencja (#508 F2): faza integracji może ruszyć drugi raz na tym
    # samym parencie (restart liveops / podwójne „Zatwierdź" — stan
    # zatwierdzony/zintegrowany NIE kasuje wierszy podglądu), a `integruj`
    # nie zeruje `zmiany_potrzebne`, więc wiersz wraca do worklisty. `log_zmian`
    # ustawia WYŁĄCZNIE integracja (analiza zostawia None) — więc jest pewnym
    # markerem „już zintegrowany". Bez tego guardu drugi przebieg albo nadpisuje
    # audyt `log_zmian` (gałąź materializacji), albo fałszywie oznacza wiersz
    # `pominiety_bo_nieaktualny` (świeży recheck nie widzi już driftu).
    # Restart (log_zmian już ustawiony) → nie liczymy nowego okresu ponownie.
    if row.log_zmian is not None:
        return False
    with transaction.atomic():
        # Sprawdzone PRZED materializacją — po niej `diff_do_utworzenia`
        # nadal jest niepuste (nic go nie czyści), więc to jest jedyny
        # moment, w którym rozróżnienie "miał odroczone create'y" ma sens
        # jako flaga, nie tylko jako odczyt pola.
        materializowano = bool(row.diff_do_utworzenia)
        # Zamroź stan pól PRZED materializacją diffu — potem baza = plik i live
        # dałoby „zgodne". Snapshot musi odzwierciedlać stan z podglądu (m.in.
        # odroczone AJ = None → funkcja „brak"). `integrate()` niżej go nie
        # nadpisze (guard `is None`), a gałąź create-only utrwala go tym save.
        if row.stany_pol_snapshot is None:
            row.stany_pol_snapshot = row.stany_pol()
        created = _materializuj_diff(row)
        # Nowy okres zatrudnienia = utworzono AJ (created), który analiza
        # oznaczyła jako DODATKOWY okres (nowy_okres) → licznik §10.
        nowy_okres_utworzony = bool(
            created
            and (row.diff_do_utworzenia or {})
            .get("autor_jednostka", {})
            .get("nowy_okres")
        )
        # Sygnał dla `integrate()._przepnij_aj_po_defragmentacji`: tylko świeży
        # okres może zostać scalony przez `Autor.save()` (defragmentacja) i
        # wymagać przepięcia FK przed zapisem AJ.
        row._okres_swiezo_utworzony = nowy_okres_utworzony
        row.save(
            update_fields=[
                "funkcja_autora",
                "grupa_pracownicza",
                "wymiar_etatu",
                "autor_jednostka",
                "stany_pol_snapshot",
            ]
        )
        # Świeży re-check — baza mogła się zmienić od preview (dry-run).
        if row.check_if_integration_needed():
            row.integrate()
            if getattr(row, "_okres_scalony_po_defragmentacji", False):
                # Świeży okres zlał się z sąsiadującym (defragmentacja) → netto
                # NIE powstał nowy okres, więc nie inkrementuj licznika (#3).
                nowy_okres_utworzony = False
            if materializowano:
                # `integrate()` nadpisuje `log_zmian` na starcie — ślad
                # utworzenia dopisujemy DOPIERO PO nim, do klucza
                # "utworzono", zamiast go nadpisać.
                row.log_zmian["utworzono"] = _opisz_utworzone(
                    row.diff_do_utworzenia, created
                )
                row.save(update_fields=["log_zmian"])
            return nowy_okres_utworzony
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
                "utworzono": _opisz_utworzone(row.diff_do_utworzenia, created),
            }
            row.save(update_fields=["log_zmian"])
            return nowy_okres_utworzony
        # Prawdziwy drift: diff był pusty (nic nie materializowano) i
        # recheck nie widzi potrzeby zmian — baza zmieniła się od analizy.
        row.pominiety_bo_nieaktualny = True
        row.save(update_fields=["pominiety_bo_nieaktualny"])
        return False


def _wykonaj_odpiecia(parent):
    """Kończy zatrudnienie dla zaznaczonych, jeszcze niewykonanych odpięć (§9).

    Świeży re-check ma DWA warunki pomijające (oba: NIE wykonuj, NIE licz,
    ``wykonane`` zostaje False):

    1. **Para stała się parą Z PLIKU (G1).** Odpięcia materializują się w
       analizie, gdy wiersze ``wielu``/``brak`` mają ``autor=None`` — więc AJ
       PRAWDZIWEGO autora z pliku trafia na listę „spoza pliku". Gdy user potem
       rozstrzygnie wiersz (``WybierzKandydataView``/``DopasujAutoraView``
       ustawia ``row.autor``), zmaterializowane odpięcie ZOSTAJE. Gdyby je wykonać,
       zakończylibyśmy zatrudnienie pracownika, który JEST w pliku (korupcja).
       Dlatego przed wykonaniem sprawdzamy, czy para ``(autor_id, jednostka_id)``
       AJ jest teraz obecna w wierszach importu — jeśli tak, POMIJAMY (spójne z
       definicją „spoza pliku" §9 i duchem świeżego re-checku).
    2. **AJ ma już ustawioną datę końca.** ``zakonczyl_prace is not None`` →
       pomijamy (NIE nadpisujemy). Dotyczy dat przeszłych (zakończone ręcznie,
       drift bazy) ORAZ przyszłych (zaplanowany koniec umowy — dozwolony od
       mig 0469); ustawiona data to świadoma decyzja człowieka.

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
            if aj.zakonczyl_prace is not None:
                # Ma już USTAWIONĄ datę końca — pomijamy, nie nadpisujemy.
                # Dotyczy dat przeszłych (zakończone ręcznie, drift bazy) ORAZ
                # przyszłych (zaplanowany koniec umowy, dozwolony od mig 0469):
                # ustawiona data to świadoma decyzja człowieka, a ponowny import
                # pomijający tę osobę nie może jej po cichu skasować. Dawny
                # warunek `<= today` przepuszczał przyszłe daty do nadpisania.
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

    F5: wiersz ``brak`` z ``utworz_nowego=True`` może mieć puste ``imię`` —
    dane z XLS przychodzą bez rozbicia imienia (inline-edycja rozbicia w UI już
    NIE istnieje: ekran dopasowania autora zastąpił free-text). Autora bez
    imienia NIE tworzymy (``AutorForm`` wymaga obu) — wiersz zostaje
    ``autor=None`` i wpada w istniejący licznik ``pominieto_niedopasowane``.
    Guard ZOSTAJE jako defensywa, bo ``dane_znormalizowane['imię']`` bywa puste
    u źródła.

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
    email = (dane.get("email") or "").strip()
    if not imiona:
        return False
    klucz = (nazwisko, imiona, row.tytul_id)
    with transaction.atomic():
        autor = cache.get(klucz)
        utworzono = autor is None
        if utworzono:
            # e-mail = no-overwrite dotyczy tylko ISTNIEJĄCYCH; nowy autor
            # zapisuje z pliku (spec §11.2). Stopień z FK row.stopien (analiza).
            autor = Autor.objects.create(
                nazwisko=nazwisko,
                imiona=imiona,
                tytul=row.tytul,
                stopien_sluzbowy=row.stopien,
                email=email,
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


def _resolve_parent_dla_decyzji(dec, uczelnia, pobierz_parent_domyslny):
    """Efektywny parent nowej jednostki. Jawny ``wybrany_parent`` wygrywa; dla
    ``None`` semantyka zależy od ``uzywaj_wydzialow``: root (False) albo domyślny
    węzeł-wydział (True, tworzony leniwie przez ``pobierz_parent_domyslny``)."""
    if dec.wybrany_parent_id is not None:
        return dec.wybrany_parent
    if uczelnia is not None and uczelnia.uzywaj_wydzialow:
        return pobierz_parent_domyslny()
    return None


def _rozstrzygnij_jedna_decyzje(
    dec, uczelnia, pobierz_parent_domyslny, zajete_skroty, p
):
    """Zwraca ``(jednostka|None, czy_utworzono_nowa)`` dla jednej decyzji.

    Guard idempotencji: gdy ``utworzona`` już ustawione (restart / podwójny
    commit) — używamy jej. ``pomin`` → None. ``mapuj`` → wybrana (może być None →
    wiersze niedopasowane). ``akceptuj``: ``zgadywanie`` → auto; ``brak`` → utwórz
    (albo dołącz do istniejącej po iexact — wariant wielkości liter / drift bazy).
    Tworzenie wymaga jednoznacznej uczelni; przy jej braku — log i None."""
    if dec.utworzona_id is not None:
        return dec.utworzona, False

    if dec.decyzja == ImportPracownikowJednostka.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowJednostka.DECYZJA_MAPUJ:
        return dec.wybrana_jednostka, False
    # DECYZJA_AKCEPTUJ
    if dec.tryb == ImportPracownikowJednostka.TRYB_ZGADYWANIE:
        return dec.auto_jednostka, False

    # tryb BRAK → utwórz. Case-insensitive re-match tuż przed create chroni przed
    # duplikatem (wariant wielkości liter / drift bazy między analizą a commitem).
    istniejaca = Jednostka.objects.filter(nazwa__iexact=dec.nazwa_zrodlowa).first()
    if istniejaca is not None:
        return istniejaca, False
    if uczelnia is None:
        p.log(
            f"Nie utworzono jednostki «{dec.nazwa_zrodlowa}» — brak jednoznacznej "
            "uczelni (0 lub >1 w systemie)."
        )
        return None, False

    parent_jed = _resolve_parent_dla_decyzji(dec, uczelnia, pobierz_parent_domyslny)
    baza_skrotu = dec.skrot_sugerowany or zaproponuj_skrot(dec.nazwa_zrodlowa)
    skrot = unikalny_skrot(baza_skrotu, zajete_skroty)
    zajete_skroty.add(skrot)
    nowa = Jednostka.objects.create(
        nazwa=dec.nazwa_zrodlowa[:512],
        skrot=skrot,
        uczelnia=uczelnia,
        parent=parent_jed,
    )
    return nowa, True


def _podlacz_wiersze_do_jednostek(parent):
    """Ustawia ``row.jednostka`` na rozstrzygniętą jednostkę decyzji i przelicza
    ``Autor_Jednostka``/``zmiany_potrzebne`` (dla wierszy z autorem). Wiersze
    decyzji ``pomin`` / nierozstrzygniętych (``utworzona`` None) zostają
    niedopasowane (``jednostka`` None)."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_jednostki__isnull=False
    ).select_related("zrodlo_jednostki", "autor"):
        jed = row.zrodlo_jednostki.utworzona
        if jed is None:
            continue
        row.jednostka = jed
        if row.autor is not None:
            # odtworz_autor_jednostka czyta row.autor + row.jednostka (już
            # ustawione) i wylicza AJ/diff/zmiany_potrzebne.
            odtworz_autor_jednostka(row, row.autor)
            row.save(
                update_fields=[
                    "jednostka",
                    "autor_jednostka",
                    "diff_do_utworzenia",
                    "zmiany_potrzebne",
                ]
            )
        else:
            row.save(update_fields=["jednostka"])


def _rozstrzygnij_jednostki(parent, p):
    """FAZA 0 integracji: rozstrzyga decyzje o jednostkach (utwórz/auto/mapuj/
    pomiń), tworzy brakujące i podłącza wiersze. Zwraca liczbę FAKTYCZNIE
    utworzonych jednostek. Idempotentne (guard ``utworzona`` per decyzja).

    MUSI być pierwszym krokiem ``integruj`` — przed snapshotem ``stare_jednostki``
    (inaczej świeżo podłączone wiersze nie trafią do snapshotu → przepięcia
    milczą) i przed fazą nowych autorów (inaczej wiersz z odroczoną jednostką
    poszedłby w ``get_or_create(jednostka_id=None)`` → IntegrityError).

    Uczelnię bierzemy z ``parent.uczelnia_do_integracji()`` (uczelnia importu
    złapana z requestu; fallback: jedyna w systemie) — w multi-hosted (>1
    uczelnia) ``get_single_uczelnia_or_none()`` zwróciłoby ``None`` i FAZA 0 NIE
    utworzyłaby żadnej jednostki (regresja: ciche pominięcie)."""
    uczelnia = parent.uczelnia_do_integracji()
    zajete_skroty = set()
    utworzono = 0
    _cache = {}

    def pobierz_parent_domyslny():
        if "wezel" not in _cache:
            from bpp.models.struktura_konwersja import (
                znajdz_lub_utworz_wezel_wydzialu,
            )
            from pbn_import.utils.institution_import import (
                znajdz_lub_utworz_wydzial_domyslny,
            )

            wydzial, _ = znajdz_lub_utworz_wydzial_domyslny(uczelnia)
            wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
            _cache["wezel"] = wezel
        return _cache["wezel"]

    for dec in parent.jednostki_do_decyzji.all():
        with transaction.atomic():
            jed, utworzono_nowa = _rozstrzygnij_jedna_decyzje(
                dec, uczelnia, pobierz_parent_domyslny, zajete_skroty, p
            )
            if jed is not None and dec.utworzona_id != jed.pk:
                dec.utworzona = jed
                dec.save(update_fields=["utworzona"])
        if utworzono_nowa:
            utworzono += 1

    _podlacz_wiersze_do_jednostek(parent)
    return utworzono


def unikalny_skrot_tytulu(base, zajete=None):
    """Zwraca skrót unikalny w tabeli ``Tytul`` ORAZ względem ``zajete`` (skróty
    utworzone wcześniej w TYM SAMYM runie integracji — obrona przed kolizją
    in-batch, gdy dwie różne nazwy dają tę samą bazę skrótu). Mirror
    ``unikalny_skrot`` (jednostka.py:174) na ``Tytul.skrot`` (``unique=True``).
    Kolizja → sufiks numeryczny (``dr``, ``dr2``, ``dr3``…), całość przycięta do
    128 znaków (``Tytul.skrot.max_length``)."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "TYT"

    def wolny(s):
        return s not in zajete and not Tytul.objects.filter(skrot=s).exists()

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1


def unikalny_skrot_stopnia(base, zajete=None):
    """Mirror ``unikalny_skrot_tytulu`` na ``StopienSluzbowy.skrot``."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "ST"

    def wolny(s):
        return s not in zajete and not StopienSluzbowy.objects.filter(skrot=s).exists()

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1


def unikalny_skrot_stanowiska(base, zajete=None):
    """Mirror ``unikalny_skrot_stopnia`` na ``StanowiskoDydaktyczne.skrot``."""
    zajete = set(zajete or ())
    base = (base or "").strip()[:128] or "SD"

    def wolny(s):
        return (
            s not in zajete
            and not StanowiskoDydaktyczne.objects.filter(skrot=s).exists()
        )

    if wolny(base):
        return base
    i = 2
    while True:
        suf = str(i)
        kand = base[: 128 - len(suf)] + suf
        if wolny(kand):
            return kand
        i += 1


def _rozstrzygnij_jeden_tytul(dec, zajete_nazwy, zajete_skroty, p):
    """Zwraca ``(tytul|None, czy_utworzono_nowy)`` dla jednej decyzji o tytule.

    Guard idempotencji: gdy ``utworzony`` już ustawione (restart / podwójny
    commit) — używamy go. ``pomin`` → None. ``mapuj`` → wybrany (może być None →
    wiersze bez tytułu). ``akceptuj``: ``zgadywanie`` → auto; ``brak`` → utwórz
    (albo dołącz do istniejącego).

    Tworzenie broni OBU pól ``unique=True`` na ``Tytul`` (``nazwa`` 512 ORAZ
    ``skrot`` 128): ``nazwa_do_utworzenia`` jest edytowalna na ekranie decyzji,
    więc case-insensitive re-match po nazwie tuż przed create chroni przed
    duplikatem nazwy (wariant wielkości liter / drift bazy / druga decyzja z tą
    samą edytowaną nazwą — pierwsza commituje w swojej transakcji, druga trafia
    tu w istniejący). Pusta nazwa → fallback do ``nazwa_zrodlowa``. Skrót przez
    ``unikalny_skrot_tytulu`` (sufiks przy kolizji). ``zajete_nazwy``/
    ``zajete_skroty`` to zbiory in-batch (obrona przed kolizją w obrębie runu)."""
    if dec.utworzony_id is not None:
        return dec.utworzony, False

    if dec.decyzja == ImportPracownikowTytul.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowTytul.DECYZJA_MAPUJ:
        return dec.wybrany_tytul, False
    # DECYZJA_AKCEPTUJ
    if dec.tryb == ImportPracownikowTytul.TRYB_ZGADYWANIE:
        return dec.auto_tytul, False

    # tryb BRAK → utwórz. Nazwa edytowalna → fallback na źródłową, gdy pusta.
    nazwa = (dec.nazwa_do_utworzenia or "").strip() or (
        dec.nazwa_zrodlowa or ""
    ).strip()
    nazwa = nazwa[:512]
    # Re-match po nazwie (guard `Tytul.nazwa` unique) — łapie też istniejący
    # wpis utworzony przez wcześniejszą decyzję tego samego runu (każda decyzja
    # commituje we własnej transakcji przed kolejną).
    istniejacy = Tytul.objects.filter(nazwa__iexact=nazwa).first()
    if istniejacy is not None:
        return istniejacy, False

    baza_skrotu = dec.skrot_do_utworzenia or zaproponuj_skrot_tytulu(dec.nazwa_zrodlowa)
    skrot = unikalny_skrot_tytulu(baza_skrotu, zajete_skroty)
    nowy = Tytul.objects.create(nazwa=nazwa, skrot=skrot)
    zajete_nazwy.add(nazwa)
    zajete_skroty.add(skrot)
    return nowy, True


def _podlacz_wiersze_do_tytulow(parent):
    """Ustawia ``row.tytul`` na rozstrzygnięty tytuł decyzji (ZAWSZE — faza
    nowych autorów w ``integruj`` czyta ``row.tytul``) i — tylko dla wierszy z
    już dopasowanym autorem i powiązaniem — przelicza ``zmiany_potrzebne``.

    BLOCKER-guard (finding review): ``check_if_integration_needed()`` woła
    ``getattr(self.autor, …)`` / ``self.autor_jednostka.…``, więc dla wierszy
    ``wielu``/``brak`` (``autor``/``autor_jednostka`` None — codzienny przypadek,
    gdy tytuł ma decyzję, a osoba jeszcze nie jest rozstrzygnięta) rzuciłby
    ``AttributeError`` ubijający cały task liveops. Dlatego recheck robimy TYLKO
    gdy oba FK są ustawione. Przeliczenie jest MONOTONICZNE (nie cofa
    ``True→False``): ``bool(diff) or check() or dotychczasowe``."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_tytulu__isnull=False
    ).select_related("zrodlo_tytulu", "autor", "autor_jednostka"):
        row.tytul = row.zrodlo_tytulu.utworzony
        if row.autor_id is not None and row.autor_jednostka_id is not None:
            row.zmiany_potrzebne = (
                bool(row.diff_do_utworzenia)
                or row.check_if_integration_needed()
                or row.zmiany_potrzebne
            )
            row.save(update_fields=["tytul", "zmiany_potrzebne"])
        else:
            row.save(update_fields=["tytul"])


def _rozstrzygnij_tytuly(parent, p):
    """FAZA 0.5 integracji: rozstrzyga decyzje o tytułach (utwórz/auto/mapuj/
    pomiń), tworzy brakujące i podłącza wiersze. Zwraca liczbę FAKTYCZNIE
    utworzonych tytułów. Idempotentne (guard ``utworzony`` per decyzja).

    Wołane zaraz PO ``_rozstrzygnij_jednostki`` i PRZED snapshotem
    ``stare_jednostki`` oraz fazą nowych autorów — ``_przygotuj_nowego_autora`` /
    ``_integrate_autor`` czytają ``row.tytul``/``tytul_id`` przy tworzeniu i
    aktualizacji autora."""
    zajete_nazwy = set()
    zajete_skroty = set()
    utworzono = 0

    for dec in parent.tytuly_do_decyzji.all():
        with transaction.atomic():
            tytul, utworzono_nowy = _rozstrzygnij_jeden_tytul(
                dec, zajete_nazwy, zajete_skroty, p
            )
            if tytul is not None and dec.utworzony_id != tytul.pk:
                dec.utworzony = tytul
                dec.save(update_fields=["utworzony"])
        if utworzono_nowy:
            utworzono += 1

    _podlacz_wiersze_do_tytulow(parent)
    return utworzono


def _rozstrzygnij_jeden_stopien(dec, zajete_nazwy, zajete_skroty, p):
    """Mirror ``_rozstrzygnij_jeden_tytul`` dla ``StopienSluzbowy``."""
    if dec.utworzony_id is not None:
        return dec.utworzony, False
    if dec.decyzja == ImportPracownikowStopien.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowStopien.DECYZJA_MAPUJ:
        return dec.wybrany_stopien, False
    if dec.tryb == ImportPracownikowStopien.TRYB_ZGADYWANIE:
        return dec.auto_stopien, False

    nazwa = (dec.nazwa_do_utworzenia or "").strip() or (
        dec.nazwa_zrodlowa or ""
    ).strip()
    nazwa = nazwa[:512]
    istniejacy = StopienSluzbowy.objects.filter(nazwa__iexact=nazwa).first()
    if istniejacy is not None:
        return istniejacy, False
    baza_skrotu = dec.skrot_do_utworzenia or zaproponuj_skrot_stopnia(
        dec.nazwa_zrodlowa
    )
    skrot = unikalny_skrot_stopnia(baza_skrotu, zajete_skroty)
    nowy = StopienSluzbowy.objects.create(nazwa=nazwa, skrot=skrot)
    zajete_nazwy.add(nazwa)
    zajete_skroty.add(skrot)
    return nowy, True


def _podlacz_wiersze_do_stopni(parent):
    """Mirror ``_podlacz_wiersze_do_tytulow`` — ``row.stopien``. Recompute
    ``zmiany_potrzebne`` (monotone) TYLKO gdy autor ustawiony (stopień jest na
    Autorze; ``check_if_integration_needed`` sięga ``self.autor``)."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_stopnia__isnull=False
    ).select_related("zrodlo_stopnia", "autor", "autor_jednostka"):
        row.stopien = row.zrodlo_stopnia.utworzony
        if row.autor_id is not None:
            row.zmiany_potrzebne = (
                bool(row.diff_do_utworzenia)
                or row.check_if_integration_needed()
                or row.zmiany_potrzebne
            )
            row.save(update_fields=["stopien", "zmiany_potrzebne"])
        else:
            row.save(update_fields=["stopien"])


def _rozstrzygnij_stopnie(parent, p):
    """Mirror ``_rozstrzygnij_tytuly`` dla stopni służbowych."""
    zajete_nazwy = set()
    zajete_skroty = set()
    utworzono = 0
    for dec in parent.stopnie_do_decyzji.all():
        with transaction.atomic():
            stopien, utworzono_nowy = _rozstrzygnij_jeden_stopien(
                dec, zajete_nazwy, zajete_skroty, p
            )
            if stopien is not None and dec.utworzony_id != stopien.pk:
                dec.utworzony = stopien
                dec.save(update_fields=["utworzony"])
        if utworzono_nowy:
            utworzono += 1
    _podlacz_wiersze_do_stopni(parent)
    return utworzono


def _rozstrzygnij_jedno_stanowisko(dec, zajete_nazwy, zajete_skroty, p):
    """Mirror ``_rozstrzygnij_jeden_stopien`` dla ``StanowiskoDydaktyczne``."""
    if dec.utworzone_id is not None:
        return dec.utworzone, False
    if dec.decyzja == ImportPracownikowStanowisko.DECYZJA_POMIN:
        return None, False
    if dec.decyzja == ImportPracownikowStanowisko.DECYZJA_MAPUJ:
        return dec.wybrane_stanowisko, False
    if dec.tryb == ImportPracownikowStanowisko.TRYB_ZGADYWANIE:
        return dec.auto_stanowisko, False

    nazwa = (dec.nazwa_do_utworzenia or "").strip() or (
        dec.nazwa_zrodlowa or ""
    ).strip()
    nazwa = nazwa[:512]
    istniejace = StanowiskoDydaktyczne.objects.filter(nazwa__iexact=nazwa).first()
    if istniejace is not None:
        return istniejace, False
    baza_skrotu = dec.skrot_do_utworzenia or zaproponuj_skrot_stanowiska(
        dec.nazwa_zrodlowa
    )
    skrot = unikalny_skrot_stanowiska(baza_skrotu, zajete_skroty)
    nowe = StanowiskoDydaktyczne.objects.create(nazwa=nazwa, skrot=skrot)
    zajete_nazwy.add(nazwa)
    zajete_skroty.add(skrot)
    return nowe, True


def _podlacz_wiersze_do_stanowisk(parent):
    """Mirror ``_podlacz_wiersze_do_tytulow`` — ``row.stanowisko_dydaktyczne``.
    Stanowisko jest na Autor_Jednostka, więc recompute gated jak tytuł
    (autor + autor_jednostka ustawione)."""
    for row in parent.importpracownikowrow_set.filter(
        zrodlo_stanowiska_dydaktycznego__isnull=False
    ).select_related("zrodlo_stanowiska_dydaktycznego", "autor", "autor_jednostka"):
        row.stanowisko_dydaktyczne = row.zrodlo_stanowiska_dydaktycznego.utworzone
        if row.autor_id is not None and row.autor_jednostka_id is not None:
            row.zmiany_potrzebne = (
                bool(row.diff_do_utworzenia)
                or row.check_if_integration_needed()
                or row.zmiany_potrzebne
            )
            row.save(update_fields=["stanowisko_dydaktyczne", "zmiany_potrzebne"])
        else:
            row.save(update_fields=["stanowisko_dydaktyczne"])


def _rozstrzygnij_stanowiska(parent, p):
    """Mirror ``_rozstrzygnij_stopnie`` dla stanowisk dydaktycznych."""
    zajete_nazwy = set()
    zajete_skroty = set()
    utworzono = 0
    for dec in parent.stanowiska_do_decyzji.all():
        with transaction.atomic():
            stanowisko, utworzono_nowe = _rozstrzygnij_jedno_stanowisko(
                dec, zajete_nazwy, zajete_skroty, p
            )
            if stanowisko is not None and dec.utworzone_id != stanowisko.pk:
                dec.utworzone = stanowisko
                dec.save(update_fields=["utworzone"])
        if utworzono_nowe:
            utworzono += 1
    _podlacz_wiersze_do_stanowisk(parent)
    return utworzono


def integruj(parent, p):
    zakres = parent.zakres_integracji

    # FAZA 0: rozstrzygnij i utwórz brakujące jednostki, podłącz wiersze —
    # ZANIM policzymy snapshot i fazę nowych autorów (patrz docstring wyżej).
    # Wykonywana ZAWSZE (każdy zakres tworzy jednostki).
    utworzono_jednostek = _rozstrzygnij_jednostki(parent, p)

    # FAZA 0.5: rozstrzygnij i utwórz brakujące tytuły, podłącz wiersze — zaraz
    # po jednostkach i PRZED snapshotem/fazą autorów (autorzy czytają row.tytul).
    # Pomijana dla zakresu „tylko jednostki" (STRUKTURA i PELNY dostają tytuły).
    utworzono_tytulow = 0
    utworzono_stopni = 0
    utworzono_stanowisk = 0
    if zakres != ImportPracownikow.ZAKRES_JEDNOSTKI:
        utworzono_tytulow = _rozstrzygnij_tytuly(parent, p)
        # FAZA 0.6/0.7: stopnie + stanowiska (słowniki, jak tytuły) — PRZED
        # snapshotem/fazą osób (autorzy czytają row.stopien; AJ row.stanowisko).
        utworzono_stopni = _rozstrzygnij_stopnie(parent, p)
        utworzono_stanowisk = _rozstrzygnij_stanowiska(parent, p)

    # Zakres strukturalny (JEDNOSTKI / STRUKTURA): tworzymy TYLKO strukturę —
    # bez snapshotu, fazy nowych autorów, przepięć i odpięć. Osoby są
    # NIETKNIĘTE (żadnych zapisów Autor / Autor_Jednostka — reconcilery jednostek
    # /tytułów operują wyłącznie na wierszach importu i strukturze). Kończymy
    # tutaj z licznikami struktury i flagą zakresu (panel wyniku pokaże właściwy
    # komunikat).
    if zakres in (
        ImportPracownikow.ZAKRES_JEDNOSTKI,
        ImportPracownikow.ZAKRES_STRUKTURA,
    ):
        # Krok 1 zakończony: struktura zapisana, osoby NIE. NIE „zintegrowany"
        # (to sugerowałoby komplet) — nowy stan „struktura zintegrowana"
        # odblokowuje Krok 2 (import osób) i odsłania szczegóły autorów.
        parent.stan = ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
        parent.save(update_fields=["stan"])
        p.result(
            {
                "zakres": zakres,
                "utworzono_jednostek": utworzono_jednostek,
                "utworzono_tytulow": utworzono_tytulow,
                "utworzono_stopni": utworzono_stopni,
                "utworzono_stanowisk": utworzono_stanowisk,
                "stan": parent.stan,
            }
        )
        return

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
            confidence=STATUS_BRAK,
            utworz_nowego=True,
            autor__isnull=True,
            # Jednostka MUSI być rozstrzygnięta (§6.6): wiersz z odroczoną/pominiętą
            # jednostką (jednostka None) nie może tworzyć AJ z jednostka_id=None.
            jednostka__isnull=False,
        )
    ):
        if _przygotuj_nowego_autora(row, nowi_autorzy_cache):
            utworzono_nowych += 1

    qs = parent.zmiany_potrzebne_set.all()
    utworzono_nowych_okresow = 0
    for row in p.track(list(qs), total=qs.count(), label="Integracja"):
        try:
            if _integruj_wiersz(row):
                utworzono_nowych_okresow += 1
        except BPPDatabaseError as e:
            # Naruszenie niezmiennika w JEDNYM wierszu (np. odwrócone daty z XLS)
            # NIE może wywalić całego commitu i zostawić import w połowie (audyt
            # #2). Wiersz jest już wycofany (savepoint); oznaczamy go i lecimy
            # dalej — reszta przechodzi, a błąd trafia do audytu + licznika.
            _oznacz_wiersz_bledny(row, e.reason)

    odpieto = _wykonaj_odpiecia(parent)
    przepieto_wierszy, przepieto_prac = _wykonaj_przepiecia(
        parent, stare_jednostki, parent.owner, p
    )

    parent.stan = ImportPracownikow.STAN_ZINTEGROWANY
    parent.save(update_fields=["stan"])

    # Zamroź „po imporcie" jako trwały, niezmienny rekord tego, co trafiło do
    # BPP. Błąd generacji NIE może wywalić już-zakończonej integracji (osoby są
    # zapisane); logujemy (stderr + rollbar) i lecimy dalej — widok pobierania
    # degraduje wtedy do budowy w locie. Świadomie NIE re-raise.
    # Sama generacja snapshotu nie jest write-once/idempotentna, ale
    # finalizacja jest jednorazowa (bramka stanu blokuje re-integrację
    # ZINTEGROWANEGO importu) — w praktyce ta linia wykonuje się raz.
    try:
        from import_pracownikow.eksport import zapisz_snapshot_po_imporcie

        zapisz_snapshot_po_imporcie(parent)
    except Exception:
        import traceback as _tb

        import rollbar

        _tb.print_exc()
        rollbar.report_exc_info()

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
    # Wiersze odrzucone przez guard niezmienników (np. odwrócone daty) —
    # oznaczone ``log_zmian["blad"]``. Nie są „zintegrowane" ani „nieaktualne";
    # raportujemy osobno i wykluczamy z licznika `zintegrowano` (audyt #2).
    pominieto_bledne = parent.zmiany_potrzebne_set.filter(
        log_zmian__has_key="blad"
    ).count()
    zintegrowano = (
        parent.zmiany_potrzebne_set.count() - pominieto_nieaktualne - pominieto_bledne
    )

    # Wiersze brak/wielu bez rozstrzygnięcia usera (autor None) — świadomie
    # pominięte w tej fazie (Faza 4 doda „utwórz nowego"). Raportujemy licznik
    # + flagę „wymaga uwagi", żeby podsumowanie nie udawało pełnego sukcesu.
    pominieto_niedopasowane = parent.importpracownikowrow_set.filter(
        confidence__in=[STATUS_BRAK, STATUS_WIELU], autor__isnull=True
    ).count()
    # Wiersze ze ZNANYM autorem, ale bez jednostki (odroczona / pominięta) —
    # integracja ich nie tyka (brak Autor_Jednostka, zmiany_potrzebne=False), a
    # licznik „niedopasowane" ich nie łapie (autor jest ustawiony). Bez osobnego
    # licznika znikały z podsumowania, robiąc z częściowego importu pozorny
    # pełny sukces (uwaga reviewera #3).
    pominieto_bez_jednostki = parent.importpracownikowrow_set.filter(
        autor__isnull=False, jednostka__isnull=True
    ).count()
    p.result(
        {
            "zintegrowano": zintegrowano,
            "pominieto_nieaktualne": pominieto_nieaktualne,
            "pominieto_niedopasowane": pominieto_niedopasowane,
            "pominieto_bez_jednostki": pominieto_bez_jednostki,
            "pominieto_bledne": pominieto_bledne,
            "wymaga_uwagi": (
                pominieto_niedopasowane + pominieto_bez_jednostki + pominieto_bledne
            )
            > 0,
            "odpieto": odpieto,
            "przepieto_wierszy": przepieto_wierszy,
            "przepieto_prac": przepieto_prac,
            "utworzono_nowych_autorow": utworzono_nowych,
            "utworzono_nowych_okresow": utworzono_nowych_okresow,
            "utworzono_jednostek": utworzono_jednostek,
            "utworzono_tytulow": utworzono_tytulow,
            "utworzono_stopni": utworzono_stopni,
            "utworzono_stanowisk": utworzono_stanowisk,
            "stan": parent.stan,
        }
    )
