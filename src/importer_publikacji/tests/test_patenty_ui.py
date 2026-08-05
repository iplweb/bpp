"""Testy UI kreatora patentów w importer_publikacji (dokończenie #517).

Pokrywają plumbing wizarda dodany ponad „fundament" (mapowanie @patent +
_create_patent): auto-detekcję, trój-drożny krok Verify, rozgałęzienia
przepływu (pomijanie Source/PBN), guardy widoków, get_continue_url, tłumienie
PBN na Review, gałąź patentową sugestii punktacji oraz guardy ścieżki create
(streszczenia/PBN). Testy _create_patent per-pole są w test_create_patent.py.
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession

RR = ImportSession.RodzajRekordu
ST = ImportSession.Status


def _patent_nd(**extra):
    nd = {
        "title": "Sposob wytwarzania czegos tam",
        "year": 2024,
        "doi": None,
        "authors": [],
        "abstracts": [],
        "publication_type": "patent",
        "patent_number": "PL123456",
        "patent_grant_number": None,
        "filing_date": "2024-03-15",
        "grant_date": None,
        "patent_type": None,
        "patent_holder": "ACME Corp",
        "jurisdiction": "Poland",
    }
    nd.update(extra)
    return nd


def _patent_session(user, status=ST.FETCHED, **nd_extra):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="BibTeX",
        identifier="@patent{...}",
        raw_data={"bibtex_type": "patent"},
        normalized_data=_patent_nd(**nd_extra),
        rodzaj_rekordu=RR.PATENT,
        status=status,
    )


# --- Detekcja ---------------------------------------------------------------


@pytest.mark.django_db
def test_fetch_patent_ustawia_rodzaj_rekordu(importer_user, jezyki):
    """@patent → publication_type 'patent' → auto rodzaj_rekordu=PATENT."""
    from importer_publikacji.providers.bibtex import BibTeXProvider
    from importer_publikacji.tasks import _auto_match_type_and_language

    result = BibTeXProvider().fetch(
        "@patent{k, title={Widget}, year={2024}, number={PL1}}"
    )
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="x",
        raw_data={},
        normalized_data={},
    )
    _auto_match_type_and_language(session, result)
    assert session.rodzaj_rekordu == RR.PATENT


@pytest.mark.django_db
def test_fetch_article_nie_jest_patentem(importer_user, jezyki):
    from importer_publikacji.providers.bibtex import BibTeXProvider
    from importer_publikacji.tasks import _auto_match_type_and_language

    result = BibTeXProvider().fetch("@article{k, title={Widget}, year={2024}}")
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        identifier="x",
        raw_data={},
        normalized_data={},
    )
    _auto_match_type_and_language(session, result)
    assert session.rodzaj_rekordu == RR.CIAGLE


# --- Prefill round-trip -----------------------------------------------------


@pytest.mark.django_db
def test_patent_prefill_round_trip_zachowuje_jawne_wybory(importer_user):
    """Klucze zapisane przez poprzedni submit (nawet None) mają pierwszeństwo —
    powrót do Verify nie nadpisuje wyborów operatora."""
    from importer_publikacji.views.steps import _patent_verify_initial

    session = _patent_session(
        importer_user,
        patent_number="PL42",
        rodzaj_prawa_id=None,  # operator wyczyścił
        wdrozenie=True,
        wydzial_id=7,
    )
    initial = _patent_verify_initial(session)
    assert initial["numer_zgloszenia"] == "PL42"
    assert initial["rodzaj_prawa"] is None  # present-None uszanowane
    assert initial["wdrozenie"] is True
    assert initial["wydzial"] == 7


@pytest.mark.django_db
def test_patent_prefill_best_effort_gdy_klucz_nieobecny(importer_user, statusy_korekt):
    """Pierwsze wejście (brak rodzaj_prawa_id w nd) → best-effort po nazwie."""
    from model_bakery import baker

    from bpp.models import Rodzaj_Prawa_Patentowego
    from importer_publikacji.views.steps import _patent_verify_initial

    rp = baker.make(Rodzaj_Prawa_Patentowego, nazwa="TEST-patent-nazwa")
    session = _patent_session(importer_user, patent_type="TEST-patent-nazwa")
    assert "rodzaj_prawa_id" not in session.normalized_data
    initial = _patent_verify_initial(session)
    assert initial["rodzaj_prawa"] == rp.pk


# --- Krok Verify (widok) ----------------------------------------------------


@pytest.mark.django_db
def test_verify_post_patent_pomija_source_i_zapisuje_pola(
    importer_client, importer_user, charaktery_formalne, typy_kbn, jezyki
):
    session = _patent_session(importer_user)
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})

    response = importer_client.post(
        url,
        {
            "rodzaj_rekordu": "patent",
            "rok": "2024",
            "numer_zgloszenia": "PL999",
            "data_zgloszenia": "2024-05-10",
            "uprawniony": "Politechnika X",
            "wdrozenie": "unknown",
        },
    )
    assert response.status_code == 200
    # Wyrenderowano krok Autorzy (Source pominięty) — nie panel źródła.
    content = response.content.decode()
    assert "Dopasowanie autorów" in content
    assert "Dopasowanie źródła" not in content
    session.refresh_from_db()
    assert session.rodzaj_rekordu == RR.PATENT
    assert session.jest_wydawnictwem_zwartym is False
    assert session.status == ST.VERIFIED
    # Pola patentowe zapisane do normalized_data (kontrakt).
    assert session.normalized_data["patent_number"] == "PL999"
    assert session.normalized_data["filing_date"] == "2024-05-10"
    assert session.normalized_data["patent_holder"] == "Politechnika X"
    assert session.normalized_data["wdrozenie"] is None
    # charakter/typ/jezyk wyzerowane (Patent je hardkoduje).
    assert session.charakter_formalny_id is None
    assert session.typ_kbn_id is None


@pytest.mark.django_db
def test_verify_post_toggle_patent_na_ciagle_idzie_do_source(
    importer_client, importer_user, charaktery_formalne, typy_kbn, jezyki
):
    """Przełączenie auto-wykrytego patentu na 'ciagle' wprowadza w ścieżkę
    nie-patentową (Source)."""
    from bpp.models import Charakter_Formalny, Jezyk, Typ_KBN

    session = _patent_session(importer_user)
    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})
    cf = (
        Charakter_Formalny.objects.filter(ukryty=False)
        .exclude(skrot__in=["D", "H", "PAT"])
        .first()
    )
    response = importer_client.post(
        url,
        {
            "rodzaj_rekordu": "ciagle",
            "rok": "2024",
            "charakter_formalny": cf.pk,
            "typ_kbn": Typ_KBN.objects.first().pk,
            "jezyk": Jezyk.objects.filter(widoczny=True).first().pk,
        },
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.rodzaj_rekordu == RR.CIAGLE
    assert session.charakter_formalny_id == cf.pk


@pytest.mark.django_db
def test_verify_post_patent_czysci_stale_zrodlo_i_pbn(
    importer_client, importer_user, charaktery_formalne, typy_kbn, jezyki
):
    """Toggle CIAGLE→(Source)→PATENT: stale zrodlo/pbn_mongo_id/wydawca_opis
    muszą zostać wyczyszczone (inaczej create patentu by się wywalił)."""
    from model_bakery import baker

    from bpp.models import Zrodlo

    session = _patent_session(importer_user, status=ST.SOURCE_MATCHED)
    session.zrodlo = baker.make(Zrodlo)
    session.matched_data = {"pbn_mongo_id": "deadbeef", "wydawca_opis": "X"}
    session.save()

    url = reverse("importer_publikacji:verify", kwargs={"session_id": session.pk})
    importer_client.post(url, {"rodzaj_rekordu": "patent", "rok": "2024"})

    session.refresh_from_db()
    assert session.zrodlo_id is None
    assert "pbn_mongo_id" not in session.matched_data
    assert "wydawca_opis" not in session.matched_data


# --- get_continue_url -------------------------------------------------------


@pytest.mark.django_db
def test_get_continue_url_patent(importer_user):
    session = _patent_session(importer_user, status=ST.VERIFIED)
    assert "/authors" in session.get_continue_url()
    session.status = ST.PUNKTACJA
    session.save()
    assert "/review" in session.get_continue_url()


# --- Guardy Source/PBN ------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("krok", ["source", "pbn"])
def test_guard_source_pbn_dla_patentu_przekierowuje(
    krok, importer_client, importer_user
):
    session = _patent_session(importer_user, status=ST.VERIFIED)
    url = reverse(f"importer_publikacji:{krok}", kwargs={"session_id": session.pk})
    # GET
    resp_get = importer_client.get(url)
    assert resp_get.status_code == 302
    # POST — nie może zapisać zrodlo/SOURCE_MATCHED
    resp_post = importer_client.post(url, {})
    assert resp_post.status_code == 302
    session.refresh_from_db()
    assert session.zrodlo_id is None
    assert session.status != ST.SOURCE_MATCHED


@pytest.mark.django_db
@pytest.mark.parametrize("krok", ["pbn-select", "pbn-clear"])
def test_guard_pbn_select_clear_dla_patentu(krok, importer_client, importer_user):
    """PbnSelect/PbnClear (POST-only) też mają guard — stale karta nie może
    wpisać pbn_mongo_id na sesji patentowej po wyczyszczeniu."""
    session = _patent_session(importer_user, status=ST.VERIFIED)
    url = reverse(f"importer_publikacji:{krok}", kwargs={"session_id": session.pk})
    resp = importer_client.post(url, {"mongo_id": "deadbeef"})
    assert resp.status_code == 302
    session.refresh_from_db()
    assert "pbn_mongo_id" not in session.matched_data


# --- Punktacja → Review (pomija PBN) ----------------------------------------


@pytest.mark.django_db
def test_punktacja_post_patent_idzie_do_review(importer_client, importer_user):
    session = _patent_session(importer_user, status=ST.AUTHORS_MATCHED)
    url = reverse("importer_publikacji:punktacja", kwargs={"session_id": session.pk})
    response = importer_client.post(url, {"punkty_kbn": "25"})
    assert response.status_code == 200
    # Krok PBN pominięty — treść to przegląd, nie panel PBN.
    content = response.content.decode()
    assert "Przegląd końcowy" in content


# --- Review: brak PBN, back do punktacji ------------------------------------


@pytest.mark.django_db
def test_review_context_patent_bez_pbn(rf, importer_user):
    from importer_publikacji.views.steps import _review_context

    session = _patent_session(importer_user, status=ST.PUNKTACJA)
    request = rf.get("/")
    request.user = importer_user
    ctx = _review_context(request, session)
    assert ctx["is_patent"] is True
    assert "show_save_and_pbn" not in ctx
    assert "punktacja" in ctx["back_step_url"]


# --- Sugestia punktacji dla patentu -----------------------------------------


@pytest.mark.django_db
def test_oblicz_sugestie_patent_brak_sugestii(importer_user):
    from importer_publikacji.views.steps import _oblicz_sugestie

    session = _patent_session(importer_user)
    sugestia, poziom = _oblicz_sugestie(session)
    assert sugestia.punkty is None
    assert poziom is None


# --- Duplikaty widzą Patent -------------------------------------------------


@pytest.mark.django_db
def test_find_duplicates_wykrywa_patent(importer_user, statusy_korekt):
    from model_bakery import baker

    from bpp.models import Patent
    from importer_publikacji.views.steps import _find_duplicates

    tytul = "Sposob wytwarzania unikatowego widgetu przemyslowego"
    baker.make(Patent, tytul_oryginalny=tytul)
    session = _patent_session(importer_user, title=tytul)
    wyniki = _find_duplicates(session)
    assert any(isinstance(pub, Patent) for pub, _ in wyniki)


# --- Ścieżka create: guardy streszczenia / PBN ------------------------------


@pytest.mark.django_db
def test_create_patent_z_abstraktem_nie_wywala_streszczen(
    importer_user, statusy_korekt
):
    """Patent nie ma relacji streszczenia — @patent z abstraktem nie może
    wywalić create na record.streszczenia (guard)."""
    from bpp.models import Patent
    from importer_publikacji.views import _create_publication

    session = _patent_session(
        importer_user,
        abstract="Wynalazek dotyczy sposobu...",
        abstracts=[{"text": "Wynalazek dotyczy sposobu...", "language": None}],
    )
    record = _create_publication(session)
    assert isinstance(record, Patent)


@pytest.mark.django_db
def test_create_patent_ze_stale_pbn_mongo_id_nie_linkuje(importer_user, statusy_korekt):
    """Nawet gdyby pbn_mongo_id przeciekł na sesję patentową, _link_pbn_uid
    NIE jest wołany (Patent nie ma pola pbn_uid) — create się nie wywala."""
    from bpp.models import Patent
    from importer_publikacji.views import _create_publication

    session = _patent_session(importer_user)
    session.matched_data = {"pbn_mongo_id": "deadbeef"}
    session.save()
    record = _create_publication(session)
    assert isinstance(record, Patent)


# --- Guard also_pbn w CreateView --------------------------------------------


@pytest.mark.django_db
def test_create_view_ignoruje_also_pbn_dla_patentu(
    importer_client, importer_user, statusy_korekt, settings
):
    """POST z _create_and_pbn na sesji patentowej nie zleca eksportu PBN —
    matched_data['pbn_export_pending'] pozostaje False."""
    session = _patent_session(importer_user, status=ST.REVIEW)
    url = reverse("importer_publikacji:create", kwargs={"session_id": session.pk})
    # CELERY eager, żeby task poszedł synchronicznie i nie wisiał.
    settings.CELERY_TASK_ALWAYS_EAGER = True
    importer_client.post(url, {"_create_and_pbn": "1"})
    session.refresh_from_db()
    assert session.matched_data.get("pbn_export_pending") is False
