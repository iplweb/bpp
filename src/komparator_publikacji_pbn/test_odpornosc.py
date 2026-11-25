"""Komparator publikacji PBN: odporność przeliczania (recenzje PR 1189) —
nietypowe dane z PBN, równoległe przeliczenia, zabity worker, odczyt w trakcie
podmiany wyników, reset integracji PBN, eksport."""

import logging
from datetime import timedelta
from io import BytesIO
from unittest import mock

import pytest
from django.db import connection
from django.db.models.signals import post_delete
from django.utils import timezone
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Wydawnictwo_Ciagle
from komparator_publikacji_pbn import core
from komparator_publikacji_pbn.models import (
    KomparatorPublikacjiMeta,
    RoznicaPublikacjiPBN,
)
from komparator_publikacji_pbn.tasks import porownaj_publikacje_task
from komparator_publikacji_pbn.views import PublicationComparisonView
from pbn_api.models import Publication

URL = "/komparator-publikacji-pbn/2022-2025/"
URL_PRZELICZ = URL + "przelicz/"
ZLEC = "komparator_publikacji_pbn.tasks.porownaj_publikacje_task.apply_async"


def _praca(nr, obj=None, rok=2023, **pola):
    """Praca ciągła z różnicą w tytule; ``obj`` — dodatkowe pola rekordu PBN."""
    tytul = f"Praca w PBN {nr:04}"
    pbn = baker.make(
        Publication,
        mongoId=f"odp-{nr}",
        title=tytul,
        year=rok,
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": tytul, **(obj or {})}}],
    )
    return baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=pola.pop("tytul", f"Praca {nr:04}"),
        rok=rok,
        pbn_uid=pbn,
        **pola,
    )


def _meta():
    return KomparatorPublikacjiMeta.get_instance()


def _widoczne():
    return RoznicaPublikacjiPBN.objects.filter(przebieg=_meta().przebieg)


# --- nietypowe dane z PBN ---------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "obj",
    [
        # realny kształt z PBN: słowa kluczowe wg języka
        {"keywords": {"pol": ["nauka", "testowanie"], "eng": ["science"]}},
        {"keywords": {"pol": "nauka; testowanie"}},
        {"keywords": ["nauka", {"pol": "testowanie"}]},
        {"pages": 12},  # liczba stron jako int (879 rekordów w próbce klienta)
        {"issue": 2},
    ],
    ids=[
        "keywords-dict",
        "keywords-dict-str",
        "keywords-lista-z-dict",
        "pages",
        "issue",
    ],
)
def test_ksztalty_danych_spotykane_w_pbn_sa_porownywane_bez_bledu(obj):
    """Te kształty występują w prawdziwych danych PBN — porównanie ma je
    obsłużyć, a nie tylko przeżyć (dawniej wywracały całe przeliczenie)."""
    _praca(1, obj, nr_zeszytu="5", strony="1-10")

    stats = core.przelicz()

    assert stats["errors"] == 0
    assert _meta().status == "completed"
    wiersz = _widoczne().get()
    assert set(obj) <= {"keywords", "pages", "issue"}
    assert {"keywords": "keywords", "pages": "pages", "issue": "issue"}[
        next(iter(obj))
    ] in wiersz.pola


@pytest.mark.django_db
@pytest.mark.parametrize(
    "obj",
    [
        {"conferenceName": {"a": 1}},
        {"series": {"a": 1}},
        {"language": {"code": "pl"}},
        {"publicationPlace": 5},
        {"abstract": {"pol": "x" * 50}},
        {"points": {"2023": {"points": 100}}},
        {"volume": 7},
        {"doi": 5},
        {"publicUri": ["a"]},
    ],
    ids=lambda o: next(iter(o)),
)
def test_nieprzewidziany_ksztalt_pola_nie_przerywa_przeliczenia(obj):
    """Cokolwiek przyjdzie z PBN w jednym polu jednej pracy — przeliczenie
    dobiega końca, a pozostałe prace i pola są porównane."""
    _praca(1, obj)
    _praca(2)

    stats = core.przelicz()

    assert stats["processed"] == 2
    assert _meta().status == "completed"
    assert _widoczne().filter(pola__contains=["title"]).count() == 2


