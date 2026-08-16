``grunt build`` odświeża teraz sam znacznik kompletnego builda assetów.
Wcześniej robiła to wyłącznie reguła w ``Makefile``, więc ręcznie odpalony
``npx grunt build`` budował pliki, ale zostawiał znacznik nieaktualny —
i kolejne ``make assets`` przebudowywało wszystko bez potrzeby.

Budowanie assetów przed testami stoi dodatkowo pod zamkiem plikowym: dwa
przebiegi ``pytest`` uruchomione naraz w tym samym katalogu roboczym nie
wejdą już sobie w drogę, pisząc równolegle do tych samych plików.
