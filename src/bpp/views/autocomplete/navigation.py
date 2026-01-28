"""Navigation autocomplete views for global and admin search."""

from collections import OrderedDict

from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import IntegerField
from django.db.models.expressions import RawSQL
from django.db.models.query_utils import Q
from django.utils.text import capfirst
from queryset_sequence import QuerySetSequence

from bpp.models import Uczelnia
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.profile import BppUser
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from import_common.core import normalized_db_isbn
from import_common.normalization import normalize_isbn

from .mixins import SanitizedAutocompleteMixin
from .search_services import (
    globalne_wyszukiwanie_autora,
    globalne_wyszukiwanie_jednostki,
    globalne_wyszukiwanie_journal,
    globalne_wyszukiwanie_publication,
    globalne_wyszukiwanie_scientist,
    globalne_wyszukiwanie_zrodla,
    jest_pbn_uid,
)


class StaffRequired(UserPassesTestMixin):
    """Mixin requiring user to be staff."""

    def test_func(self):
        return self.request.user.is_staff


class DjangoApp:
    """Pseudo-model representing a Django app in search results."""

    def __init__(self, app_label, verbose_name, app_url):
        self.pk = f"app:{app_label}"
        self.app_label = app_label
        self.verbose_name = verbose_name
        self.app_url = app_url

    def __str__(self):
        return self.verbose_name


class DjangoModel:
    """Pseudo-model representing a Django model in search results."""

    def __init__(
        self,
        app_label,
        model_name,
        verbose_name,
        changelist_url,
        add_url=None,
        can_add=False,
        is_add_action=False,
    ):
        # Distinguish between list and add actions in the pk
        action_suffix = ":add" if is_add_action else ""
        self.pk = f"model:{app_label}:{model_name}{action_suffix}"
        self.app_label = app_label
        self.model_name = model_name
        self.verbose_name = verbose_name
        self.changelist_url = changelist_url
        self.add_url = add_url
        self.can_add = can_add
        self.is_add_action = is_add_action

    def __str__(self):
        if self.is_add_action:
            return f"Dodaj {self.verbose_name.lower()}"
        return self.verbose_name


