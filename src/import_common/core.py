from typing import Union

from django.db.models import Q

from .normalization import (
    normalize_funkcja_autora,
    normalize_grupa_pracownicza,
    normalize_kod_dyscypliny,
    normalize_nazwa_dyscypliny,
    normalize_nazwa_jednostki,
    normalize_nazwa_wydawcy,
    normalize_tytul_naukowy,
    normalize_tytul_publikacji,
    normalize_tytul_zrodla,
    normalize_wymiar_etatu,
)

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Dyscyplina_Naukowa,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Tytul,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
    Wymiar_Etatu,
    Zrodlo,
)


def matchuj_wydzial(nazwa):
    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


def matchuj_tytul(tytul: str, create_if_not_exist=False) -> Tytul:
    """
    Dostaje tytuł: pełną nazwę albo skrót
    """

    try:
        return Tytul.objects.get(nazwa__iexact=tytul)
    except (Tytul.DoesNotExist, Tytul.MultipleObjectsReturned):
        return Tytul.objects.get(skrot=normalize_tytul_naukowy(tytul))


def matchuj_funkcja_autora(funkcja_autora: str) -> Funkcja_Autora:
    funkcja_autora = normalize_funkcja_autora(funkcja_autora)
    return Funkcja_Autora.objects.get(
        Q(nazwa__iexact=funkcja_autora) | Q(skrot__iexact=funkcja_autora)
    )


def matchuj_grupa_pracownicza(grupa_pracownicza: str) -> Grupa_Pracownicza:
    grupa_pracownicza = normalize_grupa_pracownicza(grupa_pracownicza)
    return Grupa_Pracownicza.objects.get(nazwa__iexact=grupa_pracownicza)


def matchuj_wymiar_etatu(wymiar_etatu: str) -> Wymiar_Etatu:
    wymiar_etatu = normalize_wymiar_etatu(wymiar_etatu)
    return Wymiar_Etatu.objects.get(nazwa__iexact=wymiar_etatu)


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
    pbn_uid_id: Union[str, None] = None,
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

    if pbn_uid_id is not None:
        try:
            return Autor.objects.get(pbn_uid_id=pbn_uid_id)
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


def matchuj_zrodlo(
    s: Union[str, None],
    issn: Union[str, None] = None,
    e_issn: Union[str, None] = None,
    alt_nazwa=None,
) -> Union[None, Zrodlo]:
    if s is None or str(s) == "":
        return

    if issn is not None:
        try:
            return Zrodlo.objects.get(issn=issn)
        except (Zrodlo.DoesNotExist, Zrodlo.MultipleObjectsReturned):
            pass

    if e_issn is not None:
        try:
            return Zrodlo.objects.get(e_issn=e_issn)
        except (Zrodlo.DoesNotExist, Zrodlo.MultipleObjectsReturned):
            pass

    for elem in s, alt_nazwa:
        if elem is None:
            continue

        elem = normalize_tytul_zrodla(elem)
        try:
            return Zrodlo.objects.get(Q(nazwa__iexact=elem) | Q(skrot__iexact=elem))
        except Zrodlo.MultipleObjectsReturned:
            pass
        except Zrodlo.DoesNotExist:
            if elem.endswith("."):
                try:
                    return Zrodlo.objects.get(
                        Q(nazwa__istartswith=elem[:-1])
                        | Q(skrot__istartswith=elem[:-1])
                    )
                except Zrodlo.DoesNotExist:
                    pass
                except Zrodlo.MultipleObjectsReturned:
                    pass


def matchuj_dyscypline(kod, nazwa):
    nazwa = normalize_nazwa_dyscypliny(nazwa)
    try:
        return Dyscyplina_Naukowa.objects.get(nazwa=nazwa)
    except Dyscyplina_Naukowa.DoesNotExist:
        pass
    except Dyscyplina_Naukowa.MultipleObjectsReturned:
        pass

    kod = normalize_kod_dyscypliny(kod)
    try:
        return Dyscyplina_Naukowa.objects.get(kod=kod)
    except Dyscyplina_Naukowa.DoesNotExist:
        pass
    except Dyscyplina_Naukowa.MultipleObjectsReturned:
        pass


def matchuj_wydawce(nazwa):
    nazwa = normalize_nazwa_wydawcy(nazwa)
    try:
        return Wydawca.objects.get(nazwa=nazwa, alias_dla_id=None)
    except Wydawca.DoesNotExist:
        return


def matchuj_publikacje(
    klass: [Wydawnictwo_Zwarte, Wydawnictwo_Ciagle],
    title,
    year,
    doi=None,
    public_uri=None,
    zrodlo=None,
):

    if doi is not None:
        doi = doi.strip()
        if doi:
            try:
                return klass.objects.get(doi=doi)
            except klass.DoesNotExist:
                pass
            except klass.MultipleObjectsReturned:
                print(f"DOI nie jest unikalne w bazie: {doi}")

    if public_uri is not None:
        try:
            return klass.objects.get(Q(www=public_uri) | Q(public_www=public_uri))
        except klass.MultipleObjectsReturned:
            print(f"www lub public_www nie jest unikalne w bazie: {public_uri}")
        except klass.DoesNotExist:
            pass

    title = normalize_tytul_publikacji(title)

    if zrodlo is not None:
        try:
            return klass.objects.get(
                tytul_oryginalny__istartswith=title, rok=year, zrodlo=zrodlo
            )
        except klass.DoesNotExist:
            pass
        except klass.MultipleObjectsReturned:
            print(
                f"MultipleObjectsReturned dla title={title} rok={year} zrodlo={zrodlo}"
            )

    try:
        return klass.objects.get(tytul_oryginalny__istartswith=title, rok=year)
    except klass.DoesNotExist:
        pass
    except klass.MultipleObjectsReturned:
        print(f"MultipleObjectsReturned dla title={title} rok={year}")