@pytest.mark.django_db
def test_blad_porownania_jednego_pola_jest_izolowany_logowany_i_pokazany(
    admin_client, caplog
):
    """Błąd porównania pola jednej pracy: reszta pól tej pracy i pozostałe
    prace są porównane, błąd idzie do logu z tracebackiem, a lista pokazuje
    licznik „nie udało się porównać”."""
    zla = _praca(1, {"doi": "10.1/pbn"}, doi="10.1/bpp")
    _praca(2)
    prawdziwe = PublicationComparisonView._compare_doi

    def wybuchowe(self, bpp_pub, pbn_pub, differences):
        if bpp_pub.pk == zla.pk:
            raise AttributeError("'dict' object has no attribute 'strip'")
        return prawdziwe(self, bpp_pub, pbn_pub, differences)

    with (
        mock.patch.object(PublicationComparisonView, "_compare_doi", wybuchowe),
        caplog.at_level(logging.ERROR, logger="komparator_publikacji_pbn.core"),
    ):
        stats = core.przelicz()

    assert stats == {"processed": 2, "with_differences": 2, "errors": 1}
    meta = _meta()
    assert (meta.status, meta.liczba_bledow) == ("completed", 1)
    assert meta.przyklad_bledu.startswith("doi: AttributeError")
    wiersz = _widoczne().get(rekord_id=zla.pk)
    assert "title" in wiersz.pola and "doi" not in wiersz.pola
    (rekord,) = [r for r in caplog.records if "błąd porównania pola" in r.message]
    assert rekord.exc_info is not None
    assert f"pk={zla.pk}" in rekord.getMessage()

    tresc = admin_client.get(URL).content.decode()
    assert "Nie udało się porównać: 1" in tresc
    assert "doi: AttributeError" in tresc


@pytest.mark.django_db
def test_log_nie_puchnie_gdy_ten_sam_blad_dotyczy_wielu_prac(caplog):
    for nr in range(core.LIMIT_TRACEBACKOW + 15):
        _praca(nr)

    with (
        mock.patch.object(
            PublicationComparisonView, "_compare_doi", side_effect=TypeError("x")
        ),
        caplog.at_level(logging.WARNING, logger="komparator_publikacji_pbn.core"),
    ):
        stats = core.przelicz()

    assert stats["errors"] == core.LIMIT_TRACEBACKOW + 15
    z_tracebackiem = [r for r in caplog.records if r.exc_info]
    assert len(z_tracebackiem) == core.LIMIT_TRACEBACKOW
    assert any("nie dało się porównać" in r.getMessage() for r in caplog.records)


# --- jedno przeliczenie naraz ----------------------------------------------


@pytest.mark.django_db
def test_drugie_przeliczenie_w_trakcie_pierwszego_jest_odrzucane(monkeypatch):
    """Dawniej dwa nakładające się przeliczenia kasowały sobie wiersze i po
    cichu zostawiały niepełne wyniki (15 albo 10 z 20)."""
    monkeypatch.setattr(core, "PACZKA", 5)
    for nr in range(20):
        _praca(nr)
    proby = []

    def cb(current, total, z_roznicami):
        if current == 5:
            with pytest.raises(core.PrzeliczanieJuzTrwa):
                core.przelicz()
            proby.append(porownaj_publikacje_task.apply(throw=True).result)

    stats = core.przelicz(progress_callback=cb)

    assert proby == [{"status": "SKIPPED", "message": "Trwa inne przeliczenie"}]
    assert stats["processed"] == 20
    meta = _meta()
    assert (meta.status, meta.liczba_z_roznicami) == ("completed", 20)
    assert _widoczne().count() == 20


@pytest.mark.django_db
def test_przebieg_ktory_stracil_wlasnosc_nie_publikuje_i_sprzata_po_sobie(
    monkeypatch,
):
    """Przebieg A uznany za porzucony (brak postępu), rusza B. Gdy A się
    „obudzi”, nie nadpisuje stanu ani wyników B i kasuje własne wiersze."""
    monkeypatch.setattr(core, "PACZKA", 5)
    for nr in range(20):
        _praca(nr)
    przebiegi = {}

    def cb(current, total, z_roznicami):
        if current == 10 and "b" not in przebiegi:
            przebiegi["a"] = _meta().przebieg_w_toku
            # A „zawisa”: brak znaku życia od 10 minut; B liczy całość.
            KomparatorPublikacjiMeta.objects.filter(pk=1).update(
                ostatni_postep=timezone.now() - timedelta(minutes=10)
            )
            przebiegi["b"] = core.przelicz()

    with pytest.raises(core.PrzeliczaniePrzejete):
        core.przelicz(progress_callback=cb)

    meta = _meta()
    assert przebiegi["b"]["processed"] == 20
    assert (meta.status, meta.przebieg_w_toku) == ("completed", None)
    assert _widoczne().count() == 20
    assert not RoznicaPublikacjiPBN.objects.filter(przebieg=przebiegi["a"]).exists()


