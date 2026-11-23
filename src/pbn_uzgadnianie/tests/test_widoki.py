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


def _pobranie(przebieg, godzin_temu=1, rok_od=2020, rok_do=2030, **pola):
    """Zakończone pobranie danych z PBN sprzed ``godzin_temu`` godzin."""
    kiedy = (timezone.now() - timezone.timedelta(hours=godzin_temu)).isoformat()
    return przebieg(
        tryb="pobranie",
        status="zakonczone",
        rok_od=rok_od,
        rok_do=rok_do,
        zakonczono=timezone.now(),
        zakres={
            "pobrano": {"profil": kiedy, "publikacje": kiedy, "oswiadczenia": kiedy},
            "pobrano_lata": [rok_od, rok_do],
            "profil": {},
            "w_zakresie": [],
        },
        **pola,
    )


@pytest.fixture
def pobrane(przebieg):
    return _pobranie(przebieg)


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
    client,
    redaktor,
    uczelnia_pbn,
    zlecenia,
    django_capture_on_commit_callbacks,
    pobrane,
):
    assert client.get(reverse("pbn_uzgadnianie:main")).status_code == 200

    with django_capture_on_commit_callbacks(execute=True):
        odp = client.post(
            reverse("pbn_uzgadnianie:start"),
            {"rok_od": 2025, "rok_do": 2026, "tryb": "podglad"},
        )

    p = UzgodnienieZPBN.objects.get(tryb="podglad")
    assert p.na_podstawie == pobrane
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
    client,
    redaktor,
    uczelnia_pbn,
    zlecenia,
    django_capture_on_commit_callbacks,
    pobrane,
):
    dane = {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"}
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), dane)
        client.post(reverse("pbn_uzgadnianie:start"), dane)

    assert UzgodnienieZPBN.objects.filter(tryb="wykonanie").count() == 1
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
    pobrane,
):
    przebieg(uczelnia=baker.make(Uczelnia, skrot="DRU"))

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("pbn_uzgadnianie:start"),
            {"rok_od": 2026, "rok_do": 2026, "tryb": "wykonanie"},
        )

    assert (
        UzgodnienieZPBN.objects.filter(uczelnia=uczelnia_pbn, tryb="wykonanie").count()
        == 1
    )
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
            "bpp_model": "wydawnictwo_ciagle",
            "bpp_pk": 9,
            "bpp_tytul": "Artykuł różniący się",
            "bpp_rok": 2025,
            "roznice": [
                {"pole": "Rok", "bpp": "2025", "pbn": "2026"},
                {
                    "pole": "Tytuł",
                    "bpp": "Badanie wpływu światła na <b>wzrost</b> roślin",
                    "pbn": "Badanie wpływu ciepła na <b>wzrost</b> roślin",
                },
                {
                    "pole": "Dyscyplina (Kowalski Jan)",
                    "bpp": "nauki medyczne",
                    "pbn": "",
                    "brak_pbn": "brak oświadczenia w PBN",
                },
            ],
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
    # Każda różnica w osobnym wierszu: pole | BPP | PBN, z wyróżnieniem.
    assert "Ten sam PBN UID po obu stronach:</strong> pbn-rozna" in strona
    assert "<td>Rok</td>" in strona and "<mark>2025</mark>" in strona
    assert "<mark>światła</mark>" in strona and "<mark>ciepła</mark>" in strona
    assert "<mark>Badanie" not in strona, "podświetlono część wspólną"
    assert "&lt;b&gt;wzrost&lt;/b&gt;" in strona, "HTML z danych nie jest escapowany"
    assert "<em>brak oświadczenia w PBN</em>" in strona
    assert reverse("admin:bpp_wydawnictwo_ciagle_change", args=[9]) in strona
    assert reverse("admin:bpp_wydawnictwo_zwarte_change", args=[7]) in strona

    odp = client.get(reverse("pbn_uzgadnianie:raport_xlsx", args=[p.pk]))
    arkusz = load_workbook(io.BytesIO(odp.content))["Raport"]
    wiersze = list(arkusz.iter_rows(values_only=True))
    assert wiersze[1][:3] == (
        "Utworzono rekord w BPP",
        "pbn-nowa",
        "Monografia utworzona",
    )
    assert wiersze[2][12].startswith("Rok: „2025” → „2026”; Tytuł:")
    roznice = list(
        load_workbook(io.BytesIO(odp.content))["Różnice"].iter_rows(values_only=True)
    )
    assert roznice[1] == (
        "pbn-rozna",
        "wydawnictwo_ciagle",
        9,
        "Artykuł różniący się",
        "Rok",
        "2025",
        "2026",
    )
    assert roznice[3][4:] == (
        "Dyscyplina (Kowalski Jan)",
        "nauki medyczne",
        "brak oświadczenia w PBN",
    )
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


