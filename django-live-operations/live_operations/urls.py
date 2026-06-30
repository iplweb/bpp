"""
URL configuration for live_operations.

These are illustrative patterns.  Consumer apps must subclass the generic
views (setting model/form_class), then include their own URL patterns under
the "live_operations" namespace.  See tests/urls.py for a concrete example.

  app_name = "live_operations"
  urlpatterns = [
      path("",                  MyListView.as_view(),    name="index"),
      path("new/",              MyCreateView.as_view(),  name="new"),
      path("<uuid:pk>/",        MyLiveView.as_view(),    name="live"),
      path("<uuid:pk>/cancel/", MyCancelView.as_view(),  name="cancel"),
      path("<uuid:pk>/restart/",MyRestartView.as_view(), name="restart"),
  ]

NOTE: no WebSocket path here (§19.1 — WS uses channels_broadcast's fixed
path /asgi/notifications/ + subscription_token, not a per-pk URL).
"""

app_name = "live_operations"
urlpatterns: list = []
