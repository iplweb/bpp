# Reorganizacja dokumentacji (MkDocs site) — design

**Data:** 2026-06-01
**Branch/worktree:** `docs/restructure` → `~/Programowanie/bpp-docs-restructure`
**Zakres:** publikowany site MkDocs (`docs/`). Bez zmian w prozie treści,
bez Diátaxis, bez `mkdocs-redirects`.

## Problem

Site ma sekcje audytorialne tylko w `nav` (`mkdocs.yml`) — **filesystem jest
płaski**: 24 pliki `.md` w korzeniu `docs/`, bez podkatalogów. Dodatkowo:

1. **Zerwany kontrakt dev-docs.** `CLAUDE.md` linkuje do
   `docs/CODEBASE_MAP.md`, `docs/COMMANDS.md`, `docs/CSS_BUILD.md` — pliki
   **nie istnieją** (skasowane w commicie `6c8e383e8 "Cleanups"`; treść
   żyje w historii git: 557 / 117 / 72 linii).
2. **Niespójne nazewnictwo.** PL snake_case dla user-docs
   (`edycja_autor.md`) vs SCREAMING_SNAKE EN dla dev/ops
   (`CHANNELS_BROADCAST_FLAKE.md`, `MACOS_WEASYPRINT.md`).
3. **„Operacje" to grab-bag** — miesza dev-troubleshooting z polityką
   bezpieczeństwa.
4. **„Funkcje zaawansowane" dzieli po trudności, nie po odbiorcy.**
5. **Artefakty migracji RST→MkDocs.** 15 nagłówków RST `~~~~`
   zostało zescape'owanych do dosłownych tyld (`\~\~\~…`) w `api.md` (10)
   i `usage_admin.md` (5) — patrz np.
   https://iplweb.github.io/bpp/api/#api-dla-raportów-slotu---uczelnia
   Te podsekcje przestały być nagłówkami → wypadły z TOC stron. Dodatkowo
   3 linie zescape'owanych gwiazdek (`\*`) w `usage_admin.md` do weryfikacji.

## Decyzje (potwierdzone z userem)

- **Approach A — foldery per-odbiorca**, 1:1 z sekcjami `nav`.
- **Wszystkie slugi po polsku**, kebab-case (web-standard).
- **Bez redirectów** — site świeżo zmigrowany z RTD, ruch minimalny;
  stare URL-e mogą wygasnąć.
- **Dev/agent docs PUBLIKOWANE** jako osobna sekcja „Dla deweloperów
  i agentów" (jawnie oznaczona: to dokumentacja dla **dewelopera I agenta**,
  nie dla użytkownika końcowego).
- `sloty`, `raporty-rankingi` → **użytkownik**. `pbn` (integracja),
  `advanced` → **administrator**.
