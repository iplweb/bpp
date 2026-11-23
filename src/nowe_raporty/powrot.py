"""Powrót z formularza „Źródła danych” do otwartego raportu (FD#448).

Wspólne dla widoku raportu (buduje odnośnik) i admina (wraca po zapisaniu),
żeby nazwa parametru nie rozjechała się między nimi.
"""

from django.utils.http import url_has_allowed_host_and_scheme, urlencode

#: Parametr adresu formularza źródła danych: dokąd wrócić po zapisaniu.
PARAMETR_POWROTU = "powrot"


def z_powrotem(url, powrot):
    """``url`` z doklejonym parametrem powrotu."""
    return f"{url}?{urlencode({PARAMETR_POWROTU: powrot})}"


def adres_powrotu(request):
    """Adres z ``?powrot=`` albo ``None``.

    Przyjmujemy wyłącznie adresy tego samego serwisu — parametr pochodzi
    z URL-a, więc bez tej kontroli byłby otwartym przekierowaniem.
    """
    url = request.GET.get(PARAMETR_POWROTU)
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return None
