"""Serializacja ``bpp.Konferencja`` do encji CERIF ``Event``.

Kolejność wymuszona przez ``xs:sequence``: ``Type``, ``Acronym``, ``Name``,
``Place``, ``Country``, ``StartDate``, ``EndDate``, ``Description``,
``Subject``, ``Keyword``, ``Organizer``, ``Sponsor``, ``Partner``.

Konferencja nie ma w BPP żadnej relacji do uczelni ani pól organizatora, więc
wychodzą wyłącznie pola opisowe. ``Event`` nie wymaga w profilu ani typu, ani
nazwy — pusty ``<Event/>`` też jest poprawny.
"""

from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, element, tekst


def serializuj(konferencja, ctx):
    """``bpp.Konferencja`` → element ``Event``."""
    el = element("Event", nsmap=wspolne.NSMAP_REKORDU)
    wspolne.ustaw_id(el, konferencja, ctx)

    dodaj(el, "Acronym", tekst(getattr(konferencja, "skrocona_nazwa", None)))
    dodaj(el, "Name", tekst(getattr(konferencja, "nazwa", None)))
    dodaj(el, "Place", tekst(getattr(konferencja, "miasto", None)))
    # `Country` odwzorowuje `Event.CountryCode`, ale schemat to zwykły
    # `cfString__Type` bez słownika, a BPP trzyma tu nazwę państwa wpisaną
    # ręcznie ("Polska"). Przepisujemy wprost — mapowanie na ISO 3166 wymaga
    # słownika, którego w BPP nie ma, a zgadywanie byłoby wpisywaniem nieprawdy.
    dodaj(el, "Country", tekst(getattr(konferencja, "panstwo", None)))
    dodaj(el, "StartDate", wspolne.data_iso(getattr(konferencja, "rozpoczecie", None)))
    dodaj(el, "EndDate", wspolne.data_iso(getattr(konferencja, "zakonczenie", None)))

    return el
