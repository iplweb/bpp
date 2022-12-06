#!/bin/bash

export KATALOG="$1/raport.txt"

IFS=$(echo -en "\n\b")

for a in $1/*xlsx; do
    python src/manage.py import_oplaty_publikacje --dry "$a" >> "$KATALOG" ;
done
