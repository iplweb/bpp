Admin interface dla aplikacji ``importer_publikacji``: superuser może
przeglądać historię importu publikacji (model ``ImportSession`` z
oryginalnym tekstem BibTeX w polu ``raw_data``) oraz dopasowanych
autorów (model ``ImportedAuthor``). Obie klasy zarejestrowane w
Django adminie jako read-only (bez możliwości ręcznego tworzenia
lub edycji, podgląd tylko). Lista sesji wspiera filtrowanie po statusie,
dostawcy, dacie i autorach; wyszukiwanie po identyfikatorze, tytule,
DOI; szczegóły sesji pokazują sformatowane JSON ``raw_data``,
``normalized_data``, ``matched_data`` oraz tabelę autorów z
linkami do dopasowanych obiektów BPP.
