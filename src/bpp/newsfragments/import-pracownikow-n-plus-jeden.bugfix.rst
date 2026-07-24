Lista wyników importu pracowników wykonywała trzy zapytania do bazy na każdy
wiersz importu i powielała ten sam blok skryptu w każdym wierszu HTML-a. Przy
tysiącu wierszy dawało to ponad trzy tysiące zapytań i dziewięć megabajtów
strony. Teraz liczba zapytań nie zależy od liczby wierszy.