# -- z kiedy są dane z PBN ----------------------------------------------------

START = {"rok_od": 2026, "rok_do": 2026}


def _strona(client):
    return client.get(reverse("pbn_uzgadnianie:main")).content.decode()


def test_brak_danych_czytelny_komunikat_i_brak_pustego_raportu(
    client, redaktor, uczelnia_pbn, zlecenia
):
    assert "Nie ma jeszcze pobranych danych z PBN" in _strona(client)

    odp = client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "podglad"})

    assert odp.status_code == 302
    assert not UzgodnienieZPBN.objects.exists(), "powstał przebieg bez danych"
    zlecenia.assert_not_called()
    assert "Nie ma pobranych danych z PBN dla lat 2026–2026" in _strona(client)


def test_swieze_dane_pokazuja_date_bez_ostrzezenia(client, redaktor, przebieg):
    _pobranie(przebieg, godzin_temu=2)

    strona = _strona(client)

    dzis = timezone.localtime(timezone.now() - timezone.timedelta(hours=2))
    assert f"{dzis:%d.%m.%Y %H:%M}" in strona
    for zrodlo in ("profil instytucji", "publikacje", "oświadczenia"):
        assert zrodlo in strona
    assert "Dane są starsze niż" not in strona


def test_stare_dane_ostrzegaja_ale_pozwalaja_uruchomic(
    client, redaktor, przebieg, zlecenia, django_capture_on_commit_callbacks, settings
):
    settings.PBN_UZGADNIANIE_DANE_AKTUALNE_GODZIN = 24
    stare = _pobranie(przebieg, godzin_temu=30)

    strona = _strona(client)

    assert "Dane są starsze niż 24 godz." in strona
    assert "Pobierz dane z PBN" in strona
    assert 'value="wykonanie"' in strona, "przycisk uruchomienia zniknął"

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "wykonanie"})

    wykonanie = UzgodnienieZPBN.objects.get(tryb="wykonanie")
    assert wykonanie.na_podstawie == stare
    zlecenia.assert_called_once_with(wykonanie.pk)


def test_prog_starosci_jest_ustawieniem(client, redaktor, przebieg, settings):
    _pobranie(przebieg, godzin_temu=30)
    settings.PBN_UZGADNIANIE_DANE_AKTUALNE_GODZIN = 48

    assert "Dane są starsze niż" not in _strona(client)


def test_dane_pobrane_dla_innych_lat_nie_wystarczaja(
    client, redaktor, przebieg, zlecenia
):
    _pobranie(przebieg, rok_od=2024, rok_do=2025)

    client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "podglad"})

    assert not UzgodnienieZPBN.objects.exclude(tryb="pobranie").exists()
    zlecenia.assert_not_called()


def test_cudze_pobranie_nie_jest_uzywane(client, redaktor, przebieg, zlecenia):
    """Multi-hosted: dane pobrane dla innej uczelni to nie nasze dane."""
    _pobranie(przebieg, uczelnia=baker.make(Uczelnia, skrot="DRU"))

    assert "Nie ma jeszcze pobranych danych z PBN" in _strona(client)
    client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "podglad"})

    assert not UzgodnienieZPBN.objects.exclude(tryb="pobranie").exists()


def test_przycisk_pobierz_zleca_pobranie(
    client, redaktor, uczelnia_pbn, zlecenia, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "pobranie"})

    pobranie = UzgodnienieZPBN.objects.get()
    assert pobranie.to_pobranie and pobranie.na_podstawie is None
    zlecenia.assert_called_once_with(pobranie.pk)


