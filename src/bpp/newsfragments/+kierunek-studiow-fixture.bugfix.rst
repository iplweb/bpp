Naprawiono ``fixture 'kierunek_studiow' not found`` w testach
``test_KierunekStudiowQueryObject`` — fixture przeniesiony z
``src/fixtures/conftest.py`` do ``src/fixtures/conftest_models.py``,
który jest zarejestrowany w ``pytest_plugins`` i tym samym widoczny
globalnie. Fixture w zwykłym ``conftest.py`` był dostępny tylko dla
testów w podrzędnych katalogach.
