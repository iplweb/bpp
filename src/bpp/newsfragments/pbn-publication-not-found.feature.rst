Rozpoznanie „publikacja nie istnieje w PBN” (HTTP 422 „was not exists!”)
odbywa się teraz RAZ w endpoincie pakietu ``pbn_client``
(``get_publication_by_id`` rzuca ``PublicationNotFound``), a nie jest
duplikowane w BPP. ``BrakIDPracyPoStroniePBN`` jest aliasem
``PublicationNotFound`` (ta sama klasa), więc istniejące handlery działają bez
zmian. Zwykły HTTP 404 świadomie NIE jest traktowany jako brak pracy (bywa
przejściowy) i nie kasuje lokalnego cache'u publikacji.
