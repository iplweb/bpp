#!/bin/bash

python src/manage.py mapuj_kola_naukowe &> res.txt
grep "nie ma zadnego" res.txt > brak_kol.txt
grep "Przypisano" res.txt > przypisano.txt
grep "ma ilość przypisań" res.txt > wiele_kol.txt
