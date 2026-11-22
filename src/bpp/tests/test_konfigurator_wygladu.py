import json
import re

import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import MOTYW_WLASNY, MotywWlasny
from django_bpp.version import VERSION

# Link do CSS-a motywu z plików statycznych (w testach z haszem w nazwie).
RE_MOTYW_STATYCZNY = re.compile(r'href="[^"]*/scss/app-[^"]*\.css"')

KONFIG = {"wersja": 1, "kolor_glowny": "#284fab", "tryb_kolorow": "ciemny"}
CSS = "body{color:#123456}"


def _zastosuj(client, **dane):
    return client.post(
        reverse("bpp:konfigurator_wygladu_zastosuj"),
        data=json.dumps(dane),
        content_type="application/json",
    )


# --- dostęp --------------------------------------------------------------------


@pytest.mark.django_db
def test_konfigurator_wymaga_obslugi(client, uczelnia):
    res = client.get(reverse("bpp:konfigurator_wygladu"))
    assert res.status_code == 302


@pytest.mark.django_db
def test_konfigurator_dla_obslugi(staff_client, uczelnia):
    res = staff_client.get(reverse("bpp:konfigurator_wygladu"))
    assert res.status_code == 200
    assert b"konfigurator-podglady" in res.content
    stan = json.loads(
        res.content.split(b'id="konfigurator-serwer" type="application/json">')[
            1
        ].split(b"</script>")[0]
    )
    assert stan["mozna_zastosowac"] is False


@pytest.mark.django_db
def test_zastosuj_tylko_superuzytkownik(staff_client, uczelnia):
    res = _zastosuj(staff_client, konfig=KONFIG)
    assert res.status_code == 403
    assert not MotywWlasny.objects.exists()


# --- zastosowanie ----------------------------------------------------------------


@pytest.mark.django_db
def test_zastosuj_kompiluje_na_serwerze_i_wlacza(superuser_client, uczelnia):
    # Przeglądarka wysyła tylko ustawienia; przesłany CSS jest ignorowany.
    res = _zastosuj(superuser_client, konfig=KONFIG, css="body{display:none}")
    assert res.status_code == 200, res.content

    motyw = MotywWlasny.objects.get(uczelnia=uczelnia)
    assert motyw.konfig == KONFIG
    assert "display:none" not in motyw.css[:100]
    assert ".top-bar" in motyw.css
    assert len(motyw.skrot) == 64
    assert motyw.wersja_bpp == VERSION
    uczelnia.refresh_from_db()
    assert uczelnia.theme_name == MOTYW_WLASNY


@pytest.mark.django_db
@pytest.mark.parametrize(
    "dane",
    [
        {},
        {"konfig": "nie-slownik"},
        {"konfig": {"kolor_glowny": "#ffff00"}},  # za mały kontrast
        {"konfig": {"tlo_obraz": "javascript:alert(1)"}},
        {"konfig": {"nieznane": 1}},
    ],
)
def test_zastosuj_odrzuca_zle_ustawienia(superuser_client, uczelnia, dane):
    res = _zastosuj(superuser_client, **dane)
    assert res.status_code == 400
    assert res.json()["blad"]
    assert not MotywWlasny.objects.exists()


@pytest.mark.django_db
def test_zastosuj_odrzuca_zly_json(superuser_client, uczelnia):
    res = superuser_client.post(
        reverse("bpp:konfigurator_wygladu_zastosuj"),
        data="{",
        content_type="application/json",
    )
    assert res.status_code == 400


# --- serwowanie i strony ----------------------------------------------------------


@pytest.mark.django_db
def test_css_motywu_z_cache_na_zawsze(client, uczelnia):
    motyw = baker.make(MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS)
    res = client.get(reverse("bpp:motyw_wlasny_css", args=(motyw.skrot,)))
    assert res.status_code == 200
    assert res["Content-Type"].startswith("text/css")
    assert "immutable" in res["Cache-Control"]
    assert res.content.decode() == CSS


