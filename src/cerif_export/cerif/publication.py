"""Serializacja rekordów bibliograficznych do encji CERIF ``Publication``.

Jeden moduł obsługuje pięć modeli, bo w profilu wszystkie są tą samą encją:

============================  ==========================================
``Wydawnictwo_Ciagle``        artykuł; ``zrodlo`` → ``PublishedIn``
``Wydawnictwo_Zwarte``        książka/rozdział; ``wydawnictwo_nadrzedne``
                              → ``PartOf``
``Praca_Doktorska``           inna struktura autorstwa — patrz niżej
``Praca_Habilitacyjna``       jw.
``Zrodlo``                    kanał wydawniczy (typ *journal*), czyli
                              obiekt wskazywany przez ``PublishedIn``
============================  ==========================================

Prace doktorskie i habilitacyjne mają **pojedyncze FK** ``autor`` i
``promotor`` zamiast ``BazaModeluOdpowiedzialnosciAutorow``. ``autor`` daje
jedynego ``Authors/Author``; ``promotor`` jest **pomijany** — CERIF nie zna
roli promotora, a wpisanie go jako współautora byłoby nieprawdą.

Kolejność elementów jest wymuszona przez ``xs:sequence`` profilu; funkcje
``dodaj_*`` wołane są dokładnie w tej kolejności w :func:`serializuj`.

Prefetche wymagane od providera
-------------------------------

``select_related``: ``charakter_formalny``, ``jezyk``, ``zrodlo``
(+ ``zrodlo__jezyk``), ``wydawnictwo_nadrzedne``
(+ ``wydawnictwo_nadrzedne__charakter_formalny``), ``konferencja``,
``openaccess_licencja``, ``openaccess_tryb_dostepu``, a dla prac
doktorskich/habilitacyjnych ``autor`` i ``jednostka``.

``prefetch_related``: ``autorzy_set__autor``, ``autorzy_set__jednostka``,
``autorzy_set__typ_odpowiedzialnosci``, ``dodatkowe_tytuly__jezyk``,
``streszczenia__jezyk_streszczenia``, ``slowa_kluczowe``.
"""

import datetime

from bpp import const as bpp_const
from cerif_export import const, identyfikatory
from cerif_export.cerif import event as event_cerif
from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst
from cerif_export.slowniki import coar, dostep, jezyki, licencje

# Slugi z `identyfikatory` — po nich rozpoznajemy, z którym z pięciu modeli
# mamy do czynienia. Rozpoznawanie po klasie wymagałoby importu modeli BPP
# do modułu, który ma być czystą funkcją obiektu.
SLUG_ZRODLO = "zr"
SLUGI_PRAC = frozenset({"pd", "ph"})


def _slug(obj):
    return identyfikatory.slug_dla(obj)


# -- typ, język ----------------------------------------------------------


def typ_coar(obj, slug):
    """URI typu COAR dla rekordu. ``Publication/Type`` jest obowiązkowy."""
    if slug == SLUG_ZRODLO:
        return coar.JOURNAL

    if slug in SLUGI_PRAC:
        # Provider podaje gotowy URI — patrz `wspolne.ATRYBUT_TYP_COAR`.
        # Fallback ze słownika, gdy provider go nie podwiesił.
        gotowy = getattr(obj, wspolne.ATRYBUT_TYP_COAR, None)
        if gotowy:
            return gotowy
        return coar.DOCTORAL_THESIS if slug == "pd" else coar.THESIS

    charakter = obj.charakter_formalny if obj.charakter_formalny_id else None
    return coar.typ_publikacji(getattr(charakter, "coar_type", None))


def kod_jezyka(obj):
    """Kod BCP 47 języka rekordu albo ``None``."""
    if getattr(obj, "jezyk_id", None) is None:
        return None
    return jezyki.kod_jezyka(obj.jezyk)


def dodaj_typ(el, obj, slug):
    """Dopisz ``Type`` z przestrzeni nazw słownika COAR dla publikacji."""
    return dodaj(el, "Type", typ_coar(obj, slug), ns=const.NS_COAR_PUBLICATION_TYPES)


