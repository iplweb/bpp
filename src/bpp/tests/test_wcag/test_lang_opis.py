"""WCAG 3.1.2 w opisie bibliograficznym (wektor 2).

Opis jest generowany serwerowo i cache'owany jako gotowy HTML, więc
znacznik języka musi trafić DO ŚRODKA tego HTML-u — poprawka na poziomie
szablonu strony go nie obejmuje.

Asercje idą na wynik ``opis_bibliograficzny()``, a NIE na render samego
szablonu: metoda kończy się sanityzacją nh3, która wycięłaby ``<span>``
gdyby allowlista nie została rozszerzona. Test broni tego rozszerzenia
przed cofnięciem.
"""

import json

import lxml.html
import pytest
from model_bakery import baker

from bpp.models.system import Jezyk
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


@pytest.fixture
def jezyk_angielski(jezyki):
    return Jezyk.objects.get(skrot="ang.")


@pytest.fixture
def jezyk_bez_kodu(db):
    return baker.make(Jezyk, nazwa="suahili", skrot="swa.", kod_bcp47="")


@pytest.mark.django_db
def test_opis_zawiera_lang_tytulu(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis
    assert "Effects of X on Y" in opis


@pytest.mark.django_db
def test_opis_bez_lang_gdy_kod_pusty(wydawnictwo_ciagle, jezyk_bez_kodu):
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł bez kodu"
    wydawnictwo_ciagle.jezyk = jezyk_bez_kodu
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert "Tytuł bez kodu" in opis
    assert "lang=" not in opis


@pytest.mark.django_db
def test_opis_nie_oznacza_przekladu(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X"
    wydawnictwo_ciagle.tytul = "Wpływ X"
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert opis.count('lang="en"') == 1
    assert "Wpływ X" in opis


@pytest.mark.django_db
def test_znacznik_przezywa_post_processing(wydawnictwo_ciagle, jezyk_angielski):
    # Dowodzi, że <span lang="en"> przechodzi CAŁY pipeline
    # opis_bibliograficzny() — render szablonu, łańcuch normalizacji
    # interpunkcji .replace() (util.py:106-123) i sanityzację nh3 —
    # nienaruszony i niezdublowany: dokładnie jedno otwarcie i jedno
    # zamknięcie <span lang="en">…</span> w wyniku. Tytuł kończący się
    # kropką stawia znacznik w bezpośrednim sąsiedztwie normalizowanej
    # interpunkcji (".</span></b>[" — patrz osobny .replace() dla tego
    # wariantu), więc to najostrzejszy z tych testów przypadek kontaktu.
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X."
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis
    assert "</span>" in opis
    assert "<span lang=" not in opis.replace('<span lang="en">', "")


@pytest.mark.django_db
def test_znacznik_w_wariancie_praca_tabela(wydawnictwo_ciagle, jezyk_angielski):
    # Drugi szablon opisu, instalowany kiedyś przez migrację 0295 obok
    # domyślnego. Leży w katalogu browse/, ale NIE jest stroną — żaden widok
    # go nie renderuje; wchodzi wyłącznie przez nazwa_szablonu.
    SzablonDlaOpisuBibliograficznego.objects.update_or_create(
        model=None,
        defaults={"nazwa_szablonu": "browse/praca_tabela.html"},
    )
    # Migracja 0488 (purge_praca_tabela_dbtemplate) czyści osierocony wiersz
    # dbtemplates dla "browse/praca_tabela.html" na poziomie schematu — więc
    # do czasu testu ten wiersz już nie istnieje i ręczne drop_dbtemplate()
    # tutaj byłoby no-opem (a dopóki tu stało, test przechodziłby także po
    # cofnięciu 0488, czyli przestał bronić tego, o co chodzi). Czystość
    # loadera dbtemplates dla tej nazwy pilnuje osobny test:
    # test_purge_dbtemplate.py.
    wydawnictwo_ciagle.tytul_oryginalny = "Effects of X on Y"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert '<span lang="en">' in opis


@pytest.mark.django_db
def test_kursywa_w_tytule_przezywa_obok_znacznika(wydawnictwo_ciagle, jezyk_angielski):
    wydawnictwo_ciagle.tytul_oryginalny = "Role of <i>Candida</i> in X"
    wydawnictwo_ciagle.tytul = ""
    wydawnictwo_ciagle.jezyk = jezyk_angielski
    wydawnictwo_ciagle.save()

    opis = wydawnictwo_ciagle.opis_bibliograficzny()

    assert "<i>Candida</i>" in opis
    assert 'lang="en"' in opis


@pytest.mark.django_db
def test_data_records_zawiera_znacznik_jezyka(
    client, wydawnictwo_zwarte, jezyk_angielski, denorms
):
    # Wyszukiwarka rekordów powiązanych czyta surowy HTML opisu z atrybutu
    # data-records (praca_tabela_mono.html:676). Rozdział w wydawnictwie
    # nadrzędnym trafia tam przez wydawnictwa_powiazane_posortowane
    # (wydawnictwo_zwarte.py:263), więc po zmianie generatora niesie
    # <span lang=…> — i to on psuł podświetlanie przed naprawą z Task 5.
    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    rozdzial = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Effects of X on Y",
        tytul="",
        jezyk=jezyk_angielski,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        rok=wydawnictwo_zwarte.rok,
    )
    rozdzial.opis_bibliograficzny_cache = rozdzial.opis_bibliograficzny()
    rozdzial.save()

    res = client.get(wydawnictwo_zwarte.get_absolute_url())

    assert res.status_code == 200

    # Asercja NIE na całej stronie (tam "lang=" jest też w widocznym linku,
    # renderowanym osobno przez {{ elem.opis_bibliograficzny_cache|safe }}),
    # tylko konkretnie na wartości atrybutu data-records — to on jest
    # wejściem wyszukiwarki/podświetlania. Wartość tekstowa przechodzi przez
    # filtr |escapejs (Django), który zamienia "<", "=", "\"" na sekwencje
    # \uXXXX — dokładnie tak samo, jak JS w przeglądarce robi to przez
    # JSON.parse(), dekodujemy więc atrybut jako JSON zamiast szukać
    # dosłownego 'lang="en"' w surowym źródle strony.
    tree = lxml.html.fromstring(res.content)
    elementy = tree.xpath("//*[@data-records]")
    assert elementy, "brak elementu z atrybutem data-records na stronie"

    znaleziono_lang = False
    for element in elementy:
        rekordy = json.loads(element.get("data-records"))
        if any('lang="en"' in rekord["text"] for rekord in rekordy):
            znaleziono_lang = True
            break
    assert znaleziono_lang, "znacznik lang nie dotarl do atrybutu data-records"
