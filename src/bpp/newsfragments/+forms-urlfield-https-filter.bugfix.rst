Wyciszono ``RemovedInDjango60Warning: The FORMS_URLFIELD_ASSUME_HTTPS
transitional setting is deprecated`` w konfiguracji pytest
(``pytest.ini``). Ustawienie zostaje, bo jest intencjonalnym opt-in
na domyślne zachowanie Django 6.0 — jego usunięcie w 5.x przywróci
warningi z ``forms.URLField`` dla URL-i bez schematu. Filter do
zdjęcia razem z samym ustawieniem podczas upgrade na Django 6.0.
