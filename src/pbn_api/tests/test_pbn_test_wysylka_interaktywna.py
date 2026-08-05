"""Testy dla interaktywnego narzędzia CLI ``pbn_test_wysylka_interaktywna``.

Narzędzie jest interaktywne i używa wejścia przez ``input()``.
W testach mockujemy ``builtins.input`` przez ``monkeypatch``, a transport
HTTP przez ``MockTransport`` dostarczany przez fixturę ``pbn_client``.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pbn_client.const import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)

from fixtures.pbn_api import pbn_pageable_json
from pbn_api.exceptions import HttpException
from pbn_api.management.commands import pbn_test_wysylka_interaktywna as cmd_mod


def _patch_get_client(monkeypatch, pbn_client):
    """Zamienia Command.get_client() żeby zwracał mockowanego klienta."""
    monkeypatch.setattr(
        cmd_mod.Command,
        "get_client",
        lambda self, *args, **kwargs: pbn_client,
    )


def _patch_input(monkeypatch, answers):
    """Mockuje builtins.input — zwraca kolejno podane odpowiedzi.

    Po wyczerpaniu listy zwraca pusty string (Enter = kontynuuj).
    """
    it = iter(answers)

    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            return ""

    monkeypatch.setattr("builtins.input", _input)


def _patch_intended_statements(monkeypatch, statements):
    """Patchuje adapter żeby zwracał zadaną listę intended statements.

    Patch dotyczy:
    - ``pbn_get_json_statements`` — używana w KROK 6/8 (porównanie).
      Zwraca surową listę dict-ów (każdy może mieć personObjectId,
      disciplineId, disciplineUuid, type itd.).
    - ``pbn_get_api_statements`` — używana w KROK 8/8 (POST /v2/statements).
      Zwraca ``{"publicationUuid": ..., "statements": [...]}``.
    - ``__init__`` — dodatkowo ustawia ``pbn_wysylaj_bez_oswiadczen=True``
      na instancji. Potrzebne gdy ``statements=[]``: inaczej ``pbn_get_json``
      w KROK 2/8 wywoła ``StatementsMissing`` (bo artykuł/rozdział bez
      statements jest walidowany jako błąd). W testach chcemy móc
      symulować każdy stan — flaga wyłącza walidację.

    Fixture testowy ``pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina`` nie
    tworzy ``PublikacjaInstytucji_V2``, bez czego ``pbn_get_api_statements``
    rzuciłoby ``DaneLokalneWymagajaAktualizacjiException``.
    """
    from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter

    statements_list = list(statements)
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_json_statements",
        lambda self, _lst=None: list(statements_list),
    )
    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_api_statements",
        lambda self: {
            "publicationUuid": "00000000-0000-0000-0000-000000000001",
            "statements": list(statements_list),
        },
    )
    original_init = WydawnictwoPBNAdapter.__init__

    def patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.pbn_wysylaj_bez_oswiadczen = True

    monkeypatch.setattr(WydawnictwoPBNAdapter, "__init__", patched_init)


@pytest.mark.django_db
def test_wymaga_jednego_argumentu_publikacji(pbn_client, monkeypatch):
    _patch_get_client(monkeypatch, pbn_client)
    _patch_input(monkeypatch, [])

    with pytest.raises(CommandError, match="dokładnie jedno"):
        call_command(
            "pbn_test_wysylka_interaktywna",
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_oba_argumenty_publikacji_to_blad(pbn_client, monkeypatch):
    _patch_get_client(monkeypatch, pbn_client)
    _patch_input(monkeypatch, [])

    with pytest.raises(CommandError, match="dokładnie jedno"):
        call_command(
            "pbn_test_wysylka_interaktywna",
            "--wydawnictwo-zwarte",
            "1",
            "--wydawnictwo-ciagle",
            "2",
            stdout=StringIO(),
        )


@pytest.mark.django_db
def test_nieistniejaca_publikacja_zwarte(pbn_client, monkeypatch):
    _patch_get_client(monkeypatch, pbn_client)
    _patch_input(monkeypatch, [])
    out = StringIO()

    with pytest.raises(CommandError, match="Nie znaleziono"):
        call_command(
            "pbn_test_wysylka_interaktywna",
            "--wydawnictwo-zwarte",
            "999999",
            stdout=out,
        )


@pytest.mark.django_db
def test_dry_run_nie_wysyla_niczego_do_pbn(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """W trybie --dry-run żadne żądanie HTTP nie może wyjść przez transport."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    _patch_intended_statements(monkeypatch, [])
    # kolejność promptów: preview JSON? n, wybór endpointa=1, [Enter]-y
    _patch_input(monkeypatch, ["n", "1"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--dry-run",
        "--yes-all",
        stdout=out,
    )

    assert pbn_client.transport.input_values == {}, (
        "W trybie --dry-run transport nie powinien dostać żadnego żądania."
    )
    output = out.getvalue()
    assert "DRY-RUN" in output
    assert "KROK 1/8" in output
    assert "PODSUMOWANIE" in output


@pytest.mark.django_db
def test_happy_path_endpoint_publications(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Pełen przebieg z endpointem /api/v1/publications (all-in-one)."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    # Intended statements puste — tak samo jak PBN → identyczne → domyślnie
    # nie robimy DELETE ani POST oświadczeń (default_act=False w yes_all).
    _patch_intended_statements(monkeypatch, [])
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json([])

    # --yes-all akceptuje domyślnie (Enter, yes/no z defaultem), a dla
    # wyboru endpointu (niedomyślny prompt) musimy dostarczyć "1".
    _patch_input(monkeypatch, ["1"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    # POST publikacji faktycznie poszedł do endpointu publications:
    assert PBN_POST_PUBLICATIONS_URL in pbn_client.transport.input_values
    # Endpoint repozytoryjny nie powinien być użyty:
    assert (
        PBN_POST_PUBLICATION_NO_STATEMENTS_URL not in pbn_client.transport.input_values
    )
    # Porównanie oświadczeń - lokalne puste, PBN puste - identyczne,
    # więc DELETE i POST /v2/statements NIE powinny się odbyć:
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values

    output = out.getvalue()
    assert "PODSUMOWANIE" in output
    assert "KROK 4/8" in output
    assert "identyczne" in output


@pytest.mark.django_db
def test_happy_path_endpoint_repositorium(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Pełen przebieg z endpointem /api/v1/repositorium/publications (bez oświadczeń)."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    _patch_intended_statements(monkeypatch, [])
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk},
    ]
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json([])

    _patch_input(monkeypatch, ["2"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    # POST faktycznie do repozytorium:
    assert PBN_POST_PUBLICATION_NO_STATEMENTS_URL in pbn_client.transport.input_values
    # Endpoint all-in-one NIE powinien być użyty:
    assert PBN_POST_PUBLICATIONS_URL not in pbn_client.transport.input_values

    # Dodatkowo: body wysłane do repozytorium NIE ma klucza "statements" — to
    # kluczowa gwarancja bezpieczeństwa narzędzia (user zastrzegł: żadnych
    # nie-spec wysyłek z `statements` na endpoint repozytoryjny).
    body = pbn_client.transport.input_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL][
        "body"
    ]
    assert isinstance(body, list) and len(body) == 1
    assert "statements" not in body[0]


@pytest.mark.django_db
def test_nieprawidlowa_opcja_endpointa_potem_prawidlowa(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Po błędnej odpowiedzi na wybór endpointa pętla prosi ponownie."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    _patch_intended_statements(monkeypatch, [])
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json([])

    # najpierw bzdura, potem 1 (publications)
    _patch_input(monkeypatch, ["foo", "1"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    output = out.getvalue()
    assert "Nieprawidłowa opcja" in output
    assert PBN_POST_PUBLICATIONS_URL in pbn_client.transport.input_values


@pytest.mark.django_db
def test_quit_przy_wyborze_endpointa_konczy_flow(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    _patch_input(monkeypatch, ["q"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    # Nic nie wyszło do transportu:
    assert pbn_client.transport.input_values == {}
    output = out.getvalue()
    assert "Przerwano" in output
    assert "PODSUMOWANIE" in output


@pytest.mark.django_db
def test_blad_http_na_post_publikacji_nie_crashuje(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Gdy POST publikacji zwróci HttpException 423, narzędzie ma czytelnie
    wypisać błąd i wrócić do podsumowania (nie robić traceback-crash)."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = HttpException(
        423,
        PBN_POST_PUBLICATIONS_URL,
        '{"message":"Locked","description":"Zablokowane"}',
    )

    _patch_input(monkeypatch, ["1"])

    out = StringIO()
    # Komenda powinna zakończyć się bez wyjątku — UserAbort jest łapany w handle().
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    output = out.getvalue()
    assert "HTTP 423" in output
    assert "PODSUMOWANIE" in output
    # DELETE i POST /v2/statements NIE powinny się wykonać po błędzie:
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values


@pytest.mark.django_db
def test_rozne_oswiadczenia_triggeruja_delete_post_gdy_user_zgodzi(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    monkeypatch,
):
    """Gdy lokalne oświadczenia różnią się od PBN i user zgodzi się,
    narzędzie wysyła DELETE a następnie POST /v2/statements."""
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    # PBN zwraca 1 oświadczenie, które lokalnie nie istnieje → różnica
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json(
        [
            {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "addedTimestamp": "2020.05.06",
                "institutionId": pbn_jednostka.pbn_uid_id,
                "personId": pbn_autor.pbn_uid_id,
                "publicationId": pbn_publication.pk,
                "area": "999",
                "inOrcid": True,
                "type": "AUTHOR",
            }
        ]
    )
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    pbn_client.transport.return_values[url_delete] = []
    pbn_client.transport.return_values[PBN_POST_INSTITUTION_STATEMENTS_URL] = {
        "data": []
    }

    # Podmieniamy pbn_get_api_statements żeby nie wymagał PublikacjaInstytucji_V2
    # (ten fixture go nie tworzy). Zwracamy sztuczny payload.
    from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter

    monkeypatch.setattr(
        WydawnictwoPBNAdapter,
        "pbn_get_api_statements",
        lambda self: {
            "publicationUuid": "00000000-0000-0000-0000-000000000001",
            "statements": [{"personId": "x"}],
        },
    )

    # 1=publications, 't'=tak (skasuj i wyślij)
    _patch_input(monkeypatch, ["1", "t"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )

    # DELETE i POST /v2/statements poszły:
    assert url_delete in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL in pbn_client.transport.input_values
    assert pbn_client.transport.input_values[url_delete]["delete"] is True

    output = out.getvalue()
    assert "KROK 7/8" in output
    assert "KROK 8/8" in output


@pytest.mark.django_db
def test_odmowa_delete_post_gdy_sa_roznice_ale_user_nie_chce(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    monkeypatch,
):
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json(
        [
            {
                "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "institutionId": pbn_jednostka.pbn_uid_id,
                "personId": pbn_autor.pbn_uid_id,
                "publicationId": pbn_publication.pk,
                "area": "999",
                "inOrcid": True,
                "type": "AUTHOR",
            }
        ]
    )

    # Pełen flow bez --yes-all, bo chcemy dać user-owi odpowiedź "n" na
    # dwa pytania (DELETE i POST). yes_all ignoruje decyzje yes/no i
    # wraca do defaultów, a default_act=True (są różnice) → DELETE+POST
    # by się wykonały. Lista odpowiedzi (po kolei):
    #   1) Enter po KROK 1
    #   2) "" (n na preview JSON, default=False)
    #   3) Enter po KROK 2
    #   4) "1" — wybór endpointa: all-in-one
    #   5) "" (Wyślij teraz? default=True)
    #   6) Enter po KROK 4
    #   7) Enter po KROK 5
    #   8) Enter po KROK 6
    #   9) "n" — nie kasuj oświadczeń (DELETE)
    #  10) "n" — nie wysyłaj oświadczeń (POST)
    _patch_input(monkeypatch, ["", "", "", "1", "", "", "", "", "n", "n"])

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        stdout=out,
    )

    # DELETE nie powinien się wykonać:
    url_delete = PBN_DELETE_PUBLICATION_STATEMENT.format(
        publicationId=pbn_publication.pk
    )
    assert url_delete not in pbn_client.transport.input_values
    assert PBN_POST_INSTITUTION_STATEMENTS_URL not in pbn_client.transport.input_values

    output = out.getvalue()
    assert "decyzja użytkownika" in output


@pytest.mark.django_db
def test_compare_uses_intended_not_cache_bug1(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    pbn_autor,
    pbn_jednostka,
    monkeypatch,
):
    """Regression BUG 1: narzędzie ma porównywać intended (adapter) z PBN,
    NIE cache OswiadczenieInstytucji.

    Scenariusz: cache (OswiadczenieInstytucji) ma 1 rekord (stary stan),
    PBN zwraca ten sam 1 rekord. Intended z adaptera zwraca PUSTĄ listę
    (user skasował autora lokalnie). Stary kod pokazałby "identyczne"
    (cache 1 == PBN 1). Nowy kod musi pokazać "różnice" (intended 0 ≠ PBN 1).
    """
    from datetime import date

    from model_bakery import baker

    from pbn_api.models import OswiadczenieInstytucji

    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    # Cache (stary stan, niesprzątnięty) — 1 rekord OswiadczenieInstytucji:
    baker.make(
        OswiadczenieInstytucji,
        publicationId=pbn_publication,
        personId=pbn_autor.pbn_uid,
        institutionId=pbn_jednostka.pbn_uid,
        area=100,
        addedTimestamp=date(2020, 1, 1),
    )
    assert OswiadczenieInstytucji.objects.count() == 1

    # Intended BPP (live) — PUSTE (jakby user skasował autora z rekordu):
    _patch_intended_statements(monkeypatch, [])

    _patch_get_client(monkeypatch, pbn_client)
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    # PBN zwraca 1 oświadczenie (zgodne z cache):
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json(
        [
            {
                "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "institutionId": pbn_jednostka.pbn_uid_id,
                "personId": pbn_autor.pbn_uid_id,
                "publicationId": pbn_publication.pk,
                "area": "100",
                "type": "AUTHOR",
                "inOrcid": True,
            }
        ]
    )

    # Wybieramy endpoint 1, nie kasujemy/nie wysyłamy (chcemy sprawdzić
    # tylko KROK 6/8 output).
    _patch_input(
        monkeypatch,
        ["", "", "", "1", "", "", "", "", "n", "n"],
    )

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        stdout=out,
    )

    output = out.getvalue()
    # Musi pokazać intencja 0 vs PBN 1 → różnice (NIE identyczne):
    assert "Intencja BPP (live):          0" in output
    assert "Aktualnie w PBN:              1" in output
    assert "Tylko w PBN (do usunięcia):    1" in output
    # A NIE pokazać że są identyczne (to byłby stary bug):
    assert "Porównanie                     → różnice" in output


def test_json_truncated_obcina_dlugi_tekst():
    big = {"key": "x" * 5000}
    result = cmd_mod._json_truncated(big, max_len=100)
    assert len(result) < 500
    assert "obcięto" in result


def test_json_truncated_nie_obcina_krotkiego_tekstu():
    small = {"a": 1}
    result = cmd_mod._json_truncated(small, max_len=100)
    assert "obcięto" not in result
    assert '"a": 1' in result


@pytest.mark.django_db
def test_niejednoznaczny_objectId_glosno_krzyczy_i_przerywa(
    pbn_client,
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina,
    pbn_publication,
    monkeypatch,
):
    """Repozytorium zwraca listę != 1 element → pakietowe
    ``decode_publication_object_id`` rzuca zamiast po cichu zwracać None.

    Narzędzie łapie to głośno (pokazuje błąd + surową odpowiedź) i pyta czy
    kontynuować. Pod ``--yes-all`` pytanie idzie na default (False = nie) →
    flow przerywany, zamiast jechać dalej z ``objectId=None``.
    """
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pbn_uid = pbn_publication
    pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.save()

    _patch_get_client(monkeypatch, pbn_client)
    _patch_intended_statements(monkeypatch, [])
    # Dwa elementy — sytuacja niejednoznaczna (spodziewamy się dokładnie 1):
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = [
        {"id": pbn_publication.pk},
        {"id": pbn_publication.pk},
    ]
    _patch_input(monkeypatch, ["2"])  # endpoint repozytoryjny

    out = StringIO()
    call_command(
        "pbn_test_wysylka_interaktywna",
        "--wydawnictwo-zwarte",
        str(pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.pk),
        "--yes-all",
        stdout=out,
    )
    output = out.getvalue()
    assert "Nie mogę zdekodować objectId" in output
    assert "Przerwano przez użytkownika." in output
    # Nie dobił do GET oświadczeń (KROK 5) — przerwał już na dekodowaniu:
    assert not any(
        k.startswith(PBN_GET_INSTITUTION_STATEMENTS)
        for k in pbn_client.transport.input_values
    )


def test_extract_object_id_niejednoznaczny_kontynuacja_zwraca_none(monkeypatch):
    """Gałąź „kontynuuj mimo błędu": user zgadza się jechać dalej →
    ``_extract_object_id`` zwraca None (zamiast rzucać UserAbort)."""
    from django.core.management.base import OutputWrapper

    cmd = cmd_mod.Command()
    cmd.stdout = OutputWrapper(StringIO())
    monkeypatch.setattr(cmd, "_prompt_yes_no", lambda *args, **kwargs: True)

    result = cmd._extract_object_id(
        [{"id": 1}, {"id": 2}], endpoint_choice="repositorium"
    )
    assert result is None
