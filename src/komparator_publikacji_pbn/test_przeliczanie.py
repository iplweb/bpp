"""Komparator publikacji PBN: przeliczanie w tle do tabeli wyników (FD#514)."""

from io import BytesIO
from unittest import mock

import pytest
from django.utils import timezone
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from komparator_publikacji_pbn import core
from komparator_publikacji_pbn.models import (
    KomparatorPublikacjiMeta,
    RoznicaPublikacjiPBN,
)
from komparator_publikacji_pbn.tasks import porownaj_publikacje_task
from komparator_publikacji_pbn.views import COMPARISON_FIELDS, PublicationComparisonView
from pbn_api.models import Publication

URL = "/komparator-publikacji-pbn/2022-2025/"
URL_PRZELICZ = "/komparator-publikacji-pbn/2022-2025/przelicz/"
NA_STRONE = PublicationComparisonView.paginate_by


def _praca(nr, model=Wydawnictwo_Ciagle, rok=2023, zgodna=False, autorzy=0):
    """Praca BPP powiązana z PBN; ``zgodna=False`` → różnica w tytule."""
    tytul_pbn = f"Praca {nr:04}" if zgodna else f"Praca w PBN {nr:04}"
    pbn = baker.make(
        Publication,
        mongoId=f"{model.__name__}-{nr}",
        title=tytul_pbn,
        year=rok,
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": tytul_pbn}}],
    )
    praca = baker.make(model, tytul_oryginalny=f"Praca {nr:04}", rok=rok, pbn_uid=pbn)
    for kolejnosc in range(autorzy):
        baker.make(f"bpp.{model.__name__}_Autor", rekord=praca, kolejnosc=kolejnosc)
    return praca


@pytest.fixture
def swieze_dane_pbn():
    with mock.patch(
        "komparator_publikacji_pbn.views.is_pbn_publications_data_fresh",
        return_value=(True, None, timezone.now()),
    ):
        yield


@pytest.mark.django_db
def test_przeliczenie_obejmuje_wszystkie_prace_bez_limitu_100():
    """Dawniej porównywane było pierwsze 100 prac każdego typu; teraz
    wszystkie powiązane z PBN (tu: 130 ciągłych i 5 zwartych)."""
    for nr in range(130):
        _praca(nr)
    for nr in range(5):
        _praca(nr, Wydawnictwo_Zwarte)
    _praca(999, zgodna=True)

    stats = core.przelicz()

    assert stats["processed"] == 136
    z_tytulem = RoznicaPublikacjiPBN.objects.filter(pola__contains=["title"])
    assert z_tytulem.filter(typ="ciagle").count() == 130
    assert z_tytulem.filter(typ="zwarte").count() == 5
    meta = KomparatorPublikacjiMeta.get_instance()
    assert meta.status == "completed"
    assert meta.liczba_prac == 136
    assert meta.liczba_z_roznicami == stats["with_differences"]
    assert meta.ostatnie_uruchomienie is not None


@pytest.mark.django_db
def test_wynik_zgodny_z_porownaniem_pojedynczej_pracy():
    """Strażnik: tabela wyników zawiera dokładnie te różnice, które daje
    dotychczasowe porównanie pól (logika porównania się nie zmienia)."""
    praca = _praca(1, autorzy=2)
    oczekiwane = PublicationComparisonView()._compare_publication(
        praca, "ciagle", list(COMPARISON_FIELDS)
    )["differences"]

    core.przelicz()

    wiersz = RoznicaPublikacjiPBN.objects.get()
    bez_klucza = [{k: v for k, v in r.items() if k != "key"} for r in wiersz.roznice]
    assert sorted(bez_klucza, key=repr) == sorted(oczekiwane, key=repr)
    assert set(wiersz.pola) == {r["key"] for r in wiersz.roznice}
    assert {"title", "authors"} <= set(wiersz.pola)
    assert (wiersz.rekord_id, wiersz.rok, wiersz.tytul) == (
        praca.pk,
        2023,
        "Praca 0001",
    )


