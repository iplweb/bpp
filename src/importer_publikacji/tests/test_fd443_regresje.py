"""FD#443 — regresje z adwersarialnej recenzji PR-a.

Każdy test w tym pliku pilnuje konkretnej naprawy, której poprzednia suita
NIE złapała. Grupy odpowiadają lukom z recenzji:

* **A** — dopasowanie po DOI wyłuskanym ze ``strona_www`` (pole ``doi`` jest
  produkcyjnie ZAWSZE puste: publiczny formularz go nie ma). Testy oparte na
  ``baker.make(doi=...)`` sprawdzały stan nieosiągalny produkcyjnie, więc
  przepuściły martwy kod.
* **B** — ścieżka jawna (``?zgloszenie=<pk>`` → ukryte pole ``FetchForm``)
  omijała walidację uczelni i statusów (gołe ``objects.filter(pk=...)``).
* **C** — zapis zwrotny rewaliduje status w chwili ZAPISU, nie w chwili
  związania, i kasuje ``kod_do_edycji``.
* **D** — lost update: pełne ``session.save()`` w tasku kasowało wiązanie
  dopisane w międzyczasie przez widok; ``update_fields`` musi zawierać
  ``modified``, inaczej watchdog uzna żywą sesję za martwą.
* **E** — wyjątek w zapisie zwrotnym nie może wywrócić importu (sesja zostaje
  ``COMPLETED``, inaczej „Ponów" tworzy drugi rekord tej samej pracy).
* **F** — charakteryzacja świadomych ograniczeń zawężania do uczelni.
* **G** — renderowanie banera i strony „Gotowe" (wcześniej zero pokrycia).
"""

import datetime
import logging
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from importer_publikacji.models import ImportSession
from importer_publikacji.tasks import create_publication_task, fetch_session_task
from importer_publikacji.zgloszenia import (
    kandydaci_dla_sesji,
    oznacz_jako_zaimportowane,
    zgloszenie_dozwolone,
    zwiaz_automatycznie,
)
from zglos_publikacje.models import Zgloszenie_Publikacji

DOI = "10.1234/fd443.regresja"
TYTUL = "Praca zgłoszona przez publiczny formularz zgłoszeniowy"

STATUSY = Zgloszenie_Publikacji.Statusy


# --------------------------------------------------------------------------
# Pomocnicze
# --------------------------------------------------------------------------


def _zgl(doi=None, strona_www="", status=STATUSY.NOWY, tytul=TYTUL, **kwargs):
    """Zgłoszenie publikacji.

    Domyślnie z ``doi=None`` — dokładnie tak, jak wygląda zgłoszenie złożone
    przez publiczny formularz (ten pola ``doi`` w ogóle nie ma, a kolumna jest
    ``null=True``, więc produkcyjnie siedzi tam NULL, nie pusty string).
    """
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        doi=doi,
        strona_www=strona_www,
        tytul_oryginalny=tytul,
        status=status,
        rok=2024,
        rodzaj_zglaszanej_publikacji=1,
        **kwargs,
    )


def _zpa(zgloszenie, jednostka):
    """Autor zgłoszenia — jedyny nośnik atrybucji zgłoszenia do uczelni."""
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji_Autor",
        rekord=zgloszenie,
        autor=baker.make("bpp.Autor"),
        jednostka=jednostka,
        rok=2024,
    )


def _sesja(user, doi=DOI, uczelnia=None, **kwargs):
    return ImportSession.objects.create(
        created_by=user,
        uczelnia=uczelnia,
        provider_name="CrossRef",
        identifier=doi or "brak-doi",
        raw_data={},
        normalized_data={
            "title": TYTUL,
            "doi": doi,
            "year": 2024,
            "authors": [],
        },
        **kwargs,
    )


def _rekord():
    return baker.make(Wydawnictwo_Ciagle, rok=2024)


def _jednostka_obcej_uczelni(skrot):
    """Jednostka nowo utworzonej uczelni (≠ ta spod hosta ``testserver``)."""
    from bpp.models import Jednostka, Uczelnia, Wydzial
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    site = Site.objects.create(
        domain=f"{skrot.lower()}.example.com", name=f"Site {skrot}"
    )
    uczelnia = Uczelnia.objects.create(
        nazwa=f"Uczelnia {skrot}", skrot=skrot, site=site
    )
    wydzial = Wydzial.objects.create(
        uczelnia=uczelnia, skrot=f"W-{skrot}", nazwa=f"Wydział {skrot}"
    )
    wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
    return Jednostka.objects.create(
        uczelnia=uczelnia,
        parent=wezel,
        skrot=f"J-{skrot}",
        nazwa=f"Jednostka {skrot}",
    )


@pytest.fixture
def jednostka_obca(db, uczelnia):
    """Jednostka DRUGIEJ uczelni — włącza zawężanie (>1 uczelnia)."""
    return _jednostka_obcej_uczelni("OBC")


def _post_fetch(client, **extra):
    """POST na ``FetchView`` z zamockowanym providerem i taskiem Celery."""
    dane = {"provider": "CrossRef", "identifier": "10.1234/x"}
    dane.update(extra)

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        from importer_publikacji.providers import InputMode

        mock_provider.return_value.input_mode = InputMode.IDENTIFIER
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"
        mock_task.delay.return_value.id = "task-uuid"

        return client.post(reverse("importer_publikacji:fetch"), dane)


def _uruchom_create_task(session, rekord=None):
    rekord = rekord or _rekord()
    with patch("importer_publikacji.tasks._create_publication") as mock_create:
        mock_create.return_value = rekord
        create_publication_task.apply(
            args=[session.pk, session.created_by_id, False]
        ).get()
    return rekord


