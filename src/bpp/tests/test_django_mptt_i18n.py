"""Polskie nadpisania brakujących tłumaczeń z django-mptt.

``django-mptt`` jest zainstalowanym ``INSTALLED_APPS`` i ładuje własny katalog
``locale/pl/LC_MESSAGES/django.mo``, ale katalog ten jest stary i nie zawiera
wszystkich msgidów używanych przez aktualną wersję pakietu. Projektowy katalog
``django_bpp/locale`` jest w ``LOCALE_PATHS``, więc dokładamy tam brakujące
wpisy zamiast patchować nietrwałe pliki w ``site-packages``.
"""

from django.conf import settings
from django.utils.translation import gettext, override

DJANGO_MPTT_MISSING_POLISH_TRANSLATIONS = {
    "mptt": "MPTT",
    "Successfully deleted %(count)d items.": "Usunięto %(count)d elementów.",
    "title": "tytuł",
    "Did not understand moving instruction.": (
        "Nie rozpoznano polecenia przeniesienia."
    ),
    "Objects have disappeared, try again.": "Obiekty zniknęły, spróbuj ponownie.",
    "No permission": "Brak uprawnień",
    "Database error: %s": "Błąd bazy danych: %s",
    "%s has been successfully moved.": "%s został pomyślnie przeniesiony.",
    "move node before node": "przenieś węzeł przed wskazany węzeł",
    "move node to child position": ("przenieś węzeł jako dziecko wskazanego węzła"),
    "move node after node": "przenieś węzeł za wskazany węzeł",
    "Collapse tree": "Zwiń drzewo",
    "Expand tree": "Rozwiń drzewo",
    "All": "Wszystko",
    "Invalid parent": "Nieprawidłowy rodzic",
    "register() expects a Django model class argument": (
        "register() oczekuje argumentu będącego klasą modelu Django"
    ),
    "Node %s not in depth-first order": ("Węzeł %s nie jest w kolejności depth-first"),
    " By %(filter_title)s ": " Według: %(filter_title)s ",
    "%s tag requires either three, four, seven, eight, or nine arguments": (
        "tag %s wymaga trzech, czterech, siedmiu, ośmiu lub dziewięciu argumentów"
    ),
}


def test_django_mptt_is_installed_app():
    """Bez tego Django nie ładuje katalogu tłumaczeń pakietu django-mptt."""
    assert "mptt" in settings.INSTALLED_APPS


def test_missing_django_mptt_messages_are_translated_by_project_catalog():
    """Projektowy katalog przejmuje msgidy, których brakuje w upstream pl."""
    with override("pl"):
        for msgid, msgstr in DJANGO_MPTT_MISSING_POLISH_TRANSLATIONS.items():
            assert gettext(msgid) == msgstr
