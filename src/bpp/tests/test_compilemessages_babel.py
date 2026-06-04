"""Projektowa komenda ``compilemessages`` kompiluje .po → .mo w czystym
Pythonie (Babel), BEZ systemowej binarki ``msgfmt`` z pakietu apt ``gettext``.

To jest kontrakt buildu: obraz Dockera nie instaluje już ``gettext``, więc
``manage.py compilemessages`` nie może wołać ``msgfmt`` przez subprocess.
Wszystkie call-site'y (Makefile, Dockerfile) wołają ``compilemessages``
tak jak dotąd — override w aplikacji ``bpp`` wygrywa nad ``django.core``.
"""

import gettext as gettext_module
from pathlib import Path

from django.core.management import call_command
from django.core.management.commands import compilemessages as dj_compilemessages
from django.test import override_settings

# Nagłówek z polskim Plural-Forms (3 formy) + treści z UTF-8 oraz jednym
# wpisem ``msgid_plural``, żeby sprawdzić, że liczby mnogie przeżyją kompilację.
PO_CONTENT = """\
msgid ""
msgstr ""
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: pl\\n"
"Plural-Forms: nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && \
(n%100<12 || n%100>14) ? 1 : 2);\\n"

msgid "Cancel"
msgstr "Anuluj"

msgid "Yes, I'm sure"
msgstr "Tak, jestem pewny"

msgid "%(count)d record"
msgid_plural "%(count)d records"
msgstr[0] "%(count)d rekord"
msgstr[1] "%(count)d rekordy"
msgstr[2] "%(count)d rekordów"
"""


# Realny przypadek z repo: ``django_bpp/django.po`` ma PUSTY nagłówek
# ``Language:`` (Django generuje go takim). Autorytatywne locale katalogu
# pochodzi wtedy WYŁĄCZNIE ze ścieżki (``locale/pl/LC_MESSAGES``), nie z
# nagłówka. Pilnujemy, że 4-formowa polska reguła liczby mnogiej przeżyje
# kompilację mimo pustego ``Language:`` — inaczej Babel cicho degraduje do
# germańskich 2 form i polskie liczebniki renderują się błędnie.
PO_EMPTY_LANGUAGE = """\
msgid ""
msgstr ""
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: \\n"
"Plural-Forms: nplurals=4; plural=(n==1 ? 0 : (n%10>=2 && n%10<=4) && \
(n%100<12 || n%100>14) ? 1 : n!=1 && (n%10>=0 && n%10<=1) || \
(n%10>=5 && n%10<=9) || (n%100>=12 && n%100<=14) ? 2 : 3);\\n"

msgid "%(count)d file"
msgid_plural "%(count)d files"
msgstr[0] "%(count)d plik"
msgstr[1] "%(count)d pliki"
msgstr[2] "%(count)d plików"
msgstr[3] "%(count)d pliku"
"""


def _make_locale_tree(tmp_path: Path, content: str = PO_CONTENT) -> Path:
    lc = tmp_path / "locale" / "pl" / "LC_MESSAGES"
    lc.mkdir(parents=True)
    (lc / "django.po").write_text(content, encoding="utf-8")
    return lc


def test_compilemessages_without_system_msgfmt(tmp_path, monkeypatch):
    """Kompilacja działa nawet gdy binarki ``msgfmt`` nie ma na PATH."""
    lc = _make_locale_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    # Symuluj brak GNU gettext: gdyby komenda wołała msgfmt, padłaby z
    # CommandError("Can't find msgfmt..."). Nasz override kompiluje Babelem.
    monkeypatch.setattr(dj_compilemessages, "find_command", lambda program: None)

    with override_settings(LOCALE_PATHS=[str(tmp_path / "locale")]):
        call_command("compilemessages", "-l", "pl", verbosity=0)

    assert (lc / "django.mo").exists(), "Nie powstał plik .mo"


def test_compiled_mo_translations_and_plurals(tmp_path, monkeypatch):
    """Skompilowany .mo zwraca poprawne tłumaczenia (UTF-8) i liczby mnogie."""
    lc = _make_locale_tree(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dj_compilemessages, "find_command", lambda program: None)

    with override_settings(LOCALE_PATHS=[str(tmp_path / "locale")]):
        call_command("compilemessages", "-l", "pl", verbosity=0)

    with (lc / "django.mo").open("rb") as fp:
        tr = gettext_module.GNUTranslations(fp)

    assert tr.gettext("Cancel") == "Anuluj"
    assert tr.gettext("Yes, I'm sure") == "Tak, jestem pewny"
    # Plural-Forms z nagłówka muszą przetrwać kompilację (ngettext):
    plural = ("%(count)d record", "%(count)d records")
    assert tr.ngettext(*plural, 1) == "%(count)d rekord"
    assert tr.ngettext(*plural, 3) == "%(count)d rekordy"
    assert tr.ngettext(*plural, 5) == "%(count)d rekordów"


def test_plural_forms_survive_empty_language_header(tmp_path, monkeypatch):
    """4-formowa polska reguła przeżywa kompilację mimo pustego ``Language:``.

    Locale katalogu (``pl``) pochodzi ze ścieżki, nie z nagłówka — kompilator
    musi to uszanować, inaczej Babel degraduje do germańskich 2 form.
    """
    lc = _make_locale_tree(tmp_path, content=PO_EMPTY_LANGUAGE)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(dj_compilemessages, "find_command", lambda program: None)

    with override_settings(LOCALE_PATHS=[str(tmp_path / "locale")]):
        call_command("compilemessages", "-l", "pl", verbosity=0)

    with (lc / "django.mo").open("rb") as fp:
        tr = gettext_module.GNUTranslations(fp)

    plural = ("%(count)d file", "%(count)d files")
    # Polskie formy: 1=plik(0), 2-4=pliki(1), 5+=plików(2), 22=pliki(1).
    assert tr.ngettext(*plural, 1) == "%(count)d plik"
    assert tr.ngettext(*plural, 2) == "%(count)d pliki"
    assert tr.ngettext(*plural, 5) == "%(count)d plików"
    assert tr.ngettext(*plural, 22) == "%(count)d pliki"
