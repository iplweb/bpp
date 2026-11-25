"""FD#527: nowe nazwy ``punkty_mnisw`` / ``typ_mnisw`` na modelach.

Kolumny w bazie i pola modeli nazywają się po staremu (``punkty_kbn``,
``typ_kbn``). Tu dokładamy same nazwy-aliasy tylko do odczytu, żeby nowej
nazwy dało się użyć tam, gdzie tekst trzymany w bazie sięga po atrybut
obiektu: w szablonach (``{{ record.punkty_mnisw }}``,
``{{ praca.typ_mnisw.nazwa }}``) i w polu „Atrybut” kolumny raportu.

Alias NIE jest polem modelu: nie ma go w ``_meta``, nie tworzy migracji
i ORM go nie zna (``filter(punkty_mnisw=…)`` nie zadziała — od zapytań jest
``bpp.djangoql_schema.ALIASY_POL``, a od sortowania
:class:`AliasyMNiSWQuerySetMixin`).
"""

#: ``alias: nazwa pola w modelu``.
ALIASY_MNISW = {
    "punkty_mnisw": "punkty_kbn",
    "typ_mnisw": "typ_kbn",
}


class AliasPola:
    """Deskryptor tylko do odczytu: atrybut pod drugą nazwą.

    Na obiekcie zwraca wartość pola docelowego. Na klasie zwraca to samo
    co pole docelowe,
    czyli deskryptor Django; dzięki temu kod, który sprawdza ścieżkę atrybutów
    na klasie modelu (walidacja pola „Atrybut” kolumny raportu), przechodzi
    przez alias relacji tak jak przez samą relację (``typ_mnisw.nazwa``).
    """

    def __init__(self, pole):
        self.pole = pole

    def __set_name__(self, owner, name):
        self.nazwa = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return getattr(owner, self.pole)
        return getattr(instance, self.pole)

    def __set__(self, instance, value):
        raise AttributeError(
            f"„{self.nazwa}” to alias tylko do odczytu — ustaw „{self.pole}”."
        )


class AliasPunktyMNiSWMixin:
    """``punkty_mnisw`` — dla modeli z polem ``punkty_kbn``."""

    punkty_mnisw = AliasPola("punkty_kbn")


class AliasTypMNiSWMixin:
    """``typ_mnisw`` — dla modeli z polem ``typ_kbn``.

    Osobno od punktów, bo nie każdy punktowany model ma typ (patent):
    alias ma istnieć dokładnie tam, gdzie pole, które zastępuje.
    """

    typ_mnisw = AliasPola("typ_kbn")


def _bez_aliasu_w_sortowaniu(nazwa):
    """``-punkty_mnisw`` → ``-punkty_kbn``, ``typ_mnisw__nazwa`` →
    ``typ_kbn__nazwa``; wszystko inne (także wyrażenia ORM) bez zmian."""
    if not isinstance(nazwa, str):
        return nazwa
    znak = "-" if nazwa.startswith("-") else ""
    rdzen, separator, reszta = nazwa.lstrip("-").partition("__")
    return znak + ALIASY_MNISW.get(rdzen, rdzen) + separator + reszta


class AliasyMNiSWQuerySetMixin:
    """Sortowanie po aliasie: ``order_by("punkty_mnisw")``.

    Tabela raportu sortuje w bazie po tym, co wpisano w polu „Atrybut”
    kolumny — bez tej podmiany kolumna z aliasem dawałaby się wyświetlić,
    ale kliknięcie w jej nagłówek kończyłoby się błędem ORM.
    """

    def order_by(self, *field_names):
        return super().order_by(*[_bez_aliasu_w_sortowaniu(f) for f in field_names])
