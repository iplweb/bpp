"""Raport po FD#640: dyscypliny (i jednostki) dopisane autorom spoza uczelni
przez formularz zgłaszania publikacji.

Od FD#620 do FD#640 zapis zgłoszenia dopisywał autorowi bez dyscypliny na rok
pracy wybraną dyscyplinę (``Autor_Dyscyplina``, z wpisem w historii „…podczas
zgłaszania pracy… (zgłoszenie #N)”) — także autorom obcym. Wcześniej (także
przed FD#620) zapis autora zgłoszenia zakładał mu powiązanie z wybraną
jednostką (``Autor_Jednostka`` bez dat), więc obcy autor, przy którym
zgłaszający wybrał jednostkę uczelni, wyglądał potem jak jej pracownik.
Teraz zgłoszenie przechowuje dyscyplinę i jednostkę tylko jako propozycję.

Moduł WYŁĄCZNIE raportuje — nic nie zmienia w bazie. Na podstawie raportu
człowiek decyduje o ręcznym sprzątaniu (edycja autora w module redagowania).
Raport jest ostrożny:

- powiązanie z jednostką bez dat, danych kadrowych i prac w tej jednostce,
  wybraną przy autorze w zgłoszeniu, NIE jest dowodem, że założyło je
  zgłoszenie (powiązania nie mają daty utworzenia) — przypadek, który
  „wygląda na obcego” dopiero po pominięciu takich powiązań, jest oznaczony
  jako niepewny; powiązanie, które historia autora pokazuje jako dodane
  w module redagowania albo istniejące przed zgłoszeniem, nie jest pomijane;
- przypisanie zmienione później przez redakcję (także przez inline
  „Powiązania autor-dyscyplina” w edycji autora) jest oznaczone;
- liczba prac, które straciłyby dyscyplinę przy usunięciu przypisania,
  jest liczona jak trigger ``bpp_autor_dyscyplina_delete``: zeruje on
  dyscyplinę we WSZYSTKICH autorstwach autora w pracach z tego roku,
  niezależnie od tego, jaka to dyscyplina.

Używa go komenda ``fd640_dyscypliny_obcych_ze_zgloszen``.
"""

import json
import re
from dataclasses import dataclass, field

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from reversion.errors import RevertError
from reversion.models import Version

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Autor_Jednostka,
    Patent_Autor,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from bpp.models.autor import _jednostki_uczelni_bez_sztucznych
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor

ZNACZNIK_ZGLOSZENIA = "podczas zgłaszania pracy"
NUMER_ZGLOSZENIA = re.compile(r"\(zgłoszenie #(\d+)\)")

MODELE_AUTORSTW = (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor)

NAZWA_AD = str(Autor_Dyscyplina._meta.verbose_name)
NAZWA_AJ = str(Autor_Jednostka._meta.verbose_name)


@dataclass
class Przypadek:
    """Autor, który wygląda na obcego, z danymi dopisanymi przez zgłoszenie.

    ``przypisanie`` — ``Autor_Dyscyplina`` dopisane przez zgłoszenie (sekcja
    główna) albo ``None`` (sekcja „tylko jednostki”, zgłoszenia sprzed
    FD#620)."""

    autor: Autor
    zgloszenie_id: int | None
    przypisanie: Autor_Dyscyplina | None = None
    opis_utworzenia: str = ""
    # Powiązania z jednostkami, które WYGLĄDAJĄ na założone przez zgłoszenie
    # (bez dat i danych kadrowych, bez prac w tej jednostce). Pominięte przy
    # ocenie „obcości” — dlatego ich obecność czyni przypadek niepewnym.
    jednostki_ze_zgloszenia: list = field(default_factory=list)
    # Przypisanie zmienione później przez redakcję.
    zmienione: bool = False
    # Ile autorstw straciłoby dyscyplinę przy usunięciu przypisania (trigger).
    prace_tracace_dyscypline: int = 0

    @property
    def niepewne(self):
        return bool(self.jednostki_ze_zgloszenia)


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


def _jest_jednostka_uczelni(jednostka):
    return (
        _jednostki_uczelni_bez_sztucznych(jednostka.uczelnia)
        .filter(pk=jednostka.pk)
        .exists()
    )


def _wpisy_historii_autora(autor_id):
    """Teksty z historii autora: wpisy ``LogEntry`` (JSON zmian z admina)
    i komentarze rewizji reversion — z datą."""
    ct = ContentType.objects.get_for_model(Autor)
    wynik = [
        (w.action_time, w.action_flag, w.change_message or "")
        for w in LogEntry.objects.filter(content_type=ct, object_id=str(autor_id))
    ]
    wynik += [
        (v.revision.date_created, CHANGE, v.revision.comment or "")
        for v in Version.objects.filter(
            content_type=ct, object_id=str(autor_id)
        ).select_related("revision")
    ]
    return wynik


