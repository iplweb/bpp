"""FD#482 — przycisk „Wróć do zgłoszeń" na końcu importu.

Operator, który wszedł do importera przyciskiem „Użyj importera" z modułu
redagowania zgłoszeń, po zakończonym imporcie dostaje przycisk powrotu do
listy zgłoszeń — z tymi samymi filtrami, z którymi tę listę zostawił.

Pamięć „skąd przyszedł" siedzi w ``ImportSession.powrot_do_zgloszen``:

* ``NULL`` — import nie zaczął się w module zgłoszeń (np. wiązanie po DOI),
* ``""`` — zaczął się tam, lista bez filtrów,
* querystring — zaczął się tam, z filtrami listy.
"""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.zgloszenia import normalizuj_filtry_listy_zgloszen
from zglos_publikacje.models import Zgloszenie_Publikacji

STATUSY = Zgloszenie_Publikacji.Statusy
CHANGELIST = "admin:zglos_publikacje_zgloszenie_publikacji_changelist"
DOI = "10.1234/fd482.test"
FILTRY = "stan_obslugi=do_obslugi&q=kowalski"


def _zgl(status=STATUSY.NOWY, **kwargs):
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        strona_www=f"https://doi.org/{DOI}",
        tytul_oryginalny="Praca testowa FD482",
        status=status,
        rok=2024,
        rodzaj_zglaszanej_publikacji=1,
        **kwargs,
    )


def _post_fetch(client, **extra):
    """POST na FetchView z zamockowanym providerem i taskiem Celery."""
    dane = {"provider": "CrossRef", "identifier": DOI}
    dane.update(extra)

    with (
        patch("importer_publikacji.views.wizard.fetch_session_task") as mock_task,
        patch("importer_publikacji.views.wizard.get_provider") as mock_provider,
    ):
        from importer_publikacji.providers import InputMode

        mock_provider.return_value.input_mode = InputMode.IDENTIFIER
        mock_provider.return_value.validate_identifier.return_value = DOI
        mock_task.delay.return_value.id = "task-uuid"

        return client.post(reverse("importer_publikacji:fetch"), dane)


def _sesja_zakonczona(user, **kwargs):
    rekord = baker.make("bpp.Wydawnictwo_Ciagle")
    return ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier=DOI,
        raw_data={},
        normalized_data={"doi": DOI},
        status=ImportSession.Status.COMPLETED,
        created_record_content_type=ContentType.objects.get_for_model(rekord),
        created_record_id=rekord.pk,
        **kwargs,
    )


def _done_html(client, session):
    response = client.get(
        reverse("importer_publikacji:done", kwargs={"session_id": session.pk})
    )
    assert response.status_code == 200
    return response.content.decode()


def _href_powrotu(html):
    """Adres przycisku „Wróć do zgłoszeń" (``None``, gdy go nie ma)."""
    import re

    m = re.search(r'<a href="([^"]*)"[^>]*id="wroc-do-zgloszen"', html)
    if m is None:
        m = re.search(r'id="wroc-do-zgloszen"[^>]*href="([^"]*)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


# --------------------------------------------------------------------------
# Normalizacja filtrów listy
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        (None, ""),
        ("", ""),
        ("stan_obslugi=wszystkie", "stan_obslugi=wszystkie"),
        ("q=a b&q=c", "q=a+b&q=c"),
        ("q=%C5%BC%C3%B3%C5%82w", "q=%C5%BC%C3%B3%C5%82w"),
    ],
)
def test_normalizacja_filtrow(wejscie, oczekiwane):
    assert normalizuj_filtry_listy_zgloszen(wejscie) == oczekiwane


def test_normalizacja_nie_przepuszcza_adresu_ani_fragmentu():
    """Wynik to wyłącznie querystring — nie da się nim wyjść poza listę."""
    wynik = normalizuj_filtry_listy_zgloszen("//evil.example.com/#x=1&a=b")
    assert "/" not in wynik.replace("%2F", "")
    assert "#" not in wynik


def test_normalizacja_za_dlugich_filtrow_daje_pusty_ciag():
    assert normalizuj_filtry_listy_zgloszen("q=" + "x" * 5000) == ""


# --------------------------------------------------------------------------
# Moduł redagowania: filtry listy jadą w adresie „Użyj importera"
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_uzyj_importera_niesie_filtry_listy(admin_client):
    zgl = _zgl()
    url = reverse("admin:zglos_publikacje_zgloszenie_publikacji_change", args=[zgl.pk])

    response = admin_client.get(url, {"_changelist_filters": FILTRY})

    importer_url = response.context["importer_url"]
    params = parse_qs(urlparse(importer_url).query)
    assert params["zgloszenie"] == [str(zgl.pk)]
    assert params["zgloszenia_filtry"] == [FILTRY]


@pytest.mark.django_db
def test_uzyj_importera_otwiera_sie_w_tej_samej_karcie(admin_client):
    """Import w tej samej karcie — „Wróć do zgłoszeń" zamyka pętlę."""
    zgl = _zgl()
    url = reverse("admin:zglos_publikacje_zgloszenie_publikacji_change", args=[zgl.pk])

    html = admin_client.get(url).content.decode()

    linia = next(x for x in html.splitlines() if "Użyj importera" in x)
    assert 'target="_blank"' not in linia


