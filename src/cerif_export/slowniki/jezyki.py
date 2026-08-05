"""Odczyt kodu języka wg IETF BCP 47."""


def kod_jezyka(jezyk):
    """Kod BCP 47 albo ``None``, gdy nieustalony.

    ``jezyk`` to obiekt ``Jezyk`` (już pobrany przez provider) albo
    ``None``. Funkcja jest czysta: żadnych zapytań do bazy.

    Skrótów w rodzaju „ang." nie tłumaczymy tutaj na kody — to robi raz
    migracja danych, a resztę uzupełnia redakcja (patrz komenda
    ``cerif_raport_mapowan``). Lepszy brak ``xml:lang`` niż ``xml:lang``
    z wartością, której nikt nie zrozumie.
    """
    if jezyk is None:
        return None

    return (jezyk.kod_bcp47 or "").strip() or None