# -- tytuły --------------------------------------------------------------


def dodaj_tytuly(el, obj, slug, jezyk):
    """Dopisz ``Title`` — oryginalny plus tytuły w pozostałych językach."""
    if slug == SLUG_ZRODLO:
        dodaj(el, "Title", tekst(obj.nazwa))
        return

    dodaj(el, "Title", tekst(obj.tytul_oryginalny), jezyk=jezyk)

    dodatkowe = getattr(obj, "dodatkowe_tytuly", None)
    if dodatkowe is None:
        return
    for wiersz in dodatkowe.all():
        kod = None
        if wiersz.jezyk_id is not None:
            kod = jezyki.kod_jezyka(wiersz.jezyk)
        kod = kod or tekst(wiersz.kod_jezyka_pbn)
        dodaj(el, "Title", tekst(wiersz.tytul), jezyk=kod)


def dodaj_skrot_nazwy(el, obj, slug):
    """Dopisz ``NameAbbreviation`` — tylko dla kanału wydawniczego."""
    if slug != SLUG_ZRODLO:
        return None
    return dodaj(el, "NameAbbreviation", tekst(obj.skrot))


# -- powiązania z innymi publikacjami ------------------------------------


def osadz_publikacje(rodzic, obj, ctx):
    """Dopisz skrócony ``Publication`` (``Type`` + ``Title`` + ``ISSN``).

    Kontrola 5b walidatora wymaga, żeby osadzona encja była podzbiorem swojego
    pełnego rekordu, więc każdy element budujemy tą samą funkcją co rekord.
    """
    slug = _slug(obj)
    el = element("Publication")
    wspolne.ustaw_id(el, obj, ctx)
    dodaj_typ(el, obj, slug)
    dodaj_tytuly(el, obj, slug, kod_jezyka(obj))
    dodaj_skrot_nazwy(el, obj, slug)
    dodaj_issn(el, obj)
    rodzic.append(el)
    return el


def dodaj_published_in(el, obj, ctx):
    """Dopisz ``PublishedIn`` wskazujące na źródło (kanał wydawniczy)."""
    if getattr(obj, "zrodlo_id", None) is None:
        return None
    kontener = dodaj_kontener(el, "PublishedIn")
    osadz_publikacje(kontener, obj.zrodlo, ctx)
    return kontener


def dodaj_part_of(el, obj, ctx):
    """Dopisz ``PartOf`` wskazujące na wydawnictwo nadrzędne."""
    if getattr(obj, "wydawnictwo_nadrzedne_id", None) is None:
        return None
    kontener = dodaj_kontener(el, "PartOf")
    osadz_publikacje(kontener, obj.wydawnictwo_nadrzedne, ctx)
    return kontener


# -- opis wydawniczy -----------------------------------------------------


def dodaj_opis_wydawniczy(el, obj):
    """Dopisz ``PublicationDate``, ``Volume``, ``Issue``, ``StartPage``/``EndPage``."""
    dodaj(el, "PublicationDate", wspolne.rok_iso(getattr(obj, "rok", None)))
    dodaj(el, "Volume", tekst(getattr(obj, "tom", None)))
    dodaj(el, "Issue", tekst(getattr(obj, "nr_zeszytu", None)))

    poczatek, koniec = wspolne.rozbij_strony(getattr(obj, "strony", None))
    dodaj(el, "StartPage", poczatek)
    dodaj(el, "EndPage", koniec)


# -- identyfikatory ------------------------------------------------------


def dodaj_issn(el, obj):
    """Dopisz ``ISSN`` (drukowany i elektroniczny), o ile pasują do wzorca."""
    for pole in ("issn", "e_issn"):
        wartosc = wspolne.pasuje(wspolne.WZ_ISSN, tekst(getattr(obj, pole, None)))
        dodaj(el, "ISSN", wartosc)


