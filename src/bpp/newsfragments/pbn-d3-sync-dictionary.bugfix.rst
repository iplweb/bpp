Synchronizacja słownika dyscyplin z PBN nie trzyma już otwartej transakcji
bazodanowej przez cały czas pobierania danych z PBN. Pobranie (remote) wykonuje
się teraz przed otwarciem transakcji (wzorzec ``sync_dictionary`` z pakietu
``django-pbn-client``), a zapis leci atomowo — dłuższa niedostępność PBN nie
blokuje już połączenia bazodanowego.
