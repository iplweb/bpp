from django.urls import path

from . import views

app_name = "ewaluacja_optymalizacja"

urlpatterns = [
    path("", views.index, name="index"),
    path("runs/", views.run_list, name="run-list"),
    path("runs/<int:pk>/", views.run_detail, name="run-detail"),
    path("comparison/", views.discipline_comparison, name="discipline-comparison"),
    path("bulk/start/", views.start_bulk_optimization, name="bulk-start"),
    path(
        "bulk/status/<int:uczelnia_id>/<str:task_id>/",
        views.bulk_optimization_status,
        name="bulk-status",
    ),
    path("optimize-unpin/", views.optimize_with_unpinning, name="optimize-unpin"),
    path(
        "optimize-unpin-status/<str:task_id>/",
        views.optimize_unpin_status,
        name="optimize-unpin-status",
    ),
    path(
        "reset-pins/<int:pk>/",
        views.reset_discipline_pins,
        name="reset-discipline-pins",
    ),
    path("reset-all-pins/", views.reset_all_pins, name="reset-all-pins"),
    path(
        "reset-all-pins-status/<str:task_id>/",
        views.reset_all_pins_status,
        name="reset-all-pins-status",
    ),
    path("denorm-progress/", views.denorm_progress, name="denorm-progress"),
]
