"""Testy limitów uploadu na poziomie kreatora zgłoszeń (sekcje A1/A3/B/B2/B3).

Pokrywa:
- `_pliki_w_limicie` (A3) — defensywny filtr + alarm rollbar,
- rewiring `process_step_files` (A1) — utrwalanie tylko zwalidowanych plików
  kroku 2, `return {}` dla pozostałych ścieżek (zamknięcie wektora review #1),
- rozdzielenie katalogu tmp od trwałego (B),
- odporność na late-completion (`render_done`, B2),
- sprzątanie tmp przy restarcie kreatora przez GET (B3).

Katalog tmp/trwały weryfikujemy na dysku pod `settings.MEDIA_ROOT` (tmp_path).
`Zgloszenie_PublikacjiWizard.file_storage` to cached_property liczony w
runtime, więc podmiana MEDIA_ROOT przez fikstury pytest-django działa.
"""

import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from zglos_publikacje.models import Zgloszenie_Publikacji
from zglos_publikacje.storage import ZGLOS_TMP_DIRNAME
from zglos_publikacje.validators import MAX_LICZBA_PLIKOW, MAX_ROZMIAR_PLIKU
from zglos_publikacje.views import Zgloszenie_PublikacjiWizard

PDF_PATH = os.path.join(os.path.dirname(__file__), "example.pdf")


# --------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------
def _pdf_bytes():
    with open(PDF_PATH, "rb") as fh:
        return fh.read()


def _plik(name="a.pdf", size=1024):
    """SimpleUploadedFile z nadpisanym `.size` (bez alokacji realnych MB)."""
    f = SimpleUploadedFile(name, b"x", content_type="application/pdf")
    f.size = size
    return f


def _url():
    return reverse("zglos_publikacje:nowe_zgloszenie")


def _tmp_dir(media_root):
    return os.path.join(media_root, "protected", ZGLOS_TMP_DIRNAME)


def _perm_dir(media_root):
    return os.path.join(media_root, "protected", "zglos_publikacje")


def _list_files(d):
    if not os.path.isdir(d):
        return []
    return [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]


def _step0(webtest_app, rodzaj="ARTYKUL"):
    page = webtest_app.get(_url())
    page.forms[0]["0-rodzaj"] = rodzaj
    return page.forms[0].submit()


def _do_kroku2(webtest_app, rodzaj="ARTYKUL", forma="OGRANICZONY"):
    page1 = _step0(webtest_app, rodzaj)
    page1.forms[0]["1-forma_dostepu"] = forma
    return page1.forms[0].submit()


def _post_step2_pliki(webtest_app, page, *, ile_plikow, rok="2020"):
    """Submit kroku 2 z N plikami przez `webtest_app.post`.

    `webtest`-owy Form nie obsługuje wieloplikowych pól z tym samym `name=`,
    więc schodzimy do `post()` z `upload_files` (zachowuje duplikaty kluczy).
    Pozostałe pola (management_form itd.) przepisujemy z aktualnego formularza.
    """
    form = page.forms[0]
    fields = [(n, v) for n, v in form.submit_fields() if not (n and n.startswith("2-"))]
    fields.extend(
        [
            ("2-tytul_oryginalny", "Test"),
            ("2-rok", str(rok)),
            ("2-email", "test@test.pl"),
            ("2-strona_www", "https://example.com/"),
        ]
    )
    upload_files = [
        ("2-pliki", f"plik_{i}.pdf", _pdf_bytes()) for i in range(ile_plikow)
    ]
    return webtest_app.post(_url(), params=fields, upload_files=upload_files)


def _goto_step(webtest_app, page, step):
    """Cofnij kreator na wskazany krok (`wizard_goto_step`)."""
    fields = list(page.forms[0].submit_fields())
    fields.append(("wizard_goto_step", step))
    return webtest_app.post(_url(), params=fields)


# --------------------------------------------------------------------------
# 2b. `_pliki_w_limicie` — filtr defensywny (A3)
# --------------------------------------------------------------------------
def _patch_rollbar(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "zglos_publikacje.views.rollbar.report_message",
        lambda *a, **k: calls.append((a, k)),
    )
    return calls


