Pytest nie emituje już ostrzeżeń ``PytestAssertRewriteWarning:
Module already imported so cannot be rewritten; fixtures.conftest_*``
(85 wystąpień w poprzednim runie). Przywrócono deklarację
``pytest_plugins = [...]`` w top-level ``src/conftest.py`` — pytest
rejestruje ``fixtures.conftest_{models,publications,system,browser,
disciplines}`` jako pluginy z aplikowanym assert-rewritingiem
przed ich pierwszym importem.

Jednocześnie ``fixtures/__init__.py`` przestał eager-importować
``conftest_*`` — wcześniejsze ``from .conftest_X import *``
pociągało te moduły przez łańcuch
``from fixtures.playwright_fixtures import ...`` → ``fixtures/
__init__.py`` PRZED rejestracją jako plugin, co właśnie generowało
ostrzeżenia.

Stałe (``NORMAL_DJANGO_USER_LOGIN/PASSWORD``, ``JEDNOSTKA_UCZELNI``,
``JEDNOSTKA_PODRZEDNA``) przeniesione do nowego modułu
``fixtures.const``, żeby ``from fixtures import X`` mogło je
re-eksportować bez ściągania modułów-pluginów.