def test_raport_podaje_z_kiedy_byly_dane(client, redaktor, przebieg):
    stare = _pobranie(przebieg, godzin_temu=50)
    p = przebieg(tryb="podglad", status="zakonczone", zakres=stare.zakres)

    strona = client.get(
        reverse("pbn_uzgadnianie:szczegoly", args=[p.pk])
    ).content.decode()
    assert "Przebieg pracował na danych z PBN" in strona
    assert "2 dni temu" in strona
    assert "Dane są starsze niż" in strona

    odp = client.get(reverse("pbn_uzgadnianie:raport_xlsx", args=[p.pk]))
    arkusz = load_workbook(io.BytesIO(odp.content))["Podsumowanie"]
    tekst = " ".join(str(w[0]) for w in arkusz.iter_rows(values_only=True) if w[0])
    assert "profil instytucji" in tekst and "2 dni temu" in tekst
    assert "UWAGA: dane z PBN są starsze" in tekst


def test_duplikat_pokazuje_oba_rekordy_i_link_do_deduplikatora(
    client, redaktor, przebieg
):
    wpisy = [
        {
            "kategoria": silnik.DUPLIKAT_W_BPP,
            "pbn_uid": "pbn-oryginal",
            "bpp_model": "wydawnictwo_ciagle",
            "bpp_pk": 11,
            "bpp_tytul": "Rekord wpisany ręcznie",
            "bpp_rok": 2026,
            "dopasowanie": "ten sam DOI",
            "blizniak": {
                "bpp_model": "wydawnictwo_ciagle",
                "bpp_pk": 12,
                "bpp_tytul": "Rekord pobrany z PBN",
                "bpp_rok": 2026,
            },
        },
        {
            "kategoria": silnik.TYLKO_W_BPP,
            "bpp_model": "wydawnictwo_ciagle",
            "bpp_pk": 13,
            "bpp_tytul": "Kandydat do wysłania",
            "bpp_rok": 2026,
            "wysylka": "nigdy nie wysyłany z BPP do PBN",
        },
    ]
    p = przebieg(status="zakonczone", wynik=wpisy, podsumowanie=silnik.podsumuj(wpisy))

    strona = client.get(
        reverse("pbn_uzgadnianie:szczegoly", args=[p.pk])
    ).content.decode()

    for pk in (11, 12):
        assert reverse("admin:bpp_wydawnictwo_ciagle_change", args=[pk]) in strona
    assert "Dopasowano po: ten sam DOI" in strona
    assert reverse("deduplikator_publikacji:duplicate_publications") in strona
    assert "Wysyłka z BPP: nigdy nie wysyłany z BPP do PBN" in strona


def test_pobranie_domyslnie_bierze_swiezy_profil_a_na_zyczenie_pobiera_caly(
    client, redaktor, przebieg, zlecenia, django_capture_on_commit_callbacks
):
    swieze = _pobranie(przebieg, godzin_temu=1)
    assert 'name="caly_profil"' in _strona(client)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "pobranie"})
    szybkie = UzgodnienieZPBN.objects.exclude(pk=swieze.pk).get()
    assert szybkie.na_podstawie == swieze
    UzgodnienieZPBN.objects.filter(pk=szybkie.pk).update(status="blad")

    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            reverse("pbn_uzgadnianie:start"),
            {**START, "tryb": "pobranie", "caly_profil": "on"},
        )
    pelne = UzgodnienieZPBN.objects.exclude(pk__in=[swieze.pk, szybkie.pk]).get()
    assert pelne.na_podstawie is None


def test_stary_profil_jest_zawsze_pobierany_ponownie(
    client, redaktor, przebieg, zlecenia, django_capture_on_commit_callbacks
):
    stare = _pobranie(przebieg, godzin_temu=30)
    assert 'name="caly_profil"' not in _strona(client)

    with django_capture_on_commit_callbacks(execute=True):
        client.post(reverse("pbn_uzgadnianie:start"), {**START, "tryb": "pobranie"})

    assert UzgodnienieZPBN.objects.exclude(pk=stare.pk).get().na_podstawie is None