def _fake_fetch_result(doi=DOI):
    """Minimalny wynik dostawcy — komplet atrybutów czytanych przez task."""
    return MagicMock(
        raw_data={"k": "v"},
        title=TYTUL,
        doi=doi,
        year=2024,
        authors=[],
        source_title="",
        source_abbreviation="",
        issn="",
        e_issn="",
        isbn="",
        e_isbn="",
        publisher="",
        publication_type="article",
        language="en",
        abstract="",
        volume="",
        issue="",
        pages="",
        url="",
        license_url="",
        keywords=[],
        extra={},
        patent_number=None,
        patent_grant_number=None,
        filing_date=None,
        grant_date=None,
        patent_type=None,
        patent_holder=None,
        jurisdiction=None,
    )


# ==========================================================================
# A. Dopasowanie po DOI wyłuskanym ze ``strona_www``
# ==========================================================================


@pytest.mark.django_db
def test_kandydat_gdy_doi_jest_wylacznie_w_strona_www(importer_user):
    """NAJWAŻNIEJSZY test grupy A: pole ``doi`` puste, DOI w ``strona_www``.

    Produkcyjnie to JEDYNY osiągalny kształt zgłoszenia — publiczny
    formularz nie ma pola ``doi``, a help-text każe wkleić DOI właśnie do
    ``strona_www``. Dopóki match szedł po ``doi__iexact``, ścieżki B i C
    były martwym kodem.
    """
    session = _sesja(importer_user)
    zgl = _zgl(strona_www=f"https://dx.doi.org/{DOI}")

    assert zgl.doi is None
    assert list(kandydaci_dla_sesji(session)) == [zgl]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "strona_www",
    [
        f"https://doi.org/{DOI}",
        f"https://dx.doi.org/{DOI}",
        f"http://dx.doi.org/{DOI}",
        f"http://doi.org/{DOI}",
        f"https://doi.org/{DOI}?utm_source=newsletter&rel=cite-as",
        f"https://wydawca.example.com/artykuly/{DOI}",
        f"https://doi.org/{DOI.upper()}",
    ],
)
def test_kandydat_dla_roznych_form_zapisu_doi_w_strona_www(importer_user, strona_www):
    session = _sesja(importer_user)
    zgl = _zgl(strona_www=strona_www)

    assert list(kandydaci_dla_sesji(session)) == [zgl], strona_www


@pytest.mark.django_db
def test_doi_bedace_prefiksem_innego_nie_daje_trafienia(importer_user):
    """Prefiltr SQL to ``icontains`` — precyzję daje dopiero Python.

    Zgłoszenie o DOI ``10.1234/x.suffix`` przechodzi przez ``LIKE
    '%10.1234/x%'``, więc bez dokładnego porównania w Pythonie stałoby się
    kandydatem sesji o DOI ``10.1234/x`` i zostałoby cicho oznaczone jako
    zaimportowane.
    """
    session = _sesja(importer_user)
    dluzsze = _zgl(strona_www=f"https://doi.org/{DOI}.suffix")

    # Kontrola negatywna prefiltru: SQL SAM w sobie by to wpuścił.
    assert Zgloszenie_Publikacji.objects.filter(strona_www__icontains=DOI).exists()

    assert list(kandydaci_dla_sesji(session)) == []
    assert zwiaz_automatycznie(session) is False

    session.refresh_from_db()
    assert session.zgloszenie_id is None
    dluzsze.refresh_from_db()
    assert dluzsze.status == STATUSY.NOWY


@pytest.mark.django_db
def test_doi_sesji_bedace_dluzsze_od_zgloszenia_nie_daje_trafienia(importer_user):
    """Symetrycznie: DOI sesji dłuższe niż DOI zgłoszenia też nie pasuje."""
    session = _sesja(importer_user, doi=f"{DOI}.suffix")
    _zgl(strona_www=f"https://doi.org/{DOI}")

    assert list(kandydaci_dla_sesji(session)) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "strona_www",
    [
        "https://example.com/papers/123",
        "https://repozytorium.example.com/handle/11089/12345",
        "",
    ],
)
def test_strona_www_niebedaca_doi_nie_daje_trafienia(importer_user, strona_www):
    session = _sesja(importer_user)
    _zgl(strona_www=strona_www)

    assert list(kandydaci_dla_sesji(session)) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "wartosc_pola_doi",
    [
        DOI,
        DOI.upper(),
        f"https://doi.org/{DOI}",
        f"http://dx.doi.org/{DOI}",
        f"  {DOI}  ",
    ],
)
def test_doi_w_polu_doi_takze_trafia(importer_user, wartosc_pola_doi):
    """Ścieżka historyczna (dane wgrane skryptem/migracją) nadal działa."""
    session = _sesja(importer_user)
    zgl = _zgl(doi=wartosc_pola_doi)

    assert list(kandydaci_dla_sesji(session)) == [zgl], wartosc_pola_doi


@pytest.mark.django_db
def test_auto_wiazanie_na_zgloszeniu_z_doi_tylko_w_strona_www(importer_user):
    """Ścieżka B end-to-end na produkcyjnym kształcie zgłoszenia."""
    session = _sesja(importer_user)
    zgl = _zgl(strona_www=f"https://dx.doi.org/{DOI}")

    assert zwiaz_automatycznie(session) is True

    session.refresh_from_db()
    assert session.zgloszenie_id == zgl.pk


