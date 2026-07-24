Nowa zmienna środowiskowa ``DJANGO_BPP_ROLLBAR_IGNORE_SMTP_AUTH_ERRORS``
(domyślnie wyłączona) pozwala wyciszyć w monitoringu błędów zgłoszenia
o odrzuconych poświadczeniach serwera poczty na konkretnej instalacji.
Do użycia tam, gdzie administratorzy poczty po stronie klienta mają znaną
awarię, której nie da się naprawić po naszej stronie. Pozostałe błędy poczty
— w tym błędny adres odbiorcy czy nadawcy — są raportowane jak dotąd.
