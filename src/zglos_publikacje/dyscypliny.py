"""Dyscyplina dla autora bez przypisania na rok zgłaszanej pracy (FD#620).

W kroku „Autorzy” formularza zgłaszania publikacji lista „Dyscyplina naukowa”
dla autora, który nie ma przypisanej dyscypliny na rok pracy, podpowiada
dyscypliny autora z najbliższego wcześniejszego roku, a gdy nie miał ich
nigdy — typowe dla uczelni (``bpp.util.typowe_dyscypliny``). Walidacja
zgłoszenia przepuszcza dyscyplinę z tej listy.

FD#640: wybrana dyscyplina to wyłącznie PROPOZYCJA zapisana w zgłoszeniu
(``Zgloszenie_Publikacji_Autor.dyscyplina_naukowa``). Zapis zgłoszenia — także
przez niezalogowanego — nie zmienia danych autora. ``Autor_Dyscyplina`` zakłada
dopiero redakcja przy zatwierdzaniu zgłoszenia: importer publikacji podpowiada
dyscyplinę ze zgłoszenia, a przy tworzeniu rekordu zakłada brakujące
przypisanie w imieniu redaktora (``importer_publikacji.dyscypliny``).
Autorowi spoza uczelni dyscypliny w zgłoszeniu nie podaje się wcale.
"""

from bpp.models import Autor_Dyscyplina
from bpp.util.typowe_dyscypliny import propozycja_dla_autora_bez_przypisania


def ma_przypisanie_na_rok(autor_id, rok):
    return Autor_Dyscyplina.all_objects.filter(autor_id=autor_id, rok=rok).exists()


def dyscyplina_z_propozycji(autor_id, rok, dyscyplina):
    """Czy ``dyscyplina`` jest na liście podpowiadanej autorowi bez
    przypisania na ``rok`` (bez zawężenia do uczelni — lista ogólna jest
    nadzbiorem list poszczególnych uczelni)."""
    propozycja = propozycja_dla_autora_bez_przypisania(autor_id, rok)
    return dyscyplina in propozycja.dyscypliny


def podpowiedz_dla_redakcji(zpa, rok):
    """Dane autora zgłoszenia ``zpa`` do wstępnego wypełnienia rekordu pracy
    w adminie („Dodaj wyd. ciągłe/zwarte” ze zgłoszenia, rok pracy ``rok``).

    Zwraca ``(initial, uwagi)``: słownik ``autor``/``jednostka``/
    ``dyscyplina_naukowa`` (i ``afiliuje=False`` dla jednostki obcej) dla
    wiersza autora oraz listę komunikatów dla
    redaktora o tym, czego ze zgłoszenia nie przeniesiono:

    - autorowi spoza uczelni — jednostki uczelni (w zamian jednostka obca
      uczelni, gdy jest skonfigurowana) i dyscypliny (FD#640);
    - autorowi uczelni bez przypisania do proponowanej dyscypliny na rok
      pracy — dyscypliny: walidacja rekordu i tak by jej nie przyjęła, a
      przypisanie zakłada redakcja (edycja autora albo importer publikacji).
    """
    from django.db.models import Q

    uwagi = []
    jednostka = zpa.jednostka_dla_redakcji()
    if jednostka is None and zpa.jednostka_id is not None:
        uczelnia = zpa.uczelnia_zgloszenia()
        obca = uczelnia.obca_jednostka if uczelnia is not None else None
        jednostka = obca
        uwagi.append(
            f"Autor {zpa.autor} jest spoza uczelni — pominięto jednostkę "
            f"„{zpa.jednostka}” ze zgłoszenia"
            + (f" (wpisano „{obca}”)." if obca is not None else "; wybierz ją.")
        )

    dyscyplina = zpa.dyscyplina_dla_redakcji()
    if (
        dyscyplina is not None
        and rok
        and not Autor_Dyscyplina.objects.filter(
            Q(dyscyplina_naukowa=dyscyplina) | Q(subdyscyplina_naukowa=dyscyplina),
            autor_id=zpa.autor_id,
            rok=rok,
        ).exists()
    ):
        uwagi.append(
            f"Zgłoszenie proponuje dla autora {zpa.autor} dyscyplinę "
            f"„{dyscyplina}”, ale autor nie ma do niej przypisania na rok {rok} "
            "— pominięto ją. Przypisz dyscyplinę autorowi (edycja autora) i "
            "uzupełnij ją w rekordzie albo zatwierdź zgłoszenie importerem "
            "publikacji, który założy przypisanie."
        )
        dyscyplina = None

    initial = {
        "autor": zpa.autor_id,
        "jednostka": jednostka.pk if jednostka is not None else None,
        "dyscyplina_naukowa": dyscyplina.pk if dyscyplina is not None else None,
    }
    if jednostka is not None and not jednostka.przyjmuje_afiliacje():
        # Obca jednostka (i każda nieprzyjmująca afiliacji) nigdy nie
        # afiliuje — bez tego domyślnie zaznaczone „Afiliuje” zablokowałoby
        # zapis rekordu.
        initial["afiliuje"] = False
    return initial, uwagi
