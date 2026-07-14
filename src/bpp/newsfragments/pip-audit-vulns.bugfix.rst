Załatano podatności bezpieczeństwa w zależnościach: ``click`` (8.4.2) i
``pillow`` (12.3.0) podniesione do wersji z poprawkami. Podatność
``setuptools`` (PYSEC-2026-3447) jest świadomie whitelistowana w skanie
pip-audit — jej fix (setuptools 83) usuwa moduł ``pkg_resources`` wymagany
przez bibliotekę OAI-PMH (``pyoai``), więc bump wywalałby start aplikacji.
