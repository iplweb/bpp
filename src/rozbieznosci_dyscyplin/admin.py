# Register your models here.
import json
from json import JSONDecodeError

from django.http import HttpResponseRedirect
from django.urls import path

from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView

from django.contrib import admin, messages

from django.utils.itercompat import is_iterable

from bpp.admin.helpers import link_do_obiektu


def parse_object_id(object_id, max_len=3):
    # object_id '(29, 93812, 40627)'
    try:
        ret = json.loads(
            "[" + object_id[1:-1][:50].replace("%20", "").replace(" ", "") + "]"
        )  # zamień tuple na listę, bo listę wczyta json
    except JSONDecodeError:
        return None
    except TypeError:
        return None

    if not is_iterable(ret):
        return

    if not len(ret) == max_len:
        return

    for elem in ret:
        if not isinstance(elem, int):
            return

    return ret


class RequestNotifier:
    def __init__(self, request):
        self.request = request

    def info(self, msg):
        messages.info(self.request, msg)

    def warning(self, msg):
        messages.warning(self.request, msg)


class ResultNotifier:
    def __init__(self):
        self.retbuf = []

    def info(self, msg):
        self.retbuf.append(msg)

    warning = info


def real_ustaw_dyscypline(pole, elements, notifier):
    for elem in (RozbieznosciView.objects.filter(pk=elem).first() for elem in elements):
        if elem is None:
            notifier.warning(
                "Lista rekordów zmieniła się podczas operacji. Zakończono przetwarzanie, "
                "zalecane ponowne uruchomienie. ",
            )
            return

        docelowa = getattr(elem, pole)
        if docelowa is None:
            notifier.warning(
                f"Dla rekordu {link_do_obiektu(elem.rekord.original)} nie ustawiono dyscypliny, ponieważ "
                f"za rok {elem.rok} {pole.replace('_', ' ')} autora {link_do_obiektu(elem.autor)} jest żadna. "
                f"Rozbieżność {link_do_obiektu(elem)} pozostaje nierozwiązana. ",
            )
            continue

        wydawnictwo_xxx_autor = elem.get_wydawnictwo_autor_obj()
        wydawnictwo_xxx_autor.dyscyplina_naukowa = docelowa
        wydawnictwo_xxx_autor.save()

        notifier.info(
            f"Dla rekordu {link_do_obiektu(elem.rekord.original)} ustawiono dyscyplinę {docelowa.nazwa} "
            f"dla {link_do_obiektu(elem.autor)}. ",
        )


OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20


def ustaw_dyscypline_task_or_instant(pole, request, elements):
    if len(elements) < OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
        notifier = RequestNotifier(request)
        return real_ustaw_dyscypline(pole, elements, notifier)

    from rozbieznosci_dyscyplin.tasks import task_ustaw_dyscypline

    task_id = task_ustaw_dyscypline.delay(pole, elements)

    link_do_zadania = f'<a target="_blank" href="/admin/django_celery_results/taskresult/?q={task_id}">'

    messages.info(
        request,
        f"Rozpoczęto przetwarzanie w tle. ID zadania: {link_do_zadania}{task_id}</a>. Możesz kliknąc na ID zadania, "
        f"aby zobaczyć, kiedy zostanie ukończone. Możesz tez odświeżyć tą stronę w oczekiwaniu na zmiany. ",
    )

    return task_id


def ustaw_dyscypline(pole, admin, request, qset):
    # Pierwsza sprawa - musimy w tej funkcji odbudować zapytanie, bo admin zbuduje
    # je niepoprawnie, poniewaz RekordView.pk składa się z tuple (3 cyferki)

    if request.POST.get("select_across") == "1":
        elements = list(qset.values_list("pk", flat=True))
    else:
        items = request.POST.getlist("_selected_action")
        elements = [parse_object_id(elem) for elem in items]

    if not elements:
        messages.warning(
            request,
            "Nie dokonano modyfikacji - nic nie zostało zaznaczone przez użytkownika. ",
        )
        return

    return ustaw_dyscypline_task_or_instant(pole, request, elements)


