"""Ten plik, po uruchomieniu go przez py.test, powinien w pierwszym tescie 
uzyc bazy danych, w drugim - jezeli uzywamy opcji --reuse-db - uzyc TRUNCATE,
co w obecnym stanie (12.08.2015) daje blad spowodowany tym, ze nie zarzadzana
przez django tabela bpp_rekord_mat nie bedzie wlaczona do tej klauzuli TRUNCATE,
zatem... zatem trzeba cos z tym zrobic, zeby pytest mogl spokojnie dzialac 
dla serwisu django_bpp z opcja --reuse-db (bo szybciej...)
"""

def test1(preauth_browser):
    return True # 1/0

