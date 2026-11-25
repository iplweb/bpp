"""FD#449, etap 2 — pole „Pierwszeństwo z polskiego patentu o nr zgłoszenia”.

Zgłaszająca (25.11.2026): pole do RĘCZNEGO wpisania numeru, bez odnośnika do
rekordu polskiego patentu — także wtedy, gdy ten jest w bazie (numer bywa ten
sam co „Numer zgłoszenia”, ale nie zawsze). Dotyczy patentów zagranicznych.

We wzorcu opisu patentu zagranicznego pierwszeństwo stoi tam, gdzie przy
patencie polskim „Nr zgłoszenia” — przed datą zgłoszenia.
"""

import importlib
import re
from datetime import date

import pytest
from denorm import denorms
from django.core.exceptions import ValidationError
from django.db import migrations
from django.urls import reverse

from bpp.models import Patent
from bpp.models.patent import TypPatentu
from bpp.tests.test_repro_fd449 import BEZ_INDEKSU, patent_z_autorem  # noqa: F401

ETYKIETA = "Pierwszeństwo z polskiego patentu o nr zgłoszenia:"


def zagraniczny(patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.kraj = "Kanada"
    patent.numer_prawa_wylacznego = "CA1234567"
    patent.pierwszenstwo_nr_zgloszenia = "P.123456"
    patent.data_zgloszenia = date(2022, 6, 14)
    patent.data_opublikowania = date(2023, 9, 19)
    patent.www = "https://example.com/CA1234567"
    return patent


#
# Opis bibliograficzny
#


@pytest.mark.django_db
def test_opis_patentu_zagranicznego_z_pierwszenstwem(patent_z_autorem):  # noqa: F811
    opis = zagraniczny(patent_z_autorem).opis_bibliograficzny()

    assert opis == (
        'CA1234567. <b><span lang="pl">PATENT!.</span></b> '
        "[AUT.] KOWALSKI JAN. "
        f"{ETYKIETA} P.123456, Data zgłoszenia: 14.06.2022, "
        "Data opublikowania: 19.09.2023. "
        "Opublikowano w: https://example.com/CA1234567"
    )


@pytest.mark.django_db
def test_opis_pierwszenstwo_po_numerze_zgloszenia(patent_z_autorem):  # noqa: F811
    """Oba numery naraz: własny numer zgłoszenia, potem pierwszeństwo."""
    patent = zagraniczny(patent_z_autorem)
    patent.numer_zgloszenia = "CA 1234567"

    opis = patent.opis_bibliograficzny()

    assert (
        f"Nr zgłoszenia: CA 1234567, {ETYKIETA} P.123456, "
        "Data zgłoszenia: 14.06.2022" in opis
    )


@pytest.mark.django_db
def test_opis_samo_pierwszenstwo_zamyka_opis(patent_z_autorem):  # noqa: F811
    patent_z_autorem.typ_patentu = TypPatentu.ZAGRANICZNY
    patent_z_autorem.pierwszenstwo_nr_zgloszenia = "P.1"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert opis.endswith(f"KOWALSKI JAN. {ETYKIETA} P.1. ")
    assert ".." not in opis.replace("PATENT!.", "")


@pytest.mark.django_db
def test_opis_puste_pierwszenstwo_bez_sladu(patent_z_autorem):  # noqa: F811
    patent = zagraniczny(patent_z_autorem)
    patent.pierwszenstwo_nr_zgloszenia = ""

    opis = patent.opis_bibliograficzny()

    assert "Pierwszeństwo" not in opis
    assert "KOWALSKI JAN. Data zgłoszenia: 14.06.2022, " in opis


@pytest.mark.django_db
def test_opis_pierwszenstwo_escapowane(patent_z_autorem):  # noqa: F811
    patent_z_autorem.pierwszenstwo_nr_zgloszenia = "<b>P.1</b>&"

    opis = patent_z_autorem.opis_bibliograficzny()

    assert "<b>P.1" not in opis
    assert "&lt;b&gt;P.1&lt;/b&gt;&amp;" in opis


@pytest.mark.django_db
def test_opis_cache_po_zapisie(patent_z_autorem):  # noqa: F811
    patent = zagraniczny(patent_z_autorem)
    patent.save()
    denorms.flush()

    patent.refresh_from_db()
    assert f"{ETYKIETA} P.123456" in patent.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_opis_cache_po_zmianie_tylko_pierwszenstwa_save(patent_z_autorem):  # noqa: F811
    """Zmiana WYŁĄCZNIE nowej kolumny (``update_fields``) musi przeliczyć
    cache opisu — łapie trigger denorm, który tej kolumny nie obserwuje."""
    patent = zagraniczny(patent_z_autorem)
    patent.pierwszenstwo_nr_zgloszenia = "P.1"
    patent.save()
    denorms.flush()

    patent.pierwszenstwo_nr_zgloszenia = "P.2"
    patent.save(update_fields=["pierwszenstwo_nr_zgloszenia"])
    denorms.flush()

    patent.refresh_from_db()
    assert f"{ETYKIETA} P.2," in patent.opis_bibliograficzny_cache
    assert "P.1" not in patent.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_opis_cache_po_zmianie_tylko_pierwszenstwa_update(patent_z_autorem):  # noqa: F811
    """Jak wyżej, ale ``QuerySet.update()`` — z pominięciem ``save()``,
    więc przeliczenie zależy wyłącznie od triggera w bazie."""
    patent = zagraniczny(patent_z_autorem)
    patent.pierwszenstwo_nr_zgloszenia = "P.1"
    patent.save()
    denorms.flush()

    Patent.objects.filter(pk=patent.pk).update(pierwszenstwo_nr_zgloszenia="P.2")
    denorms.flush()

    patent.refresh_from_db()
    assert f"{ETYKIETA} P.2," in patent.opis_bibliograficzny_cache
    assert "P.1" not in patent.opis_bibliograficzny_cache


#
# Walidacja
#


@pytest.mark.django_db
@pytest.mark.parametrize("typ", ["", TypPatentu.POLSKI])
def test_walidacja_pierwszenstwo_tylko_dla_zagranicznego(patent, typ):
    patent.typ_patentu = typ
    patent.pierwszenstwo_nr_zgloszenia = "P.123456"

    with pytest.raises(ValidationError) as exc:
        patent.full_clean(exclude=BEZ_INDEKSU)

    assert list(exc.value.message_dict) == ["pierwszenstwo_nr_zgloszenia"]


@pytest.mark.django_db
def test_walidacja_kraj_i_pierwszenstwo_naraz_oba_bledy(patent):
    patent.typ_patentu = TypPatentu.POLSKI
    patent.kraj = "Kanada"
    patent.pierwszenstwo_nr_zgloszenia = "P.1"

    with pytest.raises(ValidationError) as exc:
        patent.full_clean(exclude=BEZ_INDEKSU)

    assert set(exc.value.message_dict) == {"kraj", "pierwszenstwo_nr_zgloszenia"}


@pytest.mark.django_db
def test_walidacja_pierwszenstwo_przy_zagranicznym_przycina_spacje(patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.pierwszenstwo_nr_zgloszenia = "  P.123456 "

    patent.full_clean(exclude=BEZ_INDEKSU)

    assert patent.pierwszenstwo_nr_zgloszenia == "P.123456"


@pytest.mark.django_db
def test_pierwszenstwo_opcjonalne_dla_zagranicznego(patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.full_clean(exclude=BEZ_INDEKSU)
    assert patent.pierwszenstwo_nr_zgloszenia == ""


#
# Admin, strona rekordu, API, BibTeX, migracja
#


@pytest.mark.django_db
def test_admin_formularz_ma_pole(admin_client, patent):
    res = admin_client.get(reverse("admin:bpp_patent_change", args=(patent.pk,)))

    assert res.status_code == 200
    tresc = res.content.decode()
    assert 'name="pierwszenstwo_nr_zgloszenia"' in tresc
    assert "Pierwszeństwo z polskiego patentu o nr zgłoszenia" in tresc
    assert "patent-typ-kraj.js" in tresc


@pytest.mark.django_db
def test_admin_formularz_odrzuca_pierwszenstwo_dla_polskiego(patent):
    from bpp.admin.patent import Patent_Form

    form = Patent_Form(instance=patent)
    dane = {k: v for k, v in form.initial.items() if v is not None}
    dane.update(typ_patentu="polski", pierwszenstwo_nr_zgloszenia="P.1")

    form = Patent_Form(dane, instance=patent)

    assert not form.is_valid()
    assert "pierwszenstwo_nr_zgloszenia" in form.errors


@pytest.mark.django_db
def test_admin_formularz_przyjmuje_pierwszenstwo_dla_zagranicznego(patent):
    from bpp.admin.patent import Patent_Form

    form = Patent_Form(instance=patent)
    dane = {k: v for k, v in form.initial.items() if v is not None}
    dane.update(typ_patentu="zagraniczny", pierwszenstwo_nr_zgloszenia="P.1")

    form = Patent_Form(dane, instance=patent)

    # Cały formularz, nie tylko jedno pole: brak błędów pól i non_field_errors.
    assert form.is_valid(), form.errors
    assert not form.non_field_errors()
    assert form.cleaned_data["pierwszenstwo_nr_zgloszenia"] == "P.1"


@pytest.mark.django_db
def test_admin_wyszukiwanie_po_pierwszenstwie(admin_client, patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.pierwszenstwo_nr_zgloszenia = "P.999777"
    patent.save()

    res = admin_client.get(
        reverse("admin:bpp_patent_changelist"), {"q": "P.999777"}
    )

    assert res.status_code == 200
    assert reverse("admin:bpp_patent_change", args=(patent.pk,)) in (
        res.content.decode()
    )


def test_skrypt_admina_chowa_wiersz_pierwszenstwa():
    from pathlib import Path

    from django.contrib.staticfiles import finders

    # Test STATYCZNY (treść skryptu) — realne chowanie wiersza sprawdza
    # test_playwright_chowa_wiersz_pierwszenstwa poniżej.
    tresc = Path(finders.find("bpp/js/patent-typ-kraj.js")).read_text()
    pola = re.search(r"POLA_ZAGRANICZNE\s*=\s*\[([^\]]*)\]", tresc)
    assert pola is not None
    assert '"id_pierwszenstwo_nr_zgloszenia"' in pola.group(1)
    assert 'typ.value === "zagraniczny"' in tresc
    assert 'style.display = pokaz ? "" : "none"' in tresc


@pytest.mark.django_db(transaction=True)
def test_playwright_chowa_wiersz_pierwszenstwa(admin_page, channels_live_server):
    from playwright.sync_api import expect

    admin_page.goto(channels_live_server.url + reverse("admin:bpp_patent_add"))
    admin_page.wait_for_selector("#id_typ_patentu", state="attached")
    wiersz = admin_page.locator("#id_pierwszenstwo_nr_zgloszenia").locator(
        "xpath=ancestor::*[contains(@class, 'grp-row') "
        "or contains(@class, 'form-row')][1]"
    )

    expect(wiersz).to_be_hidden()

    admin_page.select_option("#id_typ_patentu", "zagraniczny")
    expect(wiersz).to_be_visible()

    admin_page.select_option("#id_typ_patentu", "polski")
    expect(wiersz).to_be_hidden()


@pytest.mark.django_db
def test_strona_rekordu_pokazuje_pierwszenstwo(client, patent_z_autorem, uczelnia):  # noqa: F811
    patent = zagraniczny(patent_z_autorem)
    patent.save()

    res = client.get(
        reverse("bpp:browse_praca", args=("patent", patent.pk)), follow=True
    )

    assert res.status_code == 200
    assert (
        "<b>Pierwszeństwo z polskiego patentu o nr zgłoszenia:</b> P.123456"
        in res.content.decode()
    )


@pytest.mark.django_db
def test_strona_rekordu_bez_pierwszenstwa_bez_etykiety(
    client,
    patent_z_autorem,  # noqa: F811
    uczelnia,
):
    res = client.get(
        reverse("bpp:browse_praca", args=("patent", patent_z_autorem.pk)),
        follow=True,
    )

    assert res.status_code == 200
    assert "Pierwszeństwo z polskiego" not in res.content.decode()


@pytest.mark.django_db
def test_api_zwraca_pierwszenstwo(client, patent):
    patent.typ_patentu = TypPatentu.ZAGRANICZNY
    patent.pierwszenstwo_nr_zgloszenia = "P.123456"
    patent.save()

    dane = client.get(reverse("api_v1:patent-detail", args=(patent.pk,))).json()

    assert dane["pierwszenstwo_nr_zgloszenia"] == "P.123456"


@pytest.mark.django_db
def test_bibtex_zawiera_pierwszenstwo(patent_z_autorem):  # noqa: F811
    patent_z_autorem.pierwszenstwo_nr_zgloszenia = "P.123456"
    assert (
        "Pierwszeństwo z polskiego patentu o nr zgłoszenia: P.123456"
        in patent_z_autorem.to_bibtex()
    )


def test_migracja_tylko_dodaje_pole():
    """Migracja tylko dodaje pole (z ``default=""``) — bez RunPython: nowe pole
    jest wszędzie puste, więc żaden opis się nie zmienia i nie ma czego
    przeliczać."""
    mod = importlib.import_module("bpp.migrations.0533_patent_pierwszenstwo_fd449")

    operacje = mod.Migration.operations
    assert [type(op) for op in operacje] == [migrations.AddField]
    assert operacje[0].model_name == "patent"
    assert operacje[0].name == "pierwszenstwo_nr_zgloszenia"
    assert operacje[0].field.default == ""
