Usunięto wielokrotnie powtarzane zapytania do bazy w publicznych szablonach
(strona rekordu, jednostki i autora). Szablony odwoływały się po kilka razy do
tych samych metod modelu (``autorzy_dla_opisu``, ``pracownicy``,
``wspolpracowali``, ``liczba_cytowan``, ``jednostki_gdzie_ma_publikacje``,
podjednostki, streszczenia, metryki ewaluacyjne), a każde odwołanie budowało
świeży queryset, czyli osobne odpytanie warstwy danych. Dane są teraz materializowane
raz — przez ``prefetch_related`` w widoku, przekazanie gotowych list przez
kontekst oraz ``{% with %}`` w szablonach. Lista pracowników jednostki dostała
dodatkowo ``select_related("aktualna_funkcja")``.

Poniższe liczby zmierzono na konfiguracji testowej, czyli przy WYŁĄCZONYM
cacheops (``CACHEOPS_ENABLED = False`` w ``settings/test.py``). Na produkcji
``bpp.jednostka`` oraz ``bpp.wydawnictwo_ciagle_streszczenie`` są w ``CACHEOPS``
(``get``/``fetch``/``count``/``exists``), więc część usuniętych zapytań trafiała
tam do Redisa, a nie do PostgreSQL — realny zysk dla strony strukturalnej
jednostki i dla streszczeń będzie odpowiednio mniejszy. Wartości pokazują skalę
powtórzeń, a nie gwarantowane przyspieszenie produkcyjne (rekord z 6 autorami;
jednostka z 12 pracownikami; jednostka strukturalna z 4 podjednostkami; autor
z 3 pracami i 3 metrykami):

* strona rekordu: 43 → 41 zapytań ogółem; lista autorów opisu 4 → 1,
  streszczenia 6 → 1;
* strona jednostki (lista pracowników): 35 → 27 zapytań ogółem; ``bpp_autor``
  9 → 4, ``bpp_autor_jednostka`` 4 → 1;
* strona jednostki (struktura podjednostek): 53 → 33 zapytania ogółem;
  ``bpp_jednostka`` 16 → 5;
* strona autora: 39 → 33 zapytania ogółem; agregat cytowań 3 → 2, metryki
  ewaluacyjne 5 → 1, jednostki autora 2 → 1.
