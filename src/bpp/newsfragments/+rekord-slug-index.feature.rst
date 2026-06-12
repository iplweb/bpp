Strona pojedynczego rekordu (adres ze slugiem) ładuje się szybciej:
kolumna ``slug`` w tabeli cache ``bpp_rekord_mat`` dostała indeks —
wcześniej każde wejście na stronę rekordu skanowało całą tabelę.
Dodatkowo sprawdzenie „czy rekord ma punktację/sloty" na stronie
szczegółów kosztuje jedno zapytanie zamiast dwóch.