@pytest.mark.django_db
def test_ponowne_przeliczenie_podmienia_wyniki():
    """Praca poprawiona w BPP znika z wyników po przeliczeniu; nie zostają
    wiersze poprzedniego przeliczenia."""
    praca = _praca(1)
    _praca(2)
    z_tytulem = RoznicaPublikacjiPBN.objects.filter(pola__contains=["title"])
    core.przelicz()
    assert z_tytulem.count() == 2

    praca.tytul_oryginalny = praca.pbn_uid.title
    praca.save()
    core.przelicz()

    przebieg = KomparatorPublikacjiMeta.get_instance().przebieg
    biezace = z_tytulem.filter(przebieg=przebieg)
    assert list(biezace.values_list("tytul", flat=True)) == ["Praca 0002"]


@pytest.mark.django_db
def test_widok_pokazuje_poprzednie_wyniki_gdy_przeliczenie_sie_wywroci():
    """Błąd w trakcie przeliczania nie niszczy wyników pokazywanych w widoku,
    a resztki przerwanego przebiegu sprząta następne przeliczenie."""
    _praca(1)
    core.przelicz()
    przebieg = KomparatorPublikacjiMeta.get_instance().przebieg
    _praca(2)

    with mock.patch.object(core, "PACZKA", 1):
        with mock.patch.object(
            core, "_wiersz", side_effect=[mock.DEFAULT, RuntimeError("awaria")]
        ) as wiersz:
            wiersz.return_value = RoznicaPublikacjiPBN(
                przebieg=przebieg + 1,
                typ="ciagle",
                rekord_id=10**6,
                pbn_uid=Publication.objects.first(),
                rok=2023,
            )
            with pytest.raises(RuntimeError):
                porownaj_publikacje_task.apply(throw=True)

    meta = KomparatorPublikacjiMeta.get_instance()
    assert meta.przebieg == przebieg
    assert meta.status == "error"
    assert "awaria" in meta.ostatni_blad
    assert RoznicaPublikacjiPBN.objects.filter(przebieg=przebieg).count() == 1

    core.przelicz()
    meta = KomparatorPublikacjiMeta.get_instance()
    assert meta.status == "completed"
    assert RoznicaPublikacjiPBN.objects.filter(przebieg=meta.przebieg).count() == 2
    assert not RoznicaPublikacjiPBN.objects.filter(rekord_id=10**6).exists()


@pytest.mark.django_db
def test_przeliczanie_bez_zapytan_na_prace(django_assert_max_num_queries):
    """Liczba zapytań nie zależy od liczby prac ani autorów (liczba autorów,
    źródło, wydawca itd. dociągane paczkami)."""
    for nr in range(30):
        _praca(nr, autorzy=3)
    for nr in range(30):
        _praca(nr, Wydawnictwo_Zwarte, autorzy=2)

    # Zmierzone: 23 dla 60 prac ze 150 autorami (jedna paczka na typ pracy).
    with django_assert_max_num_queries(30):
        stats = core.przelicz()

    assert stats["processed"] == 60
    wiersz = RoznicaPublikacjiPBN.objects.filter(typ="ciagle").first()
    autorzy = [r for r in wiersz.roznice if r["key"] == "authors"]
    assert autorzy[0]["bpp_value"] == "3"


@pytest.mark.django_db
def test_zadanie_raportuje_postep():
    """Zadanie w tle podaje postęp (ile z ilu) — z tego rysuje się pasek."""
    for nr in range(5):
        _praca(nr)
    stany = []

    with (
        mock.patch.object(core, "PACZKA", 2),
        mock.patch.object(
            porownaj_publikacje_task,
            "update_state",
            side_effect=lambda **kw: stany.append(kw["meta"]),
        ),
    ):
        wynik = porownaj_publikacje_task.apply(throw=True).result

    assert wynik["stats"]["processed"] == 5
    assert [(s["current"], s["total"]) for s in stany] == [
        (0, 5),
        (2, 5),
        (4, 5),
        (5, 5),
    ]
    assert stany[-1]["progress"] == 100
    assert stany[1]["progress"] == 40


