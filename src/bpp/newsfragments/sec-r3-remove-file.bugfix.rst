Utwardzono zadanie ``remove_file`` (kasowanie plików raportów). Poprzednie
sprawdzenie ``startswith(MEDIA_ROOT/report)`` przepuszczało ścieżki rodzeństwa
o wspólnym prefiksie (``…/report-evil/…``) oraz traversal (``…/report/../…``).
Teraz ścieżka jest rozwiązywana (``Path.resolve()`` — łamie ``..`` i symlinki)
i musi leżeć wewnątrz katalogu raportów; brak pliku traktowany jest
idempotentnie (nie jest błędem).
