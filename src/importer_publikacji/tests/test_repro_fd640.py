"""FD#640: dyscyplina ze zgłoszenia staje się przypisaniem autora dopiero
po zatwierdzeniu zgłoszenia przez redakcję (importer publikacji).

Zapis zgłoszenia (także przez niezalogowanego) przechowuje wybraną dyscyplinę
wyłącznie jako propozycję w ``Zgloszenie_Publikacji_Autor``. Importer
podpowiada ją redaktorowi (``_prefill_dyscypliny_z_zgloszen``), a przy
tworzeniu rekordu zakłada brakujące ``Autor_Dyscyplina`` w imieniu redaktora
(``przypisz_brakujace_dyscypliny``).
"""

import pytest
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Autor_Jednostka
from importer_publikacji.models import ImportedAuthor
from importer_publikacji.tests.test_views_create_publication import (
    _make_session_for_publication,
)
from importer_publikacji.views import _create_publication
from importer_publikacji.views.authors import _prefill_dyscypliny_z_zgloszen
from zglos_publikacje.models import Zgloszenie_Publikacji
from zglos_publikacje.tests.tests_zglos_publikacje import (
    _krok2_dane,
    _przejdz_do_kroku_danych,
)

ROK = 2020  # rok z _krok2_dane


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
    sesja.normalized_data["title"] = "Mastitis"
    sesja.normalized_data["year"] = ROK
    sesja.save()
    return sesja


def _zglos(webtest_app, captured, autor, jednostka, dyscyplina):
    page = _przejdz_do_kroku_danych(webtest_app, rodzaj="POZOSTALE")
    page = _krok2_dane(page, tytul="Mastitis", strona_www="https://example.com/")
    page2 = page.forms[0].submit()
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    page2.forms[0]["3-0-dyscyplina_naukowa"].force_value(dyscyplina.pk)
    with captured(execute=True):
        page2.forms[0].submit().maybe_follow()
    return Zgloszenie_Publikacji.objects.get()


@pytest.mark.django_db
def test_dyscyplina_przypisana_dopiero_po_zatwierdzeniu_w_importerze(
    webtest_app,
    django_capture_on_commit_callbacks,
    sesja,
    uczelnia,
    jednostka,
    dyscyplina1,
):
    autor = baker.make(Autor, nazwisko="Burmańczuk", imiona="Artur")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)

    # Zgłoszenie przez niezalogowanego: dyscyplina tylko jako propozycja.
    zgloszenie = _zglos(
        webtest_app, django_capture_on_commit_callbacks, autor, jednostka, dyscyplina1
    )
    assert zgloszenie.zgloszenie_publikacji_autor_set.get().dyscyplina_naukowa == (
        dyscyplina1
    )
    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()

    # Redakcja zatwierdza zgłoszenie w importerze.
    sesja.zgloszenie = zgloszenie
    sesja.save()
    imported = baker.make(
        ImportedAuthor,
        session=sesja,
        order=0,
        family_name="Burmańczuk",
        given_name="Artur",
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=autor,
        matched_jednostka=jednostka,
        zapisany_jako="Burmańczuk Artur",
    )
    _prefill_dyscypliny_z_zgloszen(sesja)
    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina1
    assert imported.dyscyplina_source == ImportedAuthor.DyscyplinaSource.ZGLOSZENIE
    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()

    redaktor = baker.make("bpp.BppUser", username="redaktor")
    record = _create_publication(sesja, redaktor)

    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina1
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina1
    wpis = LogEntry.objects.get(
        content_type=ContentType.objects.get_for_model(ad), object_id=str(ad.pk)
    )
    assert wpis.action_flag == ADDITION
    assert wpis.user == redaktor


@pytest.mark.django_db
def test_obcy_z_obca_jednostka_bez_afiliacji(
    sesja, uczelnia_z_obca_jednostka, obca_jednostka
):
    """Punkt 4: importer zapisuje autora z jednostką obcą bez afiliacji."""
    sesja.uczelnia = uczelnia_z_obca_jednostka
    sesja.save()
    autor = baker.make(Autor, nazwisko="Yilmaz", imiona="Oktay")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    baker.make(
        ImportedAuthor,
        session=sesja,
        order=0,
        family_name="Yilmaz",
        given_name="Oktay",
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=autor,
        matched_jednostka=obca_jednostka,
        zapisany_jako="Yilmaz Oktay",
    )
    record = _create_publication(sesja)
    autorstwo = record.autorzy_set.get()
    assert autorstwo.jednostka == obca_jednostka
    assert autorstwo.afiliuje is False


def _imported(sesja, autor, jednostka=None, **kw):
    return baker.make(
        ImportedAuthor,
        session=sesja,
        order=0,
        family_name=autor.nazwisko,
        given_name=autor.imiona,
        match_status=ImportedAuthor.MatchStatus.MANUAL,
        matched_autor=autor,
        matched_jednostka=jednostka,
        zapisany_jako=f"{autor.nazwisko} {autor.imiona}",
        **kw,
    )