def _wpisy_admina(tekst):
    """Wpisy zmian z ``LogEntry.change_message`` (JSON Django) — lista
    ``(akcja, nazwa modelu, opis obiektu)``; tekst nie-JSON → pusta."""
    try:
        dane = json.loads(tekst)
    except (TypeError, ValueError):
        return []
    if not isinstance(dane, list):
        return []
    wynik = []
    for wpis in dane:
        if not isinstance(wpis, dict):
            continue
        for akcja, szczegoly in wpis.items():
            if isinstance(szczegoly, dict) and "name" in szczegoly:
                wynik.append(
                    (akcja, str(szczegoly["name"]), str(szczegoly.get("object", "")))
                )
    return wynik


def _zrodlo_jednostki_znane(aj, zgloszenie, historia):
    """Czy historia autora pokazuje, że powiązanie ``aj`` NIE pochodzi ze
    zgłoszenia: dodano je w module redagowania (inline w edycji autora) albo
    wersja autora sprzed zgłoszenia ma tę jednostkę jako aktualną."""
    # Opis powiązania w historii to ``str(aj)`` z chwili zmiany:
    # „<autor> ↔ <skrót jednostki>”.
    opisy = {str(aj), f"↔ {aj.jednostka.skrot}"}
    for _kiedy, _flaga, tekst in historia:
        for akcja, nazwa, obiekt in _wpisy_admina(tekst):
            if (
                akcja == "added"
                and nazwa == NAZWA_AJ
                and any(obiekt == o or obiekt.endswith(o) for o in opisy)
            ):
                return True
    if zgloszenie is None or zgloszenie.utworzono is None:
        return False
    ct = ContentType.objects.get_for_model(Autor)
    for v in Version.objects.filter(
        content_type=ct,
        object_id=str(aj.autor_id),
        revision__date_created__lt=zgloszenie.utworzono,
    ):
        try:
            pola = v.field_dict
        except RevertError:
            continue  # wersja ze starym schematem — nie da się jej odczytać
        if pola.get("aktualna_jednostka_id") == aj.jednostka_id:
            return True
    return False


def _jednostki_ze_zgloszenia(autor_id, zgloszenie_id, historia):
    """Powiązania autora z jednostkami wybranymi przy nim w zgłoszeniu
    ``zgloszenie_id``, które WYGLĄDAJĄ na założone przez to zgłoszenie: bez
    dat i danych kadrowych, bez żadnej pracy autora w tej jednostce i bez
    śladu w historii, że powstały inaczej. Tylko jednostki uczelni — tylko
    one mogły „zrobić” z autora autora uczelni."""
    if zgloszenie_id is None:
        return []
    zgloszenie = Zgloszenie_Publikacji.global_objects.filter(pk=zgloszenie_id).first()
    jednostki = Zgloszenie_Publikacji_Autor.all_objects.filter(
        rekord_id=zgloszenie_id, autor_id=autor_id
    ).values("jednostka_id")
    return [
        aj
        for aj in Autor_Jednostka.objects.filter(
            autor_id=autor_id, jednostka_id__in=jednostki
        ).select_related("jednostka")
        if _jest_jednostka_uczelni(aj.jednostka)
        and _bez_danych_kadrowych(aj)
        and not _ma_autorstwo_w_jednostce(aj)
        and not _zrodlo_jednostki_znane(aj, zgloszenie, historia)
    ]


def _jest_autorem_jakiejkolwiek_uczelni(autor, pomin_pk):
    """Czy autor jest autorem (``AutorQuerySet.autorzy_uczelni``)
    KTÓREJKOLWIEK uczelni w bazie — po pominięciu powiązań ``pomin_pk`` (ze
    zgłoszenia). Wszystkie uczelnie, nie jedna: w bazie wielu uczelni autor
    obcy dla jednej bywa pracownikiem drugiej. Ta sama definicja co
    w zgłoszeniu i na stronie autora: liczą się jednostki uczelni poza
    sztucznymi (obca jednostka, pk < 0), także te bez ``skupia_pracownikow``
    (doktoranci, emeryci)."""
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


def liczba_prac_tracacych_dyscypline(ad):
    """Ile autorstw straciłoby dyscyplinę po usunięciu przypisania ``ad`` —
    dokładnie tak, jak działa trigger ``bpp_autor_dyscyplina_delete``: dla
    przypisania z jakąkolwiek dyscypliną zeruje ``dyscyplina_naukowa`` we
    wszystkich autorstwach tego autora w pracach z roku ``ad.rok`` (ciągłe,
    zwarte, patenty) — niezależnie od dyscypliny wpisanej w autorstwie."""
    if ad.dyscyplina_naukowa_id is None and ad.subdyscyplina_naukowa_id is None:
        return 0
    return sum(
        m._base_manager.filter(
            autor_id=ad.autor_id,
            rekord__rok=ad.rok,
            dyscyplina_naukowa__isnull=False,
        ).count()
        for m in MODELE_AUTORSTW
    )


