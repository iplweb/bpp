import pytest
from denorm import denorms
from django.db import transaction
from model_bakery import baker

from import_polon.core import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Rekord,
    Wydawnictwo_Zwarte,
)


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_zly_plik(fn_test_import_absencji):
    ROK = 2020
    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )
    analyze_file_import_polon(fn_test_import_absencji, ipp)


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_plik_bez_dyscyplin(
    fn_test_import_polon_bledny,
):
    ROK = 2020
    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )
    baker.make(Autor, nazwisko="Kowalski", imiona="Aleksander Bolesław")
    analyze_file_import_polon(fn_test_import_polon_bledny, ipp)


def test_analyze_excel_file_import_polon(
    transactional_db,
    fn_test_import_polon,
    dyscyplina1,
    zwarte_z_dyscyplinami: Wydawnictwo_Zwarte,
    jednostka,
    uczelnia,  # potrzebna do liczenia slotow, ISlot() uzywa
):
    with transaction.atomic():
        ROK = 2020

        ipp: ImportPlikuPolon = baker.make(
            ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
        )

        # Artur ZN nie ma żadnego wpisu za ten rok
        artur_dyscyplinazn: Autor = baker.make(
            Autor, imiona="Artur", nazwisko="DyscyplinaZN"
        )

        # Dariusz BezN jest w Nce, ale po imporcie ma go nie być.
        dariusz_dyscyplinabezn: Autor = baker.make(
            Autor, imiona="Dariusz", nazwisko="DyscyplinaBezN"
        )
        dariusz_dyscyplinabezn.autor_dyscyplina_set.create(
            rok=ROK,
            dyscyplina_naukowa=dyscyplina1,
            rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
        )

        zwarte_z_dyscyplinami.rok = ROK
        zwarte_z_dyscyplinami.save()

        # Dariusz jest współautorem pracy, ma tam dyscyplinę; po imporcie (rekalkulacji)
        # ma go tam nie być:
        zwarte_z_dyscyplinami.dodaj_autora(
            dariusz_dyscyplinabezn, jednostka, dyscyplina_naukowa=dyscyplina1
        )

        # Przebuduj
        denorms.flush()

        # pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.cached_punkty_dyscyplin()

        rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
        assert Cache_Punktacja_Autora.objects.filter(
            rekord_id=rekord.pk, autor=dariusz_dyscyplinabezn
        ).exists()

        # Stanisław ZN ma za ten rok wpis, ze nie jest w N
        stanislaw_dyscyplinazn: Autor = baker.make(
            Autor, imiona="Stanisław", nazwisko="DyscyplinaZN"
        )

        stanislaw_dyscyplinazn.autor_dyscyplina_set.create(
            rok=ROK,
            dyscyplina_naukowa=dyscyplina1,
            rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.Z,
        )

        analyze_file_import_polon(fn_test_import_polon, ipp)

        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.N
        )
        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).dyscyplina_naukowa
            == dyscyplina1
        )

        assert (
            dariusz_dyscyplinabezn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.Z
        )

        assert (
            stanislaw_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.N
        )
    denorms.flush()

    assert Cache_Punktacja_Autora.objects.filter(
        rekord_id=rekord.pk, autor=dariusz_dyscyplinabezn
    ).exists()  # dla autora "Z" też liczymy.
