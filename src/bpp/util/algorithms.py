def _build_knapsack_table(n, W, wt, val):
    """Build the dynamic programming table for knapsack problem."""
    K = [[0 for x in range(W + 1)] for x in range(n + 1)]

    for i in range(n + 1):
        for w in range(W + 1):
            if i == 0 or w == 0:
                K[i][w] = 0
            elif wt[i - 1] <= w:
                K[i][w] = max(val[i - 1] + K[i - 1][w - wt[i - 1]], K[i - 1][w])
            else:
                K[i][w] = K[i - 1][w]

    return K


def _reconstruct_knapsack_items(K, n, W, wt, val, ids):
    """Reconstruct which items were selected in the optimal solution."""
    res = K[n][W]
    lista = []
    w = W

    for i in range(n, 0, -1):
        if res <= 0:
            break

        if res != K[i - 1][w]:
            lista.append(ids[i - 1])
            res = res - val[i - 1]
            w = w - wt[i - 1]

    return lista


def knapsack(W, wt, val, ids, zwracaj_liste_przedmiotow=True):
    """
    :param W: wielkosc plecaka -- maksymalna masa przedmiotów w plecaku (zbierany slot)
    :param wt: masy przedmiotów, które można włożyć do plecaka (sloty prac)
    :param val: ceny przedmiotów, które można włożyc do plecaka (punkty PKdAut prac)
    :param ids: ID prac, które można włożyć do plecaka (rekord.pk)
    :param zwracaj_liste_przedmiotow: gdy True (domyślnie) funkcja zwróci listę z identyfikatorami włożonych
    przedmiotów, gdy False zwrócona lista będzie pusta

    :returns: tuple(mp, lista), gdzie mp to maksymalna możliwa wartość włożonych przedmiotów, a lista to lista
    lub pusta lista gdy parametr `zwracaj_liste_przemiotów` był pusty
    """

    assert len(wt) == len(val) == len(ids), "Listy są różnej długości"

    sum_wt = sum(wt)
    if sum_wt <= W:
        # Jeżeli wszystkie przedmioty zmieszczą się w plecaku, to po co liczyć cokolwiek
        if zwracaj_liste_przedmiotow:
            return sum(val), ids
        return sum(val), []

    n = len(wt)
    K = _build_knapsack_table(n, W, wt, val)

    maks_punkty = K[n][W]
    lista = []

    if zwracaj_liste_przedmiotow:
        lista = _reconstruct_knapsack_items(K, n, W, wt, val, ids)

    return maks_punkty, lista


DEC2INT = 10000


def intsack(W, wt, val, ids):
    pkt, ids = knapsack(
        int(W * DEC2INT),
        [int(x * DEC2INT) for x in wt],
        [int(x * DEC2INT) for x in val],
        ids,
    )
    return pkt / DEC2INT, ids
