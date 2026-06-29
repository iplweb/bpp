Rozbudowano listę rozbieżności punktacji. Zmieniono kolejność kolumn (tytuł,
rok, wartość z pracy, źródło, wartość ze źródła) i usunięto kolumnę „ostatnio
zmieniony". Filtr stanu źródła ma teraz trzy tryby: „standardowy", „pokazuj
również zerowe rekordy" oraz „pokazuj wyłącznie zerowe rekordy", gdzie „zerowe"
oznacza źródło z wartością 0 / pustym kwartylem albo bez wpisu punktacji za rok
pracy. Wykrywane są też prace, których źródło nie ma w ogóle wpisu za dany rok,
a praca ma niezerową wartość — dotyczy to wszystkich metryk (Impact Factor,
MNiSW, kwartyle Scopus i WoS); takie rekordy są wyraźnie oznaczane.

Dodano filtr po charakterze formalnym (lista z polami wyboru, domyślnie
wszystkie zaznaczone). Domyślnie operacja „ustaw wg źródła" / „ustaw wszystkie
wg źródła" NIE kasuje wartości w pracy, gdy źródło jest puste — takie rekordy są
pomijane, a komunikat podaje, ile pominięto. Nowy przełącznik „W przypadku braku
kwartyla/punktacji w źródle, kasuj kwartyl/punktację w pracy" (domyślnie
wyłączony) pozwala świadomie wyczyścić wartość w pracy. Te same zmiany objęły
eksport XLSX.
