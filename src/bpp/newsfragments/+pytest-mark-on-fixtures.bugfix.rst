Usunięto redundantne dekoratory ``@pytest.mark.django_db`` nałożone
na fixtury w plikach ``conftest.py``. Pytest 8 ostrzegał
``PytestRemovedIn9Warning: Marks applied to fixtures have no
effect``, a sam marker i tak nie miał efektu — dostęp do bazy
danych w fixturach jest dziedziczony z testu wywołującego. W pytest 9
stosowanie markerów na fixturach będzie błędem.