@pytest.mark.django_db
def test_zgloszenie_z_publicznego_formularza_jest_kandydatem(importer_user, uczelnia):
    """Zgłoszenie utworzone REALNĄ ścieżką (publiczny formularz), nie bakerem.

    Formularz kroku „dane o publikacji" w ogóle nie ma pola ``doi`` — DOI
    zgłaszający wkleja do ``strona_www``. Ten test pilnuje, żeby suita nie
    zieleniła się wyłącznie na stanie nieosiągalnym produkcyjnie.
    """
    from zglos_publikacje.forms import Zgloszenie_Publikacji_DaneForm

    form = Zgloszenie_Publikacji_DaneForm(
        data={
            "tytul_oryginalny": TYTUL,
            "rok": 2024,
            "email": "zglaszajacy@example.com",
            "strona_www": f"https://dx.doi.org/{DOI}",
            "zgoda_na_publikacje_pelnego_tekstu": "True",
        },
        rodzaj="ARTYKUL",
        forma_dostepu="OTWARTY",
        uczelnia=uczelnia,
    )

    assert "doi" not in form.fields, "publiczny formularz nie ma pola DOI"
    assert form.is_valid(), form.errors

    # Tak samo jak ``Zgloszenie_PublikacjiWizard.done()``: rodzaj i status
    # dokłada widok, reszta idzie z formularza.
    zgl = form.save(commit=False)
    zgl.status = STATUSY.NOWY
    zgl.rodzaj_zglaszanej_publikacji = 1
    zgl.save()

    z_bazy = Zgloszenie_Publikacji.objects.get(pk=zgl.pk)
    assert z_bazy.doi is None, "produkcyjnie kolumna DOI zostaje pusta"
    assert DOI in z_bazy.strona_www

    session = _sesja(importer_user, uczelnia=uczelnia)
    assert list(kandydaci_dla_sesji(session)) == [z_bazy]


# ==========================================================================
# B. Ścieżka jawna (``?zgloszenie=``) przechodzi przez pełną walidację
# ==========================================================================


@pytest.mark.django_db
def test_fetch_jawne_zgloszenie_obcej_uczelni_bez_wiazania(
    importer_client, uczelnia, jednostka_obca
):
    """Dziura bezpieczeństwa: ukryte pole to input pod kontrolą klienta."""
    obce = _zgl(strona_www=f"https://doi.org/{DOI}")
    _zpa(obce, jednostka=jednostka_obca)

    response = _post_fetch(importer_client, zgloszenie=obce.pk)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_fetch_jawne_zgloszenie_wlasnej_uczelni_wiaze(
    importer_client, uczelnia, jednostka, jednostka_obca
):
    """Kontrola pozytywna: przy dwóch uczelniach SWOJE zgłoszenie przechodzi."""
    moje = _zgl(strona_www=f"https://doi.org/{DOI}")
    _zpa(moje, jednostka=jednostka)

    response = _post_fetch(importer_client, zgloszenie=moje.pk)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id == moje.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        STATUSY.SPAM,
        STATUSY.ODRZUCONO,
        STATUSY.WYMAGA_ZMIAN,
        STATUSY.ZAAKCEPTOWANY,
        STATUSY.ZAIMPORTOWANY,
    ],
)
def test_fetch_jawne_zgloszenie_w_wykluczonym_statusie_bez_wiazania(
    importer_client, status
):
    """D9 obowiązuje także ścieżkę jawną — i to bez błędu dla operatora."""
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}", status=status)

    response = _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert response.status_code == 302, status
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None, status


@pytest.mark.django_db
@pytest.mark.parametrize("status", [STATUSY.NOWY, STATUSY.PO_ZMIANACH])
def test_fetch_jawne_zgloszenie_w_dozwolonym_statusie_wiaze(importer_client, status):
    """Kontrola pozytywna do testu wykluczeń — te statusy przechodzą."""
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}", status=status)

    _post_fetch(importer_client, zgloszenie=zgl.pk)

    session = ImportSession.objects.get()
    assert session.zgloszenie_id == zgl.pk, status


@pytest.mark.django_db
def test_fetch_jawne_zgloszenie_soft_usuniete_bez_wiazania(importer_client):
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}")
    Zgloszenie_Publikacji.global_objects.filter(pk=zgl.pk).update(
        deleted_at=timezone.now()
    )

    response = _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None


@pytest.mark.django_db
def test_sciezka_jawna_do_zapisu_zwrotnego_wykluczony_status_nic_nie_oznacza(
    importer_client,
):
    """End-to-end ścieżki jawnej: co REALNIE zostało oznaczone po imporcie.

    Poprzednia suita sprawdzała wyłącznie, że FK się ustawia — dlatego
    dziura przeszła. Tu jedziemy aż do rekordu w bazie zgłoszenia.
    """
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}", status=STATUSY.WYMAGA_ZMIAN)

    _post_fetch(importer_client, zgloszenie=zgl.pk)
    session = ImportSession.objects.get()
    assert session.zgloszenie_id is None

    _uruchom_create_task(session)

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED

    zgl.refresh_from_db()
    assert zgl.status == STATUSY.WYMAGA_ZMIAN
    assert zgl.zaimportowano is None
    assert zgl.zaimportowal_id is None
    assert zgl.object_id is None


@pytest.mark.django_db
def test_sciezka_jawna_do_zapisu_zwrotnego_oznacza_dozwolone_zgloszenie(
    importer_client, importer_user
):
    """Kontrola pozytywna end-to-end: cała pętla domyka się w bazie."""
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}")

    _post_fetch(importer_client, zgloszenie=zgl.pk)
    session = ImportSession.objects.get()

    rekord = _uruchom_create_task(session)

    zgl.refresh_from_db()
    assert zgl.status == STATUSY.ZAIMPORTOWANY
    assert zgl.object_id == rekord.pk
    assert zgl.content_type == ContentType.objects.get_for_model(rekord)
    assert zgl.zaimportowal_id == importer_user.pk
    assert zgl.kod_do_edycji is None


