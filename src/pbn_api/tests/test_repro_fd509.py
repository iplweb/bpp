"""FD#509: praca trafiała do PBN bez oświadczenia autora, a nikt o tym nie wiedział.

Autor afiliujący, z przypiętą dyscypliną, ale bez odpowiednika w PBN i bez
ORCID: adapter oświadczeń po cichu zwracał ``None`` i praca szła do PBN bez
tego oświadczenia (a gdy wypadły wszystkie — ścieżką repozytoryjną, całkiem
bez oświadczeń). Teraz wysyłka takiej pracy jest zatrzymywana wyjątkiem
``AutorBezIdentyfikatoraPBN`` z listą autorów, a nic nie idzie do PBN.

Strażnicy: autor z samym ORCID (oświadczenie po ORCID), autor z odpowiednikiem
w PBN, praca bez przypiętych dyscyplin (``StatementsMissing`` / ścieżka
repozytoryjna) — bez zmian.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.urls import reverse
from model_bakery import baker
from pbn_client.const import (
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_GET_PUBLICATION_BY_ID_URL,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)

from bpp.admin.helpers.pbn_api.gui import sprobuj_wyslac_do_pbn_gui
from bpp.models import Autor_Dyscyplina
from fixtures.pbn_api import (
    MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA,
    MOCK_RETURNED_MONGODB_DATA,
    pbn_pageable_json,
)
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.adapters.wydawnictwo_autor import (
    WydawnictwoAutorToStatementPBNAdapter,
    ostrzezenie_o_pominietych_oswiadczeniach,
    powiazania_bez_identyfikatora_osoby,
    powiazania_do_oswiadczenia,
)
from pbn_api.exceptions import (
    AutorBezIdentyfikatoraPBN,
    StatementsMissing,
    WillNotExportError,
)
from pbn_api.models import Scientist
from pbn_api.tests.utils import middleware

ORCID = "0000-0002-1825-0097"


def _ustaw_autora(praca, pbn_uid, orcid):
    """Jedyny autor pracy: afiliuje, dyscyplina przypięta, jednostka własna.

    Zwraca powiązanie autor–rekord. ``pbn_uid``/``orcid`` — czy autor ma
    odpowiednik w PBN / ORCID.
    """
    wa = praca.autorzy_set.get()
    wa.afiliuje = True
    wa.przypieta = True
    wa.save()

    jednostka = wa.jednostka
    jednostka.skupia_pracownikow = True
    jednostka.save()

    autor = wa.autor
    autor.pbn_uid = baker.make(Scientist) if pbn_uid else None
    autor.orcid = ORCID if orcid else None
    autor.save()

    return praca.autorzy_set.get()


def _pbn_przyjmie_wszystko(pbn_client):
    """Odpowiedzi PBN dla obu ścieżek wysyłki — żeby test mógł wykryć, że
    praca POSZŁA, a nie wywracał się na braku zamockowanego adresu."""
    rv = pbn_client.transport.return_values
    rv[PBN_POST_PUBLICATIONS_URL] = {"objectId": "123"}
    rv[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [{"id": "123"}]
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id="123")] = MOCK_RETURNED_MONGODB_DATA
    rv[PBN_GET_PUBLICATION_BY_ID_URL.format(id=456)] = MOCK_RETURNED_MONGODB_DATA
    rv[PBN_GET_INSTITUTION_PUBLICATIONS_V2 + "?publicationId=123&size=10"] = (
        pbn_pageable_json(MOCK_RETURNED_INSTITUTION_PUBLICATION_V2_DATA)
    )
    rv[PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=123&size=5120"] = (
        pbn_pageable_json([])
    )
    rv[PBN_POST_INSTITUTION_STATEMENTS_URL] = {"status": "ok"}


def _wyslane_do_pbn(pbn_client):
    """Adresy, pod które faktycznie poszedł POST."""
    return set(pbn_client.transport.input_values)


def _wyslij_z_formularza(rf, praca, pbn_client):
    req = rf.get("/")
    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(req, praca, pbn_client=pbn_client)
    return [(m.level_tag, str(m.message)) for m in get_messages(req)]


# --------------------------------------------------------------------------
# Adapter oświadczeń: (a) ORCID bez pbn_uid, (b) brak obu, (c) jest pbn_uid
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd509_adapter_brak_pbn_uid_jest_orcid_idzie_po_orcid(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=True)

    oswiadczenie = WydawnictwoAutorToStatementPBNAdapter(wa).pbn_get_json()

    assert oswiadczenie["personOrcidId"] == ORCID
    assert "personObjectId" not in oswiadczenie
    assert not powiazania_bez_identyfikatora_osoby(praca.autorzy_set).exists()


@pytest.mark.django_db
def test_fd509_adapter_brak_pbn_uid_i_orcid_blokada(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)

    # Oświadczenia nie da się zbudować...
    assert WydawnictwoAutorToStatementPBNAdapter(wa).pbn_get_json() is None
    # ...i dokładnie ten autor jest wskazany jako powód blokady.
    assert list(powiazania_bez_identyfikatora_osoby(praca.autorzy_set)) == [wa]

    with pytest.raises(AutorBezIdentyfikatoraPBN) as excinfo:
        WydawnictwoPBNAdapter(praca).pbn_get_json()

    assert excinfo.value.autorzy == [wa]
    assert str(wa.autor) in str(excinfo.value)
    # Kolejka eksportu wyłuskuje komunikat z jednej linii tracebacku i ucina
    # dłuższe niż 512 znaków — komunikat musi się w tym mieścić.
    assert "\n" not in str(excinfo.value)
    assert len(str(excinfo.value)) < 512


@pytest.mark.django_db
def test_fd509_adapter_jest_pbn_uid(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=True, orcid=False)

    oswiadczenie = WydawnictwoAutorToStatementPBNAdapter(wa).pbn_get_json()

    assert oswiadczenie["personObjectId"] == wa.autor.pbn_uid_id
    assert not powiazania_bez_identyfikatora_osoby(praca.autorzy_set).exists()
    assert WydawnictwoPBNAdapter(praca).pbn_get_json()["statements"]


@pytest.mark.django_db
def test_fd509_pusty_orcid_to_brak_orcid(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    type(wa.autor).objects.filter(pk=wa.autor_id).update(orcid="")

    assert powiazania_bez_identyfikatora_osoby(praca.autorzy_set).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pole,wartosc",
    [("afiliuje", False), ("przypieta", False), ("dyscyplina_naukowa", None)],
)
def test_fd509_autor_nieoswiadczany_nie_blokuje(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia, pole, wartosc
):
    """Brak afiliacji / odpięta dyscyplina / brak dyscypliny: takiej osoby
    i tak się nie oświadcza, więc brak identyfikatorów niczego nie blokuje —
    to jest droga wyjścia opisana w komunikacie dla redaktora."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    setattr(wa, pole, wartosc)
    wa.save()

    assert not powiazania_bez_identyfikatora_osoby(praca.autorzy_set).exists()

    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    js = WydawnictwoPBNAdapter(praca, uczelnia=pbn_uczelnia).pbn_get_json()
    assert "statements" not in js