@pytest.mark.django_db
def test_lista_stronicowana_w_bazie_i_stan_na(
    admin_client, uczelnia, django_assert_max_num_queries
):
    for nr in range(NA_STRONE + 7):
        _praca(nr)
    core.przelicz()

    admin_client.get(URL)  # rozgrzanie
    # Zmierzone: 37, z czego ~32 to obudowa strony; lista to liczba wyników,
    # wiersze strony, prace BPP i kopie PBN — bez zapytań na pracę.
    with django_assert_max_num_queries(42):
        pierwsza = admin_client.get(URL)
    druga = admin_client.get(URL, {"page": 2})

    assert len(pierwsza.context["comparisons"]) == NA_STRONE
    assert len(druga.context["comparisons"]) == 7
    assert pierwsza.context["paginator"].count == NA_STRONE + 7
    tresc = pierwsza.content.decode()
    assert "Stan na " in tresc
    assert f"Znaleziono: <strong>{NA_STRONE + 7}</strong>" in tresc
    assert 'class="pagination' in tresc
    assert "Przelicz porównanie" in tresc
    # numer strony spoza zakresu nie daje 404
    assert admin_client.get(URL, {"page": 99}).status_code == 200


@pytest.mark.django_db
def test_przed_pierwszym_przeliczeniem_komunikat_zamiast_wynikow(admin_client):
    _praca(1)

    tresc = admin_client.get(URL).content.decode()

    assert "Porównanie nie było jeszcze przeliczane" in tresc
    assert "Przelicz porównanie" in tresc


@pytest.mark.django_db
def test_filtr_pol_pokazuje_tylko_prace_z_roznica_w_wybranych_polach(admin_client):
    """Wybór pól działa na gotowych wynikach: praca z różnicą tylko w tytule
    znika, gdy porównujemy sam rok."""
    _praca(1)
    core.przelicz()

    response = admin_client.get(URL, {"fields": "year"})
    assert response.context["comparisons"] == []

    response = admin_client.get(URL, {"fields": ["year", "title"]})
    (porownanie,) = response.context["comparisons"]
    assert [d["field"] for d in porownanie["differences"]] == ["Tytuł"]


@pytest.mark.django_db
def test_eksport_xlsx_obejmuje_calosc_nie_jedna_strone(admin_client):
    for nr in range(NA_STRONE + 7):
        _praca(nr)
    _praca(500, rok=2019)
    core.przelicz()

    response = admin_client.get(URL, {"export": "xlsx", "fields": "title"})

    arkusz = load_workbook(BytesIO(b"".join(response.streaming_content))).active
    wiersze = list(arkusz.iter_rows(min_row=2, values_only=True))
    assert len(wiersze) == NA_STRONE + 7
    assert {w[5] for w in wiersze} == {"Tytuł"}
    assert {w[4] for w in wiersze} == {2023}


ZLEC = "komparator_publikacji_pbn.tasks.porownaj_publikacje_task.apply_async"


@pytest.mark.django_db
def test_przycisk_przelicz_uruchamia_zadanie_i_prowadzi_do_postepu(
    admin_client, swieze_dane_pbn
):
    with mock.patch(ZLEC) as zlec:
        response = admin_client.post(URL_PRZELICZ)

    meta = KomparatorPublikacjiMeta.get_instance()
    assert meta.status == "running" and meta.task_id
    zlec.assert_called_once_with(task_id=meta.task_id)
    assert response.status_code == 302
    assert response["Location"].endswith(f"/status/{meta.task_id}/")

    # drugi klik w trakcie: bez drugiego zadania, od razu do postępu pierwszego
    with mock.patch(ZLEC) as zlec:
        response = admin_client.post(URL_PRZELICZ)
    zlec.assert_not_called()
    assert response["Location"].endswith(f"/status/{meta.task_id}/")

    tresc = admin_client.get(URL).content.decode()
    assert "Trwa przeliczanie porównania" in tresc
    assert f"/status/{meta.task_id}/" in tresc


