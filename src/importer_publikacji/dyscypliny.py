"""Dyscypliny autorów bez przypisania na rok pracy (FD#620).

W kroku „Dopasowanie autorów" operator może wybrać autorowi, który nie ma
przypisanej dyscypliny na rok publikacji, jedną z typowych dyscyplin uczelni
(``bpp.util.typowe_dyscypliny``). Walidacja rekordu ``*_Autor`` wymaga, żeby
autor miał na ten rok przypisanie do wybranej dyscypliny
(``Autor_Dyscyplina``) — dlatego przy tworzeniu rekordu zakładamy takie
przypisanie, z wpisem w historii autora.

Autora, który MA przypisanie na ten rok (do innej dyscypliny), nie ruszamy:
zmiana jego dyscyplin to decyzja kadrowa, nie importu. Takiego autora
wykrywamy PRZED utworzeniem rekordu (FD#623) i pokazujemy operatorowi
z odnośnikami do poprawy — zamiast wywracać tworzenie rekordu.

FD#640: autorowi spoza uczelni (``Autor.jest_autorem_uczelni``) nie
zakładamy przypisania na podstawie dyscypliny ze zgłoszenia pracy — np. gdy
redakcja po wczytaniu zgłoszenia odpięła autora od jednostek uczelni.
Taki autor blokuje utworzenie pracy z czytelnym komunikatem
(``autorzy_spoza_uczelni_bez_prawa_do_dyscypliny``).
"""

from django.core.exceptions import ValidationError
from django.db.models import Q

from bpp.models import Autor_Dyscyplina, Uczelnia
from bpp.models.autor import _jednostki_uczelni_bez_sztucznych
from bpp.wersjonowanie import zapewnij_wersje_poczatkowa

from .historia import komunikat_dyscypliny, zapisz_utworzenie, zapisz_zmiane
from .models import ImportedAuthor


def ma_przypisanie_na_rok(autor, rok):
    """Czy autor ma jakiekolwiek przypisanie dyscypliny na ``rok``."""
    if autor is None or not rok:
        return True
    return Autor_Dyscyplina.all_objects.filter(autor=autor, rok=rok).exists()


def _autorzy_z_wybrana_dyscyplina(session):
    """Autorzy sesji, którzy trafią do rekordu z dyscypliną — te same warunki,
    co w ``przypisz_brakujace_dyscypliny`` i ``_add_authors_to_record``."""
    return (
        session.authors.exclude(match_status=ImportedAuthor.MatchStatus.UNMATCHED)
        .exclude(matched_autor=None)
        .exclude(matched_jednostka=None)
        .exclude(matched_dyscyplina=None)
        .select_related(
            "matched_autor", "matched_dyscyplina", "matched_jednostka__uczelnia"
        )
        .order_by("order")
    )


def autorzy_z_niezgodna_dyscyplina(session):
    """FD#623: dopasowani autorzy, których wybranej dyscypliny nie da się
    zapisać w rekordzie — autor MA przypisanie na rok pracy, ale do innej
    dyscypliny (np. dyscyplina ze zgłoszenia, zmiana przypisań w adminie po
    kroku „Autorzy", zmiana roku pracy).

    Autor BEZ przypisania na ten rok nie jest problemem — dostanie je przy
    tworzeniu rekordu (FD#620). Zwraca listę ``ImportedAuthor`` z atrybutem
    ``dyscypliny_na_rok`` (dyscypliny przypisane autorowi na rok pracy).
    """
    rok = (session.normalized_data or {}).get("year")
    if not rok:
        return []

    problemy = []
    for imported in _autorzy_z_wybrana_dyscyplina(session):
        autor = imported.matched_autor
        if not ma_przypisanie_na_rok(autor, rok):
            continue
        dyscyplina = imported.matched_dyscyplina
        # Ten sam warunek, co walidacja rekordu ``*_Autor``
        # (``_waliduj_dyscypline``) — menedżer ``objects``.
        przypisania = Autor_Dyscyplina.objects.filter(autor=autor, rok=rok)
        if przypisania.filter(
            Q(dyscyplina_naukowa=dyscyplina) | Q(subdyscyplina_naukowa=dyscyplina)
        ).exists():
            continue
        imported.dyscypliny_na_rok = [
            d
            for ad in przypisania.select_related(
                "dyscyplina_naukowa", "subdyscyplina_naukowa"
            )
            for d in (ad.dyscyplina_naukowa, ad.subdyscyplina_naukowa)
            if d is not None
        ]
        problemy.append(imported)
    return problemy


def waliduj_dyscypliny_sesji(session):
    """Guard dyscyplin (FD#623): rzuca ``ValidationError``, gdy któryś autor
    ma wybraną dyscyplinę, do której nie jest przypisany na rok pracy.

    Wołany przed utworzeniem pracy — na przeglądzie (``CreateView.post``,
    komunikat z odnośnikami) i na początku ``_create_publication`` (retry,
    zmiany w międzyczasie). Najpierw FD#640 — autor spoza uczelni z
    dyscypliną bez przypisania na rok pracy."""
    waliduj_dyscypliny_autorow_spoza_uczelni(session)
    problemy = autorzy_z_niezgodna_dyscyplina(session)
    if not problemy:
        return
    rok = session.normalized_data.get("year")
    linie = "; ".join(
        f"{ia.matched_autor} (wybrana: {ia.matched_dyscyplina})" for ia in problemy
    )
    raise ValidationError(
        f"Nie można utworzyć pracy — część autorów nie ma na rok {rok} "
        f"przypisania do wybranej dyscypliny: {linie}. Zmień dyscyplinę w kroku "
        f"„Autorzy” albo popraw przypisanie dyscyplin autora i spróbuj ponownie."
    )


