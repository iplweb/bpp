"""Porządki po FD#640: dyscypliny dopisane autorom spoza uczelni przez
formularz zgłaszania publikacji.

Od FD#620 zapis zgłoszenia dopisywał autorowi bez dyscypliny na rok pracy
wybraną dyscyplinę (``Autor_Dyscyplina``, z wpisem w historii „…podczas
zgłaszania pracy…”) — także autorom obcym. Dodatkowo zapis autora zgłoszenia
zakładał mu powiązanie z wybraną jednostką (``Autor_Jednostka`` bez dat), więc
obcy autor, przy którym zgłaszający wybrał jednostkę uczelni, wyglądał potem
jak jej pracownik.

Ten moduł znajduje takie przypisania dyscyplin i — na żądanie — je usuwa
razem z powiązaniami z jednostkami, które powstały wyłącznie ze zgłoszeń.
Używa go komenda ``fd640_dyscypliny_obcych_ze_zgloszen`` (domyślnie tylko
raport).
"""

from dataclasses import dataclass, field

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import (
    Autor_Dyscyplina,
    Autor_Jednostka,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.wersjonowanie import zarejestruj_usuniecie, zmiana_rekordu
from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

ZNACZNIK_ZGLOSZENIA = "podczas zgłaszania pracy"

MODELE_AUTORSTW = (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)


@dataclass
class Przypadek:
    przypisanie: Autor_Dyscyplina
    opis_utworzenia: str
    # Powiązania autora z jednostkami uczelni, które powstały wyłącznie ze
    # zgłoszeń (bez dat, bez żadnej pracy w tej jednostce).
    jednostki_ze_zgloszen: list = field(default_factory=list)

    @property
    def autor(self):
        return self.przypisanie.autor


def _tylko_ze_zgloszenia(aj):
    """Powiązanie wygląda na założone wyłącznie przez zgłoszenie: bez dat
    i danych kadrowych, w tej jednostce autor nie ma żadnej pracy w bazie,
    a ma autorstwo w zgłoszeniu."""
    if any(
        (
            aj.rozpoczal_prace,
            aj.zakonczyl_prace,
            aj.funkcja_id,
            aj.stanowisko_id,
            aj.grupa_pracownicza_id,
            aj.wymiar_etatu_id,
            aj.podstawowe_miejsce_pracy,
        )
    ):
        return False
    filtr = {"autor_id": aj.autor_id, "jednostka_id": aj.jednostka_id}
    if any(m._base_manager.filter(**filtr).exists() for m in MODELE_AUTORSTW):
        return False
    return Zgloszenie_Publikacji_Autor.all_objects.filter(**filtr).exists()


def znajdz_przypadki(uczelnia):
    """Przypisania dyscyplin dopisane przez zgłoszenia autorom, którzy nie są
    autorami ``uczelnia`` — po pominięciu powiązań z jednostkami założonych
    wyłącznie przez zgłoszenia."""
    wpisy = LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Autor_Dyscyplina),
        action_flag=ADDITION,
        change_message__contains=ZNACZNIK_ZGLOSZENIA,
    ).order_by("action_time")
    opisy = {}
    for wpis in wpisy:
        opisy.setdefault(int(wpis.object_id), wpis.change_message)

    przypadki = []
    for ad in (
        Autor_Dyscyplina.all_objects.filter(pk__in=opisy)
        .select_related("autor", "dyscyplina_naukowa")
        .order_by("autor__nazwisko", "autor__imiona", "rok")
    ):
        realne = []
        ze_zgloszen = []
        for aj in Autor_Jednostka.objects.filter(
            autor_id=ad.autor_id,
            jednostka__uczelnia=uczelnia,
            jednostka__skupia_pracownikow=True,
        ).select_related("jednostka"):
            (ze_zgloszen if _tylko_ze_zgloszenia(aj) else realne).append(aj)
        if realne:
            continue
        aktualna = ad.autor.aktualna_jednostka
        if (
            aktualna is not None
            and aktualna.uczelnia_id == uczelnia.pk
            and aktualna.skupia_pracownikow
            and not any(aj.jednostka_id == aktualna.pk for aj in ze_zgloszen)
        ):
            continue
        przypadki.append(Przypadek(ad, opisy[ad.pk], ze_zgloszen))
    return przypadki


KOMUNIKAT_USUNIECIA = (
    "FD#640: usunięto dyscyplinę dopisaną podczas zgłaszania pracy autorowi "
    "spoza uczelni"
)
KOMUNIKAT_USUNIECIA_JEDNOSTKI = (
    "FD#640: usunięto powiązanie z jednostką założone podczas zgłaszania "
    "pracy autorowi spoza uczelni"
)


@transaction.atomic
def usun(przypadek, user=None):
    """Usuń przypisanie dyscypliny i powiązania z jednostkami ze zgłoszeń —
    z wpisami w historii autora."""
    autor = przypadek.autor
    with zmiana_rekordu(user, autor, KOMUNIKAT_USUNIECIA):
        for aj in przypadek.jednostki_ze_zgloszen:
            zarejestruj_usuniecie(user, aj, KOMUNIKAT_USUNIECIA_JEDNOSTKI)
            aj.delete()
        zarejestruj_usuniecie(user, przypadek.przypisanie, KOMUNIKAT_USUNIECIA)
        przypadek.przypisanie.delete()
