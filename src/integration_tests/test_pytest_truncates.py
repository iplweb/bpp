"""Ten plik, po uruchomieniu go przez py.test, powinien w pierwszym tescie
uzyc bazy danych, w drugim - jezeli uzywamy opcji --reuse-db - uzyc TRUNCATE,
co kiedyś dawało błąd spowodowany tym, ze nie zarzadzana przez django tabela
bpp_rekord_mat nie bedzie wlaczona do tej klauzuli TRUNCATE, zatem...
"""


def test1(preauth_page):
    return True  # 1/0


def test2(preauth_asgi_page):
    return True  # 1/0