def _uczelnia_autora(session, imported):
    """Uczelnia, względem której liczymy „autora uczelni” — uczelnia sesji
    (multi-hosted, ta sama co w ``_add_authors_to_record``), a gdy jej brak
    — uczelnia jednostki, z którą autor trafi do rekordu."""
    if session.uczelnia_id is not None:
        return session.uczelnia
    if imported.matched_jednostka_id is not None:
        return imported.matched_jednostka.uczelnia
    return Uczelnia.objects.get_single_uczelnia_or_none()


def _moze_dostac_przypisanie(session, imported):
    """FD#640: czy autorowi wolno założyć ``Autor_Dyscyplina`` przy tworzeniu
    rekordu.

    Tak, gdy jest autorem uczelni. Autorowi spoza uczelni — tylko gdy
    dyscyplinę wybrał operator importu (nie przyszła ze zgłoszenia) i autor
    trafi do rekordu z jednostką uczelni (zapis pracy dopisze mu ją, więc
    stanie się autorem uczelni — np. nowy pracownik bez przypisań).
    Dyscyplina ze zgłoszenia to niezweryfikowana propozycja: autorowi, który
    w chwili tworzenia pracy nie jest autorem uczelni, jej nie przypisujemy."""
    uczelnia = _uczelnia_autora(session, imported)
    if imported.matched_autor.jest_autorem_uczelni(uczelnia):
        return True
    if imported.dyscyplina_source == ImportedAuthor.DyscyplinaSource.ZGLOSZENIE:
        return False
    if uczelnia is None:
        return False
    return (
        _jednostki_uczelni_bez_sztucznych(uczelnia)
        .filter(pk=imported.matched_jednostka_id)
        .exists()
    )


def autorzy_spoza_uczelni_bez_prawa_do_dyscypliny(session, rok=None):
    """FD#640: dopasowani autorzy z wybraną dyscypliną, bez przypisania na
    rok pracy, którym NIE wolno go założyć (``_moze_dostac_przypisanie``).
    Utworzenie pracy zapisałoby im dyscyplinę bez przypisania — dlatego
    blokujemy je komunikatem (``waliduj_dyscypliny_sesji``)."""
    if rok is None:
        rok = (session.normalized_data or {}).get("year")
    if not rok:
        return []
    return [
        imported
        for imported in _autorzy_z_wybrana_dyscyplina(session)
        if not ma_przypisanie_na_rok(imported.matched_autor, rok)
        and not _moze_dostac_przypisanie(session, imported)
    ]


def waliduj_dyscypliny_autorow_spoza_uczelni(session, rok=None):
    """Rzuca ``ValidationError``, gdy któryś autor spoza uczelni dostałby
    przy tworzeniu pracy przypisanie dyscypliny (FD#640)."""
    problemy = autorzy_spoza_uczelni_bez_prawa_do_dyscypliny(session, rok)
    if not problemy:
        return
    linie = "; ".join(
        f"{ia.matched_autor} (dyscyplina: {ia.matched_dyscyplina})" for ia in problemy
    )
    raise ValidationError(
        "Nie można utworzyć pracy — autorom spoza uczelni nie przypisuje się "
        f"dyscypliny ze zgłoszenia: {linie}. Usuń dyscyplinę autora w kroku "
        "„Autorzy” (albo przypisz autora do jednostki uczelni w jego edycji) "
        "i spróbuj ponownie."
    )


def przypisz_brakujace_dyscypliny(session, record, user):
    """Utwórz ``Autor_Dyscyplina`` (autor, rok pracy, wybrana dyscyplina)
    dla dopasowanych autorów sesji, którzy nie mają przypisania na rok
    ``record``.

    Wołać w transakcji tworzenia rekordu (już zapisanego), PRZED dodaniem
    autorów do rekordu. Każde przypisanie dostaje wpis w historii (dodanie
    przypisania + zmiana autora) w imieniu ``user`` — operatora importu,
    który wybrał dyscyplinę. Zwraca listę utworzonych przypisań.
    """
    utworzone = []
    rok = record.rok
    if not rok:
        return utworzone

    # FD#640: nigdy nie zakładaj przypisania autorowi spoza uczelni —
    # sprawdzane tuż przed zapisem (stan autora mógł się zmienić po kroku
    # „Autorzy”); błąd wycofuje transakcję tworzenia rekordu.
    waliduj_dyscypliny_autorow_spoza_uczelni(session, rok)

    for imported in _autorzy_z_wybrana_dyscyplina(session):
        autor = imported.matched_autor
        if ma_przypisanie_na_rok(autor, rok):
            continue
        zapewnij_wersje_poczatkowa(autor)
        ad = Autor_Dyscyplina.objects.create(
            autor=autor,
            rok=rok,
            dyscyplina_naukowa=imported.matched_dyscyplina,
        )
        komunikat = komunikat_dyscypliny(
            session, record, imported.matched_dyscyplina, rok, user
        )
        zapisz_utworzenie(user, ad, komunikat)
        zapisz_zmiane(user, autor, komunikat)
        utworzone.append(ad)
    return utworzone