# --------------------------------------------------------------------------
# zgloszenie_dozwolone — jednostkowo
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_zgloszenie_dozwolone_przyjmuje_instancje_i_pk_uczelni(uczelnia, jednostka):
    """Wołający mają raz instancję ``Uczelnia``, raz samo ``uczelnia_id``."""
    _jednostka_obcej_uczelni("DWA")  # >1 uczelnia → zawężanie aktywne
    zgl = _zgl()
    _zpa(zgl, jednostka=jednostka)

    assert zgloszenie_dozwolone(zgl.pk, uczelnia) == zgl
    assert zgloszenie_dozwolone(zgl.pk, uczelnia.pk) == zgl


@pytest.mark.django_db
def test_zgloszenie_dozwolone_bez_uczelni_nie_zaweza(uczelnia, jednostka_obca):
    """``uczelnia=None`` (brak mapowania Site→Uczelnia) → filtr jest no-opem."""
    obce = _zgl()
    _zpa(obce, jednostka=jednostka_obca)

    assert zgloszenie_dozwolone(obce.pk, None) == obce


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pk",
    [None, "", 0, "abc", "12abc", [], {}, 10**30, -1, 3.5],
)
def test_zgloszenie_dozwolone_smieciowe_pk_nigdy_nie_rzuca(db, pk):
    """Wiązanie jest opcjonalne — nie może wywrócić requestu."""
    assert zgloszenie_dozwolone(pk, None) is None


# ==========================================================================
# C. Zapis zwrotny rewaliduje status W CHWILI ZAPISU
# ==========================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status_w_miedzyczasie",
    [
        STATUSY.WYMAGA_ZMIAN,
        STATUSY.ZAAKCEPTOWANY,
        STATUSY.ODRZUCONO,
        STATUSY.SPAM,
    ],
)
def test_zapis_zwrotny_nie_oznacza_gdy_status_zmienil_sie_w_miedzyczasie(
    importer_user, status_w_miedzyczasie
):
    """Między związaniem (fetch) a zapisem (create) mija praca operatora.

    Wczytana instancja ``session.zgloszenie`` niesie stan sprzed tego czasu
    — warunek musi siedzieć w ``WHERE``, nie w Pythonie.
    """
    zgl = _zgl(status=STATUSY.NOWY)
    session = _sesja(importer_user, zgloszenie=zgl)

    # Operator (albo inny wątek) zmienia status już po związaniu.
    Zgloszenie_Publikacji.objects.filter(pk=zgl.pk).update(status=status_w_miedzyczasie)

    assert oznacz_jako_zaimportowane(session, _rekord()) is False

    zgl.refresh_from_db()
    assert zgl.status == status_w_miedzyczasie
    assert zgl.zaimportowano is None
    assert zgl.zaimportowal_id is None
    assert zgl.object_id is None


@pytest.mark.django_db
def test_zapis_zwrotny_kasuje_kod_do_edycji(importer_user):
    """Żywy kod na ZAIMPORTOWANYM zgłoszeniu = prosta droga do duplikatu.

    Widok edycji autoryzuje autora SAMYM kodem (nie patrzy na status), więc
    autor mógłby cofnąć zgłoszenie do PO_ZMIANACH i znów zobaczyć przycisk
    „Użyj importera" mimo istniejącego już rekordu.
    """
    kod = uuid.uuid4()
    zgl = _zgl(kod_do_edycji=kod)
    session = _sesja(importer_user, zgloszenie=zgl)

    assert oznacz_jako_zaimportowane(session, _rekord()) is True

    zgl.refresh_from_db()
    assert zgl.status == STATUSY.ZAIMPORTOWANY
    assert zgl.kod_do_edycji is None
    assert not Zgloszenie_Publikacji.objects.filter(kod_do_edycji=kod).exists()


@pytest.mark.django_db
def test_zapis_zwrotny_kasuje_kod_do_edycji_przez_task(importer_user):
    """To samo, ale całą ścieżką zadania — kod nie może przeżyć importu."""
    zgl = _zgl(kod_do_edycji=uuid.uuid4())
    session = _sesja(importer_user, zgloszenie=zgl)

    _uruchom_create_task(session)

    zgl.refresh_from_db()
    assert zgl.kod_do_edycji is None


@pytest.mark.django_db
def test_wiele_zgloszen_bez_kodu_do_edycji_wspolistnieje(importer_user):
    """``kod_do_edycji`` jest ``unique``, ale ``null=True`` — NULL-e nie kolidują."""
    for _ in range(3):
        zgl = _zgl(kod_do_edycji=uuid.uuid4())
        session = _sesja(importer_user, zgloszenie=zgl)
        assert oznacz_jako_zaimportowane(session, _rekord()) is True

    assert Zgloszenie_Publikacji.objects.filter(kod_do_edycji__isnull=True).count() == 3


@pytest.mark.django_db
def test_zapis_zwrotny_przy_zero_zaktualizowanych_wierszy_loguje(importer_user, caplog):
    """Warunkowy UPDATE zwrócił 0 → ``False`` + wpis w logu z powodem."""
    zgl = _zgl(status=STATUSY.NOWY)
    session = _sesja(importer_user, zgloszenie=zgl)
    Zgloszenie_Publikacji.objects.filter(pk=zgl.pk).update(status=STATUSY.SPAM)

    with caplog.at_level(logging.INFO, logger="importer_publikacji.zgloszenia"):
        assert oznacz_jako_zaimportowane(session, _rekord()) is False

    komunikaty = [r.getMessage() for r in caplog.records]
    assert any("nie kwalifikuje się" in m and str(zgl.pk) in m for m in komunikaty), (
        komunikaty
    )
    # Powód (status w chwili zapisu) MUSI być w logu — inaczej trzeba zgadywać.
    assert any(str(int(STATUSY.SPAM)) in m for m in komunikaty), komunikaty


