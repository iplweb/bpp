"""Rejestr providerów encji.

Warstwa OAI-PMH adresuje providery na dwa sposoby: po ``setSpec`` (czasowniki
``ListRecords``/``ListIdentifiers`` z parametrem ``set``) oraz po modelu
rozebranym z identyfikatora (``GetRecord``). Oba wejścia są tutaj, żeby
``oai/`` nie musiało znać układu modułów w ``providers/``.

Kolejność w :data:`PROVIDERY` jest kolejnością odpowiedzi ``ListSets`` i
kolejnością wyczerpywania setów przy harveście bez parametru ``set`` —
odpowiada ``const.WSZYSTKIE_SETY``.
"""

from cerif_export.identyfikatory import BlednyIdentyfikator, etykieta_modelu
from cerif_export.providers.jednostki import ProviderJednostek
from cerif_export.providers.konferencje import ProviderKonferencji
from cerif_export.providers.osoby import ProviderOsob
from cerif_export.providers.patenty import ProviderPatentow
from cerif_export.providers.publikacje import ProviderPublikacji
from cerif_export.providers.puste import (
    ProviderAparatury,
    ProviderFinansowania,
    ProviderProduktow,
    ProviderProjektow,
)

PROVIDERY = (
    ProviderPublikacji(),
    ProviderProduktow(),
    ProviderPatentow(),
    ProviderOsob(),
    ProviderJednostek(),
    ProviderProjektow(),
    ProviderFinansowania(),
    ProviderKonferencji(),
    ProviderAparatury(),
)

PROVIDERY_WG_SETU = {provider.set_spec: provider for provider in PROVIDERY}

PROVIDERY_WG_ETYKIETY_MODELU = {
    etykieta_modelu(model): provider
    for provider in PROVIDERY
    for model in provider.modele
}


def provider_dla_setu(set_spec):
    """Provider obsługujący dany ``setSpec``.

    :raises KeyError: gdy set nie istnieje — warstwa OAI mapuje to na błąd
        protokołu ``noSetHierarchy``/``badArgument``.
    """
    return PROVIDERY_WG_SETU[set_spec]


def provider_dla_modelu(model):
    """Provider, w którego secie wychodzi dany model.

    :raises BlednyIdentyfikator: gdy model nie jest eksportowany — warstwa
        OAI mapuje to na ``idDoesNotExist``.
    """
    etykieta = etykieta_modelu(model)
    provider = PROVIDERY_WG_ETYKIETY_MODELU.get(etykieta)
    if provider is None:
        raise BlednyIdentyfikator(f"Model {etykieta} nie jest eksportowany")
    return provider


__all__ = [
    "PROVIDERY",
    "PROVIDERY_WG_ETYKIETY_MODELU",
    "PROVIDERY_WG_SETU",
    "ProviderAparatury",
    "ProviderFinansowania",
    "ProviderJednostek",
    "ProviderKonferencji",
    "ProviderOsob",
    "ProviderPatentow",
    "ProviderProduktow",
    "ProviderProjektow",
    "ProviderPublikacji",
    "provider_dla_modelu",
    "provider_dla_setu",
]
