Dodano stabilne ``order_by`` do QuerySetów, które były stronicowane
bez jawnego sortowania. Django emitowało wtedy
``UnorderedObjectListWarning: Pagination may yield inconsistent
results with an unordered object_list``, a kolejne strony mogły
zwracać zduplikowane lub pominięte rekordy.

Poprawione miejsca:

- Autocomplete w ``bpp.views.autocomplete``: ``Dyscyplina_Naukowa``
  (``kod``), ``Wydawnictwo_Zwarte`` dla wydawnictwa nadrzędnego i
  wariantów admina (``tytul_oryginalny``), ``Wydawnictwo_Ciagle``
  admin (``tytul_oryginalny``), ``Zrodlo`` (``nazwa`` — zarówno
  bazowy queryset jak i ``QuerySetSequence`` z priorytetami PBN).
- ``pbn_wysylka_oswiadczen.views.PublicationListView`` — combined
  ``QuerySetSequence`` sortowany ``-rok, tytul_oryginalny, pk``.
- ``RaportSlotowUczelnia.get_details_set()`` — sortowanie po
  ``autor__nazwisko, autor__imiona, pk`` dla stabilnej paginacji
  szczegółów raportu.
- ``RozbieznosciView`` — dodano ``Meta.ordering = ["id"]`` (bazowy
  abstrakcyjny model już miał tę opcję, ale lokalne ``Meta`` ją
  nadpisywało). Migracja ``0021`` to wyłącznie ``AlterModelOptions``
  (model jest ``managed = False``, brak DDL).
