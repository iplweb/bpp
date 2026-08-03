"""Serializacja ``bpp.Autor`` do encji CERIF ``Person``.

Kolejność elementów jest wymuszona przez ``xs:sequence`` w profilu:
``PersonName``, ``Gender``, grupa identyfikatorów osoby, ``ElectronicAddress``,
``Affiliation``.

Provider musi dostarczyć: ``select_related("plec")`` oraz
``prefetch_related("autor_jednostka_set__jednostka")``.
"""

from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst

# `Plec` to słownik ze `skrot`; profil dopuszcza wyłącznie "m" i "f". Każda
# inna wartość (oraz brak płci) oznacza element `Gender` pominięty — CERIF nie
# ma wartości "nieokreślona", a zgadywanie byłoby wpisywaniem nieprawdy.
PLCIE = {"M": "m", "K": "f"}


def dodaj_person_name(el, autor):
    """Dopisz ``PersonName`` (``FamilyNames`` + ``FirstNames``)."""
    nazwisko = tekst(getattr(autor, "nazwisko", None))
    imiona = tekst(getattr(autor, "imiona", None))
    if nazwisko is None and imiona is None:
        return None
    nazwa = dodaj_kontener(el, "PersonName")
    dodaj(nazwa, "FamilyNames", nazwisko)
    dodaj(nazwa, "FirstNames", imiona)
    return nazwa


def dodaj_gender(el, autor):
    """Dopisz ``Gender``, o ile skrót płci daje się zmapować."""
    if getattr(autor, "plec_id", None) is None:
        return None
    plec = autor.plec
    wartosc = PLCIE.get((getattr(plec, "skrot", None) or "").strip().upper())
    return dodaj(el, "Gender", wartosc)


def dodaj_orcid(el, autor):
    """Dopisz ``ORCID``, a gdy wartość nie pasuje do wzorca profilu — ``Identifier``.

    ``Autor.orcid`` trzyma goły identyfikator (``0000-0002-1825-0097``), zaś
    ``ORCID__Type`` wymaga pełnego URI ``https://orcid.org/…`` z zawężonym
    zakresem bloków. Wartość spoza zakresu (np. literówka w bazie) nie może
    trafić do ``<ORCID>``, bo unieważniłaby cały rekord wobec XSD — idzie więc
    do generycznego ``Identifier``, gdzie nic nie ginie.
    """
    surowy = tekst(getattr(autor, "orcid", None))
    if surowy is None:
        return None
    uri = surowy if surowy.startswith("http") else f"https://orcid.org/{surowy}"
    if wspolne.pasuje(wspolne.WZ_ORCID, uri) is not None:
        return dodaj(el, "ORCID", uri)
    return dodaj(el, "Identifier", uri, type=wspolne.TYP_ID_ORCID)


def dodaj_identyfikator_pbn(el, autor):
    """Dopisz ``Identifier`` z UID-em z PBN (bez dotykania tabeli PBN-u)."""
    return dodaj(
        el,
        "Identifier",
        tekst(getattr(autor, "pbn_uid_id", None)),
        type=wspolne.TYP_ID_PBN,
    )


def dodaj_adresy(el, autor):
    """Dopisz ``ElectronicAddress`` — e-mail jako ``mailto:``, WWW jako URL."""
    email = tekst(getattr(autor, "email", None))
    if email:
        dodaj(el, "ElectronicAddress", f"mailto:{email}")
    dodaj(el, "ElectronicAddress", tekst(getattr(autor, "www", None)))


def dodaj_afiliacje(el, autor, ctx):
    """Dopisz ``Affiliation`` dla każdego powiązania autor-jednostka.

    Element ``Person/Affiliation`` ma typ rozszerzający ``cfLink__BaseType``
    z pojedynczym ``OrgUnit`` — bez ``DisplayName`` (inaczej niż afiliacja
    wewnątrz ``Authors/Author``).
    """
    powiazania = getattr(autor, "autor_jednostka_set", None)
    if powiazania is None:
        return
    widziane = set()
    for powiazanie in powiazania.all():
        jednostka = powiazanie.jednostka
        if jednostka is None or jednostka.pk in widziane:
            continue
        widziane.add(jednostka.pk)
        afiliacja = dodaj_kontener(el, "Affiliation")
        wspolne.osadz_orgunit(afiliacja, jednostka, ctx)


def serializuj(autor, ctx):
    """``bpp.Autor`` → element ``Person``."""
    el = element("Person", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, autor, ctx)

    dodaj_person_name(el, autor)
    dodaj_gender(el, autor)
    dodaj_orcid(el, autor)
    dodaj_identyfikator_pbn(el, autor)
    dodaj_adresy(el, autor)
    dodaj_afiliacje(el, autor, ctx)

    return el
