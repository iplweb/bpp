from datetime import date


def test_odepnij_autorow_spoza_pliku_autor_jest_w_pliku_ale_odpinamy_inne_miejsca_zarzadzaj_automatycznie(
    import_pracownikow_performed,
    autor_z_pliku,
    jednostka_z_pliku,
    jednostka_spoza_pliku,
    today,
    yesterday,
):
    aj_spoza_pliku = autor_z_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    jednostka_spoza_pliku.zarzadzaj_automatycznie = True
    jednostka_spoza_pliku.save()

    # Odpinamy
    import_pracownikow_performed.odepnij_autorow_spoza_pliku(
        today=today, yesterday=yesterday
    )

    # Odpięcie automatyczne jednostek zarządzanych automatycznie powinno odpiąc te jednostki
    # a w sytuacji, gdy autorowi nie pozostanie zadna jednostka, aktualna jednostka
    # będzie miała wartość None:

    autor_z_pliku.refresh_from_db()
    assert autor_z_pliku.aktualna_jednostka == jednostka_z_pliku

    # Przypisanie Autor+Jednostka znajdujące się w pliku zostanie dodane od dzisiaj
    assert autor_z_pliku.autor_jednostka_set.get(
        jednostka=jednostka_z_pliku
    ).rozpoczal_prace == date(2016, 10, 1)

    # Przypisania Autor + Jednostka spoza pliku bedzie miała "odpięte" miejsce pracy
    # czyli datę zakończenia równą wczoraj
    aj_spoza_pliku.refresh_from_db()
    assert aj_spoza_pliku.zakonczyl_prace == yesterday
    assert aj_spoza_pliku.podstawowe_miejsce_pracy is False


def test_odepnij_autorow_spoza_pliku_autor_jest_w_pliku_ale_odpinamy_inne_miejsca_nie_zarzadzaj_automatycznie(
    import_pracownikow_performed,
    autor_z_pliku,
    jednostka_z_pliku,
    jednostka_spoza_pliku,
    today,
    yesterday,
):
    autor_z_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    jednostka_spoza_pliku.zarzadzaj_automatycznie = False
    jednostka_spoza_pliku.save()

    # Zweryfikujmy stan po imporcie -- `autor_z_pliku` przypięty do `jednostka_z_pliku`
    autor_z_pliku.refresh_from_db()
    assert autor_z_pliku.aktualna_jednostka == jednostka_z_pliku

    # Przy wykorzystaniu przez tą funkcję parametru 'import_pracownikow_performed', mamy w bazie
    # danych stan taki, jak w pliku -- czyli "podstawowe miejsce pracy" ustawione dla pana
    # `autor_z_pliku` na `jednostka_z_pliku`. Z tym, że teraz chcemy przetestować odpinanie jednostek
    # zatem skasujemy tą informację z pliku importu, aby było tak jak gdyby tego wpisu w pliku
    # importu nie było. Zatem, oczekiwanym zachowaniem będzie przez system odpięcie jednostki
    # `jednostka_z_pliku` (bo jest zarządzana automatycznie) oraz NIE odpięcie jednostki `jednostka_spoza_pliku`
    # gdyż ona ma `zarzadzaj_automatycznie` ustawione na False.

    import_pracownikow_performed.importpracownikowrow_set.all().delete()

    # Skasowana.

    # Teraz odpinamy:
    import_pracownikow_performed.odepnij_autorow_spoza_pliku(
        today=today, yesterday=yesterday
    )

    # Odpięcie jednostek nie-zarządzanych automatycznie powinno ich nie ruszać:

    autor_z_pliku.refresh_from_db()
    assert autor_z_pliku.aktualna_jednostka == jednostka_spoza_pliku


def test_odepnij_autorow_spoza_pliku_inny_autor_czy_odepnie_automatyczna(
    import_pracownikow_performed,
    autor_z_pliku,
    jednostka_z_pliku,
    autor_spoza_pliku,
    jednostka_spoza_pliku,
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    jednostka_spoza_pliku.zarzadzaj_automatycznie = True
    jednostka_spoza_pliku.save()

    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka == jednostka_spoza_pliku

    # Odpinamy
    import_pracownikow_performed.odepnij_autorow_spoza_pliku()

    # Czy autor_spoza_pliku ma odpietą jednostkę?
    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka is None


def test_odepnij_autorow_spoza_pliku_inny_autor_czy_nie_odepnie_nie_automatyczna(
    import_pracownikow_performed,
    autor_z_pliku,
    jednostka_z_pliku,
    autor_spoza_pliku,
    jednostka_spoza_pliku,
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    jednostka_spoza_pliku.zarzadzaj_automatycznie = False
    jednostka_spoza_pliku.save()

    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka == jednostka_spoza_pliku

    # Odpinamy
    import_pracownikow_performed.odepnij_autorow_spoza_pliku()

    # Czy autor_spoza_pliku ma odpietą jednostkę?
    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka == jednostka_spoza_pliku
