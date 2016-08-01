# -*- encoding: utf-8 -*-


def zrob_skrot(ciag, max_length, klasa, atrybut):
    """Robi skrót z ciągu znaków "ciąg", do maksymalnej długości max_length,

    następnie sprawdza, czy taki ciąg znaków występuje w bazie danych
    w sensie: Klasa.objects.all().value_list(atrybut, flat=True),

    jeżeli taki skrót już istnieje, to zaczyna obcinać ostatnie elementy i wstawiać tam
    cyferki.
    """

    pierwsze_litery = "".join([x[0].upper() for x in ciag.split(" ")])[:max_length]
    w_bazie_sa = klasa.objects.all().values_list(atrybut, flat=True).distinct()
    ret = pierwsze_litery

    a = 0
    while ret in w_bazie_sa:
        a += 1
        cyfra = str(a)
        ret = pierwsze_litery[:max_length - len(cyfra)] + cyfra

    return ret

