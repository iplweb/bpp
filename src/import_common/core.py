from uuid import UUID

from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Q

from bpp.models import Autor, Autor_Jednostka, Jednostka, Wydzial


def matchuj_wydzial(nazwa):
    try:
        return Wydzial.objects.get(nazwa__iexact=nazwa.strip())
    except Wydzial.DoesNotExist:
        pass


def matchuj_jednostke(nazwa):
    try:
        return Jednostka.objects.get(
            Q(nazwa__iexact=nazwa.strip()) | Q(skrot__iexact=nazwa.strip())
        )
    except MultipleObjectsReturned:
        return None
    except Jednostka.DoesNotExist:
        pass


def matchuj_autora(
    imiona,
    nazwisko,
    jednostka=None,
    pbn_uuid=None,
    system_kadrowy_id=None,
    pbn_id=None,
    orcid=None,
    tytul_str=None,
):
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
