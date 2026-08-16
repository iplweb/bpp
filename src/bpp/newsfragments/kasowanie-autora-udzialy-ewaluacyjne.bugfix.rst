Kasowanie autora nie jest już blokowane komunikatem o braku uprawnień do
usunięcia obiektów „ilość udziałów dla autora". Django sprawdza uprawnienie do
usunięcia każdego obiektu kasowanego kaskadowo, a adminy udziałów ewaluacyjnych
odmawiały go bezwarunkowo — również superuserowi — więc autora, dla którego
policzono udziały, nie dało się skasować. Udziały są danymi wtórnymi
(przeliczalnymi z danych źródłowych), więc giną razem z autorem; nadal nie można
ich dopisać ani zmienić ręcznie. Redakcja otrzymała też brakujące uprawnienia do
udziałów za cały okres, żeby kasowanie autora działało dla użytkowników spoza
grupy administracyjnej.
