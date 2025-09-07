import pytest
from model_bakery import baker

from .utils import kombinacje_autorow_dyscyplin, wersje_dyscyplin

from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Zrodla,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)


@pytest.mark.django_db
def test_wersje_dyscyplin_autor_bez_dyscypliny(
    wydawnictwo_zwarte, autor_jan_nowak, jednostka, rok
):
    """Test wersje_dyscyplin dla autora bez dyscypliny w rekordzie"""
    # Utwórz podstawowe przypisanie autora bez konkretnej dyscypliny w publikacji
    autor_bez_dyscypliny = wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)

    # Funkcja powinna nie zwrócić żadnych wersji (brak dyscypliny w rekordzie)
    wersje = list(wersje_dyscyplin(autor_bez_dyscypliny))
    assert len(wersje) == 0


@pytest.mark.django_db
def test_wersje_dyscyplin_autor_nie_ma_autor_dyscyplina(
    wydawnictwo_zwarte, autor_jan_nowak, dyscyplina1, jednostka, rok
):
    """Test wersje_dyscyplin dla autora który nie ma rekordu Autor_Dyscyplina"""
    # Najpierw utwórz Autor_Dyscyplina żeby móc dodać autora z dyscypliną
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora="N",
    )

    # Dodaj autora do wydawnictwa z dyscypliną
    autor_wydaw = wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Usuń Autor_Dyscyplina żeby zasymulować brak rekordu
    Autor_Dyscyplina.objects.filter(autor=autor_jan_nowak, rok=rok).delete()

    # Funkcja powinna nie zwrócić żadnych wersji (brak Autor_Dyscyplina)
    wersje = list(wersje_dyscyplin(autor_wydaw))
    assert len(wersje) == 0


@pytest.mark.django_db
def test_wersje_dyscyplin_autor_status_n_podstawowy_przypadek(
    wydawnictwo_zwarte, autor_jan_nowak, dyscyplina1, jednostka, rok
):
    """Test wersje_dyscyplin dla autora ze statusem N - podstawowy przypadek"""
    # Najpierw utwórz Autor_Dyscyplina z statusem N
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora="N",
    )

    # Teraz dodaj autora do wydawnictwa z dyscypliną
    autor_wydaw = wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wersje = list(wersje_dyscyplin(autor_wydaw))

    # Powinno być 2 wersje: z dyscypliną (przypieta=True) i bez (przypieta=False)
    assert len(wersje) == 2

    # Pierwsza wersja: z oryginalną dyscypliną
    wersja1 = wersje[0]
    assert wersja1.dyscyplina_naukowa == dyscyplina1
    assert wersja1.przypieta is True

    # Druga wersja: bez dyscypliny
    wersja2 = wersje[1]
    assert wersja2.dyscyplina_naukowa is None
    assert wersja2.przypieta is False


@pytest.mark.django_db
def test_wersje_dyscyplin_autor_status_d_z_innymi_dyscyplinami_zwarte(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    jednostka,
    rok,
):
    """Test wersje_dyscyplin dla wydawnictwa zwartego z dodatkowymi dyscyplinami"""
    # Najpierw utwórz Autor_Dyscyplina z statusem D i dodatkowymi dyscyplinami
    # Autor musi mieć dyscyplina1 w przypisaniu żeby móc ją użyć w publikacji
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,  # Główna dyscyplina - ta sama co w wydawnictwie
        subdyscyplina_naukowa=dyscyplina2,  # Subdyscyplina - różna
        rodzaj_autora="D",
    )

    # Teraz dodaj autora do wydawnictwa z dyscypliną
    autor_wydaw = wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wersje = list(wersje_dyscyplin(autor_wydaw))

    # Powinno być 3 wersje:
    # 1. Z oryginalną dyscypliną (dyscyplina1, przypieta=True)
    # 2. Bez dyscypliny (None, przypieta=False)
    # 3. Z subdyscypliną autora (dyscyplina2, przypieta=True)
    # Główna dyscyplina autora to ta sama co w publikacji, więc nie zostanie dodana jako różna
    assert len(wersje) == 3

    # Sprawdź wszystkie wersje
    dyscypliny_w_wersjach = [w.dyscyplina_naukowa for w in wersje]
    assert dyscyplina1 in dyscypliny_w_wersjach  # oryginalna
    assert None in dyscypliny_w_wersjach  # bez dyscypliny
    assert dyscyplina2 in dyscypliny_w_wersjach  # subdyscyplina autora