def dodaj_identyfikatory(el, obj):
    """Dopisz grupę ``PublicationIdentifiers`` w kolejności ze schematu.

    Wartości niepasujące do wzorców profilu (``DOI__SimpleType``,
    ``ISSN__SimpleType``, ``ISBN__SimpleType``) są **pomijane**: grupa nie ma
    generycznego ``Identifier``, do którego dałoby się je odłożyć, a wpisanie
    ich wprost unieważniłoby cały rekord wobec XSD.
    """
    dodaj(el, "DOI", wspolne.pasuje(wspolne.WZ_DOI, tekst(getattr(obj, "doi", None))))
    dodaj(el, "PMCID", tekst(getattr(obj, "pmc_id", None)))
    dodaj_issn(el, obj)
    for pole in ("isbn", "e_isbn"):
        dodaj(el, "ISBN", wspolne.poprawny_isbn(tekst(getattr(obj, pole, None))))
    dodaj(el, "URL", tekst(getattr(obj, "www", None)))


# -- autorstwo -----------------------------------------------------------


def dodaj_autorstwo(el, obj, slug, ctx):
    """Dopisz ``Authors`` i ``Editors``.

    Prace doktorskie/habilitacyjne mają pojedyncze FK ``autor``; ``promotor``
    jest świadomie pomijany (patrz docstring modułu).
    """
    if slug in SLUGI_PRAC:
        return _autorstwo_pracy(el, obj, ctx)
    if slug == SLUG_ZRODLO:
        return None
    return _autorstwo_z_odpowiedzialnosci(el, obj, ctx)


def _autorstwo_pracy(el, obj, ctx):
    if getattr(obj, "autor_id", None) is None:
        return None
    autorzy = dodaj_kontener(el, "Authors")
    autor = obj.autor
    jednostka = obj.jednostka if getattr(obj, "jednostka_id", None) else None
    wspolne.dodaj_wklad_osoby(
        autorzy,
        "Author",
        autor,
        ctx,
        nazwa_wyswietlana=f"{autor.nazwisko or ''} {autor.imiona or ''}",
        jednostka=jednostka,
    )
    return autorzy


def _autorstwo_z_odpowiedzialnosci(el, obj, ctx):
    powiazania = getattr(obj, "autorzy_set", None)
    if powiazania is None:
        return None

    autorzy_rekordu = []
    redaktorzy_rekordu = []
    for powiazanie in powiazania.all():
        typ = powiazanie.typ_odpowiedzialnosci
        if getattr(typ, "typ_ogolny", None) == bpp_const.TO_REDAKTOR:
            redaktorzy_rekordu.append(powiazanie)
        else:
            autorzy_rekordu.append(powiazanie)

    for nazwa_kontenera, nazwa_wkladu, lista in (
        ("Authors", "Author", autorzy_rekordu),
        ("Editors", "Editor", redaktorzy_rekordu),
    ):
        if not lista:
            continue
        kontener = dodaj_kontener(el, nazwa_kontenera)
        for powiazanie in lista:
            wspolne.dodaj_wklad_osoby(
                kontener,
                nazwa_wkladu,
                powiazanie.autor,
                ctx,
                nazwa_wyswietlana=powiazanie.zapisany_jako,
                jednostka=(powiazanie.jednostka if powiazanie.jednostka_id else None),
            )


# -- licencja, streszczenia, konferencja, dostęp -------------------------


def dodaj_licencje(el, obj):
    """Dopisz ``License`` z URI licencji Open Access."""
    if getattr(obj, "openaccess_licencja_id", None) is None:
        return None
    uri = licencje.uri_licencji(obj.openaccess_licencja)
    if not uri:
        return None
    return dodaj(el, "License", uri, scheme=wspolne.schemat_licencji(uri))


def dodaj_streszczenia(el, obj):
    """Dopisz ``Abstract`` dla każdego streszczenia rekordu."""
    streszczenia = getattr(obj, "streszczenia", None)
    if streszczenia is None:
        return
    for wiersz in streszczenia.all():
        kod = None
        if wiersz.jezyk_streszczenia_id is not None:
            kod = jezyki.kod_jezyka(wiersz.jezyk_streszczenia)
        dodaj(el, "Abstract", tekst(wiersz.streszczenie), jezyk=kod)