@pytest.mark.django_db
def test_przelicz_wymaga_swiezych_danych_pbn_post_i_uprawnien(admin_client, client):
    with (
        mock.patch(
            "komparator_publikacji_pbn.views.is_pbn_publications_data_fresh",
            return_value=(False, "dane PBN są nieaktualne", None),
        ),
        mock.patch(
            "komparator_publikacji_pbn.tasks.porownaj_publikacje_task.delay"
        ) as delay,
    ):
        response = admin_client.post(URL_PRZELICZ, follow=True)
    delay.assert_not_called()
    assert "Nie można przeliczyć porównania" in response.content.decode()

    assert admin_client.get(URL_PRZELICZ).status_code == 405
    assert client.post(URL_PRZELICZ).status_code == 302  # logowanie
    assert KomparatorPublikacjiMeta.get_instance().status == "idle"


URL_STATUS = "/komparator-publikacji-pbn/2022-2025/status/{}/"


def _stan(**pola):
    KomparatorPublikacjiMeta.get_instance()
    KomparatorPublikacjiMeta.objects.filter(pk=1).update(**pola)


@pytest.mark.django_db
def test_strona_postepu_pokazuje_pasek_i_po_zakonczeniu_wraca_na_liste(admin_client):
    url = URL_STATUS.format("zadanie-1")
    _stan(
        status="running",
        task_id="zadanie-1",
        przebieg_w_toku=1,
        ostatni_postep=timezone.now(),
        postep_biezacy=50,
        postep_razem=200,
    )

    strona = admin_client.get(url).content.decode()
    fragment = admin_client.get(url, headers={"HX-Request": "true"})

    assert 'hx-trigger="every 5s"' in strona
    assert 'role="progressbar"' in strona and "width: 25%" in strona
    assert fragment.status_code == 200
    assert "50 / 200 prac" in fragment.content.decode()
    assert "<html" not in fragment.content.decode()

    _stan(status="completed", przebieg_w_toku=None, liczba_prac=200)
    koniec = admin_client.get(url, headers={"HX-Request": "true"})

    assert koniec["HX-Redirect"] == "/komparator-publikacji-pbn/2022-2025/"


@pytest.mark.django_db
def test_strona_postepu_cudzego_lub_zastapionego_zadania_wraca_na_liste(
    admin_client,
):
    _stan(status="running", task_id="nowe", ostatni_postep=timezone.now())

    odpowiedz = admin_client.get(URL_STATUS.format("stare"))
    htmx = admin_client.get(URL_STATUS.format("stare"), headers={"HX-Request": "1"})

    assert odpowiedz.status_code == 302
    assert htmx["HX-Redirect"] == "/komparator-publikacji-pbn/2022-2025/"


@pytest.mark.django_db
def test_blad_uruchomienia_zadania_nie_blokuje_kolejnej_proby(
    admin_client, swieze_dane_pbn
):
    """Gdy zadania nie da się zlecić (np. broker nie działa), komparator nie
    zostaje w stanie „trwa przeliczanie”."""
    with mock.patch(ZLEC, side_effect=ConnectionError("broker nie działa")):
        response = admin_client.post(URL_PRZELICZ, follow=True)

    tresc = response.content.decode()
    assert "Nie udało się uruchomić zadania w tle" in tresc
    assert "Przelicz porównanie" in tresc
    assert KomparatorPublikacjiMeta.get_instance().status == "error"
