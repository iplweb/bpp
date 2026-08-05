Usunięto trzy zbędne shimy zgodności (``pbn_api.const``, ``pbn_api.utils``,
``pbn_api.client.transport``) — czyste re-eksporty z pakietów PBN. Kod importuje
teraz stałe, helpery słownikowe i transport wprost z ``pbn_client`` (spójnie z
resztą kodu po ekstrakcji). Warstwa zgodności ``pbn_api.exceptions`` oraz baza
modeli ``pbn_api.models.base`` pozostają (mają zawartość BPP-specific / stanowią
punkt rozszerzeń).
