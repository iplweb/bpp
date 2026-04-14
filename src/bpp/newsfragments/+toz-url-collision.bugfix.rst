Naprawiono kolizję nazw URL-i w panelu administracyjnym: trzy widoki
"toż" (dla ``Wydawnictwo_Ciagle``, ``Wydawnictwo_Zwarte`` oraz ``Patent``)
były zarejestrowane pod tą samą nazwą ``admin_bpp_wydawnictwo_ciagle_toz``,
przez co ``reverse()`` zawsze zwracał adres widoku patentu. Nazwy zostały
rozdzielone na ``admin_bpp_wydawnictwo_ciagle_toz``,
``admin_bpp_wydawnictwo_zwarte_toz`` i ``admin_bpp_patent_toz``, oraz
dodano test regresyjny.
