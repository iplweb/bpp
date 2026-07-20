Usunięto wielokrotnie powtarzane zapytania do bazy w publicznych szablonach
(strona rekordu, jednostki i autora). Szablony odwoływały się po kilka razy do
tych samych metod modelu (``autorzy_dla_opisu``, ``pracownicy``,
``wspolpracowali``, ``liczba_cytowan``, ``jednostki_gdzie_ma_publikacje``,
podjednostki, streszczenia, metryki ewaluacyjne), a każde odwołanie budowało
świeży queryset, czyli osobny roundtrip do bazy. Dane są teraz materializowane
raz — przez ``prefetch_related`` w widoku, przekazanie gotowych list przez
kontekst oraz ``{% with %}`` w szablonach. Lista pracowników jednostki dostała
dodatkowo ``select_related("aktualna_funkcja")``.

Zmierzone liczby zapytań na żądanie (rekord z 6 autorami; jednostka z 12
pracownikami; jednostka strukturalna z 4 podjednostkami; autor z 3 pracami
i 3 metrykami):

* strona rekordu: 43 → 41 zapytań ogółem; lista autorów opisu 4 → 1,
  streszczenia 6 → 1;
* strona jednostki (lista pracowników): 35 → 27 zapytań ogółem; ``bpp_autor``
  9 → 4, ``bpp_autor_jednostka`` 4 → 1;
* strona jednostki (struktura podjednostek): 53 → 33 zapytania ogółem;
  ``bpp_jednostka`` 16 → 5;
* strona autora: 39 → 33 zapytania ogółem; agregat cytowań 3 → 2, metryki
  ewaluacyjne 5 → 1, jednostki autora 2 → 1.
