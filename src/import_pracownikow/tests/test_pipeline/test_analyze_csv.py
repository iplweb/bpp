"""End-to-end: plik CSV (polski Excel: ``;`` + cp1250 + data DD.MM.YYYY)
przez pełną fazę analizy. Weryfikuje, że warstwa źródeł + normalizacja dat
spinają się z pipeline'em Fazy 0 (matchowanie autora/jednostki, dry-run)."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from liveops.testing import MockProgress

from import_common.exceptions import HeaderNotFoundException
from import_pracownikow.models import ImportPracownikow


def _csv_bytes(nazwisko, imie, jednostka):
    tresc = (
        "Numer;Nazwisko;Imię;Orcid;Tytuł/Stopień;Stanowisko;"
        "Grupa pracownicza;Nazwa jednostki;Wydział;Data zatrudnienia;"
        "Wymiar etatu;Podstawowe miejsce pracy\n"
        f"1;{nazwisko};{imie};;dr;Asystent;Badawczo-dydaktyczna;"
        f"{jednostka};Wydział Testowy;01.10.2016;Pełny etat;TAK\n"
    )
    return tresc.encode("cp1250")


@pytest.mark.django_db
def test_analiza_csv_end_to_end(admin_user, dwaj_autorzy_z_jednostki, tytuly):
    autor, jednostka = dwaj_autorzy_z_jednostki
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile(
        "pracownicy.csv",
        _csv_bytes(autor.nazwisko, autor.imiona, jednostka.nazwa),
    )
    imp.save()

    from import_pracownikow.pipeline.analyze import analizuj

    analizuj(imp, MockProgress(imp))

    imp.refresh_from_db()
    # Jednostka i tytuł („dr") z pliku są już w bazie → zero decyzji
    # strukturalnych → analiza przeskakuje Krok 1 (od razu faza osób).
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    row = imp.importpracownikowrow_set.get()
    # źródło CSV rozpoznane, autor i jednostka zmatchowani:
    assert row.autor_id == autor.pk
    assert row.jednostka_id == jednostka.pk
    # data DD.MM.YYYY sparsowana. UWAGA: dane_znormalizowane to
    # JSONField(encoder=DjangoJSONEncoder) — date serializuje się do stringa
    # "2016-10-01" i po refresh_from_db JEST stringiem. Property
    # dane_bardziej_znormalizowane parsuje go z powrotem na date (models.py:193).
    assert row.dane_bardziej_znormalizowane["data_zatrudnienia"] == date(2016, 10, 1)


@pytest.mark.django_db
def test_analiza_csv_bez_naglowka_rzuca(admin_user):
    # kontrakt §13: CSV bez wykrywalnego nagłówka → jawny HeaderNotFoundException
    # (asymetria wobec XLSX, który daje ValueError "0 wierszy" — udokumentowana
    # w sekcji „Poza zakresem"). Błąd propaguje przez analizuj() jako traceback.
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("zle.csv", b"aaa;bbb;ccc\n1;2;3\n")
    imp.save()

    from import_pracownikow.pipeline.analyze import analizuj

    with pytest.raises(HeaderNotFoundException):
        analizuj(imp, MockProgress(imp))
