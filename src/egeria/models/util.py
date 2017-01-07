# -*- encoding: utf-8 -*-
from datetime import date


def zrob_skrot(ciag, max_length, klasa, atrybut):
    """Robi skrót z ciągu znaków "ciąg", do maksymalnej długości max_length,

    następnie sprawdza, czy taki ciąg znaków występuje w bazie danych
    w sensie: Klasa.objects.all().value_list(atrybut, flat=True),

    jeżeli taki skrót już istnieje, to zaczyna obcinać ostatnie elementy i wstawiać tam
    cyferki.
    """

    pierwsze_litery = "".join([x.strip()[0].upper() for x in ciag.split(" ") if x.strip()])[:max_length]
    w_bazie_sa = klasa.objects.all().values_list(atrybut, flat=True).distinct()
    ret = pierwsze_litery

    a = 0
    while ret in w_bazie_sa:
        a += 1
        cyfra = str(a)
        ret = pierwsze_litery[:max_length - len(cyfra)] + cyfra

    return ret


def date_range_inside(s1, e1, s2, e2):
    """
    Zwraca True jeżeli zakres czasowy s2, e2 znajduje się wewnątrz zakresu czasowego
    s1, e1.

    Wartości wejściowe mogą być "None" dla czasokresów potencjalnie nieskończonych,
    wówczas za None podstawione zostaną wartości 1. sty 1 - 31. gru 9999.
    """

    s1 = s1 or date(1, 1, 1)
    e1 = e1 or date(9999, 12, 31)

    s2 = s2 or date(1, 1, 1)
    e2 = e2 or date(9999, 12, 31)

    try:
        assert s1 <= s2
        assert e1 >= e2
        return True
    except AssertionError:
        return False