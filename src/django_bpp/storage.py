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
    # Runtime: brakujący wpis w manifeście → zwróć nazwę nie-hashowaną zamiast
    # rzucać "Missing staticfiles manifest entry". Chroni dev/testy bez
    # collectstatic (choć tam i tak działa short-circuit DEBUG w `.url()`)
    # oraz 132 vendored-refy, które zostały niezahashowane na buildzie.
    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Build-time tolerancja: nierozwiązywalne odwołanie (vendored .map
            # / sprite, którego targetu nie ma w zebranych statykach). Zostaw
            # nazwę oryginalną zamiast przerywać collectstatic — issue #269.
            return name
