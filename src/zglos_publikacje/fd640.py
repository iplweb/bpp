"""Porządki po FD#640: dyscypliny dopisane autorom spoza uczelni przez
formularz zgłaszania publikacji.

Od FD#620 do FD#640 zapis zgłoszenia dopisywał autorowi bez dyscypliny na rok
pracy wybraną dyscyplinę (``Autor_Dyscyplina``, z wpisem w historii „…podczas
zgłaszania pracy… (zgłoszenie #N)”) — także autorom obcym. Teraz zgłoszenie
przechowuje dyscyplinę tylko jako propozycję dla redakcji. Dodatkowo zapis
autora zgłoszenia zakładał mu powiązanie z wybraną jednostką
(``Autor_Jednostka`` bez dat), więc obcy autor, przy którym zgłaszający wybrał
jednostkę uczelni, wyglądał potem jak jej pracownik.

Ten moduł znajduje takie przypisania i — na żądanie — usuwa je razem
z powiązaniami z jednostkami, które założyło to samo zgłoszenie. Ostrożnie:
nie rusza przypisań zmienionych później przez redakcję ani użytych
w pracach (usunięcie przypisania wyzerowałoby dyscyplinę w tych pracach —
trigger ``bpp_autor_dyscyplina_delete``). Używa go komenda
``fd640_dyscypliny_obcych_ze_zgloszen`` (domyślnie tylko raport).
"""

