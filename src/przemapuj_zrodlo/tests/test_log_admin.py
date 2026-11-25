"""Log przemapowań źródeł w module redagowania (FD#508): kto go widzi,
co pokazuje strona operacji i przycisk „Cofnij”."""

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from bpp.system import odtworz_grupy
from przemapuj_zrodla_pbn.models import PrzeMapowanieZrodla
from przemapuj_zrodlo.models import PrzemapowaZrodla

LISTA = "admin:przemapuj_zrodlo_przemapowazrodla_changelist"
OPERACJA = "admin:przemapuj_zrodlo_przemapowazrodla_change"
LISTA_PBN = "admin:przemapuj_zrodla_pbn_przemapowaniezrodla_changelist"
OPERACJA_PBN = "admin:przemapuj_zrodla_pbn_przemapowaniezrodla_change"


@pytest.fixture
def redaktor_staff(django_user_model):
    """Konto z dostępem do modułu redagowania, w grupie „wprowadzanie
    danych” — z uprawnieniami nadanymi tak, jak na instalacji klienta
    (``odtworz_grupy`` leci po każdym ``migrate``)."""
    odtworz_grupy()
    user = django_user_model.objects.create(username="redaktor-log", is_staff=True)
    user.groups.add(Group.objects.get(name=GR_WPROWADZANIE_DANYCH))
    return user


@pytest.fixture
def staff_spoza_grupy(django_user_model):
    odtworz_grupy()
    user = django_user_model.objects.create(username="obcy-staff", is_staff=True)
    # Jakakolwiek grupa — bez niej menu admina nie ma czego pokazać.
    user.groups.add(Group.objects.get(name="raporty"))
    return user


@pytest.fixture
def operacja(django_user_model):
    autor = baker.make(django_user_model)
    zrodlo_z = baker.make(Zrodlo, nazwa="Stare czasopismo", pbn_uid=None)
    zrodlo_do = baker.make(Zrodlo, nazwa="Nowe czasopismo", pbn_uid=None)
    praca = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_do)
    return PrzemapowaZrodla.objects.create(
        zrodlo_z=zrodlo_z,
        zrodlo_do=zrodlo_do,
        liczba_publikacji=1,
        publikacje_historia=[{"id": praca.pk, "tytul": "Praca", "rok": 2020}],
        utworzono_przez=autor,
    )


@pytest.fixture
def operacja_pbn(django_user_model):
    autor = baker.make(django_user_model)
    journal = baker.make(
        "pbn_api.Journal",
        status="DELETED",
        title="",
        issn="",
        eissn="",
        websiteLink="",
    )
    return PrzeMapowanieZrodla.objects.create(
        zrodlo_skasowane_pbn_uid=journal,
        zrodlo_stare=baker.make(Zrodlo, nazwa="Skasowane", pbn_uid=journal),
        zrodlo_nowe=baker.make(Zrodlo, nazwa="Aktualne", pbn_uid=None),
        liczba_rekordow=1,
        utworzono_przez=autor,
        # Pozycja bez ``id`` — taki kształt miewają stare/ręczne wpisy.
        rekordy_historia=[{"tytul": "Praca bez identyfikatora", "rok": 2023}],
    )


@pytest.mark.django_db
def test_redaktor_z_grupy_oglada_oba_logi(
    client, redaktor_staff, operacja, operacja_pbn
):
    client.force_login(redaktor_staff)
    for nazwa, args in (
        (LISTA, []),
        (OPERACJA, [operacja.pk]),
        (LISTA_PBN, []),
        (OPERACJA_PBN, [operacja_pbn.pk]),
    ):
        resp = client.get(reverse(nazwa, args=args))
        assert resp.status_code == 200, nazwa


@pytest.mark.django_db
def test_redaktor_z_grupy_nie_moze_zmieniac_logow(
    client, redaktor_staff, operacja, operacja_pbn
):
    client.force_login(redaktor_staff)
    for nazwa, obiekt in ((OPERACJA, operacja), (OPERACJA_PBN, operacja_pbn)):
        url = reverse(nazwa, args=[obiekt.pk])
        # Strona jest podglądem: bez przycisku zapisu.
        assert 'name="_save"' not in client.get(url).content.decode()
        assert client.post(url, {"liczba_publikacji": 99}).status_code == 403
        assert client.post(url.replace("/change/", "/delete/")).status_code == 403
        assert (
            client.get(url.replace(f"/{obiekt.pk}/change/", "/add/")).status_code == 403
        )
    operacja.refresh_from_db()
    assert operacja.liczba_publikacji == 1
    assert PrzeMapowanieZrodla.objects.filter(pk=operacja_pbn.pk).exists()


@pytest.mark.django_db
def test_staff_spoza_grupy_nie_widzi_logow(
    client, staff_spoza_grupy, operacja, operacja_pbn
):
    client.force_login(staff_spoza_grupy)
    for nazwa, args in (
        (LISTA, []),
        (OPERACJA, [operacja.pk]),
        (LISTA_PBN, []),
        (OPERACJA_PBN, [operacja_pbn.pk]),
    ):
        assert client.get(reverse(nazwa, args=args)).status_code == 403, nazwa


