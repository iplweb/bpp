#!/bin/bash

# Polecenie towarzyszące poleceniu z systemu `pbn_importuj_dyscypliny_i_punkty_zrodel`
# dzieli plik wyjściowy na kilka strumieni, każdy wysyła do oddzielnego
# pliku CSV.

for a in IDZ-0 IDZ-1 IDZ-2 IDZ-3 IDZ-4 IDZ-5 IDZ-6; do
    grep $a $1 > $1-$a.csv;
done