@pytest.mark.django_db
def test_zapis_zwrotny_odswieza_ostatnio_zmieniony(importer_user):
    """``.update()`` omija ``auto_now`` — datę trzeba wpisać jawnie.

    ``ostatnio_zmieniony`` ma ``auto_now=True``, ale bulk ``UPDATE`` nie
    woła ``Model.save()``, więc pole zostawało z datą sprzed importu.
    Zapis zwrotny jest realną zmianą zgłoszenia (status, rekord, kod do
    edycji) — musi być po niej widoczny w polu „ostatnio zmieniony".
    """
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    stara_data = timezone.now() - datetime.timedelta(days=3)
    Zgloszenie_Publikacji.objects.filter(pk=zgl.pk).update(
        ostatnio_zmieniony=stara_data
    )
    przed = Zgloszenie_Publikacji.objects.values_list(
        "ostatnio_zmieniony", flat=True
    ).get(pk=zgl.pk)
    assert przed == stara_data

    assert oznacz_jako_zaimportowane(session, _rekord()) is True

    po, zaimportowano = Zgloszenie_Publikacji.objects.values_list(
        "ostatnio_zmieniony", "zaimportowano"
    ).get(pk=zgl.pk)

    assert po > przed, "``ostatnio_zmieniony`` zamarło na dacie sprzed importu"
    # Jeden ``timezone.now()`` na cały UPDATE — obie kolumny opisują to samo
    # zdarzenie, więc rozjazd znaczyłby dwa niezależne odczyty zegara.
    assert po == zaimportowano


@pytest.mark.django_db
def test_zaimportowane_zgloszenie_laduje_na_gorze_domyslnej_listy(importer_user):
    """``Meta.ordering = ("-ostatnio_zmieniony", …)`` — to nie jest kosmetyka.

    Zamrożona data spychała świeżo domknięte zgłoszenie na DÓŁ listy
    w module redagowania: operator kończył import i nie widział efektu
    tam, gdzie go szukał.
    """
    assert Zgloszenie_Publikacji._meta.ordering[0] == "-ostatnio_zmieniony"

    zgl = _zgl(tytul="Zgłoszenie domykane importem")
    Zgloszenie_Publikacji.objects.filter(pk=zgl.pk).update(
        ostatnio_zmieniony=timezone.now() - datetime.timedelta(days=7)
    )
    for numer in range(3):
        _zgl(tytul=f"Inne zgłoszenie {numer}")

    kolejnosc = list(Zgloszenie_Publikacji.objects.values_list("pk", flat=True))
    assert kolejnosc[-1] == zgl.pk, "stan wyjściowy: zgłoszenie jest na dole"

    session = _sesja(importer_user, zgloszenie=zgl)
    assert oznacz_jako_zaimportowane(session, _rekord()) is True

    kolejnosc = list(Zgloszenie_Publikacji.objects.values_list("pk", flat=True))
    assert kolejnosc[0] == zgl.pk


# ==========================================================================
# D. Lost update + ``modified`` w ``update_fields``
# ==========================================================================


