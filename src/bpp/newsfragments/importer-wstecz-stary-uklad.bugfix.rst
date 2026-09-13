Przycisk „Wstecz" w importerze publikacji nie przywraca już nieaktualnego
układu kroku 1 (wybór źródła przyciskami radio i lista sesji pod spodem).
Przeglądarki, które odwiedziły importer przed wprowadzeniem kafelków,
trzymały jego zrzut w pamięci podręcznej historii HTMX-a — a że nowa wersja
strony celowo nic już tam nie zapisuje, nieaktualny zrzut nie miał jak
zostać nadpisany. Strona kasuje go teraz przy wejściu.
