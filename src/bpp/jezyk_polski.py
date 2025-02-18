"""
Ten moduł zawiera rozwiązania dla języka polskiego.
"""

deklinacja = [
    ("WYDZIAL", "wydział", "m"),
    ("WYDZIAL", "wydziału", "d"),
    ("WYDZIAL", "wydziałowi", "c"),
    ("WYDZIAL", "wydział", "b"),
    ("WYDZIAL", "wydziałem", "n"),
    ("WYDZIAL", "wydziale", "ms"),
    ("WYDZIAL", "wydział", "w"),
    ("UCZELNIA", "uczelnia", "m"),
    ("UCZELNIA", "uczelni", "d"),
    ("UCZELNIA", "uczelni", "c"),
    ("UCZELNIA", "uczelni", "b"),
    ("UCZELNIA", "uczelnią", "n"),
    ("UCZELNIA", "uczelni", "ms"),
    ("UCZELNIA", "uczelnio", "w"),
    ("UCZELNIA_PL", "uczelnie", "m"),
    ("UCZELNIA_PL", "uczelni", "d"),
    ("UCZELNIA_PL", "uczelniom", "c"),
    ("UCZELNIA_PL", "uczelnie", "b"),
    ("UCZELNIA_PL", "uczelniami", "n"),
    ("UCZELNIA_PL", "uczelniach", "ms"),
    ("UCZELNIA_PL", "uczelnie", "w"),
    ("JEDNOSTKA", "jednostka", "m"),
    ("JEDNOSTKA", "jednostki", "d"),
    ("JEDNOSTKA", "jednostce", "c"),
    ("JEDNOSTKA", "jednostkę", "b"),
    ("JEDNOSTKA", "jednostką", "n"),
    ("JEDNOSTKA", "jednostce", "ms"),
    ("JEDNOSTKA", "jednostko", "w"),
    ("JEDNOSTKA_PL", "jednostki", "m"),
    ("JEDNOSTKA_PL", "jednostek", "d"),
    ("JEDNOSTKA_PL", "jednostkom", "c"),
    ("JEDNOSTKA_PL", "jednostki", "b"),
    ("JEDNOSTKA_PL", "jednostkami", "n"),
    ("JEDNOSTKA_PL", "jednostkach", "ms"),
    ("JEDNOSTKA_PL", "jednostki", "w"),
]


def znajdz_rzeczownik(uid, p):
    for _uid, wartosc, przypadek in deklinacja:
        if p == przypadek and uid == _uid:
            return wartosc
    return f"(brak deklinacji dla {uid=} {p=}"


def lazy_rzeczownik_title(uid, p="m"):
    class Lazy:
        def __str__(self):
            from bpp.models import Rzeczownik

            try:
                return getattr(Rzeczownik.objects.get(uid=uid), p)
            except Rzeczownik.DoesNotExist:
                return znajdz_rzeczownik(
                    uid=uid,
                    p=p,
                )

    return Lazy()


czasownik_byc = dict(
    czas_przeszly=dict(K="była", M="był", default="był(a)"),
    czas_terazniejszy=dict(K="jest", M="jest", default="jest"),
)


def warianty_zapisanego_nazwiska(p_imiona, p_nazwisko, poprzednie_nazwiska):
    imiona = p_imiona.replace("*", "")
    nazwisko = p_nazwisko.replace("*", "")
    # Pozbądź się pustych imion
    imiona = [x for x in imiona.split(" ") if x]
    # Sprawdź, czy mamy podwójne nazwiska
    nazwiska = [x for x in nazwisko.replace("-", " ").split(" ") if x]
    if len(nazwiska) > 1:
        nazwiska = [
            nazwisko,
        ] + nazwiska

    def wersje_imienia(imie):
        buf = [
            imie,
        ]
        if len(imie) > 2:
            buf.append(imie[0] + "[" + imie[1:] + "]")
            buf.append(imie[0] + ".")
        else:
            buf.append(imie)
            buf.append(imie)
        return buf

    for i in zip(*tuple(wersje_imienia(imie) for imie in imiona)):
        for n in nazwiska:
            yield " ".join(list(i)) + " " + n
            yield n + " " + " ".join(list(i))

    # Wersja, w której z autora z wieloma imionami robimy autora z jednym imieniem,
    # czyli np. Stanisław J. Czuczwar => Stanisław Czuczwar
    if len(imiona) > 1:
        yield from warianty_zapisanego_nazwiska(
            imiona[0], p_nazwisko, poprzednie_nazwiska
        )

        yield from warianty_zapisanego_nazwiska(
            imiona[1], p_nazwisko, poprzednie_nazwiska
        )

    if poprzednie_nazwiska:
        yield from warianty_zapisanego_nazwiska(p_imiona, poprzednie_nazwiska, None)