@pytest.mark.django_db
def test_task_fetch_nie_kasuje_wiazania_dopisanego_w_locie(importer_user):
    """Regresja lost update.

    Sesja jest in-flight (FETCHING), więc task trzyma własną, starszą
    instancję wiersza. W trakcie jego pracy widok (gałąź idempotency
    ``FetchView``) dopisuje ``zgloszenie`` warunkowym UPDATE-em. Pełne
    ``session.save()`` taska wpisywało z powrotem ``zgloszenie_id = NULL``.
    """
    session = _sesja(importer_user, doi=DOI, status=ImportSession.Status.FETCHING)
    # DOI zgłoszenia ≠ DOI sesji — auto-match po DOI go NIE odtworzy, więc
    # jedynym powodem, dla którego FK może przeżyć, jest brak nadpisania.
    zgl = _zgl(strona_www="https://doi.org/10.9999/inne")

    def _fetch_i_rownolegly_zapis_widoku(identifier):
        # Dokładnie to, co robi FetchView w gałęzi idempotency.
        ImportSession.objects.filter(pk=session.pk, zgloszenie__isnull=True).update(
            zgloszenie=zgl
        )
        return _fake_fetch_result()

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.side_effect = _fetch_i_rownolegly_zapis_widoku
        mock_get_provider.return_value = provider

        fetch_session_task.apply(args=[session.pk, session.created_by_id]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.FETCHED
    assert session.zgloszenie_id == zgl.pk, "wiązanie skasowane przez zapis taska"


@pytest.mark.django_db
def test_task_fetch_nie_przestemplowuje_jawnego_wiazania_auto_matchem(importer_user):
    """Jawny wybór dopisany w locie bije auto-wiązanie po DOI (ścieżka A > B)."""
    session = _sesja(importer_user, doi=DOI, status=ImportSession.Status.FETCHING)
    jawne = _zgl(strona_www="https://doi.org/10.9999/jawne")
    po_doi = _zgl(strona_www=f"https://doi.org/{DOI}", tytul="Kandydat po DOI")

    def _fetch(identifier):
        ImportSession.objects.filter(pk=session.pk, zgloszenie__isnull=True).update(
            zgloszenie=jawne
        )
        return _fake_fetch_result()

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.side_effect = _fetch
        mock_get_provider.return_value = provider

        fetch_session_task.apply(args=[session.pk, session.created_by_id]).get()

    session.refresh_from_db()
    assert session.zgloszenie_id == jawne.pk
    po_doi.refresh_from_db()
    assert po_doi.status == STATUSY.NOWY


@pytest.mark.django_db
def test_zwiaz_automatycznie_nie_przestemplowuje_wiazania_zapisanego_po_odczycie(
    importer_user, caplog
):
    """Okno wyścigu PO ``refresh_from_db`` w zadaniu.

    ``test_task_fetch_nie_przestemplowuje_jawnego_wiazania_auto_matchem``
    pokrywa zapis widoku, który zdążył PRZED odświeżeniem instancji w tasku.
    Tu symulujemy drugą połowę okna: instancja w pamięci ma
    ``zgloszenie_id = None``, ale w bazie jawne wiązanie JUŻ jest.

    Dopóki reguła „tylko gdy puste" siedziała w sprawdzeniu na obiekcie
    w pamięci, a zapis był bezwarunkowym ``save(update_fields=…)``,
    auto-match po DOI przestemplowywał jawny wybór operatora — i domknięte
    zostawało INNE zgłoszenie niż to, które operator wskazał.
    """
    session = _sesja(importer_user, doi=DOI)
    jawne = _zgl(strona_www="https://doi.org/10.9999/jawne")
    po_doi = _zgl(strona_www=f"https://doi.org/{DOI}", tytul="Kandydat po DOI")

    # Ścieżka A (widok) zapisuje wiązanie już po tym, jak zadanie wczytało
    # swój wiersz — instancja w pamięci nadal go nie widzi.
    ImportSession.objects.filter(pk=session.pk).update(zgloszenie=jawne)
    assert session.zgloszenie_id is None, "obiekt w pamięci nie widzi zapisu"

    # Kontrola pozytywna założeń: auto-match MA jednego kandydata, więc
    # gdyby nie warunek w ``WHERE``, zapis by się wykonał.
    assert list(kandydaci_dla_sesji(session)) == [po_doi]

    with caplog.at_level(logging.INFO, logger="importer_publikacji.zgloszenia"):
        assert zwiaz_automatycznie(session) is False

    w_bazie = ImportSession.objects.values_list("zgloszenie", flat=True).get(
        pk=session.pk
    )
    assert w_bazie == jawne.pk, "auto-match przestemplował jawny wybór"

    # ``refresh_from_db`` w gałęzi przegranej: instancja w pamięci przestaje
    # kłamać, więc dalszy ciąg zadania (zapis zwrotny) oznacza właściwe
    # zgłoszenie, a nie żadne.
    assert session.zgloszenie_id == jawne.pk

    assert any("w międzyczasie" in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


@pytest.mark.django_db
def test_zwiaz_automatycznie_wiaze_gdy_w_bazie_nadal_pusto(importer_user):
    """Kontrola pozytywna do testu wyżej: bez wyścigu wiązanie powstaje.

    Bez tego warunkowy ``UPDATE`` mógłby nie wiązać NIGDY i test wyścigu
    i tak byłby zielony.
    """
    session = _sesja(importer_user, doi=DOI)
    kandydat = _zgl(strona_www=f"https://doi.org/{DOI}")

    assert (
        ImportSession.objects.values_list("zgloszenie", flat=True).get(pk=session.pk)
        is None
    )

    assert zwiaz_automatycznie(session) is True

    assert (
        ImportSession.objects.values_list("zgloszenie", flat=True).get(pk=session.pk)
        == kandydat.pk
    )
    assert session.zgloszenie_id == kandydat.pk


@pytest.mark.django_db
def test_task_fetch_przesuwa_modified(importer_user):
    """``update_fields`` MUSI zawierać ``modified``.

    ``auto_now`` odpala się WYŁĄCZNIE dla pól wymienionych w
    ``update_fields`` — bez tego ``modified`` zamarza i ``is_stalled()``
    uznaje żywą sesję za martwą (watchdog ubija działający import).
    """
    session = _sesja(importer_user, doi=DOI, status=ImportSession.Status.FETCHING)
    stara_data = timezone.now() - datetime.timedelta(hours=1)
    ImportSession.objects.filter(pk=session.pk).update(modified=stara_data)

    # Stan wyjściowy: watchdog uznałby tę sesję za martwą.
    assert ImportSession.objects.get(pk=session.pk).is_stalled() is True

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = _fake_fetch_result()
        mock_get_provider.return_value = provider

        fetch_session_task.apply(args=[session.pk, session.created_by_id]).get()

    session.refresh_from_db()
    assert session.modified > stara_data

    # Gdyby ``modified`` zamarzło, sesja nadal in-flight (kolejny etap
    # przetwarzania) zostałaby ubita przez watchdog jako zawieszona.
    session.status = ImportSession.Status.FETCHING
    assert session.is_stalled() is False


@pytest.mark.django_db
def test_task_fetch_bledny_przesuwa_modified(importer_user):
    """Gałąź ``except`` też zapisuje ``modified`` (``_POLA_BLEDU``)."""
    session = _sesja(importer_user, doi=DOI, status=ImportSession.Status.FETCHING)
    stara_data = timezone.now() - datetime.timedelta(hours=1)
    ImportSession.objects.filter(pk=session.pk).update(modified=stara_data)

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.side_effect = RuntimeError("boom")
        mock_get_provider.return_value = provider

        with pytest.raises(RuntimeError, match="boom"):
            fetch_session_task.apply(args=[session.pk, session.created_by_id]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.IMPORT_FAILED
    assert session.modified > stara_data


@pytest.mark.django_db
def test_task_create_przesuwa_modified(importer_user):
    session = _sesja(importer_user, status=ImportSession.Status.CREATING)
    stara_data = timezone.now() - datetime.timedelta(hours=1)
    ImportSession.objects.filter(pk=session.pk).update(modified=stara_data)

    _uruchom_create_task(session)

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED
    assert session.modified > stara_data


@pytest.mark.django_db
def test_task_create_nie_kasuje_odpiecia_zrobionego_w_locie(importer_user):
    """Operator odpiął zgłoszenie w trakcie tworzenia rekordu — jego decyzja
    jest nowsza niż stan wczytany na starcie zadania."""
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    def _create(sess):
        ImportSession.objects.filter(pk=sess.pk).update(zgloszenie=None)
        return _rekord()

    with patch("importer_publikacji.tasks._create_publication") as mock_create:
        mock_create.side_effect = _create
        create_publication_task.apply(
            args=[session.pk, session.created_by_id, False]
        ).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED
    zgl.refresh_from_db()
    assert zgl.status == STATUSY.NOWY
    assert zgl.zaimportowano is None


# ==========================================================================
# E. Wyjątek w zapisie zwrotnym nie wywraca importu
# ==========================================================================


@pytest.mark.django_db
def test_wyjatek_w_zapisie_zwrotnym_zostawia_sesje_completed(importer_user):
    """Inaczej operator klika „Ponów" i powstaje DRUGI rekord tej pracy."""
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)
    rekord = _rekord()

    with (
        patch("importer_publikacji.tasks._create_publication") as mock_create,
        patch(
            "importer_publikacji.zgloszenia.oznacz_jako_zaimportowane"
        ) as mock_oznacz,
        patch("importer_publikacji.tasks.rollbar") as mock_rollbar,
    ):
        mock_create.return_value = rekord
        mock_oznacz.side_effect = RuntimeError("zapis zwrotny wybuchł")

        # Bez ``pytest.raises``: wyjątek NIE może wypłynąć z zadania.
        create_publication_task.apply(
            args=[session.pk, session.created_by_id, False]
        ).get()

        assert mock_rollbar.report_exc_info.called

    session.refresh_from_db()
    assert session.status == ImportSession.Status.COMPLETED
    assert session.created_record_id == rekord.pk
    assert session.last_failed_stage == ""

    # Rekord publikacji istnieje, zgłoszenie zostaje do ręcznego domknięcia.
    assert Wydawnictwo_Ciagle.objects.filter(pk=rekord.pk).exists()
    zgl.refresh_from_db()
    assert zgl.status == STATUSY.NOWY


@pytest.mark.django_db
def test_wyjatek_w_zapisie_zwrotnym_loguje_traceback(importer_user, caplog):
    zgl = _zgl()
    session = _sesja(importer_user, zgloszenie=zgl)

    with (
        patch("importer_publikacji.tasks._create_publication") as mock_create,
        patch(
            "importer_publikacji.zgloszenia.oznacz_jako_zaimportowane"
        ) as mock_oznacz,
        patch("importer_publikacji.tasks.rollbar"),
        caplog.at_level(logging.ERROR, logger="importer_publikacji.tasks"),
    ):
        mock_create.return_value = _rekord()
        mock_oznacz.side_effect = RuntimeError("zapis zwrotny wybuchł")

        create_publication_task.apply(
            args=[session.pk, session.created_by_id, False]
        ).get()

    wpisy = [r for r in caplog.records if "ręcznego domknięcia" in r.getMessage()]
    assert wpisy, [r.getMessage() for r in caplog.records]
    # ``logger.exception`` — bez tracebacku nie da się dojść, co wybuchło.
    assert wpisy[0].exc_info is not None
    assert "zapis zwrotny wybuchł" in (wpisy[0].exc_text or "")


# ==========================================================================
# F. Zawężenie do uczelni — udokumentowane ograniczenia (charakteryzacja)
# ==========================================================================


@pytest.mark.django_db
def test_zgloszenie_wspolautorskie_jest_kandydatem_dla_obu_uczelni(
    importer_user, uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2
):
    """ŚWIADOMY przeciek D8: JOIN po autorach daje semantykę OR.

    Test charakteryzujący — praca współautorska naprawdę „należy" do obu
    uczelni, a wariant restrykcyjny („wszyscy autorzy z jednej") ukrywałby
    ją przed obiema. Gdyby ktoś to zmienił, ten test ma zapalić się na
    czerwono, żeby zmiana była decyzją, a nie efektem ubocznym.
    """
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}")
    _zpa(zgl, jednostka=jednostka_uczelnia1)
    _zpa(zgl, jednostka=jednostka_uczelnia2)

    sesja_1 = _sesja(importer_user, uczelnia=uczelnia1)
    sesja_2 = _sesja(importer_user, uczelnia=uczelnia2)

    assert list(kandydaci_dla_sesji(sesja_1)) == [zgl]
    assert list(kandydaci_dla_sesji(sesja_2)) == [zgl]


@pytest.mark.django_db
def test_zgloszenie_bez_autorow_wypada_w_instalacji_wielouczelnianej(
    importer_user, uczelnia1, uczelnia2
):
    """ŚWIADOME fail-closed: bez autorów nie da się przypisać do uczelni.

    Lepiej nie pokazać nikomu niż pokazać wszystkim — operator dojdzie do
    zgłoszenia przez moduł redagowania i zwiąże je jawnie.
    """
    _zgl(strona_www=f"https://doi.org/{DOI}")
    session = _sesja(importer_user, uczelnia=uczelnia1)

    assert list(kandydaci_dla_sesji(session)) == []


@pytest.mark.django_db
def test_zgloszenie_bez_autorow_widoczne_w_instalacji_jednouczelnianej(
    importer_user, uczelnia
):
    """Kontrola pozytywna: przy jednej uczelni filtr jest no-opem."""
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}")
    session = _sesja(importer_user, uczelnia=uczelnia)

    assert list(kandydaci_dla_sesji(session)) == [zgl]


