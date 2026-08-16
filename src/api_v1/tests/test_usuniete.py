"""Testy endpointu ``/api/v1/usuniete/`` — nagrobki dla klientów REST."""

from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_usuniete_zwraca_nagrobek_bez_tresci(api_client, wydawnictwo_ciagle):
    """Nagrobek REST niesie identyfikator, nigdy treść.

    Rekord bywa usuwany właśnie dlatego, że był błędny albo zawierał dane
    osobowe — wystawienie huska w całości cofnęłoby skutek usunięcia.
    """
    tytul = wydawnictwo_ciagle.tytul_oryginalny
    pk = wydawnictwo_ciagle.pk
    wydawnictwo_ciagle.delete()

    odpowiedz = api_client.get(reverse("api_v1:usuniete-list"))
    assert odpowiedz.status_code == 200

    wyniki = odpowiedz.json()["results"]
    assert any(w["model"] == "wydawnictwo_ciagle" and w["pk"] == pk for w in wyniki), (
        f"brak nagrobka dla skasowanego rekordu {pk}: {wyniki}"
    )

    assert tytul not in odpowiedz.content.decode(), (
        "treść usuniętego rekordu wyciekła przez endpoint nagrobków"
    )


@pytest.mark.django_db
def test_usuniete_pomija_rekordy_zywe(api_client, wydawnictwo_ciagle):
    """Endpoint mówi „co zniknęło", więc żywy rekord nie ma tu czego szukać."""
    odpowiedz = api_client.get(reverse("api_v1:usuniete-list"))
    assert odpowiedz.status_code == 200
    assert odpowiedz.json()["results"] == []


@pytest.mark.django_db
def test_usuniete_filtruje_po_zakresie_dat(api_client, wydawnictwo_ciagle):
    """Klient przyrostowy pyta „co zniknęło od ostatniego razu".

    Bez filtra zakresowego musiałby pobierać cały kosz przy każdym
    odpytaniu — czyli dokładnie ten pełny re-harvest, którego ta faza
    ma go pozbawić.
    """
    from bpp.models import Wydawnictwo_Ciagle

    pk = wydawnictwo_ciagle.pk
    wydawnictwo_ciagle.delete()

    usuniety_od = Wydawnictwo_Ciagle.deleted_objects.get(pk=pk).deleted_at
    przed = usuniety_od - timedelta(hours=1)
    po = usuniety_od + timedelta(hours=1)

    url = reverse("api_v1:usuniete-list")

    def wyniki(parametr, moment):
        # ``urlencode``, bo offset strefy ``+00:00`` w surowym query stringu
        # rozkodowałby się jako spacja i data przestałaby się parsować.
        odpowiedz = api_client.get(f"{url}?{urlencode({parametr: moment.isoformat()})}")
        assert odpowiedz.status_code == 200, odpowiedz.content
        return odpowiedz.json()["results"]

    assert wyniki("usuniety_od_after", przed)
    assert wyniki("usuniety_od_before", po)
    assert not wyniki("usuniety_od_after", po)
    assert not wyniki("usuniety_od_before", przed)


@pytest.mark.django_db
def test_usuniete_odrzuca_bledna_date(api_client):
    """Nieparsowalna data to błąd klienta, nie cichy brak filtra.

    Zignorowanie parametru dałoby odpowiedź wyglądającą poprawnie, a
    zawierającą cały kosz — konsument przyrostowy przetworzyłby ją jako
    „to wszystko zniknęło od wczoraj".
    """
    url = reverse("api_v1:usuniete-list")
    odpowiedz = api_client.get(f"{url}?usuniety_od_after=wczoraj")
    assert odpowiedz.status_code == 400


@pytest.mark.django_db
def test_usuniete_sortuje_od_najstarszego(api_client, wydawnictwo_ciagle, patent):
    """Porządek rosnący po dacie — konsument przesuwa kursor do przodu.

    Kasujemy po kolei i polegamy na zegarze zamiast przestawiać
    ``deleted_at`` — patrz uzasadnienie przy fixture ``kosz_szesciu``.
    """
    from bpp.models import Patent, Wydawnictwo_Ciagle

    wydawnictwo_ciagle.delete()
    patent.delete()

    assert (
        Wydawnictwo_Ciagle.deleted_objects.get(pk=wydawnictwo_ciagle.pk).deleted_at
        < Patent.deleted_objects.get(pk=patent.pk).deleted_at
    ), "oba kasowania trafiły w ten sam znacznik — test nie bada kolejności"

    wyniki = api_client.get(reverse("api_v1:usuniete-list")).json()["results"]
    modele = [w["model"] for w in wyniki]
    assert modele == ["wydawnictwo_ciagle", "patent"], wyniki


