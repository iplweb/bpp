Naprawiono niestabilne (zależne od ziarna RNG, pod pytest-xdist)
testy sortowania listy kolejki eksportu PBN
(``test_pbnexportqueuelistview_sort_by_pk`` /
``...sort_by_reverse_pk``). Drugi rekord tworzony był przez bare
``baker.make(Wydawnictwo_Ciagle)``, które losowało pole ``rok`` (często
ujemne), przez co wypadał z domyślnego filtra roku widoku
(``rok_od=2022``) i asercja robiła ``IndexError``. Testy nadają teraz
``rok=current_rok()`` i zawężają asercję do własnych wierszy.
