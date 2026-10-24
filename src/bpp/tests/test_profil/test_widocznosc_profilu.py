"""Widoczność danych na profilu autora i w eksportach BibTeX/RIS.

Prace o statusach korekty ukrytych (kanał „podglad”) nie trafiają do sekcji
profilu ani do eksportów dla osób bez uprawnień redakcyjnych; ukryci autorzy
(``pokazuj=False``) nie są pokazywani; sekcja slotów podlega tej samej
bramce co raport slotów autora.
"""

import io
from unittest import mock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, override_settings
from django.urls import reverse
from model_bakery import baker
from PIL import Image

from bpp.models import (
    Autor,
    AutorEksportTask,
    OpcjaWyswietlaniaField,
    Status_Korekty,
    Ukryj_Status_Korekty,
)
from bpp.profil_autora_dane import (
    _punkty_lata,
    _wspolautorzy,
    _wybrane_publikacje,
    _wykres_lata,
    przygotuj_sekcje,
    ukryte_statusy_podgladu,
)

pytestmark = pytest.mark.django_db


def _ukryj(uczelnia, status, **kanaly):
    """Ukryj ``status`` tylko w podanych kanałach (pozostałe wyłączone)."""
    wszystkie = dict(
        multiwyszukiwarka=False,
        podglad=False,
        raporty=False,
        rankingi=False,
        sloty=False,
        api=False,
        cerif=False,
    )
    wszystkie.update(kanaly)
    return Ukryj_Status_Korekty.objects.create(
        uczelnia=uczelnia, status_korekty=status, **wszystkie
    )


def _request(user=None):
    req = RequestFactory().get("/")
    req.user = user or AnonymousUser()
    return req


@pytest.fixture
def dorobek_z_ukryta(
    uczelnia,
    autor_jan_nowak,
    jednostka,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
):
    """Autor z dwiema pracami: widoczną (2020) i o ukrytym statusie (2021)."""
    ukryty = baker.make(Status_Korekty, nazwa="ukryty-test")
    _ukryj(uczelnia, ukryty, podglad=True)

    wydawnictwo_ciagle.tytul_oryginalny = "Praca widoczna"
    wydawnictwo_ciagle.rok = 2020
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

    wydawnictwo_zwarte.tytul_oryginalny = "Praca ukryta"
    wydawnictwo_zwarte.rok = 2021
    wydawnictwo_zwarte.status_korekty = ukryty
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    return autor_jan_nowak


# --- profil: ukryte statusy -------------------------------------------------


def test_profil_anonim_nie_widzi_prac_o_ukrytym_statusie(dorobek_z_ukryta):
    dane = _wykres_lata(dorobek_z_ukryta, 10, _request())
    assert dict(dane["dane"]) == {2020: 1}


def test_profil_redakcja_widzi_wszystko(dorobek_z_ukryta, admin_user):
    dane = _wykres_lata(dorobek_z_ukryta, 10, _request(admin_user))
    assert dict(dane["dane"]) == {2020: 1, 2021: 1}


def test_profil_tylko_kanal_podglad(uczelnia, dorobek_z_ukryta):
    # Ukrycie w innych kanałach (bez „podglad”) nie wpływa na profil.
    Ukryj_Status_Korekty.objects.update(podglad=False, api=True, raporty=True)
    assert ukryte_statusy_podgladu(_request()) == []
    dane = _wykres_lata(dorobek_z_ukryta, 10, _request())
    assert dict(dane["dane"]) == {2020: 1, 2021: 1}


def test_profil_przygotuj_sekcje_bez_prac_ukrytych(uczelnia, dorobek_z_ukryta):
    sekcje = przygotuj_sekcje(dorobek_z_ukryta, uczelnia, _request())
    for s in sekcje:
        for praca in (s["dane"] or {}).get("prace", []):
            assert praca.tytul_oryginalny != "Praca ukryta"
    podsumowanie = next(s for s in sekcje if s["klucz"] == "podsumowanie")
    assert podsumowanie["dane"]["liczba"] == 1


def test_wybrane_publikacje_bez_ukrytych(dorobek_z_ukryta, wydawnictwo_zwarte):
    from bpp.models.wybrana_publikacja import WybranaPublikacjaAutora

    WybranaPublikacjaAutora.objects.create(
        autor=dorobek_z_ukryta,
        content_type=ContentType.objects.get_for_model(wydawnictwo_zwarte),
        object_id=wydawnictwo_zwarte.pk,
    )
    assert _wybrane_publikacje(dorobek_z_ukryta, 10, _request()) is None


# --- współautorzy ------------------------------------------------------------


