"""Serializacja ``bpp.Jednostka`` i ``bpp.Uczelnia`` do encji CERIF ``OrgUnit``.

Oba modele trafiają do setu ``openaire_cris_orgunits`` i mają w profilu tę samą
encję — różnią się tylko tym, czy mają nadrzędną jednostkę.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Acronym``, ``Name``,
grupa identyfikatorów jednostki, ``ElectronicAddress``, ``PartOf``.

Provider musi dostarczyć: ``select_related("parent", "uczelnia")`` dla
``Jednostka``.
"""

from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst

TYP_ID_ROR = "https://w3id.org/cerif/vocab/IdentifierTypes#RORID"
TYP_ID_PBN_INSTYTUCJA = "https://pbn.nauka.gov.pl/core/#/institution"


def dodaj_ror(el, jednostka):
    """Dopisz ``RORID``; wartość spoza wzorca profilu → ``Identifier``.

    ``RORID__Type`` wymaga pełnego ``https://ror.org/<9 znaków>`` z alfabetem
    Crockforda. Redakcja bywa wpisuje sam sufiks albo adres z ukośnikiem na
    końcu — normalizujemy prefiks, a to, co i tak nie pasuje, odkładamy do
    generycznego ``Identifier``, żeby nie unieważnić rekordu wobec XSD.
    """
    surowy = tekst(getattr(jednostka, "ror_id", None))
    if surowy is None:
        return None
    uri = surowy if surowy.startswith("http") else f"https://ror.org/{surowy}"
    uri = uri.rstrip("/")
    if wspolne.pasuje(wspolne.WZ_ROR, uri) is not None:
        return dodaj(el, "RORID", uri)
    return dodaj(el, "Identifier", uri, type=TYP_ID_ROR)


def dodaj_identyfikator_pbn(el, jednostka):
    """Dopisz ``Identifier`` z UID-em z PBN (bez dotykania tabeli PBN-u)."""
    return dodaj(
        el,
        "Identifier",
        tekst(getattr(jednostka, "pbn_uid_id", None)),
        type=TYP_ID_PBN_INSTYTUCJA,
    )


def dodaj_adresy(el, jednostka):
    """Dopisz ``ElectronicAddress`` — e-mail jako ``mailto:``, WWW jako URL."""
    email = tekst(getattr(jednostka, "email", None))
    if email:
        dodaj(el, "ElectronicAddress", f"mailto:{email}")
    dodaj(el, "ElectronicAddress", tekst(getattr(jednostka, "www", None)))


def _nadrzedna(jednostka):
    """Jednostka nadrzędna: rodzic w drzewie MPTT, a w korzeniu — uczelnia.

    Bez podpięcia korzeni pod uczelnię drzewo organizacyjne w OpenAIRE
    rozpadłoby się na niepowiązane wydziały.
    """
    if getattr(jednostka, "parent_id", None):
        return jednostka.parent
    if getattr(jednostka, "uczelnia_id", None):
        return jednostka.uczelnia
    return None


def dodaj_part_of(el, jednostka, ctx):
    """Dopisz ``PartOf`` wskazujące na jednostkę nadrzędną."""
    nadrzedna = _nadrzedna(jednostka)
    if nadrzedna is None:
        return None
    part_of = dodaj_kontener(el, "PartOf")
    wspolne.osadz_orgunit(part_of, nadrzedna, ctx)
    return part_of


def serializuj(jednostka, ctx):
    """``bpp.Jednostka`` albo ``bpp.Uczelnia`` → element ``OrgUnit``."""
    el = element("OrgUnit", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id(el, jednostka, ctx)

    # Acronym + Name budowane tak samo jak w `wspolne.osadz_orgunit` —
    # osadzona encja musi być podzbiorem pełnego rekordu (kontrola 5b
    # walidatora), więc te dwa elementy muszą wychodzić identycznie.
    dodaj(el, "Acronym", tekst(getattr(jednostka, "skrot", None)))
    dodaj(el, "Name", tekst(getattr(jednostka, "nazwa", None)))

    dodaj_ror(el, jednostka)
    dodaj_identyfikator_pbn(el, jednostka)
    dodaj_adresy(el, jednostka)
    dodaj_part_of(el, jednostka, ctx)

    return el
