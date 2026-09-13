"""Budowanie selektorów pól USOS API.

USOS przyjmuje w parametrze ``fields`` listę pól rozdzieloną ``|``, a podpola
zapisuje w nawiasach kwadratowych, np.::

    id|name|stats[staff_count]|path[id|name]

Składanie tego ręcznie w f-stringach szybko robi się nieczytelne przy
zagnieżdżeniach, stąd ten helper.
"""


def buduj_selektor(*pola):
    """Zamienia pola na selektor USOS API.

    Pole to napis (zwykłe pole) albo słownik ``{nazwa: [podpola]}``. Podpola
    mogą być zagnieżdżone dowolnie głęboko.

    >>> buduj_selektor("id", {"stats": ["staff_count"]})
    'id|stats[staff_count]'
    """
    czesci = []
    for pole in pola:
        if isinstance(pole, dict):
            for nazwa, podpola in pole.items():
                czesci.append(f"{nazwa}[{buduj_selektor(*podpola)}]")
        else:
            czesci.append(pole)
    return "|".join(czesci)
