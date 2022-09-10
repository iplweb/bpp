from django.db.models import F

from bpp.util import knapsack


def zbieraj_sloty(
    autor_id,
    zadany_slot,
    rok_min,
    rok_max,
    minimalny_pk=None,
    dyscyplina_id=None,
    jednostka_id=None,
    akcja=None,
):
    from bpp.models.cache import Cache_Punktacja_Autora_Query

    rekordy = Cache_Punktacja_Autora_Query.objects.filter(
        rekord__rok__gte=rok_min, rekord__rok__lte=rok_max, autor_id=autor_id
    )
    if dyscyplina_id is not None:
        rekordy = rekordy.filter(dyscyplina_id=dyscyplina_id)

    if jednostka_id is not None:
        rekordy = rekordy.filter(jednostka_id=jednostka_id)

    if minimalny_pk is not None:
        rekordy = rekordy.filter(rekord__punkty_kbn__gte=minimalny_pk)

    res = [
        (name, int(size), int(value))
        for name, size, value in rekordy.values_list(
            "pk", F("slot") * 10000, F("pkdaut") * 10000
        )
    ]  # name, size, value

    id_wpisow_cpaq = [x[0] for x in res]
    sloty = [x[1] for x in res]
    punkty = [x[2] for x in res]

    if akcja == "wszystko":
        return sum(punkty) / 10000, id_wpisow_cpaq, sum(sloty) / 10000

    maks, lista = knapsack(int(zadany_slot * 10000), sloty, punkty, id_wpisow_cpaq)

    sloty_ret = 0
    for elem in lista:
        index = id_wpisow_cpaq.index(elem)
        sloty_ret += sloty[index]

    return maks / 10000, lista, sloty_ret / 10000


def group_emails(group_name):
    "Zwraca maile osób z danej grupy"
    from bpp.models.profile import BppUser

    return (
        BppUser.objects.filter(groups__name=group_name)
        .exclude(email="")
        .exclude(email=None)
        .exclude(email="brak@email.pl")
        .values_list("email", flat=True)
        .distinct()
    )


def editors_emails():
    # E-maile redaktorów -- osób, które mają grupę "wprowadzanie danych"
    from bpp.const import GR_WPROWADZANIE_DANYCH

    return group_emails(GR_WPROWADZANIE_DANYCH)


def zgloszenia_publikacji_emails():
    from bpp.const import GR_ZGLOSZENIA_PUBLIKACJI

    ret = group_emails(GR_ZGLOSZENIA_PUBLIKACJI)
    if ret:
        return ret

    # W sytuacji gdy grupa "zgłoszenia publikacji" nie ma żadnych użytkowników
    # e-mail zostaje wysłany do redaktorów
    return editors_emails()
