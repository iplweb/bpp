"""FD#623: importer — tworzenie rekordu wywracało się na dyscyplinie autora.

Sesja importu rozdziału (CrossRef) z rokiem 2027 kończyła się w ostatnim
kroku błędem „Autor nie ma przypisania na dany rok do takiej dyscypliny."
z wnętrza tworzenia rekordu — bez wskazania, którego autora to dotyczy.

- autor BEZ przypisania na rok pracy: przypisanie zakłada importer (FD#620),
  rekord powstaje,
- autor Z przypisaniem na rok pracy, ale do innej dyscypliny: przed
  utworzeniem rekordu (przegląd, ``CreateView.post``) operator dostaje listę
  takich autorów z odnośnikami do ich stron w module redagowania; nic nie
  jest zapisywane, sesja zostaje na przeglądzie, task nie startuje.
"""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Wydawnictwo_Zwarte
from importer_publikacji.dyscypliny import autorzy_z_niezgodna_dyscyplina
from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.tests.test_views_create_publication import (
    _make_session_for_publication,
)
from importer_publikacji.views import _create_publication

ROK = 2027


@pytest.fixture
def sesja(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    sesja = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )
    sesja.normalized_data["year"] = ROK
    sesja.normalized_data["doi"] = "10.1016/b978-0-12-819517-8.00012-6"
    sesja.jest_wydawnictwem_zwartym = True
    sesja.rodzaj_rekordu = ImportSession.RodzajRekordu.ZWARTE
    sesja.status = ImportSession.Status.REVIEW
    sesja.save()
    return sesja


@pytest.fixture
def autor():
    return baker.make(Autor, nazwisko="Kowalska", imiona="Anna")


def _dopasuj(sesja, autor, jednostka, dyscyplina):
    return baker.make(
        ImportedAuthor,
        session=sesja,
        order=0,
        family_name="Kowalska",
        given_name="Anna",
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=autor,
        matched_jednostka=jednostka,
        matched_dyscyplina=dyscyplina,
        zapisany_jako="Kowalska Anna",
    )


@pytest.mark.django_db
def test_autor_bez_przypisania_na_2027_rekord_powstaje(
    sesja, autor, jednostka, dyscyplina1
):
    """Dokładnie scenariusz zgłoszenia: autor ma dyscyplinę na rok
    wcześniejszy, na 2027 — żadnej; operator wybrał dyscyplinę w imporcie."""
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK - 1, dyscyplina_naukowa=dyscyplina1
    )
    _dopasuj(sesja, autor, jednostka, dyscyplina1)
    assert autorzy_z_niezgodna_dyscyplina(sesja) == []

    record = _create_publication(sesja)

    assert isinstance(record, Wydawnictwo_Zwarte)
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina1
    assert Autor_Dyscyplina.objects.get(autor=autor, rok=ROK).dyscyplina_naukowa == (
        dyscyplina1
    )


@pytest.fixture
def autor_z_inna_dyscyplina(sesja, autor, jednostka, dyscyplina1, dyscyplina2):
    """Autor przypisany na 2027 do ``dyscyplina2``, w imporcie ``dyscyplina1``."""
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina2
    )
    return _dopasuj(sesja, autor, jednostka, dyscyplina1)


@pytest.mark.django_db
def test_create_publication_czytelny_blad_bez_zapisu(sesja, autor_z_inna_dyscyplina):
    with pytest.raises(ValidationError) as exc:
        _create_publication(sesja)

    komunikat = " ".join(exc.value.messages)
    assert "Kowalska Anna" in komunikat
    assert f"na rok {ROK}" in komunikat
    assert not Wydawnictwo_Zwarte.objects.exists()


@pytest.fixture
def operator_client(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True, is_superuser=True)
    client.force_login(user)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize("htmx", [False, True])
def test_przeglad_pokazuje_autorow_z_odnosnikami_i_nie_startuje_taska(
    operator_client, sesja, autor, autor_z_inna_dyscyplina, dyscyplina2, htmx
):
    headers = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    with patch("importer_publikacji.views.wizard.create_publication_task") as task:
        response = operator_client.post(
            reverse("importer_publikacji:create", kwargs={"session_id": sesja.pk}),
            {},
            **headers,
        )

    task.delay.assert_not_called()
    sesja.refresh_from_db()
    assert sesja.status == ImportSession.Status.REVIEW
    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="autorzy-niezgodna-dyscyplina"' in html
    url_autora = reverse("admin:bpp_autor_change", args=(autor.pk,))
    assert f'href="{url_autora}" target="_blank"' in html
    assert str(dyscyplina2) in html
    assert reverse("importer_publikacji:authors", args=(sesja.pk,)) in html
    assert "Utwórz publikację" in html


@pytest.mark.django_db
def test_po_poprawce_przypisania_task_startuje(
    operator_client, sesja, autor, autor_z_inna_dyscyplina, dyscyplina1
):
    Autor_Dyscyplina.objects.filter(autor=autor, rok=ROK).update(
        subdyscyplina_naukowa=dyscyplina1
    )
    with patch("importer_publikacji.views.wizard.create_publication_task") as task:
        task.delay.return_value.id = "abc"
        operator_client.post(
            reverse("importer_publikacji:create", kwargs={"session_id": sesja.pk}), {}
        )

    task.delay.assert_called_once()


@pytest.mark.django_db
def test_strona_bledu_taska_pokazuje_liste_i_ponow(
    operator_client, sesja, autor, autor_z_inna_dyscyplina
):
    """Gdy przypisania zmieniły się już po kliknięciu „Utwórz" — strona błędu
    taska też pokazuje autorów z odnośnikami i „Spróbuj ponownie"."""
    sesja.status = ImportSession.Status.IMPORT_FAILED
    sesja.last_failed_stage = "create"
    sesja.last_error_message = "Problem danych wejściowych"
    sesja.save()

    response = operator_client.get(
        reverse("importer_publikacji:task-status", kwargs={"session_id": sesja.pk})
    )

    html = response.content.decode()
    assert 'id="autorzy-niezgodna-dyscyplina"' in html
    assert reverse("admin:bpp_autor_change", args=(autor.pk,)) in html
    assert "Spróbuj ponownie" in html


@pytest.mark.django_db
def test_subdyscyplina_na_rok_nie_jest_problemem(
    sesja, autor, jednostka, dyscyplina1, dyscyplina2
):
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=ROK,
        dyscyplina_naukowa=dyscyplina2,
        subdyscyplina_naukowa=dyscyplina1,
    )
    _dopasuj(sesja, autor, jednostka, dyscyplina1)

    assert autorzy_z_niezgodna_dyscyplina(sesja) == []
    record = _create_publication(sesja)
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina1


@pytest.mark.django_db
def test_autor_bez_dyscypliny_w_imporcie_nie_jest_problemem(
    sesja, autor, jednostka, dyscyplina2
):
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina2
    )
    _dopasuj(sesja, autor, jednostka, None)

    assert autorzy_z_niezgodna_dyscyplina(sesja) == []
    _create_publication(sesja)
