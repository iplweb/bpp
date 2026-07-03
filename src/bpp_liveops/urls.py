from django.urls import path

from bpp_liveops import views

app_name = "liveops"

urlpatterns = [
    path("<uuid:pk>/", views.BppLiveView.as_view(), name="live"),
    path("<uuid:pk>/cancel/", views.BppCancelView.as_view(), name="cancel"),
    path("<uuid:pk>/restart/", views.BppRestartView.as_view(), name="restart"),
]
