"""Serializacja ``bpp.Jednostka``, ``bpp.Uczelnia`` i
``bpp.Instytucja_Finansujaca`` do encji CERIF ``OrgUnit``.

Wszystkie trzy modele trafiają do setu ``openaire_cris_orgunits`` i mają
w profilu tę samą encję. Jednostka i uczelnia różnią się tylko tym, czy mają
nadrzędną jednostkę; grantodawca jest tu, bo profil nie ma osobnej encji
instytucji finansującej — ``Funding/Funder`` wskazuje na ``OrgUnit``.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Acronym``, ``Name``,
grupa ``OrgUnitIdentifiers__Group``, ``ElectronicAddress``, ``PartOf``.
Wewnątrz grupy identyfikatorów kolejność też jest wymuszona:
``RORID``, ``AlternativeRORID``, ``GRID``, ``AlternativeGRID``, ``ISNI``,
``AlternativeISNI``, ``FundRefID``, ``AlternativeFundRefID`` i dopiero na
końcu generyczny ``Identifier`` (``includes/orgunit-identifiers.xsd``).
Dlatego wartości zapasowe, które nie zmieściły się w dedykowanych
elementach, dopisujemy **po** wszystkich dedykowanych, a nie w miejscu,
w którym powstały.

Profil **nie ma** w sekwencji ``OrgUnit`` elementu ``Country`` —
``Instytucja_Finansujaca.kraj`` zostaje danymi wewnętrznymi.

Provider musi dostarczyć: ``select_related("parent", "uczelnia")`` dla
``Jednostka``.
"""

import re

from bpp.models.projekt import Instytucja_Finansujaca
from bpp.util import ror
from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst

TYP_ID_ROR = "https://w3id.org/cerif/vocab/IdentifierTypes#RORID"
TYP_ID_PBN_INSTYTUCJA = "https://pbn.nauka.gov.pl/core/#/institution"
TYP_ID_FUNDREF = "https://w3id.org/cerif/vocab/IdentifierTypes#FundRefID"

# ``FundRefID__Type`` dopuszcza wyłącznie pełny DOI rejestru Crossrefa
# (``https://doi.org/10.13039/<cyfry>``). W BPP pole trzyma sam numer, bo
# tak podaje go Crossref w wynikach wyszukiwania i tak wpisuje go redakcja —
# prefiks doklejamy tutaj, żeby dane w bazie nie zależały od formatu XML-a.
PREFIKS_FUNDREF = "https://doi.org/10.13039/"
_WZ_FUNDREF_SUROWY = re.compile(
    r"^(?:https?://(?:dx\.)?doi\.org/)?(?:10\.13039/)?(?P<numer>\d+)/?$"
)


def _rozstrzygnij_ror(obj):
    """Zwróć ``(do_RORID, do_Identifier)`` dla surowego pola ``ror_id``.

    ``RORID__Type`` wymaga pełnego ``https://ror.org/<9 znaków>`` z alfabetem
    Crockforda. Redakcja bywa wpisuje sam sufiks albo adres z ukośnikiem na
    końcu — normalizujemy prefiks, a to, co i tak nie pasuje, odkładamy do
    generycznego ``Identifier``, żeby nie unieważnić rekordu wobec XSD.
    """
    surowy = tekst(getattr(obj, "ror_id", None))
    if surowy is None:
        return None, None
    # Normalizacja z `bpp.util.ror` — ta sama, której używa walidacja pola.
    # Ręczne sklejanie prefiksu nie łykało `www.` ani wielkich liter, więc
    # poprawny ROR wpisany w innej postaci lądował w generycznym Identifier.
    uri = ror.normalizuj(surowy)
    if wspolne.pasuje(wspolne.WZ_ROR, uri) is not None:
        return uri, None
    return None, uri


def _rozstrzygnij_fundref(obj):
    """Zwróć ``(do_FundRefID, do_Identifier)`` dla pola ``fundref_id``.

    Akceptujemy sam numer, numer z prefiksem DOI oraz pełny URL (także
    historyczny ``dx.doi.org`` i ``http``) — wszystko sprowadzamy do postaci
    wymaganej przez profil. Wartość, z której nie da się wyłuskać numeru,
    idzie do generycznego ``Identifier``: to nadal informacja, a nie powód,
    żeby unieważnić cały rekord wobec XSD.
    """
    surowy = tekst(getattr(obj, "fundref_id", None))
    if surowy is None:
        return None, None
    dopasowanie = _WZ_FUNDREF_SUROWY.match(surowy)
    if dopasowanie is None:
        return None, surowy
    return PREFIKS_FUNDREF + dopasowanie.group("numer"), None


def dodaj_ror(el, jednostka):
    """Dopisz ``RORID``; wartość spoza wzorca profilu → ``Identifier``."""
    uri, zapasowy = _rozstrzygnij_ror(jednostka)
    if uri is not None:
        return dodaj(el, "RORID", uri)
    return dodaj(el, "Identifier", zapasowy, type=TYP_ID_ROR)


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


def serializuj_grantodawce(instytucja, ctx):
    """``bpp.Instytucja_Finansujaca`` → element ``OrgUnit``.

    Nazwa polska idzie **bez** ``xml:lang``, dokładnie tak, jak wychodzi
    z :func:`cerif_export.cerif.wspolne.osadz_orgunit`. Kontrola 5b
    walidatora wymaga, żeby encja osadzona (``Funding/Funder``,
    ``Project/Funded/By``) była podzbiorem pełnego rekordu — a osadzenie
    jest generyczne i o językach nic nie wie. Oznaczenie języka wyłącznie
    na nazwie angielskiej zachowuje ten podzbiór i nadal jednoznacznie
    mówi, która nazwa jest która.
    """
    el = element("OrgUnit", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, instytucja, ctx)

    dodaj(el, "Acronym", tekst(instytucja.akronim))
    dodaj(el, "Name", tekst(instytucja.nazwa))
    dodaj(el, "Name", tekst(instytucja.nazwa_en), jezyk="en")

    # Kolejność wewnątrz ``OrgUnitIdentifiers__Group``: dedykowane elementy
    # (RORID przed FundRefID), a generyczny ``Identifier`` dopiero po nich.
    ror_uri, ror_zapasowy = _rozstrzygnij_ror(instytucja)
    fundref_uri, fundref_zapasowy = _rozstrzygnij_fundref(instytucja)
    dodaj(el, "RORID", ror_uri)
    dodaj(el, "FundRefID", fundref_uri)
    dodaj(el, "Identifier", ror_zapasowy, type=TYP_ID_ROR)
    dodaj(el, "Identifier", fundref_zapasowy, type=TYP_ID_FUNDREF)

    dodaj(el, "ElectronicAddress", tekst(instytucja.strona_www))

    return el


def serializuj(jednostka, ctx):
    """``Jednostka``, ``Uczelnia`` albo grantodawca → element ``OrgUnit``."""
    if isinstance(jednostka, Instytucja_Finansujaca):
        return serializuj_grantodawce(jednostka, ctx)

    el = element("OrgUnit", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, jednostka, ctx)

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
