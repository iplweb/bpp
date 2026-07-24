Import osób z API instytucji PBN nie pomija już osób, którym PBN zmienił
identyfikator. ``polonUuid`` (identyfikator z POL-onu) jest stabilną
tożsamością osoby, a ``personId`` PBN potrafi zmienić — np. po scaleniu
zdublowanych profili. Import dopasowywał wiersz wyłącznie po ``personId``,
więc taka osoba rozbijała się o unikalność ``polonUuid`` i była pomijana,
a błąd wracał przy każdym kolejnym imporcie. Teraz wiersz jest przepinany
na nowy identyfikator.
