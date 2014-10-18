# -*- encoding: utf-8 -*-

from django import shortcuts
from django.db.models import Q
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.http.response import HttpResponseNotFound, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView
from django import forms
from sendfile import sendfile

from bpp.views.utils import JSONResponseMixin


from bpp.models import Autor, Jednostka, Wydawnictwo_Zwarte, \
    Wydawnictwo_Ciagle, Praca_Doktorska, Praca_Habilitacyjna, Patent, Zrodlo, \
    Uczelnia, BppUser


def zapytaj_o_autora(q):
    myQ = Q()
    for elem in q.split(" "):
        myQ = myQ & Q(
            Q(nazwisko__istartswith=elem) |
            Q(imiona__istartswith=elem) |
            Q(poprzednie_nazwiska__istartswith=elem))
    return myQ


def navigation_autocomplete(
        request, template_name='navigation_autocomplete.html'):
    q = request.GET.get('q', '')
    context = {'q': q}

    # % url admin:bpp_wydawnictwo_zwarte_change wydawnictwo.pk %}

    # element.model
    # element.label
    # element.url

    #{% for wydawnictwo in wydawnictwa_zwarte %}
    #{% for wydawnictwo in wydawnictwa_ciagle %}
    #{% for patent in patenty %}
    #{% for praca in prace_doktorskie %}
    #{% for praca in prace_habilitacyjne %}
    #{% for jednostka in jednostki %}
    #{% for autor in autorzy %}
    #{% for user in users %}

    elements = []
    user = request.user

    def doloz(model, qset, label=lambda x: unicode(x)):

        for obj in qset:

            if model == Rekord:
                app_label = 'bpp'
                object_name = obj.content_type.model
                object_pk = obj.object_id
            else:
                app_label = obj._meta.app_label
                object_name = obj._meta.object_name.lower()
                object_pk = obj.pk

            url = 'admin:%s_%s_change' % (app_label, object_name)

            elements.append(dict(
                model=object_name,
                label=label(obj),
                url=reverse(url, args=(object_pk, ))
            ))

    if user.is_staff or user.groups.filter(name="administracja"):
        User = get_user_model()

        qset = User.objects.filter(
            Q(username__istartswith=q) |
            Q(first_name__istartswith=q) |
            Q(last_name__istartswith=q) |
            Q(email__istartswith=q)
        ).distinct()[:6]

        doloz(User, qset)

    if user.is_staff or user.groups.filter(name="struktura"):
        doloz(Jednostka, Jednostka.objects.fulltext_filter(q)[:6])

    if user.is_staff or user.groups.filter(name="indeks_autorow") or \
            user.groups.filter(name="wprowadzanie danych"):

        doloz(Autor, Autor.objects.fulltext_filter(q)[:6])
        doloz(Zrodlo, Zrodlo.objects.fulltext_filter(q)[:6])
        doloz(Rekord, Rekord.objects.fulltext_filter(q).only(
            "tytul_oryginalny", "content_type_id", "object_id").select_related()[:6])

    # DSU
    elements = [(x['label'], x) for x in elements]
    elements.sort()
    elements = [x[1] for x in elements]

    context['elements'] = elements

    return shortcuts.render(request, template_name, context)


def user_navigation_autocomplete(
        request, template_name='user_navigation_autocomplete.html'):
    elements = []
    q = request.GET.get('q', '')
    context = {'q': q}

    def doloz(model, qset, url, label=lambda x: unicode(x), attr='slug'):
        no_obj = 0

        for obj in qset:
            elements.append(dict(
                model=model._meta.object_name.lower(),
                label=label(obj),
                url=reverse(url, args=(getattr(obj, attr), ))
            ))

    def doloz_rekord(qset):
        for obj in qset:
            elements.append(dict(
                model=obj.content_type.model,
                label=obj.tytul_oryginalny,
                url=reverse(
                    "bpp:browse_praca",
                    args=(obj.content_type.model, obj.object_id))
            ))

    doloz(
        Jednostka, Jednostka.objects.fulltext_filter(q).only("pk", "nazwa")[:5],
        'bpp:browse_jednostka')

    doloz(Autor, Autor.objects.fulltext_filter(q).only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul").select_related()[:5],
          'bpp:browse_autor')

    doloz(Zrodlo,
          Zrodlo.objects.fulltext_filter(q).only("pk", "nazwa", "poprzednia_nazwa")[:5],
          'bpp:browse_zrodlo')

    doloz_rekord(Rekord.objects.fulltext_filter(q).only("tytul_oryginalny", "content_type__model", "object_id")[:6])

    # DSU
    elements = [(x['label'], x) for x in elements]
    elements.sort()
    elements = [x[1] for x in elements]

    context['elements'] = elements

    return shortcuts.render(request, template_name, context)


def autorform_dependant_js(request):
    return shortcuts.render(request, "autorform_dependant.js", {
        'class': request.GET.get('class', 'NO CLASS ON REQUEST').lower()
    }, content_type='text/javascript')


def root(request):
    """Zachowanie domyślne: przekieruj nas na pierwszą dostępną w bazie danych
    uczelnię, lub wyświetl komunikat jeżeli nie ma żadnych uczelni wpisanych do
    bazy danych."""
    try:
        # TODO: jeżeli będzie więcej, niż jeden obiekt Uczelnia, to co?
        uczelnia = Uczelnia.objects.all()[0]
    except IndexError:
        return shortcuts.render(request, "browse/brak_uczelni.html")

    return shortcuts.redirect(
        reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))


def favicon(request):
    try:
        fn = Uczelnia.objects.get(pk=1).favicon_ico
    except Uczelnia.DoesNotExist:
        raise Http404

    try:
        return sendfile(request, fn.path)
    except ValueError:
        raise Http404


from .mymultiseek import *


@csrf_exempt
def update_multiseek_title(request):
    v = request.POST.get('value')
    if not v or not len(v):
        v = ''
    request.session["MULTISEEK_TITLE"] = v
    return HttpResponse(v)