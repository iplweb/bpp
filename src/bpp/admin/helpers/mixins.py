from contextlib import contextmanager

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers as admin_helpers
from django.db.models import ProtectedError
from django.template.response import TemplateResponse
from django.urls import reverse
from django_softdelete.filters import SoftDeleteFilter

from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.system import Status_Korekty


class ZapiszZAdnotacjaMixin:
    readonly_fields = ("ostatnio_zmieniony",)


class AdnotacjeZDatamiMixin:
    readonly_fields = ("utworzono", "ostatnio_zmieniony", "id")


class AdnotacjeZDatamiOrazPBNMixin:
    readonly_fields = (
        "utworzono",
        "ostatnio_zmieniony",
        "id",
        "pbn_id",
    )


class DomyslnyStatusKorektyMixin:
    status_korekty = forms.ModelChoiceField(
        required=True,
        queryset=Status_Korekty.objects.all(),
        initial=lambda: Status_Korekty.objects.first(),
    )


class Wycinaj_W_z_InformacjiMixin:
    def clean_informacje(self):
        i = self.cleaned_data.get("informacje")
        if i:
            x = i.lower()
            n = 0
            if x.startswith("w:"):
                n = 2
            if x.startswith("w :"):
                n = 3
            if n:
                return i[n:].strip()
        return i


class OptionalPBNSaveMixin:
    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        from bpp.models import Uczelnia

        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is not None:
            if uczelnia.pbn_integracja and uczelnia.pbn_aktualizuj_na_biezaco:
                context.update({"show_save_and_pbn": True})

        return super().render_change_form(request, context, add, change, form_url, obj)

    def response_post_save_change(self, request, obj):
        from .pbn_api.gui import (
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
            sprobuj_wyslac_do_pbn_gui,
        )

        if "_continue_and_pbn" in request.POST:
            sprobuj_wyslac_do_pbn_gui(request, obj)

        elif "_continue_and_pbn_later" in request.POST:
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request, obj)

        else:
            # Otherwise, use default behavior
            return super().response_post_save_change(request, obj)

        # Przekieruj użytkownika na formularz zmian
        opts = self.model._meta
        route = f"admin:{opts.app_label}_{opts.model_name}_change"

        post_url = reverse(route, args=(obj.pk,))

        from django.http import HttpResponseRedirect

        return HttpResponseRedirect(post_url)


class RestrictDeletionWhenPBNUIDSetMixin:
    def has_delete_permission(self, request, obj=None):
        if obj is not None:
            if obj.pbn_uid_id is not None:
                return False
        return super().has_delete_permission(request, obj)


class PokazSkasowaneFilter(SoftDeleteFilter):
    """Filtr „kosz" dla changelisty modeli soft-delete.

    RÓŻNICA WOBEC PAKIETU JEST JEDNA: brak parametru w URL-u znaczy tutaj
    „tylko żywe", a nie „wszystko". Pakietowy ``SoftDeleteFilter`` mapuje
    ``self.value() or 'all'`` na ``'ALL'`` i zwraca cały queryset, więc
    wejście na gołą changelistę pokazywałoby kosz wymieszany z żywymi
    rekordami. Skoro ``get_queryset`` mixinu podaje ``global_objects``,
    to ten filtr jest JEDYNYM miejscem, które chowa kosz — bez tej zmiany
    nie schowałby go nikt.

    SEMANTYKA WARTOŚCI ZOSTAJE PAKIETOWA, celowo: ``is_deleted=true`` to
    rekordy skasowane (pakiet mapuje ``'true'`` na
    ``deleted_at__isnull=False``). Parametr w URL-u czyta się więc wprost
    i da się go bezpiecznie zabookmarkować.
    """

    title = "Kosz"

    def lookups(self, request, model_admin):
        return (
            ("true", "🗑️ Tylko skasowane"),
            ("all", "Wszystkie (żywe + kosz)"),
        )

    def choices(self, changelist):
        """Pierwsza pozycja to stan domyślny — a ten NIE znaczy „wszystkie".

        Odziedziczona etykieta „All" opisywałaby dokładnie odwrotność tego,
        co filtr robi bez parametru.
        """
        wybory = super().choices(changelist)
        domyslny = next(iter(wybory))
        domyslny["display"] = "Bez kosza (tylko żywe)"
        yield domyslny
        yield from wybory

    def queryset(self, request, queryset):
        wartosc = self.value()
        if wartosc == "all":
            return queryset
        if wartosc == "true":
            return queryset.filter(deleted_at__isnull=False)
        return queryset.filter(deleted_at__isnull=True)


