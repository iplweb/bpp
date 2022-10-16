from functools import cached_property

from dynamic_columns.models import ModelAdmin

# TODO: 1) checks for list_display_always (czy kolumna istnieje)


class DynamicColumnsMixin:
    """This is a mixin you use in your ModelAdmin class.

    It enables the ModelAdmin to:

    1) automatically create its in-database representation (``ModelAdmin`` model),

    2) basing on this mixin settings, it creates a list of columns in-database
       (``ModelAdminColumn`` instances) thus giving the end-user ability to enable or disable
       them,

    3) keeps a list of "forbidden" columns, eg. columns that should never be visible.
    """

    # ``list_display_always``
    #
    # this is a list of always-displayed columns. Those columns are displayed
    # first in the list view of Django's Admin, they cannot be enabled or disabled,
    # they cannot be moved. This does what the "old" ``list_display`` did:

    # list_display_always = []

    # ``list_display_default``
    #
    # this is a list of columns enabled by default, that can be moved or
    # disabled (hidden) via admin interface at some point later. Here one can
    # give the end-user a reasonable selection of initially visible columns:

    # list_display_default = []

    # ``list_display_allowed``
    #
    # this is a list of columns not enabled by default, but they can be enabled
    # in the admin later:

    # list_display_allowed = []

    # ``list_display_forbidden``
    #
    # You can use "__all__" string in above variables if you want to give the
    # user access to all the attributes of the model to be used as columns
    # in the admin; this way user can decide what the user wants. But the
    # column selection could be too broad. We use ``list_display_forbidden``
    # to avoid some columns.
    #
    # This is a list of columns that are forbidden - those columns should not
    # appear in database, and even if they do - they should not be allowed to be
    # displayed.
    #
    # ``list_display_forbidden`` is in fact a list of regex that will be matched
    # against column names.

    # list_display_forbidden = []

    # ``list_select_related``
    #
    # It becomes a dictionary now! Unless this code becomes Django's mainstream,
    # please ignore system check ``admin.E117`` -- add the line below to ``settings.py``
    #
    #   SILENCED_SYSTEM_CHECKS = ["admin.E117"]
    #
    # Example ``list_select_related`` below:
    #
    #     list_select_related = {
    #         "__always__": ["some", "columns"],
    #         "some_other_column": [
    #             "some_other_column",
    #         ],
    #         "admin_callable": ["another_column", "maybe_more"],
    #     }

    @cached_property
    def _modeladmin_enabled(self):
        return ModelAdmin.objects.enable(self)

    def get_list_display(self, request):
        ret = self._modeladmin_enabled
        return ret.get_list_display(model_admin=self, request=request)

    def get_list_select_related(self, request):
        """
        As DynamicColumnsMixin allowed Django to display variable number of columns,
        the ``list_select_related`` attribute can be also dynamic. Why use ``select_related``
        with a column name, if that column was disabled by the end-user?

        DynamicColumnsMixin assumes, that ``list_select_related`` can be also a dictionary.
        If you define it as one, unless this code becomes Django's mainstream,
        please ignore system check ``admin.E117`` -- add the line below to ``settings.py``

            SILENCED_SYSTEM_CHECKS = ["admin.E117"]

        Example ``list_select_related`` below:

            list_select_related = {
                "__always__": ["some", "columns"],
                "some_other_column": [
                    "some_other_column",
                ],
                "admin_callable": ["another_column", "maybe_more"],
            }

        The key ``__always__`` is special -- it contains the columns that will be always
        returned by DynamicColumnsMixin.get_select_related. Think about it as
        "old list_select_related".
        """

        # If the type of self.list_select_related is a list, just return it.
        # This is standard Django's ModelAdmin behavior:
        if isinstance(self.list_select_related, (list, tuple, set)):
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
                elif isinstance(values, (list, set, tuple)):
                    [ret.add(_x) for _x in values]
                else:
                    raise NotImplementedError(
                        f"Handling of values of type {type(values)} not implemented"
                    )
        return ret
