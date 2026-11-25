"""FD#449 — pola patentu i opis bibliograficzny patentu.

Nowe pola: „Uprawnieni”, „Typ patentu”, „Kraj”, „Data opublikowania”.
Do opisu bibliograficznego patentu trafiają: numer prawa wyłącznego,
uprawnieni, strony, numer zgłoszenia, daty oraz adres WWW — każde tylko, gdy
jest wypełnione.

Testy-strażnicy (``test_straznik_*``) NIE używają nowych pól i pilnują, że
opis patentu, w którym pól patentowych nie wypełniono, wygląda dokładnie jak
przed zmianą (sprawdzone także na kodzie sprzed zmiany).
"""

import importlib
from datetime import date

import pytest
from denorm import denorms
from denorm.models import DirtyInstance
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse

from bpp.models import Patent
from bpp.models.patent import TypPatentu

#: ``search_index`` wypełnia trigger bazy, nie formularz.
BEZ_INDEKSU = ["search_index"]

OPIS_PELNY = (
    'PL123456. <b><span lang="pl">PATENT!.</span></b> '
    "Uniwersytet X, Warszawa, PL. [AUT.] KOWALSKI JAN. W: WUP 06/25. "
    "s. 12-15, Nr zgłoszenia: P.654321, Data zgłoszenia: 14.06.2022, "
    "Data decyzji: 13.11.2024, Data opublikowania: 10.02.2025. "
    "Opublikowano w: https://example.com/wup.pdf"
)


@pytest.fixture
def patent_z_autorem(patent, autor_jan_kowalski, jednostka):
    patent.dodaj_autora(autor_jan_kowalski, jednostka)
    # Fixture wypełnia te pola wartościami z licznikiem czasu — zerujemy,
    # żeby porównywać opis co do znaku.
    patent.informacje = ""
    patent.szczegoly = ""
    patent.uwagi = ""
    return patent


def wypelnij(patent):
    patent.informacje = "WUP 06/25"
    patent.numer_prawa_wylacznego = "PL123456"
    patent.uprawnieni = "Uniwersytet X, Warszawa, PL"
    patent.numer_zgloszenia = "P.654321"
    patent.data_zgloszenia = date(2022, 6, 14)
    patent.data_decyzji = date(2024, 11, 13)
    patent.data_opublikowania = date(2025, 2, 10)
    patent.www = "https://example.com/wup.pdf"
    patent.strony = "12-15"
    return patent


#
# Strażnicy: opis bez pól patentowych — jak dotąd
#


@pytest.mark.django_db
def test_straznik_opis_bez_pol_patentowych_z_informacjami(patent_z_autorem):
    patent_z_autorem.informacje = "INF"
    patent_z_autorem.szczegoly = "SZCZ"
    patent_z_autorem.uwagi = "UW"

    assert patent_z_autorem.opis_bibliograficzny() == (
        ' <b><span lang="pl">PATENT!.</span></b> [AUT.] KOWALSKI JAN. W: INF SZCZ, UW. '
    )


@pytest.mark.django_db
def test_straznik_opis_bez_pol_patentowych_sam_tytul_i_autor(patent_z_autorem):
    assert patent_z_autorem.opis_bibliograficzny() == (
        ' <b><span lang="pl">PATENT!.</span></b> [AUT.] KOWALSKI JAN.. '
    )


@pytest.mark.django_db
def test_straznik_wydawnictwo_ciagle_konczy_sie_jak_dotad(
    wydawnictwo_ciagle_z_autorem,
):
    """Kropka/DOI zamykające opis zostały przeniesione poza gałęzie szablonu
    — dla rekordów innych niż patent wynik ma być identyczny."""
    wydawnictwo_ciagle_z_autorem.doi = "10.1000/xyz"
    assert wydawnictwo_ciagle_z_autorem.opis_bibliograficzny().endswith(
        ". DOI: 10.1000/xyz"
    )

    wydawnictwo_ciagle_z_autorem.doi = ""
    opis = wydawnictwo_ciagle_z_autorem.opis_bibliograficzny()
    assert opis.endswith(". ")
    assert "Nr zgłoszenia" not in opis
    assert "Opublikowano w" not in opis


#
# Opis z polami patentowymi
#


@pytest.mark.django_db
def test_opis_ze_wszystkimi_polami(patent_z_autorem):
    assert wypelnij(patent_z_autorem).opis_bibliograficzny() == OPIS_PELNY


