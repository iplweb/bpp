Usunięto martwy kod integracji słownika dyscyplin (``integruj_dyscypliny``
i pomocnicze funkcje w ``pbn_integrator/utils/dictionaries.py``). Kod ten
wywoływał nieistniejącą metodę klienta ``get_discipline_groups()`` i zakładał
nieaktualny kształt odpowiedzi PBN — nie miał żadnego produkcyjnego wywołania,
a jedynie testy charakteryzujące zepsuty kontrakt. Właściwa synchronizacja
dyscyplin odbywa się przez ``download_disciplines()``/``sync_disciplines()``.
