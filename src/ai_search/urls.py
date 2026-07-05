from django.urls import path

from ai_search.views import ZapytanieAIView

app_name = "ai_search"

urlpatterns = [
    path("", ZapytanieAIView.as_view(), name="index"),
]