- `readme.md` (10 linii, „zobacz README na GitHub") — **usunąć z nav**,
  treść wchłania `index.md`.
- `DJANGO_5_2_UPGRADE.md` (skasowany, nielinkowany, jednorazowy) —
  **zostaje skasowany**.

## Docelowa struktura

```
docs/
  index.md                         hub z kartami per-odbiorca
  uzytkownik/
    uczelnia.md                    ← edycja_uczelnia.md
    jednostki.md                   ← edycja_jednostka.md
    autorzy.md                     ← edycja_autor.md
    wydawnictwa.md                 ← edycja_wydawnictwo.md
    wyszukiwanie-redagowanie.md    ← wyszukiwanie_redagowanie.md
    raporty-rankingi.md            ← raporty_rankingi.md
    sloty.md                       ← sloty.md
  administrator/
    ogolna.md                      ← usage_admin.md
    importer-publikacji.md         ← importer_publikacji.md
    import-pracownikow.md          ← import_pracownikow.md
    zglaszanie-publikacji.md       ← zglos_publikacje.md
    konfiguracja-pbn.md            ← konfiguracja_pbn.md
    integracja-pbn.md              ← pbn.md
    zaawansowane.md                ← advanced.md
  api/
    index.md                       ← api.md
  deweloper/
    index.md                       NOWY — landing, banner „dla dev+agent"
    mapa-kodu.md                   ← restore CODEBASE_MAP.md
    polecenia.md                   ← restore COMMANDS.md
    budowanie-css.md               ← restore CSS_BUILD.md
    rozwijanie-projektu.md         ← contributing.md
    weasyprint-macos.md            ← MACOS_WEASYPRINT.md
    testy-channels-broadcast.md    ← CHANNELS_BROADCAST_FLAKE.md
  bezpieczenstwo/
    polityka.md                    ← SECURITY.md
    praktyki.md                    ← SECURITY_PRACTICES.md
  o-projekcie/
    autorzy.md                     ← authors.md
    historia.md                    ← history.md
```

Slugi dev-sekcji są polskie tam, gdzie to naturalne; żargon techniczny
(`channels`, `broadcast`, `weasyprint`, `css`) zachowany jako rozpoznawalny
termin w obrębie polskiego slugu.

## Plan pracy (workstreamy)

### WS1 — Przenosiny plików (`git mv`)
- `git mv` każdego pliku do docelowego folderu+nazwy (zachowuje historię).
- Utworzyć foldery: `uzytkownik administrator api deweloper bezpieczenstwo
  o-projekcie`.

### WS2 — Restore dev-docs
- `git show 6c8e383e8^:docs/CODEBASE_MAP.md > docs/deweloper/mapa-kodu.md`
  (analogicznie COMMANDS, CSS_BUILD).
- `mapa-kodu.md`: dodać banner na górze — „Plik generowany maszynowo
  (Cartographer). NIE edytować ręcznie — regenerować." Frontmatter
  `last_mapped` zostaje jako znacznik świeżości.

### WS3 — `deweloper/index.md` (nowy)
- Krótki landing: dla kogo (deweloper + agent AI), czym się różni od
  reszty docs, link do `CLAUDE.md` w repo, spis stron dev-sekcji.

### WS4 — Naprawa artefaktów migracji RST
- 15× `\~\~\~…` → usunąć linię tyld, podnieść linię nad nią do `###`
  (poziom: podsekcja pod `##` → `h3`). Pliki: `api/index.md`,
  `administrator/ogolna.md`.
- Zweryfikować 3× `\*` w `administrator/ogolna.md` — escape zamierzony
  czy resztka RST emphasis; naprawić jeśli resztka.

### WS5 — Naprawa linków wewnętrznych
- Zaktualizować wszystkie relatywne linki między stronami (np. lista
  w `index.md`, cross-refy) na nowe ścieżki folderowe.
- `grep -rnE '\]\([a-z_]+\.md' docs/` żeby znaleźć stare linki.

### WS6 — `mkdocs.yml`
- Przepisać `nav` na nową strukturę (6 sekcji + index + sekcja
  „Dla deweloperów i agentów").
- `exclude_docs`: nadal wyklucza `superpowers/`; dev-docs NIE są
  wykluczone (mają być publikowane).

### WS7 — `CLAUDE.md`
- Zaktualizować 3 linki: `docs/CODEBASE_MAP.md` → `docs/deweloper/mapa-kodu.md`,
  `docs/COMMANDS.md` → `docs/deweloper/polecenia.md`,
  `docs/CSS_BUILD.md` → `docs/deweloper/budowanie-css.md`.

## Kryterium akceptacji

- `mkdocs build --strict` przechodzi (zero broken links / nav warnings).
  To główna brama — `--strict` zamienia zerwany link w błąd builda.
- `grep -rE '\\~\\~|\\\*\\\*' docs/` nie zwraca artefaktów RST.
- `grep -rE 'CODEBASE_MAP\.md|COMMANDS\.md|CSS_BUILD\.md' CLAUDE.md`
  zwraca tylko nowe ścieżki `docs/deweloper/…`.
- Wszystkie 3 dev-docs istnieją i są w `nav`.
- Wizualny sanity-check renderu strony `api/` (znikły tyldy, wróciły
  nagłówki h3 + TOC).

## Poza zakresem

Redirecty, przepisywanie prozy treści, Diátaxis, tłumaczenie dev-docs,
regeneracja `mapa-kodu.md` (tylko restore + banner).
