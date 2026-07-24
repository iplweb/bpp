Narzędzie diagnostyczne ``pbn_test_wysylka_interaktywna`` korzysta teraz z
pakietowych helperów ``pbn_client`` do dekodowania identyfikatora publikacji
(``decode_publication_object_id``) oraz porównywania oświadczeń
(``diff_statements`` + ``statement_key_*``). Przy niejednoznacznej odpowiedzi
PBN (lista różna od jednego elementu) narzędzie głośno sygnalizuje błąd i pyta
o kontynuację zamiast po cichu jechać dalej.
