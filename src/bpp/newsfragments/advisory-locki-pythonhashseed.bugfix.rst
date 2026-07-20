Naprawiono grupę błędów w kluczach blokad i pamięci podręcznej.

Klucze liczone wbudowaną funkcją ``hash()`` przyjmowały inną wartość w każdym
procesie serwera (sól ``PYTHONHASHSEED``). Skutkiem było to, że blokady
chroniące przed równoczesnym uruchomieniem zadań w ogóle nie działały między
procesami: dwa zgłoszenia wysyłki oświadczeń do PBN złożone w tej samej chwili
mogły przejść oba i zakolejkować ZDUPLIKOWANĄ wysyłkę oświadczeń do PBN, a
pobierania danych z PBN mogły wystartować równolegle mimo blokady. Z tego
samego powodu pamięć podręczna licznika rekordów na listach w panelu
administracyjnym była w praktyce nieskuteczna (każdy proces serwera miał
własną, rozłączną przestrzeń kluczy), przez co ciężkie zapytania zliczające
wykonywały się wielokrotnie zamiast raz.

Naprawiono też pamięć podręczną panelu filtrów w panelu administracyjnym,
która budowała klucz z adresu w pamięci zamiast z parametrów filtrowania.
Powodowało to, że po zmianie filtrów przez maksymalnie 5 minut wyświetlał się
panel filtrów wyliczony dla innego, wcześniejszego zestawu parametrów (błędnie
podświetlone aktywne filtry).

W instalacjach wielouczelnianych statystyki na pulpicie administratora nie
uwzględniały domeny w kluczu pamięci podręcznej, przez co dane wyliczone dla
jednej uczelni mogły zostać pokazane pod domeną innej. Odpowiedzi są teraz
różnicowane po domenie.