@pytest.mark.django_db
def test_fd509_jednostka_nie_skupia_pracownikow_nie_blokuje(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    jednostka = wa.jednostka
    jednostka.skupia_pracownikow = False
    jednostka.save()

    assert not powiazania_bez_identyfikatora_osoby(praca.autorzy_set).exists()


# --------------------------------------------------------------------------
# Odtworzenie: wysyłka z formularza rekordu
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("bez_oswiadczen", [True, False])
def test_fd509_autor_bez_pbn_uid_i_orcid_nic_nie_wyslano_czytelny_blad(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_client,
    pbn_uczelnia,
    rf,
    bez_oswiadczen,
):
    """NIE przechodzi na starym kodzie.

    Stary kod przy ``pbn_wysylaj_bez_oswiadczen=True`` wysyłał pracę ścieżką
    repozytoryjną — bez oświadczenia — i raportował sukces. Przy ``False``
    odmawiał, ale komunikatem „bez zadeklarowanych oświadczeń", który nie
    mówił, że chodzi o identyfikator autora.
    """
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = bez_oswiadczen
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    assert _wyslane_do_pbn(pbn_client) == set(), "nic nie może pójść do PBN"
    praca.refresh_from_db()
    assert praca.pbn_uid_id is None

    bledy = [tresc for poziom, tresc in komunikaty if "error" in poziom]
    assert len(bledy) == 1, komunikaty
    blad = bledy[0]
    assert "NIE został wysłany do PBN" in blad
    assert praca.tytul_oryginalny in blad
    assert str(wa.autor) in blad
    assert reverse("admin:bpp_autor_change", args=(wa.autor_id,)) in blad
    assert "Odpowiednik w PBN" in blad
    assert "ORCID" in blad
    assert "odepnij jej dyscyplinę" in blad
    assert not any("zaktualizowane" in tresc for _, tresc in komunikaty)


@pytest.mark.django_db
def test_fd509_jeden_z_dwoch_autorow_bez_identyfikatora_blokuje_cala_prace(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_client,
    pbn_uczelnia,
    rf,
    autor_jan_kowalski,
    dyscyplina1,
):
    """Sedno zgłoszenia: drugi autor ma komplet danych, więc stary kod wysyłał
    pracę z JEDNYM oświadczeniem zamiast dwóch — bez słowa. NIE przechodzi na
    starym kodzie."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    kompletny = _ustaw_autora(praca, pbn_uid=True, orcid=False)
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=praca.rok, dyscyplina_naukowa=dyscyplina1
    )
    praca.dodaj_autora(
        autor_jan_kowalski, kompletny.jednostka, dyscyplina_naukowa=dyscyplina1
    )
    type(autor_jan_kowalski).objects.filter(pk=autor_jan_kowalski.pk).update(
        pbn_uid=None, orcid=None
    )
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    assert _wyslane_do_pbn(pbn_client) == set()
    bledy = [tresc for poziom, tresc in komunikaty if "error" in poziom]
    assert len(bledy) == 1, komunikaty
    assert str(autor_jan_kowalski) in bledy[0]
    assert reverse("admin:bpp_autor_change", args=(kompletny.autor_id,)) not in bledy[0]


@pytest.mark.django_db
def test_fd509_po_uzupelnieniu_orcid_wysylka_przechodzi(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia, rf
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    _pbn_przyjmie_wszystko(pbn_client)

    _wyslij_z_formularza(rf, praca, pbn_client)
    assert _wyslane_do_pbn(pbn_client) == set()

    autor = wa.autor
    autor.orcid = ORCID
    autor.save()

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    assert PBN_POST_PUBLICATIONS_URL in _wyslane_do_pbn(pbn_client)
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty), komunikaty


# --------------------------------------------------------------------------
# Strażnicy: zachowanie, które ma się NIE zmienić
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd509_straznik_autor_z_orcid_wysylany_bez_falszywego_ostrzezenia(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia, rf
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=True)
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    wyslane = pbn_client.transport.input_values[PBN_POST_PUBLICATIONS_URL]["body"]
    assert [s["personOrcidId"] for s in wyslane["statements"]] == [ORCID]
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty), komunikaty
    # Dawne ostrzeżenie twierdziło, że dyscyplina „nie zostanie oświadczona",
    # choć oświadczenie szło po ORCID.
    assert not any("nie zostanie oświadczona" in t for _, t in komunikaty)
    assert not any("error" in p or "warning" in p for p, _ in komunikaty), komunikaty
    informacje = [t for p, t in komunikaty if "info" in p]
    assert any("z identyfikatorem ORCID" in t and ORCID in t for t in informacje)


@pytest.mark.django_db
def test_fd509_straznik_autor_z_pbn_uid_wysylany_jak_dotad(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia, rf
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=True, orcid=False)
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    wyslane = pbn_client.transport.input_values[PBN_POST_PUBLICATIONS_URL]["body"]
    assert [s["personObjectId"] for s in wyslane["statements"]] == [wa.autor.pbn_uid_id]
    assert [p for p, _ in komunikaty if "error" in p or "warning" in p] == []
    assert not any("ORCID" in t for _, t in komunikaty)


@pytest.mark.django_db
def test_fd509_straznik_statements_missing_jak_dotad(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia
):
    """Nikt nie ma przypiętej dyscypliny, uczelnia nie wysyła prac bez
    oświadczeń → dalej ``StatementsMissing``, nie nowy wyjątek."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    wa.przypieta = False
    wa.save()
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = False
    pbn_uczelnia.save()

    with pytest.raises(StatementsMissing):
        WydawnictwoPBNAdapter(praca, uczelnia=pbn_uczelnia).pbn_get_json()


@pytest.mark.django_db
def test_fd509_straznik_tryb_bez_oswiadczen_praca_bez_dyscyplin_idzie_repozytorium(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia, rf
):
    """``pbn_wysylaj_bez_oswiadczen``: praca, w której oświadczeń świadomie
    nie ma (dyscyplina odpięta), idzie ścieżką repozytoryjną mimo autora bez
    identyfikatorów — blokada tego trybu nie psuje."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    wa.przypieta = False
    wa.save()
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    assert _wyslane_do_pbn(pbn_client) == {PBN_POST_PUBLICATION_NO_STATEMENTS_URL}
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty), komunikaty


@pytest.mark.django_db
def test_fd509_wyjatek_jest_will_not_export(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    """Ścieżki łapiące ``WillNotExportError`` (integrator, kolejka, importer)
    obsługują nowy wyjątek bez zmian — to „popraw dane", nie awaria."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=False)

    with pytest.raises(WillNotExportError):
        WydawnictwoPBNAdapter(praca).pbn_get_json()


