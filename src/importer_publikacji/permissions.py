from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404

from bpp.const import GR_WPROWADZANIE_DANYCH


def scope_import_do_uczelni(qs, request, uczelnia_path="uczelnia"):
    """Zawęź queryset importera do uczelni oglądającego (multi-hosted).

    Importer publikacji to WSPÓLNY warsztat redaktorów: w obrębie jednej
    uczelni redaktorzy widzą i kontynuują nawzajem swoje sesje/paczki. Ale w
    trybie multi-host dane jednej uczelni NIE mogą wyciec do redaktora innej
    (uwagi #2/#3 reviewera — dotąd obiekty pobierano po samym ``pk``).

    No-op (pełny dostęp), gdy:

    * user jest superuserem (admin cross-uczelnia widzi wszystko),
    * w systemie jest dokładnie jedna uczelnia (single-install — filtr zbędny),
    * brak mapowania Site→Uczelnia (``uczelnia is None``) — jak reszta systemu
      nie izolujemy (nie chcemy nagle ukryć wszystkiego).

    ``uczelnia_path`` — ścieżka ORM do FK uczelni: ``"uczelnia"`` dla
    ``ImportSession``/``MultipleWorksImport``, ``"parent__uczelnia"`` dla wpisu
    paczki (``MultipleWorksImportEntry``).
    """
    from bpp.models import Uczelnia
    from bpp.util.uczelnia_scope import tylko_jedna_uczelnia

    if request.user.is_superuser or tylko_jedna_uczelnia():
        return qs
    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None:
        return qs
    return qs.filter(**{uczelnia_path: uczelnia})


class ImporterPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return (
            user.is_superuser
            or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
        )

    def scope_do_uczelni(self, qs, uczelnia_path="uczelnia"):
        """Zawęź queryset do uczelni oglądającego (patrz
        :func:`scope_import_do_uczelni`)."""
        return scope_import_do_uczelni(qs, self.request, uczelnia_path)

    def get_scoped_or_404(self, model, uczelnia_path="uczelnia", **kwargs):
        """``get_object_or_404`` zawężone do uczelni oglądającego. Obiekt spoza
        uczelni redaktora daje 404 (nie da się go odczytać ani zmodyfikować)."""
        qs = self.scope_do_uczelni(model._default_manager.all(), uczelnia_path)
        return get_object_or_404(qs, **kwargs)
