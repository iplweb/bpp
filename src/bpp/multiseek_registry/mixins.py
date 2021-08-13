from django.db.models import Max

from bpp.models.multiseek import BppMultiseekVisibility


class BppMultiseekVisibilityMixin:
    """Klasa zapewniająca funkcję .enable, która to z kolei odpytuje bazę danych
    o dostępność lub niedostępność danego obiektu dla danego użytkownika."""

    def enabled(self, request=None):
        try:
            vis = BppMultiseekVisibility.objects.get(name=self.name)
        except BppMultiseekVisibilityMixin.DoesNotExist:
            max_sort_order = BppMultiseekVisibilityMixin.objects.aggregate(
                Max("sort_order")
            )
            vis = BppMultiseekVisibility.objects.create(
                label=self.label,
                name=self.name,
                public=self.public,
                authorized=True,
                staff=True,
                sort_order=(max_sort_order["sort_order__max"] or 0) + 1,
            )

        if request is None or not request.user.is_authenticated:
            # Jeżeli nie został podany parametr 'request' lub użytkownik jest anonimowy
            # to zwróc wartość parametru 'widoczny dla wszystkich'
            return vis.public

        if request.user.is_staff and vis.staff:
            return True

        if request.user.is_authenticated and vis.authenticated:
            return True

        return False
