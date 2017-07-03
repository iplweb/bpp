# -*- encoding: utf-8 -*-

"""
Ten moduł zawiera rozwiązania dla języka polskiego.
"""

czasownik_byc = dict(
    czas_przeszly=dict(
        K='była',
        M='był',
        default='był(a)'
    ),
    czas_terazniejszy=dict(
        K='jest',
        M='jest',
        default='jest'
    )
)

def warianty_zapisanego_nazwiska(p_imiona, p_nazwisko, poprzednie_nazwiska):
    imiona = p_imiona.replace("*", "")
    nazwisko = p_nazwisko.replace("*", "")
    # Pozbądź się pustych imion
    imiona = [x for x in imiona.split(" ") if x]
    # Sprawdź, czy mamy podwójne nazwiska
    nazwiska = [x for x in nazwisko.replace("-", " ").split(" ") if x]
    if len(nazwiska)>1:
        nazwiska = [nazwisko,] + nazwiska

    def wersje_imienia(imie):
        buf = [imie, ]
        if len(imie)>2:
            buf.append(imie[0] + "[" + imie[1:] + "]")
            buf.append(imie[0] + ".")
        else:
            buf.append(imie)
            buf.append(imie)
        return buf

    for i in zip(*tuple([wersje_imienia(imie) for imie in imiona])):
        for n in nazwiska:
            yield " ".join(list(i)) + " " + n

    # Wersja, w której z autora z wieloma imionami robimy autora z jednym imieniem,
    # czyli np. Stanisław J. Czuczwar => Stanisław Czuczwar
    if len(imiona)>1:
        for elem in warianty_zapisanego_nazwiska(imiona[0], p_nazwisko, poprzednie_nazwiska):
            yield elem

        for elem in warianty_zapisanego_nazwiska(imiona[1], p_nazwisko, poprzednie_nazwiska):
            yield elem

    if poprzednie_nazwiska:
        for elem in warianty_zapisanego_nazwiska(p_imiona, poprzednie_nazwiska, None):
            yield elem