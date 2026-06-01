"""Tolerancyjny ManifestStaticFilesStorage dla BPP (issue #269).

`ManifestStaticFilesStorage` hashuje każdy `{% static %}` z osobna
(`name.<content-hash>.ext`) i przepisuje odwołania `url(...)` /
`sourceMappingURL` wewnątrz CSS/JS na wersje hashowane. Dzięki temu
cache-bustuje cały long-tail statyków — w tym to, czego `{% compress %}`
nie umie: pliki z atrybutem `defer`/`async` (compress sklejałby je w jeden
synchroniczny plik), dane ładowane `fetch`-em (np. `bpp/js/Polish.json`)
oraz vendored skrypty (`multiseek/js/multiseek.js`, `djangoql`, ...).

Problem z vanilla wersją: przerywa `collectstatic` przy pierwszym
nierozwiązywalnym odwołaniu — `url(...)`/`sourceMappingURL` wskazującym na
plik, którego nie ma w zebranych statykach. W BPP to ~132 odwołania
(sprite'y `.png` grappelli/jqueryui w adminie + sourcemapy `.map` foundation),
których targetów fizycznie nie da się zahashować, bo ich nie ma w STATIC_ROOT.
`manifest_strict=False` tu NIE pomaga — dotyczy runtime'owych lookupów
`.url()`, a crash leci na etapie build-time `post_process`, którego ta flaga
nie obejmuje.

Subklasa przechwytuje ten `ValueError` w `hashed_name` i zostawia odwołanie
pod nazwą oryginalną (niezahashowaną) zamiast wywalać build. Te pliki serwują
się dokładnie tak jak dziś — bez cache-bustingu, ale działają; i tak ~nigdy
się nie zmieniają między wydaniami.
"""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class TolerantManifestStaticFilesStorage(ManifestStaticFilesStorage):
    # Runtime: brakujący wpis w manifeście → nie rzucaj "Missing staticfiles
    # manifest entry". Potrzebne dla 132 vendored-refów niezahashowanych na
    # buildzie. UWAGA: samo `manifest_strict=False` NIE wystarcza dla dev/testów
    # bez collectstatic — vanilla fallback liczy wtedy hash w locie (martwy URL,
    # bo hashowanej kopii nie ma na dysku). Pod pytest `DEBUG=False`, więc
    # short-circuit DEBUG w `.url()` też nie ratuje. Realnie chroni nas dopiero
    # override `stored_name` poniżej.
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Build-time tolerancja: nierozwiązywalne odwołanie (vendored .map
            # / sprite, którego targetu nie ma w zebranych statykach). Zostaw
            # nazwę oryginalną zamiast przerywać collectstatic — issue #269.
            return name

    def stored_name(self, name):
        # Runtime lookup używany przez `url()`. Gdy manifestu NIE MA w ogóle
        # (`staticfiles.json` nie istnieje → `hashed_files` puste — dev/testy
        # bez collectstatic, albo stary `staticroot` sprzed Manifestu),
        # vanilla `ManifestFilesMixin.stored_name` z `manifest_strict=False`
        # liczy content-hash w locie przez `hashed_name()`. Dla pliku, który
        # PRZYPADKIEM leży w STATIC_ROOT, daje to `name.<hash>.ext` — nazwę,
        # której fizycznej kopii nikt nigdy nie wygenerował (stary
        # collectstatic zrobił tylko nie-hashowaną). URL jest martwy:
        # django-compressor rzuca `UncompressableFileError`, a bezpośredni GET
        # (webtest) dostaje 404. Manifest jest jedynym źródłem prawdy dla
        # hashy — bez niego serwujemy nazwę oryginalną; realny plik źródłowy
        # zaserwuje finder / runserver / whitenoise.
        #
        # Gating na PUSTY manifest (nie per-wpis) jest celowo wąski: gdy
        # collectstatic wygenerował manifest (produkcja, `.baked`),
        # `hashed_files` jest niepuste → delegujemy do vanilla bez zmian, więc
        # cache-busting długiego ogona działa 1:1 jak dotąd. Build-time
        # `post_process` używa osobnej ścieżki (`_stored_name`, force=True),
        # więc ten override go nie dotyka.
        if not self.hashed_files:
            return name
        return super().stored_name(name)
