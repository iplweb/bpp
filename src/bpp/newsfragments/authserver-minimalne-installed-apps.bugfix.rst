Lekki serwer uwierzytelniania (``authserver``, obsługujący logowanie do
Grafany i Dozzle) znów wstaje. Od czasu wprowadzenia faviconów podążających
za hostem workery gunicorna wywracały się przy starcie, bo kod ``bpp``
sięgał po modele aplikacji, których authserver celowo nie instaluje.
Ten sam problem — ujawniający się dopiero przy renderowaniu formularza
logowania — dotyczył edytora zapytań DjangoQL. Dochodzi test odpalający
authserver w osobnym procesie, żeby kolejna taka regresja nie przeszła
niezauważona.