def _zmienione_przez_redakcje(ad, utworzono, historia):
    """Czy przypisanie zmieniono po utworzeniu: wpis CHANGE na samym
    przypisaniu albo — typowa ścieżka — zmiana przez inline „Powiązania
    autor-dyscyplina” w edycji autora (wpis w historii autora o zmianie
    przypisania na ten rok)."""
    ct = ContentType.objects.get_for_model(Autor_Dyscyplina)
    if LogEntry.objects.filter(
        content_type=ct, action_flag=CHANGE, object_id=str(ad.pk)
    ).exists():
        return True
    na_rok = f"na rok {ad.rok} "
    for kiedy, _flaga, tekst in historia:
        if utworzono is not None and kiedy < utworzono:
            continue
        for akcja, nazwa, obiekt in _wpisy_admina(tekst):
            if akcja == "changed" and nazwa == NAZWA_AD and na_rok in obiekt + " ":
                return True
    return False


def znajdz_przypadki():
    """Przypisania dyscyplin dopisane przez zgłoszenia autorom, którzy (po
    pominięciu powiązań wyglądających na założone przez te zgłoszenia) nie są
    autorami żadnej uczelni w bazie."""
    ct = ContentType.objects.get_for_model(Autor_Dyscyplina)
    opisy = {}
    for wpis in LogEntry.objects.filter(
        content_type=ct,
        action_flag=ADDITION,
        change_message__contains=ZNACZNIK_ZGLOSZENIA,
    ).order_by("action_time"):
        opisy.setdefault(int(wpis.object_id), (wpis.change_message, wpis.action_time))

    przypadki = []
    for ad in (
        Autor_Dyscyplina.all_objects.filter(pk__in=opisy)
        .select_related("autor", "autor__aktualna_jednostka", "dyscyplina_naukowa")
        .order_by("autor__nazwisko", "autor__imiona", "rok")
    ):
        opis, utworzono = opisy[ad.pk]
        numer = NUMER_ZGLOSZENIA.search(opis)
        zgloszenie_id = int(numer.group(1)) if numer else None
        historia = _wpisy_historii_autora(ad.autor_id)
        ze_zgloszenia = _jednostki_ze_zgloszenia(ad.autor_id, zgloszenie_id, historia)
        if _jest_autorem_jakiejkolwiek_uczelni(
            ad.autor, [aj.pk for aj in ze_zgloszenia]
        ):
            continue
        przypadki.append(
            Przypadek(
                autor=ad.autor,
                zgloszenie_id=zgloszenie_id,
                przypisanie=ad,
                opis_utworzenia=opis,
                jednostki_ze_zgloszenia=ze_zgloszenia,
                zmienione=_zmienione_przez_redakcje(ad, utworzono, historia),
                prace_tracace_dyscypline=liczba_prac_tracacych_dyscypline(ad),
            )
        )
    return przypadki


def znajdz_jednostki_bez_dyscyplin(pomin_autorow=()):
    """Autorzy, którzy wyglądają na obcych dopiero po pominięciu powiązań
    z jednostkami wyglądających na założone przez zgłoszenia — także gdy
    zgłoszenie nie dopisało dyscypliny (zgłoszenia sprzed FD#620). Zawsze
    niepewne: powiązanie bez dat mogła też założyć redakcja albo import.
    ``pomin_autorow`` — pk autorów już opisanych w sekcji głównej."""
    zgloszenia_autora = {}
    for autor_id, zgloszenie_id in (
        Zgloszenie_Publikacji_Autor.all_objects.exclude(autor_id__in=pomin_autorow)
        .values_list("autor_id", "rekord_id")
        .distinct()
    ):
        zgloszenia_autora.setdefault(autor_id, set()).add(zgloszenie_id)

    przypadki = []
    for autor_id, zgloszenia in zgloszenia_autora.items():
        historia = _wpisy_historii_autora(autor_id)
        ze_zgloszen = {}
        for zgloszenie_id in sorted(zgloszenia):
            for aj in _jednostki_ze_zgloszenia(autor_id, zgloszenie_id, historia):
                ze_zgloszen.setdefault(aj.pk, aj)
        if not ze_zgloszen:
            continue
        autor = Autor.global_objects.get(pk=autor_id)
        if _jest_autorem_jakiejkolwiek_uczelni(autor, list(ze_zgloszen)):
            continue
        przypadki.append(
            Przypadek(
                autor=autor,
                zgloszenie_id=min(zgloszenia),
                jednostki_ze_zgloszenia=list(ze_zgloszen.values()),
            )
        )
    przypadki.sort(key=lambda p: (p.autor.nazwisko, p.autor.imiona, p.autor.pk))
    return przypadki