import re
from dataclasses import dataclass, field

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import (
    Autor_Dyscyplina,
    Autor_Jednostka,
    Patent_Autor,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.autor import _jednostki_uczelni_bez_sztucznych
from bpp.wersjonowanie import zarejestruj_usuniecie, zmiana_rekordu
from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

ZNACZNIK_ZGLOSZENIA = "podczas zgłaszania pracy"
NUMER_ZGLOSZENIA = re.compile(r"\(zgłoszenie #(\d+)\)")

MODELE_AUTORSTW = (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)

POWOD_ZMIENIONE = "przypisanie zmieniono po utworzeniu — pominięto"
POWOD_W_PRACACH = "dyscyplina użyta w pracach ({}) — pominięto"


@dataclass
class Przypadek:
    przypisanie: Autor_Dyscyplina
    opis_utworzenia: str
    # Powiązania z jednostkami założone przez to samo zgłoszenie.
    jednostki_ze_zgloszenia: list = field(default_factory=list)
    # ``None`` — do usunięcia; inaczej powód pominięcia.
    pominiety: str | None = None

    @property
    def autor(self):
        return self.przypisanie.autor


def _ma_autorstwo_w_jednostce(aj):
    filtr = {"autor_id": aj.autor_id, "jednostka_id": aj.jednostka_id}
    return any(m._base_manager.filter(**filtr).exists() for m in MODELE_AUTORSTW)


def _bez_danych_kadrowych(aj):
    return not any(
        (
            aj.rozpoczal_prace,
            aj.zakonczyl_prace,
            aj.funkcja_id,
            aj.stanowisko_id,
            aj.grupa_pracownicza_id,
            aj.wymiar_etatu_id,
            aj.podstawowe_miejsce_pracy,
        )
    )


def _jednostki_ze_zgloszenia(ad, zgloszenie_id):
    """Powiązania autora z jednostkami wybranymi przy nim w zgłoszeniu
    ``zgloszenie_id``, które wyglądają na założone przez to zgłoszenie:
    bez dat i danych kadrowych, bez żadnej pracy autora w tej jednostce."""
    if zgloszenie_id is None:
        return []
    jednostki = Zgloszenie_Publikacji_Autor.all_objects.filter(
        rekord_id=zgloszenie_id, autor_id=ad.autor_id
    ).values("jednostka_id")
    return [
        aj
        for aj in Autor_Jednostka.objects.filter(
            autor_id=ad.autor_id, jednostka_id__in=jednostki
        ).select_related("jednostka")
        if _bez_danych_kadrowych(aj) and not _ma_autorstwo_w_jednostce(aj)
    ]


def _jest_autorem_jakiejkolwiek_uczelni(ad, pomin_pk):
    """Czy autor jest autorem (``AutorQuerySet.autorzy_uczelni``)
    KTÓREJKOLWIEK uczelni w bazie — po pominięciu powiązań ``pomin_pk`` (ze
    zgłoszenia). Wszystkie uczelnie, nie jedna: w bazie wielu uczelni autor
    obcy dla jednej bywa pracownikiem drugiej i jego dyscypliny nie wolno
    ruszać. Ta sama definicja co w zgłoszeniu i na stronie autora: liczą się
    jednostki uczelni poza sztucznymi (obca jednostka, pk < 0), także te bez
    ``skupia_pracownikow`` (doktoranci, emeryci)."""
    autor = ad.autor
    for uczelnia in Uczelnia.objects.all():
        nasze = _jednostki_uczelni_bez_sztucznych(uczelnia)
        if (
            autor.aktualna_jednostka_id is not None
            and nasze.filter(pk=autor.aktualna_jednostka_id).exists()
            and not Autor_Jednostka.objects.filter(
                pk__in=pomin_pk, jednostka_id=autor.aktualna_jednostka_id
            ).exists()
        ):
            return True
        if (
            Autor_Jednostka.objects.filter(autor_id=autor.pk, jednostka__in=nasze)
            .exclude(pk__in=pomin_pk)
            .exists()
        ):
            return True
    return False


def _liczba_prac_z_dyscyplina(ad):
    dyscypliny = [
        d for d in (ad.dyscyplina_naukowa_id, ad.subdyscyplina_naukowa_id) if d
    ]
    return sum(
        m._base_manager.filter(
            autor_id=ad.autor_id,
            rekord__rok=ad.rok,
            dyscyplina_naukowa_id__in=dyscypliny,
        ).count()
        for m in MODELE_AUTORSTW
    )


def znajdz_przypadki():
    """Przypisania dyscyplin dopisane przez zgłoszenia autorom, którzy (po
    pominięciu powiązań założonych przez te zgłoszenia) nie są autorami
    żadnej uczelni w bazie."""
    ct = ContentType.objects.get_for_model(Autor_Dyscyplina)
    opisy = {}
    for wpis in LogEntry.objects.filter(
        content_type=ct,
        action_flag=ADDITION,
        change_message__contains=ZNACZNIK_ZGLOSZENIA,
    ).order_by("action_time"):
        opisy.setdefault(int(wpis.object_id), wpis.change_message)

    zmienione = set(
        int(pk)
        for pk in LogEntry.objects.filter(
            content_type=ct, action_flag=CHANGE, object_id__in=map(str, opisy)
        ).values_list("object_id", flat=True)
    )

    przypadki = []
    for ad in (
        Autor_Dyscyplina.all_objects.filter(pk__in=opisy)
        .select_related("autor", "autor__aktualna_jednostka", "dyscyplina_naukowa")
        .order_by("autor__nazwisko", "autor__imiona", "rok")
    ):
        numer = NUMER_ZGLOSZENIA.search(opisy[ad.pk])
        ze_zgloszenia = _jednostki_ze_zgloszenia(
            ad, int(numer.group(1)) if numer else None
        )
        if _jest_autorem_jakiejkolwiek_uczelni(ad, [aj.pk for aj in ze_zgloszenia]):
            continue
        przypadek = Przypadek(ad, opisy[ad.pk], ze_zgloszenia)
        if ad.pk in zmienione:
            przypadek.pominiety = POWOD_ZMIENIONE
        elif ile := _liczba_prac_z_dyscyplina(ad):
            przypadek.pominiety = POWOD_W_PRACACH.format(ile)
        przypadki.append(przypadek)
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
def usun(przypadek, user=None, usuniete_jednostki=None):
    """Usuń przypisanie dyscypliny i powiązania z jednostkami ze zgłoszenia —
    z wpisami w historii autora. ``usuniete_jednostki`` — zbiór pk powiązań
    już usuniętych (ten sam autor w kilku przypadkach), uzupełniany tutaj."""
    if przypadek.pominiety is not None:
        raise ValueError(f"Przypadek pominięty: {przypadek.pominiety}")
    if usuniete_jednostki is None:
        usuniete_jednostki = set()
    autor = przypadek.autor
    with zmiana_rekordu(user, autor, KOMUNIKAT_USUNIECIA):
        for aj in przypadek.jednostki_ze_zgloszenia:
            if aj.pk in usuniete_jednostki:
                continue
            usuniete_jednostki.add(aj.pk)
            zarejestruj_usuniecie(user, aj, KOMUNIKAT_USUNIECIA_JEDNOSTKI)
            aj.delete()
        zarejestruj_usuniecie(user, przypadek.przypisanie, KOMUNIKAT_USUNIECIA)
        przypadek.przypisanie.delete()
