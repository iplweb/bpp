"""Stałe słownikowe raportu kompletności danych POL-on.

Rozporządzenie MNiSW z dnia 16 czerwca 2026 r. w sprawie danych przetwarzanych
w ZSIoSW POL-on (Dz. U. 2026 poz. 811) określa w § 2 ust. 10 zakres danych
o osiągnięciach naukowych wprowadzanych do wykazu pracowników.
"""

from django.db import models


class Osiagniecie(models.TextChoices):
    """Typ osiągnięcia naukowego w rozumieniu § 2 ust. 10 rozporządzenia.

    Każdy wariant odwzorowuje jeden punkt ustępu i jeden model BPP:

    * ``ARTYKUL`` — pkt 4, ``bpp.Wydawnictwo_Ciagle``,
    * ``MONOGRAFIA`` — pkt 5, ``bpp.Wydawnictwo_Zwarte`` o charakterze
      slotów „książka” (``bpp.const.CHARAKTER_SLOTY_KSIAZKA``),
    * ``ROZDZIAL`` — pkt 6, ``bpp.Wydawnictwo_Zwarte`` o charakterze slotów
      „rozdział” (``bpp.const.CHARAKTER_SLOTY_ROZDZIAL``),
    * ``PATENT`` — pkt 1, ``bpp.Patent``.

    Osiągnięcia artystyczne (pkt 7), wzory użytkowe (pkt 2) i odmiany roślin
    (pkt 3) nie mają w BPP modelu ani charakteru formalnego, więc raport ich
    nie obejmuje — nie da się zgłosić braku danej, dla której nie istnieje
    miejsce zapisu.
    """

    ARTYKUL = "ART", "Artykuł naukowy"
    MONOGRAFIA = "MON", "Monografia naukowa"
    ROZDZIAL = "ROZ", "Rozdział w monografii naukowej"
    PATENT = "PAT", "Patent"


class Waga(models.TextChoices):
    """Kategoria wymogu — czy rozporządzenie żąda danej bezwarunkowo.

    ``WYMAGANE`` to wymóg bezwarunkowy; brak danej jest błędem, który trzeba
    uzupełnić. ``WARUNKOWE`` odwzorowuje zwroty „jeżeli posiada”, „jeżeli są
    znane”, „o ile został nadany” — braki tej kategorii raport pokazuje
    osobno i nie wlicza do licznika braków krytycznych.
    """

    WYMAGANE = "W", "Wymagane"
    WARUNKOWE = "C", "Warunkowe"


#: Skrót pozycji słownika ``bpp.Czas_Udostepnienia_OpenAccess`` oznaczającej
#: udostępnienie utworu *po* opublikowaniu. Tylko dla tej wartości ma sens
#: pytanie o liczbę miesięcy karencji (patrz reguły ``*_OA_MIESIACE``).
#: Wartość pochodzi z fixture instalacyjnego ``bpp.fixtures.DANE_OPEN_ACCESS``
#: i jest tożsama ze słownikiem PBN (``releaseDateMode``).
OA_CZAS_PO_OPUBLIKOWANIU = "AFTER_PUBLICATION"
