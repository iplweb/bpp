"""
Testy dla modułu multiseek_registry.

Ten plik został podzielony na mniejsze moduły dla lepszej organizacji.
Testy zostały przeniesione do następujących plików:

- test_multiseek_basic.py
    Testy podstawowych obiektów zapytań (TytulPracyQueryObject,
    StronaWWWUstawionaQueryObject, LicencjaOpenAccessUstawionaQueryObject,
    CharakterOgolnyQueryObject, DataUtworzeniaQueryObject, DyscyplinaQueryObject,
    openaccess queries, ForeignKeyDescribeMixin, CharakterFormalnyQueryObject,
    JezykQueryObject)

- test_multiseek_authors.py
    Testy obiektów zapytań związanych z autorami (NazwiskoIImieQueryObject,
    Typ_OdpowiedzialnosciQueryObject, TypOgolnyAutorQueryObject,
    TypOgolnyRedaktorQueryObject, TypOgolnyTlumaczQueryObject,
    TypOgolnyRecenzentQueryObject, OstatnieNazwiskoIImie,
    PierwszeNazwiskoIImie, OswiadczenieKENQueryObject)

- test_multiseek_organizations.py
    Testy obiektów zapytań związanych z jednostkami i wydziałami
    (JednostkaQueryObject, WydzialQueryObject, PierwszyWydzialQueryObject,
    PierwszaJednostkaQueryObject, AktualnaJednostkaAutoraQueryObject,
    ObcaJednostkaQueryObject, RodzajJednostkiQueryObject,
    KierunekStudiowQueryObject)

- test_multiseek_misc.py
    Testy różnych obiektów zapytań (OstatnioZmieniony,
    RodzajKonferenckjiQueryObject, LiczbaAutorowQueryObject,
    ZewnetrznaBazaDanychQueryObject, DOIQueryObject,
    PublicDostepDniaQueryObject, SlowaKluczoweQueryObject,
    StatusKorektyQueryObject)
"""
