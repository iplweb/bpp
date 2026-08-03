"""Serializacja opisu samego CRIS-a do encji CERIF ``Service``.

Jeden rekord na instalację, zwracany w ``<description>`` odpowiedzi
``Identify`` — nie należy do żadnego setu i nie ma własnego identyfikatora
OAI-PMH.

``Acronym`` **musi** być równy identyfikatorowi repozytorium
(``Uczelnia.oai_repository_identifier()``, czyli ``ctx.namespace``) — tego
wprost pilnuje ``openaire-cris-validator`` (kontrola 1c: „Service acronym is
not the same as the repository identifier").

Kolejność wymuszona przez ``xs:sequence``: ``Compatibility``, ``Acronym``,
``Name``, ``Identifier``, ``Description``, ``WebsiteURL``, ``OAIPMHBaseURL``,
``SubjectHeadingsURL``, ``Owner``.
"""

from cerif_export.cerif import wspolne
from cerif_export.cerif.wspolne import dodaj, dodaj_kontener, element, tekst

# Identyfikator serwisu jest lokalny — nie ma rekordu w żadnym secie, więc
# `ctx.id_dla` nie ma czego sprawdzić i identyfikator budujemy wprost.
ID_SERWISU = "Services/cris"


def serializuj(uczelnia, ctx, base_url=None, www_url=None):
    """``bpp.Uczelnia`` → element ``Service``.

    ``base_url`` (URL endpointu OAI-PMH) i ``www_url`` (adres serwisu) zna
    warstwa HTTP, nie provider — dlatego są parametrami opcjonalnymi, a nie
    polami kontekstu. Gdy ich nie podano, odpowiednie elementy nie powstają.
    """
    el = element("Service", nsmap=wspolne.NSMAP_REKORDU)
    el.set("id", ID_SERWISU)

    dodaj(el, "Acronym", ctx.namespace)
    dodaj(el, "Name", tekst(getattr(uczelnia, "nazwa", None)))
    dodaj(el, "WebsiteURL", tekst(www_url))
    dodaj(el, "OAIPMHBaseURL", tekst(base_url))

    wlasciciel = dodaj_kontener(el, "Owner")
    wspolne.osadz_orgunit(wlasciciel, uczelnia, ctx)

    return el
