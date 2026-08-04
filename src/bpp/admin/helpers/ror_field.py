"""Walidacja pola ``ror_id`` w formularzach admina.

Identyfikator ROR ma wbudowaną sumę kontrolną (ISO/IEC 7064 MOD 97-10), więc
literówkę da się wyłapać od razu przy zapisie, zamiast dowiadywać się o niej
z odrzuconego harvestu OpenAIRE albo z cichego braku ``RORID`` w eksporcie.

Import ``cerif_export`` jest **leniwy**, wewnątrz funkcji. ``bpp`` jest
aplikacją rdzeniową, a ``cerif_export`` importuje z niej modele — import na
poziomie modułu odwróciłby tę zależność i groził cyklem przy starcie.
"""


def czysc_ror(wartosc):
    """Zwaliduj i znormalizuj wartość pola ``ror_id``.

    Puste pole jest w porządku — ROR jest opcjonalny i po prostu nie
    zostanie wyeksportowany. Wartość niepusta jest sprowadzana do postaci
    kanonicznej ``https://ror.org/<id>``, żeby w bazie nie leżały obok
    siebie trzy zapisy tego samego identyfikatora.
    """
    from cerif_export import ror

    wartosc = (wartosc or "").strip()
    if not wartosc:
        return ""

    znormalizowana = ror.normalizuj(wartosc)
    ror.waliduj(znormalizowana)
    return znormalizowana
