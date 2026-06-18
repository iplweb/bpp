import traceback
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.core.management import BaseCommand
from django.template import loader
from django.test import RequestFactory
from minify_html import minify as html_minify

from bpp.context_processors.config import bpp_configuration
from bpp.context_processors.global_nav import user as global_nav_user
from bpp.context_processors.google_analytics import google_analytics
from bpp.context_processors.microsoft_auth import microsoft_auth_status
from bpp.context_processors.testing import testing
from bpp.models import Uczelnia

# JavaScript usuwający z wygenerowanej strony 500 wpisy menu logowania/raportów/
# ewaluacji (statyczny plik nie zna stanu zalogowania użytkownika).
CLEANUP_SCRIPT = """
<script type="text/javascript">
    // Remove login, raporty and ewaluacja menus from 500 error page (added by generate_500_page command)
    $(document).ready(function() {
        // Remove login menu entry that contains "zaloguj" text
        $('a:contains("zaloguj")').closest('li').remove();
        // Remove raporty menu entry that contains "raporty" text
        $('a:contains("raporty")').closest('li').remove();
        // Remove ewaluacja menu entry that contains "ewaluacja" text
        $('a:contains("ewaluacja")').closest('li').remove();
    });
</script>
"""


class Command(BaseCommand):
    help = "Generuje statyczne pliki 500.html dla nginx (generyczny + per-domena)"

    def handle(self, *args, **options):
        static_root = Path(settings.STATIC_ROOT)

        # 1. Generyczny fallback — pojedyncza uczelnia (single-site) albo
        #    neutralna „niezdefiniowana uczelnia" (multi-site bez dopasowania
        #    domeny). nginx serwuje go przez `try_files ... /static/500.html`,
        #    gdy brak strony per-domena. Host z ALLOWED_HOSTS, by jakikolwiek
        #    procesor/template wołający get_host() nie wywalił DisallowedHost.
        generic_html = self._render_500(
            Uczelnia.objects.get_single_uczelnia_or_none(), self._valid_host()
        )
        # Source-dir (gitignored) — zbierany przez collectstatic na buildzie,
        # zachowuje wsteczny kontrakt z obrazami pre-multi-hosted.
        bpp_app_dir = Path(__file__).parent.parent.parent
        self._write(bpp_app_dir / "static" / "500.html", generic_html)
        # $STATIC_ROOT — autorytatywne miejsce serwowane przez nginx w runtime.
        self._write(static_root / "500.html", generic_html)

        # 2. Per-domena — każdy Site dostaje stronę z brandingiem swojej
        #    uczelni w `$STATIC_ROOT/500/<domena>.html`.
        count = 0
        for site in Site.objects.all():
            try:
                uczelnia = Uczelnia.objects.get_for_site(site)
                html = self._render_500(uczelnia, site.domain)
                self._write(static_root / "500" / f"{site.domain}.html", html)
                count += 1
            except Exception:
                # Best-effort artefakt: jedna wadliwa domena nie może wywalić
                # generacji pozostałych. Loguj pełny traceback i kontynuuj.
                self.stderr.write(
                    self.style.ERROR(
                        f"Nie udało się wygenerować strony 500 dla domeny "
                        f"{site.domain!r}:"
                    )
                )
                traceback.print_exc()
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Wygenerowano stronę 500: generyczną + {count} per-domena "
                f"w {static_root}"
            )
        )

    def _render_500(self, uczelnia, host):
        """Wyrenderuj finalny HTML strony 500 dla danej uczelni i hosta.

        ``uczelnia`` może być ``None`` (→ neutralna „niezdefiniowana uczelnia").
        ``host`` trafia do ``SERVER_NAME`` fałszywego requestu — musi być w
        ALLOWED_HOSTS, bo procesory/template mogą wołać ``get_host()``.
        """
        factory = RequestFactory()
        request = factory.get("/", SERVER_NAME=host)
        request.user = AnonymousUser()
        request.session = {}
        # KLUCZ: ustaw uczelnię z góry. ``Uczelnia.objects.get_for_request``
        # zwraca ``request._uczelnia`` ZANIM sięgnie po ``get_host()`` w
        # ``_site_dla_requestu`` — to jednocześnie wymusza właściwy branding
        # per-domena i uodparnia command na DisallowedHost (testserver).
        request._uczelnia = uczelnia

        context = {}
        context.update(bpp_configuration(request))
        context.update(global_nav_user(request))
        context.update(google_analytics(request))
        context.update(microsoft_auth_status(request))
        context.update(testing(request))
        context["messages"] = []
        context["password_change_required"] = False
        # Ustaw cookielaw na zaakceptowane, by nie pokazywać bannera cookies.
        context["cookielaw"] = {"notset": False, "accepted": True, "rejected": False}

        # Context processor ``uczelnia`` trzyma globalny cache ``b"bpp_uczelnia"``
        # NIE rozróżniający domen — przy seryjnym renderowaniu per-domena
        # pierwsza uczelnia „zatrułaby" kolejne strony. Czyść przed każdym
        # renderem, by processor policzył uczelnię z ``request._uczelnia``.
        cache.delete(b"bpp_uczelnia")

        template = loader.get_template("50x.html")
        rendered_html = template.render(context, request)
        rendered_html = rendered_html.replace("</body>", CLEANUP_SCRIPT + "</body>")

        warning = f"""<!--
This file was automatically generated by: python src/manage.py generate_500_page
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

WARNING: DO NOT EDIT THIS FILE MANUALLY!
This file is auto-generated and any manual changes will be lost when regenerated.
To modify this page, edit src/bpp/templates/50x.html and run the generate_500_page command again.
-->
"""
        final_html = warning + rendered_html

        # Minify HTML, usuwając zbędne białe znaki.
        return html_minify(
            final_html,
            keep_comments=True,
            keep_closing_tags=True,
            keep_html_and_head_opening_tags=True,
            keep_input_type_text_attr=True,
        )

    @staticmethod
    def _write(path, html):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")

    @staticmethod
    def _valid_host():
        """Pierwszy konkretny host z ALLOWED_HOSTS (get_host() go waliduje).

        Pomija wildcardy: ``"*"`` oraz subdomenowe ``".example.com"`` nie są
        poprawną wartością nagłówka ``Host:``.
        """
        for h in settings.ALLOWED_HOSTS:
            if h and h != "*" and not h.startswith(".") and "*" not in h:
                return h
        return "localhost"
