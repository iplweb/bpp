"""Limit zgłoszeń na godzinę, łączny rozmiar załączników, temat maila."""

import os

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_ZGLOSZENIA_PUBLIKACJI
from zglos_publikacje import limity
from zglos_publikacje.forms import MultipleFileField
from zglos_publikacje.models import Zgloszenie_Publikacji
from zglos_publikacje.storage import ZGLOS_TMP_DIRNAME
from zglos_publikacje.views import Zgloszenie_PublikacjiWizard, tytul_do_tematu

from .tests_zglos_publikacje import _zrob_submit_calego_formularza

PDF_PATH = os.path.join(os.path.dirname(__file__), "example.pdf")

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "zglos-limity-testy",
    }
}
DUMMY = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}


@pytest.fixture
def locmem_cache():
    with override_settings(CACHES=LOCMEM):
        cache.clear()
        yield cache
        cache.clear()


def _request(ip="10.0.0.1", user=None, xff=None):
    meta = {"REMOTE_ADDR": ip}
    if xff:
        meta["HTTP_X_FORWARDED_FOR"] = xff
    req = RequestFactory().post("/", **meta)
    req.user = user or AnonymousUser()
    return req


def _plik(name="a.pdf", size=1024):
    f = SimpleUploadedFile(name, b"x", content_type="application/pdf")
    f.size = size
    return f


def _tmp_files(media_root):
    d = os.path.join(media_root, "protected", ZGLOS_TMP_DIRNAME)
    if not os.path.isdir(d):
        return []
    return os.listdir(d)


# --------------------------------------------------------------------------
# Licznik (jednostkowo)
# --------------------------------------------------------------------------
@override_settings(ZGLOS_LIMIT_NA_GODZINE=2)
def test_limit_per_ip(locmem_cache):
    req = _request(ip="10.0.0.1")
    assert limity.zarezerwuj_zgloszenie(req) is True
    assert limity.zarezerwuj_zgloszenie(req) is True
    assert limity.limit_wyczerpany(req) is True
    assert limity.zarezerwuj_zgloszenie(req) is False
    # Inny adres IP ma własny licznik.
    inny = _request(ip="10.0.0.2")
    assert limity.limit_wyczerpany(inny) is False
    assert limity.zarezerwuj_zgloszenie(inny) is True


@override_settings(ZGLOS_LIMIT_NA_GODZINE=1)
def test_limit_per_ip_uzywa_ostatniego_wpisu_xff(locmem_cache):
    assert limity.zarezerwuj_zgloszenie(_request(xff="1.1.1.1, 10.9.9.9")) is True
    # Zmiana lewego (podawanego przez klienta) wpisu nie daje nowego licznika.
    assert limity.zarezerwuj_zgloszenie(_request(xff="2.2.2.2, 10.9.9.9")) is False


@pytest.mark.django_db
@override_settings(ZGLOS_LIMIT_NA_GODZINE=0, ZGLOS_LIMIT_NA_GODZINE_ZALOGOWANI=1)
def test_limit_per_uzytkownik(locmem_cache):
    u1 = baker.make("bpp.BppUser")
    u2 = baker.make("bpp.BppUser")
    assert limity.zarezerwuj_zgloszenie(_request(ip="10.0.0.1", user=u1)) is True
    # Ten sam użytkownik z innego IP — nadal ten sam licznik.
    assert limity.zarezerwuj_zgloszenie(_request(ip="10.0.0.2", user=u1)) is False
    # Inny użytkownik z tego samego IP — własny licznik.
    assert limity.zarezerwuj_zgloszenie(_request(ip="10.0.0.1", user=u2)) is True


@pytest.mark.django_db
@override_settings(ZGLOS_LIMIT_NA_GODZINE=2, ZGLOS_LIMIT_NA_GODZINE_ZALOGOWANI=3)
def test_osobne_limity_anonim_i_zalogowany(locmem_cache):
    anonim = _request(ip="10.0.0.1")
    assert [limity.zarezerwuj_zgloszenie(anonim) for _ in range(3)] == [
        True,
        True,
        False,
    ]
    # Zalogowany z tego samego IP ma własny, wyższy limit.
    zalogowany = _request(ip="10.0.0.1", user=baker.make("bpp.BppUser"))
    assert [limity.zarezerwuj_zgloszenie(zalogowany) for _ in range(4)] == [
        True,
        True,
        True,
        False,
    ]