@pytest.mark.django_db
def test_dwa_klikniecia_naraz_zlecaja_jedno_zadanie(admin_client):
    """Start sprawdza i zajmuje komparator pod blokadą wiersza stanu: drugi
    POST widzi już stan „w toku” i nie zleca drugiego zadania."""
    with (
        mock.patch(
            "komparator_publikacji_pbn.views.is_pbn_publications_data_fresh",
            return_value=(True, None, timezone.now()),
        ),
        mock.patch(ZLEC) as zlec,
    ):
        pierwsza = admin_client.post(URL_PRZELICZ)
        druga = admin_client.post(URL_PRZELICZ)

    assert zlec.call_count == 1
    assert pierwsza["Location"] == druga["Location"]


# --- zabity worker ----------------------------------------------------------


@pytest.fixture
def porzucone_przeliczanie(db):
    """Zakończone przeliczenie (1 praca), a po nim przebieg przerwany w pół
    drogi: status „w toku”, wiersze niedokończonego przebiegu, brak postępu
    od 10 minut."""
    praca = _praca(1)
    core.przelicz()
    stary = _meta().przebieg
    RoznicaPublikacjiPBN.objects.create(
        przebieg=stary + 1,
        typ="ciagle",
        rekord_id=10**6,
        pbn_uid=praca.pbn_uid,
        rok=2023,
        pola=["title"],
    )
    KomparatorPublikacjiMeta.objects.filter(pk=1).update(
        status="running",
        task_id="martwe",
        przebieg_w_toku=stary + 1,
        rozpoczeto=timezone.now() - timedelta(minutes=12),
        ostatni_postep=timezone.now() - timedelta(minutes=10),
    )
    return stary


def test_po_zabiciu_workera_przycisk_wraca_a_stare_wyniki_zostaja(
    admin_client, porzucone_przeliczanie
):
    """Dawniej stan „w toku” blokował komparator na 6 godzin."""
    odpowiedz = admin_client.get(URL)
    tresc = odpowiedz.content.decode()

    assert "Ostatnie przeliczanie zostało przerwane" in tresc
    assert "Przelicz porównanie" in tresc
    assert "Trwa przeliczanie porównania" not in tresc
    assert len(odpowiedz.context["comparisons"]) == 1  # poprzednie wyniki

    with (
        mock.patch(
            "komparator_publikacji_pbn.views.is_pbn_publications_data_fresh",
            return_value=(True, None, timezone.now()),
        ),
        mock.patch(ZLEC) as zlec,
    ):
        admin_client.post(URL_PRZELICZ)
    zlec.assert_called_once()

    _praca(2)
    core.przelicz()
    assert _widoczne().count() == 2
    assert not RoznicaPublikacjiPBN.objects.filter(rekord_id=10**6).exists()


def test_strona_postepu_martwego_zadania_konczy_odpytywanie(
    admin_client, porzucone_przeliczanie
):
    """Dawniej strona postępu martwego zadania odpytywała bez końca."""
    url = URL + "status/martwe/"

    strona = admin_client.get(url).content.decode()
    fragment = admin_client.get(url, headers={"HX-Request": "true"})

    assert "Przeliczanie zostało przerwane" in strona
    assert fragment.status_code == 286  # HTMX: koniec odpytywania
    assert "Przeliczanie zostało przerwane" in fragment.content.decode()


@pytest.mark.django_db
def test_strona_postepu_po_bledzie_pokazuje_blad_i_konczy_odpytywanie(admin_client):
    _meta()
    KomparatorPublikacjiMeta.objects.filter(pk=1).update(
        status="error", task_id="z-bledem", ostatni_blad="RuntimeError: awaria"
    )

    fragment = admin_client.get(
        URL + "status/z-bledem/", headers={"HX-Request": "true"}
    )

    assert fragment.status_code == 286
    assert "RuntimeError: awaria" in fragment.content.decode()


@pytest.mark.django_db
def test_znak_zycia_zapisywany_co_paczke(monkeypatch):
    monkeypatch.setattr(core, "PACZKA", 2)
    for nr in range(5):
        _praca(nr)
    widziane = []

    def cb(current, total, z_roznicami):
        meta = _meta()
        widziane.append((meta.postep_biezacy, meta.postep_razem))
        assert core.przeliczanie_w_toku(meta)

    core.przelicz(progress_callback=cb)

    assert widziane == [(0, 5), (2, 5), (4, 5), (5, 5)]


# --- odczyt w trakcie podmiany wyników --------------------------------------


@pytest.mark.django_db
def test_odczyt_rozpoczety_przed_podmiana_nadal_widzi_wiersze():
    """Żądanie, które odczytało numer przebiegu tuż przed publikacją nowego,
    ma jeszcze swoje wiersze (dawniej: „brak różnic” / sam nagłówek XLSX).
    Stary komplet sprząta dopiero następne przeliczenie."""
    _praca(1)
    core.przelicz()
    odczytany = _meta().przebieg

    core.przelicz()

    assert _meta().przebieg == odczytany + 1
    assert RoznicaPublikacjiPBN.objects.filter(przebieg=odczytany).count() == 1
    assert _widoczne().count() == 1

    core.przelicz()
    assert not RoznicaPublikacjiPBN.objects.filter(przebieg=odczytany).exists()
    assert RoznicaPublikacjiPBN.objects.count() == 2


