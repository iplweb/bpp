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
    path(
        "bulk/cancel/<int:uczelnia_id>/<str:task_id>/",
        views.cancel_bulk_optimization,
        name="bulk-cancel",
    ),
    path("optimize-unpin/", views.optimize_with_unpinning, name="optimize-unpin"),
    path(
        "optimize-unpin-status/<str:task_id>/",
        views.optimize_unpin_status,
        name="optimize-unpin-status",
    ),
    path(
        "cancel-optimize-unpin/<str:task_id>/",
        views.cancel_optimize_unpin_task,
        name="cancel-optimize-unpin",
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
    path("unpin-all-sensible/", views.unpin_all_sensible, name="unpin-all-sensible"),
    path(
        "unpin-all-sensible-status/<str:task_id>/",
        views.unpin_all_sensible_status,
        name="unpin-all-sensible-status",
    ),
    path("denorm-progress/", views.denorm_progress, name="denorm-progress"),
    path(
        "trigger-denorm-flush/", views.trigger_denorm_flush, name="trigger-denorm-flush"
    ),
    path(
        "analyze-unpinning/",
        views.analyze_unpinning_opportunities,
        name="analyze-unpinning",
    ),
    path(
        "unpinning-combined-status/<str:task_id>/",
        views.unpinning_combined_status,
        name="unpinning-combined-status",
    ),
    path(
        "cancel-unpinning-task/<str:task_id>/",
        views.cancel_unpinning_task,
        name="cancel-unpinning-task",
    ),
    path(
        "unpinning-status/<str:task_id>/",
        views.unpinning_analysis_status,
        name="unpinning-status",
    ),
    path(
        "unpinning-opportunities/",
        views.unpinning_opportunities_list,
        name="unpinning-list",
    ),
    path(
        "unpinning-opportunities/export-xlsx/",
        views.export_unpinning_opportunities_xlsx,
        name="unpinning-export-xlsx",
    ),
    path(
        "database-verification/",
        views.database_verification_view,
        name="database-verification",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/",
        views.author_works_detail,
        name="author-works-detail",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/export-xlsx/",
        views.export_author_sedn_xlsx,
        name="export-author-sedn-xlsx",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/export-nazbierane-xlsx/",
        views.export_prace_nazbierane_xlsx,
        name="export-prace-nazbierane-xlsx",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/export-nienazbierane-xlsx/",
        views.export_prace_nienazbierane_xlsx,
        name="export-prace-nienazbierane-xlsx",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/export-odpiete-xlsx/",
        views.export_prace_odpiete_xlsx,
        name="export-prace-odpiete-xlsx",
    ),
    path(
        "runs/<int:run_pk>/author/<int:autor_pk>/export-all-xlsx/",
        views.export_all_works_xlsx,
        name="export-all-works-xlsx",
    ),
    path(
        "runs/<int:run_pk>/export-all-authors-zip/",
        views.export_all_authors_zip,
        name="export-all-authors-zip",
    ),
    path(
        "export-all-disciplines-zip/",
        views.export_all_disciplines_zip,
        name="export-all-disciplines-zip",
    ),
    path(
        "export-sedn-report-1/",
        views.export_sedn_report_1,
        name="export-sedn-report-1",
    ),
    path(
        "export-sedn-report-2/",
        views.export_sedn_report_2,
        name="export-sedn-report-2",
    ),
]
