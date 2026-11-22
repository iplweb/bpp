"""Obiekty danych demo, które pokazują zrzuty ekranu dokumentacji.

Wspólne dla skryptów przygotowujących dane (``bin/docs-demo-*.py``) i dla
scenariuszy zrzutów (``bin/docs-screenshots.py``, który pobiera słownik
:func:`obiekty` poleceniem ``manage.py obiekty_demo_zrzutow``). Dzięki temu
skrypt przygotowujący dane i scenariusz zrzutu wybierają TEN SAM obiekt.

Zasady wyboru — nic po pk ani po nazwie wylosowanej przez generator danych
demo (pk zależą od tego, czy baza była już zapełniana; nazwy jednostek
i czasopism zależą od puli nazw motywu i ``--seed``):

- autorzy obowiązkowi motywu „wiedzmin” (Yennefer Merigold, Margarita
  Merigold, Regis z Cintry…) — po imieniu i nazwisku, bo motyw tworzy ich
  zawsze; Yennefer — przez konto ``yennefer``,
- poza tym pierwsze alfabetycznie obiekty spełniające warunek (przy remisie
  niższe pk),
- obiekty tworzone przez skrypty ``docs-demo-*`` — po tym, co skrypt
  ustawia (ISSN z wykazu, ORCID, stały tytuł).

Brak potrzebnych danych kończy się ``SystemExit`` z czytelnym komunikatem.
Szczegóły: docs/deweloper/zrzuty-ekranu.md.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Count, F

from bpp.demo_data.themes.wiedzmin import WIEDZMIN
from bpp.models import (
    Autor,
    BppUser,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)

INSTRUKCJA = "wygeneruj dane wg docs/deweloper/zrzuty-ekranu.md"

# Czasopisma z wymyślonego wykazu ministerialnego (WYKAZ_DEMO_WIERSZE
# w bin/docs-screenshots.py) — bez „Zoologii Brokilońskiej”, której celowo
# w BPP nie ma. bin/docs-demo-import-list-ministerialnych.py nadaje te nazwy
# i ISSN-y kolejnym alfabetycznie czasopismom spoza wykazu.
ZRODLA_Z_WYKAZU = [
    ("Acta Wiedźmińska", "6746-8071"),
    ("Annales Aretuzańska", "9770-3482"),
    ("Folia Temerska", "7109-3248"),
    ("Studia Aretuzańska", "4990-913X"),
    ("Acta Oxenfurcka", "4936-183X"),
    ("Przegląd Temerska", "9938-6774"),
]
ISSN_ACTA_WIEDZMINSKA = "6746-8071"
ISSN_FOLIA_TEMERSKA = "7109-3248"

# Rekord czasopisma z PBN, który bin/docs-demo-duplikaty.py podpina do
# zdublowanego czasopisma (rozpoznajemy po nim oryginał).
MONGO_ID_ZDUBLOWANEGO_ZRODLA = "5e709189878c28a04737dc6f"

# Tytuł pracy z 2027 r. tworzonej przez bin/docs-demo-nowy-rok.py.
TYTUL_PRACY_2027 = "Eliksiry wiedźmińskie w nowym okresie ewaluacji"

# Osoby spoza BPP do plików importu: pierwsza z listy, której nie ma w bazie.
NIEOBECNI_IMPORTER = [
    ("Zoltan", "Chivay"),
    ("Sheala", "de Tancarville"),
    ("Fringilla", "Vigo"),
]
NIEOBECNI_IMPORT_PRACOWNIKOW = [
    ("Vilgefortz", "z Roggeveen"),
    ("Lydia", "van Bredevoort"),
    ("Artorius", "Vigo"),
]
# Nowa jednostka z pliku importu pracowników (jej jeszcze nie ma w BPP).
NOWA_JEDNOSTKA_IMPORTU = "Pracownia Eliksirów Bojowych"


def brak(co):
    """Przerwij skrypt z komunikatem, czego brakuje w bazie demo."""
    raise SystemExit(f"Brak w bazie demo: {co} — {INSTRUKCJA}.")


def autor(imiona, nazwisko):
    """Autor obowiązkowy motywu (najniższe pk, gdyby miał imiennika)."""
    a = Autor.objects.filter(imiona=imiona, nazwisko=nazwisko).order_by("pk").first()
    if a is None:
        brak(f"autor {imiona} {nazwisko}")
    return a


def autor_konta(username="yennefer"):
    """Autor powiązany z kontem demo (krok 2 w docs/deweloper/zrzuty-ekranu.md)."""
    u = BppUser.objects.filter(username=username, autor__isnull=False).first()
    if u is None:
        brak(f"konto „{username}” powiązane z autorem")
    return u.autor


def yennefer():
    return autor_konta("yennefer")


def margarita():
    return autor("Margarita", "Merigold")


def regis():
    return autor("Regis", "z Cintry")


def aktualna_jednostka(a):
    if a.aktualna_jednostka is None:
        brak(f"aktualna jednostka autora {a}")
    return a.aktualna_jednostka


def wydzialy():
    """Wydziały uczelni demo, alfabetycznie."""
    return Jednostka.objects.filter(parent=None, rodzaj__nazwa="Wydział").order_by(
        "nazwa", "pk"
    )


def wydzial_zgloszen():
    """Wydział, którego zgłoszenia obsługuje redaktor ``vesemir``."""
    w = wydzialy().first()
    if w is None:
        brak("wydział")
    return w


def jednostki_bez_podjednostek(wyklucz=()):
    """Zwykłe jednostki wydziałów (bez podjednostek, skupiające pracowników),
    alfabetycznie. Bez jednostek technicznych („Jednostka Domyślna”, „Obca
    jednostka”, „Pracownicy emerytowani”), które skrypty dokładają po drodze —
    inaczej wynik zależałby od kolejności uruchamiania skryptów."""
    return (
        Jednostka.objects.filter(
            rght=F("lft") + 1,
            parent__rodzaj__nazwa="Wydział",
            skupia_pracownikow=True,
        )
        .exclude(pk__in=[j.pk for j in wyklucz])
        .order_by("nazwa", "pk")
    )


def inne_jednostki(jednostka, ile):
    wynik = list(jednostki_bez_podjednostek(wyklucz=[jednostka])[:ile])
    if len(wynik) < ile:
        brak(f"{ile} jednostki bez podjednostek poza „{jednostka}”")
    return wynik


# --- imiennicy -------------------------------------------------------------


def grupy_imiennikow():
    """Pary (nazwisko, imiona) noszone przez co najmniej dwóch autorów,
    alfabetycznie."""
    return [
        (g["nazwisko"], g["imiona"])
        for g in Autor.objects.values("nazwisko", "imiona")
        .annotate(ile=Count("pk"))
        .filter(ile__gte=2)
        .order_by("nazwisko", "imiona")
    ]


def imiennicy(nazwisko, imiona):
    return list(Autor.objects.filter(nazwisko=nazwisko, imiona=imiona).order_by("pk"))


def autor_z_imiennikiem():
    """Autor do przemapowania prac (bin/docs-demo-przemapowanie-prac-autora.py).

    Pierwsze alfabetycznie imię i nazwisko noszone przez co najmniej dwie
    osoby (bez Geralta z Rivii — jego duplikaty tworzy
    bin/docs-demo-duplikaty.py); spośród nich osoba z największą liczbą prac
    w czasopismach (przy remisie: niższe pk).
    """
    for nazwisko, imiona in grupy_imiennikow():
        if (nazwisko, imiona) == ("z Rivii", "Geralt"):
            continue
        return (
            Autor.objects.filter(nazwisko=nazwisko, imiona=imiona)
            .annotate(prac=Count("wydawnictwo_ciagle_autor"))
            .order_by("-prac", "pk")
            .first()
        )
    brak("dwóch autorów o tym samym imieniu i nazwisku")


def drugi_imiennik(a):
    return (
        Autor.objects.filter(nazwisko=a.nazwisko, imiona=a.imiona)
        .exclude(pk=a.pk)
        .order_by("pk")
        .first()
    )


def nieobecny(kandydaci):
    for imiona, nazwisko in kandydaci:
        if not Autor.objects.filter(imiona=imiona, nazwisko=nazwisko).exists():
            return imiona, nazwisko
    brak("wolne imię i nazwisko spoza BPP (wszyscy kandydaci już są w bazie)")


def imiennicy_importera():
    """Para imienników do importera publikacji (wybór osoby po jednostce):
    druga alfabetycznie grupa imienników o różnych jednostkach (pierwszą
    bierze przemapowanie prac autora), bez Geralta z Rivii."""
    grupy = []
    for nazwisko, imiona in grupy_imiennikow():
        if (nazwisko, imiona) == ("z Rivii", "Geralt"):
            continue
        osoby = imiennicy(nazwisko, imiona)
        jednostki = {o.aktualna_jednostka_id for o in osoby}
        if None not in jednostki and len(jednostki) == len(osoby):
            grupy.append(osoby)
    if not grupy:
        brak("dwóch autorów o tym samym imieniu i nazwisku z różnych jednostek")
    return grupy[1] if len(grupy) > 1 else grupy[0]


def autorzy_pomocniczy():
    """Autorzy, których skrypty mogą zmieniać „w tle” (np. ukryć profil,
    przenieść do koła naukowego) bez psucia innych zrzutów: bez autorów
    obowiązkowych motywu, bez imienników (w tym duplikatów Geralta z Rivii),
    bez współautorów Yennefer, bez osób jednostki Margarity Merigold (import
    pracowników) i bez autorów z dyscypliną w latach 2022–2025 (liczba N,
    sloty)."""
    qs = Autor.objects.all()
    for imiona, nazwisko in WIEDZMIN.autorzy_obowiazkowi:
        qs = qs.exclude(imiona=imiona, nazwisko=nazwisko)
    for nazwisko, imiona in grupy_imiennikow():
        qs = qs.exclude(imiona=imiona, nazwisko=nazwisko)
    y = BppUser.objects.filter(username="yennefer").values("autor_id")
    m = margarita()
    return (
        qs.exclude(nazwisko="z Rivii")
        .exclude(wydawnictwo_ciagle_autor__rekord__autorzy_set__autor__in=y)
        .exclude(aktualna_jednostka_id=m.aktualna_jednostka_id)
        .exclude(autor_dyscyplina__rok__range=(2022, 2025))
        .distinct()
    )


# --- import pracowników ------------------------------------------------------


def import_pracownikow():
    """Osoby do wymyślonego pliku importu pracowników (scenariusz
    ``import-pracownikow``; bin/docs-demo-admin-import-pracownikow.py zostawia
    „Zarządzaj automatycznie” tylko na tej jednostce).

    - jednostka = obecna jednostka Margarity Merigold (pierwsza osoba pliku),
    - „po BPP ID” = pierwsza alfabetycznie osoba tej jednostki, która ma
      imiennika w innej jednostce,
    - „wielu kandydatów” = pierwsza alfabetycznie grupa imienników spoza tej
      jednostki (w pliku bez BPP ID),
    - do trzech kolejnych osób jednostki jest w pliku, dwie następne — nie
      (to one trafiają do propozycji odpięć); bez osób z imiennikami i bez
      autorów obowiązkowych motywu,
    - osoba i jednostka spoza BPP.
    """
    m = margarita()
    jedn = aktualna_jednostka(m)
    if jedn.wydzial is None:
        brak(f"wydział jednostki „{jedn}”")
    osoby = list(
        Autor.objects.filter(aktualna_jednostka=jedn)
        .exclude(pk=m.pk)
        .order_by("nazwisko", "imiona", "pk")
    )
    po_id = None
    for o in osoby:
        inni = [i for i in imiennicy(o.nazwisko, o.imiona) if i.pk != o.pk]
        if inni and all(i.aktualna_jednostka_id != jedn.pk for i in inni):
            po_id = o
            break
    # bez osób z imiennikami (dopasowanie po nazwisku byłoby niejednoznaczne)
    # i bez autorów obowiązkowych motywu — po nich sięgają inne scenariusze,
    # a ten może ich odpiąć od jednostki
    obowiazkowi = set(WIEDZMIN.autorzy_obowiazkowi)
    reszta = [
        o
        for o in osoby
        if o != po_id
        and (o.imiona, o.nazwisko) not in obowiazkowi
        and len(imiennicy(o.nazwisko, o.imiona)) == 1
    ]
    if po_id is None or len(reszta) < 3:
        brak(
            f"jednostka „{jedn}” z osobą mającą imiennika poza nią i co "
            "najmniej 3 innymi osobami"
        )
    n = min(len(reszta), 5)
    wielu = None
    for nazwisko, imiona in grupy_imiennikow():
        grupa = imiennicy(nazwisko, imiona)
        if (nazwisko, imiona) != ("z Rivii", "Geralt") and all(
            g.aktualna_jednostka_id not in (None, jedn.pk) for g in grupa
        ):
            wielu = grupa[0]
            break
    if wielu is None:
        brak("grupa imienników spoza jednostki importu pracowników")
    imie_nowego, nazwisko_nowego = nieobecny(NIEOBECNI_IMPORT_PRACOWNIKOW)
    if Jednostka.objects.filter(nazwa=NOWA_JEDNOSTKA_IMPORTU).exists():
        brak(f"jednostki „{NOWA_JEDNOSTKA_IMPORTU}” nie powinno jeszcze być")
    return {
        "jednostka": jedn,
        "wydzial": jedn.wydzial,
        "margarita": m,
        "po_id": po_id,
        "w_pliku": reszta[: n - 2],
        "spoza_pliku": reszta[n - 2 : n],
        "wielu": wielu,
        "nowy": (imie_nowego, nazwisko_nowego),
    }


# --- czasopisma ---------------------------------------------------------------


def zrodlo_po_issn(issn):
    z = Zrodlo.objects.filter(issn=issn).order_by("pk").first()
    if z is None:
        brak(
            f"czasopismo o ISSN {issn} (uruchom "
            "bin/docs-demo-import-list-ministerialnych.py)"
        )
    return z


def issn_zdublowane():
    """ISSN-y noszone przez więcej niż jedno czasopismo."""
    return list(
        Zrodlo.objects.exclude(issn=None)
        .exclude(issn="")
        .values("issn")
        .annotate(ile=Count("pk"))
        .filter(ile__gte=2)
        .values_list("issn", flat=True)
    )


def zrodlo_do_zdublowania():
    """Czasopismo z największą liczbą prac (bin/docs-demo-duplikaty.py) — bez
    czasopism z wykazu ministerialnego, żeby duplikat nie zmieniał zrzutów
    importu wykazu."""
    z = (
        Zrodlo.objects.exclude(issn=None)
        .exclude(issn="")
        .exclude(issn__in=[issn for _, issn in ZRODLA_Z_WYKAZU])
        .annotate(prac=Count("wydawnictwo_ciagle"))
        .order_by("-prac", "nazwa", "pk")
        .first()
    )
    if z is None:
        brak("czasopismo z ISSN")
    return z


def zrodla_zdublowane():
    """(oryginał, duplikat) utworzone przez bin/docs-demo-duplikaty.py."""
    org = Zrodlo.objects.filter(pbn_uid_id=MONGO_ID_ZDUBLOWANEGO_ZRODLA).first()
    if org is None:
        brak("zdublowane czasopismo (uruchom bin/docs-demo-duplikaty.py)")
    dup = (
        Zrodlo.objects.filter(issn=org.issn, nazwa=org.nazwa.upper())
        .exclude(pk=org.pk)
        .first()
    )
    if dup is None:
        brak("duplikat czasopisma (uruchom bin/docs-demo-duplikaty.py)")
    return org, dup


# --- autorzy i prace ----------------------------------------------------------


def geralt():
    """„Geralt z Rivii” z ORCID — główny rekord z bin/docs-demo-duplikaty.py."""
    g = (
        Autor.objects.filter(nazwisko="z Rivii", imiona="Geralt")
        .exclude(orcid=None)
        .exclude(orcid="")
        .first()
    )
    if g is None:
        brak("Geralt z Rivii z ORCID (uruchom bin/docs-demo-duplikaty.py)")
    return g


def autor_do_zdublowania():
    """Autor, z którego bin/docs-demo-duplikaty.py robi „Geralta z Rivii”."""
    g = (
        Autor.objects.filter(aktualna_jednostka__isnull=False)
        .annotate(prac=Count("wydawnictwo_ciagle_autor"))
        .filter(prac__gte=3)
        .order_by("nazwisko", "imiona", "pk")
        .first()
    )
    if g is None:
        brak("autor z aktualną jednostką i co najmniej 3 pracami")
    return g


def bledna_jednostka_geralta(g):
    """Jednostka, pod którą trafiły prace duplikatu „G. z Rivii”."""
    return inne_jednostki(aktualna_jednostka(g), 1)[0]


def wspolautor(a):
    """Najczęstszy współautor prac w czasopismach (przy remisie
    alfabetycznie)."""
    w = (
        Autor.objects.filter(
            wydawnictwo_ciagle_autor__rekord__autorzy_set__autor=a,
        )
        .exclude(pk=a.pk)
        .annotate(wspolnych=Count("wydawnictwo_ciagle_autor__rekord", distinct=True))
        .order_by("-wspolnych", "nazwisko", "imiona", "pk")
        .first()
    )
    if w is None:
        brak(f"współautor autora {a}")
    return w


def rekord_ze_slotami(a):
    """Praca autora w czasopiśmie z punktami i slotami: najwyżej punktowana
    praca z lat 2022–2025 z policzonymi slotami (przy remisie: nowsza,
    niższe pk)."""
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    pk = {
        rid[1]
        for rid in Cache_Punktacja_Autora.objects.filter(autor=a).values_list(
            "rekord_id", flat=True
        )
        if rid[0] == ct.pk
    }
    r = (
        Wydawnictwo_Ciagle.objects.filter(pk__in=pk, rok__range=(2022, 2025))
        .order_by("-punkty_kbn", "-rok", "pk")
        .first()
    )
    if r is None:
        brak(f"praca autora {a} z policzonymi slotami (bin/docs-demo-sloty.py)")
    return r


def rekord_oswiadczen():
    """Praca z 2023 r. z dyscypliną Regisa z Cintry (bin/docs-demo-oswiadczenia.py):
    pierwsza (po pk) praca trzech autorów, w której jest drugi; gdy takiej nie
    ma — pierwsza, w której jest drugi lub dalszy. Zwraca (praca, indeks
    Regisa wśród autorów pracy)."""
    r = regis()
    wca = (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=r, rekord__rok=2023, dyscyplina_naukowa__isnull=False
        )
        .annotate(autorow=Count("rekord__autorzy_set"))
        .select_related("rekord")
    )
    kandydaci = []
    for w in wca:
        kolejni = list(w.rekord.autorzy_set.order_by("kolejnosc", "pk"))
        idx = [k.pk for k in kolejni].index(w.pk)
        if idx >= 1:
            kandydaci.append((w.autorow != 3, idx != 1, w.rekord.pk, w.rekord, idx))
    if not kandydaci:
        brak("praca z 2023 r., w której Regis z Cintry nie jest pierwszym autorem")
    kandydaci.sort(key=lambda k: k[:3])
    return kandydaci[0][3], kandydaci[0][4]


def _dyscypliny_zgodne(rekord):
    """Czy każdy autor z dyscypliną ma ją (albo subdyscyplinę) przypisaną na
    rok pracy — inaczej formularz pracy nie da się zapisać (rozbieżności
    tworzy np. bin/docs-demo-rozbieznosci-dyscyplin.py)."""
    from bpp.models import Autor_Dyscyplina

    for wa in rekord.autorzy_set.exclude(dyscyplina_naukowa=None):
        if (
            not Autor_Dyscyplina.objects.filter(autor_id=wa.autor_id, rok=rekord.rok)
            .filter(
                models.Q(dyscyplina_naukowa_id=wa.dyscyplina_naukowa_id)
                | models.Q(subdyscyplina_naukowa_id=wa.dyscyplina_naukowa_id)
            )
            .exists()
        ):
            return False
    return True


def rekord_pbn():
    """Artykuł z 2024 r. bez odpowiednika w PBN (do przycisków wysyłki):
    pierwszy po pk, w którym jest autor z przypiętą dyscypliną, afiliujący,
    bez odpowiednika w PBN — wtedy wysyłka pokazuje ostrzeżenie „autor nie
    posiada odpowiednika w PBN” — i którego dyscypliny autorów są zgodne
    z przypisaniami (scenariusz zapisuje formularz pracy)."""
    kandydaci = (
        Wydawnictwo_Ciagle.objects.filter(
            rok=2024,
            charakter_formalny__skrot="AC",
            pbn_uid=None,
            autorzy_set__dyscyplina_naukowa__isnull=False,
            autorzy_set__przypieta=True,
            autorzy_set__afiliuje=True,
            autorzy_set__jednostka__skupia_pracownikow=True,
            autorzy_set__autor__pbn_uid=None,
        )
        .distinct()
        .order_by("pk")
    )
    for r in kandydaci:
        if _dyscypliny_zgodne(r):
            return r
    brak("artykuł z 2024 r. z autorem z dyscypliną (bin/docs-demo-sloty.py)")


def prace_pbn():
    """Prace z lat 2023–2024, z których bin/docs-demo-pbn.py robi kolejkę
    wysyłki do PBN (pierwsze po pk): (16 artykułów, 3 prace zwarte)."""
    from bpp.models import Wydawnictwo_Zwarte

    ciagle = list(
        Wydawnictwo_Ciagle.objects.filter(rok__in=[2023, 2024]).order_by("pk")[:16]
    )
    zwarte = list(
        Wydawnictwo_Zwarte.objects.filter(rok__in=[2023, 2024]).order_by("pk")[:3]
    )
    if len(ciagle) < 16 or len(zwarte) < 3:
        brak("16 artykułów i 3 prace zwarte z lat 2023–2024")
    return ciagle, zwarte


# Indeks pracy (w prace_pbn()[0]), której wysyłka kończy się błędem walidacji
# PBN — scenariusz pokazuje jej szczegóły.
PBN_PRACA_Z_BLEDEM = 3


def rekord_czasopisma(zrodlo, rok):
    """Pierwsza (po pk) praca w czasopiśmie z danego roku."""
    r = Wydawnictwo_Ciagle.objects.filter(zrodlo=zrodlo, rok=rok).order_by("pk").first()
    if r is None:
        brak(f"praca z {rok} r. w czasopiśmie „{zrodlo}”")
    return r


def praca_2027():
    r = Wydawnictwo_Ciagle.objects.filter(tytul_oryginalny=TYTUL_PRACY_2027).first()
    if r is None:
        brak("praca z 2027 r. (uruchom bin/docs-demo-nowy-rok.py)")
    return r


def liczba_n_autorzy(dyscyplina, ile, lata=range(2022, 2026)):
    """Pierwsi (po pk) autorzy z ``dyscyplina`` w każdym roku z ``lata``,
    liczeni do N (aktualna jednostka skupia pracowników). Po pk, nie
    alfabetycznie: bin/docs-demo-duplikaty.py zmienia jednemu autorowi
    nazwisko, a wybór ma być ten sam przed tym skryptem i po nim. Bez autorów
    obowiązkowych motywu — ich pokazują inne zrzuty (np. Yennefer na pół
    etatu zmieniłaby jej stronę i raporty)."""
    obowiazkowi = Autor.objects.none()
    for imiona, nazwisko in WIEDZMIN.autorzy_obowiazkowi:
        obowiazkowi |= Autor.objects.filter(imiona=imiona, nazwisko=nazwisko)
    wynik = list(
        Autor.objects.exclude(pk__in=obowiazkowi.values("pk"))
        .filter(
            aktualna_jednostka__skupia_pracownikow=True,
            autor_dyscyplina__rok__in=lata,
            autor_dyscyplina__dyscyplina_naukowa__nazwa=dyscyplina,
        )
        .annotate(lat=Count("autor_dyscyplina__rok", distinct=True))
        .filter(lat=len(lata))
        .order_by("pk")[:ile]
    )
    if len(wynik) < ile:
        brak(
            f"{ile} autorów z dyscypliną „{dyscyplina}” w latach "
            f"{lata.start}-{lata.stop - 1} (z krokiem bin/docs-demo-sloty.py)"
        )
    return wynik


# bin/docs-demo-liczba-n-faq.py: (dyscyplina, ilu autorów, lata). Osoby
# „biotechnologii” wybieramy po latach 2024–2025, bo skrypt usuwa pierwszej
# z nich lata 2022–2023 („zatrudniona od 2024”) — ta sama reguła wskazuje ją
# więc i przed, i po zmianach skryptu.
LICZBA_N_FILOZOFIA = ("filozofia", 3, range(2022, 2026))
LICZBA_N_BIOTECHNOLOGIA = ("biotechnologia", 2, range(2024, 2026))


def imiennicy_w_sieci(a):
    """Imię i nazwisko noszone przez co najmniej dwie osoby widoczne w sieci
    powiązań autora (domyślny widok: głębokość 2, 15 współautorów) —
    pierwsze alfabetycznie. Wyszukiwarka grafu podświetla wtedy dwa kółka."""
    from powiazania_autorow.queries import _autorzy_widocznej_sieci

    widoczni = _autorzy_widocznej_sieci(a.pk, depth=2, topn=15)
    for nazwisko, imiona in grupy_imiennikow():
        if sum(o.pk in widoczni for o in imiennicy(nazwisko, imiona)) >= 2:
            return imiona, nazwisko
    brak(
        f"dwie osoby o tym samym imieniu i nazwisku w sieci powiązań {a} "
        "(bin/docs-demo-powiazania-autorow.py)"
    )


# --- duplikaty publikacji (bin/docs-demo-duplikaty-publikacji.py) -------------

ROK_DUPLIKATOW_PUBLIKACJI = 2024


def _pierwsza_z_roku(qs, co):
    rekord = (
        qs.filter(rok=ROK_DUPLIKATOW_PUBLIKACJI)
        .order_by("tytul_oryginalny", "pk")
        .first()
    )
    if rekord is None:
        brak(f"{co} z {ROK_DUPLIKATOW_PUBLIKACJI} r.")
    return rekord


def _z_autorami(qs, ile):
    return qs.annotate(ile_autorow=Count("autorzy_set")).filter(ile_autorow__gte=ile)


def duplikaty_publikacji():
    """Prace z 2024 r., które bin/docs-demo-duplikaty-publikacji.py wprowadza
    drugi raz: pierwsze alfabetycznie (po tytule) spełniające warunek. Reguły
    wskazują te same prace także po uruchomieniu skryptu (kopie mają mniej
    autorów albo wyższe pk)."""
    from bpp.models import Wydawnictwo_Zwarte

    artykul_doi = _pierwsza_z_roku(
        _z_autorami(Wydawnictwo_Ciagle.objects.exclude(doi=None).exclude(doi=""), 3),
        "artykuł z DOI i co najmniej 3 autorami",
    )
    artykul_rozdzial = _pierwsza_z_roku(
        _z_autorami(
            Wydawnictwo_Ciagle.objects.filter(
                tytul_oryginalny__contains=" (nr"
            ).exclude(pk=artykul_doi.pk),
            3,
        ),
        "artykuł z „(nr …)” w tytule",
    )
    ksiazka = _pierwsza_z_roku(
        Wydawnictwo_Zwarte.objects.filter(
            charakter_formalny__nazwa="Książka", autorzy_set__isnull=False
        ).distinct(),
        "książka",
    )
    return {
        "artykul_doi": artykul_doi,
        "artykul_rozdzial": artykul_rozdzial,
        "ksiazka": ksiazka,
    }


# --- zgłoszenia publikacji (docs/redaktor/obsluga-zgloszen.md) -------------


def _zgloszenia():
    from zglos_publikacje.models import Zgloszenie_Publikacji

    return Zgloszenie_Publikacji


def _do_obslugi():
    Z = _zgloszenia()
    return Z.objects.filter(
        status__in=[Z.Statusy.NOWY, Z.Statusy.WYMAGA_ZMIAN, Z.Statusy.PO_ZMIANACH]
    ).order_by("tytul_oryginalny", "pk")


def zgloszenie_artykulu():
    """Zgłoszenie artykułu z DOI „do obsługi”: ostatnio zmienione (lista
    zgłoszeń jest tak posortowana, więc stoi na jej górze), przy remisie
    niższe pk."""
    Z = _zgloszenia()
    z = (
        _do_obslugi()
        .filter(rodzaj_zglaszanej_publikacji=Z.Rodzaje.ARTYKUL, doi__isnull=False)
        .exclude(doi="")
        .order_by("-ostatnio_zmieniony", "pk")
        .first()
    )
    if z is None:
        brak("zgłoszenie artykułu z DOI do obsługi (create_demo_data --zgloszen)")
    return z


def zgloszenie_ksiazki():
    """Zgłoszenie monografii „do obsługi” (pierwsze alfabetycznie);
    bin/docs-demo-obsluga-zgloszen.py dokłada mu plik PDF i usuwa adres WWW."""
    Z = _zgloszenia()
    z = _do_obslugi().filter(rodzaj_zglaszanej_publikacji=Z.Rodzaje.MONOGRAFIA).first()
    if z is None:
        brak("zgłoszenie monografii do obsługi (create_demo_data --zgloszen)")
    return z


def zgloszenie_zaimportowane():
    """Zgłoszenie zamknięte przez importer publikacji (pierwsze alfabetycznie)."""
    Z = _zgloszenia()
    z = (
        Z.objects.filter(status=Z.Statusy.ZAIMPORTOWANY)
        .order_by("tytul_oryginalny", "pk")
        .first()
    )
    if z is None:
        brak("zgłoszenie zaimportowane przez importer (create_demo_data --zgloszen)")
    return z


def slowo_wyszukiwania():
    """Słowo do szybkiego wyszukiwania, które znajduje i jednostkę, i prace:
    rdzeń (bez dwóch ostatnich liter) pierwszego dłuższego słowa z nazw
    jednostek (alfabetycznie), występujący też w tytułach prac."""
    for j in jednostki_bez_podjednostek():
        for slowo in j.nazwa.split():
            if len(slowo) < 6:
                continue
            rdzen = slowo[:-2].lower()
            if Wydawnictwo_Ciagle.objects.filter(
                tytul_oryginalny__icontains=rdzen
            ).exists():
                return rdzen
    brak("słowo wspólne dla nazwy jednostki i tytułu pracy")


# Miejsca z motywu „wiedzmin”, które bywają w tytułach prac.
MIEJSCA_W_TYTULACH = (
    "Brokilon",
    "Novigrad",
    "Oxenfurt",
    "Wyzim",
    "Cintr",
    "Skellig",
    "Kaer Morhen",
    "Zerrikani",
)


def slowo_tytulow():
    """Słowo, które jest w tytułach i prac w czasopismach, i książek (wyniki
    globalnego wyszukiwania w module redagowania mają obie grupy)."""
    from bpp.models import Wydawnictwo_Zwarte

    for slowo in MIEJSCA_W_TYTULACH:
        if (
            Wydawnictwo_Ciagle.objects.filter(
                tytul_oryginalny__icontains=slowo
            ).exists()
            and Wydawnictwo_Zwarte.objects.filter(
                tytul_oryginalny__icontains=slowo
            ).exists()
        ):
            return slowo
    brak("słowo wspólne dla tytułów prac w czasopismach i książek")


# Konta demo z docs/deweloper/zrzuty-ekranu.md i skryptów docs-demo-*.
KONTA_DEMO = ("yennefer", "filippa", "vesemir", "regis")

# Okres ewaluacji pokazywany na zrzutach (liczba N, metryki, optymalizacja,
# dwudyscyplinowcy). Bez wyboru ekrany ewaluacji pokazują okres zawierający
# bieżący rok — od 2026 r. pusty okres 2026–2030.
ROK_OKRESU_ZRZUTOW = 2022


def ustaw_okres_zrzutow():
    """Zapamiętaj kontom demo okres ewaluacji zawierający ROK_OKRESU_ZRZUTOW
    (jak wybór na górnym pasku okresu)."""
    from ewaluacja_common.models import OkresEwaluacji, WybranyOkresEwaluacji

    okres = OkresEwaluacji.objects.filter(
        rok_od__lte=ROK_OKRESU_ZRZUTOW, rok_do__gte=ROK_OKRESU_ZRZUTOW
    ).first()
    if okres is None:
        brak(f"okres ewaluacji z rokiem {ROK_OKRESU_ZRZUTOW}")
    for u in BppUser.objects.filter(username__in=KONTA_DEMO):
        WybranyOkresEwaluacji.objects.update_or_create(
            user=u, defaults={"okres": okres}
        )
    return okres


def slowo_do_wyszukania(a):
    """Jedno słowo (imię albo ostatni człon nazwiska), które wskazuje autora
    najmniej dwuznacznie — wyszukiwarki list przyjmują jedno słowo."""
    from django.db.models import Q

    slowa = [a.imiona.split()[0], a.nazwisko.split()[-1]]
    return min(
        slowa,
        key=lambda s: Autor.objects.filter(
            Q(imiona__icontains=s) | Q(nazwisko__icontains=s)
        ).count(),
    )


# --- dla bin/docs-screenshots.py ---------------------------------------------


def _autor(a):
    return {
        "pk": a.pk,
        "imiona": a.imiona,
        "nazwisko": a.nazwisko,
        "nazwa": f"{a.nazwisko} {a.imiona}",
        "url": a.get_absolute_url(),
        "jednostka": a.aktualna_jednostka.nazwa if a.aktualna_jednostka else None,
    }


def _jednostka(j):
    return {"pk": j.pk, "nazwa": j.nazwa, "url": j.get_absolute_url()}


def _rekord(r):
    return {
        "pk": r.pk,
        "tytul": r.tytul_oryginalny,
        "url": r.get_absolute_url(),
        "rok": r.rok,
    }


def _zrodlo(z):
    return {"pk": z.pk, "nazwa": z.nazwa, "slug": z.slug, "issn": z.issn}


def _sprobuj(fn):
    """Obiekt dla scenariusza, którego dane jeszcze nie przygotowano: zamiast
    przerywać całe pobieranie — komunikat; scenariusz sięgający po ten klucz
    padnie dopiero wtedy, gdy go użyje."""
    try:
        return fn()
    except SystemExit as e:
        return {"brak": str(e)}


def obiekty():
    """Słownik (JSON) z obiektami, które pokazują scenariusze zrzutów."""
    y = yennefer()
    y_jedn = aktualna_jednostka(y)

    def importer():
        osoby = imiennicy_importera()
        imiona, nazwisko = nieobecny(NIEOBECNI_IMPORTER)
        return {
            "imiennik": _autor(osoby[0]),
            "imiennik_wlasciwy": _autor(osoby[-1]),
            "nieobecny": {"imiona": imiona, "nazwisko": nazwisko},
        }

    def import_prac():
        d = import_pracownikow()
        return {
            "jednostka": d["jednostka"].nazwa,
            "wydzial": d["wydzial"].nazwa,
            "margarita": _autor(d["margarita"]),
            "po_id": _autor(d["po_id"]),
            "w_pliku": [_autor(a) for a in d["w_pliku"]],
            "spoza_pliku": [_autor(a) for a in d["spoza_pliku"]],
            "wielu": _autor(d["wielu"]),
            "nowy": {"imiona": d["nowy"][0], "nazwisko": d["nowy"][1]},
            "nowa_jednostka": NOWA_JEDNOSTKA_IMPORTU,
        }

    def oswiadczenia():
        rekord, idx = rekord_oswiadczen()
        return {"rekord": _rekord(rekord), "indeks_regisa": idx}

    def duplikaty():
        g = geralt()
        org, dup = zrodla_zdublowane()
        return {
            "geralt": _autor(g),
            "bledna_jednostka": bledna_jednostka_geralta(g).nazwa,
            "zrodlo": _zrodlo(org),
            "zrodlo_duplikat": _zrodlo(dup),
        }

    def przemapowanie():
        a = autor_z_imiennikiem()
        return {"autor": _autor(a), "imiennik": _autor(drugi_imiennik(a))}

    def wykaz():
        acta = zrodlo_po_issn(ISSN_ACTA_WIEDZMINSKA)
        return {
            "acta": _zrodlo(acta),
            "acta_rekord_2024": _sprobuj(
                lambda: _rekord(rekord_czasopisma(acta, 2024))
            ),
            "folia": _zrodlo(zrodlo_po_issn(ISSN_FOLIA_TEMERSKA)),
        }

    def liczba_n():
        od_2024 = liczba_n_autorzy(*LICZBA_N_BIOTECHNOLOGIA)[0]
        return {
            "procent_75": _autor(liczba_n_autorzy(*LICZBA_N_FILOZOFIA)[2]),
            "od_2024": _autor(od_2024),
            "od_2024_szukaj": slowo_do_wyszukania(od_2024),
        }

    return {
        "yennefer": _autor(y),
        "yennefer_jednostka": _jednostka(y_jedn),
        "yennefer_wspolautor": _autor(wspolautor(y)),
        "margarita": _autor(margarita()),
        "regis": _autor(regis()),
        "wydzial_zgloszen": wydzial_zgloszen().nazwa,
        "slowo_wyszukiwania": slowo_wyszukiwania(),
        "slowo_tytulow": slowo_tytulow(),
        "imiennicy_w_sieci": _sprobuj(lambda: " ".join(imiennicy_w_sieci(y))),
        "rekord_ze_slotami": _sprobuj(lambda: _rekord(rekord_ze_slotami(y))),
        "rekord_pbn": _sprobuj(lambda: _rekord(rekord_pbn())),
        "pbn_praca_z_bledem": _sprobuj(
            lambda: _rekord(prace_pbn()[0][PBN_PRACA_Z_BLEDEM])
        ),
        "praca_2027": _sprobuj(lambda: _rekord(praca_2027())),
        "oswiadczenia": _sprobuj(oswiadczenia),
        "import_pracownikow": _sprobuj(import_prac),
        "importer": _sprobuj(importer),
        "duplikaty": _sprobuj(duplikaty),
        "przemapowanie": _sprobuj(przemapowanie),
        "wykaz": _sprobuj(wykaz),
        "liczba_n": _sprobuj(liczba_n),
        "duplikaty_publikacji": _sprobuj(
            lambda: {k: _rekord(v) for k, v in duplikaty_publikacji().items()}
        ),
        "zgloszenia": _sprobuj(
            lambda: {
                "artykul": zgloszenie_artykulu().tytul_oryginalny,
                "ksiazka": zgloszenie_ksiazki().tytul_oryginalny,
                "zaimportowane": zgloszenie_zaimportowane().tytul_oryginalny,
            }
        ),
    }