@pytest.mark.django_db
def test_css_motywu_nieznany_skrot(client, uczelnia):
    res = client.get(reverse("bpp:motyw_wlasny_css", args=("0" * 64,)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_strona_dolacza_motyw_wlasny(client, uczelnia):
    motyw = baker.make(MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS)
    uczelnia.theme_name = MOTYW_WLASNY
    uczelnia.save()

    html = client.get("/").content.decode()
    assert reverse("bpp:motyw_wlasny_css", args=(motyw.skrot,)) in html
    assert not RE_MOTYW_STATYCZNY.search(html)


@pytest.mark.django_db
def test_motyw_wlasny_bez_zapisu_wraca_do_domyslnego(client, uczelnia, settings):
    uczelnia.theme_name = MOTYW_WLASNY
    uczelnia.save()

    html = client.get("/").content.decode()
    assert f"/scss/{settings.THEME_NAME}." in html
    assert "motyw-wlasny" not in html


@pytest.mark.django_db
def test_podglad_motywu_tylko_dla_obslugi(staff_client, uczelnia):
    # Osobny klient: fikstura `staff_client` loguje współdzielony `client`.
    html = Client().get("/?podglad_motywu=1").content.decode()
    assert 'id="bpp-motyw-podglad"' not in html
    assert RE_MOTYW_STATYCZNY.search(html)

    html = staff_client.get("/?podglad_motywu=1").content.decode()
    assert 'id="bpp-motyw-podglad"' in html
    assert not RE_MOTYW_STATYCZNY.search(html)


# --- admin uczelni ----------------------------------------------------------------


@pytest.mark.django_db
def test_admin_oferuje_motyw_wlasny_gdy_zapisany(uczelnia):
    from bpp.admin.uczelnia import UczelniaAdminForm

    def wartosci():
        form = UczelniaAdminForm(instance=uczelnia)
        return [v for v, _ in form.fields["theme_name"].choices]

    assert MOTYW_WLASNY not in wartosci()
    baker.make(MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS)
    assert MOTYW_WLASNY in wartosci()


@pytest.mark.django_db
def test_strona_demo_komunikatow(staff_client, uczelnia):
    res = staff_client.get(reverse("bpp:konfigurator_wygladu_demo"))
    assert res.status_code == 200
    html = res.content.decode()
    for klasa in ("callout primary", "callout success", "callout alert"):
        assert klasa in html
    # Komunikaty flash (wszystkie poziomy) trafiają do skryptu channelsBroadcast.
    for poziom in ("info", "success", "warning", "error"):
        assert f"cssClass: '{poziom}'" in html


@pytest.mark.django_db
def test_strona_demo_tylko_dla_obslugi(client, uczelnia):
    res = client.get(reverse("bpp:konfigurator_wygladu_demo"))
    assert res.status_code == 302


# --- migracja wyglądu ----------------------------------------------------------------


@pytest.mark.django_db
def test_odswiez_motywy_przebudowuje_tylko_nieaktualne(uczelnia):
    from django.core.management import call_command

    stary = baker.make(
        MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS, wersja_bpp="1.0"
    )
    call_command("odswiez_motywy")

    stary.refresh_from_db()
    assert stary.wersja_bpp == VERSION
    assert ".top-bar" in stary.css
    nowy_skrot = stary.skrot

    # Drugi przebieg: motyw aktualny — bez zmian.
    call_command("odswiez_motywy")
    stary.refresh_from_db()
    assert stary.skrot == nowy_skrot


@pytest.mark.django_db
def test_odswiez_motywy_zostawia_stary_css_przy_bledzie(uczelnia):
    from django.core.management import CommandError, call_command

    zly = baker.make(
        MotywWlasny,
        uczelnia=uczelnia,
        konfig={"kolor_glowny": "#ffff00"},
        css=CSS,
        wersja_bpp="1.0",
    )
    with pytest.raises(CommandError):
        call_command("odswiez_motywy")
    zly.refresh_from_db()
    assert zly.css == CSS
    assert zly.wersja_bpp == "1.0"


# --- klient kompilatora (serwis HTTP) -------------------------------------------------


class _Odpowiedz:
    def __init__(self, status_code, tekst="", dane=None):
        self.status_code = status_code
        self.text = tekst
        self._dane = dane

    def json(self):
        if self._dane is None:
            raise ValueError("brak JSON")
        return self._dane


def test_kompilator_przez_serwis(settings, monkeypatch):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095/"
    wywolania = []

    def post(url, json, timeout):
        wywolania.append((url, json))
        return _Odpowiedz(200, tekst="body{}")

    monkeypatch.setattr(motyw_kompilator.requests, "post", post)
    assert motyw_kompilator.kompiluj(KONFIG) == "body{}"
    assert wywolania[0][0] == "http://motyw-kompilator:8095/kompiluj"
    assert wywolania[0][1]["konfig"] == KONFIG
    assert wywolania[0][1]["czcionkiUrl"].endswith("/bpp/fonts")


def test_kompilator_serwis_zwraca_bledy_ustawien(settings, monkeypatch):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"
    bledy = [{"pole": "kolor_glowny", "komunikat": "Za jasny."}]
    monkeypatch.setattr(
        motyw_kompilator.requests,
        "post",
        lambda url, json, timeout: _Odpowiedz(
            400, tekst=__import__("json").dumps({"blad": "Za jasny.", "bledy": bledy})
        ),
    )
    with pytest.raises(motyw_kompilator.BladKompilacjiMotywu) as e:
        motyw_kompilator.kompiluj(KONFIG)
    assert str(e.value) == "Za jasny."
    assert e.value.bledy == bledy


def test_kompilator_blad_wewnetrzny_bez_szczegolow(settings, monkeypatch):
    """Nieoczekiwany błąd kompilatora: użytkownik dostaje ogólny komunikat,
    szczegóły (np. ścieżki, stos) tylko w logu."""
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"
    monkeypatch.setattr(
        motyw_kompilator.requests,
        "post",
        lambda url, json, timeout: _Odpowiedz(
            500, tekst='{"blad": "/app/x.js:1 boom"}'
        ),
    )
    wynik = motyw_kompilator.skompiluj(KONFIG)
    assert not wynik.ok
    assert "/app/" not in wynik.blad
    assert "log" in wynik.blad


def test_kompilator_serwis_niedostepny(settings, monkeypatch):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"

    def post(url, json, timeout):
        raise motyw_kompilator.requests.ConnectionError("odmowa")

    monkeypatch.setattr(motyw_kompilator.requests, "post", post)
    with pytest.raises(motyw_kompilator.BladKompilacjiMotywu, match="niedostępny"):
        motyw_kompilator.kompiluj(KONFIG)


@pytest.mark.parametrize(
    "obraz",
    [
        "http://example.com/obrazek-z-zewnatrz",
        "data:text/html;base64,PGI+",
        "data:image/png;base64," + "A" * (700 * 1024),
    ],
)
def test_kompilator_odrzuca_obrazek_przed_wyslaniem(settings, monkeypatch, obraz):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"

    def post(url, json, timeout):
        raise AssertionError("nie powinno dojść do kompilatora")

    monkeypatch.setattr(motyw_kompilator.requests, "post", post)
    with pytest.raises(motyw_kompilator.BladKompilacjiMotywu, match="Grafika"):
        motyw_kompilator.kompiluj({**KONFIG, "tlo_obraz": obraz})


@pytest.mark.django_db
def test_odswiez_motywy_gdy_kompilator_nie_wstaje(uczelnia, monkeypatch):
    from django.core.management import CommandError, call_command

    monkeypatch.setattr(
        "bpp.management.commands.odswiez_motywy.czekaj_na_kompilator", lambda: False
    )
    motyw = baker.make(
        MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS, wersja_bpp="1.0"
    )
    with pytest.raises(CommandError, match="nie odpowiada"):
        call_command("odswiez_motywy")
    motyw.refresh_from_db()
    assert motyw.css == CSS


def test_czekaj_na_kompilator_limit_czasu(settings, monkeypatch):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"

    def get(url, timeout):
        raise motyw_kompilator.requests.ConnectionError("odmowa")

    monkeypatch.setattr(motyw_kompilator.requests, "get", get)
    monkeypatch.setattr(motyw_kompilator.time, "sleep", lambda s: None)
    assert motyw_kompilator.czekaj_na_kompilator(limit_s=0) is False


# --- favicon --------------------------------------------------------------------------


def _png_data_url(rozmiar=(64, 64)):
    import base64
    import io

    from PIL import Image

    bufor = io.BytesIO()
    Image.new("RGBA", rozmiar, (200, 30, 40, 255)).save(bufor, format="PNG")
    return "data:image/png;base64," + base64.b64encode(bufor.getvalue()).decode()


@pytest.mark.django_db
def test_zastosuj_zapisuje_favicon(superuser_client, uczelnia, settings, tmp_path):
    from favicon.models import Favicon

    settings.MEDIA_ROOT = str(tmp_path)
    res = _zastosuj(superuser_client, konfig=KONFIG, favicon=_png_data_url())
    assert res.status_code == 200, res.content

    uczelnia.refresh_from_db()
    assert uczelnia.favicon_ico.name.endswith(".png")
    fav = Favicon.objects.get(site=uczelnia.site, isFavicon=True)
    assert fav.faviconImage


@pytest.mark.django_db
@pytest.mark.parametrize(
    "favicon",
    [
        "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
        "data:image/png;base64,bmllLW9icmF6ZWs=",  # nie obraz
    ],
)
def test_zastosuj_odrzuca_zly_favicon(superuser_client, uczelnia, favicon):
    res = _zastosuj(superuser_client, konfig=KONFIG, favicon=favicon)
    assert res.status_code == 400
    assert "Ikona" in res.json()["blad"]
    assert not MotywWlasny.objects.exists()


# --- unieważnianie cache faviconu ------------------------------------------------------


@pytest.fixture
def cache_locmem(settings):
    """Domyślny cache testów to Dummy (incr/get nic nie pamiętają) — LocMem."""
    from django.core.cache import cache

    poprzednie = settings.CACHES
    settings.CACHES = {
        **poprzednie,
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-favicon-wersja",
        },
    }
    cache.clear()
    yield cache
    cache.clear()
    settings.CACHES = poprzednie


@pytest.mark.django_db
def test_zapis_ikony_podbija_wersje_faviconu(
    uczelnia, settings, tmp_path, cache_locmem
):
    from django.core.files.base import ContentFile

    from bpp.favicon_wersja import wersja

    settings.MEDIA_ROOT = str(tmp_path)
    przed = wersja()
    uczelnia.favicon_ico.save("a.png", ContentFile(b"x"), save=True)
    assert wersja() > przed


@pytest.mark.django_db
def test_favicon_ico_etag_i_nowa_ikona(client, uczelnia, settings, tmp_path):
    import base64

    from django.core.files.base import ContentFile

    settings.MEDIA_ROOT = settings.SENDFILE_ROOT = str(tmp_path)
    png = base64.b64decode(_png_data_url().split(",", 1)[1])
    uczelnia.favicon_ico.save("pierwsza.png", ContentFile(png), save=True)

    res = client.get("/favicon.ico")
    assert res.status_code == 200
    etag = res["ETag"]
    assert client.get("/favicon.ico", HTTP_IF_NONE_MATCH=etag).status_code == 304

    uczelnia.favicon_ico.save("druga.png", ContentFile(png), save=True)
    res = client.get("/favicon.ico", HTTP_IF_NONE_MATCH=etag)
    assert res.status_code == 200
    assert res["ETag"] != etag


# --- jedna kompilacja naraz ------------------------------------------------------------


@pytest.mark.django_db
def test_zastosuj_gdy_trwa_inna_kompilacja_429(
    superuser_client, uczelnia, cache_locmem
):
    from bpp.motyw_kompilator import KLUCZ_BLOKADY

    cache_locmem.set(KLUCZ_BLOKADY, 1)
    res = _zastosuj(superuser_client, konfig=KONFIG)
    assert res.status_code == 429
    assert res["Retry-After"] == "5"
    assert "Trwa budowanie" in res.json()["blad"]
    assert not MotywWlasny.objects.exists()


def test_kompiluj_zwalnia_blokade_po_bledzie(settings, monkeypatch, cache_locmem):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"

    def post(url, json, timeout):
        raise motyw_kompilator.requests.ConnectionError("odmowa")

    monkeypatch.setattr(motyw_kompilator.requests, "post", post)
    with pytest.raises(motyw_kompilator.BladKompilacjiMotywu):
        motyw_kompilator.kompiluj(KONFIG)
    assert cache_locmem.get(motyw_kompilator.KLUCZ_BLOKADY) is None


# --- zapis bez stosowania (motyw roboczy) -----------------------------------------------


def _zapisz(client, **dane):
    return client.post(
        reverse("bpp:konfigurator_wygladu_zapisz"),
        data=json.dumps(dane),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_zapisz_nie_zmienia_strony(staff_client, uczelnia):
    # Zapisać może też obsługa bez prawa „Zastosuj” — strona się nie zmienia.
    res = _zapisz(staff_client, konfig=KONFIG)
    assert res.status_code == 200, res.content
    motyw = MotywWlasny.objects.get(uczelnia=uczelnia)
    assert motyw.konfig_roboczy == KONFIG
    assert motyw.css == ""
    assert motyw.skrot == ""
    uczelnia.refresh_from_db()
    assert uczelnia.theme_name != MOTYW_WLASNY


@pytest.mark.django_db
def test_zapisz_odrzuca_zly_obrazek(staff_client, uczelnia):
    res = _zapisz(staff_client, konfig={**KONFIG, "tlo_obraz": "javascript:x"})
    assert res.status_code == 400
    assert not MotywWlasny.objects.exists()


@pytest.mark.django_db
def test_zastosuj_czysci_motyw_roboczy(superuser_client, uczelnia):
    _zapisz(superuser_client, konfig=KONFIG)
    assert _zastosuj(superuser_client, konfig=KONFIG).status_code == 200
    motyw = MotywWlasny.objects.get(uczelnia=uczelnia)
    assert motyw.konfig_roboczy is None
    assert motyw.css


@pytest.mark.django_db
def test_zastosuj_bez_kompilatora_proponuje_zapis(
    superuser_client, uczelnia, settings, monkeypatch
):
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"

    def post(url, json, timeout):
        raise motyw_kompilator.requests.ConnectionError("odmowa")

    monkeypatch.setattr(motyw_kompilator.requests, "post", post)
    res = _zastosuj(superuser_client, konfig=KONFIG)
    assert res.status_code == 400
    assert res.json()["niedostepny"] is True


@pytest.mark.django_db
def test_odswiez_motywy_pomija_sam_motyw_roboczy(staff_client, uczelnia):
    from django.core.management import call_command

    _zapisz(staff_client, konfig=KONFIG)
    call_command("odswiez_motywy", "--wszystkie")
    assert MotywWlasny.objects.get().css == ""


@pytest.mark.django_db
def test_konfigurator_zna_stan_kompilatora_i_roboczy(staff_client, uczelnia):
    _zapisz(staff_client, konfig=KONFIG)
    res = staff_client.get(reverse("bpp:konfigurator_wygladu"))
    stan = json.loads(
        res.content.split(b'id="konfigurator-serwer" type="application/json">')[
            1
        ].split(b"</script>")[0]
    )
    assert "kompilator_dostepny" in stan
    assert stan["roboczy"]["konfig"] == KONFIG


# --- strona błędu 500 w motywie z konfiguratora -----------------------------------------


@pytest.mark.django_db
def test_strona_500_ma_css_motywu_obok_siebie(uczelnia, settings, tmp_path):
    from django.core.management import call_command

    settings.STATIC_ROOT = str(tmp_path)
    motyw = baker.make(MotywWlasny, uczelnia=uczelnia, konfig=KONFIG, css=CSS)
    uczelnia.theme_name = MOTYW_WLASNY
    uczelnia.save()
    stara = tmp_path / "500" / ("motyw-" + "0" * 64 + ".css")
    stara.parent.mkdir(parents=True)
    stara.write_text("stary")

    call_command("generate_500_page")

    kopia = tmp_path / "500" / f"motyw-{motyw.skrot}.css"
    assert kopia.read_text() == CSS
    html = (tmp_path / "500" / f"{uczelnia.site.domain}.html").read_text()
    # nginx serwuje stronę 500, gdy Django leży — CSS nie może iść przez widok.
    assert f"/500/motyw-{motyw.skrot}.css" in html
    assert "/bpp/motyw-wlasny/" not in html
    assert not stara.exists()


@pytest.mark.django_db
def test_zastosuj_przebudowuje_strone_500(
    superuser_client, uczelnia, settings, tmp_path
):
    settings.STATIC_ROOT = str(tmp_path)
    assert _zastosuj(superuser_client, konfig=KONFIG).status_code == 200
    motyw = MotywWlasny.objects.get(uczelnia=uczelnia)
    assert (tmp_path / "500" / f"motyw-{motyw.skrot}.css").exists()


# --- historia i cofanie --------------------------------------------------------------


@pytest.mark.django_db
def test_zastosuj_zapisuje_historie_i_motyw_sprzed(superuser_client, uczelnia):
    from bpp.models import MotywWersja

    uczelnia.theme_name = "app-green"
    uczelnia.save()
    _zastosuj(superuser_client, konfig=KONFIG)
    _zastosuj(superuser_client, konfig={**KONFIG, "kolor_glowny": "#1f3a5f"})

    wersje = list(MotywWersja.objects.filter(uczelnia=uczelnia))
    assert [w.konfig["kolor_glowny"] for w in wersje] == ["#1f3a5f", "#284fab"]
    assert [w.motyw_przed for w in wersje] == [MOTYW_WLASNY, "app-green"]

    res = superuser_client.get(reverse("bpp:konfigurator_wygladu"))
    stan = json.loads(
        res.content.split(b'id="konfigurator-serwer" type="application/json">')[
            1
        ].split(b"</script>")[0]
    )
    assert len(stan["historia"]) == 2
    assert stan["motyw_sprzed"]["wartosc"] == "app-green"


@pytest.mark.django_db
def test_historia_ma_limit(uczelnia):
    from bpp.models import MotywWersja
    from bpp.models.motyw_wlasny import HISTORIA_MOTYWU_LIMIT

    for i in range(HISTORIA_MOTYWU_LIMIT + 3):
        MotywWersja.zapisz(uczelnia, {"i": i}, "", None, "1")
    wersje = MotywWersja.objects.filter(uczelnia=uczelnia)
    assert wersje.count() == HISTORIA_MOTYWU_LIMIT
    assert wersje.first().konfig == {"i": HISTORIA_MOTYWU_LIMIT + 2}


@pytest.mark.django_db
def test_wersja_z_historii_tylko_swojej_uczelni(staff_client, uczelnia):
    from bpp.models import MotywWersja

    wersja = MotywWersja.objects.create(uczelnia=uczelnia, konfig=KONFIG)
    res = staff_client.get(
        reverse("bpp:konfigurator_wygladu_wersja", args=(wersja.pk,))
    )
    assert res.json()["konfig"] == KONFIG

    inna = baker.make("bpp.Uczelnia", skrot="IN")
    obca = MotywWersja.objects.create(uczelnia=inna, konfig=KONFIG)
    res = staff_client.get(reverse("bpp:konfigurator_wygladu_wersja", args=(obca.pk,)))
    assert res.status_code == 404


def _przywroc(client, **dane):
    return client.post(
        reverse("bpp:konfigurator_wygladu_przywroc"),
        data=json.dumps(dane),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_przywroc_motyw_sprzed_konfiguratora(superuser_client, uczelnia):
    uczelnia.theme_name = MOTYW_WLASNY
    uczelnia.save()
    assert _przywroc(superuser_client, motyw="app-green").status_code == 200
    uczelnia.refresh_from_db()
    assert uczelnia.theme_name == "app-green"


@pytest.mark.django_db
def test_przywroc_odrzuca_nieznany_motyw(superuser_client, uczelnia):
    assert _przywroc(superuser_client, motyw="app-hakerski").status_code == 400
    assert _przywroc(superuser_client, motyw=MOTYW_WLASNY).status_code == 400


@pytest.mark.django_db
def test_przywroc_tylko_superuzytkownik(staff_client, uczelnia):
    # Osobny test: fikstury *_client logują ten sam obiekt `client`.
    assert _przywroc(staff_client, motyw="app-green").status_code == 403


# --- przymiarka (tylko ta sesja) ------------------------------------------------------


@pytest.mark.django_db
def test_przymiarka_widoczna_tylko_w_tej_sesji(staff_client, uczelnia):
    res = staff_client.post(
        reverse("bpp:konfigurator_wygladu_przymierz"),
        data=json.dumps({"konfig": KONFIG}),
        content_type="application/json",
    )
    assert res.status_code == 200, res.content

    html = staff_client.get("/").content.decode()
    assert "/bpp/motyw-przymiarka/" in html
    assert "Przymierzasz motyw" in html
    adres = re.search(r'href="(/bpp/motyw-przymiarka/[0-9a-f]{64}\.css)"', html)
    css = staff_client.get(adres.group(1))
    assert css.status_code == 200
    assert ".top-bar" in css.content.decode()

    # Odwiedzający (inna sesja) nie widzi ani przymiarki, ani jej CSS.
    anonim = Client()
    assert "motyw-przymiarka" not in anonim.get("/").content.decode()
    assert anonim.get(adres.group(1)).status_code == 302

    # Zakończenie przymiarki.
    res = staff_client.post(
        reverse("bpp:konfigurator_wygladu_przymiarka_koniec"), {"next": "/bpp/autorzy/"}
    )
    assert res.status_code == 302 and res["Location"] == "/bpp/autorzy/"
    assert "motyw-przymiarka" not in staff_client.get("/").content.decode()


@pytest.mark.django_db
def test_przymiarka_konczy_sie_po_dobie(staff_client, uczelnia):
    from datetime import timedelta

    from django.utils.timezone import now

    from bpp.models import MotywPrzymiarka

    staff_client.post(
        reverse("bpp:konfigurator_wygladu_przymierz"),
        data=json.dumps({"konfig": KONFIG}),
        content_type="application/json",
    )
    MotywPrzymiarka.objects.update(utworzono=now() - timedelta(days=2))
    assert "motyw-przymiarka" not in staff_client.get("/").content.decode()


@pytest.mark.django_db
def test_koniec_przymiarki_nie_przekierowuje_na_obca_domene(staff_client, uczelnia):
    res = staff_client.post(
        reverse("bpp:konfigurator_wygladu_przymiarka_koniec"),
        {"next": "https://zly.example.com/"},
    )
    assert res["Location"] == "/"


def test_kompilator_bez_zasobow_to_niedostepny(settings, monkeypatch):
    """Serwis działa, ale wolumen plików statycznych nie ma jeszcze jego
    zasobów (start appservera, starsza wersja BPP) — 503 = „niedostępny”,
    konfigurator proponuje zapisanie motywu."""
    from bpp import motyw_kompilator

    settings.BPP_MOTYW_KOMPILATOR_URL = "http://motyw-kompilator:8095"
    monkeypatch.setattr(
        motyw_kompilator.requests,
        "post",
        lambda url, json, timeout: _Odpowiedz(503, tekst='{"blad": "brak"}'),
    )
    wynik = motyw_kompilator.skompiluj(KONFIG)
    assert wynik.rodzaj == motyw_kompilator.BRAK_KOMPILATORA