@pytest.mark.django_db
def test_opis_puste_pola_nie_zostawiaja_sladow(patent_z_autorem):
    patent = wypelnij(patent_z_autorem)
    patent.informacje = ""
    patent.www = ""
    patent.numer_zgloszenia = ""
    patent.data_zgloszenia = None
    patent.data_decyzji = None
    patent.strony = ""

    opis = patent.opis_bibliograficzny()

    assert opis == (
        'PL123456. <b><span lang="pl">PATENT!.</span></b> '
        "Uniwersytet X, Warszawa, PL. [AUT.] KOWALSKI JAN. "
        "Data opublikowania: 10.02.2025. "
    )
    for slad in (
        "Nr zgłoszenia",
        "Data zgłoszenia",
        "Data decyzji",
        "Opublikowano",
        "s.",
        ", ,",
        ",.",
        "..",
        "None",
    ):
        assert slad not in opis.replace("PATENT!.", "")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pole,wartosc,oczekiwany_fragment",
    [
        ("numer_zgloszenia", "P.1", "KOWALSKI JAN. Nr zgłoszenia: P.1. "),
        ("data_zgloszenia", date(2022, 6, 4), "Data zgłoszenia: 04.06.2022. "),
        ("data_decyzji", date(2024, 1, 2), "Data decyzji: 02.01.2024. "),
        ("data_opublikowania", date(2025, 2, 10), "Data opublikowania: 10.02.2025. "),
        ("strony", "5-9", "KOWALSKI JAN. s. 5-9. "),
        ("www", "https://example.com/a", "Opublikowano w: https://example.com/a"),
    ],
)
def test_opis_pojedyncze_pole(patent_z_autorem, pole, wartosc, oczekiwany_fragment):
    setattr(patent_z_autorem, pole, wartosc)

    opis = patent_z_autorem.opis_bibliograficzny()

    assert opis.endswith(oczekiwany_fragment)
    assert ".." not in opis.replace("PATENT!.", "")
    assert ", ." not in opis


@pytest.mark.django_db
def test_opis_adres_publiczny_ma_pierwszenstwo(patent_z_autorem):
    patent_z_autorem.www = "https://example.com/wewnetrzny"
    patent_z_autorem.public_www = "https://example.com/publiczny"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert opis.endswith("Opublikowano w: https://example.com/publiczny")
    assert "wewnetrzny" not in opis


@pytest.mark.django_db
def test_opis_strony_nie_powtarzaja_szczegolow(patent_z_autorem):
    """Strony bywały dotąd wpisywane do „Szczegółów” — nie dubluj ich."""
    patent_z_autorem.szczegoly = "s. 12-15"
    patent_z_autorem.strony = "12-15"
    patent_z_autorem.numer_zgloszenia = "P.1"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert opis.count("12-15") == 1
    assert opis.endswith("KOWALSKI JAN. s. 12-15. Nr zgłoszenia: P.1. ")


@pytest.mark.django_db
def test_opis_typ_patentu_i_kraj_nie_wchodza_do_opisu(patent_z_autorem):
    """Zgodnie ze wzorcem typ patentu i kraj są na stronie rekordu, nie
    w jednolinijkowym opisie."""
    patent_z_autorem.typ_patentu = TypPatentu.ZAGRANICZNY
    patent_z_autorem.kraj = "Kanada"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert "Kanada" not in opis
    assert "zagraniczny" not in opis


@pytest.mark.django_db
def test_opis_uprawnieni_sa_escapowani(patent_z_autorem):
    patent_z_autorem.uprawnieni = "<script>alert(1)</script>Firma & Syn"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert "<script" not in opis
    assert "Firma &amp; Syn." in opis


@pytest.mark.django_db
def test_opis_cache_odswieza_sie_po_zapisie(patent_z_autorem):
    wypelnij(patent_z_autorem).save()
    denorms.flush()

    patent_z_autorem.refresh_from_db()
    assert patent_z_autorem.opis_bibliograficzny_cache == OPIS_PELNY


#
# Walidacja
#


@pytest.mark.django_db
def test_walidacja_kraj_bez_typu_zagranicznego(patent):
    patent.kraj = "Kanada"
    for typ in ("", TypPatentu.POLSKI):
        patent.typ_patentu = typ
        with pytest.raises(ValidationError) as exc:
            patent.full_clean(exclude=BEZ_INDEKSU)
        assert list(exc.value.message_dict) == ["kraj"]