def test_pliki_w_limicie_odrzuca_za_duzy_plik(monkeypatch):
    calls = _patch_rollbar(monkeypatch)
    wizard = Zgloszenie_PublikacjiWizard()
    pliki = [_plik(name="ok.pdf"), _plik(name="big.pdf", size=MAX_ROZMIAR_PLIKU + 1)]
    result = wizard._pliki_w_limicie(pliki)
    assert [f.name for f in result] == ["ok.pdf"]
    assert calls, "odrzucenie za dużego pliku musi zaalarmować rollbar"


def test_pliki_w_limicie_przycina_do_maksimum(monkeypatch):
    calls = _patch_rollbar(monkeypatch)
    wizard = Zgloszenie_PublikacjiWizard()
    pliki = [_plik(name=f"p{i}.pdf") for i in range(7)]
    result = wizard._pliki_w_limicie(pliki)
    assert len(result) == MAX_LICZBA_PLIKOW
    assert calls, "przycięcie liczby plików musi zaalarmować rollbar"


def test_pliki_w_limicie_przepuszcza_bez_alarmu(monkeypatch):
    calls = _patch_rollbar(monkeypatch)
    wizard = Zgloszenie_PublikacjiWizard()
    pliki = [_plik(name=f"p{i}.pdf") for i in range(MAX_LICZBA_PLIKOW)]
    result = wizard._pliki_w_limicie(pliki)
    assert result == pliki
    assert not calls, "5 poprawnych plików nie może alarmować rollbara"


