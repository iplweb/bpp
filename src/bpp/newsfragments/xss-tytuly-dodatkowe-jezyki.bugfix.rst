Domknięto lukę stored-XSS w tytułach publikacji w pozostałych językach
(``Wydawnictwo_*_Tytul``): są teraz sanityzowane przy każdym zapisie
(``save()``), tak jak tytuł oryginalny i przetłumaczony, a komenda
``sanityzuj_tytuly`` czyści również istniejące, brudne dane w tych polach.
Dodatkowo w metrykach ewaluacji filtr ``safe_tytul`` stosowany jest po
skróceniu tekstu (``truncatewords_html``), żeby nie rozcinać znaczników.
