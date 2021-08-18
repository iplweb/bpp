from django.db.models import Max

from bpp.models.multiseek import BppMultiseekVisibility


class BppMultiseekVisibilityMixin:
    """Klasa zapewniająca funkcję .enable, która to z kolei odpytuje bazę danych
    o dostępność lub niedostępność danego obiektu dla danego użytkownika."""

    def _get_or_create(self):
        try:
            vis = BppMultiseekVisibility.objects.get(field_name=self.field_name)
        except BppMultiseekVisibility.DoesNotExist:
            max_sort_order = BppMultiseekVisibility.objects.aggregate(Max("sort_order"))
            vis = BppMultiseekVisibility.objects.create(
                label=self.label,
                field_name=self.field_name,
                public=self.public,
                authenticated=True,
                staff=True,
                sort_order=(max_sort_order["sort_order__max"] or 0) + 1,
            )

        return vis

    def option_enabled(self):
        return True

    def enabled(self, request=None):
        if not self.option_enabled():
            return False

        vis = self._get_or_create()

        if request is None or not request.user.is_authenticated:
            # Jeżeli nie został podany parametr 'request' lub użytkownik jest anonimowy
            # to zwróc wartość parametru 'widoczny dla wszystkich'
            return vis.public

        if request.user.is_staff:
            return vis.staff

        if request.user.is_authenticated:
            return vis.authenticated

        raise NotImplementedError("This should not happen")