# ==========================================================================
# G. Renderowanie — baner kandydatów i strona „Gotowe"
# ==========================================================================


def _url_verify(session):
    return reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})


@pytest.mark.django_db
def test_baner_wersja_rozstrzygajaca_przy_dwoch_kandydatach(
    importer_client, importer_user
):
    session = _sesja(importer_user, status=ImportSession.Status.FETCHED)
    a = _zgl(strona_www=f"https://doi.org/{DOI}", tytul="Pierwszy kandydat")
    b = _zgl(strona_www=f"https://doi.org/{DOI}", tytul="Drugi kandydat")

    response = importer_client.get(_url_verify(session))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'id="baner-zgloszenia"' in html
    assert f"#{a.pk}" in html
    assert f"#{b.pk}" in html
    assert "Które z nich domknąć tym importem?" in html
    assert "Żadne z nich" in html


@pytest.mark.django_db
def test_baner_wersja_potwierdzajaca_dla_sesji_zwiazanej(
    importer_client, importer_user
):
    zgl = _zgl(strona_www=f"https://doi.org/{DOI}")
    session = _sesja(importer_user, status=ImportSession.Status.FETCHED, zgloszenie=zgl)

    response = importer_client.get(_url_verify(session))
    html = response.content.decode()

    assert 'id="baner-zgloszenia"' in html
    assert "Ten import domknie zgłoszenie publikacji" in html
    assert f"#{zgl.pk}" in html
    assert "Odepnij" in html
    # Wersja potwierdzająca NIE pyta o wybór.
    assert "Które z nich domknąć tym importem?" not in html


