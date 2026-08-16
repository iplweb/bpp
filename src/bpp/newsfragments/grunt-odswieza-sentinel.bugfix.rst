``grunt build`` odświeża teraz sam znacznik kompletnego builda assetów.
Wcześniej robiła to wyłącznie reguła w ``Makefile``, więc ręcznie odpalony
``npx grunt build`` budował pliki, ale zostawiał znacznik nieaktualny —
i kolejne ``make assets`` przebudowywało wszystko bez potrzeby.
