Import pracowników: akcje w tabelach podglądu i odpięć (wybór autora, przepięcie,
odpięcie) podmieniają teraz zawartość wiersza przez HTMX ``innerHTML`` zamiast
``outerHTML``, dzięki czemu węzeł wiersza zostaje stały i DataTables poprawnie
odświeża go po zmianie — wcześniej filtrowanie/sortowanie po edycji potrafiło
przywrócić starą treść wiersza z pamięci podręcznej.
