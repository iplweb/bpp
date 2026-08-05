"""Walidacja pola ``ror_id`` w formularzach admina.

Identyfikator ROR ma wbudowaną sumę kontrolną (ISO/IEC 7064 MOD 97-10), więc
literówkę da się wyłapać od razu przy zapisie, zamiast dowiadywać się o niej
z odrzuconego harvestu OpenAIRE albo z cichego braku ``RORID`` w eksporcie.

Sama walidacja mieszka w ``bpp.util.ror`` — czyli w aplikacji rdzeniowej,
nie w ``cerif_export``. Dzięki temu można ją wpiąć jako ``validators=[...]``
na polach modelu (migracje serializują ścieżkę do funkcji i nie mogą
referencjonować aplikacji nadbudowanej), a walidator siedzi na polu modelu, nie tylko
w formularzu admina.

Uwaga na zakres: ``validators`` na polu odpalają się przez
``full_clean()``, czyli w formularzach (admin, ModelForm) i wszędzie,
gdzie ktoś zawoła je jawnie. ``loaddata``, ``QuerySet.update()``
i gołe ``save()`` z shella **omijają** walidację — tak działa Django
i nie jest to obejście specyficzne dla tego pola.
"""

from bpp.util import ror


def czysc_ror(wartosc):
    """Zwaliduj i znormalizuj wartość pola ``ror_id``.

    Puste pole jest w porządku — ROR jest opcjonalny i po prostu nie
    zostanie wyeksportowany. Wartość niepusta jest sprowadzana do postaci
    kanonicznej ``https://ror.org/<id>``, żeby w bazie nie leżały obok
    siebie trzy zapisy tego samego identyfikatora.
    """
    wartosc = (wartosc or "").strip()
    if not wartosc:
        return ""

    znormalizowana = ror.normalizuj(wartosc)
    ror.waliduj(znormalizowana)
    return znormalizowana
