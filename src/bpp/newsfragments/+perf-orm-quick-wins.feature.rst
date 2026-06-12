Mniej zbędnych zapytań SQL na często odwiedzanych stronach: wyniki
multiwyszukiwarki dla raportów tabelarycznych liczą rekordy i sumy
punktacji jednym skanem zamiast dwóch; przeglądanie lat nie wykonuje
ponownie tych samych COUNT-ów; eksport multiseek nie odpytuje bazy
o typ rekordu dla każdego wiersza z osobna (procesowy cache
``ContentType``); API ostatnich publikacji autora nie pobiera ~40
zbędnych kolumn i nie duplikuje publikacji, gdy autor występuje na
rekordzie wielokrotnie.
