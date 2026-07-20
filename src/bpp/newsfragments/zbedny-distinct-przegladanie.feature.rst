Przyspieszenie strony głównej oraz list autorów, źródeł i jednostek: usunięto
zbędne ``SELECT DISTINCT`` z zapytań przeglądania. Deduplikacja jest teraz
dokładana tylko tam, gdzie filtr faktycznie łączy tabele mogące zwielokrotnić
wiersze (tryb wielouczelniany), a nie bezwarunkowo — dzięki temu licznik
publikacji i lista ostatnio zmienionych rekordów korzystają z indeksów zamiast
przetwarzać całą tabelę.

Przy okazji poprawiono zawyżone liczby publikacji na stronie „Lata": w
instalacjach wielouczelnianych publikacja z kilkoma wpisanymi autorstwami tej
samej uczelni była liczona wielokrotnie, więc licznik przy roku pokazywał
więcej pozycji, niż faktycznie znajdowało się na liście.