@pytest.mark.django_db
def test_walidacja_kraj_przy_patencie_zagranicznym(patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.kraj = "  Kanada "
    patent.uprawnieni = "  Firma X \n"

    patent.full_clean(exclude=BEZ_INDEKSU)

    assert patent.kraj == "Kanada"
    assert patent.uprawnieni == "Firma X"
    assert patent.typ_patentu_z_krajem() == "zagraniczny / Kanada"


@pytest.mark.django_db
def test_walidacja_typ_patentu_spoza_listy(patent):
    patent.typ_patentu = "europejski"
    with pytest.raises(ValidationError) as exc:
        patent.full_clean(exclude=BEZ_INDEKSU)
    assert "typ_patentu" in exc.value.message_dict


@pytest.mark.django_db
def test_nowe_pola_sa_opcjonalne(patent):
    patent.full_clean(exclude=BEZ_INDEKSU)
    assert patent.typ_patentu == ""
    assert patent.kraj == ""
    assert patent.uprawnieni == ""
    assert patent.data_opublikowania is None
    assert patent.typ_patentu_z_krajem() == ""


#
# Admin, strona rekordu, API, migracja
#


@pytest.mark.django_db
def test_admin_formularz_ma_nowe_pola(admin_client, patent):
    res = admin_client.get(reverse("admin:bpp_patent_change", args=(patent.pk,)))

    assert res.status_code == 200
    tresc = res.content.decode()
    for pole in ("uprawnieni", "typ_patentu", "kraj", "data_opublikowania"):
        assert f'name="{pole}"' in tresc
    assert "patent-typ-kraj.js" in tresc
    assert "Data decyzji" in tresc


@pytest.mark.django_db
def test_admin_formularz_odrzuca_kraj_dla_patentu_polskiego(patent):
    from bpp.admin.patent import Patent_Form

    form = Patent_Form(instance=patent)
    dane = {k: v for k, v in form.initial.items() if v is not None}
    dane.update(typ_patentu="polski", kraj="Kanada")

    form = Patent_Form(dane, instance=patent)

    assert not form.is_valid()
    assert "kraj" in form.errors


@pytest.mark.django_db
def test_strona_rekordu_pokazuje_nowe_pola(client, patent_z_autorem, uczelnia):
    patent = wypelnij(patent_z_autorem)
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.kraj = "Kanada"
    patent.save()

    res = client.get(
        reverse("bpp:browse_praca", args=("patent", patent.pk)), follow=True
    )

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "<b>Uprawnieni:</b> Uniwersytet X, Warszawa, PL" in tresc
    assert "<b>Typ patentu:</b> zagraniczny / Kanada" in tresc
    assert "<b>Data opublikowania:</b>" in tresc
    assert "<b>Strony:</b> 12-15" in tresc
    # blok patentowy ma być na stronie dokładnie raz (wspólny include)
    assert tresc.count("<b>Numer prawa wyłącznego:</b>") == 1


@pytest.mark.django_db
def test_strona_rekordu_bez_nowych_pol_bez_pustych_etykiet(
    client, patent_z_autorem, uczelnia
):
    res = client.get(
        reverse("bpp:browse_praca", args=("patent", patent_z_autorem.pk)),
        follow=True,
    )

    assert res.status_code == 200
    tresc = res.content.decode()
    assert "<b>Numer zgłoszenia:</b> brak" in tresc
    for etykieta in ("Uprawnieni:", "Typ patentu:", "Data opublikowania:"):
        assert etykieta not in tresc


@pytest.mark.django_db
def test_api_zwraca_nowe_pola(client, patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.kraj = "Kanada"
    patent.uprawnieni = "Firma X"
    patent.data_opublikowania = date(2025, 2, 10)
    patent.save()

    dane = client.get(reverse("api_v1:patent-detail", args=(patent.pk,))).json()

    assert dane["typ_patentu"] == "zagraniczny"
    assert dane["kraj"] == "Kanada"
    assert dane["uprawnieni"] == "Firma X"
    assert dane["data_opublikowania"] == "2025-02-10"


@pytest.mark.django_db
def test_bibtex_zawiera_date_opublikowania(patent_z_autorem):
    patent_z_autorem.data_opublikowania = date(2025, 2, 10)
    assert "Data opublikowania: 2025-02-10" in patent_z_autorem.to_bibtex()


@pytest.mark.django_db
def test_migracja_oznacza_patenty_do_przeliczenia_opisu(patent):
    denorms.flush()
    ct = ContentType.objects.get_for_model(Patent)
    DirtyInstance.objects.filter(content_type=ct).delete()

    mod = importlib.import_module("bpp.migrations.0532_patent_pola_fd449")
    mod.przelicz_opisy_patentow(None, None)

    assert DirtyInstance.objects.filter(content_type=ct, object_id=patent.pk).exists()
