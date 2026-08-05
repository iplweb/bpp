"""Serializacja ``bpp.Projekt`` do encji CERIF ``Project``.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Acronym``, ``Title``,
``Identifier``, ``StartDate``, ``EndDate``, ``Consortium``, ``Team``,
``Funded``, ``Subject``, ``Keyword``, ``Abstract``, ``Status``, ``Uses``,
``OAMandate``.

Czego świadomie nie wystawiamy
------------------------------

``Type`` — profil oczekuje tu ``cfGenericURIClassification__Type``
z atrybutem ``scheme``, a BPP nie prowadzi typologii projektów
(badawczy/wdrożeniowy/infrastrukturalny). Wymyślenie własnej i wpisanie
wszystkim tej samej wartości byłoby twierdzeniem bez pokrycia w danych.

``Projekt.strona_www`` — sekwencja ``Project`` nie ma elementu na adres
strony, a wciśnięcie URL-a do generycznego ``Identifier`` mówiłoby, że to
identyfikator projektu, czym adres strony nie jest.

Afiliacje osób z ``Team`` — ``Projekt_Autor`` nie niesie jednostki, a
podstawienie ``Projekt.jednostka`` twierdziłoby, że każdy członek zespołu
pracuje w jednostce realizującej. Bywa nieprawdą przy projektach
międzyjednostkowych, więc ``Affiliation`` zostaje puste.

Referencje wychodzące
---------------------

``Consortium/Coordinator`` (jednostka realizująca) i ``Funded/By``
(grantodawca) są **referencjami** do ``OrgUnit``; ``Funded/As`` niesie
**osadzone pełne** ``<Funding>``. ``Team`` powstaje wyłącznie wtedy, gdy
osoby są widoczne w harveście — przy ``Uczelnia.eksport_cerif_osoby=False``
referencja do ``Person`` byłaby wisząca, a to najboleśniejsza klasa błędu
w kontroli integralności referencyjnej walidatora.

Prefetche wymagane od providera: ``select_related("jednostka")``,
``prefetch_related("projekt_autor_set__autor", "finansowanie_set__instytucja",
"dyscypliny", "slowa_kluczowe")``.
"""

from bpp.models.projekt import Projekt_Autor
from cerif_export import const
from cerif_export.cerif import funding as cerif_funding
from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst


def dodaj_tytuly(el, projekt):
    """Dopisz ``Title`` w obu językach (``cfMLangString__Type``)."""
    dodaj(el, "Title", tekst(getattr(projekt, "tytul", None)), jezyk="pl")
    dodaj(el, "Title", tekst(getattr(projekt, "tytul_en", None)), jezyk="en")


def dodaj_daty(el, projekt):
    """Dopisz ``StartDate`` i ``EndDate``."""
    dodaj(el, "StartDate", wspolne.data_iso(getattr(projekt, "data_rozpoczecia", None)))
    dodaj(el, "EndDate", wspolne.data_iso(getattr(projekt, "data_zakonczenia", None)))


def dodaj_konsorcjum(el, projekt, ctx):
    """Dopisz ``Consortium`` z jednostką realizującą jako ``Coordinator``.

    Kontener powstaje dopiero razem z koordynatorem: pusty ``<Consortium/>``
    nie niesie żadnej informacji, a jednostka spoza zbioru widoczności nie
    ma prawa się w nim pojawić nawet samą nazwą.
    """
    if getattr(projekt, "jednostka_id", None) is None:
        return None
    if not wspolne.jednostka_ujawnialna(projekt.jednostka, ctx):
        return None

    konsorcjum = dodaj_kontener(el, "Consortium")
    wspolne.dodaj_link_do_orgunit(konsorcjum, "Coordinator", projekt.jednostka, ctx)
    return konsorcjum


def _nazwa_wyswietlana(autor):
    return " ".join(
        czlon
        for czlon in (
            getattr(autor, "nazwisko", None),
            getattr(autor, "imiona", None),
        )
        if czlon
    )


