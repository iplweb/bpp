"""Strony „Uzgodnij z PBN”: uprawnienia, multi-hosted, uruchamianie."""

import io

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker
from openpyxl import load_workbook

from bpp import const
from bpp.models import Uczelnia
from pbn_uzgadnianie import silnik, views
from pbn_uzgadnianie.models import UzgodnienieZPBN

pytestmark = pytest.mark.django_db

ADRESY_PRZEBIEGU = ["szczegoly", "stan", "raport_xlsx"]
AKCJE_PRZEBIEGU = ["anuluj", "wykonaj"]


@pytest.fixture
def redaktor(django_user_model, client):
    from django.contrib.auth.models import Group

    user = baker.make(
        django_user_model, pbn_token="token", pbn_token_updated=timezone.now()
    )
    user.groups.add(Group.objects.get_or_create(name=const.GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)
    return user


@pytest.fixture
def zlecenia(mocker):
    return mocker.patch.object(views.uzgodnij_z_pbn, "delay")


def test_anonim_jest_odsylany_do_logowania(client, uczelnia_pbn):
    odp = client.get(reverse("pbn_uzgadnianie:main"))
    assert odp.status_code == 302
    assert "login" in odp.url


def test_uzytkownik_bez_grupy_nie_ma_dostepu(
    client, django_user_model, uczelnia_pbn, przebieg, zlecenia
):
    client.force_login(baker.make(django_user_model))
    p = przebieg()

    assert client.get(reverse("pbn_uzgadnianie:main")).status_code == 403
    odp = client.post(
        reverse("pbn_uzgadnianie:start"),
        {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"},
    )
    assert odp.status_code == 403
    for nazwa in ADRESY_PRZEBIEGU:
        assert (
            client.get(reverse(f"pbn_uzgadnianie:{nazwa}", args=[p.pk])).status_code
            == 403
        )
    for nazwa in AKCJE_PRZEBIEGU:
        assert (
            client.post(reverse(f"pbn_uzgadnianie:{nazwa}", args=[p.pk])).status_code
            == 403
        )
    zlecenia.assert_not_called()
    assert UzgodnienieZPBN.objects.count() == 1


def test_redaktor_widzi_strone_i_uruchamia_podglad(
    client, redaktor, uczelnia_pbn, zlecenia, django_capture_on_commit_callbacks
):
    assert client.get(reverse("pbn_uzgadnianie:main")).status_code == 200

    with django_capture_on_commit_callbacks(execute=True):
        odp = client.post(
            reverse("pbn_uzgadnianie:start"),
            {"rok_od": 2025, "rok_do": 2026, "tryb": "podglad"},
        )

    p = UzgodnienieZPBN.objects.get()
    assert odp.status_code == 302
    assert odp.url == reverse("pbn_uzgadnianie:szczegoly", args=[p.pk])
    assert (p.uczelnia, p.user, p.rok_od, p.rok_do) == (
        uczelnia_pbn,
        redaktor,
        2025,
        2026,
    )
    assert p.to_podglad and p.status == "oczekuje"
    zlecenia.assert_called_once_with(p.pk)
    # Strona przebiegu w toku pokazuje postęp i przycisk anulowania.
    strona = client.get(odp.url).content.decode()
    assert "Anuluj" in strona


def test_drugie_uruchomienie_w_trakcie_pierwszego_jest_odrzucane(
    client, redaktor, uczelnia_pbn, zlecenia, django_capture_on_commit_callbacks
):
    dane = {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"}
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), dane)
        client.post(reverse("pbn_uzgadnianie:start"), dane)

    assert UzgodnienieZPBN.objects.count() == 1
    assert zlecenia.call_count == 1


def test_bez_autoryzacji_w_pbn_nie_da_sie_uruchomic(
    client, redaktor, uczelnia_pbn, zlecenia
):
    redaktor.pbn_token = ""
    redaktor.save()

    odp = client.post(
        reverse("pbn_uzgadnianie:start"),
        {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"},
    )

    assert odp.status_code == 302
    assert not UzgodnienieZPBN.objects.exists()
    zlecenia.assert_not_called()
    assert (
        "autoryzuj PBN API"
        in client.get(reverse("pbn_uzgadnianie:main")).content.decode()
    )


@pytest.mark.parametrize(
    "dane", [{"rok_od": 2026, "rok_do": 2020}, {"rok_od": "x", "rok_do": 2026}]
)
def test_bledny_zakres_lat_nie_uruchamia(
    client, redaktor, uczelnia_pbn, zlecenia, dane
):
    client.post(reverse("pbn_uzgadnianie:start"), {**dane, "tryb": "wykonanie"})

    assert not UzgodnienieZPBN.objects.exists()
    zlecenia.assert_not_called()


def test_przebieg_innej_uczelni_jest_niewidoczny(
    client, redaktor, uczelnia_pbn, przebieg, zlecenia
):
    """Multi-hosted: redaktor uczelni A nie widzi ani nie rusza przebiegu B."""
    druga = baker.make(Uczelnia, skrot="DRU")
    cudzy = przebieg(uczelnia=druga, tryb="podglad", status="zakonczone")
    aktywny_cudzy = przebieg(uczelnia=baker.make(Uczelnia, skrot="TRZ"))

    for nazwa in ADRESY_PRZEBIEGU:
        assert (
            client.get(reverse(f"pbn_uzgadnianie:{nazwa}", args=[cudzy.pk])).status_code
            == 404
        )
    for nazwa in AKCJE_PRZEBIEGU:
        assert (
            client.post(
                reverse(f"pbn_uzgadnianie:{nazwa}", args=[cudzy.pk])
            ).status_code
            == 404
        )
    assert (
        client.post(
            reverse("pbn_uzgadnianie:anuluj", args=[aktywny_cudzy.pk])
        ).status_code
        == 404
    )

    aktywny_cudzy.refresh_from_db()
    assert aktywny_cudzy.anuluj is False
    zlecenia.assert_not_called()
    assert str(cudzy.pk) not in [
        str(p.pk)
        for p in client.get(reverse("pbn_uzgadnianie:main")).context["przebiegi"]
    ]


def test_aktywny_przebieg_innej_uczelni_nie_blokuje(
    client,
    redaktor,
    uczelnia_pbn,
    przebieg,
    zlecenia,
    django_capture_on_commit_callbacks,
):
    przebieg(uczelnia=baker.make(Uczelnia, skrot="DRU"))

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("pbn_uzgadnianie:start"),
            {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"},
        )

    assert UzgodnienieZPBN.objects.filter(uczelnia=uczelnia_pbn).count() == 1
    zlecenia.assert_called_once()


def test_anulowanie_ustawia_znacznik(client, redaktor, przebieg):
    p = przebieg()

    client.post(reverse("pbn_uzgadnianie:anuluj", args=[p.pk]))

    p.refresh_from_db()
    assert p.anuluj is True


def test_wykonanie_zakonczonego_podgladu(
    client, redaktor, przebieg, zlecenia, django_capture_on_commit_callbacks
):
    podglad = przebieg(tryb="podglad", status="zakonczone", rok_od=2024, rok_do=2025)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:wykonaj", args=[podglad.pk]))

    wykonanie = UzgodnienieZPBN.objects.get(na_podstawie=podglad)
    assert (wykonanie.tryb, wykonanie.rok_od, wykonanie.rok_do) == (
        "wykonanie",
        2024,
        2025,
    )
    zlecenia.assert_called_once_with(wykonanie.pk)


def test_nie_da_sie_wykonac_niezakonczonego_podgladu_ani_wykonania(
    client, redaktor, przebieg, zlecenia
):
    w_toku = przebieg(tryb="podglad", status="w_toku")
    client.post(reverse("pbn_uzgadnianie:wykonaj", args=[w_toku.pk]))
    w_toku.status = "blad"
    w_toku.save()
    wykonanie = przebieg(tryb="wykonanie", status="zakonczone")
    client.post(reverse("pbn_uzgadnianie:wykonaj", args=[wykonanie.pk]))

    assert UzgodnienieZPBN.objects.count() == 2
    zlecenia.assert_not_called()


def test_raport_na_stronie_i_w_xlsx(client, redaktor, przebieg):
    wpisy = [
        {
            "kategoria": silnik.UTWORZONO,
            "pbn_uid": "pbn-nowa",
            "pbn_tytul": "Monografia utworzona",
            "pbn_rok": 2026,
            "bpp_model": "wydawnictwo_zwarte",
            "bpp_pk": 7,
            "bpp_tytul": "Monografia utworzona",
            "bpp_rok": 2026,
            "wersja": "przypięta na profilu instytucji",
        },
        {
            "kategoria": silnik.ROZNI_SIE,
            "pbn_uid": "pbn-rozna",
            "pbn_tytul": "=HYPERLINK(1)",
            "roznice": [{"pole": "Rok", "bpp": "2025", "pbn": "2026"}],
        },
    ]
    p = przebieg(
        tryb="podglad",
        status="zakonczone",
        wynik=wpisy,
        podsumowanie=silnik.podsumuj(wpisy),
    )

    strona = client.get(
        reverse("pbn_uzgadnianie:szczegoly", args=[p.pk])
    ).content.decode()
    assert "Do wykonania: Utworzono rekord w BPP" in strona
    assert "Wykonaj ten podgląd" in strona
    assert "Rok: „2025” → „2026”" in strona
    assert reverse("admin:bpp_wydawnictwo_zwarte_change", args=[7]) in strona

    odp = client.get(reverse("pbn_uzgadnianie:raport_xlsx", args=[p.pk]))
    arkusz = load_workbook(io.BytesIO(odp.content))["Raport"]
    wiersze = list(arkusz.iter_rows(values_only=True))
    assert wiersze[1][:3] == (
        "Utworzono rekord w BPP",
        "pbn-nowa",
        "Monografia utworzona",
    )
    assert wiersze[2][12] == "Rok: „2025” → „2026”"
    # Tytuł z PBN to dane obce — nie może wejść do arkusza jako formuła.
    assert not str(wiersze[2][2]).startswith("=")


def test_przerwany_przebieg_zwalnia_blokade(uczelnia_pbn, przebieg):
    stary = przebieg(status="w_toku")
    UzgodnienieZPBN.objects.filter(pk=stary.pk).update(
        ostatnia_aktualizacja=timezone.now() - timezone.timedelta(hours=2)
    )

    assert UzgodnienieZPBN.oznacz_przerwane(uczelnia_pbn) == 1

    stary.refresh_from_db()
    assert stary.status == "blad"
    przebieg()  # nowy aktywny przebieg da się już utworzyć