class BppSoftDeleteAdminMixin:
    """Kosz w adminie dla modeli soft-delete (5 publikacji + ``Autor``).

    Daje: changelistę nad ``global_objects`` z filtrem kosza, akcje
    „przywróć" / „usuń do kosza (z powodem)" / „usuń trwale"
    (superuser-only) oraz JEDEN punkt wstrzyknięcia ``request.user``.

    ⚠️ MIEJSCE W LIŚCIE BAZ: **OSTATNIE**, tuż przed terminalnym
    ``admin.ModelAdmin`` (albo przed konkretną klasą bazową admina, np.
    ``Wydawnictwo_ZwarteAdmin_Baza``). NIE pierwsze.

    Plan fazy 07 kazał wpinać mixin jako PIERWSZY — to był błąd i wpiąłby
    lukę wielotenantową. ``get_queryset`` poniżej nie woła ``super()``
    (nie ma jak: musi podmienić manager bazowy na ``global_objects``),
    więc postawiony na początku MRO uciąłby cały łańcuch — w tym
    ``SiteFilteredAdminMixin.get_queryset`` w ``AutorAdmin``, które zawęża
    widok nie-superusera do jego uczelni (FD#390). Personel uczelni A
    zobaczyłby i skasował autorów uczelni B.

    Na końcu łańcucha ``get_queryset`` tego mixinu jest jego PODSTAWĄ:
    zwraca ``global_objects``, a wszystkie mixiny stojące wyżej nakładają
    na to swoje filtry normalnie. Pozostałe nadpisane metody
    (``get_actions``, ``get_list_filter``) działają z tej pozycji tak samo,
    bo tamte implementacje w łańcuchu wołają ``super()`` i tylko DOKŁADAJĄ
    pozycje. Strażnikiem tej decyzji jest
    ``test_admin.py::test_staff_widzi_tylko_autorow_swojej_uczelni``.
    """

    def get_queryset(self, request):
        """Podstawa łańcucha: ``global_objects`` (żywe + kosz).

        Skasowanego rekordu nie da się inaczej ani otworzyć, ani
        przywrócić — changeform szuka obiektu w tym samym querysecie.
        Kosz chowa dopiero ``PokazSkasowaneFilter``, więc domyślny widok
        listy się nie zmienia.
        """
        qs = self.model.global_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_urls(self):
        """# SZEW reversion (odłożone).

        Gdy włączymy ``django-reversion``, jego widok „recover deleted"
        (URL ``recover/``) musi tu zostać UKRYTY albo przekierowany na
        ``restore()``. Recover wskrzesza rekord POZA przepływem
        soft-delete: bez zlecenia ``WYSYLKA`` do PBN, bez wpisu
        ``SoftDeleteLog``, bez przeliczenia punktacji i z pominięciem
        warunkowego unique na ``Autor.slug`` (husk trzyma slug
        zarezerwowany). Byłaby to druga, cicha ścieżka przywracania —
        dokładnie to, czemu ta faza ma zapobiegać.
        """
        return super().get_urls()

    def get_list_filter(self, request):
        list_filter = list(super().get_list_filter(request) or [])
        if PokazSkasowaneFilter not in list_filter:
            list_filter.insert(0, PokazSkasowaneFilter)
        return list_filter

    # --- jeden punkt wstrzykniecia usera --------------------------------

    @contextmanager
    def _soft_delete_user_context(self, request):
        """JEDEN punkt wstrzyknięcia ``request.user`` dla całego przepływu
        kosza w adminie: ``delete_model``, ``delete_queryset``,
        ``usun_do_kosza``, ``przywroc_zaznaczone``, ``usun_trwale_zaznaczone``.

        Deleguje do ``soft_delete_context`` z fazy 06 — thread-locala czytają
        receivery sygnałów, bo sygnały pakietu ``django-soft-delete`` niosą
        wyłącznie ``sender`` i ``instance``.

        DLACZEGO KONTEKST, SKORO ``delete()`` PRZYJMUJE ``user=``: bo
        ``hard_delete()`` go NIE przyjmuje. ``BppPkPrzedHardDeleteMixin.
        hard_delete()`` przekazuje argumenty prosto do pakietu, który o
        żadnym userze nie wie — atrybucja trwałego usunięcia ma więc tylko
        ten jeden kanał. Plan fazy 07 zakładał tu ``hard_delete(user=,
        reason=)``; taka sygnatura nie istnieje.

        # SZEW reversion: tutaj (i tylko tutaj) dojdzie w przyszłości
        # ``reversion.set_user(request.user)`` — jeden hook, nie dwa
        # konkurencyjne. Patrz overview, „Kontrakty z reversion".
        """
        with soft_delete_context(
            user=request.user, reason=self._powod_z_requestu(request)
        ):
            yield

    def _powod_z_requestu(self, request):
        """Powód operacji podany na stronie pośredniej (``usun_do_kosza``).

        Puste, gdy ścieżka nie pyta o powód — ``soft_delete_context``
        traktuje pusty łańcuch jako „nie wnoszę informacji" i dziedziczy
        powód z kontekstu zewnętrznego, zamiast go zerować.
        """
        if request.method != "POST":
            return ""
        return request.POST.get("powod", "")

    # --- kasowanie = kosz -----------------------------------------------

    def _soft_delete_jeden(self, request, obj, powod):
        """Soft-delete jednego rekordu; ``False`` gdy guard fazy 04 zablokował.

        POKAZUJEMY KOMUNIKAT Z WYJĄTKU, nie własny. ``raise_if_has_protected_
        children`` zna liczbę i rodzaj powiązań i już je opisuje po polsku;
        drugi tekst tutaj byłby kopią tej samej reguły, która rozjedzie się
        z oryginałem przy pierwszej zmianie listy relacji.

        Łapiemy per instancja, żeby jeden zablokowany autor nie przewracał
        całego zaznaczenia — reszta ma trafić do kosza.
        """
        try:
            obj.delete(user=request.user, reason=powod)
            return True
        except ProtectedError as e:
            self.message_user(request, e.args[0], level=messages.ERROR)
            return False

    def delete_model(self, request, obj):
        """Przycisk „Usuń" na changeformie przenosi do kosza.

        Bez tego nadpisania rekord i tak trafiłby do kosza (``delete()``
        modelu jest miękkie), ale BEZ atrybucji — wpis ``SoftDeleteLog``
        powstawałby z ``user=None``.
        """
        with self._soft_delete_user_context(request):
            # Guard rzuca ProtectedError takze tutaj — Django zrobi wtedy
            # redirect z komunikatem bledu, a rekord zostanie.
            self._soft_delete_jeden(request, obj, self._powod_z_requestu(request))

    def delete_queryset(self, request, queryset):
        """Akcja ``delete_selected`` — soft-delete PER INSTANCJA.

        Nigdy zbiorczo: kaskada ``*_Autor`` (faza 02), ``SoftDeleteLog``
        i sprzątanie ``Cache_Punktacja_*`` wiszą na sygnałach per obiekt,
        a gate w ``BppSoftDeleteQuerySet.update()`` i tak blokuje bulk
        ustawienie ``deleted_at``.
        """
        with self._soft_delete_user_context(request):
            powod = self._powod_z_requestu(request)
            for obj in queryset:
                self._soft_delete_jeden(request, obj, powod)

    # --- akcje kosza ----------------------------------------------------

    @admin.action(description="♻️ Przywróć zaznaczone (z kosza)")
    def przywroc_zaznaczone(self, request, queryset):
        """Przywraca rekordy z kosza przez ten sam hook usera.

        Zaznaczenie idzie z ``global_objects``, więc może zawierać rekordy
        żywe — te pomijamy zamiast wołać na nich ``restore()``. To nie jest
        kosmetyka: ``restore()`` publikacji przelicza punktację dyscyplin
        (operacja licząca, nie ``UPDATE``) i kolejkuje wysyłkę do PBN,
        więc „przywrócenie" nieskasowanego rekordu byłoby kosztownym
        no-opem z fałszywym wpisem w ``SoftDeleteLog``.
        """
        with self._soft_delete_user_context(request):
            przywrocono = 0
            for obj in queryset:
                if obj.deleted_at is None:
                    continue
                obj.restore(user=request.user)
                przywrocono += 1
        if not przywrocono:
            # Najczestsza przyczyna: operator zaznaczyl rekordy na liscie
            # bez filtra kosza, wiec do akcji nie doszedl ani jeden
            # skasowany wiersz. Ciche "przywrocono: 0" wygladaloby jak
            # awaria przywracania.
            self.message_user(
                request,
                "Nie przywrócono nic — w zaznaczeniu nie było rekordów "
                "z kosza. Ustaw filtr „Kosz” na „🗑️ Tylko skasowane”, "
                "zaznacz rekordy i powtórz akcję.",
                level=messages.WARNING,
            )
            return
        self.message_user(
            request,
            f"Przywrócono z kosza: {przywrocono}.",
            level=messages.SUCCESS,
        )

    #: Ile rekordow wypisac na stronie posredniej z powodem. Zaznaczenie
    #: "wszystkie pasujace" (``select_across``) potrafi objac dziesiatki
    #: tysiecy wierszy — wypisanie wszystkich zabiloby te strone, a nikt
    #: i tak nie czyta takiej listy.
    LIMIT_PODGLADU_KOSZA = 50

    @admin.action(description="🗑️ Usuń do kosza (z powodem)")
    def usun_do_kosza(self, request, queryset):
        """Kasowanie do kosza z powodem podanym na stronie pośredniej.

        DLACZEGO OSOBNA AKCJA, SKORO ``delete_selected`` TEŻ IDZIE DO KOSZA:
        bo Django nie ma gdzie zapytać o powód. Jego strona potwierdzenia
        jest zbudowana wokół kolektora (co jeszcze zniknie), nie wokół
        metadanych operacji, a ``SoftDeleteLog.powod`` odpowiada na pytanie
        „dlaczego", na które sam kolektor nie odpowie.

        ``delete_selected`` zostaje działające (kosz bez powodu) — to ta
        sama operacja, tylko uboższa o uzasadnienie.
        """
        if request.POST.get("powod_potwierdzony"):
            with self._soft_delete_user_context(request):
                powod = self._powod_z_requestu(request)
                usunieto = 0
                for obj in queryset:
                    if self._soft_delete_jeden(request, obj, powod):
                        usunieto += 1
            if usunieto:
                self.message_user(
                    request,
                    f"Przeniesiono do kosza: {usunieto}.",
                    level=messages.SUCCESS,
                )
            return None

        ile = queryset.count()
        podglad = list(queryset[: self.LIMIT_PODGLADU_KOSZA])
        context = {
            **self.admin_site.each_context(request),
            "title": "Usuń do kosza",
            "obiekty": podglad,
            "ile_obiektow": ile,
            "ile_ukrytych": max(0, ile - len(podglad)),
            "wybrane_pk": request.POST.getlist(admin_helpers.ACTION_CHECKBOX_NAME),
            "opts": self.model._meta,
            "action_checkbox_name": admin_helpers.ACTION_CHECKBOX_NAME,
            # Przenosimy stan zaznaczenia dalej — bez ``select_across``
            # potwierdzenie zawezilo by "wszystkie pasujace" do biezacej
            # strony i czesc rekordow po cichu nie trafilaby do kosza.
            "action_index": request.POST.get("index", 0),
            "select_across": request.POST.get("select_across", "0"),
        }
        return TemplateResponse(request, "admin/bpp/soft_delete_powod.html", context)

    @admin.action(description="❌ Usuń TRWALE (nieodwracalnie, tylko superuser)")
    def usun_trwale_zaznaczone(self, request, queryset):
        """Opróżnianie kosza: fizyczne skasowanie rekordów.

        TYLKO Z KOSZA, nigdy wprost z rekordu żywego — i nie jest to
        ostrożnościowy rytuał. ``Cache_Punktacja_*`` nie ma FK do
        publikacji (klucz to tablica ``[content_type_id, pk]``), więc nie
        sprząta jej ani kolektor Django, ani triggery. Kasuje ją dopiero
        receiver ``post_soft_delete`` (faza 06). Twarde skasowanie rekordu
        z pominięciem kosza zostawiłoby więc wiersze punktacji wskazujące
        na nieistniejący rekord — i liczące się do ewaluacji.

        Podwójny gate na superusera (tu i w ``get_actions``) jest celowy:
        ``get_actions`` decyduje o WIDOCZNOŚCI, ta metoda o WYKONANIU.
        Django odrzuca akcje spoza ``get_actions``, ale to jest operacja
        nieodwracalna — jeden mechanizm obronny na nią za mało.
        """
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Trwałe usuwanie jest dostępne wyłącznie dla superużytkownika.",
                level=messages.ERROR,
            )
            return

        with self._soft_delete_user_context(request):
            usunieto = 0
            pominieto = 0
            for obj in queryset:
                if obj.deleted_at is None:
                    pominieto += 1
                    continue
                # hard_delete() NIE przyjmuje user=/reason= — atrybucję
                # niesie wyłącznie kontekst powyżej.
                obj.hard_delete()
                usunieto += 1

        if pominieto:
            self.message_user(
                request,
                f"Pominięto rekordów spoza kosza: {pominieto}. Trwale usuwać "
                "można wyłącznie to, co jest już w koszu — najpierw „🗑️ Usuń "
                "do kosza”, potem „❌ Usuń TRWALE”.",
                level=messages.WARNING,
            )
        if usunieto:
            self.message_user(
                request,
                f"Usunięto trwale (nieodwracalnie): {usunieto}.",
                level=messages.SUCCESS,
            )

    def get_actions(self, request):
        """Dokłada akcje kosza do tych zebranych przez resztę łańcucha.

        Wołamy ``super()`` i tylko DOKŁADAMY klucze — dlatego mixin działa
        także z ostatniej pozycji w MRO (patrz docstring klasy), mimo że
        wyżej stoją ``AutorAdmin.get_actions`` i ``ExportActionsMixin.
        get_actions``.
        """
        actions = super().get_actions(request)
        actions["usun_do_kosza"] = self.get_action("usun_do_kosza")
        actions["przywroc_zaznaczone"] = self.get_action("przywroc_zaznaczone")
        if request.user.is_superuser:
            actions["usun_trwale_zaznaczone"] = self.get_action(
                "usun_trwale_zaznaczone"
            )
        else:
            # Gdyby ktos dopisal ta akcje wyzej w lancuchu — zdejmij.
            actions.pop("usun_trwale_zaznaczone", None)
        return actions