def dodaj_zespol(el, projekt, ctx):
    """Dopisz ``Team`` — kierownik jako ``PrincipalInvestigator``, reszta
    jako ``Member``.

    Do zespołu wchodzą wyłącznie osoby, które faktycznie wyjdą w secie
    ``openaire_cris_persons`` (``ctx.id_dla`` zwraca identyfikator). Osoba
    z ``pokazuj=False`` albo cała lista przy wyłączonym
    ``eksport_cerif_osoby`` znika bez śladu — razem z kontenerem, żeby nie
    zostawiać pustego ``<Team/>``.
    """
    powiazania = getattr(projekt, "projekt_autor_set", None)
    if powiazania is None:
        return None

    kierownicy, czlonkowie = [], []
    for powiazanie in powiazania.all():
        if powiazanie.autor_id is None:
            continue
        if ctx.id_dla(powiazanie.autor) is None:
            continue
        if powiazanie.rola == Projekt_Autor.ROLA_KIEROWNIK:
            kierownicy.append(powiazanie)
        else:
            czlonkowie.append(powiazanie)

    if not kierownicy and not czlonkowie:
        return None

    # ``xs:sequence`` w ``Team``: PrincipalInvestigator, Contact, Member.
    zespol = dodaj_kontener(el, "Team")
    for nazwa, lista in (
        ("PrincipalInvestigator", kierownicy),
        ("Member", czlonkowie),
    ):
        for powiazanie in lista:
            wspolne.dodaj_wklad_osoby(
                zespol,
                nazwa,
                powiazanie.autor,
                ctx,
                nazwa_wyswietlana=_nazwa_wyswietlana(powiazanie.autor),
            )
    return zespol


def dodaj_finansowania(el, projekt, ctx):
    """Dopisz po jednym ``Funded`` na każde źródło finansowania.

    ``By`` to referencja do ``OrgUnit`` grantodawcy, ``As`` to osadzone
    pełne ``<Funding>`` — dwie różne rzeczy w jednym kontenerze. Kontener
    powstaje nawet wtedy, gdy grantodawca jest niewidoczny: samo
    ``Funding`` (typ, nazwa programu, numer umowy) nadal niesie treść.
    """
    finansowania = getattr(projekt, "finansowanie_set", None)
    if finansowania is None:
        return

    for finansowanie in finansowania.all():
        kontener = dodaj_kontener(el, "Funded")
        if finansowanie.instytucja_id is not None:
            wspolne.dodaj_link_do_orgunit(kontener, "By", finansowanie.instytucja, ctx)
        osadzenie = dodaj_kontener(kontener, "As")
        osadzenie.append(cerif_funding.serializuj(finansowanie, ctx))


def dodaj_dyscypliny(el, projekt):
    """Dopisz ``Subject`` dla każdej dyscypliny naukowej.

    ``cfGenericURIClassification__Type`` wymaga URI wartości i atrybutu
    ``scheme``. Profil nie zna polskiej klasyfikacji dyscyplin, więc URI
    budujemy we własnym schemacie (``const.SCHEMAT_DYSCYPLIN``) — jawnie
    nazwane pochodzenie jest lepsze i od pominięcia danych, i od podszycia
    się pod cudzy słownik.
    """
    dyscypliny = getattr(projekt, "dyscypliny", None)
    if dyscypliny is None:
        return
    for dyscyplina in dyscypliny.all():
        kod = tekst(getattr(dyscyplina, "kod", None))
        if kod is None:
            continue
        dodaj(
            el,
            "Subject",
            f"{const.SCHEMAT_DYSCYPLIN}/{kod}",
            scheme=const.SCHEMAT_DYSCYPLIN,
        )


def dodaj_abstrakty(el, projekt):
    """Dopisz ``Abstract`` w obu językach.

    ``Project/Abstract`` to ``cfMLangAnyMixed__Type``, w którym ``xml:lang``
    jest **wymagany** — inaczej niż w abstraktach publikacji
    (``cfMLangString__Type``). Dlatego oba wywołania podają język na sztywno:
    treść pól rozstrzyga o nim jednoznacznie.
    """
    dodaj(el, "Abstract", tekst(getattr(projekt, "abstrakt", None)), jezyk="pl")
    dodaj(el, "Abstract", tekst(getattr(projekt, "abstrakt_en", None)), jezyk="en")


def dodaj_status(el, projekt):
    """Dopisz ``Status`` jako URI we własnym schemacie klasyfikacji."""
    status = tekst(getattr(projekt, "status", None))
    if status is None:
        return None
    return dodaj(
        el,
        "Status",
        f"{const.SCHEMAT_STATUSU_PROJEKTU}/{status}",
        scheme=const.SCHEMAT_STATUSU_PROJEKTU,
    )


def serializuj(projekt, ctx):
    """``bpp.Projekt`` → element ``Project``."""
    el = element("Project", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, projekt, ctx)

    dodaj(el, "Acronym", tekst(getattr(projekt, "akronim", None)))
    dodaj_tytuly(el, projekt)
    dodaj_daty(el, projekt)
    dodaj_konsorcjum(el, projekt, ctx)
    dodaj_zespol(el, projekt, ctx)
    dodaj_finansowania(el, projekt, ctx)
    dodaj_dyscypliny(el, projekt)
    wspolne.dodaj_slowa_kluczowe(el, projekt)
    dodaj_abstrakty(el, projekt)
    dodaj_status(el, projekt)

    return el
