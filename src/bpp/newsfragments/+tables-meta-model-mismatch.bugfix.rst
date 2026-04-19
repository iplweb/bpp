Wyrównano ``class Meta: model = ...`` w tabelach ``django-tables2``
do faktycznego typu wierszy w QuerySecie. Dotychczas wyświetlane były
ostrzeżenia ``UserWarning: Table data is of type <X> but <Y> is
specified in Table.Meta.model``:

- ``RankingAutorowTable`` — ``model = Autor`` → ``model = Sumy``
  (dane pochodzą z ``Nowe_Sumy_View`` / ``Sumy``, nie bezpośrednio
  z ``Autor``).
- ``RaportSlotowUczelniaTable`` — ``model =
  Cache_Punktacja_Autora_Query`` → ``model =
  RaportSlotowUczelniaWiersz`` (widok listy iteruje po rekordach
  ``RaportSlotowUczelnia.raportslotowuczelniawiersz_set``).

``Meta.model`` w ``django-tables2`` służy tylko do introspekcji pól;
poza zniknięciem samego ostrzeżenia zachowanie tabel nie uległo
zmianie.
