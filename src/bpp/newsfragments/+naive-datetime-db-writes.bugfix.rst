Naprawiono zapis naive datetime do pól ``DateTimeField`` w kilku
miejscach kodu produkcyjnego, które używały ``datetime.now()``
zamiast ``django.utils.timezone.now()``. Przy ``USE_TZ=True`` Django
wywoływało ``RuntimeWarning: received a naive datetime while time
zone support is active`` i interpretowało wartość w lokalnej strefie
czasowej — co przy zmianach DST mogło prowadzić do niespójności
dat w bazie.

Zasięg zmian:

- ``OptimizationRun.finished_at`` — zapisywane w
  ``ewaluacja_optymalizacja.tasks.optimization`` oraz w komendach
  ``solve_uczelnia`` i ``solve_evaluation``.
- ``remove_old_objects`` (``bpp.util``) — filtr wieku plików
  używany m.in. przez ``remove_old_oswiadczenia_export_files``
  i ``remove_old_integrator_files``.
- ``TemplateAdmin.template_updated`` — filtr rekordów do
  przebudowy cache opisu bibliograficznego.
