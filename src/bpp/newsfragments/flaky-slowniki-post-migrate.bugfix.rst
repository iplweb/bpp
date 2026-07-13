Naprawiono flaky testy zależne od danych słownikowych: ``post_migrate`` odtwarza
teraz ``RodzajJednostki`` po transakcyjnym flushu testów (``TRUNCATE`` zmiatał
słowniki zaseedowane migracjami danych, których żaden receiver nie odtwarzał).
Seed reużywa oryginalnych funkcji migracji (0449/0454/0464) — bez duplikacji
wartości.
