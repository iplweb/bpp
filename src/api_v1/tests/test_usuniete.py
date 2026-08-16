"""Testy endpointu ``/api/v1/usuniete/`` — nagrobki dla klientów REST."""

from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone


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
    """Porządek rosnący po dacie — konsument przesuwa kursor do przodu."""
    from bpp.models import Patent, Wydawnictwo_Ciagle

    wydawnictwo_ciagle.delete()
    patent.delete()

    # Rozsuwamy znaczniki, żeby porządek nie zależał od rozdzielczości zegara.
    Wydawnictwo_Ciagle.deleted_objects.filter(pk=wydawnictwo_ciagle.pk).update(
        deleted_at=timezone.now() - timedelta(days=2)
    )
    Patent.deleted_objects.filter(pk=patent.pk).update(
        deleted_at=timezone.now() - timedelta(days=1)
    )

    wyniki = api_client.get(reverse("api_v1:usuniete-list")).json()["results"]
    modele = [w["model"] for w in wyniki]
    assert modele == ["wydawnictwo_ciagle", "patent"], wyniki