@pytest.mark.django_db
def test_logi_przemapowan_sa_w_menu_redaktora(client, redaktor_staff):
    client.force_login(redaktor_staff)
    tresc = client.get(reverse("admin:index")).content.decode()
    assert reverse(LISTA) in tresc
    assert reverse(LISTA_PBN) in tresc


@pytest.mark.django_db
def test_strona_operacji_pbn_znosi_pozycje_bez_identyfikatora(
    admin_client, operacja_pbn
):
    resp = admin_client.get(reverse(OPERACJA_PBN, args=[operacja_pbn.pk]))
    assert resp.status_code == 200
    assert "Praca bez identyfikatora (2023)" in resp.content.decode()


@pytest.mark.django_db
def test_strona_operacji_kosz_usuniecie_i_znaczniki_w_tytule(admin_client, operacja):
    zrodlo = operacja.zrodlo_do
    w_koszu = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    usunieta = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    zywa = operacja.publikacje_historia[0]["id"]
    operacja.publikacje_historia = [
        {"id": zywa, "tytul": "A <i>in vitro</i> B", "rok": 2020},
        {"id": w_koszu.pk, "tytul": "Praca w koszu", "rok": 2021},
        {"id": usunieta.pk, "tytul": "Praca skasowana", "rok": 2022},
    ]
    operacja.save()
    w_koszu.delete()
    usunieta.hard_delete()

    tresc = admin_client.get(reverse(OPERACJA, args=[operacja.pk])).content.decode()

    # Znaczniki z tytułu znikają (ani dosłownie, ani jako HTML).
    assert "A in vitro B (2020)" in tresc
    assert "&lt;i&gt;" not in tresc

    zmiana = "admin:bpp_wydawnictwo_ciagle_change"
    assert "Praca w koszu (2021) — ♻️ w koszu" in tresc
    assert reverse(zmiana, args=[w_koszu.pk]) in tresc
    assert "Praca skasowana (2022) — rekord usunięty trwale" in tresc
    assert reverse(zmiana, args=[usunieta.pk]) not in tresc
    # Link zbiorczy obejmuje tylko żywe rekordy (lista domyślnie chowa kosz).
    lista = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    assert f"{lista}?id__in={zywa}&quot;" in tresc or f'{lista}?id__in={zywa}"' in tresc


@pytest.mark.django_db
def test_przycisk_cofnij_nie_wkleja_nazwy_zrodla_do_js(admin_client, operacja):
    """Nazwa z apostrofem i cudzysłowem psuła inline ``onclick`` (encje HTML
    są dekodowane przed wykonaniem JS) — cofnięcie nie działało, a nazwa
    mogła wstrzyknąć kod."""
    zrodlo = operacja.zrodlo_z
    zrodlo.nazwa = "O'Reilly \"Journal\"'); alert(1); ('"
    zrodlo.save()

    tresc = admin_client.get(reverse(LISTA)).content.decode()

    start = tresc.index("przemapowanie-cofnij")
    przycisk = tresc[tresc.rindex("<a ", 0, start) : tresc.index("</a>", start)]
    assert "onclick" not in przycisk
    assert "alert(1)" in przycisk  # nazwa jest, ale tylko jako dane…
    assert 'data-potwierdzenie="' in przycisk
    assert "'" not in przycisk and przycisk.count('"') == 8  # …w pełni zakodowane
    assert reverse("przemapuj_zrodlo:cofnij", args=[operacja.pk]) in przycisk
    assert "przemapuj_zrodlo/admin_cofnij.js" in tresc


@pytest.mark.django_db
def test_przemapowanie_blokuje_publikacje_i_aktualizuje_ten_sam_zestaw(
    admin_client,
):
    """Lista do logu/historii i aktualizacja muszą objąć te same rekordy:
    publikacje są blokowane (``FOR UPDATE``), a ``UPDATE`` idzie po kluczach,
    nie po ponownym filtrze źródła."""
    zrodlo_z = baker.make(Zrodlo, nazwa="Gazeta", pbn_uid=None)
    zrodlo_do = baker.make(Zrodlo, nazwa="Gazeta", pbn_uid=None)
    praca = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo_z)

    with CaptureQueriesContext(connection) as zapytania:
        admin_client.post(
            reverse("przemapuj_zrodlo:przemapuj", args=[zrodlo_z.slug]),
            {"zrodlo_docelowe": zrodlo_do.pk, "potwierdzenie": "on"},
        )

    sql = [q["sql"] for q in zapytania if "bpp_wydawnictwo_ciagle" in q["sql"]]
    assert any(s.startswith("SELECT") and "FOR UPDATE" in s for s in sql)
    aktualizacje = [s for s in sql if s.startswith("UPDATE") and '"zrodlo_id" =' in s]
    assert aktualizacje
    assert all('"id" IN' in s.split("WHERE")[1] for s in aktualizacje)
    praca.refresh_from_db()
    assert praca.zrodlo == zrodlo_do
