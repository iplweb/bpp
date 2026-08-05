"""Serializacja ``bpp.Finansowanie`` do encji CERIF ``Funding``.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Acronym``, ``Name``,
``Amount``, grupa ``FundingIdentifiers__Group`` (``GrantDOI``, potem
generyczny ``Identifier``), ``Description``, ``Subject``, ``Keyword``,
``Funder``, ``PartOf``, ``Duration``, ``OAMandate``.

Jedna funkcja, dwa konteksty
----------------------------

:func:`serializuj` obsługuje naraz rekord setu ``openaire_cris_funding``
i element osadzony w ``Project/Funded/As`` — osadzenie polega na doczepieniu
dokładnie tego samego elementu w innym miejscu drzewa. Kontrola 5b
walidatora (encja osadzona musi być podzbiorem pełnego rekordu) jest wtedy
spełniona trywialnie, bo to jest ten sam element. Z tego samego powodu
``@id`` nadajemy zawsze: finansowanie osadzone w projekcie tej uczelni
wychodzi też jako osobny rekord w secie funding — providery obu setów
filtrują po tym samym warunku (``projekt__jednostka__uczelnia``).

Grantodawca jest **referencją** do ``OrgUnit`` (profil nie ma osobnej encji
instytucji finansującej), a element nazywa się ``Funder`` — nie ``FundedBy``,
jak po stronie projektu.

Prefetche wymagane od providera: ``select_related("instytucja")``.
"""

from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, element, tekst
from cerif_export.slowniki import typy_finansowania

# Typy generycznego ``Identifier``. Element ``GrantDOI`` przyjmuje wyłącznie
# wartości pasujące do ``DOI__SimpleType``; wszystko inne odkładamy do
# generycznego identyfikatora, żeby nie unieważnić rekordu wobec XSD.
TYP_ID_DOI = "https://w3id.org/cerif/vocab/IdentifierTypes#DOI"

# Numer umowy grantowej nie ma w CERIF-ie własnego typu identyfikatora, a
# atrybut ``type`` jest ``xs:anyURI`` i obowiązkowy. Podszycie się pod cudzy
# słownik byłoby fałszywym twierdzeniem o pochodzeniu wartości, więc — jak
# przy ``const.SCHEMAT_*`` — nazywamy własny schemat wprost.
TYP_ID_NUMER_UMOWY = "https://bpp.iplweb.pl/vocab/IdentifierTypes#NumerUmowy"


class NieznanyTypFinansowania(ValueError):
    """``Funding/Type`` nie da się zmapować na słownik profilu.

    ``Type`` jest w sekwencji obowiązkowy, więc rekord bez niego (ale
    z resztą elementów) byłby niepoprawny wobec XSD. Warstwa OAI łapie ten
    wyjątek, zgłasza go do Rollbara i pomija jeden rekord — to jedyna
    reakcja lepsza od wypuszczenia dokumentu, który agregator odrzuci
    w całości.
    """


def dodaj_typ(el, finansowanie):
    """Dopisz obowiązkowy ``Type`` z własnej przestrzeni nazw słownika."""
    uri = typy_finansowania.uri_typu(getattr(finansowanie, "typ", None))
    if uri is None:
        raise NieznanyTypFinansowania(
            f"Finansowanie {finansowanie.pk}: typ "
            f"{getattr(finansowanie, 'typ', None)!r} spoza słownika profilu"
        )
    return dodaj(el, "Type", uri, ns=typy_finansowania.SCHEMAT)


def dodaj_kwote(el, finansowanie, ctx):
    """Dopisz ``Amount`` — tylko za zgodą uczelni i tylko z walutą.

    ``cfAmount__Type`` wymaga atrybutu ``currency``, więc kwota bez waluty
    nie ma jak wyjść poprawnie. Model tego pilnuje w ``clean()``, ale dane
    wgrane importem tę ścieżkę omijają.
    """
    if not ctx.kwoty_dozwolone:
        return None
    kwota = getattr(finansowanie, "kwota", None)
    waluta = tekst(getattr(finansowanie, "waluta", None))
    if kwota is None or not waluta:
        return None
    return dodaj(el, "Amount", f"{kwota}", currency=waluta)


def dodaj_identyfikatory(el, finansowanie):
    """Dopisz ``GrantDOI`` i generyczne ``Identifier`` w kolejności z grupy."""
    doi = tekst(getattr(finansowanie, "grant_doi", None))
    poprawny = wspolne.pasuje(wspolne.WZ_DOI, doi)

    dodaj(el, "GrantDOI", poprawny)
    if doi is not None and poprawny is None:
        dodaj(el, "Identifier", doi, type=TYP_ID_DOI)
    dodaj(
        el,
        "Identifier",
        tekst(getattr(finansowanie, "numer_umowy", None)),
        type=TYP_ID_NUMER_UMOWY,
    )


def dodaj_grantodawce(el, finansowanie, ctx):
    """Dopisz ``Funder`` — referencję do ``OrgUnit`` instytucji finansującej."""
    if getattr(finansowanie, "instytucja_id", None) is None:
        return None
    return wspolne.dodaj_link_do_orgunit(el, "Funder", finansowanie.instytucja, ctx)


def serializuj(finansowanie, ctx):
    """``bpp.Finansowanie`` → element ``Funding``."""
    el = element("Funding", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id_rekordu(el, finansowanie, ctx)

    dodaj_typ(el, finansowanie)
    # ``Acronym`` zostaje pusty: BPP nie ma osobnego pola na skrót
    # finansowania, a wpisanie tam nazwy programu dublowałoby ``Name``.
    dodaj(el, "Name", tekst(getattr(finansowanie, "nazwa_programu", None)))
    dodaj_kwote(el, finansowanie, ctx)
    dodaj_identyfikatory(el, finansowanie)
    dodaj_grantodawce(el, finansowanie, ctx)

    return el
