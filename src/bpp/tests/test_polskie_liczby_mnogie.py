"""Polska odmiana liczebnikowa w komunikatach admina (``bpp/admin/actions.py``).

Komunikaty typu „Wybrano N rekord(y/ów)" używają
``ngettext("rekord", "rekordów", n)``. Polszczyzna wymaga dla liczebników
całkowitych 3 form (1 / 2–4 / 5+), więc 2-formowy fallback gettext-a daje
błędne „2 rekordów". Poprawne formy dostarcza wpis ``msgid_plural`` z 4
formami (msgstr[0..3]) w ``django_bpp/locale/pl/LC_MESSAGES/django.po``,
kompilowany do ``.mo`` (sesyjny fixture ``make assets`` w ``conftest.py``).

Forma 4. (CLDR „other") dotyczy ułamków i przy zliczaniu rekordów nigdy nie
pada — testujemy całkowite n pokrywające one/few/many oraz wyjątek 12–14.
"""

from django.utils.translation import ngettext, override

REKORD = ("rekord", "rekordów")


def test_rekord_formy_one_few_many():
    """1→rekord, 2–4→rekordy, 5+→rekordów (z wyjątkiem 12–14→rekordów)."""
    with override("pl"):
        assert ngettext(*REKORD, 1) == "rekord"
        assert ngettext(*REKORD, 2) == "rekordy"
        assert ngettext(*REKORD, 3) == "rekordy"
        assert ngettext(*REKORD, 4) == "rekordy"
        assert ngettext(*REKORD, 5) == "rekordów"
        assert ngettext(*REKORD, 11) == "rekordów"
        # 12–14 to wyjątek: mimo końcówki 2–4 idą do formy „many".
        assert ngettext(*REKORD, 12) == "rekordów"
        assert ngettext(*REKORD, 13) == "rekordów"
        assert ngettext(*REKORD, 14) == "rekordów"
        # …ale 22–24 (końcówka 2–4, setki ≠ 12–14) znów „few".
        assert ngettext(*REKORD, 22) == "rekordy"
        assert ngettext(*REKORD, 25) == "rekordów"