# --------------------------------------------------------------------------
# 3. Krok 2 OGRANICZONY, 6 plików → krok nieważny, NIC nie utrwalone
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_krok2_szesc_plikow_krok_niewazny_nic_nie_utrwalone(
    webtest_app, uczelnia, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    resp = _post_step2_pliki(webtest_app, page, ile_plikow=6)
    # Krok nieważny (MultipleFileField.clean odrzuca > 5) → re-render kroku 2.
    assert resp.status_code == 200
    assert b"2-tytul_oryginalny" in resp.content
    # process_step_files nie odpalił (form invalid) → nic w tmp ani w trwałym.
    assert _list_files(_tmp_dir(str(tmp_path))) == []
    assert _list_files(_perm_dir(str(tmp_path))) == []


# --------------------------------------------------------------------------
# 4. Krok 2, 5 plików → utrwalone w zglos_publikacje_tmp/, NIE w zglos_publikacje/
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_krok2_piec_plikow_utrwalone_tylko_w_tmp(
    webtest_app, uczelnia, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    resp = _post_step2_pliki(webtest_app, page, ile_plikow=5)
    assert resp.status_code == 200
    assert b"autor" in resp.content.lower()  # przeszliśmy na krok 3
    assert len(_list_files(_tmp_dir(str(tmp_path)))) == 5
    # Trwały katalog nie powstaje przed done().
    assert _list_files(_perm_dir(str(tmp_path))) == []


# --------------------------------------------------------------------------
# 5. Ważny krok != 2 z doczepionymi plikami → NIC nie utrwalone (review #1).
#    Parametryzacja po krokach 0/1/3/4 — każdy to ścieżka `return {}`.
# --------------------------------------------------------------------------
def _reach_step(webtest_app, step, autor=None, jednostka=None):
    page = webtest_app.get(_url())  # krok 0
    if step == "0":
        return page
    page.forms[0]["0-rodzaj"] = "ARTYKUL"
    page = page.forms[0].submit()  # krok 1
    if step == "1":
        return page
    page.forms[0]["1-forma_dostepu"] = "OTWARTY"
    page = page.forms[0].submit()  # krok 2 (OTWARTY — bez pola pliki)
    page.forms[0]["2-tytul_oryginalny"] = "Test"
    page.forms[0]["2-rok"] = "2020"
    page.forms[0]["2-email"] = "test@test.pl"
    page.forms[0]["2-strona_www"] = "https://example.com/"
    page = page.forms[0].submit()  # krok 3
    if step == "3":
        return page
    page.forms[0]["3-0-autor"].force_value(autor.pk)
    page.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    return page.forms[0].submit()  # krok 4 (ARTYKUL wymaga opłat)


def _post_krok_z_bogus_plikiem(webtest_app, page, overrides):
    fields = [(n, v) for n, v in page.forms[0].submit_fields() if n not in overrides]
    fields.extend(overrides.items())
    upload_files = [("attack", "evil.pdf", _pdf_bytes())]
    return webtest_app.post(_url(), params=fields, upload_files=upload_files)


@pytest.mark.django_db
@pytest.mark.parametrize("step", ["0", "1", "3", "4"])
def test_wazny_krok_z_doczepionymi_plikami_nic_nie_utrwala(
    step,
    webtest_app,
    uczelnia,
    settings,
    tmp_path,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _reach_step(
        webtest_app, step, autor=autor_jan_kowalski, jednostka=aktualna_jednostka
    )
    overrides = {
        "0": {"0-rodzaj": "ARTYKUL"},
        "1": {"1-forma_dostepu": "OTWARTY"},
        "3": {
            "3-0-autor": str(autor_jan_kowalski.pk),
            "3-0-jednostka": str(aktualna_jednostka.pk),
        },
        "4": {"4-opl_pub_cost_free": "true"},
    }[step]
    resp = _post_krok_z_bogus_plikiem(webtest_app, page, overrides)
    # Krok MUSI być ważny — inaczej formtools nie wywoła process_step_files
    # (bronionej ścieżki `return {}`) i test przechodziłby PUSTO (L1).
    # Dowodzimy awansu na kolejny krok / ukończenia wizardu.
    if step == "4":
        assert Zgloszenie_Publikacji.objects.count() == 1  # wizard ukończony
    else:
        marker = {
            "0": b"1-forma_dostepu",
            "1": b"2-tytul_oryginalny",
            "3": b"4-opl_pub_cost_free",
        }[step]
        assert resp.status_code == 200
        assert marker in resp.content
    # Doczepiony plik nie został utrwalony nigdzie.
    assert _list_files(_tmp_dir(str(tmp_path))) == []
    assert _list_files(_perm_dir(str(tmp_path))) == []


# --------------------------------------------------------------------------
# 5b. Happy-path OGRANICZONY end-to-end (kluczowy regression-guard).
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_ograniczony_happy_path_tworzy_zalaczniki(
    webtest_app,
    uczelnia,
    settings,
    tmp_path,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    page2 = _post_step2_pliki(webtest_app, page, ile_plikow=2)  # → krok 3
    page2.forms[0]["3-0-autor"].force_value(autor_jan_kowalski.pk)
    page2.forms[0]["3-0-jednostka"].force_value(aktualna_jednostka.pk)
    page3 = page2.forms[0].submit()  # → krok 4
    page3.forms[0]["4-opl_pub_cost_free"] = "true"
    with django_capture_on_commit_callbacks(execute=True):
        result = page3.forms[0].submit().maybe_follow()

    assert (
        b"powiadomiony" in result.content or b"zostanie zaakceptowane" in result.content
    )
    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.zalaczniki.count() == 2
    # tmp wyczyszczone po przeniesieniu do trwałego storage.
    assert _list_files(_tmp_dir(str(tmp_path))) == []
    # Pliki trwałe lądują w zglos_publikacje/ (NIE w tmp).
    assert len(_list_files(_perm_dir(str(tmp_path)))) == 2
    for zal in zp.zalaczniki.all():
        assert zal.plik.name.startswith("protected/zglos_publikacje/")
        assert os.path.exists(os.path.join(str(tmp_path), zal.plik.name))


# --------------------------------------------------------------------------
# 6. Krok 2 OTWARTY (bez pola pliki) z doczepionym 2-pliki → NIC nie utrwalone.
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_krok2_otwarty_z_doczepionymi_plikami_nic_nie_utrwalone(
    webtest_app, uczelnia, settings, tmp_path
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OTWARTY")
    resp = _post_step2_pliki(webtest_app, page, ile_plikow=3)
    assert resp.status_code == 200
    assert b"autor" in resp.content.lower()  # krok 2 OTWARTY ważny → krok 3
    assert _list_files(_tmp_dir(str(tmp_path))) == []
    assert _list_files(_perm_dir(str(tmp_path))) == []


# --------------------------------------------------------------------------
# 6b. OGRANICZONY z plikami → powrót na krok 1 → OTWARTY → done bez załączników.
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_ograniczony_zmiana_na_otwarty_czysci_pliki(
    webtest_app,
    uczelnia,
    settings,
    tmp_path,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    page2 = _post_step2_pliki(webtest_app, page, ile_plikow=2)  # → krok 3
    assert len(_list_files(_tmp_dir(str(tmp_path)))) == 2

    # Powrót na krok 1 i zmiana formy dostępu na OTWARTY.
    back = _goto_step(webtest_app, page2, "1")
    back.forms[0]["1-forma_dostepu"] = "OTWARTY"
    page_otw = back.forms[0].submit()  # → krok 2 (OTWARTY)

    page_otw.forms[0]["2-tytul_oryginalny"] = "Test"
    page_otw.forms[0]["2-rok"] = "2020"
    page_otw.forms[0]["2-email"] = "test@test.pl"
    page_otw.forms[0]["2-strona_www"] = "https://example.com/"
    page3 = page_otw.forms[0].submit()  # → krok 3; process_step_files czyści tmp
    assert _list_files(_tmp_dir(str(tmp_path))) == []

    page3.forms[0]["3-0-autor"].force_value(autor_jan_kowalski.pk)
    page3.forms[0]["3-0-jednostka"].force_value(aktualna_jednostka.pk)
    page4 = page3.forms[0].submit()  # → krok 4
    page4.forms[0]["4-opl_pub_cost_free"] = "true"
    with django_capture_on_commit_callbacks(execute=True):
        page4.forms[0].submit().maybe_follow()

    zp = Zgloszenie_Publikacji.objects.order_by("-pk").first()
    assert zp is not None
    assert zp.forma_dostepu == Zgloszenie_Publikacji.FormyDostepu.OTWARTY
    assert zp.zalaczniki.count() == 0


# --------------------------------------------------------------------------
# 7. Late-completion: tmp-plik usunięty przed done() → brak 500, reset na krok 2.
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_late_completion_wygasle_pliki_reset_na_krok2(
    webtest_app,
    uczelnia,
    settings,
    tmp_path,
    typy_odpowiedzialnosci,
    autor_jan_kowalski,
    aktualna_jednostka,
):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    page2 = _post_step2_pliki(webtest_app, page, ile_plikow=2)  # → krok 3
    page2.forms[0]["3-0-autor"].force_value(autor_jan_kowalski.pk)
    page2.forms[0]["3-0-jednostka"].force_value(aktualna_jednostka.pk)
    page3 = page2.forms[0].submit()  # → krok 4

    # Symuluj wygaśnięcie tmp: skasuj pliki z dysku PRZED finalnym submitem.
    tmp = _tmp_dir(str(tmp_path))
    for f in _list_files(tmp):
        os.remove(os.path.join(tmp, f))

    page3.forms[0]["4-opl_pub_cost_free"] = "true"
    resp = page3.forms[0].submit()  # render_done → reset na krok 2, brak 500

    assert resp.status_code == 200
    assert b"2-tytul_oryginalny" in resp.content  # z powrotem na kroku 2
    assert "wygasły".encode() in resp.content  # komunikat warning
    assert Zgloszenie_Publikacji.objects.count() == 0  # done() nie wykonane


# --------------------------------------------------------------------------
# 7b. B3 — GET na URL wizardu czyści tmp z dysku.
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_get_na_wizard_czysci_tmp(webtest_app, uczelnia, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    page = _do_kroku2(webtest_app, forma="OGRANICZONY")
    _post_step2_pliki(webtest_app, page, ile_plikow=2)  # → krok 3, tmp ma 2 pliki
    assert len(_list_files(_tmp_dir(str(tmp_path)))) == 2

    # GET restartuje kreator; B3 czyści tmp PRZED storage.reset().
    webtest_app.get(_url())
    assert _list_files(_tmp_dir(str(tmp_path))) == []