@override_settings(ZGLOS_LIMIT_NA_GODZINE=0)
def test_limit_zero_wylacza(locmem_cache):
    req = _request()
    for _ in range(20):
        assert limity.zarezerwuj_zgloszenie(req) is True
    assert limity.limit_wyczerpany(req) is False


@override_settings(ZGLOS_LIMIT_NA_GODZINE=1, CACHES=DUMMY)
def test_cache_bez_licznikow_nie_blokuje():
    req = _request()
    assert limity.zarezerwuj_zgloszenie(req) is True
    assert limity.zarezerwuj_zgloszenie(req) is True


# --------------------------------------------------------------------------
# Limit w kreatorze
# --------------------------------------------------------------------------
def _uzyj_ip(webtest_app, ip="10.1.2.3"):
    webtest_app.extra_environ = {
        **(webtest_app.extra_environ or {}),
        "REMOTE_ADDR": ip,
    }


def _do_kroku2(webtest_app, forma="OTWARTY"):
    page = webtest_app.get(reverse("zglos_publikacje:nowe_zgloszenie"))
    page.forms[0]["0-rodzaj"] = "ARTYKUL"
    page = page.forms[0].submit()
    page.forms[0]["1-forma_dostepu"] = forma
    return page.forms[0].submit()


@pytest.mark.django_db
@override_settings(ZGLOS_LIMIT_NA_GODZINE=1)
def test_kreator_drugie_zgloszenie_odrzucone(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    locmem_cache,
):
    normal_django_user.email = "zespol@example.com"
    normal_django_user.save()
    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_ZGLOSZENIA_PUBLIKACJI)[0]
    )
    _uzyj_ip(webtest_app)

    _zrob_submit_calego_formularza(webtest_app, django_capture_on_commit_callbacks)
    assert Zgloszenie_Publikacji.objects.count() == 1
    assert len(mail.outbox) == 1

    page = _do_kroku2(webtest_app)
    page.forms[0]["2-tytul_oryginalny"] = "Drugie"
    page.forms[0]["2-rok"] = "2020"
    page.forms[0]["2-email"] = "test@test.pl"
    page.forms[0]["2-strona_www"] = "https://example.com/"
    resp = page.forms[0].submit()

    assert resp.status_code == 200
    assert "Przekroczono limit zgłoszeń" in resp.text
    assert "2-tytul_oryginalny" in resp.text  # nadal krok 2
    assert Zgloszenie_Publikacji.objects.count() == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(ZGLOS_LIMIT_NA_GODZINE=1)
def test_kreator_limit_wyczerpany_nie_zapisuje_plikow_tmp(
    webtest_app, uczelnia, settings, tmp_path, locmem_cache
):
    settings.MEDIA_ROOT = str(tmp_path)
    _uzyj_ip(webtest_app)
    # Wyczerp limit dla tego IP.
    assert limity.zarezerwuj_zgloszenie(_request(ip="10.1.2.3")) is True

    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    fields = [
        (n, v)
        for n, v in page.forms[0].submit_fields()
        if not (n and n.startswith("2-"))
    ]
    fields += [
        ("2-tytul_oryginalny", "Test"),
        ("2-rok", "2020"),
        ("2-email", "test@test.pl"),
        ("2-strona_www", "https://example.com/"),
    ]
    with open(PDF_PATH, "rb") as fh:
        pdf = fh.read()
    resp = webtest_app.post(
        reverse("zglos_publikacje:nowe_zgloszenie"),
        params=fields,
        upload_files=[("2-pliki", "a.pdf", pdf)],
    )
    assert "Przekroczono limit zgłoszeń" in resp.text
    assert _tmp_files(str(tmp_path)) == []


