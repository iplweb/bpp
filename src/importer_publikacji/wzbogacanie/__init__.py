"""Wzbogacanie istniejącego rekordu danymi z CrossRef albo PBN (FD#517, FD#518).

Rekord (wydawnictwo ciągłe albo zwarte) jest już w bazie. Redaktor otwiera
porównanie „źródło ↔ BPP”, zaznacza pola do przeniesienia i zatwierdza.
Nic nie jest zmieniane bez zaznaczenia pola.

* ``zrodla`` — pobranie danych (CrossRef po DOI; PBN z odpowiednika, w
  wybranej wersji) do tej samej postaci, której używa importer publikacji
  (``FetchedPublication``) — mapowanie pól źródła jest jedno, w dostawcach,
* ``pola`` — które pola BPP porównujemy i jak wartość ze źródła trafia do
  rekordu,
* ``autorzy`` — porównanie list autorów (tylko do podglądu),
* ``admin`` — widok w module redagowania.
"""
