# -*- encoding: utf-8 -*-

"""
Ten moduł zawiera rozwiązania dla języka polskiego.
"""

czasownik_byc = dict(
    czas_przeszly=dict(
        K=u'była',
        M=u'był',
        default=u'był(a)'
    ),
    czas_terazniejszy=dict(
        K=u'jest',
        M=u'jest',
        default=u'jest'
    )
)

def warianty_zapisanego_nazwiska(p_imiona, p_nazwisko, poprzednie_nazwiska):
    imiona = p_imiona.replace("*", "")
    nazwisko = p_nazwisko.replace("*", "")
    # Pozbądź się pustych imion
    imiona = [x for x in imiona.split(u" ") if x]
    # Sprawdź, czy mamy podwójne nazwiska
    nazwiska = [x for x in nazwisko.replace(u"-", u" ").split(u" ") if x]
    if len(nazwiska)>1:
        nazwiska = [nazwisko,] + nazwiska

    def wersje_imienia(imie):
        buf = [imie, ]
        if len(imie)>2:
            buf.append(imie[0] + u"[" + imie[1:] + u"]")
            buf.append(imie[0] + u".")
        else:
            buf.append(imie)
            buf.append(imie)
        return buf

    for i in zip(*tuple([wersje_imienia(imie) for imie in imiona])):
        for n in nazwiska:
            yield u" ".join(list(i)) + u" " + n

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