@pytest.mark.django_db
@override_settings(ZGLOS_LIMIT_NA_GODZINE=1)
def test_kreator_rezerwacja_w_done_domyka_wyscig(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
    locmem_cache,
    monkeypatch,
):
    """Gdy limit wyczerpie się między krokiem 2 a zakończeniem (równoległe
    żądania), done() nie zapisuje zgłoszenia i nie wysyła maila."""
    normal_django_user.email = "zespol@example.com"
    normal_django_user.save()
    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_ZGLOSZENIA_PUBLIKACJI)[0]
    )
    _uzyj_ip(webtest_app)
    monkeypatch.setattr("zglos_publikacje.views.limit_wyczerpany", lambda r: False)
    assert limity.zarezerwuj_zgloszenie(_request(ip="10.1.2.3")) is True

    result = _zrob_submit_calego_formularza(
        webtest_app, django_capture_on_commit_callbacks
    )
    assert Zgloszenie_Publikacji.objects.count() == 0
    assert len(mail.outbox) == 0
    assert "Przekroczono limit zgłoszeń" in result.text


# --------------------------------------------------------------------------
# Łączny rozmiar załączników
# --------------------------------------------------------------------------
MB = 1024 * 1024


@override_settings(ZGLOS_MAX_LACZNY_ROZMIAR_MB=1)
def test_laczny_rozmiar_odrzucony():
    pole = MultipleFileField(required=False)
    with pytest.raises(ValidationError, match="Łączny rozmiar"):
        pole.clean([_plik("a.pdf", 600 * 1024), _plik("b.pdf", 600 * 1024)])


@override_settings(ZGLOS_MAX_LACZNY_ROZMIAR_MB=1)
def test_laczny_rozmiar_w_limicie():
    pole = MultipleFileField(required=False)
    pliki = [_plik("a.pdf", 400 * 1024), _plik("b.pdf", 400 * 1024)]
    assert len(pole.clean(pliki)) == 2


@override_settings(ZGLOS_MAX_LACZNY_ROZMIAR_MB=1)
def test_pliki_w_limicie_przycina_do_lacznego_rozmiaru(monkeypatch):
    monkeypatch.setattr(
        "zglos_publikacje.views.rollbar.report_message", lambda *a, **k: None
    )
    pliki = [_plik(f"p{i}.pdf", 400 * 1024) for i in range(3)]
    wynik = Zgloszenie_PublikacjiWizard()._pliki_w_limicie(pliki)
    assert [f.name for f in wynik] == ["p0.pdf", "p1.pdf"]


def test_domyslny_laczny_limit_50_mb():
    from zglos_publikacje.validators import max_laczny_rozmiar_plikow

    assert max_laczny_rozmiar_plikow() == 50 * MB


# --------------------------------------------------------------------------
# Temat maila
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tytul,oczekiwany",
    [
        ("Zwykły tytuł", "Zwykły tytuł"),
        ("A\r\nB\tC", "A B C"),
        ("A B C\x00D‎E", "A B C D E"),
        ("", ""),
        (None, ""),
    ],
)
def test_tytul_do_tematu_usuwa_znaki_sterujace(tytul, oczekiwany):
    assert tytul_do_tematu(tytul) == oczekiwany


def test_tytul_do_tematu_przycina():
    wynik = tytul_do_tematu("x" * 500)
    assert len(wynik) == 100
    assert wynik.endswith("…")


@pytest.mark.django_db
def test_temat_maila_przyciety(
    webtest_app,
    django_capture_on_commit_callbacks,
    normal_django_user,
    typy_odpowiedzialnosci,
    uczelnia,
):
    normal_django_user.email = "zespol@example.com"
    normal_django_user.save()
    normal_django_user.groups.add(
        Group.objects.get_or_create(name=GR_ZGLOSZENIA_PUBLIKACJI)[0]
    )
    _zrob_submit_calego_formularza(
        webtest_app,
        django_capture_on_commit_callbacks,
        tytul_oryginalny="Długi tytuł " * 15,
    )
    assert len(mail.outbox) == 1
    temat = mail.outbox[0].subject
    assert "\n" not in temat and "\r" not in temat
    assert len(temat) < 200
    assert "…" in temat