def test_wspolautorzy_bez_ukrytych_autorow():
    from powiazania_autorow.models import AuthorConnection

    autor = baker.make(Autor)
    widoczny = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, pokazuj=False)
    baker.make(
        AuthorConnection,
        primary_author=autor,
        secondary_author=ukryty,
        shared_publications_count=10,
    )
    baker.make(
        AuthorConnection,
        primary_author=widoczny,
        secondary_author=autor,
        shared_publications_count=5,
    )
    dane = _wspolautorzy(autor, 1, None)
    assert [w["autor"] for w in dane["wspolautorzy"]] == [widoczny]


# --- sekcja slotów -----------------------------------------------------------


@pytest.fixture
def punktacja(uczelnia, autor_jan_nowak, wydawnictwo_ciagle, jednostka):
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora

    wydawnictwo_ciagle.rok = 2022
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    baker.make(
        Cache_Punktacja_Autora,
        rekord_id=[ct.pk, wydawnictwo_ciagle.pk],
        autor=autor_jan_nowak,
        jednostka=jednostka,
        pkdaut=10,
        slot=1,
    )
    return autor_jan_nowak


def test_punkty_lata_pokazywane_gdy_raport_slotow_dostepny(uczelnia, punktacja):
    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()
    dane = _punkty_lata(punktacja, 10, _request())
    assert [w["rekord__rok"] for w in dane["wiersze"]] == [2022]


def test_punkty_lata_bramkowane_jak_raport_slotow(uczelnia, punktacja, admin_user):
    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    uczelnia.save()
    assert _punkty_lata(punktacja, 10, _request()) is None
    assert _punkty_lata(punktacja, 10, None) is None
    assert _punkty_lata(punktacja, 10, _request(admin_user)) is not None

    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    uczelnia.save()
    assert _punkty_lata(punktacja, 10, _request(admin_user)) is None


def test_punkty_lata_bez_statusow_ukrytych_dla_slotow(
    uczelnia, punktacja, wydawnictwo_ciagle, admin_user
):
    _ukryj(uczelnia, wydawnictwo_ciagle.status_korekty, sloty=True)
    assert _punkty_lata(punktacja, 10, _request(admin_user)) is None


# --- eksport synchroniczny ---------------------------------------------------


def _zwykly_user(django_user_model, nazwa="czytelnik"):
    return django_user_model.objects.create_user(username=nazwa, password="x")


def test_eksport_sync_bez_ukrytych_dla_zwyklego_usera(
    client, django_user_model, dorobek_z_ukryta
):
    client.force_login(_zwykly_user(django_user_model))
    url = reverse("bpp:autor_eksport_bibtex", args=(dorobek_z_ukryta.pk,))
    body = client.get(url).content.decode("utf-8")
    assert "Praca widoczna" in body
    assert "Praca ukryta" not in body


def test_eksport_sync_redakcja_widzi_ukryte(admin_client, dorobek_z_ukryta):
    url = reverse("bpp:autor_eksport_bibtex", args=(dorobek_z_ukryta.pk,))
    body = admin_client.get(url).content.decode("utf-8")
    assert "Praca ukryta" in body


def test_eksport_sync_ukryty_autor_404(client, admin_client, django_user_model):
    autor = baker.make(Autor, pokazuj=False)
    url = reverse("bpp:autor_eksport_ris", args=(autor.pk,))
    client.force_login(_zwykly_user(django_user_model))
    assert client.get(url).status_code == 404
    assert admin_client.get(url).status_code == 200


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
def test_eksport_sync_limit_zadan(client, django_user_model):
    from django.core.cache import cache

    from bpp.views.eksport_autora import LIMIT_EKSPORTOW_SYNC

    cache.clear()
    autor = baker.make(Autor)
    client.force_login(_zwykly_user(django_user_model))
    url = reverse("bpp:autor_eksport_ris", args=(autor.pk,))
    for _ in range(LIMIT_EKSPORTOW_SYNC):
        assert client.get(url).status_code == 200
    assert client.get(url).status_code == 429
    cache.clear()


# --- eksport asynchroniczny --------------------------------------------------


def test_eksport_async_zapisuje_zakres_i_rozdziela_deduplikacje(
    client, admin_client, uczelnia, dorobek_z_ukryta
):
    ukryte = list(uczelnia.ukryte_statusy("podglad"))
    url = reverse(
        "bpp:autor_eksport_start", kwargs={"pk": dorobek_z_ukryta.pk, "format": "bib"}
    )
    with mock.patch("bpp.tasks.generuj_eksport_autora.delay"):
        admin_client.post(url)
        with mock.patch(
            "django_altcha.altcha.verify_solution", return_value=(True, None)
        ):
            client.post(url, {"captcha": "eyJjaGFsbGVuZ2UiOiAieCJ9"})

    zadania = AutorEksportTask.objects.filter(autor=dorobek_z_ukryta)
    assert sorted(list(t.ukryte_statusy) for t in zadania) == sorted([[], ukryte])