@pytest.mark.django_db
def test_wersje_dyscyplin_wydawnictwo_ciagle_z_ograniczeniami_zrodla(
    wydawnictwo_ciagle,
    autor_jan_nowak,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    jednostka,
    rok,
):
    """Test wersje_dyscyplin dla wydawnictwa ciągłego z ograniczeniami źródła"""
    # Najpierw utwórz Autor_Dyscyplina z dodatkowymi dyscyplinami
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,  # Główna dyscyplina - ta sama co w wydawnictwie
        subdyscyplina_naukowa=dyscyplina2,  # Subdyscyplina - różna
        rodzaj_autora="N",
    )

    # Teraz dodaj autora do wydawnictwa ciągłego z dyscypliną
    autor_wydaw = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Dodaj tylko dyscyplina2 do Dyscyplina_Zrodla (nie dyscyplina3)
    Dyscyplina_Zrodla.objects.create(
        zrodlo=wydawnictwo_ciagle.zrodlo, dyscyplina=dyscyplina2, rok=rok
    )

    wersje = list(wersje_dyscyplin(autor_wydaw))

    # Powinno być 3 wersje:
    # 1. Z oryginalną dyscypliną (dyscyplina1, przypieta=True)
    # 2. Bez dyscypliny (None, przypieta=False)
    # 3. Z subdyscypliną autora (dyscyplina2, przypieta=True) - ona jest w Dyscyplina_Zrodla
    # Główna dyscyplina autora to ta sama co w publikacji, więc nie zostanie dodana jako różna
    assert len(wersje) == 3

    # Sprawdź wszystkie wersje
    dyscypliny_w_wersjach = [w.dyscyplina_naukowa for w in wersje]
    assert dyscyplina1 in dyscypliny_w_wersjach  # oryginalna
    assert None in dyscypliny_w_wersjach  # bez dyscypliny
    assert (
        dyscyplina2 in dyscypliny_w_wersjach
    )  # subdyscyplina autora (w Dyscyplina_Zrodla)


@pytest.mark.django_db
def test_wersje_dyscyplin_wydawnictwo_ciagle_bez_zrodla(
    autor_jan_nowak,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    rok,
    typ_odpowiedzialnosci_autor,
):
    """Test wersje_dyscyplin dla wydawnictwa ciągłego bez źródła"""
    # Najpierw utwórz Autor_Dyscyplina z dodatkowymi dyscyplinami
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,  # Ta sama co będzie użyta w publikacji
        subdyscyplina_naukowa=dyscyplina2,  # Dodatkowa dyscyplina
        rodzaj_autora="N",
    )

    # Utwórz wydawnictwo ciągłe bez źródła
    wydawnictwo_ciagle = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=None)

    # Dodaj autora z dyscypliną
    autor_wydaw = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wersje = list(wersje_dyscyplin(autor_wydaw))

    # Powinno być tylko 2 wersje (podstawowe):
    # 1. Z oryginalną dyscypliną (dyscyplina1, przypieta=True)
    # 2. Bez dyscypliny (None, przypieta=False)
    # dyscyplina2 NIE powinna być uwzględniona, bo brak źródła
    assert len(wersje) == 2

    dyscypliny_w_wersjach = [w.dyscyplina_naukowa for w in wersje]
    assert dyscyplina1 in dyscypliny_w_wersjach
    assert None in dyscypliny_w_wersjach
    assert dyscyplina2 not in dyscypliny_w_wersjach


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_wydawnictwo_zwarte_jeden_autor(
    wydawnictwo_zwarte, autor_jan_nowak, dyscyplina1, dyscyplina2, jednostka, rok
):
    """Test kombinacje_autorow_dyscyplin dla wydawnictwa zwartego z jednym autorem"""
    # Najpierw utwórz Autor_Dyscyplina
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
        rodzaj_autora="N",
    )

    # Dodaj autora z dyscypliną
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    kombinacje = list(kombinacje_autorow_dyscyplin(wydawnictwo_zwarte))

    # Autor ma 3 wersje: oryginalną dyscyplinę, bez dyscypliny, subdyscyplinę
    # Więc powinno być 3 kombinacje, każda z jednym autorem
    assert len(kombinacje) == 3

    # Każda kombinacja powinna mieć dokładnie jednego autora
    for kombinacja in kombinacje:
        assert len(kombinacja) == 1

    # Sprawdź dyscypliny w kombinacjach
    dyscypliny_w_kombinacjach = [k[0].dyscyplina_naukowa for k in kombinacje]
    assert dyscyplina1 in dyscypliny_w_kombinacjach  # oryginalna
    assert None in dyscypliny_w_kombinacjach  # bez dyscypliny
    assert dyscyplina2 in dyscypliny_w_kombinacjach  # subdyscyplina


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_wydawnictwo_zwarte_dwoch_autorow(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    rok,
):
    """Test kombinacje_autorow_dyscyplin dla wydawnictwa zwartego z dwoma autorami"""
    # Utwórz Autor_Dyscyplina dla pierwszego autora (2 wersje)
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora="N",  # Będzie miał 2 wersje: z dyscypliną i bez
    )

    # Utwórz Autor_Dyscyplina dla drugiego autora (2 wersje)
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina2,
        rodzaj_autora="D",  # Będzie miał 2 wersje: z dyscypliną i bez
    )

    # Dodaj pierwszego autora z dyscypliną
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Dodaj drugiego autora z dyscypliną
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    kombinacje = list(kombinacje_autorow_dyscyplin(wydawnictwo_zwarte))

    # Pierwszy autor ma 2 wersje, drugi autor ma 2 wersje
    # Wszystkich kombinacji powinno być 2 × 2 = 4
    assert len(kombinacje) == 4

    # Każda kombinacja powinna mieć dokładnie dwóch autorów
    for kombinacja in kombinacje:
        assert len(kombinacja) == 2

    # Sprawdź że wszystkie kombinacje są różne
    kombinacje_set = set()
    for kombinacja in kombinacje:
        # Utwórz unikalny identyfikator kombinacji na podstawie dyscyplin
        identyfikator = tuple(
            (
                autor.autor.id,
                autor.dyscyplina_naukowa.id if autor.dyscyplina_naukowa else None,
            )
            for autor in kombinacja
        )
        kombinacje_set.add(identyfikator)

    assert len(kombinacje_set) == 4  # Wszystkie kombinacje są unikalne


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_wydawnictwo_ciagle(
    wydawnictwo_ciagle, autor_jan_nowak, dyscyplina1, dyscyplina2, jednostka, rok
):
    """Test kombinacje_autorow_dyscyplin dla wydawnictwa ciągłego"""
    # Utwórz Autor_Dyscyplina z dodatkową dyscypliną
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
        rodzaj_autora="N",
    )

    # Dodaj autora z dyscypliną
    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Dodaj dyscyplina2 do Dyscyplina_Zrodla
    Dyscyplina_Zrodla.objects.create(
        zrodlo=wydawnictwo_ciagle.zrodlo, dyscyplina=dyscyplina2, rok=rok
    )

    kombinacje = list(kombinacje_autorow_dyscyplin(wydawnictwo_ciagle))

    # Autor ma 3 wersje: oryginalną, bez dyscypliny, subdyscyplinę (która jest w Dyscyplina_Zrodla)
    assert len(kombinacje) == 3

    # Każda kombinacja ma jednego autora
    for kombinacja in kombinacje:
        assert len(kombinacja) == 1


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_brak_autorow(db):
    """Test kombinacje_autorow_dyscyplin dla wydawnictwa bez autorów"""
    wydawnictwo_zwarte = baker.make(Wydawnictwo_Zwarte)

    kombinacje = list(kombinacje_autorow_dyscyplin(wydawnictwo_zwarte))

    # Brak autorów = brak kombinacji
    assert len(kombinacje) == 0


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_autor_bez_wersji(
    wydawnictwo_zwarte, autor_jan_nowak, dyscyplina1, jednostka, rok
):
    """Test kombinacje_autorow_dyscyplin gdy autor nie ma wersji dyscyplin"""
    # Utwórz Autor_Dyscyplina żeby móc dodać autora
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora="N",
    )

    # Dodaj autora z dyscypliną
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    # Usuń Autor_Dyscyplina - autor nie będzie miał wersji
    Autor_Dyscyplina.objects.filter(autor=autor_jan_nowak, rok=rok).delete()

    kombinacje = list(kombinacje_autorow_dyscyplin(wydawnictwo_zwarte))

    # Autor nie ma żadnych wersji, więc nie ma kombinacji
    assert len(kombinacje) == 0


