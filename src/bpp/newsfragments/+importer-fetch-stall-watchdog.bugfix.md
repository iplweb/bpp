Importer publikacji: sesja pobierania danych (np. z CrossRef po DOI) nie
zawiesza się już na stałe na „Pobieram dane od dostawcy…". Gdy zadanie w tle
zginęło poza kontrolą aplikacji (ubity/zgubiony worker Celery), status sesji
zostawał w nieskończoność w stanie „Trwa pobieranie", a strona odświeżała się w
kółko. Dodano watchdog: sesja tkwiąca zbyt długo w pobieraniu/tworzeniu rekordu
jest automatycznie oznaczana jako błąd z możliwością ponowienia. Timeout
zapytania HTTP do CrossRef jest teraz ustawiony jawnie i konfigurowalny
(`IMPORTER_STALL_TIMEOUT`, `CROSSREF_API_TIMEOUT`).