def dodaj_konferencje(el, obj, ctx):
    """Dopisz ``PresentedAt`` wskazujące na konferencję."""
    if getattr(obj, "konferencja_id", None) is None:
        return None
    kontener = dodaj_kontener(el, "PresentedAt")
    kontener.append(event_cerif.serializuj(obj.konferencja, ctx))
    return kontener


#: Skrót czasu udostępnienia oznaczający embargo (``Czas_Udostepnienia_OpenAccess``).
CZAS_PO_OPUBLIKOWANIU = "AFTER_PUBLICATION"


def _pod_embargiem(obj, dzisiaj=None):
    """Czy praca jest jeszcze pod embargiem?

    BPP trzyma embargo OSOBNO od trybu dostępu:
    ``openaccess_czas_publikacji`` mówi „po opublikowaniu", a
    ``openaccess_ilosc_miesiecy`` — po ilu. Sam tryb (``OPEN_JOURNAL``,
    ``OPEN_REPOSITORY``) mówi tylko GDZIE praca będzie otwarta, nie KIEDY.

    Gdy nie da się ustalić, czy embargo minęło, zwracamy ``True``. Lepiej
    zaniżyć otwartość, niż powiedzieć agregatorowi „open access" o pracy,
    której nikt nie może pobrać — to drugie kończy się zgłoszeniem od
    użytkownika OpenAIRE, a nie tylko brakiem punktu w statystyce.
    """
    czas = getattr(obj, "openaccess_czas_publikacji", None)
    if czas is None or getattr(czas, "skrot", None) != CZAS_PO_OPUBLIKOWANIU:
        return False

    miesiecy = getattr(obj, "openaccess_ilosc_miesiecy", None)
    if not miesiecy:
        # „Po opublikowaniu", ale nie wiadomo po ilu miesiącach.
        return True

    data = getattr(obj, "openaccess_data_opublikowania", None)
    if data is None:
        return True

    dzisiaj = dzisiaj or datetime.date.today()
    koniec = data + datetime.timedelta(days=int(miesiecy) * 30)
    return dzisiaj < koniec


def dodaj_dostep(el, obj):
    """Dopisz ``Access`` (COAR Access Rights) z trybu dostępu Open Access.

    ``Zrodlo.openaccess_tryb_dostepu`` to zwykły ``CharField`` (``FULL`` /
    ``PARTIAL``), a nie FK do słownika — dlatego sprawdzamy pole ``*_id``,
    które istnieje tylko na wydawnictwach.

    Tryb dostępu sam w sobie NIE wystarcza: praca w otwartym czasopiśmie,
    ale z embargiem, jest w tej chwili niedostępna i profil ma na to osobny
    termin (``embargoed access``).
    """
    if getattr(obj, "openaccess_tryb_dostepu_id", None) is None:
        return None
    uri = dostep.prawo_dostepu(obj.openaccess_tryb_dostepu)
    if not uri:
        return None
    if uri == dostep.OPEN and _pod_embargiem(obj):
        uri = dostep.EMBARGOED
    return dodaj(el, "Access", uri, ns=const.NS_COAR_ACCESS)


# -- wejście -------------------------------------------------------------


def serializuj(obj, ctx):
    """Rekord bibliograficzny albo ``bpp.Zrodlo`` → element ``Publication``."""
    slug = _slug(obj)
    jezyk = kod_jezyka(obj)

    el = element("Publication", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, obj, ctx)

    dodaj_typ(el, obj, slug)
    dodaj(el, "Language", jezyk)
    dodaj_tytuly(el, obj, slug, jezyk)
    dodaj_skrot_nazwy(el, obj, slug)
    dodaj_published_in(el, obj, ctx)
    dodaj_part_of(el, obj, ctx)
    dodaj_opis_wydawniczy(el, obj)
    dodaj_identyfikatory(el, obj)
    dodaj_autorstwo(el, obj, slug, ctx)
    dodaj_licencje(el, obj)
    wspolne.dodaj_slowa_kluczowe(el, obj)
    dodaj_streszczenia(el, obj)
    dodaj_konferencje(el, obj, ctx)
    dodaj_dostep(el, obj)
    wspolne.dodaj_pliki(el, obj)

    return el