@pytest.mark.django_db
def test_baner_wyciszony_po_zadne_z_nich(importer_client, importer_user):
    session = _sesja(
        importer_user,
        status=ImportSession.Status.FETCHED,
        zgloszenie_odrzucone_przez_operatora=True,
    )
    _zgl(strona_www=f"https://doi.org/{DOI}")
    _zgl(strona_www=f"https://doi.org/{DOI}", tytul="Drugi kandydat")

    response = importer_client.get(_url_verify(session))
    html = response.content.decode()

    assert response.status_code == 200
    assert 'id="baner-zgloszenia"' not in html


@pytest.mark.django_db
def test_baner_nie_pokazuje_emaila_zglaszajacego(importer_client, importer_user):
    """Regresja przecieku przez granicę uczelni.

    Zgłoszenie współautorskie jest kandydatem dla OBU uczelni, więc e-mail
    zgłaszającego zobaczyłby operator obcej uczelni. Numer, autor, tytuł
    i rok wystarczą do rozpoznania kandydata.
    """
    email = "prywatny.adres@example.com"
    session = _sesja(importer_user, status=ImportSession.Status.FETCHED)
    _zgl(strona_www=f"https://doi.org/{DOI}", email=email)
    _zgl(
        strona_www=f"https://doi.org/{DOI}",
        email="drugi.adres@example.com",
        tytul="Drugi kandydat",
    )

    response = importer_client.get(_url_verify(session))
    html = response.content.decode()

    assert 'id="baner-zgloszenia"' in html, "baner musi się wyrenderować"
    assert email not in html
    assert "drugi.adres@example.com" not in html


@pytest.mark.django_db
def test_done_callout_o_domknieciu_dokladnie_raz(importer_client, importer_user):
    """Wcześniej komunikat szedł 3× (flash × 2 ramki + callout).

    Flash został usunięty; callout jest wyliczany z bazy przy każdym GET,
    więc nie znika też po F5.
    """
    rekord = _rekord()
    zgl = _zgl(
        status=STATUSY.ZAIMPORTOWANY,
        zaimportowano=timezone.now(),
        zaimportowal=importer_user,
        content_type=ContentType.objects.get_for_model(rekord),
        object_id=rekord.pk,
    )
    session = _sesja(
        importer_user,
        status=ImportSession.Status.COMPLETED,
        zgloszenie=zgl,
        created_record_content_type=ContentType.objects.get_for_model(rekord),
        created_record_id=rekord.pk,
    )
    url = reverse("importer_publikacji:done", kwargs={"session_id": session.pk})

    response = importer_client.get(url)
    html = response.content.decode()

    assert response.status_code == 200
    assert html.count("omknięto zgłoszenie publikacji") == 1

    # Idempotencja: F5 nie gasi calloutu (flash by zniknął).
    html_po_odswiezeniu = importer_client.get(url).content.decode()
    assert html_po_odswiezeniu.count("omknięto zgłoszenie publikacji") == 1


@pytest.mark.django_db
def test_done_bez_domknietego_zgloszenia_bez_calloutu(importer_client, importer_user):
    """Kontrola negatywna: sesja związana, ale zgłoszenie NIE oznaczone."""
    rekord = _rekord()
    zgl = _zgl(status=STATUSY.NOWY)
    session = _sesja(
        importer_user,
        status=ImportSession.Status.COMPLETED,
        zgloszenie=zgl,
        created_record_content_type=ContentType.objects.get_for_model(rekord),
        created_record_id=rekord.pk,
    )

    response = importer_client.get(
        reverse("importer_publikacji:done", kwargs={"session_id": session.pk})
    )

    assert response.status_code == 200
    assert "omknięto zgłoszenie publikacji" not in response.content.decode()
