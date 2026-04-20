"""Testy dla interaktywnego narzędzia CLI ``pbn_test_wysylka_interaktywna``.

Narzędzie jest interaktywne i używa wejścia przez ``input()``.
W testach mockujemy ``builtins.input`` przez ``monkeypatch``, a transport
HTTP przez ``MockTransport`` dostarczany przez fixturę ``pbn_client``.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from fixtures.pbn_api import pbn_pageable_json
from pbn_api.const import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
    PBN_POST_PUBLICATION_NO_STATEMENTS_URL,
    PBN_POST_PUBLICATIONS_URL,
)
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
    pbn_client.transport.return_values[PBN_POST_PUBLICATIONS_URL] = {
        "objectId": pbn_publication.pk,
    }
    pbn_client.transport.return_values[
        PBN_GET_INSTITUTION_STATEMENTS
        + f"?publicationId={pbn_publication.pk}&size=5120"
    ] = pbn_pageable_json([])

    # --yes-all akceptuje domyślnie, a dla wyboru endpointu robimy wejście "1"
    # — _prompt w trybie yes-all zwraca "", a _step_choose_endpoint wtedy
    # pętli dopóki nie dostanie prawidłowej odpowiedzi; dlatego wstrzykujemy "1".
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

    # Pełen flow bez --yes-all, bo chcemy dać user-owi odpowiedź "n" na pytanie
    # o skasowanie oświadczeń (yes_all ignoruje decyzje yes/no i wraca do defaultów).
    # Lista odpowiedzi (po kolei):
    #   1) Enter po KROK 1
    #   2) "" (n na preview JSON, default=False)
    #   3) Enter po KROK 2
    #   4) "1" — wybór endpointa: all-in-one
    #   5) "" (Wyślij teraz? default=True)
    #   6) Enter po KROK 4
    #   7) Enter po KROK 5
    #   8) Enter po KROK 6
    #   9) "n" — nie kasuj oświadczeń
    _patch_input(monkeypatch, ["", "", "", "1", "", "", "", "", "n"])

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
