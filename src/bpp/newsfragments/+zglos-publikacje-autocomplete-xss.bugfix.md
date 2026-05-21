Publiczny autocomplete w ``zglos_publikacje`` (wybór wydawcy
i wydawnictwa nadrzędnego) escape'uje teraz nazwy z bazy BPP
oraz dane pobrane z PBN przy budowie etykiet w wynikach. Wcześniej
``mark_safe(f"...")`` interpolował wartości bez sanityzacji,
przez co tytuł lub nazwa wydawcy zawierające znaczniki HTML
mogły wstrzyknąć skrypt na publicznej stronie zgłoszenia.
