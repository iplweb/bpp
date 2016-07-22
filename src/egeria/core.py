# -*- encoding: utf-8 -*-


from bpp.models.autor import Tytul, Funkcja_Autora
from bpp.models.struktura import Wydzial
from egeria import models as egeria_models

def diff_nazwa_i_skrot(egeria_import, nazwa_kolumny_w_egerii, klasa, nazwa_kolumny_w_klasie):
    current_import = egeria_import.rows()

    wartosci_w_xls = current_import.values(nazwa_kolumny_w_egerii).distinct()

    create_obj = egeria_models.__dict__['Diff_%s_Create' % klasa.__name__]
    # ACTION_CREATE
    nowe_rekordy = wartosci_w_xls.exclude(tytul_stopien__in=klasa.objects.all().values(nazwa_kolumny_w_klasie))
    for elem in nowe_rekordy:
        create_obj.objects.create(parent=egeria_import, nazwa_skrot=elem[nazwa_kolumny_w_egerii])

    delete_obj = egeria_models.__dict__['Diff_%s_Delete' % klasa.__name__]
    # ACTION_DELETE
    rekordy_do_usuniecia = klasa.objects.all().exclude(skrot__in=wartosci_w_xls.values(nazwa_kolumny_w_egerii))
    for elem in rekordy_do_usuniecia:
        if delete_obj.check_if_needed(reference=elem):
            delete_obj.objects.create(parent=egeria_import, reference=elem)


def diff_tytuly(egeria_import):
    diff_nazwa_i_skrot(egeria_import, 'tytul_stopien', Tytul, 'skrot')


def diff_funkcje(egeria_import):
    diff_nazwa_i_skrot(egeria_import, 'stanowisko', Funkcja_Autora, 'skrot')


def diff_wydzialy(egeria_import):
    diff_nazwa_i_skrot(egeria_import, 'nazwa_jednostki', Wydzial, 'nazwa')

def diff_jednostki(egeria_import):
    """
    Jednostka po nazwie
    - czy jest w bazie:
        TAK:
            - czy jest to ten sam wydział?
                TAK: nic
                NIE: zaktualizuj wydział,
            - czy jest widoczna i dostępna dla raportów?
                TAK: nic
                NIE: zaktualizuj widoczność

        NIE:
            - utwórz jednostkę, tworząc wcześniej wydział

    Sprawdź wszystkie jednostki w bazie:
    - czy jest w pliku XLS?
        TAK: nic nie rób,
        NIE: ukryj z raportów, ukryj jednostkę, ustaw wydział na "Jednostki Dawne"

    :param egeria_import:
    :return:
    """
    raise NotImplementedError