@pytest.mark.django_db
def test_odpiety_od_uczelni_nie_dostaje_dyscypliny_ze_zgloszenia(
    webtest_app,
    django_capture_on_commit_callbacks,
    sesja,
    uczelnia,
    jednostka,
    dyscyplina1,
):
    """Redakcja odpina autora od jedynej jednostki uczelni PO wczytaniu
    zgłoszenia do importera — zapamiętana propozycja dyscypliny nie może
    założyć mu ``Autor_Dyscyplina`` (nie jest już autorem uczelni)."""
    from django.core.exceptions import ValidationError

    from importer_publikacji.dyscypliny import (
        autorzy_spoza_uczelni_bez_prawa_do_dyscypliny,
        przypisz_brakujace_dyscypliny,
    )

    autor = baker.make(Autor, nazwisko="Burmańczuk", imiona="Artur")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    zgloszenie = _zglos(
        webtest_app, django_capture_on_commit_callbacks, autor, jednostka, dyscyplina1
    )
    sesja.zgloszenie = zgloszenie
    sesja.save()
    imported = _imported(sesja, autor, jednostka)
    _prefill_dyscypliny_z_zgloszen(sesja)
    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina1

    # Redakcja odpina autora od uczelni.
    Autor_Jednostka.objects.filter(autor=autor).delete()
    Autor.objects.filter(pk=autor.pk).update(aktualna_jednostka=None)

    assert autorzy_spoza_uczelni_bez_prawa_do_dyscypliny(sesja) == [imported]
    with pytest.raises(ValidationError, match="autorom spoza uczelni"):
        _create_publication(sesja)
    # Bezpiecznik także w samym zakładaniu przypisań.
    with pytest.raises(ValidationError, match="autorom spoza uczelni"):
        przypisz_brakujace_dyscypliny(sesja, type("R", (), {"rok": ROK})(), None)
    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()


@pytest.mark.django_db
def test_operator_wybiera_dyscypline_nowemu_pracownikowi(
    sesja, uczelnia, jednostka, dyscyplina1
):
    """FD#620 bez zmian: operator importu wybiera dyscyplinę autorowi bez
    przypisań i dopasowuje go do jednostki uczelni — przypisanie powstaje
    (zapis pracy i tak dopisze mu tę jednostkę)."""
    autor = baker.make(Autor, nazwisko="Nowy", imiona="Pracownik")
    _imported(
        sesja,
        autor,
        jednostka,
        matched_dyscyplina=dyscyplina1,
        dyscyplina_source=ImportedAuthor.DyscyplinaSource.MANUAL,
    )
    record = _create_publication(sesja)
    assert Autor_Dyscyplina.objects.filter(autor=autor, rok=ROK).exists()
    assert record.autorzy_set.get().dyscyplina_naukowa == dyscyplina1


@pytest.mark.django_db
def test_operator_nie_przypisze_dyscypliny_obcemu_z_obca_jednostka(
    sesja, uczelnia_z_obca_jednostka, obca_jednostka, dyscyplina1
):
    from django.core.exceptions import ValidationError

    sesja.uczelnia = uczelnia_z_obca_jednostka
    sesja.save()
    autor = baker.make(Autor, nazwisko="Yilmaz", imiona="Oktay")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    _imported(
        sesja,
        autor,
        obca_jednostka,
        matched_dyscyplina=dyscyplina1,
        dyscyplina_source=ImportedAuthor.DyscyplinaSource.MANUAL,
    )
    with pytest.raises(ValidationError, match="autorom spoza uczelni"):
        _create_publication(sesja)
    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()


@pytest.mark.django_db
def test_prefill_obcemu_z_jednostka_innej_uczelni_daje_obca(
    sesja, uczelnia_z_obca_jednostka, obca_jednostka
):
    """FD#640 (A): stare zgłoszenie z jednostką innej uczelni przy obcym
    autorze — importer podpowiada obcą jednostkę, rekord bez afiliacji."""
    from bpp.models import Jednostka, Uczelnia
    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    sesja.uczelnia = uczelnia_z_obca_jednostka
    sesja.save()
    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    jednostka_innej = baker.make(
        Jednostka, uczelnia=inna, skupia_pracownikow=True, parent=None
    )
    autor = baker.make(Autor, nazwisko="Yilmaz", imiona="Oktay")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    zgloszenie = baker.make(Zgloszenie_Publikacji, tytul_oryginalny="Mastitis")
    zpa = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        rekord=zgloszenie,
        autor=autor,
        jednostka=jednostka_innej,
        rok=ROK,
        _save_related=True,
    )
    zpa.save(**{"__disable_bmoa_clean_method": True})
    sesja.zgloszenie = zgloszenie
    sesja.save()
    imported = _imported(sesja, autor)

    _prefill_dyscypliny_z_zgloszen(sesja)
    imported.refresh_from_db()
    assert imported.matched_jednostka == obca_jednostka

    autorstwo = _create_publication(sesja).autorzy_set.get()
    assert autorstwo.jednostka == obca_jednostka
    assert autorstwo.afiliuje is False