@pytest.mark.django_db
def test_kombinacje_autorow_dyscyplin_nieobslugiwany_typ_rekordu():
    """Test kombinacje_autorow_dyscyplin dla nieobsługiwanego typu rekordu"""
    # Przekaż obiekt, który nie jest Wydawnictwo_Zwarte ani Wydawnictwo_Ciagle
    kombinacje = list(kombinacje_autorow_dyscyplin("nieprawidłowy_obiekt"))

    # Powinno zwrócić pustą listę
    assert len(kombinacje) == 0


@pytest.mark.django_db
def test_wersje_dyscyplin_kopiowanie_obiektow_jest_glebkie(
    wydawnictwo_zwarte, autor_jan_nowak, dyscyplina1, jednostka, rok
):
    """Test że wersje_dyscyplin zwraca głębokie kopie obiektów"""
    # Utwórz Autor_Dyscyplina
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora="N",
    )

    # Dodaj autora z dyscypliną
    autor_wydaw = wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wersje = list(wersje_dyscyplin(autor_wydaw))

    # Sprawdź że kopie są niezależne od oryginału
    for wersja in wersje:
        assert wersja is not autor_wydaw  # Różne obiekty
        assert wersja.autor == autor_wydaw.autor  # Ale ten sam autor

    # Sprawdź że modyfikacja kopii nie wpływa na oryginał
    oryginal_dyscyplina = autor_wydaw.dyscyplina_naukowa
    wersje[0].dyscyplina_naukowa = None
    assert (
        autor_wydaw.dyscyplina_naukowa == oryginal_dyscyplina
    )  # Oryginał niezmieniony
