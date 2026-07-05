"""Faza B / issue #438 — współdzielona logika węzła-lustra Wydzial→Jednostka.

Węzeł-lustro to ukryta ``Jednostka`` z ``legacy_wydzial_id == wydzial.id``,
używana jako ``Jednostka_Rodzic.parent`` w miejsce dawnego pola ``wydzial``.
Migracja ``0455`` / komenda ``konwertuj_wydzialy_na_jednostki`` tworzą te węzły
wsadowo (dla istniejących wydziałów, na modelach historycznych).

Model LAZY (decyzja koordynatora, #438): NIE tworzymy lustra dla KAŻDEGO
wydziału (to zawyżałoby ``Jednostka.objects.count()`` przy każdym fixture'cie
Wydziału). Lustro powstaje dopiero w MOMENCIE LINKOWANIA — gdy kod potrzebuje
wydziału jako ``parent`` — przez ``znajdz_lub_utworz_wezel_wydzialu``. Inwariant
zawężony: „każdy PODPIĘTY wydział ma lustro" (nie „każdy wydział").

Runtime = MPTT liczy pola drzewa (lft/rght/tree_id) sam — tworzymy przez
zwykłe ``Jednostka.objects.create(parent=None, ...)``, bez ręcznego
ustawiania pól drzewa (inaczej niż migracja na modelach historycznych).
"""


def _bez_kolizji(model, field, value, max_length, suffix):
    """Zwraca ``value`` jeśli nie koliduje z istniejącą ``Jednostka`` na
    ``field``; inaczej dokleja deterministyczny ``suffix`` (wyprowadzony ze
    stabilnego ``Wydzial.id``), przycinając bazę do ``max_length``.

    Ta sama logika co ``_bez_kolizji`` w migracji ``0455`` — ``nazwa`` i
    ``skrot`` ``Jednostka`` są ``unique=True`` GLOBALNIE, więc runtime create
    węzła-lustra musi bronić się przed kolizją identycznie jak konwersja
    wsadowa (te same suffiksy → ten sam wynik, gdyby oba się spotkały).
    Puste/None zostawiamy bez zmian (nie ma po czym kolidować).
    """
    if not value:
        return value
    if not model.objects.filter(**{field: value}).exists():
        return value
    base = value
    if len(base) + len(suffix) > max_length:
        base = base[: max_length - len(suffix)]
    return f"{base}{suffix}"


def znajdz_lub_utworz_wezel_wydzialu(wydzial):
    """LAZY get-or-create węzła-lustra ``Jednostka`` dla ``wydzial`` (po
    ``legacy_wydzial_id``). Zwraca ``(jednostka, created)``.

    Wołany w miejscach LINKOWANIA (tam, gdzie kod ustawia
    ``Jednostka_Rodzic.parent`` z wydziału): pbn_import, import_jednostki_ipis
    itp. Idempotentny; nie synchronizuje pól przy kolejnych wywołaniach —
    istnienie wystarcza. Brak rekurencji (create Jednostki nie tworzy Wydziału).
    """
    from bpp.models.jednostka import Jednostka
    from bpp.models.rodzaj_jednostki import RodzajJednostki

    existing = Jednostka.objects.filter(legacy_wydzial_id=wydzial.id).first()
    if existing is not None:
        return existing, False

    rodzaj_wydzial, _ = RodzajJednostki.objects.get_or_create(nazwa="Wydział")

    nazwa = _bez_kolizji(Jednostka, "nazwa", wydzial.nazwa, 512, f" [W{wydzial.id}]")
    skrot = _bez_kolizji(Jednostka, "skrot", wydzial.skrot, 128, f"-W{wydzial.id}")
    skrot_nazwy = _bez_kolizji(
        Jednostka, "skrot_nazwy", wydzial.skrot_nazwy, 250, f"-W{wydzial.id}"
    )

    jednostka = Jednostka.objects.create(
        nazwa=nazwa,
        skrot=skrot,
        skrot_nazwy=skrot_nazwy,
        opis=wydzial.opis,
        adnotacje=wydzial.adnotacje,
        poprzednie_nazwy=wydzial.poprzednie_nazwy,
        pbn_id=wydzial.pbn_id,
        uczelnia=wydzial.uczelnia,
        rodzaj=rodzaj_wydzial,
        legacy_wydzial_id=wydzial.id,
        parent=None,
        # IV-1 (#438): węzeł-lustro dziedziczy widoczność ze źródłowego
        # Wydziału (spójnie z jednorazowym „odkryciem" w migracji 0462) —
        # runtime-tworzony wydział (pbn_import) ma widoczny węzeł, gdy sam
        # jest widoczny. ``aktualna`` zostaje False do czasu, aż węzeł
        # dostanie wpis Jednostka_Rodzic (sygnał zderywuje finalną wartość).
        widoczna=wydzial.widoczny,
        aktualna=False,
        zezwalaj_na_ranking_autorow=wydzial.zezwalaj_na_ranking_autorow,
        pokazuj_opis=wydzial.pokazuj_opis,
        zarzadzaj_automatycznie=wydzial.zarzadzaj_automatycznie,
        kolejnosc=max(0, wydzial.kolejnosc),
    )
    return jednostka, True
