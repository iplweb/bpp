Nowa zmienna środowiskowa ``DJANGO_BPP_ROLLBAR_IGNORE_SMTP_ERRORS`` (domyślnie
wyłączona) pozwala wyciszyć w monitoringu błędów całą rodzinę błędów SMTP na
konkretnej instalacji. Do użycia tam, gdzie administratorzy poczty po stronie
klienta mają znaną awarię, której nie da się naprawić po naszej stronie —
zamiast zasypywać monitoring powtarzalnym zgłoszeniem. Na pozostałych
instalacjach błędy poczty są raportowane jak dotąd.
