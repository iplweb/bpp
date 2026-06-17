Zaktualizowano trzy zależności tranzytywne do wersji łatających
podatności zgłoszone w audycie ``pip-audit``: ``bleach`` do 6.4.0
(GHSA-8rfp-98v4-mmr6, GHSA-gj48-438w-jh9v), ``daphne`` do 4.2.2
(PYSEC-2026-213, PYSEC-2026-214) oraz ``pypdf`` do 6.13.2
(CVE-2026-48735, CVE-2026-49460, CVE-2026-49461, CVE-2026-54530,
CVE-2026-54531). Minimalne wersje są od teraz egzekwowane przez
``constraint-dependencies`` w ``pyproject.toml``, dzięki czemu
przyszłe przeliczenie ``uv.lock`` nie cofnie się poniżej
załatanego wydania.