def test_eksport_async_wyklucza_ukryte(dorobek_z_ukryta, uczelnia):
    from bpp.tasks import generuj_eksport_autora

    task = AutorEksportTask.objects.create(
        autor=dorobek_z_ukryta,
        format="bib",
        ukryte_statusy=list(uczelnia.ukryte_statusy("podglad")),
    )
    generuj_eksport_autora(str(task.pk))
    task.refresh_from_db()
    body = task.result_file.read().decode("utf-8")
    assert "Praca widoczna" in body
    assert "Praca ukryta" not in body


def test_eksport_async_blad_bez_szczegolow(client, autor_jan_nowak):
    from bpp.tasks import KOMUNIKAT_BLEDU_EKSPORTU_AUTORA, generuj_eksport_autora

    task = AutorEksportTask.objects.create(autor=autor_jan_nowak, format="bib")
    with (
        mock.patch(
            "bpp.tasks._zbuduj_tresc_eksportu_autora",
            side_effect=RuntimeError("szczegol-wewnetrzny"),
        ),
        mock.patch("bpp.tasks.logger.exception") as log_mock,
        pytest.raises(RuntimeError),
    ):
        generuj_eksport_autora(str(task.pk))

    log_mock.assert_called_once()
    task.refresh_from_db()
    assert task.status == "failed"
    assert task.error_message == KOMUNIKAT_BLEDU_EKSPORTU_AUTORA

    url = reverse("bpp:autor_eksport_status", args=(task.pk,))
    body = client.get(url, HTTP_HX_REQUEST="true").content.decode("utf-8")
    assert "szczegol-wewnetrzny" not in body


# --- zdjęcie -----------------------------------------------------------------


def _png(w, h):
    buf = io.BytesIO()
    Image.new("L", (w, h)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def test_zdjecie_zbyt_duza_rozdzielczosc(monkeypatch):
    from django.core.exceptions import ValidationError

    from bpp.util import obrazy

    monkeypatch.setattr(obrazy, "MAKS_PIKSELI_ZDJECIA", 100 * 100)
    with pytest.raises(ValidationError):
        obrazy.przetworz_zdjecie_autora(_png(101, 100))
    obrazy.przetworz_zdjecie_autora(_png(100, 100))


def test_zdjecie_bomba_dekompresji(monkeypatch):
    from django.core.exceptions import ValidationError

    from bpp.util import obrazy

    # Limit Pillow poniżej własnego — DecompressionBombError z ``open()``.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(ValidationError):
        obrazy.przetworz_zdjecie_autora(_png(50, 50))


# --- admin: wybrane publikacje -----------------------------------------------


def _formset_admina(user, autor, ct, object_id):
    from django.contrib import admin

    from bpp.admin.autor import WybranaPublikacjaAutoraInline

    inline = WybranaPublikacjaAutoraInline(Autor, admin.site)
    # Bez uprawnień add/change admin ignoruje zmiany w formularzu inline.
    req = _request(user)
    FormSet = inline.get_formset(req, autor)
    prefix = FormSet.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-0-content_type": str(ct.pk),
        f"{prefix}-0-object_id": str(object_id),
        f"{prefix}-0-kolejnosc": "0",
    }
    return FormSet(data, instance=autor, prefix=prefix)


def test_admin_wybrane_tylko_modele_publikacji(admin_user, autor_jan_nowak):
    fs = _formset_admina(
        admin_user,
        autor_jan_nowak,
        ContentType.objects.get_for_model(Autor),
        autor_jan_nowak.pk,
    )
    assert not fs.is_valid()
    qs = fs.forms[0].fields["content_type"].queryset
    assert set(qs.values_list("model", flat=True)) <= {
        "wydawnictwo_ciagle",
        "wydawnictwo_zwarte",
        "praca_doktorska",
        "praca_habilitacyjna",
        "patent",
    }


def test_admin_wybrane_tylko_prace_autora(
    admin_user, autor_jan_nowak, autor_jan_kowalski, jednostka, wydawnictwo_ciagle
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)

    assert _formset_admina(
        admin_user, autor_jan_nowak, ct, wydawnictwo_ciagle.pk
    ).is_valid()
    assert not _formset_admina(
        admin_user, autor_jan_kowalski, ct, wydawnictwo_ciagle.pk
    ).is_valid()
