Naprawiono klucze blokad i cache liczone wbudowaną funkcją ``hash()``, która
w Pythonie zwraca inną wartość w każdym procesie (sól ``PYTHONHASHSEED``).
Skutkiem było to, że blokady chroniące przed równoczesnym uruchomieniem
zadań w ogóle nie działały między procesami serwera: dwa zgłoszenia wysyłki
oświadczeń do PBN złożone w tej samej chwili mogły przejść oba i zakolejkować
ZDUPLIKOWANĄ wysyłkę oświadczeń do PBN, a pobierania danych z PBN mogły
wystartować równolegle mimo blokady. Z tego samego powodu cache licznika
rekordów na listach w panelu administracyjnym był w praktyce nieskuteczny
(każdy proces serwera miał własną, rozłączną przestrzeń kluczy), przez co
ciężkie zapytania zliczające wykonywały się wielokrotnie zamiast raz.
