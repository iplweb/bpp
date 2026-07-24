Główny bundle JavaScript jest teraz w pełni minifikowany (esbuild
``--minify``; wcześniej brakowało ``--minify-identifiers``, więc bundle
woził pełne nazwy zmiennych). Rozmiar spadł z 921,5 KB do 785,4 KB
(-136,2 KB, -14,8%), a po kompresji gzip — z 242,6 KB do 221,5 KB
(-21,0 KB, -8,7%). Bundle ładowany jest render-blocking w ``<head>``,
więc zysk dotyczy każdego wejścia na stronę.

Przy okazji uodporniono na minifikację łatę eksportującą globalną
przestrzeń nazw ``yl`` z django-autocomplete-light. Dotąd dopasowywała
ona sztywną nazwę ``yl2``, którą ``--minify-identifiers`` zmienia — bez
poprawki autouzupełnianie (select2) w panelu administracyjnym przestałoby
działać. Łata dopasowuje teraz kształt deklaracji zamiast nazwy, a build
przerywa się z czytelnym błędem, jeśli nie uda się jej zaaplikować.
