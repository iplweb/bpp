"""Dyscyplina dla autora bez przypisania na rok zgłaszanej pracy (FD#620).

W kroku „Autorzy” formularza zgłaszania publikacji lista „Dyscyplina naukowa”
dla autora, który nie ma przypisanej dyscypliny na rok pracy, podpowiada
dyscypliny autora z najbliższego wcześniejszego roku, a gdy nie miał ich
nigdy — typowe dla uczelni (``bpp.util.typowe_dyscypliny``). Walidacja
wymaga przypisania ``Autor_Dyscyplina`` na rok pracy, więc przy zapisie
zgłoszenia zakładamy je — z wpisem w historii autora i przypisania.

Autora, który MA przypisanie na rok pracy, nie ruszamy. Autorowi spoza
uczelni (FD#640) dyscypliny w zgłoszeniu nie podaje się wcale.
"""

from bpp.models import Autor_Dyscyplina
from bpp.util.typowe_dyscypliny import propozycja_dla_autora_bez_przypisania
from bpp.wersjonowanie import opis_uzytkownika, zarejestruj_utworzenie, zmiana_rekordu


def ma_przypisanie_na_rok(autor_id, rok):
    return Autor_Dyscyplina.all_objects.filter(autor_id=autor_id, rok=rok).exists()


def dyscyplina_z_propozycji(autor_id, rok, dyscyplina):
    """Czy ``dyscyplina`` jest na liście podpowiadanej autorowi bez
    przypisania na ``rok`` (bez zawężenia do uczelni — lista ogólna jest
    nadzbiorem list poszczególnych uczelni)."""
    propozycja = propozycja_dla_autora_bez_przypisania(autor_id, rok)
    return dyscyplina in propozycja.dyscypliny


def komunikat_dyscypliny(zgloszenie, dyscyplina, rok, user):
    tytul = (zgloszenie.tytul_oryginalny or "").strip()
    if len(tytul) > 120:
        tytul = tytul[:119] + "…"
    if user is not None and user.is_authenticated:
        kto = f"przez użytkownika {opis_uzytkownika(user)}"
    else:
        kto = f"przez niezalogowanego zgłaszającego ({zgloszenie.email})"
    return (
        f"Przypisano dyscyplinę „{dyscyplina}” na rok {rok} {kto} podczas "
        f"zgłaszania pracy „{tytul}” (zgłoszenie #{zgloszenie.pk})"
    )


def przypisz_dyscypline_jesli_brak(zpa, user):
    """Dla autora zgłoszenia ``zpa`` (już zapisanego) bez przypisania na rok
    pracy utwórz ``Autor_Dyscyplina`` z wybraną dyscypliną i wpisem
    w historii. ``user`` — zgłaszający (niezalogowany: konto systemowe,
    e-mail zgłaszającego w treści wpisu). Zwraca utworzone przypisanie albo
    ``None``."""
    if zpa.dyscyplina_naukowa_id is None or zpa.autor_id is None:
        return None
    if ma_przypisanie_na_rok(zpa.autor_id, zpa.rok):
        return None
    if not zpa.autor_jest_autorem_uczelni():
        # FD#640: autorowi spoza uczelni dyscypliny nie dopisujemy (walidacja
        # i tak jej nie przepuści — to druga linia obrony).
        return None

    autor = zpa.autor
    uzytkownik = user if (user is not None and user.is_authenticated) else None
    komunikat = komunikat_dyscypliny(zpa.rekord, zpa.dyscyplina_naukowa, zpa.rok, user)
    with zmiana_rekordu(uzytkownik, autor, komunikat):
        ad = Autor_Dyscyplina.objects.create(
            autor=autor, rok=zpa.rok, dyscyplina_naukowa=zpa.dyscyplina_naukowa
        )
    zarejestruj_utworzenie(uzytkownik, ad, komunikat)
    return ad