# --- sprzątanie -------------------------------------------------------------


@pytest.mark.django_db
def test_kasowanie_starych_wynikow_nie_laduje_wierszy_do_pamieci():
    """Stare wyniki kasuje jeden ``DELETE`` — bez sygnałów na wiersz (globalny
    ``post_delete`` easyaudit zmuszałby Django do wczytania całej tabeli)."""
    _praca(1)
    core.przelicz()
    core.przelicz()
    skasowane = []

    def odbiornik(sender, instance, **kwargs):
        skasowane.append(instance.pk)

    post_delete.connect(odbiornik, sender=RoznicaPublikacjiPBN)
    try:
        core.przelicz()
    finally:
        post_delete.disconnect(odbiornik, sender=RoznicaPublikacjiPBN)

    assert skasowane == []
    assert RoznicaPublikacjiPBN.objects.count() == 2


@pytest.mark.django_db
def test_reset_integracji_pbn_po_przeliczeniu_nie_konczy_sie_bledem(admin_client):
    """``pbn_integrator --clear-publications`` kasuje kopie publikacji PBN
    z pominięciem kaskady — wyniki komparatora muszą zniknąć wcześniej."""
    from pbn_integrator.utils.cleanup import clear_publications

    _praca(1)
    core.przelicz()
    assert RoznicaPublikacjiPBN.objects.count() == 1

    clear_publications()
    connection.check_constraints()

    assert not RoznicaPublikacjiPBN.objects.exists()
    assert not Publication.objects.exists()
    tresc = admin_client.get(URL).content.decode()
    assert "Porównanie nie było jeszcze przeliczane" in tresc


# --- lista i eksport --------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "parametry",
    [
        {"year_min": "", "year_max": ""},
        {"year_min": "abc", "year_max": "xyz"},
        {"year_min": "99999999999999999999", "year_max": "-5"},
    ],
)
def test_naglowek_pokazuje_lata_faktycznie_uzyte(admin_client, parametry):
    """Puste albo nieliczbowe „Rok od/do” = lata okresu, także w nagłówku
    (dawniej „publikacje z lat –2030” albo „abc”)."""
    _praca(1)
    core.przelicz()

    odpowiedz = admin_client.get(URL, parametry)

    assert odpowiedz.status_code == 200
    assert "publikacje z lat 2022–2025" in odpowiedz.content.decode()
    assert len(odpowiedz.context["comparisons"]) == 1


@pytest.mark.django_db
def test_znaleziono_i_eksport_bez_prac_skasowanych_po_przeliczeniu(admin_client):
    zostaje = _praca(1)
    skasowana = _praca(2)
    core.przelicz()
    Wydawnictwo_Ciagle.objects.filter(pk=skasowana.pk)._raw_delete("default")

    odpowiedz = admin_client.get(URL)
    eksport = admin_client.get(URL, {"export": "xlsx", "fields": "title"})

    assert odpowiedz.context["paginator"].count == 1
    assert "Znaleziono: <strong>1</strong>" in odpowiedz.content.decode()
    arkusz = load_workbook(BytesIO(b"".join(eksport.streaming_content))).active
    assert [w[1] for w in arkusz.iter_rows(min_row=2, values_only=True)] == [zostaje.pk]


@pytest.mark.django_db
def test_eksport_strumieniowy_z_sanityzacja_formul_i_naglowkiem(admin_client):
    """Eksport nie buduje skoroszytu w pamięci (tryb „tylko zapis”, wysyłka
    strumieniowa), a wartości zaczynające się od „=” nadal nie są formułami."""
    _praca(1, tytul='=HYPERLINK("http://zle")')
    core.przelicz()

    with mock.patch(
        "komparator_publikacji_pbn.views.Workbook",
        wraps=__import__("openpyxl").Workbook,
    ) as workbook:
        eksport = admin_client.get(URL, {"export": "xlsx", "fields": "title"})

    workbook.assert_called_once_with(write_only=True)
    assert eksport.streaming is True
    assert "attachment" in eksport["Content-Disposition"]
    skoroszyt = load_workbook(BytesIO(b"".join(eksport.streaming_content)))
    wiersze = list(skoroszyt.active.iter_rows(values_only=True))
    assert wiersze[0][:3] == ("Typ", "ID BPP", "ID PBN")
    assert skoroszyt.active["A1"].font.bold is True
    (dane,) = wiersze[1:]
    assert "HYPERLINK" in dane[3] and not dane[3].startswith("=")
    assert "HYPERLINK" in dane[6] and not dane[6].startswith("=")
