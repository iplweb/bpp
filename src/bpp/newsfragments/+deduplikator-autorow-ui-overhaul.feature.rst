Deduplikator autorów: gruntowna przebudowa UI. Tytuł i pozycje
menu uproszczone z "Deduplikator autorów PBN" na "Deduplikator
autorów" (bez znacznika BETA), wpis dodany dodatkowo do podmenu
"Operacje". Tryb skanowania (PBN/ogólny) prezentowany jest jako
kolorowy badge przy "Główny rekord autora", filtr "Pokaż wyniki"
zmieniony z radio-buttonów na poziomy button-group.

Przyciski na karcie każdego potencjalnego duplikatu pogrupowane
w trzy logiczne sekcje: Podgląd (otwórz wyd. ciągłe/zwarte,
redagowanie, stronę główną, PBN), Decyzja ("Nie jest duplikatem
głównego autora", usuń autora bez publikacji), Scalanie (cztery
warianty scalania). Przyciski "Scal + ustaw dyscyplinę" oraz
"Scal + ustaw subdyscyplinę" są ukryte, gdy główny autor nie ma
żadnej dyscypliny.

Powody podobieństwa renderowane są jako kolorowe chipy z ikonami
Foundation, z tonami match/info/weak/warn dobranymi do siły
przesłanki. Procent pewności jest sklampowany do zakresu 0–100%
(wcześniej widoczne były wartości typu 140% wynikające z surowego
score).

Naprawione: oznaczenie autora jako nie-duplikat (przycisk
"Nie jest duplikatem głównego autora") wykonuje się teraz przez
AJAX z fadeOut karty, zamiast przeładowywać widok i przeskakiwać
do kolejnego głównego autora. Naprawiono też "Scal wszystkie",
który dla kandydatów z trybu ogólnego zwracał błąd 400 (JS
wysyłał ``main_scientist_id`` zamiast ``main_autor_id``); brakujące
parametry trafiają teraz dodatkowo do Rollbara.
