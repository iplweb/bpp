"""Identyfikatory OAI-PMH dla eksportu CERIF.

Format: ``oai:{namespace}:{Typ}/{slug}-{pk}``

``namespace`` pochodzi z :meth:`Uczelnia.oai_repository_identifier`, a nie
z literału — patrz spec, sekcja o zależności od gałęzi
``fix/oai-identyfikator-repozytorium``.

Slug jest jawny i stały, celowo **nie** jest to ``ContentType.pk``.
ContentType.pk nadaje baza i różni się między instalacjami; wpuszczony do
trwałego, publicznego identyfikatora spowodowałby, że po odtworzeniu bazy
z baseline'u agregator zobaczy duplikat całego korpusu jako nowe rekordy.
"""

import re

from django.apps import apps

from cerif_export import const


class BlednyIdentyfikator(ValueError):
    """Identyfikator OAI nie daje się rozebrać na (namespace, model, pk).

    Warstwa OAI mapuje ten wyjątek na błąd protokołu ``idDoesNotExist``.
    """


# model (jako "app_label.ModelName") -> (typ CERIF, slug)
_REJESTR = {
    "bpp.Wydawnictwo_Ciagle": (const.TYP_PUBLICATION, "wc"),
    "bpp.Wydawnictwo_Zwarte": (const.TYP_PUBLICATION, "wz"),
    "bpp.Praca_Doktorska": (const.TYP_PUBLICATION, "pd"),
    "bpp.Praca_Habilitacyjna": (const.TYP_PUBLICATION, "ph"),
    "bpp.Zrodlo": (const.TYP_PUBLICATION, "zr"),
    "bpp.Autor": (const.TYP_PERSON, "au"),
    "bpp.Jednostka": (const.TYP_ORGUNIT, "je"),
    "bpp.Uczelnia": (const.TYP_ORGUNIT, "uc"),
    "bpp.Patent": (const.TYP_PATENT, "pt"),
    "bpp.Konferencja": (const.TYP_EVENT, "kf"),
}

SLUGI_WG_ETYKIETY = {etykieta: slug for etykieta, (_, slug) in _REJESTR.items()}
TYPY_WG_ETYKIETY = {etykieta: typ for etykieta, (typ, _) in _REJESTR.items()}
ETYKIETY_WG_SLUGU = {slug: etykieta for etykieta, slug in SLUGI_WG_ETYKIETY.items()}

_WZORZEC = re.compile(
    r"^oai:(?P<namespace>[^:]+):(?P<typ>[A-Za-z]+)/(?P<slug>[a-z]{2})-(?P<pk>\d+)$"
)


def etykieta_modelu(obj_lub_model) -> str:
    """Zwróć ``app_label.ModelName`` dla obiektu albo klasy modelu."""
    meta = obj_lub_model._meta
    return f"{meta.app_label}.{meta.object_name}"


def model_wg_slugu(slug: str):
    """Zwróć klasę modelu dla sluga. Podnosi ``BlednyIdentyfikator``."""
    etykieta = ETYKIETY_WG_SLUGU.get(slug)
    if etykieta is None:
        raise BlednyIdentyfikator(f"Nieznany slug encji: {slug!r}")
    return apps.get_model(etykieta)


def slug_dla(obj_lub_model) -> str:
    """Zwróć slug dla obiektu albo klasy modelu."""
    etykieta = etykieta_modelu(obj_lub_model)
    slug = SLUGI_WG_ETYKIETY.get(etykieta)
    if slug is None:
        raise BlednyIdentyfikator(f"Model {etykieta} nie jest eksportowany")
    return slug


def typ_dla(obj_lub_model) -> str:
    """Zwróć człon typu CERIF (np. ``Publications``)."""
    etykieta = etykieta_modelu(obj_lub_model)
    typ = TYPY_WG_ETYKIETY.get(etykieta)
    if typ is None:
        raise BlednyIdentyfikator(f"Model {etykieta} nie jest eksportowany")
    return typ


def zbuduj(namespace: str, obj) -> str:
    """Złóż identyfikator OAI dla obiektu."""
    return f"oai:{namespace}:{typ_dla(obj)}/{slug_dla(obj)}-{obj.pk}"


def zbuduj_z_czesci(namespace: str, slug: str, pk: int) -> str:
    """Złóż identyfikator bez posiadania instancji obiektu."""
    model = model_wg_slugu(slug)
    return f"oai:{namespace}:{typ_dla(model)}/{slug}-{pk}"


def rozbierz(oai_id: str):
    """Rozbierz identyfikator OAI na ``(namespace, model, pk)``.

    Świadomie bez ``assert`` — pod ``python -O`` asserty znikają i parsowanie
    szłoby dalej na niesprawdzonych danych.
    """
    if not isinstance(oai_id, str):
        raise BlednyIdentyfikator("Identyfikator musi być łańcuchem znaków")

    dopasowanie = _WZORZEC.match(oai_id)
    if dopasowanie is None:
        raise BlednyIdentyfikator(f"Niepoprawny identyfikator OAI: {oai_id!r}")

    slug = dopasowanie.group("slug")
    model = model_wg_slugu(slug)

    if typ_dla(model) != dopasowanie.group("typ"):
        raise BlednyIdentyfikator(f"Człon typu nie zgadza się ze slugiem w {oai_id!r}")

    return dopasowanie.group("namespace"), model, int(dopasowanie.group("pk"))
