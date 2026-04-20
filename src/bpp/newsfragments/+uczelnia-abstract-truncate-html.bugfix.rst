Stopka na stronie głównej potrafiła wyświetlić się wewnątrz prawej
kolumny (sekcja „Najnowsze rekordy ze streszczeniem") zamiast na
dole jako pełnoszerokościowy pasek. Przyczyną było użycie filtra
``truncatewords`` (który nie zna się na HTML) na streszczeniach
publikacji zawierających znaczniki z bazy (np. ``<jats:p>``).
Truncate obcinał tekst w środku znacznika, pozostawiając niedomknięte
tagi, przez co przeglądarka dopasowywała zamknięcia dopiero na
stopce. Przełączono na ``truncatewords_html``, który zamyka otwarte
tagi w punkcie obcięcia i utrzymuje poprawne drzewo DOM.
