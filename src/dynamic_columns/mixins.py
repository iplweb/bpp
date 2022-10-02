from functools import cached_property

from dynamic_columns.models import ModelAdmin

# TODO: 1) checks for list_display_always (czy kolumna istnieje)


class DynamicColumnsMixin:
    @cached_property
    def _enabled(self):
        return ModelAdmin.objects.enable(self)

    def get_list_display(self, request):
        ret = self._enabled
        return ret.get_list_display(model_admin=self, request=request)

    def get_list_select_related(self, request):
        # If the type of self.list_select_related is a list, just return it.
        # This is standard Django's ModelAdmin behavior:
        if isinstance(self.list_select_related, list):
            return self.list_select_related

        # IF the type of self.list_select_related is a dict, this means it describes
        # a mapping between a column name (and this column may or may not be visible)
        # and it's select_related name.
        columns = self.get_list_display(request)

        ret = set()
        for elem in self.list_select_related:
            if elem in columns or elem == "__always__":
                values = self.list_select_related[elem]
                if isinstance(values, str):
                    ret.add(values)
                elif isinstance(values, (list, set)):
                    [ret.add(_x) for _x in values]
                else:
                    raise NotImplementedError(
                        f"Handling of values of type {type(values)} not implemented"
                    )
        print(ret)
        return ret
