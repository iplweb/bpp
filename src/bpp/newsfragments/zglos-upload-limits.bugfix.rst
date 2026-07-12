Formularz zgłaszania publikacji: ograniczono anonimowe uploady (maks. 20 MB
na plik, maks. 5 plików na krok) i rozdzielono pliki tymczasowe kreatora od
plików trwałych zgłoszeń. Dodano komendę ``wyczysc_zglos_tmp`` czyszczącą
porzucone pliki tymczasowe (domyślnie starsze niż 24 h) — do wpięcia w cron.
Zapobiega to zapełnieniu dysku przez porzucone sesje kreatora, bez ryzyka
skasowania plików ukończonych zgłoszeń.