@pytest.fixture
def kosz_szesciu(db):
    """Sześć nagrobków w dwóch modelach, skasowanych po kolei.

    Znaczników ``deleted_at`` NIE przestawiamy: ``BppSoftDeleteQuerySet``
    słusznie blokuje ``.update(deleted_at=...)`` (omijałoby ``post_save``,
    kaskadę ``*_Autor``, ``SoftDeleteLog`` i reversion), a ``Autor`` ten gate
    dziedziczy. Zamiast obchodzić zabezpieczenie w teście, opieramy się na
    zegarze: każde ``.delete()`` to osobna runda do bazy, więc znaczniki
    wychodzą różne. Fixture to **sprawdza** i pada głośno, gdyby kiedyś
    zaczęły się zlewać — zamiast po cichu produkować flaka.

    Zwraca listę ``(model, pk)`` w oczekiwanym porządku odpowiedzi.
    """
    from model_bakery import baker

    from bpp.models import Autor, Wydawnictwo_Ciagle

    utworzone = []
    for numer in range(6):
        if numer % 2:
            obiekt = baker.make(Autor, nazwisko=f"Nazwisko{numer}", imiona="Jan")
            nazwa, model = "autor", Autor
        else:
            obiekt = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Praca {numer}")
            nazwa, model = "wydawnictwo_ciagle", Wydawnictwo_Ciagle
        obiekt.delete()
        utworzone.append(
            (nazwa, obiekt.pk, model.deleted_objects.get(pk=obiekt.pk).deleted_at)
        )

    znaczniki = [wiersz[2] for wiersz in utworzone]
    assert len(set(znaczniki)) == len(znaczniki), (
        "kasowania zlały się w jeden znacznik czasu — test kolejności stron "
        f"nie miałby czego sprawdzać: {znaczniki}"
    )
    assert znaczniki == sorted(znaczniki), "zegar cofnął się w trakcie fixture"

    return [(nazwa, pk) for nazwa, pk, _ in utworzone]


@pytest.mark.django_db
def test_usuniete_stronicuje(api_client, kosz_szesciu):
    """Odpowiedź jest stronicowana — inaczej duży kosz idzie jednym ciosem."""
    odpowiedz = api_client.get(reverse("api_v1:usuniete-list") + "?limit=2")
    assert odpowiedz.status_code == 200

    tresc = odpowiedz.json()
    assert tresc["count"] == 6, tresc
    assert len(tresc["results"]) == 2
    assert tresc["next"], "brak linku do kolejnej strony"
    assert tresc["previous"] is None


@pytest.mark.django_db
def test_usuniete_przejscie_stron_nie_gubi_i_nie_dubluje(api_client, kosz_szesciu):
    """Przejście po ``next`` oddaje komplet, w porządku dat, bez powtórek."""
    url = reverse("api_v1:usuniete-list") + "?limit=2"
    zebrane = []
    daty = []

    for _ in range(20):
        tresc = api_client.get(url).json()
        zebrane.extend((w["model"], w["pk"]) for w in tresc["results"])
        daty.extend(w["usuniety_od"] for w in tresc["results"])
        if not tresc["next"]:
            break
        url = tresc["next"]
    else:
        raise AssertionError("stronicowanie się nie zakończyło")

    assert len(zebrane) == len(set(zebrane)), f"rekord wyszedł dwa razy: {zebrane}"
    assert zebrane == kosz_szesciu, "kolejność albo komplet się nie zgadza"
    assert daty == sorted(daty), "porządek dat rozjechał się na granicy strony"


@pytest.mark.django_db
def test_usuniete_stronicowanie_wspolpracuje_z_filtrem(api_client, kosz_szesciu):
    """``count`` liczy przefiltrowany zbiór, nie cały kosz.

    Gdyby ``count`` szedł po całości, klient przyrostowy stronicowałby
    w nieskończoność po pustych stronach.
    """
    from bpp.models import Autor

    nazwa, pk = kosz_szesciu[3]
    assert nazwa == "autor"
    moment = Autor.deleted_objects.get(pk=pk).deleted_at

    url = reverse("api_v1:usuniete-list")
    tresc = api_client.get(
        f"{url}?{urlencode({'usuniety_od_after': moment.isoformat(), 'limit': 2})}"
    ).json()

    # Rekordy 3, 4 i 5 (licząc od zera) mają datę >= momentowi rekordu 3.
    assert tresc["count"] == 3, tresc
    assert len(tresc["results"]) == 2


@pytest.mark.django_db(transaction=False)
def test_usuniete_tnie_strone_w_bazie_a_nie_w_pythonie(api_client, kosz_szesciu):
    """``LIMIT``/``OFFSET`` muszą zejść do SQL-a.

    To jedyny powód, dla którego endpoint składa ``UNION`` zamiast sklejać
    sześć list w Pythonie. Gdyby slice wykonywał się po stronie aplikacji,
    każde żądanie ciągnęłoby CAŁY kosz — a przy stronicowaniu klient robi
    N żądań zamiast jednego, więc łączna praca byłaby WIĘKSZA niż przed
    wprowadzeniem stron. Ten test pilnuje, żeby optymalizacja nie
    zdegradowała się po cichu do pesymalizacji.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as zapytania:
        odpowiedz = api_client.get(reverse("api_v1:usuniete-list") + "?limit=2")

    assert odpowiedz.status_code == 200
    assert len(odpowiedz.json()["results"]) == 2

    # Bez filtra na ``startswith("SELECT")``: złączone zapytanie zaczyna się
    # od nawiasu (``(SELECT ...) UNION ALL (SELECT ...)``), więc taki warunek
    # przepuszczałby wyłącznie zapytanie ``COUNT``.
    zlaczone = [
        z["sql"] for z in zapytania.captured_queries if "UNION" in z["sql"].upper()
    ]
    assert zlaczone, "brak złączonego zapytania — UNION się nie wykonał"

    z_limitem = [s for s in zlaczone if "LIMIT 2" in s.upper()]
    assert z_limitem, (
        "złączone zapytanie poszło bez LIMIT-u — strona jest wycinana "
        f"w Pythonie po pobraniu całego kosza:\n{zlaczone}"
    )
