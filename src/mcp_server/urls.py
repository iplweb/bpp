"""Routing Django dla strony /mcp/ (instrukcja dla człowieka)."""

from django.urls import path

from mcp_server.views import StronaMcp

app_name = "mcp_server"

urlpatterns = [
    path("", StronaMcp.as_view(), name="strona"),
]
