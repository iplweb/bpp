Importer publikacji podpowiada teraz język pracy również dla angielskiego
i pozostałych języków z danych referencyjnych BPP. Dotąd dopasowanie szło
wyłącznie przez pole „Skrót nazwy języka wg API CrossRef", które wypełnione
jest tylko dla polskiego — więc import pracy z ``language="en"`` zostawiał
pole „Język" puste. Teraz, gdy to pole jest niewypełnione, importer sięga po
kod BCP 47 języka (uzupełniony dla polskiego, angielskiego, niemieckiego,
francuskiego, hiszpańskiego, rosyjskiego i włoskiego), pomijając oznaczenie
regionu. Ta sama poprawka dotyczy języka streszczeń.
