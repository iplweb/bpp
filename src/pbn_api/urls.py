# https://publikacje.up.lublin.pl/pbn_api/callback?ott=dc37f06a-30bd-445a-80bd-199745f65d62


from django.urls import path

from .views import TokenLandingPage, TokenRedirectPage

app_name = "pbn_api"

urlpatterns = [
    path("callback", TokenLandingPage.as_view(), name="callback"),
    path("authorize", TokenRedirectPage.as_view(), name="authorize"),
]