class GlobalNavigationAutocomplete(
    SanitizedAutocompleteMixin, Select2QuerySetSequenceView
):
    """Global navigation autocomplete for public search."""

    paginate_by = 40

    def get_result_label(self, result):
        if isinstance(result, Autor):
            if result.aktualna_funkcja_id is not None:
                return str(result) + ", " + str(result.aktualna_funkcja.nazwa)
        elif isinstance(result, Rekord):
            return result.opis_bibliograficzny_cache
        return str(result)

    def get_results(self, context):
        """Return a list of results usable by Select2.

        It will render as a list of one <optgroup> per different content type
        containing a list of one <option> per model.
        """
        groups = OrderedDict()

        for result in context["object_list"]:
            groups.setdefault(type(result), [])
            groups[type(result)].append(result)

        return [
            {
                "id": None,
                "text": capfirst(self.get_model_name(model)),
                "children": [
                    {
                        "id": self.get_result_value(result),
                        "text": self.get_result_label(result),
                    }
                    for result in results
                ],
            }
            for model, results in groups.items()
        ]

    def get_queryset(self):
        if not hasattr(self, "q"):
            return []

        if not self.q:
            return []

        querysets = []
        globalne_wyszukiwanie_jednostki(querysets, self.q)

        globalne_wyszukiwanie_autora(querysets, self.q)

        globalne_wyszukiwanie_zrodla(querysets, self.q)

        # Rekord

        rekord_qset_ftx = Rekord.objects.fulltext_filter(self.q)

        rekord_qset_doi = Rekord.objects.filter(doi__iexact=self.q)
        rekord_qset_isbn = Rekord.objects.filter(isbn__iexact=self.q)
        rekord_qset_pbn = None
        if jest_pbn_uid(self.q):
            rekord_qset_pbn = Rekord.objects.filter(pbn_uid_id=self.q)

        qry = Q(pk__in=rekord_qset_doi.values_list("pk"))
        qry |= Q(pk__in=rekord_qset_isbn)
        if rekord_qset_pbn:
            qry |= Q(pk__in=rekord_qset_pbn.values_list("pk"))

        rekord_qset = Rekord.objects.filter(qry).only("tytul_oryginalny")

        if hasattr(self, "request") and self.request.user.is_anonymous:
            uczelnia = Uczelnia.objects.get_for_request(self.request)
            if uczelnia is not None:
                rekord_qset_ftx = rekord_qset_ftx.exclude(
                    status_korekty_id__in=uczelnia.ukryte_statusy("podglad")
                )

                rekord_qset = rekord_qset.exclude(
                    status_korekty_id__in=uczelnia.ukryte_statusy("podglad")
                )
        querysets.append(rekord_qset_ftx)
        querysets.append(rekord_qset)

        this_is_an_id = False
        try:
            this_is_an_id = int(self.q)
        except (TypeError, ValueError):
            pass

        if this_is_an_id:
            querysets.append(
                Rekord.objects.annotate(
                    _object_id=RawSQL("(id)[2]", [], output_field=IntegerField())
                )
                .filter(_object_id=this_is_an_id)
                .only("tytul_oryginalny")
            )

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class AdminNavigationAutocomplete(
    SanitizedAutocompleteMixin, StaffRequired, Select2QuerySetSequenceView
):
    """Admin navigation autocomplete for staff search."""

    paginate_by = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.django_items = []

    def get_result_value(self, result):
        """Get the value to use for the result's ID."""
        if isinstance(result, DjangoApp | DjangoModel):
            return result.pk
        return super().get_result_value(result)

    def get_result_label(self, result):
        """Format the display of results in the dropdown."""
        if isinstance(result, DjangoApp):
            return f"📁 {result.verbose_name}"
        elif isinstance(result, DjangoModel):
            if result.is_add_action:
                return f"➕ Dodaj {result.verbose_name.lower()}"
            return f"📄 {result.verbose_name}"

        # Publikacje - wyświetl opis_bibliograficzny_cache
        elif isinstance(
            result,
            (
                Wydawnictwo_Zwarte,
                Wydawnictwo_Ciagle,
                Patent,
                Praca_Doktorska,
                Praca_Habilitacyjna,
            ),
        ):
            return result.opis_bibliograficzny_cache or str(result)

        # Default handling for other types
        return super().get_result_label(result)

    def get_model_name(self, model):
        """Return the display name for grouping results."""
        if model == DjangoApp:
            return "Aplikacje modułu redagowania"
        elif model == DjangoModel:
            return "Modele modułu redagowania"

        # Default handling for other types
        return super().get_model_name(model)

    def get_results(self, context):
        """Override to include Django items and use get_result_label for formatting."""
        # Build results with get_result_label instead of str()
        # (the parent library uses str() which doesn't call our get_result_label)
        groups = OrderedDict()

        for result in context["object_list"]:
            groups.setdefault(type(result), [])
            groups[type(result)].append(result)

        results = [
            {
                "id": None,
                "text": capfirst(self.get_model_name(model)),
                "children": [
                    {
                        "id": self.get_result_value(result),
                        "text": self.get_result_label(result),
                    }
                    for result in model_results
                ],
            }
            for model, model_results in groups.items()
        ]

        # If we have Django items, add them to the results
        if self.django_items:
            # Group Django items by type
            apps = [item for item in self.django_items if isinstance(item, DjangoApp)]
            models = [
                item for item in self.django_items if isinstance(item, DjangoModel)
            ]

            # Add Django apps group
            if apps:
                results.append(
                    {
                        "id": None,
                        "text": "Aplikacje Django",
                        "children": [
                            {
                                "id": self.get_result_value(app),
                                "text": self.get_result_label(app),
                            }
                            for app in apps
                        ],
                    }
                )

            # Add Django models group
            if models:
                results.append(
                    {
                        "id": None,
                        "text": "Modele Django",
                        "children": [
                            {
                                "id": self.get_result_value(model),
                                "text": self.get_result_label(model),
                            }
                            for model in models
                        ],
                    }
                )

        return results

    def _check_model_permissions(self, user, app_label, model_name):
        """Check permissions for a model and return permission dict."""
        return {
            "view": user.has_perm(f"{app_label}.view_{model_name}"),
            "add": user.has_perm(f"{app_label}.add_{model_name}"),
            "change": user.has_perm(f"{app_label}.change_{model_name}"),
            "delete": user.has_perm(f"{app_label}.delete_{model_name}"),
        }

    def _model_matches_query(self, model):
        """Check if model matches the search query."""
        model_verbose_name = model._meta.verbose_name_plural
        model_verbose_name_singular = getattr(
            model._meta, "verbose_name", model._meta.verbose_name_plural
        )
        q_lower = self.q.lower()
        return (
            q_lower in model_verbose_name.lower()
            or q_lower in model._meta.model_name.lower()
            or q_lower in model_verbose_name_singular.lower()
        )

    def _add_model_entries(self, results, model, perms, changelist_url, add_url):
        """Add model entries to results if they match the search query."""
        from django.utils.text import capfirst

        if not self._model_matches_query(model):
            return

        app_label = model._meta.app_label
        model_verbose_name = model._meta.verbose_name_plural
        model_verbose_name_singular = getattr(
            model._meta, "verbose_name", model._meta.verbose_name_plural
        )

        # Add entry for model list (changelist)
        django_model = DjangoModel(
            app_label=app_label,
            model_name=model._meta.model_name,
            verbose_name=capfirst(model_verbose_name),
            changelist_url=changelist_url,
            add_url=add_url,
            can_add=perms["add"],
            is_add_action=False,
        )
        results.append(django_model)

        # Add separate entry for adding new instance if user has permission
        if perms["add"]:
            django_model_add = DjangoModel(
                app_label=app_label,
                model_name=model._meta.model_name,
                verbose_name=capfirst(model_verbose_name_singular),
                changelist_url=changelist_url,
                add_url=add_url,
                can_add=True,
                is_add_action=True,
            )
            results.append(django_model_add)

    def get_django_apps_and_models(self):
        """Get Django apps and models accessible to the current user."""
        from django.apps import apps
        from django.contrib import admin
        from django.urls import reverse
        from django.utils.text import capfirst

        results = []

        if not hasattr(self, "request"):
            return results

        user = self.request.user
        admin_site = admin.site
        app_dict = {}

        for model, _model_admin in admin_site._registry.items():
            app_label = model._meta.app_label

            # Check if user has any permission for this model
            if not user.has_module_perms(app_label):
                continue

            # Check specific permissions
            perms = self._check_model_permissions(
                user, app_label, model._meta.model_name
            )

            # Skip if no view permission
            if not perms["view"] and not perms["change"]:
                continue

            # Get URLs
            changelist_url = reverse(
                f"admin:{app_label}_{model._meta.model_name}_changelist"
            )
            add_url = None
            if perms["add"]:
                add_url = reverse(f"admin:{app_label}_{model._meta.model_name}_add")

            # Add model entries to results if they match the search query
            self._add_model_entries(results, model, perms, changelist_url, add_url)

            # Build app dict for app-level search
            if app_label not in app_dict:
                app_config = apps.get_app_config(app_label)
                app_dict[app_label] = {
                    "name": capfirst(app_config.verbose_name),
                    "app_label": app_label,
                    "app_url": reverse(
                        "admin:app_list", kwargs={"app_label": app_label}
                    ),
                    "has_models": True,
                }

        # Add matching apps to results
        for app_label, app_info in app_dict.items():
            if (
                self.q.lower() in app_info["name"].lower()
                or self.q.lower() in app_label.lower()
            ):
                django_app = DjangoApp(
                    app_label=app_label,
                    verbose_name=app_info["name"],
                    app_url=app_info["app_url"],
                )
                results.append(django_app)

        return results

    def _build_publication_filter(self, klass):
        """Build filter for publication models."""
        query_filter = Q(tytul_oryginalny__icontains=self.q)

        # Try to add primary key filter if q is an integer
        try:
            int(self.q)
            query_filter |= Q(pk=self.q)
        except (TypeError, ValueError):
            pass

        # Add DOI filter for non-Patent models
        if klass != Patent:
            query_filter |= Q(doi__iexact=self.q)

        # Add PBN UID filter if applicable
        if len(self.q) == 24 and self.q.find(" ") == -1:
            if "pbn_uid" in [fld.name for fld in klass._meta.fields]:
                query_filter |= Q(pbn_uid__pk=self.q)

        return query_filter

    def _add_publication_querysets(self, querysets):
        """Add querysets for publication models."""
        for klass in [
            Wydawnictwo_Zwarte,
            Wydawnictwo_Ciagle,
            Patent,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        ]:
            query_filter = self._build_publication_filter(klass)

            # Handle ISBN normalization if applicable
            annotate_isbn = False
            if hasattr(klass, "isbn"):
                ni = normalize_isbn(self.q)
                if len(ni) < 20:
                    query_filter |= Q(normalized_isbn=ni)
                    annotate_isbn = True

            if annotate_isbn:
                qset = klass.objects.annotate(
                    normalized_isbn=normalized_db_isbn
                ).filter(query_filter)
            else:
                qset = klass.objects.filter(query_filter)

            querysets.append(
                qset.only("tytul_oryginalny", "opis_bibliograficzny_cache")
            )

    def get_queryset(self):
        if not self.q or len(self.q) < 1:
            return []

        querysets = []

        # Add user queryset
        querysets.append(
            BppUser.objects.filter(username__icontains=self.q).only("pk", "username")
        )

        # Add organizational units and other querysets
        globalne_wyszukiwanie_jednostki(querysets, self.q)

        querysets.append(
            Konferencja.objects.filter(
                Q(nazwa__icontains=self.q) | Q(skrocona_nazwa__icontains=self.q)
            ).only("pk", "nazwa", "baza_inna", "baza_wos", "baza_scopus")
        )

        globalne_wyszukiwanie_autora(querysets, self.q)
        globalne_wyszukiwanie_zrodla(querysets, self.q)
        globalne_wyszukiwanie_scientist(querysets, self.q)
        globalne_wyszukiwanie_journal(querysets, self.q)
        globalne_wyszukiwanie_publication(querysets, self.q)

        # Add publication querysets
        self._add_publication_querysets(querysets)

        # Store Django apps and models separately (don't add to QuerySetSequence)
        self.django_items = self.get_django_apps_and_models()

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)