# --------------------------------------------------------------------------
# Pozostałe ścieżki wysyłki
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd509_integrator_upload_bez_wysylki_i_bez_monitoringu(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia
):
    from pbn_integrator.utils import synchronization

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    with patch.object(synchronization, "capture_exception") as capture:
        synchronization._handle_no_pbn_uid(pbn_client, praca, upload_publication=True)

    assert _wyslane_do_pbn(pbn_client) == set()
    capture.assert_not_called()


@pytest.mark.django_db
def test_fd509_integrator_synchronizacja_bez_wysylki(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia
):
    from pbn_integrator.utils.synchronization import (
        _synchronizuj_pojedyncza_publikacje,
    )

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = True
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    _synchronizuj_pojedyncza_publikacje(pbn_client, praca)

    assert _wyslane_do_pbn(pbn_client) == set()


@pytest.mark.django_db
def test_fd509_masowa_wysylka_oswiadczen_nie_kasuje_i_nie_wysyla(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    """Wysyłka samych oświadczeń najpierw kasuje te z PBN — przy autorze bez
    identyfikatorów nie wolno jej nawet zacząć."""
    from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask
    from pbn_wysylka_oswiadczen.tasks import process_single_publication

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    klient = MagicMock()
    zadanie = baker.make(PbnWysylkaOswiadczenTask)

    status, wpis = process_single_publication(praca, klient, zadanie, PbnWysylkaLog)

    assert status == "error"
    assert str(wa.autor) in wpis.error_message
    assert klient.mock_calls == []


@pytest.mark.django_db
def test_fd509_komenda_wysylki_oswiadczen_nie_kasuje_i_nie_wysyla(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    from pbn_api.management.commands.pbn_wyslij_oswiadczenia_instytucji import (
        process_single_publication,
    )

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    klient = MagicMock()

    wynik = process_single_publication(praca, klient)

    assert wynik["success"] is False
    assert str(wa.autor) in wynik["error"]
    assert klient.mock_calls == []


# --------------------------------------------------------------------------
# Zestawienie dla administratora
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd509_komenda_zestawienie(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)

    out = StringIO()
    call_command("pbn_oswiadczenia_bez_identyfikatora", "--szczegoly", stdout=out)
    tekst = out.getvalue()

    assert "Prace z zatrzymaną wysyłką do PBN: 1; autorzy do uzupełnienia: 1." in tekst
    assert f"wydawnictwo_zwarte;{praca.pk};{praca.rok};" in tekst
    assert f"  {wa.autor_id};{wa.autor};1" in tekst

    # Filtr roku: poza zakresem nie ma nic.
    out = StringIO()
    call_command(
        "pbn_oswiadczenia_bez_identyfikatora", f"--rok-od={praca.rok + 1}", stdout=out
    )
    assert "Prace z zatrzymaną wysyłką do PBN: 0;" in out.getvalue()

    # Po uzupełnieniu ORCID autor znika z zestawienia.
    autor = wa.autor
    autor.orcid = ORCID
    autor.save()
    out = StringIO()
    call_command("pbn_oswiadczenia_bez_identyfikatora", stdout=out)
    assert "Prace z zatrzymaną wysyłką do PBN: 0;" in out.getvalue()


# --------------------------------------------------------------------------
# Ustawienie uczelni „Wysyłaj prace, gdy autor nie ma identyfikatora w PBN”
# --------------------------------------------------------------------------


def _dodaj_autora_bez_identyfikatorow(praca, autor, jednostka, dyscyplina):
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=praca.rok, dyscyplina_naukowa=dyscyplina
    )
    praca.dodaj_autora(autor, jednostka, dyscyplina_naukowa=dyscyplina)
    type(autor).objects.filter(pk=autor.pk).update(pbn_uid=None, orcid=None)


@pytest.mark.django_db
def test_fd509_opcja_domyslnie_wylaczona(pbn_uczelnia):
    assert pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora is False


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_wysyla_i_ostrzega_ile_oswiadczen(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_client,
    pbn_uczelnia,
    rf,
    autor_jan_kowalski,
    dyscyplina1,
):
    """Uczelnia świadomie pozwala wysyłać: praca idzie z JEDNYM oświadczeniem
    z dwóch, a redaktor dostaje ostrzeżenie z liczbami i pominiętym autorem."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    kompletny = _ustaw_autora(praca, pbn_uid=True, orcid=False)
    _dodaj_autora_bez_identyfikatorow(
        praca, autor_jan_kowalski, kompletny.jednostka, dyscyplina1
    )
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    wyslane = pbn_client.transport.input_values
    oswiadczenia = wyslane[PBN_POST_PUBLICATIONS_URL]["body"]["statements"]
    assert [s["personObjectId"] for s in oswiadczenia] == [kompletny.autor.pbn_uid_id]
    assert len(wyslane[PBN_POST_PUBLICATIONS_URL]["body"]["authors"]) == 2

    assert not [tresc for poziom, tresc in komunikaty if "error" in poziom]
    assert any("zaktualizowane" in tresc for _, tresc in komunikaty)
    ostrzezenia = [
        tresc
        for poziom, tresc in komunikaty
        if "warning" in poziom and "NIEPEŁNE" in tresc
    ]
    assert len(ostrzezenia) == 1, komunikaty
    ostrzezenie = ostrzezenia[0]
    assert "Z 2 autorów" in ostrzezenie
    assert "trafiło 1 oświadczeń" in ostrzezenie
    assert "pominięto 1" in ostrzezenie
    assert str(autor_jan_kowalski) in ostrzezenie
    assert reverse("admin:bpp_autor_change", args=(autor_jan_kowalski.pk,)) in (
        ostrzezenie
    )
    assert (
        reverse("admin:bpp_autor_change", args=(kompletny.autor_id,)) not in ostrzezenie
    )


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_komplet_identyfikatorow_bez_ostrzezenia(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_client, pbn_uczelnia, rf
):
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=True, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()
    _pbn_przyjmie_wszystko(pbn_client)

    komunikaty = _wyslij_z_formularza(rf, praca, pbn_client)

    assert PBN_POST_PUBLICATIONS_URL in _wyslane_do_pbn(pbn_client)
    assert not any("NIEPEŁNE" in tresc for _, tresc in komunikaty)


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_jedyny_autor_dalej_statements_missing(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia
):
    """Opcja nie zastępuje „Wysyłaj prace bez oświadczeń”: gdy wypadną WSZYSTKIE
    oświadczenia, artykuł/rozdział dalej nie idzie bez tamtej zgody."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.pbn_wysylaj_bez_oswiadczen = False
    pbn_uczelnia.save()

    adapter = WydawnictwoPBNAdapter(praca, uczelnia=pbn_uczelnia)
    if adapter.get_type() in (adapter.ARTICLE, adapter.CHAPTER):
        with pytest.raises(StatementsMissing):
            adapter.pbn_get_json()
    else:
        assert "statements" not in adapter.pbn_get_json()


@pytest.mark.django_db
def test_fd509_adapter_bez_uczelni_blokuje(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia
):
    """Adapter zbudowany bez uczelni nie wie o zgodzie — bezpiecznie blokuje."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()

    with pytest.raises(AutorBezIdentyfikatoraPBN):
        WydawnictwoPBNAdapter(praca).sprawdz_identyfikatory_autorow()


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_adapter_zostawia_slad_w_logu(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia, caplog
):
    """Drogi bez redaktora przy ekranie (integrator, komendy): ślad w logu."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()

    with caplog.at_level("WARNING", logger="pbn_api.adapters.wydawnictwo"):
        WydawnictwoPBNAdapter(
            praca, uczelnia=pbn_uczelnia
        ).sprawdz_identyfikatory_autorow()

    assert "z 1 autorów" in caplog.text
    assert "trafi 0 oświadczeń" in caplog.text
    assert str(wa.autor) in caplog.text


@pytest.mark.django_db
def test_fd509_ostrzezenie_liczy_tylko_autorow_do_oswiadczenia(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, autor_jan_kowalski, dyscyplina1
):
    """Mianownik to autorzy, którzy MAJĄ dostać oświadczenie — autor
    z odpiętą dyscypliną do niego nie wchodzi."""
    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    kompletny = _ustaw_autora(praca, pbn_uid=True, orcid=False)
    assert ostrzezenie_o_pominietych_oswiadczeniach(praca) is None

    _dodaj_autora_bez_identyfikatorow(
        praca, autor_jan_kowalski, kompletny.jednostka, dyscyplina1
    )
    assert powiazania_do_oswiadczenia(praca.autorzy_set).count() == 2
    tekst = ostrzezenie_o_pominietych_oswiadczeniach(praca)
    assert "z 2 autorów" in tekst
    assert "trafi 1 oświadczeń" in tekst
    assert str(autor_jan_kowalski) in tekst

    praca.autorzy_set.filter(autor=autor_jan_kowalski).update(przypieta=False)
    assert powiazania_do_oswiadczenia(praca.autorzy_set).count() == 1
    assert ostrzezenie_o_pominietych_oswiadczeniach(praca) is None


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_masowa_wysylka_oswiadczen_idzie_z_ostrzezeniem(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_uczelnia,
    autor_jan_kowalski,
    dyscyplina1,
):
    from pbn_wysylka_oswiadczen import tasks
    from pbn_wysylka_oswiadczen.models import PbnWysylkaLog, PbnWysylkaOswiadczenTask

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    kompletny = _ustaw_autora(praca, pbn_uid=True, orcid=False)
    _dodaj_autora_bez_identyfikatorow(
        praca, autor_jan_kowalski, kompletny.jednostka, dyscyplina1
    )
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()
    klient = MagicMock()
    klient.uczelnia = pbn_uczelnia
    klient.post_discipline_statements.return_value = {"status": "ok"}
    zadanie = baker.make(PbnWysylkaOswiadczenTask)
    dane = {"publicationUuid": "x", "statements": [{"personObjectId": "1"}]}

    with patch.object(
        tasks.WydawnictwoPBNAdapter, "pbn_get_api_statements", return_value=dane
    ):
        status, wpis = tasks.process_single_publication(
            praca, klient, zadanie, PbnWysylkaLog
        )

    assert status == "success"
    klient.post_discipline_statements.assert_called_once()
    assert wpis.error_message.startswith("UWAGA: ")
    assert "z 2 autorów" in wpis.error_message
    assert str(autor_jan_kowalski) in wpis.error_message


@pytest.mark.django_db
def test_fd509_opcja_wlaczona_komenda_wysylki_oswiadczen_idzie_z_ostrzezeniem(
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina, pbn_uczelnia
):
    from pbn_api.management.commands import pbn_wyslij_oswiadczenia_instytucji as cmd

    praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    wa = _ustaw_autora(praca, pbn_uid=False, orcid=False)
    pbn_uczelnia.pbn_wysylaj_bez_identyfikatora_autora = True
    pbn_uczelnia.save()
    klient = MagicMock()
    klient.uczelnia = pbn_uczelnia

    with patch.object(
        cmd.WydawnictwoPBNAdapter, "pbn_get_api_statements", return_value=None
    ):
        wynik = cmd.process_single_publication(praca, klient)

    assert wynik["error"] is None
    assert wynik["success"] is True
    assert str(wa.autor) in wynik["warning"]
