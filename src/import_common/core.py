from typing import Union
from uuid import UUID

from django.db.models import Q

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Tytul,
    Wydzial,
    Wymiar_Etatu,
)


def matchuj_wydzial(nazwa):
    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


def normalize_nullboleanfield(s: Union[str, None, bool]) -> Union[bool, None]:
    if isinstance(s, bool):
        return s
    if s is None:
        return
    s = s.strip().lower()

    if s in ["true", "tak", "prawda", "t", "p"]:
        return True
    if s in ["false", "nie", "fałsz", "falsz", "f", "n"]:
        return False


def remove_extra_spaces(s: str) -> str:
    while s.find("  ") >= 0:
        s = s.replace("  ", " ")
    s = s.strip()
    return s


def normalize_skrot(s):
    return remove_extra_spaces(s.lower().replace(" .", ". "))


def normalize_tytul(s):
    return normalize_skrot(s)


def matchuj_tytul(tytul: str, create_if_not_exist=False) -> Tytul:
    """
    Dostaje tytuł: pełną nazwę albo skrót
    """

    try:
        return Tytul.objects.get(nazwa__iexact=tytul)
    except (Tytul.DoesNotExist, Tytul.MultipleObjectsReturned):
        return Tytul.objects.get(skrot=normalize_tytul(tytul))


def normalize_funkcja_autora(s: str) -> str:
    return normalize_skrot(s).lower()


def matchuj_funkcja_autora(funkcja_autora: str) -> Funkcja_Autora:
    funkcja_autora = normalize_funkcja_autora(funkcja_autora)
    return Funkcja_Autora.objects.get(
        Q(nazwa__iexact=funkcja_autora) | Q(skrot__iexact=funkcja_autora)
    )


def normalize_grupa_pracownicza(s: str):
    return normalize_skrot(s)


def matchuj_grupa_pracownicza(grupa_pracownicza: str) -> Grupa_Pracownicza:
    grupa_pracownicza = normalize_grupa_pracownicza(grupa_pracownicza)
    return Grupa_Pracownicza.objects.get(nazwa__iexact=grupa_pracownicza)


def normalize_wymiar_etatu(s: str):
    return normalize_skrot(s)


def matchuj_wymiar_etatu(wymiar_etatu: str) -> Wymiar_Etatu:
    wymiar_etatu = normalize_wymiar_etatu(wymiar_etatu)
    return Wymiar_Etatu.objects.get(nazwa__iexact=wymiar_etatu)


def normalize_nazwa_jednostki(s: str) -> str:
    return remove_extra_spaces(s.strip())


def matchuj_jednostke(nazwa, wydzial=None):
    nazwa = normalize_nazwa_jednostki(nazwa)

    try:
        return Jednostka.objects.get(Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa))
    except Jednostka.DoesNotExist:
        if nazwa.endswith("."):
            nazwa = nazwa[:-1].strip()

        try:
            return Jednostka.objects.get(
                Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa)
            )
        except Jednostka.MultipleObjectsReturned as e:
            if wydzial is None:
                raise e

        return Jednostka.objects.get(
            Q(nazwa__istartswith=nazwa) | Q(skrot__istartswith=nazwa),
            Q(wydzial__nazwa__iexact=wydzial),
        )

    except Jednostka.MultipleObjectsReturned as e:
        if wydzial is None:
            raise e

        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa) | Q(skrot__iexact=nazwa),
            Q(wydzial__nazwa__iexact=wydzial),
        )


def matchuj_autora(
    imiona: str,
    nazwisko: str,
    jednostka: Union[Jednostka, None] = None,
    bpp_id: Union[int, None] = None,
    pbn_uuid: Union[UUID, None] = None,
    system_kadrowy_id: Union[int, None] = None,
    pbn_id: Union[int, None] = None,
    orcid: Union[str, None] = None,
    tytul_str: Union[Tytul, None] = None,
):
    if bpp_id is not None:
        try:
            return Autor.objects.get(pk=bpp_id)
        except Autor.DoesNotExist:
            pass

    if pbn_uuid is not None:
        try:
            UUID(pbn_uuid)
        except (TypeError, ValueError):
            pbn_uuid = None

        if pbn_uuid is not None:
            try:
                return Autor.objects.get(pbn_uuid=pbn_uuid)
            except Autor.DoesNotExist:
                pass

    if system_kadrowy_id is not None:
        try:
            int(system_kadrowy_id)
        except (TypeError, ValueError):
            system_kadrowy_id = None

        if system_kadrowy_id is not None:
            try:
                return Autor.objects.get(system_kadrowy_id=system_kadrowy_id)
            except Autor.DoesNotExist:
                pass

    if pbn_id is not None:
        if isinstance(pbn_id, str):
            pbn_id = pbn_id.strip()

        try:
            pbn_id = int(pbn_id)
        except (TypeError, ValueError):
            pbn_id = None

        if pbn_id is not None:
            try:
                return Autor.objects.get(pbn_id=pbn_id)
            except Autor.DoesNotExist:
                pass

    if orcid:
        try:

            return Autor.objects.get(orcid__iexact=orcid.strip())
        except Autor.DoesNotExist:
            pass

    queries = [
        Q(
            Q(nazwisko__iexact=nazwisko.strip())
            | Q(poprzednie_nazwiska__icontains=nazwisko.strip()),
            imiona__iexact=imiona.strip(),
        )
    ]
    if tytul_str:
        queries.append(queries[0] & Q(tytul__skrot=tytul_str))

    for qry in queries:
        try:
            return Autor.objects.get(qry)
        except (Autor.DoesNotExist, Autor.MultipleObjectsReturned):
            pass

        # wdrozyc matchowanie po tytule
        # wdrozyc matchowanie po jednostce
        # testy mają przejść
        # commit do głównego brancha
        # mbockowska odpisać na zgłoszenie w mantis

        try:
            return Autor.objects.get(qry & Q(aktualna_jednostka=jednostka))
        except (Autor.MultipleObjectsReturned, Autor.DoesNotExist):
            pass

    # Jesteśmy tutaj. Najwyraźniej poszukiwanie po aktualnej jednostce, imieniu, nazwisku,
    # tytule itp nie bardzo się powiodło. Spróbujmy innej strategii -- jednostka jest
    # określona, poszukajmy w jej autorach. Wszak nie musi być ta jednostka jednostką
    # aktualną...

    if jednostka:

        queries = [
            Q(
                Q(autor__nazwisko__iexact=nazwisko.strip())
                | Q(autor__poprzednie_nazwiska__icontains=nazwisko.strip()),
                autor__imiona__iexact=imiona.strip(),
            )
        ]
        if tytul_str:
            queries.append(queries[0] & Q(autor__tytul__skrot=tytul_str))

        for qry in queries:
            try:
                return jednostka.autor_jednostka_set.get(qry).autor
            except (
                Autor_Jednostka.MultipleObjectsReturned,
                Autor_Jednostka.DoesNotExist,
            ):
                pass

    return None
