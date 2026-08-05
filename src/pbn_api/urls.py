# https://publikacje.up.lublin.pl/pbn_api/callback?ott=dc37f06a-30bd-445a-80bd-199745f65d62


from django.urls import path

from .views import TokenLandingPage, TokenRedirectPage

app_name = "pbn_api"

# Kanoniczny redirect_uri to ".../pbn_api/callback". W praktyce jednak bywa
# wpisywany recznie po stronie PBN i regularnie trafiaja sie literowki
# ("calback", "kalbak", ...). Zamiast liczyc na bezbledna konfiguracje,
# przyjmujemy komplet typowych przekrecen tego samego slowa — kazdy wariant,
# z ukosnikiem i bez, laduje na tym samym TokenLandingPage. Wersja "callback"
# jako jedyna ma name=, zeby reverse("pbn_api:callback") zwracalo
# deterministycznie poprawny URL; aliasy sa wylacznie "przychodzace".
CALLBACK_ALIASES = [
    "callback",  # kanoniczna forma
    "calback",  # jedno "l"
    "calbak",  # jedno "l" + "ck" -> "k"
    "calbac",  # jedno "l" + brak "k"
    "callbak",  # "ck" -> "k"
    "callbac",  # brak "k"
    "callbck",  # brak "a"
    "callbakc",  # przestawione "ck" -> "kc"
    "kallback",  # "c" -> "k"
    "kallbak",  # "c" -> "k" + "ck" -> "k"
    "kalback",  # "c" -> "k" + jedno "l"
    "kalbak",  # "c" -> "k" + jedno "l" + "ck" -> "k"
    "kalbac",  # "c" -> "k" + jedno "l" + brak "k"
    "collback",  # "a" -> "o"
    "colback",  # "a" -> "o" + jedno "l"
]

urlpatterns = [
    path("authorize", TokenRedirectPage.as_view(), name="authorize"),
]

for _alias in CALLBACK_ALIASES:
    _kwargs = {"name": "callback"} if _alias == "callback" else {}
    urlpatterns += [
        # bez ukosnika oraz z ukosnikiem — patrz komentarz wyzej
        path(_alias, TokenLandingPage.as_view(), **_kwargs),
        path(f"{_alias}/", TokenLandingPage.as_view()),
    ]
