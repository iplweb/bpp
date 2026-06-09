Naprawiono błąd serwera (HTTP 500) przy zgłaszaniu publikacji z
załącznikiem PDF większym niż 2,5 MB. W kreatorze „Zgłoś publikację"
dodanie takiego pliku w kroku z danymi przerywało wysyłkę z błędem —
plik tymczasowy był zapisywany dwukrotnie, a drugi zapis trafiał na
już przeniesiony plik. Pliki dowolnej wielkości są teraz przyjmowane
poprawnie.
