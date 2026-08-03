"""Serializacja ``bpp.Patent`` do encji CERIF ``Patent``.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Title``,
``RegistrationDate``, ``ApprovalDate``, ``PatentNumber``, grupa
identyfikatorów patentu (``URL``), ``Inventors``, ``Keyword``,
``FileLocations``.

Provider musi dostarczyć: ``select_related("rodzaj_prawa")`` oraz
``prefetch_related("autorzy_set__autor", "autorzy_set__jednostka",
"slowa_kluczowe")``.
"""

from cerif_export import const
from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst
from cerif_export.slowniki import coar


def typ_coar(patent):
    """URI typu COAR patentu. ``Patent/Type`` jest w profilu obowiązkowy.

    ``Patent.rodzaj_prawa`` jest ``null=True`` — brak rodzaju traktujemy tak
    samo jak rodzaj bez mapowania, czyli oddajemy ``None`` do słownika, który
    zwróci korzeń gałęzi patentów.
    """
    rodzaj = patent.rodzaj_prawa if patent.rodzaj_prawa_id else None
    return coar.typ_patentu(getattr(rodzaj, "coar_type", None))


def dodaj_wynalazcow(el, patent, ctx):
    """Dopisz ``Inventors`` z powiązań ``Patent_Autor`` (w kolejności)."""
    powiazania = getattr(patent, "autorzy_set", None)
    if powiazania is None:
        return None
    lista = list(powiazania.all())
    if not lista:
        return None

    kontener = dodaj_kontener(el, "Inventors")
    for powiazanie in lista:
        wspolne.dodaj_wklad_osoby(
            kontener,
            "Inventor",
            powiazanie.autor,
            ctx,
            nazwa_wyswietlana=powiazanie.zapisany_jako,
            jednostka=powiazanie.jednostka if powiazanie.jednostka_id else None,
        )
    return kontener


def serializuj(patent, ctx):
    """``bpp.Patent`` → element ``Patent``."""
    el = element("Patent", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id(el, patent, ctx)

    dodaj(el, "Type", typ_coar(patent), ns=const.NS_COAR_PATENT_TYPES)
    dodaj(el, "Title", tekst(patent.tytul_oryginalny))
    dodaj(el, "RegistrationDate", wspolne.data_iso(patent.data_zgloszenia))
    dodaj(el, "ApprovalDate", wspolne.data_iso(patent.data_decyzji))
    dodaj(el, "PatentNumber", tekst(patent.numer_prawa_wylacznego))
    dodaj(el, "URL", tekst(getattr(patent, "www", None)))
    dodaj_wynalazcow(el, patent, ctx)
    wspolne.dodaj_slowa_kluczowe(el, patent)
    wspolne.dodaj_pliki(el, patent)

    return el