# --------------------------------------------------------------------------
# Importer: kontekst przeżywa kafelki i „Wybierz inne źródło"
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_formularz_fetch_niesie_filtry_w_ukrytym_polu(importer_client):
    response = importer_client.get(
        reverse("importer_publikacji:index"),
        {"provider": "CrossRef", "zgloszenie": "7", "zgloszenia_filtry": FILTRY},
    )

    form = response.context["form"]
    assert form["zgloszenia_filtry"].value() == FILTRY
    assert 'name="zgloszenia_filtry"' in response.content.decode()


@pytest.mark.django_db
def test_wybierz_inne_zrodlo_i_kafelki_nie_gubia_filtrow(importer_client):
    index = reverse("importer_publikacji:index")
    response = importer_client.get(
        index,
        {
            "provider": "CrossRef",
            "zgloszenie": "7",
            "zgloszenia_filtry": FILTRY,
            "identifier": DOI,
        },
    )
    html = response.content.decode()

    import re

    zmiana = re.search(r'class="importer-change-source"\s+href="([^"]*)"', html)
    assert zmiana, "brak linku „Wybierz inne źródło”"
    params = parse_qs(urlparse(zmiana.group(1).replace("&amp;", "&")).query)
    assert params["zgloszenie"] == ["7"]
    assert params["zgloszenia_filtry"] == [FILTRY]
    assert params["identifier"] == [DOI]

    landing = importer_client.get(zmiana.group(1).replace("&amp;", "&"))
    kafel = re.search(
        r'data-provider="CrossRef"\s+href="([^"]*)"', landing.content.decode()
    )
    assert kafel, "brak kafelka CrossRef"
    params = parse_qs(urlparse(kafel.group(1).replace("&amp;", "&")).query)
    assert params["provider"] == ["CrossRef"]
    assert params["zgloszenie"] == ["7"]
    assert params["zgloszenia_filtry"] == [FILTRY]
    assert params["identifier"] == [DOI]


# --------------------------------------------------------------------------
# FetchView: zapamiętanie „przyszedł ze zgłoszeń"
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_ze_zgloszen_zapamietuje_filtry(importer_client):
    zgl = _zgl()

    _post_fetch(importer_client, zgloszenie=zgl.pk, zgloszenia_filtry=FILTRY)

    assert ImportSession.objects.get().powrot_do_zgloszen == FILTRY


@pytest.mark.django_db
def test_fetch_ze_zgloszen_bez_filtrow_to_pusty_ciag(importer_client):
    zgl = _zgl()

    _post_fetch(importer_client, zgloszenie=zgl.pk)

    assert ImportSession.objects.get().powrot_do_zgloszen == ""


@pytest.mark.django_db
def test_fetch_bez_zgloszenia_nie_zapamietuje_powrotu(importer_client):
    _post_fetch(importer_client, zgloszenia_filtry=FILTRY)

    assert ImportSession.objects.get().powrot_do_zgloszen is None


@pytest.mark.django_db
def test_fetch_smieciowe_filtry_nie_blokuja_importu(importer_client):
    zgl = _zgl()

    response = _post_fetch(
        importer_client, zgloszenie=zgl.pk, zgloszenia_filtry="q=" + "x" * 5000
    )

    assert response.status_code == 302
    session = ImportSession.objects.get()
    assert session.zgloszenie_id == zgl.pk
    assert session.powrot_do_zgloszen == ""


@pytest.mark.django_db
def test_fetch_idempotency_dopisuje_powrot_do_sesji_in_flight(
    importer_client, importer_user
):
    istniejaca = baker.make(
        ImportSession,
        created_by=importer_user,
        provider_name="CrossRef",
        identifier=DOI,
        status=ImportSession.Status.FETCHING,
    )
    zgl = _zgl()

    _post_fetch(importer_client, zgloszenie=zgl.pk, zgloszenia_filtry=FILTRY)

    assert ImportSession.objects.count() == 1
    istniejaca.refresh_from_db()
    assert istniejaca.powrot_do_zgloszen == FILTRY


# --------------------------------------------------------------------------
# Ekran końcowy
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_done_ze_zgloszen_pokazuje_powrot_z_filtrami(importer_client, importer_user):
    session = _sesja_zakonczona(importer_user, powrot_do_zgloszen=FILTRY)

    href = _href_powrotu(_done_html(importer_client, session))

    assert href == f"{reverse(CHANGELIST)}?{FILTRY}"


@pytest.mark.django_db
def test_done_ze_zgloszen_bez_filtrow(importer_client, importer_user):
    session = _sesja_zakonczona(importer_user, powrot_do_zgloszen="")

    href = _href_powrotu(_done_html(importer_client, session))

    assert href == reverse(CHANGELIST)


@pytest.mark.django_db
def test_done_wiazanie_po_doi_bez_przycisku_powrotu(importer_client, importer_user):
    """Auto-wiązanie po DOI: operator w zgłoszeniach nie był — nie ma dokąd wracać."""
    session = _sesja_zakonczona(importer_user, zgloszenie=_zgl())

    assert _href_powrotu(_done_html(importer_client, session)) is None


@pytest.mark.django_db
def test_done_po_odpieciu_zgloszenia_przycisk_zostaje(importer_client, importer_user):
    """„Odepnij" kasuje wiązanie, ale nie to, skąd operator przyszedł."""
    session = _sesja_zakonczona(
        importer_user, zgloszenie=_zgl(), powrot_do_zgloszen=FILTRY
    )
    importer_client.post(
        reverse(
            "importer_publikacji:zgloszenie-wybierz",
            kwargs={"session_id": session.pk},
        ),
        {"odepnij": "1"},
    )
    session.refresh_from_db()
    assert session.zgloszenie_id is None

    assert _href_powrotu(_done_html(importer_client, session)) is not None
