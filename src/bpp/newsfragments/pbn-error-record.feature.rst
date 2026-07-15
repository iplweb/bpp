Ujednolicono parsowanie błędów wysyłki do PBN. Czysty, wersjonowany kontrakt
błędów (``ErrorRecord`` + ``parse``/``serialize``) trafił do pakietu
``pbn-client`` (0.2.1), a wszystkie miejsca wyświetlania w BPP (kolejka
eksportu, widoki detalu, panel admina ``SentData``) korzystają teraz z niego
jako cienkie adaptery — znika kilka kruchych, rozjeżdżających się parserów.
Poprawia to m.in. błąd wyświetlania błędów o payloadzie liczbowym oraz kruchy
skrót w panelu admina; readery rozumieją już nowy format v1 (reader-first).