DYSCYPLINA_AUTORA = "dyscyplina_autora"
SUBDYSCYPLINA_AUTORA = "subdyscyplina_autora"


def ustaw_pierwsza_dyscypline(*args, **kw):
    ustaw_dyscypline(DYSCYPLINA_AUTORA, *args, **kw)
    return HttpResponseRedirect(".")


def ustaw_druga_dyscypline(*args, **kw):
    ustaw_dyscypline(SUBDYSCYPLINA_AUTORA, *args, **kw)
    return HttpResponseRedirect(".")


class ReadonlyAdminMixin:
    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RozbieznosciView)
class RozbieznosciViewAdmin(ReadonlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "rekord",
        "rok",
        "autor",
        "dyscyplina_rekordu",
        "dyscyplina_autora",
        "subdyscyplina_autora",
    ]
    list_select_related = [
        "autor__tytul",
        "dyscyplina_autora",
        "subdyscyplina_autora",
        "dyscyplina_rekordu",
        "rekord",
    ]

    list_filter = [
        "dyscyplina_autora",
        "subdyscyplina_autora",
        "dyscyplina_rekordu",
        "rok",
    ]

    list_per_page = 25
    search_fields = ["rekord__tytul_oryginalny", "autor__nazwisko", "autor__imiona"]

    def get_object(self, request, object_id, from_field=None):
        parse_incoming_id = parse_object_id(object_id)
        return RozbieznosciView.objects.get(pk=tuple(parse_incoming_id))

    def get_actions(self, request):
        return {
            "ustaw_pierwsza": (
                ustaw_pierwsza_dyscypline,
                "ustaw_pierwsza",
                "Ustaw pierwszą dyscyplinę autora jako dyscyplinę rekordu",
            ),
            "ustaw_druga": (
                ustaw_druga_dyscypline,
                "ustaw_druga",
                "Ustaw drugą dyscyplinę autora jako dyscyplinę rekordu",
            ),
        }

    def przypisz_wszystkim(self, request, dyscyplina_autora=DYSCYPLINA_AUTORA):
        elements = list(RozbieznosciView.objects.all().values_list("pk", flat=True))
        if elements:
            ustaw_dyscypline_task_or_instant(
                dyscyplina_autora,
                request,
                elements,
            )
            return HttpResponseRedirect("..")

        messages.warning(
            request,
            "Nie dokonano żadnych modyfikacji - nie stwierdzono rekordów z rozbieżnymi dyscyplinami. ",
        )
        return HttpResponseRedirect("..")

    def przypisz_druga_wszystkim(self, request):
        return self.przypisz_wszystkim(request, SUBDYSCYPLINA_AUTORA)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path("przypisz-wszystkim-pierwsza/", self.przypisz_wszystkim),
            path("przypisz-wszystkim-druga/", self.przypisz_druga_wszystkim),
        ]
        return my_urls + urls


@admin.register(RozbieznosciZrodelView)
class RozbieznosciZrodelViewAdmin(ReadonlyAdminMixin, admin.ModelAdmin):
    list_display = [
        "wydawnictwo_ciagle",
        "zrodlo",
        "autor",
        "dyscyplina_naukowa",
    ]
    list_select_related = [
        "wydawnictwo_ciagle",
        "zrodlo",
        "autor",
        "dyscyplina_naukowa",
    ]

    list_filter = [
        "dyscyplina_naukowa",
    ]

    list_per_page = 25
    search_fields = [
        "wydawnictwo_ciagle__tytul_oryginalny",
        "wydawnictwo_ciagle__rok",
        "zrodlo__nazwa",
        "autor__nazwisko",
        "autor__imiona",
        "dyscyplina_naukowa__nazwa",
        "dyscyplina_naukowa__kod",
    ]

    readonly_fields = [
        "wydawnictwo_ciagle",
        "dyscyplina_naukowa",
        "autor",
        "zrodlo",
        "id",
    ]

    def get_object(self, request, object_id, from_field=None):
        parse_incoming_id = parse_object_id(object_id, max_len=4)
        return RozbieznosciZrodelView.objects.get(pk=tuple(parse_incoming_id))
